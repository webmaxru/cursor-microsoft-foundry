"""Bounded, keyless Foundry inference. No provider credentials are returned or logged."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import APIError, OpenAI

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "foundry.json"
EXAMPLE_CONFIG_PATH = ROOT / "config" / "foundry.example.json"
AUDIT_PATH = ROOT / "evidence" / "foundry-audit.jsonl"


class FoundryError(RuntimeError):
    pass


def load_config(path=CONFIG_PATH):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Copy config/foundry.example.json to config/foundry.json "
            "and replace the placeholders with your Foundry resource and deployment names."
        )
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    url = urlsplit(config["base_url"])
    expected_host = f"{config['account_name']}.openai.azure.com"
    if (
        url.scheme != "https"
        or url.hostname != expected_host
        or url.port not in (None, 443)
        or url.username
        or url.password
        or url.path != "/openai/v1/"
        or url.query
        or url.fragment
    ):
        raise ValueError("base_url must be the configured Azure account's HTTPS OpenAI v1 endpoint.")
    if not config["deployment_name"].strip():
        raise ValueError("deployment_name must not be empty.")
    if config["anthropic_base_url"] != f"https://{config['account_name']}.services.ai.azure.com/anthropic":
        raise ValueError("anthropic_base_url must be the configured Azure account's Anthropic endpoint.")
    return config


def request_body(prompt, max_output_tokens):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
        raise ValueError("prompt must contain 1-8000 characters, with non-whitespace content.")
    if type(max_output_tokens) is not int or not 128 <= max_output_tokens <= 2048:
        raise ValueError("max_output_tokens must be an integer between 128 and 2048.")
    return {
        "input": prompt,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": "none"},
        "store": False,
    }


def response_result(response, config, body):
    if response.status != "completed":
        raise FoundryError(f"Foundry response was not completed (status={response.status}).")
    if not response.output_text or not response.output_text.strip():
        raise FoundryError("Foundry returned no output text.")
    return {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "route": "Microsoft Foundry / Azure OpenAI Responses API",
        "authentication": "Microsoft Entra ID via Azure CLI",
        "deployment": config["deployment_name"],
        "configured_model": config["model_name"],
        "configured_model_version": config["model_version"],
        "model": response.model,
        "response_id": response.id,
        "azure_request_id": response._request_id,
        "status": response.status,
        "request_sha256": hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest(),
        "usage": response.usage.model_dump() if response.usage else None,
        "response_sha256": hashlib.sha256(response.output_text.encode("utf-8")).hexdigest(),
        "text": response.output_text,
    }


def infer(prompt, max_output_tokens=512):
    body = request_body(prompt, max_output_tokens)
    config = load_config()
    body["model"] = config["deployment_name"]
    with AzureCliCredential(subscription=config["subscription_id"]) as credential:
        token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
        with OpenAI(
            base_url=config["base_url"],
            api_key=token_provider,
            max_retries=0,
            http_client=httpx.Client(timeout=90, follow_redirects=False),
        ) as client:
            try:
                response = client.responses.create(**body)
            except APIError as error:
                # Do not echo provider error bodies or request headers into an MCP result.
                status = getattr(error, "status_code", None)
                request_id = getattr(error, "request_id", None)
                raise FoundryError(
                    f"Foundry request failed ({type(error).__name__}, "
                    f"HTTP={status}, request_id={request_id}). No retry or model fallback."
                ) from None
    result = response_result(response, config, body)
    write_audit(result)
    return result


def write_audit(result):
    audit = {key: value for key, value in result.items() if key != "text"}
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(audit, ensure_ascii=True) + "\n")
