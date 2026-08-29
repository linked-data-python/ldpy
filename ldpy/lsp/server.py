"""Serveur LSP Linked-Data Python — mince, par request-forwarding.

Architecture (voir docs/explanation/tooling.md) :

- ZERO dependency: home-made JSON-RPC/framing (ldpy/lsp/rpc.py), no pygls.
- NATIVE layer: transpiler diagnostics (errors + scope warnings), hover on
  the islands, semantic tokens for the islands (a precise complement to the
  coloration TextMate, docs/how-to/use-vscode.md).
- DELEGATED layer: for every .ldpy, a Python shadow document is kept up to
  date on a REAL Python language server (pylsp, subprocess, not forked);
  completion, definition, references, signatureHelp — and hover outside an
  island — are forwarded to it with positions translated through the
  LanguageMap, answers translated back (shadow URIs in Locations included).
  Without pylsp installed, the server works in native-only mode.

Lancement : python -m ldpy.lsp [--backend pylsp|none]
"""

import sys

from ldpy.transpiler import transpile, LdpySyntaxError
from ldpy.lsp.rpc import Endpoint, read_message, RpcClosed
from ldpy.lsp import translate as tr
from ldpy.lsp import hover as hv
from ldpy.transpiler.linemap import snap_breakpoint_lines


def fmt_default():
    """Default line length, without importing black."""
    from ldpy.formatter import DEFAULT_LINE_LENGTH
    return DEFAULT_LINE_LENGTH


def _ldpy_version():
    """The installed package version — never duplicated here."""
    from ldpy import __version__
    return __version__

def _setting(settings, *path, default=None):
    """Read a nested setting, whether the client sends the whole tree
    (`{"ldpy": {"hover": ...}}`) or just our section (`{"hover": ...}`).
    Clients differ on this and both spellings are legitimate."""
    for root in (settings, (settings or {}).get("ldpy")):
        node = root
        for key in path:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if node is not None:
            return node
    return default


FORWARDED = {
    "textDocument/completion",
    "textDocument/definition",
    "textDocument/references",
    "textDocument/signatureHelp",
    "textDocument/documentHighlight",
}


class Document:
    """An open .ldpy document: text, version, transpilation result."""

    __slots__ = ("uri", "text", "version", "result",
                 "native_diags", "py_diags")

    def __init__(self, uri, text, version):
        self.uri = uri
        self.text = text
        self.version = version
        self.result = None          # TranspileResult, or None on error
        self.native_diags = []      # diagnostics du transpileur
        self.py_diags = []          # backend diagnostics, already translated


