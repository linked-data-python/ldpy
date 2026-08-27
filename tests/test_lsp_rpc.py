"""Framing JSON-RPC (ldpy/lsp/rpc.py)."""

import io
import threading

import pytest

from ldpy.lsp.rpc import read_message, write_message, Endpoint, RpcClosed


def test_write_read_roundtrip():
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "method": "m", "params": {"a": 1}})
    buf.seek(0)
    assert read_message(buf)["params"] == {"a": 1}


def test_utf8_content_length_is_bytes():
    buf = io.BytesIO()
    write_message(buf, {"x": "héhé îlot"})
    raw = buf.getvalue()
    header, body = raw.split(b"\r\n\r\n", 1)
    assert int(header.split(b":")[1]) == len(body)
    buf.seek(0)
    assert read_message(buf)["x"] == "héhé îlot"


def test_read_eof_raises_rpcclosed():
    with pytest.raises(RpcClosed):
        read_message(io.BytesIO(b""))


def test_read_truncated_body_raises():
    buf = io.BytesIO(b"Content-Length: 100\r\n\r\n{}")
    with pytest.raises(RpcClosed):
        read_message(buf)


def test_extra_headers_ignored():
    body = b'{"ok": true}'
    raw = (b"Content-Type: application/vscode-jsonrpc\r\n"
           b"Content-Length: %d\r\n\r\n%s" % (len(body), body))
    assert read_message(io.BytesIO(raw))["ok"] is True


def test_endpoint_request_response_pairing():
    a2b, b2a = io.BytesIO(), io.BytesIO()
    ep = Endpoint(b2a, a2b)
    rid, slot = ep.request_async("t/m", {"k": 1})
    ep.feed_response({"jsonrpc": "2.0", "id": rid, "result": 42})
    assert slot["response"]["result"] == 42
    assert slot["event"].is_set()


def test_endpoint_request_timeout():
    ep = Endpoint(io.BytesIO(), io.BytesIO())
    with pytest.raises(TimeoutError):
        ep.request("jamais", timeout=0.05)


def test_endpoint_concurrent_writes_are_framed():
    out = io.BytesIO()
    ep = Endpoint(io.BytesIO(), out)
    threads = [threading.Thread(target=ep.notify, args=("m%d" % i, {"i": i}))
               for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    out.seek(0)
    seen = set()
    for _ in range(20):
        seen.add(read_message(out)["params"]["i"])
    assert seen == set(range(20))
