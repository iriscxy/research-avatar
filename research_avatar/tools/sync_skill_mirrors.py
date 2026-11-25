#!/usr/bin/env python3
"""Synchronize Claude Code skill mirrors from canonical Codex skills.

``.agents/skills`` is the sole editable source. This tool rebuilds the
corresponding ``.claude/skills`` directories while adapting invocation syntax.
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / ".agents" / "skills"
TARGET_ROOT = ROOT / ".claude" / "skills"


def is_disposable(path: Path) -> bool:
    """Return whether a generated filesystem entry must never enter a mirror."""
    return (
        "__pycache__" in path.parts
        or path.suffix.lower() in {".pyc", ".pyo"}
        or path.name == ".DS_Store"
    )

def skill_names() -> tuple[str, ...]:
    return tuple(
        path.name
        for path in sorted(SOURCE_ROOT.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    )


def adapt_invocations(text: str, names: tuple[str, ...]) -> str:
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(
            rf"(?<![A-Za-z0-9_.-])\${re.escape(name)}\b",
            f"/{name}",
            text,
        )
    return text


def adapt_markdown(text: str, skill_name: str, names: tuple[str, ...]) -> str:
    # Skill bodies are runtime-specific mirrors, but the shared maintenance
    # README must keep pointing contributors to the canonical .agents source.
    if skill_name:
        text = text.replace(".agents/skills", ".claude/skills")
    text = text.replace("Codex `spawn_agent` tool", "Agent tool")
    text = text.replace("Codex `spawn_agent`", "the Agent tool")
    text = text.replace("Codex Plan tracking", "native Plan tracking")
    text = adapt_invocations(text, names)
    return text


def build_mirror(destination: Path) -> None:
    names = skill_names()
    destination.mkdir(parents=True, exist_ok=True)
    readme = SOURCE_ROOT / "README.md"
    if readme.is_file():
        destination.joinpath("README.md").write_text(
            adapt_markdown(readme.read_text(encoding="utf-8"), "", names),
            encoding="utf-8",
        )
    for name in names:
        source_dir = SOURCE_ROOT / name
        target_dir = destination / name
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in source_dir.rglob("*"):
            if not source.is_file() or is_disposable(source):
                continue
            relative = source.relative_to(source_dir)
            if relative.parts[:1] == ("agents",):
                continue
            target = target_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() == ".md":
                target.write_text(
                    adapt_markdown(source.read_text(encoding="utf-8"), name, names),
                    encoding="utf-8",
                )
            else:
                shutil.copy2(source, target)


def file_snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not is_disposable(path)
    }


def report_difference(expected: dict[str, bytes], actual: dict[str, bytes]) -> None:
    for relative in sorted(expected.keys() | actual.keys()):
        if relative not in actual:
            print(f"missing mirror: {relative}")
        elif relative not in expected:
            print(f"unexpected mirror file: {relative}")
        elif expected[relative] != actual[relative]:
            print(f"different mirror: {relative}")
            if relative.endswith(".md"):
                before = actual[relative].decode("utf-8", errors="replace").splitlines()
                after = expected[relative].decode("utf-8", errors="replace").splitlines()
                diff = list(difflib.unified_diff(before, after, lineterm="", n=2))
                print("\n".join(diff[:20]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit nonzero when the Claude mirror differs from the canonical Agents skills",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="skill-mirror-") as temporary:
        expected_root = Path(temporary) / "skills"
        build_mirror(expected_root)
        expected = file_snapshot(expected_root)
        actual = file_snapshot(TARGET_ROOT)
        if args.check:
            if expected != actual:
                report_difference(expected, actual)
                return 1
            print("Claude skill mirror is synchronized with .agents/skills.")
            return 0

        if TARGET_ROOT.exists():
            shutil.rmtree(TARGET_ROOT)
        shutil.copytree(expected_root, TARGET_ROOT)
        print(f"Synchronized {len(skill_names())} skills: {SOURCE_ROOT} -> {TARGET_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
