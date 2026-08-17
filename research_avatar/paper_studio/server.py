"""Local Paper Studio.

Run from the repository root:

    python3 -m research_avatar.paper_studio.server

The browser never receives an API key. Each manuscript section owns an
independent selected-provider conversation.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
import webbrowser
import zipfile
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .api_usage import append_usage, usage_record, usage_summary


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
# Runtime project data belongs to the directory from which the Studio is
# launched. Package-owned web assets and helper programs remain beside this
# module, which matters after a wheel is installed into site-packages.
ROOT = Path(os.environ.get("RESEARCH_AVATAR_ROOT", Path.cwd())).resolve()
STATIC = Path(__file__).resolve().parent / "static"
PAPER = ROOT / "paper"
STATE_DIR = PAPER / ".paper_studio"
STATE_FILE = STATE_DIR / "state.json"
API_USAGE_FILE = STATE_DIR / "api_usage.jsonl"
PARAGRAPH_PLAN_FILE = PAPER / "paragraph_plan.json"
FIGURE_DIR = PAPER / "fig"
FIGURE_SOURCE_DIR = PAPER / "figsrc"
DATA_FIGURE_AGENT_DIR = FIGURE_SOURCE_DIR / "data_agents"
PPT_COMPOSER = Path(__file__).resolve().parent / "ppt_compose.mjs"
TABLE_PREVIEW_DIR = STATE_DIR / "table_previews"
PAPER_PAGE_DIR = STATE_DIR / "paper_pages"
FIGURE_TOOL = PACKAGE_ROOT / "tools" / "figure_ppt.py"
PROJECT_CONFIG_FILE = PAPER / "paper_studio.json"
DEFAULT_MODEL = os.environ.get("PAPER_STUDIO_MODEL", "gpt-5-nano")
DEFAULT_PROVIDER = os.environ.get("PAPER_STUDIO_PROVIDER", "openai").strip().lower()
ONLINE_PROJECT_MODE = os.environ.get("PAPER_STUDIO_ONLINE", "").lower() in {
    "1",
    "true",
    "yes",
}
ONLINE_DISABLED_ARTIFACT_AGENT_PATHS = {
    "/api/figure/build",
    "/api/figure/generate",
    "/api/figure/panel/generate",
    "/api/figure/compose",
    "/api/table/generate",
    "/api/table/agent-edit",
}
DEMO_MODE = os.environ.get("PAPER_STUDIO_DEMO_MODE", "").lower() in {
    "1",
    "true",
    "yes",
}
if DEFAULT_PROVIDER not in {"openai", "deepseek"}:
    DEFAULT_PROVIDER = "openai"
PROVIDER_DEFAULT_MODELS = {
    "openai": DEFAULT_MODEL,
    "deepseek": os.environ.get("DEEPSEEK_PAPER_MODEL", "deepseek-v4-flash"),
}
PROVIDER_MODEL_OPTIONS = {
    "openai": (
        ("gpt-5", "GPT-5"),
        ("gpt-5-mini", "GPT-5 mini"),
        ("gpt-5-nano", "GPT-5 nano"),
    ),
    "deepseek": (
        ("deepseek-v4-pro", "DeepSeek V4 Pro"),
        ("deepseek-v4-flash", "DeepSeek V4 Flash"),
    ),
}
MECHANISM_AGENT_TIMEOUT_SECONDS = 120
API_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
API_URL += "/responses"
API_KEY_ENVIRONMENT_VARIABLE = "OPENAI_API_KEY"
API_KEY_SETUP_LOCATION = "启动 Paper Studio 的本机终端"
API_KEY_SETUP_COMMAND = 'export OPENAI_API_KEY="粘贴你的 API key"'
API_KEY_RESTART_COMMAND = "python3 -m research_avatar.paper_studio.server"
CHAT_HISTORY_LOCK = threading.RLock()
CHAT_RESPONSE_HISTORIES: dict[str, list[dict[str, str]]] = {}
STATE_LOCK = threading.RLock()
FIGURE_PROCESS_LOCK = threading.RLock()
RUNNING_FIGURE_PROCESSES: dict[str, subprocess.Popen[str]] = {}
CANCELLED_FIGURE_JOBS: set[str] = set()
FULL_DRAFT_JOB_LOCK = threading.RLock()
CANCELLED_FULL_DRAFT_JOBS: set[str] = set()
SERVER_INSTANCE_TOKEN = uuid.uuid4().hex
REFERENCE_EXCERPT_MAX_CHARS = 6000
BIBLIOGRAPHY_PROMPT_MAX_CHARS = 32000
BIBLIOGRAPHY_PROMPT_MIN_RECORDS = 8


class StudioHTTPServer(ThreadingHTTPServer):
    """Threaded local server with enough backlog for browser asset bursts."""

    request_queue_size = 64


class ProjectConfigError(RuntimeError):
    """Raised when paper/paper_studio.json cannot safely drive the fixed Studio engine."""


def _project_path(root: Path, value: str, field: str) -> Path:
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ProjectConfigError(f"{field} must stay inside the workspace: {value}") from exc
    return candidate


def load_project_config(
    path: Path = PROJECT_CONFIG_FILE, *, root: Path = ROOT
) -> dict[str, Any]:
    """Load and validate project data without changing the reusable web application."""
    if not path.exists():
        raise ProjectConfigError(
            f"Missing {path}. Create one project config before starting Paper Studio."
        )
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectConfigError(f"Invalid Paper Studio project config: {exc}") from exc
    if config.get("schema_version") != "1.0":
        raise ProjectConfigError("paper_studio.json schema_version must be 1.0")
    project = config.get("project")
    if (
        not isinstance(project, dict)
        or not str(project.get("id", "")).strip()
        or not str(project.get("name", "")).strip()
    ):
        raise ProjectConfigError("paper_studio.json project.id and project.name are required")
    section_specs = config.get("sections")
    if not isinstance(section_specs, list) or not section_specs:
        raise ProjectConfigError("paper_studio.json sections must be a non-empty list")
    section_ids: list[str] = []
    for index, section in enumerate(section_specs):
        if not isinstance(section, dict):
            raise ProjectConfigError(f"sections[{index}] must be an object")
        for field in ("id", "title", "file", "result_keys"):
            if field not in section:
                raise ProjectConfigError(f"sections[{index}].{field} is required")
        section_id = str(section["id"])
        if section_id in section_ids:
            raise ProjectConfigError(f"Duplicate section id: {section_id}")
        if Path(str(section["file"])).name != str(section["file"]):
            raise ProjectConfigError(f"Section file must be a filename: {section['file']}")
        if not isinstance(section["result_keys"], list):
            raise ProjectConfigError(f"Section result_keys must be a list: {section_id}")
        section_ids.append(section_id)
    batch_order = config.get("batch_writing_order", section_ids)
    if (
        not isinstance(batch_order, list)
        or len(batch_order) != len(set(batch_order))
        or set(map(str, batch_order)) != set(section_ids)
    ):
        raise ProjectConfigError(
            "batch_writing_order must list every configured section exactly once"
        )
    for kind, order_key in (("figures", "figure_order"), ("tables", "table_order")):
        definitions = config.get(kind)
        order = config.get(order_key)
        if not isinstance(definitions, dict) or not isinstance(order, list):
            raise ProjectConfigError(f"paper_studio.json {kind} and {order_key} are required")
        if len(order) != len(set(order)) or set(order) != set(definitions):
            raise ProjectConfigError(f"{order_key} must list every {kind} id exactly once")
        for artifact_id, definition in definitions.items():
            if not isinstance(definition, dict):
                raise ProjectConfigError(f"{kind}.{artifact_id} must be an object")
            for field in ("title", "label", "kind", "width", "source_sections", "description", "caption"):
                if field not in definition:
                    raise ProjectConfigError(f"{kind}.{artifact_id}.{field} is required")
            unknown_sections = set(definition["source_sections"]) - set(section_ids)
            if unknown_sections:
                raise ProjectConfigError(
                    f"{kind}.{artifact_id} references unknown sections: {sorted(unknown_sections)}"
                )
            panel_ids = [str(item.get("id", "")) for item in definition.get("panels", [])]
            if len(panel_ids) != len(set(panel_ids)) or any(not item for item in panel_ids):
                raise ProjectConfigError(f"{kind}.{artifact_id} panel ids must be unique")
            if kind == "tables" and not isinstance(definition.get("data_grid"), dict):
                raise ProjectConfigError(f"tables.{artifact_id}.data_grid is required")
            if kind == "tables":
                grid = definition["data_grid"]
                grid_type = grid.get("type")
                if not isinstance(grid.get("path"), str) or not grid["path"].strip():
                    raise ProjectConfigError(f"tables.{artifact_id}.data_grid.path is required")
                if grid_type == "records":
                    columns = grid.get("columns")
                    if not isinstance(columns, list) or not columns:
                        raise ProjectConfigError(
                            f"tables.{artifact_id}.data_grid.columns must be a non-empty list"
                        )
                    keys = []
                    for index, column in enumerate(columns):
                        if not isinstance(column, dict):
                            raise ProjectConfigError(
                                f"tables.{artifact_id}.data_grid.columns[{index}] must be an object"
                            )
                        key = str(column.get("key", "")).strip()
                        label = str(column.get("label", "")).strip()
                        if not key or not label:
                            raise ProjectConfigError(
                                f"tables.{artifact_id}.data_grid columns require key and label"
                            )
                        keys.append(key)
                    if len(keys) != len(set(keys)):
                        raise ProjectConfigError(
                            f"tables.{artifact_id}.data_grid column keys must be unique"
                        )
                elif grid_type == "benchmark_rows":
                    row_key = str(grid.get("row_key", "")).strip()
                    benchmarks = grid.get("benchmarks")
                    metrics = grid.get("metrics")
                    if not row_key:
                        raise ProjectConfigError(
                            f"tables.{artifact_id}.data_grid.row_key is required"
                        )
                    if (
                        not isinstance(benchmarks, list)
                        or not benchmarks
                        or any(not isinstance(item, str) or not item.strip() for item in benchmarks)
                        or len(benchmarks) != len(set(benchmarks))
                    ):
                        raise ProjectConfigError(
                            f"tables.{artifact_id}.data_grid.benchmarks must be a non-empty unique string list"
                        )
                    if not isinstance(metrics, list) or not metrics:
                        raise ProjectConfigError(
                            f"tables.{artifact_id}.data_grid.metrics must be a non-empty list"
                        )
                    metric_keys = []
                    for metric in metrics:
                        if not isinstance(metric, dict):
                            raise ProjectConfigError(
                                f"tables.{artifact_id}.data_grid.metrics entries must be objects"
                            )
                        key = str(metric.get("key", "")).strip()
                        label = str(metric.get("label", "")).strip()
                        if not key or not label:
                            raise ProjectConfigError(
                                f"tables.{artifact_id}.data_grid metrics require key and label"
                            )
                        metric_keys.append(key)
                    if len(metric_keys) != len(set(metric_keys)):
                        raise ProjectConfigError(
                            f"tables.{artifact_id}.data_grid metric keys must be unique"
                        )
                else:
                    raise ProjectConfigError(
                        f"tables.{artifact_id}.data_grid.type must be records or benchmark_rows"
                    )
    labels = [item["label"] for item in config["figures"].values()]
    labels += [item["label"] for item in config["tables"].values()]
    if len(labels) != len(set(labels)):
        raise ProjectConfigError("Figure and table LaTeX labels must be unique")
    paths = config.get("paths")
    if not isinstance(paths, dict):
        raise ProjectConfigError("paper_studio.json paths is required")
    resolved_paths: dict[str, Path] = {}
    for field in ("metrics", "main", "reference"):
        value = str(paths.get(field, "")).strip()
        if not value:
            raise ProjectConfigError(f"paper_studio.json paths.{field} is required")
        resolved = _project_path(root, value, f"paths.{field}")
        if not resolved.is_file():
            raise ProjectConfigError(f"paper_studio.json paths.{field} does not exist: {value}")
        resolved_paths[field] = resolved
    if len(set(resolved_paths.values())) != 3:
        raise ProjectConfigError("paper_studio.json main, reference, and metrics paths must be distinct")
    if resolved_paths["main"].suffix.lower() != ".tex" or r"\begin{document}" not in resolved_paths[
        "main"
    ].read_text(encoding="utf-8", errors="replace"):
        raise ProjectConfigError("paper_studio.json paths.main must be a LaTeX document entry point")
    if not resolved_paths["reference"].read_text(encoding="utf-8", errors="replace").strip():
        raise ProjectConfigError("paper_studio.json paths.reference must contain extracted reference text")
    try:
        metrics_payload = json.loads(resolved_paths["metrics"].read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectConfigError("paper_studio.json paths.metrics must contain valid JSON") from exc
    if not isinstance(metrics_payload, (dict, list)) or not metrics_payload:
        raise ProjectConfigError("paper_studio.json paths.metrics must contain a non-empty JSON object or list")
    target = project.get("target")
    reference_paper = project.get("reference_paper")
    venue = str(project.get("venue", "")).strip()
    if (
        not venue
        or not isinstance(target, dict)
        or str(target.get("venue", "")).strip() != venue
    ):
        raise ProjectConfigError(
            "paper_studio.json project.venue and matching project.target.venue "
            "must be inherited from the approved 03 experiment plan"
        )
    if not isinstance(reference_paper, dict) or not str(
        reference_paper.get("title", "")
    ).strip():
        raise ProjectConfigError(
            "paper_studio.json project.reference_paper.title must identify the "
            "structural reference selected before paper writing"
        )
    if not str(project.get("decision_source", "")).strip():
        raise ProjectConfigError(
            "paper_studio.json project.decision_source must name the approved "
            "HTML contract that selected the venue and reference paper"
        )
    return config


EMPTY_PROJECT_MODE = "--empty" in sys.argv or not PROJECT_CONFIG_FILE.exists()


def project_files_ready() -> bool:
    """Return whether a loaded project still has its two canonical control files."""
    return PROJECT_CONFIG_FILE.is_file() and PARAGRAPH_PLAN_FILE.is_file()


def empty_project_config() -> dict[str, Any]:
    """Built-in shell configuration; it contains no paper-specific content."""
    return {
        "schema_version": "1.0",
        "project": {
            "id": "__paper_studio_empty__",
            "name": "",
            "eyebrow": "PAPER STUDIO",
            "studio_title": "Paper Studio",
            "subtitle": "等待 paperwrite 填入论文项目数据",
        },
        "sections": [],
        "batch_writing_order": [],
        "figure_order": [],
        "figures": {},
        "table_order": [],
        "tables": {},
        "paths": {"metrics": "paper/.paper_studio/empty_metrics.json"},
    }


PROJECT_CONFIG = empty_project_config() if EMPTY_PROJECT_MODE else load_project_config()
PROJECT_METADATA: dict[str, Any] = PROJECT_CONFIG["project"]
PROJECT_ID = str(PROJECT_METADATA["id"])
SECTION_SPECS: list[dict[str, Any]] = PROJECT_CONFIG["sections"]
SECTIONS = [
    (str(item["id"]), str(item["title"]), str(item["file"]))
    for item in SECTION_SPECS
]
SECTION_MAP = {
    str(item["id"]): {
        "title": str(item["title"]),
        "file": str(item["file"]),
        "render": str(item.get("render", "section")),
        "latex_title": str(item.get("latex_title", "")),
        "start_label": str(item.get("start_label", "")),
        "end_label": str(item.get("end_label", "")),
    }
    for item in SECTION_SPECS
}
SECTION_LATEX_TITLES = {
    key: str(metadata["latex_title"])
    for key, metadata in SECTION_MAP.items()
    if metadata["latex_title"]
}
RESULT_KEYS = {
    str(item["id"]): [str(key) for key in item["result_keys"]]
    for item in SECTION_SPECS
}
FIGURES: dict[str, dict[str, Any]] = PROJECT_CONFIG["figures"]
FIGURE_ORDER = [str(item) for item in PROJECT_CONFIG["figure_order"]]
TABLES: dict[str, dict[str, Any]] = PROJECT_CONFIG["tables"]
TABLE_ORDER = [str(item) for item in PROJECT_CONFIG["table_order"]]
METRICS_FILE = _project_path(ROOT, PROJECT_CONFIG["paths"]["metrics"], "paths.metrics")


def reload_figure_and_table_definitions_if_paper_studio_json_changed(
    changed_files: list[str],
) -> None:
    """Pick up figure/table add/remove edits the local Agent made to disk.

    FIGURES/FIGURE_ORDER/TABLES/TABLE_ORDER are loaded once at process
    startup from paper/paper_studio.json and never re-read afterward. The
    local Agent is explicitly documented to edit that file directly (e.g. a
    researcher asking it to delete a figure/table), so without this a
    correctly-completed deletion is invisible to the running server: it
    keeps rendering, compiling, and reporting the old definition in
    /api/state until the process is restarted, which looks from the
    researcher's side exactly like "nothing happened, the PDF still has the
    figure" even though the Agent's edit and recompile were both correct.
    Only figure/table *definitions* are reloaded in place (not project.id,
    sections, or other structural fields, which have their own explicit
    invalidation path elsewhere); mutate the existing dict/list objects
    rather than rebinding the module names so every already-imported
    reference sees the update. load_state()'s own figures/tables
    reconciliation against FIGURE_ORDER/TABLE_ORDER then cleans up any
    now-removed artifact's runtime state on the very next load.
    """
    if EMPTY_PROJECT_MODE:
        return
    if "paper/paper_studio.json" not in changed_files:
        return
    try:
        fresh = load_project_config()
    except ProjectConfigError:
        return
    FIGURES.clear()
    FIGURES.update(fresh["figures"])
    FIGURE_ORDER[:] = [str(item) for item in fresh["figure_order"]]
    TABLES.clear()
    TABLES.update(fresh["tables"])
    TABLE_ORDER[:] = [str(item) for item in fresh["table_order"]]


def batch_writing_order() -> list[str]:
    """Return project-owned whole-draft order without inferring paper structure."""
    configured = PROJECT_CONFIG.get("batch_writing_order")
    if isinstance(configured, list) and set(map(str, configured)) == set(SECTION_MAP):
        return [str(item) for item in configured]
    return [str(item["id"]) for item in SECTION_SPECS]


def default_table_prompt(table_id: str) -> str:
    """Return the editable, deterministic writing brief for a result table."""
    definition = TABLES[table_id]
    prompt = definition.get("prompt", {})
    return "\n".join(
        [
            f"数据源: {PROJECT_CONFIG['paths']['metrics']}",
            f"列: {prompt.get('columns', '')}",
            f"行: {prompt.get('rows', 'source')}",
            f"Caption: {definition['caption']}",
            f"字号: {prompt.get('font_size', 'small')}",
            f"最优值: {prompt.get('best_values', 'none')}",
        ]
    )


def recovered_mechanism_prompt(figure_id: str) -> str:
    """Rebuild an honest editable brief when a completed figure lost its prompt."""
    definition = FIGURES[figure_id]
    configured = str(definition.get("design_prompt", "")).strip()
    if configured:
        return configured
    canvas = definition.get("canvas_in") or []
    canvas_text = " × ".join(str(value) for value in canvas) + " in" if canvas else "project-configured"
    return "\n".join(
        [
            "[恢复的设计说明｜原始生成 Prompt 未归档]",
            f"Create an editable academic mechanism figure titled: {definition['title']}.",
            f"Required content: {definition['description']}",
            f"Rhetorical role: {definition.get('rhetorical_role', 'mechanism')}.",
            f"Canvas: {canvas_text}; layout: {definition.get('width', 'single-column')}.",
            f"Caption contract: {definition['caption']}",
            "Use a pure white background, restrained paper colors, readable labels, and native editable shapes.",
            "Preserve the meaning and visual organization of the currently approved figure.",
        ]
    )


def recovered_data_panel_prompt(figure_id: str, panel_id: str) -> str:
    """Rebuild the plot brief for an already materialized data panel."""
    definition = FIGURES[figure_id]
    panel = next(item for item in definition.get("panels", []) if item["id"] == panel_id)
    configured = str(panel.get("agent_prompt", "")).strip()
    if configured:
        return configured
    result_keys = ", ".join(str(key) for key in panel.get("result_keys", [])) or "none"
    return "\n".join(
        [
            "[恢复的绘图说明｜原始 Agent Prompt 未归档]",
            f"Create the data panel '{panel['title']}' for figure {figure_id}: {definition['title']}.",
            f"Goal: {panel['goal']}",
            f"Use only traceable result keys: {result_keys}.",
            f"Figure description: {definition['description']}",
            f"Caption contract: {definition['caption']}",
            "Keep labels readable at the configured paper width and export an editable vector PDF/PPTX result.",
            "Preserve the data and visual organization of the currently approved figure.",
        ]
    )


def outline_is_confirmed() -> bool:
    """Recognize both the marker and the canonical paperwrite approval record."""
    if (PAPER / ".outline-approved").exists():
        return True
    approval = PAPER / "outline_approval.json"
    try:
        payload = json.loads(approval.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return str(payload.get("status", "")).strip().lower() == "approved"


def artifact_metadata(artifact_id: str) -> dict[str, str] | None:
    if artifact_id in FIGURES:
        definition = FIGURES[artifact_id]
        return {
            "id": artifact_id,
            "kind": "figure",
            "title": str(definition["title"]),
            "label": str(definition["label"]),
        }
    if artifact_id in TABLES:
        definition = TABLES[artifact_id]
        return {
            "id": artifact_id,
            "kind": "table",
            "title": str(definition["title"]),
            "label": str(definition["label"]),
        }
    return None


def artifact_writing_context(
    artifact_ids: list[str] | None,
    figure_states: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Describe paragraph-bound artifacts and their mandatory LaTeX references."""
    context: list[dict[str, Any]] = []
    for artifact_id in artifact_ids or []:
        if artifact_id in FIGURES:
            definition = FIGURES[artifact_id]
            figure_state = (figure_states or {}).get(artifact_id, {})
            context.append(
                {
                    "id": artifact_id,
                    "kind": "figure",
                    "title": definition["title"],
                    "description": definition["description"],
                    "caption": figure_state.get("caption") or definition["caption"],
                    "panels": [
                        {
                            "id": panel["id"],
                            "title": panel["title"],
                            "goal": panel["goal"],
                        }
                        for panel in definition.get("panels", [])
                    ],
                    "label": definition["label"],
                    "required_reference": (
                        f"Figure~\\ref{{{definition['label']}}}"
                    ),
                }
            )
        elif artifact_id in TABLES:
            definition = TABLES[artifact_id]
            context.append(
                {
                    "id": artifact_id,
                    "kind": "table",
                    "title": definition["title"],
                    "description": definition["description"],
                    "caption": definition["caption"],
                    "label": definition["label"],
                    "required_reference": f"Table~\\ref{{{definition['label']}}}",
                }
            )
    return context


