"""Backend Python délégué : un vrai serveur LSP Python (pylsp) en
sous-processus, à qui le serveur ldpy transmet les requêtes traduites
(fiche lsp/101 — request forwarding, PAS de fork).

Le backend ne voit QUE les documents fantômes : pour chaque .ldpy ouvert,
un didOpen/didChange du Python transpilé sous l'URI <uri>.shadow.py.
"""

import subprocess
import sys
import threading

from ldpy.lsp.rpc import Endpoint, read_message, RpcClosed


class PythonBackend:
    """Cycle de vie + délégation vers `python -m pylsp` (ou autre argv)."""

    def __init__(self, argv=None, root_uri=None):
        self.argv = argv or [sys.executable, "-m", "pylsp"]
        self.root_uri = root_uri
        self.proc = None
        self.endpoint = None
        self.diagnostics_handler = None    # callable(uri_ombre, diagnostics)
        self._reader = None

    # -- cycle de vie -------------------------------------------------------

    def start(self):
        """Démarre le sous-processus et fait la poignée de main initialize."""
        self.proc = subprocess.Popen(
            self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
        self.endpoint = Endpoint(self.proc.stdout, self.proc.stdin)
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()
        self.endpoint.request("initialize", {
            "processId": None,
            "rootUri": self.root_uri,
            "capabilities": {"textDocument": {
                "synchronization": {},
                "completion": {"completionItem": {"snippetSupport": False}},
                "hover": {"contentFormat": ["markdown", "plaintext"]},
                "definition": {}, "references": {}, "signatureHelp": {},
            }},
        }, timeout=30.0)
        self.endpoint.notify("initialized", {})
        return self

    def _pump(self):
        try:
            while True:
                msg = read_message(self.endpoint.reader)
                if "id" in msg and ("result" in msg or "error" in msg):
                    self.endpoint.feed_response(msg)
                elif msg.get("method") == "textDocument/publishDiagnostics":
                    if self.diagnostics_handler:
                        p = msg.get("params", {})
                        self.diagnostics_handler(p.get("uri", ""),
                                                 p.get("diagnostics", []))
                elif "id" in msg:
                    # requête serveur->client (configuration...) : réponse vide
                    self.endpoint.respond(msg["id"], result=None)
        except (RpcClosed, ValueError, OSError):
            pass

    def stop(self):
        """Arrêt propre (shutdown/exit), kill en dernier recours."""
        if not self.proc:
            return
        try:
            self.endpoint.request("shutdown", {}, timeout=5.0)
            self.endpoint.notify("exit")
            self.proc.wait(timeout=5.0)
        except Exception:
            self.proc.kill()
        self.proc = None

    def alive(self):
        """Le sous-processus backend tourne-t-il encore ?"""
        return self.proc is not None and self.proc.poll() is None

    # -- documents fantômes -------------------------------------------------

    def open_shadow(self, uri, text, version=1):
        """didOpen du document fantôme Python chez le backend."""
        self.endpoint.notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "python",
            "version": version, "text": text}})

    def change_shadow(self, uri, text, version):
        """didChange (synchronisation complète) du document fantôme."""
        self.endpoint.notify("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": [{"text": text}]})

    def close_shadow(self, uri):
        """didClose du document fantôme."""
        self.endpoint.notify("textDocument/didClose",
                             {"textDocument": {"uri": uri}})

    # -- requêtes -----------------------------------------------------------

    def forward(self, method, params, timeout=15.0):
        """Transmet une requête déjà traduite ; retourne le result brut
        (ou lève l'erreur du backend)."""
        resp = self.endpoint.request(method, params, timeout=timeout)
        if "error" in resp:
            raise BackendError(resp["error"])
        return resp.get("result")


class BackendError(Exception):
    """Erreur JSON-RPC renvoyée par le backend délégué."""

    def __init__(self, error):
        super().__init__(error.get("message", "erreur backend"))
        self.error = error
