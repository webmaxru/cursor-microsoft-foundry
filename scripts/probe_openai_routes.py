"""Probe the request shapes Cursor's OpenAI-compatible BYOK paths can send to the OpenAI deployment.

Cursor's "Override OpenAI Base URL" and "Azure OpenAI" settings send Chat Completions requests,
or Responses requests for some models. This probe sends those shapes with Entra auth, so you can
see which ones your deployment accepts before you paste a key into Cursor. It never sends or
stores an API key.
"""

import json
from datetime import datetime, timezone

import httpx
from azure.identity import AzureCliCredential

from foundry_client import ROOT, load_config

LEGACY_API_VERSION = "2025-04-01-preview"
PROMPT = "Reply exactly ROUTE_OK."


def summarize(response):
    try:
        body = response.json()
    except ValueError:
        return {"text": response.text[:300]}
    if response.is_success:
        if "choices" in body:
            text = body["choices"][0]["message"].get("content")
        else:
            text = body.get("output_text") or next(
                (part.get("text") for item in body.get("output", []) if item.get("type") == "message"
                 for part in item.get("content", []) if part.get("type") == "output_text"),
                None,
            )
        return {"model": body.get("model"), "id": body.get("id"), "usage": body.get("usage"), "text": text}
    error = body.get("error") or {}
    return {"error_code": error.get("code"), "error_param": error.get("param"), "error_message": error.get("message")}


def cases(config):
    deployment = config["deployment_name"]
    v1 = config["base_url"]
    legacy = f"https://{config['account_name']}.openai.azure.com/openai/deployments/{deployment}/chat/completions"
    chat = {"messages": [{"role": "user", "content": PROMPT}], "max_completion_tokens": 256}
    return [
        ("current v1 chat/completions", v1 + "chat/completions", {"model": deployment, **chat}, 200),
        ("current v1 chat/completions + reasoning_effort",
         v1 + "chat/completions", {"model": deployment, **chat, "reasoning_effort": "none"}, 200),
        ("current v1 chat/completions + Responses-style reasoning object",
         v1 + "chat/completions", {"model": deployment, **chat, "reasoning": {"effort": "none"}}, 400),
        ("legacy deployments chat/completions (Azure OpenAI slot shape)",
         f"{legacy}?api-version={LEGACY_API_VERSION}", chat, 200),
        ("current v1 responses", v1 + "responses",
         {"model": deployment, "input": PROMPT, "max_output_tokens": 256, "reasoning": {"effort": "none"}, "store": False},
         200),
    ]


def main():
    config = load_config()
    results = []
    with AzureCliCredential(subscription=config["subscription_id"]) as credential:
        token = credential.get_token("https://ai.azure.com/.default").token
        with httpx.Client(timeout=60, follow_redirects=False) as client:
            for name, url, body, expected in cases(config):
                response = client.post(url, headers={"Authorization": f"Bearer {token}"}, json=body)
                results.append({
                    "case": name,
                    "url": url,
                    "request_keys": sorted(body),
                    "http_status": response.status_code,
                    "expected_status": expected,
                    "as_expected": response.status_code == expected,
                    "request_id": response.headers.get("x-request-id") or response.headers.get("apim-request-id"),
                    **summarize(response),
                })
    evidence = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "authentication": "Microsoft Entra ID via Azure CLI",
        "deployment": config["deployment_name"],
        "configured_model": config["model_name"],
        "passed": all(item["as_expected"] for item in results),
        "routes": results,
    }
    path = ROOT / "evidence" / "openai-api-routes.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    for item in results:
        print(f"{item['http_status']} {'ok ' if item['as_expected'] else 'BAD'} {item['case']}")
    print(f"passed={evidence['passed']} -> {path.relative_to(ROOT)}")
    raise SystemExit(0 if evidence["passed"] else 1)


if __name__ == "__main__":
    main()
