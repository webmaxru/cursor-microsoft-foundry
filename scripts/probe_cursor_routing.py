"""Black-box routing checks. The local listener discards bodies and all credential values."""

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cursor_runtime import ROOT, run_cursor


def main():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = min(int(self.headers.get("Content-Length", 0)), 1048576)
            self.rfile.read(length)
            requests.append({
                "method": self.command, "path": self.path,
                "content_type": self.headers.get("Content-Type"),
            })
            body = b'{"code":"unauthenticated","message":"LOCAL_PROTOCOL_PROBE"}'
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    evidence = {"observed_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        with tempfile.TemporaryDirectory(prefix="cursor-routing-") as directory:
            Path(directory, "cli-config.json").write_text(json.dumps({
                "version": 1, "editor": {"vimMode": False},
                "permissions": {"allow": [], "deny": ["Shell(*)", "Read(**)", "Write(**)", "Mcp(*:*)"]},
                "network": {"useHttp1ForAgent": True},
            }), encoding="utf-8")
            env = dict(os.environ, CURSOR_CONFIG_DIR=directory)
            result = run_cursor([
                "--endpoint", endpoint, "--api-key", "not-a-real-cursor-api-key",
                "models",
            ], env=env, timeout=60)
            evidence["endpoint_override"] = {
                "exit_code": result.returncode, "requests": list(requests),
                "output": (result.stdout + result.stderr).strip()[:4000],
                "credential": "Deliberately invalid synthetic Cursor key; no Azure key used.",
            }
        requests.clear()
        env = dict(os.environ)
        for name in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "AZURE_OPENAI_ENDPOINT", "ANTHROPIC_BASE_URL"):
            env[name] = endpoint
        for name in ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            env[name] = "not-a-real-provider-key"
        result = run_cursor([
            "--workspace", str(ROOT / "demo"), "--trust", "--mode", "ask",
            "--model", "auto", "--print", "--output-format", "json",
            "Do not use any tools. Reply with exactly CURSOR_NATIVE_ROUTE_OK.",
        ], env=env)
        evidence["provider_environment_override"] = {
            "exit_code": result.returncode,
            "local_provider_request_count": len(requests),
            "requests": list(requests),
            "output": result.stdout.strip(),
            "stderr": result.stderr.strip()[:4000],
            "scope": "These variables did not redirect this Auto run; this is not an exhaustive provider test.",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    path = ROOT / "evidence" / "cursor-routing.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if not evidence["endpoint_override"]["requests"]:
        raise RuntimeError("Endpoint probe observed no requests; do not infer a protocol result.")
    if evidence["provider_environment_override"]["exit_code"] != 0:
        raise RuntimeError("Authenticated Cursor baseline failed; inspect saved evidence.")


if __name__ == "__main__":
    main()
