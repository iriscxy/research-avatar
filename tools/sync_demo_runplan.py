#!/usr/bin/env python3
"""Export the public Run Plan demo snapshot from the canonical embedded state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from tools.run_plan_progress import STATE_RE
except ModuleNotFoundError:  # Direct execution sets sys.path[0] to tools/.
    from run_plan_progress import STATE_RE


def export(source: Path, destination: Path) -> dict:
    html = source.read_text(encoding="utf-8")
    match = STATE_RE.search(html)
    if not match:
        raise ValueError(f"{source} lacks embedded run-plan-state JSON")
    state = json.loads(match.group(1))
    goal_fields = (
        "id", "part_id", "title", "status", "decision_question", "visible_work",
        "visible_evidence", "completion_check", "artifact_ids", "budget", "outputs",
        "goal_command",
    )
    part_fields = ("id", "title", "decision", "goals")
    try:
        source_label = source.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        source_label = source.as_posix()
    snapshot = {
        "source": source_label,
        "schema_version": state.get("schema_version"),
        "active_goal": state.get("active_goal"),
        "proposed_goal_id": state.get("proposed_goal_id"),
        "approved_artifact_ids": state.get("approved_artifact_ids", []),
        "parts": [
            {key: part.get(key) for key in part_fields}
            for part in state.get("parts", [])
        ],
        "goals": [
            {key: goal.get(key) for key in goal_fields}
            for goal in state.get("goals", [])
        ],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("reports/04_RUN_PLAN.html"))
    parser.add_argument("--output", type=Path, default=Path("demo/runplan-state.json"))
    args = parser.parse_args()
    snapshot = export(args.source, args.output)
    current = snapshot.get("active_goal") or snapshot.get("proposed_goal_id") or "none"
    print(json.dumps({"output": str(args.output), "current_goal": current}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
