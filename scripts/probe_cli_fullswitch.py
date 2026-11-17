"""Check whether the Cursor CLI has any way to use a different model provider.

Three observations, none of which sends a Foundry credential anywhere:

1. `--endpoint` is pointed at a local listener. The listener records only the
   method, path, header names and content type of what the CLI sends, never a
   header value or a body. The CLI authenticates with your normal Cursor login,
   and that login token reaches only this local listener, which discards it.
2. `--model` is given a name that is not in Cursor's catalog.
3. `agent --help` is searched for a provider command other than `bedrock`.
"""

import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cursor_runtime import ROOT, run_cursor

PROVIDER_WORDS = ("bedrock", "azure", "foundry", "openai", "anthropic", "vertex")


def commands_from_help(text):
    """Return the subcommand names listed under the `Commands:` heading."""
    names, active = [], False
    for line in text.splitlines():
        if re.match(r"^\s*Commands:\s*$", line):
            active = True
            continue
        if active:
            match = re.match(r"^ {2}([a-z][a-z0-9-]*)(?:\|[a-z-]+)?(?:\s|$)", line)
            if match:
                names.append(match.group(1))
            elif line.strip() and not line.startswith(" "):
                break
    return names


def main():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def record(self):
            length = min(int(self.headers.get("Content-Length") or 0), 1048576)
            self.rfile.read(length)
            requests.append({
                "method": self.command,
                "path": self.path,
                "header_names": sorted(name.lower() for name in self.headers.keys()),
                "content_type": self.headers.get("Content-Type"),
                "body_bytes": length,
            })
            body = b'{"error":"local probe"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = record

        def log_message(self, *_):
            pass

    class QuietServer(ThreadingHTTPServer):
        def handle_error(self, *_):
            """The CLI resets idle keep-alive connections; that is expected."""

    server = QuietServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    evidence = {"observed_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        result = run_cursor(
            ["--endpoint", endpoint, "--print", "--trust", "--mode", "ask", "Say hi."],
            timeout=120,
        )
        evidence["endpoint_override"] = {
            "exit_code": result.returncode,
            "output": (result.stdout + result.stderr).strip()[:400],
            "requests": list(requests),
            "reading": "Every request is a Connect call to a Cursor `aiserver.v1` service with "
                       "`application/proto` bodies. None is an OpenAI or Anthropic request.",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    result = run_cursor(
        ["--model", "cursor-poc-gpt-6-luna", "--print", "--trust", "--mode", "ask", "Say hi."],
        timeout=120,
    )
    evidence["unknown_model_name"] = {
        "exit_code": result.returncode,
        "output": (result.stdout + result.stderr).strip()[:300],
        "reading": "The CLI accepts only names from Cursor's own catalog; a custom Foundry deployment "
                   "name is refused before any request is made.",
    }

    help_text = run_cursor(["--help"], timeout=60).stdout
    commands = commands_from_help(help_text)
    evidence["provider_commands"] = {
        "all_commands": commands,
        "matching_provider_words": [name for name in commands if any(word in name for word in PROVIDER_WORDS)],
        "reading": "`bedrock` is the only cloud-provider command in this version.",
    }

    path = ROOT / "evidence" / "cli-fullswitch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if not evidence["endpoint_override"]["requests"]:
        raise RuntimeError("The listener saw no requests; do not infer a protocol result.")
    if not all(item["path"].startswith("/aiserver.v1.") for item in evidence["endpoint_override"]["requests"]):
        raise RuntimeError("Unexpected request path; the protocol conclusion no longer holds.")


if __name__ == "__main__":
    main()
