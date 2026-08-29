"""Serveur LSP bout-en-bout : un client minimal (écrit ici) parle au vrai
`python -m ldpy.lsp` en sous-processus, avec un VRAI pylsp comme backend.

Chaque test vérifie une capacité différente ; le point dur est toujours le
même : les positions franchissent DEUX fois le language map (requête .ldpy
-> ombre .py, réponse .py -> .ldpy) avec le décalage du prélude."""

import os
import subprocess
import sys
import time

import pytest

from ldpy.lsp.rpc import read_message, write_message

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HAS_PYLSP = subprocess.run(
    [sys.executable, "-c", "import pylsp"], capture_output=True).returncode == 0

DOC = """\
@prefix ex: <http://example.org/ns#> .
import os
def observation(sensor):
    return g{ ex:{sensor} a ex:Sensor }
chemin = os.
"""
URI = "file:///virtuel/test.ldpy"


class Client:
    """Client LSP minimal : un thread lit tout, les attentes ont un timeout
    (un test qui n'obtient pas sa réponse ÉCHOUE, il ne bloque pas la suite)."""

    def __init__(self, backend="pylsp", extra_argv=()):
        import queue
        import threading
        env = dict(os.environ, PYTHONPATH=REPO)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "ldpy.lsp", "--backend", backend,
             *extra_argv],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, cwd=REPO, env=env)
        self.next_id = 1
        self.notifications = []
        self.queue = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        try:
            while True:
                self.queue.put(read_message(self.proc.stdout))
        except Exception:
            self.queue.put(None)

    def _next(self, timeout):
        import queue
        try:
            msg = self.queue.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("aucun message du serveur")
        if msg is None:
            raise RuntimeError("serveur terminé")
        return msg

    def request(self, method, params, timeout=30.0):
        rid = self.next_id
        self.next_id += 1
        write_message(self.proc.stdin,
                      {"jsonrpc": "2.0", "id": rid,
                       "method": method, "params": params})
        deadline = time.time() + timeout
        while True:
            msg = self._next(max(0.1, deadline - time.time()))
            if msg.get("id") == rid:
                assert "error" not in msg, msg
                return msg.get("result")
            if "method" in msg:
                self.notifications.append(msg)
            if time.time() > deadline:
                raise TimeoutError(method)

    def notify(self, method, params):
        write_message(self.proc.stdin,
                      {"jsonrpc": "2.0", "method": method, "params": params})

    def wait_notification(self, method, timeout=30.0, where=None):
        for n in self.notifications:
            if n["method"] == method and (where is None or where(n)):
                return n["params"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._next(max(0.1, deadline - time.time()))
            if "method" in msg:
                self.notifications.append(msg)
                if msg["method"] == method and \
                        (where is None or where(msg)):
                    return msg["params"]
        raise TimeoutError(method)

    def open(self, uri=URI, text=DOC):
        self.notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "ldpy", "version": 1, "text": text}})

    def close(self):
        try:
            self.request("shutdown", {}, timeout=10.0)
            self.notify("exit", {})
            self.proc.wait(timeout=10.0)
        except Exception:
            self.proc.kill()


@pytest.fixture(scope="module")
def lsp():
    if not HAS_PYLSP:
        pytest.skip("pylsp non installé")
    c = Client()
    caps = c.request("initialize", {"processId": None, "rootUri": None,
                                    "capabilities": {}})
    c.notify("initialized", {})
    c.caps = caps
    c.open()
    yield c
    c.close()


# ------------------------------------------------------------- capacités

def test_initialize_capabilities(lsp):
    caps = lsp.caps["capabilities"]
    assert caps["hoverProvider"] is True
    assert caps["semanticTokensProvider"]["legend"]["tokenTypes"]
    assert lsp.caps["serverInfo"]["name"] == "ldpy-lsp"


# ----------------------------------------------------------- diagnostics

def test_native_diagnostics_on_bad_document(lsp):
    bad_uri = "file:///virtuel/bad.ldpy"
    lsp.open(uri=bad_uri, text="gr = g{ foo:bar a foo:C }\n")
    params = lsp.wait_notification(
        "textDocument/publishDiagnostics",
        where=lambda n: n["params"]["uri"] == bad_uri and
                        n["params"]["diagnostics"])
    d = params["diagnostics"][0]
    assert d["source"] == "ldpy"
    assert "foo" in d["message"]
    assert d["range"]["start"]["line"] == 0        # position .ldpy, pas ombre


