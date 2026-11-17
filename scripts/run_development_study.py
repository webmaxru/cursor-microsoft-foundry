"""Run Cursor-only and Foundry-heavy development in fresh synthetic workspaces.

Consumes Cursor and Foundry quota. Raw transcripts stay under ignored evidence/.
No provider key is copied into either workspace. Run with the configured venv.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from cursor_runtime import ROOT, cursor_command

SPEC = """Build Ledger Lab, a tiny offline Python 3.12 stdlib application from scratch.
Create ledger.py, test_ledger.py and README.md (plus .foundry/ work files if delegating).
No network from the application, dependencies or git commands.
API: summarize_csv(text: str) -> dict[str, str]. Input CSV must have exactly the headers
date,category,amount in that order. Dates must be real calendar dates in exact YYYY-MM-DD format.
Category must be nonempty after trimming; preserve internal punctuation, support CSV quoting.
Amount must be ordinary decimal notation (no scientific notation), nonnegative, finite,
at most two fractional digits. Accept integers. Reject malformed rows including extra/missing
cells. Raise ValueError with useful messages for invalid input. Header-only input returns {}.
Sum with Decimal, output two decimal places, categories alphabetically sorted.
CLI: python ledger.py input.csv prints the summary as JSON; invalid files/input produce
a useful stderr message, nonzero exit, and no partial JSON on stdout.
Write meaningful unittest tests and concise usage documentation.
Run python -m unittest -v, repair failures, and report actual results.
"""
FOLLOWUPS = [
    """Extend Ledger Lab with month: str | None = None on summarize_csv and --month YYYY-MM
on the CLI. A supplied month must be exact YYYY-MM with month 01..12, even for empty data.
Filter totals, but validate EVERY input row, including excluded months. Preserve the initial
contract. Add tests, update README, run python -m unittest -v and fix failures.""",
    """This is a fresh session handoff. Read the existing code, tests and README as the source
