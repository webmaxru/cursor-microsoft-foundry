"""Test a LiteLLM gateway that serves Foundry GPT and Claude deployments on the routes Cursor uses.

LiteLLM documents two ways Cursor reaches a gateway (Cursor IDE 3.30.14 used neither in testing
here). The OpenAI base URL override posts to `<base>/chat/completions`
(LiteLLM's `<proxy>/cursor` route), sometimes with Chat Completions bodies and sometimes with
Responses-shaped bodies (`input`, flat tool definitions, `reasoning`). The Azure OpenAI slot posts plain
Chat Completions bodies to `/openai/deployments/<name>/chat/completions` with an `api-key` header.
This script starts LiteLLM locally with both Foundry deployments and sends each of those shapes:
plain text, tool calls, a tool-result round trip, streaming with usage, the model list, the Azure
route, a Cursor model-name suffix, and a wrong key.

The gateway runs on 127.0.0.1 with a throwaway master key. The Foundry resource key is read from
FOUNDRY_API_KEY or from `az` in memory, handed to LiteLLM through its environment, and never printed
or written.

LiteLLM is not a dependency of this repository. Install it in a separate environment and pass the
executable:  python scripts/probe_litellm_gateway.py --litellm path/to/litellm
"""

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from foundry_client import ROOT, load_config
from litellm_gateway import ALIASES, HAIKU_ALIAS, LUNA_ALIAS, model_entries, render_config
from probe_fullswitch_routes import MESSAGES, TOOLS, resource_key

FLAT_TOOLS = [{"type": "function", "name": item["function"]["name"],
               "description": item["function"]["description"], "parameters": item["function"]["parameters"]}
              for item in TOOLS]
