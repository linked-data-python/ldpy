"""JSON-RPC 2.0 over streams with Content-Length headers (the LSP framing).

Used twice: on the server side (the editor's stdin/stdout) and on the client
side (the pipes of the delegated Python backend). No dependency.
"""

import io
import json
import threading


class RpcClosed(Exception):
    """The JSON-RPC stream is over (EOF or a truncated body)."""


def read_message(stream):
    """Read one framed message; raises RpcClosed at end of stream."""
    length = None
    while True:
        line = stream.readline()
        if not line:
            raise RpcClosed()
        line = line.strip()
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    if length is None:
        raise RpcClosed()
    body = stream.read(length)
    if len(body) < length:
        raise RpcClosed()
    return json.loads(body.decode("utf-8"))


def write_message(stream, msg):
    """Write a message with its Content-Length header."""
    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    stream.write(b"Content-Length: %d\r\n\r\n" % len(body))
    stream.write(body)
    stream.flush()


class Endpoint:
    """A JSON-RPC endpoint: outgoing requests paired up, writes serialised.

    Pumping incoming messages is the caller's job (the server loop) or a
    reader thread's (the backend client)."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self._wlock = threading.Lock()
        self._next_id = 1
        self._pending = {}          # id -> threading.Event + answer slot

    def send(self, msg):
        """Write a raw message (writes serialised by a lock)."""
        with self._wlock:
            write_message(self.writer, msg)

    def notify(self, method, params=None):
        """Send a notification (no id)."""
        self.send({"jsonrpc": "2.0", "method": method,
                   "params": params if params is not None else {}})

    def request_async(self, method, params=None):
        """Send a request; returns (id, event) — the answer will arrive
        via feed_response()."""
        with self._wlock:
            rid = self._next_id
            self._next_id += 1
            slot = {"event": threading.Event(), "response": None}
            self._pending[rid] = slot
            write_message(self.writer, {"jsonrpc": "2.0", "id": rid,
                                        "method": method,
                                        "params": params if params is not None else {}})
        return rid, slot

    def request(self, method, params=None, timeout=15.0):
        """Synchronous request (needs a thread pumping feed_response)."""
        rid, slot = self.request_async(method, params)
        if not slot["event"].wait(timeout):
            self._pending.pop(rid, None)
            raise TimeoutError("no answer to %s" % method)
        return slot["response"]

    def feed_response(self, msg):
        """Call this for every incoming message carrying a response id."""
        slot = self._pending.pop(msg.get("id"), None)
        if slot is not None:
            slot["response"] = msg
            slot["event"].set()
            return True
        return False

    def respond(self, rid, result=None, error=None):
        """Answer the incoming request with id ``rid``."""
        msg = {"jsonrpc": "2.0", "id": rid}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        self.send(msg)
