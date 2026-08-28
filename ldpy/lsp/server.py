"""Serveur LSP Linked-Data Python — mince, par request-forwarding.

Architecture (voir docs/explanation/tooling.md) :

- ZÉRO dépendance : JSON-RPC/framing maison (ldpy/lsp/rpc.py), pas de pygls.
- Couche NATIVE : diagnostics du transpileur (erreurs + warnings de portée),
  hover sur les îlots, semantic tokens des îlots (complément précis de la
  coloration TextMate, docs/how-to/use-vscode.md).
- Couche DÉLÉGUÉE : pour chaque .ldpy, un document fantôme Python est
  maintenu chez un VRAI serveur LSP Python (pylsp, non forké, sous-processus) ;
  completion, definition, references, signatureHelp — et hover hors îlot —
  lui sont transmis avec positions traduites par le LanguageMap, réponses
  re-traduites au retour (y compris les URIs d'ombre dans les Locations).
  Sans pylsp installé, le serveur fonctionne en mode natif seul.

Lancement : python -m ldpy.lsp [--backend pylsp|none]
"""

import sys

from ldpy.transpiler import transpile, LdpySyntaxError
from ldpy.lsp.rpc import Endpoint, read_message, RpcClosed
from ldpy.lsp import translate as tr
from ldpy.transpiler.linemap import snap_breakpoint_lines


def fmt_default():
    """Longueur de ligne par défaut, sans importer black."""
    from ldpy.formatter import DEFAULT_LINE_LENGTH
    return DEFAULT_LINE_LENGTH

FORWARDED = {
    "textDocument/completion",
    "textDocument/definition",
    "textDocument/references",
    "textDocument/signatureHelp",
    "textDocument/documentHighlight",
}


class Document:
    """Un document .ldpy ouvert : texte, version, résultat de transpilation."""

    __slots__ = ("uri", "text", "version", "result",
                 "native_diags", "py_diags")

    def __init__(self, uri, text, version):
        self.uri = uri
        self.text = text
        self.version = version
        self.result = None          # TranspileResult ou None si erreur
        self.native_diags = []      # diagnostics du transpileur
        self.py_diags = []          # diagnostics du backend, déjà traduits


