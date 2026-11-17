"""Transparent request-capture proxy for testing what Cursor actually sends to a custom endpoint.

Cursor's "Override OpenAI Base URL" setting is called by Cursor's servers, not by the IDE, so the
target must be reachable from the internet. Pasting a real Foundry key into Cursor would hand that
key to a third party, so this proxy lets you test with a throwaway shared secret instead: it
authenticates the incoming request against that secret, replaces the credential with your own
Microsoft Entra token, forwards the request body byte for byte to Microsoft Foundry, and records
the request shape. Because the body is forwarded unchanged, any success or error you see is what a
direct Foundry endpoint would have returned for the same request.

Run it only while testing, bound to localhost, behind a tunnel you delete afterwards.
"""

import argparse
import hmac
import json
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from azure.identity import AzureCliCredential

from foundry_client import ROOT, load_config

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
              "transfer-encoding", "upgrade", "content-length", "content-encoding", "host"}
SCOPE = "https://cognitiveservices.azure.com/.default"
MAX_BODY = 8 * 1024 * 1024


def body_shape(raw):
    """Summarize a request body without recording prompt text."""
    try:
        body = json.loads(raw)
    except ValueError:
        return {"json": False, "bytes": len(raw)}
    if not isinstance(body, dict):
        return {"json": True, "type": type(body).__name__}
    tools = body.get("tools") or []
    messages = body.get("messages")
    shape = {
        "keys": sorted(body),
        "model": body.get("model"),
        "stream": body.get("stream"),
        "stream_options": body.get("stream_options"),
        "reasoning_effort": body.get("reasoning_effort"),
        "reasoning": body.get("reasoning"),
        "max_tokens": body.get("max_tokens"),
        "max_completion_tokens": body.get("max_completion_tokens"),
        "max_output_tokens": body.get("max_output_tokens"),
        "temperature": body.get("temperature"),
        "tool_count": len(tools),
        "tool_names": [t.get("function", {}).get("name") or t.get("name") for t in tools if isinstance(t, dict)][:40],
        "tool_choice": body.get("tool_choice"),
        "parallel_tool_calls": body.get("parallel_tool_calls"),
        "message_roles": [m.get("role") for m in messages if isinstance(m, dict)] if isinstance(messages, list) else None,
        "has_input": "input" in body,
        "bytes": len(raw),
    }
    return {k: v for k, v in shape.items() if v is not None}


