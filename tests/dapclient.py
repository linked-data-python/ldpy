"""Client DAP minimal pour piloter debugpy depuis les tests (fiche vscode/103).

Le serveur debugpy (`python -m debugpy --listen H:P --wait-for-client ...`)
parle le Debug Adapter Protocol directement sur sa socket : ni adaptateur ni
VS Code à lancer. On reproduit ici EXACTEMENT ce que lance l'extension
(`-m ldpy.debug --run fichier.ldpy`, fiche vscode/102), on déroule des gestes
de débogage, et on note où le débogueur s'arrête.

    with DapSession(prog, breakpoints=[5]) as s:
        stops = s.walk(["over", "over", "in", "out"])
        assert all(st.file == "prog.ldpy" for st in stops)

Trois fils : le programme (sous debugpy), un lecteur de la socket DAP, un
pompeur de la sortie standard du programme. Aucune lecture bloquante n'a lieu
dans le fil principal, si bien qu'un test qui échoue échoue vite.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    """Un port TCP libre (course bénigne : debugpy le rouvre aussitôt)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class DapError(RuntimeError):
    pass


class Stop:
    """Un arrêt du débogueur : sa raison et la pile TELLE QUE RAPPORTÉE.

    C'est la donnée que la fiche vscode/103 met sous contrainte : `where` est
    la « région sélectionnée » que VS Code montre à l'utilisateur."""

    __slots__ = ("reason", "frames")

    def __init__(self, reason, frames):
        self.reason = reason
        self.frames = frames                      # dicts DAP stackFrame

    @property
    def top(self):
        return self.frames[0] if self.frames else {}

    @property
    def path(self):
        return (self.top.get("source") or {}).get("path")

    @property
    def file(self):
        p = self.path
        return os.path.basename(p) if p else None

    @property
    def line(self):
        return self.top.get("line")

    @property
    def column(self):
        return self.top.get("column")

    @property
    def depth(self):
        return len(self.frames)

    @property
    def where(self):
        """(fichier, ligne, colonne, profondeur) — ce qui doit bouger."""
        return (self.file, self.line, self.column, self.depth)

    @property
    def files(self):
        """Les fichiers de toute la pile — pour vérifier qu'aucune frame du
        lanceur ne fuit dans le panneau « pile d'appels »."""
        return [os.path.basename(((f.get("source") or {}).get("path") or "?"))
                for f in self.frames]

    def __repr__(self):
        return "Stop(%s at %s:%s:%s, depth=%d)" % (
            self.reason, self.file, self.line, self.column, self.depth)


