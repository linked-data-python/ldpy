"""Delegated Python backend: a real Python language server (pylsp) in a
subprocess, to which the ldpy server forwards translated requests
(request forwarding, NOT a fork).

The backend only ever sees shadow documents: for every open .ldpy, a
didOpen/didChange of the transpiled Python under the URI <uri>.shadow.py.
"""

import subprocess
import sys
import threading

from ldpy.lsp.rpc import Endpoint, read_message, RpcClosed


class PythonBackend:
    """Lifecycle and delegation to `python -m pylsp` (or another argv)."""

    def __init__(self, argv=None, root_uri=None):
        self.argv = argv or [sys.executable, "-m", "pylsp"]
        self.root_uri = root_uri
        self.proc = None
        self.endpoint = None
        self.diagnostics_handler = None    # callable(uri_ombre, diagnostics)
        self._reader = None

    # -- cycle de vie -------------------------------------------------------

    def start(self):
        """Start the subprocess and do the initialize handshake."""
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
                    # server->client request (configuration…): empty answer
                    self.endpoint.respond(msg["id"], result=None)
        except (RpcClosed, ValueError, OSError):
            pass

    def stop(self):
        """Clean stop (shutdown/exit), kill as a last resort."""
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
        """Is the backend subprocess still running?"""
        return self.proc is not None and self.proc.poll() is None

    # -- shadow documents ---------------------------------------------------

    def open_shadow(self, uri, text, version=1):
        """didOpen of the Python shadow document, on the backend."""
        self.endpoint.notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "python",
            "version": version, "text": text}})

    def change_shadow(self, uri, text, version):
        """didChange (full sync) of the shadow document."""
        self.endpoint.notify("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": [{"text": text}]})

    def close_shadow(self, uri):
        """didClose of the shadow document."""
        self.endpoint.notify("textDocument/didClose",
                             {"textDocument": {"uri": uri}})

    # -- requests -----------------------------------------------------------

    def forward(self, method, params, timeout=15.0):
        """Forward an already translated request; returns the raw result
        (or raises the backend error)."""
        resp = self.endpoint.request(method, params, timeout=timeout)
        if "error" in resp:
            raise BackendError(resp["error"])
        return resp.get("result")


class BackendError(Exception):
    """A JSON-RPC error returned by the delegated backend."""

    def __init__(self, error):
        super().__init__(error.get("message", "erreur backend"))
        self.error = error
