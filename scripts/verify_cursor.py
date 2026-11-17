"""Verify actual Cursor CLI -> MCP -> both Foundry APIs, not just model self-report."""

import hashlib
import json

from cursor_runtime import ROOT, run_cursor
from foundry_client import load_config, request_body
from smoke_test import challenge


def main():
    openai_prompt, openai_expected = challenge()
    claude_prompt, claude_expected = challenge()
    config = load_config()
    audit_path = ROOT / "evidence" / "foundry-audit.jsonl"
    old_count = len(audit_path.read_text(encoding="utf-8").splitlines()) if audit_path.exists() else 0
    prompt = (
        "This is a synthetic integration test. Do not read files, run shell commands, browse, or use other tools. "
        "Call foundry-models foundry_openai exactly once with max_output_tokens=256 and this exact prompt: "
        + json.dumps(openai_prompt)
        + ". Then call foundry-models foundry_claude exactly once with max_output_tokens=256 and this exact prompt: "
        + json.dumps(claude_prompt)
        + ". Do not compute the answers yourself. Report each tool's exact text, deployment, model, and response_id. "
        "If either tool fails, report failure; do not invent output."
    )
    result = run_cursor([
        "--workspace", str(ROOT / "demo"), "--trust", "--mode", "ask", "--model", "auto",
        "--print", "--output-format", "json", prompt,
    ], timeout=240)
    output = result.stdout.strip()
    records = [
        json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()[old_count:]
    ] if audit_path.exists() else []
    openai_body = {**request_body(openai_prompt, 256), "model": config["deployment_name"]}
    claude_body = {
        "model": config["claude_deployment_name"], "max_tokens": 256,
        "messages": [{"role": "user", "content": claude_prompt}], "thinking": {"type": "disabled"},
    }
    expected_hashes = {
        config["deployment_name"]: (
            hashlib.sha256(json.dumps(openai_body, sort_keys=True, ensure_ascii=True).encode()).hexdigest(),
            hashlib.sha256(openai_expected.encode()).hexdigest(),
        ),
        config["claude_deployment_name"]: (
            hashlib.sha256(json.dumps(claude_body, sort_keys=True, ensure_ascii=True).encode()).hexdigest(),
            hashlib.sha256(claude_expected.encode()).hexdigest(),
        ),
    }
    matched = [
        record for record in records
        if record["response_id"] in output
        and (record["request_sha256"], record.get("response_sha256")) == expected_hashes.get(record["deployment"])
    ]
    success = (
        result.returncode == 0
        and openai_expected in output and claude_expected in output
        and set(expected_hashes) <= {r["deployment"] for r in matched}
    )
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
