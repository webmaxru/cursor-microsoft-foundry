"""Verify Cursor IDE Agent -> MCP -> both Foundry APIs in two phases.

The IDE has no headless mode, so a person (or a UI-automation agent) pastes the
prompt from `prepare` into Agent chat, copies the finished chat transcript to a
text file, and runs `check`. Success requires the nonce answers *and* response
IDs in the transcript to match new hash-only records in the local audit log.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from cursor_runtime import ROOT
from foundry_client import load_config
from smoke_test import challenge
from verify_cursor import audit_records, build_prompt, correlate, expected_hashes, proven

STATE_PATH = ROOT / "evidence" / "ide-challenge.json"
EVIDENCE_PATH = ROOT / "evidence" / "ide-mcp-e2e.json"


def prepare():
    openai_prompt, openai_expected = challenge()
    claude_prompt, claude_expected = challenge()
    state = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_offset": len(audit_records()),
        "prompts": {"openai": openai_prompt, "claude": claude_prompt},
        "expected": {"openai": openai_expected, "claude": claude_expected},
        "agent_prompt": build_prompt(openai_prompt, claude_prompt),
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(state["agent_prompt"])


def check(transcript_path, surface):
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    transcript = Path(transcript_path).read_text(encoding="utf-8")
    expected = expected_hashes(
        load_config(), state["prompts"]["openai"], state["expected"]["openai"],
        state["prompts"]["claude"], state["expected"]["claude"],
    )
    matched = correlate(audit_records(state["audit_offset"]), transcript, expected)
    passed = proven(transcript, state["expected"].values(), expected, matched)
    evidence = {
        "passed": passed, "surface": surface,
        "cursor_orchestrator": "Cursor Agent model chosen in the IDE (Cursor-routed, not the Foundry deployment)",
        "challenge_created_at_utc": state["created_at_utc"],
        "expected": state["expected"], "cursor_transcript": transcript.strip(),
        "correlated_local_azure_audit": matched,
        "interpretation": "Cursor orchestrates; only the two MCP tool inferences are billed to Foundry.",
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if not passed:
        raise SystemExit("IDE-to-Foundry proof failed. Inspect evidence; do not claim success.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="phase", required=True)
    sub.add_parser("prepare", help="Create a fresh challenge and print the Agent prompt.")
    check_parser = sub.add_parser("check", help="Correlate a saved IDE transcript with the audit log.")
    check_parser.add_argument("transcript", help="UTF-8 text file with the copied Agent chat.")
    check_parser.add_argument("--surface", default="Cursor IDE Agent")
    args = parser.parse_args()
    prepare() if args.phase == "prepare" else check(args.transcript, args.surface)


if __name__ == "__main__":
    main()
