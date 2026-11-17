"""Launch the same version-local Node entry point used by the installed Windows wrapper."""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cursor_command():
    if os.name != "nt":
        return ["agent"]
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", "(Get-Command agent -ErrorAction Stop).Source"],
        text=True, capture_output=True, check=True, timeout=15,
    )
    launcher = Path(result.stdout.strip())
    base = launcher.parent
    if not (base / "node.exe").is_file():
        versions = [
            path for path in (base / "versions").iterdir()
            if path.is_dir() and re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}(?:-\d{2}-\d{2}-\d{2})?-[a-f0-9]+", path.name)
        ]
        if not versions:
            raise RuntimeError("No versioned Cursor CLI installation found.")
        base = max(versions, key=lambda path: tuple(int(n) for n in path.name.split("-")[0].split(".")))
    if not (base / "index.js").is_file():
        raise RuntimeError("Cursor CLI entry point is missing.")
    return [str(base / "node.exe"), str(base / "index.js")]


def run_cursor(arguments, *, env=None, timeout=180):
    child_env = dict(os.environ if env is None else env)
    child_env["CURSOR_INVOKED_AS"] = "agent"
    return subprocess.run(
        cursor_command() + arguments,
        cwd=ROOT / "demo", env=child_env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
