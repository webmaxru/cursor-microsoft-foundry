"""Probe what a Foundry resource API key can do on the routes a Cursor "full switch" would use.

Claude Code switches to Foundry by pointing its own client at the resource. Cursor's closest
settings (the Azure OpenAI slot and the OpenAI base URL override) send OpenAI Chat Completions
requests with a resource API key. This probe sends those request shapes directly, with the key,
so you can see which ones your deployments accept before you paste a key into any client.

The key is read from FOUNDRY_API_KEY or, when that is unset, from `az cognitiveservices account keys
list` in memory. It is never printed or written. Key authentication must be enabled on the resource.
"""

import json
import os
import subprocess
from datetime import datetime, timezone

import httpx

from foundry_client import ROOT, load_config

TOOLS = [{"type": "function", "function": {
    "name": "read_file", "description": "Read a file",
    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]
MESSAGES = [{"role": "system", "content": "You are a coding agent."},
            {"role": "user", "content": "Call read_file with path README.md"}]
SIMPLE = [{"role": "user", "content": "Reply exactly ROUTE_OK."}]


def resource_key(config):
    key = os.environ.get("FOUNDRY_API_KEY", "").strip()
    if key:
        return key
    result = subprocess.run(
        ["az", "cognitiveservices", "account", "keys", "list", "-g", config["resource_group"],
         "-n", config["account_name"], "--subscription", config["subscription_id"], "--query", "key1", "-o", "tsv"],
        capture_output=True, text=True, shell=os.name == "nt", timeout=120)
    if result.returncode or not result.stdout.strip():
        raise SystemExit("No API key. Enable key authentication on the resource, or set FOUNDRY_API_KEY.")
    return result.stdout.strip()


def cases(config):
    luna, claude = config["deployment_name"], config["claude_deployment_name"]
    v1 = config["base_url"]
    messages = config["anthropic_base_url"] + "/v1/messages"
    chat = v1 + "chat/completions"
    stream = {"stream": True, "stream_options": {"include_usage": True}}
    anthropic = {"model": claude, "max_tokens": 64, "messages": SIMPLE}
    bearer, api_key, x_api_key = "bearer", "api-key", "x-api-key"
    return [
        ("Luna chat/completions, Authorization: Bearer", chat, bearer,
         {"model": luna, "messages": SIMPLE, "max_completion_tokens": 64}, 200),
        ("Luna chat/completions, api-key header", chat, api_key,
         {"model": luna, "messages": SIMPLE, "max_completion_tokens": 64}, 200),
        ("Luna chat/completions with tools, no reasoning_effort", chat, bearer,
         {"model": luna, "messages": MESSAGES, "tools": TOOLS, "max_completion_tokens": 128}, 400),
        ("Luna chat/completions with tools, reasoning_effort=low", chat, bearer,
         {"model": luna, "messages": MESSAGES, "tools": TOOLS, "reasoning_effort": "low", "max_completion_tokens": 128}, 400),
        ("Luna chat/completions with tools, reasoning_effort=none", chat, bearer,
         {"model": luna, "messages": MESSAGES, "tools": TOOLS, "reasoning_effort": "none", "max_completion_tokens": 128}, 200),
        ("Luna chat/completions with tools, reasoning_effort=none, streaming", chat, bearer,
         {"model": luna, "messages": MESSAGES, "tools": TOOLS, "reasoning_effort": "none", "max_completion_tokens": 128, **stream}, 200),
        ("Luna chat/completions with legacy max_tokens", chat, bearer,
         {"model": luna, "messages": SIMPLE, "max_tokens": 64}, 400),
        ("Luna chat/completions, wrong key", chat, "wrong",
         {"model": luna, "messages": SIMPLE, "max_completion_tokens": 64}, 401),
        ("Claude chat/completions, Authorization: Bearer", chat, bearer,
         {"model": claude, "messages": SIMPLE, "max_completion_tokens": 64}, 404),
        ("Claude responses, Authorization: Bearer", v1 + "responses", bearer,
         {"model": claude, "input": "Reply exactly ROUTE_OK.", "max_output_tokens": 64, "store": False}, 200),
        ("Claude Anthropic messages, x-api-key", messages, x_api_key, anthropic, 200),
        ("Claude Anthropic messages, Authorization: Bearer", messages, bearer, anthropic, 200),
    ]


def headers_for(style, key, url):
    headers = {"Content-Type": "application/json"}
    if "/anthropic/" in url:
        headers["anthropic-version"] = "2023-06-01"
    credential = "wrong-key" if style == "wrong" else key
    if style == "api-key":
        headers["api-key"] = credential
    elif style == "x-api-key":
        headers["x-api-key"] = credential
    else:
        headers["Authorization"] = f"Bearer {credential}"
    return headers


def summarize(response):
    if "event-stream" in response.headers.get("content-type", ""):
        finishes = [json.loads(line[5:])["choices"][0].get("finish_reason")
                    for line in response.text.splitlines()
                    if line.startswith("data:") and line[5:].strip().startswith("{") and json.loads(line[5:]).get("choices")]
        return {"stream_finish_reasons": [item for item in finishes if item]}
    try:
        body = response.json()
    except ValueError:
        return {"text": response.text[:200]}
    if not response.is_success:
        error = body.get("error", body)
        error = error if isinstance(error, dict) else {"message": str(error)}
        return {"error_code": error.get("code") or error.get("type"), "error_message": (error.get("message") or "")[:300]}
    summary = {"model": body.get("model"), "usage": body.get("usage")}
    if body.get("choices"):
        choice = body["choices"][0]
        summary["finish_reason"] = choice.get("finish_reason")
        summary["tool_calls"] = [call["function"]["name"] for call in choice["message"].get("tool_calls") or []]
    return summary


def main():
    config = load_config()
    key = resource_key(config)
    results = []
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        for name, url, style, body, expected in cases(config):
            response = client.post(url, headers=headers_for(style, key, url), json=body)
            results.append({
                "case": name,
                "route": url.split(".azure.com", 1)[1].split("?")[0],
                "auth": {"bearer": "Authorization: Bearer", "api-key": "api-key", "x-api-key": "x-api-key",
                         "wrong": "wrong key"}[style],
                "request_keys": sorted(body),
                "http_status": response.status_code,
                "expected_status": expected,
                "as_expected": response.status_code == expected,
                **summarize(response),
            })
    evidence = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "authentication": "Foundry resource API key (never recorded)",
        "luna_deployment": config["deployment_name"],
        "claude_deployment": config["claude_deployment_name"],
        "passed": all(item["as_expected"] for item in results),
        "routes": results,
    }
    path = ROOT / "evidence" / "fullswitch-key-routes.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    for item in results:
        print(f"{item['http_status']} {'ok ' if item['as_expected'] else 'BAD'} {item['case']}")
    print(f"passed={evidence['passed']} -> {path.relative_to(ROOT)}")
    raise SystemExit(0 if evidence["passed"] else 1)


if __name__ == "__main__":
    main()
