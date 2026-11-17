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


if __name__ == "__main__":
    unittest.main()