of truth. Extend summarize_csv with allow_refunds: bool = False and CLI --refunds to allow
negative amounts only when enabled. Preserve strict money format, all validation, month
filtering and sorted exact totals. Normalize a zero total to "0.00", not "-0.00".
Add combined month/refunds regression tests and usage docs. Run python -m unittest -v and
repair failures. Explain any context you had to reconstruct.""",
]
POLICY = """Use Foundry inference for as much substantive work as this bridge permits:
delegate design and production code to foundry_openai, and test design/review to foundry_claude.
For each follow-up, delegate the implementation change and regression review again.
You remain the orchestrator: read files, send explicit relevant code/contracts/errors,
apply returned code, run tests and integrate corrections. Do not silently substitute your
own implementation if a tool fails; report it and retry only a smaller bounded task.
Each tool is STATELESS, has an 8000-character input limit and 2048-token output limit.
Split work into small complete files or functions, request at most 1800 output tokens.
Keep each request self-contained. No secrets. Do not ask the models to access files.
Use actual MCP calls only. Do not import or call the underlying Python API clients.
If native MCP tools are unavailable, STOP; do not substitute a different transport.
Before final response, write actual decisions and remaining constraints into README.md.
"""


def records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def run(command, cwd, timeout=900):
    started = time.monotonic()
    env = {**os.environ, "CURSOR_INVOKED_AS": "agent",
           "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")}
    result = subprocess.run(command, cwd=cwd, env=env,
                            text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
    return result, round(time.monotonic() - started, 3)


def prepare(workspace, foundry, transport):
    workspace.mkdir(parents=True)
    # Cursor resolves project MCP configuration at the Git root, not a nested cwd.
    subprocess.run(["git", "init", "--quiet", str(workspace)], check=True, timeout=30)
    config_dir = workspace / ".cursor"
    config_dir.mkdir()
    allow = ["Read(**)", "Write(ledger.py)", "Write(test_ledger.py)", "Write(README.md)",
             "Shell(python:*)"]
    if foundry:
        allow += ["Write(.foundry/requests/**)", "Write(.foundry/proposals/**)"]
        if transport == "native":
            allow += ["Mcp(foundry-models:foundry_openai)", "Mcp(foundry-models:foundry_claude)"]
    config = {"permissions": {"allow": allow, "deny": ["WebFetch(*)", "Read(.env*)", "Write(.cursor/**)"]}}
    (config_dir / "cli.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    servers = {"foundry-models": {"type": "stdio", "command": sys.executable,
                                "args": [str(ROOT / "scripts" / "foundry_mcp.py")]}} if foundry and transport == "native" else {}
    (config_dir / "mcp.json").write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
    if foundry and transport == "native":
        result, _ = run(cursor_command() + ["--workspace", str(workspace), "mcp", "enable", "foundry-models"], workspace, 60)
        if result.returncode:
            raise RuntimeError("Could not enable the experiment's MCP server: " + result.stderr)


def execute_phase(workspace, directory, label, prompt, model, session=None):
    audit = ROOT / "evidence" / "foundry-audit.jsonl"
    offset = len(records(audit))
    client_offset = len(records(workspace / ".foundry" / "calls.jsonl"))
    args = ["--workspace", str(workspace), "--trust", "--model", model, "--print", "--output-format", "stream-json"]
    if session:
        args += ["--resume", session]
    command = cursor_command() + args + [prompt]
    started = time.monotonic()
    timed_out = False
    try:
        result, duration = run(command, workspace)
    except subprocess.TimeoutExpired as error:
        timed_out = True
        duration = round(time.monotonic() - started, 3)
        stdout, stderr = error.stdout or "", error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        result = subprocess.CompletedProcess(command, 124, stdout, stderr + "\nCursor exceeded the 900-second phase limit.")
    (directory / f"{label}.jsonl").write_text(result.stdout, encoding="utf-8")
    (directory / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    events = []
    for line in result.stdout.splitlines():
        if line.startswith("{"):
            events.append(json.loads(line))
    terminal = next((e for e in reversed(events) if e.get("type") == "result"), {})
    # Correlate Azure responses to this Cursor transcript, not merely a time window.
    correlated = [r for r in records(audit)[offset:] if r.get("response_id") and r["response_id"] in result.stdout]
    record = {
        "phase": label, "exit_code": result.returncode, "wall_seconds": duration, "timed_out": timed_out,
        "cursor_usage": terminal.get("usage"), "cursor_result_error": terminal.get("is_error"),
        "cursor_model": next((e.get("model") for e in events if e.get("type") == "system"), None),
        "terminal_present": bool(terminal), "foundry_calls": correlated,
        "mcp_client_calls": records(workspace / ".foundry" / "calls.jsonl")[client_offset:],
        "tool_calls": [e.get("tool_call") for e in events if e.get("type") == "tool_call" and e.get("subtype") == "completed"],
    }
    (directory / f"{label}.metrics.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"{workspace.name} {label}: exit={result.returncode} seconds={duration} foundry_calls={len(correlated)} usage={terminal.get('usage')}", flush=True)
    if result.returncode or not terminal or terminal.get("is_error"):
        raise RuntimeError(f"Cursor failed in {label}; raw evidence preserved in {directory}.")
    return terminal.get("session_id"), record


def delegation_policy(transport):
    if transport == "native":
        return POLICY
    return f"""Use the explicitly selected SHELL-INVOKED MCP CLIENT transport, not native Cursor
MCP dispatch (unavailable here), and NEVER call the Foundry Python API clients directly.
The client uses real MCP stdio tools and saves their text as proposal files without executing it.
Use Foundry for substantive implementation, then for independent review/test design.
1. Write a self-contained request to .foundry/requests/<unique-name>.txt with the exact
   contract and relevant current code. Max 8000 characters. Use your file editing tools.
2. Run: python "{ROOT / 'scripts' / 'development_worker.py'}" --model openai --prompt
   .foundry/requests/<unique-name>.txt --out <unique-name>.py --max-output-tokens 1800
   (one single-line command). The command prints metadata, not code.