def artifact_reference_issues(
    paragraph: str, artifact_context: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Check the paragraph-plan contract for figure/table references."""
    expected = {str(item["label"]): item for item in artifact_context}
    configured = artifact_writing_context(list(FIGURES) + list(TABLES))
    configured_by_label = {str(item["label"]): item for item in configured}
    counts = {
        label: len(re.findall(rf"\\ref\{{{re.escape(label)}\}}", paragraph))
        for label in configured_by_label
    }
    missing = [expected[label] for label in expected if counts.get(label, 0) == 0]
    repeated = [
        {**expected[label], "count": counts[label]}
        for label in expected
        if counts.get(label, 0) > 1
    ]
    unexpected = [
        {**configured_by_label[label], "count": count}
        for label, count in counts.items()
        if count and label not in expected
    ]
    return {"missing": missing, "repeated": repeated, "unexpected": unexpected}


def artifact_reference_error(
    paragraph: str, artifact_context: list[dict[str, Any]]
) -> str:
    """Return an actionable error, or an empty string when references are valid."""
    issues = artifact_reference_issues(paragraph, artifact_context)
    details: list[str] = []
    if issues["missing"]:
        details.append(
            "缺少 " + ", ".join(item["required_reference"] for item in issues["missing"])
        )
    if issues["repeated"]:
        details.append(
            "同段重复 "
            + ", ".join(
                f"{item['required_reference']}（{item['count']} 次）"
                for item in issues["repeated"]
            )
        )
    if issues["unexpected"]:
        details.append(
            "本段未绑定 "
            + ", ".join(item["required_reference"] for item in issues["unexpected"])
        )
    if not details:
        return ""
    return (
        "图表引用不符合 paragraph plan："
        + "；".join(details)
        + "。每个绑定图表在该段必须且只能引用一次；需要在其他段落再次引用时，先在 "
        "paper/paragraph_plan.json 中显式绑定。"
    )
FIGURE_PROMPT_INSTRUCTIONS = """You are an expert designer of figures for ACL-family NLP papers. Carefully read the supplied manuscript evidence and return one complete, production-ready GPT Image prompt for a restrained academic diagram.

First identify the figure's single scientific message and the minimum visual structure needed to communicate it. Follow common ACL figure conventions: pure white background, flat vector geometry, thin consistent strokes, compact alignment, generous whitespace, precise typography, two to four clearly related regions, and a muted colorblind-safe palette of three to five colors. Use tokens, small semantic glyphs, arrows, brackets, paths, matrices, or modules only when they encode the mechanism. Prefer an Illustrator/TikZ-like schematic over a decorative BioRender poster. Do not add people, scenery, mascots, photorealistic objects, gradients, glow, glass, 3D depth, glossy buttons, heavy shadows, or marketing-style visual drama unless the manuscript explicitly requires them. Do not default to oversized text cards or a generic box-and-arrow flowchart; small boxes and panels are acceptable when they precisely encode tokens, states, or modules. Keep labels short and print-readable. Never invent evidence or put result charts in a method figure.

You are operating one persistent conversation dedicated to exactly one paper figure. Keep the figure faithful to its bound manuscript section and approved figure role. The supplied <paper_figure_format> is mandatory: explicitly restate its single-column or two-column target, physical aspect ratio, central safe composition band, and density guidance in the returned image-generation prompt. On revision turns, preserve sound prior design decisions but follow the researcher's latest instruction about scope, layout, density, hierarchy, and column width. Return only the complete revised image-generation prompt, with no commentary or Markdown fence."""


class StudioError(Exception):
    """A user-actionable Studio error."""


def generate_figure_caption(
    figure_id: str,
    state: dict[str, Any],
    current_caption: str,
    prompt_instruction: str,
) -> str:
    """Generate an editable caption candidate grounded in the figure's bound evidence."""
    definition = FIGURES[figure_id]
    metrics = metrics_bundle()
    evidence = {
        key: result_path_value(metrics, key)
        for key in definition.get("result_keys", [])
        if has_result_path(metrics, key)
    }
    figure_state = state["figures"][figure_id]
    context = {
        "id": figure_id,
        "title": definition["title"],
        "description": definition["description"],
        "label": definition["label"],
        "panels": definition.get("panels", []),
        "layout_plan": figure_state.get("layout_plan", {}),
        "current_caption": current_caption,
        "researcher_instruction": prompt_instruction,
        "traceable_results": evidence,
    }
    payload = {
        "model": str(state.get("model") or DEFAULT_MODEL),
        "store": False,
        "instructions": (
            "Write one concise, publication-ready English figure caption grounded only "
            "in the supplied figure context and traceable results. Follow the researcher's "
            "instruction. Explain panel semantics when panels exist, define non-obvious "
            "metrics or conditions, and do not invent measurements. Return only the caption "
            "text: no Markdown, no commentary, and no LaTeX caption wrapper. Preserve the "
            "literal [SYNTHETIC] marker whenever the context contains synthetic data."
        ),
        "input": json.dumps(context, ensure_ascii=False, indent=2)[:24000],
    }
    response = post_openai(payload)
    caption = " ".join(extract_output_text(response).split()).strip()
    if caption.startswith("\\caption{") and caption.endswith("}"):
        caption = caption[len("\\caption{") : -1].strip()
    if not caption:
        raise StudioError("GPT 没有返回可用的 Caption。")
    if len(caption) > 2000:
        raise StudioError("GPT 返回的 Caption 超过 2000 字符，请缩短 Prompt 后重试。")
    synthetic = "[SYNTHETIC]" in current_caption or any(
        isinstance(value, dict) and value.get("synthetic") is True
        for value in evidence.values()
    )
    if synthetic and "[SYNTHETIC]" not in caption:
        caption = "[SYNTHETIC] " + caption
    return caption


def figure_latex(
    figure_id: str, figure_state: dict[str, Any] | None = None
) -> str:
    """Return the canonical LaTeX reference and float for one approved figure."""
    definition = FIGURES[figure_id]
    paths = figure_paths(figure_id)
    figure_state = figure_state or {}
    caption = str(figure_state.get("caption") or definition["caption"]).strip()
    mode = figure_state.get("layout_mode")
    stored_width = figure_state.get("layout_width")
    if mode == "wrapfigure":
        relative_pdf = paths["pdf"].relative_to(PAPER).as_posix()
        return "\n".join(
            [
                r"\begin{wrapfigure}{r}{0.48\columnwidth}",
                "  \\centering",
                f"  \\includegraphics[width=\\linewidth]{{{relative_pdf}}}",
                f"  \\caption{{{caption}}}",
                f"  \\label{{{definition['label']}}}",
                r"\end{wrapfigure}",
            ]
        )
    if mode in {"single-column", "two-column"}:
        wide = mode == "two-column"
    elif definition["kind"] == "data" and stored_width:
        wide = stored_width == "two-column"
    else:
        wide = definition["width"].startswith("two-column")
    environment = "figure*" if wide else "figure"
    width = "\\textwidth" if wide else "\\columnwidth"
    relative_pdf = paths["pdf"].relative_to(PAPER).as_posix()
    return "\n".join(
        [
            f"\\begin{{{environment}}}[t]",
            "  \\centering",
            f"  \\includegraphics[width={width}]{{{relative_pdf}}}",
            f"  \\caption{{{caption}}}",
            f"  \\label{{{definition['label']}}}",
            f"\\end{{{environment}}}",
        ]
    )


def section_figure_anchors(
    section: str, figure_states: dict[str, dict[str, Any]]
) -> dict[str | None, list[str]]:
    """Group approved figures by the paragraph after which they belong."""
    anchors: dict[str | None, list[str]] = {}
    for figure_id in FIGURE_ORDER:
        definition = FIGURES[figure_id]
        if section not in definition["source_sections"]:
            continue
        if figure_states.get(figure_id, {}).get("status") != "approved":
            continue
        dependency_ids = definition.get("depends_on_paragraphs", {}).get(section, [])
        anchor = figure_states.get(figure_id, {}).get("placement_after")
        if not anchor:
            anchor = dependency_ids[-1] if dependency_ids else None
        anchors.setdefault(anchor, []).append(figure_id)
    return anchors


def section_figure_placeholder_anchors(
    section: str,
    section_state: dict[str, Any],
    figure_states: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    """Place one labelled draft box after an artifact's first accepted reference."""
    accepted = accepted_paragraph_ids(section_state)
    anchors: dict[str, list[str]] = {}
    for figure_id in FIGURE_ORDER:
        if figure_states.get(figure_id, {}).get("status") == "approved":
            continue
        binding = first_artifact_binding(figure_id)
        if binding is None or binding[0] != section or binding[1] not in accepted:
            continue
        anchors.setdefault(binding[1], []).append(figure_id)
    return anchors


def figure_placeholder_latex(
    figure_id: str, figure_state: dict[str, Any] | None = None
) -> str:
    """Return a compilable labelled float until the real figure is approved."""
    definition = FIGURES[figure_id]
    figure_state = figure_state or {}
    caption = str(figure_state.get("caption") or definition["caption"]).strip()
    mode = figure_state.get("layout_mode")
    wide = mode == "two-column" or (
        mode is None and definition["width"].startswith("two-column")
    )
    environment = "figure*" if wide else "figure"
    box_width = r"0.94\textwidth" if wide else r"0.94\columnwidth"
    placeholder = latex_escape_title(
        f"{figure_id} placeholder -- figure generation is in progress"
    )
    return "\n".join(
        [
            f"\\begin{{{environment}}}[t]",
            r"  \centering",
            f"  \\fbox{{\\parbox[c][0.16\\textheight][c]{{{box_width}}}{{\\centering {placeholder}}}}}",
            f"  \\caption{{{caption}}}",
            f"  \\label{{{definition['label']}}}",
            f"\\end{{{environment}}}",
        ]
    )


def section_table_anchors(
    section: str, table_states: dict[str, dict[str, Any]]
) -> dict[str | None, list[str]]:
    """Group approved tables by the paragraph after which they belong."""
    anchors: dict[str | None, list[str]] = {}
    for table_id in TABLE_ORDER:
        definition = TABLES[table_id]
        if section not in definition["source_sections"]:
            continue
        stored = table_states.get(table_id, {})
        if stored.get("status") != "approved" or not stored.get("latex"):
            continue
        related = definition.get("related_paragraphs", {}).get(section, [])
        anchor = stored.get("placement_after") or (related[-1] if related else None)
        anchors.setdefault(anchor, []).append(table_id)
    return anchors


def section_table_placeholder_anchors(
    section: str,
    section_state: dict[str, Any],
    table_states: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    """Place one labelled draft box after a table's first accepted reference.

    Mirrors section_figure_placeholder_anchors: without this, a batch-written
    paragraph that cites a not-yet-approved table's \\ref{} compiles with a
    genuinely undefined reference for the rest of the run, since table
    materialization (like figure materialization) only happens once the
    whole full-draft loop finishes.
    """
    accepted = accepted_paragraph_ids(section_state)
    anchors: dict[str, list[str]] = {}
    for table_id in TABLE_ORDER:
        if table_states.get(table_id, {}).get("status") == "approved":
            continue
        binding = first_artifact_binding(table_id)
        if binding is None or binding[0] != section or binding[1] not in accepted:
            continue
        anchors.setdefault(binding[1], []).append(table_id)
    return anchors


def table_placeholder_latex(
    table_id: str, table_state: dict[str, Any] | None = None
) -> str:
    """Return a compilable labelled float until the real table is approved."""
    definition = TABLES[table_id]
    table_state = table_state or {}
    caption = str(table_state.get("caption") or definition["caption"]).strip()
    wide = str(definition.get("width", "")).startswith("two-column")
    environment = "table*" if wide else "table"
    box_width = r"0.94\textwidth" if wide else r"0.94\columnwidth"
    placeholder = latex_escape_title(
        f"{table_id} placeholder -- table generation is in progress"
    )
    return "\n".join(
        [
            f"\\begin{{{environment}}}[t]",
            r"  \centering",
            f"  \\fbox{{\\parbox[c][0.1\\textheight][c]{{{box_width}}}{{\\centering {placeholder}}}}}",
            f"  \\caption{{{caption}}}",
            f"  \\label{{{definition['label']}}}",
            f"\\end{{{environment}}}",
        ]
    )


def render_section_source(
    section: str,
    section_state: dict[str, Any],
    figure_states: dict[str, dict[str, Any]] | None = None,
    table_states: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Render accepted paragraphs without discarding the section's LaTeX wrapper."""
    accepted_paragraphs = [
        (item["id"], normalize_latex_ready_text(item["accepted_text"].strip()))
        for item in section_state["paragraphs"]
        if item["accepted_text"].strip()
    ]
    accepted_text = "\n\n".join(text for _, text in accepted_paragraphs)
    section_metadata = SECTION_MAP[section]
    if section_metadata.get("render") == "abstract":
        marked = "\n\n".join(
            f"% PAPER_STUDIO_PARAGRAPH:{paragraph_id}\n{text}"
            for paragraph_id, text in accepted_paragraphs
        )
        return marked + "\n", accepted_text

    title = SECTION_LATEX_TITLES.get(section)
    if not title:
        raise StudioError(f"Section {section} is missing latex_title in paper_studio.json")
    parts = [f"\\section{{{title}}}"]
    if section_metadata.get("start_label"):
        parts.append(f"\\label{{{section_metadata['start_label']}}}")
    figure_anchors = section_figure_anchors(section, figure_states or {})
    placeholder_anchors = (
        section_figure_placeholder_anchors(section, section_state, figure_states)
        if figure_states is not None
        else {}
    )
    table_anchors = section_table_anchors(section, table_states or {})
    table_placeholder_anchors = (
        section_table_placeholder_anchors(section, section_state, table_states)
        if table_states is not None
        else {}
    )
    for paragraph_id, text in accepted_paragraphs:
        parts.append(f"% PAPER_STUDIO_PARAGRAPH:{paragraph_id}")
        parts.append(text)
        parts.extend(
            figure_latex(figure_id, (figure_states or {}).get(figure_id))
            for figure_id in figure_anchors.pop(paragraph_id, [])
        )
        parts.extend(
            figure_placeholder_latex(
                figure_id, (figure_states or {}).get(figure_id)
            )
            for figure_id in placeholder_anchors.pop(paragraph_id, [])
        )
        parts.extend(
            (table_states or {})[table_id]["latex"]
            for table_id in table_anchors.pop(paragraph_id, [])
        )
        parts.extend(
            table_placeholder_latex(table_id, (table_states or {}).get(table_id))
            for table_id in table_placeholder_anchors.pop(paragraph_id, [])
        )
    for figure_ids in figure_anchors.values():
        parts.extend(
            figure_latex(figure_id, (figure_states or {}).get(figure_id))
            for figure_id in figure_ids
        )
    for table_ids in table_anchors.values():
        parts.extend((table_states or {})[table_id]["latex"] for table_id in table_ids)
    if len(parts) == 1:
        parts.append("% Awaiting paragraph-level drafting in Paper Studio.")
    if section_metadata.get("end_label"):
        parts.append(f"\\label{{{section_metadata['end_label']}}}")
    return "\n\n".join(parts) + "\n", accepted_text


def paragraph_plan() -> dict[str, Any]:
    if not PARAGRAPH_PLAN_FILE.exists():
        raise StudioError("paper/paragraph_plan.json is missing.")
    return json.loads(PARAGRAPH_PLAN_FILE.read_text(encoding="utf-8"))


def first_artifact_binding(artifact_id: str) -> tuple[str, str] | None:
    """Return the first planned paragraph that is responsible for this artifact."""
    for section, paragraphs in paragraph_plan().get("sections", {}).items():
        for paragraph in paragraphs:
            if artifact_id in paragraph.get("artifacts", []):
                return section, str(paragraph["id"])
    return None


def figure_generation_prerequisites(figure_id: str) -> list[tuple[str, str]]:
    """Return project-configured prose required before a mechanism drawing starts."""
    definition = FIGURES[figure_id]
    configured = definition.get("generation_requires_paragraphs")
    if configured is not None:
        return [
            (section, str(paragraph_id))
            for section, paragraph_ids in configured.items()
            for paragraph_id in paragraph_ids
        ]
    first = first_artifact_binding(figure_id)
    return [first] if first is not None else []


def paragraph_plan_item(section: str, paragraph_id: str) -> dict[str, Any] | None:
    return next(
        (
            paragraph
            for paragraph in paragraph_plan().get("sections", {}).get(section, [])
            if str(paragraph.get("id")) == paragraph_id
        ),
        None,
    )


def mechanism_generation_prerequisite_message(
    missing: list[tuple[str, str]],
) -> str:
    grouped: dict[str, list[str]] = {}
    for section, paragraph_id in missing:
        item = paragraph_plan_item(section, paragraph_id) or {}
        label = str(item.get("heading") or f"{paragraph_id} 段落")
        grouped.setdefault(section, []).append(label)
    groups = []
    for section, labels in grouped.items():
        section_name = str(
            SECTION_MAP.get(section, {}).get("latex_title")
            or SECTION_MAP.get(section, {}).get("title")
            or section
        )
        suffix = " subsection" if all(not label.endswith("段落") for label in labels) else ""
        groups.append(f"{section_name} section 的 {'、'.join(labels)}{suffix}")
    return f"请先生成并写入 {'；'.join(groups)}，然后再画图。"


def validate_project_workspace() -> None:
    """Fail fast when project config, paragraph plan, and artifact bindings disagree."""
    if EMPTY_PROJECT_MODE:
        return
    plan = paragraph_plan()
    planned_sections = plan.get("sections")
    if not isinstance(planned_sections, dict):
        raise StudioError("paper/paragraph_plan.json sections must be an object.")
    configured_sections = set(SECTION_MAP)
    missing_sections = configured_sections - set(planned_sections)
    extra_sections = set(planned_sections) - configured_sections
    if missing_sections or extra_sections:
        details = []
        if missing_sections:
            details.append("缺少 " + ", ".join(sorted(missing_sections)))
        if extra_sections:
            details.append("多出 " + ", ".join(sorted(extra_sections)))
        raise StudioError("paragraph_plan 与 paper_studio.json 的 section 不一致：" + "；".join(details))
    artifact_ids = set(FIGURES) | set(TABLES)
    artifact_bindings = {artifact_id: [] for artifact_id in artifact_ids}
    paragraph_ids: dict[str, set[str]] = {}
    for section, paragraphs in planned_sections.items():
        if not isinstance(paragraphs, list):
            raise StudioError(f"paragraph_plan section {section} must be a list.")
        ids = [str(item.get("id", "")) for item in paragraphs]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise StudioError(f"paragraph_plan section {section} has invalid paragraph ids.")
        paragraph_ids[section] = set(ids)
        for paragraph in paragraphs:
            reference_lines = paragraph.get("reference_lines")
            if (
                not isinstance(reference_lines, list)
                or len(reference_lines) != 2
                or any(not isinstance(item, int) or isinstance(item, bool) or item < 1 for item in reference_lines)
                or reference_lines[0] > reference_lines[1]
            ):
                raise StudioError(
                    f"段落 {paragraph['id']} 的 reference_lines 必须是两个递增的正整数。"
                )
            bound = paragraph.get("artifacts", [])
            if not isinstance(bound, list) or len(bound) != len(set(bound)):
                raise StudioError(
                    f"段落 {paragraph['id']} 的 artifacts 必须是无重复 ID 的列表。"
                )
            unknown = set(bound) - artifact_ids
            if unknown:
                raise StudioError(
                    f"段落 {paragraph['id']} 绑定了未知图表：{', '.join(sorted(unknown))}"
                )
            for artifact_id in bound:
                artifact_bindings[artifact_id].append(f"{section}/{paragraph['id']}")
    configured_reference = str(PROJECT_CONFIG.get("paths", {}).get("reference", "")).strip()
    if str(plan.get("reference_file", "")).strip() != configured_reference:
        raise StudioError(
            "paragraph_plan.reference_file 必须与 paper_studio.json paths.reference 完全一致。"
        )
    for section, paragraphs in planned_sections.items():
        for paragraph in paragraphs:
            reference_excerpt(paragraph["reference_lines"])
    unbound = sorted(
        artifact_id for artifact_id, bindings in artifact_bindings.items() if not bindings
    )
    if unbound:
        raise StudioError(
            "每个图表至少要绑定一个负责引用它的段落；当前未绑定："
            + ", ".join(unbound)
        )
    for figure_id, definition in FIGURES.items():
        unknown_figures = set(definition.get("depends_on_figures", [])) - set(FIGURES)
        if unknown_figures:
            raise StudioError(
                f"{figure_id} 依赖未知 Figure：{', '.join(sorted(unknown_figures))}"
            )
        for section, ids in definition.get("depends_on_paragraphs", {}).items():
            unknown = set(ids) - paragraph_ids.get(section, set())
            if unknown:
                raise StudioError(
                    f"{figure_id} 依赖未知段落：{section} / {', '.join(sorted(unknown))}"
                )
        generation_requirements = definition.get("generation_requires_paragraphs")
        if generation_requirements is not None:
            if definition.get("kind") != "mechanism" or not isinstance(
                generation_requirements, dict
            ):
                raise StudioError(
                    f"{figure_id}.generation_requires_paragraphs 只能用于机制图且必须是对象。"
                )
            for section, ids in generation_requirements.items():
                if not isinstance(ids, list) or not ids:
                    raise StudioError(
                        f"{figure_id} 的绘图前置段落必须是非空列表：{section}"
                    )
                unknown = set(ids) - paragraph_ids.get(section, set())
                if unknown:
                    raise StudioError(
                        f"{figure_id} 的绘图前置段落不存在："
                        f"{section} / {', '.join(sorted(unknown))}"
                    )
    for artifact_id, definition in {**FIGURES, **TABLES}.items():
        shape_spec = str(definition.get("shape_spec", "")).strip()
        if shape_spec:
            path = _project_path(ROOT, shape_spec, f"{artifact_id}.shape_spec")
            if not path.exists():
                raise StudioError(f"{artifact_id} 的 shape_spec 不存在：{shape_spec}")


def planned_paragraphs(section: str) -> list[dict[str, Any]]:
    if EMPTY_PROJECT_MODE or not project_files_ready():
        return []
    specs = paragraph_plan().get("sections", {}).get(section, [])
    return [
        {
            **spec,
            "candidate": None,
            "accepted_text": "",
            "history": [],
        }
        for spec in specs
    ]


def heading_latex(heading: str | None, heading_style: str | None = None) -> str:
    """Return the exact plan-defined LaTeX heading for one paragraph group."""
    if not heading:
        return ""
    style = heading_style or "paragraph"
    if style not in {"paragraph", "textbf", "subsection"}:
        raise StudioError(f"Unsupported heading style: {style}")
    return f"\\{style}{{{heading.strip()}}}"


def enforce_required_heading(
    text: str,
    heading: str | None,
    heading_style: str | None = None,
) -> str:
    """Make an outline-defined group heading deterministic instead of model-inferred."""
    prose = text.strip()
    if not prose:
        return ""
    prose = re.sub(
        r"^\\(?:paragraph|subsection|textbf)\{[^{}]*\}\s*",
        "",
        prose,
        count=1,
    ).strip()
    if not heading:
        return prose
    expected = heading_latex(heading, heading_style)
    separator = "\n\n" if (heading_style or "paragraph") == "subsection" else " "
    return f"{expected}{separator}{prose}".strip()


def reference_excerpt(lines: list[int]) -> str:
    plan = paragraph_plan()
    path = ROOT / plan["reference_file"]
    source_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = lines
    selected = source_lines[max(start - 1, 0) : min(end, len(source_lines))]
    text = " ".join(line.strip("\f ").strip() for line in selected if line.strip())
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > REFERENCE_EXCERPT_MAX_CHARS:
        raise StudioError(
            "reference_lines 选中了过长的参考论文片段（"
            f"{len(text)} 字符，上限 {REFERENCE_EXCERPT_MAX_CHARS}）；"
            "请只绑定与当前段落修辞作用匹配的局部段落。"
        )
    return text


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": "1.2",
        "project_id": PROJECT_ID,
        "llm_provider": DEFAULT_PROVIDER,
        "model": PROVIDER_DEFAULT_MODELS.get(DEFAULT_PROVIDER) or DEFAULT_MODEL,
        "title_editor": {
            "prompt": "",
            "candidate": "",
            "previous_response_id": None,
            "last_message": "",
        },
        "full_draft_job": None,
        "updated_at": None,
        "sections": {
            key: {
                "title": title,
                "file": filename,
                "previous_response_id": None,
                "bibliography_fingerprint": None,
                "conversation_section_fingerprint": None,
                "revision": 0,
                "current_index": 0,
                "paragraphs": planned_paragraphs(key),
                "accepted_text": "",
            }
            for key, title, filename in SECTIONS
        },
        "figures": {
            figure_id: {
                "status": "pending",
                "previous_response_id": None,
                "revision": 0,
                "approved_at": None,
                "prompt_approved_at": None,
                "last_message": "",
                "draw_prompt": "",
                "prompt_instruction": "",
                "prompt_history": [],
                "agent_prompt": "",
                "agent_history": [],
                "layout_prompt": "",
                "layout_prompt_is_default": False,
                "layout_plan": {},
                "composed_at": None,
                "layout_width": None,
                "layout_mode": (
                    "two-column"
                    if FIGURES[figure_id]["width"].startswith("two-column")
                    else "single-column"
                ),
                "requested_layout_width": (
                    "two-column"
                    if FIGURES[figure_id]["width"].startswith("two-column")
                    else "single-column"
                ),
                "panels": {
                    panel["id"]: {
                        "status": "pending",
                        "revision": 0,
                        "agent_prompt": "",
                        "last_message": "",
                        "progress": 0,
                        "progress_message": "",
                    }
                    for panel in FIGURES[figure_id].get("panels", [])
                },
                "placement_after": None,
                "progress": 0,
                "progress_message": "",
                "job_token": None,
                "job_revision": 0,
                "job_started_at": None,
            }
            for figure_id in FIGURE_ORDER
        },
        "tables": {
            table_id: {
                "status": "pending",
                "revision": 0,
                "approved_at": None,
                "last_message": "",
                "latex": "",
                "generation_prompt": default_table_prompt(table_id),
                "prompt_history": [],
                "agent_prompt": "",
                "agent_history": [],
                "placement_after": None,
                "progress": 0,
                "progress_message": "",
                "job_token": None,
                "job_revision": 0,
                "job_started_at": None,
            }
            for table_id in TABLE_ORDER
        },
        "compile": {"status": "not_run", "message": "", "updated_at": None},
    }


def load_state() -> dict[str, Any]:
    with STATE_LOCK:
        if not STATE_FILE.exists():
            return _default_state()
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        default = _default_state()
        stored_project_id = str(state.get("project_id", "")).strip()
        if stored_project_id and stored_project_id != PROJECT_ID:
            return default
        state["project_id"] = PROJECT_ID
        stored_sections = state.get("sections", {})
        state["sections"] = {
            key: stored_sections.get(key, section)
            for key, section in default["sections"].items()
        }
        for key, section in default["sections"].items():
            current = state.setdefault("sections", {}).setdefault(key, section)
            existing = {
                item.get("id"): item
                for item in current.get("paragraphs", [])
                if item.get("id")
            }
            appended_to_completed_section = bool(
                existing
                and any(
                    planned["id"] not in existing for planned in section["paragraphs"]
                )
                and all(
                    str(item.get("accepted_text", "")).strip()
                    for item in existing.values()
                )
            )
            merged = []
            for planned in section["paragraphs"]:
                prior = existing.get(planned["id"], {})
                candidate = prior.get("candidate")
                if candidate:
                    candidate = {
                        **candidate,
                        "text": enforce_required_heading(
                            str(candidate.get("text", "")),
                            planned.get("heading"),
                            planned.get("heading_style"),
                        ),
                    }
                accepted_text = enforce_required_heading(
                    str(prior.get("accepted_text", "")),
                    planned.get("heading"),
                    planned.get("heading_style"),
                )
                merged.append(
                    {
                        **planned,
                        "candidate": candidate,
                        "accepted_text": accepted_text,
                        "history": prior.get("history", []),
                    }
                )
            current["paragraphs"] = merged
            selected = min(int(current.get("current_index", 0)), len(merged))
            if appended_to_completed_section:
                selected = next_unaccepted_index(merged)
            elif selected >= len(merged):
                next_index = next_unaccepted_index(merged)
                selected = (
                    len(merged) - 1
                    if merged and next_index >= len(merged)
                    else next_index
                )
            current["current_index"] = selected
            current["accepted_text"] = "\n\n".join(
                item["accepted_text"].strip()
                for item in merged
                if item["accepted_text"].strip()
            )
            current.pop("candidate", None)
            current.pop("history", None)
        if state.get("llm_provider") not in PROVIDER_DEFAULT_MODELS:
            state["llm_provider"] = "openai"
            if state.get("model") == "model-name":
                state["model"] = PROVIDER_DEFAULT_MODELS["openai"]
        state.setdefault("llm_provider", DEFAULT_PROVIDER)
        state.setdefault("model", PROVIDER_DEFAULT_MODELS.get(state["llm_provider"]) or DEFAULT_MODEL)
        title_editor = state.setdefault("title_editor", default["title_editor"])
        for field, value in default["title_editor"].items():
            title_editor.setdefault(field, value)
        draft_job = state.setdefault("full_draft_job", None)
        if (
            isinstance(draft_job, dict)
            and draft_job.get("status") == "running"
            and draft_job.get("server_instance") != SERVER_INSTANCE_TOKEN
        ):
            state["full_draft_job"] = {
                **draft_job,
                "status": "failed",
                "token": None,
                "progress_message": "服务已重启；全文生成任务已停止，可从未完成段落继续。",
                "finished_at": int(time.time()),
            }
        state.setdefault("compile", default["compile"])
        stored_figures = state.get("figures", {})
        state["figures"] = {
            figure_id: stored_figures.get(figure_id, figure_state)
            for figure_id, figure_state in default["figures"].items()
        }
        for figure_id, figure_state in default["figures"].items():
            current_figure = state.setdefault("figures", {}).setdefault(
                figure_id, figure_state
            )
            for field, value in figure_state.items():
                current_figure.setdefault(field, value)
            if current_figure.get("layout_prompt_is_default"):
                current_figure["layout_prompt"] = ""
                current_figure["layout_prompt_is_default"] = False
            for panel_id, panel_state in figure_state.get("panels", {}).items():
                current_panel = current_figure.setdefault("panels", {}).setdefault(
                    panel_id, panel_state
                )
                for field, value in panel_state.items():
                    current_panel.setdefault(field, value)
                panel_paths = data_panel_paths(figure_id, panel_id)
                recovered_panel_exists = panel_paths["pdf"].exists() or (
                    len(figure_state.get("panels", {})) == 1
                    and figure_paths(figure_id)["pdf"].exists()
                )
                if (
                    recovered_panel_exists
                    and current_panel.get("status") in {"built", "approved"}
                    and not str(current_panel.get("agent_prompt", "")).strip()
                ):
                    current_panel["agent_prompt"] = recovered_data_panel_prompt(
                        figure_id, panel_id
                    )
            if (
                FIGURES[figure_id]["kind"] == "mechanism"
                and figure_paths(figure_id)["pdf"].exists()
                and current_figure.get("status") in {"built", "approved"}
                and not str(current_figure.get("draw_prompt", "")).strip()
            ):
                current_figure["draw_prompt"] = recovered_mechanism_prompt(figure_id)
            if (
                FIGURES[figure_id]["kind"] == "data"
                and not current_figure.get("composed_at")
                and not current_figure.get("approved_at")
                and current_figure.get("status") not in FIGURE_RUNNING_STATUSES
            ):
                current_figure["status"] = "pending"
        stored_tables = state.get("tables", {})
        state["tables"] = {
            table_id: stored_tables.get(table_id, table_state)
            for table_id, table_state in default["tables"].items()
        }
        for table_id, table_state in default["tables"].items():
            current_table = state.setdefault("tables", {}).setdefault(table_id, table_state)
            for field, value in table_state.items():
                current_table.setdefault(field, value)
        state["schema_version"] = default["schema_version"]
        return state


def save_state(state: dict[str, Any]) -> None:
    with STATE_LOCK:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        # A slow background figure job and an unrelated prose request can both load
        # the same snapshot. Preserve whichever figure job revision reached disk
        # later instead of letting the prose save resurrect an older running state.
        if STATE_FILE.exists():
            try:
                persisted = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                persisted = {}
            if persisted.get("project_id") == state.get("project_id"):
                # Accepted prose is monotonic per section. A slow citation lookup,
                # next-paragraph generation, figure job, or Agent reload may hold an
                # older whole-state snapshot; never let it erase a newer accepted
                # paragraph from another section.
                for section_id, persisted_section in persisted.get("sections", {}).items():
                    incoming_section = state.get("sections", {}).get(section_id)
                    if not isinstance(incoming_section, dict):
                        continue
                    if int(persisted_section.get("revision", 0)) > int(
                        incoming_section.get("revision", 0)
                    ):
                        state["sections"][section_id] = persisted_section
                for figure_id, persisted_figure in persisted.get("figures", {}).items():
                    incoming_figure = state.get("figures", {}).get(figure_id)
                    if not isinstance(incoming_figure, dict):
                        continue
                    if int(persisted_figure.get("job_revision", 0)) > int(
                        incoming_figure.get("job_revision", 0)
                    ):
                        state["figures"][figure_id] = persisted_figure
                for table_id, persisted_table in persisted.get("tables", {}).items():
                    incoming_table = state.get("tables", {}).get(table_id)
                    if not isinstance(incoming_table, dict):
                        continue
                    if int(persisted_table.get("job_revision", 0)) > int(
                        incoming_table.get("job_revision", 0)
                    ):
                        state["tables"][table_id] = persisted_table
        state["updated_at"] = int(time.time())
        temporary = STATE_FILE.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, STATE_FILE)


def replace_state(state: dict[str, Any]) -> None:
    """Intentionally replace runtime state, bypassing monotonic stale-save guards."""
    with STATE_LOCK:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = int(time.time())
        temporary = STATE_FILE.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, STATE_FILE)


def read_text(path: Path, limit: int = 24000) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def writing_style_context() -> str:
    profile = read_text(ROOT / "researcher-profile/PROFILE.html", 50000)
    html_match = re.search(
        r"<section\b[^>]*(?:id|data-report-section)=[\"']writing-style[\"'][^>]*>"
        r"(.*?)</section>",
        profile,
        re.DOTALL | re.IGNORECASE,
    )
    if html_match:
        return strip_html(html_match.group(1))[:16000]
    match = re.search(
        r"## Writing Style\s*(.*?)(?=\n## Experiment Templates)",
        profile,
        re.DOTALL,
    )
    return match.group(1).strip()[:16000] if match else ""


def strip_html(source: str) -> str:
    source = re.sub(r"<script\b.*?</script>", " ", source, flags=re.DOTALL | re.I)
    source = re.sub(r"<style\b.*?</style>", " ", source, flags=re.DOTALL | re.I)
    source = re.sub(r"<[^>]+>", " ", source)
    source = html.unescape(source)
    return re.sub(r"\s+", " ", source).strip()


def metrics_bundle() -> dict[str, Any]:
    if not METRICS_FILE.exists():
        return {}
    return json.loads(METRICS_FILE.read_text(encoding="utf-8"))


def figure_paths(figure_id: str) -> dict[str, Path]:
    slug = artifact_label_slug(FIGURES[figure_id]["label"], fallback=figure_id)
    deliverable_slug = str(FIGURES[figure_id].get("deliverable_stem") or slug)
    return {
        "spec": FIGURE_SOURCE_DIR / f"{slug}_spec.json",
        "shapes": FIGURE_SOURCE_DIR / f"{slug}_shapes.json",
        "source": FIGURE_SOURCE_DIR / f"{slug}_source.txt",
        "draft": FIGURE_SOURCE_DIR / f"{slug}.bg.png",
        "preview": FIGURE_DIR / f"{deliverable_slug}.png",
        "pdf": FIGURE_DIR / f"{deliverable_slug}.pdf",
        "pptx": FIGURE_DIR / f"{deliverable_slug}.pptx",
        "agent_source": DATA_FIGURE_AGENT_DIR / f"{figure_id.lower()}_{slug}.py",
        "layout_source": FIGURE_SOURCE_DIR / f"{slug}_layout.json",
        "layout_prompt": FIGURE_SOURCE_DIR / f"{slug}_layout_prompt.txt",
    }


def mechanism_spec_path(figure_id: str) -> Path:
    """Resolve a mechanism spec across canonical and reorganized source trees."""
    paths = figure_paths(figure_id)
    slug = artifact_label_slug(FIGURES[figure_id]["label"], fallback=figure_id)
    canonical = paths.get("spec", FIGURE_SOURCE_DIR / f"{slug}_spec.json")
    if canonical.exists():
        return canonical
    deliverable_stem = str(FIGURES[figure_id].get("deliverable_stem") or "").strip()
    relocated = FIGURE_SOURCE_DIR / f"{deliverable_stem}_spec.json"
    return relocated if deliverable_stem and relocated.exists() else canonical


def mechanism_draft_path(figure_id: str) -> Path:
    """Resolve the canonical GPT draft or the latest prompt-backed archive."""
    paths = figure_paths(figure_id)
    if paths["draft"].exists() or FIGURES[figure_id]["kind"] != "mechanism":
        return paths["draft"]
    spec_path = mechanism_spec_path(figure_id)
    if not spec_path.exists():
        return paths["draft"]
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        iteration_dir = spec_path.parent / "iterations" / str(spec["figure_id"])
    except (OSError, KeyError, json.JSONDecodeError):
        return paths["draft"]
    for candidate in reversed(sorted(iteration_dir.glob("round_*.png"))):
        if candidate.with_suffix(".prompt.txt").is_file():
            return candidate
    return paths["draft"]


def mechanism_gpt_preview_no_text(figure_id: str) -> bool:
    """Expose whether the archived GPT image was intentionally text-free."""
    if FIGURES[figure_id]["kind"] != "mechanism":
        return False
    spec_path = mechanism_spec_path(figure_id)
    if not spec_path.exists():
        return False
    try:
        return bool(json.loads(spec_path.read_text(encoding="utf-8")).get("no_text"))
    except (OSError, json.JSONDecodeError):
        return False


def data_panel_paths(figure_id: str, panel_id: str) -> dict[str, Path]:
    """Return the independently generated artifacts for one atomic data panel."""
    if panel_id not in {item["id"] for item in FIGURES[figure_id].get("panels", [])}:
        raise StudioError(f"Unknown panel {figure_id}{panel_id}.")
    slug = artifact_label_slug(FIGURES[figure_id]["label"], fallback=figure_id)
    stem = f"{figure_id.lower()}_{panel_id}_{slug}"
    return {
        "source": DATA_FIGURE_AGENT_DIR / f"{stem}.py",
        "pdf": FIGURE_SOURCE_DIR / "data_panels" / f"{stem}.pdf",
        "preview": FIGURE_SOURCE_DIR / "data_panels" / f"{stem}.png",
    }


def accepted_paragraph_ids(section_state: dict[str, Any]) -> set[str]:
    return {
        item["id"]
        for item in section_state.get("paragraphs", [])
        if item.get("accepted_text")
    }


def has_result_path(metrics: dict[str, Any], dotted_path: str) -> bool:
    value: Any = metrics
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return value not in (None, "", [], {})


def result_path_value(metrics: dict[str, Any], dotted_path: str) -> Any:
    value: Any = metrics
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def traceable_result_payload(
    result_keys: list[str], metrics: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the exact, provenance-preserving input consumed by plot programs."""
    metrics = metrics if metrics is not None else metrics_bundle()
    missing = [key for key in result_keys if not has_result_path(metrics, key)]
    if missing:
        raise StudioError("缺少结果数据：" + ", ".join(missing))
    fixture = metrics.get("fixture", {})
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "source_metrics": PROJECT_CONFIG["paths"]["metrics"],
        "traceable_results": {
            key: result_path_value(metrics, key) for key in result_keys
        },
    }
    if isinstance(fixture, dict):
        if "synthetic" in fixture:
            payload["synthetic"] = fixture["synthetic"]
        if "notice" in fixture:
            payload["notice"] = fixture["notice"]
        payload["provenance"] = fixture
    return payload


def figure_generation_gate(
    figure_id: str, state: dict[str, Any], metrics: dict[str, Any] | None = None
) -> tuple[bool, str]:
    definition = FIGURES[figure_id]
    metrics = metrics if metrics is not None else metrics_bundle()
    missing_results = [
        key for key in definition.get("result_keys", []) if not has_result_path(metrics, key)
    ]
    if missing_results:
        return False, "缺少结果数据：" + ", ".join(missing_results)
    if definition.get("kind") == "mechanism":
        requirements = figure_generation_prerequisites(figure_id)
        if not requirements:
            return False, f"{figure_id} 尚未配置绘图所需的正文段落。"
        missing = [
            (section, paragraph_id)
            for section, paragraph_id in requirements
            if paragraph_id
            not in accepted_paragraph_ids(state["sections"][section])
        ]
        if missing:
            return False, mechanism_generation_prerequisite_message(missing)
    return True, ""


def figure_insertion_gate(
    figure_id: str, state: dict[str, Any], metrics: dict[str, Any] | None = None
) -> tuple[bool, str]:
    definition = FIGURES[figure_id]
    binding = first_artifact_binding(figure_id)
    if binding is None:
        return False, f"{figure_id} 尚未绑定负责首次引用它的段落。"
    section, paragraph_id = binding
    if paragraph_id not in accepted_paragraph_ids(state["sections"][section]):
        return False, f"插入前请先写入首个引用段落 {paragraph_id}。"
    for dependency in definition.get("depends_on_figures", []):
        if state["figures"][dependency].get("status") != "approved":
            return False, f"图候选可以先生成；插入正文前请先确认 {dependency}"
    return figure_generation_gate(figure_id, state, metrics)


def figure_gate(
    figure_id: str, state: dict[str, Any], metrics: dict[str, Any] | None = None
) -> tuple[bool, str]:
    """Backward-compatible name for the stricter insertion gate."""
    return figure_insertion_gate(figure_id, state, metrics)


def figure_public_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = metrics_bundle()
    result: list[dict[str, Any]] = []
    for figure_id in FIGURE_ORDER:
        definition = FIGURES[figure_id]
        stored = state["figures"][figure_id]
        section = definition["source_sections"][0]
        paragraphs = state["sections"][section]["paragraphs"]
        dependency_ids = definition.get("depends_on_paragraphs", {}).get(section, [])
        placement_after = stored.get("placement_after")
        if not placement_after:
            placement_after = dependency_ids[-1] if dependency_ids else next(
                (
                    item["id"]
                    for item in reversed(paragraphs)
                    if item.get("accepted_text")
                ),
                None,
            )
        generation_ready, generation_gate_reason = figure_generation_gate(
            figure_id, state, metrics
        )
        insertion_ready, insertion_gate_reason = figure_insertion_gate(
            figure_id, state, metrics
        )
        paths = figure_paths(figure_id)
        mechanism_draft = mechanism_draft_path(figure_id)
        is_data = definition["kind"] == "data"
        preview_kind = "draft" if mechanism_draft.exists() else "preview"
        preview_path = mechanism_draft if preview_kind == "draft" else paths["preview"]
        composition_ready = bool(stored.get("composed_at") and paths["pdf"].exists())
        if is_data:
            if composition_ready:
                preview_kind = "pdf"
                preview_path = paths["pdf"]
            else:
                preview_path = Path("__paper_studio_missing_composition__")
        elif stored.get("status") in {"built", "approved"} and paths["pdf"].exists():
            preview_kind = "pdf"
            preview_path = paths["pdf"]
        panels = []
        for panel in definition.get("panels", []):
            panel_id = panel["id"]
            panel_stored = stored.get("panels", {}).get(panel_id, {})
            panel_paths = data_panel_paths(figure_id, panel_id)
            panel_preview_kind = "pdf" if panel_paths["pdf"].exists() else "preview"
            panel_preview_path = panel_paths[panel_preview_kind]
            recovered_single_panel = bool(
                len(definition.get("panels", [])) == 1
                and composition_ready
                and not panel_preview_path.exists()
                and paths["pdf"].exists()
            )
            panel_preview_url = (
                f"/figure-file/{figure_id}/pdf?v={int(paths['pdf'].stat().st_mtime)}"
                if recovered_single_panel
                else (
                    f"/figure-panel-file/{figure_id}/{panel_id}/{panel_preview_kind}"
                    f"?v={int(panel_preview_path.stat().st_mtime)}"
                    if panel_preview_path.exists()
                    else None
                )
            )
            panels.append(
                {
                    **panel,
                    "status": panel_stored.get("status", "pending"),
                    "revision": int(panel_stored.get("revision", 0)),
                    "agent_prompt": panel_stored.get("agent_prompt", ""),
                    "last_message": panel_stored.get("last_message", ""),
                    "progress": int(panel_stored.get("progress", 0)),
                    "progress_message": panel_stored.get("progress_message", ""),
                    "preview_url": panel_preview_url,
                    "preview_type": "pdf" if recovered_single_panel else panel_preview_kind,
                    "downloads": {
                        "pdf": (
                            f"/figure-file/{figure_id}/pdf"
                            if recovered_single_panel
                            else f"/figure-panel-file/{figure_id}/{panel_id}/pdf"
                        )
                    }
                    if panel_paths["pdf"].exists() or recovered_single_panel
                    else {},
                }
            )
        result.append(
            {
                "id": figure_id,
                **definition,
                "caption": stored.get("caption") or definition["caption"],
                "status": stored.get("status", "pending"),
                "revision": int(stored.get("revision", 0)),
                "approved_at": stored.get("approved_at"),
                "prompt_approved_at": stored.get("prompt_approved_at"),
                "conversation_active": bool(stored.get("previous_response_id")),
                "last_message": stored.get("last_message", ""),
                "draw_prompt": stored.get("draw_prompt", ""),
                "prompt_instruction": stored.get("prompt_instruction", ""),
                "agent_prompt": stored.get("agent_prompt", ""),
                "layout_prompt": stored.get("layout_prompt", ""),
                "layout_prompt_is_default": False,
                "layout_plan": stored.get("layout_plan", {}),
                "width": stored.get("layout_width") or definition["width"],
                "requested_width": stored.get("requested_layout_width")
                or (
                    "two-column"
                    if definition["width"].startswith("two-column")
                    else "single-column"
                ),
                "layout_mode": stored.get("layout_mode")
                or (
                    "two-column"
                    if definition["width"].startswith("two-column")
                    else "single-column"
                ),
                "composition_ready": composition_ready,
                "panels": panels,
                "placement_after": placement_after,
                "placement_options": [
                    {
                        "id": item["id"],
                        "purpose": item["purpose"],
                        "accepted": bool(item.get("accepted_text")),
                    }
                    for item in paragraphs
                ],
                "progress": int(stored.get("progress", 0)),
                "progress_message": stored.get("progress_message", ""),
                "running_seconds": (
                    max(0, int(time.time()) - int(stored.get("job_started_at") or time.time()))
                    if stored.get("status") in FIGURE_RUNNING_STATUSES
                    else 0
                ),
                "ready": generation_ready,
                "gate_reason": generation_gate_reason,
                "generation_ready": generation_ready,
                "generation_gate_reason": generation_gate_reason,
                "insertion_ready": insertion_ready,
                "insertion_gate_reason": insertion_gate_reason,
                "preview_url": (
                    f"/figure-file/{figure_id}/{preview_kind}"
                    f"?v={int(preview_path.stat().st_mtime)}"
                    if preview_path.exists()
                    else None
                ),
                "preview_type": (
                    "image"
                    if preview_path.suffix.lower() in {".png", ".jpg", ".jpeg"}
                    else "pdf"
                ),
                "gpt_preview_url": (
                    f"/figure-file/{figure_id}/draft"
                    f"?v={int(mechanism_draft.stat().st_mtime)}"
                    if not is_data and mechanism_draft.exists()
                    else None
                ),
                "gpt_preview_no_text": mechanism_gpt_preview_no_text(figure_id),
                "paper_preview_url": (
                    f"/figure-file/{figure_id}/pdf"
                    f"?v={int(paths['pdf'].stat().st_mtime)}"
                    if (
                        not is_data
                        and stored.get("status") in {"built", "approved"}
                        and paths["pdf"].exists()
                    )
                    else None
                ),
                "downloads": {
                    kind: f"/figure-file/{figure_id}/{kind}"
                    for kind in ("pdf", "pptx")
                    if paths[kind].exists() and (not is_data or composition_ready)
                },
            }
        )
    return result


def table_gate(
    table_id: str, state: dict[str, Any], metrics: dict[str, Any] | None = None
) -> tuple[bool, str]:
    definition = TABLES[table_id]
    metrics = metrics if metrics is not None else metrics_bundle()
    missing_results = [
        key for key in definition.get("result_keys", []) if not has_result_path(metrics, key)
    ]
    if missing_results:
        return False, "缺少结果数据：" + ", ".join(missing_results)
    return True, ""


def table_grid(table_id: str, metrics: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    grid = TABLES[table_id]["data_grid"]
    grid_type = str(grid.get("type", ""))
    source = result_path_value(metrics, str(grid.get("path", "")))
    if grid_type == "records":
        if not isinstance(source, list):
            raise StudioError(f"{table_id} data_grid records path must resolve to a list")
        columns = list(grid.get("columns", []))
        headers = [str(column["label"]) for column in columns]
        rows = [
            [str(record.get(str(column["key"]), "—")) for column in columns]
            for record in source
            if isinstance(record, dict)
        ]
        return headers, rows
    if grid_type == "benchmark_rows":
        if not isinstance(source, dict):
            raise StudioError(
                f"{table_id} data_grid benchmark_rows path must resolve to an object"
            )
        benchmark_names = [str(item) for item in grid.get("benchmarks", [])]
        metric_specs = list(grid.get("metrics", []))
        row_key = str(grid.get("row_key", "name"))
        if not benchmark_names or not metric_specs:
            raise StudioError(f"{table_id} benchmark_rows requires benchmarks and metrics")
        first_rows = source.get(benchmark_names[0], {}).get("rows", [])
        row_names = [str(item[row_key]) for item in first_rows if row_key in item]
        indexed = {
            benchmark: {
                str(record[row_key]): record
                for record in source.get(benchmark, {}).get("rows", [])
                if isinstance(record, dict) and row_key in record
            }
            for benchmark in benchmark_names
        }
        headers = [row_key.replace("_", " ").title()]
        headers.extend(
            f"{benchmark} {metric['label']}"
            for benchmark in benchmark_names
            for metric in metric_specs
        )
        rows = []
        for row_name in row_names:
            row = [row_name]
            row.extend(
                str(indexed[benchmark].get(row_name, {}).get(str(metric["key"]), "—"))
                for benchmark in benchmark_names
                for metric in metric_specs
            )
            rows.append(row)
        return headers, rows
    raise StudioError(f"{table_id} uses unsupported data_grid type: {grid_type}")


def parse_table_prompt(
    table_id: str,
    prompt: str,
    available_columns: list[str],
    available_rows: list[list[str]],
) -> dict[str, Any]:
    """Parse the small local table-writing language; no model call is involved."""
    source = prompt.strip() or default_table_prompt(table_id)
    directives: dict[str, str] = {}
    aliases = {
        "数据源": "source",
        "source": "source",
        "列": "columns",
        "columns": "columns",
        "行": "rows",
        "rows": "rows",
        "caption": "caption",
        "标题": "caption",
        "字号": "size",
        "size": "size",
        "最优值": "best",
        "best": "best",
    }
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([^:：]+)[:：]\s*(.*)$", line)
        if not match:
            raise StudioError(
                f"无法解析表格 Prompt 行：{line}。请使用“键: 值”格式。"
            )
        raw_key, value = match.groups()
        key = aliases.get(raw_key.strip().lower())
        if key is None:
            raise StudioError(
                f"不支持的表格 Prompt 指令：{raw_key.strip()}。"
                "支持：数据源、列、行、Caption、字号、最优值。"
            )
        directives[key] = value.strip()

    configured_source = str(PROJECT_CONFIG["paths"]["metrics"]).rstrip("/")
    requested_source = directives.get("source", configured_source).rstrip("/")
    if requested_source not in {"results", configured_source}:
        raise StudioError(
            f"表格数据源固定为 {configured_source}，不能改用非追溯数据。"
        )

    columns = list(available_columns)
    requested_columns = directives.get("columns", "")
    if requested_columns:
        names = [
            item.strip()
            for item in re.split(r"\s*[|,，]\s*", requested_columns)
            if item.strip()
        ]
        lookup = {name.casefold(): name for name in available_columns}
        unknown = [name for name in names if name.casefold() not in lookup]
        if unknown:
            raise StudioError("表格 Prompt 含未知列：" + ", ".join(unknown))
        columns = [lookup[name.casefold()] for name in names]
    identifier = available_columns[0]
    if identifier not in columns:
        raise StudioError(f"表格必须保留标识列 {identifier}。")

    row_lookup = {str(row[0]).casefold(): row for row in available_rows}
    row_directive = directives.get("rows", "source").strip()
    if row_directive.casefold() in {
        "source",
        "all",
        "保持 results/ 顺序",
        "全部",
    }:
        selected_rows = list(available_rows)
    else:
        requested_rows = [
            item.strip()
            for item in re.split(r"\s*[|,，]\s*", row_directive)
            if item.strip()
        ]
        unknown_rows = [
            name for name in requested_rows if name.casefold() not in row_lookup
        ]
        if unknown_rows:
            raise StudioError("表格 Prompt 含未知行：" + ", ".join(unknown_rows))
        selected_rows = [row_lookup[name.casefold()] for name in requested_rows]

    column_indices = [available_columns.index(name) for name in columns]
    rows = [[str(row[index]) for index in column_indices] for row in selected_rows]
    size = directives.get("size", "small").lstrip("\\").casefold()
    if size not in {"small", "footnotesize", "scriptsize"}:
        raise StudioError("字号仅支持 small、footnotesize 或 scriptsize。")
    best = directives.get("best", "none").casefold()
    best_aliases = {"无": "none", "不加粗": "none", "最大": "max", "最小": "min"}
    best = best_aliases.get(best, best)
    if best not in {"none", "max", "min"}:
        raise StudioError("最优值仅支持 none、max 或 min。")
    caption = directives.get("caption", TABLES[table_id]["caption"]).strip()
    if not caption:
        raise StudioError("Caption 不能为空。")
    return {
        "columns": columns,
        "rows": rows,
        "caption": caption,
        "size": size,
        "best": best,
        "prompt": source,
    }


def latex_escape_cell(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "↑": r"$\uparrow$",
        "↓": r"$\downarrow$",
    }
    return "".join(replacements.get(character, character) for character in value)


def numeric_cell(value: str) -> float | None:
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value)
    return float(match.group(0)) if match else None


def generate_table_latex(
    table_id: str, metrics: dict[str, Any], prompt: str = ""
) -> str:
    definition = TABLES[table_id]
    available_columns, available_rows = table_grid(table_id, metrics)
    spec = parse_table_prompt(
        table_id, prompt, available_columns, available_rows
    )
    columns = spec["columns"]
    rows = spec["rows"]
    wide = definition["width"].startswith("two-column")
    environment = "table*" if wide else "table"
    alignment = "l" + "c" * (len(columns) - 1)
    best_cells: set[tuple[int, int]] = set()
    if spec["best"] != "none":
        for column_index in range(1, len(columns)):
            numeric_values = [
                (row_index, value)
                for row_index, row in enumerate(rows)
                if (value := numeric_cell(row[column_index])) is not None
            ]
            if numeric_values:
                target = (
                    max(value for _, value in numeric_values)
                    if spec["best"] == "max"
                    else min(value for _, value in numeric_values)
                )
                best_cells.update(
                    (row_index, column_index)
                    for row_index, value in numeric_values
                    if value == target
                )
    lines = [
        f"\\begin{{{environment}}}[{'t' if wide else 'tb'}]",
        "  \\centering",
        f"  \\{spec['size']}",
        f"  \\begin{{tabular}}{{{alignment}}}",
        "    \\toprule",
        "    " + " & ".join(latex_escape_cell(item) for item in columns) + r" \\",
        "    \\midrule",
    ]
    for row_index, row in enumerate(rows):
        cells = []
        for column_index, item in enumerate(row):
            escaped = latex_escape_cell(item)
            if (row_index, column_index) in best_cells:
                escaped = f"\\textbf{{{escaped}}}"
            cells.append(escaped)
        lines.append(
            "    " + " & ".join(cells) + r" \\"
        )
    lines.extend(
        [
            "    \\bottomrule",
            "  \\end{tabular}",
            f"  \\caption{{{latex_escape_cell(spec['caption'])}}}",
            f"  \\label{{{definition['label']}}}",
            f"\\end{{{environment}}}",
        ]
    )
    return "\n".join(lines)


def table_preview_paths(
    table_id: str, output_dir: Path | None = None
) -> dict[str, Path]:
    directory = output_dir or TABLE_PREVIEW_DIR
    slug = table_id.lower()
    return {
        "pdf": directory / f"{slug}.pdf",
        "preview": directory / f"{slug}.png",
    }


def compile_table_preview(
    table_id: str, latex: str, output_dir: Path | None = None
) -> dict[str, Path]:
    """Compile the actual table LaTeX and rasterize that PDF for the browser."""
    for command in ("pdflatex", "pdfcrop", "pdftoppm"):
        if not shutil_which(command):
            raise StudioError(f"无法生成 LaTeX 表格预览：缺少 {command}。")
    destination = output_dir or TABLE_PREVIEW_DIR
    destination.mkdir(parents=True, exist_ok=True)
    paths = table_preview_paths(table_id, destination)
    document = "\n".join(
        [
            r"\documentclass[letterpaper]{article}",
            r"\usepackage[margin=0.35in]{geometry}",
            r"\usepackage{times}",
            r"\usepackage{booktabs}",
            r"\usepackage{caption}",
            r"\usepackage{graphicx}",
            r"\pagestyle{empty}",
            r"\begin{document}",
            latex.strip(),
            r"\end{document}",
            "",
        ]
    )
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"table-{table_id.lower()}-", dir=STATE_DIR
    ) as temporary_name:
        build_dir = Path(temporary_name)
        source = build_dir / "preview.tex"
        source.write_text(document, encoding="utf-8")
        try:
            run_checked(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "preview.tex",
                ],
                cwd=build_dir,
                timeout=120,
            )
            run_checked(
                ["pdfcrop", "--margins", "8", "preview.pdf", "cropped.pdf"],
                cwd=build_dir,
                timeout=120,
            )
            run_checked(
                [
                    "pdftoppm",
                    "-png",
                    "-r",
                    "160",
                    "-singlefile",
                    "cropped.pdf",
                    "preview",
                ],
                cwd=build_dir,
                timeout=120,
            )
        except StudioError as exc:
            raise StudioError("LaTeX 表格预览编译失败。\n" + str(exc)) from exc
        temporary_pdf = build_dir / "cropped.pdf"
        temporary_png = build_dir / "preview.png"
        if not temporary_pdf.exists() or not temporary_png.exists():
            raise StudioError("LaTeX 表格预览工具未产生 PDF/PNG。")
        pdf_target = paths["pdf"].with_suffix(".pdf.tmp")
        png_target = paths["preview"].with_suffix(".png.tmp")
        pdf_target.write_bytes(temporary_pdf.read_bytes())
        png_target.write_bytes(temporary_png.read_bytes())
        os.replace(pdf_target, paths["pdf"])
        os.replace(png_target, paths["preview"])
    return paths


def labeled_float_from_source(
    source: str, kind: str, label: str
) -> tuple[str, int, int] | None:
    """Return one exact labelled figure/table float and its source offsets."""
    if kind not in {"figure", "table"}:
        raise StudioError(f"Unsupported LaTeX float kind: {kind}")
    pattern = re.compile(
        rf"\\begin\{{({kind}\*?)\}}.*?\\end\{{\1\}}",
        flags=re.DOTALL,
    )
    marker = f"\\label{{{label}}}"
    for match in pattern.finditer(source):
        if marker in match.group(0):
            return match.group(0).strip(), match.start(), match.end()
    return None


def latex_command_content(source: str, command: str) -> str:
    """Extract the first balanced ``\\command{...}`` body without flattening LaTeX."""
    marker = f"\\{command}{{"
    start = source.find(marker)
    if start < 0:
        return ""
    cursor = start + len(marker)
    depth = 1
    body_start = cursor
    while cursor < len(source):
        character = source[cursor]
        if character == "{" and (cursor == 0 or source[cursor - 1] != "\\"):
            depth += 1
        elif character == "}" and (cursor == 0 or source[cursor - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return source[body_start:cursor].strip()
        cursor += 1
    return ""


def artifact_anchor_before_offset(
    section: str, source: str, offset: int, state: dict[str, Any]
) -> str | None:
    """Find the last accepted paragraph that precedes a recovered float."""
    candidates: list[tuple[int, str]] = []
    for paragraph in state.get("sections", {}).get(section, {}).get("paragraphs", []):
        text = str(paragraph.get("accepted_text", "")).strip()
        if not text:
            continue
        position = source.find(text)
        if position >= 0 and position + len(text) <= offset:
            candidates.append((position + len(text), str(paragraph.get("id", ""))))
    return max(candidates)[1] if candidates else None


def _without_complete_floats(source: str) -> str:
    """Remove complete figure/table floats while preserving prose around them."""
    for kind in ("figure", "table"):
        source = re.sub(
            rf"\\begin\{{({kind}\*?)\}}.*?\\end\{{\1\}}",
            "\n\n",
            source,
            flags=re.DOTALL,
        )
    return source


def _clean_recovered_paragraph(text: str) -> str:
    """Remove renderer bookkeeping that is not part of editable paragraph prose."""
    text = _without_complete_floats(text)
    text = re.sub(r"(?m)^% PAPER_STUDIO_PARAGRAPH:[^\n]*\n?", "", text)
    text = re.sub(r"(?m)^\\label\{[^{}]+\}\s*$", "", text)
    return text.strip()


def paragraph_texts_from_manuscript(
    section: str, source: str, state: dict[str, Any]
) -> dict[str, str] | None:
    """Recover every planned editable paragraph from a terminal-written section.

    Explicit renderer markers are preferred. Older manuscripts are recovered only
    when their planned headings or ordered prose blocks give a complete one-to-one
    mapping. Returning ``None`` leaves browser state untouched instead of guessing.
    """
    paragraphs = state.get("sections", {}).get(section, {}).get("paragraphs", [])
    if not paragraphs:
        return {}

    marker_pattern = re.compile(r"(?m)^% PAPER_STUDIO_PARAGRAPH:([^\s]+)\s*$")
    markers = list(marker_pattern.finditer(source))
    planned_ids = [str(paragraph["id"]) for paragraph in paragraphs]
    if markers and [match.group(1) for match in markers] == planned_ids:
        recovered: dict[str, str] = {}
        for index, match in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(source)
            text = _clean_recovered_paragraph(source[match.end() : end])
            if not text:
                return None
            recovered[match.group(1)] = text
        return recovered

    headings: list[tuple[str, str, int, int]] = []
    for paragraph in paragraphs:
        paragraph_id = str(paragraph["id"])
        heading = heading_latex(
            paragraph.get("heading"), paragraph.get("heading_style")
        )
        if not heading:
            headings = []
            break
        start = source.find(heading)
        if start < 0:
            return None
        headings.append((paragraph_id, heading, start, start + len(heading)))
    if headings:
        recovered = {}
        generic_heading = re.compile(r"\\(?:section|subsection|paragraph|textbf)\{")
        float_start = re.compile(r"\\begin\{(?:figure|table)\*?\}")
        for index, (paragraph_id, _heading, start, body_start) in enumerate(headings):
            candidates = [len(source)]
            if index + 1 < len(headings):
                candidates.append(headings[index + 1][2])
            next_heading = generic_heading.search(source, body_start)
            if next_heading:
                candidates.append(next_heading.start())
            next_float = float_start.search(source, body_start)
            if next_float:
                candidates.append(next_float.start())
            text = _clean_recovered_paragraph(source[start : min(candidates)])
            if not text:
                return None
            recovered[paragraph_id] = text
        return recovered

    # Abstract, Introduction, Conclusion, and Limitations use ordered prose blocks.
    prose = _without_complete_floats(source)
    prose = re.sub(r"(?m)^\\section\*?\{[^{}]+\}\s*$", "", prose)
    prose = re.sub(r"(?m)^\\label\{[^{}]+\}\s*$", "", prose)
    prose = re.sub(r"(?m)^% PAPER_STUDIO_PARAGRAPH:[^\n]*$", "", prose)
    blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n", prose)
        if block.strip() and not block.lstrip().startswith("%")
    ]
    if len(blocks) != len(paragraphs):
        return None
    return {
        str(paragraph["id"]): block
        for paragraph, block in zip(paragraphs, blocks)  # noqa: B905 - equal lengths checked above
    }


def synchronize_paragraph_editors_from_manuscript(state: dict[str, Any]) -> bool:
    """Make browser paragraph editors reflect the canonical terminal-written LaTeX."""
    changed = False
    for section, section_state in state.get("sections", {}).items():
        metadata = SECTION_MAP.get(section)
        if not metadata:
            continue
        source_path = PAPER / "sections" / metadata["file"]
        if not source_path.is_file():
            continue
        recovered = paragraph_texts_from_manuscript(
            section, read_text(source_path, 500000), state
        )
        if recovered is None:
            continue
        section_changed = False
        for paragraph in section_state.get("paragraphs", []):
            paragraph_id = str(paragraph["id"])
            text = recovered.get(paragraph_id, "")
            if text and str(paragraph.get("accepted_text", "")).strip() != text:
                paragraph["accepted_text"] = text
                paragraph["candidate"] = None
                section_changed = True
        if section_changed:
            section_state["revision"] = int(section_state.get("revision", 0)) + 1
            changed = True
    return changed


def synchronize_artifact_workbenches_from_manuscript(
    state: dict[str, Any], *, build_table_previews: bool = True
) -> bool:
    """Recover editable artifact state from labelled floats in canonical section sources.

    A loose file on disk is never enough. Recovery requires a matching configured
    label in the manuscript source; figures additionally require that the exact
    included PDF exists. This makes terminal full-draft output and the browser one
    shared artifact state without mistaking abandoned files for approved results.
    """
    changed = False
    section_sources: dict[str, tuple[Path, str]] = {}

    def section_source(section: str) -> tuple[Path, str]:
        if section not in section_sources:
            path = PAPER / "sections" / SECTION_MAP[section]["file"]
            section_sources[section] = (path, read_text(path, 500000))
        return section_sources[section]

    for figure_id in FIGURE_ORDER:
        definition = FIGURES[figure_id]
        stored = state["figures"][figure_id]
        recovered: tuple[str, int, int, str, Path] | None = None
        for section in definition.get("source_sections", []):
            source_path, source = section_source(section)
            match = labeled_float_from_source(source, "figure", definition["label"])
            if match:
                recovered = (*match, section, source_path)
                break
        if not recovered:
            continue
        latex, start, _end, section, source_path = recovered
        include = re.search(
            r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", latex
        )
        paths = figure_paths(figure_id)
        if not include or not paths["pdf"].is_file():
            continue
        included = (PAPER / include.group(1)).resolve()
        expected = paths["pdf"].resolve()
        if included != expected and included.with_suffix(".pdf") != expected:
            continue
        recovered_at = int(max(source_path.stat().st_mtime, paths["pdf"].stat().st_mtime))
        updates: dict[str, Any] = {
            "status": "approved",
            "approved_at": int(stored.get("approved_at") or recovered_at),
            "placement_after": artifact_anchor_before_offset(
                section, section_source(section)[1], start, state
            )
            or stored.get("placement_after")
            or (first_artifact_binding(figure_id) or (None, None))[1],
            "caption": latex_command_content(latex, "caption")
            or stored.get("caption")
            or definition["caption"],
            "progress": 100,
            "progress_message": "已从论文源码恢复图片工作台。",
        }
        if "\\begin{figure*}" in latex:
            updates.update(layout_mode="two-column", requested_layout_width="two-column")
        else:
            updates.update(layout_mode="single-column", requested_layout_width="single-column")
        if definition.get("kind") == "data":
            updates["composed_at"] = int(stored.get("composed_at") or recovered_at)
            for panel in stored.get("panels", {}).values():
                if panel.get("status") != "built":
                    panel.update(
                        status="built",
                        progress=100,
                        progress_message="已从论文中的最终数据图恢复。",
                    )
                    changed = True
        for field, value in updates.items():
            if stored.get(field) != value:
                stored[field] = value
                changed = True

    for table_id in TABLE_ORDER:
        definition = TABLES[table_id]
        stored = state["tables"][table_id]
        recovered = None
        for section in definition.get("source_sections", []):
            source_path, source = section_source(section)
            match = labeled_float_from_source(source, "table", definition["label"])
            if match:
                recovered = (*match, section, source_path)
                break
        if not recovered:
            continue
        latex, start, _end, section, source_path = recovered
        latex = validate_table_latex_source(table_id, latex)
        recovered_at = int(source_path.stat().st_mtime)
        updates = {
            "latex": latex,
            "status": "approved",
            "approved_at": int(stored.get("approved_at") or recovered_at),
            "placement_after": artifact_anchor_before_offset(
                section, section_source(section)[1], start, state
            )
            or stored.get("placement_after")
            or (definition.get("related_paragraphs", {}).get(section, []) or [None])[-1],
            "progress": 100,
            "progress_message": "已从论文源码恢复表格工作台。",
        }
        latex_changed = stored.get("latex", "").strip() != latex
        for field, value in updates.items():
            if stored.get(field) != value:
                stored[field] = value
                changed = True
        preview = table_preview_paths(table_id)["preview"]
        if build_table_previews and (latex_changed or not preview.is_file()):
            try:
                compile_table_preview(table_id, latex)
            except StudioError as exc:
                stored["last_message"] = (
                    "表格 LaTeX 已恢复，但浏览器预览生成失败：" + str(exc)
                )
            else:
                stored["last_message"] = "已从论文源码恢复可编辑表格与预览。"
            changed = True
    return changed


def materialize_direct_full_draft_artifacts(state: dict[str, Any]) -> bool:
    """Fill bound figure/table workbenches after unattended prose drafting.

    Direct drafting must end in the same project state as interactive acceptance.
    Only configured deliverable paths are accepted, and every artifact remains gated
    on its bound paragraph being present. Data tables are regenerated from the real
    metrics fixture rather than copied from prose.
    """
    changed = False
    for figure_id in FIGURE_ORDER:
        definition = FIGURES[figure_id]
        stored = state["figures"][figure_id]
        binding = first_artifact_binding(figure_id)
        if not binding:
            continue
        section, paragraph_id = binding
        paragraph, _index = paragraph_by_id(state, section, paragraph_id)
        if not str(paragraph.get("accepted_text", "")).strip():
            continue
        paths = figure_paths(figure_id)
        if not paths["pdf"].is_file():
            continue
        if definition.get("kind") == "mechanism" and not paths["pptx"].is_file():
            continue
        updates = {
            "status": "approved",
            "approved_at": int(paths["pdf"].stat().st_mtime),
            "placement_after": stored.get("placement_after") or paragraph_id,
            "progress": 100,
            "progress_message": "已从 direct full draft 的配置产物恢复图片工作台。",
        }
        if definition.get("kind") == "data":
            updates["composed_at"] = int(paths["pdf"].stat().st_mtime)
            for panel in stored.get("panels", {}).values():
                panel.update(
                    status="built",
                    progress=100,
                    progress_message="已从验证结果图恢复。",
                )
        for field, value in updates.items():
            if stored.get(field) != value:
                stored[field] = value
                changed = True

    metrics = metrics_bundle()
    for table_id in TABLE_ORDER:
        definition = TABLES[table_id]
        stored = state["tables"][table_id]
        binding = first_artifact_binding(table_id)
        if not binding:
            continue
        section, paragraph_id = binding
        paragraph, _index = paragraph_by_id(state, section, paragraph_id)
        if not str(paragraph.get("accepted_text", "")).strip():
            continue
        # Project configuration is the canonical unattended brief. A stale UI
        # draft from an earlier schema must not break terminal full-draft sync.
        prompt = default_table_prompt(table_id)
        latex = validate_table_latex_source(
            table_id, generate_table_latex(table_id, metrics, prompt)
        )
        compile_table_preview(table_id, latex)
        updates = {
            "latex": latex,
            "status": "approved",
            "approved_at": int(time.time()),
            "placement_after": stored.get("placement_after") or paragraph_id,
            "progress": 100,
            "progress_message": "已从验证 metrics 恢复可编辑表格与预览。",
            "last_message": "表格数字由 paper/metrics.json 确定性生成。",
            "generation_prompt": prompt,
        }
        for field, value in updates.items():
            if stored.get(field) != value:
                stored[field] = value
                changed = True

    if not changed:
        return False
    for section, section_state in state["sections"].items():
        for paragraph in section_state.get("paragraphs", []):
            accepted_text = str(paragraph.get("accepted_text", ""))
            if accepted_text:
                paragraph["accepted_text"] = normalize_latex_ready_text(accepted_text)
        source, accepted = render_section_source(
            section, section_state, state["figures"], state["tables"]
        )
        target = PAPER / "sections" / SECTION_MAP[section]["file"]
        temporary = target.with_suffix(".tex.tmp")
        temporary.write_text(source, encoding="utf-8")
        os.replace(temporary, target)
        section_state["accepted_text"] = accepted
    compile_result = compile_paper()
    if not compile_result.ok:
        raise StudioError(
            "Direct full draft 图表物化后 LaTeX 编译失败。\n" + compile_result.message
        )
    state["compile"] = {
        "status": "ok",
        "message": compile_result.message,
        "updated_at": int(time.time()),
    }
    return True


def extract_agent_table_latex(text: str) -> str:
    """Extract one complete table float from a local agent's final response."""
    source = text.strip()
    fenced = re.fullmatch(
        r"```(?:latex|tex)?\s*(.*?)\s*```",
        source,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        source = fenced.group(1).strip()
    match = re.search(
        r"(\\begin\{(table\*?)\}.*?\\end\{\2\})",
        source,
        flags=re.DOTALL,
    )
    if not match:
        raise StudioError("本地 Agent 没有返回完整的 table/table* LaTeX。")
    return match.group(1).strip()


def validate_table_latex_source(table_id: str, latex: str) -> str:
    source = latex.strip()
    definition = TABLES[table_id]
    if not source:
        raise StudioError("表格 LaTeX 不能为空。")
    if not re.search(r"\\begin\{table\*?\}", source):
        raise StudioError("表格 LaTeX 缺少 table/table* 环境。")
    expected_environment = (
        "table*" if str(definition.get("width", "")).startswith("two-column") else "table"
    )
    if not re.search(
        rf"\\begin\{{{re.escape(expected_environment)}\}}.*?"
        rf"\\end\{{{re.escape(expected_environment)}\}}",
        source,
        flags=re.DOTALL,
    ):
        raise StudioError(
            f"表格宽度配置要求使用 {expected_environment} 环境；"
            "请不要把双栏表退化为单栏表或反之。"
        )
    expected_label = f"\\label{{{definition['label']}}}"
    if expected_label not in source:
        raise StudioError(f"表格必须保留固定标签 {expected_label}。")
    if "\\caption{" not in source:
        raise StudioError("表格 LaTeX 缺少 caption。")
    return source


def table_reference_context() -> tuple[str, str]:
    """Return the approved reference-paper extraction and its project-local path."""
    if not PARAGRAPH_PLAN_FILE.exists():
        return "", ""
    try:
        plan = json.loads(PARAGRAPH_PLAN_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", ""
    relative = str(plan.get("reference_file", "")).strip()
    if not relative:
        return "", ""
    candidate = (ROOT / relative).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return "", ""
    if not candidate.is_file():
        return "", ""
    return relative, candidate.read_text(encoding="utf-8", errors="replace")[:60000]


def table_numeric_cells(latex: str) -> tuple[str, ...]:
    """Extract data-cell numbers while ignoring LaTeX layout arguments."""
    tabular = re.search(
        r"\\begin\{tabular\}.*?(.*?)\\end\{tabular\}",
        latex,
        flags=re.DOTALL,
    )
    if not tabular:
        return ()
    values: list[str] = []
    for raw_line in tabular.group(1).splitlines():
        line = raw_line.strip()
        if (
            "&" not in line
            or "\\multicolumn" in line
            or "\\cmidrule" in line
            or any(
                marker in line
                for marker in ("\\toprule", "\\midrule", "\\bottomrule")
            )
        ):
            continue
        cells = line.split("&")[1:]
        for cell in cells:
            match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", cell)
            if match:
                values.append(match.group(0))
    return tuple(values)


def requests_reference_expansion(instruction: str) -> bool:
    lowered = instruction.casefold()
    markers = (
        "pdf",
        "reference",
        "参考",
        "更多数字",
        "不止这么多",
        "别的数字",
        "更多实验",
        "more numbers",
        "additional results",
    )
    return any(marker in lowered for marker in markers)


def local_agent_environment(provider: str = "codex") -> dict[str, str]:
    """Build an Agent environment without exposing unrelated writing secrets."""
    environment = dict(os.environ)
    online_codex_key = environment.get("OPENAI_API_KEY", "") if ONLINE_PROJECT_MODE else ""
    for secret_name in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "LLM_API_KEY"):
        environment.pop(secret_name, None)
    environment["PAPER_STUDIO_AGENT_CHILD"] = "1"
    if ONLINE_PROJECT_MODE and provider == "codex":
        if not online_codex_key:
            raise StudioError("线上 Agent 需要当前写作会话的 OpenAI API Key。")
        environment["CODEX_API_KEY"] = online_codex_key
        codex_home = STATE_DIR / "codex-runtime"
        codex_home.mkdir(parents=True, exist_ok=True)
        environment["CODEX_HOME"] = str(codex_home)
    return environment


def local_agent_auth_args() -> list[str]:
    """Keep an online session key out of every command spawned by Codex."""
    if not ONLINE_PROJECT_MODE:
        return []
    return [
        "--ignore-user-config",
        "--config",
        "shell_environment_policy.ignore_default_excludes=false",
    ]


def codex_thread_id(output: str) -> str | None:
    """Read the persisted Codex thread id from JSONL without trusting prose."""
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "thread.started":
            continue
        candidate = str(
            event.get("thread_id") or event.get("thread", {}).get("id") or ""
        ).strip()
        if re.fullmatch(r"[0-9a-fA-F-]{16,64}", candidate):
            return candidate
    return None


def claude_result(output: str) -> tuple[str, str | None]:
    """Extract the structured answer and resumable session id from Claude JSON."""
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return output.strip(), None
    if not isinstance(payload, dict):
        return output.strip(), None
    result = payload.get("result", "")
    if isinstance(result, list):
        result = "\n".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in result
        )
    session_id = str(payload.get("session_id") or "").strip() or None
    return str(result).strip(), session_id


def require_substantive_table_revision(
    current: str, revised: str, instruction: str
) -> None:
    if re.sub(r"\s+", "", current) == re.sub(r"\s+", "", revised):
        raise StudioError("本地 Agent 返回的表格与当前版本完全相同。")
    if requests_reference_expansion(instruction):
        before = table_numeric_cells(current)
        after = table_numeric_cells(revised)
        if len(after) <= len(before) and set(after).issubset(set(before)):
            raise StudioError(
                "你要求补充参考 PDF 中的更多实验数字，但本地 Agent 没有增加"
                "任何可追溯数值。当前草稿未被覆盖。"
            )


def edit_table_with_local_agent(
    table_id: str,
    latex: str,
    instruction: str,
    *,
    metrics: dict[str, Any] | None = None,
) -> str:
    """Ask the installed Codex CLI—not the Responses API—to revise one table."""
    codex = shutil_which("codex")
    if not codex:
        raise StudioError("未找到本机 codex CLI，无法调用本地 Agent。")
    instruction = instruction.strip()
    if not instruction:
        raise StudioError("请填写希望本地 Agent 如何修改表格。")
    definition = TABLES[table_id]
    columns, rows = table_grid(table_id, metrics or metrics_bundle())
    evidence = json.dumps(
        {"columns": columns, "rows": rows},
        ensure_ascii=False,
        indent=2,
    )
    reference_path, reference_text = table_reference_context()
    reference_block = (
        f"<reference_pdf_extraction path={json.dumps(reference_path)}>\n"
        f"{reference_text}\n</reference_pdf_extraction>"
        if reference_text
        else "<reference_pdf_extraction unavailable=\"true\" />"
    )
    action = "重写当前 LaTeX 表格" if latex.strip() else "从零生成 LaTeX 表格初稿"
    prompt = f"""你是 Paper Studio 的本地表格 agent。根据研究者的自由文本要求，
{action}。只返回一个完整的 table/table* 环境，不要 Markdown fence，不要解释，
也不要修改仓库文件。

硬约束：
1. 只能使用 <traceable_results> 或 <reference_pdf_extraction> 中明确出现的实验
   数值；不得创造、推断或改写任何数值。用户提到“那篇 PDF”或“参考稿”时，
   必须阅读后一个区块并从中恢复她点名的完整结果维度。
2. 必须保留固定标签 \\label{{{definition['label']}}}，并保留 caption。
3. 保持 booktabs 学术表格风格；caption 位于 tabular 之后。
4. 可以按要求修改分组表头、列/行顺序、对齐、字号、加粗、caption 措辞和注释。
5. 当前数据为测试 fixture 时，所有现有 [SYNTHETIC] 标记必须原样保留。
6. 只能使用标准 LaTeX 与 booktabs 已提供的命令。不要使用 \\multirow、\\makecell、
   tabularx、adjustbox 或任何需要新增 package 的命令；分组表头使用 \\multicolumn
   与 \\cmidrule 实现。宽表可使用 graphicx 已提供的
   \\resizebox{{\\textwidth}}{{!}}{{...}}。

<researcher_instruction>
{instruction}
</researcher_instruction>

<traceable_results>
{evidence}
</traceable_results>

{reference_block}

<current_table_latex>
{latex.strip()}
</current_table_latex>
"""
    environment = local_agent_environment()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"agent-table-{table_id.lower()}-", dir=STATE_DIR
    ) as temporary_name:
        output = Path(temporary_name) / "last_message.txt"
        command = [
            codex,
            "exec",
            "--ephemeral",
            *local_agent_auth_args(),
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--cd",
            str(ROOT),
            "--output-last-message",
            str(output),
            "-",
        ]
        try:
            process = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=600,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise StudioError("本地 Agent 修改表格超时。") from exc
        if process.returncode:
            diagnostic = (process.stdout + "\n" + process.stderr).strip()
            raise StudioError(
                "本地 Agent 执行失败。\n"
                + (diagnostic[-2400:] or "codex exec returned a non-zero status.")
            )
        if not output.exists():
            raise StudioError("本地 Agent 未写出最终回复。")
        revised = extract_agent_table_latex(
            output.read_text(encoding="utf-8", errors="replace")
        )
    return validate_table_latex_source(table_id, revised)


def table_agent_worker(
    table_id: str, job_token: str, latex: str, instruction: str
) -> None:
    """Run one local-agent revision and commit it only if the job is still current."""
    try:
        with STATE_LOCK:
            state = load_state()
            stored = state["tables"][table_id]
            if stored.get("job_token") != job_token:
                return
            stored["progress"] = 35
            stored["progress_message"] = "本地 codex agent 正在重写 LaTeX 表格…"
            stored["job_revision"] = int(stored.get("job_revision", 0)) + 1
            save_state(state)
        revised = edit_table_with_local_agent(
            table_id, latex, instruction, metrics=metrics_bundle()
        )
        require_substantive_table_revision(latex, revised, instruction)
        try:
            compile_table_preview(table_id, revised)
        except StudioError as first_error:
            repair_instruction = (
                instruction
                + "\n\n你的上一版 LaTeX 未通过本地编译。请修复下面的真实错误，"
                "保持原修改目标和全部数据不变；只使用标准 LaTeX 与 booktabs，"
                "不要使用需要额外 package 的命令。\n<compile_error>\n"
                + str(first_error)[-1800:]
                + "\n</compile_error>"
            )
            revised = edit_table_with_local_agent(
                table_id,
                revised,
                repair_instruction,
                metrics=metrics_bundle(),
            )
            require_substantive_table_revision(latex, revised, instruction)
            compile_table_preview(table_id, revised)
        with STATE_LOCK:
            state = load_state()
            stored = state["tables"][table_id]
            if stored.get("job_token") != job_token:
                return
            history = stored.setdefault("agent_history", [])
            history.append(
                {
                    "prompt": instruction,
                    "previous_latex": latex,
                    "completed_at": int(time.time()),
                }
            )
            before_cells = len(table_numeric_cells(latex))
            after_cells = len(table_numeric_cells(revised))
            change_summary = (
                f"实验数值单元格由 {before_cells} 个扩展为 {after_cells} 个。"
                if after_cells > before_cells
                else "表格结构或文字已更新，实验数值单元格数量未变。"
            )
            stored.update(
                {
                    "status": "built",
                    "latex": revised,
                    "agent_history": history[-20:],
                    "revision": int(stored.get("revision", 0)) + 1,
                    "progress": 100,
                    "progress_message": "本地 Agent 修改完成，LaTeX 预览已重新编译。",
                    "last_message": (
                        "本地 Agent 已按自由文本 Prompt 修改表格；"
                        f"{change_summary}结果通过固定 label/caption 校验并重新编译。"
                    ),
                    "job_token": None,
                    "job_started_at": None,
                }
            )
            stored["job_revision"] = int(stored.get("job_revision", 0)) + 1
            save_state(state)
    except Exception as exc:
        with STATE_LOCK:
            state = load_state()
            stored = state["tables"][table_id]
            if stored.get("job_token") != job_token:
                return
            stored.update(
                {
                    "status": "error",
                    "progress": 0,
                    "progress_message": "",
                    "last_message": str(exc),
                    "job_token": None,
                    "job_started_at": None,
                }
            )
            stored["job_revision"] = int(stored.get("job_revision", 0)) + 1
            save_state(state)


def table_public_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = metrics_bundle()
    result: list[dict[str, Any]] = []
    for table_id in TABLE_ORDER:
        definition = TABLES[table_id]
        stored = state["tables"][table_id]
        section = definition["source_sections"][0]
        paragraphs = state["sections"][section]["paragraphs"]
        related = definition.get("related_paragraphs", {}).get(section, [])
        placement_after = stored.get("placement_after") or (
            related[-1] if related else None
        )
        ready, gate_reason = table_gate(table_id, state, metrics)
        columns: list[str] = []
        rows: list[list[str]] = []
        if ready:
            available_columns, available_rows = table_grid(table_id, metrics)
            try:
                spec = parse_table_prompt(
                    table_id,
                    stored.get("generation_prompt", ""),
                    available_columns,
                    available_rows,
                )
                columns, rows = spec["columns"], spec["rows"]
            except StudioError:
                columns, rows = available_columns, available_rows
        preview_paths = table_preview_paths(table_id)
        preview_path = preview_paths["preview"]
        result.append(
            {
                "id": table_id,
                **definition,
                "status": stored.get("status", "pending"),
                "revision": int(stored.get("revision", 0)),
                "approved_at": stored.get("approved_at"),
                "last_message": stored.get("last_message", ""),
                "latex": stored.get("latex", ""),
                "generation_prompt": stored.get(
                    "generation_prompt", default_table_prompt(table_id)
                ),
                "prompt_history": stored.get("prompt_history", []),
                "agent_prompt": stored.get("agent_prompt", ""),
                "agent_history": stored.get("agent_history", []),
                "placement_after": placement_after,
                "progress": int(stored.get("progress", 0)),
                "progress_message": stored.get("progress_message", ""),
                "placement_options": [
                    {
                        "id": item["id"],
                        "purpose": item["purpose"],
                        "accepted": bool(item.get("accepted_text")),
                    }
                    for item in paragraphs
                ],
                "ready": ready,
                "gate_reason": gate_reason,
                "preview_columns": columns,
                "preview_rows": rows,
                "preview_url": (
                    f"/table-file/{table_id}/preview"
                    f"?v={int(preview_path.stat().st_mtime)}"
                    if preview_path.exists()
                    else None
                ),
                "preview_type": "image",
                "downloads": (
                    {"pdf": f"/table-file/{table_id}/pdf"}
                    if preview_paths["pdf"].exists()
                    else {}
                ),
            }
        )
    return result


def section_evidence(section: str) -> str:
    metrics = metrics_bundle()
    selected = {key: metrics[key] for key in RESULT_KEYS.get(section, []) if key in metrics}
    return json.dumps(selected, ensure_ascii=False, indent=2)[:26000]


def current_paragraph(section_state: dict[str, Any]) -> dict[str, Any] | None:
    index = int(section_state.get("current_index", 0))
    paragraphs = section_state.get("paragraphs", [])
    if not (0 <= index < len(paragraphs)):
        return None
    return paragraphs[index]


def normalize_latex_ready_text(source: str) -> str:
    """Collapse JSON-style double escaping before known manuscript commands only."""
    commands = (
        r"cite\w*|ref|pageref|label|textbf|textit|emph|subsection|subsubsection|"
        r"paragraph|footnote|url|href"
    )
    normalized = re.sub(rf"\\\\(?=(?:{commands})\b)", lambda _match: "\\", source)
    # LLMs sometimes obey the general "put mathematics in \( ... \)" rule
    # inside an already-open display environment.  TeX rejects those nested
    # inline delimiters with "Bad math environment delimiter".  Removing only
    # the redundant pair preserves the expression and its display/numbering.
    display_patterns = (
        r"\\\[.*?\\\]",
        r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}.*?"
        r"\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}",
    )
    for pattern in display_patterns:
        normalized = re.sub(
            pattern,
            lambda match: match.group(0).replace(r"\(", "").replace(r"\)", ""),
            normalized,
            flags=re.S,
        )
    normalized = re.sub(
        r"(\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\})"
        r"[ \t]*\n(?:[ \t]*\n)+",
        r"\1\n",
        normalized,
    )
    normalized = re.sub(
        r"(?:[ \t]*\n)+([ \t]*\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\})",
        r"\n\1",
        normalized,
    )
    normalized = re.sub(r"(\\\[)[ \t]*\n(?:[ \t]*\n)+", r"\1\n", normalized)
    normalized = re.sub(r"(?:[ \t]*\n)+([ \t]*\\\])", r"\n\1", normalized)
    # Escape TeX specials only in prose. Mathematical environments and
    # identifier-bearing citation/reference commands remain verbatim.
    protected = re.compile(
        r"(?s)(\\\(.*?\\\)|\\\[.*?\\\]|(?<!\\)\$.*?(?<!\\)\$|"
        r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}.*?"
        r"\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}|"
        r"\\(?:cite\w*|ref|pageref|label)\{[^{}]*\})"
    )
    pieces = protected.split(normalized)
    for index in range(0, len(pieces), 2):
        pieces[index] = re.sub(r"(?<!\\)([_%&#])", r"\\\1", pieces[index])
    normalized = "".join(pieces)
    # Models occasionally decorate the reserved placeholder with notes or even
    # provisional cite commands. Canonicalize the whole bracket so the verified
    # citation resolver handles it instead of leaking workflow syntax into prose.
    return re.sub(
        r"\[CITATION\s+NEEDED[^\]]*\]",
        "[CITATION NEEDED]",
        normalized,
        flags=re.IGNORECASE,
    )


