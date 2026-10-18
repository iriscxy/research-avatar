#!/usr/bin/env python3
"""Assemble a Jinghui-style personalized generation request.

The system prompt follows ``demo_paper/jinghui_prompt.md``: task prompt →
setting text → structure rule (abstract/introduction only) → data instruction.
With ``--setting profile`` the user JSON also carries the ``author_differences``
of the researcher's earlier papers most similar to the current input, retrieved
from the paired records in ``profile_pairs.json``. ``--setting history`` carries
those papers' own texts as ``retrieved_history`` instead, and
``--setting profile_history`` carries the texts with each paper's differences.
``--setting none`` is the non-personalized counterpart used as the baseline.

The tool only builds the request; a fresh, isolated context performs the
generation so the None-setting output never sees the profile.

Examples
--------
python3 research_avatar/tools/jinghui_prompt.py --task idea --setting profile \
  --input '{"research_question": "..."}' --output reports/.build/idea_request.json
python3 research_avatar/tools/jinghui_prompt.py --task abstract --setting none \
  --input-file brief.json --output reports/.build/abstract_request.none.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "demo_paper/jinghui_prompt.md"
PAIRS = ROOT / "researcher-profile/profile_pairs.json"

TASKS = ("idea", "abstract", "introduction")
SETTINGS = ("none", "profile", "history", "profile_history")
# Source heading for each task prompt and its Profile setting text.
TASK_HEADINGS = {"idea": "Idea", "abstract": "摘要", "introduction": "引言"}
PROFILE_HEADINGS = {"idea": "Profile（Idea）", "abstract": "Profile（写作）", "introduction": "Profile（写作）"}
HISTORY_HEADINGS = {"idea": "History（Idea）", "abstract": "History（写作）", "introduction": "History（写作）"}
PROFILE_HISTORY_PREFIX = {"idea": "Profile+History（Idea", "abstract": "Profile+History（写作", "introduction": "Profile+History（写作"}
INPUT_KEYS = {
    "idea": ("research_question",),
    "abstract": ("content_brief", "references"),
    "introduction": ("content_brief", "references"),
}
STOPWORDS = set(
    "a an and are as at be by can do does for from how in into is it its of on or such that the "
    "their this to under we what when which while with within without".split()
)


def subsections(text: str) -> dict[str, str]:
    """Map every ``###`` heading (and ``##`` heading) to the text beneath it."""
    parts: dict[str, str] = {}
    for match in re.finditer(r"^(#{2,3}) (.+?)\n(.*?)(?=^#{2,3} |\Z)", text, re.M | re.S):
        parts[match.group(2).strip()] = match.group(3).strip()
    return parts


def load_sources() -> tuple[dict[str, str], str]:
    source = SOURCE.read_text(encoding="utf-8")
    return subsections(source), hashlib.sha256(source.encode("utf-8")).hexdigest()


def section_body(parts: dict[str, str], prefix: str) -> str:
    for heading, body in parts.items():
        if heading.startswith(prefix):
            return body
    raise SystemExit(f"ERROR: prompt source has no section starting with {prefix!r}")


def system_prompt(task: str, setting: str) -> str:
    parts, _ = load_sources()
    task_text = parts[TASK_HEADINGS[task]]
    # The source writes the data instruction once, in section 4.
    data_instruction = section_body(parts, "4.")
    pieces = [task_text]
    if setting == "profile":
        pieces.append(parts[PROFILE_HEADINGS[task]])
    if setting in {"history", "profile_history"}:
        # The writing History text opens with a Chinese note on filling {section}; keep only the prompt.
        history = parts[HISTORY_HEADINGS[task]].split("\n\n")[-1].replace("{section}", task)
        pieces.append(history)
    if setting == "profile_history":
        pieces.append(section_body(parts, PROFILE_HISTORY_PREFIX[task]))
    if task in {"abstract", "introduction"}:
        pieces.append(section_body(parts, "3."))
    pieces.append(data_instruction)
    return "\n\n".join(pieces)


