"""JSON-RPC 2.0 sur flux avec en-têtes Content-Length (base commune LSP).

Utilisé deux fois : côté serveur (stdin/stdout de l'éditeur) et côté client
(pipes du backend Python délégué). Aucune dépendance.
"""

import io
import json
import threading


class RpcClosed(Exception):
    """Le flux JSON-RPC est terminé (EOF ou corps tronqué)."""


def read_message(stream):
    """Lit un message encadré ; lève RpcClosed sur fin de flux."""
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
    """Écrit un message avec son en-tête Content-Length."""
    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    stream.write(b"Content-Length: %d\r\n\r\n" % len(body))
    stream.write(body)
    stream.flush()


class Endpoint:
    """Extrémité JSON-RPC : requêtes sortantes appariées, écriture sérialisée.

    Le pompage des messages entrants est à la charge de l'appelant
    (boucle serveur) ou d'un thread lecteur (client backend)."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self._wlock = threading.Lock()
        self._next_id = 1
        self._pending = {}          # id -> threading.Event + slot réponse

    def send(self, msg):
        """Écrit un message brut (écriture sérialisée par verrou)."""
        with self._wlock:
            write_message(self.writer, msg)

    def notify(self, method, params=None):
        """Envoie une notification (sans id)."""
        self.send({"jsonrpc": "2.0", "method": method,
                   "params": params if params is not None else {}})

    def request_async(self, method, params=None):
        """Envoie une requête ; retourne (id, event) — la réponse arrivera
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
        """Requête synchrone (nécessite un thread qui pompe feed_response)."""
        rid, slot = self.request_async(method, params)
        if not slot["event"].wait(timeout):
            self._pending.pop(rid, None)
            raise TimeoutError("pas de réponse à %s" % method)
        return slot["response"]

    def feed_response(self, msg):
        """À appeler pour tout message entrant portant un id de réponse."""
        slot = self._pending.pop(msg.get("id"), None)
        if slot is not None:
            slot["response"] = msg
            slot["event"].set()
            return True
        return False

    def respond(self, rid, result=None, error=None):
        """Répond à la requête entrante d'id ``rid``."""
        msg = {"jsonrpc": "2.0", "id": rid}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        self.send(msg)
