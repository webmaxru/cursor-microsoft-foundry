"""Post-study probes, separate from the prewritten acceptance suite.

Reports observed behavior without repairing the generated experiment artifacts.
Runs offline; no Cursor or Foundry inference.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "unclosed_amount_quote": 'date,category,amount\n2026-01-01,x,"1\n',
    "leading_zero_amount": "date,category,amount\n2026-01-01,x,00.50\n",
    "date_trailing_space": "date,category,amount\n2026-01-01 ,x,1\n",
}


def probe(project):
    spec = importlib.util.spec_from_file_location("ledger_probe", project / "ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observations = {}
    for name, text in CASES.items():
        try:
            observations[name] = {"returned": module.summarize_csv(text)}
        except ValueError as error:
            observations[name] = {"error": "ValueError", "message": str(error)}
    suites = {}
    for encoding in ("utf-8", "cp1252"):
        env = {**os.environ, "PYTHONIOENCODING": encoding}
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(project)],
            capture_output=True, env=env, timeout=60,
        )
        output = result.stderr.decode(encoding)
        count = re.search(r"Ran (\d+) tests?", output)
        suites[encoding] = {
            "exit_code": result.returncode,
            "tests_run": int(count[1]) if count else None,
            "unicode_decode_error": "UnicodeDecodeError" in output,
        }
    return {"api_probes": observations, "generated_suite_by_stdio_encoding": suites}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "scope": "Offline probes added after the timed comparison; not part of its prewritten acceptance suite or token totals.",
        "inputs": CASES,
        "encoding_note": "Explicit UTF-8 and CP1252 stdio reproduce the environment dependency; CP1252 is a Windows legacy encoding, not an inference failure.",
        "runs": {
            arm: probe(ROOT / "examples" / "ledger-lab" / arm)
            for arm in ("cursor-only", "foundry-heavy")
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