def tokens(value: object) -> list[str]:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS and len(w) > 2]


def query_text(task: str, payload: dict) -> object:
    return payload["content_brief"] if task in {"abstract", "introduction"} else payload[INPUT_KEYS[task][0]]


def paired_entries(pairs_file: Path, task: str, setting: str = "profile") -> list[tuple[dict, object]]:
    """Return (entry for the setting, pair input used for retrieval) per completed pair.

    Profile entries are the ``author_differences`` entries. History entries carry the
    author's own text (the plan for the Idea task, the section for writing), and
    Profile+History entries add that paper's differences.
    """
    papers = json.loads(pairs_file.read_text(encoding="utf-8"))["papers"]
    entries = []
    for record in papers.values():
        pair = record.get(task) or {}
        entry = pair.get("author_differences_entry")
        if not (pair.get("status") == "complete" and entry and entry.get("differences")):
            continue
        if setting in {"history", "profile_history"}:
            text_key = "plan" if task == "idea" else task
            history = {"id": entry["id"], "title": entry["title"]}
            if task == "idea":
                history["research_question"] = entry.get("research_question", "")
            history[text_key] = pair["author_version"]
            if setting == "profile_history":
                history["differences"] = entry["differences"]
            entry = history
        entries.append((entry, query_text(task, pair.get("input") or {}) if pair.get("input") else entry))
    return entries


def rank(query: object, candidates: list[tuple[dict, object]], top_k: int) -> list[dict]:
    documents = [Counter(tokens(text)) for _, text in candidates]
    frequency = Counter(term for doc in documents for term in doc)
    total = len(documents)

    def vector(counts: Counter) -> dict[str, float]:
        return {t: c * math.log((1 + total) / (1 + frequency[t])) + c for t, c in counts.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        dot = sum(a[t] * b.get(t, 0.0) for t in a)
        norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
        return dot / norm if norm else 0.0

    q = vector(Counter(tokens(query)))
    scored = sorted(
        ((cosine(q, vector(doc)), entry) for (entry, _), doc in zip(candidates, documents)),
        key=lambda item: -item[0],
    )
    return [entry for _, entry in scored[:top_k]]


def build(task: str, setting: str, payload: dict, pairs_file: Path, top_k: int) -> dict:
    missing = [k for k in INPUT_KEYS[task] if k not in payload]
    if missing:
        raise SystemExit(f"ERROR: {task} input needs {', '.join(missing)}")
    user = {k: payload[k] for k in INPUT_KEYS[task]}
    if task == "abstract" and "reference_abstract_words" in payload:
        # Length target named in the abstract task prompt: the reference paper's abstract length.
        user["reference_abstract_words"] = payload["reference_abstract_words"]
    retrieved: list[dict] = []
    if setting != "none":
        candidates = paired_entries(pairs_file, task, setting)
        if not candidates:
            raise SystemExit(
                f"ERROR: no completed {task} pairs in {pairs_file}; run profileconstruct before the {setting} setting"
            )
        retrieved = rank(query_text(task, payload), candidates, top_k)
        user["author_differences" if setting == "profile" else "retrieved_history"] = retrieved
    system = system_prompt(task, setting)
    _, source_digest = load_sources()
    return {
        "task": task,
        "setting": setting,
        "system": system,
        "user": user,
        "retrieved_ids": [entry.get("id") for entry in retrieved],
        "system_sha256": hashlib.sha256(system.encode("utf-8")).hexdigest(),
        "prompt_source_sha256": source_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--setting", required=True, choices=SETTINGS)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="JSON object with the task input")
    group.add_argument("--input-file", type=Path)
    parser.add_argument("--pairs", type=Path, default=PAIRS)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input if args.input is not None else args.input_file.read_text(encoding="utf-8"))
    request = build(args.task, args.setting, payload, args.pairs, args.top_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.task}/{args.setting} request with {len(request['retrieved_ids'])} retrieved papers to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