# Explicit Greek/letterlike math variable ranges: Unicode's general category
# alone cannot flag these, since it classifies them as ordinary letters
# (Ll/Lu) -- the same category as plain ASCII a-z, which prose legitimately
# contains everywhere. Every other math glyph pdflatex can't render directly
# (operators, relations, arrows, set notation, ...) is category "Sm" ("Symbol,
# math"), which we check directly below instead of maintaining a manually
# curated, perpetually-incomplete character list -- the previous fixed set
# (∈∉≤≥≠≈⋆⋅×÷±μΣδκΦλ−→←⇒∞) missed ⊆ and every other subset/set-operation
# glyph, which is exactly what broke a real batch-writing run.
LATEX_PROSE_UNICODE_MATH_RANGES = (
    (0x0370, 0x03FF),  # Greek and Coptic (math variables: α β γ θ φ ψ ω ...)
    (0x2100, 0x214F),  # Letterlike Symbols (blackboard bold: ℝ ℤ ℕ ℚ ℂ ...)
    (0x2190, 0x21FF),  # Arrows
    (0x27C0, 0x27EF),  # Miscellaneous Mathematical Symbols-A
    (0x2980, 0x29FF),  # Miscellaneous Mathematical Symbols-B
    (0x2A00, 0x2AFF),  # Supplemental Mathematical Operators
)


