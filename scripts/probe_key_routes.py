"""Probe the Foundry routes with the resource API key, the way an Azure OpenAI slot client authenticates.

Cursor's Azure OpenAI setting sends an `api-key` header to `<resource>.openai.azure.com`. This script sends
that header to the GPT and Claude deployments on the legacy Azure route, the current v1 routes and the
Anthropic Messages route, so you can see which shapes a key-authenticated client gets before you paste the
key into any tool. The key is read from `az` (or FOUNDRY_API_KEY) into memory, never printed and never written.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import httpx

from foundry_client import ROOT, load_config

PROMPT = "Reply exactly KEY_ROUTE_OK."
LEGACY_API_VERSION = "2025-04-01-preview"


def load_key(config):
    key = os.environ.get("FOUNDRY_API_KEY")
    if key:
        return key
    result = subprocess.run(
        ["az", "cognitiveservices", "account", "keys", "list", "-g", config["resource_group"],
         "-n", config["account_name"], "--query", "key2", "-o", "tsv"],
        capture_output=True, text=True, shell=os.name == "nt", check=False)
    key = result.stdout.strip()
    if not key:
        sys.exit("No key: set FOUNDRY_API_KEY or sign in with `az login` and enable key access on the resource.")
    return key


def summarize(response):
    try:
        body = response.json()
    except ValueError:
        return {"text": response.text[:200]}
    if response.is_success:
        if "choices" in body:
            text = body["choices"][0]["message"].get("content")
        elif "content" in body:
            text = next((part.get("text") for part in body["content"] if part.get("type") == "text"), None)
        else:
            text = body.get("output_text") or next(
                (part.get("text") for item in body.get("output", []) if item.get("type") == "message"
                 for part in item.get("content", []) if part.get("type") == "output_text"), None)
        return {"model": body.get("model"), "text": text}
    error = body.get("error") or {}
    return {"error_code": error.get("code"), "error_message": (error.get("message") or "")[:160]}


def cases(config):
    openai_host = f"https://{config['account_name']}.openai.azure.com"
    messages = [{"role": "user", "content": PROMPT}]
    out = []
    for label, deployment in (("GPT", config["deployment_name"]), ("Claude", config["claude_deployment_name"])):
        legacy = f"{openai_host}/openai/deployments/{deployment}/chat/completions?api-version={LEGACY_API_VERSION}"
        out += [
            (label, "legacy Azure chat/completions, max_tokens", legacy,
             {"messages": messages, "max_tokens": 256}, {"api-key": None}),
            (label, "legacy Azure chat/completions, max_completion_tokens", legacy,
             {"messages": messages, "max_completion_tokens": 256}, {"api-key": None}),
            (label, "v1 chat/completions", f"{openai_host}/openai/v1/chat/completions",
             {"model": deployment, "messages": messages, "max_completion_tokens": 256}, {"api-key": None}),
            (label, "v1 responses", f"{openai_host}/openai/v1/responses",
             {"model": deployment, "input": PROMPT, "max_output_tokens": 256, "store": False}, {"api-key": None}),
        ]
    out.append(("Claude", "Anthropic Messages (x-api-key)", config["anthropic_base_url"] + "/v1/messages",
                {"model": config["claude_deployment_name"], "max_tokens": 256,
                 "messages": messages}, {"x-api-key": None, "anthropic-version": "2023-06-01"}))
    out.append(("Claude", "Anthropic Messages (api-key)", config["anthropic_base_url"] + "/v1/messages",
                {"model": config["claude_deployment_name"], "max_tokens": 256,
                 "messages": messages}, {"api-key": None, "anthropic-version": "2023-06-01"}))
    return out


def main():
    config = load_config()
    key = load_key(config)
    results = []
    with httpx.Client(timeout=60) as client:
        for model, name, url, body, auth in cases(config):
            headers = {k: (key if v is None else v) for k, v in auth.items()}
            response = client.post(url, headers=headers, json=body)
            entry = {"target": model, "case": name, "route": url.split("?")[0].replace(
                f"{config['account_name']}.", "<resource>."), "http_status": response.status_code,
                **summarize(response)}
            results.append(entry)
            print(f"{response.status_code}  {model:6} {name}  {entry.get('text') or entry.get('error_code')}")
    evidence = {"observed_at_utc": datetime.now(timezone.utc).isoformat(), "authentication": "resource API key",
                "results": results}
    serialized = json.dumps(evidence, indent=2)
    if key in serialized:
        sys.exit("Refusing to write evidence that contains the key.")
    (ROOT / "evidence" / "key-route-probe.json").write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