class DapSession:
    """Session de débogage scriptée sur un fichier .ldpy."""

    def __init__(self, program, breakpoints=(), just_my_code=True,
                 python=None, cwd=None, timeout=20, args=(),
                 module="ldpy.debug", module_args=("--run",), env=None,
                 rules=None):
        self.program = str(program)
        self.breakpoints = list(breakpoints)
        self.just_my_code = just_my_code
        self.python = python or sys.executable
        self.cwd = str(cwd or os.path.dirname(self.program))
        self.timeout = timeout
        self.args = list(args)
        self.module = module
        self.module_args = list(module_args)
        self.extra_env = dict(env or {})
        self.rules = rules
        self.thread_id = 1
        self._seq = 0
        self._proc = None
        self._sock = None
        self._f = None
        self._events = []
        self._responses = {}
        self._lock = threading.Condition()
        self._closed = False
        self._out = []

    # -- cycle de vie -------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    @property
    def output(self):
        """Sortie du programme débogué, telle que lue jusqu'ici."""
        return "".join(self._out)

    def start(self):
        port = free_port()
        cmd = [self.python, "-m", "debugpy", "--listen",
               "127.0.0.1:%d" % port, "--wait-for-client",
               "-m", self.module] + self.module_args + [self.program]
        if self.args:
            cmd += ["--"] + self.args
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONUNBUFFERED"] = "1"
        env["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"
        env.update(self.extra_env)
        self._proc = subprocess.Popen(
            cmd, cwd=self.cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, start_new_session=True)
        threading.Thread(target=self._pump_stdout, daemon=True).start()

        deadline = time.time() + self.timeout
        while True:
            try:
                self._sock = socket.create_connection(("127.0.0.1", port), 1)
                break
            except OSError:
                if time.time() > deadline or self._proc.poll() is not None:
                    raise DapError("debugpy n'écoute pas : %s" % self.output)
                time.sleep(0.05)
        self._f = self._sock.makefile("rwb")
        threading.Thread(target=self._read_loop, daemon=True).start()

        self.request("initialize", {
            "clientID": "ldpy-tests", "adapterID": "debugpy",
            "pathFormat": "path", "linesStartAt1": True,
            "columnsStartAt1": True, "supportsVariableType": True})
        self._send("attach", {
            "name": "ldpy", "type": "python", "request": "attach",
            "connect": {"host": "127.0.0.1", "port": port},
            "justMyCode": self.just_my_code,
            **({"rules": self.rules} if self.rules is not None else {})})
        self.wait_event("initialized")
        if self.breakpoints:
            self.set_breakpoints(self.program, self.breakpoints)
        self.request("configurationDone")

    def close(self):
        """Débranche, puis tue le GROUPE de processus.

        Un debuggee suspendu n'honore pas SIGTERM tant que pydevd ne l'a pas
        repris : on demande d'abord un `disconnect` DAP, puis on tue le groupe
        (debugpy laisse des fils et parfois un enfant sur le tube)."""
        if self._sock is not None and not self._closed:
            try:
                self.request("disconnect", {"terminateDebuggee": True},
                             timeout=3)
            except Exception:
                pass
        self._closed = True
        try:
            if self._sock is not None:
                self._sock.close()
        except OSError:
            pass
        if self._proc is not None and self._proc.poll() is None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
            except OSError:
                self._proc.kill()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    # -- transport ----------------------------------------------------------

    def _pump_stdout(self):
        try:
            for line in self._proc.stdout:
                self._out.append(line)
        except (OSError, ValueError):
            pass

    def _read_loop(self):
        try:
            while True:
                headers = {}
                while True:
                    line = self._f.readline()
                    if not line:
                        raise EOFError
                    line = line.strip()
                    if not line:
                        break
                    k, v = line.split(b":", 1)
                    headers[k.strip().lower()] = v.strip()
                msg = json.loads(self._f.read(int(headers[b"content-length"])))
                with self._lock:
                    if msg.get("type") == "event":
                        self._events.append(msg)
                    elif msg.get("type") == "response":
                        self._responses[msg["request_seq"]] = msg
                    self._lock.notify_all()
        except Exception:
            with self._lock:
                self._closed = True
                self._lock.notify_all()

    def _send(self, command, arguments=None):
        self._seq += 1
        body = json.dumps({"seq": self._seq, "type": "request",
                           "command": command,
                           "arguments": arguments or {}}).encode()
        self._f.write(b"Content-Length: %d\r\n\r\n%s" % (len(body), body))
        self._f.flush()
        return self._seq

    def request(self, command, arguments=None, timeout=None):
        seq = self._send(command, arguments)
        deadline = time.time() + (timeout or self.timeout)
        with self._lock:
            while seq not in self._responses:
                if self._closed:
                    raise DapError("session fermée pendant %r" % command)
                if time.time() > deadline:
                    raise DapError("pas de réponse à %r" % command)
                self._lock.wait(0.1)
            resp = self._responses.pop(seq)
        if not resp.get("success"):
            raise DapError("%s a échoué : %s" % (command, resp.get("message")))
        return resp.get("body") or {}

    def wait_event(self, name, timeout=None):
        deadline = time.time() + (timeout or self.timeout)
        with self._lock:
            while True:
                for i, ev in enumerate(self._events):
                    if ev["event"] == name:
                        return self._events.pop(i)
                if self._closed:
                    raise DapError("session fermée en attendant %r" % name)
                if time.time() > deadline:
                    raise DapError("événement %r jamais reçu" % name)
                self._lock.wait(0.1)

    # -- API de débogage ----------------------------------------------------

    def set_breakpoints(self, path, lines):
        body = self.request("setBreakpoints", {
            "source": {"path": str(path)},
            "breakpoints": [{"line": l} for l in lines]})
        return body.get("breakpoints", [])

    def wait_stopped(self, timeout=None):
        ev = self.wait_event("stopped", timeout)
        self.thread_id = ev["body"].get("threadId", 1)
        frames = self.request("stackTrace",
                              {"threadId": self.thread_id})["stackFrames"]
        return Stop(ev["body"].get("reason"), frames)

    def step(self, kind):
        """Un geste : 'over', 'in', 'out' ou 'continue'."""
        command = {"over": "next", "in": "stepIn", "out": "stepOut",
                   "continue": "continue"}[kind]
        self.request(command, {"threadId": self.thread_id})

    def step_over(self):
        self.step("over")

    def step_in(self):
        self.step("in")

    def step_out(self):
        self.step("out")

    def continue_(self):
        self.step("continue")

    def walk(self, gestures, timeout=6):
        """Déroule une suite de gestes et rend la liste des arrêts.

        La liste s'arrête court si le programme se termine avant la fin de la
        suite : c'est une observation, pas une erreur."""
        stops = [self.wait_stopped()]
        for g in gestures:
            try:
                self.step(g)
                stops.append(self.wait_stopped(timeout))
            except DapError:
                break
        return stops
