"""Summarize Cursor IDE agent turns from the local Agent Host log, without ids or prompts.

When an own-key slot (OpenAI or Azure OpenAI) is on, the Cursor IDE logs how each agent turn was routed
and how it ended. This script reads `Cursor Agent Host.log`, finds each turn, and prints the routing
decision, the backend error codes, the retry decisions and the final error. Session, conversation,
request and generation ids are never copied out, and UUIDs or long hex ids in error text are masked.

Use it after a failed own-key turn to see whether the request was routed through Cursor's backend
(`byok-connect-routed`) and which error the backend returned. It reads only the local log; it can't see
what the backend sent to your provider. Check your provider's metrics or logs for that.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_NAME = "Cursor Agent Host.log"
LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) \[(\w+)\] (.*)$")
MODEL = re.compile(r"\[agent-harness\] turn -> .*?model=(\S+)")
RUNTIME = re.compile(r'Selected Agent Host turn runtime \{"runtime":"([^"]+)","disposition":"([^"]+)","reason":"([^"]+)"')
CAUGHT = re.compile(r'"caughtError":"ConnectError: \[(\w+)\]')
DECISION = re.compile(r"\[AGENT_ERROR_DIAGNOSTICS\] .*?decision=([A-Z]+(?: \w+)?)")
CODE_NAME = re.compile(r'"underlyingConnectError":\{"code":(\d+),"codeName":"(\w+)"')
IDS = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\b[0-9a-f]{12,}\b", re.I)


def default_log():
    homes = [Path(os.environ.get("APPDATA", "")) / "Cursor" / "logs",
             Path.home() / "Library" / "Application Support" / "Cursor" / "logs",
             Path.home() / ".config" / "Cursor" / "logs"]
    found = [p for home in homes if home.is_dir() for p in home.glob(f"*/window*/exthost/anysphere.cursor-agent-host/{LOG_NAME}")]
    if not found:
        sys.exit(f"No '{LOG_NAME}' found; pass --log PATH.")
    return max(found, key=lambda p: p.stat().st_mtime)


def to_utc(stamp, offset_minutes):
    local = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S.%f")
    if offset_minutes is None:
        moment = local.astimezone().astimezone(timezone.utc)
    else:
        moment = local.replace(tzinfo=timezone.utc) - timedelta(minutes=offset_minutes)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def mask(text):
    return IDS.sub("<id>", text)[:200]


def summarize(lines, offset_minutes=None):
    turns, model, current, expect_message = [], None, None, False
    for raw in lines:
        match = LINE.match(raw.rstrip("\n"))
        if not match:
            continue
        stamp, level, body = match.groups()
        if expect_message:
            expect_message = False
            if level == "error" and current is not None:
                current["error_message"] = mask(body)
                continue
        if found := MODEL.search(body):
            model = found.group(1)
        elif found := RUNTIME.search(body):
            current = {"started_utc": to_utc(stamp, offset_minutes),
                       "model": model, "runtime": found.group(1), "disposition": found.group(2),
                       "reason": found.group(3), "backend_errors": {}, "decisions": [], "outcome": "no failure logged"}
            turns.append(current)
            model = None
        elif current is None:
            continue
        elif found := CAUGHT.search(body):
            current["backend_errors"][found.group(1)] = current["backend_errors"].get(found.group(1), 0) + 1
        elif found := DECISION.search(body):
            current["decisions"].append(found.group(1))
        elif found := CODE_NAME.search(body):
            current["final_grpc_code"] = {"code": int(found.group(1)), "name": found.group(2)}
        elif body.startswith("Agent host turn failed"):
            current["outcome"] = "failed"
            current["ended_utc"] = to_utc(stamp, offset_minutes)
            expect_message = True
    return turns


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, help=f"path to '{LOG_NAME}' (default: newest Cursor log)")
    parser.add_argument("--since", help="only turns at or after this UTC time, e.g. 2026-11-17T16:00:00Z")
    parser.add_argument("--utc-offset-minutes", type=int, help="local offset of the log clock (default: this machine's)")
    parser.add_argument("--out", type=Path, help="also write the JSON here")
    args = parser.parse_args()
    log = args.log or default_log()
    with log.open(encoding="utf-8", errors="replace") as handle:
        turns = summarize(handle, args.utc_offset_minutes)
    if args.since:
        since = args.since.replace("Z", "+00:00")
        turns = [t for t in turns if datetime.fromisoformat(t["started_utc"].replace("Z", "+00:00")) >= datetime.fromisoformat(since)]
    result = {"source": LOG_NAME, "turns": turns}
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
