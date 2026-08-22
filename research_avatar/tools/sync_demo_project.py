#!/usr/bin/env python3
"""Atomically refresh the committed Paper Studio demo from the canonical project.

The allowlist is deliberately explicit: the demo receives the finished paper,
its editable figures/tables/prompts, the evidence needed by the UI, and no
unrelated experiment or full-text corpus.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "research_avatar/online_studio/demo_project"

FILES = (
    "paper/.paper_studio/state.json",
    "paper/.paper_studio/table_previews/t1.pdf",
    "paper/.paper_studio/table_previews/t1.png",
    "paper/.paper_studio/table_previews/t2.pdf",
    "paper/.paper_studio/table_previews/t2.png",
    "paper/EXPERIMENT_PLAN.md",
    "paper/abstract_contract.json",
    "paper/acl.sty",
    "paper/acl_natbib.bst",
    "paper/budget.json",
    "paper/fig/make_figs.py",
    "paper/fig/typo_margin/F1_motivation.pdf",
    "paper/fig/typo_margin/F1_motivation.png",
    "paper/fig/typo_margin/F1_motivation.pptx",
    "paper/fig/typo_margin/actual/F2_confirmation.pdf",
    "paper/fig/typo_margin/actual/F2_confirmation.png",
    "paper/fig/typo_margin/actual/F3_budget.pdf",
    "paper/fig/typo_margin/actual/F3_budget.png",
    "paper/figsrc/motivation_shapes.json",
    "paper/figsrc/motivation_source.txt",
    "paper/figsrc/motivation_spec.json",
    "paper/figsrc/typo_margin/figure_schema.json",
    "paper/figsrc/typo_margin/make_projected_fixture.py",
    "paper/figsrc/typo_margin/projected_fixture.json",
    "paper/logic_check.md",
    "paper/main.pdf",
    "paper/main.tex",
    "paper/official_acl_latex_template.tex",
    "paper/outline_approval.json",
    "paper/paper_studio.json",
    "paper/reference_context.json",
    "paper/reference_wang2025word.txt",
    "paper/references.bib",
    "paper/scholarship_contract.json",
    "paper/scientific_consistency.json",
    "paper/sections/abstract.tex",
    "paper/sections/appendix.tex",
    "paper/sections/conclusion.tex",
    "paper/sections/discussion.tex",
    "paper/sections/experiments.tex",
    "paper/sections/introduction.tex",
    "paper/sections/limitations.tex",
    "paper/sections/method.tex",
    "paper/sections/related_work.tex",
    "paper/theory/README.md",
    "paper/theory/verify.py",
    "paper/writing_style.json",
    "researcher-profile/PROFILE.html",
    "researcher-profile/publications.json",
    "results/typo_margin/confirmatory_results.json",
    "results/typo_margin/figure_metrics.json",
    "results/typo_margin/main_results.json",
    "results/typo_margin/paper_values.json",
    "results/typo_margin/studio_metrics.json",
)


def sync(root: Path = ROOT, destination: Path = DESTINATION) -> dict[str, object]:
    root = root.resolve()
    destination = destination.resolve()
    missing = [name for name in FILES if not (root / name).is_file()]
    if missing:
        raise SystemExit("Cannot sync demo; missing canonical files: " + ", ".join(missing))

    state = json.loads((root / "paper/.paper_studio/state.json").read_text(encoding="utf-8"))
    config = json.loads((root / "paper/paper_studio.json").read_text(encoding="utf-8"))
    project_id = str(config.get("project", {}).get("id") or "").strip()
    if not project_id or state.get("project_id") != project_id:
        raise SystemExit("Refusing to publish a stale or mismatched demo project")
    reference_context = json.loads(
        (root / "paper/reference_context.json").read_text(encoding="utf-8")
    )
    reference_paper = config.get("project", {}).get("reference_paper") or {}
    if reference_context.get("reference_title") != reference_paper.get("title"):
        raise SystemExit("Refusing to publish mismatched reference-paper context")
    section_ids = [str(item.get("id") or "") for item in config.get("sections", [])]
    contexts = reference_context.get("sections")
    if not isinstance(contexts, dict) or set(contexts) != set(section_ids):
        raise SystemExit("Refusing to publish incomplete section reference context")
    for section_id in section_ids:
        context = contexts[section_id]
        excerpts = context.get("excerpts") if isinstance(context, dict) else None
        if (
            not str(context.get("source_heading") or "").strip()
            or not str(context.get("logic_summary_zh") or "").strip()
            or not isinstance(excerpts, list)
            or not excerpts
            or any(not str(item.get("text") or "").strip() for item in excerpts if isinstance(item, dict))
            or any(not isinstance(item, dict) for item in excerpts)
        ):
            raise SystemExit(f"Refusing to publish invalid {section_id} reference context")
    reference_source_name = str(reference_context.get("reference_source") or "").strip()
    reference_source = (root / reference_source_name).resolve()
    try:
        reference_source.relative_to(root)
    except ValueError as exc:
        raise SystemExit("Reference source escapes the canonical project") from exc
    if not reference_source.is_file():
        raise SystemExit(f"Cannot sync demo; missing reference source: {reference_source_name}")
    for figure_id in ("F1", "F2", "F3"):
        figure = state.get("figures", {}).get(figure_id, {})
        if figure.get("status") != "approved":
            raise SystemExit(f"Refusing to publish incomplete {figure_id} state")
    if not str(state.get("figures", {}).get("F1", {}).get("draw_prompt") or "").strip():
        raise SystemExit("Refusing to publish F1 without its archived drawing prompt")

    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="demo-project-", dir=parent))
    try:
        for name in FILES:
            source = root / name
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        reference_target = staging / reference_source_name
        if reference_target.resolve() != (staging / "paper/reference_context.json").resolve():
            reference_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(reference_source, reference_target)
        sources = sorted((root / "paper/sources").glob("*.txt"))
        if not sources:
            raise SystemExit("Cannot sync demo without paper source evidence")
        for source in sources:
            target = staging / "paper/sources" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        mechanism_rounds = sorted(
            (root / "paper/figsrc/iterations/F1_motivation").glob(
                "round_*.png"
            )
        )
        if not mechanism_rounds:
            raise SystemExit(
                "Cannot sync demo without the archived GPT Image reference"
            )
        # Paper Studio keys the archived raster reference by the configured
        # LaTeX label slug, while the editable deliverable may use a different
        # nested stem.
        label = str(config["figures"]["F1"]["label"])
        label_slug = label.split(":", 1)[-1].replace("-", "_")
        gpt_reference = staging / f"paper/figsrc/{label_slug}.bg.png"
        gpt_reference.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mechanism_rounds[-1], gpt_reference)

        backup = destination.with_name(destination.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            os.replace(destination, backup)
        os.replace(staging, destination)
        if backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    files = sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file())
    if any("typo_basis" in name or "micro_typo_intent" in name for name in files):
        raise SystemExit("Stale negative-study demo files survived synchronization")
    return {"project_id": project_id, "files": len(files), "sources": len(sources)}


def main() -> int:
    print(json.dumps(sync(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
