import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import (
    WATSON_DIR, STATE_FILE, PAPERS_FILE, SIMILAR_PAPERS_FILE, TOP_CONF_PAPERS_FILE,
    ALL_RELEVANT_PAPERS_FILE,
    IDEA_FILE, IDEA_ASSESSMENT_FILE,
    EXPERIMENT_FILE, CODE_FILE, RUN_LOG_FILE, RESULTS_FILE, ANALYSIS_FILE, PAPER_FILE,
    EXPERIMENTS_DIR, PAPER_DIR, PAPER_SECTIONS_DIR, STEPS,
)

TEMPLATE_LATEX_FILE = WATSON_DIR / "template_latex.json"

# Re-export so callers can do `S.IDEA_FILE`
__all__ = ["IDEA_FILE", "PAPER_FILE"]


def ensure_dirs() -> None:
    WATSON_DIR.mkdir(exist_ok=True)
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    PAPER_DIR.mkdir(exist_ok=True)
    PAPER_SECTIONS_DIR.mkdir(exist_ok=True)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def load_json(path: Path) -> Any:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_json(path: Path, data: Any) -> None:
    ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Text file helpers ──────────────────────────────────────────────────────────

def load_file(path: Path) -> Optional[str]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def save_file(path: Path, content: str) -> None:
    ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def append_file(path: Path, content: str) -> None:
    ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


# ── State helpers ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    ensure_dirs()
    data = load_json(STATE_FILE)
    return data if isinstance(data, dict) else {}


def save_state(updates: dict) -> None:
    state = load_state()
    state.update(updates)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_json(STATE_FILE, state)


def get_current_step() -> str:
    return load_state().get("last_step", "")


def get_completed_steps() -> list[str]:
    step = get_current_step()
    if not step or step not in STEPS:
        return []
    return STEPS[: STEPS.index(step) + 1]


# ── Convenience loaders ────────────────────────────────────────────────────────

def load_idea() -> Optional[str]:
    state = load_state()
    return state.get("idea") or load_file(IDEA_FILE)


def load_similar_papers() -> list[dict]:
    data = load_json(SIMILAR_PAPERS_FILE)
    return data if isinstance(data, list) else []


def load_top_conf_papers() -> list[dict]:
    data = load_json(TOP_CONF_PAPERS_FILE)
    return data if isinstance(data, list) else []


def load_all_relevant_papers() -> list[dict]:
    data = load_json(ALL_RELEVANT_PAPERS_FILE)
    return data if isinstance(data, list) else []


def load_papers() -> list[dict]:
    """Return all papers (similar + top_conf combined)."""
    return load_similar_papers() + load_top_conf_papers()


def load_idea_assessment() -> Optional[str]:
    return load_file(IDEA_ASSESSMENT_FILE)


def load_experiment() -> Optional[str]:
    return load_file(EXPERIMENT_FILE)


def load_code() -> Optional[str]:
    return load_file(CODE_FILE)


def load_run_log() -> Optional[str]:
    return load_file(RUN_LOG_FILE)


def load_results() -> Optional[str]:
    return load_file(RESULTS_FILE)


def load_analysis() -> Optional[str]:
    return load_file(ANALYSIS_FILE)


def load_paper() -> Optional[str]:
    return load_file(PAPER_FILE)


def load_paper_section(key: str) -> Optional[str]:
    return load_file(PAPER_SECTIONS_DIR / f"{key}.tex")


def save_paper_section(key: str, content: str) -> None:
    save_file(PAPER_SECTIONS_DIR / f"{key}.tex", content)


def load_paper_template() -> Optional[dict]:
    """Return the custom template paper saved by the user, if any."""
    return load_json(WATSON_DIR / "paper_template.json")


def save_paper_template(template: dict) -> None:
    save_json(WATSON_DIR / "paper_template.json", template)


def load_template_latex() -> dict[str, str]:
    data = load_json(TEMPLATE_LATEX_FILE)
    if not isinstance(data, dict):
        return {}
    # Normalize line endings on load to fix cached content with \r or \r\n
    return {
        k: v.replace("\r\n", "\n").replace("\r", "\n")
        for k, v in data.items()
        if isinstance(v, str)
    }


def save_template_latex(sections: dict[str, str]) -> None:
    save_json(TEMPLATE_LATEX_FILE, sections)
