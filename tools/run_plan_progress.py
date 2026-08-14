#!/usr/bin/env python3
"""Render Run Plan goal progress and nest the current command under its goal."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


STATE_RE = re.compile(
    r'<script\s+type="application/json"\s+id="run-plan-state">(.*?)</script>',
    re.DOTALL,
)
PARTS_RE = re.compile(
    r'<section\s+data-report-section="parts-and-goals">.*?</section>',
    re.DOTALL,
)
LEGACY_CURRENT_RE = re.compile(
    r'\s*<section\s+data-report-section="current-goal">.*?</section>',
    re.DOTALL,
)
STATUS_MARK = {
    "completed": "✅",
    "running": "▶",
    "proposed": "→",
    "locked": "○",
    "pending": "○",
    "blocked": "⚠",
    "invalidated": "⚠",
}
GOAL_RESULT_PROVENANCE_STYLE = (
    '<style>.goal-results .result-value{position:relative;display:inline-block;cursor:help}'
    '.goal-results .result-value::after{content:attr(data-provenance-summary);position:absolute;'
    'z-index:80;left:50%;bottom:calc(100% + 9px);display:none;width:min(430px,72vw);'
    'max-height:320px;overflow:auto;padding:11px 13px;border:1px solid #8fbeb6;'
    'border-radius:8px;background:#102e3b;color:#f2fbf9;text-align:left;white-space:pre-line;'
    'box-shadow:0 12px 28px #102e3b3d;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;'
    'transform:translateX(-50%)}.goal-results .result-value:hover::after,'
    '.goal-results .result-value:focus-visible::after{display:block}</style>'
)
GOAL_COPY_ASSETS = (
    '<style>.goal-command-copy{position:relative}.goal-copy-actions{display:flex;align-items:center;'
    'gap:10px;margin-top:9px}.copy-goal-button{appearance:none;border:1px solid #087f74;'
    'border-radius:8px;background:#087f74;color:#fff;padding:8px 13px;font:700 14px/1.2 '
    'Inter,system-ui,sans-serif;cursor:pointer}.copy-goal-button:hover{background:#066b62}'
    '.copy-goal-button:focus-visible{outline:3px solid #7bd3c7;outline-offset:2px}'
    '.goal-copy-status{min-height:1.2em;color:#087f74;font-size:13px;font-weight:700}</style>'
    '<script>(()=>{const script=document.currentScript;const root=script&&script.closest('
    '\'[data-report-section="parts-and-goals"]\');if(!root||root.dataset.goalCopyBound==='
    '"true")return;root.dataset.goalCopyBound="true";const fallback=text=>{const area='
    'document.createElement("textarea");area.value=text;area.setAttribute("readonly","");'
    'area.style.position="fixed";area.style.opacity="0";document.body.appendChild(area);'
    'area.select();const copied=document.execCommand("copy");area.remove();if(!copied)throw '
    'new Error("copy command failed")};const bridge=text=>new Promise((resolve,reject)=>{if('
    'window.parent===window){reject(new Error("no parent copy bridge"));return}const requestId='
    '`${Date.now()}-${Math.random()}`;const timer=window.setTimeout(()=>{window.removeEventListener('
    '"message",receive);reject(new Error("copy bridge timeout"))},3000);function receive(event){'
    'const data=event.data||{};if(event.source!==window.parent||data.type!=='
    '"research-studio-copy-goal-result"||data.requestId!==requestId)return;window.clearTimeout(timer);'
    'window.removeEventListener("message",receive);data.copied?resolve():reject(new Error('
    '"parent copy failed"))}window.addEventListener("message",receive);window.parent.postMessage('
    '{type:"research-studio-copy-goal",requestId,value:text},"*")});root.addEventListener('
    '"click",async event=>{const '
    'button=event.target.closest("[data-copy-goal-target]");if(!button||!root.contains(button))'
    'return;const source=document.getElementById(button.dataset.copyGoalTarget);const status='
    'document.getElementById(button.getAttribute("aria-describedby"));if(!source)return;const '
    'original=button.textContent;const value=source.textContent;try{if(navigator.clipboard&&'
    'window.isSecureContext)await navigator.clipboard.writeText(value);else fallback(value);'
    'button.textContent="已复制 ✓";if(status)status.textContent="完整 /goal 命令已复制"}'
    'catch(error){try{await bridge(value);button.textContent="已复制 ✓";if(status)status.textContent='
    '"完整 /goal 命令已复制"}catch(bridgeError){button.textContent="复制未完成";if(status)'
    'status.textContent="请在新窗口打开报告后重试"}}'
    'window.setTimeout(()=>{button.textContent=original;if(status)status.textContent=""},2200)'
    '})})();</script>'
)


def goal_command(goal: dict) -> str:
    existing = str(goal.get("goal_command", "")).strip()
    if existing:
        return existing
    goal_id = str(goal["id"])
    description = " ".join(
        str(goal.get(key, "")).strip()
        for key in ("visible_work", "visible_evidence", "completion_check")
        if str(goal.get(key, "")).strip()
    )
    return (
        f"/goal Complete {goal_id}: {description}; follow reports/04_RUN_PLAN.html "
        "and its embedded run-plan state; save each result immediately; before completing "
        "the goal, organize its code and files, remove only disposable temporary artifacts, "
        "and verify every recorded path; append and validate every result in "
        "code/RESULTS_LEDGER.csv; update the embedded state, regenerate "
        "reports/04_RUN_PLAN.html so the goal shows ✅ and, for paper-facing targets, "
        "embeds the matching 05 figure source-data table or result table with every filled "
        "number linked to provenance; update the matching shells in "
        f"reports/05_EXP_RESULT.html from the ledger; stop after {goal_id}, do not start the "
        "successor goal, and only propose the next unlocked /goal."
    )


def current_goal_html(goal: dict, *, active_goal: str | None) -> str:
    goal_id = str(goal["id"])
    safe_goal_id = re.sub(r"[^A-Za-z0-9_-]+", "-", goal_id).strip("-") or "current"
    command_id = f"goal-command-{safe_goal_id}"
    status_id = f"goal-copy-status-{safe_goal_id}"
    running = active_goal == goal_id or goal.get("status") == "running"
    label = "▶ running" if running else "→ unlocked"
    outputs = "、".join(str(value) for value in goal.get("outputs", [])) or "按 embedded state 保存目标输出"
    budget = str(goal.get("budget", "按批准预算执行"))
    completion = str(goal.get("completion_check", "完成 embedded state 中的机械检查"))
    return (
        f'<div class="current-goal" data-current-goal-id="{html.escape(goal_id)}">'
        f'<h4>Current Goal · {html.escape(goal_id)}</h4>'
        f'<p><span class="pill">{label}</span> '
        f'{html.escape(str(goal.get("title", goal_id)))}；只执行这一项，不启动后继 Goal。</p>'
        '<div class="goal-command-copy">'
        f'<pre class="copybox" id="{html.escape(command_id)}">{html.escape(goal_command(goal))}</pre>'
        '<div class="goal-copy-actions">'
        f'<button type="button" class="copy-goal-button" data-copy-goal-target="{html.escape(command_id)}" '
        f'aria-describedby="{html.escape(status_id)}">复制 /goal</button>'
        f'<span class="goal-copy-status" id="{html.escape(status_id)}" aria-live="polite"></span>'
        '</div></div>'
        f'<p><strong>Outputs:</strong> {html.escape(outputs)}</p>'
        f'<p><strong>Resources:</strong> {html.escape(budget)}</p>'
        f'<p><strong>Completion:</strong> {html.escape(completion)}</p>'
        '</div>'
    )


def render_parts_and_goals(state: dict, completed_artifacts: dict[str, list[str]] | None = None) -> str:
    goals = state.get("goals", [])
    parts = state.get("parts", [])
    goals_by_id = {str(item.get("id")): item for item in goals}
    proposed = str(state.get("proposed_goal_id") or "")
    active = str(state.get("active_goal") or "") or None
    current_id = active or proposed
    completed_artifacts = completed_artifacts or {}
    if current_id and current_id not in goals_by_id:
        raise ValueError(f"current goal {current_id!r} is absent from run-plan-state.goals")

    chunks = ['<section data-report-section="parts-and-goals"><h2>4. Parts and Goals</h2>']
    current_count = 0
    for part in parts:
        chunks.append(
            f'<div class="part"><h3>{html.escape(str(part["id"]))} — '
            f'{html.escape(str(part["title"]))}</h3>'
            f'<p>{html.escape(str(part.get("decision", "")))}</p>'
        )
        for goal_id in part.get("goals", []):
            item = goals_by_id[str(goal_id)]
            artifact_ids = [str(value) for value in item.get("artifact_ids", [])]
            mapping = "、".join(artifact_ids) if artifact_ids else "无直接图表（基础设施或配置冻结）"
            if str(goal_id) == "G1.1":
                mapping += "；F1 为非实验图，仅计数，后续由 paperwrite/figureppt 绘制"
            mark = STATUS_MARK.get(str(item.get("status", "locked")), "○")
            chunks.append(
                f'<article class="goal" data-goal-id="{html.escape(str(goal_id))}" '
                f'data-artifact-ids="{html.escape(" ".join(artifact_ids))}">'
                f'<h3>{mark} {html.escape(str(goal_id))} — {html.escape(str(item.get("title", "")))}</h3>'
                f'<p>{html.escape(str(item.get("decision_question", "")))}</p>'
                f'<p>{html.escape(str(item.get("visible_work", "")))}</p>'
                f'<p>{html.escape(str(item.get("visible_evidence", "")))} 完成检查：'
                f'{html.escape(str(item.get("completion_check", "")))}</p>'
                f'<p class="mapping">对应图表：{html.escape(mapping)}</p>'
            )
            if str(goal_id) == current_id:
                chunks.append(current_goal_html(item, active_goal=active))
                current_count += 1
            snapshots = completed_artifacts.get(str(goal_id), [])
            if item.get("status") == "completed" and snapshots:
                chunks.append(
                    '<div class="goal-results"><h4>Completed Goal Evidence</h4>'
                    '<p>以下图表直接来自 05 实验结果；悬停或聚焦已填数字可预览生成过程，点击可在 05 查看完整记录。</p>'
                    + GOAL_RESULT_PROVENANCE_STYLE
                    + "".join(snapshots)
                    + '</div>'
                )
            chunks.append('</article>')
        chunks.append('</div>')
    if current_id:
        chunks.append(GOAL_COPY_ASSETS)
    chunks.append('</section>')
    if current_id and current_count != 1:
        raise ValueError(f"expected one nested Current Goal for {current_id}, rendered {current_count}")
    copy_button_count = sum(chunk.count('data-copy-goal-target=') for chunk in chunks)
    if current_id and copy_button_count != 1:
        raise ValueError(f"expected one /goal copy button for {current_id}, rendered {copy_button_count}")
    if not current_id and copy_button_count:
        raise ValueError("rendered a /goal copy button without a current goal")
    return "".join(chunks)


def _artifact_snapshot(report: str, artifact_id: str) -> str:
    pattern = re.compile(
        rf'<section\b(?=[^>]*\bdata-artifact-id=["\']{re.escape(artifact_id)}["\'])[^>]*>.*?</section>',
        re.DOTALL,
    )
    match = pattern.search(report)
    if not match:
        raise ValueError(f"05_EXP_RESULT.html lacks artifact {artifact_id}")
    snapshot = match.group(0)
    return re.sub(
        r'href=(["\'])#provenance-',
        lambda found: f'href={found.group(1)}05_EXP_RESULT.html#provenance-',
        snapshot,
    )


def _verified_target(snapshot: str, target_id: str) -> bool:
    element = re.search(
        rf'<(?P<tag>[a-zA-Z0-9]+)\b(?=[^>]*\bdata-target-id=["\']{re.escape(target_id)}["\'])'
        rf'(?P<open>[^>]*)>(?P<body>.*?)</(?P=tag)>',
        snapshot,
        re.DOTALL,
    )
    if not element:
        return False
    result = re.search(r'\bdata-result-id=["\']([^"\']+)["\']', element.group("open"))
    if not result:
        return False
    result_id = re.escape(result.group(1))
    return bool(re.search(
        rf'<a\b(?=[^>]*href=["\'](?:05_EXP_RESULT\.html)?#provenance-{result_id}["\'])'
        rf'(?=[^>]*data-provenance-summary=["\'][^"\']+["\'])'
        rf'(?=[^>]*title=["\'][^"\']+["\'])[^>]*>',
        element.group("body"),
    ))


def completed_artifact_snapshots(state: dict, results_path: Path) -> dict[str, list[str]]:
    completed = {str(goal.get("id")) for goal in state.get("goals", []) if goal.get("status") == "completed"}
    scoped: dict[str, dict[str, list[str]]] = {}
    for contract in state.get("acquisition_contracts", []):
        goal_id = str(contract.get("producing_goal") or "")
        artifact_id = str(contract.get("artifact_id") or "")
        target_id = str(contract.get("target_id") or "")
        if goal_id in completed and artifact_id and target_id:
            scoped.setdefault(goal_id, {}).setdefault(artifact_id, []).append(target_id)
    if not scoped:
        return {}
    if not results_path.exists():
        raise ValueError("completed paper-facing goal requires reports/05_EXP_RESULT.html")
    report = results_path.read_text(encoding="utf-8")
    snapshots: dict[str, list[str]] = {}
    for goal_id, artifacts in scoped.items():
        for artifact_id, target_ids in artifacts.items():
            snapshot = _artifact_snapshot(report, artifact_id)
            missing = [target for target in target_ids if not _verified_target(snapshot, target)]
            if missing:
                raise ValueError(
                    f"completed goal {goal_id} has unlinked/unverified targets in {artifact_id}: {missing[:5]}"
                )
            snapshots.setdefault(goal_id, []).append(snapshot)
    return snapshots


def refresh(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    match = STATE_RE.search(source)
    if not match:
        raise ValueError("04_RUN_PLAN.html lacks embedded run-plan-state JSON")
    state = json.loads(match.group(1))
    snapshots = completed_artifact_snapshots(state, path.parent / "05_EXP_RESULT.html")
    rendered = render_parts_and_goals(state, snapshots)
    if not PARTS_RE.search(source):
        raise ValueError("04_RUN_PLAN.html lacks Parts and Goals section")
    updated = PARTS_RE.sub(rendered, source, count=1)
    updated = LEGACY_CURRENT_RE.sub("", updated, count=1)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8")
    temporary.replace(path)
    return {
        "file": str(path),
        "current_goal": state.get("active_goal") or state.get("proposed_goal_id") or "",
        "nested_current_goal_count": rendered.count('class="current-goal"'),
        "copy_goal_button_count": rendered.count('data-copy-goal-target='),
        "completed_artifact_snapshots": sum(len(value) for value in snapshots.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path, nargs="?", default=Path("reports/04_RUN_PLAN.html"))
    args = parser.parse_args()
    print(json.dumps(refresh(args.html), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
