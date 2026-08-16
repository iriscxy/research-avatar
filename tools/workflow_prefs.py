#!/usr/bin/env python3
"""Mine *workflow preferences* (how the researcher likes to work) from coding-agent
transcripts — a SEMANTIC complement to ``experiment_history.py`` (which mines
toolchain, model, hardware, and failure-memory signals).

This tool does the **deterministic narrowing only**: it pulls the human's own
short directive turns out of ``~/.claude/projects/<slug>/*.jsonl`` and keeps the
ones that carry a *preference signal* (mandates, prohibitions, trade-offs,
corrections, process/order cues, rigor cues). It does NOT decide the final
preferences — that is an LLM judgement made by the consuming skill, which reads
this bundle and distills 1-line preference statements for the user to confirm
before they land in ``PROFILE.html`` (*Workflow Preferences* / *Tacit
Knowledge*).

Why a bundle, not an answer: "I always smoke-test on 1 epoch first" is a behaviour
pattern, not a token; no regex can label it. So the tool's job is recall (surface
every candidate), and the LLM's job is precision (keep the real, recurring ones).

Examples
--------
python3 tools/workflow_prefs.py --transcripts ~/.claude/projects/* --output prefs_bundle.json
python3 tools/workflow_prefs.py --transcripts ~/.claude/projects/my-proj --max-snippets 300
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# --------------------------------------------------------------------------- #
# preference-signal cues (CN + EN). A snippet is a candidate if it hits >=1.
# Each category is a hint for the LLM, not a final label.
# --------------------------------------------------------------------------- #
_CUES: dict[str, list[str]] = {
    "cadence": [  # iteration rhythm: small first, then scale
        r"先.{0,12}(再|然后|才)", r"smoke", r"试跑", r"小数据", r"通了", r"跑通",
        r"sanity", r"pilot", r"first.{0,20}then", r"1\s?个?\s?epoch", r"先验证",
    ],
    "prohibition": [
        r"不要", r"别(?!的)", r"永远不", r"从不", r"不能", r"禁止", r"不准",
        r"\bnever\b", r"\bdon'?t\b", r"\bdo not\b", r"\bavoid\b", r"不许",
    ],
    "mandate": [
        r"必须", r"一定要", r"总是", r"永远", r"每次", r"记得", r"务必",
        r"\balways\b", r"\bmust\b", r"\bmake sure\b", r"\bremember to\b",
    ],
    "tradeoff": [
        r"宁可", r"宁愿", r"优先", r"偏好", r"更倾向", r"尽量", r"能.{0,6}就不",
        r"\bprefer\b", r"\binstead\b", r"\brather\b", r"简单", r"别太复杂", r"最省",
    ],
    "correction": [
        r"不对", r"错了", r"不是这样", r"应该是", r"其实", r"重新", r"改成",
        r"\bactually\b", r"\bwrong\b", r"\bshould be\b", r"\bno,\b", r"搞错",
    ],
    "process": [
        r"顺序", r"流程", r"步骤", r"第[一二三]步", r"workflow", r"先做", r"接下来",
        r"\bworkflow\b", r"\bpipeline\b", r"\bstep\b",
    ],
    "rigor": [
        r"复现", r"复跑", r"reproduce", r"baseline", r"对不上", r"seed",
        r"消融", r"ablation", r"可复现", r"raw", r"追溯", r"几个种子", r"如实",
    ],
}

_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in _CUES.items()}

# turns that are NOT human directives (system/tool noise) — drop fast.
_NOISE = re.compile(
    r"(local-command|command-name|tool_result|system-reminder|stdout|caveat:"
    r"|<command-|Result of calling|<function_results|persisted-output)",
    re.IGNORECASE,
)


def _user_text(ev: dict) -> str | None:
    """Return the human's text for a user turn, or None if not a plain directive."""
    if ev.get("type") != "user":
        return None
    msg = ev.get("message")
    if not isinstance(msg, dict) or msg.get("role") != "user":
        return None
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):  # skip tool_result-bearing turns (not human prose)
        texts = [b.get("text", "") for b in c
                 if isinstance(b, dict) and b.get("type") == "text"]
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        return "\n".join(t for t in texts if t) or None
    return None


def _categorize(text: str) -> list[str]:
    return [cat for cat, pats in _COMPILED.items() if any(p.search(text) for p in pats)]


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def _iter_files(transcripts: list[Path]) -> list[Path]:
    files: list[Path] = []
    for t in transcripts:
        if t.is_file() and t.suffix == ".jsonl":
            files.append(t)
        elif t.is_dir():
            files.extend(sorted(t.glob("*.jsonl")))
    return files


def mine(transcripts: list[Path], min_len: int, max_len: int,
         max_snippets: int) -> dict:
    files = _iter_files(transcripts)
    by_cat: dict[str, list[dict]] = {k: [] for k in _CUES}
    seen: set[str] = set()
    snippets: list[dict] = []
    lines = 0
    for path in files:
        try:
            fh = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                lines += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = _user_text(ev)
                if not text:
                    continue
                text = text.strip()
                # length gate: short human directives, not pasted prompts/data
                if not (min_len <= len(text) <= max_len):
                    continue
                if _NOISE.search(text):
                    continue
                cats = _categorize(text)
                if not cats:
                    continue
                key = _norm(text)
                if key in seen:
                    continue
                seen.add(key)
                snippet = {
                    "text": text,
                    "categories": cats,
                    "source": path.parent.name,  # project slug
                }
                snippets.append(snippet)
                for c in cats:
                    by_cat[c].append(snippet)

    snippets.sort(key=lambda s: len(s["categories"]), reverse=True)  # multi-cue first
    capped = snippets[:max_snippets]
    return {
        "lines_scanned": lines,
        "files_scanned": len(files),
        "candidate_count": len(snippets),
        "returned": len(capped),
        "category_counts": {k: len(v) for k, v in by_cat.items()},
        "snippets": capped,
        "note": ("Candidate preference-bearing user turns. NOT final preferences — "
                 "feed to the LLM (profileconstruct) to distill & confirm before "
                 "writing PROFILE Workflow Preferences."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Mine candidate workflow-preference turns from transcripts.")
    ap.add_argument("--transcripts", nargs="*", default=[],
                    help="Transcript dirs/files (e.g. ~/.claude/projects/*).")
    ap.add_argument("--output", help="Write JSON bundle here (default: stdout).")
    ap.add_argument("--min-len", type=int, default=4, help="Min chars of a human turn.")
    ap.add_argument("--max-len", type=int, default=600,
                    help="Max chars (longer = pasted prompt/data, skipped).")
    ap.add_argument("--max-snippets", type=int, default=400,
                    help="Cap on returned snippets (multi-cue ranked first).")
    args = ap.parse_args()

    transcripts = [Path(t).expanduser() for t in args.transcripts]
    if not transcripts:
        print(json.dumps({"error": "no --transcripts given"}))
        return 1
    result = mine(transcripts, args.min_len, args.max_len, args.max_snippets)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).expanduser().write_text(text, encoding="utf-8")
        print(json.dumps({"ok": True, "output": args.output,
                          "candidate_count": result["candidate_count"],
                          "returned": result["returned"],
                          "category_counts": result["category_counts"]},
                         ensure_ascii=False))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
