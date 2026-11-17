"""Export an allowlisted, identifier-free summary of local development-study runs."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

CURSOR_COUNTERS = ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens", "reasoningTokens")


def total_usage(usages, fields):
    """Missing usage stays unknown rather than becoming a zero-cost success."""
    if not usages or any(u is None or any(k not in u for k in fields) for u in usages):
        return None
    return {key: sum(u[key] for u in usages) for key in fields}


def summarize_run(directory):
    data = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    recorded = {p["phase"]: p for p in data["phases"]}
    # A failed/timed-out turn can have metrics but never reach summary persistence.
    for path in sorted(directory.glob("stage-*.metrics.json")):
        phase = json.loads(path.read_text(encoding="utf-8"))
        recorded.setdefault(phase["phase"], phase)
    phases = []
    previous_session = None
    for phase in sorted(recorded.values(), key=lambda p: p["phase"]):
        events = [json.loads(line) for line in (directory / f"{phase['phase']}.jsonl").read_text(
            encoding="utf-8").splitlines() if line.startswith("{")]
        terminal = next((e for e in reversed(events) if e.get("type") == "result"), {})
        session = terminal.get("session_id")
        reused = session == previous_session if session else None
        previous_session = session
        counts = Counter()
        shell_outcomes = Counter()
        shell_exits = []
        native_successes, native_errors = 0, 0
        for tool in phase["tool_calls"]:
            for name, value in tool.items():
                if name.endswith("ToolCall"):
                    counts[name] += 1
                if name == "shellToolCall":
                    result = value.get("result", {})
                    outcome = next((key for key in ("success", "failure", "rejected", "error") if key in result), "unknown")
                    shell_outcomes[outcome] += 1
                    shell_exits.append(result.get(outcome, {}).get("exitCode"))
                if name == "mcpToolCall":
                    native_successes += int(bool(value.get("result", {}).get("success")))
                    native_errors += int(bool(value.get("result", {}).get("error")))
        calls = [
            {key: call.get(key) for key in ("route", "configured_model", "configured_model_version",
                                           "usage", "request_sha256", "response_sha256")}
            for call in phase["foundry_calls"]
        ]
        phases.append({
            "phase": phase["phase"], "wall_seconds": phase["wall_seconds"],
            "timed_out": phase.get("timed_out", False),
            "exit_code": phase["exit_code"], "terminal_present": phase["terminal_present"],
            "cursor_model": phase["cursor_model"], "cursor_usage": phase["cursor_usage"],
            "mcp_client_call_count": len(phase.get("mcp_client_calls", [])),
            "native_mcp_success_count": native_successes, "native_mcp_error_count": native_errors,
            "session_reused_from_previous": reused,
            "acceptance_exit_code": phase.get("acceptance_exit_code"),
            "completed_tool_counts": dict(counts), "shell_outcomes": dict(shell_outcomes),
            "shell_exit_codes": shell_exits,
            "foundry_calls": calls,
        })
    workspace = directory / data["arm"]
    artifacts = {}
    for name in ("ledger.py", "test_ledger.py", "README.md"):
        if not (workspace / name).is_file():
            artifacts[name] = None
            continue
        content = (workspace / name).read_bytes()
        artifacts[name] = {"sha256": hashlib.sha256(content).hexdigest(),
                           "bytes": len(content), "lines": len(content.splitlines())}
    calls = [call for phase in phases for call in phase["foundry_calls"]]
    by_model = {}
    for model in sorted({c["configured_model"] for c in calls}):
        model_calls = [c for c in calls if c["configured_model"] == model]
        by_model[model] = {
            "calls": len(model_calls),
            "usage": total_usage([c["usage"] for c in model_calls], ("input_tokens", "output_tokens")),
        }
    return {
        "arm": data["arm"], "started_utc": data["started_utc"],
        "model_requested": data["model_requested"], "transport": data.get("transport", "unverified pilot"),
        "completed_all_stages": all(
            any(p["phase"].startswith(f"stage-{stage}") and p["acceptance_exit_code"] == 0 for p in phases)
            for stage in (1, 2, 3)
        ),
        "phases": phases,
        "cursor_usage_totals": total_usage([p["cursor_usage"] for p in phases], CURSOR_COUNTERS),
        "foundry_usage_totals": total_usage([c["usage"] for c in calls], ("input_tokens", "output_tokens")) if calls else (
            {"input_tokens": 0, "output_tokens": 0} if data["arm"] == "cursor-only" else None
        ),
        "foundry_calls": len(calls), "foundry_by_model": by_model,
        "wall_seconds": round(sum(p["wall_seconds"] for p in phases), 3),
        "artifacts": artifacts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true", help="Label excluded, potentially incomplete setup pilots")
    parser.add_argument("--preflight", type=Path, nargs="*", default=[])
    parser.add_argument("--preflight-encoding", default="utf-8")
    args = parser.parse_args()
    result = {
        "design": ("Excluded setup pilots, not an MCP comparison. Interrupted turns may lack usage."
                   if args.pilot else "One sequential paired case; three stages per arm; stage 2 resumes, stage 3 starts fresh."),
        "limits": [
            "Use each run's model_requested field; Auto pilots are not pinned-model controls.",
            "Cursor usage counters are reported separately; cache and reasoning counters are not added to input/output.",
            "Foundry usage covers successful responses correlated by response ID to Cursor tool output.",
            "Failed provider calls may be billed without a successful audit record.",
            "Wall time includes tools and local execution; not a controlled inference benchmark.",
            "Single small Python project, not a statistical cost estimate or production-scale evaluation.",
        ],
        "runs": [summarize_run(path) for path in args.runs],
        "preflights": [],
    }
    for path in args.preflight:
        events = [json.loads(line) for line in path.read_text(encoding=args.preflight_encoding).splitlines() if line.startswith("{")]
        terminal = next((e for e in reversed(events) if e.get("type") == "result"), {})
        result["preflights"].append({
            "label": path.stem,
            "model": next((e.get("model") for e in events if e.get("type") == "system"), None),
            "cursor_usage": terminal.get("usage"),
            "assistant_reported_unavailable": "unavailable" in terminal.get("result", "").lower(),
            "successful_native_mcp_calls": sum(
                bool(e.get("tool_call", {}).get("mcpToolCall", {}).get("result", {}).get("success"))
                for e in events if e.get("subtype") == "completed"
            ),
        })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
