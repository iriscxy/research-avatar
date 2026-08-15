#!/usr/bin/env python3
"""One stable entry point for repository setup, tests, validation, and paper builds."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> int:
    process = subprocess.run(
        command, cwd=ROOT, encoding="utf-8", errors="replace", check=False
    )
    return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "test", "validate", "paper"])
    args = parser.parse_args()
    if args.command == "setup":
        return run([sys.executable, "-m", "pip", "install", "-r", "requirements.lock"])
    if args.command == "test":
        return run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    if args.command == "validate":
        commands = [
            [sys.executable, "-m", "compileall", "-q", "tools", "paper_studio"],
            ["node", "--check", "paper_studio/static/app.js"],
        ]
        if (ROOT / "paper" / "main.tex").is_file():
            commands.append(
                [sys.executable, "tools/paper_preflight.py", "--paper-dir", "paper", "--source-only"]
            )
        for command in commands:
            code = run(command)
            if code:
                return code
        return 0
    return run([
        sys.executable, "tools/paper_preflight.py", "--paper-dir", "paper", "--compile",
        "--render-dir", "paper/.paper_preflight/pages",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
