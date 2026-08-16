#!/usr/bin/env python3
"""Mark the one currently proposed Run Plan goal as running."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from tools.run_plan_progress import (
        completed_artifact_snapshots,
        render_parts_and_goals,
        replace_report_section,
    )
except ModuleNotFoundError:  # Direct ``python tools/activate_run_plan_goal.py`` execution.
    from run_plan_progress import (  # type: ignore[no-redef]
        completed_artifact_snapshots,
        render_parts_and_goals,
        replace_report_section,
    )


STATE_RE = re.compile(r'<script type="application/json" id="run-plan-state">(.*?)</script>', re.S)


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
