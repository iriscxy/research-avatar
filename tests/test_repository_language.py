from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
TEXT_SUFFIXES = {
    ".bib",
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".jsonc",
    ".md",
    ".py",
    ".sh",
    ".sql",
    ".sty",
    ".tex",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {"Dockerfile", "Makefile"}


def repository_source_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item for item in result.stdout.decode("utf-8").split("\0") if item]


class RepositoryLanguageTests(unittest.TestCase):
    def test_repository_source_contains_no_han_characters(self):
        violations: list[str] = []
        for path in repository_source_paths():
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_FILENAMES:
                continue
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if HAN.search(line):
                    violations.append(f"{path.relative_to(ROOT)}:{line_number}")
        self.assertEqual([], violations, "Han characters found in repository source files")


if __name__ == "__main__":
    unittest.main()
