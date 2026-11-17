"""Use the native Anthropic Messages API hosted in the chosen Foundry account."""

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone

import httpx
from anthropic import APIError, AnthropicFoundry
from azure.identity import AzureCliCredential, get_bearer_token_provider

from foundry_client import FoundryError, load_config, request_body, write_audit


@contextmanager
def claude_client():
    config = load_config()
    with AzureCliCredential(subscription=config["subscription_id"]) as credential:
        token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
        with AnthropicFoundry(
            base_url=config["anthropic_base_url"],
            azure_ad_token_provider=token_provider,
            max_retries=0,
            http_client=httpx.Client(timeout=90, follow_redirects=False),
        ) as client:
            try:
                yield client
            except APIError as error:
                raise FoundryError(
                    f"Foundry Anthropic request failed ({type(error).__name__}, "
                    f"HTTP={getattr(error, 'status_code', None)}, "
                    f"request_id={getattr(error, 'request_id', None)}). No retry or model fallback."
                ) from None


def claude_audit(message, body, request_id=None):
    config = load_config()
    return {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "route": "Microsoft Foundry / Anthropic Messages API",
        "authentication": "Microsoft Entra ID via Azure CLI",
        "deployment": config["claude_deployment_name"],
        "configured_model": config["claude_model_name"],
        "configured_model_version": config["claude_model_version"],
        "model": message.model,
        "response_id": message.id,
        "azure_request_id": request_id or getattr(message, "_request_id", None),
        "stop_reason": message.stop_reason,
        "request_sha256": hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest(),
        "usage": message.usage.model_dump(),
    }


def infer_claude(prompt, max_output_tokens=512):
    request_body(prompt, max_output_tokens)
    config = load_config()
    body = {
        "model": config["claude_deployment_name"],
        "max_tokens": max_output_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "disabled"},
    }
    with claude_client() as client:
        message = client.messages.create(**body)
    if message.stop_reason != "end_turn":
        raise FoundryError(f"Claude did not finish normally (stop_reason={message.stop_reason}).")
    if any(block.type != "text" for block in message.content):
        raise FoundryError("Claude returned a non-text content block for a text-only request.")
    text = "".join(block.text for block in message.content)
    if not text.strip():
        raise FoundryError("Claude returned no output text.")
    result = {
        **claude_audit(message, body),
        "response_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
    }
    write_audit(result)
    return result