INSTRUCTIONS = MESSAGES[0]["content"]
REQUEST = MESSAGES[1]["content"]
RESULT = "TOOL_RESULT_42"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_ready(base, proc, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit("LiteLLM exited before it was ready.")
        try:
            if httpx.get(base + "/health/liveliness", timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise SystemExit("LiteLLM did not become ready in time.")


def read_stream(response):
    """Collect what a Chat Completions SSE stream says: text, tool calls, finish reason, usage."""
    events, text, usage, finish, calls = 0, [], None, None, {}
    for line in response.iter_lines():
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        events += 1
        chunk = json.loads(line[6:])
        usage = chunk.get("usage") or usage
        for choice in chunk.get("choices", []):
            finish = choice.get("finish_reason") or finish
            delta = choice.get("delta") or {}
            text.append(delta.get("content") or "")
            for call in delta.get("tool_calls") or []:
                slot = calls.setdefault(call.get("index", 0), {"id": None, "name": "", "arguments": ""})
                slot["id"] = call.get("id") or slot["id"]
                function = call.get("function") or {}
                slot["name"] += function.get("name") or ""
                slot["arguments"] += function.get("arguments") or ""
    return {"events": events, "text": "".join(text), "usage": usage, "finish_reason": finish,
            "tool_calls": [calls[index] for index in sorted(calls)]}


def post(base, path, key, body, header="Authorization"):
    headers = {"Authorization": f"Bearer {key}"} if header == "Authorization" else {header: key}
    if not body.get("stream"):
        response = httpx.post(base + path, headers=headers, json=body, timeout=180)
        data = response.json() if response.content else {}
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = [{"id": call.get("id"), "name": call["function"]["name"], "arguments": call["function"]["arguments"]}
                 for call in message.get("tool_calls") or []]
        return response.status_code, {"text": message.get("content") or "", "tool_calls": calls,
                                      "finish_reason": choice.get("finish_reason"), "usage": data.get("usage"),
                                      "model": data.get("model"), "message": message,
                                      "error": (data.get("error") or {}).get("message") if response.status_code >= 400 else None}
    with httpx.stream("POST", base + path, headers=headers, json=body, timeout=180) as response:
        if response.status_code >= 400:
            response.read()
            return response.status_code, {"error": response.text[:300], "tool_calls": [], "text": ""}
        return response.status_code, read_stream(response)


def tool_args(result):
    calls = result.get("tool_calls") or []
    try:
        return calls[0]["name"], json.loads(calls[0]["arguments"] or "{}")
    except (IndexError, ValueError):
        return None, {}


def run_cases(base, master):
    results = []

    def record(alias, case, status, ok, **details):
        results.append({"model": alias, "case": case, "http_status": status, "as_expected": bool(ok), **details})

    status, response = None, httpx.get(base + "/cursor/models", headers={"Authorization": f"Bearer {master}"}, timeout=30)
    listed = sorted(item.get("id") for item in (response.json().get("data") or [])) if response.status_code == 200 else []
    record("*", "GET /cursor/models lists both aliases", response.status_code,
           response.status_code == 200 and set(ALIASES) <= set(listed), models=listed)

    for alias in ALIASES:
        status, data = post(base, "/v1/chat/completions", master, {
            "model": alias, "max_completion_tokens": 256,
            "messages": [{"role": "user", "content": "Reply exactly GATEWAY_OK."}]})
        record(alias, "Chat Completions text", status, status == 200 and "GATEWAY_OK" in data["text"],
               finish_reason=data.get("finish_reason"), usage_reported=bool(data.get("usage")), error=data.get("error"))

        status, data = post(base, "/cursor/chat/completions", master, {
            "model": alias, "messages": MESSAGES, "tools": TOOLS, "tool_choice": "auto",
            "max_completion_tokens": 512})
        name, arguments = tool_args(data)
        record(alias, "Cursor route, Chat Completions body, tool call", status,
               status == 200 and name == "read_file" and arguments.get("path") == "README.md",
               tool_call=name, tool_arguments=arguments, finish_reason=data.get("finish_reason"), error=data.get("error"))

        if name:
            followup = MESSAGES + [data["message"], {"role": "tool", "tool_call_id": data["tool_calls"][0]["id"],
                                                    "content": RESULT}]
            status, data = post(base, "/cursor/chat/completions", master, {
                "model": alias, "messages": followup, "tools": TOOLS, "max_completion_tokens": 512})
            record(alias, "Cursor route, tool-result round trip", status, status == 200 and "42" in data["text"],
                   finish_reason=data.get("finish_reason"), error=data.get("error"),
                   **({} if "42" in data["text"] else {"answer_excerpt": data["text"][:200],
                                                       "tool_calls_again": [c["name"] for c in data["tool_calls"]]}))

        status, data = post(base, "/cursor/chat/completions", master, {
            "model": alias, "instructions": INSTRUCTIONS, "tools": FLAT_TOOLS, "reasoning": {"effort": "low"},
            "input": [{"role": "user", "content": [{"type": "input_text", "text": REQUEST}]}],
            "stream": True, "stream_options": {"include_usage": True}})
        name, arguments = tool_args(data)
        record(alias, "Cursor route, Responses-shaped body, streamed tool call", status,
               status == 200 and name == "read_file" and arguments.get("path") == "README.md",
               tool_call=name, tool_arguments=arguments, stream_events=data.get("events"),
               finish_reason=data.get("finish_reason"), usage_reported=bool(data.get("usage")), error=data.get("error"))

        if name:
            call_id = data["tool_calls"][0]["id"]
            status, data = post(base, "/cursor/chat/completions", master, {
                "model": alias, "instructions": INSTRUCTIONS, "tools": FLAT_TOOLS, "stream": True,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": REQUEST}]},
                          {"type": "function_call", "call_id": call_id, "name": "read_file",
                           "arguments": json.dumps({"path": "README.md"})},
                          {"type": "function_call_output", "call_id": call_id, "output": RESULT}]})
            record(alias, "Cursor route, Responses-shaped tool-result round trip", status,
                   status == 200 and "42" in data.get("text", ""), finish_reason=data.get("finish_reason"),
                   error=data.get("error"),
                   **({} if "42" in data.get("text", "") else {"answer_excerpt": data.get("text", "")[:200]}))

        status, data = post(base, f"/openai/deployments/{alias}/chat/completions", master, {
            "messages": MESSAGES, "tools": TOOLS, "max_completion_tokens": 512, "stream": True,
            "stream_options": {"include_usage": True}}, header="api-key")
        name, arguments = tool_args(data)
        record(alias, "Azure slot route with api-key header, streamed tool call", status,
               status == 200 and name == "read_file", tool_call=name, tool_arguments=arguments,
               usage_reported=bool(data.get("usage")), error=data.get("error"))

    status, data = post(base, "/cursor/chat/completions", master, {
        "model": LUNA_ALIAS + "-thinking-high", "max_completion_tokens": 256,
        "messages": [{"role": "user", "content": "Reply exactly GATEWAY_OK."}]})
    record(LUNA_ALIAS, "Cursor -thinking-high suffix resolves to the alias", status,
           status == 200 and "GATEWAY_OK" in data["text"], error=data.get("error"))

    status, data = post(base, "/cursor/chat/completions", "sk-gw-" + "0" * 32, {
        "model": HAIKU_ALIAS, "max_completion_tokens": 16, "messages": [{"role": "user", "content": "hi"}]})
    record("*", "Wrong gateway key is rejected", status, status in (400, 401, 403))
    return results


def probe_existing(args):
    """Probe a gateway that is already running, such as LiteLLM's Docker quickstart."""
    key = (os.environ.get("LITELLM_API_KEY") or os.environ.get("LITELLM_MASTER_KEY") or "").strip()
    if not key:
        raise SystemExit("Set LITELLM_API_KEY (or LITELLM_MASTER_KEY) to a key the gateway accepts.")
    base = args.base_url.rstrip("/")
    version = args.version
    try:
        version = version or httpx.get(base + "/health/readiness", timeout=10).json().get("litellm_version", "")
    except (httpx.HTTPError, ValueError):
        pass
    results, error = [], None
    try:
        results = run_cases(base, key)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:300]
    return results, error, key, version, "existing LiteLLM proxy on " + ("127.0.0.1" if "127.0.0.1" in base or "localhost" in base else "a private address")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--litellm", default=os.environ.get("LITELLM_BIN") or shutil.which("litellm"),
                        help="Path to the litellm executable (or set LITELLM_BIN)")
    parser.add_argument("--base-url", help="Probe a running gateway instead of starting one; the key comes from "
                                           "LITELLM_API_KEY or LITELLM_MASTER_KEY")
    parser.add_argument("--version", default="", help="LiteLLM version to record in the evidence")
    parser.add_argument("--out", default="litellm-gateway.json", help="Evidence file name under evidence/")
    parser.add_argument("--keep-log", action="store_true", help="Print the LiteLLM log path instead of deleting it")
    args = parser.parse_args()
    config = load_config()
    if args.base_url:
        results, error, master, version, where = probe_existing(args)
        report = build_report(config, results, error, version, where)
        return finish(report, args.out, master)
    if not args.litellm:
        raise SystemExit('LiteLLM not found. In a separate environment run: pip install "litellm[proxy]", '
                         "then pass --litellm <path to litellm executable>.")

    foundry_key = resource_key(config)
    master = "sk-gw-" + secrets.token_hex(16)
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    workdir = tempfile.mkdtemp(prefix="litellm-gateway-")
    log_path = Path(workdir) / "litellm.log"
    env = dict(os.environ, AZURE_AI_API_KEY=foundry_key, LITELLM_MASTER_KEY=master,
               LITELLM_LOCAL_MODEL_COST_MAP="True", PYTHONUTF8="1")
    results, error = [], None
    with log_path.open("wb") as log:
        settings = Path(workdir) / "litellm.config.yaml"
        settings.write_text(render_config(config), encoding="utf-8")
        proc = subprocess.Popen([args.litellm, "--config", str(settings), "--host", "127.0.0.1", "--port", str(port)],
                                env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_ready(base, proc)
            results = run_cases(base, master)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()

    if args.keep_log:
        print("LiteLLM log:", log_path)
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    report = build_report(config, results, error, args.version, "proxy started by this script on 127.0.0.1")
    return finish(report, args.out, master, foundry_key)


def build_report(config, results, error, version, where):
    upstreams = {alias: params["model"] for alias, params, _info in model_entries(config)}
    return {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "gateway": f"LiteLLM {version}".strip() + ", " + where,
        "aliases": list(ALIASES),
        "upstreams": {
            LUNA_ALIAS: f"{upstreams[LUNA_ALIAS]} on the Foundry OpenAI v1 Responses route",
            HAIKU_ALIAS: f"{upstreams[HAIKU_ALIAS]} on the Foundry Anthropic Messages route",
        },
        "upstream_authentication": "Foundry resource API key (never recorded)",
        "client_authentication": "Gateway key (never recorded)",
        "error": error,
        "cases": results,
        "passed": error is None and bool(results) and all(item["as_expected"] for item in results),
    }


def finish(report, name, *secrets_to_check):
    text = json.dumps(report, indent=2)
    if any(secret and secret in text for secret in secrets_to_check):
        raise SystemExit("Refusing to write evidence that contains a key.")
    out = ROOT / "evidence" / name
    out.parent.mkdir(exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    for item in report["cases"]:
        print(("PASS " if item["as_expected"] else "FAIL ") + f"{item['model']:14} {item['case']}", item["http_status"],
              item.get("error") or "")
    print("passed" if report["passed"] else f"FAILED ({report['error'] or 'see evidence'})")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