def test_backend_diagnostics_translated_to_ldpy_lines(lsp):
    """pyflakes voit l'ombre (décalée d'une ligne par le prélude) ; le
    diagnostic doit revenir sur la ligne .ldpy d'origine."""
    u = "file:///virtuel/undef.ldpy"
    lsp.open(uri=u, text="@prefix ex: <http://e/> .\ny = variable_inconnue\n")
    params = lsp.wait_notification(
        "textDocument/publishDiagnostics",
        where=lambda n: n["params"]["uri"] == u and
                        any("variable_inconnue" in d["message"]
                            for d in n["params"]["diagnostics"]))
    d = [x for x in params["diagnostics"]
         if "variable_inconnue" in x["message"]][0]
    assert d["range"]["start"]["line"] == 1        # ligne .ldpy


# ----------------------------------------------------------------- hover

def test_hover_on_island_is_native(lsp):
    result = lsp.request("textDocument/hover", {
        "textDocument": {"uri": URI},
        "position": {"line": 0, "character": 4}})   # dans @prefix
    assert result and "island" in result["contents"]["value"]


def test_hover_on_python_is_forwarded(lsp):
    # sur `os` de `import os` (ligne 1, col 7) : la doc du module os
    result = lsp.request("textDocument/hover", {
        "textDocument": {"uri": URI},
        "position": {"line": 1, "character": 7}})
    assert result is not None
    text = str(result.get("contents"))
    assert "operating system" in text.lower() or "os" in text


# ------------------------------------------------------------ completion

def test_completion_through_the_map(lsp):
    """Compléter `os.` ligne 4 du .ldpy (= ligne 5 de l'ombre) : la
    délégation doit produire les membres du module os."""
    result = lsp.request("textDocument/completion", {
        "textDocument": {"uri": URI},
        "position": {"line": 4, "character": 12}})
    items = result["items"] if isinstance(result, dict) else result
    labels = {i["label"] for i in items}
    assert "path" in labels or any(l.startswith("path") for l in labels)


# ------------------------------------------------------------ definition

def test_definition_result_translated_back(lsp):
    u = "file:///virtuel/defs.ldpy"
    text = ("@prefix ex: <http://e/> .\n"
            "def cible():\n"
            "    return ex:a\n"
            "y = cible()\n")
    lsp.open(uri=u, text=text)
    result = lsp.request("textDocument/definition", {
        "textDocument": {"uri": u},
        "position": {"line": 3, "character": 5}})    # sur `cible` ligne 3
    locs = result if isinstance(result, list) else [result]
    assert locs and locs[0]["uri"] == u              # URI dé-shadowée
    assert locs[0]["range"]["start"]["line"] == 1    # ligne .ldpy de def


def test_references_translated_back(lsp):
    u = "file:///virtuel/refs.ldpy"
    text = ("@prefix ex: <http://e/> .\n"
            "valeur = ex:a\n"
            "print(valeur)\n")
    lsp.open(uri=u, text=text)
    result = lsp.request("textDocument/references", {
        "textDocument": {"uri": u},
        "position": {"line": 1, "character": 2},
        "context": {"includeDeclaration": True}})
    lines = sorted(l["range"]["start"]["line"] for l in result)
    assert lines == [1, 2]


# -------------------------------------------------------- semantic tokens

def test_semantic_tokens_full(lsp):
    result = lsp.request("textDocument/semanticTokens/full",
                         {"textDocument": {"uri": URI}})
    data = result["data"]
    assert data and len(data) % 5 == 0


# ------------------------------------------------- robustesse / dégradation

def test_unknown_method_answered_not_fatal(lsp):
    assert lsp.request("textDocument/foldingRange",
                       {"textDocument": {"uri": URI}}) is None
    # le serveur répond encore ensuite
    assert lsp.request("textDocument/semanticTokens/full",
                       {"textDocument": {"uri": URI}})["data"] is not None


def test_style_diagnostics_from_backend_are_dropped():
    """A style linter judges the GENERATED shadow, not the user's source:
    its findings, re-projected, would underline whole islands (record
    vscode/107). Only semantic diagnostics (pyflakes…) come back."""
    import io
    from ldpy.lsp import translate as tr
    from ldpy.lsp.server import Document, LdpyServer
    from ldpy.transpiler import transpile

    srv = LdpyServer(io.BytesIO(), io.BytesIO(), backend="none")
    doc = Document(URI, "@prefix ex: <http://e/> .\nx = unknown_name\n", 1)
    doc.result = transpile(doc.text, doc.uri)
    srv.docs[URI] = doc
    pos = tr.pos_to_py(doc.result.map, {"line": 1, "character": 4})
    rng = {"start": pos, "end": dict(pos, character=pos["character"] + 3)}
    srv._on_backend_diags(tr.shadow_uri(URI), [
        {"range": rng, "source": "pycodestyle",
         "message": "E501 line too long"},
        {"range": rng, "source": "pyflakes",
         "message": "undefined name 'unknown_name'"},
    ])
    assert [d["source"] for d in doc.py_diags] == ["pyflakes"]


