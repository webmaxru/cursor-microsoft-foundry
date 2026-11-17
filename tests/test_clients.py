import asyncio
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import APIStatusError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import foundry_client
from foundry_client import EXAMPLE_CONFIG_PATH, FoundryError, load_config, request_body, response_result


class ClientGuards(unittest.TestCase):
    def test_invalid_inputs_rejected_before_credentials(self):
        cases = [("", 256), ("  ", 256), ("x" * 8001, 256), ([], 256), ("x", 0), ("x", 2049), ("x", True)]
        for prompt, tokens in cases:
            with self.subTest(prompt_type=type(prompt).__name__, tokens=tokens):
                with patch("foundry_client.AzureCliCredential") as credential:
                    with self.assertRaises(ValueError):
                        foundry_client.infer(prompt, tokens)
                    credential.assert_not_called()

    def test_config_rejects_non_azure_destinations_and_url_credentials(self):
        config = load_config(EXAMPLE_CONFIG_PATH)
        urls = [
            "http://my-foundry-resource.openai.azure.com/openai/v1/",
            "https://my-foundry-resource.openai.azure.com.attacker.invalid/openai/v1/",
            "https://user:password@my-foundry-resource.openai.azure.com/openai/v1/",
            config["base_url"] + "?forward=https://example.invalid",
            config["base_url"] + "#fragment",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for url in urls:
                with self.subTest(url=url):
                    path.write_text(json.dumps({**config, "base_url": url}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_config(path)
            path.write_text(json.dumps({**config, "anthropic_base_url": "https://api.anthropic.com"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_missing_config_points_to_example(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "foundry.example.json"):
                load_config(Path(directory) / "foundry.json")

    def test_incomplete_and_empty_responses_are_not_success(self):
        for status, text in [("incomplete", "partial"), ("failed", ""), ("completed", "")]:
            with self.subTest(status=status):
                with self.assertRaises(FoundryError):
                    response_result(SimpleNamespace(status=status, output_text=text), {}, {})

    def test_audit_has_hashes_but_no_prompt_or_answer(self):
        prompt = "SYNTHETIC_PROMPT_SENTINEL"
        answer = "SYNTHETIC_ANSWER_SENTINEL"
        config = load_config(EXAMPLE_CONFIG_PATH)
        response = SimpleNamespace(
            status="completed", output_text=answer, model=config["deployment_name"],
            id="resp_test", _request_id="req_test", usage=None,
        )
        result = response_result(response, config, request_body(prompt, 256))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            with patch("foundry_client.AUDIT_PATH", path):
                foundry_client.write_audit(result)
            content = path.read_text(encoding="utf-8")
            self.assertNotIn(prompt, content)
            self.assertNotIn(answer, content)
            self.assertEqual(json.loads(content)["response_sha256"], hashlib.sha256(answer.encode()).hexdigest())

    def test_provider_errors_are_redacted_and_not_retried(self):
        response = httpx.Response(429, request=httpx.Request("POST", "https://example.invalid"),
                                  headers={"x-request-id": "req_error"})
        error = APIStatusError("SENSITIVE_PROVIDER_BODY", response=response, body={"secret": "SENTINEL"})
        example = load_config(EXAMPLE_CONFIG_PATH)
        with patch("foundry_client.load_config", return_value=example), \
                patch("foundry_client.AzureCliCredential"), patch("foundry_client.get_bearer_token_provider"):
            with patch("foundry_client.OpenAI") as factory, patch("foundry_client.write_audit") as audit:
                client = factory.return_value.__enter__.return_value
                client.responses.create.side_effect = error
                with self.assertRaises(FoundryError) as caught:
                    foundry_client.infer("Synthetic prompt")
                self.assertIn("HTTP=429", str(caught.exception))
                self.assertNotIn("SENSITIVE", str(caught.exception))
                self.assertNotIn("SENTINEL", str(caught.exception))
                client.responses.create.assert_called_once()
                self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
                audit.assert_not_called()


class TranscriptCorrelation(unittest.TestCase):
    def test_proof_needs_displayed_ids_matching_hashes_and_both_deployments(self):
        import verify_cursor
        config = load_config(EXAMPLE_CONFIG_PATH)
        expected = verify_cursor.expected_hashes(config, "p1", "NONCE_a:1", "p2", "NONCE_b:2")
        openai_dep, claude_dep = config["deployment_name"], config["claude_deployment_name"]

        def record(deployment, response_id, tamper=False):
            request, response = expected[deployment]
            return {"deployment": deployment, "response_id": response_id,
                    "request_sha256": request, "response_sha256": "0" * 64 if tamper else response}

        records = [record(openai_dep, "resp_1"), record(claude_dep, "msg_2"),
                   record(claude_dep, "msg_hidden"), record(claude_dep, "msg_tampered", tamper=True)]
        transcript = "NONCE_a:1 resp_1 NONCE_b:2 msg_2 msg_tampered"
        matched = verify_cursor.correlate(records, transcript, expected)
        self.assertEqual([r["response_id"] for r in matched], ["resp_1", "msg_2"])
        self.assertTrue(verify_cursor.proven(transcript, ("NONCE_a:1", "NONCE_b:2"), expected, matched))
        self.assertFalse(verify_cursor.proven(transcript, ("NONCE_a:1", "NONCE_b:2"), expected, matched[:1]))
        self.assertFalse(verify_cursor.proven("resp_1 msg_2", ("NONCE_a:1", "NONCE_b:2"), expected, matched))


class McpValidation(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_tool_arguments_never_reach_azure(self):
        audit = foundry_client.AUDIT_PATH
        before = audit.read_bytes() if audit.exists() else b""
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(foundry_client.ROOT / "scripts" / "foundry_mcp.py")],
        )
        async with asyncio.timeout(60):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    for tool in ("foundry_openai", "foundry_claude"):
                        result = await session.call_tool(tool, {"prompt": "Synthetic", "max_output_tokens": 2049})
                        self.assertTrue(result.isError)
        after = audit.read_bytes() if audit.exists() else b""
        self.assertEqual(before, after)


class CaptureProxy(unittest.TestCase):
    def test_body_shape_keeps_request_shape_but_not_prompt_text(self):
        import capture_proxy
        raw = json.dumps({
            "model": "m", "stream": True, "reasoning_effort": "none", "max_completion_tokens": 8,
            "messages": [{"role": "system", "content": "SECRET PROMPT"}, {"role": "user", "content": "SECRET PROMPT"}],
            "tools": [{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
        }).encode()
        shape = capture_proxy.body_shape(raw)
        self.assertNotIn("SECRET PROMPT", json.dumps(shape))
        self.assertEqual(shape["tool_names"], ["read_file"])
        self.assertEqual(shape["message_roles"], ["system", "user"])
        self.assertEqual(shape["reasoning_effort"], "none")
        self.assertEqual(capture_proxy.body_shape(b"not json"), {"json": False, "bytes": 8})

    def test_response_summary_reports_errors_and_stream_usage(self):
        import capture_proxy
        error = json.dumps({"error": {"code": "api_not_supported", "message": "nope"}}).encode()
        summary = capture_proxy.summarize_response(404, "application/json", error)
        self.assertEqual((summary["status"], summary["error_code"], summary["error"]), (404, "api_not_supported", "nope"))
        stream = b'data: {"usage": {"total_tokens": 3}}\n\ndata: [DONE]\n\n'
        summary = capture_proxy.summarize_response(200, "text/event-stream", stream)
        self.assertEqual((summary["sse_events"], summary["usage"]), (2, {"total_tokens": 3}))

    def test_wrong_secret_is_rejected_before_any_azure_token_is_requested(self):
        import contextlib
        import io
        import threading
        import capture_proxy
        config = load_config(EXAMPLE_CONFIG_PATH)
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            log = Path(directory) / "capture.jsonl"
            with patch("capture_proxy.AzureCliCredential") as credential:
                server = capture_proxy.Server(("127.0.0.1", 0), config, "right-secret", log, None)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                try:
                    url = f"http://127.0.0.1:{server.server_address[1]}/chat/completions"
                    wrong = httpx.post(url, json={"model": "m"}, headers={"Authorization": "Bearer wrong-secret"})
                    missing = httpx.post(url, json={"model": "m"})
                finally:
                    server.shutdown()
                    server.server_close()
                credential.return_value.get_token.assert_not_called()
            self.assertEqual((wrong.status_code, missing.status_code), (401, 401))
            self.assertNotIn("wrong-secret", log.read_text(encoding="utf-8"))

    def test_stub_answers_locally_without_azure_token_or_forwarding(self):
        import contextlib
        import io
        import threading
        import capture_proxy
        config = load_config(EXAMPLE_CONFIG_PATH)
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            log = Path(directory) / "capture.jsonl"
            with patch("capture_proxy.AzureCliCredential") as credential:
                server = capture_proxy.Server(("127.0.0.1", 0), config, "right-secret", log, None, stub=True)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                try:
                    with patch.object(server.http, "send") as forward:
                        url = f"http://127.0.0.1:{server.server_address[1]}/chat/completions"
                        reply = httpx.post(url, json={"model": "foundry-luna", "messages": [{"role": "user", "content": "distinct-prompt-7f3"}]},
                                           headers={"Authorization": "Bearer right-secret"})
                finally:
                    server.shutdown()
                    server.server_close()
                credential.assert_not_called()
                forward.assert_not_called()
            self.assertEqual(reply.status_code, 200)
            self.assertEqual(reply.json()["model"], "foundry-luna")
            entry = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
            self.assertTrue(entry["result"]["stub"])
            self.assertNotIn("distinct-prompt-7f3", log.read_text(encoding="utf-8"))


class ClaudeProxy(unittest.TestCase):
    def test_tool_round_trip_translates_to_messages(self):
        import foundry_claude_proxy as proxy
        body = {"model": "x", "temperature": 1.5, "parallel_tool_calls": False, "stop": "END", "messages": [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Weather in Oslo and Paris?"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "Oslo"}'}},
                {"id": "c2", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "12C"},
            {"role": "tool", "tool_call_id": "c2", "content": "18C"}],
            "tools": [{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object"}}}]}
        out = proxy.chat_to_messages(body, "claude-dep")
        self.assertEqual((out["model"], out["max_tokens"], out["temperature"]), ("claude-dep", 8192, 1.0))
        self.assertEqual(out["system"], [{"type": "text", "text": "Be brief."}])
        self.assertEqual([m["role"] for m in out["messages"]], ["user", "assistant", "user"])
        self.assertEqual([b["input"] for b in out["messages"][1]["content"]], [{"city": "Oslo"}, {"city": "Paris"}])
        self.assertEqual([b["tool_use_id"] for b in out["messages"][2]["content"]], ["c1", "c2"])
        self.assertEqual(out["tools"][0]["input_schema"], {"type": "object"})
        self.assertEqual(out["tool_choice"], {"type": "auto", "disable_parallel_tool_use": True})
        self.assertEqual(out["stop_sequences"], ["END"])
        with self.assertRaises(proxy.TranslationError):
            proxy.chat_to_messages(dict(body, n=2), "claude-dep")

    def test_parallel_tool_use_stream_becomes_two_indexed_tool_calls(self):
        import foundry_claude_proxy as proxy
        events = [
            {"type": "message_start", "message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": 5}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "t1", "name": "w"}},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "t2", "name": "w"}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"city": "Paris"}'}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"city": "Oslo"}'}},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 7}},
            {"type": "message_stop"}]
        stream = proxy.MessagesStream("alias", include_usage=True)
        chunks = [chunk for event in events for chunk in stream.feed(event)]
        args, ids = {}, {}
        for chunk in chunks:
            for call in (chunk["choices"][0]["delta"].get("tool_calls") or []) if chunk["choices"] else []:
                ids.setdefault(call["index"], call.get("id"))
                args[call["index"]] = args.get(call["index"], "") + call["function"].get("arguments", "")
        self.assertEqual(ids, {0: "t1", 1: "t2"})
        self.assertEqual({i: json.loads(a) for i, a in args.items()}, {0: {"city": "Oslo"}, 1: {"city": "Paris"}})
        self.assertEqual(chunks[-2]["choices"][0]["finish_reason"], "tool_calls")
        self.assertEqual(chunks[-1]["usage"], {"prompt_tokens": 15, "completion_tokens": 7, "total_tokens": 22,
                                               "prompt_tokens_details": {"cached_tokens": 5}})

    def test_responses_stream_uses_final_arguments_not_garbled_deltas(self):
        import foundry_claude_proxy as proxy
        item = {"type": "function_call", "call_id": "c1", "name": "w"}
        events = [
            {"type": "response.created"},
            {"type": "response.output_item.added", "output_index": 0, "item": item},
            {"type": "response.function_call_arguments.delta", "output_index": 0, "delta": '{"city": "Oslo"}'},
            {"type": "response.function_call_arguments.delta", "output_index": 0, "delta": "}"},
            {"type": "response.output_item.done", "output_index": 0, "item": dict(item, arguments='{"city": "Paris"}')},
            {"type": "response.completed", "response": {"usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}}}]
        stream = proxy.ResponsesStream("alias", include_usage=False)
        chunks = [chunk for event in events for chunk in stream.feed(event)]
        arguments = "".join(call["function"].get("arguments", "") for chunk in chunks
                            for call in chunk["choices"][0]["delta"].get("tool_calls") or [])
        self.assertEqual(json.loads(arguments), {"city": "Paris"})
        self.assertEqual(chunks[-1]["choices"][0]["finish_reason"], "tool_calls")

    def test_bad_secret_and_unknown_model_never_reach_foundry(self):
        import contextlib
        import io
        import threading
        import foundry_claude_proxy as proxy
        config = load_config(EXAMPLE_CONFIG_PATH)
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            log = Path(directory) / "proxy.jsonl"
            server = proxy.Server(("127.0.0.1", 0), config, "right-secret", proxy.model_map(config), log, key="k")
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with patch.object(server, "upstream") as upstream:
                    url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
                    body = {"model": config["claude_deployment_name"], "messages": [{"role": "user", "content": "prompt-9c1"}]}
                    wrong = httpx.post(url, json=body, headers={"Authorization": "Bearer wrong-secret"})
                    unknown = httpx.post(url, json=dict(body, model="gpt-5.2"), headers={"api-key": "right-secret"})
                    upstream.assert_not_called()
            finally:
                server.shutdown()
                server.server_close()
            self.assertEqual((wrong.status_code, unknown.status_code), (401, 404))
            self.assertEqual(unknown.json()["error"]["code"], "model_not_found")
            text = log.read_text(encoding="utf-8")
            self.assertNotIn("wrong-secret", text)
            self.assertNotIn("prompt-9c1", text)


class CliProbe(unittest.TestCase):
    def test_command_names_come_from_the_commands_section_only(self):
        import probe_cli_fullswitch
        help_text = (
            "Options:\n  -p, --print   Print\n\nCommands:\n"
            "  persist                     Start a session that survives terminal\n"
            "                              disconnects\n"
            "  status|whoami [options]     View authentication status\n"
            "  bedrock                     Configure AWS Bedrock usage for CLI\n"
            "  help [command]              Display help for command\n"
        )
        self.assertEqual(probe_cli_fullswitch.commands_from_help(help_text), ["persist", "status", "bedrock", "help"])


class KeyRouteProbe(unittest.TestCase):
    def test_cases_cover_both_models_and_both_claude_headers_without_a_key(self):
        import probe_key_routes
        config = {"account_name": "res", "deployment_name": "gpt-dep", "claude_deployment_name": "claude-dep",
                  "anthropic_base_url": "https://res.services.ai.azure.com/anthropic"}
        cases = probe_key_routes.cases(config)
        self.assertEqual(len(cases), 10)
        slot_style = [c for c in cases if c[1].startswith("legacy Azure")]
        self.assertEqual({c[0] for c in slot_style}, {"GPT", "Claude"})
        self.assertTrue(all(c[4] == {"api-key": None} for c in cases if c[3].get("messages") and "openai" in c[2]))
        messages = {c[1]: c[4] for c in cases if c[2].endswith("/v1/messages")}
        self.assertIn("x-api-key", messages["Anthropic Messages (x-api-key)"])
        self.assertIn("api-key", messages["Anthropic Messages (api-key)"])
        self.assertTrue(all(value is None or value == "2023-06-01" for h in messages.values() for value in h.values()))


class AgentLogSummary(unittest.TestCase):
    def test_turns_keep_routing_and_errors_but_drop_ids(self):
        import summarize_cursor_agent_log as summary
        conv = "0b7c1e52-9f3a-4d1e-8c2b-6a5f4e3d2c1b"
        lines = [
            "2026-11-17 17:40:16.100 [info] [agent-harness] turn -> conversation=" + conv + " model=foundry-haiku\n",
            '2026-11-17 17:40:16.200 [info] Selected Agent Host turn runtime {"runtime":"connect","disposition":"fallback","reason":"byok-connect-routed"}\n',
            '2026-11-17 17:40:17.300 [warning] retry {"caughtError":"ConnectError: [unauthenticated] Error"}\n',
            "2026-11-17 17:40:17.400 [info] [AGENT_ERROR_DIAGNOSTICS] request=" + conv + " decision=THROW ActionRequiredError\n",
            '2026-11-17 17:40:17.500 [info] {"underlyingConnectError":{"code":16,"codeName":"Unauthenticated"}}\n',
            "2026-11-17 17:40:17.600 [info] Agent host turn failed\n",
            "2026-11-17 17:40:17.700 [error] Invalid API key. Request " + conv + "\n",
            "2026-11-17 17:45:00.000 [info] [agent-harness] turn -> model=grok-4.7\n",
            '2026-11-17 17:45:00.100 [info] Selected Agent Host turn runtime {"runtime":"managed-local","disposition":"expected","reason":"eligible"}\n',
        ]
        turns = summary.summarize(lines, offset_minutes=60)
        self.assertEqual(len(turns), 2)
        failed, ok = turns
        self.assertEqual((failed["model"], failed["reason"], failed["outcome"]), ("foundry-haiku", "byok-connect-routed", "failed"))
        self.assertEqual(failed["backend_errors"], {"unauthenticated": 1})
        self.assertEqual(failed["decisions"], ["THROW ActionRequiredError"])
        self.assertEqual(failed["final_grpc_code"], {"code": 16, "name": "Unauthenticated"})
        self.assertEqual((failed["started_utc"], failed["ended_utc"]), ("2026-11-17T16:40:16Z", "2026-11-17T16:40:17Z"))
        self.assertEqual(failed["error_message"], "Invalid API key. Request <id>")
        self.assertEqual((ok["reason"], ok["outcome"]), ("eligible", "no failure logged"))
        self.assertNotIn(conv, json.dumps(turns))


if __name__ == "__main__":
    unittest.main()
