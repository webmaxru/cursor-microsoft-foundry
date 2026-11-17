"""Verify text streaming and a complete tool round trip on the actual model APIs."""

import argparse
import json
import secrets
from datetime import datetime, timezone

import httpx
from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import OpenAI

from claude_client import claude_audit, claude_client
from foundry_client import ROOT, load_config, response_result, write_audit

PARAMETERS = {
    "type": "object",
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    "required": ["a", "b"],
    "additionalProperties": False,
}


def verify_responses(model):
    config = load_config()
    deployment = config["deployment_name" if model == "openai" else "claude_deployment_name"]
    expected = "STREAM_" + secrets.token_hex(8)
    evidence = {"model": model, "api": "OpenAI Responses"}
    reasoning = {"effort": "none" if model == "openai" else "low"}
    with AzureCliCredential(subscription=config["subscription_id"]) as credential:
        with OpenAI(
            base_url=config["base_url"],
            api_key=get_bearer_token_provider(credential, "https://ai.azure.com/.default"),
            max_retries=0, http_client=httpx.Client(timeout=90, follow_redirects=False),
        ) as client:
            body = {
                "model": deployment, "input": f"Reply exactly {expected}.",
                "max_output_tokens": 1024, "store": False, "reasoning": reasoning,
            }
            text = ""
            event_types = set()
            completed = None
            with client.responses.create(**body, stream=True) as stream:
                for event in stream:
                    event_types.add(event.type)
                    if event.type == "response.output_text.delta":
                        text += event.delta
                    elif event.type == "response.completed":
                        completed = event.response
                    elif event.type in ("error", "response.failed", "response.incomplete"):
                        raise RuntimeError(f"Responses stream failed: {event.type}")
            if completed is None or text.strip() != expected or completed.status != "completed":
                raise RuntimeError("Streaming challenge did not complete successfully.")
            evidence["stream"] = {
                "passed": True, "text": text, "response_id": completed.id,
                "model_returned": completed.model, "events": sorted(event_types),
                "usage": completed.usage.model_dump(),
            }
            a, b = secrets.randbelow(900) + 100, secrets.randbelow(900) + 100
            marker = "TOOL_" + secrets.token_hex(8)
            instructions = f"After using add, reply only {marker}:<sum>, replacing <sum> with the integer tool result. No spaces or markdown."
            items = [{"role": "user", "content": f"Call add with a={a} and b={b}. {instructions}"}]
            tool = {"type": "function", "name": "add", "description": "Add two integers.", "parameters": PARAMETERS, "strict": True}
            first = client.responses.create(
                model=deployment, input=items, tools=[tool],
                tool_choice={"type": "function", "name": "add"},
                max_output_tokens=1024, reasoning=reasoning, store=False,
            )
            calls = [item for item in first.output if item.type == "function_call"]
            if first.status != "completed" or len(calls) != 1 or calls[0].name != "add":
                raise RuntimeError("Expected exactly one completed add tool call.")
            call = calls[0]
            if json.loads(call.arguments) != {"a": a, "b": b}:
                raise RuntimeError("The model supplied unexpected tool arguments.")
            items += [item.model_dump(exclude_none=True) for item in first.output]
            items.append({"type": "function_call_output", "call_id": call.call_id, "output": str(a + b)})
            final_body = {
                "model": deployment, "input": items, "tools": [tool], "tool_choice": "none",
                "max_output_tokens": 1024, "reasoning": reasoning, "store": False,
                "instructions": instructions,
            }
            final = client.responses.create(**final_body)
            metadata = {
                **config, "deployment_name": deployment,
                "model_name": config["model_name" if model == "openai" else "claude_model_name"],
                "model_version": config["model_version" if model == "openai" else "claude_model_version"],
            }
            result = response_result(final, metadata, final_body)
            if result["text"].strip() != f"{marker}:{a + b}":
                raise RuntimeError(f"Tool round trip: expected {marker}:{a + b}, received {result['text']!r}")
            write_audit(result)
            evidence["tool_round_trip"] = {
                "passed": True, "first_response_id": first.id, "call_id": call.call_id,
                "arguments": json.loads(call.arguments), "result": result,
                "first_usage": first.usage.model_dump(),
            }
    return evidence


def verify_anthropic():
    config = load_config()
    expected = "STREAM_" + secrets.token_hex(8)
    defaults = {"model": config["claude_deployment_name"], "max_tokens": 512, "thinking": {"type": "disabled"}}
    evidence = {"model": "claude", "api": "Native Anthropic Messages"}
    with claude_client() as client:
        with client.messages.stream(
            **defaults, messages=[{"role": "user", "content": f"Reply exactly {expected}."}]
        ) as stream:
            text = "".join(stream.text_stream)
            message = stream.get_final_message()
        if text.strip() != expected or message.stop_reason != "end_turn":
            raise RuntimeError("Native Anthropic streaming challenge failed.")
        evidence["stream"] = {
            "passed": True, "text": text, "response_id": message.id,
            "model_returned": message.model, "usage": message.usage.model_dump(),
        }
        a, b = secrets.randbelow(900) + 100, secrets.randbelow(900) + 100
        marker = "TOOL_" + secrets.token_hex(8)
        instructions = f"After using add, reply only {marker}:<sum>, replacing <sum> with the integer tool result. No spaces or markdown."
        messages = [{"role": "user", "content": f"Call add with a={a} and b={b}. {instructions}"}]
        tool = {"name": "add", "description": "Add two integers.", "input_schema": PARAMETERS}
        first = client.messages.create(
            **defaults, messages=messages, tools=[tool],
            tool_choice={"type": "tool", "name": "add", "disable_parallel_tool_use": True},
        )
        calls = [block for block in first.content if block.type == "tool_use"]
        if first.stop_reason != "tool_use" or len(calls) != 1 or calls[0].name != "add":
            raise RuntimeError("Expected exactly one native add tool_use block.")
        call = calls[0]
        if call.input != {"a": a, "b": b}:
            raise RuntimeError("Unexpected native tool arguments.")
        messages.extend([
            {"role": "assistant", "content": [block.model_dump(exclude_none=True) for block in first.content]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call.id, "content": str(a + b)}]},
        ])
        body = {**defaults, "messages": messages, "tools": [tool], "tool_choice": {"type": "none"}, "system": instructions}
        final = client.messages.create(**body)
        text = "".join(block.text for block in final.content if block.type == "text")
        if final.stop_reason != "end_turn" or text.strip() != f"{marker}:{a + b}":
            raise RuntimeError(f"Native tool round trip: expected {marker}:{a + b}, received {text!r}")
        result = {**claude_audit(final, body), "text": text}
        write_audit(result)
        evidence["tool_round_trip"] = {
            "passed": True, "first_response_id": first.id, "tool_use_id": call.id,
            "arguments": call.input, "result": result, "first_usage": first.usage.model_dump(),
        }
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", choices=["responses", "anthropic"], required=True)
    parser.add_argument("--model", choices=["openai", "claude"], required=True)
    args = parser.parse_args()
    if args.api == "anthropic" and args.model != "claude":
        parser.error("The Anthropic Messages API is only applicable to Claude.")
    evidence = verify_responses(args.model) if args.api == "responses" else verify_anthropic()
    evidence.update(passed=True, observed_at_utc=datetime.now(timezone.utc).isoformat())
    path = ROOT / "evidence" / f"{args.model}-{args.api}-features.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
