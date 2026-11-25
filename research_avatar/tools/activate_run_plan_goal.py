#!/usr/bin/env python3
"""Mark the one currently proposed Run Plan goal as running."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from research_avatar.tools.run_plan_progress import (
        completed_artifact_snapshots,
        render_parts_and_goals,
        replace_report_section,
    )
except ModuleNotFoundError:  # Direct ``python research_avatar/tools/activate_run_plan_goal.py`` execution.
    from run_plan_progress import (  # type: ignore[no-redef]
        completed_artifact_snapshots,
        render_parts_and_goals,
        replace_report_section,
    )


STATE_RE = re.compile(r'<script type="application/json" id="run-plan-state">(.*?)</script>', re.S)


def activation_issues(state: dict, goal_id: str) -> list[str]:
    """Return deterministic reasons why a proposed Goal cannot start."""
    goals = [item for item in state.get("goals", []) if isinstance(item, dict)]
    by_id = {str(item.get("id", "")): item for item in goals}
    target = by_id.get(goal_id)
    if target is None:
        return [f"{goal_id} is absent from run-plan state"]
    errors = [
        f"dependency {dependency} is not completed"
        for dependency in target.get("depends_on", [])
        if by_id.get(str(dependency), {}).get("status") != "completed"
    ]
    if state.get("scientific_integrity_version") == 3:
        target_index = goals.index(target)
        earlier_ids = {str(item.get("id", "")) for item in goals[:target_index]}
        gates = {
            str(gate.get("goal_id", "")): gate
            for gate in state.get("gate_decisions", [])
            if isinstance(gate, dict) and gate.get("goal_id")
        }
        for dependency in target.get("depends_on", []):
            dependency_id = str(dependency)
            if (
                by_id.get(dependency_id, {}).get("status") == "completed"
                and dependency_id not in gates
            ):
                errors.append(
                    f"completed dependency {dependency_id} lacks a gate decision"
                )
        for gate in gates.values():
            if not isinstance(gate, dict) or str(gate.get("goal_id", "")) not in earlier_ids:
                continue
            if gate.get("decision") != "continue":
                errors.append(
                    f"claim gate {gate.get('goal_id')} requires {gate.get('decision')}; "
                    f"{goal_id} cannot start"
                )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("goal_id")
    parser.add_argument("--plan", type=Path, default=Path("reports/04_RUN_PLAN.html"))
    args = parser.parse_args()
    source = args.plan.read_text(encoding="utf-8")
    match = STATE_RE.search(source)
    if not match:
        raise ValueError("run-plan-state missing")
    state = json.loads(match.group(1))
    if state.get("active_goal") not in (None, args.goal_id):
        raise ValueError(f"another goal is active: {state['active_goal']}")
    if state.get("proposed_goal_id") != args.goal_id and state.get("active_goal") != args.goal_id:
        raise ValueError(f"{args.goal_id} is not the one proposed goal")
    target = next((goal for goal in state["goals"] if goal["id"] == args.goal_id), None)
    if target is None or target["status"] not in ("proposed", "running"):
        raise ValueError(f"{args.goal_id} is not activatable")
    issues = activation_issues(state, args.goal_id)
    if issues:
        raise ValueError("; ".join(issues))
    target["status"] = "running"
    state["state"] = "goal_running"
    state["active_goal"] = args.goal_id
    state["proposed_goal_id"] = None
    state["next_authorized_action"] = f"Complete exactly {args.goal_id}; do not start a successor."
    snapshots = completed_artifact_snapshots(state, args.plan.parent / "05_EXP_RESULT.html")
    source = replace_report_section(
        source, "parts-and-goals", render_parts_and_goals(state, snapshots)
    )
    serialized = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    source = STATE_RE.sub(
        f'<script type="application/json" id="run-plan-state">{serialized}</script>', source, count=1
    )
    args.plan.write_text(source, encoding="utf-8")
    print(json.dumps({"status": "PASS", "active_goal": args.goal_id}))


if __name__ == "__main__":
    main()
