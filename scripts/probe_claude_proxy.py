"""Drive scripts/foundry_claude_proxy.py with the OpenAI SDK and record what works, per Claude API mode.

Starts the proxy in this process on a free localhost port (once with --claude-api messages, once with
responses), then sends the request shapes an OpenAI-compatible coding client sends: plain and streamed
answers, a tool loop with two parallel calls, the legacy Azure path that Cursor's Azure OpenAI slot uses, a
Luna passthrough, and a wrong secret. Every result is checked, not just its status. Writes
evidence/claude-proxy-probe.json with statuses, finish reasons, tool-call counts and token usage; prompt
and answer text are not recorded. Uses the Foundry key from FOUNDRY_API_KEY or `az`, never printed.
"""

import argparse
import json
import secrets
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
from openai import AzureOpenAI, OpenAI

import foundry_claude_proxy as proxy
from foundry_client import ROOT, load_config

TOOLS = [{"type": "function", "function": {
    "name": "get_weather", "description": "Get the current weather for one city.",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
TOOL_PROMPT = "What's the weather in Oslo and in Paris? Call get_weather once for each city."
WEATHER = {"oslo": "12C, rain", "paris": "18C, sun"}


def tool_loop(client, model, stream):
    """Run the tool loop until Claude answers; returns per-turn tool-call counts and the final finish reason."""
    messages = [{"role": "user", "content": TOOL_PROMPT}]
    turns, cities = [], set()
    for _ in range(4):
        if stream:
            calls, finish, content = {}, None, ""
            for chunk in client.chat.completions.create(model=model, messages=messages, tools=TOOLS, max_tokens=400,
                                                        stream=True):
                for choice in chunk.choices:
                    finish = choice.finish_reason or finish
                    content += choice.delta.content or ""
                    for call in choice.delta.tool_calls or []:
                        slot = calls.setdefault(call.index, {"id": None, "name": None, "arguments": ""})
                        slot["id"] = call.id or slot["id"]
                        if call.function:
                            slot["name"] = call.function.name or slot["name"]
                            slot["arguments"] += call.function.arguments or ""
            tool_calls = [calls[i] for i in sorted(calls)]
        else:
            reply = client.chat.completions.create(model=model, messages=messages, tools=TOOLS, max_tokens=400)
            choice = reply.choices[0]
            finish, content = choice.finish_reason, choice.message.content or ""
            tool_calls = [{"id": c.id, "name": c.function.name, "arguments": c.function.arguments}
                          for c in choice.message.tool_calls or []]
        turns.append(len(tool_calls))
        if finish != "tool_calls":
            mentions = all(word in content for word in ("12", "18"))
            return {"turns": turns, "final_finish": finish, "cities_called": sorted(cities),
                    "answer_uses_both_results": mentions}
        messages.append({"role": "assistant", "content": content or None, "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
            for c in tool_calls]})
        for call in tool_calls:
            city = json.loads(call["arguments"]).get("city", "").lower()
            cities.add(city)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": WEATHER.get(city, "unknown")})
    return {"turns": turns, "final_finish": "loop_limit", "cities_called": sorted(cities)}


def run_mode(config, key, claude_api, log_path):
    secret = secrets.token_urlsafe(24)
    models = proxy.model_map(config, ["foundry-haiku=" + config["claude_deployment_name"]])
    server = proxy.Server(("127.0.0.1", 0), config, secret, models, log_path, claude_api, "key", key)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    client = OpenAI(base_url=base + "/v1", api_key=secret, max_retries=0, timeout=180)
    results = {}

    def case(name, function):
        try:
            results[name] = dict(function(), ok=True)
        except Exception as error:  # record the failure and keep probing
            results[name] = {"ok": False, "error": f"{type(error).__name__}: {str(error)[:300]}"}

    def plain():
        reply = client.chat.completions.create(model="foundry-haiku", max_tokens=64, messages=[
            {"role": "system", "content": "Answer in one word."}, {"role": "user", "content": "Reply PROXY_OK"}])
        choice = reply.choices[0]
        assert "PROXY_OK" in (choice.message.content or ""), "marker missing"
        return {"finish": choice.finish_reason, "usage": reply.usage.model_dump(exclude_none=True)}

    def streamed():
        text, finish, usage = "", None, None
        for chunk in client.chat.completions.create(model="foundry-haiku", max_tokens=64, stream=True,
                                                    stream_options={"include_usage": True},
                                                    messages=[{"role": "user", "content": "Count from 1 to 5."}]):
            usage = chunk.usage or usage
            for choice in chunk.choices:
                text += choice.delta.content or ""
                finish = choice.finish_reason or finish
        assert "5" in text and usage and usage.completion_tokens > 0, "stream incomplete"
        return {"finish": finish, "usage": usage.model_dump(exclude_none=True)}

    def tools(stream):
        def run():
            result = tool_loop(client, "foundry-haiku", stream)
            assert result["final_finish"] == "stop" and result["cities_called"] == ["oslo", "paris"], result
            assert result["answer_uses_both_results"], "answer ignores a tool result"
            return result
        return run

    def azure_slot_path():
        azure = AzureOpenAI(azure_endpoint=base, api_key=secret, api_version="2025-04-01-preview", max_retries=0)
        reply = azure.chat.completions.create(model=config["claude_deployment_name"], max_tokens=32,
                                              messages=[{"role": "user", "content": "Reply AZURE_PATH_OK"}])
        assert "AZURE_PATH_OK" in (reply.choices[0].message.content or ""), "marker missing"
        return {"path": "/openai/deployments/<claude deployment>/chat/completions", "finish": reply.choices[0].finish_reason}

    def luna_passthrough():
        reply = client.chat.completions.create(model=config["deployment_name"], max_tokens=256,
                                               messages=[{"role": "user", "content": "Reply LUNA_OK"}])
        assert "LUNA_OK" in (reply.choices[0].message.content or ""), "marker missing"
        return {"finish": reply.choices[0].finish_reason, "model": reply.model}

    def models_list():
        names = sorted(model.id for model in client.models.list())
        assert "foundry-haiku" in names, names
        return {"models": names}

    def wrong_secret():
        status = httpx.post(base + "/v1/chat/completions", headers={"Authorization": "Bearer wrong"},
                            json={"model": "foundry-haiku", "messages": [{"role": "user", "content": "x"}]}).status_code
        assert status == 401, status
        return {"status": status}

    try:
        case("plain", plain)
        case("stream_with_usage", streamed)
        case("tool_loop", tools(False))
        case("tool_loop_streamed", tools(True))
        case("azure_slot_path", azure_slot_path)
        if claude_api == "messages":
            case("luna_passthrough", luna_passthrough)
            case("models_list", models_list)
            case("wrong_secret_rejected", wrong_secret)
    finally:
        server.shutdown()
        server.server_close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "evidence" / "claude-proxy-probe.json",
                        help="where to write the JSON report (default: evidence/claude-proxy-probe.json)")
    args = parser.parse_args()
    config = load_config()
    key = proxy.load_key(config)
    report = {"observed_at_utc": datetime.now(timezone.utc).isoformat(), "claude_deployment": config["claude_deployment_name"],
              "openai_deployment": config["deployment_name"], "modes": {}}
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "proxy.jsonl"
        for mode in ("messages", "responses"):
            report["modes"][mode] = run_mode(config, key, mode, log)
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    report["proxy_log_entries"] = len(entries)
    report["prompt_text_in_log"] = any(word in json.dumps(entries) for word in ("PROXY_OK", "Oslo", "Count from"))
    passed = sum(case["ok"] for mode in report["modes"].values() for case in mode.values())
    total = sum(len(mode) for mode in report["modes"].values())
    report["passed"], report["total"] = passed, total
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for mode, cases in report["modes"].items():
        for name, result in cases.items():
            detail = {k: v for k, v in result.items() if k not in ("ok", "usage")}
            print(f"{mode:9} {name:22} {'PASS' if result['ok'] else 'FAIL'}  {json.dumps(detail)[:160]}")
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"{passed}/{total} passed; prompt text in proxy log: {report['prompt_text_in_log']}; wrote {shown}")
    return 0 if passed == total and not report["prompt_text_in_log"] else 1


if __name__ == "__main__":
    sys.exit(main())