class LdpyServer:
    """The language server: native layer plus delegation to the Python backend."""

    def __init__(self, reader, writer, backend="pylsp", backend_argv=None,
                 line_length=None):
        self.endpoint = Endpoint(reader, writer)
        self.docs = {}              # uri -> Document
        self.backend_kind = backend
        self.backend_argv = backend_argv
        self.backend = None
        self.line_length = line_length
        # `ldpy.hover.showTranslation` — the generated Python in the hover.
        # On by default: it is the point of the feature (record vscode/108).
        self.hover_translation = True
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
        """Transpile, publish the diagnostics, sync the shadow."""
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
        """The backend's Python diagnostics, re-projected onto the .ldpy.
        Those landing on synthetic text (the prelude) are dropped, and so is
        everything a style linter says about the shadow: it judges GENERATED
        code (record vscode/107). The backend is asked not to compute style
        at all (SHADOW_SETTINGS); this filter covers a backend that does not
        honour the configuration."""
        from ldpy.lsp.backend import STYLE_PLUGINS
        doc = self.docs.get(tr.unshadow_uri(shadow))
        if doc is None or doc.result is None:
            return
        lmap = doc.result.map
        kept = []
        for d in diags:
            if d.get("source") in STYLE_PLUGINS:
                continue
            rng = d.get("range", {})
            start = tr.pos_to_ldpy(lmap, rng.get("start", {}))
            if start is None:
                continue                     # prelude, or off the map
            end = tr.pos_to_ldpy(lmap, rng.get("end", {})) or start
            d = dict(d, range={"start": start, "end": end},
                     source=d.get("source") or "python")
            kept.append(d)
        doc.py_diags = kept
        self._publish(doc)

    # ------------------------------------------------------------- boucle

    def serve(self):
        """Main loop: read stdin, dispatch, answer; leave on exit."""
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

    # ------------------------------------------------------------ dispatch

    def _dispatch(self, method, params, rid):
        if method == "initialize":
            self._apply_settings(params.get("initializationOptions"))
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
                    # our own extension, announced so the client can detect
                    # it instead of assuming it (record vscode/103)
                    "experimental": {"ldpyBreakpointLines": True},
                },
                "serverInfo": {"name": "ldpy-lsp", "version": _ldpy_version()},
            }
        if method == "workspace/didChangeConfiguration":
            # a live toggle: no restart, and no re-transpilation either —
            # only the rendering of the next hover changes
            self._apply_settings(params.get("settings"))
            return None
        if method in ("initialized", "$/setTrace", "$/cancelRequest"):
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
            # Snap breakpoint lines onto those that really bind (inside a
            # multi-line island -> the island's first line). The extension
            # then moves the dot, instead of leaving the user with a
            # breakpoint that never fires.
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
        """The formatter delegates Python to black (extra `[format]`): we
        only announce the capability when it is actually available."""
        try:
            from ldpy.formatter import _black
            _black()
            return True
        except Exception:
            return False

    def _format(self, params):
        """`textDocument/formatting`: one edit replacing everything.

        A faulty document is not formatted — we then return NO edit rather
        than invented text; the diagnostics already say why."""
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

    def _apply_settings(self, settings):
        """Client configuration, from `initialize` or a later change."""
        value = _setting(settings, "hover", "showTranslation")
        if isinstance(value, bool):
            self.hover_translation = value

    def _gen_text(self, doc, gen):
        """The generated Python covered by a map range."""
        gl0, gc0, gl1, gc1 = gen
        lines = doc.result.code.split("\n")[gl0:gl1 + 1]
        if not lines:
            return ""
        if len(lines) == 1:
            return lines[0][gc0:gc1]
        lines[0] = lines[0][gc0:]
        lines[-1] = lines[-1][:gc1]
        return "\n".join(lines)

    def _hover(self, params):
        """Native on an island, delegated on the Python around it.

        Inside an island we answer on the SMALLEST described element under
        the cursor (record vscode/108): hovering a prefixed name in a
        forty-line `g{ }` should explain that name, not dump the whole
        translated block."""
        doc = self.docs.get(params["textDocument"]["uri"])
        if doc is None or doc.result is None:
            return None
        pos = params["position"]
        seg = tr.island_at(doc.result.map, pos["line"], pos["character"])
        if seg is None:
            return self._forward("textDocument/hover", params)
        kind, src, code = tr.island_target(seg, pos["line"],
                                           pos["character"])
        if code is None:
            code = self._gen_text(doc, seg.gen)
        width = self.line_length or fmt_default()
        sl0, sc0, sl1, sc1 = src
        return {"contents": {"kind": "markdown",
                             "value": hv.render(kind, code, width,
                                                self.hover_translation)},
                "range": {"start": {"line": sl0, "character": sc0},
                          "end": {"line": sl1, "character": sc1}}}

    # --------------------------------------------------------- delegation

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
                        help="delegated Python server (default: pylsp)")
    parser.add_argument("--line-length", type=int, default=None,
                        help="formatter line length "
                             "(default: black's own)")
    args = parser.parse_args(argv)
    server = LdpyServer(sys.stdin.buffer, sys.stdout.buffer,
                        backend=args.backend, line_length=args.line_length)
    server.serve()


if __name__ == "__main__":
    main()