3. Read the proposal under .foundry/proposals/, inspect it, and copy/apply it to ledger.py.
   For an unchanged complete file you may use a short python shutil.copyfile command.
4. Repeat with --model claude for a bounded review and test design, saving a .txt proposal.
   Include the current code and exact invariants. Cursor may implement the proposed tests.
   Do not ask for a full large test file in one response.
5. Run python -m unittest -v, repair issues via focused MCP requests, and update README.
Keep calls bounded; no repeated health checks or requests for a model to certify PASS.
If a call fails, report it and split the task; never silently replace it with direct SDK calls.
Both Foundry models must do useful work on each stage. All calls are stateless.
No secrets. Cursor remains responsible for context, tests and integration.
"""


def verified_transport(metrics, transport):
    ids = {c["response_id"] for c in metrics["foundry_calls"]}
    if transport == "shell-mcp":
        return bool(ids) and ids <= {c["response_id"] for c in metrics["mcp_client_calls"]}
    successes = []
    for tool in metrics["tool_calls"]:
        call = tool.get("mcpToolCall", {})
        if call.get("result", {}).get("success"):
            successes.append(call)
    serialized = json.dumps(successes)
    return bool(ids) and all(response_id in serialized for response_id in ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("cursor-only", "foundry-heavy"), required=True)
    parser.add_argument("--out", type=Path, required=True, help="Fresh directory under evidence/")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--transport", choices=("native", "shell-mcp"), default="native")
    args = parser.parse_args()
    directory = args.out.resolve()
    if not directory.is_relative_to(ROOT / "evidence") or directory.exists():
        parser.error("--out must be a new directory inside evidence/")
    directory.mkdir(parents=True)
    workspace = directory / args.arm
    foundry = args.arm == "foundry-heavy"
    prepare(workspace, foundry, args.transport)
    summary = {"arm": args.arm, "started_utc": datetime.now(timezone.utc).isoformat(),
               "model_requested": args.model, "transport": args.transport if foundry else "none", "phases": []}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    session = None
    for stage, brief in enumerate([SPEC, *FOLLOWUPS], 1):
        prompt = (delegation_policy(args.transport) if foundry else "Use Cursor's own model. Do not use any MCP tools.\n") + brief
        if stage == 3:
            session = None
        session, metrics = execute_phase(workspace, directory, f"stage-{stage}", prompt, args.model, session)
        summary["phases"].append(metrics)
        if foundry and (len({call["route"] for call in metrics["foundry_calls"]}) < 2
                        or not verified_transport(metrics, args.transport)):
            (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            raise RuntimeError(f"Stage {stage} did not verify both Foundry tools; do not claim delegated development.")
        check, _ = run([sys.executable, str(ROOT / "scripts" / "development_acceptance.py"),
                        str(workspace), "--stage", str(stage)], workspace, 60)
        (directory / f"stage-{stage}.acceptance.txt").write_text(check.stdout + check.stderr, encoding="utf-8")
        metrics["acceptance_exit_code"] = check.returncode
        if check.returncode:
            repair = ("Repair the failures from independent acceptance checks. Preserve the documented contract. "
                      "Run your tests again.\n" + check.stdout + check.stderr)
            if foundry:
                repair = delegation_policy(args.transport) + repair
            session, fix = execute_phase(workspace, directory, f"stage-{stage}-repair", repair, args.model, session)
            summary["phases"].append(fix)
            if foundry and not verified_transport(fix, args.transport):
                raise RuntimeError("Repair did not use the requested MCP transport; evidence retained.")
            check, _ = run([sys.executable, str(ROOT / "scripts" / "development_acceptance.py"),
                            str(workspace), "--stage", str(stage)], workspace, 60)
            (directory / f"stage-{stage}.repair-acceptance.txt").write_text(check.stdout + check.stderr, encoding="utf-8")
            fix["acceptance_exit_code"] = check.returncode
        (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if check.returncode:
            raise RuntimeError(f"Acceptance still fails after one repair in stage {stage}. Evidence retained.")
    print("All three stages passed independent acceptance.", flush=True)


if __name__ == "__main__":
    main()
