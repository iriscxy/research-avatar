#!/usr/bin/env python3
"""Snapshot the current Research Studio project into the read-only Online Demo."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEMO_PROJECT = ROOT / "research_avatar/online_studio/demo_project"
DEMO_WEB = ROOT / "research_avatar/web/demo"

WORKFLOW_ARTIFACTS = {
    "profile": ROOT / "researcher-profile/PROFILE.html",
    "literature": ROOT / "reports/01_LIT_SURVEY.html",
    "ideas": ROOT / "reports/02_IDEA_REPORT.html",
    "expplan": ROOT / "reports/03_EXPERIMENT_PLAN.html",
    "runplan": ROOT / "reports/04_RUN_PLAN.html",
}


def extract_script_json(path: Path, identifier: str) -> dict:
    source = path.read_text(encoding="utf-8")
    match = re.search(
        rf'<script[^>]+id=["\']{re.escape(identifier)}["\'][^>]*>(.*?)</script>',
        source,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        raise RuntimeError(f"{path} does not contain #{identifier}")
    return json.loads(match.group(1))


def copy_tree(source: Path, destination: Path, *, ignore=None) -> None:
    if not source.exists():
        return
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


def sync_paper_project() -> None:
    if DEMO_PROJECT.exists():
        shutil.rmtree(DEMO_PROJECT)
    DEMO_PROJECT.mkdir(parents=True)
    copy_tree(
        ROOT / "paper",
        DEMO_PROJECT / "paper",
        ignore=shutil.ignore_patterns(
            "api_usage.jsonl",
            "paper_pages",
            "iterations",
            "*.bg.png",
            "*.rollback",
            "*.tmp",
        ),
    )
    copy_tree(ROOT / "reports", DEMO_PROJECT / "reports")
    profile = DEMO_PROJECT / "researcher-profile"
    profile.mkdir(parents=True)
    for name in ("PROFILE.html", "publications.json"):
        shutil.copy2(ROOT / "researcher-profile" / name, profile / name)
    copy_tree(
        ROOT / "researcher-profile/fulltext/txt",
        profile / "fulltext/txt",
    )
    copy_tree(ROOT / "results/more_reconstruction", DEMO_PROJECT / "results/more_reconstruction")
    code = DEMO_PROJECT / "code"
    code.mkdir()
    shutil.copy2(ROOT / "code/build_more_reports.py", code / "build_more_reports.py")


def sync_run_plan() -> None:
    plan = extract_script_json(ROOT / "reports/04_RUN_PLAN.html", "run-plan-state")
    plan["state"] = plan.get("status", plan.get("state", "pending"))
    if plan.get("active_goal") == "":
        plan["active_goal"] = None
    if plan.get("proposed_goal_id") == "":
        plan["proposed_goal_id"] = None
    plan["goal_confirmation"] = {
        "status": "confirmed" if plan.get("status") == "completed" else "pending",
        "scope": "all_goals" if plan.get("execution_mode") == "sequential_all_goals" else "one_goal",
        "confirmed_goal_ids": [goal.get("id") for goal in plan.get("goals", [])],
    }
    (DEMO_WEB / "runplan-state.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sync_workflow_artifacts() -> None:
    """Publish exact workflow reports instead of maintaining demo prose by hand."""
    destination = DEMO_WEB / "artifacts"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    manifest = {}
    for key, source in WORKFLOW_ARTIFACTS.items():
        if not source.is_file():
            raise RuntimeError(f"canonical workflow artifact is missing: {source}")
        target = destination / f"{key}.html"
        shutil.copy2(source, target)
        source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != source_digest:
            raise RuntimeError(f"demo artifact copy does not match source: {source}")
        manifest[key] = {
            "url": f"artifacts/{key}.html",
            "source": str(source.relative_to(ROOT)),
            "sha256": source_digest,
        }
    (DEMO_WEB / "artifact-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    sync_paper_project()
    sync_run_plan()
    sync_workflow_artifacts()
    print(f"Synced Online Demo from {ROOT}")


if __name__ == "__main__":
    main()
