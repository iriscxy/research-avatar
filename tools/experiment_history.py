#!/usr/bin/env python3
"""Mine coding-agent interaction history into experiment habits.

Used by `/profileconstruct` (to fill PROFILE.html's *Experiment Templates*) and
by `/experiment-bridge` (resource- and failure-aware planning). Scans, in order of
preference:

- ``.aris/meta/events.jsonl`` — ARIS's own structured event log (skill_invoke /
  PostToolUse / tool_failure), already produced by the framework.
- Claude Code session transcripts (``~/.claude/projects/<slug>/*.jsonl``), passed
  via ``--transcripts``.

The scan is **format-agnostic**: each line is treated as text and pattern-mined,
so it survives schema drift between Claude Code versions. Output is a structured
JSON habit profile. Absent inputs degrade to an empty skeleton with a note — never
an error.

Scope (deliberate): habits.json captures only the **genuinely personal** axes —
toolchain/launchers, base-model backbone, hardware, dependency preferences, and
failure memory (OOM / error types). Hyperparameter VALUES are NOT mined: lr, batch
size, epochs, seed, etc. are task-determined (the experiment plan decides them),
not person-determined, so personalizing them imposed habit over task need and was
the main noise source. Workflow *preferences* (how the researcher likes to work)
are a separate, LLM-distilled artifact — see ``workflow_prefs.py``.

Examples
--------
python3 tools/experiment_history.py --output habits.json
python3 tools/experiment_history.py --transcripts ~/.claude/projects/my-proj --output habits.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# framework / dependency signals
_FRAMEWORK_PATTERNS = {
    name: re.compile(pattern, re.I)
    for name, pattern in {
        "transformers": r"(?<![A-Za-z0-9])transformers(?![A-Za-z0-9])",
        "deepspeed": r"(?<![A-Za-z0-9])deepspeed(?![A-Za-z0-9])",
        "accelerate": r"(?<![A-Za-z0-9])accelerate(?![A-Za-z0-9])",
        "fsdp": r"(?<![A-Za-z0-9])fsdp(?![A-Za-z0-9])",
        "vllm": r"(?<![A-Za-z0-9])vllm(?![A-Za-z0-9])",
        "peft": r"(?<![A-Za-z0-9])peft(?![A-Za-z0-9])",
        "trl": r"(?<![A-Za-z0-9])trl(?![A-Za-z0-9])",
        "lightning": r"(?<![A-Za-z0-9])lightning(?![A-Za-z0-9])",
        "pytorch": r"(?<![A-Za-z0-9])pytorch(?![A-Za-z0-9])",
        "torch": r"(?<![A-Za-z0-9])torch(?![A-Za-z0-9])",
        "jax": r"(?<![A-Za-z0-9])jax(?![A-Za-z0-9])",
        "flax": r"(?<![A-Za-z0-9])flax(?![A-Za-z0-9])",
        "wandb": r"(?<![A-Za-z0-9])wandb(?![A-Za-z0-9])",
        "datasets": r"(?<![A-Za-z0-9])datasets(?![A-Za-z0-9])",
        "bitsandbytes": r"(?<![A-Za-z0-9])bitsandbytes(?![A-Za-z0-9])",
        "flash-attn": r"(?<![A-Za-z0-9])flash[_-]attn(?![A-Za-z0-9])",
        "xformers": r"(?<![A-Za-z0-9])xformers(?![A-Za-z0-9])",
    }.items()
}
# launchers
_LAUNCHERS = ["torchrun", "accelerate launch", "deepspeed", "python -m torch.distributed",
              "srun", "sbatch", "modal run"]
# GPU types — matched with WORD BOUNDARIES to avoid substring false positives
# (e.g. a bare "tpu"/"4090" inside an unrelated token). This is environment signal.
_GPU_RE = re.compile(
    r"\b(a100|h100|h800|a800|v100|rtx\s?3090|rtx\s?4090|3090|4090|a6000|l40|mi250|tpu)\b",
    re.I,
)
# Base-model backbone — KEPT (it's a real environment/stack fingerprint: which model
# the researcher habitually fine-tunes). Capture stops at whitespace, quotes, or a
# backslash so JSON-escaped "\n\nUsage" tails don't bleed into the value.
_MODEL_RE = re.compile(r"--(?:model|model_name_or_path|base_model)[= ]+([^\s\"'\\]+)")
# NOTE: hyperparameter VALUES (lr/batch_size/grad_accum/epochs/seed/warmup) are
# deliberately NOT mined. They are task-determined, not person-determined — the
# experiment plan decides them. Personalizing them imposed habit over task need and
# was the main source of noise (batch_size=2000, lr n=4). habits.json now captures
# only the genuinely-personal axes: toolchain, base model, hardware, failure memory.
_OOM = re.compile(r"out of memory|CUDA out of memory|OutOfMemoryError|OOM", re.I)
_ERR = re.compile(r"(Traceback|Error:|Exception|RuntimeError|AssertionError|"
                  r"ModuleNotFoundError|ImportError|ValueError)", re.I)


def _empty() -> dict:
    return {
        "sources_scanned": [],
        "lines_scanned": 0,
        "impl_patterns": {"launchers": {}, "base_models": {}},
        "dependency_prefs": {},
        "resource_habits": {"gpus": {}},
        "failure_modes": {"oom_hits": 0, "error_types": {}, "total_error_lines": 0},
        "success_signals": {"wandb_runs": 0, "checkpoints_saved": 0},
        "note": "",
    }


def _scan_text(text: str, agg: dict) -> None:
    low = text.lower()
    for fw, pattern in _FRAMEWORK_PATTERNS.items():
        if pattern.search(text):
            agg["_dep"][fw] += 1
    for la in _LAUNCHERS:
        if la in low:
            agg["_launch"][la] += 1
    for g in _GPU_RE.findall(low):
        agg["_gpu"][re.sub(r"\s+", " ", g)] += 1
    for m in _MODEL_RE.findall(text):
        agg["_model"][m] += 1
    if _OOM.search(text):
        agg["oom"] += 1
    for m in _ERR.findall(text):
        agg["_err"][m.rstrip(":")] += 1
    if "wandb" in low and re.search(r"wandb.*run|run.*wandb|wandb\.init", low):
        agg["wandb"] += 1
    if re.search(r"saving checkpoint|checkpoint.*saved|\.pt\b|\.safetensors\b|save_pretrained", low):
        agg["ckpt"] += 1


def _iter_files(events: Path | None, transcripts: list[Path]) -> list[Path]:
    files: list[Path] = []
    if events and events.is_file():
        files.append(events)
    for t in transcripts:
        if t.is_dir():
            files.extend(sorted(t.glob("*.jsonl")))
        elif t.is_file():
            files.append(t)
    return files


def mine(events: Path | None, transcripts: list[Path], max_lines: int) -> dict:
    out = _empty()
    agg = {
        "_dep": Counter(), "_launch": Counter(), "_gpu": Counter(),
        "_model": Counter(), "_err": Counter(),
        "oom": 0, "wandb": 0, "ckpt": 0,
    }
    files = _iter_files(events, transcripts)
    n = 0
    for f in files:
        out["sources_scanned"].append(str(f))
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if n >= max_lines:
                        break
                    n += 1
                    _scan_text(line, agg)
        except (OSError, UnicodeError) as error:
            print(f"warning: could not read history source {f}: {error}", file=sys.stderr)
            continue
    out["lines_scanned"] = n

    out["impl_patterns"]["launchers"] = dict(agg["_launch"].most_common())
    out["impl_patterns"]["base_models"] = dict(agg["_model"].most_common(8))
    out["dependency_prefs"] = dict(agg["_dep"].most_common())
    out["resource_habits"]["gpus"] = dict(agg["_gpu"].most_common())
    out["failure_modes"] = {
        "oom_hits": agg["oom"],
        "error_types": dict(agg["_err"].most_common(8)),
        "total_error_lines": sum(agg["_err"].values()),
    }
    out["success_signals"] = {"wandb_runs": agg["wandb"], "checkpoints_saved": agg["ckpt"]}

    if not files:
        out["note"] = ("No history found (no .aris/meta/events.jsonl and no "
                       "--transcripts given). Experiment Templates will stay seeded "
                       "from paper abstracts until interaction history accrues.")
    elif n == 0:
        out["note"] = "History files were empty."
    else:
        out["note"] = f"Mined {n} lines from {len(files)} file(s)."
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Mine coding-agent history into experiment habits.")
    ap.add_argument("--events", default=".aris/meta/events.jsonl",
                    help="ARIS event log (default: .aris/meta/events.jsonl)")
    ap.add_argument("--transcripts", nargs="*", default=[],
                    help="Extra transcript dirs/files (e.g. ~/.claude/projects/<slug>)")
    ap.add_argument("--output", help="Write JSON here (default: stdout)")
    ap.add_argument("--max-lines", type=int, default=200_000)
    args = ap.parse_args()

    events = Path(args.events).expanduser() if args.events else None
    transcripts = [Path(t).expanduser() for t in args.transcripts]
    result = mine(events, transcripts, args.max_lines)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(json.dumps({"ok": True, "output": args.output,
                          "lines_scanned": result["lines_scanned"],
                          "sources": len(result["sources_scanned"])}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