def _is_latex_unsafe_unicode_math(character: str) -> bool:
    codepoint = ord(character)
    if codepoint < 128:
        # Plain ASCII +, <, =, >, |, ~ are also Unicode category "Sm" but are
        # ordinary, pdflatex-safe characters (e.g. the common "Figure~\ref{}"
        # non-breaking-space convention) -- only non-ASCII math glyphs are a
        # rendering hazard.
        return False
    if unicodedata.category(character) == "Sm":
        return True
    return any(low <= codepoint <= high for low, high in LATEX_PROSE_UNICODE_MATH_RANGES)


def latex_prose_issues(source: str) -> list[str]:
    """Return pdflatex hazards in GPT/manually edited manuscript prose.

    Math bodies and identifier-like arguments of cross-reference commands are masked
    before checking raw TeX specials. This deliberately remains a preflight check,
    not a lossy character-rewriter: GPT gets one chance to preserve the intended
    mathematics while converting it to valid LaTeX.
    """
    masked = source
    for pattern in (
        r"(?s)\\\(.*?\\\)",
        r"(?s)\\\[.*?\\\]",
        r"(?s)(?<!\\)\$.*?(?<!\\)\$",
        r"(?s)\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}.*?"
        r"\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}",
        r"\\(?:cite\w*|ref|pageref|label)\{[^{}]*\}",
    ):
        masked = re.sub(pattern, "", masked)

    issues: list[str] = []
    unicode_math = sorted(
        {character for character in set(masked) if _is_latex_unsafe_unicode_math(character)}
    )
    if unicode_math:
        issues.append("Unicode math glyphs: " + " ".join(unicode_math))
    specials = {
        "_": "raw underscore",
        "%": "raw percent sign",
        "&": "raw ampersand",
        "#": "raw hash sign",
    }
    for character, label in specials.items():
        if re.search(rf"(?<!\\){re.escape(character)}", masked):
            issues.append(label)
    return issues


def online_latex_security_issues(source: str) -> list[str]:
    """Reject TeX primitives that could escape an online session's paper tree."""
    if not ONLINE_PROJECT_MODE:
        return []
    forbidden = re.compile(
        r"\\(?:"
        r"input|include|includegraphics|openin|openout|read|write|immediate|"
        r"usepackage|documentclass|bibliography|addbibresource|newcommand|"
        r"renewcommand|providecommand|def|edef|gdef|xdef|let|catcode|csname|"
        r"special|directlua|write18|lstinputlisting|verbatiminput|"
        r"begin\s*\{\s*filecontents\*?\s*\}"
        r")",
        re.IGNORECASE,
    )
    matches = sorted(set(match.group(0) for match in forbidden.finditer(source)))
    if "^^" in source:
        matches.append("TeX ^^ character encoding")
    return matches


def candidate_for_accept(
    paragraph: dict[str, Any],
    *,
    candidate_id: str,
    submitted_text: str,
    base_text: str,
) -> tuple[dict[str, Any], str]:
    """Reconcile GPT candidates and direct edits of an accepted paragraph."""
    submitted = normalize_latex_ready_text(submitted_text.strip())
    candidate = paragraph.get("candidate")
    if candidate:
        latest = normalize_latex_ready_text(str(candidate.get("text", "")).strip())
        if candidate.get("id") != candidate_id and submitted != latest:
            raise StudioError("候选已被更新；请检查页面自动载入的最新版后再次 Accept。")
        text = submitted or latest
        if not text:
            raise StudioError("候选正文不能为空。")
        candidate["text"] = text
        return candidate, text

    accepted = str(paragraph.get("accepted_text", "")).strip()
    if not accepted:
        raise StudioError("当前段落没有可接受的 candidate；请先生成候选。")
    if base_text.strip() != accepted:
        raise StudioError("已接受版本已在别处更新；页面将载入最新版，请检查后再次修改。")
    if not submitted or submitted == accepted:
        raise StudioError("正文没有尚未写入的修改。")
    candidate = {
        "id": uuid.uuid4().hex,
        "text": submitted,
        "purpose": paragraph.get("purpose", ""),
        "citations_added": [],
        "created_at": int(time.time()),
        "source": "manual_edit",
    }
    paragraph["candidate"] = candidate
    return candidate, submitted


def next_unaccepted_index(
    paragraphs: list[dict[str, Any]], after: int | None = None
) -> int:
    if not paragraphs:
        return 0
    start = 0 if after is None else after + 1
    order = list(range(start, len(paragraphs))) + list(range(0, start))
    for index in order:
        if not paragraphs[index].get("accepted_text"):
            return index
    return len(paragraphs)


def bibliography_keys() -> set[str]:
    bib = read_text(PAPER / "references.bib", 2_000_000)
    return {
        match.group(1).strip()
        for match in re.finditer(r"@\w+\s*\{\s*([^,\s]+)", bib)
    }


def bibliography_catalog() -> str:
    return read_text(PAPER / "references.bib", 2_000_000)


def _bibtex_field(entry: str, field: str) -> str:
    """Extract one prompt-facing BibTeX field without requiring a BibTeX dependency."""
    match = re.search(rf"(?:^|,)\s*{re.escape(field)}\s*=\s*", entry, re.I | re.M)
    if not match:
        return ""
    cursor = match.end()
    if cursor >= len(entry):
        return ""
    opener = entry[cursor]
    if opener in "{\"":
        closer = "}" if opener == "{" else '"'
        cursor += 1
        start = cursor
        depth = 1
        while cursor < len(entry):
            character = entry[cursor]
            if opener == "{" and character == "{":
                depth += 1
            elif character == closer:
                depth -= 1
                if depth == 0:
                    return re.sub(r"\s+", " ", entry[start:cursor]).strip()
            cursor += 1
        return ""
    end = entry.find(",", cursor)
    return entry[cursor : end if end >= 0 else len(entry)].strip()


def bibliography_prompt_catalog(
    relevant_text: str = "", *, required_keys: set[str] | None = None
) -> str:
    """Return a bounded, relevance-ranked citation catalog for one writing turn.

    A paper may have hundreds of BibTeX records.  Sending all of them at every
    section bootstrap wastes input tokens and usually makes citation selection
    worse.  Keep records already cited by the supplied text, rank the remainder
    by lexical overlap, and retain a small fallback set for sparse plans.
    """
    source = bibliography_catalog()
    starts = list(re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", source))
    entries: list[tuple[str, str, str, int]] = []
    fields = ("author", "title", "year", "booktitle", "journal", "doi", "eprint", "url")
    for index, match in enumerate(starts):
        entry = source[match.start() : starts[index + 1].start() if index + 1 < len(starts) else len(source)]
        key = match.group(1).strip()
        values = [f"key={key}"]
        for field in fields:
            value = _bibtex_field(entry, field)
            if value:
                values.append(f"{field}={value[:800]}")
        record = " | ".join(values)
        entries.append((key, record, " ".join(values).lower(), index))

    required = set(required_keys or ()) | citation_keys(relevant_text)
    terms = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", relevant_text)
        if token.lower()
        not in {
            "about", "after", "before", "between", "could", "figure", "from",
            "have", "into", "paper", "paragraph", "results", "section", "should",
            "table", "that", "their", "these", "this", "using", "were", "with",
        }
    }

    def rank(item: tuple[str, str, str, int]) -> tuple[int, int, int]:
        key, _record, searchable, index = item
        overlap = sum(1 for term in terms if term in searchable)
        return (1 if key in required else 0, overlap, -index)

    ranked = sorted(entries, key=rank, reverse=True)
    if terms or required:
        relevant = [item for item in ranked if rank(item)[0] or rank(item)[1]]
        seen = {item[0] for item in relevant}
        for item in entries:
            if len(relevant) >= BIBLIOGRAPHY_PROMPT_MIN_RECORDS:
                break
            if item[0] not in seen:
                relevant.append(item)
                seen.add(item[0])
        ranked = relevant

    records: list[str] = []
    used = 0
    for _key, record, _searchable, _index in ranked:
        if used + len(record) + 1 > BIBLIOGRAPHY_PROMPT_MAX_CHARS:
            records.append("[catalog truncated; missing citations may use verified scholarly search]")
            break
        records.append(record)
        used += len(record) + 1
    return "\n".join(records)


def bibliography_fingerprint() -> str:
    return hashlib.sha256(bibliography_catalog().encode("utf-8")).hexdigest()


def section_source_fingerprint(section: str) -> str:
    section_path = PAPER / "sections" / SECTION_MAP[section]["file"]
    return hashlib.sha256(read_text(section_path, 500_000).encode("utf-8")).hexdigest()


def citation_keys(source: str) -> set[str]:
    found: set[str] = set()
    for match in re.finditer(r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}", source):
        found.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return found


def manuscript_citation_keys() -> set[str]:
    keys: set[str] = set()
    sections = PAPER / "sections"
    if not sections.exists():
        return keys
    for path in sections.glob("*.tex"):
        if path.name == "bibliography.tex":
            continue
        keys.update(citation_keys(read_text(path, 500_000)))
    return keys


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"].strip()
    pieces: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                pieces.append(content.get("text", ""))
    return "\n".join(piece for piece in pieces if piece).strip()


def artifact_label_slug(label: object, *, fallback: str) -> str:
    """Return a safe filename stem for both LaTeX labels and human labels."""
    raw = str(label or "").strip()
    candidate = raw.split(":", 1)[1] if ":" in raw else raw
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._-")
    if not candidate:
        candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", fallback).strip("._-")
    return (candidate or "artifact").replace("-", "_")


def provider_configuration(provider: str) -> dict[str, str]:
    provider = provider.strip().lower()
    configurations = {
        "openai": {
            "id": "openai",
            "label": "OpenAI",
            "environment_variable": "OPENAI_API_KEY",
            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            "protocol": "responses",
        },
        "deepseek": {
            "id": "deepseek",
            "label": "DeepSeek",
            "environment_variable": "DEEPSEEK_API_KEY",
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            "protocol": "chat_completions",
        },
    }
    if provider not in configurations:
        raise StudioError(f"不支持的 LLM API：{provider}")
    return configurations[provider]


def active_llm_provider() -> str:
    try:
        provider = str(load_state().get("llm_provider") or DEFAULT_PROVIDER).strip().lower()
    except Exception:
        provider = DEFAULT_PROVIDER
    return provider if provider in PROVIDER_DEFAULT_MODELS else "openai"


def api_setup_for_provider(provider: str) -> dict[str, Any]:
    config = provider_configuration(provider)
    env_name = config["environment_variable"]
    configured = bool(os.environ.get(env_name))
    commands = [f'export {env_name}="粘贴你的 API key"']
    result = {
        "provider": provider,
        "provider_label": config["label"],
        "required": True,
        "configured": configured,
        "location": API_KEY_SETUP_LOCATION,
        "environment_variable": env_name,
        "setup_command": "\n".join(commands),
        "restart_command": API_KEY_RESTART_COMMAND,
        "security_note": "不要把真实 API key 输入聊天、提交到仓库或保存到浏览器。",
    }
    if ONLINE_PROJECT_MODE:
        result.update(
            {
                "location": "Online Paper Studio 会话内存",
                "setup_command": "",
                "restart_command": "",
                "security_note": "API key 只驻留在线会话进程内存，不写入项目或浏览器存储。",
            }
        )
    return result


def select_llm_provider(state: dict[str, Any], provider: str) -> bool:
    """Apply one supported provider and clear conversation IDs when it changes."""
    provider = provider.strip().lower()
    provider_configuration(provider)
    if provider == state.get("llm_provider"):
        return False
    state["llm_provider"] = provider
    state["model"] = PROVIDER_DEFAULT_MODELS[provider]
    state.setdefault("title_editor", {})["previous_response_id"] = None
    for section_state in state.get("sections", {}).values():
        section_state["previous_response_id"] = None
        section_state["bibliography_fingerprint"] = None
        section_state["conversation_section_fingerprint"] = None
    for figure_state in state.get("figures", {}).values():
        figure_state["previous_response_id"] = None
    return True


def model_options_for_provider(provider: str, current_model: str = "") -> list[dict[str, str]]:
    """Return the supported browser choices, retaining an explicit deployment override."""
    provider_configuration(provider)
    options = [
        {"id": model_id, "label": label}
        for model_id, label in PROVIDER_MODEL_OPTIONS[provider]
    ]
    current_model = current_model.strip()
    if current_model and current_model not in {item["id"] for item in options}:
        options.append({"id": current_model, "label": f"{current_model}（当前配置）"})
    return options


def select_llm_model(state: dict[str, Any], model: str) -> bool:
    """Persist a researcher-entered model name and reset incompatible LLM chains."""
    provider = str(state.get("llm_provider") or DEFAULT_PROVIDER).strip().lower()
    provider_configuration(provider)
    model = model.strip()
    if not model:
        raise StudioError("模型名称不能为空。")
    if len(model) > 128 or any(character.isspace() or ord(character) < 32 for character in model):
        raise StudioError("模型名称必须是不含空格或控制字符的单行标识，且不超过 128 个字符。")
    if model == state.get("model"):
        return False
    state["model"] = model
    state.setdefault("title_editor", {})["previous_response_id"] = None
    for section_state in state.get("sections", {}).values():
        section_state["previous_response_id"] = None
        section_state["bibliography_fingerprint"] = None
        section_state["conversation_section_fingerprint"] = None
    for figure_state in state.get("figures", {}).values():
        figure_state["previous_response_id"] = None
    return True


def _chat_completion_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    previous_id = str(payload.get("previous_response_id") or "")
    with CHAT_HISTORY_LOCK:
        messages = list(CHAT_RESPONSE_HISTORIES.get(previous_id, []))
    instructions = str(payload.get("instructions") or "").strip()
    if instructions:
        messages.append({"role": "system", "content": instructions})
    user_input = payload.get("input", "")
    if not isinstance(user_input, str):
        user_input = json.dumps(user_input, ensure_ascii=False)
    messages.append({"role": "user", "content": user_input})
    request_payload: dict[str, Any] = {
        "model": payload.get("model"),
        "messages": messages,
    }
    text_config = payload.get("text") or {}
    format_config = text_config.get("format") if isinstance(text_config, dict) else None
    if isinstance(format_config, dict) and format_config.get("type") == "json_schema":
        request_payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": format_config.get("name", "paper_studio_response"),
                "strict": bool(format_config.get("strict", True)),
                "schema": format_config.get("schema", {}),
            },
        }
    return request_payload, messages


def reusable_response_id(response_id: str | None) -> str | None:
    """Drop an in-memory chat ID after restart; OpenAI IDs remain server-hosted."""
    if not response_id or active_llm_provider() == "openai":
        return response_id
    with CHAT_HISTORY_LOCK:
        return response_id if response_id in CHAT_RESPONSE_HISTORIES else None


def post_openai(
    payload: dict[str, Any], *, provider: str | None = None, operation: str = "paper_text"
) -> dict[str, Any]:
    """Call the selected text LLM and normalize it to a Responses-style record."""
    provider = (provider or active_llm_provider()).strip().lower()
    config = provider_configuration(provider)
    api_key = os.environ.get(config["environment_variable"])
    if not api_key:
        setup = api_setup_for_provider(provider)
        if ONLINE_PROJECT_MODE:
            raise StudioError(
                f"当前在线会话没有配置 {config['label']} API key；"
                "请返回 Online Paper Studio 入口并创建新会话。"
            )
        raise StudioError(
            f"尚未配置 {config['label']} LLM API。请在启动 Paper Studio 的本机终端输入 "
            f"`{setup['setup_command']}`，停止当前服务后重新运行 "
            f"`{API_KEY_RESTART_COMMAND}`。不要把真实 API key 输入聊天、"
            "提交到仓库或保存到浏览器。"
        )
    if provider != "openai" and payload.get("tools"):
        raise StudioError(
            f"{config['label']} 当前可用于正文、标题、Caption 和设计 Prompt；"
            "自动联网核验 citation 需要切换到 OpenAI 后重试。"
        )
    request_payload = payload
    history: list[dict[str, str]] | None = None
    api_url = config["base_url"] + "/responses"
    if config["protocol"] == "chat_completions":
        request_payload, history = _chat_completion_payload(payload)
        api_url = config["base_url"] + "/chat/completions"
    request = urllib.request.Request(
        api_url,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = json.loads(response.read().decode("utf-8"))
            if config["protocol"] == "responses":
                append_usage(
                    API_USAGE_FILE,
                    usage_record(
                        body,
                        provider=provider,
                        requested_model=str(payload.get("model") or ""),
                        operation=operation,
                    ),
                )
                return body
            choices = body.get("choices") or []
            content = ""
            if choices:
                content = str((choices[0].get("message") or {}).get("content") or "")
            response_id = str(body.get("id") or f"chat-{uuid.uuid4().hex}")
            if history is not None:
                with CHAT_HISTORY_LOCK:
                    CHAT_RESPONSE_HISTORIES[response_id] = history + [
                        {"role": "assistant", "content": content}
                    ]
            normalized = {
                "id": response_id,
                "model": body.get("model") or payload.get("model"),
                "usage": body.get("usage") or {},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": content}]}],
            }
            append_usage(
                API_USAGE_FILE,
                usage_record(
                    normalized,
                    provider=provider,
                    requested_model=str(payload.get("model") or ""),
                    operation=operation,
                ),
            )
            return normalized
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise StudioError(f"{config['label']} API returned HTTP {exc.code}: {detail[:1200]}") from exc
    except urllib.error.URLError as exc:
        raise StudioError(f"{config['label']} API request failed: {exc.reason}") from exc


def needs_citation_resolution(text: str) -> bool:
    return (
        "[CITATION NEEDED]" in text
        or any(
            key.startswith("[") and key.endswith("]")
            for key in citation_keys(text)
        )
        or bool(citation_keys(text) - bibliography_keys())
    )


def drop_unresolved_citation_sentences(text: str) -> str:
    """Remove whole unsupported sentences after search and GPT narrowing both fail."""
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        supported = [
            sentence.strip()
            for sentence in sentences
            if sentence.strip() and "[CITATION NEEDED]" not in sentence
        ]
        if supported:
            paragraphs.append(" ".join(supported))
    return "\n\n".join(paragraphs).strip()


def response_source_urls(response: dict[str, Any]) -> set[str]:
    urls: set[str] = set()

    def visit(value: Any, in_sources: bool = False) -> None:
        if isinstance(value, dict):
            value_type = value.get("type")
            source_context = in_sources or value_type in {
                "web_search_call",
                "url_citation",
            }
            for key, child in value.items():
                if key == "url" and source_context and isinstance(child, str):
                    urls.add(child)
                else:
                    visit(child, source_context or key == "sources")
        elif isinstance(value, list):
            for child in value:
                visit(child, in_sources)

    visit(response)
    return urls


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def append_verified_citations(
    citations: list[dict[str, str]], consulted_urls: set[str]
) -> list[str]:
    known = bibliography_keys()
    normalized_sources = {normalize_url(url) for url in consulted_urls}
    additions: list[tuple[str, str, str]] = []
    for citation in citations:
        key = citation.get("key", "").strip()
        bibtex = citation.get("bibtex", "").strip()
        source_url = citation.get("source_url", "").strip()
        if key in known:
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9:_-]*", key):
            continue
        if normalize_url(source_url) not in normalized_sources:
            continue
        if not re.search(r"@\w+\s*\{\s*" + re.escape(key) + r"\s*,", bibtex):
            continue
        additions.append((key, bibtex, source_url))
        known.add(key)

    if not additions:
        return []
    bib_path = PAPER / "references.bib"
    previous = read_text(bib_path, 2_000_000).rstrip()
    blocks = [
        f"% Added by Paper Studio web citation resolver; source: {source_url}\n{bibtex}"
        for _, bibtex, source_url in additions
    ]
    temporary = bib_path.with_suffix(".bib.tmp")
    temporary.write_text(previous + "\n\n" + "\n\n".join(blocks) + "\n", encoding="utf-8")
    os.replace(temporary, bib_path)
    return [key for key, _, _ in additions]


def sync_verified_bibliography(
    *,
    model: str,
    previous_response_id: str,
    section: str,
    purpose: str,
    paragraph: str,
    added_keys: list[str],
) -> tuple[str, str]:
    """Give the same section conversation the exact bibliography written to disk."""
    payload: dict[str, Any] = {
        "model": model,
        "store": True,
        "previous_response_id": previous_response_id,
        "instructions": """Synchronize one paper paragraph with the verified
bibliography supplied by the server. Return only the LaTeX paragraph. Preserve its
claims, wording, and required heading. Use only citation keys present in
<verified_bibliography>. Replace any rejected or unresolved pseudo-key with
[CITATION NEEDED]; never invent a key or bibliographic record.""",
        "input": f"""<section>{section}</section>
<paragraph_purpose>{purpose}</paragraph_purpose>
<newly_added_keys>{", ".join(added_keys)}</newly_added_keys>
<paragraph>{paragraph}</paragraph>
<verified_bibliography>{bibliography_prompt_catalog(paragraph, required_keys=set(added_keys))}</verified_bibliography>

Return the paragraph with citations synchronized to this exact bibliography.""",
        "text": {"verbosity": "low"},
    }
    if model.startswith("gpt-5.6"):
        payload["reasoning"] = {"effort": "low", "context": "all_turns"}
    response = post_openai(payload)
    revised = extract_output_text(response)
    response_id = response.get("id")
    if not revised or not response_id:
        raise StudioError("Bibliography synchronization returned no paragraph.")
    return response_id, revised


