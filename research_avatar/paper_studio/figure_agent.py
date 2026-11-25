"""Local coding-agent bridge for paper figures: Claude Code or Codex, never a GPT API.

The agent that draws is the one the researcher is working in: Claude Code draws
when Studio runs inside a Claude Code session, Codex draws when Codex is the
host. The reference paper's own figure pages are attached as images so the new
figure follows its visual language (layout density, colors, typography) without
copying its content.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

MAX_REFERENCE_PAGES = 4


class FigureAgentError(RuntimeError):
    pass


def choose_agent(which: Callable[[str], str | None] = shutil.which) -> str:
    """Return ``claude`` or ``codex``: explicit override, then the host session, then what is installed."""
    forced = os.environ.get("PAPER_STUDIO_FIGURE_AGENT", "").strip().lower()
    if forced in {"claude", "codex"}:
        if not which(forced):
            raise FigureAgentError(f"PAPER_STUDIO_FIGURE_AGENT={forced} but the {forced} CLI is not installed.")
        return forced
    if os.environ.get("CLAUDECODE") and which("claude"):
        return "claude"
    if which("codex"):
        return "codex"
    if which("claude"):
        return "claude"
    raise FigureAgentError("Neither the claude nor the codex CLI is installed; cannot draw figures.")


def reference_pdf(root: Path) -> Path | None:
    """The single researcher-owned reference paper approved in the experiment plan."""
    plan = root / "reports" / "03_EXPERIMENT_PLAN.html"
    if not plan.exists():
        return None
    match = re.search(r'id="experiment-plan-contract">(.*?)</script>', plan.read_text(encoding="utf-8"), re.S)
    if not match:
        return None
    key = json.loads(match.group(1)).get("references", {}).get("researcher_owned_logic", {}).get("publication_key", "")
    pdf = root / "researcher-profile" / "fulltext" / "pdf" / f"{key}.pdf"
    return pdf if key and pdf.is_file() else None


def reference_figure_images(root: Path, cache: Path, limit: int = MAX_REFERENCE_PAGES) -> list[Path]:
    """Render the reference paper's pages that carry figures, so the agent can look at them."""
    pdf = reference_pdf(root)
    if pdf is None or not shutil.which("pdftotext") or not shutil.which("pdftoppm"):
        return []
    folder = cache / pdf.stem
    folder.mkdir(parents=True, exist_ok=True)
    pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout or "Pages: 0").group(1))
    chosen: list[int] = []
    for page in range(1, pages + 1):
        text = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), str(pdf), "-"], capture_output=True, text=True).stdout
        if re.search(r"^\s*(Figure|Fig\.)\s*\d+\s*[:.]", text, re.M):
            chosen.append(page)
    images = []
    for page in chosen[:limit]:
        target = folder / f"figure-page-{page}"
        if not target.with_suffix(".png").exists():
            subprocess.run(["pdftoppm", "-r", "90", "-f", str(page), "-l", str(page), "-png", "-singlefile", str(pdf), str(target)], check=True)
        images.append(target.with_suffix(".png"))
    return images


def run_agent(prompt: str, *, root: Path, images: list[Path], timeout: int, env: dict[str, str], auth_args: list[str] | None = None) -> str:
    """Run one prompt through the chosen local agent and return its final message."""
    agent = choose_agent()
    note = ""
    if images:
        listing = "\n".join(f"- {p}" for p in images)
        note = ("\n\nReference figures from the researcher's own reference paper are attached as images. Study their visual language "
                "(layout density, palette, line weights, typography, panel arrangement) and draw in that style. Never copy their content, labels, or numbers.\n"
                + (f"Image files:\n{listing}\n" if agent == "claude" else ""))
    full = prompt + note
    if agent == "codex":
        codex = shutil.which("codex")
        with tempfile.TemporaryDirectory(prefix="figure-agent-") as directory:
            out = Path(directory) / "last_message.txt"
            command = [codex, "exec", "--ephemeral", *(auth_args or []), "--sandbox", "read-only", "--color", "never", "--cd", str(root), "--output-last-message", str(out)]
            for image in images:
                command += ["-i", str(image)]
            command.append("-")
            process = subprocess.run(command, input=full, capture_output=True, text=True, timeout=timeout, env=env)
            if process.returncode or not out.exists():
                raise FigureAgentError("codex exec failed: " + ((process.stdout + process.stderr).strip()[-1800:] or "no message returned"))
            return out.read_text(encoding="utf-8", errors="replace").strip()
    claude = shutil.which("claude")
    command = [claude, "-p", "--output-format", "text", "--allowedTools", "Read"]
    for folder in sorted({str(p.parent) for p in images}):
        command += ["--add-dir", folder]
    process = subprocess.run(command, input=full, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(root))
    if process.returncode or not process.stdout.strip():
        raise FigureAgentError("claude -p failed: " + ((process.stderr or process.stdout).strip()[-1800:] or "no message returned"))
    return process.stdout.strip()
