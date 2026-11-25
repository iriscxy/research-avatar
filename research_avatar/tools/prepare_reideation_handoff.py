#!/usr/bin/env python3
"""Materialize a RunPlan anomaly checkpoint as IdeaGen's auditable input."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from bs4 import BeautifulSoup


def load_checkpoint(path: Path) -> dict:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    node = soup.find("script", id="run-plan-state", attrs={"type": "application/json"})
    if node is None:
        raise ValueError("Run Plan lacks run-plan-state")
    state = json.loads(node.get_text())
    checkpoint = state.get("reideation_checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("Run Plan lacks reideation_checkpoint")
    return checkpoint


def build_handoff(checkpoint: dict, root: Path) -> dict:
    root = root.resolve()
    status = str(checkpoint.get("status") or "")
    required = {
        "status", "conformance_status", "anomaly_status", "checked_goal_id",
        "evidence_artifact", "decision",
    }
    missing = sorted(field for field in required if checkpoint.get(field) in (None, ""))
    if missing:
        raise ValueError("reideation checkpoint missing: " + ", ".join(missing))
    payload = {
        "schema_version": "1.0",
        "status": status,
        "checked_goal_id": checkpoint["checked_goal_id"],
        "conformance_status": checkpoint["conformance_status"],
        "anomaly_status": checkpoint["anomaly_status"],
        "decision": checkpoint["decision"],
    }
    if status == "not_triggered":
        return payload
    if status != "decision_required":
        raise ValueError(f"unsupported reideation checkpoint status: {status}")
    if checkpoint["conformance_status"] != "VERIFIED":
        raise ValueError("reideation handoff requires verified conformance")
    if checkpoint["anomaly_status"] != "VERIFIED_SCIENTIFIC_ANOMALY":
        raise ValueError("reideation handoff requires a verified scientific anomaly")
    for field in ("command", "observed_mismatch", "baseline_contract"):
        if not str(checkpoint.get(field) or "").strip():
            raise ValueError(f"triggered reideation checkpoint lacks {field}")
    evidence = (root / str(checkpoint["evidence_artifact"])).resolve()
    try:
        evidence.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("reideation evidence points outside the project") from exc
    if not evidence.is_file():
        raise ValueError(f"reideation evidence does not exist: {evidence}")
    payload.update(
        {
            "command": checkpoint["command"],
            "observed_mismatch": checkpoint["observed_mismatch"],
            "baseline_contract": checkpoint["baseline_contract"],
            "evidence_artifact": evidence.relative_to(root).as_posix(),
            "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            "ideagen_instruction": (
                "Generate revised candidate seeds from this verified anomaly while preserving "
                "the baseline contract; do not treat an implementation defect as science."
            ),
        }
    )
    return payload


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run-plan", type=Path, default=Path("reports/04_RUN_PLAN.html"))
    parser.add_argument("--output", type=Path, default=Path("reports/.build/reideation_input.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    run_plan = args.run_plan if args.run_plan.is_absolute() else root / args.run_plan
    output = args.output if args.output.is_absolute() else root / args.output
    payload = build_handoff(load_checkpoint(run_plan), root)
    atomic_json(output, payload)
    print(json.dumps({"status": "PASS", "output": str(output), "handoff": payload["status"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
