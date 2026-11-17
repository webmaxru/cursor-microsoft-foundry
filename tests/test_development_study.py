import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from summarize_development_study import summarize_run, total_usage
from run_development_study import verified_transport
from development_worker import proposal_paths


class StudyAccounting(unittest.TestCase):
    def test_interrupted_turn_is_preserved_without_claiming_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "summary.json").write_text(json.dumps({
                "arm": "foundry-heavy", "started_utc": "test", "model_requested": "test",
                "phases": [],
            }), encoding="utf-8")
            phase = {"phase": "stage-1", "wall_seconds": 900, "exit_code": 124,
                     "timed_out": True, "terminal_present": False, "cursor_model": "test",
                     "cursor_usage": None, "tool_calls": [
                         {"shellToolCall": {"result": {"failure": {"exitCode": 1}}}},
                         {"shellToolCall": {"result": {"rejected": {"reason": ""}}}},
                     ], "foundry_calls": []}
            (root / "stage-1.metrics.json").write_text(json.dumps(phase), encoding="utf-8")
            (root / "stage-1.jsonl").write_text("", encoding="utf-8")
            result = summarize_run(root)
            self.assertFalse(result["completed_all_stages"])
            self.assertTrue(result["phases"][0]["timed_out"])
            self.assertIsNone(result["phases"][0]["acceptance_exit_code"])
            self.assertIsNone(result["cursor_usage_totals"])
            self.assertIsNone(result["artifacts"]["ledger.py"])
            self.assertEqual(result["phases"][0]["shell_outcomes"], {"failure": 1, "rejected": 1})
            self.assertEqual(result["phases"][0]["shell_exit_codes"], [1, None])

    def test_direct_sdk_response_cannot_count_as_mcp_evidence(self):
        metrics = {"foundry_calls": [{"response_id": "resp_test"}], "mcp_client_calls": [],
                   "tool_calls": [{"shellToolCall": {"result": {"success": {"stdout": "resp_test"}}}}]}
        self.assertFalse(verified_transport(metrics, "native"))
        self.assertFalse(verified_transport(metrics, "shell-mcp"))
        metrics["mcp_client_calls"] = [{"response_id": "resp_test"}]
        self.assertTrue(verified_transport(metrics, "shell-mcp"))
        self.assertFalse(verified_transport(metrics, "native"))

    def test_proposal_paths_reject_escape_and_overwrite_before_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / ".foundry" / "requests" / "task.txt"
            prompt.parent.mkdir(parents=True)
            prompt.write_text("synthetic", encoding="utf-8")
            source, target = proposal_paths(root, prompt, "code.py")
            self.assertEqual(source, prompt.resolve())
            for name in ("../escape.py", ".."):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    proposal_paths(root, prompt, name)
            outside = root / "outside.txt"
            outside.write_text("not a request", encoding="utf-8")
            with self.assertRaises(ValueError):
                proposal_paths(root, outside, "code.py")
            target.parent.mkdir()
            target.touch()
            with self.assertRaises(FileExistsError):
                proposal_paths(root, prompt, "code.py")

    def test_missing_usage_is_not_silently_counted_as_zero(self):
        for usages in ([], [None], [{"input_tokens": 5}], [{"input_tokens": 5, "output_tokens": 2}, None]):
            with self.subTest(usages=usages):
                self.assertIsNone(total_usage(usages, ("input_tokens", "output_tokens")))

    def test_cache_and_reasoning_are_not_double_counted(self):
        usages = [{"input_tokens": 5, "output_tokens": 2, "cached_tokens": 3, "reasoning_tokens": 1},
                  {"input_tokens": 7, "output_tokens": 4, "cached_tokens": 6, "reasoning_tokens": 2}]
        self.assertEqual(total_usage(usages, ("input_tokens", "output_tokens")),
                         {"input_tokens": 12, "output_tokens": 6})


if __name__ == "__main__":
    unittest.main()
