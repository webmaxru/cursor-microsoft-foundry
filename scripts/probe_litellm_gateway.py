"""Test a LiteLLM gateway that gives Cursor's OpenAI slot a Chat Completions endpoint for Foundry Claude.

Foundry's Claude deployment answers only the Anthropic Messages API and the OpenAI Responses API.
Cursor's IDE key slots send OpenAI Chat Completions requests, so a translating gateway has to sit
between them. This script starts LiteLLM locally, points it at the Claude deployment, and sends the
request shapes an IDE agent produces: plain text, tool calls, a tool-result round trip, streaming
with usage, and both token-limit spellings.

The gateway is a local process on 127.0.0.1 with a throwaway master key. The Foundry resource key is
read from FOUNDRY_API_KEY or from `az` in memory, handed to LiteLLM through its environment, and never
printed or written. The model alias deliberately does not start with `claude`, because Cursor sends
every `claude-*` model to its Anthropic key slot.

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
from probe_fullswitch_routes import MESSAGES, TOOLS, resource_key

ALIAS = "foundry-haiku"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def write_config(directory, api_base, deployment):
    path = Path(directory) / "litellm.config.yaml"
    path.write_text(
        "model_list:\n"
        f"  - model_name: {ALIAS}\n"
        "    litellm_params:\n"
        f"      model: azure_ai/{deployment}\n"
        f"      api_base: {api_base}\n"
        "      api_key: os.environ/AZURE_AI_API_KEY\n"
        "general_settings:\n"
        "  master_key: os.environ/LITELLM_MASTER_KEY\n",
        encoding="utf-8")
    return path


def wait_ready(base, proc, timeout=180):
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


def chat(base, master, body, expect_stream=False):
    headers = {"Authorization": f"Bearer {master}"}
    if not expect_stream:
        response = httpx.post(base + "/v1/chat/completions", headers=headers, json=body, timeout=120)
        return response.status_code, response.json() if response.content else {}
    events, usage, finish = 0, None, None
    with httpx.stream("POST", base + "/v1/chat/completions", headers=headers, json=body, timeout=120) as response:
        for line in response.iter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            events += 1
            chunk = json.loads(line[6:])
            if chunk.get("usage"):
                usage = chunk["usage"]
            for choice in chunk.get("choices", []):
                finish = choice.get("finish_reason") or finish
        return response.status_code, {"events": events, "usage": usage, "finish_reason": finish}


def run_cases(base, master):
    results = []

    def record(case, status, expected, **details):
        accepted = expected if isinstance(expected, tuple) else (expected,)
        results.append({"case": case, "http_status": status, "expected_status": list(accepted),
                        "as_expected": status in accepted, **details})

    status, data = chat(base, master, {"model": ALIAS, "max_completion_tokens": 64,
                                       "messages": [{"role": "user", "content": "Reply exactly GATEWAY_OK."}]})
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    record("Text, max_completion_tokens", status, 200, finish_reason=(data.get("choices") or [{}])[0].get("finish_reason"),
           contains_marker="GATEWAY_OK" in (text or ""), model=data.get("model"), usage=data.get("usage"))

    status, data = chat(base, master, {"model": ALIAS, "max_tokens": 64,
                                       "messages": [{"role": "user", "content": "Reply exactly GATEWAY_OK."}]})
    record("Text, legacy max_tokens", status, 200, model=data.get("model"))

    status, data = chat(base, master, {"model": ALIAS, "messages": MESSAGES, "tools": TOOLS,
                                       "tool_choice": "auto", "max_completion_tokens": 128})
    message = (data.get("choices") or [{}])[0].get("message", {})
    calls = message.get("tool_calls") or []
    arguments = json.loads(calls[0]["function"]["arguments"]) if calls else {}
    record("Tool call", status, 200, tool_call_name=calls[0]["function"]["name"] if calls else None,
           tool_call_arguments=arguments, finish_reason=(data.get("choices") or [{}])[0].get("finish_reason"))

    if calls:
        followup = MESSAGES + [message, {"role": "tool", "tool_call_id": calls[0]["id"], "content": "TOOL_RESULT_42"}]
        status, data = chat(base, master, {"model": ALIAS, "messages": followup, "tools": TOOLS,
                                           "max_completion_tokens": 128})
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        record("Tool result round trip", status, 200, answer_mentions_result="TOOL_RESULT_42" in (text or "")
               or "42" in (text or ""), finish_reason=(data.get("choices") or [{}])[0].get("finish_reason"))

    status, data = chat(base, master, {"model": ALIAS, "messages": MESSAGES, "tools": TOOLS, "stream": True,
                                       "stream_options": {"include_usage": True}, "max_completion_tokens": 128},
                        expect_stream=True)
    record("Streaming with tools and usage", status, 200, stream_events=data["events"],
           finish_reason=data["finish_reason"], usage_reported=bool(data["usage"]))

    status, _ = chat(base, "sk-gw-" + "0" * 32, {"model": ALIAS, "max_completion_tokens": 16,
                                                "messages": [{"role": "user", "content": "hi"}]})
    record("Wrong gateway key is rejected", status, (400, 401, 403))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--litellm", default=os.environ.get("LITELLM_BIN") or shutil.which("litellm"),
                        help="Path to the litellm executable (or set LITELLM_BIN)")
    parser.add_argument("--version", default="", help="LiteLLM version to record in the evidence")
    args = parser.parse_args()
    if not args.litellm:
        raise SystemExit('LiteLLM not found. In a separate environment run: pip install "litellm[proxy]", '
                         "then pass --litellm <path to litellm executable>.")

    config = load_config()
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
        settings = write_config(workdir, config["anthropic_base_url"], config["claude_deployment_name"])
        proc = subprocess.Popen([args.litellm, "--config", str(settings), "--host", "127.0.0.1", "--port", str(port)],
                                env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_ready(base, proc)
            results = run_cases(base, master)
        except Exception as exc:
            error = type(exc).__name__
        finally:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()

    report = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "gateway": f"LiteLLM {args.version}".strip() + " proxy on 127.0.0.1",
        "alias": ALIAS,
        "upstream": f"azure_ai/{config['claude_deployment_name']} through the Foundry Anthropic Messages route",
        "upstream_authentication": "Foundry resource API key (never recorded)",
        "client_authentication": "Throwaway gateway master key (never recorded)",
        "error": error,
        "cases": results,
        "passed": error is None and bool(results) and all(item["as_expected"] for item in results),
    }
    text = json.dumps(report, indent=2)
    if foundry_key in text or master in text:
        raise SystemExit("Refusing to write evidence that contains a key.")
    shutil.rmtree(workdir, ignore_errors=True)
    out = ROOT / "evidence" / "litellm-gateway.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    for item in results:
        print(("PASS " if item["as_expected"] else "FAIL ") + item["case"], item["http_status"])
    print("passed" if report["passed"] else f"FAILED ({error or 'see evidence'})")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
