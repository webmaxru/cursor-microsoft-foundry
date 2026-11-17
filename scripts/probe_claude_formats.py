"""Check which OpenAI-compatible routes accept the configured Claude deployment."""

import json
from datetime import datetime, timezone

import httpx
from azure.identity import AzureCliCredential

from foundry_client import ROOT, load_config


def main():
    config = load_config()
    routes = [
        (config["base_url"] + "chat/completions", "chat"),
        (config["base_url"] + "responses", "responses"),
        (config["anthropic_base_url"] + "/v1/chat/completions", "chat"),
    ]
    results = []
    with AzureCliCredential(subscription=config["subscription_id"]) as credential:
        token = credential.get_token("https://ai.azure.com/.default").token
        with httpx.Client(timeout=45, follow_redirects=False) as client:
            for url, kind in routes:
                body = {"model": config["claude_deployment_name"]}
                if kind == "chat":
                    body.update(messages=[{"role": "user", "content": "Reply exactly CLAUDE_FORMAT_OK."}], max_tokens=128)
                else:
                    body.update(input="Reply exactly CLAUDE_FORMAT_OK.", max_output_tokens=128, store=False)
                response = client.post(url, headers={
                    "Authorization": f"Bearer {token}", "anthropic-version": "2023-06-01",
                }, json=body)
                results.append({
                    "url": url, "http_status": response.status_code,
                    "request_id": response.headers.get("x-request-id") or response.headers.get("apim-request-id"),
                    "body": response.json() if "json" in response.headers.get("content-type", "") else response.text[:1000],
                })
    evidence = {"observed_at_utc": datetime.now(timezone.utc).isoformat(), "routes": results}
    (ROOT / "evidence" / "claude-api-formats.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
