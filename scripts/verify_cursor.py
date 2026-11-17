"""Verify actual Cursor CLI -> MCP -> both Foundry APIs, not just model self-report."""

import hashlib
import json

from cursor_runtime import ROOT, run_cursor
from foundry_client import load_config, request_body
from smoke_test import challenge

AUDIT_PATH = ROOT / "evidence" / "foundry-audit.jsonl"


def build_prompt(openai_prompt, claude_prompt):
    return (
        "This is a synthetic integration test. Do not read files, run shell commands, browse, or use other tools. "
        "Call foundry-models foundry_openai exactly once with max_output_tokens=256 and this exact prompt: "
        + json.dumps(openai_prompt)
        + ". Then call foundry-models foundry_claude exactly once with max_output_tokens=256 and this exact prompt: "
        + json.dumps(claude_prompt)
        + ". Do not compute the answers yourself. Report each tool's exact text, deployment, model, and response_id. "
        "If either tool fails, report failure; do not invent output."
    )


def expected_hashes(config, openai_prompt, openai_expected, claude_prompt, claude_expected):
    """Map each deployment to the (request, response) SHA-256 pair the bridge must audit."""
    openai_body = {**request_body(openai_prompt, 256), "model": config["deployment_name"]}
    claude_body = {
        "model": config["claude_deployment_name"], "max_tokens": 256,
        "messages": [{"role": "user", "content": claude_prompt}], "thinking": {"type": "disabled"},
    }

    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    return {
        config["deployment_name"]: (digest(json.dumps(openai_body, sort_keys=True, ensure_ascii=True)), digest(openai_expected)),
        config["claude_deployment_name"]: (digest(json.dumps(claude_body, sort_keys=True, ensure_ascii=True)), digest(claude_expected)),
    }


def audit_records(offset=0):
    if not AUDIT_PATH.exists():
        return []
    return [json.loads(line) for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines()[offset:] if line.strip()]


def correlate(records, output, expected):
    """Keep audit records whose exact request/answer hashes match and whose response ID Cursor displayed."""
    return [
        record for record in records
        if record.get("response_id") and record["response_id"] in output
        and (record.get("request_sha256"), record.get("response_sha256")) == expected.get(record.get("deployment"))
    ]


def proven(output, answers, expected, matched):
    return all(answer in output for answer in answers) and set(expected) <= {r["deployment"] for r in matched}


def main():
    openai_prompt, openai_expected = challenge()
    claude_prompt, claude_expected = challenge()
    config = load_config()
    old_count = len(audit_records())
    result = run_cursor([
        "--workspace", str(ROOT / "demo"), "--trust", "--mode", "ask", "--model", "auto",
        "--print", "--output-format", "json", build_prompt(openai_prompt, claude_prompt),
    ], timeout=240)
    output = result.stdout.strip()
    expected = expected_hashes(config, openai_prompt, openai_expected, claude_prompt, claude_expected)
    matched = correlate(audit_records(old_count), output, expected)
    success = result.returncode == 0 and proven(output, (openai_expected, claude_expected), expected, matched)
    evidence = {
        "passed": success, "cursor_orchestrator": "auto (Cursor-routed, not the Foundry deployment)",
        "exit_code": result.returncode, "expected": {"openai": openai_expected, "claude": claude_expected},
        "cursor_output": output, "stderr": result.stderr.strip()[:4000],
        "correlated_local_azure_audit": matched,
        "interpretation": "Cursor orchestrates; only the two MCP tool inferences are billed to Foundry.",
    }
    path = ROOT / "evidence" / "cursor-mcp-e2e.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if not success:
        raise RuntimeError("Cursor-to-Foundry proof failed. Inspect evidence; do not claim success.")


if __name__ == "__main__":
    main()
