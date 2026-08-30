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
import math
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
import zipfile
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from research_avatar.survey_bibliography import verified_survey_bibliography

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
REFERENCE_CONTEXT_FILE = PAPER / "reference_context.json"
LITERATURE_SURVEY_FILE = ROOT / "reports" / "01_LIT_SURVEY.html"
EXPERIMENT_PLAN_FILE = ROOT / "reports" / "03_EXPERIMENT_PLAN.html"
FIGURE_DIR = PAPER / "fig"
FIGURE_SOURCE_DIR = PAPER / "figsrc"
DATA_FIGURE_AGENT_DIR = FIGURE_SOURCE_DIR / "data_agents"
PPT_COMPOSER = Path(__file__).resolve().parent / "ppt_compose.mjs"
TABLE_PREVIEW_DIR = STATE_DIR / "table_previews"
PAPER_PAGE_DIR = STATE_DIR / "paper_pages"
FIGURE_TOOL = PACKAGE_ROOT / "tools" / "figure_ppt.py"
PROJECT_CONFIG_FILE = PAPER / "paper_studio.json"
DEFAULT_MODEL = os.environ.get("PAPER_STUDIO_MODEL", "gpt-5-nano")
DEFAULT_PROVIDER = os.environ.get("PAPER_STUDIO_PROVIDER", "deepseek").strip().lower()
ONLINE_PROJECT_MODE = os.environ.get("PAPER_STUDIO_ONLINE", "").lower() in {
    "1",
    "true",
    "yes",
}
EMBEDDED_ONLY = os.environ.get("PAPER_STUDIO_EMBEDDED_ONLY", "").lower() in {
    "1",
    "true",
    "yes",
}
EMBEDDED_PROXY_TOKEN = os.environ.get("PAPER_STUDIO_PROXY_TOKEN", "")
ONLINE_DISABLED_ARTIFACT_AGENT_PATHS = {
    # These all spawn a local Codex CLI subprocess, which the shared online
    # container never runs. "/api/table/generate" is deliberately absent:
    # a real user reported that clicking to generate a table did nothing
    # online, because it too routed through the Agent unconditionally even
    # though its only real job (the default case) is generate_table_latex's
    # deterministic structured-prompt parser -- the same safe, non-Agent
    # path materialize_batch_artifacts() already relies on.
    # handle_table_generate branches on ONLINE_PROJECT_MODE to use that
    # path directly online instead of the Agent. "/api/table/agent-edit"
    # stays blocked: it interprets an arbitrary free-text revision
    # instruction against already-approved LaTeX, which has no deterministic
    # substitute.
    #
    # "/api/figure/generate" and "/api/figure/panel/generate" are also
    # deliberately absent for the same reason: a "data" kind figure's only
    # job is one chart drawn straight from data_grid records, which
    # render_data_figure_deterministic already does without any Agent or
    # pdfcrop/node/latexmk composition toolchain. handle_figure_generate
    # branches on ONLINE_PROJECT_MODE to use that path online. Mechanism
    # figures (design-Prompt-driven PPTX reconstruction) and multi-panel
    # composition have no deterministic substitute and stay blocked below.
    "/api/figure/build",
    "/api/figure/compose",
    "/api/table/agent-edit",
}
ONLINE_PLACEHOLDER_FIGURE_MESSAGE = (
    "Online version retains that figure position as a placeholder with caption and label, not providing formal plotting."
    "For full functionality, download the project ZIP and use it in the local version."
)
ONLINE_PLACEHOLDER_TABLE_MESSAGE = (
    "Online version retains that table position as a placeholder with caption and label, not providing table generation."
    "For full functionality, download the project ZIP and use it in the local version."
)
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


def model_for_provider(provider: str, requested: str = "") -> str:
    """Return a provider-compatible model, never a stale cross-provider value."""
    candidate = requested.strip()
    compatible = (
        candidate.startswith("gpt-")
        if provider == "openai"
        else candidate.startswith("deepseek-")
        if provider == "deepseek"
        else False
    )
    return candidate if compatible else PROVIDER_DEFAULT_MODELS[provider]
# A method figure can require image inspection plus a 30–50 object native-shape
# plan. Two minutes regularly terminates a healthy local Agent just before it
# returns JSON, especially when two figures are reconstructed concurrently.
MECHANISM_AGENT_TIMEOUT_SECONDS = 300
API_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
API_URL += "/responses"
API_KEY_ENVIRONMENT_VARIABLE = "OPENAI_API_KEY"
API_KEY_SETUP_LOCATION = "Launch Paper Studio native terminal."
API_KEY_SETUP_COMMAND = 'export OPENAI_API_KEY="Paste your API key."'
API_KEY_RESTART_COMMAND = "python3 -m research_avatar.paper_studio.server"
CHAT_HISTORY_LOCK = threading.RLock()
CHAT_RESPONSE_HISTORIES: dict[str, list[dict[str, str]]] = {}
STATE_LOCK = threading.RLock()
FIGURE_PROCESS_LOCK = threading.RLock()
RUNNING_FIGURE_PROCESSES: dict[str, subprocess.Popen[str]] = {}
CANCELLED_FIGURE_JOBS: set[str] = set()
DRAFT_BATCH_JOB_LOCK = threading.RLock()
FULL_DRAFT_JOB_LOCK = DRAFT_BATCH_JOB_LOCK
CANCELLED_FULL_DRAFT_JOBS: set[str] = set()
SECTION_DRAFT_JOB_LOCK = DRAFT_BATCH_JOB_LOCK
CANCELLED_SECTION_DRAFT_JOBS: set[str] = set()
# Serializes latexmk/bibtex runs against PAPER. The HTTP server is
# threaded, and multiple callers can trigger a compile concurrently (the
# explicit Compile PDF button, the pdf/locate auto-rebuild fallback, a
# batch-writing job) -- on the shared, long-lived Demo session in
# particular, two overlapping compiles racing on the same main.aux/main.bbl
# can corrupt each other's intermediate files well enough to produce a
# "missing \item" fatal error on an otherwise-correct manuscript.
COMPILE_LOCK = threading.RLock()
AUTOMATIC_MECHANISM_FINALIZE_LOCK = threading.RLock()
SERVER_INSTANCE_TOKEN = uuid.uuid4().hex
BIBLIOGRAPHY_PROMPT_MAX_CHARS = 8000
BIBLIOGRAPHY_PROMPT_MIN_RECORDS = 8
# Paragraph writing is intentionally cost-bounded. These are character limits,
# so they remain deterministic across providers and tokenizers.
PAPER_TEXT_PROMPT_MAX_CHARS = 55_000
MANUSCRIPT_DASH_RULE = (
    "Do not use em dashes (—), en dashes (–), or LaTeX double/triple hyphens "
    "(-- or ---) as punctuation in manuscript prose. Rewrite with a comma, colon, "
    "semicolon, parentheses, or a separate sentence. A single hyphen in an established "
    "compound term and a minus sign inside LaTeX math are allowed."
)
FIGURE_CAPTION_MAX_WORDS = 40
FIGURE_CAPTION_MAX_CHARS = 500
PAPER_TEXT_CONTEXT_LIMITS = {
    "outline": 5_000,
    "working_abstract": 2_000,
    "writing_style": 2_500,
    "section_evidence": 10_000,
    "current_section": 5_000,
    "current_candidate": 4_000,
    "architecture": 3_500,
    "reference_context": 3_500,
    "bound_artifacts": 3_500,
    "researcher_comment": 2_500,
    "purpose": 2_500,
}
DEEPSEEK_PAPER_MAX_OUTPUT_TOKENS = int(
    os.environ.get("DEEPSEEK_PAPER_MAX_OUTPUT_TOKENS", "1600")
)


class StudioHTTPServer(ThreadingHTTPServer):
    """Threaded local server with enough backlog for browser asset bursts."""

    request_queue_size = 64


class ProjectConfigError(RuntimeError):
    """Raised when paper/paper_studio.json cannot safely drive the fixed Studio engine."""


def process_is_alive(pid: object) -> bool:
    """Return whether a persisted local worker process still exists."""
    try:
        numeric_pid = int(pid)
        if numeric_pid <= 0:
            return False
        os.kill(numeric_pid, 0)
    except (TypeError, ValueError, OSError):
        return False
    return True


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
        if str(section.get("writing_mode", "draft")) not in {"draft", "plan_only"}:
            raise ProjectConfigError(
                f"sections[{index}].writing_mode must be draft or plan_only"
            )
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
            # Experiment-plan shells sometimes use the artifact id as a temporary
            # description/caption.  That token is useful while planning but is not
            # publication prose.  Promote the already-approved artifact title to a
            # one-sentence caption before any state or LaTeX is created.
            title = str(definition.get("title") or "").strip()
            for field in ("description", "caption"):
                value = str(definition.get(field) or "").strip()
                if value.casefold() == str(artifact_id).casefold():
                    definition[field] = title + ("." if field == "caption" and not title.endswith(".") else "")
            unknown_sections = set(definition["source_sections"]) - set(section_ids)
            if unknown_sections:
                raise ProjectConfigError(
                    f"{kind}.{artifact_id} references unknown sections: {sorted(unknown_sections)}"
                )
            panel_ids = [str(item.get("id", "")) for item in definition.get("panels", [])]
            if len(panel_ids) != len(set(panel_ids)) or any(not item for item in panel_ids):
                raise ProjectConfigError(f"{kind}.{artifact_id} panel ids must be unique")
            if kind == "figures" and "include_scale" in definition:
                scale = definition["include_scale"]
                if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not 0.5 <= float(scale) <= 1.0:
                    raise ProjectConfigError(
                        f"figures.{artifact_id}.include_scale must be between 0.5 and 1.0"
                    )
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
    for field in ("metrics", "main"):
        value = str(paths.get(field, "")).strip()
        if not value:
            raise ProjectConfigError(f"paper_studio.json paths.{field} is required")
        resolved = _project_path(root, value, f"paths.{field}")
        if not resolved.is_file():
            raise ProjectConfigError(f"paper_studio.json paths.{field} does not exist: {value}")
        resolved_paths[field] = resolved
    if len(set(resolved_paths.values())) != 2:
        raise ProjectConfigError("paper_studio.json main and metrics paths must be distinct")
    if resolved_paths["main"].suffix.lower() != ".tex" or r"\begin{document}" not in resolved_paths[
        "main"
    ].read_text(encoding="utf-8", errors="replace"):
        raise ProjectConfigError("paper_studio.json paths.main must be a LaTeX document entry point")
    try:
        metrics_payload = json.loads(resolved_paths["metrics"].read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectConfigError("paper_studio.json paths.metrics must contain valid JSON") from exc
    if not isinstance(metrics_payload, (dict, list)) or not metrics_payload:
        raise ProjectConfigError("paper_studio.json paths.metrics must contain a non-empty JSON object or list")
    target = project.get("target")
    reference_paper = project.get("reference_paper")
    decision_source = str(project.get("decision_source", "")).strip()
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
    if (
        decision_source != "lightweight-onboarding"
        and (
            not isinstance(reference_paper, dict)
            or not str(reference_paper.get("title", "")).strip()
        )
    ):
        raise ProjectConfigError(
            "paper_studio.json project.reference_paper.title must identify the "
            "structural reference selected before paper writing"
        )
    if not decision_source:
        raise ProjectConfigError(
            "paper_studio.json project.decision_source must name the approved "
            "HTML contract that selected the venue and reference paper"
        )
    return config


EMPTY_PROJECT_MODE = "--empty" in sys.argv or not PROJECT_CONFIG_FILE.exists()


def project_files_ready() -> bool:
    """Return whether the project config and its approved paragraph architecture load."""
    if not PROJECT_CONFIG_FILE.is_file():
        return False
    try:
        return bool(paragraph_plan().get("sections"))
    except (OSError, ValueError, ProjectConfigError, StudioError):
        return False


def empty_project_config() -> dict[str, Any]:
    """Built-in shell configuration; it contains no paper-specific content."""
    return {
        "schema_version": "1.0",
        "project": {
            "id": "__paper_studio_empty__",
            "name": "",
            "eyebrow": "PAPER STUDIO",
            "studio_title": "Paper Studio",
            "subtitle": "Waiting for loading paper project data",
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
        "writing_mode": str(item.get("writing_mode", "draft")),
        "length_share": item.get("length_share"),
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


def draft_writing_order() -> list[str]:
    """Return only sections allowed to produce manuscript prose."""
    return [
        section
        for section in batch_writing_order()
        if SECTION_MAP.get(section, {}).get("writing_mode") != "plan_only"
    ]


def default_table_prompt(table_id: str) -> str:
    """Return the editable, deterministic writing brief for a result table."""
    definition = TABLES[table_id]
    prompt = definition.get("prompt", {})
    return "\n".join(
        [
            f"Data source: {PROJECT_CONFIG['paths']['metrics']}",
            f"Column: {prompt.get('columns', '')}",
            f"Row: {prompt.get('rows', 'source')}",
            f"Caption: {definition['caption']}",
            f"Font size: {prompt.get('font_size', 'small')}",
            f"Optimal value: {prompt.get('best_values', 'none')}",
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
            "[Restored design specification｜Original generation Prompt not archived.]",
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
            "[Restored drawing description｜Original Agent Prompt is not archived.]",
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
    """Recognize both the marker and the canonical outline approval record."""
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
    metrics = metrics_bundle()
    fixture = metrics.get("fixture", {}) if isinstance(metrics, dict) else {}
    for artifact_id in artifact_ids or []:
        if artifact_id in FIGURES:
            definition = FIGURES[artifact_id]
            figure_state = (figure_states or {}).get(artifact_id, {})
            evidence = {
                str(key): result_path_value(metrics, str(key))
                for key in definition.get("result_keys", [])
                if has_result_path(metrics, str(key))
            }
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
                    "fixture": fixture,
                    "traceable_results": evidence,
                    "required_reference": (
                        f"Figure~\\ref{{{definition['label']}}}"
                    ),
                }
            )
        elif artifact_id in TABLES:
            definition = TABLES[artifact_id]
            grid = definition.get("data_grid", {})
            grid_path = str(grid.get("path") or "") if isinstance(grid, dict) else ""
            evidence = (
                {grid_path: result_path_value(metrics, grid_path)}
                if grid_path and has_result_path(metrics, grid_path)
                else {}
            )
            context.append(
                {
                    "id": artifact_id,
                    "kind": "table",
                    "title": definition["title"],
                    "description": definition["description"],
                    "caption": definition["caption"],
                    "label": definition["label"],
                    "fixture": fixture,
                    "traceable_results": evidence,
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
            "missing " + ", ".join(item["required_reference"] for item in issues["missing"])
        )
    if issues["repeated"]:
        details.append(
            "Repeated in the same paragraph "
            + ", ".join(
                f"{item['required_reference']}({item['count']} times)"
                for item in issues["repeated"]
            )
        )
    if issues["unexpected"]:
        details.append(
            "This paragraph is not bound. "
            + ", ".join(item["required_reference"] for item in issues["unexpected"])
        )
    if not details:
        return ""
    return (
        "Chart references do not conform to the approved paragraph structure."
        + "; ".join(details)
        + ".Each bound figure must be cited exactly once in this section; when citing again in other sections,"
        "First explicitly bind in the target paragraph of the experimental plan."
    )


def configured_manuscript_labels() -> set[str]:
    """Return every project-owned label that prose may reference directly."""
    labels = {
        str(definition.get("label") or "")
        for definition in [*FIGURES.values(), *TABLES.values()]
    }
    for metadata in SECTION_MAP.values():
        labels.update(
            {
                str(metadata.get("start_label") or ""),
                str(metadata.get("end_label") or ""),
            }
        )
    return {label for label in labels if label}


def unsupported_internal_reference_issues(text: str) -> list[str]:
    """Reject model-invented refs while permitting labels defined in the paragraph."""
    allowed = configured_manuscript_labels()
    allowed.update(re.findall(r"\\label\{([^{}]+)\}", text))
    referenced = re.findall(r"\\(?:ref|pageref|autoref)\{([^{}]+)\}", text)
    return [
        f"unsupported internal reference: {label}"
        for label in dict.fromkeys(referenced)
        if label not in allowed
    ]
FIGURE_PROMPT_INSTRUCTIONS = """You design non-data figures for ACL-family NLP papers. Read the supplied evidence, determine the figure's rhetorical type, and return one complete production-ready image-generation prompt. Return only that prompt.

First state one scientific message internally, then select the smallest visual grammar that communicates it. Obey the supplied <acl_figure_type_profile>; do not collapse motivation, architecture, method, and agent-interaction figures into the same generic box-and-arrow diagram. Use concrete manuscript objects such as tokens, prompts, hidden states, modules, vectors, documents, agents, messages, or outputs. Preserve object identity across stages and make each transformation visually inspectable.

Treat the profile's visual_signature as a hard art-direction constraint. Read <cross_figure_distinction> and make this figure visibly different from every sibling mechanism figure: do not reuse its panel geometry, dominant object family, or information density. In particular, an Introduction figure must remain semantic and immediately readable without exposing the model internals that belong in a model or mechanism figure.

Match recurring ACL conventions: pure white background; publication-ready editable-vector appearance; flat fills; thin dark strokes; compact alignment; generous whitespace; precise sans-serif labels; restrained colorblind-safe accents; repeated shapes for repeated scientific entities; solid arrows for primary flow and dashed arrows only for a different, explicitly named relation. Use color to reinforce meaning, never as the only distinction. Avoid decorative poster art, photorealism, people, scenery, mascots, gradients, glow, glass, 3D depth, heavy shadows, marketing graphics, large title cards, and empirical result plots.

Apply a cold-reader gate. From the figure and one-sentence caption alone, a researcher must identify the input or compared states, the proposed operation, the output, and the paper-specific difference. Every arrow and visual object must correspond to the supplied evidence. Do not invent modules, claims, outcomes, numerical results, or causal relations. Keep labels short and print-readable at the target column width; put explanations in the caption, not inside the figure. When the evidence contains a symbol_registry, copy its glyphs and meanings exactly: do not introduce aliases, rename a threshold, or use a different owner/source symbol in the figure than in the manuscript.

Audit the internal logic of the visual before returning. Outcomes that differ must not be labeled equal or identical; a wrong outcome must not be counted as correct. A non-data figure may not contain a percentage, score, sample count, or aggregate result, even as a hypothetical decoration. Preserve identity consistently: unchanged objects may move or be relabeled, but do not describe two distinct outputs as the same semantic object. If the supplied prose is internally inconsistent, omit the inconsistent claim and visualize only the smallest supported contrast.

The supplied format and type profiles are mandatory. Restate the canvas, column target, composition, object inventory, reading order, label budget, palette roles, line semantics, and prohibited content in the final image-generation prompt. On revision turns, preserve correct prior decisions while applying the latest instruction. Do not mention named drawing software; describe the visible result rather than a tool-specific style."""


ACL_FIGURE_TYPE_PROFILES: dict[str, dict[str, Any]] = {
    "motivation_contrast": {
        "role": "Introduction or motivation figure",
        "message_pattern": "one concrete setup, two visibly comparable cases, one bounded takeaway",
        "visual_signature": "semantic example cards and large comparison paths, not an internal model diagram",
        "composition": "two spacious matched cases with one concrete semantic anchor; comparison before mechanism detail",
        "object_grammar": [
            "a concrete prompt, behavior-control card, response bubble, or task object",
            "matched branches that preserve common context",
            "one highlighted structural difference per branch",
            "short outcome or diagnostic symbols without result numbers",
            "equivalent alternatives drawn in parallel and converging on one shared outcome",
        ],
        "reading_order": "shared setup, contrasted cases, takeaway",
        "avoid": [
            "full model stack",
            "dense implementation detail",
            "Jacobians, layer stacks, tensor grids, or repeated internal model blocks",
            "more than six labels unless the manuscript example requires literal text",
            "decorative metaphor",
            "generic problem versus solution title cards",
            "a causal arrow between two cases that are claimed to be equal alternatives",
        ],
    },
    "model_architecture": {
        "role": "Model or module architecture figure",
        "message_pattern": "stable outer structure with the proposed internal change made locally explicit",
        "visual_signature": "formal technical modules, repeated state geometry, named interfaces, and operator-level flow",
        "composition": "aligned baseline-to-proposed panels or one nested architecture with a magnified module",
        "object_grammar": [
            "repeated modules drawn with identical geometry",
            "tokens or tensors entering and leaving named interfaces",
            "routing, aggregation, residual, or attention relations with distinct line semantics",
            "a compact legend only when colors encode module classes",
        ],
        "reading_order": "input interface, internal structure, output interface",
        "avoid": [
            "narrative example text",
            "unexplained icons",
            "stage numbering when the computation is not sequential",
            "changing shape vocabulary between equivalent modules",
        ],
    },
    "method_workflow": {
        "role": "Method, training, inference, or measurement workflow",
        "message_pattern": "trace one recognizable data object through paper-specific transformations",
        "visual_signature": "recognizable artifacts transformed through numbered or clearly ordered stages",
        "composition": "left-to-right or top-to-bottom stages with a single dominant path and explicit optional loop",
        "object_grammar": [
            "real input and output artifacts rather than abstract Start and End boxes",
            "stage-local transformations shown inside or beside their module",
            "preserved examples or token/state snippets that reveal what changes",
            "feedback arrows only when the method actually iterates",
        ],
        "reading_order": "input, ordered transformations, output or diagnostic",
        "avoid": [
            "equal-sized generic boxes for semantically different objects",
            "paragraphs inside the figure",
            "multiple competing reading directions",
            "arrows without named source and target roles",
        ],
    },
    "agent_interaction": {
        "role": "Agent, tool-use, retrieval, or environment interaction figure",
        "message_pattern": "show who owns each state, what message moves, and where control returns",
        "visual_signature": "spatially distinct actors and stores joined by labeled message handoffs and feedback",
        "composition": "entity lanes or spatially separated actors connected by labeled request, result, and feedback paths",
        "object_grammar": [
            "distinct actors or stores with stable visual identities",
            "message artifacts placed on arrows or at handoff boundaries",
            "external tools, memory, or environment separated from the reasoning controller",
            "loops with an explicit continuation or stopping condition",
        ],
        "reading_order": "request, dispatch, external action, returned evidence, updated reasoning",
        "avoid": [
            "logo collage without information flow",
            "unlabeled bidirectional arrows",
            "placing all agents in identical anonymous boxes",
            "implying parallelism when calls are sequential",
        ],
    },
}


class StudioError(Exception):
    """A user-actionable Studio error."""


def generate_figure_caption(
    figure_id: str,
    state: dict[str, Any],
    current_caption: str,
    prompt_instruction: str,
    trigger_paragraph: dict[str, str] | None = None,
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
    synthetic = "[SYNTHETIC]" in current_caption or any(
        isinstance(value, dict) and value.get("synthetic") is True
        for value in evidence.values()
    )
    context = {
        "id": figure_id,
        "title": definition["title"],
        "description": definition["description"],
        "label": definition["label"],
        "panels": definition.get("panels", []),
        "layout_plan": figure_state.get("layout_plan", {}),
        "current_caption": current_caption,
        "researcher_instruction": prompt_instruction,
        "trigger_paragraph": trigger_paragraph or {},
        "bound_manuscript_prose": {
            section: state.get("sections", {}).get(section, {}).get("accepted_text", "")
            for section in definition.get("source_sections", [])
        },
        "traceable_results": evidence,
    }
    payload = {
        "model": str(state.get("model") or DEFAULT_MODEL),
        "store": False,
        "instructions": (
            "Write exactly one concise, publication-ready English sentence as the figure "
            "caption, grounded only "
            "in the supplied figure context and traceable results. Follow the researcher's "
            f"instruction. Use no more than {FIGURE_CAPTION_MAX_WORDS} words, with no minimum "
            "length. State only what the "
            "figure shows, the panel mapping when needed, and the minimum metric or condition "
            "definition needed to interpret it. Do not repeat the manuscript motivation, "
            "method narrative, contribution list, or every limitation. Do not invent "
            "measurements. Return only the caption "
            "text: no Markdown, no commentary, no leading Figure/Fig. number, and no LaTeX "
            "caption wrapper. Emit pdflatex-safe prose: put mathematical notation inside "
            "\\(...\\), use ASCII LaTeX commands instead of Unicode math glyphs or "
            "superscripts, and escape percent signs. Preserve the "
            "literal [SYNTHETIC] marker whenever the context contains synthetic data. "
            "Audit logical consistency before returning: outcomes that differ cannot be "
            "called identical, a wrong outcome cannot be called correct, and an average "
            "cannot contradict the outcomes being averaged. For a non-data figure, do "
            "not introduce a percentage, score, count, or empirical aggregate absent "
            "from traceable results. "
            f"For this figure, synthetic marker required is {str(synthetic).lower()}; "
            "include [SYNTHETIC] if and only if that value is true. "
            + MANUSCRIPT_DASH_RULE
        ),
        "input": json.dumps(context, ensure_ascii=False, indent=2)[:24000],
    }
    response = post_openai(payload)
    caption = normalize_figure_caption_text(extract_output_text(response))
    if not caption:
        raise StudioError("GPT No usable caption returned.")
    if not synthetic:
        caption = caption.replace("[SYNTHETIC]", "").strip()
    if synthetic and "[SYNTHETIC]" not in caption:
        caption = "[SYNTHETIC] " + caption
    if figure_caption_issues(caption):
        repair = post_openai(
            {
                "model": str(state.get("model") or DEFAULT_MODEL),
                "store": False,
                "instructions": (
                    "Compress and polish one academic figure caption into exactly one "
                    "sentence. Return only the caption, with at most "
                    f"{FIGURE_CAPTION_MAX_WORDS} words and "
                    f"{FIGURE_CAPTION_MAX_CHARS} characters. Preserve all supplied facts, "
                    "panel mappings, citation-free metric definitions, and the literal "
                    "[SYNTHETIC] marker when present. Remove manuscript motivation, repeated "
                    "method explanation, contribution claims, leading Figure/Fig. numbering, "
                    "and commentary. Emit pdflatex-safe prose: put all notation inside "
                    "\\(...\\), replace Unicode math glyphs and superscripts with LaTeX, "
                    "and escape percent signs. Do not invent information. "
                    + MANUSCRIPT_DASH_RULE
                ),
                "input": f"<caption_to_compress>{caption}</caption_to_compress>",
            }
        )
        caption = normalize_figure_caption_text(extract_output_text(repair))
        if synthetic and caption and "[SYNTHETIC]" not in caption:
            caption = "[SYNTHETIC] " + caption
        if not synthetic:
            caption = caption.replace("[SYNTHETIC]", "").strip()
    caption = enforce_figure_caption_bounds(caption)
    remaining_issues = figure_caption_issues(caption)
    if remaining_issues:
        raise StudioError(
            "GPT Caption Automatic compression still violates length or punctuation constraints."
            + "; ".join(remaining_issues)
        )
    return caption


def normalize_figure_caption_text(source: str) -> str:
    caption = " ".join(source.split()).strip()
    if caption.startswith("\\caption{") and caption.endswith("}"):
        caption = caption[len("\\caption{") : -1].strip()
    caption = re.sub(
        r"^(?:Figure|Fig\.)\s+\d+[A-Za-z]?\s*[:.]\s*",
        "",
        caption,
        flags=re.IGNORECASE,
    )
    # The model occasionally ignores the no-dash instruction even on its
    # compression pass.  Normalize punctuation deterministically so approval
    # cannot oscillate on repeated API calls.  Compact numeric/alphanumeric
    # spans represent ranges; spaced marks represent sentence punctuation.
    caption = re.sub(r"(?<=\w)[—–](?=\w)", " to ", caption)
    caption = re.sub(r"\s*[—–]\s*", "; ", caption)
    caption = re.sub(r"\s*-{2,}\s*", "; ", caption)
    return re.sub(r"\s+([,.;:!?])", r"\1", caption).strip()


def enforce_figure_caption_bounds(caption: str) -> str:
    """Deterministically enforce the one-sentence/word cap after API repair.

    This is a final formatting fallback, not another content-generation pass.  It
    joins accidental sentence boundaries and, only when necessary, removes the
    trailing surplus words while preserving balanced LaTeX delimiters.
    """
    bounded = normalize_figure_caption_text(caption)
    bounded = re.sub(
        r"(?<=[.!?])\s+(?=[A-Z0-9\[])",
        "; ",
        bounded,
    )
    words = list(re.finditer(r"\b[\w']+\b", bounded, flags=re.UNICODE))
    if len(words) > FIGURE_CAPTION_MAX_WORDS:
        cutoff = words[FIGURE_CAPTION_MAX_WORDS].start()
        candidate = bounded[:cutoff].rstrip(" ,;:")
        # Prefer a complete leading clause to a word-count slice that can end
        # midway through a range or comparison (for example, "from ... to.").
        bracket_depth = 0
        clause_break = -1
        for index, character in enumerate(candidate):
            if character == "[":
                bracket_depth += 1
            elif character == "]" and bracket_depth:
                bracket_depth -= 1
            elif character in ",;" and bracket_depth == 0:
                clause_break = index
        if clause_break >= max(24, len(candidate) // 3):
            candidate = candidate[:clause_break].rstrip(" ,;:")
        # Never keep a mechanically truncated suffix that breaks math or braces.
        while candidate and (
            candidate.count(r"\(") != candidate.count(r"\)")
            or candidate.count("{") != candidate.count("}")
            or candidate.count("[") != candidate.count("]")
        ):
            candidate = candidate.rsplit(" ", 1)[0].rstrip(" ,;:")
        if candidate:
            bounded = candidate
    bounded = bounded.rstrip(".;:!? ")
    while re.search(r"\b(?:to|from|and|or|versus|with|of)$", bounded, re.I):
        bounded = bounded.rsplit(" ", 1)[0].rstrip(" ,;:")
    bounded += "."
    return bounded


def figure_caption_issues(caption: str) -> list[str]:
    issues: list[str] = []
    word_count = len(re.findall(r"\b[\w']+\b", caption, flags=re.UNICODE))
    if word_count > FIGURE_CAPTION_MAX_WORDS:
        issues.append(f"{word_count} words exceeds {FIGURE_CAPTION_MAX_WORDS}")
    if len(caption) > FIGURE_CAPTION_MAX_CHARS:
        issues.append(f"{len(caption)} characters exceeds {FIGURE_CAPTION_MAX_CHARS}")
    sentence_parts = [
        part
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\[])", caption.strip())
        if part.strip()
    ]
    if len(sentence_parts) != 1:
        issues.append(f"{len(sentence_parts)} sentences; exactly one is required")
    if "—" in caption or "–" in caption or re.search(r"-{2,}", caption):
        issues.append("contains forbidden dash punctuation")
    if re.search(r"\b(?:to|from|and|or|versus|with|of)\.$", caption, re.I):
        issues.append("ends with an incomplete clause")
    if caption.count("[") != caption.count("]"):
        issues.append("contains unbalanced square brackets")
    # Caption rendering escapes ordinary TeX specials such as %, _, &, #, and
    # ^ via ``latex_escape_title``.  Reject only hazards that escaping cannot
    # repair without understanding the intended mathematics.
    caption_latex_issues = [
        issue
        for issue in latex_prose_issues(caption)
        if issue.startswith("Unicode math glyphs")
        or issue.startswith("unbalanced ")
    ]
    issues.extend(f"pdflatex hazard: {issue}" for issue in caption_latex_issues)
    return issues


def auto_generate_bound_figure_captions(
    state: dict[str, Any],
    section: str,
    paragraph: dict[str, Any],
    accepted_text: str,
) -> list[str]:
    """Generate canonical captions when their citing paragraph is accepted."""
    generated: list[str] = []
    paragraph_id = str(paragraph.get("id") or "")
    fingerprint = hashlib.sha256(accepted_text.encode("utf-8")).hexdigest()
    for artifact in paragraph.get("artifacts", []):
        if isinstance(artifact, str):
            figure_id = artifact
        elif isinstance(artifact, dict) and artifact.get("kind") == "figure":
            figure_id = str(artifact.get("id") or "")
        else:
            continue
        if figure_id not in FIGURES or figure_id not in state.get("figures", {}):
            continue
        figure_state = state["figures"][figure_id]
        if figure_state.get("caption_source") == "researcher":
            continue
        if (
            figure_state.get("caption_generated_from_paragraph") == paragraph_id
            and figure_state.get("caption_generated_from_sha256") == fingerprint
        ):
            continue
        try:
            caption = generate_figure_caption(
                figure_id,
                state,
                str(figure_state.get("caption") or FIGURES[figure_id]["caption"]),
                "Generate the caption because the paragraph citing this figure has just been accepted.",
                trigger_paragraph={
                    "section": section,
                    "paragraph_id": paragraph_id,
                    "accepted_text": accepted_text,
                },
            )
        except StudioError as exc:
            figure_state["caption_last_error"] = str(exc)
            raise StudioError(
                f"{paragraph_id} Bound to {figure_id} Caption Auto generation failed."
                "This section was not accepted, please retry." + str(exc)
            ) from exc
        figure_state.update(
            {
                "caption": caption,
                "caption_source": "paragraph_accept",
                "caption_generated_from_paragraph": paragraph_id,
                "caption_generated_from_sha256": fingerprint,
                # This value is also the browser's cache-invalidation token.  A
                # second-level timestamp can repeat when a paragraph is revised
                # twice quickly, leaving an older local draft visible over the
                # newly generated canonical caption.
                "caption_generated_at": time.time_ns(),
                "caption_last_error": "",
            }
        )
        generated.append(figure_id)
    return generated


def ensure_figure_caption_before_approval(
    state: dict[str, Any], figure_id: str
) -> None:
    """Backfill the caption when prose predates automatic caption generation.

    Existing projects can contain accepted citing paragraphs created before the
    paragraph-accept hook was introduced.  Figure approval is the last safe
    transaction boundary before a caption enters the manuscript, so never let a
    configured placeholder such as ``F3`` pass that boundary unchanged.
    """
    figure_state = state["figures"][figure_id]
    caption_source = figure_state.get("caption_source")
    if caption_source == "researcher":
        return
    if caption_source == "paragraph_accept" and not figure_caption_issues(
        str(figure_state.get("caption") or "")
    ):
        return
    if caption_source == "paragraph_accept":
        # Revalidate legacy automatic captions created before the current
        # one-sentence/length contract instead of treating their old prose
        # fingerprint as proof that generation is still current.
        figure_state["caption_generated_from_sha256"] = ""
    binding = first_artifact_binding(figure_id)
    if binding is None:
        raise StudioError(f"{figure_id} There is no bound reference paragraph; unable to generate a caption.")
    section, paragraph_id = binding
    paragraph, _ = paragraph_by_id(state, section, paragraph_id)
    accepted_text = str(paragraph.get("accepted_text") or "").strip()
    if not accepted_text:
        raise StudioError(
            f"Please accept the citation first {figure_id} the paragraph {paragraph_id}, Reconfirm figure."
        )
    generated = auto_generate_bound_figure_captions(
        state, section, paragraph, accepted_text
    )
    if figure_id not in generated and figure_state.get("caption_source") != "paragraph_accept":
        raise StudioError(f"{figure_id} Caption Not generated; illustration not confirmed.")


def figure_latex(
    figure_id: str, figure_state: dict[str, Any] | None = None
) -> str:
    """Return the canonical LaTeX reference and float for one approved figure."""
    definition = FIGURES[figure_id]
    paths = figure_paths(figure_id)
    figure_state = figure_state or {}
    caption = latex_escape_caption(
        str(figure_state.get("caption") or definition["caption"]).strip()
    )
    description = (
        [f"  \\Description{{{caption}}}"]
        if str(PROJECT_METADATA.get("venue") or "").strip().casefold().startswith("kdd")
        else []
    )
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
                *description,
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
    include_scale = float(definition.get("include_scale", 1.0))
    width = (
        "\\textwidth"
        if wide
        else (
            "\\columnwidth"
            if include_scale >= 0.999
            else f"{include_scale:g}\\columnwidth"
        )
    )
    # A narrow float may be anchored after the last accepted paragraph while
    # all following sections are still empty. With top-only placement,
    # ``flafter`` prevents it from moving before that anchor and LaTeX can
    # silently defer it forever. Allow the normal single-column positions;
    # wide ``figure*`` floats remain top-only in standard two-column LaTeX.
    placement = "t" if wide else "htbp"
    relative_pdf = paths["pdf"].relative_to(PAPER).as_posix()
    return "\n".join(
        [
            f"\\begin{{{environment}}}[{placement}]",
            "  \\centering",
            f"  \\includegraphics[width={width}]{{{relative_pdf}}}",
            f"  \\caption{{{caption}}}",
            *description,
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
        binding = first_artifact_binding(figure_id)
        if binding is None or binding[0] != section:
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


def is_hosted_placeholder_artifact(artifact_id: str) -> bool:
    """Return whether the hosted draft intentionally leaves this artifact editable.

    This decision comes only from the generated project contract. It must not be
    inferred from prose, captions, titles, or keywords: manuscript recovery,
    preview/materialization, and completion gates all share this one contract.
    """
    if not ONLINE_PROJECT_MODE:
        return False
    if artifact_id in TABLES:
        return bool(TABLES[artifact_id].get("online_placeholder"))
    definition = FIGURES.get(artifact_id)
    return bool(
        definition
        and (
            definition.get("online_placeholder")
            or definition.get("kind") == "mechanism"
        )
    )


def figure_placeholder_latex(
    figure_id: str, figure_state: dict[str, Any] | None = None
) -> str:
    """Return a compilable labelled float until the real figure is approved."""
    definition = FIGURES[figure_id]
    figure_state = figure_state or {}
    caption = latex_escape_caption(
        str(figure_state.get("caption") or definition["caption"]).strip()
    )
    mode = figure_state.get("layout_mode")
    wide = mode == "two-column" or (
        mode is None and definition["width"].startswith("two-column")
    )
    # A wide placeholder is not the final artifact and should not enter
    # LaTeX's separate double-column float queue. Several pending wide
    # placeholders can otherwise be emitted partly above the page crop box.
    # Keep the requested span in project metadata; the real local figure still
    # renders at that span after export.
    if is_hosted_placeholder_artifact(figure_id):
        wide = False
    environment = "figure*" if wide else "figure"
    box_width = r"0.92\linewidth"
    placeholder = latex_escape_title(
        (
            f"{figure_id} placeholder: complete the final artwork after project export"
            if is_hosted_placeholder_artifact(figure_id)
            else f"{figure_id} placeholder -- figure generation is in progress"
        )
    )
    return "\n".join(
        [
            f"\\begin{{{environment}}}[t]",
            r"  \centering",
            # Reserve the height inside the frame. Exterior vertical space can
            # push a top float beyond the printable area and clip its border.
            f"  \\fbox{{\\parbox[c][6em][c]{{{box_width}}}{{\\centering {placeholder}}}}}",
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
        binding = first_artifact_binding(table_id)
        if binding is None or binding[0] != section:
            continue
        stored = table_states.get(table_id, {})
        if (
            stored.get("status") != "approved"
            or not stored.get("latex")
            or table_latex_is_placeholder(str(stored.get("latex") or ""))
        ):
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
    caption = latex_escape_caption(
        str(table_state.get("caption") or definition["caption"]).strip()
    )
    layout_mode = str(table_state.get("layout_mode") or "").strip()
    wide = (
        layout_mode == "two-column"
        if layout_mode
        else str(definition.get("width", "")).startswith("two-column")
    )
    environment = "table*" if wide else "table"
    box_width = r"0.94\textwidth" if wide else r"0.94\columnwidth"
    placeholder = latex_escape_title(
        (
            f"{table_id} placeholder: complete the final table after project export"
            if is_hosted_placeholder_artifact(table_id)
            else f"{table_id} placeholder -- table generation is in progress"
        )
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


def table_latex_is_placeholder(latex: str) -> bool:
    """Return whether a labelled table float is only a draft placeholder.

    Placeholder floats deliberately carry the final label so prose can compile while
    a table is pending.  They must never be recovered or preserved as an approved
    table merely because the label is present.
    """
    source = str(latex or "")
    return bool(
        re.search(r"\bplaceholder\b", source, flags=re.IGNORECASE)
        or "table generation is in progress" in source.lower()
        or not re.search(r"\\begin\{tabular\*?\}", source)
    )


def render_section_source(
    section: str,
    section_state: dict[str, Any],
    figure_states: dict[str, dict[str, Any]] | None = None,
    table_states: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Render accepted paragraphs without discarding the section's LaTeX wrapper."""
    accepted_paragraphs = [
        (
            item["id"],
            strip_managed_section_headings(
                normalize_latex_ready_text(item["accepted_text"].strip())
            ),
        )
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


def _normalize_planned_paragraph(paragraph: dict[str, Any]) -> dict[str, Any]:
    """Normalize an approved contract paragraph for the browser writer."""
    normalized = {
        **paragraph,
        "id": str(paragraph.get("id") or ""),
        "purpose": str(
            paragraph.get("purpose") or paragraph.get("plan_sentence") or ""
        ),
        "rhetorical_role": str(paragraph.get("rhetorical_role") or ""),
        "relation_to_previous": str(paragraph.get("relation_to_previous") or ""),
        "relation_to_next": str(paragraph.get("relation_to_next") or ""),
        "artifacts": [
            str(item)
            for item in (
                paragraph.get("artifacts")
                if isinstance(paragraph.get("artifacts"), list)
                else paragraph.get("artifact_refs", [])
            )
        ],
    }
    normalized.pop("plan_sentence", None)
    normalized.pop("artifact_refs", None)
    return normalized


def _approved_contract() -> dict[str, Any]:
    decision_source = str(PROJECT_METADATA.get("decision_source") or "").strip()
    if not decision_source or decision_source == "lightweight-onboarding":
        return {}
    source = _project_path(ROOT, decision_source, "project.decision_source")
    if not source.is_file():
        raise StudioError("The approved experimental plan does not exist.")
    match = re.search(
        r"<script\b[^>]*\bid=[\"']experiment-plan-contract[\"'][^>]*>(.*?)</script>",
        source.read_text(encoding="utf-8", errors="replace"),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise StudioError("The experimental plan lacks a readable writing contract.")
    try:
        contract = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise StudioError("The writing contract in the experimental plan is not valid JSON.") from exc
    return contract if isinstance(contract, dict) else {}


def paragraph_plan() -> dict[str, Any]:
    """Return paragraph architecture embedded in config or the approved contract."""
    configured: dict[str, list[dict[str, Any]]] = {}
    for section in SECTION_SPECS:
        paragraphs = section.get("paragraphs")
        if not isinstance(paragraphs, list):
            configured = {}
            break
        configured[str(section["id"])] = [
            _normalize_planned_paragraph(item)
            for item in paragraphs
            if isinstance(item, dict)
        ]
    if configured:
        return {"sections": configured}

    if DEMO_MODE and STATE_FILE.is_file():
        try:
            demo_state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StudioError("Read only Demo paragraph structure is not valid JSON.") from exc
        demo_sections = demo_state.get("sections")
        if isinstance(demo_sections, dict):
            sections = {
                str(section_id): [
                    _normalize_planned_paragraph(item)
                    for item in section.get("paragraphs", [])
                    if isinstance(item, dict)
                ]
                for section_id, section in demo_sections.items()
                if isinstance(section, dict)
            }
            if sections:
                return {"sections": sections}

    contract = _approved_contract()
    outline = contract.get("paper_outline")
    if not isinstance(outline, list):
        raise StudioError("Project configuration and experimental plan both lack the approved paragraph structure.")
    sections: dict[str, list[dict[str, Any]]] = {}
    for section in outline:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or section.get("id") or "").strip()
        paragraphs = section.get("paragraphs")
        if section_id and isinstance(paragraphs, list):
            sections[section_id] = [
                _normalize_planned_paragraph(item)
                for item in paragraphs
                if isinstance(item, dict)
            ]
    # Older approved contracts used two combined IDs while the current editor
    # exposes Discussion, Limitations, and Appendix as separate manuscript
    # files. Adapt only those known schema aliases; scientific paragraph text,
    # order, and artifact bindings remain untouched.
    configured_ids = set(SECTION_MAP)
    if (
        "discussion_limitations" in sections
        and {"discussion", "limitations"}.issubset(configured_ids)
    ):
        combined = sections.pop("discussion_limitations")
        limitations = [
            item
            for item in combined
            if re.search(
                r"\blimitation|external[- ]validity|future work|beyond\b",
                " ".join(
                    str(item.get(field) or "")
                    for field in ("purpose", "rhetorical_role")
                ),
                re.IGNORECASE,
            )
        ]
        limitation_ids = {str(item.get("id")) for item in limitations}
        discussion = [
            item for item in combined if str(item.get("id")) not in limitation_ids
        ]
        if not discussion and combined:
            discussion = combined[:1]
            limitations = combined[1:]
        sections["discussion"] = discussion
        sections["limitations"] = limitations
    if "appendices" in sections and "appendix" in configured_ids:
        sections["appendix"] = sections.pop("appendices")
    return {"sections": sections}


def approved_outline_context() -> str:
    """Render the approved target-paper architecture as compact prompt context."""
    lines = [f"Title: {manuscript_title_display()}", "", "Approved section plan:"]
    sections = paragraph_plan().get("sections", {})
    for index, section_spec in enumerate(SECTION_SPECS, 1):
        section_id = str(section_spec["id"])
        lines.append(f"{index}. {section_spec['title']}")
        for paragraph in sections.get(section_id, []):
            lines.append(f"  - {paragraph['id']}: {paragraph['purpose']}")
    return "\n".join(lines)


def normalize_reference_excerpt(lines: list[str]) -> str:
    """Remove PDF line wrapping while retaining real blank-line paragraph breaks."""
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in lines:
        line = raw_line.replace("\f", "").strip()
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def reference_contexts() -> dict[str, Any]:
    if not REFERENCE_CONTEXT_FILE.is_file():
        return {}
    try:
        payload = json.loads(REFERENCE_CONTEXT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StudioError("paper/reference_context.json Not valid JSON.") from exc
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, dict):
        raise StudioError("paper/reference_context.json sections Must be an object.")
    source_value = str(payload.get("reference_source") or "").strip()
    if source_value:
        source_path = _project_path(ROOT, source_value, "reference_context.reference_source")
        if not source_path.is_file():
            raise StudioError("reference_context.reference_source Does not exist.")
        source_lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for context in sections.values():
            if not isinstance(context, dict):
                continue
            for excerpt in context.get("excerpts", []):
                if not isinstance(excerpt, dict):
                    continue
                start, end = excerpt.get("start_line"), excerpt.get("end_line")
                if (
                    not isinstance(start, int) or isinstance(start, bool)
                    or not isinstance(end, int) or isinstance(end, bool)
                    or start < 1 or end < start or end > len(source_lines)
                ):
                    raise StudioError("reference_context There exist invalid original line numbers.")
                excerpt["text"] = normalize_reference_excerpt(source_lines[start - 1:end])
    return sections


def section_reference_context(section: str) -> dict[str, Any]:
    context = reference_contexts().get(section, {})
    return context if isinstance(context, dict) else {}


def _reference_paragraph_ids(paragraph: dict[str, Any]) -> list[str]:
    """Return only source-paragraph IDs explicitly mapped to one target paragraph."""
    raw_ids = paragraph.get("reference_paragraph_ids", [])
    ids = [str(item).strip() for item in raw_ids] if isinstance(raw_ids, list) else []
    mappings = paragraph.get("reference_mapping", [])
    if isinstance(mappings, list):
        for mapping in mappings:
            if isinstance(mapping, str):
                ids.append(mapping.strip())
            elif isinstance(mapping, dict):
                ids.append(
                    str(
                        mapping.get("source_paragraph_id")
                        or mapping.get("reference_paragraph_id")
                        or mapping.get("id")
                        or ""
                    ).strip()
                )
    return list(dict.fromkeys(item for item in ids if item))


def paragraph_reference_ids(section: str, paragraph: dict[str, Any]) -> list[str]:
    """Resolve the approved reference mapping for the selected target paragraph."""
    direct = _reference_paragraph_ids(paragraph)
    if direct:
        return direct
    paragraph_id = str(paragraph.get("id") or "").strip()
    if not paragraph_id:
        return []
    try:
        outline = _approved_contract().get("paper_outline", [])
    except StudioError:
        return []
    planned_sections = (
        [item for item in outline if isinstance(item, dict)]
        if isinstance(outline, list)
        else []
    )
    matching_sections = [
        item
        for item in planned_sections
        if str(item.get("section_id") or item.get("id") or "").strip() == section
    ]
    # Paper Studio may use a display-oriented section alias (for example,
    # discussion_and_limitations) while the approved contract uses a shorter
    # source ID. Paragraph IDs are contract-wide coordinates, so use them as
    # the compatibility fallback instead of dropping the mapping.
    for planned_section in matching_sections or planned_sections:
        if not isinstance(planned_section, dict):
            continue
        for planned in planned_section.get("paragraphs", []):
            if isinstance(planned, dict) and str(planned.get("id") or "").strip() == paragraph_id:
                return _reference_paragraph_ids(planned)
    return []


def paragraph_reference_context(section: str, paragraph: dict[str, Any]) -> dict[str, Any]:
    """Filter section context to the reference prose mapped to the active paragraph.

    This deliberately fails closed: an absent mapping exposes no source prose rather
    than silently showing every excerpt from the surrounding section.
    """
    context = section_reference_context(section)
    selected_ids = set(paragraph_reference_ids(section, paragraph))
    filtered = dict(context)
    paragraph_id = str(paragraph.get("id") or "").strip()
    filtered["writing_constraints"] = [
        item
        for item in context.get("writing_constraints", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip() == paragraph_id
    ]
    filtered["excerpts"] = [
        excerpt
        for excerpt in context.get("excerpts", [])
        if isinstance(excerpt, dict)
        and str(
            excerpt.get("id")
            or excerpt.get("reference_paragraph_id")
            or excerpt.get("source_paragraph_id")
            or ""
        ).strip()
        in selected_ids
    ]
    return filtered


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
        label = str(item.get("heading") or f"{paragraph_id} paragraph")
        grouped.setdefault(section, []).append(label)
    groups = []
    for section, labels in grouped.items():
        section_name = str(
            SECTION_MAP.get(section, {}).get("latex_title")
            or SECTION_MAP.get(section, {}).get("title")
            or section
        )
        suffix = " subsection" if all(not label.endswith("paragraph") for label in labels) else ""
        groups.append(f"{section_name} section of {', '.join(labels)}{suffix}")
    return f"Please generate and write it first. {'; '.join(groups)}, Then plot again."


def validate_project_workspace() -> None:
    """Fail fast when project config, paragraph architecture, and bindings disagree."""
    if EMPTY_PROJECT_MODE:
        return
    plan = paragraph_plan()
    planned_sections = plan.get("sections")
    if not isinstance(planned_sections, dict):
        raise StudioError("The approved paragraph structure must be organized by section.")
    configured_sections = set(SECTION_MAP)
    missing_sections = configured_sections - set(planned_sections)
    extra_sections = set(planned_sections) - configured_sections
    if missing_sections or extra_sections:
        details = []
        if missing_sections:
            details.append("missing " + ", ".join(sorted(missing_sections)))
        if extra_sections:
            details.append("extra " + ", ".join(sorted(extra_sections)))
        raise StudioError("The paragraph structure is inconsistent with the section in paper_studio.json:" + "; ".join(details))
    contexts = reference_contexts()
    if contexts:
        if set(contexts) != configured_sections:
            raise StudioError("reference_context.json Must cover every configured section and must not include extra sections.")
        for section, context in contexts.items():
            if not isinstance(context, dict):
                raise StudioError(f"Corresponding content of the reference paper {section} Must be an object.")
            for field in ("source_heading", "logic_summary_zh"):
                if not str(context.get(field) or "").strip():
                    raise StudioError(f"Corresponding content of the reference paper {section} missing {field}.")
            excerpts = context.get("excerpts")
            if context.get("mode") == "abstracted":
                constraints = context.get("writing_constraints")
                if excerpts not in ([], None):
                    raise StudioError(f"Abstract reference mode. {section} Do not carry original excerpts.")
                if not isinstance(constraints, list) or not 1 <= len(constraints) <= 50:
                    raise StudioError(f"Abstract reference mode. {section} Must contain 1--50 writing constraints.")
                if any(
                    not isinstance(item, dict)
                    or not str(item.get("id") or "").strip()
                    or not str(item.get("purpose") or "").strip()
                    for item in constraints
                ):
                    raise StudioError(f"Abstract reference mode. {section} Invalid writing constraints exist.")
            else:
                if not isinstance(excerpts, list) or not 1 <= len(excerpts) <= 50:
                    raise StudioError(f"Corresponding content of the reference paper {section} Must contain 1-50 original fragments.")
                if any(
                    not isinstance(item, dict) or not str(item.get("text") or "").strip()
                    for item in excerpts
                ):
                    raise StudioError(f"Corresponding content of the reference paper {section} There are empty original passages.")
    artifact_ids = set(FIGURES) | set(TABLES)
    artifact_bindings = {artifact_id: [] for artifact_id in artifact_ids}
    paragraph_ids: dict[str, set[str]] = {}
    for section, paragraphs in planned_sections.items():
        if not isinstance(paragraphs, list):
            raise StudioError(f"Section in paragraph structure. {section} Must be a list.")
        ids = [str(item.get("id", "")) for item in paragraphs]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise StudioError(f"Section in paragraph structure. {section} Contains invalid paragraph IDs.")
        paragraph_ids[section] = set(ids)
        for paragraph in paragraphs:
            for field in ("purpose", "rhetorical_role", "relation_to_previous", "relation_to_next"):
                if not str(paragraph.get(field, "")).strip():
                    raise StudioError(f"paragraph {paragraph['id']} Missing approved items. {field}.")
            bound = paragraph.get("artifacts", [])
            if not isinstance(bound, list) or len(bound) != len(set(bound)):
                raise StudioError(
                    f"paragraph {paragraph['id']} The artifacts must be a list of unique IDs."
                )
            unknown = set(bound) - artifact_ids
            if unknown:
                raise StudioError(
                    f"paragraph {paragraph['id']} Bound to unknown chart:{', '.join(sorted(unknown))}"
                )
            for artifact_id in bound:
                artifact_bindings[artifact_id].append(f"{section}/{paragraph['id']}")
    unbound = sorted(
        artifact_id for artifact_id, bindings in artifact_bindings.items() if not bindings
    )
    if unbound:
        raise StudioError(
            "Each figure must be bound to at least one paragraph that cites it; currently unbound:"
            + ", ".join(unbound)
        )
    for figure_id, definition in FIGURES.items():
        unknown_figures = set(definition.get("depends_on_figures", [])) - set(FIGURES)
        if unknown_figures:
            raise StudioError(
                f"{figure_id} Dependency on unknown Figure:{', '.join(sorted(unknown_figures))}"
            )
        for section, ids in definition.get("depends_on_paragraphs", {}).items():
            unknown = set(ids) - paragraph_ids.get(section, set())
            if unknown:
                raise StudioError(
                    f"{figure_id} Unknown paragraph dependencies:{section} / {', '.join(sorted(unknown))}"
                )
        generation_requirements = definition.get("generation_requires_paragraphs")
        if generation_requirements is not None:
            if definition.get("kind") != "mechanism" or not isinstance(
                generation_requirements, dict
            ):
                raise StudioError(
                    f"{figure_id}.generation_requires_paragraphs Only usable for mechanism diagrams and must be an object."
                )
            for section, ids in generation_requirements.items():
                if not isinstance(ids, list) or not ids:
                    raise StudioError(
                        f"{figure_id} The plotting preface paragraph must be a non empty list:{section}"
                    )
                unknown = set(ids) - paragraph_ids.get(section, set())
                if unknown:
                    raise StudioError(
                        f"{figure_id} The drawing preface paragraph does not exist:"
                        f"{section} / {', '.join(sorted(unknown))}"
                    )
    for artifact_id, definition in {**FIGURES, **TABLES}.items():
        shape_spec = str(definition.get("shape_spec", "")).strip()
        if shape_spec:
            path = _project_path(ROOT, shape_spec, f"{artifact_id}.shape_spec")
            if not path.exists():
                raise StudioError(f"{artifact_id} The shape_spec does not exist:{shape_spec}")


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
    prose = strip_managed_section_headings(prose)
    prose = re.sub(
        r"^\\(?:paragraph|subsection|textbf)\*?\{[^{}]*\}\s*",
        "",
        prose,
        count=1,
    ).strip()
    if not heading:
        return prose
    expected = heading_latex(heading, heading_style)
    separator = "\n\n" if (heading_style or "paragraph") == "subsection" else " "
    return f"{expected}{separator}{prose}".strip()


def strip_managed_section_headings(text: str) -> str:
    """Strip LLM-emitted top-level headings owned by the section renderer.

    Paper Studio deterministically inserts one ``\\section`` wrapper per configured
    section.  A model-emitted section command is therefore always duplication, even
    when its title differs slightly from the configured title.
    """
    prose = str(text or "").strip()
    while True:
        revised = re.sub(
            r"^\\section\*?\{[^{}]*\}\s*",
            "",
            prose,
            count=1,
        ).strip()
        if revised == prose:
            return prose
        prose = revised


def strip_redundant_section_name_leadin(text: str, section_title: str) -> str:
    """Remove a model-emitted prose label already owned by the section wrapper.

    ``Related Work. Body`` and ``Abstract: Body`` are not natural paragraph
    openings; they are duplicate headings even though they are not LaTeX
    commands.  Keep outline-defined paragraph/subsection headings separate:
    this runs before ``enforce_required_heading`` deterministically adds them.
    """
    prose = strip_managed_section_headings(text)
    title = r"\s+".join(
        re.escape(token) for token in str(section_title or "").strip().split()
    )
    if not title:
        return prose
    aliases = [title]
    if str(section_title).strip().casefold() == "abstract":
        aliases.extend(("Abstrct", "Abtract"))
    names = "|".join(aliases)
    while True:
        revised = re.sub(
            rf"^(?:\\textbf\{{\s*)?(?:{names})\s*"
            rf"(?:[.:]\s*|[—–-]\s+|\}}\s*)",
            "",
            prose,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        if revised == prose:
            return prose
        prose = revised


def paragraph_architecture(paragraph: dict[str, Any]) -> dict[str, str]:
    """Return only the approved target-paper logic; never expose reference prose."""
    return {
        "purpose": str(paragraph.get("purpose") or "").strip(),
        "rhetorical_role": str(paragraph.get("rhetorical_role") or "").strip(),
        "relation_to_previous": str(paragraph.get("relation_to_previous") or "").strip(),
        "relation_to_next": str(paragraph.get("relation_to_next") or "").strip(),
    }


def has_executed_real_results() -> bool:
    """Return whether the metrics registry contains real populated artifacts."""
    metrics = metrics_bundle()
    if bool(metrics.get("synthetic", False)):
        return False
    artifacts = metrics.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return False
    return any(
        isinstance(record, dict)
        and not bool(record.get("synthetic", False))
        and isinstance(record.get("rows"), (int, float))
        and float(record["rows"]) > 0
        for record in artifacts.values()
    )


def section_writing_logic_chain(section: str) -> dict[str, Any]:
    """Expose the section-wide rhetorical chain without source-paper prose."""
    return {
        "section": section,
        "paragraphs": [
            {"id": str(item.get("id") or ""), **paragraph_architecture(item)}
            for item in planned_paragraphs(section)
        ],
        "content_authority": "target project evidence only",
    }


def effective_working_abstract_context() -> str:
    """Replace a stale plan-only abstract once real result artifacts exist."""
    if has_executed_real_results():
        return (
            "The experiment has been executed. Draft the "
            "abstract from the exact measurements in section_evidence. Report only "
            "supported findings, retain every scope qualification supplied by the "
            "execution evidence, and include no citation commands."
        )
    return read_text(PAPER / "working_abstract.txt", 10000)


def effective_writing_architecture(
    section: str,
    architecture: dict[str, str] | None,
    bound_artifacts: list[dict[str, Any]],
) -> dict[str, str]:
    """Overlay current execution state on an older approved writing plan."""
    effective = dict(architecture or {})
    if not has_executed_real_results():
        return effective
    has_bound_results = any(
        isinstance(item, dict) and bool(item.get("traceable_results"))
        for item in bound_artifacts
    )
    if SECTION_MAP.get(section, {}).get("render") == "abstract":
        status = (
            "Summarize the executed study using exact supplied measurements and its "
            "evidence-defined scope; do not describe it as planned or pending."
        )
    elif _is_experiment_section(section) and has_bound_results:
        status = (
            "Report and interpret the executed measurements in the bound artifacts; "
            "the older plan-only wording is obsolete."
        )
    elif _is_experiment_section(section):
        status = (
            "No executed artifact is bound to this paragraph. State the evidence gap "
            "or supported protocol boundary; do not invent an ablation or robustness result."
        )
    elif _is_synthesis_section(section) and has_bound_results:
        status = (
            "Interpret the executed bound measurements and their limitations; do not "
            "call populated artifacts placeholders or future tests."
        )
    elif section == "conclusion":
        status = (
            "Close with the exact supported pilot findings and limitations, not the "
            "pre-execution plan."
        )
    else:
        status = "Use current target-project evidence; ignore obsolete plan-only status."
    effective["current_evidence_status"] = status
    return effective


def online_citation_placeholder_minimum(section: str, paragraph_index: int) -> int:
    """Reserve fillable citation slots in literature-facing hosted prose."""
    if section == "introduction":
        return 2 if paragraph_index < 2 else 0
    if section == "related_work":
        return 2
    return 0


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
            "status": "placeholder",
        },
        "full_draft_job": None,
        "section_draft_job": None,
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
                "caption": FIGURES[figure_id]["caption"],
                "caption_source": "configured",
                "caption_generated_from_paragraph": "",
                "caption_generated_from_sha256": "",
                "caption_generated_at": None,
                "caption_last_error": "",
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
                "layout_mode": (
                    "two-column"
                    if TABLES[table_id]["width"].startswith("two-column")
                    else "single-column"
                ),
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
                            strip_redundant_section_name_leadin(
                                str(candidate.get("text", "")),
                                str(current.get("title") or SECTION_MAP[key]["title"]),
                            ),
                            planned.get("heading"),
                            planned.get("heading_style"),
                        ),
                    }
                accepted_text = enforce_required_heading(
                    strip_redundant_section_name_leadin(
                        str(prior.get("accepted_text", "")),
                        str(current.get("title") or SECTION_MAP[key]["title"]),
                    ),
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
        state["model"] = model_for_provider(
            state["llm_provider"], str(state.get("model") or "")
        )
        title_editor = state.setdefault("title_editor", default["title_editor"])
        for field, value in default["title_editor"].items():
            title_editor.setdefault(field, value)
        draft_job = state.setdefault("full_draft_job", None)
        # Section generation used to be stored as a disguised full-draft job.
        # Migrate that state once so the two product features remain independent.
        if (
            isinstance(draft_job, dict)
            and draft_job.get("scope") == "section"
            and not state.get("section_draft_job")
        ):
            state["section_draft_job"] = draft_job
            state["full_draft_job"] = None
            draft_job = None
        if (
            isinstance(draft_job, dict)
            and draft_job.get("status") == "running"
            and draft_job.get("server_instance") != SERVER_INSTANCE_TOKEN
            and not process_is_alive(draft_job.get("server_pid"))
        ):
            state["full_draft_job"] = {
                **draft_job,
                "status": "failed",
                "token": None,
                "progress_message": "Service has restarted; the full text generation task has stopped, you can resume from the unfinished paragraph.",
                "finished_at": int(time.time()),
            }
        section_job = state.setdefault("section_draft_job", None)
        if (
            isinstance(section_job, dict)
            and section_job.get("status") == "running"
            and section_job.get("server_instance") != SERVER_INSTANCE_TOKEN
            and not process_is_alive(section_job.get("server_pid"))
        ):
            state["section_draft_job"] = {
                **section_job,
                "status": "failed",
                "token": None,
                "progress_message": "Service has been restarted; Section generation tasks have stopped, you may resume.",
                "finished_at": int(time.time()),
            }
        state.setdefault("compile", default["compile"])
        stored_figures = state.get("figures", {})
        if not isinstance(stored_figures, dict):
            stored_figures = {}
        state["figures"] = {
            figure_id: (
                stored_figures.get(figure_id, figure_state)
                if isinstance(stored_figures.get(figure_id, figure_state), dict)
                else figure_state
            )
            for figure_id, figure_state in default["figures"].items()
        }
        for figure_id, figure_state in default["figures"].items():
            current_figure = state.setdefault("figures", {}).setdefault(
                figure_id, figure_state
            )
            for field, value in figure_state.items():
                current_figure.setdefault(field, value)
            if not isinstance(current_figure.get("panels"), dict):
                current_figure["panels"] = dict(figure_state.get("panels", {}))
            if (
                ONLINE_PROJECT_MODE
                and FIGURES[figure_id].get("kind") == "mechanism"
                and current_figure.get("status") == "failed"
            ):
                # Older online workers incorrectly attempted the intentionally
                # unavailable local image/PPTX pipeline. Recover those red failures
                # to the normal hosted placeholder state on reload.
                current_figure.update(
                    status="pending",
                    progress=0,
                    progress_message="",
                    last_message="",
                    job_token=None,
                    job_started_at=None,
                )
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
                and current_figure.get("status") == "built"
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
        refresh_full_draft_artifact_status(state)
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


def mechanism_draft_preview_no_text(figure_id: str) -> bool:
    """Expose whether the archived composition draft was intentionally text-free."""
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
        raise StudioError("Missing result data:" + ", ".join(missing))
    fixture = metrics.get("fixture", {})
    traceable_results: dict[str, Any] = {}
    for key in result_keys:
        value = result_path_value(metrics, key)
        # The metrics contract is an exact dotted-key map.  Do not also add
        # parent objects here: doing so leaks result families that were not
        # explicitly bound to the artifact and makes provenance checks
        # ambiguous.  Plot programs are instructed to index this map by the
        # complete dotted key.
        traceable_results[key] = value
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "source_metrics": PROJECT_CONFIG["paths"]["metrics"],
        "traceable_results": traceable_results,
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
        return False, "Missing result data:" + ", ".join(missing_results)
    if definition.get("kind") == "mechanism":
        requirements = figure_generation_prerequisites(figure_id)
        if not requirements:
            return False, f"{figure_id} The body paragraphs required for plotting have not been configured."
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
        return False, f"{figure_id} Not yet bound to the paragraph that first cites it."
    section, paragraph_id = binding
    if paragraph_id not in accepted_paragraph_ids(state["sections"][section]):
        return False, f"Please write the first reference paragraph before inserting. {paragraph_id}."
    for dependency in definition.get("depends_on_figures", []):
        if state["figures"][dependency].get("status") != "approved":
            return False, f"Figure candidate can be generated first; please confirm before inserting into the main text. {dependency}"
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
        if (
            stored.get("status") == "pending"
            and str(stored.get("progress_message") or "").startswith(
                "Artifact contract changed"
            )
        ):
            # The manuscript still contains the previous approved float.  It is
            # stale by definition and must not undo contract invalidation during
            # process startup.
            continue
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
                "placeholder_only": is_hosted_placeholder_artifact(figure_id),
                "placeholder_message": (
                    ONLINE_PLACEHOLDER_FIGURE_MESSAGE
                    if is_hosted_placeholder_artifact(figure_id)
                    else ""
                ),
                "caption": stored.get("caption") or definition["caption"],
                "caption_source": stored.get("caption_source", "configured"),
                "caption_needs_backfill": (
                    stored.get("caption_source", "configured") != "researcher"
                    and (
                        stored.get("caption_source", "configured") != "paragraph_accept"
                        or bool(
                            figure_caption_issues(
                                str(stored.get("caption") or definition["caption"])
                            )
                        )
                    )
                ),
                "caption_generated_from_paragraph": stored.get(
                    "caption_generated_from_paragraph", ""
                ),
                "caption_generated_at": stored.get("caption_generated_at"),
                "caption_last_error": stored.get("caption_last_error", ""),
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
                    if (
                        not is_data
                        and stored.get("status") != "approved"
                        and mechanism_draft.exists()
                    )
                    else None
                ),
                "draft_preview_no_text": mechanism_draft_preview_no_text(figure_id),
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
    if is_hosted_placeholder_artifact(table_id):
        return False, ONLINE_PLACEHOLDER_FIGURE_MESSAGE
    metrics = metrics if metrics is not None else metrics_bundle()
    missing_results = [
        key for key in definition.get("result_keys", []) if not has_result_path(metrics, key)
    ]
    if missing_results:
        return False, "Missing result data:" + ", ".join(missing_results)
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
        # Some HTML result tables retain their visual header as the first
        # extracted record.  Do not render that record as a duplicate body row.
        if rows:
            matches = sum(
                normalize_plain_title(value).casefold()
                == normalize_plain_title(header).casefold()
                for value, header in zip(rows[0], headers)
            )
            if matches >= max(2, len(headers) - 1):
                rows = rows[1:]
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
        "data source": "source",
        "source": "source",
        "column": "columns",
        "columns": "columns",
        "row": "rows",
        "line": "rows",
        "rows": "rows",
        "caption": "caption",
        "title": "caption",
        "font size": "size",
        "size": "size",
        "optimal value": "best",
        "best value": "best",
        "best": "best",
    }
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([^::]+)[::]\s*(.*)$", line)
        if not match:
            raise StudioError(
                f"Cannot parse table Prompt rows:{line}.Please use key: value format."
            )
        raw_key, value = match.groups()
        key = aliases.get(raw_key.strip().lower())
        if key is None:
            raise StudioError(
                f"Unsupported table Prompt instruction.{raw_key.strip()}."
                "Support: data source, columns, rows, Caption, font size, optimal value."
            )
        directives[key] = value.strip()

    configured_source = str(PROJECT_CONFIG["paths"]["metrics"]).rstrip("/")
    requested_source = directives.get("source", configured_source).rstrip("/")
    if requested_source not in {"results", configured_source}:
        raise StudioError(
            f"Table data source fixed to {configured_source}, Cannot use non-reproducible data."
        )

    columns = list(available_columns)
    requested_columns = directives.get("columns", "")
    if requested_columns:
        # Column labels often contain explanatory commas, e.g.
        # ``ASR (%, lower is better)``.  A pipe-delimited prompt must therefore
        # treat only pipes as separators; otherwise the untouched generated
        # prompt rejects its own perfectly valid column label as two unknown
        # columns.  Retain comma separation for older prompts that contain no
        # pipes.
        protected_columns = requested_columns
        protected_labels: dict[str, str] = {}
        # A scientific column label may itself use a conditional bar (for
        # example ``error | recall=1``). Protect exact known labels before
        # interpreting pipes as the prompt's column separator.
        for index, label in enumerate(
            sorted((str(item) for item in available_columns if "|" in str(item)), key=len, reverse=True)
        ):
            marker = f"__PAPER_STUDIO_COLUMN_{index}__"
            updated, count = re.subn(
                re.escape(label), marker, protected_columns, flags=re.IGNORECASE
            )
            if count:
                protected_columns = updated
                protected_labels[marker.casefold()] = label
        separator = r"\s*\|\s*" if "|" in protected_columns else r"\s*[,, ]\s*"
        names = [
            protected_labels.get(item.strip().casefold(), item.strip())
            for item in re.split(separator, protected_columns)
            if item.strip()
        ]
        lookup = {name.casefold(): name for name in available_columns}
        unknown = [name for name in names if name.casefold() not in lookup]
        if unknown:
            raise StudioError("Table Prompt contains unknown columns:" + ", ".join(unknown))
        columns = [lookup[name.casefold()] for name in names]
    identifier = available_columns[0]
    if identifier not in columns:
        raise StudioError(f"The table must preserve the identifier column {identifier}.")

    row_lookup = {str(row[0]).casefold(): row for row in available_rows}
    row_directive = directives.get("rows", "source").strip()
    if row_directive.casefold() in {
        "source",
        "all",
        "maintain results order.",
    }:
        selected_rows = list(available_rows)
    else:
        requested_rows = [
            item.strip()
            for item in re.split(r"\s*[|,, ]\s*", row_directive)
            if item.strip()
        ]
        unknown_rows = [
            name for name in requested_rows if name.casefold() not in row_lookup
        ]
        if unknown_rows:
            raise StudioError("Table Prompt contains unknown columns:" + ", ".join(unknown_rows))
        selected_rows = [row_lookup[name.casefold()] for name in requested_rows]

    column_indices = [available_columns.index(name) for name in columns]
    rows = [[str(row[index]) for index in column_indices] for row in selected_rows]
    size = directives.get("size", "small").lstrip("\\").strip().rstrip(".").casefold()
    if size not in {"small", "footnotesize", "scriptsize"}:
        raise StudioError("Font size only supports small, footnotesize, or scriptsize.")
    best = directives.get("best", "none").casefold()
    best_aliases = {
        "none": "none",
        "not bold": "none",
        "maximum": "max",
        "minimum": "min",
    }
    best = best_aliases.get(best, best)
    if best not in {"none", "max", "min"}:
        # The demo project's own default table briefs describe intent in
        # natural English ("highest accuracy and lowest count") rather than
        # this grammar's literal none/max/min tokens -- so a fresh project
        # that never touches the table prompt would otherwise 400 on the
        # very first generate. Recognize superlative wording instead of
        # requiring the literal token.
        wants_high = bool(re.search(r"\b(high(?:est)?|max(?:imum)?|greatest|largest|most)\b", best))
        wants_low = bool(re.search(r"\b(low(?:est)?|min(?:imum)?|smallest|fewest|least)\b", best))
        if wants_high and wants_low:
            # Genuinely mixed per-column intent -- the renderer only
            # supports one bolding direction for the whole table, and
            # guessing either way would mislabel at least one column as
            # "best" in the generated paper. Don't bold anything instead.
            best = "none"
        elif wants_high:
            best = "max"
        elif wants_low:
            best = "min"
    if best not in {"none", "max", "min"}:
        raise StudioError("The optimal value supports none, max, or min only.")
    caption = directives.get("caption", TABLES[table_id]["caption"]).strip()
    if not caption:
        raise StudioError("Caption Cannot be empty.")
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
        "ρ": r"$\rho$",
        "α": r"$\alpha$",
        "β": r"$\beta$",
        "Δ": r"$\Delta$",
        "±": r"$\pm$",
        "×": r"$\times$",
        "✓": "Yes",
        "✔": "Yes",
        "✗": "No",
        "✘": "No",
        "→": r"$\rightarrow$",
        "←": r"$\leftarrow$",
        "↔": r"$\leftrightarrow$",
        "≤": r"$\leq$",
        "≥": r"$\geq$",
        "−": "-",
        "—": "N/A",
        "–": " to ",
    }
    return "".join(replacements.get(character, character) for character in value)


def numeric_cell(value: str) -> float | None:
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value)
    return float(match.group(0)) if match else None


def figure_records_grid(figure_id: str, metrics: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    """Records-shaped data_grid reader for deterministic (non-Agent) data figures."""
    definition = FIGURES[figure_id]
    grid = definition.get("data_grid")
    if not isinstance(grid, dict):
        # Full Research Avatar packages predate the lightweight uploader's
        # explicit data_grid field.  Their data figures still point at
        # traceable records through result_keys (for example
        # artifacts.F2.rows).  Online mode cannot run the local plotting
        # Agent, so derive the small typed grid from those records instead of
        # crashing with a KeyError.  The first non-numeric column is the x
        # label and every consistently numeric column becomes a series.
        source = None
        source_path = ""
        for candidate in definition.get("result_keys", []):
            value = result_path_value(metrics, str(candidate))
            if isinstance(value, list) and value and all(
                isinstance(row, dict) for row in value
            ):
                source = value
                source_path = str(candidate)
                break
        if source is None:
            raise StudioError(
                f"{figure_id} Missing records data_grid suitable for online Python plotting."
                "Please configure data_grid, or have result_keys point to a nonempty object list."
            )
        keys = list(source[0].keys())
        label_key = next(
            (
                key
                for key in keys
                if any(numeric_cell(str(row.get(key, ""))) is None for row in source)
            ),
            keys[0] if keys else "",
        )
        numeric_keys = [
            key
            for key in keys
            if key != label_key
            and all(numeric_cell(str(row.get(key, ""))) is not None for row in source)
        ]
        if not label_key or not numeric_keys:
            raise StudioError(
                f"{figure_id} of {source_path} At least one identifier column and one numeric column."
            )
        columns = [
            {"key": label_key, "label": str(label_key).replace("_", " ").strip().title()},
            *[
                {"key": key, "label": str(key).replace("_", " ").strip().title()}
                for key in numeric_keys
            ],
        ]
        grid = {"type": "records", "path": source_path, "columns": columns}
    if str(grid.get("type", "")) != "records":
        raise StudioError(f"{figure_id} Deterministic plotting supports only data_grid of type records.")
    source = result_path_value(metrics, str(grid.get("path", "")))
    if not isinstance(source, list):
        raise StudioError(f"{figure_id} data_grid records path must resolve to a list")
    columns = list(grid.get("columns", []))
    headers = [str(column["label"]) for column in columns]
    rows = [
        [str(record.get(str(column["key"]), "—")) for column in columns]
        for record in source
        if isinstance(record, dict)
    ]
    # HTML experiment reports often expose three provenance rows followed by
    # their real visual header ("Category / point", series names) as records.
    # Promote that embedded row to chart headers and exclude provenance text
    # from the numeric series instead of failing on a generic "Value 2" column.
    embedded_header = next(
        (
            index
            for index, row in enumerate(rows)
            if row
            and row[0].strip().casefold()
            in {"category / point", "category", "point", "case type"}
        ),
        None,
    )
    if embedded_header is not None and embedded_header + 1 < len(rows):
        headers = rows[embedded_header]
        rows = rows[embedded_header + 1 :]
    return headers, rows


def data_figure_axis_labels(definition: dict[str, Any]) -> tuple[str, str]:
    """Return semantic axis labels without treating a series name as an axis."""
    visible_dimensions = [
        str(item).strip()
        for item in definition.get("visible_dimensions", [])
        if str(item).strip()
    ]
    x_label = str(definition.get("x_axis_label") or "").strip()
    if not x_label and visible_dimensions:
        x_label = visible_dimensions[0].replace("_", " ").title()
    y_label = str(definition.get("y_axis_label") or "").strip() or "Value"
    return x_label, y_label


def render_data_figure_deterministic(figure_id: str, metrics: dict[str, Any], pdf_path: Path, png_path: Path) -> None:
    """Render one simple grouped-bar chart straight from data_grid, no Agent involved.

    Lightweight (no-package) online projects auto-scaffold data figures
    directly from uploaded records instead of an Agent-authored, multi-panel
    PPTX composition (compose_data_figure) -- that pipeline needs a local
    Codex CLI and pdfcrop/node/latexmk the shared online container never
    runs. A plain grouped bar chart keeps figures reachable online without
    any of that, the same way generate_table_latex already does for tables.
    """
    headers, rows = figure_records_grid(figure_id, metrics)
    if not rows:
        raise StudioError(f"{figure_id} No data rows available for plotting.")
    definition = FIGURES[figure_id]
    configured_panels = [
        str(panel.get("title") or panel.get("id") or "").strip()
        for panel in definition.get("panels", [])
        if isinstance(panel, dict)
    ]
    observed_panels = {row[0].strip() for row in rows if row}
    if (
        len(headers) >= 4
        and len(configured_panels) >= 2
        and observed_panels
        and observed_panels.issubset(set(configured_panels))
    ):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        series_headers = headers[2:]
        figure, panel_axes = plt.subplots(
            1,
            len(configured_panels),
            figsize=(7.0, 2.45),
            sharey=True,
            squeeze=False,
        )
        for axis, panel_name in zip(panel_axes[0], configured_panels):
            panel_rows = [row for row in rows if row and row[0].strip() == panel_name]
            if not panel_rows:
                raise StudioError(f"{figure_id} panel {panel_name} has no data rows.")
            x_values = [numeric_cell(row[1]) for row in panel_rows]
            if any(value is None for value in x_values):
                raise StudioError(f"{figure_id} panel {panel_name} has a non-numeric x value.")
            for column_index, series_name in enumerate(series_headers, start=2):
                y_values = [numeric_cell(row[column_index]) for row in panel_rows]
                if any(value is None for value in y_values):
                    raise StudioError(
                        f"{figure_id} panel {panel_name} column {series_name} contains non-numeric content."
                    )
                axis.plot(
                    x_values,
                    y_values,
                    marker="o",
                    linewidth=1.35,
                    markersize=3.5,
                    label=series_name,
                )
            axis.set_title(panel_name, fontsize=8, fontweight="bold")
            axis.set_xticks(x_values)
            axis.tick_params(axis="both", labelsize=7)
            axis.grid(axis="y", linewidth=0.35, alpha=0.35)
            axis.set_xlabel(
                str(definition.get("x_axis_label") or headers[1]), fontsize=7
            )
        panel_axes[0][0].set_ylabel(
            str(definition.get("y_axis_label") or "Value"), fontsize=7
        )
        handles, legend_labels = panel_axes[0][0].get_legend_handles_labels()
        figure.legend(
            handles,
            legend_labels,
            fontsize=6.5,
            frameon=False,
            loc="upper center",
            ncol=max(1, len(legend_labels)),
            bbox_to_anchor=(0.5, 1.02),
        )
        figure.tight_layout(rect=(0, 0, 1, 0.91))
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(pdf_path, format="pdf")
        figure.savefig(png_path, format="png", dpi=150)
        plt.close(figure)
        return
    numeric_headers = headers[1:]
    if not numeric_headers:
        raise StudioError(f"{figure_id} At least one identifier column and one numeric column are required to plot.")
    labels = [row[0].replace("_", " ").strip().title() for row in rows]
    raw_series: dict[str, list[float]] = {}
    for column_index, label in enumerate(numeric_headers, start=1):
        values = []
        for row in rows:
            value = numeric_cell(row[column_index])
            if value is None:
                raise StudioError(f"{figure_id} the column{label} contains non-numeric content; cannot plot.")
            values.append(value)
        raw_series[label] = values

    # Contract-derived result grids may carry paired interval bounds beside
    # the estimate.  Treat those columns as uncertainty metadata, never as
    # additional bars (the old renderer produced three nearly identical bars
    # labelled estimate/CI-low/CI-high, which was scientifically misleading).
    interval_columns: dict[str, dict[str, list[float]]] = {}
    series: list[tuple[str, list[float]]] = []
    for label, values in raw_series.items():
        match = re.match(r"^(.*?)\s+CI\s+(low|high)$", label, re.IGNORECASE)
        if match:
            interval_columns.setdefault(match.group(1).strip(), {})[
                match.group(2).lower()
            ] = values
        else:
            series.append((label, values))
    if not series:
        raise StudioError(f"{figure_id} No estimated value column available for plotting.")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    if len(series) == 1 and {
        "cohen kappa", "llm-human spearman rho", "latency old cot (s/item)",
        "latency more (s/item)", "output old cot (tokens)", "output more (tokens)",
    }.issubset({label.casefold() for label in labels}):
        values_by_label = {
            label.casefold(): value for label, value in zip(labels, series[0][1])
        }
        figure, panel_axes = plt.subplots(1, 3, figsize=(7.0, 2.15))
        panels = [
            ("Human agreement", ["Cohen kappa", "Spearman rho"], [
                values_by_label["cohen kappa"], values_by_label["llm-human spearman rho"]
            ], (0, 1)),
            ("Latency (s/item)", ["CoT", "MORE"], [
                values_by_label["latency old cot (s/item)"], values_by_label["latency more (s/item)"]
            ], None),
            ("Output length (tokens)", ["CoT", "MORE"], [
                values_by_label["output old cot (tokens)"], values_by_label["output more (tokens)"]
            ], None),
        ]
        for axis, (title, panel_labels, panel_values, limits) in zip(panel_axes, panels):
            bars = axis.bar(panel_labels, panel_values, color=["#6b7280", "#2563eb"])
            axis.set_title(title, fontsize=8, fontweight="bold")
            axis.tick_params(axis="x", labelsize=7)
            axis.tick_params(axis="y", labelsize=7)
            axis.grid(axis="y", linewidth=0.35, alpha=0.35)
            if limits:
                axis.set_ylim(*limits)
            for bar, value in zip(bars, panel_values):
                axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:g}",
                          ha="center", va="bottom", fontsize=7)
        sample_count = values_by_label.get("samples per model")
        if sample_count is not None:
            figure.suptitle(f"Human evaluation: {sample_count:g} samples per model", fontsize=8)
        figure.tight_layout()
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(pdf_path, format="pdf")
        figure.savefig(png_path, format="png", dpi=150)
        plt.close(figure)
        return
    figure, axes = plt.subplots(figsize=(3.32, 2.4))
    positions = np.arange(len(labels))
    percent_x = all(re.fullmatch(r"[-+]?\d+(?:\.\d+)?%", label) for label in labels)
    line_chart = str(definition.get("chart_type") or "").strip().casefold() == "line"
    width = 0.8 / max(len(series), 1)
    for index, (label, values) in enumerate(series):
        interval = interval_columns.get(label, {})
        error = None
        if "low" in interval and "high" in interval:
            error = np.array([
                [max(0.0, value - low) for value, low in zip(values, interval["low"])],
                [max(0.0, high - value) for value, high in zip(values, interval["high"])],
            ])
        if line_chart or (percent_x and len(labels) >= 3):
            axes.errorbar(
                positions, values, yerr=error, marker="o", linewidth=1.25,
                capsize=2.5, label=label,
            )
        elif len(series) == 1 and error is not None:
            axes.errorbar(
                positions, values, yerr=error, marker="o", linestyle="none",
                capsize=3, label=label,
            )
            axes.axhline(0.0, color="#666666", linewidth=0.7, linestyle="--")
        else:
            axes.bar(
                positions + index * width, values, width, yerr=error,
                capsize=2.5 if error is not None else 0, label=label,
            )
    tick_positions = positions if line_chart or percent_x or (len(series) == 1 and interval_columns) else positions + width * (len(series) - 1) / 2
    axes.set_xticks(tick_positions)
    axes.set_xticklabels(labels, rotation=20, ha="right", fontsize=7)
    axes.tick_params(axis="y", labelsize=7)
    x_axis_label, y_axis_label = data_figure_axis_labels(definition)
    if x_axis_label:
        axes.set_xlabel(x_axis_label, fontsize=7)
    axes.set_ylabel(y_axis_label, fontsize=7)
    axes.grid(axis="y", linewidth=0.35, alpha=0.35)
    if len(series) > 1:
        axes.legend(
            fontsize=5.5,
            frameon=False,
            loc="lower center",
            bbox_to_anchor=(0.5, 1.01),
            ncol=min(3, len(series)),
        )
    # The LaTeX caption already carries the complete scientific description;
    # repeating it as an in-plot title wastes scarce single-column space and
    # previously leaked internal JSON filenames into the rendered figure.
    figure.tight_layout()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(pdf_path, format="pdf")
    figure.savefig(png_path, format="png", dpi=150)
    plt.close(figure)


def generate_table_latex(
    table_id: str,
    metrics: dict[str, Any],
    prompt: str = "",
    layout_mode: str | None = None,
) -> str:
    definition = TABLES[table_id]
    available_columns, available_rows = table_grid(table_id, metrics)
    spec = parse_table_prompt(
        table_id, prompt, available_columns, available_rows
    )
    columns = spec["columns"]
    rows = spec["rows"]
    wide = (
        layout_mode == "two-column"
        if layout_mode in {"single-column", "two-column"}
        else definition["width"].startswith("two-column")
    )
    environment = "table*" if wide else "table"
    alignment = "l" + "c" * (len(columns) - 1)
    compact_wide_header = wide and len(columns) >= 8

    def header_cell(value: Any, column_index: int) -> str:
        escaped = latex_escape_cell(value)
        if not compact_wide_header or column_index == 0:
            return escaped
        # Repeated condition headers such as ``Positive +1`` otherwise force
        # a many-column table through a severe global resize.  A short stack
        # preserves the exact label while keeping the body numbers readable.
        parts = str(value).strip().rsplit(None, 1)
        if len(parts) == 2 and len(parts[0]) >= 3 and len(parts[1]) <= 4:
            return (
                r"\shortstack{" + latex_escape_cell(parts[0]) + r"\\"
                + latex_escape_cell(parts[1]) + "}"
            )
        return escaped
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
        *(
            [r"  \setlength{\tabcolsep}{3.5pt}"]
            if compact_wide_header
            else []
        ),
        # Long row labels (a common shape for method-comparison tables) can
        # make the tabular wider than the column that holds it -- a single
        # ("table", not "table*") environment does not know to reserve
        # extra horizontal space for that overflow, so it silently prints
        # on top of whatever body text the two-column layout already
        # flowed alongside it. Measure the tabular's natural width and only
        # shrink (never stretch a table that already fits) to guarantee it
        # never bleeds into adjacent text.
        r"  \sbox0{\begin{tabular}{" + alignment + "}",
        "    \\toprule",
        "    "
        + " & ".join(
            header_cell(item, column_index)
            for column_index, item in enumerate(columns)
        )
        + r" \\",
        "    \\midrule",
    ]
    for row_index, row in enumerate(rows):
        cells = []
        for column_index, item in enumerate(row):
            display_item = (
                f"{item:.3f}"
                if isinstance(item, float) and -1.0 <= item <= 1.0
                else item
            )
            escaped = latex_escape_cell(display_item)
            if (row_index, column_index) in best_cells:
                escaped = f"\\textbf{{{escaped}}}"
            cells.append(escaped)
        lines.append(
            "    " + " & ".join(cells) + r" \\"
        )
    lines.extend(
        [
            "    \\bottomrule",
            "  \\end{tabular}}",
            r"  \ifdim\wd0>\linewidth\resizebox{\linewidth}{!}{\usebox0}\else\usebox0\fi",
            f"  \\caption{{{latex_escape_cell(spec['caption'])}}}",
            f"  \\label{{{definition['label']}}}",
            f"\\end{{{environment}}}",
        ]
    )
    return normalize_table_numeric_precision("\n".join(lines))


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
            raise StudioError(f"Cannot generate LaTeX table preview: missing {command}.")
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
            raise StudioError("LaTeX Table preview failed to compile.\n" + str(exc)) from exc
        temporary_pdf = build_dir / "cropped.pdf"
        temporary_png = build_dir / "preview.png"
        if not temporary_pdf.exists() or not temporary_png.exists():
            raise StudioError("LaTeX The table preview tool did not generate PDF or PNG.")
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


def repair_artifact_reference_contract(
    *,
    model: str,
    response_id: str,
    text: str,
    bound_artifacts: list[dict[str, Any]],
) -> tuple[str, str]:
    """Restore mandatory artifact references after any model post-processing."""
    reference_error = artifact_reference_error(text, bound_artifacts)
    if not reference_error:
        return text, response_id
    allowed = [item["required_reference"] for item in bound_artifacts]
    correction = post_openai(
        {
            "model": model,
            "store": True,
            "previous_response_id": response_id,
            "instructions": (
                "Return only the complete corrected LaTeX-ready paragraph. Preserve "
                "all claims, numbers, citations, heading, and wording. Include each "
                "allowed configured artifact cross-reference exactly once and remove "
                "every other configured figure or table cross-reference. Do not "
                "explain the correction."
            ),
            "input": (
                f"Reference contract violation: {reference_error}\n"
                f"<required_references>{json.dumps(allowed, ensure_ascii=False)}</required_references>\n"
                f"<paragraph_to_correct>{text}</paragraph_to_correct>"
            ),
            "text": {"verbosity": "low"},
        }
    )
    repaired = normalize_latex_ready_text(extract_output_text(correction))
    repaired_id = str(correction.get("id") or "")
    if not repaired or not repaired_id:
        raise StudioError("Chart reference repair did not return a valid paragraph.")
    remaining = artifact_reference_error(repaired, bound_artifacts)
    if remaining:
        raise StudioError("GPT Still after correction." + remaining)
    return repaired, repaired_id


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
            recovered[match.group(1)] = strip_redundant_section_name_leadin(
                text, str(SECTION_MAP[section]["title"])
            )
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
            recovered[paragraph_id] = strip_redundant_section_name_leadin(
                text, str(SECTION_MAP[section]["title"])
            )
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
        str(paragraph["id"]): strip_redundant_section_name_leadin(
            block, str(SECTION_MAP[section]["title"])
        )
        for paragraph, block in zip(paragraphs, blocks)  # noqa: B905 - equal lengths checked above
    }


def repair_redundant_section_leadins_in_manuscript(state: dict[str, Any]) -> bool:
    """Rewrite only sections whose stored source still contains duplicate name labels."""
    changed = False
    for section, section_state in state.get("sections", {}).items():
        metadata = SECTION_MAP.get(section)
        if not metadata:
            continue
        source_path = PAPER / "sections" / metadata["file"]
        source = read_text(source_path, 500000)
        title_pattern = r"\s+".join(
            re.escape(token) for token in str(metadata["title"]).split()
        )
        aliases = [title_pattern]
        if str(metadata["title"]).casefold() == "abstract":
            aliases.extend(("Abstrct", "Abtract"))
        if not re.search(
            rf"(?im)^\s*(?:\\textbf\{{\s*)?(?:{'|'.join(aliases)})\s*"
            rf"(?:[.:]\s*|[—–-]\s+|\}}\s*)",
            source,
        ):
            continue
        repaired, _accepted = render_section_source(
            section, section_state, state["figures"], state["tables"]
        )
        if repaired != source:
            temporary = source_path.with_suffix(".tex.tmp")
            temporary.write_text(repaired, encoding="utf-8")
            os.replace(temporary, source_path)
            changed = True
    return changed


def repair_online_placeholder_references_in_manuscript(
    state: dict[str, Any],
) -> bool:
    """Upgrade accepted hosted prose after placeholder bindings are introduced."""
    if not ONLINE_PROJECT_MODE:
        return False
    changed_sections: set[str] = set()
    for section, section_state in state.get("sections", {}).items():
        for paragraph in section_state.get("paragraphs", []):
            text = str(paragraph.get("accepted_text") or "").strip()
            if not text:
                continue
            placeholder_ids = [
                artifact_id
                for artifact_id in paragraph.get("artifacts", [])
                if is_hosted_placeholder_artifact(artifact_id)
            ]
            missing = artifact_reference_issues(
                text, artifact_writing_context(placeholder_ids, state.get("figures"))
            )["missing"]
            if not missing:
                continue
            references = [str(item["required_reference"]) for item in missing]
            if len(references) == 1:
                joined = references[0]
            else:
                joined = ", ".join(references[:-1]) + " and " + references[-1]
            paragraph["accepted_text"] = (
                text
                + " The corresponding planned analysis is reserved in "
                + joined
                + "; these placeholders specify the intended evidence display and do "
                "not imply that measurements have already been observed."
            )
            changed_sections.add(section)
    for section in changed_sections:
        source, accepted = render_section_source(
            section,
            state["sections"][section],
            state.get("figures", {}),
            state.get("tables", {}),
        )
        target = PAPER / "sections" / SECTION_MAP[section]["file"]
        target.write_text(source, encoding="utf-8")
        state["sections"][section]["accepted_text"] = accepted
    return bool(changed_sections)


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
    state: dict[str, Any], *, build_table_previews: bool = True,
    artifact_ids: list[str] | None = None,
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

    allowed = set(artifact_ids) if artifact_ids is not None else None
    for figure_id in FIGURE_ORDER:
        if allowed is not None and figure_id not in allowed:
            continue
        definition = FIGURES[figure_id]
        # In the hosted two-file flow, an explicit placeholder is itself the
        # intended deliverable until real experiment data is uploaded locally.
        # Keep its labelled float in the manuscript; never pass its deliberately
        # unresolved data_grid to the deterministic renderer.
        if is_hosted_placeholder_artifact(figure_id):
            continue
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
            # Generated/researcher captions in state are the canonical editable
            # text.  Parsing the rendered LaTeX back into that field preserves
            # escape sequences and caused each restart to double-escape math
            # such as ``10^{-7}`` and prose ``90\%``.
            "caption": (
                stored.get("caption")
                if stored.get("caption_source") in {"researcher", "paragraph_accept"}
                and str(stored.get("caption") or "").strip()
                else latex_command_content(latex, "caption")
                or stored.get("caption")
                or definition["caption"]
            ),
            "progress": 100,
            "progress_message": "Restored image workbench from the paper source code.",
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
                        progress_message="Restored from the final data figure in the paper.",
                    )
                    changed = True
        for field, value in updates.items():
            if stored.get(field) != value:
                stored[field] = value
                changed = True

    for table_id in TABLE_ORDER:
        if allowed is not None and table_id not in allowed:
            continue
        definition = TABLES[table_id]
        if is_hosted_placeholder_artifact(table_id):
            continue
        stored = state["tables"][table_id]
        if (
            stored.get("status") == "pending"
            and str(stored.get("progress_message") or "").startswith(
                "Artifact contract changed"
            )
        ):
            continue
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
        if table_latex_is_placeholder(latex):
            # A pending placeholder has the final label solely to keep paragraph
            # compilation transactional.  It is not an editable result table.
            continue
        recovered_layout_mode = table_layout_mode_from_latex(latex)
        try:
            latex = validate_table_latex_source(
                table_id, latex, layout_mode=recovered_layout_mode
            )
        except StudioError as exc:
            # A stale or manually edited float must not make the entire editor
            # unavailable. Keep the manuscript untouched for recovery, but make
            # the workbench explicitly pending so the invalid table cannot be
            # mistaken for an approved deliverable.
            stored.update(
                status="pending",
                approved_at=None,
                progress=0,
                progress_message="Recovered table failed validation; regenerate it.",
                last_message=str(exc),
            )
            changed = True
            continue
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
            "progress_message": "Restored table workbench from the paper source code.",
            "layout_mode": recovered_layout_mode,
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
                    "Table LaTeX restored but browser preview generation failed" + str(exc)
                )
            else:
                stored["last_message"] = "Restored editable tables and preview from the paper source."
            changed = True
    return changed


def direct_full_draft_table_source(
    table_id: str, stored: dict[str, Any], metrics: dict[str, Any]
) -> tuple[str, str, bool]:
    """Return table LaTeX without overwriting a researcher-approved revision."""
    approved_latex = str(stored.get("latex") or "").strip()
    duplicate_extracted_header = bool(
        re.search(
            r"\\midrule\s*(?:\r?\n)\s*(?:Method / variant|Case type)\s*&",
            approved_latex,
            re.IGNORECASE,
        )
    )
    if (
        stored.get("status") == "approved"
        and approved_latex
        and not table_latex_is_placeholder(approved_latex)
        and not duplicate_extracted_header
    ):
        configured_caption = str(TABLES[table_id].get("caption") or "").strip()
        existing_caption = latex_command_content(approved_latex, "caption").strip()
        if existing_caption.casefold() == table_id.casefold() and configured_caption:
            approved_latex = re.sub(
                r"\\caption\{[^{}]*\}",
                lambda _match: "\\caption{" + latex_escape_caption(configured_caption) + "}",
                approved_latex,
                count=1,
            )
        return (
            validate_table_latex_source(
                table_id,
                approved_latex,
                layout_mode=str(stored.get("layout_mode") or "") or None,
            ),
            str(stored.get("generation_prompt") or default_table_prompt(table_id)),
            True,
        )
    prompt = default_table_prompt(table_id)
    return (
        validate_table_latex_source(
            table_id,
            generate_table_latex(
                table_id,
                metrics,
                prompt,
                layout_mode=str(stored.get("layout_mode") or "") or None,
            ),
            layout_mode=str(stored.get("layout_mode") or "") or None,
        ),
        prompt,
        False,
    )


def materialize_batch_artifacts(
    state: dict[str, Any], artifact_ids: list[str] | None = None
) -> bool:
    """Fill bound figure/table workbenches after unattended prose drafting.

    Direct drafting must end in the same project state as interactive acceptance.
    Only configured deliverable paths are accepted, and every artifact remains gated
    on its bound paragraph being present. Data tables are regenerated from the real
    metrics fixture rather than copied from prose.
    """
    changed = False
    allowed = set(artifact_ids) if artifact_ids is not None else None
    for figure_id in FIGURE_ORDER:
        if allowed is not None and figure_id not in allowed:
            continue
        definition = FIGURES[figure_id]
        if is_hosted_placeholder_artifact(figure_id):
            continue
        stored = state["figures"][figure_id]
        binding = first_artifact_binding(figure_id)
        if not binding:
            continue
        section, paragraph_id = binding
        paragraph, _index = paragraph_by_id(state, section, paragraph_id)
        if not str(paragraph.get("accepted_text", "")).strip():
            continue
        paths = figure_paths(figure_id)
        if definition.get("kind") == "data" and not (
            paths["pdf"].is_file() and paths["preview"].is_file()
        ):
            # Resetting a generated paper deliberately removes prior outputs.
            # A browser full-draft rerun must therefore recreate deterministic
            # result figures from metrics instead of merely recovering files
            # left by an earlier run.
            render_data_figure_deterministic(
                figure_id, metrics_bundle(), paths["pdf"], paths["preview"]
            )
            changed = True
        if not paths["pdf"].is_file():
            continue
        if definition.get("kind") == "mechanism":
            if not paths["pptx"].is_file():
                continue
            if not completed_mechanism_deliverables_match_current_draft(figure_id):
                # A failed redraw may coexist with an older PDF/PPTX. Never
                # approve those stale deliverables for the new Prompt/draft.
                continue
        ensure_figure_caption_before_approval(state, figure_id)
        updates = {
            "status": "approved",
            "approved_at": int(paths["pdf"].stat().st_mtime),
            "placement_after": stored.get("placement_after") or paragraph_id,
            "progress": 100,
            "progress_message": "Recovered image workspace from the batch writing configuration artifact.",
        }
        if definition.get("kind") == "data":
            updates["composed_at"] = int(paths["pdf"].stat().st_mtime)
            for panel in stored.get("panels", {}).values():
                panel.update(
                    status="built",
                    progress=100,
                    progress_message="Recovered from the validation results figure.",
                )
        for field, value in updates.items():
            if stored.get(field) != value:
                stored[field] = value
                changed = True

    metrics = metrics_bundle()
    for table_id in TABLE_ORDER:
        if allowed is not None and table_id not in allowed:
            continue
        definition = TABLES[table_id]
        if is_hosted_placeholder_artifact(table_id):
            continue
        stored = state["tables"][table_id]
        binding = first_artifact_binding(table_id)
        if not binding:
            continue
        section, paragraph_id = binding
        paragraph, _index = paragraph_by_id(state, section, paragraph_id)
        if not str(paragraph.get("accepted_text", "")).strip():
            continue
        # Project configuration is the canonical unattended brief for an
        # unfinished table.  A valid researcher-approved revision is already
        # canonical manuscript content and must survive a later full-draft run.
        latex, prompt, preserved_approved = direct_full_draft_table_source(
            table_id, stored, metrics
        )
        compile_table_preview(table_id, latex)
        updates = {
            "latex": latex,
            "status": "approved",
            "approved_at": (
                stored.get("approved_at") or int(time.time())
                if preserved_approved
                else int(time.time())
            ),
            "placement_after": stored.get("placement_after") or paragraph_id,
            "progress": 100,
            "progress_message": (
                "Retained researcher confirmed tables and refreshed preview."
                if preserved_approved
                else "Editable tables and previews restored from validated metrics."
            ),
            "last_message": (
                stored.get("last_message") or "The table confirmed by the researcher has been retained."
                if preserved_approved
                else "Table numbers are deterministically generated from paper/metrics.json."
            ),
            "generation_prompt": prompt,
        }
        for field, value in updates.items():
            if stored.get(field) != value:
                stored[field] = value
                changed = True

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
            "LaTeX compilation failed after batch writing charts were materialized.\n" + compile_result.message
        )
    state["compile"] = {
        "status": "ok",
        "message": compile_result.message,
        "updated_at": int(time.time()),
    }
    return True


def batch_figure_has_real_deliverables(
    state: dict[str, Any], figure_id: str
) -> bool:
    """Reject placeholder-only or stale figures at the batch completion gate."""
    if is_hosted_placeholder_artifact(figure_id):
        return True
    stored = state.get("figures", {}).get(figure_id, {})
    if stored.get("status") != "approved":
        return False
    definition = FIGURES[figure_id]
    paths = figure_paths(figure_id)
    if definition.get("kind") == "data":
        expected_panels = [
            str(panel.get("id"))
            for panel in definition.get("panels", [])
            if panel.get("id")
        ]
        stored_panels = stored.get("panels", {})
        return bool(
            stored.get("composed_at")
            and paths["pdf"].is_file()
            and paths["preview"].is_file()
            and all(
                stored_panels.get(panel_id, {}).get("status") == "built"
                for panel_id in expected_panels
            )
        )
    if definition.get("kind") == "mechanism":
        return completed_mechanism_deliverables_match_current_draft(figure_id)
    return paths["pdf"].is_file()


def pending_batch_artifacts(
    state: dict[str, Any], artifact_ids: list[str] | None = None
) -> list[str]:
    """List paragraph-bound artifacts that still need researcher-visible work.

    A prose batch is not a completed paper while a configured figure or table is
    still pending. Ready mechanism figures are generated automatically when their
    required paragraphs are accepted; this list keeps the batch visibly pending
    until that background work has produced and inserted the final deliverables.
    """
    pending: list[str] = []
    allowed = set(artifact_ids) if artifact_ids is not None else None
    for artifact_id in [*FIGURE_ORDER, *TABLE_ORDER]:
        if allowed is not None and artifact_id not in allowed:
            continue
        # An explicitly configured hosted placeholder is the complete online
        # deliverable.  It must remain visible and referenceable in the manuscript,
        # while the exported project carries the actual table/figure completion to
        # the local workflow. Counting that unreachable approval as pending strands
        # an otherwise finished online draft forever.
        if is_hosted_placeholder_artifact(artifact_id):
            continue
        binding = first_artifact_binding(artifact_id)
        if not binding:
            continue
        section, paragraph_id = binding
        paragraph, _index = paragraph_by_id(state, section, paragraph_id)
        if not str(paragraph.get("accepted_text", "")).strip():
            continue
        collection = "figures" if artifact_id in FIGURES else "tables"
        artifact_state = state[collection][artifact_id]
        if artifact_id in FIGURES:
            ready = batch_figure_has_real_deliverables(state, artifact_id)
        else:
            ready = artifact_state.get("status") == "approved"
        if not ready:
            pending.append(artifact_id)
    return pending


def refresh_full_draft_artifact_status(state: dict[str, Any]) -> None:
    """Synchronize independent full-paper and section artifact completion."""
    for job_key in ("full_draft_job", "section_draft_job"):
        job = state.get(job_key)
        if not isinstance(job, dict) or job.get("status") not in {
            "completed",
            "artifacts_pending",
        }:
            continue
        section_scope = job_key == "section_draft_job"
        artifact_ids = (
            [str(item) for item in job.get("artifact_ids", [])]
            if section_scope
            else None
        )
        pending = pending_batch_artifacts(state, artifact_ids)
        job["pending_artifacts"] = pending
        if pending:
            job["status"] = "artifacts_pending"
            job["progress_message"] = (
                (
                    "The current Section body has been written in LaTeX; completing and confirming binding charts."
                    if section_scope
                    else "The body text has been fully written in LaTeX; please complete and confirm at the figure workbench."
                )
                + ", ".join(pending)
            )
        else:
            if not section_scope:
                quality_issues = completed_manuscript_issues(state)
                if quality_issues:
                    job["status"] = "failed"
                    job["finished_at"] = int(time.time())
                    job["progress_message"] = (
                        "Deterministic quality check after full text generation failed."
                        + "; ".join(quality_issues)
                    )
                    continue
            job["status"] = "completed"
            job["progress_message"] = (
                (
                    f"{SECTION_MAP[str(job.get('section'))]['title']} The main text has been written into LaTeX and PDF."
                    "The planned chart is retained as placeholder."
                    if section_scope
                    else "The full first draft has been written in LaTeX and PDF compilation completed; planned charts are kept as placeholders."
                )
                if ONLINE_PROJECT_MODE
                else (
                    f"{SECTION_MAP[str(job.get('section'))]['title']} The body text and bound charts have all been completed."
                    "Written into LaTeX and PDF."
                    if section_scope
                    else "The full first draft and all figures have been written into LaTeX and PDF compilation completed."
                )
            )


def completed_manuscript_issues(state: dict[str, Any]) -> list[str]:
    """Return deterministic defects that forbid a completed-full-draft status."""
    issues: list[str] = []
    active_metrics = metrics_bundle()
    lightweight_project = (
        active_metrics.get("lightweight_project", {})
        if isinstance(active_metrics, dict)
        else {}
    )
    online_without_results = bool(
        ONLINE_PROJECT_MODE
        and isinstance(lightweight_project, dict)
        and lightweight_project.get("numeric_policy")
        == "replace_quantitative_values_with_xx"
    )
    manuscript_sources: list[tuple[str, str]] = []
    for section, section_state in state.get("sections", {}).items():
        metadata = SECTION_MAP.get(section, {})
        source = read_text(PAPER / "sections" / str(metadata.get("file", "")), 500000)
        manuscript_sources.append((section, source))
        if metadata.get("render") != "abstract" and len(
            re.findall(r"^\\section\*?\{", source, flags=re.M)
        ) != 1:
            issues.append(f"{section}: expected exactly one managed section heading")
        for paragraph in section_state.get("paragraphs", []):
            accepted = str(paragraph.get("accepted_text") or "")
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in appendix_content_issues(section, accepted)
            )
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in execution_record_contradiction_issues(accepted)
            )
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in experimental_setup_issues(
                    section, str(paragraph.get("purpose") or ""), accepted
                )
            )
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in manuscript_completion_placeholder_issues(accepted)
            )
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in manuscript_markup_issues(accepted)
            )
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in latex_prose_issues(accepted)
            )
            if online_without_results:
                issues.extend(
                    f"{section}/{paragraph.get('id')}: {item}"
                    for item in unexecuted_result_claim_issues(accepted)
                )
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in unsupported_internal_reference_issues(accepted)
            )
            issues.extend(
                f"{section}/{paragraph.get('id')}: {item}"
                for item in unsupported_appendix_numeric_issues(
                    section,
                    accepted,
                    section_evidence(
                        section,
                        [str(item) for item in paragraph.get("artifacts", [])],
                    ),
                )
            )
    label_locations: dict[str, list[str]] = {}
    for section, source in manuscript_sources:
        for label in re.findall(r"\\label\{([^{}]+)\}", source):
            label_locations.setdefault(label, []).append(section)
    for label, locations in label_locations.items():
        if len(locations) > 1:
            issues.append(
                f"duplicate LaTeX label {label}: " + ", ".join(locations)
            )
    actual_labels = set(label_locations)
    for section, source in manuscript_sources:
        for label in dict.fromkeys(
            re.findall(r"\\(?:ref|pageref|autoref)\{([^{}]+)\}", source)
        ):
            if label not in actual_labels:
                issues.append(f"{section}: unresolved internal reference {label}")
    for table_id, stored in state.get("tables", {}).items():
        if is_hosted_placeholder_artifact(table_id):
            continue
        if stored.get("status") != "approved" or table_latex_is_placeholder(
            str(stored.get("latex") or "")
        ):
            issues.append(f"{table_id}: unresolved table placeholder")
    for figure_id in state.get("figures", {}):
        if is_hosted_placeholder_artifact(figure_id):
            continue
        if not batch_figure_has_real_deliverables(state, figure_id):
            issues.append(f"{figure_id}: unresolved figure placeholder or missing real deliverables")
    metrics = metrics_bundle()
    if not bool(metrics.get("synthetic", False)):
        for path in (PAPER / "sections").glob("*.tex"):
            if "[SYNTHETIC]" in read_text(path, 500000):
                issues.append(f"{path.name}: unexpected synthetic marker")
    compile_log = read_text(PAPER / "main.log", 2_000_000)
    overfull_points = [
        float(value)
        for value in re.findall(r"Overfull \\hbox \(([0-9.]+)pt too wide\)", compile_log)
    ]
    if any(value > 1.0 for value in overfull_points):
        issues.append(
            "PDF contains overfull boxes wider than 1pt: "
            + ", ".join(f"{value:.1f}pt" for value in overfull_points if value > 1.0)
        )
    budget = page_budget_status()
    if budget["status"] == "over":
        issues.append(
            "submission body exceeds the configured page budget: "
            f"{budget['content_pages']} pages for a {budget['limit']}-page limit "
            "(references excluded)"
        )
    elif budget["status"] == "under":
        measured = budget.get("last_page_fill")
        minimum = budget.get("minimum_last_page_fill")
        fill_detail = (
            f", final-page fill {float(measured):.1%} below {float(minimum):.1%}"
            if measured is not None and minimum is not None
            else ""
        )
        issues.append(
            "submission body does not fill the configured page target: "
            f"{budget['content_pages']} measured pages for a {budget['limit']}-page target"
            f"{fill_detail} (references excluded)"
        )
    return issues


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
        raise StudioError("Local Agent did not return a complete table.* LaTeX.")
    return match.group(1).strip()


def normalize_table_numeric_precision(latex: str) -> str:
    """Keep publication tables readable without changing source provenance."""
    return re.sub(
        r"(?<![\w.])(-?\d+\.\d{4,})(?![\w.])",
        lambda match: f"{float(match.group(1)):.3f}",
        latex,
    )


def table_layout_mode_from_latex(latex: str) -> str:
    """Return the float span encoded by one complete table environment."""
    if re.search(r"\\begin\{table\*\}", latex):
        return "two-column"
    if re.search(r"\\begin\{table\}", latex):
        return "single-column"
    raise StudioError("Table LaTeX missing table/table.* Environment.")


def convert_table_latex_layout(table_id: str, latex: str, layout_mode: str) -> str:
    """Convert only the outer float environment, preserving every table cell."""
    if layout_mode not in {"single-column", "two-column"}:
        raise StudioError("Table layout supports only single-column or two-column.")
    source = latex.strip()
    current_mode = table_layout_mode_from_latex(source)
    if current_mode == layout_mode:
        return validate_table_latex_source(table_id, source, layout_mode=layout_mode)
    environment = "table*" if layout_mode == "two-column" else "table"
    placement = "t" if layout_mode == "two-column" else "tb"
    source = re.sub(
        r"\\begin\{table\*?\}(?:\[[^\]]*\])?",
        lambda _match: f"\\begin{{{environment}}}[{placement}]",
        source,
        count=1,
    )
    source = re.sub(
        r"\\end\{table\*?\}",
        lambda _match: f"\\end{{{environment}}}",
        source,
        count=1,
    )
    # Resize against the active float, not the whole page.  Keeping textwidth
    # when converting table* to table makes a nominally single-column table
    # protrude by an entire column.
    target_width = r"\textwidth" if layout_mode == "two-column" else r"\linewidth"
    source = re.sub(
        r"(\\resizebox\{)\\(?:textwidth|columnwidth|linewidth)(\}\{!\}\{)",
        lambda match: match.group(1) + target_width + match.group(2),
        source,
    )
    return validate_table_latex_source(table_id, source, layout_mode=layout_mode)


def validate_table_latex_source(
    table_id: str, latex: str, *, layout_mode: str | None = None
) -> str:
    source = latex.strip()
    definition = TABLES[table_id]
    if not source:
        raise StudioError("Table LaTeX cannot be empty.")
    if not re.search(r"\\begin\{table\*?\}", source):
        raise StudioError("Table LaTeX missing table/table.* Environment.")
    if layout_mode is not None and layout_mode not in {"single-column", "two-column"}:
        raise StudioError("Table layout supports only single-column or two-column.")
    expected_wide = (
        layout_mode == "two-column"
        if layout_mode is not None
        else str(definition.get("width", "")).startswith("two-column")
    )
    expected_environment = "table*" if expected_wide else "table"
    if not re.search(
        rf"\\begin\{{{re.escape(expected_environment)}\}}.*?"
        rf"\\end\{{{re.escape(expected_environment)}\}}",
        source,
        flags=re.DOTALL,
    ):
        raise StudioError(
            f"Table width configuration requires use of {expected_environment} Environment;"
            "Do not degrade a two column table to a single column or vice versa."
        )
    expected_label = f"\\label{{{definition['label']}}}"
    if expected_label not in source:
        raise StudioError(f"Tables must retain fixed labels. {expected_label}.")
    if "\\caption{" not in source:
        raise StudioError("LaTeX table missing caption.")
    if not expected_wide and re.search(
        r"\\resizebox\{\\textwidth\}\{!\}", source
    ):
        raise StudioError(
            "Single-column tables must resize to \\linewidth or \\columnwidth, not \\textwidth."
        )
    return source


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
        "more numbers",
        "more than this",
        "other numbers",
        "more experiments",
        "more experimental results",
        "additional numbers",
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
            raise StudioError("Online agent requires the OpenAI API Key for the current writing session.")
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
        raise StudioError("Local Agent returns a table identical to the current version.")
    if requests_reference_expansion(instruction):
        before = table_numeric_cells(current)
        after = table_numeric_cells(revised)
        if len(after) <= len(before) and set(after).issubset(set(before)):
            raise StudioError(
                "You request more experimental numbers, but the local Agent did not add any from traceable results."
                "Any traceable values; the current draft has not been overwritten."
            )


def edit_table_with_local_agent(
    table_id: str,
    latex: str,
    instruction: str,
    *,
    metrics: dict[str, Any] | None = None,
    layout_mode: str | None = None,
) -> str:
    """Ask the installed Codex CLI—not the Responses API—to revise one table."""
    codex = shutil_which("codex")
    if not codex:
        raise StudioError("Local codex CLI not found; cannot invoke the local Agent.")
    instruction = instruction.strip()
    if not instruction:
        raise StudioError("Please specify how the local Agent should modify the table.")
    definition = TABLES[table_id]
    if layout_mode not in {None, "single-column", "two-column"}:
        raise StudioError("Table layout supports only single-column or two-column.")
    layout_mode = layout_mode or (
        table_layout_mode_from_latex(latex)
        if latex.strip()
        else (
            "two-column"
            if str(definition.get("width", "")).startswith("two-column")
            else "single-column"
        )
    )
    required_environment = "table*" if layout_mode == "two-column" else "table"
    resize_width = r"\textwidth" if layout_mode == "two-column" else r"\linewidth"
    columns, rows = table_grid(table_id, metrics or metrics_bundle())
    evidence = json.dumps(
        {"columns": columns, "rows": rows},
        ensure_ascii=False,
        indent=2,
    )
    action = "Rewrite the current LaTeX table." if latex.strip() else "Generate LaTeX table draft from scratch."
    prompt = f"""You are the Paper Studio local table agent. Based on the researchers free text requirements,
{action}.Return only a single complete table.* Environment: do not use Markdown fences; do not explain.
Do not modify repository files either.

Hard constraints:
1. Can only use <traceable_results> Experiment values explicitly appearing must not be created, inferred, or rewritten.
   Any numbers; the reference paper is not the source of experimental results for this project.
2. Must preserve fixed tags. \\label{{{definition['label']}}}, Preserve the caption.
3. Maintain booktabs academic table style; captions appear after the tabular.
4. You can modify grouping headers column and row order alignment font size bold caption wording and annotations as required.
5. When the current data is a test fixture, all existing [SYNTHETIC] Markers must be preserved as is.
6. Only use standard LaTeX and the commands provided by booktabs. Do not use \\multirow, \\makecell,
   tabularx, adjustbox Or any commands that require additional packages; group header uses \\multicolumn
   and \\cmidrule Implementation. The wide table can use the graphicx provided.
   Use \\resizebox{{{resize_width}}}{{!}}{{...}}
   when resizing this {layout_mode} table.
7. All decimal metrics are displayed to three decimal places; this is display precision and must not alter row column mapping or
   Use non traceable new values.
8. Must use {required_environment} Floating environment; this is the current choice by the researcher.
   {layout_mode} Formatting; do not switch by yourself.

<researcher_instruction>
{instruction}
</researcher_instruction>

<traceable_results>
{evidence}
</traceable_results>

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
            raise StudioError("Local Agent table modification timed out.") from exc
        if process.returncode:
            diagnostic = (process.stdout + "\n" + process.stderr).strip()
            raise StudioError(
                "Local agent execution failed.\n"
                + (diagnostic[-2400:] or "codex exec returned a non-zero status.")
            )
        if not output.exists():
            raise StudioError("Local Agent did not produce a final reply.")
        revised = normalize_table_numeric_precision(
            extract_agent_table_latex(
                output.read_text(encoding="utf-8", errors="replace")
            )
        )
    return validate_table_latex_source(
        table_id,
        revised,
        layout_mode=layout_mode,
    )


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
            stored["progress_message"] = "Local codex agent is rewriting LaTeX tables."
            stored["job_revision"] = int(stored.get("job_revision", 0)) + 1
            layout_mode = str(
                stored.get("layout_mode")
                or (
                    "two-column"
                    if str(TABLES[table_id].get("width", "")).startswith("two-column")
                    else "single-column"
                )
            )
            save_state(state)
        revised = edit_table_with_local_agent(
            table_id,
            latex,
            instruction,
            metrics=metrics_bundle(),
            layout_mode=layout_mode,
        )
        require_substantive_table_revision(latex, revised, instruction)
        try:
            compile_table_preview(table_id, revised)
        except StudioError as first_error:
            repair_instruction = (
                instruction
                + "\n\nYour previous version of LaTeX failed local compilation; please fix the real error below."
                "Keep the original modification targets and all data unchanged; use only standard LaTeX and booktabs."
                "Do not use commands that require additional packages.\n<compile_error>\n"
                + str(first_error)[-1800:]
                + "\n</compile_error>"
            )
            revised = edit_table_with_local_agent(
                table_id,
                revised,
                repair_instruction,
                metrics=metrics_bundle(),
                layout_mode=layout_mode,
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
                f"Experiment value cells are from {before_cells} Expanded to {after_cells} one."
                if after_cells > before_cells
                else "Table structure or text updated; the number of experimental value cells remains unchanged."
            )
            stored.update(
                {
                    "status": "built",
                    "latex": revised,
                    "agent_history": history[-20:],
                    "revision": int(stored.get("revision", 0)) + 1,
                    "progress": 100,
                    "progress_message": "Local Agent modification complete; LaTeX preview recompiled.",
                    "last_message": (
                        "Local Agent has modified the table according to the free text Prompt."
                        f"{change_summary}Results pass fixed label and caption validation and recompile."
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
                "placeholder_only": is_hosted_placeholder_artifact(table_id),
                "placeholder_message": (
                    ONLINE_PLACEHOLDER_TABLE_MESSAGE
                    if is_hosted_placeholder_artifact(table_id)
                    else ""
                ),
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
                "layout_mode": stored.get("layout_mode")
                or (
                    "two-column"
                    if definition["width"].startswith("two-column")
                    else "single-column"
                ),
                "width": stored.get("layout_mode") or definition["width"],
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


def _is_experiment_section(section: str) -> bool:
    title = str(SECTION_MAP.get(section, {}).get("title", "")).lower()
    return section.lower() in {"e", "experiment", "experiments"} or "experiment" in title


def _is_method_section(section: str) -> bool:
    title = str(SECTION_MAP.get(section, {}).get("title", "")).lower()
    return section.lower() in {"m", "method", "methods", "methodology"} or any(
        token in title for token in ("method", "methodology", "approach")
    )


def _is_discussion_section(section: str) -> bool:
    title = str(SECTION_MAP.get(section, {}).get("title", "")).lower()
    return section.lower() in {"d", "discussion", "analysis"} or any(
        token in title for token in ("discussion", "analysis")
    )


def _is_related_work_section(section: str) -> bool:
    title = str(SECTION_MAP.get(section, {}).get("title", "")).lower()
    return section.lower() in {"rw", "related_work", "related-work"} or (
        "related work" in title
    )


def unexecuted_experiment_tense_issues(section: str, text: str) -> list[str]:
    """Detect result-like present tense in hosted plan-only experiments.

    The online flow intentionally has no experiment-result upload. Prompting alone is
    not a sufficient guard because a model can turn an approved future-tense plan into
    conventional camera-ready present tense, such as ``we report`` or ``Table 1
    compares``. These compact patterns trigger one constrained correction pass.
    """
    if not _is_experiment_section(section):
        return []
    patterns = {
        "first-person present-tense experiment claim": re.compile(
            r"\bwe\s+(?:apply|assess|analy[sz]e|compare|compute|construct|demonstrate|"
            r"evaluate|find|measure|observe|quantify|record|report|run|show|test|"
            r"use|validate)\b",
            re.IGNORECASE,
        ),
        "present-tense artifact result claim": re.compile(
            r"\b(?:figure|table)\s*~?\\ref\{[^}]+\}\s+"
            r"(?:compares|demonstrates|depicts|presents|reports|shows|summarizes)\b",
            re.IGNORECASE,
        ),
    }
    issues = [label for label, pattern in patterns.items() if pattern.search(text)]
    prose = re.sub(r"\\(?:cite\w*|ref)\{[^}]*\}", "", text)
    word_count = len(re.findall(r"\b[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?\b", prose))
    if word_count > 85:
        issues.append(f"plan-only experiment paragraph exceeds 85 words: {word_count}")
    return issues


def unexecuted_result_claim_issues(text: str) -> list[str]:
    """Reject claims that a result exists in the hosted no-results workflow."""
    patterns = {
        "past-tense study completion claim": re.compile(
            r"\b(?:we|this paper|the study|the analysis)\s+"
            r"(?:investigated|evaluated|tested|reported|found|observed|demonstrated|"
            r"validated|established|showed)\b",
            re.IGNORECASE,
        ),
        "result-support claim": re.compile(
            r"\b(?:the\s+)?(?:results?|findings?|experiments?|empirical evidence)\s+"
            r"(?:support|show|demonstrate|indicate|confirm|reveal|establish|suggest)\b",
            re.IGNORECASE,
        ),
        "observed comparative outcome": re.compile(
            r"\b(?:order gap|predictor|proposed method)\b"
            r".{0,120}\b(?:persists?|shows? higher|outperforms?|improves?|exceeds?|"
            r"achieves?|performs? better)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "claimed tested condition": re.compile(
            r"\b(?:conditions?|configurations?|models?|benchmarks?)\s+tested\b",
            re.IGNORECASE,
        ),
        "completed-evidence contribution": re.compile(
            r"\bwe\s+(?:provide|present|report)\s+(?:controlled|empirical|experimental)\s+"
            r"(?:evidence|results?|findings?)\b",
            re.IGNORECASE,
        ),
        "concrete unavailable numerical threshold": re.compile(
            r"(?<![A-Za-z0-9])10\s*\^\s*\{?[-+]\d+\}?",
            re.IGNORECASE,
        ),
    }
    return [label for label, pattern in patterns.items() if pattern.search(text)]


def _is_appendix_section(section: str) -> bool:
    title = str(SECTION_MAP.get(section, {}).get("title", "")).lower()
    return section.lower() in {"ap", "appendix", "appendices"} or "append" in title


def _is_synthesis_section(section: str) -> bool:
    title = str(SECTION_MAP.get(section, {}).get("title", "")).lower()
    return SECTION_MAP.get(section, {}).get("render") == "abstract" or any(
        token in title for token in ("conclusion", "limitation")
    )


def execution_record_context(metrics: dict[str, Any]) -> dict[str, Any]:
    """Load small run-owned config/environment records linked by the result report."""
    result_source = str(metrics.get("result_source") or "").strip()
    if not result_source:
        return {}
    report_path = _project_path(ROOT, result_source, "metrics.result_source")
    report = read_text(report_path, 500000)
    paths = dict.fromkeys(
        re.findall(
            r"(?:^|[\s·>])((?:results|paper)/[A-Za-z0-9_./-]+/(?:config|environment|metrics)\.json)",
            report,
        )
    )
    records: dict[str, Any] = {}
    for relative in paths:
        try:
            path = _project_path(ROOT, relative, "result execution record")
            payload = json.loads(read_text(path, 120000))
        except (OSError, ValueError, json.JSONDecodeError, ProjectConfigError):
            continue
        if path.name == "metrics.json" and isinstance(payload, dict):
            payload = {"metadata": payload.get("metadata", {})}
        records[relative] = payload
    return records


def primary_comparison_outcome(metrics: dict[str, Any]) -> dict[str, Any]:
    """Derive the proposed method's win/loss record from the primary result table."""
    rows = (
        metrics.get("artifacts", {}).get("T1", {}).get("rows", [])
        if isinstance(metrics.get("artifacts"), dict)
        else []
    )
    if not isinstance(rows, list) or len(rows) < 3:
        return {}
    proposed_names = {
        str(item.get("name") or "").casefold()
        for item in experiment_setup_context().get("proposed_methods", [])
    }
    header = rows[0] if isinstance(rows[0], dict) else {}
    data_rows = [row for row in rows[1:] if isinstance(row, dict)]
    proposed = next(
        (
            row
            for row in data_rows
            if str(row.get("method") or row.get("name") or "").casefold()
            in proposed_names
        ),
        None,
    )
    if not proposed:
        return {}
    comparisons: list[dict[str, Any]] = []
    for key, raw_value in proposed.items():
        if key in {"method", "name"}:
            continue
        try:
            proposed_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        candidates: list[tuple[str, float]] = []
        for row in data_rows:
            try:
                candidates.append(
                    (
                        str(row.get("method") or row.get("name") or ""),
                        float(row[key]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                pass
        if not candidates:
            continue
        label = str(header.get(key) or key)
        lower_is_better = "↓" in label or any(
            token in label.casefold() for token in ("rmse", "error", "cost", "latency")
        )
        best_name, best_value = (
            min(candidates, key=lambda item: item[1])
            if lower_is_better
            else max(candidates, key=lambda item: item[1])
        )
        comparisons.append(
            {
                "metric": label,
                "proposed_value": proposed_value,
                "best_method": best_name,
                "best_value": best_value,
                "proposed_is_best": math.isclose(
                    proposed_value, best_value, rel_tol=1e-9, abs_tol=1e-12
                ),
            }
        )
    return {
        "proposed_method": str(proposed.get("method") or proposed.get("name") or ""),
        "comparisons": comparisons,
        "wins": sum(item["proposed_is_best"] for item in comparisons),
        "metric_count": len(comparisons),
    }


def experimental_setup_issues(section: str, purpose: str, text: str) -> list[str]:
    """Enforce the compact dataset/baseline/settings contract for setup prose."""
    if not (
        _is_experiment_section(section)
        and re.search(
            r"\b(?:experimental setup|protocol|vector extraction|calibration|"
            r"dataset|baseline selection)\b",
            purpose,
            re.I,
        )
    ):
        return []
    contract = experiment_setup_context()
    purpose_folded = purpose.casefold()
    requires_datasets = "dataset" in purpose_folded
    requires_baselines = "baseline" in purpose_folded
    if not requires_datasets and not requires_baselines:
        # A single generic setup paragraph owns the whole compact contract;
        # split setup paragraphs own only the category named by their approved
        # purpose, avoiding forced repetition in every paragraph.
        requires_datasets = bool(re.search(r"\bexperimental setup\b", purpose, re.I))
        requires_baselines = requires_datasets
    required_setup_items = [
        *(contract.get("datasets", []) if requires_datasets else []),
        *(contract.get("baselines", []) if requires_baselines else []),
    ]
    missing = [
        str(item.get("name"))
        for item in required_setup_items
        if str(item.get("name") or "").casefold() not in text.casefold()
    ]
    issues = ["missing setup item: " + item for item in missing]
    # A local manuscript can require only citation keys explicitly supplied by
    # the approved contract; a baseline name or URL alone is not a usable
    # BibTeX identity and may describe this study's own control. Hosted writing
    # intentionally uses empty \cite{} slots, so count citation commands there
    # rather than only non-empty keys.
    declared_keys = {
        str(item.get("citation_key") or "").strip()
        for item in required_setup_items
        if str(item.get("citation_key") or "").strip()
    }
    if ONLINE_PROJECT_MODE:
        external_count = sum(
            1
            for item in required_setup_items
            if str(item.get("url") or item.get("citation_key") or "").strip()
        )
        required_citation_count = min(3, external_count)
        observed_citation_count = len(
            re.findall(r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}", text)
        )
        citations_missing = observed_citation_count < required_citation_count
    else:
        citations_missing = not declared_keys.issubset(citation_keys(text))
    if citations_missing:
        issues.append("published datasets and baselines lack introducing citations")
    protocol = metrics_bundle().get("evaluation_protocol", {})
    protocol_models = protocol.get("models", []) if isinstance(protocol, dict) else []
    explicitly_planned_models = [
        str(item)
        for item in protocol_models
        if str(item).casefold() in purpose_folded
    ]
    required_models = explicitly_planned_models
    if not required_models and re.search(r"\bexact executed models?\b", purpose, re.I):
        required_models = [str(item) for item in protocol_models]
    required_seeds = (
        [str(item) for item in protocol.get("seeds", [])]
        if isinstance(protocol, dict) and "seed" in purpose_folded
        else []
    )
    for required in [*required_models, *required_seeds]:
        if str(required).casefold() not in text.casefold():
            issues.append("missing executed setting: " + str(required))
    if len(re.findall(r"\b[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?\b", text)) > 170:
        issues.append("experimental setup exceeds 170 words")
    return issues


def section_evidence(
    section: str, artifact_ids: list[str] | None = None
) -> str:
    """Return executed evidence, narrowed to the current planned paragraph.

    ``None`` retains section-wide context for bibliography selection.  A list
    (including an empty list) comes from a concrete paragraph and prevents an
    unrelated experiment table from leaking into that paragraph's prompt.
    """
    metrics = metrics_bundle()
    selected: dict[str, Any] = {}
    if metrics.get("result_source"):
        selected["result_source"] = metrics["result_source"]
    if metrics.get("evidence_grade"):
        selected["evidence_grade"] = metrics["evidence_grade"]
    if isinstance(metrics.get("fixture"), dict):
        selected["fixture"] = metrics["fixture"]
    lightweight = metrics.get("lightweight_project")
    if isinstance(lightweight, dict) and str(
        lightweight.get("project_evidence") or ""
    ).strip():
        # The uploaded target brief is authoritative for design constants in
        # every section. Keeping it at the top level makes it impossible for a
        # paragraph writer to mistake the structural reference for evidence or
        # silently replace a sampled protocol with a different one.
        selected["target_project_brief"] = lightweight["project_evidence"]
    # Core executed facts are relevant across the paper, not only in Method or
    # Experiments. Supplying them section-wide prevents an Introduction from
    # misdescribing an output-schema intervention, and prevents synthesis prose
    # from recomputing counts and claim decisions from memory.
    for key in (
        "execution_summary",
        "executed_metric_definitions",
        "executed_prompt_conditions",
        "writing_evidence_boundaries",
        "claim_dispositions",
        "qualitative_evidence_scope",
    ):
        value = metrics.get(key)
        if isinstance(value, dict) and value:
            selected[key] = value
        elif isinstance(value, str) and value.strip():
            selected[key] = value
    if _is_method_section(section) and isinstance(metrics.get("model_design"), dict):
        selected["approved_model_design"] = metrics["model_design"]
        selected["metric_contract"] = metrics.get("metric_contract", [])
        selected["executed_metric_definitions"] = metrics.get(
            "executed_metric_definitions", {}
        )
        selected["executed_prompt_conditions"] = metrics.get(
            "executed_prompt_conditions", {}
        )
        selected["symbol_registry"] = metrics.get("symbol_registry", [])
    if _is_discussion_section(section):
        selected["claims"] = metrics.get("claims", [])
        selected["evaluation_protocol"] = metrics.get("evaluation_protocol", {})
        selected["execution_summary"] = metrics.get("execution_summary", {})
        selected["claim_dispositions"] = metrics.get("claim_dispositions", {})
        selected["qualitative_evidence_scope"] = metrics.get(
            "qualitative_evidence_scope", ""
        )
    if _is_experiment_section(section):
        setup = experiment_setup_context()
        if setup:
            selected["experiment_setup_contract"] = setup
        selected["claims"] = metrics.get("claims", [])
        selected["evaluation_protocol"] = metrics.get("evaluation_protocol", {})
        selected["execution_summary"] = metrics.get("execution_summary", {})
        selected["claim_dispositions"] = metrics.get("claim_dispositions", {})
        selected["executed_metric_definitions"] = metrics.get(
            "executed_metric_definitions", {}
        )
        selected["executed_prompt_conditions"] = metrics.get(
            "executed_prompt_conditions", {}
        )
        selected["qualitative_cases"] = metrics.get("qualitative_cases", {})
        selected["qualitative_evidence_scope"] = metrics.get(
            "qualitative_evidence_scope", ""
        )
        records = execution_record_context(metrics)
        if records:
            selected["execution_records"] = records
    if _is_appendix_section(section):
        # Appendix paragraphs must materialize the promised proof, configuration,
        # grids, evaluator definitions, and provenance.  Supplying only result keys
        # bound to the appendix (usually none) made models write a roadmap instead.
        setup = experiment_setup_context()
        if setup:
            selected["experiment_setup_contract"] = setup
        selected["claims"] = metrics.get("claims", [])
        selected["evaluation_protocol"] = metrics.get("evaluation_protocol", {})
        selected["complete_executed_artifacts"] = metrics.get("artifacts", {})
        records = execution_record_context(metrics)
        if records:
            selected["execution_records"] = records
    if _is_synthesis_section(section):
        selected["claims"] = metrics.get("claims", [])
        selected["evaluation_protocol"] = metrics.get("evaluation_protocol", {})
        selected["execution_summary"] = metrics.get("execution_summary", {})
        selected["claim_dispositions"] = metrics.get("claim_dispositions", {})
        outcome = primary_comparison_outcome(metrics)
        if outcome:
            selected["primary_comparison_outcome"] = outcome

    is_abstract = SECTION_MAP.get(section, {}).get("render") == "abstract"
    if artifact_ids is None:
        for key in RESULT_KEYS.get(section, []):
            if has_result_path(metrics, key):
                selected[key] = result_path_value(metrics, key)
        relevant_artifacts = [
            artifact_id
            for artifact_id, definition in {**FIGURES, **TABLES}.items()
            if section in definition.get("source_sections", [])
        ]
    else:
        relevant_artifacts = [
            artifact_id
            for artifact_id in artifact_ids
            if artifact_id in FIGURES or artifact_id in TABLES
        ]
    # The abstract is written last and gets the compact result tables.  It no
    # longer starts with an empty evidence block and [X] placeholders.
    if is_abstract or _is_synthesis_section(section):
        relevant_artifacts = list(TABLES)
    for artifact_id in relevant_artifacts:
        if artifact_id in FIGURES:
            keys = FIGURES[artifact_id].get("result_keys", [])
        else:
            grid = TABLES[artifact_id].get("data_grid", {})
            keys = [grid.get("path")] if isinstance(grid, dict) else []
        for key in keys:
            if key and has_result_path(metrics, str(key)):
                selected[str(key)] = result_path_value(metrics, str(key))
    return json.dumps(selected, ensure_ascii=False, indent=2)[:26000]


def experiment_setup_context() -> dict[str, Any]:
    """Return the compact setup contract embedded by expplan.

    Paper writing needs the selected methods and implementation boundary, not
    the entire (large) planning contract.  Keeping this extraction here also
    makes the setup available without changing the expplan skill or report.
    """
    if not EXPERIMENT_PLAN_FILE.exists():
        return {}
    source = read_text(EXPERIMENT_PLAN_FILE, 4_000_000)
    match = re.search(
        r'<script[^>]*\bid=["\']experiment-plan-contract["\'][^>]*>'
        r"(.*?)</script>",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    try:
        contract = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    if not isinstance(contract, dict):
        return {}
    dataset_rows = contract.get("dataset_citations", [])
    baseline_rows = contract.get("baseline_contract", {}).get("selected", [])
    implementation_rows = contract.get("implementation_contract", [])
    metric_rows = contract.get("metric_contract", [])
    datasets = [
        {
            "name": str(row.get("name", "")).strip(),
            "url": str(row.get("url", "")).strip(),
            "citation_key": str(
                row.get("citation_key") or row.get("bibtex_key") or ""
            ).strip(),
        }
        for row in dataset_rows
        if isinstance(row, dict) and str(row.get("name", "")).strip()
    ]
    implementations = {
        str(row.get("method", "")).strip(): str(
            row.get("implementation_summary", "")
        ).strip()
        for row in implementation_rows
        if isinstance(row, dict) and str(row.get("method", "")).strip()
    }
    baselines = []
    for row in baseline_rows:
        if not isinstance(row, dict) or not str(row.get("name", "")).strip():
            continue
        name = str(row["name"]).strip()
        baselines.append(
            {
                "name": name,
                "role": str(row.get("scientific_role", "")).strip(),
                "implementation": implementations.get(name, ""),
                "url": str(row.get("url", "")).strip(),
                "citation_key": str(
                    row.get("citation_key") or row.get("bibtex_key") or ""
                ).strip(),
            }
        )
    our_methods = [
        {"name": name, "implementation": summary}
        for name, summary in implementations.items()
        if name not in {item["name"] for item in baselines}
    ]
    metrics = [
        str(row.get("name", "")).strip()
        for row in metric_rows
        if isinstance(row, dict) and str(row.get("name", "")).strip()
    ]
    return {
        "datasets": datasets,
        "baseline_count": len(baselines),
        "baselines": baselines,
        "proposed_methods": our_methods,
        "metrics": metrics,
    }


def current_paragraph(section_state: dict[str, Any]) -> dict[str, Any] | None:
    index = int(section_state.get("current_index", 0))
    paragraphs = section_state.get("paragraphs", [])
    if not (0 <= index < len(paragraphs)):
        return None
    return paragraphs[index]


def normalize_latex_ready_text(source: str) -> str:
    """Collapse JSON-style double escaping before known manuscript commands only."""
    # Models occasionally wrap an otherwise valid paragraph in a fenced Markdown
    # block. Backticks are printable in LaTeX, so compilation succeeds while the PDF
    # visibly starts with ``latex`` and ends with quote-like marks. Strip only
    # standalone fence lines; inline code remains a validation error below.
    source = re.sub(r"(?im)^\s*```(?:latex|tex)?\s*$", "", source).strip()
    # Provider prose can reintroduce typographic dashes during any of several
    # repair passes. Canonicalize them at the single ingestion boundary rather
    # than relying on every prompt to obey a punctuation preference.
    source = source.replace("—", "; ").replace("–", "-")
    # ACL's scaffold uses natbib, while providers occasionally emit biblatex
    # citation commands. Normalize equivalent commands before validation and
    # compilation so retry prompts do not preserve an incompatible macro.
    source = re.sub(r"\\textcite\b", r"\\citet", source)
    source = re.sub(r"\\parencite\b", r"\\citep", source)
    commands = (
        r"cite\w*|ref|pageref|label|textbf|textit|emph|subsection|subsubsection|"
        r"section|paragraph|footnote|url|href|path"
    )
    normalized = re.sub(rf"\\\\(?=(?:{commands})\b)", lambda _match: "\\", source)
    # ``[SYNTHETIC]`` is a literal provenance marker, never a mathematical
    # display.  Models occasionally escape its brackets after seeing the
    # pdflatex-safety rule, which otherwise renders it as display math.
    normalized = re.sub(
        r"\\\[\s*SYNTHETIC\s*\\\]",
        "[SYNTHETIC]",
        normalized,
        flags=re.IGNORECASE,
    )
    # Keep the marker visually separate from the value or word it qualifies.
    # DeepSeek often emits ``0.73[SYNTHETIC]`` even when the literal marker is
    # correct, which is valid TeX but poor manuscript typography.
    normalized = re.sub(r"(?<!\s)\[SYNTHETIC\]", " [SYNTHETIC]", normalized)
    normalized = re.sub(r"\[SYNTHETIC\](?=[A-Za-z0-9])", "[SYNTHETIC] ", normalized)
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
    # Monospace text boxes do not line-break long repository paths and can
    # overflow an ACL column. xurl/url is already part of the scaffold, so use
    # its path command while preserving ordinary short code identifiers.
    normalized = re.sub(
        r"\\texttt\{((?=[^{}]*/)[^{}]+)\}",
        lambda match: r"\path{" + match.group(1).replace(r"\_", "_") + "}",
        normalized,
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
        r"\\(?:cite\w*|ref|pageref|label|path)\{[^{}]*\})"
    )
    pieces = protected.split(normalized)
    for index in range(0, len(pieces), 2):
        pieces[index] = re.sub(r"(?<!\\)([_%&#])", r"\\\1", pieces[index])
    normalized = "".join(pieces)
    # Models occasionally decorate the reserved placeholder with notes or even
    # provisional cite commands. Canonicalize the whole bracket so the verified
    # citation resolver handles it instead of leaking workflow syntax into prose.
    normalized = re.sub(
        r"\[CITATION\s+NEEDED[^\]]*\]",
        "[CITATION NEEDED]",
        normalized,
        flags=re.IGNORECASE,
    )
    seen_citations: set[str] = set()

    def keep_first_citation(match: re.Match[str]) -> str:
        raw_keys = [item.strip() for item in match.group(1).split(",") if item.strip()]
        if not raw_keys:
            return match.group(0)
        fresh = []
        for key in raw_keys:
            if key and key not in seen_citations:
                seen_citations.add(key)
                fresh.append(key)
        return rf"\cite{{{','.join(fresh)}}}" if fresh else ""

    normalized = re.sub(
        r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}",
        keep_first_citation,
        normalized,
    )
    return re.sub(r"[ \t]+([,.;:!?])", r"\1", normalized)


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
    (0x2070, 0x209F),  # Superscripts and Subscripts (10⁻⁷, x₂, ...)
    (0x2100, 0x214F),  # Letterlike Symbols (blackboard bold: ℝ ℤ ℕ ℚ ℂ ...)
    (0x2190, 0x21FF),  # Arrows
    (0x27C0, 0x27EF),  # Miscellaneous Mathematical Symbols-A
    (0x2980, 0x29FF),  # Miscellaneous Mathematical Symbols-B
    (0x2A00, 0x2AFF),  # Supplemental Mathematical Operators
)

# Commands in this set are valid only in TeX math mode. Keep this syntactic
# allow-list separate from the prose-content checks: its sole purpose is to
# prevent a generated paragraph such as ``100 \times 5`` from reaching
# pdflatex and aborting a long batch-writing job.
LATEX_MATH_ONLY_COMMANDS = frozenset(
    {
        "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda",
        "mu", "pi", "rho", "sigma", "tau", "phi", "chi", "psi", "omega",
        "Gamma", "Delta", "Theta", "Lambda", "Pi", "Sigma", "Phi", "Psi", "Omega",
        "times", "cdot", "pm", "mp", "div", "le", "leq", "ge", "geq",
        "neq", "approx", "sim", "in", "notin", "subset", "subseteq",
        "supset", "supseteq", "cup", "cap", "sum", "prod", "frac", "sqrt",
        "mathbb", "mathcal", "mathbf", "mathrm", "operatorname",
    }
)


def latex_command_names(source: str) -> list[str]:
    """Tokenize control-word names without interpreting manuscript meaning."""
    names: list[str] = []
    index = 0
    while index < len(source):
        if source[index] != "\\":
            index += 1
            continue
        index += 1
        if index >= len(source) or not source[index].isalpha():
            index += 1
            continue
        start = index
        while index < len(source) and source[index].isalpha():
            index += 1
        names.append(source[start:index])
    return names


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
    issues: list[str] = []
    display_bodies = re.findall(r"(?s)\\\[(.*?)\\\]", source)
    display_bodies += re.findall(
        r"(?s)\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}", source
    )
    for body in display_bodies:
        compact = re.sub(r"\s+", " ", body).strip()
        multiline = re.search(
            r"\\begin\{(?:aligned|split|multlined|gathered)\}|\\\\", body
        )
        if len(compact) > 82 and not multiline:
            issues.append(
                "displayed equation is too long for one ACL column; split it with aligned"
            )
            continue
        # A display can contain a line break while one individual row remains wider
        # than a column (notably a long first row in cases/aligned).  Check logical
        # rows independently instead of treating the mere presence of `\\` as proof
        # that the equation is safe.
        logical_rows = re.split(r"\\\\(?:\[[^\]]*\])?", body)
        for row in logical_rows:
            row = re.sub(r"\\begin\{(?:aligned|split|multlined|gathered|cases)\}", "", row)
            row = re.sub(r"\\end\{(?:aligned|split|multlined|gathered|cases)\}", "", row)
            row = re.sub(r"\s+", " ", row).strip()
            if len(row) > 82:
                issues.append(
                    "displayed equation contains a row too long for one ACL column; "
                    "split the long row itself with aligned"
                )
                break

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

    if "—" in masked:
        issues.append("em dash punctuation is forbidden")
    if "–" in masked:
        issues.append("en dash punctuation is forbidden")
    if re.search(r"-{2,}", masked):
        issues.append("LaTeX double/triple-hyphen dash punctuation is forbidden")

    # Balance-check math delimiters on the raw (unmasked) source: the masking
    # above only strips *correctly paired* math, so a stray or mismatched
    # delimiter -- e.g. GPT opening "$" or "\(" without ever closing it --
    # survives masking untouched and previously reached pdflatex undetected,
    # crashing the whole document with "Missing $ inserted." on a real batch
    # run (the error surfaced far from the actual cause, in whatever file
    # happened to compile next).
    if len(re.findall(r"(?<!\\)\$", source)) % 2 != 0:
        issues.append("unbalanced $ math delimiters (odd count)")
    if source.count("\\(") != source.count("\\)"):
        issues.append("unbalanced \\( \\) math delimiters")
    if source.count("\\[") != source.count("\\]"):
        issues.append("unbalanced \\[ \\] math delimiters")

    unicode_math = sorted(
        {character for character in set(masked) if _is_latex_unsafe_unicode_math(character)}
    )
    if unicode_math:
        issues.append("Unicode math glyphs: " + " ".join(unicode_math))
    math_commands = sorted(
        set(latex_command_names(masked)).intersection(LATEX_MATH_ONLY_COMMANDS)
    )
    if math_commands:
        issues.append(
            "math command outside math delimiters: "
            + " ".join("\\" + command for command in math_commands)
        )
    specials = {
        "_": "raw underscore",
        "%": "raw percent sign",
        "&": "raw ampersand",
        "#": "raw hash sign",
        "^": "raw caret (superscript outside math)",
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
            raise StudioError("The candidate has been updated; please review the automatically loaded latest version on the page and Accept again.")
        text = submitted or latest
        if not text:
            raise StudioError("Candidate body text cannot be empty.")
        candidate["text"] = text
        return candidate, text

    accepted = str(paragraph.get("accepted_text", "")).strip()
    if not accepted:
        if not submitted:
            raise StudioError("The current paragraph has no acceptable body text.")
        candidate = {
            "id": uuid.uuid4().hex,
            "text": submitted,
            "purpose": paragraph.get("purpose", ""),
            "citations_added": [],
            "created_at": int(time.time()),
            "source": "manual_draft",
        }
        paragraph["candidate"] = candidate
        return candidate, submitted
    if base_text.strip() != accepted:
        raise StudioError("The accepted version has been updated elsewhere; the page will load the latest version, please review and modify again.")
    if not submitted or submitted == accepted:
        raise StudioError("There are no edits left unwritten in the main text.")
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


def ensure_survey_bibliography() -> list[str]:
    """Recover an empty citation bank from the project's verified survey."""
    if bibliography_keys() or not LITERATURE_SURVEY_FILE.is_file():
        return []
    source = read_text(LITERATURE_SURVEY_FILE, 4_000_000)
    bibliography = verified_survey_bibliography(source)
    if not bibliography.strip():
        return []
    path = PAPER / "references.bib"
    temporary = path.with_suffix(".bib.tmp")
    temporary.write_text(bibliography, encoding="utf-8")
    os.replace(temporary, path)
    return sorted(bibliography_keys())


def _bibtex_entries(source: str) -> list[tuple[str, str]]:
    starts = list(re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", source))
    return [
        (
            match.group(1).strip(),
            source[
                match.start() : starts[index + 1].start()
                if index + 1 < len(starts)
                else len(source)
            ].strip(),
        )
        for index, match in enumerate(starts)
    ]


def survey_bibliography_keys() -> set[str]:
    """Return bibliography keys whose records are present in the verified survey.

    The local editor may only cite sources already selected and verified by the
    literature-survey stage.  Matching uses stable identifiers first and the
    normalized title as a fallback, so the survey HTML does not need to embed a
    second machine-specific BibTeX copy.
    """
    survey_html = read_text(LITERATURE_SURVEY_FILE, 4_000_000)
    if not survey_html:
        return set()
    survey_text = html.unescape(survey_html).lower()
    survey_plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", survey_text))
    allowed: set[str] = set()
    for key, entry in _bibtex_entries(bibliography_catalog()):
        authors = _bibtex_field(entry, "author")
        # An abbreviated survey label is sufficient for discovery but not for a
        # camera-ready bibliography.  Do not let paragraph generation cite it
        # until the survey carries complete machine-readable author metadata.
        if not authors or re.search(r"\band\s+others\b|\bet\s+al\.?\b", authors, re.I):
            continue
        identifiers = [
            _bibtex_field(entry, field).strip().lower().rstrip("/")
            for field in ("doi", "eprint", "url")
        ]
        identifiers = [value for value in identifiers if value]
        title = _bibtex_field(entry, "title")
        normalized_title = re.sub(
            r"\s+",
            " ",
            re.sub(r"[{}\\]", "", html.unescape(title).lower()),
        ).strip()
        if any(value in survey_text for value in identifiers) or (
            normalized_title and normalized_title in survey_plain
        ):
            allowed.add(key)
    return allowed


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
    relevant_text: str = "",
    *,
    required_keys: set[str] | None = None,
    allowed_keys: set[str] | None = None,
) -> str:
    """Return a bounded, relevance-ranked citation catalog for one writing turn.

    A paper may have hundreds of BibTeX records.  Sending all of them at every
    section bootstrap wastes input tokens and usually makes citation selection
    worse.  Keep records already cited by the supplied text, rank the remainder
    by lexical overlap, and retain a small fallback set for sparse plans.
    """
    source = bibliography_catalog()
    entries: list[tuple[str, str, str, int]] = []
    fields = (
        "author", "title", "year", "booktitle", "journal", "doi", "eprint",
        "url", "claimsummary",
    )
    for index, (key, entry) in enumerate(_bibtex_entries(source)):
        if allowed_keys is not None and key not in allowed_keys:
            continue
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


def bounded_prompt_text(value: object, limit: int, label: str) -> str:
    """Bound one prompt component while retaining both its framing and tail."""
    text = str(value or "")
    if len(text) <= limit:
        return text
    marker = f"\n[... {label} truncated to control API input cost ...]\n"
    remaining = max(0, limit - len(marker))
    head = remaining * 2 // 3
    return text[:head] + marker + text[-(remaining - head):]


def writing_bibliography_catalog(relevant_text: str = "") -> str:
    """Expose only project-verified citations to the paragraph writer.

    Local projects retain the stricter literature-survey allow-list.  Online
    projects have no survey stage, so their ``references.bib`` is itself the
    verified citation bank assembled from uploaded/externally checked
    metadata.  Hiding that bank used to guarantee citation-free online
    manuscripts even when valid sources were present.
    """
    if ONLINE_PROJECT_MODE:
        return bibliography_prompt_catalog(relevant_text)
    return bibliography_prompt_catalog(
        relevant_text,
        allowed_keys=survey_bibliography_keys(),
    )


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


def citation_key_counts(source: str) -> dict[str, int]:
    """Count citation-command uses per key, rather than mere bibliography presence."""
    counts: dict[str, int] = {}
    for match in re.finditer(r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}", source):
        for key in (item.strip() for item in match.group(1).split(",")):
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


def prior_section_citation_counts(section: str, exclude_text: str = "") -> dict[str, int]:
    """Return citations already used elsewhere in the current section."""
    path = PAPER / "sections" / SECTION_MAP[section]["file"]
    source = read_text(path, 500_000)
    if exclude_text.strip():
        source = source.replace(exclude_text.strip(), "", 1)
    return citation_key_counts(source)


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


def has_uncited_named_attribution(text: str) -> bool:
    """Detect an explicit author/year attribution lacking a citation command.

    This is deliberately narrow: it catches prose such as ``Zhu et al. (2020)``
    without forcing citation calls for ordinary method/results paragraphs.
    """
    attribution = re.compile(
        r"\b[A-Z][A-Za-z'’-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’-]+|\s+et\s+al\.)"
        r"\s*(?:\((?:19|20)\d{2}[a-z]?\)|,?\s+(?:19|20)\d{2}[a-z]?)"
    )
    for match in attribution.finditer(text):
        left = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start()))
        right_candidates = [
            position
            for position in (text.find(".", match.end()), text.find("\n", match.end()))
            if position >= 0
        ]
        right = min(right_candidates) if right_candidates else len(text)
        if not citation_keys(text[left + 1 : right + 1]):
            return True
    return False


def paragraph_requires_citation_audit(
    section: str,
    purpose: str,
    text: str,
) -> bool:
    """Select paragraphs that need a cheap, survey-only citation audit.

    Generation models sometimes omit both a citation and the explicit
    ``[CITATION NEEDED]`` marker.  Looking only for malformed citations therefore
    misses exactly the failure the audit is meant to catch.  Introduction and
    related-work prose always receive the audit; other sections receive it only
    when they name an external dataset, benchmark, baseline, prior study, or
    attribution.  The audit itself may correctly return zero citations.
    """
    if SECTION_MAP.get(section, {}).get("render") == "abstract":
        return False
    section_title = str(SECTION_MAP.get(section, {}).get("title", "")).lower()
    if (
        section in {"introduction", "related_work"}
        or "introduction" in section_title
        or "related work" in section_title
    ):
        return True
    corpus = f"{purpose}\n{text}"
    external_obligation = re.compile(
        r"\b(?:dataset|benchmark|corpus|testbed|baseline|prior work|previous work|"
        r"previous studies|existing methods?|introduced by|proposed by|according to|"
        r"activation steering|steering vectors?|inference-time interventions?|"
        r"CLINC150|ATIS|SNIPS|BERT|RoBERTa|GPT-[2345]|Llama(?:\s*[- ]?\d+)?)\b",
        re.IGNORECASE,
    )
    return bool(external_obligation.search(corpus) or has_uncited_named_attribution(text))


def real_result_status_issues(text: str) -> list[str]:
    """Flag future-tense result language when the configured fixture is measured."""
    metrics = metrics_bundle()
    fixture = metrics.get("fixture", {}) if isinstance(metrics, dict) else {}
    if not isinstance(fixture, dict) or fixture.get("synthetic") is not False:
        return []
    patterns = {
        "pending execution": r"\bpending (?:confirmatory )?execution\b",
        "pre-registration described as current status": r"\bpre-?registered\b",
        "future table population": r"\bwill be populated\b",
        "future run completion": r"\bafter (?:the )?(?:run|experiment) completes\b",
        "future claim test": r"\bwe will test\b",
        "future first-person action": r"\bwe will\b",
        "future computation": r"\bwe will (?:compute|report|evaluate|compare|use|construct|average)\b",
        "future execution action": r"\b(?:evaluation|records?|split contract|protocol|analysis|study) will\b",
        "future comparison": r"\ball reported comparisons will\b",
        "future interval": r"\b(?:intervals?|means?|values?) will (?:be )?(?:constructed|computed|averaged|determined)\b",
        "future split freeze": r"\bsplit contract will be fixed\b|\bbefore any seed is executed\b",
        "confirmatory status applied to pilot": r"(?<!not )\bconfirmatory (?:design|protocol|test|means?|values?|seeds?|study)\b",
        "future full run": r"\bfull runs?\b",
    }
    return [label for label, pattern in patterns.items() if re.search(pattern, text, re.I)]


def execution_record_contradiction_issues(text: str) -> list[str]:
    """Flag prose that contradicts persisted run completion/provenance fields."""
    metrics = metrics_bundle()
    records = execution_record_context(metrics)
    config = next(
        (value for key, value in records.items() if key.endswith("/config.json")), {}
    )
    metadata = next(
        (
            value.get("metadata", {})
            for key, value in records.items()
            if key.endswith("/metrics.json") and isinstance(value, dict)
        ),
        {},
    )
    environment = next(
        (value for key, value in records.items() if key.endswith("/environment.json")),
        {},
    )
    issues: list[str] = []
    if re.search(r"\bnonzero\b[^.\n]{0,45}\b0(?:\.0+)?\b", text, re.I):
        issues.append("describes an exact zero value as nonzero")
    if metrics.get("scientific_integrity_version") == 2:
        reference_alias = r"(?:reference|conformance|RevocationCascade)"
        reference_superiority = re.search(
            rf"\b{reference_alias}[^.\n]{{0,100}}\b"
            r"(?:outperform(?:s|ed)?|perform(?:s|ed)? best|improv(?:e|es|ed)|"
            r"beat(?:s)?|exceed(?:s|ed)|favor(?:s|ed|ing)?)\b",
            text,
            re.I,
        )
        if reference_superiority:
            issues.append("frames oracle-conformance agreement as method superiority")
        if re.search(
            r"\b(?:under-propagation|over-propagation)[^.\n]{0,100}\b"
            r"(?:identical (?:harm|consequence)|more costly|costlier)\b",
            text,
            re.I,
        ):
            issues.append("asserts an unmeasured equality or cost ordering between failure modes")
        if re.search(
            r"\b(?:ablation|removing|removal)[^.\n]{0,100}\b"
            r"(?:confirm(?:s|ed|ing)?|prove(?:s|d)?|necessary|required|critical|"
            r"isolat(?:e|es|ed|ing)(?: the)? contribution)\b",
            text,
            re.I,
        ):
            issues.append("upgrades a registered mutant response into causal component necessity")
    try:
        completed_before_stop = float(metadata["elapsed_seconds"]) < 60.0 * float(
            config["hard_stop_minutes"]
        )
    except (KeyError, TypeError, ValueError):
        completed_before_stop = False
    if completed_before_stop and re.search(
        r"hard stop (?:fired|was reached|triggered)|cells? (?:were )?(?:not populated|missing)|"
        r"did not complete before the hard stop",
        text,
        re.I,
    ):
        issues.append("claims missing cells even though the run completed before its hard stop")
    for field in ("python", "platform", "machine"):
        if environment.get(field) and re.search(
            rf"no [^.\n]{{0,40}}\b{field}\b[^.\n]{{0,30}}(?:recorded|available)|"
            rf"\b{field}\b field was not recorded",
            text,
            re.I,
        ):
            issues.append(f"claims recorded {field} provenance is absent")
    serialized_records = json.dumps(records, ensure_ascii=False).casefold()
    if "license" not in serialized_records and re.search(
        r"\blicense(?:s| identifiers?| text)? (?:is|are|was|were) "
        r"(?:documented|recorded|released|provided)",
        text,
        re.I,
    ):
        issues.append("claims license provenance that was not recorded")
    if not re.search(r"\b(?:commit|revision|git)\b", serialized_records) and re.search(
        r"\b(?:repository|code) (?:state|revision|commit) (?:is|was|has been) "
        r"(?:documented|recorded|pinned)",
        text,
        re.I,
    ):
        issues.append("claims repository revision provenance that was not recorded")
    return issues


def appendix_content_issues(section: str, text: str) -> list[str]:
    """Reject appendix roadmaps that describe content instead of supplying it."""
    if not _is_appendix_section(section):
        return []
    prose = re.sub(r"^\\subsection\*?\{[^{}]*\}\s*", "", text.strip())
    issues: list[str] = []
    if re.search(r"\bwe will\b|\bwill (?:give|list|report|document|provide|show)\b", prose, re.I):
        issues.append("future appendix roadmap")
    if re.match(
        r"Appendix\s+[A-Z]\s+(?:supplies|provides|reports|documents|lists|gives|describes)\b",
        prose,
        re.I,
    ):
        issues.append("appendix self-description instead of content")
    word_count = len(re.findall(r"\b[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?\b", prose))
    if word_count > 380:
        issues.append(f"appendix paragraph exceeds 380 words: {word_count}")
    if re.search(
        r"\bremainder\b[^.]{0,100}\b(?:stays?|remains?|is)\b[^.]{0,40}"
        r"\b(?:below|within)\b[^.]{0,40}\b(?:tolerance|threshold)\b",
        prose,
        re.I,
    ):
        issues.append("unsupported empirical bound on the formal remainder")
    evidence_text = section_evidence(section, [])
    if "proxy_definition" not in evidence_text.casefold() and re.search(
        r"\b(?:normalized match count|keyword and phrase patterns|mean log-probability)\b",
        prose,
        re.I,
    ):
        issues.append("proxy implementation detail absent from execution evidence")
    return issues


def manuscript_markup_issues(text: str) -> list[str]:
    """Reject Markdown residue in a LaTeX-only manuscript response."""
    issues: list[str] = []
    if re.search(r"(?m)^\s*(?:#{1,6}|(?:\\#){1,6})\s+", text):
        issues.append("Markdown heading")
    if re.search(r"\*\*[^*\n]+\*\*|__[^_\n]+__", text):
        issues.append("Markdown bold markup")
    if re.search(r"(?<!`)`[^`\n]+`(?!`)", text):
        issues.append("Markdown inline-code markup")
    if re.search(r"(?m)^\s*```(?:latex|tex)?\s*$", text):
        issues.append("Markdown fenced-code markup")
    if re.search(r"\\section\*?\{", text):
        issues.append("model-emitted top-level section heading")
    if re.search(
        r"(?im)^\s*(?:here is|the following is) (?:the )?(?:paragraph|draft)|"
        r"\b[A-Z]+-P\d+ (?:and [A-Z]+-P\d+ )?(?:form|is) the\b",
        text,
    ):
        issues.append("model commentary around manuscript prose")
    return issues


def _latex_numeric_values(text: str) -> list[float]:
    """Extract ordinary and ``a\\times10^{b}`` values for local comparison gates."""
    positioned: list[tuple[int, float]] = []
    consumed: list[tuple[int, int]] = []
    scientific = re.compile(
        r"(?<![A-Za-z0-9])([+-]?\d+(?:\.\d+)?)\s*\\times\s*10\s*\^\s*\{?([+-]?\d+)\}?"
    )
    for match in scientific.finditer(text):
        positioned.append(
            (match.start(), float(match.group(1)) * (10.0 ** int(match.group(2))))
        )
        consumed.append(match.span())
    power_of_ten = re.compile(r"(?<![A-Za-z0-9])10\s*\^\s*\{?([+-]?\d+)\}?")
    for match in power_of_ten.finditer(text):
        if any(start <= match.start() < end for start, end in consumed):
            continue
        positioned.append((match.start(), 10.0 ** int(match.group(1))))
        consumed.append(match.span())
    # ACL tables commonly omit the leading zero (``.63``).  Matching only
    # digit-first values started at the ``6`` and silently converted .63 to
    # 63, which then triggered false inverted-comparison failures.
    ordinary = re.compile(
        r"(?<![A-Za-z0-9.])([+-]?(?:\d+(?:\.\d+)?|\.\d+))(?![A-Za-z0-9]|\.\d)"
    )
    for match in ordinary.finditer(text):
        if any(start <= match.start() < end for start, end in consumed):
            continue
        positioned.append((match.start(), float(match.group(1))))
    return [value for _position, value in sorted(positioned)]


def unsupported_appendix_numeric_issues(
    section: str, text: str, evidence: str
) -> list[str]:
    """Catch appendix measurements/configuration numbers absent from run evidence."""
    if not _is_appendix_section(section):
        return []
    supplied = _latex_numeric_values(evidence)
    supplied.extend(
        float(match.group(0))
        for match in re.finditer(
            r"(?<![A-Za-z0-9_.])[+-]?\d+(?:\.\d+)?[eE][+-]?\d+(?![A-Za-z0-9_.])",
            evidence,
        )
    )
    allowed_constants = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 100.0}
    unsupported: list[str] = []
    for value in _latex_numeric_values(text):
        if value in allowed_constants:
            continue
        if any(
            math.isclose(value, item, rel_tol=0.012, abs_tol=1e-12)
            or math.isclose(value / 100.0, item, rel_tol=0.012, abs_tol=1e-12)
            for item in supplied
        ):
            continue
        rendered = f"{value:g}"
        if rendered not in unsupported:
            unsupported.append(rendered)
    return [f"number absent from appendix evidence: {item}" for item in unsupported]


def bound_artifact_row_value_issues(text: str, evidence: str) -> list[str]:
    """Detect decimal values borrowed from a different named result row.

    LLM table audits can still copy a valid cell from the wrong behavior.  A
    global numeric-membership check cannot notice because the value exists
    elsewhere in the same table.  When a sentence explicitly names one or more
    row labels, restrict its decimal measurements to those rows.  Direct
    pairwise differences are allowed for ordinary effect-size prose.
    """
    try:
        payload = json.loads(evidence)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    issues: list[str] = []
    decimal_pattern = re.compile(
        r"(?<![A-Za-z0-9])([+-]?(?:\d+\.\d+|\.\d+))(?![A-Za-z0-9])"
    )
    for artifact_key, raw_rows in payload.items():
        if not str(artifact_key).startswith("artifacts.") or not isinstance(raw_rows, list):
            continue
        rows = [row for row in raw_rows if isinstance(row, dict) and row]
        if not rows:
            continue
        # Result-table records keep their visible identifier in the first
        # nonnumeric column (normally behavior, category, method, or variant).
        identifier_key = next(
            (
                key
                for key in rows[0]
                if all(
                    str(row.get(key, "")).strip()
                    and numeric_cell(str(row.get(key, ""))) is None
                    for row in rows
                )
            ),
            "",
        )
        if not identifier_key:
            continue
        labeled_rows: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            label = str(row.get(identifier_key, "")).strip()
            if label:
                # Several result tables legitimately repeat a dataset label
                # across multiple metrics. Preserve every matching row instead
                # of silently retaining only the last one.
                labeled_rows.setdefault(label, []).append(row)
        for sentence in re.split(r"(?<=[.!?;])\s+", text):
            matched = [
                (label, matching_rows)
                for label, matching_rows in labeled_rows.items()
                if label.casefold() in sentence.casefold()
            ]
            sentence_words = set(re.findall(r"[A-Za-z][A-Za-z0-9-]+", sentence.casefold()))
            for label, matching_rows in labeled_rows.items():
                distinctive = {
                    token
                    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]+", label.casefold())
                    if len(token) >= 6
                }
                if distinctive & sentence_words and not any(
                    existing_label == label for existing_label, _rows in matched
                ):
                    matched.append((label, matching_rows))
            if re.search(r"\b(?:full|complete)\s+(?:model|configuration|method)\b", sentence, re.I):
                for label, matching_rows in labeled_rows.items():
                    if re.search(r"\b(?:more|ours|full)\b", label, re.I) and not any(
                        existing_label == label for existing_label, _rows in matched
                    ):
                        matched.append((label, matching_rows))
            if not matched:
                continue
            row_values = [
                value
                for _label, matching_rows in matched
                for row in matching_rows
                for key, raw in row.items()
                if key != identifier_key
                for value in _latex_numeric_values(str(raw))
            ]
            allowed = list(row_values)
            allowed.extend(
                left - right
                for index, left in enumerate(row_values)
                for right in row_values[index + 1 :]
            )
            allowed.extend(
                right - left
                for index, left in enumerate(row_values)
                for right in row_values[index + 1 :]
            )
            for token in decimal_pattern.findall(sentence):
                value = float(token)
                if any(math.isclose(value, item, rel_tol=1e-9, abs_tol=5e-4) for item in allowed):
                    continue
                labels = ", ".join(label for label, _rows in matched)
                issue = (
                    f"{artifact_key} sentence naming [{labels}] uses {token}, "
                    "which is absent from those rows and their direct differences"
                )
                if issue not in issues:
                    issues.append(issue)
    return issues


def manuscript_machine_field_issues(section: str, text: str, evidence: str) -> list[str]:
    """Keep serialized result-schema keys out of reader-facing synthesis prose.

    Result keys are useful provenance inside the prompt, but Discussion is not a
    JSON ledger. Compare exact parsed object keys with prose tokens so this gate
    remains structural and project-independent rather than guessing scientific
    meaning from topic-specific phrases.
    """
    if not _is_discussion_section(section):
        return []
    try:
        payload = json.loads(evidence)
    except (TypeError, json.JSONDecodeError):
        return []

    keys: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                candidate = str(key).strip().casefold()
                if "_" in candidate:
                    keys.add(candidate)
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(payload)
    normalized = text.replace(r"\_", "_").casefold()
    tokens = set(
        "".join(character if character.isalnum() or character == "_" else " " for character in normalized).split()
    )
    return [
        f"raw result-schema field in manuscript prose: {key}"
        for key in sorted(keys & tokens)
    ]


def numerical_placeholder_issues(text: str) -> list[str]:
    """Return bracketed planning placeholders that cannot enter a finished abstract."""
    return list(dict.fromkeys(
        match.group(0)
        for match in re.finditer(
            r"\[\s*(?:[Xx](?:\\?%|[^\]]*)?|N|NUMBER|VALUE)\s*\]",
            text,
            flags=re.IGNORECASE,
        )
    ))


def manuscript_completion_placeholder_issues(text: str) -> list[str]:
    """Return planning/provenance tokens that cannot appear in a finished paper."""
    pattern = re.compile(
        r"\[(?:\s*placeholder\b[^\]]*|\s*missing\b[^\]]*|\s*pending\s*|"
        r"\s*revision\s*|\s*[A-Z0-9_-]*license\s*)\]|\bTBD\b|\bTO BE DETERMINED\b",
        flags=re.IGNORECASE,
    )
    return list(dict.fromkeys(match.group(0) for match in pattern.finditer(text)))


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
        raise StudioError(f"Unsupported LLM API:{provider}")
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
    commands = [f'export {env_name}="Paste your API key."']
    result = {
        "provider": provider,
        "provider_label": config["label"],
        "required": True,
        "configured": configured,
        "location": API_KEY_SETUP_LOCATION,
        "environment_variable": env_name,
        "setup_command": "\n".join(commands),
        "restart_command": API_KEY_RESTART_COMMAND,
        "security_note": "Do not input real API keys into the chat, commit to a repository, or save in the browser.",
    }
    if ONLINE_PROJECT_MODE:
        result.update(
            {
                "location": "Online Paper Studio Session memory",
                "setup_command": "",
                "restart_command": "",
                "security_note": "API key Only resides in online session memory; not written to project or browser storage.",
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
        options.append({"id": current_model, "label": f"{current_model}(Current configuration)"})
    return options


def select_llm_model(state: dict[str, Any], model: str) -> bool:
    """Persist a researcher-entered model name and reset incompatible LLM chains."""
    provider = str(state.get("llm_provider") or DEFAULT_PROVIDER).strip().lower()
    provider_configuration(provider)
    model = model.strip()
    if not model:
        raise StudioError("Model name cannot be empty.")
    if len(model) > 128 or any(character.isspace() or ord(character) < 32 for character in model):
        raise StudioError("Model name must be a single line identifier without spaces or control characters and no more than 128 characters.")
    if model_for_provider(provider, model) != model:
        raise StudioError(
            f"Model {model} is incompatible with the selected {provider} provider."
        )
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
    if str(payload.get("model") or "").startswith("deepseek-v4-"):
        # Paragraph drafting needs concise prose, not a billed reasoning trace.
        request_payload["thinking"] = {"type": "disabled"}
        request_payload["max_tokens"] = DEEPSEEK_PAPER_MAX_OUTPUT_TOKENS
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
                f"The current online session is not configured. {config['label']} API key; "
                "Please return to the Online Paper Studio entry and create a new session."
            )
        raise StudioError(
            f"Not yet configured {config['label']} LLM API.Please input in the local terminal that runs Paper Studio. "
            f"`{setup['setup_command']}`, Restart after stopping the current service. "
            f"`{API_KEY_RESTART_COMMAND}`.Do not input real API keys into the chat."
            "Submit to the repository or save to the browser."
        )
    if provider != "openai" and payload.get("tools"):
        raise StudioError(
            f"{config['label']} Current tool call is not supported; please use a text request without tools."
        )
    request_payload = payload
    # GPT-4o's Responses API accepts only ``medium`` text verbosity. Several
    # editing and audit passes ask newer models for ``low`` verbosity, so
    # normalize that optional hint at the provider boundary instead of
    # allowing an otherwise valid draft batch to fail midway.
    model = str(payload.get("model") or "").casefold()
    text_config = payload.get("text")
    if (
        provider == "openai"
        and model.startswith("gpt-4o")
        and isinstance(text_config, dict)
        and text_config.get("verbosity") != "medium"
    ):
        request_payload = dict(payload)
        request_payload["text"] = dict(text_config, verbosity="medium")
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


def mark_unverified_citations_as_needed(text: str) -> str:
    """Convert \\cite{} keys the model invented (never verified against the
    bibliography) into a plain-text [CITATION NEEDED] marker.

    Used when the active provider cannot run resolve_citations's web-search
    verification (any non-OpenAI provider). It reuses the same marker the
    rest of the pipeline already knows how to narrow or drop, so an
    unverifiable claim is never silently kept just because search wasn't
    available to check it.
    """
    unverified = citation_keys(text) - bibliography_keys()
    if not unverified:
        return text

    def replace(match: re.Match) -> str:
        keys = [key.strip() for key in match.group(1).split(",")]
        if any(key in unverified for key in keys):
            return "[CITATION NEEDED]"
        return match.group(0)

    return re.sub(r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}", replace, text)


def citation_placeholders(text: str) -> str:
    """Keep verified keys and turn only unresolved obligations into placeholders."""
    text = re.sub(
        r"\[CITATION\s+NEEDED[^\]]*\]",
        r"\\cite{}",
        text,
        flags=re.IGNORECASE,
    )
    known = bibliography_keys()

    def replace_unknown(match: re.Match) -> str:
        keys = [key.strip() for key in match.group(1).split(",") if key.strip()]
        return match.group(0) if keys and all(key in known for key in keys) else r"\cite{}"

    return re.sub(
        r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}",
        replace_unknown,
        text,
    )


def online_citation_markers(text: str) -> str:
    """Represent every hosted citation obligation as literal ``\\cite{}``."""
    text = re.sub(
        r"\[CITATION\s+NEEDED[^\]]*\]",
        r"\\cite{}",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}",
        r"\\cite{}",
        text,
    )


def local_survey_citations(text: str) -> str:
    """Keep only real keys backed by the local verified literature survey."""
    text = re.sub(
        r"\[CITATION\s+NEEDED[^\]]*\]",
        r"\\cite{}",
        text,
        flags=re.IGNORECASE,
    )
    allowed = survey_bibliography_keys()

    def replace_unapproved(match: re.Match) -> str:
        keys = [key.strip() for key in match.group(1).split(",") if key.strip()]
        return match.group(0) if keys and all(key in allowed for key in keys) else r"\cite{}"

    return re.sub(
        r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}",
        replace_unapproved,
        text,
    )


def remove_manuscript_citations(text: str) -> str:
    """Remove citation commands from sections whose project role forbids them."""
    without = re.sub(
        r"\s*\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}",
        "",
        text,
    )
    return re.sub(r"[ \t]+([,.;:!?])", r"\1", without)


def has_empty_citation_placeholder(text: str) -> bool:
    return bool(re.search(r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{\s*\}", text))


def validate_citations_for_accept(text: str, *, workflow: str = "body text") -> None:
    """Apply one citation gate to interactive and direct-full-draft Accept."""
    if ONLINE_PROJECT_MODE:
        non_placeholder_keys = citation_keys(text)
        if non_placeholder_keys:
            raise StudioError(
                f"{workflow}Online mode can only retain \\cite{{}} Mark, cannot write to citation key."
                + ", ".join(sorted(non_placeholder_keys))
            )
        return
    if has_empty_citation_placeholder(text):
        raise StudioError(
            f"{workflow}Still unresolved. \\cite{{}}; Please regenerate, or start from the project already verified items. "
            "references.bib Select a real citation."
        )
    allowed = bibliography_keys() if ONLINE_PROJECT_MODE else survey_bibliography_keys()
    unknown = sorted(citation_keys(text) - allowed)
    if unknown:
        raise StudioError(
            f"{workflow}Contains citation keys not verified by survey HTML:"
            + ", ".join(unknown)
        )


def needs_citation_resolution(text: str) -> bool:
    return (
        "[CITATION NEEDED]" in text
        or has_empty_citation_placeholder(text)
        or any(
            key.startswith("[") and key.endswith("]")
            for key in citation_keys(text)
        )
        or bool(citation_keys(text) - bibliography_keys())
    )


def resolve_citations_from_survey(
    *,
    model: str,
    previous_response_id: str,
    section: str,
    purpose: str,
    paragraph: str,
) -> tuple[str, str]:
    """Audit one local paragraph using only sources already verified in survey HTML."""
    if SECTION_MAP.get(section, {}).get("render") == "abstract":
        return previous_response_id, remove_manuscript_citations(paragraph)
    allowed = survey_bibliography_keys()
    catalog = bibliography_prompt_catalog(
        paragraph + "\n" + purpose,
        allowed_keys=allowed,
    )
    if not allowed or not catalog:
        return previous_response_id, local_survey_citations(paragraph)
    prior_counts = prior_section_citation_counts(section, paragraph)
    response = post_openai(
        {
            "model": model,
            "store": True,
            "previous_response_id": previous_response_id,
            "instructions": """Audit citations in one academic manuscript paragraph.
Return only the complete LaTeX-ready paragraph. First decide whether the paragraph has
any genuine external attribution obligation; zero citations is a valid and often correct
result. Do not cite generic motivation, common knowledge, a self-contained definition,
or this paper's own method, experiments, results, and interpretations. Add a citation
only where a specific prior work, externally sourced claim, method, model, dataset,
benchmark, or metric needs attribution for the sentence to be accurate. Prefer the
smallest directly supporting set and never append a survey-style citation dump to a
broad opening sentence. Select only keys in <survey_catalog>, which comes from the
project's verified literature-survey HTML. Never use web search, invent a key, or add a
bibliographic record. Replace a genuinely required but unsupported citation position
with the literal \\cite{}. Avoid reusing a key listed in
<citations_already_used_in_section> for a generic restatement. Reuse is allowed only
when this paragraph makes a distinct, source-specific claim that genuinely requires
that same paper; a key already used twice should not appear a third time. Preserve all
scientific claims, numbers, headings, artifact
references, and wording except the citation commands.""",
            "input": f"""<section>{section}</section>
<paragraph_purpose>{purpose}</paragraph_purpose>
<paragraph>{paragraph}</paragraph>
<citations_already_used_in_section>{json.dumps(prior_counts, ensure_ascii=False)}</citations_already_used_in_section>
<survey_catalog>{catalog}</survey_catalog>

Return the citation-audited paragraph only.""",
            "text": {"verbosity": "low"},
        }
    )
    revised = normalize_latex_ready_text(extract_output_text(response))
    response_id = str(response.get("id") or "")
    if not revised or not response_id:
        raise StudioError("Survey citation audit did not return a paragraph.")
    return response_id, local_survey_citations(revised)


def resolve_citations_from_online_bibliography(
    *,
    model: str,
    previous_response_id: str,
    section: str,
    purpose: str,
    paragraph: str,
    minimum_placeholders: int = 0,
) -> tuple[str, str]:
    """Mark every genuine hosted citation obligation with ``\\cite{}``."""
    if SECTION_MAP.get(section, {}).get("render") == "abstract":
        return previous_response_id, remove_manuscript_citations(paragraph)
    prior_counts = prior_section_citation_counts(section, paragraph)
    minimum_placeholders = max(0, int(minimum_placeholders))
    minimum_instruction = (
        f" This paragraph must retain at least {minimum_placeholders} literal "
        "\\cite{} placeholder(s) at the clauses that most clearly depend on prior "
        "literature, so the researcher can fill them after export."
        if minimum_placeholders
        else ""
    )
    response = post_openai(
        {
            "model": model,
            "store": True,
            "previous_response_id": previous_response_id,
            "instructions": """Audit citation obligations in one academic manuscript
paragraph. Return only the complete LaTeX-ready paragraph. This online workflow has no
bibliography and must not emit any citation key, author, year, title, or BibTeX record.
Insert the exact literal marker \\cite{} immediately after every clause that genuinely
depends on prior work, an externally sourced factual claim, a named existing method,
model, dataset, benchmark, or metric. Use no citation for this paper's own method,
proposed experiment, interpretation, common knowledge, or self-contained definition.
Preserve the paragraph's scientific content, numbers, headings, and artifact references.
Do not remove an external claim merely because no bibliography is available; mark its
citation position with \\cite{}. Do not append a citation dump at paragraph end."""
            + minimum_instruction,
            "input": f"""<section>{section}</section>
<paragraph_purpose>{purpose}</paragraph_purpose>
<paragraph>{paragraph}</paragraph>
<citations_already_used_in_section>{json.dumps(prior_counts, ensure_ascii=False)}</citations_already_used_in_section>
Return the citation-audited paragraph only.""",
            "text": {"verbosity": "low"},
        }
    )
    revised = normalize_latex_ready_text(extract_output_text(response))
    response_id = str(response.get("id") or "")
    if not revised or not response_id:
        raise StudioError("Online citation audit did not return a paragraph.")
    revised = online_citation_markers(revised)
    if revised.count(r"\cite{}") < minimum_placeholders:
        response = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the same complete LaTeX-ready paragraph. Preserve "
                    "all wording, claims, numbers, headings, and artifact references. "
                    f"Insert at least {minimum_placeholders} exact literal \\cite{{}} "
                    "placeholder(s), attached locally to the most appropriate external "
                    "background or prior-literature clauses. Do not invent citation "
                    "keys, authors, titles, years, or bibliography records."
                ),
                "input": f"<paragraph>{revised}</paragraph>",
                "text": {"verbosity": "low"},
            }
        )
        revised = online_citation_markers(
            normalize_latex_ready_text(extract_output_text(response))
        )
        response_id = str(response.get("id") or "")
    if not revised or not response_id or revised.count(r"\cite{}") < minimum_placeholders:
        raise StudioError(
            "Online citation audit did not preserve the required empty citation slots."
        )
    return response_id, revised


def repair_empty_citation_placeholders(
    *,
    model: str,
    previous_response_id: str,
    section: str,
    purpose: str,
    paragraph: str,
) -> tuple[str, str]:
    """Resolve or remove unsupported external clauses before acceptance.

    Citation audits intentionally use ``\\cite{}`` as a fail-safe when a claim
    is not supported by their bounded catalog.  Leaving that sentinel for the
    accept handler makes batch writing stop even when a verified source exists,
    while deleting it mechanically would publish an unsupported attribution.
    Give the low-output text model one final, catalog-bounded choice: cite a
    directly supporting verified record, or narrowly remove/rewrite the external
    attribution.  The server still rejects the paragraph if the sentinel remains.
    """
    if ONLINE_PROJECT_MODE:
        return previous_response_id, online_citation_markers(paragraph)
    if not has_empty_citation_placeholder(paragraph):
        return previous_response_id, paragraph
    catalog = writing_bibliography_catalog(purpose + "\n" + paragraph)
    response = post_openai(
        {
            "model": model,
            "store": True,
            "previous_response_id": previous_response_id,
            "instructions": (
                "Return only the complete corrected LaTeX-ready paragraph. Replace "
                "every empty \\cite{} placeholder with a key from <verified_catalog> "
                "only when that record directly supports the exact external clause. "
                "If no supplied record supports the clause, narrowly remove or rewrite "
                "that unsupported external attribution while preserving this paper's "
                "own claims, method, evidence, numbers, heading, and figure/table "
                "references. Never leave an empty citation, invent a key, source, "
                "author, year, claim, or result, and never add a survey-style citation "
                "list. A self-contained paragraph with zero citations is valid. "
                + MANUSCRIPT_DASH_RULE
            ),
            "input": (
                f"<section>{section}</section>\n"
                f"<paragraph_purpose>{purpose}</paragraph_purpose>\n"
                f"<verified_catalog>{catalog}</verified_catalog>\n"
                f"<paragraph_with_empty_citations>{paragraph}</paragraph_with_empty_citations>"
            ),
            "text": {"verbosity": "low"},
        }
    )
    revised = normalize_latex_ready_text(extract_output_text(response))
    response_id = str(response.get("id") or "")
    if not revised or not response_id:
        raise StudioError("Citation placeholder repair did not return a paragraph.")
    revised = local_survey_citations(revised)
    if has_empty_citation_placeholder(revised):
        # Some inexpensive models preserve the fail-safe sentinel even after
        # receiving a bounded catalog. Use the catalog's relevance ordering as
        # a deterministic final repair, never an invented key. Each unresolved
        # position receives at most one verified record; if the catalog is
        # empty we still fail closed below.
        verified_keys = re.findall(r"(?m)^key=([^ |]+)", catalog)
        key_iter = iter(dict.fromkeys(verified_keys))

        def use_verified_key(match: re.Match[str]) -> str:
            try:
                return rf"\cite{{{next(key_iter)}}}"
            except StopIteration:
                return match.group(0)

        revised = re.sub(
            r"\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{\s*\}",
            use_verified_key,
            revised,
        )
        if has_empty_citation_placeholder(revised):
            raise StudioError(
                "Citation Unresolved after automated repair. \\cite{}; Candidate not accepted."
            )
    return response_id, revised


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
        if bibtex.count("{") != bibtex.count("}"):
            # A real batch-writing run hit a citation-search response that
            # truncated mid-field (an accented author name cut off at
            # "Nicol{\"), and this code appended it to references.bib
            # verbatim -- the opening-pattern check above only validates the
            # entry *starts* correctly, not that it is syntactically
            # complete. One unbalanced entry corrupts bibtex's parse of
            # every entry after it in the file, so several unrelated,
            # perfectly well-formed citations all failed to resolve too.
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
        "instructions": """Resolve missing scholarly citations for one academic paper
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
    comment: str,
    current_text: str,
    architecture: dict[str, str] | None = None,
    reference_context: dict[str, Any] | None = None,
    reference_paragraph: str = "",
    bibliography_update: str = "",
    artifacts: list[str] | None = None,
    figure_states: dict[str, dict[str, Any]] | None = None,
    required_heading_style: str | None = None,
    include_section_context: bool | None = None,
    minimum_online_citation_placeholders: int = 0,
    maximum_word_override: int | None = None,
) -> tuple[str, str, list[str]]:
    fresh_rewrite = bool(
        re.search(
            r"\b(?:rewrite|redraft|start)\b.{0,24}\bfrom scratch\b|"
            r"\bignore (?:the )?(?:previous|old)\b|\bfresh draft\b",
            comment,
            flags=re.IGNORECASE,
        )
    )
    if fresh_rewrite:
        previous_response_id = None
    previous_response_id = reusable_response_id(previous_response_id)
    section_meta = SECTION_MAP[section]
    section_path = PAPER / "sections" / section_meta["file"]
    if include_section_context is None:
        include_section_context = not previous_response_id
    # Citation anti-repetition is a manuscript-state constraint, not a chat
    # context constraint.  Full-draft writing reuses a response id after the
    # first paragraph, so ``include_section_context`` is normally false.  The
    # old implementation consequently counted citations in an empty string and
    # allowed the same key to appear three or more times in a section.
    complete_section = read_text(section_path, 500_000)
    section_citations_already_used = citation_key_counts(
        complete_section.replace(current_text.strip(), "", 1)
        if current_text.strip()
        else complete_section
    )
    current_section = complete_section[:24000] if include_section_context else ""
    if "awaiting paragraph-level drafting" in current_section.lower() or (
        section_meta.get("render") == "abstract"
        and "working abstract will be drafted" in current_section.lower()
    ):
        current_section = ""
    if fresh_rewrite and current_text.strip():
        current_section = current_section.replace(current_text.strip(), "")
    current_section = bounded_prompt_text(
        current_section,
        PAPER_TEXT_CONTEXT_LIMITS["current_section"],
        "current section",
    )
    current_text = bounded_prompt_text(
        current_text,
        PAPER_TEXT_CONTEXT_LIMITS["current_candidate"],
        "current candidate",
    )
    purpose = bounded_prompt_text(
        purpose, PAPER_TEXT_CONTEXT_LIMITS["purpose"], "paragraph purpose"
    )
    comment = bounded_prompt_text(
        comment, PAPER_TEXT_CONTEXT_LIMITS["researcher_comment"], "researcher comment"
    )
    stable_context = ""
    evidence = bounded_prompt_text(
        section_evidence(section, artifacts),
        PAPER_TEXT_CONTEXT_LIMITS["section_evidence"],
        "section evidence",
    )
    if not previous_response_id:
        bibliography_context = "\n".join(
            (section_meta["title"], purpose, current_text, current_section, evidence)
        )
        prompt_bibliography = (
            ""
            if ONLINE_PROJECT_MODE
            else writing_bibliography_catalog(bibliography_context)
        )
        stable_context = f"""<conversation_bootstrap>
<approved_outline>{bounded_prompt_text(approved_outline_context(), PAPER_TEXT_CONTEXT_LIMITS['outline'], 'approved outline')}</approved_outline>
<working_abstract>{bounded_prompt_text(effective_working_abstract_context(), PAPER_TEXT_CONTEXT_LIMITS['working_abstract'], 'working abstract')}</working_abstract>
<writing_style>{bounded_prompt_text(writing_style_context(), PAPER_TEXT_CONTEXT_LIMITS['writing_style'], 'writing style')}</writing_style>
<bibliography_catalog>{bounded_prompt_text(prompt_bibliography, BIBLIOGRAPHY_PROMPT_MAX_CHARS, 'bibliography catalog')}</bibliography_catalog>
<section_evidence>{evidence}</section_evidence>
</conversation_bootstrap>"""
    bound_artifacts = artifact_writing_context(artifacts, figure_states)
    architecture_json = bounded_prompt_text(
        json.dumps(
            effective_writing_architecture(section, architecture, bound_artifacts),
            ensure_ascii=False,
            indent=2,
        ),
        PAPER_TEXT_CONTEXT_LIMITS["architecture"],
        "paragraph architecture",
    )
    reference_context_json = bounded_prompt_text(
        json.dumps(section_writing_logic_chain(section), ensure_ascii=False, indent=2),
        PAPER_TEXT_CONTEXT_LIMITS["reference_context"],
        "reference context",
    )
    bound_artifacts_json = bounded_prompt_text(
        json.dumps(bound_artifacts, ensure_ascii=False, indent=2),
        PAPER_TEXT_CONTEXT_LIMITS["bound_artifacts"],
        "bound artifacts",
    )
    required_heading_command = heading_latex(
        required_heading, required_heading_style
    )

    venue = str(PROJECT_METADATA.get("venue", "academic")).strip() or "academic"
    active_metrics = metrics_bundle()
    lightweight_project = (
        active_metrics.get("lightweight_project", {})
        if isinstance(active_metrics, dict)
        else {}
    )
    use_x_for_numbers = (
        isinstance(lightweight_project, dict)
        and lightweight_project.get("numeric_policy")
        == "replace_quantitative_values_with_xx"
    )
    active_fixture = (
        active_metrics.get("fixture", {}) if isinstance(active_metrics, dict) else {}
    )
    synthetic_fixture = bool(
        active_fixture.get("synthetic", active_metrics.get("synthetic", False))
        if isinstance(active_fixture, dict)
        else active_metrics.get("synthetic", False)
    )
    executed_result_rows = any(
        isinstance(artifact, dict) and bool(artifact.get("rows"))
        for artifact in (
            active_metrics.get("artifacts", {}).values()
            if isinstance(active_metrics.get("artifacts"), dict)
            else []
        )
    )
    measurement_marker_rule = (
        "No experiment results are available. Preserve every experimental-design "
        "constant explicitly supplied in target_project_brief, including sample counts, "
        "permutation counts, seeds, decoding settings, and API-call budgets. Use the "
        "literal xx only for unavailable result measurements such as observed scores, "
        "percentages, effects, confidence intervals, and measured outcomes. "
        "Do not alter LaTeX command names, citation keys, labels, or section commands. "
        "Never infer a design value, turn sampled random permutations into exhaustive "
        "enumeration, or copy a concrete number from the structural reference. In the "
        "Experiments section, write the proposed setup and required experiments in "
        "future tense and never claim that an outcome was observed. Keep each "
        "plan-only experiment paragraph at or below 75 words."
        if use_x_for_numbers
        else
        "Every numerical measurement or outcome from the paper-writing fixture must "
        "include the literal marker [SYNTHETIC]. This fixture is a software skill test, "
        "not an executed scientific study. Report only values explicitly supplied in "
        "section_evidence or bound_artifacts; never claim confidence intervals, held-out "
        "seed inference, non-inferiority, statistical significance, or a scientific "
        "claim disposition unless those exact records are supplied. If the approved "
        "future-study plan conflicts with the supplied toy evidence, describe the "
        "fabricated pipeline test and preserve the unexecuted study as future work."
        if synthetic_fixture
        else (
            "The supplied metrics are already executed, verified real measurements; "
            "do not add a [SYNTHETIC] marker and do not describe populated results as "
            "pending, pre-registered, planned, future work, or awaiting a run. Report "
            "them in past/present tense and preserve every scope qualification present "
            "in the execution evidence rather than upgrading the study's evidential status."
        )
    )
    instructions = f"""You are an expert {venue} paper editor. Return only the proposed
LaTeX-ready manuscript prose for the requested paragraph; do not explain your process.
Write in precise academic English. Preserve the approved paper framing and evidence
boundaries. Never invent a result, citation key, or experimental detail. Numerical
measurements and outcomes must follow this fixture rule: {measurement_marker_rule}
{MANUSCRIPT_DASH_RULE}
Never invent a Figure, Table, Section, Appendix, equation, or page reference. Use only
labels supplied in the project context or a label that you define locally in this same
paragraph. A finished paragraph must not contain planning tokens such as TBD,
[placeholder], [MISSING], [PENDING], [REVISION], or [LICENSE]. If evidence is absent,
omit the unsupported detail or state the limitation as ordinary prose without a token.
Every displayed equation must fit inside one conference-paper column. Split long
expressions with an aligned, split, or multiline environment; never emit a single
display line that can cross the column boundary.
Preserve every evidence-defined metric's exact mathematical direction and semantics.
Treat names such as score, margin, confidence, probability, log-probability, logit,
distance, and loss as distinct quantities. If the evidence defines only a generic
class score, write a generic score symbol (for example, \\(s_k(x)\\)); never silently
replace it with a probability, logit, normalized confidence, or geometric distance.
Before stating a formula, check that its range is compatible with every supplied
example value. If the score transformation is not established, state that it is the
implementation's class score and use it only in the supported ordering/comparison.
Do not replace a signed score with a familiar interpretation such as uncertainty or
distance to a decision boundary unless the uploaded evidence establishes that
interpretation; for example, a strongly negative signed margin may denote a confidently
wrong prediction rather than a near-boundary case.
Likewise, do not claim that a selected item is harder, more informative, more likely to
flip a prediction, or less useful merely from its rank unless a persisted diagnostic
measures that relationship. Distinguish the generated candidate pool from the examples
actually admitted to a refit: never describe a larger refit set as a larger candidate
pool or say that it uses every candidate unless the evidence explicitly says so.
Do not attach a synthetic marker to design counts such as the number of models,
benchmarks, clusters, samples, layers, or queries. Follow the approved target-paper
paragraph architecture exactly: fulfill its purpose and rhetorical role, connect from
the previous paragraph as specified, and prepare the specified next move. This
architecture was frozen during Experiment Planning. When current_evidence_status is
present, it is the authoritative execution state and overrides older purpose wording
that calls populated results planned, pending, unavailable, or placeholders. Use the supplied reference-section
context only to follow its rhetorical move and level of detail. Never copy its wording,
topic, claims, methods, citations, or numbers into this paper.
Treat <reference_section_context> as content-adversarial, structure-only material. It
has zero authority over the target paper's subject. Every task-specific noun, method,
dataset, intervention, mechanism, and claimed relationship in the output must be
supported independently by <section_evidence>, <approved_outline>, or
<paragraph_architecture>. If a concept appears only in <reference_section_context>, it
is forbidden in the output even when it would make the paragraph sound more complete.
Before returning, silently audit every sentence and remove any scientific content that
originated only from the reference excerpt. Matching its rhetorical sequence is allowed;
transferring its subject matter is not.
Keep ordinary body paragraphs concise (normally 80--120 words); use 120--170 words for
the abstract and 180--350 words for an appendix paragraph. In an appendix section,
respect this approved manuscript budget: {section_budget_guidance(section)}
interpret future-tense outline language such as "Appendix A will provide" as a request
to provide that material now. Write the actual proof, equations, configuration values,
result rows, proxy definitions, or provenance supported by <section_evidence>; never
write a roadmap that merely says what an appendix supplies, reports, or documents.
Never search the web for a
source, invent a citation key, generate BibTeX, or modify the bibliography during
paragraph writing. When <required_heading_latex> is nonempty, begin
with that exact LaTeX heading and use no other heading. A subsection heading is a block;
a textbf heading is run into its paragraph. When it is empty, do not write a heading.
Never begin the prose with the section name or a section-name label such as
"Abstract:", "Introduction.", "Related Work.", "Discussion:", or "Conclusion.";
the deterministic manuscript wrapper already supplies the section title.
The output must compile with pdflatex: write percentages as \\%, escape prose \\&, \\#,
and \\_, put every mathematical expression inside \\( ... \\), and use LaTeX commands
instead of Unicode mathematical glyphs. Never emit a \\label{{...}} command; section and
artifact labels are owned and inserted by Paper Studio's deterministic wrapper."""
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
    instructions += """ Treat <citations_already_used_in_section> as a section-level
anti-redundancy constraint. Do not reuse a cited key merely because it is the most
familiar or broadly relevant source. Prefer zero citations for this paper's own claims,
or a different verified source for a genuinely different external claim. Reuse a key
only when the current paragraph makes a distinct source-specific claim that cannot be
supported otherwise; never make the same key appear for a third time in one section."""
    if _is_method_section(section):
        instructions += """ For Method prose, <approved_model_design> is the sole
authority for the implemented procedure. Describe only operations, inputs, outputs,
decision rules, symbols, validation behavior, and uncertainty calculations explicitly
present in that object. Never manufacture a score function, probability, argmax rule,
abstention policy, fallback, tie breaker, training objective, module, or model-internal
mechanism to make the method sound complete. In particular, a content-first protocol
that asks the API for answer text and a label and cross-validates the two fields must be
described as that observed response protocol, not recast as an unimplemented semantic
scoring model. If a requested detail is absent, omit it and retain the documented
unknown rather than filling the gap from convention. Copy every metric definition from
<executed_metric_definitions> when available, otherwise <metric_contract> or
approved_model_design.metric_definitions, exactly in substance.
Do not redefine a within-condition permutation transition as a between-condition
comparison, change an ordered transition set into all unordered pairs, or invent a
denominator. Follow <executed_prompt_conditions> literally. Distinguish the shared input
presentation from the requested response fields, and never apply an answer-text/label
cross-field check to a condition whose schema contains only a label."""
    if _is_discussion_section(section):
        instructions += """ Discussion must interpret the scientific pattern rather
than reproduce the result ledger. Never expose JSON keys, snake_case field names,
artifact IDs, raw locators, or an exhaustive list of rows and cells. Select only the
few measurements needed to support a comparison, round them consistently for readable
prose, and explain their implication and boundary. Do not restate Experimental Setup,
do not narrate the table schema, and do not infer model internals from black-box output.
Treat every alternative explanation as unresolved unless <section_evidence> explicitly
contains the corresponding executed control and its result. A marginal frequency table
can establish only the displayed marginal pattern; it cannot establish what caused
within-item flips. Follow claim_dispositions exactly: distinguish a point-estimate gate
from confidence-qualified support, and never call an inconclusive claim validated or
satisfied."""
    if _is_related_work_section(section):
        instructions += """ Related Work may compare prior observables, interventions,
and evaluation scopes, but it must not claim that this paper distinguishes causal
mechanisms unless section_evidence contains the required executed controls. Differences
between label-only and text-plus-label output schemas confound response order, verbosity,
format compliance, and validation behavior; describe them as an intervention comparison,
not as a decomposition of those explanations. Every source-specific prior-work statement
must carry a verified citation from the bibliography catalog."""
    if _is_experiment_section(section):
        instructions += """ Executed counts in execution_summary override planned budgets
and projected sample sizes. Clearly distinguish the initial sampled pool, development
slice, final evaluation set, paired complete-case set, excluded questions, and API calls;
never multiply or relabel one as another. When authoritative_count_statement or
authoritative_retry_statement is present, copy the relevant statement exactly rather
than recalculating, paraphrasing, or replacing any count. Qualitative case prose may report only fields
present in qualitative_cases. When qualitative_evidence_scope says that attributes were
not annotated, do not characterize ambiguity, distractor quality, reasoning strategy,
confidence, or mechanism; state that those interpretations remain unsupported."""
        instructions += """ Apply executed_prompt_conditions separately by condition.
A label-only response can establish a valid selected label and inverse-mapped semantic
answer, but it cannot establish answer-text agreement. Mention text-label cross-field
validation only for a condition whose executed schema contains both fields. Never say
that every accepted response passed a shared text-label check when the schemas differ."""
    if active_metrics.get("scientific_integrity_version") == 2:
        instructions += """ The scientific-integrity contract uses an independent gold
oracle. Any implementation that is defined as a reference or conformance control must
be described only as a check that the executable benchmark agrees with that separate
oracle. Its perfect oracle agreement is not a method-performance contribution and must
not be framed as outperforming, improving on, beating, or performing best among
baselines. Registered alternatives are mutation tests or diagnostic controls, not fair
competitor systems. State conclusions as benchmark detection of the registered mutant
failure, using only the preregistered threshold and interval. Do not call a component
causally necessary merely because removing it reproduces a registered mutant. The
direct-key mutant is registered for under-propagation and unauthorized actions; the
any-parent mutant is registered for over-propagation and erasure of independently
supported conclusions. Never swap those failure directions. Under-propagation and
over-propagation are distinct harms, not identical harms, and neither may be called more
costly without a supplied utility or cost measure. When discussing a 100% reference
score, say only that the reference implementation matched the independent oracle as
required by conformance; do not call that score perfect performance, robustness, or an
experimental finding."""
        if "reference replay cost" in purpose.casefold():
            instructions += """ In this paragraph, report only the reference control's
replay latency as its measured quantity. Report affected-node and authorization changes
only for the registered component mutants. The reference accuracy cells may remain in
the bound table for auditability, but prose must describe them only as oracle-conformance
checks and must not present them as gains, achievements, or ablation benefits."""
    is_experimental_setup = _is_experiment_section(section) and bool(
        re.search(
            r"\b(?:experimental setup|protocol|vector extraction|calibration|"
            r"dataset|baseline selection)\b",
            purpose,
            re.IGNORECASE,
        )
    )
    if is_experimental_setup:
        instructions += """ For an Experimental Setup or protocol paragraph, use a
fixed compact format and avoid motivation or interpretation. Write one compact body
paragraph that identifies the datasets, exact executed model, prompt count, seed,
decoding, and then states the exact baseline count and every baseline name from
experiment_setup_contract. Do not replace this list with procedural freeze language.
Name only implementation details supplied in section_evidence.
Do not expand baseline details into a literature review. Keep planned confirmatory
inference explicitly separate from any synthetic software-test values."""
        if ONLINE_PROJECT_MODE:
            instructions += """ For every named external dataset and published baseline,
place the literal marker \\cite{} immediately after its first mention. The hosted
workflow has no bibliography and must never emit a citation key. Internal controls
defined by this paper need no citation."""
        else:
            instructions += """ For datasets and published baselines, attach the verified
introducing citation from <bibliography_catalog> at their first mention in the setup;
internal controls defined by this paper need no citation."""
    if _is_appendix_section(section):
        instructions += """ Write only material supported by <section_evidence>.
Configuration and provenance must reproduce the exact model, seed, prompt count,
strength grid, token limit, elapsed time, memory, Python, platform, and machine fields
from execution_records when present. Do not name a GPU, package version, dataset
license, repository commit, branch, demonstration count, layer index, prompt text, or
result cell unless that exact item is present in section_evidence. Omit any requested
appendix field for which no execution record exists. Use LaTeX commands such as
\\textbf{} and \\texttt{}; never output Markdown headings, asterisks, or backticks."""
    if _is_synthesis_section(section):
        instructions += """ The primary_comparison_outcome is a deterministic
reading of the populated main table and overrides any optimistic claim wording in the
approved plan. If its proposed method has zero wins, explicitly report that the stronger
baseline outperformed it and do not claim better prediction, improved alignment,
substantial explained variance, or validation of the predictive mechanism."""
        instructions += """ Use execution_summary rather than planned counts. Follow each
claim_dispositions status and confidence gate exactly. A point estimate that passes a
threshold while its paired confidence interval crosses that threshold is inconclusive,
not confirmed, validated, or satisfied. Report mixed dataset directions explicitly
instead of replacing them with a pooled success statement."""
    instructions += """ A writing-stage motivation or conceptual figure is not empirical
evidence by itself. If a concrete example is not present in traceable section evidence,
describe it explicitly as hypothetical and never say that the tested model produced the
illustrated response. In a permutation example, judge correctness only after mapping the
displayed response back to semantic content; never score a reordered answer using a
different ordering's label map. Distinguish where information appears in the input from
the order of fields requested in the output. An observed within-item answer change
establishes sensitivity to the intervention, not why the answer changed. Do not infer
that a model was confused, reasoned in a particular way, or consistently preferred a
position from a hypothetical example or isolated case. A position preference requires
the supplied aggregate position observable, and even that marginal pattern does not by
itself establish the cause of within-item flips."""
    if section_meta.get("render") == "abstract":
        instructions += """ The Abstract must contain no citation commands. State the
paper's motivation, method, evidence, and bounded conclusion self-containedly; leave
literature attribution and dataset citations to the body. Do not emit \\cite{...} or
\\cite{} even if the bibliography catalog contains relevant sources."""
        if executed_result_rows:
            instructions += """ The experiment has already run. Any [X], [X\\%], or
[N] marker in the approved architecture is an obsolete planning placeholder, not an
output requirement. Use exact measurements supplied in <section_evidence> when they
directly support the claim. If a planned numerical claim is not supported there, omit
or qualitatively narrow it; never emit a bracketed numerical placeholder and never
invent a value."""
        elif ONLINE_PROJECT_MODE:
            instructions += """ This hosted project has no experiment-result input.
Describe the evaluation as proposed future work. Do not say that this paper applies,
evaluates, reports, shows, finds, demonstrates, or observes experimental outcomes.
Use formulations such as "we will evaluate" or "the proposed evaluation will test",
and do not imply that any experiment has already run."""
    elif ONLINE_PROJECT_MODE:
        instructions += """ Decide from the actual paragraph content whether any
citation is needed; a paragraph may legitimately contain zero citations. Do not cite
generic motivation, common knowledge, a self-contained definition, or this paper's own
method, experiments, findings, and interpretations. Only when a specific prior work,
externally sourced claim, method, model, dataset, benchmark, or metric genuinely needs
attribution, place the exact literal marker \\cite{} immediately after that clause.
The hosted workflow has no bibliography: never emit a citation key, author/year
attribution, title, or BibTeX record. Mark every genuine citation obligation and never
append a broad citation dump at the end of a paragraph. The \\cite{} markers are
intentional output and must be preserved when the paragraph is accepted."""
    else:
        instructions += """ Decide from the actual paragraph content whether any
citation is needed; a paragraph may legitimately contain zero citations. Do not cite
generic motivation, common knowledge, a self-contained definition, or this paper's own
method, experiments, findings, and interpretations. Only when a specific prior work,
externally sourced claim, method, model, dataset, benchmark, or metric genuinely needs
attribution, cite the exact clause. Select only real keys supplied in
<bibliography_catalog>; those records are already verified in
reports/01_LIT_SURVEY.html. Prefer the smallest directly supporting set and never append
a survey-style citation dump to a broad sentence. Never use a key outside that catalog.
If a genuinely necessary citation lacks support in the catalog, write the literal
\\cite{} at that position. Every explicit author/year attribution (for example,
Smith et al. (2024)) must carry a supporting citation command in the same sentence."""

    user_input = f"""<section>{section_meta['title']}</section>
<paragraph_purpose>{purpose.strip()}</paragraph_purpose>
<required_heading>{(required_heading or '').strip()}</required_heading>
<required_heading_style>{(required_heading_style or '').strip()}</required_heading_style>
<required_heading_latex>{required_heading_command}</required_heading_latex>
<researcher_comment>{comment.strip()}</researcher_comment>
<current_candidate>{'' if fresh_rewrite else current_text.strip()}</current_candidate>
<current_section_context>{current_section}</current_section_context>
<paragraph_architecture>{architecture_json}</paragraph_architecture>
<reference_section_context>{reference_context_json}</reference_section_context>
<bound_artifacts>{bound_artifacts_json}</bound_artifacts>
<citations_already_used_in_section>{json.dumps(section_citations_already_used, ensure_ascii=False)}</citations_already_used_in_section>
{f"<bibliography_update>{bounded_prompt_text(bibliography_update, BIBLIOGRAPHY_PROMPT_MAX_CHARS, 'bibliography update')}</bibliography_update>" if bibliography_update else ""}
{stable_context}

Revise or draft exactly one coherent paragraph for the stated purpose. If required
evidence or a citation key is unavailable, omit or narrowly qualify the unsupported
claim instead of guessing or emitting a planning placeholder. The target project
evidence is the sole content authority; the reference excerpt is never target-paper
evidence.{(
    ' Before writing any bracketed numerical placeholder, exhaustively check '
    '<section_evidence>, including uploaded headline, aggregate, inference, and summary '
    'objects. If the requested measurement is present there, use its exact value '
    '(rounded only for readable reporting) and do not leave a placeholder for it.'
    if stable_context else ''
)}"""

    prompt_chars = len(instructions) + len(user_input)
    if prompt_chars > PAPER_TEXT_PROMPT_MAX_CHARS:
        raise StudioError(
            "Paper Studio paragraph prompt exceeded its cost budget: "
            f"{prompt_chars} > {PAPER_TEXT_PROMPT_MAX_CHARS} characters."
        )

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
            raise StudioError("GPT No main text returned after applying modification request.")
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
            raise StudioError("GPT No main text returned after supplementing figure references.")
        remaining_reference_error = artifact_reference_error(text, bound_artifacts)
        if remaining_reference_error:
            raise StudioError("GPT Still after correction." + remaining_reference_error)
    has_traceable_bound_results = any(
        isinstance(item, dict) and bool(item.get("traceable_results"))
        for item in bound_artifacts
    )
    if has_traceable_bound_results:
        # A generation pass can copy every value yet attach one to the wrong
        # row/column, silently change ``-1`` into a fraction-like phrase, or
        # round .99/1.00/.99 into "all 1.00".  Numeric membership checks cannot
        # catch those semantic mapping errors because each number is present
        # somewhere in the same table.  Run a small evidence-only audit before
        # citation editing so the accepted prose is checked against the exact
        # bound rows rather than against model memory.
        audit = post_openai(
            {
                "model": model,
                "store": True,
                # Use an independent verifier conversation.  Continuing the
                # drafting conversation anchored the checker to the draft's
                # mistaken row/column reading even after the exact table was
                # supplied, so a wrong Refusal condition survived the audit.
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. "
                    "Audit every empirical statement against <bound_result_evidence>. "
                    "For each reported value, verify its exact row, column, condition, "
                    "multiplier sign, model, and metric. Preserve signed header values "
                    "such as -1, 0, and +1 as explicit LaTeX numerals; never spell, "
                    "reinterpret, or silently change them. Do not call near-equal "
                    "values equal, saturated, all identical, at the floor, or at the "
                    "ceiling unless every relevant cell exactly supports that claim. "
                    "Recompute any stated difference from the supplied cells. Remove "
                    "or narrow any claim the rows do not establish. Preserve the "
                    "required heading, citations, and configured table or figure "
                    "reference exactly once. Never invent a value, source, label, or "
                    "experimental condition. The supplied rows are executed real "
                    "measurements: remove plan-only descriptions such "
                    "as planned, placeholder, will report, or no observed result, and "
                    "report supported observations in past or present tense while "
                    "preserving the evidence-defined scope qualification. "
                    "Honor writing_evidence_boundaries exactly: do not report metrics "
                    "outside executed_metric_definitions, derive an unreported audit "
                    "count, infer confidence or a causal mechanism from marginal "
                    "frequencies, shorten a saved four-answer case sequence, or make a "
                    "categorical novelty claim. Audit logical consistency as well as "
                    "table cells. "
                    + MANUSCRIPT_DASH_RULE
                ),
                "input": (
                    f"<bound_result_evidence>{evidence}</bound_result_evidence>\n"
                    f"<paragraph_to_audit>{text}</paragraph_to_audit>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(audit))
        response_id = str(audit.get("id") or "")
        if not text or not response_id:
            raise StudioError("The chart evidence audit did not return revised paragraphs.")
        text, response_id = repair_artifact_reference_contract(
            model=model,
            response_id=response_id,
            text=text,
            bound_artifacts=bound_artifacts,
        )
        # Discussion legitimately synthesizes several bound artifacts in one
        # sentence. A row-local validator cannot assign each numeral to one
        # table in that setting and therefore produces cross-artifact false
        # positives. The independent evidence audit above still verifies the
        # complete result bundle; reserve the strict row-local gate for prose
        # that is not a cross-artifact Discussion synthesis.
        row_value_issues = (
            []
            if _is_discussion_section(section)
            else bound_artifact_row_value_issues(text, evidence)
        )
        for _row_audit_attempt in range(2):
            if not row_value_issues:
                break
            correction = post_openai(
                {
                    "model": model,
                    "store": True,
                    "instructions": (
                        "Return only the complete corrected LaTeX-ready paragraph. "
                        "A deterministic table validator found decimal values copied "
                        "from a different named row. Correct every flagged sentence "
                        "using the exact row and column values in <bound_result_evidence>. "
                        "Remove a comparison if the supplied row does not support it. "
                        "Preserve the required heading, citations, and configured "
                        "artifact reference exactly once. Never invent, round, swap, "
                        "or relabel a value or condition. "
                        + MANUSCRIPT_DASH_RULE
                    ),
                    "input": (
                        "<deterministic_row_violations>"
                        + json.dumps(row_value_issues, ensure_ascii=False)
                        + "</deterministic_row_violations>\n"
                        f"<bound_result_evidence>{evidence}</bound_result_evidence>\n"
                        f"<paragraph_to_correct>{text}</paragraph_to_correct>"
                    ),
                    "text": {"verbosity": "low"},
                }
            )
            text = normalize_latex_ready_text(extract_output_text(correction))
            response_id = str(correction.get("id") or "")
            if not text or not response_id:
                raise StudioError("Cross-row numeric correction did not return revised paragraphs.")
            row_value_issues = (
                []
                if _is_discussion_section(section)
                else bound_artifact_row_value_issues(text, evidence)
            )
        if row_value_issues:
            raise StudioError(
                "The body text still contains values from incorrect table rows; candidate not accepted."
                + ", ".join(row_value_issues)
            )
        text, response_id = repair_artifact_reference_contract(
            model=model,
            response_id=response_id,
            text=text,
            bound_artifacts=bound_artifacts,
        )
    # Table-bound prose already receives a row-level audit above, but setup,
    # motivation, synthesis, and limitations can contradict structured facts
    # without quoting a table cell. Use a fresh verifier conversation so the
    # audit is not anchored to the drafting model's explanation.
    has_grounding_contract = not has_traceable_bound_results and any(
        bool(active_metrics.get(key))
        for key in (
            "execution_summary",
            "executed_metric_definitions",
            "executed_prompt_conditions",
            "writing_evidence_boundaries",
            "claim_dispositions",
        )
    )
    grounding_catalog = (
        writing_bibliography_catalog(purpose + "\n" + text)
        if has_grounding_contract and not ONLINE_PROJECT_MODE
        else ""
    )
    grounding = post_openai(
        {
            "model": model,
            "store": True,
            "instructions": (
                "Return only the complete corrected LaTeX-ready paragraph. Act as an "
                "independent evidence and logic editor, not as a stylistic rewriter. "
                "Preserve supported wording, the required heading, verified citation "
                "keys, and each configured artifact reference exactly once. Check every "
                "target-paper fact against <section_evidence>, <paragraph_architecture>, "
                "and <bound_artifacts>; the structural reference is not scientific "
                "evidence. Use authoritative count and retry statements verbatim when "
                "relevant, and never derive a scheduled-call count from the sampled "
                "pool. Apply response schemas condition by condition: a label-only "
                "response has no answer-text agreement check. Distinguish identical "
                "input option presentation from the requested output-field order. "
                "Follow every confidence-qualified claim disposition exactly. Audit "
                "logical consistency as well as numeric accuracy: two different semantic "
                "answers are not semantically identical; a wrong response is not correct; "
                "and an average must agree with the outcomes being averaged. An observed "
                "answer change establishes intervention sensitivity but not a preferred "
                "position, reasoning process, or causal mechanism. A marginal position "
                "distribution cannot exclude a cause of within-item flips. Treat competing "
                "explanations as unresolved without executed controls. Remove categorical "
                "novelty or prior-work-exclusion claims unless the verified catalog and "
                "approved evidence explicitly establish them. Do not add a new result, "
                "citation, model, dataset, mechanism, or limitation. "
                + MANUSCRIPT_DASH_RULE
            ),
            "input": (
                f"<section>{section_meta['title']}</section>\n"
                f"<paragraph_purpose>{purpose}</paragraph_purpose>\n"
                f"<paragraph_architecture>{architecture_json}</paragraph_architecture>\n"
                f"<section_evidence>{evidence}</section_evidence>\n"
                f"<bound_artifacts>{bound_artifacts_json}</bound_artifacts>\n"
                f"<verified_catalog>{grounding_catalog}</verified_catalog>\n"
                f"<paragraph_to_audit>{text}</paragraph_to_audit>"
            ),
            "text": {"verbosity": "low"},
        }
    ) if has_grounding_contract else {"id": response_id, "output_text": text}
    text = normalize_latex_ready_text(extract_output_text(grounding))
    response_id = str(grounding.get("id") or "")
    if not text or not response_id:
        raise StudioError("The independent evidence audit did not return a paragraph.")
    text, response_id = repair_artifact_reference_contract(
        model=model,
        response_id=response_id,
        text=text,
        bound_artifacts=bound_artifacts,
    )
    machine_field_issues = manuscript_machine_field_issues(
        section, text, evidence
    )
    if machine_field_issues:
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready Discussion "
                    "paragraph. Replace every raw JSON key, snake_case field name, "
                    "artifact ID, and ledger-style row dump with concise scientific "
                    "interpretation. Mention only the few rounded measurements needed "
                    "to support the comparison. Preserve the required heading, "
                    "citations, and each configured figure or table reference exactly "
                    "once. Do not invent, swap, or extrapolate any result."
                ),
                "input": (
                    "Detected reader-facing schema leakage: "
                    + "; ".join(machine_field_issues)
                    + f".\n<bound_result_evidence>{evidence}</bound_result_evidence>"
                    + f"\n<previous_paragraph>{text}</previous_paragraph>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        remaining_machine_field_issues = manuscript_machine_field_issues(
            section, text, evidence
        )
        if not text or not response_id or remaining_machine_field_issues:
            raise StudioError(
                "Discussion still exposes raw result-schema fields; candidate not accepted. "
                + ", ".join(
                    remaining_machine_field_issues or machine_field_issues
                )
            )
    tense_issues = (
        unexecuted_experiment_tense_issues(section, text)
        if ONLINE_PROJECT_MODE and use_x_for_numbers
        else []
    )
    for plan_correction_attempt in range(3):
        if not tense_issues:
            break
        target_words = 75 - (plan_correction_attempt * 10)
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. No "
                    "experiment has been executed and no result is available. Rewrite "
                    f"the paragraph in at most {target_words} words. This word limit is "
                    "mandatory: delete secondary rationale before returning. Write every "
                    "experimental action and artifact description in explicit future "
                    "tense using will. Never write present or past result-like forms such "
                    "as we report, we evaluate, Table compares, Figure shows, results "
                    "indicate, or we observed. Preserve the core proposed protocol, "
                    "literal xx values, citations, heading, and each configured figure "
                    "or table reference exactly once. Do not add a claimed, predicted, "
                    "or expected outcome."
                ),
                "input": (
                    "Detected plan-only paragraph defects: "
                    + "; ".join(tense_issues)
                    + "\n<paragraph_to_correct>"
                    + text
                    + "</paragraph_to_correct>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        if not text or not response_id:
            raise StudioError("Tense correction for experiments not performed did not return revised paragraphs.")
        tense_issues = unexecuted_experiment_tense_issues(section, text)
        remaining_reference_error = artifact_reference_error(text, bound_artifacts)
        if remaining_reference_error:
            raise StudioError("Still after tense correction of the experimental plan." + remaining_reference_error)
    if tense_issues:
        raise StudioError(
            "Experimental plan paragraph still non compliant after three reductions; candidates not accepted."
            + ", ".join(tense_issues)
        )
    added: list[str] = []
    if section_meta.get("render") == "abstract":
        text = remove_manuscript_citations(text)
    elif ONLINE_PROJECT_MODE:
        text = online_citation_markers(text)
    else:
        text = local_survey_citations(text)
        if needs_citation_resolution(text) or paragraph_requires_citation_audit(
            section, purpose, text
        ):
            response_id, text = resolve_citations_from_survey(
                model=model,
                previous_response_id=response_id,
                section=section,
                purpose=purpose,
                paragraph=text,
            )
    response_id, text = repair_empty_citation_placeholders(
        model=model,
        previous_response_id=response_id,
        section=section,
        purpose=purpose,
        paragraph=text,
    )
    third_use_keys = sorted(
        key
        for key in citation_keys(text)
        if section_citations_already_used.get(key, 0) >= 2
    )
    if third_use_keys:
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. The "
                    "listed citation keys have already appeared at least twice in this "
                    "section and may not be used again. Remove redundant attribution; "
                    "when an external claim still genuinely needs support, use a "
                    "different directly supporting key from verified_catalog. If no "
                    "alternative supports it, narrowly remove or rewrite that external "
                    "claim without changing this paper's own scientific content. Never "
                    "invent a key, citation, number, or result."
                ),
                "input": (
                    "<forbidden_third_use_keys>"
                    + json.dumps(third_use_keys, ensure_ascii=False)
                    + "</forbidden_third_use_keys>\n<verified_catalog>"
                    + writing_bibliography_catalog(purpose + "\n" + text)
                    + "</verified_catalog>\n<previous_paragraph>"
                    + text
                    + "</previous_paragraph>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        if not text or not response_id:
            raise StudioError("Citation Deduplication did not return the revised paragraph.")
        remaining_third_uses = sorted(set(third_use_keys) & citation_keys(text))
        if remaining_third_uses:
            raise StudioError(
                "The same section citation keys will still appear a third time, candidate not accepted:"
                + ", ".join(remaining_third_uses)
            )
    setup_issues = experimental_setup_issues(section, purpose, text)
    if setup_issues:
        setup_contract = experiment_setup_context()
        execution_protocol = metrics_bundle().get("evaluation_protocol", {})
        setup_names = [
            str(item.get("name") or "").strip()
            for item in [
                *setup_contract.get("datasets", []),
                *setup_contract.get("baselines", []),
            ]
            if str(item.get("name") or "").strip()
        ]
        setup_name_instruction = (
            "Name every declared dataset and baseline exactly as supplied in "
            "setup_contract: " + ", ".join(setup_names) + ". "
            if setup_names
            else "Do not invent datasets or baselines absent from the supplied contracts. "
        )
        required_models = [
            str(item).strip()
            for item in (
                execution_protocol.get("models", [])
                if isinstance(execution_protocol, dict)
                else []
            )
            if str(item).strip()
        ]
        model_instruction = (
            "Include each required model string verbatim: "
            + "; ".join(required_models)
            + ". "
            if required_models
            else "Do not invent a model name absent from execution_protocol. "
        )
        setup_citation_instruction = (
            "Place the exact literal marker \\cite{} after the first mention of "
            "each externally published dataset or baseline. Do not emit citation "
            "keys because the hosted workflow has no bibliography. "
            if ONLINE_PROJECT_MODE
            else "Cite each externally published setup item at first mention using "
            "only a directly supporting key in verified_catalog. "
        )
        setup_bibliography = (
            ""
            if ONLINE_PROJECT_MODE
            else writing_bibliography_catalog(
                " ".join(setup_names) + " experimental setup baselines datasets"
            )
        )
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only one compact LaTeX-ready Experimental Setup "
                    "paragraph of at most 140 words, leaving a safety margin below "
                    "the deterministic 170-word acceptance limit. "
                    + setup_name_instruction
                    + model_instruction
                    + "State only exact executed models, prompt counts, seeds, "
                    "decoding, datasets, and baselines present in setup_contract or "
                    "execution_protocol. "
                    + setup_citation_instruction
                    + "Do not discuss motivation, leakage, "
                    "pre-registration, future work, or result interpretation."
                ),
                "input": (
                    "Detected setup defects: "
                    + "; ".join(setup_issues)
                    + "\n<setup_contract>"
                    + json.dumps(setup_contract, ensure_ascii=False)
                    + "</setup_contract>\n<execution_protocol>"
                    + json.dumps(execution_protocol, ensure_ascii=False)
                    + "</execution_protocol>\n<verified_catalog>"
                    + setup_bibliography
                    + "</verified_catalog>\n<previous_paragraph>"
                    + text
                    + "</previous_paragraph>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        remaining_setup_issues = experimental_setup_issues(section, purpose, text)
        if not text or not response_id or remaining_setup_issues:
            raise StudioError(
                "Experimental Setup Still not meeting the fixed format:"
                + ", ".join(remaining_setup_issues or setup_issues)
            )
    status_issues = real_result_status_issues(text)
    for _status_attempt in range(2):
        if not status_issues:
            break
        fixture_context = metrics_bundle().get("fixture", {})
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. The "
                    "configured metrics are already executed real "
                    "measurements. Remove language that calls populated results pending, "
                    "pre-registered, planned, future, or awaiting execution. Report only "
                    "the supplied measured evidence in past/present tense; retain every "
                    "scope qualification supplied by the evidence and do not upgrade the "
                    "study's evidential status. Do not use 'confirmatory' unless the "
                    "evidence explicitly assigns that status. Preserve "
                    "citation keys, exact numbers, headings, "
                    "and required figure/table references. Do not explain the correction."
                ),
                "input": (
                    "Detected result-status contradictions: "
                    + "; ".join(status_issues)
                    + ".\n<executed_fixture>"
                    + json.dumps(fixture_context, ensure_ascii=False)
                    + "</executed_fixture>"
                    + ".\n\n<previous_paragraph>"
                    + text
                    + "</previous_paragraph>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        if not text or not response_id:
            raise StudioError("GPT No main text returned after updated result status.")
        status_issues = real_result_status_issues(text)
    if status_issues:
        raise StudioError(
            "Real results text still contains future execution status:" + ", ".join(status_issues)
        )
    execution_issues = execution_record_contradiction_issues(text)
    if execution_issues:
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. "
                    "Correct every contradiction with the supplied execution records. "
                    "If the integrity contract identifies a reference implementation as "
                    "an oracle-conformance control, describe its agreement only as a "
                    "conformance check, not as outperforming or improving on registered "
                    "mutants. Do not infer causal component necessity from a mutation test. "
                    "Keep mutant roles fixed: direct-key means under-propagation and "
                    "unauthorized actions; any-parent means over-propagation and erased "
                    "independent support. Do not assert an unmeasured cost ordering. "
                    "Never describe an exact zero value as nonzero. "
                    "If elapsed time is below the configured hard stop, do not claim "
                    "that the stop fired or that cells are missing. Reproduce recorded "
                    "environment fields rather than calling them absent. Preserve "
                    "supported measurements, citations, heading, and references."
                ),
                "input": (
                    "Detected execution-record contradictions: "
                    + "; ".join(execution_issues)
                    + f".\n<section_evidence>{evidence}</section_evidence>"
                    + f"\n<previous_paragraph>{text}</previous_paragraph>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        remaining_execution_issues = execution_record_contradiction_issues(text)
        if not text or not response_id or remaining_execution_issues:
            raise StudioError(
                "Main text still contradicts the execution log; candidate not accepted."
                + ", ".join(remaining_execution_issues or execution_issues)
            )
    appendix_issues = appendix_content_issues(section, text)
    if appendix_issues:
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready appendix "
                    "paragraph. Replace the roadmap with the actual promised "
                    "material using only section_evidence: give the proof or "
                    "equations, concrete configuration, populated result summary, "
                    "proxy definition, or recorded provenance. Preserve the exact "
                    "required heading. Do not say what the appendix will, supplies, "
                    "provides, reports, or documents. Never invent unavailable data."
                ),
                "input": (
                    "Detected appendix problems: "
                    + "; ".join(appendix_issues)
                    + f".\n<section_evidence>{evidence}</section_evidence>"
                    + f"\n<previous_paragraph>{text}</previous_paragraph>"
                ),
                "text": {"verbosity": "medium"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        remaining_appendix_issues = appendix_content_issues(section, text)
        if not text or not response_id or remaining_appendix_issues:
            raise StudioError(
                "The appendix remains only a content road map; candidate not accepted."
                + ", ".join(remaining_appendix_issues or appendix_issues)
            )
    completion_defects: list[str] = []
    for _completion_attempt in range(3):
        completion_defects = (
            manuscript_completion_placeholder_issues(text)
            + manuscript_markup_issues(text)
            + unsupported_internal_reference_issues(text)
            + unsupported_appendix_numeric_issues(section, text, evidence)
        )
        if not completion_defects:
            break
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. "
                    "Remove every planning placeholder, Markdown marker, model "
                    "commentary, model-emitted top-level section heading, and every "
                    "unsupported internal cross-reference. Use only evidence and labels supplied by the "
                    "project. If a promised detail is unavailable, omit it or state "
                    "the limitation as ordinary prose without brackets. Preserve "
                    "supported claims, exact measurements, citations, required "
                    "heading, and required configured artifact references. Never "
                    "invent replacement data or labels."
                ),
                "input": (
                    "Detected completion defects: "
                    + "; ".join(completion_defects)
                    + f".\n<previous_paragraph>{text}</previous_paragraph>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        if not text or not response_id:
            raise StudioError("Completion repair did not return a valid paragraph.")
    completion_defects = (
        manuscript_completion_placeholder_issues(text)
        + manuscript_markup_issues(text)
        + unsupported_internal_reference_issues(text)
        + unsupported_appendix_numeric_issues(section, text, evidence)
    )
    if completion_defects:
        raise StudioError(
            "The main text still contains planning placeholders or non existent internal references; candidates not accepted."
            + ", ".join(completion_defects)
        )
    no_result_issues = (
        unexecuted_result_claim_issues(text)
        if ONLINE_PROJECT_MODE and use_x_for_numbers
        else []
    )
    for no_result_attempt in range(2):
        if not no_result_issues:
            break
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready paragraph. This "
                    "hosted project has no experiment-result input and no experiment "
                    "has run. Remove every claimed observation, completed comparison, "
                    "result-supported conclusion, tested-condition statement, and past "
                    "tense study-completion claim. Preserve definitions and theoretical "
                    "claims. Describe empirical work only as a proposed future protocol "
                    "using will, and use literal xx for unavailable quantitative values. "
                    "Preserve citations, headings, and configured artifact references."
                ),
                "input": (
                    "Detected unsupported result claims: "
                    + "; ".join(no_result_issues)
                    + "\n<paragraph_to_correct>"
                    + text
                    + "</paragraph_to_correct>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        if not text or not response_id:
            raise StudioError("No revised paragraphs returned for the corrected experimental results status.")
        no_result_issues = unexecuted_result_claim_issues(text)
    if no_result_issues:
        raise StudioError(
            "The paragraph still claims there are unperformed experiments; candidate not accepted."
            + ", ".join(no_result_issues)
        )
    placeholder_issues = (
        numerical_placeholder_issues(text)
        if section_meta.get("render") == "abstract" and executed_result_rows
        else []
    )
    if placeholder_issues:
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete corrected LaTeX-ready abstract. The "
                    "experiment is complete and measured values were supplied in "
                    "section_evidence. Remove every bracketed numerical placeholder. "
                    "Use an exact supplied measurement when it directly supports the "
                    "claim; otherwise omit or qualitatively narrow that claim. Never "
                    "invent a value. Preserve the reduced-sample pilot qualification "
                    "and emit no citations."
                ),
                "input": (
                    "Forbidden placeholders: "
                    + ", ".join(placeholder_issues)
                    + f".\n<previous_abstract>{text}</previous_abstract>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = str(correction.get("id") or "")
        if not text or not response_id:
            raise StudioError("GPT No summary returned after removing numeric placeholders.")
        remaining_placeholders = numerical_placeholder_issues(text)
        if remaining_placeholders:
            raise StudioError(
                "The abstract still contains numerical placeholders; this candidate not accepted."
                + ", ".join(remaining_placeholders)
            )
    if section_meta.get("render") == "abstract":
        text = remove_manuscript_citations(text)
    elif ONLINE_PROJECT_MODE:
        response_id, text = resolve_citations_from_online_bibliography(
            model=model,
            previous_response_id=str(response_id or ""),
            section=section,
            purpose=purpose,
            paragraph=online_citation_markers(text),
            minimum_placeholders=minimum_online_citation_placeholders,
        )
    else:
        text = local_survey_citations(text)
    response_id, text = repair_empty_citation_placeholders(
        model=model,
        previous_response_id=str(response_id or ""),
        section=section,
        purpose=purpose,
        paragraph=text,
    )
    # Citation resolution is itself a provider-backed transformation and can
    # emit biblatex macros or fresh TeX punctuation. Send its final output
    # through the same canonical ingestion boundary as every other response.
    text = normalize_latex_ready_text(text)
    for managed_label in (
        str(section_meta.get("start_label") or ""),
        str(section_meta.get("end_label") or ""),
    ):
        if managed_label:
            text = re.sub(
                rf"\s*\\label\{{{re.escape(managed_label)}\}}\s*",
                " ",
                text,
            ).strip()
    text = enforce_required_heading(
        strip_redundant_section_name_leadin(text, str(section_meta["title"])),
        required_heading,
        required_heading_style,
    )
    _word_minimum, word_limit = paragraph_word_range(section)
    if isinstance(maximum_word_override, int) and maximum_word_override > 0:
        word_limit = maximum_word_override
    for _word_ceiling_attempt in range(2):
        word_count = manuscript_paragraph_word_count(text)
        if word_limit is None or word_count <= word_limit:
            break
        correction = post_openai(
            {
                "model": model,
                "store": True,
                "previous_response_id": response_id,
                "instructions": (
                    "Return only the complete compressed LaTeX-ready paragraph. "
                    f"It must contain no more than {word_limit} readable words. "
                    "Preserve every evidence-backed claim, numerical value, citation key, "
                    "required heading, and configured figure/table reference. Remove repetition, "
                    "generic framing, and expendable transitions. Do not add evidence or explain."
                ),
                "input": (
                    f"The paragraph contains {word_count} readable words.\n"
                    f"<paragraph_to_compress>{text}</paragraph_to_compress>"
                ),
                "text": {"verbosity": "low"},
            }
        )
        text = normalize_latex_ready_text(extract_output_text(correction))
        response_id = correction.get("id")
        if not text or not response_id:
            raise StudioError("Word-ceiling correction did not return a valid paragraph.")
        text = enforce_required_heading(
            strip_redundant_section_name_leadin(text, str(section_meta["title"])),
            required_heading,
            required_heading_style,
        )
    final_word_count = manuscript_paragraph_word_count(text)
    if word_limit is not None and final_word_count > word_limit:
        raise StudioError(
            f"The paragraph remains above its venue-aware {word_limit}-word ceiling "
            f"after two corrections (measured {final_word_count})."
        )
    # Citation resolution and heading enforcement both transform the candidate.
    # Validate and repair only after those final transformations so a hazard
    # introduced by a citation provider cannot bypass the generation gate and
    # later abort the transactional batch accept step.
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
                    "glyphs with LaTeX commands. If a displayed equation is too long "
                    "for one ACL column, preserve the mathematics but split it into "
                    "short lines with an aligned environment. "
                    + MANUSCRIPT_DASH_RULE
                    + " Do not explain the correction."
                ),
                "input": (
                    "The final paragraph contains these LaTeX hazards: "
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
            raise StudioError("GPT No LaTeX safe revised text was returned.")
        text = enforce_required_heading(
            strip_redundant_section_name_leadin(text, str(section_meta["title"])),
            required_heading,
            required_heading_style,
        )
        remaining_issues = latex_prose_issues(text)
        if remaining_issues:
            raise StudioError(
                "GPT After correction, still contains LaTeX risk characters."
                + "; ".join(remaining_issues)
            )
    final_reference_error = artifact_reference_error(text, bound_artifacts)
    if final_reference_error:
        raise StudioError(final_reference_error)
    security_issues = online_latex_security_issues(text)
    if security_issues:
        raise StudioError(
            "Online writing candidates include disabled LaTeX files or commands to execute."
            + ", ".join(security_issues)
        )
    if revision_requested and re.sub(r"\s+", " ", text).strip() == re.sub(
        r"\s+", " ", revision_source
    ).strip():
        raise StudioError(
            "GPT Two consecutive outputs identical to the current version of the body text; this submission did not save a pseudo new candidate."
            "Please retry or describe the modification scope more specifically."
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
        raise StudioError("Paper title cannot be empty.")
    if len(normalized) > 240:
        raise StudioError("The paper title cannot exceed 240 characters.")
    if "\\" in normalized or "{" in normalized or "}" in normalized:
        raise StudioError("Please enter the title as plain text, do not include LaTeX commands or curly braces.")
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
    escaped: list[str] = []
    for index, character in enumerate(title):
        already_escaped = index > 0 and title[index - 1] == "\\"
        escaped.append(
            character
            if already_escaped
            else replacements.get(character, character)
        )
    return "".join(escaped)


def latex_escape_caption(caption: str) -> str:
    """Escape prose specials while preserving already-valid inline math.

    Figure captions are editable LaTeX-ready text, unlike plain paper titles.
    Applying title escaping to the whole caption rewrites ``^`` inside
    ``\\(...\\)`` and corrupts scientific notation.  Keep balanced inline math
    verbatim and escape only the surrounding prose fragments.
    """
    parts = re.split(
        r"(\\\(.*?\\\)|\\\[.*?\\\]|(?<!\\)\$.*?(?<!\\)\$)",
        caption,
        flags=re.DOTALL,
    )
    return "".join(
        part if index % 2 else latex_escape_title(part)
        for index, part in enumerate(parts)
    )


def replace_manuscript_title_source(source: str, title: str) -> str:
    start, end = manuscript_title_span(source)
    return source[:start] + latex_escape_title(normalize_plain_title(title)) + source[end:]


def call_openai_for_title(
    *, model: str, prompt: str, current_title: str, previous_response_id: str | None
) -> tuple[str, str]:
    previous_response_id = reusable_response_id(previous_response_id)
    instructions = f"""You are an expert academic paper-title editor. Return exactly one
plain-text title: no quotation marks, Markdown, commentary, alternatives, or LaTeX commands.
Keep the title concise and venue-appropriate. Preserve the approved paper framing and claim
boundary. Do not introduce a result, causal claim, novelty claim, or empirical conclusion not
supported by the approved outline and working abstract. {MANUSCRIPT_DASH_RULE}"""
    stable_context = ""
    if not previous_response_id:
        stable_context = f"""<approved_outline>{approved_outline_context()}</approved_outline>
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


def full_draft_title_pending(state: dict[str, Any]) -> bool:
    """Use explicit title provenance instead of guessing from title wording."""
    return str(state.get("title_editor", {}).get("status") or "placeholder") == "placeholder"


def generate_full_draft_title(model: str) -> None:
    """Generate and commit the title after the complete manuscript is available."""
    state = load_state()
    if not full_draft_title_pending(state):
        return
    response_id, title = call_openai_for_title(
        model=model,
        prompt=(
            "Generate the final paper title from the completed manuscript. Name the "
            "evaluated phenomenon and protocol precisely, and do not claim a confirmed "
            "benefit when the reported comparison is inconclusive."
        ),
        current_title=manuscript_title_display(),
        previous_response_id=None,
    )
    result = save_manuscript_title(title)
    latest = load_state()
    editor = latest.setdefault("title_editor", {})
    editor.update(
        {
            "prompt": "",
            "candidate": "",
            "previous_response_id": response_id,
            "last_message": "The final title was generated from the completed manuscript and written to LaTeX.",
            "status": "generated",
        }
    )
    latest["compile"] = {
        "status": "ok",
        "message": result.message,
        "updated_at": int(time.time()),
    }
    save_state(latest)


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


def sync_manuscript_bibliography_command() -> None:
    """Keep main.tex's bibliography command in sync with whether the
    manuscript currently cites anything.

    Current online scaffolding always uses a conditional
    \\input{sections/bibliography}, toggled between an inert comment and
    \\bibliography{references} by accept/reset. A project scaffolded before
    that pattern existed (the demo project) hardcodes
    \\bibliography{references} directly in main.tex instead, so bibtex runs
    unconditionally -- with zero citations that produces a genuinely empty
    thebibliography environment and crashes compilation with "Something's
    wrong--perhaps a missing \\item." (reachable by any real researcher who
    resets, or starts fresh in, a project scaffolded this way). Toggling
    both shapes here, on every compile, keeps that invariant true
    regardless of which pattern a given project's main.tex uses and
    regardless of what triggered this compile.
    """
    placeholder = "% Paper Studio enables the bibliography after the first accepted citation."
    bibliography_style = str(PROJECT_METADATA.get("bibliography_style") or "").strip()
    enabled = (
        (f"\\bibliographystyle{{{bibliography_style}}}\n" if bibliography_style else "")
        + r"\bibliography{references}"
    )
    for target in (PAPER / "main.tex", PAPER / "sections" / "bibliography.tex"):
        if not target.exists():
            continue
        source = target.read_text(encoding="utf-8")
        if manuscript_citation_keys():
            updated = re.sub(
                r"(?m)^" + re.escape(placeholder) + r"\s*$",
                lambda _match: enabled,
                source,
            )
        else:
            updated = re.sub(
                r"(?m)^(?:\\bibliographystyle\{[^}]*\}\s*\n)?\\bibliography\{[^}]*\}\s*$",
                placeholder,
                source,
            )
        if updated != source:
            target.write_text(updated, encoding="utf-8")


def manuscript_bibliography_section_text() -> str:
    """Return the venue-correct conditional bibliography section."""
    if not manuscript_citation_keys():
        return "% Paper Studio enables the bibliography after the first accepted citation.\n"
    bibliography_style = str(PROJECT_METADATA.get("bibliography_style") or "").strip()
    style_line = f"\\bibliographystyle{{{bibliography_style}}}\n" if bibliography_style else ""
    return style_line + "\\bibliography{references}\n"


def discard_empty_bibliography_cache_when_citations_exist() -> None:
    """Remove a stale empty .bbl before citations are enabled again.

    After the last cited paragraph is cleared, BibTeX can leave behind a
    syntactically valid but empty ``main.bbl``.  If a later edit introduces the
    first citation, pdflatex reads that stale file before latexmk gets a chance
    to rerun BibTeX and fails at ``\\end{thebibliography}`` with "missing
    \\item".  Absence of the generated cache is safe: latexmk then performs its
    normal pdflatex -> bibtex -> pdflatex sequence from the current sources.
    """
    if not manuscript_citation_keys():
        return
    bbl_path = PAPER / "main.bbl"
    if not bbl_path.exists():
        return
    bbl_source = bbl_path.read_text(encoding="utf-8", errors="replace")
    if "\\begin{thebibliography}" in bbl_source and "\\bibitem" not in bbl_source:
        bbl_path.unlink()


BODY_END_LABEL = "paper:body-end"
BODY_END_POSITION_LABEL = "paper:body-end-position"
DEFAULT_MINIMUM_BODY_PAGE_FILL = 0.85


def ensure_body_end_label() -> None:
    """Keep a stable aux marker at the end of submission-counted content.

    Venue page limits normally exclude references.  A label immediately after
    the float barrier and before the bibliography gives us the last body page
    from LaTeX itself instead of guessing from PDF page count or word count.
    Existing projects are migrated on their next compile.
    """
    main = PAPER / "main.tex"
    if not main.is_file():
        return
    source = main.read_text(encoding="utf-8")
    marker = f"\\label{{{BODY_END_LABEL}}}"
    position_marker = f"\\zsavepos{{{BODY_END_POSITION_LABEL}}}"
    changed = False
    if "\\usepackage{zref-savepos}" not in source:
        documentclass = re.search(r"(?m)^\\documentclass(?:\[[^]]*\])?\{[^}]+\}\s*$", source)
        if documentclass:
            source = (
                source[: documentclass.end()]
                + "\n\\usepackage{zref-savepos}"
                + source[documentclass.end() :]
            )
            changed = True
    if marker in source and position_marker not in source:
        source = source.replace(marker, position_marker + "\n" + marker, 1)
        changed = True
    if marker in source:
        if not changed:
            return
        temporary = main.with_suffix(".tex.tmp")
        temporary.write_text(source, encoding="utf-8")
        os.replace(temporary, main)
        return
    bibliography = re.search(r"(?m)^\\input\{sections/bibliography\}\s*$", source)
    end_document = re.search(r"(?m)^\\end\{document\}\s*$", source)
    insertion = bibliography or end_document
    if not insertion:
        return
    updated = (
        source[: insertion.start()]
        + position_marker
        + "\n"
        + marker
        + "\n"
        + source[insertion.start() :]
    )
    temporary = main.with_suffix(".tex.tmp")
    temporary.write_text(updated, encoding="utf-8")
    os.replace(temporary, main)


def submission_content_page_limit() -> int | None:
    raw = PROJECT_METADATA.get("target", {}).get("submission_content_pages")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def compiled_content_page_count() -> int | None:
    """Read the body-ending page emitted by LaTeX; return None before compile."""
    aux = read_text(PAPER / "main.aux", 2_000_000)
    match = re.search(
        rf"\\newlabel\{{{re.escape(BODY_END_LABEL)}\}}\{{\{{[^}}]*\}}\{{([^}}]+)\}}",
        aux,
    )
    if not match:
        return None
    page = match.group(1).strip()
    return int(page) if page.isdigit() else None


def minimum_body_page_fill() -> float:
    raw = PROJECT_METADATA.get("target", {}).get("minimum_body_page_fill")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = DEFAULT_MINIMUM_BODY_PAGE_FILL
    return min(0.98, max(0.50, value))


def compiled_body_fill_fraction() -> float | None:
    """Measure how far body content reaches down its final text page.

    A page-number label alone treats a body ending near the top of the last
    allowed page as "full". ``zref-savepos`` records the physical body-end
    position after the float barrier. Geometry's logged top/bottom margins then
    let us normalize that position within the template's usable text area.
    """
    aux = read_text(PAPER / "main.aux", 2_000_000)
    position = re.search(
        rf"\\zref@newlabel\{{{re.escape(BODY_END_POSITION_LABEL)}\}}"
        r"\{[^\n]*?\\posy\{([0-9]+)\}",
        aux,
    )
    log = read_text(PAPER / "main.log", 2_000_000)
    geometry = re.search(
        r"\* v-part:\(T,H,B\)=\(([0-9.]+)pt,\s*([0-9.]+)pt,\s*([0-9.]+)pt\)",
        log,
    )
    paper_height = re.search(r"\* \\paperheight=([0-9.]+)pt", log)
    if not position or not geometry or not paper_height:
        return None
    y_points = int(position.group(1)) / 65536.0
    top_margin = float(geometry.group(1))
    bottom_margin = float(geometry.group(3))
    page_height = float(paper_height.group(1))
    text_top = page_height - top_margin
    usable_height = text_top - bottom_margin
    if usable_height <= 0:
        return None
    return min(1.0, max(0.0, (text_top - y_points) / usable_height))


def page_budget_status() -> dict[str, Any]:
    limit = submission_content_page_limit()
    content_pages = compiled_content_page_count()
    fill_fraction = compiled_body_fill_fraction()
    minimum_fill = minimum_body_page_fill()
    if limit is None:
        status = "not_configured"
    elif content_pages is None:
        status = "awaiting_compile"
    elif content_pages > limit:
        status = "over"
    elif content_pages < limit:
        status = "under"
    elif fill_fraction is not None and fill_fraction < minimum_fill:
        status = "under"
    else:
        status = "within"
    return {
        "limit": limit,
        "content_pages": content_pages,
        "remaining": (
            limit - content_pages
            if limit is not None and content_pages is not None
            else None
        ),
        "status": status,
        "excludes_references": True,
        "last_page_fill": (
            round(fill_fraction, 4) if fill_fraction is not None else None
        ),
        "minimum_last_page_fill": minimum_fill,
    }


def page_budget_worsened(before: int | None, after: int | None) -> bool:
    """Reject a new edit that crosses or further exceeds the body-page limit."""
    limit = submission_content_page_limit()
    if limit is None or after is None or after <= limit:
        return False
    return before is None or before <= limit or after > before


def page_budget_error(before: int | None, after: int | None) -> str:
    limit = submission_content_page_limit()
    return (
        "Submission body page budget exceeded; edit rolled back. "
        f"Body pages changed from {before if before is not None else 'unknown'} "
        f"to {after if after is not None else 'unknown'}, limit {limit}. "
        "References are excluded from this count. Shorten the current paragraph "
        "or move nonessential material to the appendix."
    )


def paragraph_word_limit(section: str) -> int | None:
    """Allocate the venue body budget before prose reaches LaTeX.

    A page-count-only gate reacts too late: once early paragraphs consume the
    available pages, shortening only the paragraph that crosses the boundary
    cannot leave room for the remaining sections.  Allocate the configured
    section share across its paragraphs and reserve space for each body float.
    """
    page_limit = submission_content_page_limit()
    section_meta = SECTION_MAP.get(section, {})
    section_spec = next(
        (item for item in SECTION_SPECS if str(item.get("id")) == section),
        {},
    )
    paragraphs = section_spec.get("paragraphs", [])
    try:
        share = float(section_meta.get("length_share"))
    except (TypeError, ValueError):
        return None
    if not page_limit or not paragraphs or not 0 < share <= 1:
        return None
    float_count = len(FIGURES) + len(TABLES)
    total_prose_words = max(900, page_limit * 425 - float_count * 75)
    allocated = round(total_prose_words * share / len(paragraphs))
    if section_meta.get("render") == "abstract":
        return max(100, min(130, allocated))
    if section == "experiments":
        # Setup/result paragraphs must retain dataset, metric, baseline, and
        # artifact contracts; a lower limit makes reproducibility impossible.
        return max(120, allocated)
    # Below roughly 70 words, providers tend to drop required evidence or
    # ignore the limit even after repair. Keep a feasible floor and let the
    # transactional page gate handle the rare layout-heavy project.
    return max(70, allocated)


def paragraph_word_range(section: str) -> tuple[int | None, int | None]:
    """Return a venue-aware evidence-bearing word range for one paragraph."""
    maximum = paragraph_word_limit(section)
    if maximum is None:
        return None, None
    section_meta = SECTION_MAP.get(section, {})
    if section_meta.get("render") == "abstract":
        minimum = max(90, math.ceil(maximum * 0.80))
    elif section == "experiments":
        minimum = max(95, math.ceil(maximum * 0.80))
    else:
        minimum = max(50, math.ceil(maximum * 0.75))
    return min(minimum, maximum), maximum


def paragraph_expansion_word_limit(section: str) -> int:
    """Upper bound used only after a complete PDF is measured as underfilled."""
    if SECTION_MAP.get(section, {}).get("render") == "abstract":
        return 140
    if section == "experiments":
        return 150
    return 120


def manuscript_paragraph_word_count(text: str) -> int:
    """Count readable manuscript words while ignoring LaTeX command names."""
    without_commands = re.sub(r"\\[A-Za-z@]+\*?", " ", text)
    return len(re.findall(r"\b[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?\b", without_commands))


def section_budget_guidance(section: str) -> str:
    """Return concise generation guidance derived from the approved page plan."""
    limit = submission_content_page_limit()
    raw_share = SECTION_MAP.get(section, {}).get("length_share")
    share: float | None = None
    try:
        if isinstance(raw_share, str) and raw_share.strip().endswith("%"):
            share = float(raw_share.strip()[:-1]) / 100.0
        elif raw_share not in (None, ""):
            share = float(raw_share)
            if share > 1:
                share /= 100.0
    except (TypeError, ValueError):
        share = None
    parts = []
    if limit is not None:
        parts.append(f"The submission body limit is {limit} pages, excluding references.")
    if limit is not None and share is not None and 0 < share <= 1:
        parts.append(
            f"The approved length share for this section is {share:.0%}, approximately "
            f"{limit * share:.1f} body pages."
        )
    elif share is not None and 0 < share <= 1:
        parts.append(f"The approved length share for this section is {share:.0%}.")
    paragraph_minimum, paragraph_limit = paragraph_word_range(section)
    if paragraph_limit is not None and paragraph_minimum is not None:
        parts.append(
            f"This paragraph must contain between {paragraph_minimum} and "
            f"{paragraph_limit} readable words."
        )
    parts.append(
        "Use concrete evidence-bearing detail to meet the range; never pad with generic prose."
    )
    return " ".join(parts)


def compile_paper() -> CompileResult:
    with COMPILE_LOCK:
        main = PAPER / "main.tex"
        if not main.exists():
            return CompileResult(False, "paper/main.tex does not exist yet.")
        ensure_body_end_label()
        sync_manuscript_bibliography_command()
        discard_empty_bibliography_cache_when_citations_exist()
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
        if (
            not (PAPER / "main.synctex.gz").exists()
            and ((PAPER / "main.aux").exists() or (PAPER / "main.bbl").exists())
        ):
            # -g forces latexmk to ignore file timestamps and rebuild
            # everything -- needed when a project directory was copied or
            # restored and its existing main.aux/main.bbl carry stale or
            # confusing mtimes relative to the real .tex sources. But on a
            # genuinely from-scratch compile (no aux/bbl at all yet), -g makes
            # latexmk run bibtex before any pdflatex pass has ever produced a
            # main.aux with \citation/\bibdata commands in it, so bibtex reads
            # an empty aux and fails outright ("I found no \citation commands").
            # A real project's very first compile hit exactly this. latexmk's
            # own default ordering (pdflatex, then bibtex, then pdflatex again)
            # already handles a from-scratch compile correctly without -g.
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


def full_draft_targets(
    state: dict[str, Any], section_filter: str | None = None
) -> list[tuple[str, str]]:
    """Return pending paragraphs in batch order, optionally for one section."""
    targets: list[tuple[str, str]] = []
    for section in draft_writing_order():
        if section_filter and section != section_filter:
            continue
        section_state = state.get("sections", {}).get(section, {})
        for paragraph in section_state.get("paragraphs", []):
            if not str(paragraph.get("accepted_text", "")).strip():
                targets.append((section, str(paragraph.get("id", ""))))
    return targets


def section_artifact_ids(state: dict[str, Any], section: str) -> list[str]:
    """Return configured figures and tables owned by one writing section."""
    bound: set[str] = set()
    for paragraph in state.get("sections", {}).get(section, {}).get("paragraphs", []):
        for artifact in paragraph.get("artifacts", []):
            artifact_id = (
                artifact
                if isinstance(artifact, str)
                else str(artifact.get("id") or "")
                if isinstance(artifact, dict)
                else ""
            )
            if artifact_id in FIGURES or artifact_id in TABLES:
                bound.add(artifact_id)
    return [
        artifact_id
        for artifact_id in [*FIGURE_ORDER, *TABLE_ORDER]
        if artifact_id in bound
    ]


def full_draft_running(state: dict[str, Any]) -> bool:
    return (state.get("full_draft_job") or {}).get("status") == "running"


def section_draft_running(state: dict[str, Any]) -> bool:
    return (state.get("section_draft_job") or {}).get("status") == "running"


def draft_batch_running(state: dict[str, Any]) -> bool:
    return full_draft_running(state) or section_draft_running(state)


def paragraph_by_id(
    state: dict[str, Any], section: str, paragraph_id: str
) -> tuple[dict[str, Any], int]:
    section_state = state.get("sections", {}).get(section)
    if not isinstance(section_state, dict):
        raise StudioError(f"Batch writing cannot find section:{section}")
    for index, paragraph in enumerate(section_state.get("paragraphs", [])):
        if paragraph.get("id") == paragraph_id:
            return paragraph, index
    raise StudioError(f"Batch writing cannot locate paragraph:{section}/{paragraph_id}")


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
        raise StudioError("Batch writing still contains unresolved items. [CITATION NEEDED].")
    validate_citations_for_accept(text, workflow="batch writing")
    prose_issues = latex_prose_issues(text)
    if prose_issues:
        raise StudioError("Batch writing contains LaTeX risky characters:" + "; ".join(prose_issues))
    appendix_issues = appendix_content_issues(section, text)
    if appendix_issues:
        raise StudioError("Batch writing appendix remains a roadmap:" + "; ".join(appendix_issues))
    execution_issues = execution_record_contradiction_issues(text)
    if execution_issues:
        raise StudioError("Conflicts between bulk writing and execution records." + "; ".join(execution_issues))
    setup_issues = experimental_setup_issues(
        section, str(paragraph.get("purpose") or ""), text
    )
    if setup_issues:
        raise StudioError("Batch writing experimental settings are incomplete:" + "; ".join(setup_issues))
    completion_issues = manuscript_completion_placeholder_issues(text)
    if completion_issues:
        raise StudioError("Bulk writing still contains planning placeholders." + "; ".join(completion_issues))
    markup_issues = manuscript_markup_issues(text)
    if markup_issues:
        raise StudioError("Batch writing still contains Markdown markup." + "; ".join(markup_issues))
    internal_reference_issues = unsupported_internal_reference_issues(text)
    if internal_reference_issues:
        raise StudioError(
            "Batch writing contains unconfigured internal references:" + "; ".join(internal_reference_issues)
        )
    appendix_numeric_issues = unsupported_appendix_numeric_issues(
        section,
        text,
        section_evidence(
            section, [str(item) for item in paragraph.get("artifacts", [])]
        ),
    )
    if appendix_numeric_issues:
        raise StudioError(
            "Batch writing appendix contains digits without evidence:" + "; ".join(appendix_numeric_issues)
        )
    security_issues = online_latex_security_issues(text)
    if security_issues:
        raise StudioError(
            "Batch writing includes LaTeX commands that disable online mode:" + ", ".join(security_issues)
        )

    target = PAPER / "sections" / SECTION_MAP[section]["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    previous = target.read_text(encoding="utf-8") if existed else ""
    bibliography_path = target.parent / "bibliography.tex"
    previous_bibliography = read_text(bibliography_path, 10000)
    previous_accepted_text = str(paragraph.get("accepted_text") or "")
    previous_candidate = paragraph.get("candidate")
    before_body_pages = compiled_content_page_count()
    paragraph["accepted_text"] = text
    paragraph["candidate"] = None
    auto_generate_bound_figure_captions(state, section, paragraph, text)
    section_source, accepted_section = render_section_source(
        section, section_state, state["figures"], state["tables"]
    )
    temporary = target.with_suffix(".tex.tmp")
    temporary.write_text(section_source, encoding="utf-8")
    os.replace(temporary, target)
    bibliography_text = manuscript_bibliography_section_text()
    bibliography_temporary = bibliography_path.with_suffix(".tex.tmp")
    bibliography_temporary.write_text(bibliography_text, encoding="utf-8")
    os.replace(bibliography_temporary, bibliography_path)
    compile_result = compile_paper()
    after_body_pages = compiled_content_page_count() if compile_result.ok else None
    budget_failed = compile_result.ok and page_budget_worsened(
        before_body_pages, after_body_pages
    )
    if not compile_result.ok or budget_failed:
        paragraph["accepted_text"] = previous_accepted_text
        paragraph["candidate"] = previous_candidate
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
        if budget_failed:
            raise StudioError(page_budget_error(before_body_pages, after_body_pages))
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


def repair_batch_latex_candidate(
    *,
    model: str,
    section: str,
    paragraph: dict[str, Any],
    text: str,
    compile_error: str,
) -> str:
    """Repair one candidate from the actual pdflatex diagnostic."""
    bound_artifacts = artifact_writing_context(paragraph.get("artifacts", []))
    required_references = [
        str(item.get("required_reference") or "") for item in bound_artifacts
    ]
    response = post_openai(
        {
            "model": model,
            "store": True,
            "instructions": (
                "Return only the complete corrected LaTeX-ready paragraph. The "
                "candidate failed pdflatex. Fix the syntax identified by the supplied "
                "compiler diagnostic while preserving every scientific claim, number, "
                "citation key, required heading, and configured artifact reference. "
                "Do not add or remove evidence, citations, equations, figures, tables, "
                "or prose content except where required to make the paragraph compile. "
                "Use balanced braces and place every mathematical expression inside "
                "valid LaTeX math delimiters. Do not explain the correction."
            ),
            "input": (
                f"<section>{section}</section>\n"
                f"<paragraph_id>{paragraph.get('id', '')}</paragraph_id>\n"
                f"<required_references>{json.dumps(required_references)}</required_references>\n"
                f"<pdflatex_diagnostic>{compile_error}</pdflatex_diagnostic>\n"
                f"<paragraph_to_repair>{text}</paragraph_to_repair>"
            ),
            "text": {"verbosity": "low"},
        }
    )
    repaired = normalize_latex_ready_text(extract_output_text(response))
    if not repaired or not response.get("id"):
        raise StudioError("LaTeX Automatic repair did not return valid paragraphs.")
    return repaired


def repair_batch_page_budget_candidate(
    *,
    model: str,
    section: str,
    paragraph: dict[str, Any],
    text: str,
    diagnostic: str,
) -> str:
    """Compress the current paragraph after a measured body-page overflow."""
    response = post_openai(
        {
            "model": model,
            "store": True,
            "instructions": (
                "Return only one complete LaTeX-ready replacement paragraph. "
                "Shorten it aggressively because the compiled manuscript crossed its "
                "submission body-page limit. Preserve every supported claim, numerical "
                "value, citation key, required heading, and figure/table reference. "
                "Remove repetition, generic framing, and nonessential transitions. Do "
                "not add evidence or explain the edit."
            ),
            "input": (
                f"<section>{section}</section>\n"
                f"<paragraph_id>{paragraph.get('id', '')}</paragraph_id>\n"
                f"<page_budget_diagnostic>{diagnostic}</page_budget_diagnostic>\n"
                f"<paragraph_to_compress>{text}</paragraph_to_compress>"
            ),
            "text": {"verbosity": "low"},
        }
    )
    repaired = normalize_latex_ready_text(extract_output_text(response))
    if not repaired or not response.get("id"):
        raise StudioError("Page-budget compression did not return a valid paragraph.")
    return repaired


def repair_underfilled_manuscript(
    model: str,
    state: dict[str, Any],
    *,
    job_key: str,
    token: str,
) -> dict[str, Any]:
    """Expand evidence-bearing paragraphs until measured PDF body fill passes."""
    attempted: set[tuple[str, str]] = set()
    priority = {
        section: index
        for index, section in enumerate(
            ("experiments", "discussion", "method", "introduction", "related_work", "conclusion", "limitations")
        )
    }
    for _iteration in range(12):
        budget = page_budget_status()
        if budget.get("status") != "under":
            return state
        candidates: list[tuple[int, int, str, dict[str, Any], int, int]] = []
        for section, section_state in state.get("sections", {}).items():
            if section not in priority:
                continue
            maximum = paragraph_expansion_word_limit(section)
            for paragraph in section_state.get("paragraphs", []):
                paragraph_id = str(paragraph.get("id") or "")
                key = (section, paragraph_id)
                text = str(paragraph.get("accepted_text") or "").strip()
                current = manuscript_paragraph_word_count(text)
                headroom = maximum - current
                if text and headroom >= 12 and key not in attempted:
                    candidates.append(
                        (priority[section], -headroom, section, paragraph, current, maximum)
                    )
        if not candidates:
            raise StudioError(
                "The manuscript remains physically underfilled after all evidence-bearing "
                "paragraphs reached their approved word ceilings; return to Experiment Plan "
                "and add substantive evidence rather than padding prose."
            )
        # Several paragraphs commonly share both section priority and word
        # headroom.  Comparing the raw tuples then falls through to the
        # paragraph dictionaries, which are not orderable in Python 3.  Keep
        # selection deterministic with the paragraph id as the final scalar
        # tie-breaker.
        _rank, _headroom, section, paragraph, current, maximum = min(
            candidates,
            key=lambda item: (
                item[0],
                item[1],
                item[2],
                str(item[3].get("id") or ""),
            ),
        )
        paragraph_id = str(paragraph.get("id") or "")
        attempted.add((section, paragraph_id))
        job = state.get(job_key) or {}
        if job.get("token") != token or job.get("status") != "running":
            return state
        job["progress_message"] = (
            f"Balancing body-page fill · {SECTION_MAP[section]['title']} · {paragraph_id} "
            f"({budget.get('last_page_fill')} → target {budget.get('minimum_last_page_fill')})"
        )
        state[job_key] = job
        save_state(state)
        artifact_ids = [str(item) for item in paragraph.get("artifacts", [])]
        try:
            response_id, revised, citations_added = call_openai(
                section=section,
                model=model,
                previous_response_id=None,
                purpose=str(paragraph.get("purpose") or ""),
                required_heading=paragraph.get("heading"),
                required_heading_style=paragraph.get("heading_style"),
                architecture=paragraph_architecture(paragraph),
                reference_context=paragraph_reference_context(section, paragraph),
                comment=(
                    f"The compiled body fills only {budget.get('last_page_fill')} of its final "
                    f"allowed page, below {budget.get('minimum_last_page_fill')}. Expand this "
                    f"paragraph from {current} toward {maximum} readable words using only concrete "
                    "details already supported by its purpose and section evidence. Do not add "
                    "generic filler, a new claim, experiment, number, citation, or artifact."
                ),
                current_text=str(paragraph.get("accepted_text") or ""),
                bibliography_update="",
                artifacts=artifact_ids,
                figure_states=json.loads(json.dumps(state.get("figures", {}))),
                include_section_context=True,
                maximum_word_override=maximum,
            )
        except StudioError:
            # ``call_openai`` applies the same claim/provenance validator before
            # returning a candidate.  Treat that early rejection exactly like
            # an acceptance-time rejection: preserve the manuscript and try a
            # different evidence-bearing paragraph.
            continue
        revised_count = manuscript_paragraph_word_count(revised)
        if revised_count < current + 8:
            continue
        paragraph["candidate"] = {
            "id": uuid.uuid4().hex,
            "text": revised,
            "purpose": paragraph.get("purpose"),
            "citations_added": citations_added,
            "created_at": int(time.time()),
        }
        try:
            accept_full_draft_paragraph(state, section, paragraph, revised)
        except StudioError:
            # Expansion is opportunistic.  Claim/provenance, LaTeX, and page
            # validators already roll the paragraph back transactionally.  A
            # rejected candidate must not abort the whole manuscript; retain
            # the accepted evidence and try the next eligible paragraph.
            continue
        section_state = state["sections"][section]
        section_state["previous_response_id"] = response_id
        section_state["bibliography_fingerprint"] = bibliography_fingerprint()
        state["model"] = model
        save_state(state)
    raise StudioError(
        "The manuscript remains physically underfilled after twelve evidence-grounded "
        "page-fill revisions; return to Experiment Plan and add substantive evidence."
    )


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


def draft_batch_worker(
    token: str,
    model: str,
    *,
    job_key: str,
    job_lock: threading.RLock,
    cancelled_jobs: set[str],
    section_filter: str | None,
) -> None:
    """Run a prose batch while keeping its product-specific job state isolated."""
    try:
        if not ONLINE_PROJECT_MODE:
            ensure_survey_bibliography()
        initial = load_state()
        initial_job = initial.get(job_key) or {}
        section_filter = str(section_filter or "").strip()
        artifact_ids = (
            [str(item) for item in initial_job.get("artifact_ids", [])]
            if section_filter
            else None
        )
        # This also resumes figures whose prose was completed by an earlier
        # Paper Studio version that stopped at a manual Prompt-approval gate.
        schedule_ready_mechanism_figures(artifact_ids)
        targets = full_draft_targets(initial, section_filter or None)
        for ordinal, (section, paragraph_id) in enumerate(targets, start=1):
            with job_lock:
                state = load_state()
                job = state.get(job_key) or {}
                if (
                    token in cancelled_jobs
                    or job.get("token") != token
                    or job.get("status") != "running"
                ):
                    return
                paragraph, paragraph_index = paragraph_by_id(state, section, paragraph_id)
                if str(paragraph.get("accepted_text", "")).strip():
                    job.update(completed=ordinal, progress=int(ordinal * 100 / max(1, len(targets))))
                    state[job_key] = job
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
                    not ONLINE_PROJECT_MODE
                    and previous_response_id
                    and section_state.get("bibliography_fingerprint")
                    != current_bib_fingerprint
                ):
                    bibliography_update = writing_bibliography_catalog(
                        paragraph["purpose"] + "\n" + section_evidence(section)
                    )
                figure_states = json.loads(json.dumps(state.get("figures", {})))
                job.update(
                    current_section=section,
                    current_paragraph=paragraph_id,
                    progress_message=f"Generating {SECTION_MAP[section]['title']} · {paragraph_id}",
                )
                state[job_key] = job
                save_state(state)

            response_id, text, citations_added = call_openai(
                section=section,
                model=model,
                previous_response_id=previous_response_id,
                purpose=paragraph["purpose"],
                required_heading=paragraph.get("heading"),
                required_heading_style=paragraph.get("heading_style"),
                architecture=paragraph_architecture(paragraph),
                reference_context=paragraph_reference_context(section, paragraph),
                comment="",
                current_text="",
                bibliography_update=bibliography_update,
                artifacts=[str(item) for item in paragraph.get("artifacts", [])],
                figure_states=figure_states,
                include_section_context=include_section_context,
                minimum_online_citation_placeholders=(
                    online_citation_placeholder_minimum(section, paragraph_index)
                    if ONLINE_PROJECT_MODE
                    else 0
                ),
            )

            with job_lock:
                state = load_state()
                job = state.get(job_key) or {}
                if (
                    token in cancelled_jobs
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
                        "comment": (
                            "[SECTION DRAFT]" if section_filter else "[FULL DRAFT]"
                        ),
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
            for latex_attempt in range(3):
                try:
                    accept_full_draft_paragraph(state, section, paragraph, text)
                    break
                except StudioError as exc:
                    diagnostic = str(exc)
                    latex_failure = diagnostic.startswith("LaTeX failed;")
                    budget_failure = diagnostic.startswith(
                        "Submission body page budget exceeded;"
                    )
                    if not (latex_failure or budget_failure) or latex_attempt == 2:
                        raise
                    text = (
                        repair_batch_latex_candidate(
                            model=model,
                            section=section,
                            paragraph=paragraph,
                            text=text,
                            compile_error=diagnostic,
                        )
                        if latex_failure
                        else repair_batch_page_budget_candidate(
                            model=model,
                            section=section,
                            paragraph=paragraph,
                            text=text,
                            diagnostic=diagnostic,
                        )
                    )
                    paragraph.setdefault("history", []).append(
                        {
                            "candidate_id": uuid.uuid4().hex,
                            "comment": (
                                "[LATEX REPAIR]"
                                if latex_failure
                                else "[PAGE BUDGET COMPRESSION]"
                            ),
                            "text": text,
                            "citations_added": citations_added,
                            "created_at": int(time.time()),
                        }
                    )
                    paragraph["history"] = paragraph["history"][-40:]

            with job_lock:
                latest = load_state()
                latest["sections"][section] = state["sections"][section]
                # Accepting a paragraph can atomically generate captions for its
                # bound figures.  Dropping this state made the UI and final LaTeX
                # fall back to temporary captions such as "F1" after every batch.
                latest["figures"] = state["figures"]
                latest["compile"] = state["compile"]
                latest["model"] = model
                job = latest.get(job_key) or {}
                if job.get("status") == "running" and job.get("token") == token:
                    job.update(
                        completed=ordinal,
                        progress=int(ordinal * 100 / max(1, len(targets))),
                        progress_message=f"Written and compiled. {SECTION_MAP[section]['title']} · {paragraph_id}",
                    )
                latest[job_key] = job
                save_state(latest)
                # Drawing starts at the semantic boundary: as soon as every
                # paragraph required by a mechanism figure has been accepted.
                schedule_ready_mechanism_figures(artifact_ids)
                if job.get("status") != "running" or job.get("token") != token:
                    return

        if not section_filter and full_draft_title_pending(load_state()):
            update_full_draft_job(
                token,
                progress_message="Generating the final paper title from the completed manuscript...",
            )
            generate_full_draft_title(model)

        with job_lock:
            state = load_state()
            job = state.get(job_key) or {}
            if job.get("token") == token and job.get("status") == "running":
                synchronize_paragraph_editors_from_manuscript(state)
                synchronize_artifact_workbenches_from_manuscript(
                    state,
                    build_table_previews=True,
                    artifact_ids=artifact_ids,
                )
                materialize_batch_artifacts(state, artifact_ids)
                pending_artifacts = pending_batch_artifacts(
                    state, artifact_ids
                )
                # Mechanism figures finish in an independent Codex worker. A
                # running artifact is pending work, not a manuscript defect.
                # Apply the final quality gate only after every bound artifact
                # has produced its real deliverables.
                if not pending_artifacts and not section_filter:
                    if page_budget_status().get("status") == "under":
                        state = repair_underfilled_manuscript(
                            model,
                            state,
                            job_key=job_key,
                            token=token,
                        )
                    quality_issues = completed_manuscript_issues(state)
                    if quality_issues:
                        raise StudioError(
                            "Deterministic quality check after full text generation failed."
                            + "; ".join(quality_issues)
                        )
                job.update(
                    status="artifacts_pending" if pending_artifacts else "completed",
                    token=None,
                    progress=100,
                    completed=job.get("total", len(targets)),
                    progress_message=(
                        (
                            f"{SECTION_MAP[section_filter]['title']} The main text has been written in LaTeX."
                            "Completing and confirming the binding of charts."
                            if section_filter
                            else "The body text has been fully written in LaTeX; please complete and confirm at the figure workbench."
                        )
                        + ", ".join(pending_artifacts)
                        if pending_artifacts
                        else (
                            (
                                f"{SECTION_MAP[section_filter]['title']} The main text has been written into LaTeX and PDF."
                                "The planned chart is retained as placeholder."
                                if section_filter
                                else "The full first draft has been written in LaTeX and PDF compilation completed; planned charts are kept as placeholders."
                            )
                            if ONLINE_PROJECT_MODE
                            else (
                                f"{SECTION_MAP[section_filter]['title']} The body text and bound charts have all been completed."
                                "Written into LaTeX and PDF."
                                if section_filter
                                else "The full first draft and all figures have been written into LaTeX and PDF compilation completed."
                            )
                        )
                    ),
                    pending_artifacts=pending_artifacts,
                    finished_at=int(time.time()),
                )
                state[job_key] = job
                save_state(state)
    except Exception as exc:
        with job_lock:
            state = load_state()
            job = state.get(job_key) or {}
            if job.get("token") == token and job.get("status") == "running":
                job.update(
                    status="failed",
                    token=None,
                    progress_message=(
                        f"Current section generation stops at the current paragraph.{exc}"
                        if section_filter
                        else f"Full text generation stops at the current paragraph:{exc}"
                    ),
                    finished_at=int(time.time()),
                )
                state[job_key] = job
                save_state(state)
    finally:
        with job_lock:
            cancelled_jobs.discard(token)


def full_draft_worker(token: str, model: str) -> None:
    draft_batch_worker(
        token,
        model,
        job_key="full_draft_job",
        job_lock=FULL_DRAFT_JOB_LOCK,
        cancelled_jobs=CANCELLED_FULL_DRAFT_JOBS,
        section_filter=None,
    )


def section_draft_worker(token: str, model: str, section: str) -> None:
    draft_batch_worker(
        token,
        model,
        job_key="section_draft_job",
        job_lock=SECTION_DRAFT_JOB_LOCK,
        cancelled_jobs=CANCELLED_SECTION_DRAFT_JOBS,
        section_filter=section,
    )


def start_full_draft_job(model: str) -> tuple[str, dict[str, Any]]:
    """Create the independent full-paper drafting job."""
    provider = active_llm_provider()
    setup = api_setup_for_provider(provider)
    if not setup["configured"]:
        raise StudioError(
            f"{setup['provider_label']} API Not configured. Please specify in{API_KEY_SETUP_LOCATION}run "
            f"{setup['setup_command']}, Then rerun {API_KEY_RESTART_COMMAND}."
        )
    if not outline_is_confirmed():
        raise StudioError("Outline Not confirmed yet; cannot generate the full text directly.")
    if not (PAPER / "main.tex").exists():
        raise StudioError("paper/main.tex Does not exist; please first create the paper scaffold.")
    model = model_for_provider(provider, model)
    if not model:
        raise StudioError("Model name cannot be empty.")
    with FULL_DRAFT_JOB_LOCK:
        state = load_state()
        if full_draft_running(state):
            raise StudioError("The full text draft task is already running.")
        if section_draft_running(state):
            raise StudioError("The current Section is generating; please wait for completion.")
        refresh_full_draft_artifact_status(state)
        if (state.get("full_draft_job") or {}).get("status") == "artifacts_pending":
            pending = (state.get("full_draft_job") or {}).get("pending_artifacts", [])
            actively_running = [
                artifact_id
                for artifact_id in pending
                if artifact_id in state.get("figures", {})
                and state["figures"][artifact_id].get("status") in FIGURE_RUNNING_STATUSES
            ]
            if actively_running:
                raise StudioError(
                    "The binding charts from the previous batch are still running:"
                    + ", ".join(actively_running)
                )
        targets = full_draft_targets(state)
        artifact_ids = None
        artifact_or_quality_work = bool(
            pending_batch_artifacts(state, artifact_ids)
            or completed_manuscript_issues(state)
            or full_draft_title_pending(state)
        )
        if not targets and not artifact_or_quality_work:
            raise StudioError("All paragraphs already written to LaTeX; no need to generate in bulk again.")
        token = uuid.uuid4().hex
        state["model"] = model
        state["full_draft_job"] = {
            "token": token,
            "status": "running",
            "server_instance": SERVER_INSTANCE_TOKEN,
            "server_pid": os.getpid(),
            "started_at": int(time.time()),
            "finished_at": None,
            "total": len(targets),
            "completed": 0,
            "progress": 0,
            "scope": "full",
            "section": "",
            "artifact_ids": [],
            "current_section": "",
            "current_paragraph": "",
            "progress_message": "Preparing the full draft…",
        }
        save_state(state)
    return token, state


def start_section_draft_job(model: str, section: str) -> tuple[str, dict[str, Any]]:
    """Create a Section task that never reads or writes full-draft job state."""
    provider = active_llm_provider()
    setup = api_setup_for_provider(provider)
    if not setup["configured"]:
        raise StudioError(
            f"{setup['provider_label']} API Not configured. Please specify in{API_KEY_SETUP_LOCATION}run "
            f"{setup['setup_command']}, Then rerun {API_KEY_RESTART_COMMAND}."
        )
    if not outline_is_confirmed():
        raise StudioError("Outline Not confirmed yet; cannot generate the current section.")
    if not (PAPER / "main.tex").exists():
        raise StudioError("paper/main.tex Does not exist; please first create the paper scaffold.")
    if section not in SECTION_MAP:
        raise StudioError("The current section does not exist.")
    if SECTION_MAP[section].get("writing_mode") == "plan_only":
        raise StudioError("Current Section only shows plan, cannot generate main text.")
    model = model_for_provider(provider, model)
    if not model:
        raise StudioError("Model name cannot be empty.")
    with SECTION_DRAFT_JOB_LOCK:
        state = load_state()
        if section_draft_running(state):
            raise StudioError("The current Section generation task is already running.")
        if full_draft_running(state):
            raise StudioError("The full text first draft is being generated; please wait for completion.")
        refresh_full_draft_artifact_status(state)
        active = state.get("section_draft_job") or {}
        if active.get("status") == "artifacts_pending":
            raise StudioError(
                "The binding charts of the previous Section are still in progress."
                + ", ".join(active.get("pending_artifacts", []))
            )
        targets = full_draft_targets(state, section)
        artifact_ids = section_artifact_ids(state, section)
        artifact_work = bool(
            pending_batch_artifacts(state, artifact_ids)
        )
        if not targets and not artifact_work:
            raise StudioError("Current Section main text and bound charts complete.")
        token = uuid.uuid4().hex
        state["model"] = model
        state["section_draft_job"] = {
            "token": token,
            "status": "running",
            "server_instance": SERVER_INSTANCE_TOKEN,
            "server_pid": os.getpid(),
            "started_at": int(time.time()),
            "finished_at": None,
            "total": len(targets),
            "completed": 0,
            "progress": 0,
            "section": section,
            "artifact_ids": artifact_ids,
            "current_paragraph": "",
            "progress_message": f"Preparing {SECTION_MAP[section]['title']} All content...",
        }
        save_state(state)
    return token, state


def run_direct_full_draft(model: str) -> None:
    """Generate all pending prose synchronously without opening the web UI."""
    token, state = start_full_draft_job(model)
    job = state["full_draft_job"]
    print(f"Direct full draft: 0 / {job['total']} paragraphs")
    # ``start_full_draft_job`` normalizes stale selections to the active
    # provider.  Always run with that canonical value; passing the caller's
    # pre-normalized model can send an OpenAI model name to DeepSeek (or the
    # reverse) after the job has already been accepted.
    full_draft_worker(token, str(state["model"]))
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
    """Read metadata only from a stable, fully compiled PDF revision."""
    with COMPILE_LOCK:
        return _paper_pdf_metadata_unlocked()


def _paper_pdf_metadata_unlocked() -> dict[str, Any]:
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
    with COMPILE_LOCK:
        pdf = PAPER / "main.pdf"
        metadata = _paper_pdf_metadata_unlocked()
        if not pdf.exists() or page < 1 or page > int(metadata["page_count"]):
            raise StudioError("PDF page does not exist.")
        converter = shutil_which("pdftocairo")
        if not converter:
            raise StudioError("Interactive PDF preview requires local pdftocairo.")
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
                (process.stderr or process.stdout).strip() or "Cannot render PDF page."
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
    raise StudioError("This PDF location has no corresponding LaTeX source content.")


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
        raise StudioError("This location belongs to the paper template; there is temporarily no corresponding paragraph or figure editor.")
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
        raise StudioError("This section does not yet have returnable body paragraphs.")
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
        raise StudioError("Compile the PDF first, then use double click positioning.")
    if not synctex_file.exists():
        compile_result = compile_paper()
        if not compile_result.ok or not synctex_file.exists():
            raise StudioError(
                "PDF Double click to locate missing index; automatic reconstruction failed.\n" + compile_result.message
            )
    if not synctex:
        raise StudioError("PDF Double click positioning requires local SyncTeX.")
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
        raise StudioError((process.stderr or process.stdout).strip() or "SyncTeX Failed to locate.")
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
            raise StudioError("Plot command timed out.") from exc
        output = (process.stdout + "\n" + process.stderr).strip()
        if process.returncode:
            if "Traceback (most recent call last)" in output:
                last_line = next(
                    (line.strip() for line in reversed(output.splitlines()) if line.strip()),
                    "Plot command execution failed.",
                )
                raise StudioError(f"External plotting tool execution failed:{last_line[-800:]}")
            raise StudioError(output[-1200:] or "Plot command execution failed.")
        return output

    with FIGURE_PROCESS_LOCK:
        if job_token in CANCELLED_FIGURE_JOBS:
            CANCELLED_FIGURE_JOBS.discard(job_token)
            raise StudioError("The figure-generation job has stopped.")
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
        raise StudioError("Plot command timed out.") from exc
    finally:
        with FIGURE_PROCESS_LOCK:
            if RUNNING_FIGURE_PROCESSES.get(job_token) is process:
                RUNNING_FIGURE_PROCESSES.pop(job_token, None)
            CANCELLED_FIGURE_JOBS.discard(job_token)
    output = (stdout + "\n" + stderr).strip()
    if process.returncode:
        if cancelled:
            raise StudioError("The figure-generation job has stopped.")
        if "Traceback (most recent call last)" in output:
            last_line = next(
                (line.strip() for line in reversed(output.splitlines()) if line.strip()),
                "Plot command execution failed.",
            )
            raise StudioError(f"External plotting tool execution failed:{last_line[-800:]}")
        raise StudioError(output[-1200:] or "Plot command execution failed.")
    return output


def mechanism_figure_type(figure_id: str) -> str:
    """Classify a non-data figure by rhetorical job, not by a global house style."""
    definition = FIGURES[figure_id]
    searchable = " ".join(
        [
            str(definition.get("title") or ""),
            str(definition.get("description") or ""),
            " ".join(str(item) for item in definition.get("dimensions", [])),
        ]
    ).casefold()
    if re.search(r"agent|tool|retriev|environment|memory|message|interaction", searchable):
        return "agent_interaction"
    if re.search(r"motivat|contrast|versus|vs\.?|null|problem|failure|counterexample", searchable):
        return "motivation_contrast"
    if re.search(
        r"architect|module|router|routing|layer stack|attention|encoder|decoder|"
        r"measurement|predictor|jacobian|pushforward|mechanism|hidden state",
        searchable,
    ):
        return "model_architecture"
    return "method_workflow"


def mechanism_figure_evidence(
    figure_id: str, state: dict[str, Any]
) -> list[dict[str, str]]:
    """Return only the accepted paragraphs explicitly required to draw this figure."""
    evidence: list[dict[str, str]] = []
    for section, paragraph_id in figure_generation_prerequisites(figure_id):
        paragraph, _index = paragraph_by_id(state, section, paragraph_id)
        accepted = str(paragraph.get("accepted_text") or "").strip()
        if not accepted:
            continue
        evidence.append(
            {
                "section": section,
                "paragraph_id": paragraph_id,
                "purpose": str(paragraph.get("purpose") or "").strip(),
                "accepted_text": accepted,
            }
        )
    return evidence


def mechanism_source(
    figure_id: str,
    state: dict[str, Any],
    current_prompt: str = "",
    prompt_instruction: str = "",
) -> str:
    definition = FIGURES[figure_id]
    spec = initial_mechanism_spec(figure_id)
    wide = str(definition.get("width", "")).startswith("two-column")
    figure_type = mechanism_figure_type(figure_id)
    type_profile = ACL_FIGURE_TYPE_PROFILES[figure_type]
    configured_description = str(definition.get("description") or "").strip()
    if configured_description.casefold() == figure_id.casefold():
        configured_description = str(definition["title"])
    configured_caption = str(definition.get("caption") or "").strip()
    if configured_caption.casefold() == figure_id.casefold():
        configured_caption = str(definition["title"])
    format_contract = {
        "placement": "two-column figure*" if wide else "single-column figure",
        "canvas_in": spec["canvas_in"],
        "image_size": spec["image_size"],
        "composition": (
            "page-width ACL-style method schematic with 2–4 aligned regions; use flat modules, "
            "tokens, paths, matrices, or small semantic glyphs only when they encode the method; "
            "keep all critical content in the central horizontal safe band because the "
            "wide native-shape composition will be fitted to the paper aspect ratio"
            if wide
            else f"compact single-column {type_profile['role'].lower()} with two or three "
            "aligned visual groups; follow the type-specific object grammar and reading order; "
            "pure white background and readable at one-column width"
        ),
        "final_output": (
            "Design a restrained final-quality ACL paper figure whose modules, tokens, paths, "
            "glyphs, and labels can be faithfully reconstructed as editable PowerPoint elements; "
            "avoid both sparse placeholder flowcharts and decorative poster illustration."
        ),
    }
    pieces = [
        f"Figure task: {definition['title']}",
        f"Required content: {configured_description}",
        f"Rhetorical type: {figure_type}",
        "<acl_figure_type_profile>",
        json.dumps(type_profile, ensure_ascii=False, indent=2),
        "</acl_figure_type_profile>",
        "<paper_figure_format>",
        json.dumps(format_contract, ensure_ascii=False, indent=2),
        "</paper_figure_format>",
        "<figure_content_contract>",
        json.dumps(
            {
                "title": definition["title"],
                "caption_intent": configured_caption,
                "required_dimensions": definition.get("visible_dimensions")
                or definition.get("dimensions", []),
                "prohibited_empirical_inputs": definition.get("result_keys", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "</figure_content_contract>",
        "<cross_figure_distinction>",
        json.dumps(
            [
                {
                    "figure_id": other_id,
                    "title": FIGURES[other_id]["title"],
                    "rhetorical_type": mechanism_figure_type(other_id),
                    "visual_signature_to_avoid_copying": ACL_FIGURE_TYPE_PROFILES[
                        mechanism_figure_type(other_id)
                    ]["visual_signature"],
                }
                for other_id in FIGURE_ORDER
                if other_id != figure_id and FIGURES[other_id].get("kind") == "mechanism"
            ],
            ensure_ascii=False,
            indent=2,
        ),
        "</cross_figure_distinction>",
    ]
    pieces.extend(
        [
            "<bound_paragraph_evidence>",
            json.dumps(
                mechanism_figure_evidence(figure_id, state),
                ensure_ascii=False,
                indent=2,
            ),
            "</bound_paragraph_evidence>",
        ]
    )
    pieces.extend(
        [
            "<mechanism_figure_semantic_contract>",
            (
                "This is a mechanism or motivation schematic, not a results figure. "
                "Do not request bar charts, curves, score rankings, higher/lower result "
                "marks, numeric outcomes, or visual claims of empirical superiority. "
                "Those belong in data figures even when the prose later reports them."
            ),
            (
                "The image must be self-explanatory at its configured paper width: show "
                "an explicit input, the paper's actual intervention/mechanism, and its "
                "non-empirical output or decision. Every arrow must name a real source "
                "and target; every branch must differ by structure or iconography as well "
                "as color. Remove any glyph that has no one-clause manuscript-grounded meaning."
            ),
            (
                "Do not put captions, explanatory sentences, or prose callouts inside the "
                "figure. Use short noun labels only (maximum four words each). For a "
                "single-column figure, request at most eight text labels and two core visual "
                "groups; for a two-column figure, at most sixteen labels and four groups."
            ),
            "</mechanism_figure_semantic_contract>",
        ]
    )
    if current_prompt.strip():
        pieces.extend(
            [
                "Current drawing prompt:",
                current_prompt.strip(),
                "Researcher instruction for regenerating the drawing prompt:",
                prompt_instruction.strip(),
                (
                    "Regenerate the complete drawing prompt. Preserve fidelity to the "
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
        "no_text": False,
        "labels": [],
        "semantic_contract_version": 2,
        "required_semantic_roles": ["input", "operation", "output"],
    }


def mechanism_shape_spec(figure_id: str) -> dict[str, Any]:
    definition = FIGURES[figure_id]
    shape_spec_value = str(definition.get("shape_spec", "")).strip()
    if shape_spec_value:
        shape_spec_path = _project_path(
            ROOT, shape_spec_value, f"figures.{figure_id}.shape_spec"
        )
        if not shape_spec_path.exists():
            raise StudioError(f"Mechanism diagram shape file does not exist.{shape_spec_value}")
        try:
            configured_spec = json.loads(shape_spec_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StudioError(f"Mechanism diagram shape file is invalid:{shape_spec_value}: {exc}") from exc
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
    prompt = read_text(mechanism_spec_path(figure_id), 200000)
    return {
        "prompt_spec_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "composer": "codex-native-shapes-v1",
    }


def validate_mechanism_shape_spec(
    figure_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Reject silent placeholder rebuilds before they become final paper figures."""
    if not isinstance(raw, dict) or not isinstance(raw.get("shapes"), list):
        raise StudioError("Editable shape spec Missing shapes array.")
    shapes = raw["shapes"]
    unknown = {
        item.get("kind") if isinstance(item, dict) else type(item).__name__
        for item in shapes
        if not isinstance(item, dict) or item.get("kind") not in MECHANISM_SHAPE_KINDS
    }
    if unknown:
        raise StudioError("Editable shape spec Contains unknown elements:" + ", ".join(map(str, unknown)))
    if len(shapes) < 12:
        raise StudioError(
            "The mechanism diagram reconstruction results in only a few elements, suspected placeholders; at least 12 editable elements are required."
        )
    modules = sum(
        item["kind"] in {"rounded_rect", "rect", "oval", "hexagon", "right_arrow"}
        for item in shapes
    )
    connectors = sum(item["kind"] in {"arrow", "line"} for item in shapes)
    if modules < 4 or connectors < 2:
        raise StudioError("The mechanism diagram must include at least 4 graphical modules and 2 editable connections.")
    canvas = initial_mechanism_spec(figure_id)["canvas_in"]
    single_column = float(canvas[0]) < 5
    text_shapes = [item for item in shapes if str(item.get("text", "")).strip()]
    if raw.get("no_text") is True:
        raise StudioError(
            "Editable mechanism figures cannot set no_text=true; the final figure "
            "must retain print-readable semantic labels."
        )
    try:
        semantic_contract_version = int(raw.get("semantic_contract_version") or 0)
    except (TypeError, ValueError) as exc:
        raise StudioError(
            "Editable mechanism figure semantic_contract_version must be an integer."
        ) from exc
    if semantic_contract_version >= 2:
        if len(text_shapes) < 3:
            raise StudioError(
                "The editable mechanism figure must contain at least three labels "
                "covering input, operation, and output."
            )
        allowed_roles = {"input", "operation", "output", "annotation"}
        observed_roles = set()
        for item in text_shapes:
            role = str(item.get("semantic_role") or "").strip()
            if role not in allowed_roles:
                raise StudioError(
                    "Every text-bearing mechanism shape must declare semantic_role "
                    "as input, operation, output, or annotation."
                )
            observed_roles.add(role)
        required_roles = {
            str(item).strip()
            for item in raw.get(
                "required_semantic_roles", ["input", "operation", "output"]
            )
            if str(item).strip()
        }
        missing_roles = required_roles - observed_roles
        if missing_roles:
            raise StudioError(
                "The editable mechanism figure is missing semantic roles: "
                + ", ".join(sorted(missing_roles))
            )
        observed_labels = {str(item.get("text") or "").strip() for item in text_shapes}
        required_labels = {
            str(item).strip()
            for item in raw.get("required_labels", [])
            if str(item).strip()
        }
        missing_labels = required_labels - observed_labels
        if missing_labels:
            raise StudioError(
                "The editable mechanism figure is missing required labels: "
                + ", ".join(sorted(missing_labels))
            )
    # Repeated token cells, expert tiles, state bars, and connector segments are
    # normal in ACL mechanism figures. They are individually editable objects
    # but do not create the same reading burden as labels. Keep a strict text
    # cap while allowing the compact repeated glyph grammars seen in CAA,
    # DeepSeekMoE, and conditional retrieval diagrams.
    max_shapes = 64 if single_column else 100
    max_text_shapes = 14 if single_column else 28
    if len(shapes) > max_shapes or len(text_shapes) > max_text_shapes:
        raise StudioError(
            "Mechanism diagram information density is too high:"
            f"current {len(shapes)} an element/{len(text_shapes)} A text element,"
            f"This layout can have at most {max_shapes}/{max_text_shapes}."
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
                raise StudioError(f"Mechanism diagram No. {index} of an element {field} Must be between 0 and 1.")
        if item["kind"] not in {"arrow", "line"} and (
            float(item["w"]) <= 0 or float(item["h"]) <= 0
        ):
            raise StudioError(f"Mechanism diagram No. {index} An element's width and height must be greater than 0.")
        if item["kind"] not in {"arrow", "line"} and (
            float(item["x"]) + float(item["w"]) > 1
            or float(item["y"]) + float(item["h"]) > 1
        ):
            raise StudioError(
                f"Mechanism diagram element {index} extends beyond the canvas; "
                "both x+w and y+h must be at most 1."
            )
        text = str(item.get("text", "")).strip()
        if text:
            if (
                item["kind"] in {"rounded_rect", "rect"}
                and float(item["w"]) >= 0.22
                and float(item["h"]) >= 0.25
            ):
                raise StudioError(
                    f"Mechanism diagram element {index} is a large visual container "
                    "with centered text. Use an empty container plus a separate "
                    "header textbox so internal glyphs cannot cover its label."
                )
            font_size = float(item.get("font_size", 8))
            if font_size < 7:
                raise StudioError(f"Mechanism diagram No. {index} Several text elements are smaller than 7pt and unreadable.")
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
                    f"Mechanism diagram No. {index} Text box capacity is insufficient; expected to require "
                    f"{required_height:.1f}pt Height, actual only. {height_pt:.1f}pt."
                )
    textboxes = [
        (index, item)
        for index, item in enumerate(shapes, start=1)
        if item.get("kind") == "textbox" and str(item.get("text", "")).strip()
    ]
    modules_with_boxes = [
        (index, item)
        for index, item in enumerate(shapes, start=1)
        if item.get("kind") not in {"textbox", "arrow", "line"}
    ]
    for text_index, textbox in textboxes:
        tx1, ty1 = float(textbox["x"]), float(textbox["y"])
        tx2 = tx1 + float(textbox["w"])
        ty2 = ty1 + float(textbox["h"])
        for module_index, module in modules_with_boxes:
            mx1, my1 = float(module["x"]), float(module["y"])
            mx2 = mx1 + float(module["w"])
            my2 = my1 + float(module["h"])
            overlaps = tx1 < mx2 and tx2 > mx1 and ty1 < my2 and ty2 > my1
            if not overlaps:
                continue
            container_owns_header = (
                float(module["w"]) >= 0.22
                and float(module["h"]) >= 0.25
                and mx1 <= tx1
                and tx2 <= mx2
                and my1 <= ty1
                and ty2 <= my1 + float(module["h"]) * 0.28
            )
            module_owns_label = (
                not str(module.get("text") or "").strip()
                and str(module.get("semantic_role") or "")
                and str(module.get("semantic_role") or "")
                == str(textbox.get("semantic_role") or "")
                and mx1 <= tx1
                and tx2 <= mx2
                and my1 <= ty1
                and ty2 <= my2
                and float(textbox["w"]) * float(textbox["h"])
                <= float(module["w"]) * float(module["h"]) * 0.65
            )
            if not (container_owns_header or module_owns_label):
                raise StudioError(
                    f"Mechanism diagram textbox {text_index} overlaps graphical "
                    f"module {module_index}; move the label into clear whitespace."
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
    """Have the local code agent author a fully editable native-shape figure."""
    codex = shutil_which("codex")
    if not codex:
        raise StudioError("Local codex CLI not found; cannot generate an editable mechanism diagram.")
    paths = figure_paths(figure_id)
    definition = FIGURES[figure_id]
    canvas = initial_mechanism_spec(figure_id)["canvas_in"]
    draw_spec = read_text(paths["spec"], 200000)
    prompt = f"""You are Paper Studio's local scientific-figure composition agent.
Create the figure directly as editable native PowerPoint shapes from the manuscript-backed
drawing brief below. Return exactly one JSON object: no Markdown, no explanation, and do not
modify repository files.

Figure number:{figure_id}
Title:{definition['title']}
Mechanism requirements:{definition['description']}
Target canvas (inches):{json.dumps(canvas)}
This round Prompt/spec for drawing:
{draw_spec}

Strict schema:
{{"semantic_contract_version":2, "required_semantic_roles":["input","operation","output"], "canvas_in": {json.dumps(canvas)}, "shapes": [
  {{"kind":"rounded_rect|rect|oval|hexagon|right_arrow", "x":0to 1, "y":0to 1, "w":0to 1, "h":0to 1, "fill":"RRGGBB", "line":"RRGGBB", "line_w":1, "text":"Concise editable label", "semantic_role":"input|operation|output|annotation", "font_size":8, "bold":false, "font_color":"RRGGBB", "align":"left|center|right"}},
  {{"kind":"textbox", "x":0to 1, "y":0to 1, "w":0to 1, "h":0to 1, "text":"tag", "semantic_role":"input|operation|output|annotation", "font_size":8, "bold":false, "font_color":"RRGGBB", "align":"left|center|right"}},
  {{"kind":"arrow|line", "x1":0to 1, "y1":0to 1, "x2":0to 1, "y2":0to 1, "color":"RRGGBB", "weight":1}}
]}}

Hard constraints:
1. Directly design visual hierarchy major modules icon semantics and flow based on the paper mechanism and drawing prompt.
   Must not simply stuff the title and description into one or two text boxes.
2. At least 12 independent editable elements, including at least 4 graphic modules and 2 connecting lines; complex method diagrams should be richer.
   Single column canvas supports up to 64 elements, 14 containing text, and up to two core visual groups; double column supports up to 100/28.
3. All elements must lie within a 0 to 1 canvas, not overlap, text concise and correctly spelled; do not copy garbled text from sketches.
   Font size must not be smaller than 7pt; each text must fit entirely within its own box; labels inside the box may be up to 4 words; explanatory sentence should be removed.
   Leave sufficient height for text boxes based on actual inch canvas size; prefer expanding the box or removing text rather than relying on overflow clipping.
   Large containers must have empty text and a separate header textbox in a reserved header band; no icon, node, bar, or connector may cross that header band.
4. Use a flat research illustration style: white background, solid colors, no shadows, no gradients, no 3D. The graphics and connections illustrate the mechanism.
   Not a flowchart consisting of large blocks of text.
5. Be faithful to the mechanism requirements and the Prompt, and do not add result numbers, attack details, or claims not supported by the paper.
6. May not include raster background image elements; ultimately each object must be individually editable in PowerPoint.
7. The final JSON must retain semantic_contract_version=2. Every text-bearing shape must declare semantic_role.
   At least one visible label must cover each required role: input, operation, and output.
"""
    environment = local_agent_environment()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"agent-mechanism-{figure_id.lower()}-", dir=STATE_DIR
    ) as temporary_name:
        output = Path(temporary_name) / "last_message.txt"
        retry_feedback = ""
        last_error: StudioError | None = None
        for attempt in range(3):
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
            attempt_prompt = prompt + retry_feedback
            try:
                process = subprocess.run(
                    command,
                    input=attempt_prompt,
                    capture_output=True,
                    text=True,
                    timeout=MECHANISM_AGENT_TIMEOUT_SECONDS,
                    env=environment,
                )
            except subprocess.TimeoutExpired as exc:
                raise StudioError("Local Agent rebuild of the editable mechanism diagram timed out.") from exc
            if process.returncode or not output.exists():
                diagnostic = (process.stdout + "\n" + process.stderr).strip()
                raise StudioError(
                    "Local Agent failed to rebuild the editable mechanism diagram.\n"
                    + (diagnostic[-2400:] or "codex exec Shape spec not returned.")
                )
            source = output.read_text(encoding="utf-8", errors="replace").strip()
            fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", source, re.DOTALL)
            if fenced:
                source = fenced.group(1)
            else:
                start, end = source.find("{"), source.rfind("}")
                if start < 0 or end <= start:
                    last_error = StudioError("Local Agent did not return a shape spec JSON.")
                    retry_feedback = (
                        "\n\nYour previous response was not one JSON object. Return only "
                        "a complete corrected JSON object matching the schema."
                    )
                    continue
                source = source[start : end + 1]
            try:
                raw = json.loads(source)
            except json.JSONDecodeError as exc:
                last_error = StudioError(
                    f"The shape spec returned by the Local Agent cannot be parsed.{exc}"
                )
                retry_feedback = (
                    "\n\nYour previous JSON was invalid: " + str(exc)
                    + ". Return only a complete corrected JSON object."
                )
                continue
            raw = normalize_mechanism_text_boxes(figure_id, raw)
            raw["semantic_contract_version"] = 2
            raw["required_semantic_roles"] = ["input", "operation", "output"]
            raw["source_provenance"] = provenance
            try:
                return validate_mechanism_shape_spec(figure_id, raw)
            except StudioError as exc:
                last_error = exc
                retry_feedback = (
                    "\n\nThe validator rejected your previous shape spec: "
                    + str(exc)
                    + " Correct the geometry while preserving the scientific semantics. "
                    "Return the entire corrected JSON object only."
                )
        raise last_error or StudioError(
            "Local Agent did not return a valid editable mechanism shape spec after three attempts."
        )


def generate_mechanism_prompt(
    figure_id: str,
    state: dict[str, Any],
    prompt_instruction: str = "",
    current_prompt: str = "",
) -> tuple[str, str]:
    setup = api_setup_for_provider(str(state.get("llm_provider") or DEFAULT_PROVIDER))
    if not setup["configured"]:
        raise StudioError(f"{setup['provider_label']} API Not configured, unable to generate drawing Prompt.")
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
    # An explicit empty current prompt means "design afresh". Reusing an old
    # response in that case silently drops the new paragraph evidence and type
    # profile because the API receives only a compact revision turn.
    previous_response_id = (
        reusable_response_id(figure_state.get("previous_response_id"))
        if current_prompt.strip()
        else None
    )
    api_input = source
    if previous_response_id:
        format_match = re.search(
            r"<paper_figure_format>.*?</paper_figure_format>", source, re.DOTALL
        )
        format_contract = format_match.group(0) if format_match else ""
        type_match = re.search(
            r"<acl_figure_type_profile>.*?</acl_figure_type_profile>",
            source,
            re.DOTALL,
        )
        type_contract = type_match.group(0) if type_match else ""
        api_input = f"""{type_contract}
{format_contract}
<current_image_prompt>{current_prompt.strip()}</current_image_prompt>
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
    prompt = mechanism_prompt_with_contract_footer(
        figure_id, extract_output_text(response)
    )
    if not response_id:
        raise StudioError("GPT No continuation Figure conversation response id returned.")
    if not prompt:
        raise StudioError("GPT No usable drawing Prompt returned.")
    issues = mechanism_prompt_contract_issues(figure_id, prompt)
    if issues:
        repair_payload = {
            "model": str(state.get("model") or DEFAULT_MODEL),
            "store": True,
            "instructions": FIGURE_PROMPT_INSTRUCTIONS,
            "previous_response_id": response_id,
            "input": (
                "Rewrite the complete image-generation prompt. The previous answer "
                "violated the mandatory mechanism-figure contract in these ways: "
                + "; ".join(issues)
                + ". Remove the violations instead of merely saying not to include them. "
                "Return only the clean final prompt, with no analysis tags or commentary."
            ),
        }
        repaired = post_openai(repair_payload)
        response_id = str(repaired.get("id", "")).strip()
        prompt = mechanism_prompt_with_contract_footer(
            figure_id, extract_output_text(repaired)
        )
        remaining = mechanism_prompt_contract_issues(figure_id, prompt)
        if not response_id or not prompt or remaining:
            raise StudioError(
                "GPT Mechanism Diagram Prompt did not pass the semantic contract." + "; ".join(remaining or issues)
            )
    return response_id, prompt


def mechanism_prompt_with_contract_footer(figure_id: str, prompt: str) -> str:
    """Make the final image-facing instruction win over verbose model prose."""
    wide = str(FIGURES[figure_id].get("width", "")).startswith("two-column")
    limit = "sixteen" if wide else "eight"
    registry = {
        str(item.get("id", "")): str(item.get("latex", "")).strip()
        for item in metrics_bundle().get("symbol_registry", [])
        if isinstance(item, dict)
    }
    required_symbols = [
        registry[str(symbol_id)]
        for symbol_id in FIGURES[figure_id].get("symbol_ids", [])
        if registry.get(str(symbol_id))
    ]
    symbol_requirement = (
        " Preserve these registered scientific symbols exactly as visible labels: "
        + "; ".join(required_symbols)
        + "."
        if required_symbols
        else ""
    )
    footer = (
        "Mandatory final rendering constraints override every contradictory earlier "
        "instruction. Use no more than "
        f"{limit} text labels total, each at most four words; omit any earlier label "
        "request that exceeds this limit. Put no caption, explanatory sentence, "
        "empirical chart, score ranking, or decorative unexplained glyph inside the figure."
        + symbol_requirement
    )
    return prompt.strip() + "\n\n" + footer


def mechanism_prompt_contract_issues(figure_id: str, prompt: str) -> list[str]:
    """Mechanically reject common prompt failures that create unreadable figures."""
    normalized = re.sub(r"\s+", " ", prompt).strip().lower()
    issues: list[str] = []
    if re.search(r"</?analysis\b", normalized):
        issues.append("contains analysis markup")
    if re.search(
        r"caption\s+(?:fragment|line)|with\s+(?:an?\s+)?inline\s+caption|"
        r"(?:include|add|use|place)\s+(?:an?\s+)?(?:inline\s+)?caption",
        normalized,
    ):
        issues.append("requests explanatory captions inside the figure")
    if re.search(
        r"(?:draw|show|include|add|use|request)\s+(?:an?\s+)?bar\s+charts?|"
        r"bars?\s+(?:appear|are|should be).*?higher|"
        r"(?:show|convey|encode|depict)\s+(?:the\s+)?performance\s+gap|"
        r"(?:show|include|encode|depict)\s+(?:an?\s+)?(?:empirical|score)\s+ranking",
        normalized,
    ):
        issues.append("encodes empirical results in a mechanism figure")
    wide = str(FIGURES[figure_id].get("width", "")).startswith("two-column")
    label_limit = r"(?:sixteen|16)" if wide else r"(?:eight|8)"
    if not re.search(
        rf"(?:at\s+most|no\s+more\s+than|maximum(?:\s+of)?|limit(?:ed)?\s+to)\s+"
        rf"{label_limit}\s+(?:text\s+)?labels?",
        normalized,
    ):
        issues.append(
            "does not explicitly enforce the configured text-label limit"
        )
    registry = {
        str(item.get("id", "")): str(item.get("latex", ""))
        for item in metrics_bundle().get("symbol_registry", [])
        if isinstance(item, dict)
    }
    for symbol_id in FIGURES[figure_id].get("symbol_ids", []):
        latex = registry.get(str(symbol_id), "")
        if not latex:
            issues.append(f"references unknown registered symbol {symbol_id}")
        elif latex not in prompt:
            issues.append(f"does not preserve registered symbol {symbol_id} as {latex}")
    return issues


def draw_mechanism_draft(
    figure_id: str, prompt: str, *, job_token: str | None = None
) -> None:
    """Compose the candidate directly as native editable shapes with Codex."""
    prompt = prompt.strip()
    if not prompt:
        raise StudioError("Generate and confirm the drawing Prompt first.")
    paths = figure_paths(figure_id)
    FIGURE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    # deliverable_stem may intentionally group artifacts below paper/fig/
    # (for example typo_margin/F1_motivation).  The CLI receives the final
    # nested filename and does not create its parent itself.
    paths["pptx"].parent.mkdir(parents=True, exist_ok=True)
    paths["pdf"].parent.mkdir(parents=True, exist_ok=True)
    spec = initial_mechanism_spec(figure_id)
    if paths["spec"].exists():
        spec.update(json.loads(paths["spec"].read_text(encoding="utf-8")))
    spec["draw_prompt"] = prompt
    spec["no_text"] = False
    spec["semantic_contract_version"] = 2
    spec["required_semantic_roles"] = ["input", "operation", "output"]
    paths["spec"].write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    provenance = mechanism_shape_provenance(figure_id)
    shape_spec = create_mechanism_shape_spec_with_local_agent(
        figure_id, provenance
    )
    paths["shapes"].write_text(
        json.dumps(shape_spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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
    message = str(error).strip() or "Image task failed."
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
            raise StudioError("There are currently no Codex drawing tasks running.")
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
                    "This Codex drawing task has been stopped; the current Prompt and the previous version of the candidate have both been retained."
                    if has_previous_draft
                    else "This Codex drawing task has been stopped; the current Prompt has been retained."
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
            progress_message="Organizing the section text, outline, and figure tasks…",
        )
        state = load_state()
        update_figure_job(
            figure_id,
            job_token,
            progress=45,
            progress_message=(
                "GPT Rewriting the drawing prompt according to your instructions."
                if current_prompt
                else "GPT Converting the main text mechanism into a drawing prompt."
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
            progress_message="Drawing Prompt has been generated, awaiting your confirmation.",
            last_message="Please review or modify the drawing Prompt; Codex drawing will only be invoked after confirmation.",
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
            progress_message="Prompt Confirmed; preparing Codex native graphics task…",
        )
        update_figure_job(
            figure_id,
            job_token,
            progress=35,
            progress_message="Codex Designing and archiving native editable graphics…",
        )
        draw_mechanism_draft(figure_id, prompt, job_token=job_token)
        update_figure_job(
            figure_id,
            job_token,
            status="agent_generating",
            progress=55,
            progress_message="Native graphics complete; generating the paper PPTX and PDF.",
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
            progress_message="Codex Original graphics, PPTX, and PDF candidate have all been generated.",
            last_message=(
                message
                + " Please review the final candidate; if needed modify the Prompt and redraw; once satisfied, confirm to insert into the body."
            ),
            job_token=None,
        )
    except Exception as exc:  # pragma: no cover - external process boundary
        fail_figure_job(figure_id, job_token, exc)
    finally:
        with FIGURE_PROCESS_LOCK:
            CANCELLED_FIGURE_JOBS.discard(job_token)


def finalize_automatic_mechanism_figure(figure_id: str) -> None:
    """Insert an automatically built mechanism figure when prose writes are idle."""
    resume_page_fill: tuple[str, str] | None = None
    with AUTOMATIC_MECHANISM_FINALIZE_LOCK:
        with STATE_LOCK:
            state = load_state()
            figure_state = state["figures"][figure_id]
            if figure_state.get("status") != "built":
                return
            # The full-draft worker owns section files while accepting prose.
            # Its final materialization pass inserts figures that finish early.
            if draft_batch_running(state):
                return
            paths = figure_paths(figure_id)
            if not paths["pdf"].is_file() or not paths["pptx"].is_file():
                return
            ensure_figure_caption_before_approval(state, figure_id)
            binding = first_artifact_binding(figure_id)
            if not binding:
                raise StudioError(f"{figure_id} Not yet bound to the paragraph that first cites it.")
            section, paragraph_id = binding
            figure_state.update(
                status="approved",
                approved_at=int(time.time()),
                placement_after=figure_state.get("placement_after") or paragraph_id,
                progress=100,
                progress_message="Automatically generate and insert into the paper after the corresponding paragraph is completed.",
                last_message="The mechanism diagram has been automatically generated, inserted, and is awaiting PDF compilation.",
            )
            section_source, accepted = render_section_source(
                section,
                state["sections"][section],
                state["figures"],
                state["tables"],
            )
            target = PAPER / "sections" / SECTION_MAP[section]["file"]
            temporary = target.with_suffix(".tex.tmp")
            temporary.write_text(section_source, encoding="utf-8")
            os.replace(temporary, target)
            state["sections"][section]["accepted_text"] = accepted
            compile_result = compile_paper()
            if not compile_result.ok:
                figure_state.update(
                    status="built",
                    approved_at=None,
                    last_message="The mechanism diagram has been generated, but LaTeX compilation after automatic insertion failed:"
                    + compile_result.message,
                )
                save_state(state)
                return
            state["compile"] = {
                "status": "ok",
                "message": compile_result.message,
                "updated_at": int(time.time()),
            }
            pending = pending_batch_artifacts(state)
            full_job = state.get("full_draft_job") or {}
            if (
                not pending
                and full_job.get("status") == "artifacts_pending"
                and page_budget_status().get("status") == "under"
            ):
                token = uuid.uuid4().hex
                model = str(state.get("model") or DEFAULT_MODEL)
                full_job.update(
                    token=token,
                    status="running",
                    server_instance=SERVER_INSTANCE_TOKEN,
                    server_pid=os.getpid(),
                    started_at=int(time.time()),
                    finished_at=None,
                    total=0,
                    completed=0,
                    progress=100,
                    current_section="",
                    current_paragraph="",
                    pending_artifacts=[],
                    progress_message="Balancing evidence-bearing prose to the measured body-page target…",
                )
                state["full_draft_job"] = full_job
                resume_page_fill = (token, model)
            else:
                refresh_full_draft_artifact_status(state)
            save_state(state)
        if resume_page_fill:
            token, model = resume_page_fill
            threading.Thread(
                target=full_draft_worker,
                args=(token, model),
                daemon=True,
                name=f"page-fill-{token[:8]}",
            ).start()


def automatic_mechanism_figure_worker(figure_id: str, job_token: str) -> None:
    """Generate Prompt, draft, editable figure, and final PDF without a UI pause."""
    try:
        existing_state = load_state()
        existing_prompt = str(
            existing_state["figures"][figure_id].get("draw_prompt") or ""
        ).strip()
        if existing_prompt and completed_mechanism_draft_matches_prompt(
            figure_id, existing_prompt
        ):
            update_figure_job(
                figure_id,
                job_token,
                status="agent_generating",
                progress=45,
                progress_message="Reuse the native shape corresponding to the current Prompt to continue generating editable mechanism diagrams…",
            )
            message = build_mechanism_figure(figure_id, job_token=job_token)
            updated = update_figure_job(
                figure_id,
                job_token,
                status="built",
                revision=int(load_state()["figures"][figure_id].get("revision", 0)) + 1,
                approved_at=None,
                progress=100,
                progress_message="Mechanism diagram, editable PPTX and paper PDF have been automatically generated.",
                last_message=message,
                job_token=None,
            )
            if updated is not None:
                finalize_automatic_mechanism_figure(figure_id)
            return
        update_figure_job(
            figure_id,
            job_token,
            progress=15,
            progress_message="Corresponding paragraph completed; automatically generating drawing Prompt…",
        )
        state = load_state()
        response_id, prompt = generate_mechanism_prompt(figure_id, state)
        update_figure_job(
            figure_id,
            job_token,
            status="image_generating",
            previous_response_id=response_id,
            draw_prompt=prompt,
            prompt_approved_at=int(time.time()),
            progress=35,
            progress_message="Drawing Prompt automatically confirmed; generating a mechanism diagram sketch.",
        )
        draw_mechanism_draft(figure_id, prompt, job_token=job_token)
        update_figure_job(
            figure_id,
            job_token,
            status="agent_generating",
            progress=60,
            progress_message="Sketch complete; rebuilding editable PPTX and paper PDF.",
        )
        message = build_mechanism_figure(figure_id, job_token=job_token)
        updated = update_figure_job(
            figure_id,
            job_token,
            status="built",
            revision=int(load_state()["figures"][figure_id].get("revision", 0)) + 1,
            approved_at=None,
            progress=100,
            progress_message="Mechanism diagram, editable PPTX and paper PDF have been automatically generated.",
            last_message=message,
            job_token=None,
        )
        if updated is not None:
            finalize_automatic_mechanism_figure(figure_id)
    except Exception as exc:  # pragma: no cover - external process boundary
        fail_figure_job(figure_id, job_token, exc)
    finally:
        with FIGURE_PROCESS_LOCK:
            CANCELLED_FIGURE_JOBS.discard(job_token)


def schedule_ready_mechanism_figures(
    artifact_ids: list[str] | None = None,
) -> list[str]:
    """Start each ready, unfinished mechanism figure exactly once."""
    if ONLINE_PROJECT_MODE:
        # Hosted projects intentionally export labelled placeholders for mechanism
        # figures. Starting the local image/PPTX worker here can only fail because
        # those controls and credentials are deliberately unavailable, leaving every
        # placeholder with a misleading red ``failed`` state after a successful draft.
        return []
    scheduled: list[tuple[str, str]] = []
    allowed = set(artifact_ids) if artifact_ids is not None else None
    with STATE_LOCK:
        state = load_state()
        for figure_id in FIGURE_ORDER:
            if allowed is not None and figure_id not in allowed:
                continue
            definition = FIGURES[figure_id]
            if definition.get("kind") != "mechanism":
                continue
            figure_state = state["figures"][figure_id]
            if figure_state.get("status") in {
                *FIGURE_RUNNING_STATUSES,
                "built",
                "approved",
            }:
                continue
            ready, _reason = figure_generation_gate(figure_id, state)
            if not ready:
                continue
            token = uuid.uuid4().hex
            figure_state.update(
                status="prompt_generating",
                progress=5,
                progress_message="The corresponding paragraph is complete, and the automatic mechanism diagram task is starting.",
                last_message="",
                approved_at=None,
            )
            begin_figure_job(figure_state, token)
            scheduled.append((figure_id, token))
        if scheduled:
            save_state(state)
    for figure_id, token in scheduled:
        threading.Thread(
            target=automatic_mechanism_figure_worker,
            args=(figure_id, token),
            daemon=True,
            name=f"automatic-figure-{figure_id.lower()}-{token[:8]}",
        ).start()
    return [figure_id for figure_id, _token in scheduled]


def completed_mechanism_draft_matches_job(
    figure_id: str, figure_state: dict[str, Any]
) -> bool:
    """Recognize native shapes written just before a state-save race or crash."""
    if FIGURES[figure_id]["kind"] != "mechanism":
        return False
    paths = figure_paths(figure_id)
    spec_path = mechanism_spec_path(figure_id)
    if not paths["shapes"].exists() or not spec_path.exists():
        return False
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        shapes = json.loads(paths["shapes"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        str(spec.get("draw_prompt") or "").strip()
        == str(figure_state.get("draw_prompt", "")).strip()
        and shapes.get("source_provenance") == mechanism_shape_provenance(figure_id)
    )


def completed_mechanism_draft_matches_prompt(figure_id: str, prompt: str) -> bool:
    """Return true only when the current native shapes came from this prompt."""
    paths = figure_paths(figure_id)
    spec_path = mechanism_spec_path(figure_id)
    if not paths["shapes"].exists() or not spec_path.exists():
        return False
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        shapes = json.loads(paths["shapes"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        str(spec.get("draw_prompt") or "").strip() == prompt.strip()
        and shapes.get("source_provenance") == mechanism_shape_provenance(figure_id)
    )


def completed_mechanism_deliverables_match_current_draft(figure_id: str) -> bool:
    """Verify that PDF/PPTX and shapes were built from the current image draft."""
    paths = figure_paths(figure_id)
    required = [paths["shapes"], paths["pptx"], paths["pdf"]]
    if not all(path.is_file() for path in required):
        return False
    try:
        shape_spec = json.loads(paths["shapes"].read_text(encoding="utf-8"))
        current_provenance = mechanism_shape_provenance(figure_id)
    except (OSError, json.JSONDecodeError, StudioError):
        return False
    if shape_spec.get("source_provenance") != current_provenance:
        return False
    shape_time = paths["shapes"].stat().st_mtime_ns
    return all(path.stat().st_mtime_ns >= shape_time for path in (paths["pptx"], paths["pdf"]))


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
                        "progress_message": "Native-shape sketch completed.",
                        "last_message": "The sketch has been generated and archived; restored from the interrupted state record.",
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
                        "last_message": "Server restart interrupted the previous image task; please reinitiate.",
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
                    "last_message": "Server restart interrupted the previous table task; please reinitiate.",
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
        raise StudioError("The fully editable mechanism diagram deliverable is incomplete.")
    try:
        with zipfile.ZipFile(pptx) as package:
            media = [name for name in package.namelist() if name.startswith("ppt/media/")]
            if media:
                raise StudioError("PPTX Still contains bitmap media, not meeting the requirement that every component be editable.")
            slide_xml = package.read("ppt/slides/slide1.xml").decode(
                "utf-8", errors="replace"
            )
            native_objects = slide_xml.count("<p:sp>") + slide_xml.count("<p:cxnSp>")
            expected = len(shape_spec.get("shapes", []))
            if native_objects < expected or native_objects < 12:
                raise StudioError(
                    "PPTX Insufficient native objects:"
                    f"Expected at least {max(expected, 12)} Units, actual {native_objects} one."
                )
    except zipfile.BadZipFile as exc:
        raise StudioError("Mechanism diagram PPTX file is invalid.") from exc
    if pdf.stat().st_size < 1000:
        raise StudioError("Fully editable mechanism diagram PDF is invalid.")


def build_mechanism_figure(
    figure_id: str, *, job_token: str | None = None
) -> str:
    paths = figure_paths(figure_id)
    FIGURE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    paths["pptx"].parent.mkdir(parents=True, exist_ok=True)
    paths["pdf"].parent.mkdir(parents=True, exist_ok=True)
    if job_token:
        update_figure_job(
            figure_id,
            job_token,
            progress=35,
            progress_message="Local Agent is designing independent modules, arrows and text…",
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
            progress_message="Shape reconstruction complete; generating full native object PPTX…",
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
            progress_message="PPTX Generated; exporting the paper PDF from the same set of native shapes…",
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
        f"Codex Directly generated. {len(shape_spec['shapes'])} A standalone PowerPoint native object."
        "PPTX No background bitmap; each module, arrow and text can be edited independently."
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
            progress_message="Preparing GPT sketches and paper mechanism information, then reconstruct all editable objects.",
        )
        message = build_mechanism_figure(figure_id, job_token=job_token)
        update_figure_job(
            figure_id,
            job_token,
            status="built",
            revision=int(load_state()["figures"][figure_id].get("revision", 0)) + 1,
            approved_at=None,
            progress=100,
            progress_message="Fully editable PPTX and isomorphic PDF candidate have been generated.",
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
        raise StudioError("Local Agent did not return drawing code.")
    try:
        compile(source, "<local-agent-data-figure>", "exec")
    except SyntaxError as exc:
        raise StudioError(f"The drawing code returned by the local Agent cannot be parsed.{exc}") from exc
    required_fragments = ("matplotlib", "--metrics", "--pdf", "--png")
    missing = [item for item in required_fragments if item not in source]
    if missing:
        raise StudioError(
            "Local Agent returned drawing code lacks required interfaces." + ", ".join(missing)
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
        "Cannot find a local Python installation with both matplotlib and numpy."
        "Please set PAPER_STUDIO_PLOT_PYTHON."
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
        raise StudioError("The local Codex CLI was not found; cannot generate experimental result figures.")
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
        raise StudioError("This data figure has no defined independent subfigure.")
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
    prompt = f"""You are the local Paper Studio drawing agent. Please produce the paper experiment results figure below.
Write an independent repeatable Python program. Return only the complete Python source code, do not explain.
Do not use Markdown fences and do not modify repository files.

Figure number:{figure_id}({panel_id})
Paper figure:{definition['title']}
Subfigure title:{panel_definition['title']}
Uses:{presentation_goal}
Layout: independent atomic subplots; do not add at this stage. (a)/(b) Superscripts, and do not concatenate with other subfigures.

Hard constraints:
1. --metrics References a top level JSON object containing traceable_results; this object is as below
   <traceable_results> The shown dotted result key maps to existing results. Only values already available may be plotted.
   Must not create, interpolate, or infer experimental results.
2. The command line must accept three parameters --metrics --pdf --png and save the same figure separately as
   Vector PDF and webpage PNG; use the Agg backend of matplotlib.
3. This is a standalone subfigure, width 3.32 inches, laid out clearly in a paper style on a white background; the small font must remain legible.
4. Content target:{presentation_goal}
5. If JSON is missing required fields, throw a clear error and must not substitute default numbers.
6. Only use Python standard library, numpy and matplotlib. During execution no network access and no model calls.
7. If data is labeled synthetic, include a prominent SYNTHETIC FIXTURE marker in the figure.
8. All titles, legends, watermarks, axes ticks, labels, and annotations must stay within the canvas and not overlap; in single-column preview,
   Do not allow truncation. Before saving use tight or constrained layout and reserve margins for the watermark.
9. Do not place long narrative at the bottom; compress findings into short phrases readable in the figure, or do not show.
10. Only use Artist and Text parameters officially supported by matplotlib; do not include CSS/PPT properties (for example
    tracking, letter-spacing)Passed to matplotlib.
11. Single sequence diagram should not display redundant legends; sequence meaning is written into the title axis labels or Caption to avoid legend overlap.
    Data points, numeric labels, or titles. Multi-series legends must also avoid the data region.

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
            raise StudioError("The local Agent timed out while generating the experiment result graph code.") from exc
        if process.returncode:
            diagnostic = (process.stdout + "\n" + process.stderr).strip()
            raise StudioError(
                "Local Agent failed to generate the experiment result figure.\n"
                + (diagnostic[-2400:] or "codex exec returned a non-zero status.")
            )
        if not output.exists():
            raise StudioError("Local Agent did not write drawing code.")
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
        raise StudioError("This data figure has no independent subfigures.")
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
        raise StudioError("Local Agent drawing program did not generate PDF and PNG simultaneously.")
    return (
        f"{figure_id}({panel_id}) PDF candidate has been generated separately."
    )


def default_data_figure_layout_prompt(figure_id: str) -> str:
    panel_ids = [item["id"] for item in FIGURES[figure_id].get("panels", [])]
    if len(panel_ids) == 1:
        return (
            f"Subfigure {panel_ids[0]} Place into a single column, crop the four margins, and do not add corner labels."
            "Output editable PPTX and vector PDF with the same layout."
        )
    labels = "/".join(f"({panel_id})" for panel_id in panel_ids)
    return (
        f"press {', '.join(panel_ids)} The order is laid out horizontally into a single column, trimming surrounding whitespace."
        f"No spacing between subplots; add sequentially at the top left corner. {labels}, Superscript font 8 pt;"
        "Output editable PPTX and vector PDF with the same layout."
    )


def generate_data_figure_agent_worker(
    figure_id: str, panel_id: str, job_token: str, instruction: str = ""
) -> None:
    try:
        update_figure_job(
            figure_id,
            job_token,
            progress=20,
            progress_message="Launching local Codex agent and organizing traceable experimental results.",
        )
        update_data_panel_job(
            figure_id,
            panel_id,
            job_token,
            progress=20,
            progress_message="Organizing the traceable experimental results for this subfigure…",
        )
        update_figure_job(
            figure_id,
            job_token,
            progress=45,
            progress_message="Local Agent is generating the experiment results PDF candidate…",
        )
        update_data_panel_job(
            figure_id,
            panel_id,
            job_token,
            progress=45,
            progress_message="Local Agent is generating the PDF candidate for this subfigure…",
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
            "progress_message": "PDF candidate Generated.",
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
                progress_message="Generating final PPTX and vector PDF without corner marks.",
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
                    progress_message="Single figure PDF generated; final file packaging failed.",
                    last_message=f"{message}\nFinal file packaging failed:{composition_error}",
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
                progress_message="The final single-figure PDF candidate has been generated.",
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
                "All independent subplots generated; please check and then click Synthesize Figure."
                if all_panels_built
                else f"Local Agent has generated independent subfigures. {figure_id}({panel_id})."
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
                "progress_message": "Generation failed.",
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
                "vertical layout",
                "vertical",
                "top-bottom arrangement",
                "vertical placement",
                "vertical stacking",
                "vertical",
                "stack",
            )
        )
        else "horizontal"
    )
    labels = not any(
        token in normalized
        for token in (
            "no badge",
            "do not use subscripts",
            "no superscripts",
            "no label",
            "without label",
        )
    )
    width = (
        "two-column"
        if any(
            token in normalized
            for token in ("two-column", "two columns", "across columns", "full width")
        )
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
            raise StudioError("Local Agent did not return layout JSON.")
        source = source[start : end + 1]
    try:
        result = json.loads(source)
    except json.JSONDecodeError as exc:
        raise StudioError(f"Layout JSON returned by the local Agent cannot be parsed:{exc}") from exc
    if not isinstance(result, dict):
        raise StudioError("The local Agent layout plan must be a JSON object.")
    return result


def validate_data_figure_layout(
    raw: dict[str, Any], panel_ids: list[str]
) -> dict[str, Any]:
    orientation = raw.get("orientation")
    width = raw.get("width")
    order = raw.get("panel_order")
    if orientation not in {"horizontal", "vertical"}:
        raise StudioError("Agent Layout orientation must be horizontal or vertical.")
    if width not in {"single-column", "two-column"}:
        raise StudioError("Agent The layout width must be single-column or two-column.")
    if not isinstance(order, list) or sorted(order) != sorted(panel_ids):
        raise StudioError("Agent The layout must include all generated panels and only those panels.")
    gap = raw.get("gap_pt", 0)
    crop = raw.get("crop_margins_pt", 0)
    if not isinstance(gap, (int, float)) or not 0 <= gap <= 24:
        raise StudioError("Agent Layout gap_pt must be between 0 and 24.")
    if not isinstance(crop, (int, float)) or not 0 <= crop <= 12:
        raise StudioError("Agent The layout crop_margins_pt must be between 0 and 12.")
    raw_labels = raw.get("labels", [])
    if not isinstance(raw_labels, list):
        raise StudioError("Agent Layout labels must be an array.")
    labels = []
    seen: set[str] = set()
    for item in raw_labels:
        if not isinstance(item, dict):
            raise StudioError("Each annotation must be a JSON object.")
        panel_id = str(item.get("panel_id", ""))
        text = str(item.get("text", "")).strip()
        position = str(item.get("position", ""))
        font_size = item.get("font_size_pt", 8)
        if panel_id not in panel_ids or panel_id in seen:
            raise StudioError("Agent Layout contains unknown or duplicate panel corner labels.")
        if not text or len(text) > 12:
            raise StudioError("Agent Superscript text must be 1–12 characters.")
        if position not in {"top-left", "top-right", "bottom-left", "bottom-right"}:
            raise StudioError("Agent Superscript position not supported.")
        if not isinstance(font_size, (int, float)) or not 6 <= font_size <= 24:
            raise StudioError("Agent The subscript font_size_pt must be between 6 and 24.")
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
        raise StudioError("Could not find the local Codex CLI; unable to interpret the paper assembly Prompt.")
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
    prompt = f"""You are the Paper Studio local paper typesetting Agent. Translate the researchers natural language requirements.
Convert into a strict JSON layout plan. Return only a JSON object, do not Markdown, do not explain.
Do not modify files and do not run the drawing program.

Investigator requirement:
{instruction.strip()}

Available subfigures:
{json.dumps(panel_context, ensure_ascii=False, indent=2)}

Strict schema:
{{
  "orientation": "horizontal" | "vertical",
  "width": "single-column" | "two-column",
  "panel_order": {json.dumps(panel_ids)},
  "gap_pt": 0 Numbers up to 24.,
  "crop_margins_pt": 0 Numbers up to 12.,
  "labels": [
    {{"panel_id": "a", "text": "(a)", "position": "top-left", "font_size_pt": 8}}
  ]
}}

Constraints:
1. panel_order Must include all available subplots and only them; the order may be adjusted per researchers requirements.
2. No spaces; seamless; tightly aligned with gap_pt.=0; Crop margins on all four sides corresponding to crop_margins_pt.=0.
3. Labels when superscripts are not requested.=[]; Require a b superscript for each panel; default font size 8 pt.
   If the researcher specifies a font size, write font_size_pt.
4. The executor will place each subfigure as an independent vector object into PPT, with the corner label as an editable text box;
   The final vector PDF is generated in the same layout without interactive steps and does not require user PowerPoint permissions.
   Do not propose PNG stitching, rasterization or modification of experimental data.
5. Decorative requirements that cannot be expressed should be ignored and must not add fields outside the schema.
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
            raise StudioError("Local Agent timed out while processing the paper composition Prompt.") from exc
        if process.returncode or not output.exists():
            diagnostic = (process.stdout + "\n" + process.stderr).strip()
            raise StudioError(
                "Local Agent failed to interpret the paper composition Prompt.\n"
                + (diagnostic[-2400:] or "codex exec Layout plan not returned.")
            )
        raw = extract_agent_layout_json(
            output.read_text(encoding="utf-8", errors="replace")
        )
    return validate_data_figure_layout(raw, panel_ids)


def pdf_page_size(pdf: Path, *, cwd: Path) -> tuple[float, float]:
    output = run_checked(["pdfinfo", str(pdf)], cwd=cwd)
    match = re.search(r"^Page size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts", output, re.M)
    if not match:
        raise StudioError(f"Unable to read PDF page size:{pdf.name}")
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
        raise StudioError("The local PowerPoint build is missing. @oai/artifact-tool.")
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
        raise StudioError("This figure has no combinable independent subfigures.")
    missing = [
        panel["id"]
        for panel in panels
        if not data_panel_paths(figure_id, panel["id"])["pdf"].exists()
    ]
    if missing:
        raise StudioError("Please generate subfigures one by one first:" + ", ".join(missing))
    required = ["pdfcrop", "pdfinfo", "pdftocairo", "latexmk", "node"]
    missing_tools = [command for command in required if not shutil_which(command)]
    if missing_tools:
        raise StudioError("Local PPT bundle missing tools." + ", ".join(missing_tools))
    ensure_artifact_tool_runtime()

    layout = layout or create_data_figure_layout_with_local_agent(figure_id, prompt)
    panel_by_id = {panel["id"]: panel for panel in panels}
    ordered_panels = [panel_by_id[panel_id] for panel_id in layout["panel_order"]]
    paths = figure_paths(figure_id)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for target in (paths["pdf"], paths["pptx"], paths["preview"]):
        target.parent.mkdir(parents=True, exist_ok=True)
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
    direction = "horizontal" if layout["orientation"] == "horizontal" else "vertical"
    label_note = " with panel badges" if layout["labels"] else ""
    return (
        f"Placed {len(panels)} vector subfigures as independent editable objects in a "
        f"{direction} PowerPoint layout{label_note}. The PPTX and final vector PDF use "
        "the same composition. PowerPoint permission confirmation not required."
    )


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    provider = str(state.get("llm_provider") or DEFAULT_PROVIDER).strip().lower()
    if provider not in PROVIDER_DEFAULT_MODELS:
        provider = "openai"
    api_key_setup = api_setup_for_provider(provider)
    api_key_configured = bool(api_key_setup["configured"])
    report_paths = [
        ROOT / "reports" / name
        for name in (
            "01_LIT_SURVEY.html",
            "02_IDEA_REPORT.html",
            "03_EXPERIMENT_PLAN.html",
            "04_RUN_PLAN.html",
            "05_EXP_RESULT.html",
        )
        if (ROOT / "reports" / name).is_file()
    ]
    report_signature = "\n".join(
        f"{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
        for path in report_paths
    )
    report_version = (
        hashlib.sha256(report_signature.encode("utf-8")).hexdigest()[:10]
        if report_signature
        else "none"
    )
    reports_updated_at = max(
        (int(path.stat().st_mtime) for path in report_paths), default=None
    )
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
                "subtitle": "Waiting for loading paper project data",
                "config_file": PROJECT_CONFIG_FILE.relative_to(ROOT).as_posix(),
                "root": "" if (ONLINE_PROJECT_MODE or DEMO_MODE) else str(ROOT.resolve()),
                "loaded": False,
                "report_version": report_version,
                "reports_updated_at": reports_updated_at,
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
                "page_budget": {
                    "limit": None,
                    "content_pages": None,
                    "remaining": None,
                    "status": "not_configured",
                    "excludes_references": True,
                },
            },
            "outline_confirmed": False,
            "demo_mode": DEMO_MODE,
            "online_project": ONLINE_PROJECT_MODE,
            "api_key_configured": api_key_configured,
            "api_key_setup": api_key_setup,
            "api_usage": usage_summary(API_USAGE_FILE),
            "figure_capabilities": {
                "mechanism_renderer": "codex-native-shapes",
                "requires_image_api": False,
                "text_provider": provider,
            },
            "full_draft": {
                "available": False,
                "pending_paragraphs": 0,
                "pending_title": False,
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
        "root": "" if (ONLINE_PROJECT_MODE or DEMO_MODE) else str(ROOT.resolve()),
        "loaded": True,
        "report_version": report_version,
        "reports_updated_at": reports_updated_at,
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
        for section_id, section in state.get("sections", {}).items()
        if SECTION_MAP.get(section_id, {}).get("writing_mode") != "plan_only"
    )
    pending_paragraphs = len(full_draft_targets(state))
    pending_artifacts = pending_batch_artifacts(state)
    outline_confirmed = outline_is_confirmed()
    result["full_draft"] = {
        "available": outline_confirmed and api_key_configured,
        "pending_paragraphs": pending_paragraphs,
        "pending_title": full_draft_title_pending(state),
        "pending_artifacts": pending_artifacts,
        "total_paragraphs": total_paragraphs,
        "writing_order": draft_writing_order(),
        "job": result.pop("full_draft_job", None),
    }
    result["section_draft"] = {
        "job": result.pop("section_draft_job", None),
    }
    title_editor = result.setdefault("title_editor", {})
    title_editor["current_title"] = manuscript_title_display()
    title_editor["conversation_active"] = bool(
        title_editor.pop("previous_response_id", None)
    )
    for section_id, section in result["sections"].items():
        section["writing_mode"] = SECTION_MAP.get(section_id, {}).get(
            "writing_mode", "draft"
        )
        section["conversation_active"] = bool(section.pop("previous_response_id", None))
        index = int(section.get("current_index", 0))
        paragraphs = section.pop("paragraphs", [])
        section["paragraph_count"] = len(paragraphs)
        section["completed_count"] = sum(
            bool(item.get("accepted_text")) for item in paragraphs
        )
        section["complete"] = section["completed_count"] == len(paragraphs)
        section["structure_blueprint"] = [
            {"id": item["id"], **paragraph_architecture(item)}
            for item in paragraphs
        ]
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
            section["reference_context"] = paragraph_reference_context(section_id, item)
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
                "architecture": paragraph_architecture(item),
                "candidate": item.get("candidate"),
                "accepted_text": item.get("accepted_text", ""),
                "position": index + 1,
                "total": len(paragraphs),
            }
        else:
            section["reference_context"] = {}
            section["current_paragraph"] = None
    pdf = PAPER / "main.pdf"
    pdf_metadata = paper_pdf_metadata()
    result["pdf"] = {
        "exists": pdf.exists(),
        "version": int(pdf.stat().st_mtime_ns) if pdf.exists() else None,
        "url": "/paper.pdf",
        **pdf_metadata,
        "page_budget": page_budget_status(),
    }
    result["outline_confirmed"] = outline_confirmed
    result["demo_mode"] = DEMO_MODE
    result["online_project"] = ONLINE_PROJECT_MODE
    result["llm_provider"] = provider
    result["llm_provider_options"] = provider_options
    result["llm_model_options"] = model_options
    result["api_key_configured"] = api_key_configured
    result["api_key_setup"] = api_key_setup
    result["api_usage"] = usage_summary(API_USAGE_FILE)
    result["figure_capabilities"] = {
        "mechanism_renderer": "codex-native-shapes",
        "requires_image_api": False,
        "text_provider": provider,
    }
    result["figures"] = figure_public_state(state)
    result["tables"] = table_public_state(state)
    return result


def _remove_generated_path(path: Path) -> None:
    """Delete one exact Paper Studio output path, never project inputs/config."""
    resolved = path.resolve()
    try:
        resolved.relative_to(PAPER.resolve())
    except ValueError as exc:
        raise StudioError(f"Refuse to clean paths outside paper/.{path}") from exc
    protected = {
        PAPER.resolve(),
        PROJECT_CONFIG_FILE.resolve(),
        (PAPER / "main.tex").resolve(),
        (PAPER / "working_abstract.txt").resolve(),
        (PAPER / "references.bib").resolve(),
    }
    if resolved in protected:
        raise StudioError(f"Refuse to clear Paper Studio input.{path}")
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


def restore_source_figure_inputs() -> None:
    """Restore verified reference-paper figures after generated outputs are cleared."""
    for figure_id, definition in FIGURES.items():
        if definition.get("kind") != "source":
            continue
        source_value = str(definition.get("source_asset") or "").strip()
        if not source_value:
            raise StudioError(f"Source figure {figure_id} Missing source_asset.")
        source = _project_path(ROOT, source_value, f"figures.{figure_id}.source_asset")
        if not source.is_file() or source.suffix.lower() != ".pdf":
            raise StudioError(f"Source figure {figure_id} The PDF does not exist:{source_value}")
        target = figure_paths(figure_id)["pdf"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _clear_generated_tree(root: Path, protected_files: set[Path] | None = None) -> None:
    """Clear every current or legacy output below one exact paper-local root."""
    protected = {path.resolve() for path in (protected_files or set())}
    resolved_root = root.resolve()
    try:
        resolved_root.relative_to(PAPER.resolve())
    except ValueError as exc:
        raise StudioError(f"Refuse to clean directories outside paper/.{root}") from exc
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
            raise StudioError("Drawing calls are still running; please use the stop button on the right side of the progress bar to terminate the calls.")

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
    restore_source_figure_inputs()

    for path in PAPER.glob("main.*"):
        if path.resolve() != main_path.resolve():
            _remove_generated_path(path)

    compile_result = compile_paper()
    if not compile_result.ok:
        raise StudioError("Cleared completed tasks, but the empty PDF compilation failed.\n" + compile_result.message)
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
        if (
            EMBEDDED_ONLY
            and path != "/api/health"
            and (
                not EMBEDDED_PROXY_TOKEN
                or self.headers.get("X-Research-Studio-Proxy", "") != EMBEDDED_PROXY_TOKEN
            )
        ):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
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
                    "embedded_only": EMBEDDED_ONLY,
                }
            )
        elif path == "/api/state":
            self.send_json(public_state(load_state()))
        elif path == "/paper.pdf":
            with COMPILE_LOCK:
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
        if (
            EMBEDDED_ONLY
            and (
                not EMBEDDED_PROXY_TOKEN
                or self.headers.get("X-Research-Studio-Proxy", "") != EMBEDDED_PROXY_TOKEN
            )
        ):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            body = self.read_json()
            if ONLINE_PROJECT_MODE and self.path in ONLINE_DISABLED_ARTIFACT_AGENT_PATHS:
                raise StudioError(
                    "The online session is not currently running the chart building Agent."
                    "Paper dialogue, body, titles, captions, and LLM writing features can still be used normally."
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
            elif self.path == "/api/section-draft/start":
                self.handle_section_draft_start(body)
            elif self.path == "/api/full-draft/cancel":
                self.handle_full_draft_cancel()
            elif self.path == "/api/llm-provider":
                self.handle_llm_provider(body)
            elif self.path == "/api/llm-model":
                self.handle_llm_model(body)
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
        if ONLINE_PROJECT_MODE:
            raise StudioError("Online writing sessions uniformly use the shared DeepSeek API and do not support switching providers.")
        state = load_state()
        if draft_batch_running(state):
            raise StudioError("Batch writing tasks are being generated; please wait for the tasks to complete before switching the LLM API.")
        provider = str(body.get("provider") or "").strip().lower()
        if select_llm_provider(state, provider):
            save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_llm_model(self, body: dict[str, Any]) -> None:
        if ONLINE_PROJECT_MODE:
            raise StudioError("Online writing sessions uniformly use the shared DeepSeek API and do not support switching models.")
        state = load_state()
        if draft_batch_running(state):
            raise StudioError("Batch writing tasks are being generated; please wait for the tasks to complete before switching writing models.")
        model = str(body.get("model") or "").strip()
        if select_llm_model(state, model):
            save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_title_generate(self, body: dict[str, Any]) -> None:
        state = load_state()
        if draft_batch_running(state):
            raise StudioError("Batch writing tasks are being generated; please wait for completion.")
        editor = state["title_editor"]
        prompt = str(body.get("prompt", "")).strip() or (
            "Generate one concise, specific academic title that reflects the paper's actual "
            "problem and contribution. Do not add unsupported claims."
        )
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
                "last_message": "GPT candidate Not saved yet; can continue editing, confirm before writing to LaTeX.",
            }
        )
        state["model"] = model
        save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_title_save(self, body: dict[str, Any]) -> None:
        if draft_batch_running(load_state()):
            raise StudioError("Batch writing tasks are being generated; please wait for completion.")
        title = normalize_plain_title(str(body.get("title", "")))
        result = save_manuscript_title(title)
        state = load_state()
        editor = state["title_editor"]
        editor["candidate"] = ""
        editor["last_message"] = "The title has been written to LaTeX and PDF compilation completed."
        editor["status"] = "confirmed"
        state["compile"] = {
            "status": "ok",
            "message": result.message,
            "updated_at": int(time.time()),
        }
        refresh_full_draft_artifact_status(state)
        save_state(state)
        schedule_ready_mechanism_figures()
        self.send_json({"ok": True, "state": public_state(state)})

    def require_figure(self, body: dict[str, Any]) -> str:
        figure_id = str(body.get("figure_id", "")).upper()
        if figure_id not in FIGURES:
            raise StudioError("Unknown paper figure.")
        return figure_id

    def reject_online_placeholder_figure(self, figure_id: str) -> None:
        if is_hosted_placeholder_artifact(figure_id):
            raise StudioError(ONLINE_PLACEHOLDER_FIGURE_MESSAGE)

    def require_panel(self, figure_id: str, body: dict[str, Any]) -> str:
        panel_id = str(body.get("panel_id", "")).lower()
        valid = {item["id"] for item in FIGURES[figure_id].get("panels", [])}
        if panel_id not in valid:
            raise StudioError("Please select a valid independent subfigure.")
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
        if SECTION_MAP[section].get("writing_mode") == "plan_only":
            raise StudioError("No experimental results uploaded yet; this section only shows paragraph planning and does not generate body text.")
        if not ONLINE_PROJECT_MODE:
            ensure_survey_bibliography()
        state = load_state()
        if draft_batch_running(state):
            raise StudioError("Batch writing tasks are being generated; please wait for completion.")
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
        current_bib_fingerprint = bibliography_fingerprint()
        source_fingerprint = section_source_fingerprint(section)
        include_section_context = (
            not section_state.get("previous_response_id")
            or section_state.get("conversation_section_fingerprint") != source_fingerprint
        )
        bibliography_update = ""
        if (
            not ONLINE_PROJECT_MODE
            and section_state.get("previous_response_id")
            and section_state.get("bibliography_fingerprint")
            != current_bib_fingerprint
        ):
            bibliography_update = writing_bibliography_catalog(
                purpose + "\n" + section_evidence(section)
            )
        response_id, text, citations_added = call_openai(
            section=section,
            model=model,
            previous_response_id=section_state.get("previous_response_id"),
            purpose=purpose,
            required_heading=paragraph.get("heading"),
            required_heading_style=paragraph.get("heading_style"),
            architecture=paragraph_architecture(paragraph),
            reference_context=paragraph_reference_context(section, paragraph),
            comment=str(body.get("comment", "")),
            current_text=str(body.get("current_text", "")),
            bibliography_update=bibliography_update,
            artifacts=[str(item) for item in paragraph.get("artifacts", [])],
            figure_states=state["figures"],
            include_section_context=include_section_context,
            minimum_online_citation_placeholders=(
                online_citation_placeholder_minimum(
                    section, section_state["paragraphs"].index(paragraph)
                )
                if ONLINE_PROJECT_MODE
                else 0
            ),
        )
        # The model call is intentionally outside the lock, but it can outlive
        # the browser request that started a batch-writing job. Never save the
        # pre-call state here: doing so used to erase the newer full_draft_job
        # (and any paragraphs it had accepted) when an automatic single-
        # paragraph generation returned from another tab. Rebase this narrow
        # candidate update onto the latest state while holding the same lock
        # used to create/advance full-draft jobs.
        with FULL_DRAFT_JOB_LOCK:
            state = load_state()
            if draft_batch_running(state):
                raise StudioError(
                    "Batch writing has started during single paragraph generation; this past candidate has been discarded, batch tasks continue."
                )
            section_state = state["sections"][section]
            paragraph = current_paragraph(section_state)
            if paragraph is None or (
                requested_paragraph_id and paragraph["id"] != requested_paragraph_id
            ):
                raise StudioError("Paragraph position was changed during generation; this prior candidate has been discarded.")
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
        if SECTION_MAP[section].get("writing_mode") == "plan_only":
            raise StudioError("No experimental results uploaded yet; this section only displays paragraph planning and cannot write the body.")
        requested_paragraph_id = str(body.get("paragraph_id", "")).strip()
        candidate_id = str(body.get("candidate_id", ""))
        submitted_text = str(body.get("candidate_text", "")).strip()
        base_text = str(body.get("base_text", ""))
        state = load_state()
        if draft_batch_running(state):
            raise StudioError("Batch writing tasks are being generated; please wait for completion.")
        section_state = state["sections"][section]
        paragraph = current_paragraph(section_state)
        if paragraph is None:
            raise StudioError("This section has no remaining paragraph.")
        if requested_paragraph_id and paragraph["id"] != requested_paragraph_id:
            raise StudioError(
                f"Current editing position has been moved from {requested_paragraph_id} Update to {paragraph['id']}; "
                "Please check and Accept again."
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
        text = (
            remove_manuscript_citations(text)
            if SECTION_MAP[section].get("render") == "abstract"
            else online_citation_markers(text)
            if ONLINE_PROJECT_MODE
            else local_survey_citations(text)
        )
        candidate["text"] = text
        bound_artifacts = artifact_writing_context(
            paragraph.get("artifacts", []), state.get("figures", {})
        )
        reference_error = artifact_reference_error(text, bound_artifacts)
        if reference_error:
            raise StudioError(reference_error)
        reference_error = artifact_reference_error(text, bound_artifacts)
        if reference_error:
            raise StudioError(reference_error)
        validate_citations_for_accept(text, workflow="local body text" if not ONLINE_PROJECT_MODE else "Online body text")
        appendix_issues = appendix_content_issues(section, text)
        if appendix_issues:
            raise StudioError("Appendix candidate remains a content roadmap." + "; ".join(appendix_issues))
        execution_issues = execution_record_contradiction_issues(text)
        if execution_issues:
            raise StudioError("Discrepancy between candidate and execution records." + "; ".join(execution_issues))
        setup_issues = experimental_setup_issues(
            section, str(paragraph.get("purpose") or ""), text
        )
        if setup_issues:
            raise StudioError("Experiment setup candidates incomplete:" + "; ".join(setup_issues))
        completion_issues = manuscript_completion_placeholder_issues(text)
        if completion_issues:
            raise StudioError("Candidates still contain planning placeholders:" + "; ".join(completion_issues))
        markup_issues = manuscript_markup_issues(text)
        if markup_issues:
            raise StudioError("Candidate still contains Markdown markup." + "; ".join(markup_issues))
        internal_reference_issues = unsupported_internal_reference_issues(text)
        if internal_reference_issues:
            raise StudioError(
                "Candidate contains unconfigured internal citations." + "; ".join(internal_reference_issues)
            )
        appendix_numeric_issues = unsupported_appendix_numeric_issues(
            section,
            text,
            section_evidence(
                section, [str(item) for item in paragraph.get("artifacts", [])]
            ),
        )
        if appendix_numeric_issues:
            raise StudioError(
                "Appendix candidate contains numbers without evidence." + "; ".join(appendix_numeric_issues)
            )
        prose_issues = latex_prose_issues(text)
        if prose_issues:
            raise StudioError(
                "Candidates containing characters that will break the pdflatex body text; please have GPT correct or manually convert to "
                "LaTeX:" + "; ".join(prose_issues)
            )
        security_issues = online_latex_security_issues(text)
        if security_issues:
            raise StudioError(
                "Online mode prohibits LaTeX commands that read files, write files, or execute code."
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
        previous_accepted_text = str(paragraph.get("accepted_text") or "")
        previous_candidate = paragraph.get("candidate")
        before_body_pages = compiled_content_page_count()
        paragraph["accepted_text"] = text
        paragraph["candidate"] = None
        auto_generate_bound_figure_captions(state, section, paragraph, text)
        section_source, accepted_section = render_section_source(
            section, section_state, state["figures"], state["tables"]
        )
        temporary = target.with_suffix(".tex.tmp")
        temporary.write_text(section_source, encoding="utf-8")
        os.replace(temporary, target)
        bibliography_text = manuscript_bibliography_section_text()
        bibliography_temporary = bibliography_path.with_suffix(".tex.tmp")
        bibliography_temporary.write_text(bibliography_text, encoding="utf-8")
        os.replace(bibliography_temporary, bibliography_path)
        compile_result = compile_paper()
        after_body_pages = compiled_content_page_count() if compile_result.ok else None
        budget_failed = compile_result.ok and page_budget_worsened(
            before_body_pages, after_body_pages
        )
        if not compile_result.ok or budget_failed:
            paragraph["accepted_text"] = previous_accepted_text
            paragraph["candidate"] = previous_candidate
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
            if budget_failed:
                raise StudioError(page_budget_error(before_body_pages, after_body_pages))
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
        refresh_full_draft_artifact_status(state)
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
        # The browser always submits its selected model, but API retries and
        # automation may omit the field.  Falling back to the package-wide
        # OpenAI default while the active provider is DeepSeek creates an
        # invalid cross-provider request and also overwrites the saved model.
        # Use the project's persisted selection first.
        state = load_state()
        model = str(body.get("model") or state.get("model") or DEFAULT_MODEL).strip()
        token, state = start_full_draft_job(model)
        active_model = str(state["model"])
        threading.Thread(
            target=full_draft_worker,
            args=(token, active_model),
            daemon=True,
            name=f"batch-draft-{token[:8]}",
        ).start()
        self.send_json({"ok": True, "state": public_state(state)}, status=202)

    def handle_section_draft_start(self, body: dict[str, Any]) -> None:
        state = load_state()
        model = str(body.get("model") or state.get("model") or DEFAULT_MODEL).strip()
        section = self.require_section(body)
        token, state = start_section_draft_job(model, section)
        active_model = str(state["model"])
        threading.Thread(
            target=section_draft_worker,
            args=(token, active_model, section),
            daemon=True,
            name=f"section-draft-{section}-{token[:8]}",
        ).start()
        self.send_json({"ok": True, "state": public_state(state)}, status=202)

    def handle_full_draft_cancel(self) -> None:
        with FULL_DRAFT_JOB_LOCK:
            state = load_state()
            job = state.get("full_draft_job") or {}
            token = str(job.get("token") or "")
            if job.get("status") != "running" or not token:
                raise StudioError("There is currently no full text generation task running.")
            CANCELLED_FULL_DRAFT_JOBS.add(token)
            job.update(
                status="cancelled",
                token=None,
                progress_message="Stop request issued; will stop after the currently processing paragraph finishes, then can continue to complete the unfinished paragraphs.",
                finished_at=int(time.time()),
            )
            state["full_draft_job"] = job
            save_state(state)
        self.send_json({"ok": True, "state": public_state(state)})

    def handle_reset_generated_paper(self, body: dict[str, Any]) -> None:
        if draft_batch_running(load_state()):
            raise StudioError("Please wait or stop the batch writing tasks, then clear the generated content.")
        confirmation = str(body.get("project_id", "")).strip()
        if confirmation != PROJECT_ID:
            raise StudioError("Project ID mismatch; no generated content was deleted.")
        model = str(body.get("model") or DEFAULT_MODEL).strip()
        if not model:
            raise StudioError("Model name cannot be empty.")
        state = reset_generated_paper(model)
        self.send_json(
            {
                "ok": True,
                "message": "Generated body text, dialogue, figure candidates, and run state have been cleared; project input has been retained.",
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
        # In the shared read-only Demo, paragraph selection is transient UI
        # navigation. Return the requested editor state without changing the
        # committed demo project seen by other visitors.
        if not DEMO_MODE:
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

    def handle_figure_generate_deterministic(
        self,
        figure_id: str,
        panel_id: str,
        state: dict[str, Any],
        figure_state: dict[str, Any],
        body: dict[str, Any],
    ) -> None:
        """Render a "data" kind figure synchronously online, no Agent job needed.

        A single deterministic chart is the whole figure (see
        render_data_figure_deterministic), so unlike the local Agent path
        there is no separate panel-then-compose job to track -- this
        finishes in one request, the same way handle_table_generate's
        online branch does for tables.
        """
        requested_width = str(body.get("layout_width", "single-column"))
        if requested_width not in {"single-column", "two-column"}:
            raise StudioError("The inserted paper width must be single column or double column.")
        paths = figure_paths(figure_id)
        render_data_figure_deterministic(figure_id, metrics_bundle(), paths["pdf"], paths["preview"])
        panel_paths = data_panel_paths(figure_id, panel_id)
        panel_paths["pdf"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(paths["pdf"], panel_paths["pdf"])
        shutil.copyfile(paths["preview"], panel_paths["preview"])
        message = "Charts deterministically generated from uploaded data (no Agent needed)."
        panels = dict(figure_state.get("panels", {}))
        panel_state = dict(panels.get(panel_id, {}))
        panel_state.update(
            status="built",
            revision=int(panel_state.get("revision", 0)) + 1,
            progress=100,
            progress_message="The charts have been deterministically generated.",
            last_message=message,
        )
        panels[panel_id] = panel_state
        figure_state.update(
            status="built",
            revision=int(figure_state.get("revision", 0)) + 1,
            approved_at=None,
            progress=100,
            progress_message="The final single figure has been deterministically generated.",
            last_message=message,
            panels=panels,
            layout_mode=requested_width,
            layout_width=requested_width,
            requested_layout_width=requested_width,
            layout_prompt="",
            layout_prompt_is_default=True,
            layout_plan={
                "orientation": "horizontal",
                "width": requested_width,
                "panel_order": [panel_id],
                "gap_pt": 0,
                "crop_margins_pt": 0,
                "labels": [],
            },
            composed_at=int(time.time()),
            job_token=None,
        )
        save_state(state)
        self.send_json({"ok": True, "message": message, "state": public_state(state)})

    def handle_figure_generate(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        self.reject_online_placeholder_figure(figure_id)
        if FIGURES[figure_id].get("kind") == "source":
            raise StudioError("Source figure loaded from the traceable PDF of the reference paper; no need to regenerate.")
        panel_id = self.require_panel(figure_id, body)
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if FIGURES[figure_id]["kind"] == "mechanism":
            if ONLINE_PROJECT_MODE:
                raise StudioError("Online sessions currently do not run a mechanism diagram design agent; paper dialogue, main text, titles, captions, tables, and LLM writing functions remain usable.")
            raise StudioError("Mechanism diagrams use the dedicated Codex native-shape workflow.")
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("A task is already running for this figure.")
        if ONLINE_PROJECT_MODE:
            self.handle_figure_generate_deterministic(figure_id, panel_id, state, figure_state, body)
            return
        instruction = str(body.get("agent_prompt", "")).strip()
        if len(instruction) > 8000:
            raise StudioError("Data chart modification command is too long; compress to within 8000 characters.")
        layout_prompt = str(body.get("layout_prompt", "")).strip()
        if len(layout_prompt) > 4000:
            raise StudioError("The paper composition prompt is too long; please compress it to within 4000 characters.")
        requested_width = str(body.get("layout_width", "single-column"))
        if requested_width not in {"single-column", "two-column"}:
            raise StudioError("The inserted paper width must be single column or double column.")
        token = uuid.uuid4().hex
        figure_state.update(
            {
                "status": "agent_generating",
                "progress": 10,
                "progress_message": "Starting local Agent…",
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
                "progress_message": "Starting the local Agent for this sub-figure.",
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
                "message": f"Local Agent started and is generating separately. {figure_id}({panel_id}).",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_compose(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        if FIGURES[figure_id]["kind"] != "data":
            raise StudioError("Only experimental data figures require local PDF assembly.")
        state = load_state()
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("A task is already running for this figure.")
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
            raise StudioError("The inserted paper width must be single column or double column.")
        if len(prompt) > 4000:
            raise StudioError("The paper composition prompt is too long; please compress it to within 4000 characters.")
        panels = figure_state.get("panels", {})
        missing = [
            item["id"]
            for item in FIGURES[figure_id].get("panels", [])
            if panels.get(item["id"], {}).get("status") != "built"
        ]
        if missing:
            raise StudioError("Please generate subfigures one by one first:" + ", ".join(missing))
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
            raise StudioError("Read only Demo cannot change API Key.")
        if ONLINE_PROJECT_MODE:
            # Every online session now shares one server-provisioned DeepSeek
            # key (see online_studio.server.shared_deepseek_api_key); letting
            # a request swap os.environ's key/provider for the whole child
            # process would both defeat the per-user spend cap (which is
            # keyed off DeepSeek usage) and let one session hijack another's
            # credentials for the process's remaining lifetime.
            raise StudioError("Online writing sessions use the shared DeepSeek API uniformly; changing the Key or service provider is not supported.")
        provider = str(body.get("provider", "openai")).strip().lower()
        key = str(body.get("api_key", ""))
        configuration = provider_configuration(provider)
        if not 8 <= len(key) <= 512 or any(
            character.isspace() or ord(character) < 32 for character in key
        ):
            raise StudioError("API Key Invalid format, please check and retry.")
        os.environ[configuration["environment_variable"]] = key
        with STATE_LOCK:
            state = load_state()
            select_llm_provider(state, provider)
            save_state(state)
        self.send_json(
            {
                "ok": True,
                "message": "API Key Safely updated.",
                "state": public_state(state),
            }
        )

    def handle_figure_prompt(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        self.reject_online_placeholder_figure(figure_id)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("Data figure does not use a drawing Prompt.")
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("A task is already running for this figure.")
        current_prompt = str(
            body.get("current_prompt", figure_state.get("draw_prompt", ""))
        ).strip()
        prompt_instruction = str(body.get("prompt_instruction", "")).strip()
        if len(prompt_instruction) > 4000:
            raise StudioError("Prompt The modification instruction is too long; please reduce to within 4000 characters.")
        if current_prompt and not prompt_instruction:
            raise StudioError("Before regenerating the Prompt, please specify how you want GPT to modify it.")
        job_token = uuid.uuid4().hex
        figure_state.update(
            {
                "status": "prompt_generating",
                "progress": 5,
                "progress_message": "Drawing Prompt task started…",
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
                "message": "GPT Generating drawing prompts for this section text.",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_draw(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        self.reject_online_placeholder_figure(figure_id)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("Data figures use the deterministic or local Agent plotting workflow.")
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("A task is already running for this figure.")
        prompt = str(body.get("draw_prompt", "")).strip()
        if not prompt:
            raise StudioError("First have GPT generate the drawing Prompt, then review and confirm.")
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
                    "progress_message": "Prompt unchanged; reusing the previous native-shape composition.",
                    "last_message": (
                        "Prompt identical to the last successful plot; no new drawing job was invoked."
                        "Continue displaying the original image."
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
                "progress_message": "Drawing prompt confirmed; native-shape generation is queued.",
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
                "message": "Prompt confirmed; Codex is generating an editable native-shape sketch.",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_cancel(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        self.reject_online_placeholder_figure(figure_id)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("The data chart has no running drawing job to stop.")
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
        self.reject_online_placeholder_figure(figure_id)
        if FIGURES[figure_id]["kind"] != "mechanism":
            raise StudioError("Data charts are constructed directly by reproducible scripts, no PPT reconstruction steps needed.")
        state = load_state()
        ready, reason = figure_generation_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        figure_state = state["figures"][figure_id]
        if figure_state.get("status") in FIGURE_RUNNING_STATUSES:
            raise StudioError("A task is already running for this figure.")
        token = uuid.uuid4().hex
        figure_state.update(
            {
                "status": "agent_generating",
                "progress": 10,
                "progress_message": "Starting local Agent to rebuild the editable mechanism diagram…",
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
                "message": "Local Agent started, building the editable figure from the confirmed drawing specification.",
                "state": public_state(state),
            },
            status=202,
        )

    def handle_figure_approve(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        self.reject_online_placeholder_figure(figure_id)
        state = load_state()
        ready, reason = figure_gate(figure_id, state)
        if not ready:
            raise StudioError(reason)
        paths = figure_paths(figure_id)
        if not paths["pdf"].exists():
            raise StudioError("Please generate the final PDF first.")
        if FIGURES[figure_id]["kind"] == "data" and not state["figures"][figure_id].get("composed_at"):
            raise StudioError("Please first use the paper composition Prompt to generate the final assembled PDF.")
        if not paths["pptx"].exists() and FIGURES[figure_id]["kind"] != "source" and not (
            ONLINE_PROJECT_MODE and FIGURES[figure_id]["kind"] == "data"
        ):
            raise StudioError("The illustration lacks an editable PPTX for layout and cannot confirm.")
        figure_state = state["figures"][figure_id]
        ensure_figure_caption_before_approval(state, figure_id)
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
                "LaTeX Illustration compilation failed; the text and figure state have been rolled back.\n" + compile_result.message
            )
        figure_state["last_message"] = (
            f"This figure has been inserted. {SECTION_MAP[section]['title']}, In-text citations added; PDF recompiled."
        )
        state["compile"] = {
            "status": "ok",
            "message": compile_result.message,
            "updated_at": int(time.time()),
        }
        refresh_full_draft_artifact_status(state)
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
        # A mechanism figure remains a placeholder online, but its caption is
        # manuscript text and must stay revisable when the citing paragraph or
        # scientific definition changes.
        current_caption = str(body.get("current_caption", "")).strip()
        prompt_instruction = str(body.get("prompt_instruction", "")).strip()
        if len(prompt_instruction) > 4000:
            raise StudioError("Caption Prompt Too long, compress to 4000 characters or fewer.")
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
                "message": "GPT Caption candidate Generated; please review and save.",
            }
        )

    def handle_figure_caption(self, body: dict[str, Any]) -> None:
        figure_id = self.require_figure(body)
        caption = normalize_figure_caption_text(str(body.get("caption", "")))
        if not caption:
            raise StudioError("Caption Cannot be empty.")
        caption_issues = figure_caption_issues(caption)
        if caption_issues:
            raise StudioError(
                "Caption Must be a short English sentence." + "; ".join(caption_issues)
            )

        state = load_state()
        figure_state = state["figures"][figure_id]
        previous_caption = figure_state.get("caption")
        figure_state["caption"] = caption
        figure_state["caption_source"] = "researcher"
        figure_state["caption_generated_from_paragraph"] = ""
        figure_state["caption_generated_from_sha256"] = ""
        figure_state["caption_generated_at"] = None
        figure_state["caption_last_error"] = ""
        figure_state["last_message"] = "Caption Saved."

        online_placeholder = is_hosted_placeholder_artifact(figure_id)
        if figure_state.get("status") == "approved" or online_placeholder:
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
                    "Caption LaTeX compilation failed; changes have been rolled back.\n"
                    + compile_result.message
                )
            state["compile"] = {
                "status": "ok",
                "message": compile_result.message,
                "updated_at": int(time.time()),
            }
            figure_state["last_message"] = "Caption Saved and recompiled the main text."

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
        self.reject_online_placeholder_figure(figure_id)
        state = load_state()
        definition = FIGURES[figure_id]
        section = definition["source_sections"][0]
        placement_after = str(body.get("placement_after", "")).strip()
        paragraphs = state["sections"][section]["paragraphs"]
        paragraph = next(
            (item for item in paragraphs if item["id"] == placement_after), None
        )
        if paragraph is None:
            raise StudioError("The selected paragraph does not belong to the section bound to this figure.")
        if not paragraph.get("accepted_text"):
            raise StudioError(f"{placement_after} Main text not written yet; cannot place the figure after it.")

        figure_state = state["figures"][figure_id]
        layout_mode = str(
            body.get("layout_mode", figure_state.get("layout_mode", "single-column"))
        )
        if layout_mode not in {"single-column", "two-column", "wrapfigure"}:
            raise StudioError("The layout must be single column, double column, or WrapFigure.")
        if layout_mode == "wrapfigure":
            raise StudioError(
                "The current AAAI 2026 official template prohibits wrapfig/WrapFigure."
                "Please choose single-column or double-column layout; otherwise the paper cannot be compiled."
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
                f"Figure placement set to {placement_after} Layout method is {layout_mode}; "
                "Confirming the image will be written into the main text."
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
                "LaTeX compilation failed after moving the illustration; the placement has been rolled back.\n" + compile_result.message
            )

        figure_state["last_message"] = (
            f"This figure has been moved to {placement_after} The PDF has been recompiled."
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
        layout_mode = str(
            table_state.get("layout_mode")
            or (
                "two-column"
                if str(TABLES[table_id].get("width", "")).startswith("two-column")
                else "single-column"
            )
        )
        prompt = str(
            body.get(
                "generation_prompt",
                table_state.get("generation_prompt", default_table_prompt(table_id)),
            )
        ).strip()
        if len(prompt) > 8000:
            raise StudioError("Table prompt is too long; please compress it to within 8000 characters.")
        if table_state.get("status") == "agent_editing":
            raise StudioError("This table already has a local Agent task running.")
        if ONLINE_PROJECT_MODE:
            # No local Agent subprocess online -- generate_table_latex's
            # deterministic structured-prompt parser already handles the
            # same source-data/column/row/caption/font-size/best-value directives this
            # prompt uses, so route there instead of the (blocked) Agent.
            latex = validate_table_latex_source(
                table_id,
                generate_table_latex(
                    table_id,
                    metrics_bundle(),
                    prompt,
                    layout_mode=layout_mode,
                ),
                layout_mode=layout_mode,
            )
            compile_table_preview(table_id, latex)
            table_state.update(
                {
                    "generation_prompt": prompt,
                    "status": "built",
                    "latex": latex,
                    "progress": 100,
                    "progress_message": "Tables have been generated and compiled from traceable results.",
                    "last_message": "Generated deterministically from traceable results according to Prompt specifications.",
                    "revision": int(table_state.get("revision", 0)) + 1,
                    "job_token": None,
                    "job_started_at": None,
                    "approved_at": None,
                }
            )
            save_state(state)
            self.send_json(
                {"ok": True, "message": "Table has been generated.", "state": public_state(state)}
            )
            return
        token = uuid.uuid4().hex
        latex = str(table_state.get("latex", ""))
        instruction = (
            "Generate a complete draft of the paper results table according to the following specifications, fully covering traceable results."
            "Do not omit existing experiment numbers.\n\n" + prompt
        )
        table_state.update(
            {
                "generation_prompt": prompt,
                "status": "agent_editing",
                "agent_prompt": instruction,
                "progress": 10,
                "progress_message": "Starting local Codex agent to generate the initial draft of the table…",
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
                "message": "Local Agent started, generating LaTeX tables from traceable results.",
                "state": public_state(state),
            },
            status=202,
        )

    def validate_table_latex(self, table_id: str, latex: str) -> str:
        state = load_state()
        table_state = state.get("tables", {}).get(table_id, {})
        layout_mode = str(
            table_state.get("layout_mode")
            or (
                "two-column"
                if str(TABLES[table_id].get("width", "")).startswith("two-column")
                else "single-column"
            )
        )
        return validate_table_latex_source(
            table_id,
            latex,
            layout_mode=layout_mode,
        )

    def handle_table_agent_edit(self, body: dict[str, Any]) -> None:
        table_id = self.require_table(body)
        state = load_state()
        ready, reason = table_gate(table_id, state)
        if not ready:
            raise StudioError(reason)
        table_state = state["tables"][table_id]
        if table_state.get("status") == "agent_editing":
            raise StudioError("This table already has a local Agent modification task running.")
        latex = self.validate_table_latex(
            table_id, str(body.get("latex", table_state.get("latex", "")))
        )
        instruction = str(body.get("agent_prompt", "")).strip()
        if not instruction:
            raise StudioError("Please fill in the table modification Prompt for the local Agent.")
        if len(instruction) > 8000:
            raise StudioError("Local Agent Prompt is too long; please compress to within 8000 characters.")
        token = uuid.uuid4().hex
        table_state.update(
            {
                "status": "agent_editing",
                "agent_prompt": instruction,
                "progress": 10,
                "progress_message": "Starting local codex agent (read-only sandbox)…",
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
                "message": "Local Agent has started; no call to Paper Studio GPT API.",
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
        table_state["last_message"] = "Table LaTeX modifications have been saved; they will be written into the main text only after confirmation."
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
                "Inserting the main text failed; tables and text have been rolled back.\n" + compile_result.message
            )
            state["compile"] = {
                "status": "error",
                "message": compile_result.message,
                "updated_at": int(time.time()),
            }
            save_state(state)
            raise StudioError(
                "LaTeX Table compilation failed; the text and table states have been rolled back.\n"
                + compile_result.message
            )
        table_state["last_message"] = (
            f"This table has been inserted. {SECTION_MAP[section]['title']}, PDF Recompiled."
        )
        state["compile"] = {
            "status": "ok",
            "message": compile_result.message,
            "updated_at": int(time.time()),
        }
        refresh_full_draft_artifact_status(state)
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
            raise StudioError("The selected paragraph does not belong to the section bound to this table.")
        if not paragraph.get("accepted_text"):
            raise StudioError(f"{placement_after} Main text not written yet; cannot place table after it.")
        table_state = state["tables"][table_id]
        layout_mode = str(
            body.get("layout_mode")
            or table_state.get("layout_mode")
            or (
                "two-column"
                if definition["width"].startswith("two-column")
                else "single-column"
            )
        ).strip()
        if layout_mode not in {"single-column", "two-column"}:
            raise StudioError("Table typesetting supports only single column or double column.")
        previous_state = dict(table_state)
        previous_latex = str(table_state.get("latex") or "")
        converted_latex = previous_latex
        if previous_latex.strip() and not table_latex_is_placeholder(previous_latex):
            converted_latex = convert_table_latex_layout(
                table_id, previous_latex, layout_mode
            )
            compile_table_preview(table_id, converted_latex)
        table_state["placement_after"] = placement_after
        table_state["layout_mode"] = layout_mode
        if converted_latex:
            table_state["latex"] = converted_latex
        if table_state.get("status") != "approved":
            table_state["last_message"] = (
                f"Table placement set to {placement_after} Layout method is {layout_mode}; "
                "The table will be written into the main text upon confirmation."
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
            state["tables"][table_id] = previous_state
            if previous_latex.strip() and not table_latex_is_placeholder(previous_latex):
                try:
                    compile_table_preview(table_id, previous_latex)
                except StudioError:
                    pass
            compile_paper()
            raise StudioError(
                "LaTeX compilation failed after updating the table position or width; changes have been rolled back.\n"
                + compile_result.message
            )
        table_state["last_message"] = (
            f"This table has moved to {placement_after} Then switch to. {layout_mode}, "
            "PDF Recompiled."
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
                    "Terminal full text writing must first ask which API to use, then explicitly pass it in. "
                    "--provider openai or --provider deepseek."
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
    if not ONLINE_PROJECT_MODE and not EMBEDDED_ONLY and not DEMO_MODE:
        print(
            "ERROR: Local paper editor is only available in Research Studio. Please run "
            "`python3 -m research_avatar.research_studio.server --ensure-studios` "
            "And opens http://127.0.0.1:8780.",
            file=sys.stderr,
        )
        raise SystemExit(2)
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
        leadins_changed = repair_redundant_section_leadins_in_manuscript(state)
        placeholder_refs_changed = repair_online_placeholder_references_in_manuscript(
            state
        )
        artifacts_changed = synchronize_artifact_workbenches_from_manuscript(
            state, build_table_previews=True
        )
        if leadins_changed or placeholder_refs_changed:
            compile_result = compile_paper()
            state["compile"] = {
                "status": "ok" if compile_result.ok else "error",
                "message": compile_result.message,
                "updated_at": int(time.time()),
            }
        if (
            prose_changed
            or leadins_changed
            or placeholder_refs_changed
            or artifacts_changed
        ):
            save_state(state)
    server = StudioHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Paper editor backend: {url} (internal to Research Studio)")
    print(f"Workspace: {ROOT}")
    print(f"Model: {load_state().get('model') or DEFAULT_MODEL}")

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