def test_backend_configuration_disables_style_plugins():
    """The shadow settings sent at startup switch every style plugin off,
    and leave pyflakes alone."""
    from ldpy.lsp.backend import SHADOW_SETTINGS, STYLE_PLUGINS
    plugins = SHADOW_SETTINGS["pylsp"]["plugins"]
    assert "pycodestyle" in STYLE_PLUGINS
    for name in STYLE_PLUGINS:
        assert plugins[name] == {"enabled": False}
    assert "pyflakes" not in plugins


def test_native_only_mode_works_without_backend():
    c = Client(backend="none")
    try:
        c.request("initialize", {"processId": None, "rootUri": None,
                                 "capabilities": {}})
        c.notify("initialized", {})
        c.open()
        hover = c.request("textDocument/hover", {
            "textDocument": {"uri": URI},
            "position": {"line": 0, "character": 4}})
        assert "island" in hover["contents"]["value"]
        # une requête déléguée répond None proprement
        assert c.request("textDocument/definition", {
            "textDocument": {"uri": URI},
            "position": {"line": 1, "character": 7}}) is None
    finally:
        c.close()


# ------------------------------------------------------------- formatage

HAS_BLACK = subprocess.run(
    [sys.executable, "-c", "import black"], capture_output=True).returncode == 0

MAL_FORMATE = """\
@prefix   ex:   <http://example.org/ns#> .
x=1
g2 = g{ex:s ex:p 1}
"""
BIEN_FORMATE = """\
@prefix ex: <http://example.org/ns#> .
x = 1
g2 = g{ ex:s ex:p 1 }
"""


@pytest.mark.skipif(not HAS_BLACK, reason="extra [format] non installé")
def test_formatting_capability_annoncee(lsp):
    assert lsp.caps["capabilities"]["documentFormattingProvider"] is True


@pytest.mark.skipif(not HAS_BLACK, reason="extra [format] non installé")
def test_formatting_rend_un_edit_couvrant_tout(lsp):
    uri = "file:///virtuel/fmt.ldpy"
    lsp.open(uri, MAL_FORMATE)
    edits = lsp.request("textDocument/formatting", {
        "textDocument": {"uri": uri},
        "options": {"tabSize": 4, "insertSpaces": True}})
    assert len(edits) == 1
    assert edits[0]["newText"] == BIEN_FORMATE
    assert edits[0]["range"]["start"] == {"line": 0, "character": 0}
    # la portée couvre bien la fin du document
    lignes = MAL_FORMATE.split("\n")
    assert edits[0]["range"]["end"] == {"line": len(lignes) - 1,
                                        "character": len(lignes[-1])}


@pytest.mark.skipif(not HAS_BLACK, reason="extra [format] non installé")
def test_formatting_ne_rend_rien_si_deja_formate(lsp):
    uri = "file:///virtuel/fmt-ok.ldpy"
    lsp.open(uri, BIEN_FORMATE)
    assert lsp.request("textDocument/formatting", {
        "textDocument": {"uri": uri}, "options": {}}) == []


@pytest.mark.skipif(not HAS_BLACK, reason="extra [format] non installé")
def test_formatting_refuse_un_document_fautif(lsp):
    """On ne formate pas ce qu'on ne comprend pas : aucun edit, et le
    document de l'utilisateur reste intact."""
    uri = "file:///virtuel/fmt-bad.ldpy"
    lsp.open(uri, "a = g{ foo:b a foo:C }\n")
    assert lsp.request("textDocument/formatting", {
        "textDocument": {"uri": uri}, "options": {}}) is None


@pytest.mark.skipif(not HAS_BLACK, reason="extra [format] non installé")
def test_formatting_honore_la_longueur_de_ligne():
    """`--line-length` du serveur l'emporte : c'est le réglage de l'éditeur."""
    c = Client(backend="none", extra_argv=["--line-length", "40"])
    try:
        c.request("initialize", {"processId": None, "rootUri": None,
                                 "capabilities": {}})
        c.notify("initialized", {})
        uri = "file:///virtuel/long.ldpy"
        c.open(uri, "x = [111111111, 222222222, 333333333, 444444444]\n")
        edits = c.request("textDocument/formatting", {
            "textDocument": {"uri": uri}, "options": {}})
        assert edits and "\n" in edits[0]["newText"].strip()
    finally:
        c.close()