class LdpyServer:
    """Le serveur LSP : couche native + délégation au backend Python."""

    def __init__(self, reader, writer, backend="pylsp", backend_argv=None,
                 line_length=None):
        self.endpoint = Endpoint(reader, writer)
        self.docs = {}              # uri -> Document
        self.backend_kind = backend
        self.backend_argv = backend_argv
        self.backend = None
        self.line_length = line_length
        self._shutdown = False

    # ------------------------------------------------------------ backend

    def _ensure_backend(self, root_uri=None):
        if self.backend is not None or self.backend_kind == "none":
            return self.backend
        try:
            from ldpy.lsp.backend import PythonBackend
            self.backend = PythonBackend(argv=self.backend_argv,
                                         root_uri=root_uri).start()
            self.backend.diagnostics_handler = self._on_backend_diags
        except Exception as e:
            print("ldpy-lsp: backend indisponible (%s) — mode natif seul" % e,
                  file=sys.stderr)
            self.backend_kind = "none"
        return self.backend

    # ---------------------------------------------------------- documents

    def _maps_by_uri(self):
        return {u: d.result.map for u, d in self.docs.items() if d.result}

    def _sync(self, doc, opened):
        """Transpile, publie les diagnostics, synchronise l'ombre."""
        diags = []
        try:
            doc.result = transpile(doc.text, doc.uri)
        except LdpySyntaxError as e:
            doc.result = None
            diags.append({
                "range": {"start": {"line": e.line, "character": e.col},
                          "end": {"line": e.line, "character": e.col + 1}},
                "severity": 1, "source": "ldpy", "message": e.msg})
        else:
            for w in doc.result.warnings:
                diags.append({
                    "range": {"start": {"line": w.line, "character": w.col},
                              "end": {"line": w.line, "character": w.col + 1}},
                    "severity": 2, "source": "ldpy", "message": w.message})
        doc.native_diags = diags
        if doc.result is None:
            doc.py_diags = []
        self._publish(doc)
        if doc.result and self.backend:
            su = tr.shadow_uri(doc.uri)
            if opened:
                self.backend.open_shadow(su, doc.result.code, doc.version)
            else:
                self.backend.change_shadow(su, doc.result.code, doc.version)

    def _publish(self, doc):
        self.endpoint.notify(
            "textDocument/publishDiagnostics",
            {"uri": doc.uri,
             "diagnostics": doc.native_diags + doc.py_diags})

    def _on_backend_diags(self, shadow, diags):
        """Diagnostics Python du backend : re-projetés sur le .ldpy.
        Ceux qui tombent sur du texte synthétique (prélude) sont écartés."""
        doc = self.docs.get(tr.unshadow_uri(shadow))
        if doc is None or doc.result is None:
            return
        lmap = doc.result.map
        kept = []
        for d in diags:
            rng = d.get("range", {})
            start = tr.pos_to_ldpy(lmap, rng.get("start", {}))
            if start is None:
                continue                     # prélude ou hors carte
            end = tr.pos_to_ldpy(lmap, rng.get("end", {})) or start
            d = dict(d, range={"start": start, "end": end},
                     source=d.get("source") or "python")
            kept.append(d)
        doc.py_diags = kept
        self._publish(doc)

    # ------------------------------------------------------------- boucle

    def serve(self):
        """Boucle principale : lit stdin, répartit, répond ; sort sur exit."""
        while True:
            try:
                msg = read_message(self.endpoint.reader)
            except RpcClosed:
                break
            if "id" in msg and ("result" in msg or "error" in msg):
                self.endpoint.feed_response(msg)
                continue
            method = msg.get("method", "")
            rid = msg.get("id")
            params = msg.get("params") or {}
            try:
                if method == "exit":
                    break
                result = self._dispatch(method, params, rid)
                if rid is not None:
                    self.endpoint.respond(rid, result=result)
            except Exception as e:                       # jamais fatal
                if rid is not None:
                    self.endpoint.respond(
                        rid, error={"code": -32603, "message": str(e)})
        if self.backend:
            self.backend.stop()

    # --------------------------------------------------------- répartition

    def _dispatch(self, method, params, rid):
        if method == "initialize":
            self._ensure_backend(params.get("rootUri"))
            return {
                "capabilities": {
                    "textDocumentSync": 1,               # complet
                    "hoverProvider": True,
                    "completionProvider": {
                        "triggerCharacters": [".", ":", "<", "?", "/"]},
                    "definitionProvider": True,
                    "documentFormattingProvider": self._can_format(),
                    "referencesProvider": True,
                    "signatureHelpProvider": {
                        "triggerCharacters": ["(", ","]},
                    "semanticTokensProvider": {
                        "legend": {"tokenTypes": tr.TOKEN_TYPES,
                                   "tokenModifiers": []},
                        "full": True},
                    # extension maison, annoncée pour que le client puisse
                    # la détecter au lieu de la supposer (fiche vscode/103)
                    "experimental": {"ldpyBreakpointLines": True},
                },
                "serverInfo": {"name": "ldpy-lsp", "version": "0.2.0"},
            }
        if method in ("initialized", "workspace/didChangeConfiguration",
                      "$/setTrace", "$/cancelRequest"):
            return None
        if method == "shutdown":
            self._shutdown = True
            return None

        if method == "textDocument/didOpen":
            td = params["textDocument"]
            doc = Document(td["uri"], td["text"], td.get("version", 1))
            self.docs[doc.uri] = doc
            self._sync(doc, opened=True)
            return None
        if method == "textDocument/didChange":
            td = params["textDocument"]
            doc = self.docs.get(td["uri"])
            if doc is None:
                return None
            doc.text = params["contentChanges"][-1]["text"]
            doc.version = td.get("version", doc.version + 1)
            self._sync(doc, opened=False)
            return None
        if method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            self.docs.pop(uri, None)
            if self.backend:
                self.backend.close_shadow(tr.shadow_uri(uri))
            self.endpoint.notify("textDocument/publishDiagnostics",
                                 {"uri": uri, "diagnostics": []})
            return None

        if method == "textDocument/formatting":
            return self._format(params)

        if method == "ldpy/breakpointLines":
            # Rabat des lignes de points d'arrêt sur celles qui se lient
            # vraiment (intérieur d'un îlot multiligne -> début de l'îlot).
            # L'extension déplace alors la pastille, au lieu de laisser
            # l'utilisateur devant un point d'arrêt qui ne se déclenche pas.
            lines = list(params.get("lines") or [])
            doc = self.docs.get(params["textDocument"]["uri"])
            if doc is None or doc.result is None:
                return {"lines": lines}
            return {"lines": snap_breakpoint_lines(doc.result.map, lines)}

        if method == "textDocument/semanticTokens/full":
            doc = self.docs.get(params["textDocument"]["uri"])
            if doc is None or doc.result is None:
                return {"data": []}
            return {"data": tr.semantic_tokens(doc.result.map)}

        if method == "textDocument/hover":
            return self._hover(params)

        if method in FORWARDED:
            return self._forward(method, params)

        if rid is not None:
            return None
        return None

    # ------------------------------------------------------------- natives

    def _can_format(self):
        """Le formateur délègue le Python à black (extra `[format]`) : on
        n'annonce la capacité que si elle est réellement disponible."""
        try:
            from ldpy.formatter import _black
            _black()
            return True
        except Exception:
            return False

    def _format(self, params):
        """`textDocument/formatting` : un seul edit qui remplace tout.

        Un document fautif ne se formate pas — on ne rend alors AUCUN edit
        plutôt qu'un texte inventé ; les diagnostics disent déjà pourquoi."""
        doc = self.docs.get(params["textDocument"]["uri"])
        if doc is None:
            return None
        from ldpy.formatter import format_source, FormatterUnavailable
        opts = params.get("options") or {}
        width = (self.line_length
                 or opts.get("ldpyLineLength")
                 or fmt_default())
        try:
            new = format_source(doc.text, doc.uri, int(width))
        except (LdpySyntaxError, FormatterUnavailable):
            return None
        if new == doc.text:
            return []
        lines = doc.text.split("\n")
        end = {"line": len(lines) - 1, "character": len(lines[-1])}
        return [{"range": {"start": {"line": 0, "character": 0}, "end": end},
                 "newText": new}]

    def _hover(self, params):
        doc = self.docs.get(params["textDocument"]["uri"])
        if doc is None or doc.result is None:
            return None
        pos = params["position"]
        seg = tr.island_at(doc.result.map, pos["line"], pos["character"])
        if seg is not None:
            gl0, gc0, gl1, gc1 = seg.gen
            lines = doc.result.code.split("\n")[gl0:gl1 + 1]
            if len(lines) == 1:
                excerpt = lines[0][gc0:gc1]
            else:
                lines[0] = lines[0][gc0:]
                lines[-1] = lines[-1][:gc1]
                excerpt = "\n".join(lines)
            sl0, sc0, sl1, sc1 = seg.src
            return {"contents": {"kind": "markdown", "value":
                    "**îlot %s**\n```python\n%s\n```" % (
                        seg.kind.split(":", 1)[1], excerpt)},
                    "range": {"start": {"line": sl0, "character": sc0},
                              "end": {"line": sl1, "character": sc1}}}
        return self._forward("textDocument/hover", params)

    # ---------------------------------------------------------- délégation

    def _forward(self, method, params):
        doc = self.docs.get(params.get("textDocument", {}).get("uri", ""))
        if doc is None or doc.result is None or not self.backend \
                or not self.backend.alive():
            return None
        lmap = doc.result.map
        fwd = dict(params)
        fwd["textDocument"] = {"uri": tr.shadow_uri(doc.uri)}
        if "position" in params:
            p = tr.pos_to_py(lmap, params["position"])
            if p is None:
                return None
            fwd["position"] = p
        raw = self.backend.forward(method, fwd)
        return tr.translate_result(raw, lmap, self._maps_by_uri())


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="ldpy.lsp")
    parser.add_argument("--backend", default="pylsp",
                        choices=["pylsp", "none"],
                        help="serveur Python délégué (défaut : pylsp)")
    parser.add_argument("--line-length", type=int, default=None,
                        help="longueur de ligne du formateur "
                             "(défaut : celle de black)")
    args = parser.parse_args(argv)
    server = LdpyServer(sys.stdin.buffer, sys.stdout.buffer,
                        backend=args.backend, line_length=args.line_length)
    server.serve()


if __name__ == "__main__":
    main()
