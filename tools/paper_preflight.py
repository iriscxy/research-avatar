#!/usr/bin/env python3
"""Fail-closed LaTeX dependency, source, compile, and final-PDF preflight."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


REQUIRED_COMMANDS = (
    "latexmk", "pdflatex", "bibtex", "kpsewhich", "pdftotext", "pdftoppm", "pdfinfo", "pdffonts"
)
UNSAFE_MATH_GLYPHS = re.compile(r"[≤≥≠≈→←×±∑∏√∞∈∉⊂⊆∪∩]")


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", check=False
    )


def read_tex_tree(main: Path, root: Path) -> tuple[str, list[dict]]:
    issues: list[dict] = []
    visited: set[Path] = set()

    def expand(path: Path) -> str:
        resolved = path.resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            issues.append({"issue": "tex_include_escapes_paper", "path": str(path)})
            return ""
        if resolved in visited:
            return ""
        visited.add(resolved)
        try:
            raw = resolved.read_bytes()
            source = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            issues.append({"issue": "tex_not_utf8_or_unreadable", "path": str(path), "error": str(exc)})
            return ""
        source = re.sub(r"(?m)(?<!\\)%.*$", "", source)
        parts, cursor = [], 0
        # Match only the TeX file-loading commands themselves.  Without the
        # control-word boundary, ``\\includegraphics`` is misread as
        # ``\\include`` followed by a bogus filename such as
        # ``graphics[width=...]``.
        for match in re.finditer(
            r"\\(?:input|include)(?![A-Za-z@])\s*(?:\{([^}]+)\}|([^\s%]+))",
            source,
        ):
            parts.append(source[cursor:match.start()])
            child = Path((match.group(1) or match.group(2)).strip())
            if not child.suffix:
                child = child.with_suffix(".tex")
            parts.append(expand(resolved.parent / child))
            cursor = match.end()
        parts.append(source[cursor:])
        return "".join(parts)

    return expand(main), issues


def source_checks(paper: Path, main: Path) -> list[dict]:
    source, issues = read_tex_tree(main, paper)
    styles = re.findall(r"\\bibliographystyle\s*\{([^}]+)\}", source)
    if len(styles) > 1:
        issues.append({"issue": "duplicate_bibliographystyle", "values": styles})
    for glyph in sorted(set(UNSAFE_MATH_GLYPHS.findall(source))):
        issues.append({"issue": "pdflatex_unsafe_unicode_math", "glyph": glyph})
    resources = []
    resources.extend((name.strip(), ".sty") for group in re.findall(r"\\usepackage(?:\[[^]]*\])?\{([^}]+)\}", source) for name in group.split(","))
    resources.extend((name.strip(), ".cls") for name in re.findall(r"\\documentclass(?:\[[^]]*\])?\{([^}]+)\}", source))
    for name, suffix in resources:
        local = paper / f"{name}{suffix}"
        if local.exists():
            continue
        probe = run(["kpsewhich", f"{name}{suffix}"], cwd=paper) if shutil.which("kpsewhich") else None
        if probe is None or probe.returncode or not probe.stdout.strip():
            issues.append({"issue": "missing_latex_dependency", "resource": f"{name}{suffix}"})
    return issues


def pdf_checks(pdf: Path) -> list[dict]:
    issues: list[dict] = []
    info = run(["pdfinfo", str(pdf)], cwd=pdf.parent)
    pages_match = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
    if info.returncode or not pages_match:
        return [{"issue": "invalid_or_unreadable_pdf", "path": str(pdf)}]
    pages = int(pages_match.group(1))
    for page in range(1, pages + 1):
        text = run(["pdftotext", "-f", str(page), "-l", str(page), str(pdf), "-"], cwd=pdf.parent).stdout
        words = re.findall(r"\b\w+\b", text)
        if len(words) < 8:
            issues.append({"issue": "possible_orphan_or_blank_page", "page": page, "word_count": len(words)})
    fonts = run(["pdffonts", str(pdf)], cwd=pdf.parent)
    for line in fonts.stdout.splitlines()[2:]:
        fields = line.split()
        if len(fields) >= 5 and fields[4].lower() == "no":
            issues.append({"issue": "font_not_embedded", "font": fields[0]})
    return issues


def render_pages(pdf: Path, target: Path) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("page-*.png"):
        old.unlink()
    prefix = target / "page"
    process = run(["pdftoppm", "-png", "-r", "120", str(pdf), str(prefix)], cwd=pdf.parent)
    if process.returncode:
        raise RuntimeError((process.stdout + process.stderr)[-2000:] or "pdftoppm failed")
    return [str(path) for path in sorted(target.glob("page-*.png"))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-dir", default="paper")
    parser.add_argument("--main", default="main.tex")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--render-dir", default="",
                        help="optional persistent PNG directory for mandatory visual review")
    args = parser.parse_args()
    paper = Path(args.paper_dir).resolve()
    main = paper / args.main
    issues = []
    if not main.is_file():
        issues.append({"issue": "missing_main_tex", "path": str(main)})
    missing_commands = [command for command in REQUIRED_COMMANDS if not shutil.which(command)]
    issues.extend({"issue": "missing_command", "command": command} for command in missing_commands)
    if main.is_file() and not missing_commands:
        issues.extend(source_checks(paper, main))
    rendered_pages: list[str] = []
    if args.compile and not issues:
        build = run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", args.main], cwd=paper)
        if build.returncode:
            issues.append({"issue": "latex_compile_failed", "output": (build.stdout + build.stderr)[-4000:]})
        elif not args.source_only:
            issues.extend(pdf_checks(main.with_suffix(".pdf")))
            if args.render_dir:
                try:
                    rendered_pages = render_pages(main.with_suffix(".pdf"), Path(args.render_dir).resolve())
                except RuntimeError as exc:
                    issues.append({"issue": "pdf_page_render_failed", "error": str(exc)})
    result = {"ok": not issues, "paper_dir": str(paper), "rendered_pages": rendered_pages,
              "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