def summarize_response(status, content_type, payload):
    summary = {"status": status}
    text = payload.decode("utf-8", errors="replace")
    if "event-stream" in (content_type or ""):
        events = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        summary["sse_events"] = len(events)
        for event in reversed(events):
            if event and event != "[DONE]":
                try:
                    data = json.loads(event)
                except ValueError:
                    continue
                if data.get("usage"):
                    summary["usage"] = data["usage"]
                    break
        if status >= 400:
            summary["error"] = text[:400]
        return summary
    try:
        data = json.loads(text)
    except ValueError:
        summary["error"] = text[:400]
        return summary
    if status >= 400:
        err = data.get("error", data)
        summary["error"] = (err.get("message") if isinstance(err, dict) else str(err))[:400]
        if isinstance(err, dict) and err.get("code"):
            summary["error_code"] = err["code"]
    else:
        summary["usage"] = data.get("usage")
        summary["model"] = data.get("model")
    return summary


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "capture-proxy"

    def log_message(self, *_):
        pass

    def reply(self, status, payload, content_type="application/json"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        presented = (self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                     or self.headers.get("api-key", "").strip()
                     or self.headers.get("x-api-key", "").strip())
        return bool(presented) and hmac.compare_digest(presented.encode(), self.server.secret.encode())

    def upstream_url(self):
        parts = urlsplit(self.path)
        path = parts.path
        cfg = self.server.config
        if path.startswith("/anthropic"):
            base = f"https://{cfg['account_name']}.services.ai.azure.com"
        else:
            base = f"https://{cfg['account_name']}.openai.azure.com"
            if not path.startswith("/openai"):
                path = "/openai/v1" + (path if path.startswith("/") else "/" + path)
        return base + path + (f"?{parts.query}" if parts.query else "")

    def handle_any(self):
        started = time.monotonic()
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.reply(413, {"error": {"message": "body too large"}})
        raw = self.rfile.read(length) if length else b""
        entry = {
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "method": self.command,
            "path": urlsplit(self.path).path,
            "query": urlsplit(self.path).query,
            "header_names": sorted({k.lower() for k in self.headers.keys()}),
            "user_agent": self.headers.get("User-Agent"),
            "content_type": self.headers.get("Content-Type"),
            "accept": self.headers.get("Accept"),
            "auth_header_style": ("Authorization: Bearer" if self.headers.get("Authorization", "").startswith("Bearer ")
                                  else "api-key" if self.headers.get("api-key") else "x-api-key" if self.headers.get("x-api-key")
                                  else "none"),
        }
        if not self.authorized():
            entry["result"] = {"status": 401, "note": "rejected by proxy shared secret"}
            self.server.record(entry)
            return self.reply(401, {"error": {"message": "invalid shared secret", "code": "401"}})
        if raw:
            entry["body"] = body_shape(raw)
            self.server.save_body(entry, raw)
        token = self.server.token()
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP
                   and k.lower() not in ("authorization", "api-key", "x-api-key", "accept-encoding")}
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept-Encoding"] = "identity"
        try:
            with self.server.http.stream(self.command, self.upstream_url(), content=raw, headers=headers) as upstream:
                content_type = upstream.headers.get("content-type", "")
                self.send_response(upstream.status_code)
                for name, value in upstream.headers.items():
                    if name.lower() not in HOP_BY_HOP:
                        self.send_header(name, value)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                captured = bytearray()
                for chunk in upstream.iter_raw():
                    if not chunk:
                        continue
                    if len(captured) < MAX_BODY:
                        captured.extend(chunk)
                    self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                entry["result"] = summarize_response(upstream.status_code, content_type, bytes(captured))
        except (httpx.HTTPError, OSError) as error:
            entry["result"] = {"status": 502, "error": type(error).__name__}
            try:
                self.reply(502, {"error": {"message": "upstream failure"}})
            except OSError:
                pass
        entry["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        self.server.record(entry)

    do_GET = do_POST = do_PUT = do_DELETE = handle_any

    def do_OPTIONS(self):
        self.reply(204, b"", "text/plain")


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, config, secret, log_path, bodies_dir):
        super().__init__(address, Proxy)
        self.config = config
        self.secret = secret
        self.log_path = log_path
        self.bodies_dir = bodies_dir
        self.credential = AzureCliCredential(process_timeout=60)
        self._token = None
        self._lock = threading.Lock()
        self._counter = 0
        self.http = httpx.Client(timeout=httpx.Timeout(300, connect=15))

    def token(self):
        with self._lock:
            if self._token is None or self._token.expires_on - time.time() < 300:
                self._token = self.credential.get_token(SCOPE)
            return self._token.token

    def save_body(self, entry, raw):
        if not self.bodies_dir:
            return
        with self._lock:
            self._counter += 1
            name = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{self._counter:03d}.json"
        (self.bodies_dir / name).write_bytes(raw)
        entry["body_file"] = name

    def record(self, entry):
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        print(line[:400], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--secret", help="Shared secret Cursor will send as its API key. Generated when omitted.")
    parser.add_argument("--log", type=Path, default=ROOT / "evidence" / "proxy-capture.jsonl")
    parser.add_argument("--save-bodies", action="store_true",
                        help="Also save full request bodies under evidence/proxy-bodies for replay (may contain your code).")
    args = parser.parse_args()
    config = load_config()
    secret = args.secret or secrets.token_urlsafe(32)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    bodies = None
    if args.save_bodies:
        bodies = args.log.parent / "proxy-bodies"
        bodies.mkdir(exist_ok=True)
    server = Server(("127.0.0.1", args.port), config, secret, args.log, bodies)
    server.token()
    print(f"capture proxy on http://127.0.0.1:{args.port}  shared-secret={secret}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