def resolve_citations(
    *,
    model: str,
    previous_response_id: str | None,
    section: str,
    purpose: str,
    paragraph: str,
) -> tuple[str, str, list[str]]:
    existing_bibliography = bibliography_prompt_catalog(paragraph + "\n" + purpose)
    schema = {
        "type": "object",
        "properties": {
            "paragraph": {"type": "string"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "bibtex": {"type": "string"},
                        "source_url": {"type": "string"},
                        "supporting_claim": {"type": "string"},
                    },
                    "required": [
                        "key",
                        "bibtex",
                        "source_url",
                        "supporting_claim",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["paragraph", "citations"],
        "additionalProperties": False,
    }
    payload: dict[str, Any] = {
        "model": model,
        "store": True,
        "instructions": """Resolve missing scholarly citations for one AAAI paper
paragraph. Use web search and prefer primary sources: official proceedings pages,
publisher pages, DOI records, arXiv abstracts, or OpenReview papers. Never use a blog
or search-result page as bibliographic evidence. Return a revised LaTeX paragraph and
only citations whose title, authors, year, and venue you verified. Use \\cite{key}.
Treat bracketed pseudo-keys such as [REFUSAL_DIRECTION_CITATION] as semantic search
requests, never as valid BibTeX keys.
If no reliable source supports a claim, retain [CITATION NEEDED] and return no invented
entry. Do not change the paragraph's scientific claims beyond what citation resolution
requires.""",
        "input": f"""<section>{section}</section>
<paragraph_purpose>{purpose}</paragraph_purpose>
<paragraph>{paragraph}</paragraph>
<existing_bibliography>{existing_bibliography}</existing_bibliography>

Search only for citations that are missing from the existing bibliography. For each
new source, provide a complete BibTeX entry and the exact scholarly URL consulted.""",
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "text": {
            "format": {
                "type": "json_schema",
                "name": "citation_resolution",
                "strict": True,
                "schema": schema,
            }
        },
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    if model.startswith("gpt-5.6"):
        payload["reasoning"] = {"effort": "medium", "context": "all_turns"}
    response = post_openai(payload)
    raw = extract_output_text(response)
    response_id = response.get("id")
    if not raw or not response_id:
        raise StudioError("Citation resolver returned no structured output.")
    try:
        resolved = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StudioError("Citation resolver returned invalid JSON.") from exc
    consulted_urls = response_source_urls(response)
    added = append_verified_citations(resolved["citations"], consulted_urls)
    revised = normalize_latex_ready_text(str(resolved["paragraph"]).strip())
    if added:
        response_id, revised = sync_verified_bibliography(
            model=model,
            previous_response_id=response_id,
            section=section,
            purpose=purpose,
            paragraph=revised,
            added_keys=added,
        )
    unresolved_unknown = citation_keys(revised) - bibliography_keys()
    if unresolved_unknown:
        raise StudioError(
            "Citation resolver used unverified keys: "
            + ", ".join(sorted(unresolved_unknown))
        )
    return response_id, revised, added


def call_openai(
    *,
    section: str,
    model: str,
    previous_response_id: str | None,
    purpose: str,
    required_heading: str | None,
    reference_paragraph: str,
    comment: str,
    current_text: str,
    bibliography_update: str = "",
    artifacts: list[str] | None = None,
    figure_states: dict[str, dict[str, Any]] | None = None,
    required_heading_style: str | None = None,
    include_section_context: bool | None = None,
) -> tuple[str, str, list[str]]:
    previous_response_id = reusable_response_id(previous_response_id)
    section_meta = SECTION_MAP[section]
    section_path = PAPER / "sections" / section_meta["file"]
    if include_section_context is None:
        include_section_context = not previous_response_id
    current_section = read_text(section_path, 24000) if include_section_context else ""
    if "awaiting paragraph-level drafting" in current_section.lower() or (
        section_meta.get("render") == "abstract"
        and "working abstract will be drafted" in current_section.lower()
    ):
        current_section = ""
    stable_context = ""
    evidence = section_evidence(section)
    if not previous_response_id:
        bibliography_context = "\n".join(
            (section_meta["title"], purpose, current_text, current_section, evidence)
        )
        stable_context = f"""<conversation_bootstrap>
<approved_outline>{read_text(PAPER / 'outline.txt', 22000)}</approved_outline>
<working_abstract>{read_text(PAPER / 'working_abstract.txt', 10000)}</working_abstract>
<writing_style>{writing_style_context()}</writing_style>
<bibliography_catalog>{bibliography_prompt_catalog(bibliography_context)}</bibliography_catalog>
<section_evidence>{evidence}</section_evidence>
</conversation_bootstrap>"""
    bound_artifacts = artifact_writing_context(artifacts, figure_states)
    required_heading_command = heading_latex(
        required_heading, required_heading_style
    )

    venue = str(PROJECT_METADATA.get("venue", "academic")).strip() or "academic"
    synthetic_fixture = bool(metrics_bundle().get("synthetic", False))
    measurement_marker_rule = (
        "Every numerical measurement or outcome from the paper-writing fixture must "
        "include the literal marker [SYNTHETIC]."
        if synthetic_fixture
        else "The paper-writing fixture is verified real data; do not add a [SYNTHETIC] marker."
    )
    instructions = f"""You are an expert {venue} paper editor. Return only the proposed
LaTeX-ready manuscript prose for the requested paragraph; do not explain your process.
Write in precise academic English. Preserve the approved paper framing and evidence
boundaries. Never invent a result, citation key, or experimental detail. Numerical
measurements and outcomes must follow this fixture rule: {measurement_marker_rule}
Do not attach a synthetic marker to design counts such as the number of models,
benchmarks, clusters, samples, layers, or queries. Treat the reference paragraph only
as a rhetorical template. Use citation keys already introduced in this section
conversation. If a necessary source is absent, write [CITATION NEEDED]; the server will
resolve it with scholarly web search. When <required_heading_latex> is nonempty, begin
with that exact LaTeX heading and use no other heading. A subsection heading is a block;
a textbf heading is run into its paragraph. When it is empty, do not write a heading.
The output must compile with pdflatex: write percentages as \\%, escape prose \\&, \\#,
and \\_, put every mathematical expression inside \\( ... \\), and use LaTeX commands
instead of Unicode mathematical glyphs."""
    instructions += """ When <researcher_comment> is nonempty, treat its complete text as
the primary editing objective for this turn. Follow it literally and completely wherever
it does not conflict with the non-negotiable evidence-honesty, verified-citation,
configured artifact-reference, required-heading, synthetic-marker, and pdflatex-safety
contracts in these instructions. Do not preserve wording, claims, numbers, structure, or
style from the current candidate merely because they were previously accepted or because
you prefer the earlier version. Do not weaken, reinterpret, or silently omit any
nonconflicting part of the researcher's request."""
    instructions += """ The paragraph may reference only the artifacts listed in
<bound_artifacts>. Include every listed required_reference exactly once, even when the
same artifact appears elsewhere in <current_section_context>. Do not repeat a reference
inside one paragraph, and do not cite any configured figure or table that is not bound
to this paragraph. Never write an internal configured artifact ID in manuscript prose;
use Figure~\\ref{{...}} or Table~\\ref{{...}}."""

    user_input = f"""<section>{section_meta['title']}</section>
<paragraph_purpose>{purpose.strip()}</paragraph_purpose>
<required_heading>{(required_heading or '').strip()}</required_heading>
<required_heading_style>{(required_heading_style or '').strip()}</required_heading_style>
<required_heading_latex>{required_heading_command}</required_heading_latex>
<researcher_comment>{comment.strip()}</researcher_comment>
<current_candidate>{current_text.strip()}</current_candidate>
<current_section_context>{current_section}</current_section_context>
<reference_paragraph>{reference_paragraph.strip()}</reference_paragraph>
<bound_artifacts>{json.dumps(bound_artifacts, ensure_ascii=False, indent=2)}</bound_artifacts>
{f"<bibliography_update>{bibliography_update}</bibliography_update>" if bibliography_update else ""}
{stable_context}

Revise or draft exactly one coherent paragraph for the stated purpose. If required
evidence or a citation key is unavailable, retain an explicit bracketed placeholder
instead of guessing."""

    payload: dict[str, Any] = {
        "model": model,
        "store": True,
        "instructions": instructions,
        "input": user_input,
        "text": {"verbosity": "medium"},
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    if model.startswith("gpt-5.6"):
        payload["reasoning"] = {"effort": "medium", "context": "all_turns"}

    body = post_openai(payload)
    text = normalize_latex_ready_text(extract_output_text(body))
    response_id = body.get("id")
    if not text or not response_id:
        raise StudioError("OpenAI API response did not contain an id and output text.")
    revision_source = normalize_latex_ready_text(current_text).strip()
    revision_requested = bool(comment.strip() and revision_source)
    if revision_requested and re.sub(r"\s+", " ", text).strip() == re.sub(
        r"\s+", " ", revision_source
    ).strip():
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete revised LaTeX-ready paragraph. Your "
                    "previous response was unchanged from the supplied current "
                    "candidate and therefore did not perform the researcher's edit. "
                    "Apply the researcher instruction materially while preserving "
                    "all higher-priority evidence, citation, artifact-reference, "
                    "synthetic-marker, heading, and pdflatex-safety constraints. Do "
                    "not explain the correction and do not return the unchanged text."
                ),
                "input": (
                    f"<researcher_comment>{comment.strip()}</researcher_comment>\n"
                    f"<unchanged_paragraph>{text}</unchanged_paragraph>"
                ),
                "text": {"verbosity": "medium"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = correction.get("id")
        if not text or not response_id:
            raise StudioError("GPT 没有返回执行修改要求后的正文。")
    reference_error = artifact_reference_error(text, bound_artifacts)
    if reference_error:
        allowed = [item["required_reference"] for item in bound_artifacts]
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. "
                    "Preserve its claims, numbers, [SYNTHETIC] markers, heading, and "
                    "citation keys. Include each allowed artifact cross-reference "
                    "exactly once and remove every other configured figure/table "
                    "cross-reference."
                ),
                "input": (
                    f"Reference contract violation: {reference_error}\n"
                    "The complete allowed-and-required reference list for this "
                    f"paragraph is: {json.dumps(allowed, ensure_ascii=False)}. "
                    "Correct the paragraph now. Do not explain the correction.\n\n"
                    f"<previous_paragraph>{text}</previous_paragraph>"
                ),
                "text": {"verbosity": "medium"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = correction.get("id")
        if not text or not response_id:
            raise StudioError("GPT 没有返回补充图表引用后的正文。")
        remaining_reference_error = artifact_reference_error(text, bound_artifacts)
        if remaining_reference_error:
            raise StudioError("GPT 修正后仍然" + remaining_reference_error)
    added: list[str] = []
    if needs_citation_resolution(text):
        response_id, text, added = resolve_citations(
            model=model,
            previous_response_id=response_id,
            section=section_meta["title"],
            purpose=purpose,
            paragraph=text,
        )
    if "[CITATION NEEDED]" in text:
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete revised LaTeX-ready paragraph. The "
                    "citation resolver already searched once and could not verify "
                    "every marked claim. Narrow or remove every unsupported clause so "
                    "no [CITATION NEEDED] marker remains. Use only citation keys in "
                    "the supplied verified bibliography; do not invent a key, source, "
                    "claim, result, or detail. Preserve required headings, synthetic "
                    "markers, and figure/table cross-references."
                ),
                "input": (
                    f"<verified_bibliography>{bibliography_prompt_catalog(text)}</verified_bibliography>\n"
                    f"<paragraph>{text}</paragraph>"
                ),
                "text": {"verbosity": "medium"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = correction.get("id")
        if not text or not response_id:
            raise StudioError("GPT 没有返回去除未验证论断后的正文。")
        if "[CITATION NEEDED]" in text:
            text = drop_unresolved_citation_sentences(text)
            if not text or "[CITATION NEEDED]" in text:
                raise StudioError("未验证论断无法安全移除；未生成候选。")
        unknown_after_narrowing = citation_keys(text) - bibliography_keys()
        if unknown_after_narrowing:
            raise StudioError(
                "GPT 缩窄论断时使用了未验证 citation keys："
                + ", ".join(sorted(unknown_after_narrowing))
            )
    prose_issues = latex_prose_issues(text)
    if prose_issues:
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected paragraph in pdflatex-safe "
                    "LaTeX. Preserve every claim, number, [SYNTHETIC] marker, heading, "
                    "citation key, and required figure/table reference. Escape prose "
                    "percent, ampersand, hash, and underscore characters; place all "
                    "mathematics inside LaTeX math delimiters; replace Unicode math "
                    "glyphs with LaTeX commands. Do not explain the correction."
                ),
                "input": (
                    "The previous paragraph contains these LaTeX hazards: "
                    + "; ".join(prose_issues)
                    + ". Correct it now.\n\n"
                    + f"<previous_paragraph>{text}</previous_paragraph>"
                ),
                "text": {"verbosity": "medium"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = correction.get("id")
        if not text or not response_id:
            raise StudioError("GPT 没有返回 LaTeX 安全修正版正文。")
        remaining_issues = latex_prose_issues(text)
        if remaining_issues:
            raise StudioError(
                "GPT 修正后仍包含 LaTeX 风险字符：" + "; ".join(remaining_issues)
            )
    text = enforce_required_heading(
        text, required_heading, required_heading_style
    )
    final_reference_error = artifact_reference_error(text, bound_artifacts)
    if final_reference_error:
        raise StudioError(final_reference_error)
    security_issues = online_latex_security_issues(text)
    if security_issues:
        raise StudioError(
            "在线写作候选包含被禁用的 LaTeX 文件或执行命令："
            + ", ".join(security_issues)
        )
    if revision_requested and re.sub(r"\s+", " ", text).strip() == re.sub(
        r"\s+", " ", revision_source
    ).strip():
        raise StudioError(
            "GPT 连续两次返回与当前版本相同的正文；本次没有保存伪新候选。"
            "请重试或把修改范围描述得更具体。"
        )
    return response_id, text, added


def manuscript_title_span(source: str) -> tuple[int, int]:
    """Return the content span of the first balanced ``\\title{...}``."""
    match = re.search(r"\\title\s*\{", source)
    if not match:
        raise StudioError("paper/main.tex does not contain a \\title{...} command.")
    content_start = match.end()
    depth = 1
    index = content_start
    while index < len(source):
        character = source[index]
        if character == "\\":
            index += 2
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return content_start, index
        index += 1
    raise StudioError("paper/main.tex contains an unbalanced \\title{...} command.")


def manuscript_title_tex(source: str | None = None) -> str:
    if source is None:
        path = PAPER / "main.tex"
        if not path.exists():
            raise StudioError("paper/main.tex does not exist yet.")
        source = path.read_text(encoding="utf-8")
    start, end = manuscript_title_span(source)
    return source[start:end].strip()


def manuscript_title_display(source: str | None = None) -> str:
    title = manuscript_title_tex(source)
    title = re.sub(r"\\\\(?:\[[^]]*\])?", " ", title)
    title = re.sub(r"\\(?:textit|textbf|emph)\{([^{}]*)\}", r"\1", title)
    return re.sub(r"\s+", " ", title).strip()


def normalize_plain_title(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title).strip().strip('"“”')
    if not normalized:
        raise StudioError("论文标题不能为空。")
    if len(normalized) > 240:
        raise StudioError("论文标题不能超过 240 个字符。")
    if "\\" in normalized or "{" in normalized or "}" in normalized:
        raise StudioError("标题请输入纯文本，不要包含 LaTeX 命令或花括号。")
    return normalized


def latex_escape_title(title: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in title)


def replace_manuscript_title_source(source: str, title: str) -> str:
    start, end = manuscript_title_span(source)
    return source[:start] + latex_escape_title(normalize_plain_title(title)) + source[end:]


def call_openai_for_title(
    *, model: str, prompt: str, current_title: str, previous_response_id: str | None
) -> tuple[str, str]:
    previous_response_id = reusable_response_id(previous_response_id)
    instructions = """You are an expert academic paper-title editor. Return exactly one
plain-text title: no quotation marks, Markdown, commentary, alternatives, or LaTeX commands.
Keep the title concise and venue-appropriate. Preserve the approved paper framing and claim
boundary. Do not introduce a result, causal claim, novelty claim, or empirical conclusion not
supported by the approved outline and working abstract."""
    stable_context = ""
    if not previous_response_id:
        stable_context = f"""<approved_outline>{read_text(PAPER / 'outline.txt', 22000)}</approved_outline>
<working_abstract>{read_text(PAPER / 'working_abstract.txt', 10000)}</working_abstract>"""
    payload: dict[str, Any] = {
        "model": model,
        "store": True,
        "instructions": instructions,
        "input": f"""<current_title>{current_title}</current_title>
<researcher_prompt>{prompt.strip()}</researcher_prompt>
{stable_context}

Propose one replacement title. The result is only an editable candidate and will not be saved
until the researcher explicitly confirms it.""",
        "text": {"verbosity": "low"},
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    if model.startswith("gpt-5.6"):
        payload["reasoning"] = {"effort": "medium", "context": "all_turns"}
    response = post_openai(payload)
    response_id = str(response.get("id", "")).strip()
    candidate = normalize_plain_title(extract_output_text(response))
    if not response_id:
        raise StudioError("Title GPT did not return a response id.")
    return response_id, candidate


def save_manuscript_title(title: str) -> CompileResult:
    """Replace the title, compile, and roll back both source and PDF on failure."""
    main = PAPER / "main.tex"
    if not main.exists():
        raise StudioError("paper/main.tex does not exist yet.")
    previous = main.read_text(encoding="utf-8")
    revised = replace_manuscript_title_source(previous, title)
    temporary = main.with_suffix(".tex.tmp")
    temporary.write_text(revised, encoding="utf-8")
    os.replace(temporary, main)
    result = compile_paper()
    if result.ok:
        return result
    rollback = main.with_suffix(".tex.rollback")
    rollback.write_text(previous, encoding="utf-8")
    os.replace(rollback, main)
    compile_paper()
    raise StudioError("LaTeX failed; title edit rolled back.\n" + result.message)


@dataclass
class CompileResult:
    ok: bool
    message: str


def manuscript_entrypoint_errors(source: str | None = None) -> list[str]:
    """Detect a scaffold that compiles while silently omitting Studio sections."""
    main = PAPER / "main.tex"
    if source is None:
        if not main.exists():
            return ["paper/main.tex does not exist yet."]
        source = main.read_text(encoding="utf-8")
    errors: list[str] = []
    for section, metadata in SECTION_MAP.items():
        filename = str(metadata["file"])
        stem = re.escape(Path(filename).stem)
        include = rf"\\(?:input|include)\s*\{{sections/{stem}(?:\.tex)?\}}"
        if not re.search(include, source):
            errors.append(
                f"main.tex does not include Paper Studio section {section}: "
                f"sections/{filename}"
            )
        if not (PAPER / "sections" / filename).exists():
            errors.append(f"Missing Paper Studio section file: sections/{filename}")
        if metadata.get("render") == "abstract":
            abstract = re.search(
                r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
                source,
                re.DOTALL,
            )
            if not abstract or not re.search(include, abstract.group(1)):
                errors.append(
                    "The abstract section input must be inside the abstract environment."
                )
    return errors


def compile_paper() -> CompileResult:
    main = PAPER / "main.tex"
    if not main.exists():
        return CompileResult(False, "paper/main.tex does not exist yet.")
    entrypoint_errors = manuscript_entrypoint_errors()
    if entrypoint_errors:
        return CompileResult(False, "\n".join(entrypoint_errors))
    if not shutil_which("latexmk"):
        return CompileResult(False, "latexmk is not available on PATH.")
    compile_environment = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
    }
    if ONLINE_PROJECT_MODE:
        # Kpathsea paranoid mode confines TeX reads/writes to the paper tree.
        compile_environment.update(
            {"openin_any": "p", "openout_any": "p", "shell_escape": "0"}
        )
    command = [
        "latexmk",
        "-pdf",
        "-synctex=1",
        "-interaction=nonstopmode",
        "-halt-on-error",
    ]
    if not (PAPER / "main.synctex.gz").exists():
        command.append("-g")
    command.append("main.tex")
    process = subprocess.run(
        command,
        cwd=PAPER,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        env=compile_environment,
    )
    output = (process.stdout + "\n" + process.stderr).strip()
    tail = "\n".join(output.splitlines()[-30:])
    if process.returncode:
        # latexmk reruns pdflatex multiple times; the actual fatal error (a
        # line starting with "!") can appear many passes before the final
        # one, so the last-30-lines tail alone often only shows trailing
        # rerun/summary noise (e.g. a benign "undefined reference" warning)
        # with no indication of what really failed. Surface every real
        # pdflatex error line first, since those are what a researcher (or
        # a retry) actually needs to act on.
        error_lines = [
            line for line in output.splitlines() if line.startswith("!")
        ]
        if error_lines:
            summary = "Error summary:\n" + "\n".join(error_lines)
            return CompileResult(False, summary + "\n\n" + tail)
        return CompileResult(False, tail or "LaTeX compilation failed.")
    return CompileResult(True, tail or "Compilation succeeded.")


def full_draft_targets(state: dict[str, Any]) -> list[tuple[str, str]]:
    """Return pending paragraphs in the project-owned batch writing order."""
    targets: list[tuple[str, str]] = []
    for section in batch_writing_order():
        section_state = state.get("sections", {}).get(section, {})
        for paragraph in section_state.get("paragraphs", []):
            if not str(paragraph.get("accepted_text", "")).strip():
                targets.append((section, str(paragraph.get("id", ""))))
    return targets


def full_draft_running(state: dict[str, Any]) -> bool:
    return (state.get("full_draft_job") or {}).get("status") == "running"


def paragraph_by_id(
    state: dict[str, Any], section: str, paragraph_id: str
) -> tuple[dict[str, Any], int]:
    section_state = state.get("sections", {}).get(section)
    if not isinstance(section_state, dict):
        raise StudioError(f"全文生成找不到 section：{section}")
    for index, paragraph in enumerate(section_state.get("paragraphs", [])):
        if paragraph.get("id") == paragraph_id:
            return paragraph, index
    raise StudioError(f"全文生成找不到段落：{section}/{paragraph_id}")


def accept_full_draft_paragraph(
    state: dict[str, Any], section: str, paragraph: dict[str, Any], text: str
) -> CompileResult:
    """Transactionally accept one batch-generated paragraph into canonical LaTeX."""
    section_state = state["sections"][section]
    text = enforce_required_heading(
        text, paragraph.get("heading"), paragraph.get("heading_style")
    )
    bound_artifacts = artifact_writing_context(
        paragraph.get("artifacts", []), state.get("figures", {})
    )
    reference_error = artifact_reference_error(text, bound_artifacts)
    if reference_error:
        raise StudioError(reference_error)
    if "[CITATION NEEDED]" in text:
        raise StudioError("全文生成仍包含未解决的 [CITATION NEEDED]。")
    unknown = sorted(citation_keys(text) - bibliography_keys())
    if unknown:
        raise StudioError("全文生成使用了未验证 citation keys：" + ", ".join(unknown))
    prose_issues = latex_prose_issues(text)
    if prose_issues:
        raise StudioError("全文生成包含 LaTeX 风险字符：" + "; ".join(prose_issues))
    security_issues = online_latex_security_issues(text)
    if security_issues:
        raise StudioError(
            "全文生成包含在线模式禁用的 LaTeX 命令：" + ", ".join(security_issues)
        )

    target = PAPER / "sections" / SECTION_MAP[section]["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    previous = target.read_text(encoding="utf-8") if existed else ""
    bibliography_path = target.parent / "bibliography.tex"
    previous_bibliography = read_text(bibliography_path, 10000)
    paragraph["accepted_text"] = text
    paragraph["candidate"] = None
    section_source, accepted_section = render_section_source(
        section, section_state, state["figures"], state["tables"]
    )
    temporary = target.with_suffix(".tex.tmp")
    temporary.write_text(section_source, encoding="utf-8")
    os.replace(temporary, target)
    bibliography_text = (
        "\\bibliography{references}\n"
        if manuscript_citation_keys()
        else "% Paper Studio enables the bibliography after the first accepted citation.\n"
    )
    bibliography_temporary = bibliography_path.with_suffix(".tex.tmp")
    bibliography_temporary.write_text(bibliography_text, encoding="utf-8")
    os.replace(bibliography_temporary, bibliography_path)
    compile_result = compile_paper()
    if not compile_result.ok:
        paragraph["accepted_text"] = ""
        if existed:
            rollback = target.with_suffix(".tex.rollback")
            rollback.write_text(previous, encoding="utf-8")
            os.replace(rollback, target)
        elif target.exists():
            target.unlink()
        bibliography_rollback = bibliography_path.with_suffix(".tex.rollback")
        bibliography_rollback.write_text(previous_bibliography, encoding="utf-8")
        os.replace(bibliography_rollback, bibliography_path)
        compile_paper()
        raise StudioError("LaTeX failed; batch paragraph rolled back.\n" + compile_result.message)

    section_state["revision"] = int(section_state.get("revision", 0)) + 1
    section_state["accepted_text"] = accepted_section
    section_state["conversation_section_fingerprint"] = section_source_fingerprint(section)
    next_index = next_unaccepted_index(section_state["paragraphs"])
    section_state["current_index"] = (
        len(section_state["paragraphs"]) - 1
        if next_index >= len(section_state["paragraphs"])
        else next_index
    )
    state["compile"] = {
        "status": "ok",
        "message": compile_result.message,
        "updated_at": int(time.time()),
    }
    return compile_result


def update_full_draft_job(token: str, **updates: Any) -> dict[str, Any] | None:
    with FULL_DRAFT_JOB_LOCK:
        state = load_state()
        job = state.get("full_draft_job") or {}
        if job.get("token") != token or job.get("status") != "running":
            return None
        job.update(updates)
        state["full_draft_job"] = job
        save_state(state)
        return job


def full_draft_worker(token: str, model: str) -> None:
    """Fill every pending paragraph through the normal GPT and LaTeX contracts."""
    try:
        initial = load_state()
        targets = full_draft_targets(initial)
        for ordinal, (section, paragraph_id) in enumerate(targets, start=1):
            with FULL_DRAFT_JOB_LOCK:
                state = load_state()
                job = state.get("full_draft_job") or {}
                if (
                    token in CANCELLED_FULL_DRAFT_JOBS
                    or job.get("token") != token
                    or job.get("status") != "running"
                ):
                    return
                paragraph, paragraph_index = paragraph_by_id(state, section, paragraph_id)
                if str(paragraph.get("accepted_text", "")).strip():
                    job.update(completed=ordinal, progress=int(ordinal * 100 / max(1, len(targets))))
                    state["full_draft_job"] = job
                    save_state(state)
                    continue
                section_state = state["sections"][section]
                previous_response_id = section_state.get("previous_response_id")
                source_fingerprint = section_source_fingerprint(section)
                include_section_context = (
                    not previous_response_id
                    or section_state.get("conversation_section_fingerprint")
                    != source_fingerprint
                )
                current_bib_fingerprint = bibliography_fingerprint()
                bibliography_update = ""
                if (
                    previous_response_id
                    and section_state.get("bibliography_fingerprint")
                    != current_bib_fingerprint
                ):
                    bibliography_update = bibliography_prompt_catalog(
                        paragraph["purpose"] + "\n" + section_evidence(section)
                    )
                figure_states = json.loads(json.dumps(state.get("figures", {})))
                job.update(
                    current_section=section,
                    current_paragraph=paragraph_id,
                    progress_message=f"正在生成 {SECTION_MAP[section]['title']} · {paragraph_id}",
                )
                state["full_draft_job"] = job
                save_state(state)

            response_id, text, citations_added = call_openai(
                section=section,
                model=model,
                previous_response_id=previous_response_id,
                purpose=paragraph["purpose"],
                required_heading=paragraph.get("heading"),
                required_heading_style=paragraph.get("heading_style"),
                reference_paragraph=reference_excerpt(paragraph["reference_lines"]),
                comment="",
                current_text="",
                bibliography_update=bibliography_update,
                artifacts=[str(item) for item in paragraph.get("artifacts", [])],
                figure_states=figure_states,
                include_section_context=include_section_context,
            )

            with FULL_DRAFT_JOB_LOCK:
                state = load_state()
                job = state.get("full_draft_job") or {}
                if (
                    token in CANCELLED_FULL_DRAFT_JOBS
                    or job.get("token") != token
                    or job.get("status") != "running"
                ):
                    return
                paragraph, paragraph_index = paragraph_by_id(state, section, paragraph_id)
                if str(paragraph.get("accepted_text", "")).strip():
                    continue
                section_state = state["sections"][section]
                candidate_id = uuid.uuid4().hex
                paragraph["candidate"] = {
                    "id": candidate_id,
                    "text": text,
                    "purpose": paragraph["purpose"],
                    "citations_added": citations_added,
                    "created_at": int(time.time()),
                }
                paragraph.setdefault("history", []).append(
                    {
                        "candidate_id": candidate_id,
                        "comment": "[DIRECT FULL DRAFT]",
                        "text": text,
                        "citations_added": citations_added,
                        "created_at": int(time.time()),
                    }
                )
                paragraph["history"] = paragraph["history"][-40:]
                section_state["previous_response_id"] = response_id
                section_state["bibliography_fingerprint"] = bibliography_fingerprint()
                section_state["conversation_section_fingerprint"] = source_fingerprint
                section_state["current_index"] = paragraph_index

            # Compilation can take minutes. Do not hold the job lock: cancellation
            # remains responsive and takes effect after this transactional paragraph.
            accept_full_draft_paragraph(state, section, paragraph, text)

            with FULL_DRAFT_JOB_LOCK:
                latest = load_state()
                latest["sections"][section] = state["sections"][section]
                latest["compile"] = state["compile"]
                latest["model"] = model
                job = latest.get("full_draft_job") or {}
                if job.get("status") == "running" and job.get("token") == token:
                    job.update(
                        completed=ordinal,
                        progress=int(ordinal * 100 / max(1, len(targets))),
                        progress_message=f"已写入并编译 {SECTION_MAP[section]['title']} · {paragraph_id}",
                    )
                latest["full_draft_job"] = job
                save_state(latest)
                if job.get("status") != "running" or job.get("token") != token:
                    return

        with FULL_DRAFT_JOB_LOCK:
            state = load_state()
            job = state.get("full_draft_job") or {}
            if job.get("token") == token and job.get("status") == "running":
                materialize_direct_full_draft_artifacts(state)
                synchronize_paragraph_editors_from_manuscript(state)
                synchronize_artifact_workbenches_from_manuscript(
                    state, build_table_previews=True
                )
                job.update(
                    status="completed",
                    token=None,
                    progress=100,
                    completed=job.get("total", len(targets)),
                    progress_message="全文初稿已写入 LaTeX 并完成 PDF 编译，可继续逐段修改。",
                    finished_at=int(time.time()),
                )
                state["full_draft_job"] = job
                save_state(state)
    except Exception as exc:
        with FULL_DRAFT_JOB_LOCK:
            state = load_state()
            job = state.get("full_draft_job") or {}
            if job.get("token") == token and job.get("status") == "running":
                job.update(
                    status="failed",
                    token=None,
                    progress_message=f"全文生成停在当前段落：{exc}",
                    finished_at=int(time.time()),
                )
                state["full_draft_job"] = job
                save_state(state)
    finally:
        with FULL_DRAFT_JOB_LOCK:
            CANCELLED_FULL_DRAFT_JOBS.discard(token)


def start_full_draft_job(model: str) -> tuple[str, dict[str, Any]]:
    """Create the canonical batch-writing job for either HTTP or CLI execution."""
    provider = active_llm_provider()
    setup = api_setup_for_provider(provider)
    if not setup["configured"]:
        raise StudioError(
            f"{setup['provider_label']} API 未配置。请在{API_KEY_SETUP_LOCATION}运行 "
            f"{setup['setup_command']}，然后重新运行 {API_KEY_RESTART_COMMAND}。"
        )
    if not (PAPER / ".outline-approved").exists():
        raise StudioError("Outline 尚未确认，不能直接生成全文。")
    if not (PAPER / "main.tex").exists():
        raise StudioError("paper/main.tex 不存在；请先由 paperwrite 建立论文 scaffold。")
    model = model.strip()
    if not model:
        raise StudioError("模型名称不能为空。")
    with FULL_DRAFT_JOB_LOCK:
        state = load_state()
        if full_draft_running(state):
            raise StudioError("全文初稿任务已经在运行。")
        targets = full_draft_targets(state)
        if not targets:
            raise StudioError("全部段落已经写入 LaTeX，无需再次批量生成。")
        token = uuid.uuid4().hex
        state["model"] = model
        state["full_draft_job"] = {
            "token": token,
            "status": "running",
            "server_instance": SERVER_INSTANCE_TOKEN,
            "started_at": int(time.time()),
            "finished_at": None,
            "total": len(targets),
            "completed": 0,
            "progress": 0,
            "current_section": "",
            "current_paragraph": "",
            "progress_message": "正在准备全文初稿…",
        }
        save_state(state)
    return token, state


def run_direct_full_draft(model: str) -> None:
    """Generate all pending prose synchronously without opening the web UI."""
    token, state = start_full_draft_job(model)
    job = state["full_draft_job"]
    print(f"Direct full draft: 0 / {job['total']} paragraphs")
    full_draft_worker(token, model)
    finished = load_state().get("full_draft_job") or {}
    status = finished.get("status")
    message = str(finished.get("progress_message") or status or "unknown status")
    if status != "completed":
        raise StudioError(message)
    print(
        f"PASS: direct full draft completed "
        f"({finished.get('completed', 0)} / {finished.get('total', 0)} paragraphs)"
    )
    print(f"PDF: {PAPER / 'main.pdf'}")


def shutil_which(command: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / command
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def paper_pdf_metadata() -> dict[str, Any]:
    """Return dimensions needed by the browser's crisp, interactive PDF viewer."""
    pdf = PAPER / "main.pdf"
    metadata: dict[str, Any] = {
        "page_count": 0,
        "page_width_pt": 612.0,
        "page_height_pt": 792.0,
    }
    pdfinfo = shutil_which("pdfinfo")
    if not pdf.exists() or not pdfinfo:
        return metadata
    process = subprocess.run(
        [pdfinfo, str(pdf)], capture_output=True, encoding="utf-8", errors="replace", timeout=30
    )
    if process.returncode:
        return metadata
    pages = re.search(r"^Pages:\s+(\d+)", process.stdout, re.MULTILINE)
    size = re.search(
        r"^Page size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts",
        process.stdout,
        re.MULTILINE,
    )
    if pages:
        metadata["page_count"] = int(pages.group(1))
    if size:
        metadata["page_width_pt"] = float(size.group(1))
        metadata["page_height_pt"] = float(size.group(2))
    return metadata


def paper_page_svg(page: int) -> Path:
    """Render and cache one paper page as vector SVG, preserving PDF sharpness."""
    pdf = PAPER / "main.pdf"
    metadata = paper_pdf_metadata()
    if not pdf.exists() or page < 1 or page > int(metadata["page_count"]):
        raise StudioError("PDF page does not exist.")
    converter = shutil_which("pdftocairo")
    if not converter:
        raise StudioError("交互式 PDF 预览需要本地 pdftocairo。")
    version_dir = PAPER_PAGE_DIR / str(int(pdf.stat().st_mtime_ns))
    target = version_dir / f"page-{page}.svg"
    if target.exists():
        return target
    version_dir.mkdir(parents=True, exist_ok=True)
    temporary = version_dir / f"page-{page}-{uuid.uuid4().hex}.tmp"
    process = subprocess.run(
        [
            converter,
            "-svg",
            "-f",
            str(page),
            "-l",
            str(page),
            str(pdf),
            str(temporary),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if process.returncode or not temporary.exists():
        temporary.unlink(missing_ok=True)
        raise StudioError(
            (process.stderr or process.stdout).strip() or "无法渲染 PDF 页面。"
        )
    temporary.replace(target)
    return target


def parse_synctex_edit(output: str) -> tuple[Path, int]:
    """Parse the first usable source location returned by ``synctex edit``."""
    current_input: str | None = None
    for line in output.splitlines():
        if line.startswith("Input:"):
            current_input = line.split(":", 1)[1].strip()
        elif line.startswith("Line:") and current_input:
            try:
                return Path(current_input), int(line.split(":", 1)[1].strip())
            except ValueError:
                continue
    raise StudioError("这个 PDF 位置没有对应的 LaTeX 源内容。")


def _line_span(source: str, fragment: str) -> tuple[int, int] | None:
    """Find the one-based source line span occupied by an exact generated fragment."""
    start = source.find(fragment.strip())
    if start < 0:
        return None
    end = start + len(fragment.strip())
    return source.count("\n", 0, start) + 1, source.count("\n", 0, end) + 1


def structural_paragraph_spans(
    section: str, source: str, state: dict[str, Any]
) -> list[tuple[int, int, str]]:
    """Recover paragraph line spans when terminal edits changed accepted prose text."""
    paragraphs = state.get("sections", {}).get(section, {}).get("paragraphs", [])
    line_count = max(1, len(source.splitlines()))
    heading_starts: list[tuple[int, int, str]] = []
    for index, paragraph in enumerate(paragraphs):
        heading = heading_latex(
            paragraph.get("heading"), paragraph.get("heading_style")
        )
        if not heading:
            continue
        offset = source.find(heading)
        if offset >= 0:
            heading_starts.append(
                (source.count("\n", 0, offset) + 1, index, str(paragraph["id"]))
            )
    if heading_starts:
        heading_starts.sort()
        return [
            (
                start,
                heading_starts[position + 1][0] - 1
                if position + 1 < len(heading_starts)
                else line_count,
                paragraph_id,
            )
            for position, (start, _index, paragraph_id) in enumerate(heading_starts)
        ]

    # Unheaded sections such as Abstract and Introduction are rendered as ordered
    # blank-line-separated prose blocks. Remove complete floats and the section
    # wrapper, then bind the remaining blocks in plan order.
    masked = source
    for kind in ("figure", "table"):
        pattern = re.compile(
            rf"\\begin\{{({kind}\*?)\}}.*?\\end\{{\1\}}",
            flags=re.DOTALL,
        )
        masked = pattern.sub(lambda match: "\n" * match.group(0).count("\n"), masked)
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"(?:^|\n\s*\n)(\S.*?)(?=\n\s*\n|\Z)", masked, re.DOTALL):
        block = match.group(1).strip()
        if not block or re.fullmatch(r"\\section\{.*\}", block):
            continue
        if re.fullmatch(r"\\label\{.*\}", block):
            continue
        start_offset = masked.find(block, match.start(1), match.end(1))
        spans.append(
            (
                masked.count("\n", 0, start_offset) + 1,
                masked.count("\n", 0, start_offset + len(block)) + 1,
            )
        )
    return [
        (*span, str(paragraph["id"]))
        for span, paragraph in zip(spans, paragraphs)  # noqa: B905 - partial mapping is intentional
    ]


def source_edit_target(source_path: Path, line: int, state: dict[str, Any]) -> dict[str, str]:
    """Map a SyncTeX source line to a Paper Studio paragraph or artifact editor."""
    filename = source_path.name
    section = next(
        (key for key, metadata in SECTION_MAP.items() if metadata["file"] == filename),
        None,
    )
    if not section:
        raise StudioError("该位置属于论文模板，暂时没有对应的段落或图表编辑器。")
    section_path = PAPER / "sections" / filename
    source = section_path.read_text(encoding="utf-8")
    lines = source.splitlines()

    # Float content takes precedence over nearby prose. Captions and whitespace inside
    # a float should return to the figure/table editor, not its anchor paragraph.
    artifacts = [(item, FIGURES[item], "figures") for item in FIGURE_ORDER]
    artifacts += [(item, TABLES[item], "tables") for item in TABLE_ORDER]
    for artifact_id, definition, view in artifacts:
        label = f"\\label{{{definition['label']}}}"
        label_index = next((i for i, value in enumerate(lines) if label in value), None)
        if label_index is None:
            continue
        begin = label_index
        while begin > 0 and "\\begin{" not in lines[begin]:
            begin -= 1
        end = label_index
        while end + 1 < len(lines) and "\\end{" not in lines[end]:
            end += 1
        if begin + 1 <= line <= end + 1:
            return {
                "view": view,
                "section": section,
                "artifact_id": artifact_id,
            }

    paragraph_spans: list[tuple[int, int, str]] = []
    for paragraph in state["sections"][section].get("paragraphs", []):
        text = str(paragraph.get("accepted_text", "")).strip()
        if text and (span := _line_span(source, text)):
            paragraph_spans.append((*span, str(paragraph["id"])))
    containing = [span for span in paragraph_spans if span[0] <= line <= span[1]]
    structural_spans = structural_paragraph_spans(section, source, state)
    structural_containing = [
        span for span in structural_spans if span[0] <= line <= span[1]
    ]
    all_spans = paragraph_spans or structural_spans
    if not all_spans:
        raise StudioError("该 section 还没有可返回编辑的正文段落。")
    chosen = containing[0] if containing else (
        structural_containing[0] if structural_containing else min(
            all_spans,
            key=lambda span: min(abs(line - span[0]), abs(line - span[1])),
        )
    )
    return {"view": "writing", "section": section, "paragraph_id": chosen[2]}


def locate_pdf_source(page: int, x: float, y: float, state: dict[str, Any]) -> dict[str, str]:
    """Reverse-search a rendered PDF point and return its Paper Studio edit target."""
    pdf = PAPER / "main.pdf"
    synctex_file = PAPER / "main.synctex.gz"
    synctex = shutil_which("synctex")
    if not pdf.exists():
        raise StudioError("请先编译 PDF，再使用双击定位。")
    if not synctex_file.exists():
        compile_result = compile_paper()
        if not compile_result.ok or not synctex_file.exists():
            raise StudioError(
                "PDF 双击定位索引缺失，自动重建失败。\n" + compile_result.message
            )
    if not synctex:
        raise StudioError("PDF 双击定位需要本地 SyncTeX。")
    metadata = paper_pdf_metadata()
    if page < 1 or page > int(metadata["page_count"]):
        raise StudioError("PDF page does not exist.")
    width = float(metadata["page_width_pt"])
    height = float(metadata["page_height_pt"])
    if not (0 <= x <= width and 0 <= y <= height):
        raise StudioError("PDF click coordinates are outside the page.")
    process = subprocess.run(
        [synctex, "edit", "-o", f"{page}:{x:.3f}:{y:.3f}:main.pdf"],
        cwd=PAPER,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if process.returncode:
        raise StudioError((process.stderr or process.stdout).strip() or "SyncTeX 定位失败。")
    source_path, line = parse_synctex_edit(process.stdout)
    target = source_edit_target(source_path, line, state)
    target["source_line"] = str(line)
    return target


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 360,
    job_token: str | None = None,
) -> str:
    if job_token is None:
        try:
            process = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise StudioError("画图命令超时。") from exc
        output = (process.stdout + "\n" + process.stderr).strip()
        if process.returncode:
            if "Traceback (most recent call last)" in output:
                last_line = next(
                    (line.strip() for line in reversed(output.splitlines()) if line.strip()),
                    "画图命令执行失败。",
                )
                raise StudioError(f"外部绘图工具执行失败：{last_line[-800:]}")
            raise StudioError(output[-1200:] or "画图命令执行失败。")
        return output

    with FIGURE_PROCESS_LOCK:
        if job_token in CANCELLED_FIGURE_JOBS:
            CANCELLED_FIGURE_JOBS.discard(job_token)
            raise StudioError("本次 GPT Image 调用已停止。")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    )
    with FIGURE_PROCESS_LOCK:
        cancelled = job_token in CANCELLED_FIGURE_JOBS
        if not cancelled:
            RUNNING_FIGURE_PROCESSES[job_token] = process
    if cancelled:
        _terminate_process_group(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_group(process)
        process.communicate()
        raise StudioError("画图命令超时。") from exc
    finally:
        with FIGURE_PROCESS_LOCK:
            if RUNNING_FIGURE_PROCESSES.get(job_token) is process:
                RUNNING_FIGURE_PROCESSES.pop(job_token, None)
            CANCELLED_FIGURE_JOBS.discard(job_token)
    output = (stdout + "\n" + stderr).strip()
    if process.returncode:
        if cancelled:
            raise StudioError("本次 GPT Image 调用已停止。")
        if "Traceback (most recent call last)" in output:
            last_line = next(
                (line.strip() for line in reversed(output.splitlines()) if line.strip()),
                "画图命令执行失败。",
            )
            raise StudioError(f"外部绘图工具执行失败：{last_line[-800:]}")
        raise StudioError(output[-1200:] or "画图命令执行失败。")
    return output


def mechanism_source(
    figure_id: str,
    state: dict[str, Any],
    current_prompt: str = "",
    prompt_instruction: str = "",
) -> str:
    definition = FIGURES[figure_id]
    spec = initial_mechanism_spec(figure_id)
    wide = str(definition.get("width", "")).startswith("two-column")
    format_contract = {
        "placement": "two-column figure*" if wide else "single-column figure",
        "canvas_in": spec["canvas_in"],
        "image_size": spec["image_size"],
        "composition": (
            "page-width ACL-style method schematic with 2–4 aligned regions; use flat modules, "
            "tokens, paths, matrices, or small semantic glyphs only when they encode the method; "
            "keep all critical content in the central horizontal safe band because the "
            "landscape GPT Image draft will be cover-cropped to the paper aspect ratio"
            if wide
            else "compact ACL-style introduction/motivation schematic with 2–3 aligned regions; "
            "use flat tokens, a small transformation cue, and at most one restrained semantic "
            "glyph; pure white background and readable at one-column width"
        ),
        "final_output": (
            "Design a restrained final-quality ACL paper figure whose modules, tokens, paths, "
            "glyphs, and labels can be faithfully reconstructed as editable PowerPoint elements; "
            "avoid both sparse placeholder flowcharts and decorative poster illustration."
        ),
    }
    pieces = [
        f"Figure task: {definition['title']}",
        f"Required content: {definition['description']}",
        "<paper_figure_format>",
        json.dumps(format_contract, ensure_ascii=False, indent=2),
        "</paper_figure_format>",
        "Approved outline:",
        read_text(PAPER / "outline.txt", 24000),
    ]
    for section in definition["source_sections"]:
        accepted = state["sections"][section].get("accepted_text", "").strip()
        if not accepted:
            _, accepted = render_section_source(section, state["sections"][section])
        pieces.extend([f"Accepted {section} prose:", accepted])
    if current_prompt.strip():
        pieces.extend(
            [
                "Current BioRender design prompt:",
                current_prompt.strip(),
                "Researcher instruction for regenerating the design prompt:",
                prompt_instruction.strip(),
                (
                    "Regenerate the complete BioRender prompt. Preserve fidelity to the "
                    "paper, but explicitly apply the researcher's requested changes to "
                    "scope, layout, density, and visual hierarchy."
                ),
            ]
        )
    return "\n\n".join(pieces).strip() + "\n"


def initial_mechanism_spec(figure_id: str) -> dict[str, Any]:
    paths = figure_paths(figure_id)
    definition = FIGURES[figure_id]
    wide = str(definition.get("width", "")).startswith("two-column")
    canvas = definition.get("canvas_in") or (
        [7.0, 3.2]
        if wide
        else [3.32, 3.32]
    )
    return {
        "figure_id": paths["pdf"].stem,
        "canvas_in": canvas,
        "image_size": "1536x1024" if wide else "1024x1024",
        "quality": "high",
        "draw_prompt": "",
        "no_text": True,
        "labels": [],
    }


def mechanism_shape_spec(figure_id: str) -> dict[str, Any]:
    definition = FIGURES[figure_id]
    shape_spec_value = str(definition.get("shape_spec", "")).strip()
    if shape_spec_value:
        shape_spec_path = _project_path(
            ROOT, shape_spec_value, f"figures.{figure_id}.shape_spec"
        )
        if not shape_spec_path.exists():
            raise StudioError(f"机制图形状文件不存在：{shape_spec_value}")
        try:
            configured_spec = json.loads(shape_spec_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StudioError(f"机制图形状文件无效：{shape_spec_value}: {exc}") from exc
        configured_spec["figure_id"] = figure_paths(figure_id)["pdf"].stem
        return validate_mechanism_shape_spec(figure_id, configured_spec)

    paths = figure_paths(figure_id)
    provenance = mechanism_shape_provenance(figure_id)
    if paths["shapes"].exists():
        try:
            cached = json.loads(paths["shapes"].read_text(encoding="utf-8"))
            if cached.get("source_provenance") == provenance:
                return validate_mechanism_shape_spec(figure_id, cached)
        except (OSError, json.JSONDecodeError, StudioError):
            pass
    return create_mechanism_shape_spec_with_local_agent(figure_id, provenance)


MECHANISM_SHAPE_KINDS = {
    "rounded_rect",
    "rect",
    "oval",
    "hexagon",
    "right_arrow",
    "textbox",
    "arrow",
    "line",
}


def mechanism_shape_provenance(figure_id: str) -> dict[str, str]:
    paths = figure_paths(figure_id)
    draft = mechanism_draft_path(figure_id)
    if not draft.exists():
        raise StudioError("请先生成并检查机制图草稿。")
    prompt = read_text(mechanism_spec_path(figure_id), 200000)
    return {
        "draft_sha256": hashlib.sha256(draft.read_bytes()).hexdigest(),
        "prompt_spec_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }


def validate_mechanism_shape_spec(
    figure_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Reject silent placeholder rebuilds before they become final paper figures."""
    if not isinstance(raw, dict) or not isinstance(raw.get("shapes"), list):
        raise StudioError("Editable shape spec 缺少 shapes 数组。")
    shapes = raw["shapes"]
    unknown = {
        item.get("kind") if isinstance(item, dict) else type(item).__name__
        for item in shapes
        if not isinstance(item, dict) or item.get("kind") not in MECHANISM_SHAPE_KINDS
    }
    if unknown:
        raise StudioError("Editable shape spec 含未知元素：" + ", ".join(map(str, unknown)))
    if len(shapes) < 12:
        raise StudioError(
            "机制图重建结果只有少量元素，疑似 placeholder；至少需要 12 个可编辑元素。"
        )
    modules = sum(
        item["kind"] in {"rounded_rect", "rect", "oval", "hexagon", "right_arrow"}
        for item in shapes
    )
    connectors = sum(item["kind"] in {"arrow", "line"} for item in shapes)
    if modules < 4 or connectors < 2:
        raise StudioError("机制图必须包含至少 4 个图形模块和 2 条可编辑连接线。")
    canvas = initial_mechanism_spec(figure_id)["canvas_in"]
    single_column = float(canvas[0]) < 5
    text_shapes = [item for item in shapes if str(item.get("text", "")).strip()]
    max_shapes = 48 if single_column else 90
    max_text_shapes = 14 if single_column else 28
    if len(shapes) > max_shapes or len(text_shapes) > max_text_shapes:
        raise StudioError(
            "机制图信息密度过高："
            f"当前 {len(shapes)} 个元素/{len(text_shapes)} 个文字元素，"
            f"该版面最多 {max_shapes}/{max_text_shapes}。"
        )
    for index, item in enumerate(shapes, start=1):
        coordinates = (
            ("x1", "y1", "x2", "y2")
            if item["kind"] in {"arrow", "line"}
            else ("x", "y", "w", "h")
        )
        for field in coordinates:
            value = item.get(field)
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                raise StudioError(f"机制图第 {index} 个元素的 {field} 必须在 0–1 之间。")
        if item["kind"] not in {"arrow", "line"} and (
            float(item["w"]) <= 0 or float(item["h"]) <= 0
        ):
            raise StudioError(f"机制图第 {index} 个元素的宽高必须大于 0。")
        text = str(item.get("text", "")).strip()
        if text:
            font_size = float(item.get("font_size", 8))
            if font_size < 7:
                raise StudioError(f"机制图第 {index} 个文字元素小于 7pt，不可读。")
            width_pt = float(item["w"]) * float(canvas[0]) * 72
            height_pt = float(item["h"]) * float(canvas[1]) * 72
            chars_per_line = max(1, int(max(width_pt - 4, 1) / (font_size * 0.55)))
            estimated_lines = sum(
                max(1, (len(line) + chars_per_line - 1) // chars_per_line)
                for line in text.splitlines()
            )
            required_height = estimated_lines * font_size * 1.12 + 2
            if required_height > height_pt:
                raise StudioError(
                    f"机制图第 {index} 个文本框容量不足，预计需要 "
                    f"{required_height:.1f}pt 高度，实际仅 {height_pt:.1f}pt。"
                )
    result = dict(raw)
    result["figure_id"] = figure_paths(figure_id)["pdf"].stem
    result["canvas_in"] = canvas
    return result


def normalize_mechanism_text_boxes(
    figure_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Apply renderer-aware minimum font and height without changing figure semantics."""
    normalized = json.loads(json.dumps(raw))
    canvas = initial_mechanism_spec(figure_id)["canvas_in"]
    canvas_width_pt = float(canvas[0]) * 72
    canvas_height_pt = float(canvas[1]) * 72
    for item in normalized.get("shapes", []):
        if not isinstance(item, dict) or item.get("kind") in {"arrow", "line"}:
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        font_size = max(7.0, float(item.get("font_size", 8)))
        item["font_size"] = font_size
        width_pt = float(item.get("w", 0)) * canvas_width_pt
        chars_per_line = max(1, int(max(width_pt - 4, 1) / (font_size * 0.55)))
        estimated_lines = sum(
            max(1, (len(line) + chars_per_line - 1) // chars_per_line)
            for line in text.splitlines()
        )
        required_fraction = (estimated_lines * font_size * 1.12 + 2) / canvas_height_pt
        current_height = float(item.get("h", 0.08))
        if required_fraction <= current_height:
            continue
        center = float(item.get("y", 0)) + current_height / 2
        new_height = min(required_fraction, 1.0)
        item["h"] = new_height
        item["y"] = min(max(0.0, center - new_height / 2), 1.0 - new_height)
    return normalized


def create_mechanism_shape_spec_with_local_agent(
    figure_id: str,
    provenance: dict[str, str],
) -> dict[str, Any]:
    """Reconstruct the GPT Image draft as rich, fully editable native shapes."""
    codex = shutil_which("codex")
    if not codex:
        raise StudioError("未找到本机 codex CLI，无法把 GPT Image 草图重建为可编辑图。")
    paths = figure_paths(figure_id)
    definition = FIGURES[figure_id]
    canvas = initial_mechanism_spec(figure_id)["canvas_in"]
    draw_spec = read_text(paths["spec"], 200000)
    prompt = f"""你是 Paper Studio 的本地科研机制图重建 Agent。必须先使用图像查看工具读取
下面的 GPT Image 草图，再将其构图和论文机制重建成完全可编辑的 PowerPoint 原生形状。
只返回一个 JSON object，不要 Markdown，不要解释，不要修改仓库文件。

GPT Image 草图绝对路径：{paths['draft']}
图编号：{figure_id}
标题：{definition['title']}
机制要求：{definition['description']}
目标画布（英寸）：{json.dumps(canvas)}
本轮 GPT Image Prompt/spec：
{draw_spec}

严格 schema：
{{"canvas_in": {json.dumps(canvas)}, "shapes": [
  {{"kind":"rounded_rect|rect|oval|hexagon|right_arrow", "x":0到1, "y":0到1, "w":0到1, "h":0到1, "fill":"RRGGBB", "line":"RRGGBB", "line_w":1, "text":"简短可编辑标签", "font_size":8, "bold":false, "font_color":"RRGGBB", "align":"left|center|right"}},
  {{"kind":"textbox", "x":0到1, "y":0到1, "w":0到1, "h":0到1, "text":"标签", "font_size":8, "bold":false, "font_color":"RRGGBB", "align":"left|center|right"}},
  {{"kind":"arrow|line", "x1":0到1, "y1":0到1, "x2":0到1, "y2":0到1, "color":"RRGGBB", "weight":1}}
]}}

硬约束：
1. 必须真实查看草图，把草图的视觉层级、主要模块、图标语义和流向作为重建依据；
   不得只把标题和 description 塞进一两个文本框。
2. 至少 12 个独立可编辑元素，其中至少 4 个图形模块、2 条连接线；复杂方法图应更丰富。
   单栏画布最多 48 个元素、14 个含文字元素，并且最多两个核心视觉分组；双栏最多 90/28。
3. 所有元素都必须位于 0–1 画布内，互不遮挡，文字简短且拼写正确；不要照抄草图中的乱码。
   字号不得小于 7pt，每个文本必须完整落在自己的框内；框内标签最多 4 个词，说明句应删除。
   按实际英寸画布给文本框留足高度；宁可扩大框或删字，也不能依赖 overflow 裁切。
4. 使用平面科研插图风格：白底、实色、无阴影、无渐变、无 3D。图形和连接关系承载机制，
   不是大段文字组成的流程图。
5. 忠实于机制要求和 Prompt，不增加结果数字、攻击细节或未经论文支持的主张。
6. 不得加入 raster/background/image 元素；最终每个对象都必须能在 PowerPoint 中单独编辑。
"""
    environment = local_agent_environment()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"agent-mechanism-{figure_id.lower()}-", dir=STATE_DIR
    ) as temporary_name:
        output = Path(temporary_name) / "last_message.txt"
        command = [
            codex,
            "exec",
            "--ephemeral",
            *local_agent_auth_args(),
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--cd",
            str(ROOT),
            "--output-last-message",
            str(output),
            "-",
        ]
        try:
            process = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=MECHANISM_AGENT_TIMEOUT_SECONDS,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise StudioError("本地 Agent 重建可编辑机制图超时。") from exc
        if process.returncode or not output.exists():
            diagnostic = (process.stdout + "\n" + process.stderr).strip()
            raise StudioError(
                "本地 Agent 重建可编辑机制图失败。\n"
                + (diagnostic[-2400:] or "codex exec 未返回 shape spec。")
            )
        source = output.read_text(encoding="utf-8", errors="replace").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", source, re.DOTALL)
    if fenced:
        source = fenced.group(1)
    else:
        start, end = source.find("{"), source.rfind("}")
        if start < 0 or end <= start:
            raise StudioError("本地 Agent 没有返回 shape spec JSON。")
        source = source[start : end + 1]
    try:
        raw = json.loads(source)
    except json.JSONDecodeError as exc:
        raise StudioError(f"本地 Agent 返回的 shape spec 无法解析：{exc}") from exc
    raw = normalize_mechanism_text_boxes(figure_id, raw)
    raw["source_provenance"] = provenance
    return validate_mechanism_shape_spec(figure_id, raw)


def generate_mechanism_prompt(
    figure_id: str,
    state: dict[str, Any],
    prompt_instruction: str = "",
    current_prompt: str = "",
) -> tuple[str, str]:
    setup = api_setup_for_provider(str(state.get("llm_provider") or DEFAULT_PROVIDER))
    if not setup["configured"]:
        raise StudioError(f"{setup['provider_label']} API 未配置，无法生成机制图设计 Prompt。")
    paths = figure_paths(figure_id)
    FIGURE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    source = mechanism_source(
        figure_id,
        state,
        current_prompt=current_prompt,
        prompt_instruction=prompt_instruction,
    )
    paths["source"].write_text(source, encoding="utf-8")
    figure_state = state["figures"][figure_id]
    previous_response_id = reusable_response_id(figure_state.get("previous_response_id"))
    api_input = source
    if previous_response_id:
        format_match = re.search(
            r"<paper_figure_format>.*?</paper_figure_format>", source, re.DOTALL
        )
        format_contract = format_match.group(0) if format_match else ""
        api_input = f"""{format_contract}
<current_biorender_prompt>{current_prompt.strip()}</current_biorender_prompt>
<researcher_revision>{prompt_instruction.strip()}</researcher_revision>

Return the complete revised image-generation prompt."""
    payload: dict[str, Any] = {
        "model": str(state.get("model") or DEFAULT_MODEL),
        "store": True,
        "instructions": FIGURE_PROMPT_INSTRUCTIONS,
        "input": api_input,
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    response = post_openai(payload)
    response_id = str(response.get("id", "")).strip()
    prompt = extract_output_text(response)
    if not response_id:
        raise StudioError("GPT 没有返回可继续的 Figure conversation response id。")
    if not prompt:
        raise StudioError("GPT 没有返回可用的机制图设计 Prompt。")
    return response_id, prompt


def draw_mechanism_draft(
    figure_id: str, prompt: str, *, job_token: str | None = None
) -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise StudioError("OPENAI_API_KEY 未配置，无法调用 GPT Image。")
    prompt = prompt.strip()
    if not prompt:
        raise StudioError("请先生成并确认设计 Prompt。")
    paths = figure_paths(figure_id)
    FIGURE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    spec = initial_mechanism_spec(figure_id)
    if paths["spec"].exists():
        spec.update(json.loads(paths["spec"].read_text(encoding="utf-8")))
    spec["draw_prompt"] = prompt
    paths["spec"].write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    run_checked(
        [
            "python3",
            str(FIGURE_TOOL),
            "draw",
            str(paths["spec"]),
            "--provider",
            "openai",
            "--out",
            str(paths["draft"]),
        ],
        cwd=FIGURE_SOURCE_DIR,
        job_token=job_token,
    )


FIGURE_RUNNING_STATUSES = {
    "prompt_generating",
    "image_generating",
    "agent_generating",
}


def begin_figure_job(figure_state: dict[str, Any], job_token: str) -> None:
    figure_state["job_token"] = job_token
    figure_state["job_started_at"] = int(time.time())
    figure_state["job_revision"] = int(figure_state.get("job_revision", 0)) + 1


def update_figure_job(
    figure_id: str, expected_job_token: str, **updates: Any
) -> dict[str, Any] | None:
    """Update a figure job only if it is still the latest job for that figure."""
    with STATE_LOCK:
        state = load_state()
        figure_state = state["figures"][figure_id]
        if figure_state.get("job_token") != expected_job_token:
            return None
        figure_state.update(updates)
        figure_state["job_revision"] = int(figure_state.get("job_revision", 0)) + 1
        if updates.get("job_token", object()) is None:
            figure_state["job_started_at"] = None
        save_state(state)
        return state


def update_data_panel_job(
    figure_id: str,
    panel_id: str,
    expected_job_token: str,
    **updates: Any,
) -> dict[str, Any] | None:
    """Persist progress on the panel card that owns the local Agent task."""
    with STATE_LOCK:
        state = load_state()
        figure_state = state["figures"][figure_id]
        if figure_state.get("job_token") != expected_job_token:
            return None
        panel_state = figure_state.setdefault("panels", {}).setdefault(panel_id, {})
        panel_state.update(updates)
        figure_state["job_revision"] = int(figure_state.get("job_revision", 0)) + 1
        save_state(state)
        return state


def fail_figure_job(figure_id: str, job_token: str, error: Exception) -> None:
    message = str(error).strip() or "图像任务失败。"
    update_figure_job(
        figure_id,
        job_token,
        status="failed",
        progress=0,
        progress_message="",
        last_message=message,
        job_token=None,
    )


def cancel_figure_job(figure_id: str) -> dict[str, Any]:
    """Invalidate an image job before terminating its process, preserving prior work."""
    process: subprocess.Popen[str] | None = None
    with STATE_LOCK:
        state = load_state()
        figure_state = state["figures"][figure_id]
        job_token = str(figure_state.get("job_token") or "")
        if figure_state.get("status") != "image_generating" or not job_token:
            raise StudioError("当前没有正在运行的 GPT Image 调用。")
        with FIGURE_PROCESS_LOCK:
            CANCELLED_FIGURE_JOBS.add(job_token)
            process = RUNNING_FIGURE_PROCESSES.get(job_token)
        has_previous_draft = figure_paths(figure_id)["draft"].exists()
        figure_state.update(
            {
                "status": "draft" if has_previous_draft else "prompt_ready",
                "progress": 0,
                "progress_message": "",
                "last_message": (
                    "已停止本次 GPT Image 调用；当前 Prompt 和上一版草图均已保留。"
                    if has_previous_draft
                    else "已停止本次 GPT Image 调用；当前 Prompt 已保留。"
                ),
                "job_token": None,
                "job_started_at": None,
            }
        )
        figure_state["job_revision"] = int(figure_state.get("job_revision", 0)) + 1
        save_state(state)
    if process is not None:
        _terminate_process_group(process)
    return state


def generate_prompt_worker(
    figure_id: str,
    job_token: str,
    prompt_instruction: str = "",
    current_prompt: str = "",
) -> None:
    try:
        update_figure_job(
            figure_id,
            job_token,
            progress=20,
            progress_message="正在整理该 section 的正文、outline 与 figure 任务…",
        )
        state = load_state()
        update_figure_job(
            figure_id,
            job_token,
            progress=45,
            progress_message=(
                "GPT 正在按你的指令重写 BioRender 设计 Prompt…"
                if current_prompt
                else "GPT 正在把正文机制转成 BioRender 设计 Prompt…"
            ),
        )
        response_id, prompt = generate_mechanism_prompt(
            figure_id,
            state,
            prompt_instruction=prompt_instruction,
            current_prompt=current_prompt,
        )
        figure_state = load_state()["figures"][figure_id]
        prompt_history = list(figure_state.get("prompt_history", []))
        if current_prompt:
            prompt_history.append(
                {
                    "instruction": prompt_instruction,
                    "previous_prompt": current_prompt,
                    "generated_prompt": prompt,
                    "created_at": int(time.time()),
                }
            )
        update_figure_job(
            figure_id,
            job_token,
            status="prompt_ready",
            previous_response_id=response_id,
            draw_prompt=prompt,
            prompt_instruction=prompt_instruction,
            prompt_history=prompt_history[-20:],
            prompt_approved_at=None,
            progress=100,
            progress_message="设计 Prompt 已生成，等待你的确认。",
            last_message="请检查或修改设计 Prompt；确认后才会调用 GPT Image。",
            job_token=None,
        )
    except Exception as exc:  # pragma: no cover - external process boundary
        fail_figure_job(figure_id, job_token, exc)


def draw_figure_worker(figure_id: str, job_token: str, prompt: str) -> None:
    try:
        update_figure_job(
            figure_id,
            job_token,
            progress=15,
            progress_message="Prompt 已确认，正在准备 GPT Image 请求…",
        )
        update_figure_job(
            figure_id,
            job_token,
            progress=35,
            progress_message="GPT Image 正在绘制并归档草图，这一步通常需要几分钟…",
        )
        draw_mechanism_draft(figure_id, prompt, job_token=job_token)
        update_figure_job(
            figure_id,
            job_token,
            status="agent_generating",
            progress=55,
            progress_message="GPT Image 已完成，正在自动生成论文用 PPTX 与 PDF…",
            last_message="",
        )
        message = build_mechanism_figure(figure_id, job_token=job_token)
        update_figure_job(
            figure_id,
            job_token,
            status="built",
            revision=int(load_state()["figures"][figure_id].get("revision", 0)) + 1,
            approved_at=None,
            progress=100,
            progress_message="GPT Image、PPTX 与 PDF candidate 已全部生成。",
            last_message=(
                message
                + " 请检查最终候选；需要时可修改 Prompt 重画，满意后直接确认插入正文。"
            ),
            job_token=None,
        )
    except Exception as exc:  # pragma: no cover - external process boundary
        fail_figure_job(figure_id, job_token, exc)
    finally:
        with FIGURE_PROCESS_LOCK:
            CANCELLED_FIGURE_JOBS.discard(job_token)


def completed_mechanism_draft_matches_job(
    figure_id: str, figure_state: dict[str, Any]
) -> bool:
    """Recognize a completed image artifact written just before a state-save race/crash."""
    if FIGURES[figure_id]["kind"] != "mechanism":
        return False
    paths = figure_paths(figure_id)
    draft = mechanism_draft_path(figure_id)
    spec_path = mechanism_spec_path(figure_id)
    if not draft.exists() or not spec_path.exists():
        return False
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        iteration_dir = spec_path.parent / "iterations" / str(spec["figure_id"])
        prompt_files = sorted(iteration_dir.glob("round_*.prompt.txt"))
        latest_prompt = prompt_files[-1].read_text(encoding="utf-8").strip()
    except (OSError, KeyError, IndexError, json.JSONDecodeError):
        return False
    approved_at = int(figure_state.get("prompt_approved_at") or 0)
    return (
        latest_prompt == str(figure_state.get("draw_prompt", "")).strip()
        and int(draft.stat().st_mtime) >= approved_at
    )


def completed_mechanism_draft_matches_prompt(figure_id: str, prompt: str) -> bool:
    """Return true only when the current draft came from this exact prompt."""
    spec_path = mechanism_spec_path(figure_id)
    if not mechanism_draft_path(figure_id).exists() or not spec_path.exists():
        return False
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        iteration_dir = spec_path.parent / "iterations" / str(spec["figure_id"])
        prompt_files = sorted(iteration_dir.glob("round_*.prompt.txt"))
        latest_prompt = prompt_files[-1].read_text(encoding="utf-8").strip()
    except (OSError, KeyError, IndexError, json.JSONDecodeError):
        return False
    return latest_prompt == prompt.strip()


def recover_interrupted_figure_jobs() -> None:
    """Recover completed artifacts; fail genuinely interrupted jobs on restart."""
    state = load_state()
    changed = False
    for figure_id, figure_state in state["figures"].items():
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            if (
                figure_state.get("status") == "image_generating"
                and completed_mechanism_draft_matches_job(figure_id, figure_state)
            ):
                figure_state.update(
                    {
                        "status": "draft",
                        "revision": int(figure_state.get("revision", 0)) + 1,
                        "progress": 100,
                        "progress_message": "GPT Image 草图已完成。",
                        "last_message": "草图已生成并归档；已从中断的状态记录中恢复。",
                        "job_token": None,
                        "job_started_at": None,
                    }
                )
            else:
                figure_state.update(
                    {
                        "status": "failed",
                        "progress": 0,
                        "progress_message": "",
                        "last_message": "服务器重启中断了上一次图像任务，请重新发起。",
                        "job_token": None,
                        "job_started_at": None,
                    }
                )
            figure_state["job_revision"] = int(figure_state.get("job_revision", 0)) + 1
            changed = True
    if changed:
        save_state(state)


def recover_interrupted_table_jobs() -> None:
    """Release table controls after a server restart interrupts a local Agent."""
    state = load_state()
    changed = False
    for table_state in state["tables"].values():
        if table_state.get("status") == "agent_editing":
            table_state.update(
                {
                    "status": "error",
                    "progress": 0,
                    "progress_message": "",
                    "last_message": "服务器重启中断了上一次表格任务，请重新发起。",
                    "job_token": None,
                    "job_started_at": None,
                }
            )
            table_state["job_revision"] = int(table_state.get("job_revision", 0)) + 1
            changed = True
    if changed:
        save_state(state)


def validate_editable_shape_deliverables(
    shape_spec: dict[str, Any], pptx: Path, pdf: Path
) -> None:
    """Prove that the final PPT is composed only of editable native objects."""
    if not pptx.exists() or not pdf.exists():
        raise StudioError("全可编辑机制图交付物不完整。")
    try:
        with zipfile.ZipFile(pptx) as package:
            media = [name for name in package.namelist() if name.startswith("ppt/media/")]
            if media:
                raise StudioError("PPTX 仍含位图媒体，未达到每个部件均可编辑的要求。")
            slide_xml = package.read("ppt/slides/slide1.xml").decode(
                "utf-8", errors="replace"
            )
            native_objects = slide_xml.count("<p:sp>") + slide_xml.count("<p:cxnSp>")
            expected = len(shape_spec.get("shapes", []))
            if native_objects < expected or native_objects < 12:
                raise StudioError(
                    "PPTX 原生对象数量不足："
                    f"期望至少 {max(expected, 12)} 个，实际 {native_objects} 个。"
                )
    except zipfile.BadZipFile as exc:
        raise StudioError("机制图 PPTX 文件无效。") from exc
    if pdf.stat().st_size < 1000:
        raise StudioError("全可编辑机制图 PDF 无效。")


def build_mechanism_figure(
    figure_id: str, *, job_token: str | None = None
) -> str:
    paths = figure_paths(figure_id)
    if not mechanism_draft_path(figure_id).exists():
        raise StudioError("请先生成并检查机制图草稿。")
    FIGURE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    if job_token:
        update_figure_job(
            figure_id,
            job_token,
            progress=35,
            progress_message="本地 Agent 正在查看 GPT 草图并重建独立模块、箭头和文字…",
        )
    shape_spec = mechanism_shape_spec(figure_id)
    paths["shapes"].write_text(
        json.dumps(shape_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if job_token:
        update_figure_job(
            figure_id,
            job_token,
            progress=68,
            progress_message="形状重建完成，正在生成全原生对象 PPTX…",
        )
    run_checked(
        [
            "python3",
            str(FIGURE_TOOL),
            "buildshapes",
            str(paths["shapes"]),
            "--out",
            str(paths["pptx"]),
        ],
        cwd=ROOT,
        timeout=60,
    )
    if job_token:
        update_figure_job(
            figure_id,
            job_token,
            progress=86,
            progress_message="PPTX 已生成，正在从同一组原生形状导出论文 PDF…",
        )
    run_checked(
        [
            "python3",
            str(FIGURE_TOOL),
            "pdfshapes",
            str(paths["shapes"]),
            "--out",
            str(paths["pdf"]),
        ],
        cwd=ROOT,
        timeout=60,
    )
    validate_editable_shape_deliverables(shape_spec, paths["pptx"], paths["pdf"])
    return (
        f"已按 GPT 草图重建 {len(shape_spec['shapes'])} 个独立 PowerPoint 原生对象；"
        "PPTX 不含背景位图，每个模块、箭头和文字都可单独编辑。"
    )


def build_mechanism_figure_worker(
    figure_id: str, job_token: str
) -> None:
    """Build in the background because visual reconstruction can take several minutes."""
    try:
        update_figure_job(
            figure_id,
            job_token,
            progress=25,
            progress_message="正在准备 GPT 草图与论文机制信息，随后重建全可编辑对象…",
        )
        message = build_mechanism_figure(figure_id, job_token=job_token)
        update_figure_job(
            figure_id,
            job_token,
            status="built",
            revision=int(load_state()["figures"][figure_id].get("revision", 0)) + 1,
            approved_at=None,
            progress=100,
            progress_message="全可编辑 PPTX 与同构 PDF candidate 已生成。",
            last_message=message,
            job_token=None,
        )
    except Exception as exc:  # pragma: no cover - external agent/process boundary
        fail_figure_job(figure_id, job_token, exc)


def extract_agent_python_source(raw: str) -> str:
    """Extract one complete Python program from a local Agent response."""
    source = raw.strip()
    fenced = re.search(r"```(?:python)?\s*(.*?)```", source, flags=re.DOTALL | re.I)
    if fenced:
        source = fenced.group(1).strip()
    if not source:
        raise StudioError("本地 Agent 没有返回绘图代码。")
    try:
        compile(source, "<local-agent-data-figure>", "exec")
    except SyntaxError as exc:
        raise StudioError(f"本地 Agent 返回的绘图代码无法解析：{exc}") from exc
    required_fragments = ("matplotlib", "--metrics", "--pdf", "--png")
    missing = [item for item in required_fragments if item not in source]
    if missing:
        raise StudioError(
            "本地 Agent 返回的绘图代码缺少必要接口：" + ", ".join(missing)
        )
    return source + ("\n" if not source.endswith("\n") else "")


def data_figure_python() -> str:
    """Select a local interpreter that can actually import the plotting stack."""
    candidates = [
        os.environ.get("PAPER_STUDIO_PLOT_PYTHON", "").strip(),
        shutil_which("python") or "",
        shutil_which("python3") or "",
    ]
    checked: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in checked:
            continue
        checked.add(candidate)
        probe = subprocess.run(
            [candidate, "-c", "import matplotlib, numpy"],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return candidate
    raise StudioError(
        "找不到同时安装 matplotlib 与 numpy 的本地 Python。"
        "请设置 PAPER_STUDIO_PLOT_PYTHON。"
    )


def create_data_figure_code_with_local_agent(
    figure_id: str,
    *,
    panel_id: str | None = None,
    current_source: str = "",
    instruction: str = "",
) -> str:
    """Ask the installed Codex CLI to author a traceable result-figure program."""
    codex = shutil_which("codex")
    if not codex:
        raise StudioError("未找到本机 codex CLI，无法生成实验结果图。")
    definition = FIGURES[figure_id]
    panel_definition = next(
        (
            item
            for item in definition.get("panels", [])
            if item["id"] == (panel_id or definition.get("panels", [{}])[0].get("id"))
        ),
        None,
    )
    if not panel_definition:
        raise StudioError("该数据图没有可生成的独立子图定义。")
    panel_id = panel_definition["id"]
    metrics = metrics_bundle()
    evidence = {
        key: result_path_value(metrics, key)
        for key in panel_definition.get("result_keys", definition.get("result_keys", []))
    }
    presentation_goal = panel_definition.get("goal", definition["description"])
    revision_block = (
        f"""
<researcher_or_qc_instruction>
{instruction.strip()}
</researcher_or_qc_instruction>

<current_agent_source>
{current_source.strip()}
</current_agent_source>
"""
        if current_source.strip()
        else ""
    )
    prompt = f"""你是 Paper Studio 的本地科研绘图 agent。请为下面的论文实验结果图
编写一个独立、可重复运行的 Python 程序。只返回完整 Python 源码，不要解释，
不要 Markdown fence，也不要修改仓库文件。

图编号：{figure_id}({panel_id})
论文图：{definition['title']}
子图标题：{panel_definition['title']}
用途：{presentation_goal}
版面：独立原子子图；此阶段不要添加 (a)/(b) 角标，也不要和其他子图拼接

硬约束：
1. --metrics 指向一个顶层含 traceable_results 的 JSON；该对象按下方
   <traceable_results> 所示的 dotted result key 映射到已有结果。只能绘制其中已有的数值；
   不得创造、插值或推断实验结果。
2. 命令行必须接受 --metrics、--pdf、--png 三个参数，并把同一张图分别保存为
   矢量 PDF 和网页 PNG。使用 matplotlib 的 Agg backend。
3. 这是一个独立子图，宽 3.32 英寸，排版清晰、论文风格、白底；小字号仍需可读。
4. 内容目标：{presentation_goal}
5. 如果 JSON 缺少必需字段，应抛出清楚错误，绝不能用默认数字顶替。
6. 仅使用 Python 标准库、numpy 和 matplotlib。程序执行时不得联网、不得调用模型。
7. 若数据带 synthetic 标记，在图内加入醒目的 “SYNTHETIC FIXTURE” 标记。
8. 所有标题、图例、水印、刻度、标签和注释必须落在画布内且互不遮挡；单栏预览中
   不得出现截断。保存前使用 tight/constrained layout，并为水印单独预留边距。
9. 不要在底部放长段叙述；把 finding 压缩为图内可读的短语，或不显示。
10. 只使用 matplotlib 官方支持的 Artist/Text 参数；不要把 CSS/PPT 属性（例如
    tracking、letter-spacing）传给 matplotlib。

<traceable_results>
{json.dumps(evidence, ensure_ascii=False, indent=2)}
</traceable_results>
{revision_block}
"""
    environment = local_agent_environment()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"agent-figure-{figure_id.lower()}-", dir=STATE_DIR
    ) as temporary_name:
        output = Path(temporary_name) / "last_message.txt"
        command = [
            codex,
            "exec",
            "--ephemeral",
            *local_agent_auth_args(),
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--cd",
            str(ROOT),
            "--output-last-message",
            str(output),
            "-",
        ]
        try:
            process = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=600,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise StudioError("本地 Agent 生成实验结果图代码超时。") from exc
        if process.returncode:
            diagnostic = (process.stdout + "\n" + process.stderr).strip()
            raise StudioError(
                "本地 Agent 生成实验结果图失败。\n"
                + (diagnostic[-2400:] or "codex exec returned a non-zero status.")
            )
        if not output.exists():
            raise StudioError("本地 Agent 未写出绘图代码。")
        return extract_agent_python_source(
            output.read_text(encoding="utf-8", errors="replace")
        )


def generate_data_figure_with_local_agent(
    figure_id: str, panel_id: str | None = None, instruction: str = ""
) -> str:
    """Generate exactly one data panel and archive its own source/PDF/PNG."""
    definition = FIGURES[figure_id]
    panel_id = panel_id or definition.get("panels", [{}])[0].get("id")
    if not panel_id:
        raise StudioError("该数据图没有独立子图。")
    paths = data_panel_paths(figure_id, panel_id)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FIGURE_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    paths["pdf"].parent.mkdir(parents=True, exist_ok=True)
    current_source = read_text(paths["source"], 50000)
    source = create_data_figure_code_with_local_agent(
        figure_id,
        panel_id=panel_id,
        current_source=current_source,
        instruction=instruction,
    )
    temporary_source = paths["source"].with_suffix(".py.tmp")
    temporary_source.write_text(source, encoding="utf-8")
    os.replace(temporary_source, paths["source"])
    result_keys = [
        str(key)
        for key in next(
            item for item in definition.get("panels", []) if item["id"] == panel_id
        ).get("result_keys", definition.get("result_keys", []))
    ]
    payload = traceable_result_payload(result_keys)
    with tempfile.TemporaryDirectory(prefix=f"paper-studio-{figure_id.lower()}-{panel_id}-") as temporary_name:
        traceable_metrics = Path(temporary_name) / "traceable_results.json"
        traceable_metrics.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_checked(
            [
                data_figure_python(),
                str(paths["source"]),
                "--metrics",
                str(traceable_metrics),
                "--pdf",
                str(paths["pdf"]),
                "--png",
                str(paths["preview"]),
            ],
            cwd=ROOT,
        )
    if not paths["pdf"].exists() or not paths["preview"].exists():
        raise StudioError("本地 Agent 绘图程序未同时生成 PDF 和 PNG。")
    return (
        f"{figure_id}({panel_id}) 已单独生成 PDF candidate。"
    )


def default_data_figure_layout_prompt(figure_id: str) -> str:
    panel_ids = [item["id"] for item in FIGURES[figure_id].get("panels", [])]
    if len(panel_ids) == 1:
        return (
            f"将子图 {panel_ids[0]} 放入单栏，裁掉四周空白，不添加角标；"
            "输出可编辑 PPTX 与同布局矢量 PDF。"
        )
    labels = "/".join(f"({panel_id})" for panel_id in panel_ids)
    return (
        f"按 {', '.join(panel_ids)} 的顺序横向放入单栏，裁掉四周空白，"
        f"子图之间不留间距；左上角依次添加 {labels}，角标字体 8 pt；"
        "输出可编辑 PPTX 与同布局矢量 PDF。"
    )


def generate_data_figure_agent_worker(
    figure_id: str, panel_id: str, job_token: str, instruction: str = ""
) -> None:
    try:
        update_figure_job(
            figure_id,
            job_token,
            progress=20,
            progress_message="正在启动本地 Codex agent 并整理可追溯实验结果…",
        )
        update_data_panel_job(
            figure_id,
            panel_id,
            job_token,
            progress=20,
            progress_message="正在整理这张子图的可追溯实验结果…",
        )
        update_figure_job(
            figure_id,
            job_token,
            progress=45,
            progress_message="本地 Agent 正在生成实验结果 PDF candidate…",
        )
        update_data_panel_job(
            figure_id,
            panel_id,
            job_token,
            progress=45,
            progress_message="本地 Agent 正在生成这张子图的 PDF candidate…",
        )
        message = generate_data_figure_with_local_agent(
            figure_id, panel_id, instruction
        )
        stored = load_state()["figures"][figure_id]
        panel_state = stored.get("panels", {}).get(panel_id, {})
        panels = dict(stored.get("panels", {}))
        panels[panel_id] = {
            **panel_state,
            "status": "built",
            "revision": int(panel_state.get("revision", 0)) + 1,
            "agent_prompt": instruction,
            "last_message": message,
            "progress": 100,
            "progress_message": "PDF candidate 已生成。",
        }
        all_panels_built = all(item.get("status") == "built" for item in panels.values())
        revision = int(load_state()["figures"][figure_id].get("revision", 0)) + 1
        if len(panels) == 1:
            requested_width = str(
                stored.get("requested_layout_width") or "single-column"
            )
            layout_prompt = default_data_figure_layout_prompt(figure_id)
            layout = validate_data_figure_layout(
                {
                    "orientation": "horizontal",
                    "width": requested_width,
                    "panel_order": [panel_id],
                    "gap_pt": 0,
                    "crop_margins_pt": 0,
                    "labels": [],
                },
                [panel_id],
            )
            update_figure_job(
                figure_id,
                job_token,
                status="agent_generating",
                progress=85,
                progress_message="正在生成无角标的最终 PPTX 与矢量 PDF…",
                panels=panels,
            )
            try:
                composition_message = compose_data_figure(
                    figure_id, layout_prompt, layout
                )
            except Exception as composition_error:
                update_figure_job(
                    figure_id,
                    job_token,
                    status="panels_ready",
                    revision=revision,
                    approved_at=None,
                    progress=100,
                    progress_message="单图 PDF 已生成；最终文件封装失败。",
                    last_message=f"{message}\n最终文件封装失败：{composition_error}",
                    panels=panels,
                    composed_at=None,
                    job_token=None,
                )
                return
            update_figure_job(
                figure_id,
                job_token,
                status="built",
                revision=revision,
                approved_at=None,
                progress=100,
                progress_message="最终单图 PDF candidate 已生成。",
                last_message=f"{message}\n{composition_message}",
                panels=panels,
                layout_prompt="",
                layout_prompt_is_default=True,
                layout_plan=layout,
                layout_width=layout["width"],
                composed_at=int(time.time()),
                job_token=None,
            )
            return
        update_figure_job(
            figure_id,
            job_token,
            status="panels_ready" if all_panels_built else "panel_ready",
            revision=revision,
            approved_at=None,
            progress=100,
            progress_message=(
                "全部独立子图已生成；请检查后手动点击“合成图”。"
                if all_panels_built
                else f"本地 Agent 已生成独立子图 {figure_id}({panel_id})。"
            ),
            last_message=message,
            panels=panels,
            composed_at=None,
            job_token=None,
        )
    except Exception as exc:  # pragma: no cover - subprocess boundary
        stored = load_state()["figures"][figure_id]
        panels = dict(stored.get("panels", {}))
        panel_state = dict(panels.get(panel_id, {}))
        panel_state.update(
            {
                "status": "failed",
                "last_message": str(exc),
                "progress": 0,
                "progress_message": "生成失败。",
            }
        )
        panels[panel_id] = panel_state
        update_figure_job(
            figure_id,
            job_token,
            status="failed",
            panels=panels,
            progress=0,
            progress_message="",
            last_message=str(exc),
            job_token=None,
        )


def data_figure_layout(prompt: str) -> dict[str, Any]:
    """Interpret the small, explicit layout vocabulary without an API call."""
    normalized = prompt.lower()
    orientation = (
        "vertical"
        if any(
            token in normalized
            for token in (
                "竖排",
                "纵向",
                "上下排列",
                "上下放置",
                "上下堆叠",
                "vertical",
                "stack",
            )
        )
        else "horizontal"
    )
    labels = not any(
        token in normalized for token in ("无角标", "不要角标", "no label", "without label")
    )
    width = (
        "two-column"
        if any(token in normalized for token in ("双栏", "跨栏", "two-column", "full width"))
        else "single-column"
    )
    return {"orientation": orientation, "labels": labels, "width": width}


def extract_agent_layout_json(raw: str) -> dict[str, Any]:
    source = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", source, re.DOTALL)
    if fenced:
        source = fenced.group(1)
    else:
        start, end = source.find("{"), source.rfind("}")
        if start < 0 or end <= start:
            raise StudioError("本地 Agent 没有返回布局 JSON。")
        source = source[start : end + 1]
    try:
        result = json.loads(source)
    except json.JSONDecodeError as exc:
        raise StudioError(f"本地 Agent 返回的布局 JSON 无法解析：{exc}") from exc
    if not isinstance(result, dict):
        raise StudioError("本地 Agent 的布局计划必须是 JSON object。")
    return result


def validate_data_figure_layout(
    raw: dict[str, Any], panel_ids: list[str]
) -> dict[str, Any]:
    orientation = raw.get("orientation")
    width = raw.get("width")
    order = raw.get("panel_order")
    if orientation not in {"horizontal", "vertical"}:
        raise StudioError("Agent 布局的 orientation 必须是 horizontal 或 vertical。")
    if width not in {"single-column", "two-column"}:
        raise StudioError("Agent 布局的 width 必须是 single-column 或 two-column。")
    if not isinstance(order, list) or sorted(order) != sorted(panel_ids):
        raise StudioError("Agent 布局必须且只能包含全部已生成 panel。")
    gap = raw.get("gap_pt", 0)
    crop = raw.get("crop_margins_pt", 0)
    if not isinstance(gap, (int, float)) or not 0 <= gap <= 24:
        raise StudioError("Agent 布局的 gap_pt 必须在 0–24 之间。")
    if not isinstance(crop, (int, float)) or not 0 <= crop <= 12:
        raise StudioError("Agent 布局的 crop_margins_pt 必须在 0–12 之间。")
    raw_labels = raw.get("labels", [])
    if not isinstance(raw_labels, list):
        raise StudioError("Agent 布局的 labels 必须是数组。")
    labels = []
    seen: set[str] = set()
    for item in raw_labels:
        if not isinstance(item, dict):
            raise StudioError("每个角标必须是 JSON object。")
        panel_id = str(item.get("panel_id", ""))
        text = str(item.get("text", "")).strip()
        position = str(item.get("position", ""))
        font_size = item.get("font_size_pt", 8)
        if panel_id not in panel_ids or panel_id in seen:
            raise StudioError("Agent 布局包含未知或重复的角标 panel。")
        if not text or len(text) > 12:
            raise StudioError("Agent 角标文字必须为 1–12 个字符。")
        if position not in {"top-left", "top-right", "bottom-left", "bottom-right"}:
            raise StudioError("Agent 角标位置不受支持。")
        if not isinstance(font_size, (int, float)) or not 6 <= font_size <= 24:
            raise StudioError("Agent 角标 font_size_pt 必须在 6–24 之间。")
        labels.append(
            {
                "panel_id": panel_id,
                "text": text,
                "position": position,
                "font_size_pt": float(font_size),
            }
        )
        seen.add(panel_id)
    return {
        "orientation": orientation,
        "width": width,
        "panel_order": order,
        "gap_pt": float(gap),
        "crop_margins_pt": float(crop),
        "labels": labels,
        "output_format": "pptx-and-vector-pdf",
    }


def create_data_figure_layout_with_local_agent(
    figure_id: str, instruction: str
) -> dict[str, Any]:
    """Use the local Codex Agent to translate natural language into safe layout JSON."""
    codex = shutil_which("codex")
    if not codex:
        raise StudioError("未找到本机 codex CLI，无法解释论文组合 Prompt。")
    panels = FIGURES[figure_id].get("panels", [])
    panel_ids = [item["id"] for item in panels]
    panel_context = [
        {
            "id": item["id"],
            "title": item["title"],
            "pdf": str(data_panel_paths(figure_id, item["id"])["pdf"]),
        }
        for item in panels
    ]
    prompt = f"""你是 Paper Studio 的本地论文排版 Agent。把研究者的自然语言要求
转换成一个严格 JSON 布局计划。只返回 JSON object，不要 Markdown，不要解释，
不要修改文件，也不要运行绘图程序。

研究者要求：
{instruction.strip()}

可用子图：
{json.dumps(panel_context, ensure_ascii=False, indent=2)}

严格 schema：
{{
  "orientation": "horizontal" | "vertical",
  "width": "single-column" | "two-column",
  "panel_order": {json.dumps(panel_ids)},
  "gap_pt": 0 到 24 的数字,
  "crop_margins_pt": 0 到 12 的数字,
  "labels": [
    {{"panel_id": "a", "text": "(a)", "position": "top-left", "font_size_pt": 8}}
  ]
}}

约束：
1. panel_order 必须且只能包含全部可用子图，但可按研究者要求调整顺序。
2. “不留空白/无缝/紧贴”对应 gap_pt=0；裁掉四周白边对应 crop_margins_pt=0。
3. 没有要求角标时 labels=[]；要求 a/b 角标时为每个 panel 生成一项。默认字号 8 pt；
   若研究者指定字号，写入 font_size_pt。
4. 执行器会把各子图作为独立矢量对象放入 PPT，把角标作为可编辑文本框；
   最终矢量 PDF 使用同一布局无交互生成，不得要求用户点击 PowerPoint 权限。
   不要提出 PNG 拼接、栅格化或修改实验数据。
5. 无法表达的装饰性要求应忽略，不得增加 schema 外字段。
"""
    environment = local_agent_environment()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"agent-layout-{figure_id.lower()}-", dir=STATE_DIR
    ) as temporary_name:
        output = Path(temporary_name) / "last_message.txt"
        command = [
            codex,
            "exec",
            "--ephemeral",
            *local_agent_auth_args(),
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--cd",
            str(ROOT),
            "--output-last-message",
            str(output),
            "-",
        ]
        try:
            process = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=300,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise StudioError("本地 Agent 解释论文组合 Prompt 超时。") from exc
        if process.returncode or not output.exists():
            diagnostic = (process.stdout + "\n" + process.stderr).strip()
            raise StudioError(
                "本地 Agent 解释论文组合 Prompt 失败。\n"
                + (diagnostic[-2400:] or "codex exec 未返回布局计划。")
            )
        raw = extract_agent_layout_json(
            output.read_text(encoding="utf-8", errors="replace")
        )
    return validate_data_figure_layout(raw, panel_ids)


def pdf_page_size(pdf: Path, *, cwd: Path) -> tuple[float, float]:
    output = run_checked(["pdfinfo", str(pdf)], cwd=cwd)
    match = re.search(r"^Page size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts", output, re.M)
    if not match:
        raise StudioError(f"无法读取 PDF 页面尺寸：{pdf.name}")
    return float(match.group(1)), float(match.group(2))


def ensure_artifact_tool_runtime() -> None:
    package = PPT_COMPOSER.parent / "node_modules" / "@oai" / "artifact-tool"
    if package.exists():
        return
    runtime_modules = (
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
    )
    if not (runtime_modules / "@oai" / "artifact-tool").exists():
        raise StudioError("本机 PowerPoint 构建运行时缺少 @oai/artifact-tool。")
    link = PPT_COMPOSER.parent / "node_modules"
    if not link.exists():
        link.symlink_to(runtime_modules, target_is_directory=True)


def composition_geometry(
    layout: dict[str, Any], panels: list[dict[str, Any]]
) -> tuple[float, float, list[dict[str, Any]]]:
    target_width = (3.32 if layout["width"] == "single-column" else 7.0) * 72
    gap = float(layout["gap_pt"])
    placed = [dict(panel) for panel in panels]
    if layout["orientation"] == "horizontal":
        ratios = [panel["width_pt"] / panel["height_pt"] for panel in placed]
        height = (target_width - gap * (len(placed) - 1)) / sum(ratios)
        cursor = 0.0
        for panel, ratio in zip(placed, ratios):  # noqa: B905 - ratios derive from placed
            panel.update(x=cursor, top=0.0, width=height * ratio, height=height)
            cursor += panel["width"] + gap
        return target_width, height, placed
    cursor = 0.0
    for panel in placed:
        height = target_width * panel["height_pt"] / panel["width_pt"]
        panel.update(x=0.0, top=cursor, width=target_width, height=height)
        cursor += height + gap
    return target_width, cursor - gap, placed


def write_vector_composition_tex(
    target: Path,
    layout: dict[str, Any],
    panels: list[dict[str, Any]],
) -> None:
    page_width, page_height, placed = composition_geometry(layout, panels)
    labels = {item["panel_id"]: item for item in layout["labels"]}
    lines = [
        r"\documentclass[border=0pt]{standalone}",
        r"\usepackage{graphicx,tikz,helvet}",
        r"\renewcommand{\familydefault}{\sfdefault}",
        r"\begin{document}",
        r"\begin{tikzpicture}[x=1bp,y=1bp,inner sep=0pt,outer sep=0pt]",
        f"\\useasboundingbox (0,0) rectangle ({page_width:.6f},{page_height:.6f});",
    ]
    for panel in placed:
        bottom = page_height - panel["top"] - panel["height"]
        lines.append(
            f"\\node[anchor=south west] at ({panel['x']:.6f},{bottom:.6f}) "
            f"{{\\includegraphics[width={panel['width']:.6f}bp,"
            f"height={panel['height']:.6f}bp]"
            f"{{\\detokenize{{{panel['pdf']}}}}}}};"
        )
        label = labels.get(panel["id"])
        if not label:
            continue
        position = label["position"]
        x = panel["x"] + (2 if position.endswith("left") else panel["width"] - 2)
        y = bottom + (panel["height"] - 2 if position.startswith("top") else 2)
        anchor = {
            "top-left": "north west",
            "top-right": "north east",
            "bottom-left": "south west",
            "bottom-right": "south east",
        }[position]
        text = str(label["text"])
        for source, replacement in (
            ("\\", r"\textbackslash{}"),
            ("%", r"\%"),
            ("&", r"\&"),
            ("_", r"\_"),
            ("#", r"\#"),
        ):
            text = text.replace(source, replacement)
        size = float(label["font_size_pt"])
        lines.append(
            f"\\node[anchor={anchor},fill=white,inner sep=1pt,"
            f"font=\\bfseries\\fontsize{{{size:g}}}{{{size * 1.2:g}}}\\selectfont] "
            f"at ({x:.6f},{y:.6f}) {{{text}}};"
        )
    lines.extend([r"\end{tikzpicture}", r"\end{document}"])
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compose_data_figure(
    figure_id: str,
    prompt: str,
    layout: dict[str, Any] | None = None,
) -> str:
    """Lay out vector panels in editable PPTX, export to PDF, then crop it."""
    definition = FIGURES[figure_id]
    panels = definition.get("panels", [])
    if not panels:
        raise StudioError("该图没有可组合的独立子图。")
    missing = [
        panel["id"]
        for panel in panels
        if not data_panel_paths(figure_id, panel["id"])["pdf"].exists()
    ]
    if missing:
        raise StudioError("请先逐个生成子图：" + ", ".join(missing))
    required = ["pdfcrop", "pdfinfo", "pdftocairo", "latexmk", "node"]
    missing_tools = [command for command in required if not shutil_which(command)]
    if missing_tools:
        raise StudioError("本地 PPT 组合缺少工具：" + ", ".join(missing_tools))
    ensure_artifact_tool_runtime()

    layout = layout or create_data_figure_layout_with_local_agent(figure_id, prompt)
    panel_by_id = {panel["id"]: panel for panel in panels}
    ordered_panels = [panel_by_id[panel_id] for panel_id in layout["panel_order"]]
    paths = figure_paths(figure_id)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"compose-{figure_id.lower()}-", dir=STATE_DIR
    ) as temporary_name:
        build_dir = Path(temporary_name)
        panel_specs: list[dict[str, Any]] = []
        for panel in ordered_panels:
            panel_id = panel["id"]
            source_pdf = data_panel_paths(figure_id, panel_id)["pdf"]
            local_source = build_dir / f"panel-{panel_id}.pdf"
            local_source.write_bytes(source_pdf.read_bytes())
            cropped = build_dir / f"panel-{panel_id}-crop.pdf"
            run_checked(
                [
                    "pdfcrop",
                    "--margins",
                    str(layout["crop_margins_pt"]),
                    local_source.name,
                    cropped.name,
                ],
                cwd=build_dir,
            )
            width_pt, height_pt = pdf_page_size(cropped, cwd=build_dir)
            svg = build_dir / f"panel-{panel_id}.svg"
            run_checked(
                ["pdftocairo", "-svg", str(cropped), str(svg)],
                cwd=build_dir,
            )
            panel_specs.append(
                {
                    "id": panel_id,
                    "svg": str(svg),
                    "pdf": str(cropped),
                    "width_pt": width_pt,
                    "height_pt": height_pt,
                }
            )

        composition_pptx = build_dir / "composition.pptx"
        composition_pdf = build_dir / "composition.pdf"
        preview_png = build_dir / "preview.png"
        executor_spec = build_dir / "composition.json"
        executor_spec.write_text(
            json.dumps({**layout, "panels": panel_specs}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        run_checked(
            [
                "node",
                str(PPT_COMPOSER),
                str(executor_spec),
                str(composition_pptx),
                str(preview_png),
            ],
            cwd=build_dir,
        )
        composition_tex = build_dir / "composition.tex"
        write_vector_composition_tex(composition_tex, layout, panel_specs)
        run_checked(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                composition_tex.name,
            ],
            cwd=build_dir,
        )
        pdf_tmp = paths["pdf"].with_suffix(".pdf.tmp")
        pptx_tmp = paths["pptx"].with_suffix(".pptx.tmp")
        png_tmp = paths["preview"].with_suffix(".png.tmp")
        pdf_tmp.write_bytes(composition_pdf.read_bytes())
        pptx_tmp.write_bytes(composition_pptx.read_bytes())
        png_tmp.write_bytes(preview_png.read_bytes())
        os.replace(pdf_tmp, paths["pdf"])
        os.replace(pptx_tmp, paths["pptx"])
        os.replace(png_tmp, paths["preview"])
        paths["layout_source"].write_text(
            json.dumps(
                {
                    **layout,
                    "panels": [panel["id"] for panel in ordered_panels],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        paths["layout_prompt"].write_text(prompt.strip() + "\n", encoding="utf-8")
    direction = "横向" if layout["orientation"] == "horizontal" else "纵向"
    label_note = "并添加角标" if layout["labels"] else ""
    return (
        f"已将 {len(panels)} 张矢量子图作为独立对象放入 PPT，"
        f"无缝{direction}排版{label_note}；PPTX 与最终矢量 PDF 使用同一布局，"
        "全程无需 PowerPoint 权限确认。"
    )


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    provider = str(state.get("llm_provider") or DEFAULT_PROVIDER).strip().lower()
    if provider not in PROVIDER_DEFAULT_MODELS:
        provider = "openai"
    api_key_setup = api_setup_for_provider(provider)
    api_key_configured = bool(api_key_setup["configured"])
    provider_options = [
        {
            "id": candidate,
            "label": provider_configuration(candidate)["label"],
            "configured": bool(api_setup_for_provider(candidate)["configured"]),
            "default_model": PROVIDER_DEFAULT_MODELS[candidate],
        }
        for candidate in ("openai", "deepseek")
    ]
    model_options = model_options_for_provider(provider, str(state.get("model") or ""))
    if EMPTY_PROJECT_MODE or not project_files_ready():
        return {
            "schema_version": state.get("schema_version", "1.2"),
            "project_id": "__paper_studio_empty__",
            "project": {
                "id": "__paper_studio_empty__",
                "name": "",
                "eyebrow": "PAPER STUDIO",
                "studio_title": "Paper Studio",
                "subtitle": "等待 paperwrite 填入论文项目数据",
                "config_file": PROJECT_CONFIG_FILE.relative_to(ROOT).as_posix(),
                "root": "" if ONLINE_PROJECT_MODE else str(ROOT.resolve()),
                "loaded": False,
                "venue": "",
                "target": {},
                "reference_paper": {},
                "decision_source": "",
                "export_url": "",
            },
            "model": state.get("model", DEFAULT_MODEL),
            "llm_provider": provider,
            "llm_provider_options": provider_options,
            "llm_model_options": model_options,
            "sections": {},
            "figures": [],
            "tables": [],
            "pdf": {
                "exists": False,
                "version": None,
                "url": "/paper.pdf",
                "page_count": 0,
                "page_width_pt": 612.0,
                "page_height_pt": 792.0,
            },
            "outline_confirmed": False,
            "demo_mode": DEMO_MODE,
            "api_key_configured": api_key_configured,
            "api_key_setup": api_key_setup,
            "api_usage": usage_summary(API_USAGE_FILE),
            "full_draft": {
                "available": False,
                "pending_paragraphs": 0,
                "total_paragraphs": 0,
                "writing_order": [],
                "job": None,
            },
        }
    result = json.loads(json.dumps(state))
    result["project"] = {
        "id": PROJECT_ID,
        "name": str(PROJECT_METADATA.get("name", "")),
        "eyebrow": str(PROJECT_METADATA.get("eyebrow", "")),
        "studio_title": str(PROJECT_METADATA.get("studio_title", "Paper Studio")),
        "subtitle": str(PROJECT_METADATA.get("subtitle", "")),
        "config_file": PROJECT_CONFIG_FILE.relative_to(ROOT).as_posix(),
        "root": "" if ONLINE_PROJECT_MODE else str(ROOT.resolve()),
        "loaded": True,
        "venue": str(PROJECT_METADATA.get("venue", "")),
        "target": {
            key: value
            for key in (
                "venue",
                "track",
                "cycle",
                "submission_content_pages",
                "deadline",
            )
            if (value := PROJECT_METADATA.get("target", {}).get(key)) not in (None, "")
        },
        "reference_paper": {
            key: value
            for key in ("title", "authors", "venue", "publication_key", "url")
            if (value := PROJECT_METADATA.get("reference_paper", {}).get(key))
        },
        "decision_source": str(PROJECT_METADATA.get("decision_source", "")),
        "export_url": (
            "/api/online/export" if ONLINE_PROJECT_MODE and not DEMO_MODE else ""
        ),
    }
    total_paragraphs = sum(
        len(section.get("paragraphs", []))
        for section in state.get("sections", {}).values()
    )
    pending_paragraphs = len(full_draft_targets(state))
    outline_confirmed = outline_is_confirmed()
    result["full_draft"] = {
        "available": outline_confirmed and api_key_configured,
        "pending_paragraphs": pending_paragraphs,
        "total_paragraphs": total_paragraphs,
        "writing_order": batch_writing_order(),
        "job": result.pop("full_draft_job", None),
    }
    title_editor = result.setdefault("title_editor", {})
    title_editor["current_title"] = manuscript_title_display()
    title_editor["conversation_active"] = bool(
        title_editor.pop("previous_response_id", None)
    )
    for section in result["sections"].values():
        section["conversation_active"] = bool(section.pop("previous_response_id", None))
        index = int(section.get("current_index", 0))
        paragraphs = section.pop("paragraphs", [])
        section["paragraph_count"] = len(paragraphs)
        section["completed_count"] = sum(
            bool(item.get("accepted_text")) for item in paragraphs
        )
        section["complete"] = section["completed_count"] == len(paragraphs)
        section["paragraph_navigation"] = [
            {
                "id": item["id"],
                "purpose": item["purpose"],
                "artifacts": [
                    metadata
                    for artifact_id in item.get("artifacts", [])
                    if (metadata := artifact_metadata(str(artifact_id))) is not None
                ],
                "status": (
                    "candidate"
                    if item.get("candidate")
                    else "accepted"
                    if item.get("accepted_text")
                    else "pending"
                ),
                "selected": item_index == index,
            }
            for item_index, item in enumerate(paragraphs)
        ]
        if 0 <= index < len(paragraphs):
            item = paragraphs[index]
            section["current_paragraph"] = {
                "id": item["id"],
                "heading": item.get("heading"),
                "heading_style": item.get("heading_style"),
                "purpose": item["purpose"],
                "artifacts": [
                    metadata
                    for artifact_id in item.get("artifacts", [])
                    if (metadata := artifact_metadata(str(artifact_id))) is not None
                ],
                "reference_text": reference_excerpt(item["reference_lines"]),
                "candidate": item.get("candidate"),
                "accepted_text": item.get("accepted_text", ""),
                "position": index + 1,
                "total": len(paragraphs),
            }
        else:
            section["current_paragraph"] = None
    pdf = PAPER / "main.pdf"
    pdf_metadata = paper_pdf_metadata()
    result["pdf"] = {
        "exists": pdf.exists(),
        "version": int(pdf.stat().st_mtime_ns) if pdf.exists() else None,
        "url": "/paper.pdf",
        **pdf_metadata,
    }
    result["outline_confirmed"] = outline_confirmed
    result["demo_mode"] = DEMO_MODE
    result["llm_provider"] = provider
    result["llm_provider_options"] = provider_options
    result["llm_model_options"] = model_options
    result["api_key_configured"] = api_key_configured
    result["api_key_setup"] = api_key_setup
    result["api_usage"] = usage_summary(API_USAGE_FILE)
    result["figures"] = figure_public_state(state)
    result["tables"] = table_public_state(state)
    return result


def _remove_generated_path(path: Path) -> None:
    """Delete one exact Paper Studio output path, never project inputs/config."""
    resolved = path.resolve()
    try:
        resolved.relative_to(PAPER.resolve())
    except ValueError as exc:
        raise StudioError(f"拒绝清理 paper/ 之外的路径：{path}") from exc
    protected = {
        PAPER.resolve(),
        PROJECT_CONFIG_FILE.resolve(),
        PARAGRAPH_PLAN_FILE.resolve(),
        (PAPER / "main.tex").resolve(),
        (PAPER / "outline.txt").resolve(),
        (PAPER / "working_abstract.txt").resolve(),
        (PAPER / "references.bib").resolve(),
    }
    if resolved in protected:
        raise StudioError(f"拒绝清理 Paper Studio 输入：{path}")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink(missing_ok=True)


def _configured_reset_input_paths() -> set[Path]:
    """Return project inputs inside generated trees that reset must preserve."""
    protected: set[Path] = set()
    for artifact_id, definition in {**FIGURES, **TABLES}.items():
        shape_spec = str(definition.get("shape_spec", "")).strip()
        if shape_spec:
            protected.add(
                _project_path(ROOT, shape_spec, f"{artifact_id}.shape_spec").resolve()
            )
    return protected


def _clear_generated_tree(root: Path, protected_files: set[Path] | None = None) -> None:
    """Clear every current or legacy output below one exact paper-local root."""
    protected = {path.resolve() for path in (protected_files or set())}
    resolved_root = root.resolve()
    try:
        resolved_root.relative_to(PAPER.resolve())
    except ValueError as exc:
        raise StudioError(f"拒绝清理 paper/ 之外的目录：{root}") from exc
    if not root.exists():
        return
    protected_below_root = {
        path for path in protected if path == resolved_root or resolved_root in path.parents
    }
    if not protected_below_root:
        _remove_generated_path(root)
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        resolved = path.resolve()
        if resolved in protected_below_root:
            continue
        if any(resolved in protected_path.parents for protected_path in protected_below_root):
            continue
        _remove_generated_path(path)
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()


def reset_generated_paper(model: str) -> dict[str, Any]:
    """Clear generated manuscript/runtime artifacts while preserving project inputs."""
    with FIGURE_PROCESS_LOCK:
        if RUNNING_FIGURE_PROCESSES:
            raise StudioError("仍有绘图调用运行；请先用进度条右侧的停止按钮结束调用。")

    current_provider = active_llm_provider()
    fresh = _default_state()
    fresh["llm_provider"] = current_provider
    fresh["model"] = model
    sections_dir = PAPER / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    for section_id, section_state in fresh["sections"].items():
        source, _accepted = render_section_source(
            section_id, section_state, fresh["figures"], fresh["tables"]
        )
        target = sections_dir / SECTION_MAP[section_id]["file"]
        temporary = target.with_suffix(".tex.tmp")
        temporary.write_text(source, encoding="utf-8")
        os.replace(temporary, target)
    bibliography = sections_dir / "bibliography.tex"
    bibliography.write_text(
        "% Paper Studio enables the bibliography after the first accepted citation.\n",
        encoding="utf-8",
    )

    initial_title = str(
        PROJECT_METADATA.get("initial_title") or PROJECT_METADATA.get("name") or "Untitled Paper"
    ).strip()
    main_path = PAPER / "main.tex"
    main_path.write_text(
        replace_manuscript_title_source(
            main_path.read_text(encoding="utf-8"), initial_title
        ),
        encoding="utf-8",
    )

    protected_inputs = _configured_reset_input_paths()
    _clear_generated_tree(FIGURE_DIR, protected_inputs)
    _clear_generated_tree(FIGURE_SOURCE_DIR, protected_inputs)
    _clear_generated_tree(STATE_DIR)

    for path in PAPER.glob("main.*"):
        if path.resolve() != main_path.resolve():
            _remove_generated_path(path)

    compile_result = compile_paper()
    if not compile_result.ok:
        raise StudioError("清空完成，但空壳 PDF 编译失败。\n" + compile_result.message)
    fresh["compile"] = {
        "status": "ok",
        "message": compile_result.message,
        "updated_at": int(time.time()),
    }
    replace_state(fresh)
    return fresh


class Handler(BaseHTTPRequestHandler):
    server_version = "PaperStudio/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[paper-studio] {self.address_string()} {fmt % args}")

    def write_body(self, data: bytes) -> None:
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            # Browsers routinely cancel in-flight SVG/PDF previews while
            # switching sections or closing a page. The response is already
            # unusable to that client, so end it quietly instead of emitting a
            # misleading request-handler traceback.
            self.close_connection = True

    def send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.write_body(data)

    def send_file(self, path: Path, content_type: str, cache: bool = True) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=120" if cache else "no-store")
        self.end_headers()
        self.write_body(data)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                raise StudioError("Invalid request body size.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise StudioError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise StudioError("Request body must be a JSON object.")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            self.send_file(STATIC / "index.html", "text/html; charset=utf-8", cache=False)
        elif path == "/static/app.js":
            self.send_file(STATIC / "app.js", "text/javascript; charset=utf-8", cache=False)
        elif path == "/static/style.css":
            self.send_file(STATIC / "style.css", "text/css; charset=utf-8", cache=False)
        elif path == "/api/health":
            self.send_json(
                {
                    "ok": True,
                    "project": {
                        "root": "" if ONLINE_PROJECT_MODE else str(ROOT.resolve()),
                        "id": PROJECT_ID,
                    },
                    "empty_project": EMPTY_PROJECT_MODE or not project_files_ready(),
                    "pid": os.getpid(),
                }
            )
        elif path == "/api/state":
            self.send_json(public_state(load_state()))
        elif path == "/paper.pdf":
            self.send_file(PAPER / "main.pdf", "application/pdf", cache=False)
        elif path.startswith("/paper-page/") and path.endswith(".svg"):
            match = re.fullmatch(r"/paper-page/(\d+)\.svg", path)
            if not match:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                self.send_file(
                    paper_page_svg(int(match.group(1))),
                    "image/svg+xml; charset=utf-8",
                )
            except StudioError as exc:
                self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
        elif path.startswith("/figure-file/"):
            self.handle_figure_file(path)
        elif path.startswith("/figure-panel-file/"):
            self.handle_figure_panel_file(path)
        elif path.startswith("/table-file/"):
            self.handle_table_file(path)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        try:
            body = self.read_json()
            if ONLINE_PROJECT_MODE and self.path in ONLINE_DISABLED_ARTIFACT_AGENT_PATHS:
                raise StudioError(
                    "在线会话当前不运行图表构建 Agent；"
                    "论文对话、正文、标题、Caption 与 LLM 写作功能仍可正常使用。"
                )
            if self.path == "/api/generate":
                self.handle_generate(body)
            elif self.path == "/api/title/generate":
                self.handle_title_generate(body)
            elif self.path == "/api/title/save":
                self.handle_title_save(body)
            elif self.path == "/api/accept":
                self.handle_accept(body)
            elif self.path == "/api/compile":
                self.handle_compile()
            elif self.path == "/api/full-draft/start":
                self.handle_full_draft_start(body)
            elif self.path == "/api/full-draft/cancel":
                self.handle_full_draft_cancel()
            elif self.path == "/api/llm-provider":
                self.handle_llm_provider(body)
            elif self.path == "/api/llm-model":
                self.handle_llm_model(body)
            elif self.path == "/api/reset-conversation":
                self.handle_reset(body)
            elif self.path == "/api/reset-generated-paper":
                self.handle_reset_generated_paper(body)
            elif self.path == "/api/select-paragraph":
                self.handle_select_paragraph(body)
            elif self.path == "/api/pdf/locate":
                self.handle_pdf_locate(body)
            elif self.path == "/api/figure/prompt":
                self.handle_figure_prompt(body)
            elif self.path == "/api/figure/draw":
                self.handle_figure_draw(body)
            elif self.path == "/api/figure/cancel":
                self.handle_figure_cancel(body)
            elif self.path == "/api/figure/generate":
                self.handle_figure_generate(body)
            elif self.path == "/api/figure/panel/generate":
                self.handle_figure_generate(body)
            elif self.path == "/api/figure/compose":
                self.handle_figure_compose(body)
            elif self.path == "/api/runtime-key":
                self.handle_runtime_key(body)
            elif self.path == "/api/figure/build":
                self.handle_figure_build(body)
            elif self.path == "/api/figure/placement":
                self.handle_figure_placement(body)
            elif self.path == "/api/figure/caption/generate":
                self.handle_figure_caption_generate(body)
            elif self.path == "/api/figure/caption":
                self.handle_figure_caption(body)
            elif self.path == "/api/figure/approve":
                self.handle_figure_approve(body)
            elif self.path == "/api/table/generate":
                self.handle_table_generate(body)
            elif self.path == "/api/table/agent-edit":
                self.handle_table_agent_edit(body)
            elif self.path == "/api/table/save":
                self.handle_table_save(body)
            elif self.path == "/api/table/placement":
                self.handle_table_placement(body)
            elif self.path == "/api/table/approve":
                self.handle_table_approve(body)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except StudioError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - final safety net
            self.send_json({"ok": False, "error": f"Internal error: {exc}"}, status=500)

    def require_section(self, body: dict[str, Any]) -> str:
        section = str(body.get("section", ""))
        if section not in SECTION_MAP:
            raise StudioError("Unknown manuscript section.")
        return section

    def handle_llm_provider(self, body: dict[str, Any]) -> None:
        state = load_state()
        if full_draft_running(state):
            raise StudioError("全文初稿正在生成；请先停止任务再切换 LLM API。")
        provider = str(body.get("provider") or "").strip().lower()
        if select_llm_provider(state, provider):
            save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_llm_model(self, body: dict[str, Any]) -> None:
        state = load_state()
        if full_draft_running(state):
            raise StudioError("全文初稿正在生成；请先停止任务再切换写作模型。")
        model = str(body.get("model") or "").strip()
        if select_llm_model(state, model):
            save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_title_generate(self, body: dict[str, Any]) -> None:
        state = load_state()
        if full_draft_running(state):
            raise StudioError("全文初稿正在生成；请等待完成或先停止任务。")
        editor = state["title_editor"]
        prompt = str(body.get("prompt", "")).strip()
        if not prompt:
            raise StudioError("请先填写 Title GPT Prompt。")
        model = str(body.get("model") or state.get("model") or DEFAULT_MODEL).strip()
        current_title = normalize_plain_title(
            str(body.get("current_title") or manuscript_title_display())
        )
        response_id, candidate = call_openai_for_title(
            model=model,
            prompt=prompt,
            current_title=current_title,
            previous_response_id=editor.get("previous_response_id"),
        )
        editor.update(
            {
                "prompt": prompt,
                "candidate": candidate,
                "previous_response_id": response_id,
                "last_message": "GPT candidate 尚未保存；可继续编辑，确认后再写入 LaTeX。",
            }
        )
        state["model"] = model
        save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_title_save(self, body: dict[str, Any]) -> None:
        if full_draft_running(load_state()):
            raise StudioError("全文初稿正在生成；请等待完成或先停止任务。")
        title = normalize_plain_title(str(body.get("title", "")))
        result = save_manuscript_title(title)
        state = load_state()
        editor = state["title_editor"]
        editor["candidate"] = ""
        editor["last_message"] = "标题已确认写入 LaTeX，并完成 PDF 编译。"
        state["compile"] = {
            "status": "ok",
            "message": result.message,
            "updated_at": int(time.time()),
        }
        save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def require_figure(self, body: dict[str, Any]) -> str:
        figure_id = str(body.get("figure_id", "")).upper()
        if figure_id not in FIGURES:
            raise StudioError("Unknown paper figure.")
        return figure_id

    def require_panel(self, figure_id: str, body: dict[str, Any]) -> str:
        panel_id = str(body.get("panel_id", "")).lower()
        valid = {item["id"] for item in FIGURES[figure_id].get("panels", [])}
        if panel_id not in valid:
            raise StudioError("请选择一个有效的独立子图。")
        return panel_id

    def require_table(self, body: dict[str, Any]) -> str:
        table_id = str(body.get("table_id", "")).upper()
        if table_id not in TABLES:
            raise StudioError("Unknown paper table.")
        return table_id

    def handle_figure_file(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, figure_id, kind = parts
        figure_id = figure_id.upper()
        if figure_id not in FIGURES or kind not in {
            "draft",
            "preview",
            "pdf",
            "pptx",
        }:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        target = (
            mechanism_draft_path(figure_id)
            if kind == "draft"
            else figure_paths(figure_id)[kind]
        )
        content_types = {
            "draft": "image/png",
            "preview": "image/png",
            "pdf": "application/pdf",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        self.send_file(target, content_types[kind], cache=False)

    def handle_figure_panel_file(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 4:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, figure_id, panel_id, kind = parts
        figure_id = figure_id.upper()
        panel_id = panel_id.lower()
        if figure_id not in FIGURES or kind not in {"preview", "pdf"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            target = data_panel_paths(figure_id, panel_id)[kind]
        except StudioError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_file(
            target,
            "image/png" if kind == "preview" else "application/pdf",
            cache=False,
        )

    def handle_table_file(self, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, table_id, kind = parts
        table_id = table_id.upper()
        if table_id not in TABLES or kind not in {"preview", "pdf"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        target = table_preview_paths(table_id)[kind]
        content_type = "image/png" if kind == "preview" else "application/pdf"
        self.send_file(target, content_type, cache=False)

    def handle_generate(self, body: dict[str, Any]) -> None:
        section = self.require_section(body)
        state = load_state()
        if full_draft_running(state):
            raise StudioError("全文初稿正在生成；请等待完成或先停止任务。")
        model = str(body.get("model") or state.get("model") or DEFAULT_MODEL).strip()
        section_state = state["sections"][section]
        paragraph = current_paragraph(section_state)
        if paragraph is None:
            raise StudioError("This section has no remaining paragraph.")
        requested_paragraph_id = str(body.get("paragraph_id", "")).strip()
        if requested_paragraph_id and paragraph["id"] != requested_paragraph_id:
            raise StudioError(
                f"Paragraph changed from {requested_paragraph_id} to {paragraph['id']}; "
                "reload before generating."
            )
        purpose = paragraph["purpose"]
        reference = reference_excerpt(paragraph["reference_lines"])
        current_bib_fingerprint = bibliography_fingerprint()
        source_fingerprint = section_source_fingerprint(section)
        include_section_context = (
            not section_state.get("previous_response_id")
            or section_state.get("conversation_section_fingerprint") != source_fingerprint
        )
        bibliography_update = ""
        if (
            section_state.get("previous_response_id")
            and section_state.get("bibliography_fingerprint")
            != current_bib_fingerprint
        ):
            bibliography_update = bibliography_prompt_catalog(
                purpose + "\n" + section_evidence(section)
            )
        response_id, text, citations_added = call_openai(
            section=section,
            model=model,
            previous_response_id=section_state.get("previous_response_id"),
            purpose=purpose,
            required_heading=paragraph.get("heading"),
            required_heading_style=paragraph.get("heading_style"),
            reference_paragraph=reference,
            comment=str(body.get("comment", "")),
            current_text=str(body.get("current_text", "")),
            bibliography_update=bibliography_update,
            artifacts=[str(item) for item in paragraph.get("artifacts", [])],
            figure_states=state["figures"],
            include_section_context=include_section_context,
        )
        candidate_id = uuid.uuid4().hex
        section_state["previous_response_id"] = response_id
        section_state["bibliography_fingerprint"] = bibliography_fingerprint()
        section_state["conversation_section_fingerprint"] = source_fingerprint
        paragraph["candidate"] = {
            "id": candidate_id,
            "text": text,
            "purpose": purpose,
            "citations_added": citations_added,
            "created_at": int(time.time()),
        }
        paragraph["history"].append(
            {
                "candidate_id": candidate_id,
                "comment": str(body.get("comment", "")),
                "text": text,
                "citations_added": citations_added,
                "created_at": int(time.time()),
            }
        )
        paragraph["history"] = paragraph["history"][-40:]
        state["model"] = model
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "candidate": paragraph["candidate"],
                "state": public_state(state),
            }
        )

    def handle_accept(self, body: dict[str, Any]) -> None:
        section = self.require_section(body)
        requested_paragraph_id = str(body.get("paragraph_id", "")).strip()
        candidate_id = str(body.get("candidate_id", ""))
        submitted_text = str(body.get("candidate_text", "")).strip()
        base_text = str(body.get("base_text", ""))
        state = load_state()
        if full_draft_running(state):
            raise StudioError("全文初稿正在生成；请等待完成或先停止任务。")
        section_state = state["sections"][section]
        paragraph = current_paragraph(section_state)
        if paragraph is None:
            raise StudioError("This section has no remaining paragraph.")
        if requested_paragraph_id and paragraph["id"] != requested_paragraph_id:
            raise StudioError(
                f"当前编辑位置已从 {requested_paragraph_id} 更新到 {paragraph['id']}；"
                "请检查后再次 Accept。"
            )
        candidate, text = candidate_for_accept(
            paragraph,
            candidate_id=candidate_id,
            submitted_text=submitted_text,
            base_text=base_text,
        )
        text = enforce_required_heading(
            text,
            paragraph.get("heading"),
            paragraph.get("heading_style"),
        )
        candidate["text"] = text
        bound_artifacts = artifact_writing_context(
            paragraph.get("artifacts", []), state.get("figures", {})
        )
        reference_error = artifact_reference_error(text, bound_artifacts)
        if reference_error:
            raise StudioError(reference_error)
        if needs_citation_resolution(text):
            previous_response_id = section_state.get("previous_response_id")
            response_id, text, citations_added = resolve_citations(
                model=str(state.get("model") or DEFAULT_MODEL),
                previous_response_id=previous_response_id,
                section=SECTION_MAP[section]["title"],
                purpose=paragraph["purpose"],
                paragraph=text,
            )
            text = enforce_required_heading(
                text,
                paragraph.get("heading"),
                paragraph.get("heading_style"),
            )
            section_state["previous_response_id"] = response_id
            section_state["bibliography_fingerprint"] = bibliography_fingerprint()
            candidate["text"] = text
            candidate["citations_added"] = list(
                dict.fromkeys(
                    list(candidate.get("citations_added", [])) + citations_added
                )
            )
            save_state(state)
        reference_error = artifact_reference_error(text, bound_artifacts)
        if reference_error:
            raise StudioError(reference_error)
        if "[CITATION NEEDED]" in text:
            raise StudioError(
                "联网检索后仍没有找到可验证的学术来源；候选已保留 "
                "[CITATION NEEDED]，请修改该论断后重试。"
            )
        unknown = sorted(citation_keys(text) - bibliography_keys())
        if unknown:
            raise StudioError(
                "联网检索后仍存在未验证 citation keys：" + ", ".join(unknown)
            )
        prose_issues = latex_prose_issues(text)
        if prose_issues:
            raise StudioError(
                "候选含有会破坏 pdflatex 正文的字符，请先让 GPT 修正或手动转为 "
                "LaTeX：" + "; ".join(prose_issues)
            )
        security_issues = online_latex_security_issues(text)
        if security_issues:
            raise StudioError(
                "在线模式禁止会读取文件、写文件或执行代码的 LaTeX 命令："
                + ", ".join(security_issues)
            )
        if not (PAPER / "main.tex").exists():
            raise StudioError("paper/main.tex is missing; scaffold the approved outline before accepting prose.")

        sections_dir = PAPER / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        target = sections_dir / SECTION_MAP[section]["file"]
        existed = target.exists()
        previous = target.read_text(encoding="utf-8") if existed else ""
        bibliography_path = sections_dir / "bibliography.tex"
        previous_bibliography = read_text(bibliography_path, 10000)
        was_accepted = bool(paragraph.get("accepted_text"))
        paragraph["accepted_text"] = text
        paragraph["candidate"] = None
        section_source, accepted_section = render_section_source(
            section, section_state, state["figures"], state["tables"]
        )
        temporary = target.with_suffix(".tex.tmp")
        temporary.write_text(section_source, encoding="utf-8")
        os.replace(temporary, target)
        bibliography_text = (
            "\\bibliography{references}\n"
            if manuscript_citation_keys()
            else "% Paper Studio enables the bibliography after the first accepted citation.\n"
        )
        bibliography_temporary = bibliography_path.with_suffix(".tex.tmp")
        bibliography_temporary.write_text(bibliography_text, encoding="utf-8")
        os.replace(bibliography_temporary, bibliography_path)
        compile_result = compile_paper()
        if not compile_result.ok:
            if existed:
                rollback = target.with_suffix(".tex.rollback")
                rollback.write_text(previous, encoding="utf-8")
                os.replace(rollback, target)
            elif target.exists():
                target.unlink()
            bibliography_rollback = bibliography_path.with_suffix(".tex.rollback")
            bibliography_rollback.write_text(previous_bibliography, encoding="utf-8")
            os.replace(bibliography_rollback, bibliography_path)
            compile_paper()
            raise StudioError("LaTeX failed; edit rolled back.\n" + compile_result.message)

        section_state["revision"] = int(section_state.get("revision", 0)) + 1
        section_state["accepted_text"] = accepted_section
        if candidate.get("source") != "manual_edit":
            section_state["conversation_section_fingerprint"] = section_source_fingerprint(section)
        accepted_index = int(section_state.get("current_index", 0))
        if was_accepted:
            section_state["current_index"] = accepted_index
        else:
            next_index = next_unaccepted_index(
                section_state["paragraphs"], after=accepted_index
            )
            section_state["current_index"] = (
                accepted_index
                if next_index >= len(section_state["paragraphs"])
                else next_index
            )
        state["compile"] = {
            "status": "ok",
            "message": compile_result.message,
            "updated_at": int(time.time()),
        }
        save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_compile(self) -> None:
        result = compile_paper()
        state = load_state()
        state["compile"] = {
            "status": "ok" if result.ok else "failed",
            "message": result.message,
            "updated_at": int(time.time()),
        }
        save_state(state)
        status = 200 if result.ok else 400
        self.send_json({"ok": result.ok, "message": result.message, "state": public_state(state)}, status=status)

    def handle_full_draft_start(self, body: dict[str, Any]) -> None:
        model = str(body.get("model") or DEFAULT_MODEL).strip()
        token, state = start_full_draft_job(model)
        threading.Thread(
            target=full_draft_worker,
            args=(token, model),
            daemon=True,
            name=f"full-draft-{token[:8]}",
        ).start()
        self.send_json({"ok": True, "state": public_state(state)}, status=202)

    def handle_full_draft_cancel(self) -> None:
        with FULL_DRAFT_JOB_LOCK:
            state = load_state()
            job = state.get("full_draft_job") or {}
            token = str(job.get("token") or "")
            if job.get("status") != "running" or not token:
                raise StudioError("当前没有正在运行的全文生成任务。")
            CANCELLED_FULL_DRAFT_JOBS.add(token)
            job.update(
                status="cancelled",
                token=None,
                progress_message="已请求停止；当前正在事务处理的段落完成后停止，之后可继续补齐未完成段落。",
                finished_at=int(time.time()),
            )
            state["full_draft_job"] = job
            save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_reset(self, body: dict[str, Any]) -> None:
        section = self.require_section(body)
        state = load_state()
        if full_draft_running(state):
            raise StudioError("全文初稿正在生成；不能同时重置 section 对话。")
        model = str(body.get("model") or state.get("model") or DEFAULT_MODEL).strip()
        if not model:
            raise StudioError("模型名称不能为空。")
        state["model"] = model
        state["sections"][section]["previous_response_id"] = None
        state["sections"][section]["bibliography_fingerprint"] = None
        state["sections"][section]["conversation_section_fingerprint"] = None
        save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_reset_generated_paper(self, body: dict[str, Any]) -> None:
        if full_draft_running(load_state()):
            raise StudioError("请先停止全文初稿任务，再清空生成内容。")
        confirmation = str(body.get("project_id", "")).strip()
        if confirmation != PROJECT_ID:
            raise StudioError("项目 ID 不匹配；未删除任何生成内容。")
        model = str(body.get("model") or DEFAULT_MODEL).strip()
        if not model:
            raise StudioError("模型名称不能为空。")
        state = reset_generated_paper(model)
        self.send_json(
            {
                "ok": True,
                "message": "已清空生成正文、对话、图表 candidate 与运行状态；项目输入已保留。",
                "state": public_state(state),
            }
        )

    def handle_select_paragraph(self, body: dict[str, Any]) -> None:
        section = self.require_section(body)
        paragraph_id = str(body.get("paragraph_id", ""))
        state = load_state()
        section_state = state["sections"][section]
        matches = [
            index
            for index, paragraph in enumerate(section_state["paragraphs"])
            if paragraph["id"] == paragraph_id
        ]
        if not matches:
            raise StudioError("Unknown paragraph in this section.")
        index = matches[0]
        section_state["current_index"] = index
        save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_pdf_locate(self, body: dict[str, Any]) -> None:
        try:
            page = int(body.get("page", 0))
            x = float(body.get("x", -1))
            y = float(body.get("y", -1))
        except (TypeError, ValueError) as exc:
            raise StudioError("PDF location must contain numeric page, x, and y.") from exc
        target = locate_pdf_source(page, x, y, load_state())
        self.send_json({"ok": True, "target": target})

    def handle_figure_generate(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        panel_id = self.require_panel(figure_id, body)
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if FIGURES[figure_id]["kind"] == "mechanism":
            raise StudioError("机制图必须先生成并确认设计 Prompt，再调用 GPT Image。")
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("该图已有任务正在运行。")
        instruction = str(body.get("agent_prompt", "")).strip()
        if len(instruction) > 8000:
            raise StudioError("数据图修改命令过长，请压缩到 8000 字符以内。")
        layout_prompt = str(body.get("layout_prompt", "")).strip()
        if len(layout_prompt) > 4000:
            raise StudioError("论文组合 Prompt 过长，请压缩到 4000 字符以内。")
        requested_width = str(body.get("layout_width", "single-column"))
        if requested_width not in {"single-column", "two-column"}:
            raise StudioError("插入论文宽度必须是单栏或双栏。")
        token = uuid.uuid4().hex
        figure_state.update(
            {
                "status": "agent_generating",
                "progress": 10,
                "progress_message": "正在启动本地 Agent…",
                "last_message": "",
                "approved_at": None,
                "agent_prompt": instruction,
                "layout_prompt": layout_prompt,
                "layout_prompt_is_default": not bool(layout_prompt),
                "requested_layout_width": requested_width,
                "composed_at": None,
            }
        )
        begin_figure_job(figure_state, token)
        figure_state.setdefault("panels", {}).setdefault(panel_id, {}).update(
            {
                "status": "agent_generating",
                "agent_prompt": instruction,
                "last_message": "",
                "progress": 10,
                "progress_message": "正在启动这张子图的本地 Agent…",
            }
        )
        save_state(state)
        threading.Thread(
            target=generate_data_figure_agent_worker,
            args=(figure_id, panel_id, token, instruction),
            daemon=True,
        ).start()
        self.send_json(
            {
                "ok": True,
                "message": f"本地 Agent 已启动，正在单独生成 {figure_id}({panel_id})。",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_compose(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        if FIGURES[figure_id]["kind"] != "data":
            raise StudioError("只有实验数据图需要本地 PDF 组合。")
        state = load_state()
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("该图已有任务正在运行。")
        prompt = str(body.get("layout_prompt", "")).strip()
        if not prompt:
            prompt = default_data_figure_layout_prompt(figure_id)
        requested_width = str(
            body.get(
                "layout_width",
                figure_state.get("requested_layout_width", "single-column"),
            )
        )
        if requested_width not in {"single-column", "two-column"}:
            raise StudioError("插入论文宽度必须是单栏或双栏。")
        if len(prompt) > 4000:
            raise StudioError("论文组合 Prompt 过长，请压缩到 4000 字符以内。")
        panels = figure_state.get("panels", {})
        missing = [
            item["id"]
            for item in FIGURES[figure_id].get("panels", [])
            if panels.get(item["id"], {}).get("status") != "built"
        ]
        if missing:
            raise StudioError("请先逐个生成子图：" + ", ".join(missing))
        layout = create_data_figure_layout_with_local_agent(figure_id, prompt)
        layout["width"] = requested_width
        message = compose_data_figure(figure_id, prompt, layout)
        figure_state.update(
            {
                "status": "built",
                "layout_prompt": prompt,
                "layout_prompt_is_default": False,
                "layout_plan": layout,
                "composed_at": int(time.time()),
                "layout_width": layout["width"],
                "requested_layout_width": requested_width,
                "approved_at": None,
                "revision": int(figure_state.get("revision", 0)) + 1,
                "last_message": message,
            }
        )
        save_state(state)
        self.send_json({"ok": True, "message": message, "state": public_state(state)})

    def handle_runtime_key(self, body: dict[str, Any]) -> None:
        if DEMO_MODE:
            raise StudioError("只读 Demo 不能更换 API Key；请先创建私有可编辑副本。")
        provider = str(body.get("provider", "openai")).strip().lower()
        key = str(body.get("api_key", ""))
        configuration = provider_configuration(provider)
        if not 8 <= len(key) <= 512 or any(
            character.isspace() or ord(character) < 32 for character in key
        ):
            raise StudioError("API Key 格式无效，请检查后重试。")
        os.environ[configuration["environment_variable"]] = key
        with STATE_LOCK:
            state = load_state()
            select_llm_provider(state, provider)
            save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": "API Key 已安全更新。",
                "state": public_state(state),
            }
        )

    def handle_figure_prompt(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("数据图不使用图像设计 Prompt。")
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("该图已有任务正在运行。")
        current_prompt = str(
            body.get("current_prompt", figure_state.get("draw_prompt", ""))
        ).strip()
        prompt_instruction = str(body.get("prompt_instruction", "")).strip()
        if len(prompt_instruction) > 4000:
            raise StudioError("Prompt 修改指令过长，请压缩到 4000 字符以内。")
        if current_prompt and not prompt_instruction:
            raise StudioError("重新生成 Prompt 前，请先填写希望 GPT 如何修改。")
        job_token = uuid.uuid4().hex
        figure_state.update(
            {
                "status": "prompt_generating",
                "progress": 5,
                "progress_message": "设计 Prompt 任务已开始…",
                "last_message": "",
                "prompt_approved_at": None,
                "draw_prompt": current_prompt,
                "prompt_instruction": prompt_instruction,
            }
        )
        begin_figure_job(figure_state, job_token)
        save_state(state)
        threading.Thread(
            target=generate_prompt_worker,
            args=(figure_id, job_token, prompt_instruction, current_prompt),
            daemon=True,
        ).start()
        self.send_json(
            {
                "ok": True,
                "message": "GPT 正在根据该 section 正文生成设计 Prompt。",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_draw(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("数据图不调用 GPT Image。")
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("该图已有任务正在运行。")
        prompt = str(body.get("draw_prompt", "")).strip()
        if not prompt:
            raise StudioError("请先让 GPT 生成设计 Prompt，并检查后确认。")
        if completed_mechanism_draft_matches_prompt(figure_id, prompt):
            paths = figure_paths(figure_id)
            previous_status = str(figure_state.get("status", ""))
            if previous_status not in {"built", "approved"}:
                previous_status = (
                    "built"
                    if paths["pptx"].exists() and paths["pdf"].exists()
                    else "draft"
                )
            figure_state.update(
                {
                    "status": previous_status,
                    "draw_prompt": prompt,
                    "progress": 100,
                    "progress_message": "Prompt 未变化，已复用上次 GPT Image。",
                    "last_message": (
                        "Prompt 与上次成功绘图完全相同；未调用 GPT Image，"
                        "继续显示原来的图。"
                    ),
                }
            )
            save_state(state)
            self.send_json(
                {
                    "ok": True,
                    "reused": True,
                    "message": figure_state["last_message"],
                    "state": public_state(state),
                }
            )
            return
        job_token = uuid.uuid4().hex
        now = int(time.time())
        figure_state.update(
            {
                "status": "image_generating",
                "draw_prompt": prompt,
                "prompt_approved_at": now,
                "progress": 5,
                "progress_message": "已确认设计 Prompt，GPT Image 任务正在排队…",
                "last_message": "",
                "approved_at": None,
            }
        )
        begin_figure_job(figure_state, job_token)
        save_state(state)
        threading.Thread(
            target=draw_figure_worker,
            args=(figure_id, job_token, prompt),
            daemon=True,
        ).start()
        self.send_json(
            {
                "ok": True,
                "message": "Prompt 已确认，GPT Image 正在生成草图。",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_cancel(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("数据图没有 GPT Image 调用可停止。")
        state = cancel_figure_job(figure_id)
        self.send_json(
            {
                "ok": True,
                "message": state["figures"][figure_id]["last_message"],
                "state": public_state(state),
            }
        )

    def handle_figure_build(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("数据图由可复现脚本直接构建，无需 PPT 重建步骤。")
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("该图已有任务正在运行。")
        token = uuid.uuid4().hex
        figure_state.update(
            {
                "status": "agent_generating",
                "progress": 10,
                "progress_message": "正在启动本地 Agent 重建可编辑机制图…",
                "approved_at": None,
                "last_message": "",
            }
        )
        begin_figure_job(figure_state, token)
        save_state(state)
        threading.Thread(
            target=build_mechanism_figure_worker,
            args=(figure_id, token),
            daemon=True,
        ).start()
        self.send_json(
            {
                "ok": True,
                "message": "本地 Agent 已启动，正在按 GPT Image 草图重建可编辑图。",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_approve(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        state = load_state()
        ready, reason = figure_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        paths = figure_paths(figure_id)
        if not paths["pdf"].exists():
            raise StudioError("请先生成最终 PDF。")
        if FIGURES[figure_id]["kind"] == "data" and not state["figures"][figure_id].get("composed_at"):
            raise StudioError("请先用论文组合 Prompt 生成最终组合 PDF。")
        if not paths["pptx"].exists():
            raise StudioError("插图缺少排版用的可编辑 PPTX，不能确认。")
        figure_state = state["figures"][figure_id]
        section = FIGURES[figure_id]["source_sections"][0]
        section_path = PAPER / "sections" / SECTION_MAP[section]["file"]
        previous_source = read_text(section_path, 100000)
        previous_status = figure_state.get("status")
        previous_approved_at = figure_state.get("approved_at")
        figure_state["status"] = "approved"
        figure_state["approved_at"] = int(time.time())
        section_source, _ = render_section_source(
            section, state["sections"][section], state["figures"], state["tables"]
        )
        temporary = section_path.with_suffix(".tex.tmp")
        temporary.write_text(section_source, encoding="utf-8")
        os.replace(temporary, section_path)
        compile_result = compile_paper()
        if not compile_result.ok:
            rollback = section_path.with_suffix(".tex.rollback")
            rollback.write_text(previous_source, encoding="utf-8")
            os.replace(rollback, section_path)
            figure_state["status"] = previous_status
            figure_state["approved_at"] = previous_approved_at
            compile_paper()
            raise StudioError(
                "LaTeX 插图编译失败；正文和图状态已回滚。\n" + compile_result.message
            )
        figure_state["last_message"] = (
            f"该图已插入 {SECTION_MAP[section]['title']}，正文引用已补充，PDF 已重新编译。"
        )
        state["compile"] = {
            "status": "ok",
            "message": compile_result.message,
            "updated_at": int(time.time()),
        }
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": figure_state["last_message"],
                "state": public_state(state),
            }
        )

    def handle_figure_caption_generate(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        current_caption = str(body.get("current_caption", "")).strip()
        prompt_instruction = str(body.get("prompt_instruction", "")).strip()
        if len(prompt_instruction) > 4000:
            raise StudioError("Caption Prompt 过长，请压缩到 4000 字符以内。")
        state = load_state()
        caption = generate_figure_caption(
            figure_id,
            state,
            current_caption or str(FIGURES[figure_id]["caption"]),
            prompt_instruction,
        )
        self.send_json(
            {
                "ok": True,
                "caption": caption,
                "message": "GPT Caption candidate 已生成；检查后请保存。",
            }
        )

    def handle_figure_caption(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        caption = str(body.get("caption", "")).strip()
        if not caption:
            raise StudioError("Caption 不能为空。")
        if len(caption) > 2000:
            raise StudioError("Caption 过长，请压缩到 2000 字符以内。")

        state = load_state()
        figure_state = state["figures"][figure_id]
        previous_caption = figure_state.get("caption")
        figure_state["caption"] = caption
        figure_state["last_message"] = "Caption 已保存。"

        if figure_state.get("status") == "approved":
            section = FIGURES[figure_id]["source_sections"][0]
            section_path = PAPER / "sections" / SECTION_MAP[section]["file"]
            previous_source = read_text(section_path, 100000)
            section_source, _ = render_section_source(
                section,
                state["sections"][section],
                state["figures"],
                state["tables"],
            )
            temporary = section_path.with_suffix(".tex.tmp")
            temporary.write_text(section_source, encoding="utf-8")
            os.replace(temporary, section_path)
            compile_result = compile_paper()
            if not compile_result.ok:
                rollback = section_path.with_suffix(".tex.rollback")
                rollback.write_text(previous_source, encoding="utf-8")
                os.replace(rollback, section_path)
                if previous_caption is None:
                    figure_state.pop("caption", None)
                else:
                    figure_state["caption"] = previous_caption
                compile_paper()
                raise StudioError(
                    "Caption 导致 LaTeX 编译失败；修改已回滚。\n"
                    + compile_result.message
                )
            state["compile"] = {
                "status": "ok",
                "message": compile_result.message,
                "updated_at": int(time.time()),
            }
            figure_state["last_message"] = "Caption 已保存并重新编译正文。"

        save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": figure_state["last_message"],
                "state": public_state(state),
            }
        )

    def handle_figure_placement(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        state = load_state()
        definition = FIGURES[figure_id]
        section = definition["source_sections"][0]
        placement_after = str(body.get("placement_after", "")).strip()
        paragraphs = state["sections"][section]["paragraphs"]
        paragraph = next(
            (item for item in paragraphs if item["id"] == placement_after), None
        )
        if paragraph is None:
            raise StudioError("所选自然段不属于该图绑定的 section。")
        if not paragraph.get("accepted_text"):
            raise StudioError(f"{placement_after} 尚未写入正文，不能把图放在它后面。")

        figure_state = state["figures"][figure_id]
        layout_mode = str(
            body.get("layout_mode", figure_state.get("layout_mode", "single-column"))
        )
        if layout_mode not in {"single-column", "two-column", "wrapfigure"}:
            raise StudioError("排版方式必须是单栏、双栏或 Wrapfigure。")
        if layout_mode == "wrapfigure":
            raise StudioError(
                "当前 AAAI 2026 官方模板禁止 wrapfig/Wrapfigure；"
                "请选择单栏或双栏，否则论文无法编译。"
            )
        previous_placement = figure_state.get("placement_after")
        previous_mode = figure_state.get("layout_mode")
        previous_width = figure_state.get("layout_width")
        previous_requested_width = figure_state.get("requested_layout_width")
        previous_plan = json.loads(json.dumps(figure_state.get("layout_plan", {})))
        figure_state["placement_after"] = placement_after
        figure_state["layout_mode"] = layout_mode
        requested_width = (
            "two-column" if layout_mode == "two-column" else "single-column"
        )
        figure_state["requested_layout_width"] = requested_width
        if (
            definition["kind"] == "data"
            and figure_state.get("composed_at")
            and figure_state.get("layout_plan")
        ):
            layout = json.loads(json.dumps(figure_state["layout_plan"]))
            layout["width"] = requested_width
            prompt = str(figure_state.get("layout_prompt", "")).strip()
            prompt = prompt or default_data_figure_layout_prompt(figure_id)
            compose_data_figure(figure_id, prompt, layout)
            figure_state["layout_plan"] = layout
            figure_state["layout_width"] = requested_width
            figure_state["composed_at"] = int(time.time())
        if figure_state.get("status") != "approved":
            figure_state["last_message"] = (
                f"插图位置已设为 {placement_after} 后，排版方式为 {layout_mode}；"
                "确认图片时会写入正文。"
            )
            save_state(state)
            self.send_json(
                {
                    "ok": True,
                    "message": figure_state["last_message"],
                    "state": public_state(state),
                }
            )
            return

        section_path = PAPER / "sections" / SECTION_MAP[section]["file"]
        previous_source = read_text(section_path, 100000)
        section_source, _ = render_section_source(
            section, state["sections"][section], state["figures"], state["tables"]
        )
        temporary = section_path.with_suffix(".tex.tmp")
        temporary.write_text(section_source, encoding="utf-8")
        os.replace(temporary, section_path)
        compile_result = compile_paper()
        if not compile_result.ok:
            rollback = section_path.with_suffix(".tex.rollback")
            rollback.write_text(previous_source, encoding="utf-8")
            os.replace(rollback, section_path)
            figure_state["placement_after"] = previous_placement
            figure_state["layout_mode"] = previous_mode
            figure_state["layout_width"] = previous_width
            figure_state["requested_layout_width"] = previous_requested_width
            figure_state["layout_plan"] = previous_plan
            compile_paper()
            raise StudioError(
                "移动插图后 LaTeX 编译失败；位置已回滚。\n" + compile_result.message
            )

        figure_state["last_message"] = (
            f"该图已移动到 {placement_after} 后，PDF 已重新编译。"
        )
        state["compile"] = {
            "status": "ok",
            "message": compile_result.message,
            "updated_at": int(time.time()),
        }
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": figure_state["last_message"],
                "state": public_state(state),
            }
        )

    def handle_table_generate(self, body: dict[str, Any]) -> None:
        table_id = self.require_table(body)
        state = load_state()
        ready, reason = table_gate(table_id, state)
        if not ready:
            raise StudioError(reason)
        table_state = state["tables"][table_id]
        prompt = str(
            body.get(
                "generation_prompt",
                table_state.get("generation_prompt", default_table_prompt(table_id)),
            )
        ).strip()
        if len(prompt) > 8000:
            raise StudioError("表格 Prompt 过长，请压缩到 8000 字符以内。")
        if table_state.get("status") == "agent_editing":
            raise StudioError("该表已有本地 Agent 任务正在运行。")
        token = uuid.uuid4().hex
        latex = str(table_state.get("latex", ""))
        instruction = (
            "根据以下规格生成一张完整的论文结果表初稿。完整覆盖可追溯结果，"
            "不要省略已有实验数字。\n\n" + prompt
        )
        table_state.update(
            {
                "generation_prompt": prompt,
                "status": "agent_editing",
                "agent_prompt": instruction,
                "progress": 10,
                "progress_message": "正在启动本地 Codex agent 生成表格初稿…",
                "last_message": "",
                "job_token": token,
                "job_started_at": int(time.time()),
                "approved_at": None,
            }
        )
        table_state["job_revision"] = int(table_state.get("job_revision", 0)) + 1
        save_state(state)
        threading.Thread(
            target=table_agent_worker,
            args=(table_id, token, latex, instruction),
            daemon=True,
        ).start()
        self.send_json(
            {
                "ok": True,
                "message": "本地 Agent 已启动，正在从可追溯结果生成 LaTeX 表格。",
                "state": public_state(state),
            },
            status=202,
        )

    def validate_table_latex(self, table_id: str, latex: str) -> str:
        return validate_table_latex_source(table_id, latex)

    def handle_table_agent_edit(self, body: dict[str, Any]) -> None:
        table_id = self.require_table(body)
        state = load_state()
        ready, reason = table_gate(table_id, state)
        if not ready:
            raise StudioError(reason)
        table_state = state["tables"][table_id]
        if table_state.get("status") == "agent_editing":
            raise StudioError("该表已有本地 Agent 修改任务正在运行。")
        latex = self.validate_table_latex(
            table_id, str(body.get("latex", table_state.get("latex", "")))
        )
        instruction = str(body.get("agent_prompt", "")).strip()
        if not instruction:
            raise StudioError("请填写给本地 Agent 的表格修改 Prompt。")
        if len(instruction) > 8000:
            raise StudioError("本地 Agent Prompt 过长，请压缩到 8000 字符以内。")
        token = uuid.uuid4().hex
        table_state.update(
            {
                "status": "agent_editing",
                "agent_prompt": instruction,
                "progress": 10,
                "progress_message": "正在启动本机 codex agent（只读 sandbox）…",
                "last_message": "",
                "job_token": token,
                "job_started_at": int(time.time()),
                "approved_at": None,
            }
        )
        table_state["job_revision"] = int(table_state.get("job_revision", 0)) + 1
        save_state(state)
        threading.Thread(
            target=table_agent_worker,
            args=(table_id, token, latex, instruction),
            daemon=True,
        ).start()
        self.send_json(
            {
                "ok": True,
                "message": "本地 Agent 已启动；没有调用 Paper Studio 的 GPT API。",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_table_save(self, body: dict[str, Any]) -> None:
        table_id = self.require_table(body)
        state = load_state()
        source = self.validate_table_latex(table_id, str(body.get("latex", "")))
        compile_table_preview(table_id, source)
        table_state = state["tables"][table_id]
        table_state["latex"] = source
        if table_state.get("status") == "approved":
            table_state["status"] = "built"
            table_state["approved_at"] = None
        table_state["revision"] = int(table_state.get("revision", 0)) + 1
        table_state["last_message"] = "表格 LaTeX 修改已保存；确认后才会写入正文。"
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": table_state["last_message"],
                "state": public_state(state),
            }
        )

    def handle_table_approve(self, body: dict[str, Any]) -> None:
        table_id = self.require_table(body)
        state = load_state()
        ready, reason = table_gate(table_id, state)
        if not ready:
            raise StudioError(reason)
        table_state = state["tables"][table_id]
        source = self.validate_table_latex(
            table_id, str(body.get("latex", table_state.get("latex", "")))
        )
        compile_table_preview(table_id, source)
        definition = TABLES[table_id]
        section = definition["source_sections"][0]
        section_path = PAPER / "sections" / SECTION_MAP[section]["file"]
        previous_source = read_text(section_path, 100000)
        previous_state = dict(table_state)
        table_state["latex"] = source
        table_state["status"] = "approved"
        table_state["approved_at"] = int(time.time())
        section_source, _ = render_section_source(
            section,
            state["sections"][section],
            state["figures"],
            state["tables"],
        )
        temporary = section_path.with_suffix(".tex.tmp")
        temporary.write_text(section_source, encoding="utf-8")
        os.replace(temporary, section_path)
        compile_result = compile_paper()
        if not compile_result.ok:
            rollback = section_path.with_suffix(".tex.rollback")
            rollback.write_text(previous_source, encoding="utf-8")
            os.replace(rollback, section_path)
            state["tables"][table_id] = previous_state
            compile_paper()
            state["tables"][table_id]["last_message"] = (
                "插入正文失败，表格和正文已回滚。\n" + compile_result.message
            )
            state["compile"] = {
                "status": "error",
                "message": compile_result.message,
                "updated_at": int(time.time()),
            }
            save_state(state)
            raise StudioError(
                "LaTeX 表格编译失败；正文和表格状态已回滚。\n"
                + compile_result.message
            )
        table_state["last_message"] = (
            f"该表已插入 {SECTION_MAP[section]['title']}，PDF 已重新编译。"
        )
        state["compile"] = {
            "status": "ok",
            "message": compile_result.message,
            "updated_at": int(time.time()),
        }
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": table_state["last_message"],
                "state": public_state(state),
            }
        )

    def handle_table_placement(self, body: dict[str, Any]) -> None:
        table_id = self.require_table(body)
        state = load_state()
        definition = TABLES[table_id]
        section = definition["source_sections"][0]
        placement_after = str(body.get("placement_after", "")).strip()
        paragraph = next(
            (
                item
                for item in state["sections"][section]["paragraphs"]
                if item["id"] == placement_after
            ),
            None,
        )
        if paragraph is None:
            raise StudioError("所选自然段不属于该表绑定的 section。")
        if not paragraph.get("accepted_text"):
            raise StudioError(f"{placement_after} 尚未写入正文，不能把表放在它后面。")
        table_state = state["tables"][table_id]
        previous_placement = table_state.get("placement_after")
        table_state["placement_after"] = placement_after
        if table_state.get("status") != "approved":
            table_state["last_message"] = (
                f"表格位置已设为 {placement_after} 后；确认表格时会写入正文。"
            )
            save_state(state)
            self.send_json(
                {
                    "ok": True,
                    "message": table_state["last_message"],
                    "state": public_state(state),
                }
            )
            return
        section_path = PAPER / "sections" / SECTION_MAP[section]["file"]
        previous_source = read_text(section_path, 100000)
        section_source, _ = render_section_source(
            section,
            state["sections"][section],
            state["figures"],
            state["tables"],
        )
        temporary = section_path.with_suffix(".tex.tmp")
        temporary.write_text(section_source, encoding="utf-8")
        os.replace(temporary, section_path)
        compile_result = compile_paper()
        if not compile_result.ok:
            rollback = section_path.with_suffix(".tex.rollback")
            rollback.write_text(previous_source, encoding="utf-8")
            os.replace(rollback, section_path)
            table_state["placement_after"] = previous_placement
            compile_paper()
            raise StudioError(
                "移动表格后 LaTeX 编译失败；位置已回滚。\n" + compile_result.message
            )
        table_state["last_message"] = (
            f"该表已移动到 {placement_after} 后，PDF 已重新编译。"
        )
        state["compile"] = {
            "status": "ok",
            "message": compile_result.message,
            "updated_at": int(time.time()),
        }
        save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": table_state["last_message"],
                "state": public_state(state),
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Paper Studio.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--direct-full-draft",
        action="store_true",
        help="Generate every pending paragraph and compile without opening Paper Studio.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Model for --direct-full-draft (defaults to persisted state or PAPER_STUDIO_MODEL).",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "deepseek"),
        default="",
        help="Text API selected in the terminal before Paper Studio starts.",
    )
    parser.add_argument(
        "--validate-project",
        action="store_true",
        help="Validate project config, paragraph plan, and artifact bindings, then exit.",
    )
    parser.add_argument(
        "--empty",
        action="store_true",
        help="Start the permanent Paper Studio shell without loading paper/ project data.",
    )
    args = parser.parse_args()

    validate_project_workspace()
    if args.validate_project:
        print("PASS: Paper Studio project preflight")
        return
    if args.direct_full_draft:
        try:
            if not args.provider:
                raise StudioError(
                    "终端全文写作必须先询问使用哪个 API，然后显式传入 "
                    "--provider openai 或 --provider deepseek。"
                )
            state = load_state()
            if select_llm_provider(state, args.provider):
                save_state(state)
            model = str(args.model or state.get("model") or DEFAULT_MODEL).strip()
            run_direct_full_draft(model)
        except StudioError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
        return
    if args.provider or args.model:
        state = load_state()
        if args.provider:
            select_llm_provider(state, args.provider)
        if args.model:
            state["model"] = args.model.strip()
        save_state(state)
    if not EMPTY_PROJECT_MODE:
        recover_interrupted_figure_jobs()
        recover_interrupted_table_jobs()
        state = load_state()
        prose_changed = synchronize_paragraph_editors_from_manuscript(state)
        artifacts_changed = synchronize_artifact_workbenches_from_manuscript(
            state, build_table_previews=True
        )
        if prose_changed or artifacts_changed:
            save_state(state)
    server = StudioHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Paper Studio: {url}")
    print(f"Workspace: {ROOT}")
    print(f"Model: {load_state().get('model') or DEFAULT_MODEL}")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def stop_for_sigterm(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_for_sigterm)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPaper Studio stopped.")
    finally:
        server.server_close()
        signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == "__main__":
    main()
