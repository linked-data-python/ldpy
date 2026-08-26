"""Serveur LSP mince pour .ldpy — jalon 1 : diagnostics natifs.

Architecture (fiche lsp/101) : ce serveur ne fork PAS pylsp. Il transpile à
chaque frappe (didOpen/didChange), publie les diagnostics du transpileur, et
maintient les .py fantômes + language maps qui serviront, au jalon 2, à
déléguer les autres requêtes (completion, hover...) à un vrai serveur Python
avec traduction des positions."""

try:
    from pygls.server import LanguageServer
    from lsprotocol import types as lsp
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "pygls est requis pour le serveur LSP : pip install "
        "'linked-data-python[lsp]' (détail : %s)" % e)

from ldpy.transpiler import transpile, LdpySyntaxError

server = LanguageServer("ldpy-lsp", "0.1.0")

# état par document ouvert : uri -> TranspileResult
RESULTS = {}


def _diagnostics(source, uri):
    diags = []
    try:
        result = transpile(source, uri)
    except LdpySyntaxError as e:
        rng = lsp.Range(start=lsp.Position(line=e.line, character=e.col),
                        end=lsp.Position(line=e.line, character=e.col + 1))
        diags.append(lsp.Diagnostic(
            range=rng, message=e.msg, source="ldpy",
            severity=lsp.DiagnosticSeverity.Error))
        RESULTS.pop(uri, None)
        return diags
    RESULTS[uri] = result
    for w in result.warnings:
        rng = lsp.Range(start=lsp.Position(line=w.line, character=w.col),
                        end=lsp.Position(line=w.line, character=w.col + 1))
        diags.append(lsp.Diagnostic(
            range=rng, message=w.message, source="ldpy",
            severity=lsp.DiagnosticSeverity.Warning))
    return diags


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls, params):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.publish_diagnostics(doc.uri, _diagnostics(doc.source, doc.uri))


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.publish_diagnostics(doc.uri, _diagnostics(doc.source, doc.uri))


@server.feature(lsp.TEXT_DOCUMENT_HOVER)
def hover(ls, params):
    """Hover natif : IRI résolue sous le curseur (îlots iri/pname)."""
    uri = params.text_document.uri
    result = RESULTS.get(uri)
    if result is None:
        return None
    line, col = params.position.line, params.position.character
    for seg in result.map.segments:
        if seg.src is None or not seg.kind.startswith("island:"):
            continue
        sl0, sc0, sl1, sc1 = seg.src
        if (sl0, sc0) <= (line, col) < (sl1, sc1) or \
                (sl0 == line == sl1 and sc0 <= col < sc1):
            gl0, gc0, gl1, gc1 = seg.gen
            gen_excerpt = _excerpt(result.code, seg.gen)
            return lsp.Hover(contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value="**îlot %s**\n```python\n%s\n```" % (
                    seg.kind.split(":", 1)[1], gen_excerpt)))
    return None


def _excerpt(code, gen_range):
    gl0, gc0, gl1, gc1 = gen_range
    lines = code.split("\n")[gl0:gl1 + 1]
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0][gc0:gc1]
    lines[0] = lines[0][gc0:]
    lines[-1] = lines[-1][:gc1]
    return "\n".join(lines)


def main():
    server.start_io()


if __name__ == "__main__":
    main()
