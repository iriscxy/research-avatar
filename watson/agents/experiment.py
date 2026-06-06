"""Step 2: evidence-grounded experiment design and interactive revision.

本模块兼容新版 Step1：
- 优先读取 ``papers_top_conf.json`` 中已经做过技术标注的论文；
- 同时读取 ``papers_all_relevant.json`` 中的 competitor/background 文献；
- 保留旧版 ``load_papers()`` 作为兼容。

输出包含原Watson所需的 ``.watson/experiment.md``，并额外保存：
- ``experiment_plan.json``：机器可读实验合同；
- ``experiment_evidence.json``：Step1 文献证据；
- ``experiment_repo_report.json``：代码库推荐来源；
- ``download_data_plan.md``：数据准备计划；
- ``experiment_revision_history.json``：用户修改意见与版本历史。

GitHub 策略：
1. 优先直接返回论文元数据里已经给出的 GitHub 链接；
2. 论文没有链接时，默认才使用 GitHub Search 推荐；
3. 只有 light_check/deep_check 才读取 README 和文件树；
4. Step2 作为实验方案不验证代码是否可运行。
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from urllib.parse import urlparse

import requests

from ..config import EXPERIMENT_FILE, WATSON_DIR
from ..llm import (
    build_messages,
    build_messages_cached,
    complete_chat,
    stream_chat,
)
from .. import state as S


# =============================================================================
# 1. Step2 输出文件
# =============================================================================

EXPERIMENT_JSON_FILE = WATSON_DIR / "experiment_plan.json"
EXPERIMENT_EVIDENCE_FILE = WATSON_DIR / "experiment_evidence.json"
EXPERIMENT_REPO_REPORT_FILE = WATSON_DIR / "experiment_repo_report.json"
DOWNLOAD_DATA_PLAN_FILE = WATSON_DIR / "download_data_plan.md"
EXPERIMENT_REVISION_HISTORY_FILE = WATSON_DIR / "experiment_revision_history.json"

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_REPOS_API = "https://api.github.com/repos"


# =============================================================================
# 2. Prompt 模板
# =============================================================================

EXTRACTION_SYSTEM = """你是 Watson Step2 实验设计 Agent。请只输出严格 JSON，不要输出 Markdown。

你会收到：
1. 已验证的研究 idea；
2. Step1 的量化评审结论；
3. 带 paper_id 的论文 evidence pack，其中包含 competitor/background、相关性、技术区别、相似度和可能的 code_urls；
4. 用户硬件和时间约束；
5. 本地 GPU/CPU 探测结果；
6. 若为修订任务，还会收到上一版 experiment_plan 和用户修改意见。

你的目标是把研究 idea 转换成可执行、可追溯的实验设计合同。

硬性要求：
- baseline、dataset、metric、baseline-derived hyperparameter 必须尽可能引用 evidence pack 中真实存在的 paper_id。
- 不得编造 paper_id、论文结论、代码链接或论文超参数。
- baseline 按 classic / strong / sota / open_source_alternative 分层组织。
- 不要因为本地资源较弱删除科学上必要的 SOTA baseline；资源限制只影响 MVP、运行规模和执行提醒。
- 论文 evidence 中存在 code_urls 时，优先把它们写入 repo_candidates。
- 数据集必须写明 name、aliases、version、用途、下载提示、预处理、目标路径和预期统计量。
- 指标必须区分 primary / secondary / diagnostic / efficiency，并说明支持什么研究主张。
- 超参数优先继承 baseline_paper 或 baseline_repo；不知道时写 TBD。
- 必须给出 method_module_order，明确多个模块或阶段的运行顺序。
- 必须生成 mvp_plan / main_plan / ablation_plan / diagnostic_plan。
- 必须生成 command-level execution_plan，供 Step3 生成代码。
- 所有不确定信息必须进入 needs_human_confirm。

修订任务额外要求：
- 严格执行用户的增删 baseline、数据集、指标、消融、预算等意见。
- 未被用户要求修改的部分尽量保留。
- 用户明确要求加入、但 evidence pack 中暂时没有文献依据的 baseline，允许保留，必须设置 user_requested=true、needs_human_confirm=true，且不得伪造 citation。
- 用户明确要求删除的对象不能在最终候选或 selected 列表中重新出现。

输出 JSON 顶层字段：
{
  "schema_version": "2.5",
  "research_task": "string",
  "method_family": "string",
  "hypothesis": "string",
  "method_module_order": ["string"],
  "baseline_candidates": [
    {
      "name": "string",
      "role": "classic|strong|sota|open_source_alternative",
      "method_family": "string",
      "citations": [
        {
          "paper_id": "P001",
          "paper_title": "string",
          "evidence_type": "used_as_baseline|related_method|sota_claim|reports_hparams",
          "evidence": "short evidence grounded in provided metadata"
        }
      ],
      "why_relevant": "string",
      "expected_comparison_value": "string",
      "compute_level": "low|medium|high",
      "open_source_query": "string",
      "repo_candidates": [
        {
          "url": "https://github.com/owner/repo",
          "source": "paper_code_link|github_search|manual|unknown",
          "from_paper_id": "P001",
          "note": "string"
        }
      ],
      "fallback_if_unavailable": "string",
      "user_requested": false,
      "needs_human_confirm": false
    }
  ],
  "dataset_candidates": [
    {
      "name": "string",
      "aliases": ["string"],
      "version": "string or null",
      "purpose": "main|auxiliary|diagnostic|toy_mvp",
      "citations": [],
      "download_hint": "string",
      "preprocessing": [
        {
          "step": "string",
          "align_to_baseline": "string",
          "citations": []
        }
      ],
      "storage_path_hint": "data/<dataset_name>",
      "expected_statistics": ["num_samples", "label_distribution"],
      "needs_human_confirm": false
    }
  ],
  "metric_candidates": [
    {
      "name": "string",
      "type": "primary|secondary|diagnostic|efficiency",
      "higher_is_better": true,
      "citations": [],
      "why_this_metric": "string",
      "claim_supported": "string"
    }
  ],
  "hyperparameter_policy": {
    "principle": "inherit cited baseline settings; use agent_suggested only when unknown",
    "parameters": [
      {
        "name": "string",
        "initial_value": "string or number or TBD",
        "source": "baseline_paper|baseline_repo|standard_default|agent_suggested|TBD",
        "citations": [],
        "tunable": true,
        "search_space": "string",
        "fallback": "string",
        "confidence": "high|medium|low",
        "needs_human_confirm": false
      }
    ]
  },
  "experiment_matrix": {
    "mvp_plan": [],
    "main_plan": [],
    "ablation_plan": [],
    "diagnostic_plan": []
  },
  "execution_plan": {
    "environment": {
      "framework": "PyTorch",
      "python_version": ">=3.10",
      "packages": [],
      "hardware_assumption": "string"
    },
    "artifacts": {
      "results_json": "experiments/results.json",
      "run_log": ".watson/run_log.txt",
      "figures_dir": "paper/figures",
      "checkpoints_dir": "experiments/checkpoints"
    },
    "commands": []
  },
  "iteration_hooks": {
    "what_to_record": [],
    "failure_signatures": [],
    "refine_rules": [],
    "pivot_rules": []
  },
  "needs_human_confirm": []
}
"""

HYPERPARAM_SYSTEM = """你是 Watson Step2 超参数建议器。请只输出 JSON 数组。

对输入中 initial_value 为 TBD/unknown/空值的参数给出保守建议。
要求：
- source 必须是 agent_suggested 或 standard_default；
- 不得声称建议值来自论文，除非输入已经提供合法 citations；
- confidence 只能是 low 或 medium；
- needs_human_confirm 必须是 true；
- search_space 应小而可执行，适合 MVP 或有限预算主实验；
- 只输出 JSON 数组。
"""

MARKDOWN_SYSTEM = """你是 Watson Step2 实验设计报告生成器。
请把最终 experiment_plan.json 转写成人类可读的中文 experiment.md。

写作要求：
- 风格接近 KDD/ACL/ICLR 的实验设计与系统方法说明；
- baseline 必须显示 paper_id，例如 [P003]；
- 清楚区分论文直接代码链接与 GitHub 搜索推荐；
- 明确说明 repository recommendation 不等于 verified runnable；
- 明确展示用户本轮修改意见及修改轮次；
- 不要重新发明 JSON 中没有的信息；
- Structured Appendix 中附完整 JSON 代码块。

章节必须为：
# Experiment Design
## 1. Problem Framing
## 2. Step1 Evidence Coverage
## 3. Local Resource Profile
## 4. Must-Cite Baseline Retrieval
## 5. Code Repository Recommendation
## 6. Dataset and Preprocessing Plan
## 7. Metric Plan
## 8. Executable Experimental Matrix
## 9. Baseline-Anchored Hyperparameter Initialization
## 10. Execution Plan for Step 3/4
## 11. Iteration Hooks for Step 5
## 12. Revision Summary and Human Checks
## Structured Appendix
"""


# =============================================================================
# 3. 基础工具
# =============================================================================


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _truncate(value: Any, limit: int) -> str:
    text = "" if value is None else str(value).replace("\x00", "")
    return text if len(text) <= limit else text[:limit] + "..."


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", str(value).lower()).strip("_")
    return text[:80] or "unknown"


def _safe_json_dict(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def _safe_json_list(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\[.*\]", text, re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
        except Exception:
            pass
    return []


def _run_cmd(command: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return process.returncode, process.stdout.strip()
    except Exception as exc:
        return 1, str(exc)


def _memory_gb() -> float | None:
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        return None


def _load_json_file(path: Path) -> Any:
    try:
        return S.load_json(path)
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        except Exception:
            return None


# =============================================================================
# 4. 新版 Step1 论文适配
# =============================================================================


def _paper_key(paper: dict[str, Any]) -> str:
    title = re.sub(r"\s+", " ", str(paper.get("title", "")).strip().lower())
    if title:
        return title
    return str(paper.get("link", "") or paper.get("pdf", "")).strip().lower()


def _merge_paper_records(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Merge duplicate paper records while keeping richer Step1 annotations."""
    merged = dict(secondary)
    for key, value in primary.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def _load_step1_papers() -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Load papers from the updated Step1 and deduplicate them.

    Priority:
    1. top_conf: has LLM relevance/difference/similarity annotations;
    2. all_relevant: includes competitor/background tiers and wider coverage;
    3. load_papers: compatibility fallback for older projects.
    """
    top_conf = S.load_top_conf_papers()

    load_all = getattr(S, "load_all_relevant_papers", None)
    all_relevant = load_all() if callable(load_all) else []
    legacy = S.load_papers()

    merged_by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for source_name, papers in [
        ("top_annotated", top_conf),
        ("all_relevant", all_relevant),
        ("legacy", legacy),
    ]:
        for raw in papers:
            if not isinstance(raw, dict):
                continue
            paper = dict(raw)
            paper["step1_source_group"] = source_name
            key = _paper_key(paper)
            if not key:
                continue
            if key not in merged_by_key:
                merged_by_key[key] = paper
                order.append(key)
            else:
                # 前面的来源优先，因此把旧记录作为 primary。
                merged_by_key[key] = _merge_paper_records(merged_by_key[key], paper)

    papers = [merged_by_key[key] for key in order]
    stats = {
        "top_annotated_count": len(top_conf),
        "all_relevant_count": len(all_relevant),
        "legacy_count": len(legacy),
        "deduplicated_count": len(papers),
        "competitor_count": sum(1 for p in papers if p.get("tier") == "competitor"),
        "background_count": sum(1 for p in papers if p.get("tier") == "background"),
    }
    return papers, stats


def _extract_github_urls(text: str) -> list[str]:
    if not text:
        return []
    pattern = r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?"
    found = re.findall(pattern, text)
    urls: list[str] = []
    for url in found:
        url = url.rstrip(").,;，。；、")
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            normalized = f"https://github.com/{parts[0]}/{parts[1]}"
            if normalized not in urls:
                urls.append(normalized)
    return urls


def _collect_paper_text_for_code_urls(paper: dict[str, Any]) -> str:
    fields = [
        "title",
        "summary",
        "abstract",
        "relevance",
        "difference",
        "link",
        "pdf",
        "url",
        "paper_url",
        "project_url",
        "code_url",
        "github",
        "repo",
        "repository",
    ]
    parts: list[str] = []
    for field in fields:
        value = paper.get(field)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif isinstance(value, dict):
            parts.append(_json(value))
    return "\n".join(parts)


def _evidence_priority(paper: dict[str, Any]) -> tuple[Any, ...]:
    group = str(paper.get("step1_source_group", ""))
    group_rank = 0 if group == "top_annotated" else 1 if group == "all_relevant" else 2
    tier = str(paper.get("tier", ""))
    tier_rank = 0 if tier == "competitor" else 1 if tier == "background" else 2
    similarity = float(paper.get("similarity_score") or 0)
    relevance = float(paper.get("relevance_score") or 0)
    try:
        year = int(str(paper.get("published", ""))[:4])
    except Exception:
        year = 0
    return group_rank, tier_rank, -similarity, -relevance, -year, str(paper.get("title", ""))


def _evidence_pack(papers: list[dict[str, Any]], limit: int = 24) -> list[dict[str, Any]]:
    """Convert updated Step1 papers into a compact, citeable evidence pack."""
    selected = sorted(papers, key=_evidence_priority)[:limit]
    evidence: list[dict[str, Any]] = []

    for index, paper in enumerate(selected, 1):
        code_urls = _extract_github_urls(_collect_paper_text_for_code_urls(paper))
        evidence.append(
            {
                "paper_id": f"P{index:03d}",
                "title": paper.get("title", ""),
                "venue": paper.get("venue", ""),
                "published": paper.get("published", ""),
                "authors": _as_list(paper.get("authors"))[:6],
                "summary": _truncate(paper.get("summary", ""), 650),
                "relevance": _truncate(paper.get("relevance", ""), 420),
                "difference": _truncate(paper.get("difference", ""), 420),
                "relevance_score": paper.get("relevance_score"),
                "similarity_score": paper.get("similarity_score"),
                "tier": paper.get("tier", ""),
                "source": paper.get("source", ""),
                "step1_source_group": paper.get("step1_source_group", ""),
                "link": paper.get("link", ""),
                "pdf": paper.get("pdf", ""),
                "is_top_conf": bool(paper.get("is_top_conf", False)),
                "code_urls": code_urls,
            }
        )
    return evidence


# =============================================================================
# 5. 本地资源和用户约束
# =============================================================================


def _detect_local_hardware() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count() or 1,
        "memory_gb": _memory_gb(),
        "accelerator": "cpu",
        "gpu_count": 0,
        "gpu_models": [],
        "gpu_ids": [],
        "idle_gpu_ids": [],
        "busy_gpu_ids": [],
        "max_free_memory_gpu_id": None,
        "recommended_gpu_ids": [],
        "recommended_parallel_gpus": 0,
        "gpus": [],
        "notes": [],
    }

    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        info["accelerator"] = "mps_or_cpu" if platform.system() == "Darwin" else "cpu"
        info["notes"].append("nvidia-smi not found")
        return info

    code, output = _run_cmd(
        [
            nvidia_smi,
            "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ],
        timeout=10,
    )
    if code != 0 or not output:
        info["notes"].append(f"nvidia-smi failed: {output[:200]}")
        return info

    gpus: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 9:
            continue

        def to_int(value: str, default: int = 0) -> int:
            try:
                return int(float(value))
            except Exception:
                return default

        gpu_id = to_int(parts[0], len(gpus))
        total = to_int(parts[3])
        used = to_int(parts[4])
        free = to_int(parts[5])
        utilization = to_int(parts[6], 100)
        free_ratio = free / total if total else 0.0

        gpus.append(
            {
                "id": gpu_id,
                "uuid": parts[1],
                "model": parts[2],
                "memory_total_mb": total,
                "memory_used_mb": used,
                "memory_free_mb": free,
                "memory_free_ratio": round(free_ratio, 3),
                "utilization_gpu_percent": utilization,
                "temperature_c": to_int(parts[7]),
                "power_draw_w": parts[8],
                "is_idle": bool(total and free_ratio >= 0.55 and utilization <= 30),
            }
        )

    if not gpus:
        return info

    idle = [gpu for gpu in gpus if gpu["is_idle"]]
    busy = [gpu for gpu in gpus if not gpu["is_idle"]]
    by_free = sorted(gpus, key=lambda gpu: gpu["memory_free_mb"], reverse=True)
    recommended = idle if idle else by_free[:1]

    info.update(
        {
            "accelerator": "cuda",
            "gpu_count": len(gpus),
            "gpu_models": sorted({gpu["model"] for gpu in gpus}),
            "gpu_ids": [gpu["id"] for gpu in gpus],
            "idle_gpu_ids": [gpu["id"] for gpu in idle],
            "busy_gpu_ids": [gpu["id"] for gpu in busy],
            "max_free_memory_gpu_id": by_free[0]["id"],
            "recommended_gpu_ids": [gpu["id"] for gpu in recommended],
            "recommended_parallel_gpus": len(recommended),
            "gpus": gpus,
            "notes": ["hardware_detected_by=nvidia-smi"],
        }
    )
    return info


def _parse_constraints(text: str, hardware: dict[str, Any]) -> dict[str, Any]:
    raw = (text or "").strip()
    low = raw.lower()
    constraints: dict[str, Any] = {
        "raw_text": raw,
        "time_budget_hours": None,
        "gpu_budget_count": None,
        "gpu_model_hint": None,
        "gpu_ids": [],
        "framework_hint": "PyTorch",
        "max_seeds": None,
        "prefer_open_source": True,
        "prefer_local_runnable": True,
        "allow_heavy_sota": True,
        "github_check_mode": None,
        "resource_mode": "auto-detected" if not raw else "user-specified+auto-detected",
    }

    for pattern, multiplier in [
        (r"(\d+(?:\.\d+)?)\s*(?:小时|h|hr|hrs|hour|hours)\b", 1),
        (r"(\d+(?:\.\d+)?)\s*(?:天|day|days)\b", 24),
        (r"(\d+(?:\.\d+)?)\s*(?:周|week|weeks)\b", 168),
    ]:
        match = re.search(pattern, low)
        if match:
            constraints["time_budget_hours"] = round(float(match.group(1)) * multiplier, 2)
            break

    gpu_count_match = re.search(
        r"(\d+)\s*[x×*]?\s*(?:张|块)?\s*(?:gpu|卡|a100|h100|v100|4090|3090|l40s|l40|t4)?",
        low,
    )
    if gpu_count_match and any(token in low for token in ["gpu", "卡", "4090", "3090", "a100", "h100"]):
        constraints["gpu_budget_count"] = int(gpu_count_match.group(1))

    for model in ["H100", "A100", "V100", "T4", "A10", "A6000", "L40S", "L40", "4090", "3090"]:
        if model.lower() in low:
            constraints["gpu_model_hint"] = model
            break

    for group in re.findall(r"(?:gpu|卡|id|ids|cuda)[:=\s]*(\d+(?:\s*[,，]\s*\d+)*)", low):
        constraints["gpu_ids"] += [int(x) for x in re.split(r"[,，]\s*", group) if x.isdigit()]
    constraints["gpu_ids"] = sorted(set(constraints["gpu_ids"]))

    if "tensorflow" in low:
        constraints["framework_hint"] = "TensorFlow"
    elif "jax" in low:
        constraints["framework_hint"] = "JAX"
    elif "huggingface" in low or "transformers" in low:
        constraints["framework_hint"] = "PyTorch+HuggingFace"

    mode_match = re.search(r"github\s*[:=]\s*(off|recommend|light_check|light|deep_check|deep)", low)
    if mode_match:
        mode = mode_match.group(1)
        constraints["github_check_mode"] = {
            "light": "light_check",
            "deep": "deep_check",
        }.get(mode, mode)

    if constraints["gpu_budget_count"] is None and hardware.get("gpu_count"):
        constraints["gpu_budget_count"] = hardware.get("recommended_parallel_gpus") or hardware.get("gpu_count")
    if not constraints["gpu_ids"] and hardware.get("recommended_gpu_ids"):
        constraints["gpu_ids"] = list(hardware["recommended_gpu_ids"])
    if constraints["gpu_model_hint"] is None and hardware.get("gpu_models"):
        constraints["gpu_model_hint"] = hardware["gpu_models"][0]

    hours = constraints.get("time_budget_hours")
    constraints["max_seeds"] = 1 if hours is not None and hours <= 12 else 3
    return constraints


def _capacity(constraints: dict[str, Any], hardware: dict[str, Any]) -> str:
    if hardware.get("accelerator") == "cpu" or not (constraints.get("gpu_budget_count") or hardware.get("gpu_count")):
        return "low"
    if (constraints.get("gpu_budget_count") or 0) >= 4 or (constraints.get("time_budget_hours") or 0) >= 72:
        return "high"
    if (constraints.get("gpu_budget_count") or 0) >= 2 or (constraints.get("time_budget_hours") or 0) >= 24:
        return "medium"
    return "low"


def _github_check_mode(constraints: dict[str, Any]) -> str:
    mode = constraints.get("github_check_mode") or os.getenv("WATSON_GITHUB_CHECK_MODE", "recommend")
    mode = str(mode).lower().strip()
    mode = {"light": "light_check", "deep": "deep_check"}.get(mode, mode)
    if mode not in {"off", "recommend", "light_check", "deep_check"}:
        return "recommend"
    return mode


# =============================================================================
# 6. Must-cite 校验
# =============================================================================


def _normalize_citations(
    item: dict[str, Any],
    valid_ids: set[str],
    title_to_id: dict[str, str],
    id_to_title: dict[str, str],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for citation in _as_list(item.get("citations")):
        if not isinstance(citation, dict):
            continue
        paper_id = str(citation.get("paper_id", "")).strip()
        title = str(citation.get("paper_title", "")).strip()
        if paper_id not in valid_ids and title:
            paper_id = title_to_id.get(title.lower().strip(), "")
        if paper_id in valid_ids:
            normalized.append(
                {
                    "paper_id": paper_id,
                    "paper_title": id_to_title.get(paper_id, title),
                    "evidence_type": str(citation.get("evidence_type", "related_method")),
                    "evidence": _truncate(citation.get("evidence", ""), 300),
                }
            )
    item["citations"] = normalized
    return normalized


def _must_cite(plan: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    valid_ids = {paper["paper_id"] for paper in evidence}
    title_to_id = {str(paper.get("title", "")).lower().strip(): paper["paper_id"] for paper in evidence}
    id_to_title = {paper["paper_id"]: paper.get("title", "") for paper in evidence}
    errors: list[str] = []

    for section in ["baseline_candidates", "dataset_candidates", "metric_candidates"]:
        for item in _as_list(plan.get(section)):
            if not isinstance(item, dict):
                continue
            citations = _normalize_citations(item, valid_ids, title_to_id, id_to_title)
            if citations:
                item["citation_status"] = "valid"
                item["usable_as_anchor"] = True
            elif section == "baseline_candidates" and bool(item.get("user_requested")):
                item["citation_status"] = "manual_pending"
                item["usable_as_anchor"] = False
                item["needs_human_confirm"] = True
                errors.append(f"{section}:{item.get('name', 'unknown')} was user-requested but has no Step1 citation")
            else:
                item["citation_status"] = "missing"
                item["usable_as_anchor"] = False
                errors.append(f"{section}:{item.get('name', 'unknown')} missing valid Step1 citation")

    hyperparameters = _as_dict(plan.get("hyperparameter_policy"))
    for parameter in _as_list(hyperparameters.get("parameters")):
        if not isinstance(parameter, dict):
            continue
        citations = _normalize_citations(parameter, valid_ids, title_to_id, id_to_title)
        source = str(parameter.get("source", "")).lower()
        if citations:
            parameter["citation_status"] = "valid"
        elif source in {"baseline_paper", "baseline_repo"}:
            parameter["citation_status"] = "missing"
            errors.append(f"hyperparameter:{parameter.get('name', 'unknown')} missing citation")
        else:
            parameter["citation_status"] = "not_required"

    report = plan.setdefault("validation_report", {})
    report["citation_errors"] = errors
    report["valid_paper_ids"] = sorted(valid_ids)
    plan["needs_human_confirm"] = sorted(
        set(map(str, _as_list(plan.get("needs_human_confirm")) + errors[:12]))
    )
    return plan


# =============================================================================
# 7. GitHub 代码库推荐与可选轻量探测
# =============================================================================


def _gh_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Watson-Experiment-Designer",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _gh_json(url: str, params: dict[str, Any] | None = None, timeout: int = 12) -> Any:
    try:
        response = requests.get(url, params=params, headers=_gh_headers(), timeout=timeout)
        return response.json() if response.status_code < 400 else None
    except Exception:
        return None


def _gh_text(url: str, timeout: int = 12) -> str:
    try:
        response = requests.get(url, headers=_gh_headers(), timeout=timeout)
        return response.text if response.status_code < 400 else ""
    except Exception:
        return ""


def _repo_full_name_from_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        if parsed.netloc.lower() != "github.com":
            return None
        parts = [part for part in parsed.path.split("/") if part]
        return f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else None
    except Exception:
        return None


def _repo_metadata_from_url(url: str) -> dict[str, Any]:
    full_name = _repo_full_name_from_url(url)
    metadata: dict[str, Any] = {
        "repo_full_name": full_name,
        "repo_url": url,
        "api_metadata_available": False,
    }
    if not full_name:
        return metadata
    data = _gh_json(f"{GITHUB_REPOS_API}/{full_name}")
    if isinstance(data, dict):
        metadata.update(
            {
                "repo_full_name": data.get("full_name") or full_name,
                "repo_url": data.get("html_url") or url,
                "repo_stars": int(data.get("stargazers_count") or 0),
                "repo_forks": int(data.get("forks_count") or 0),
                "repo_size_kb": int(data.get("size") or 0),
                "repo_language": data.get("language"),
                "repo_description": data.get("description") or "",
                "default_branch": data.get("default_branch") or "main",
                "updated_at": data.get("updated_at"),
                "archived": bool(data.get("archived", False)),
                "api_metadata_available": True,
            }
        )
    return metadata


def _search_repos(query: str) -> list[dict[str, Any]]:
    data = _gh_json(
        GITHUB_SEARCH_API,
        {"q": query, "sort": "stars", "order": "desc", "per_page": 4},
    )
    if not isinstance(data, dict):
        return []
    results: list[dict[str, Any]] = []
    for item in data.get("items", []):
        if isinstance(item, dict) and not item.get("archived"):
            results.append(
                {
                    "repo_full_name": item.get("full_name"),
                    "repo_url": item.get("html_url"),
                    "repo_stars": int(item.get("stargazers_count") or 0),
                    "repo_forks": int(item.get("forks_count") or 0),
                    "repo_size_kb": int(item.get("size") or 0),
                    "repo_language": item.get("language"),
                    "repo_description": item.get("description") or "",
                    "default_branch": item.get("default_branch") or "main",
                    "updated_at": item.get("updated_at"),
                    "source": "github_search",
                }
            )
    return results


def _repo_tree(full_name: str, branch: str) -> list[dict[str, Any]]:
    data = _gh_json(
        f"{GITHUB_REPOS_API}/{full_name}/git/trees/{branch}",
        {"recursive": "1"},
        timeout=20,
    )
    if isinstance(data, dict) and isinstance(data.get("tree"), list):
        return data["tree"][:5000]
    return []


def _readme_path(tree: list[dict[str, Any]]) -> str | None:
    nested: list[str] = []
    for node in tree:
        path = str(node.get("path", ""))
        low = path.lower()
        if "/" not in path and low.startswith("readme"):
            return path
        if low.endswith(("/readme.md", "/readme.rst", "/readme.txt")):
            nested.append(path)
    return sorted(nested, key=len)[0] if nested else None


def _readme_quality(text: str) -> dict[str, Any]:
    low = text.lower()
    groups = {
        "install": ["install", "pip install", "conda", "requirements", "environment"],
        "usage": ["usage", "quick start", "getting started", "run", "command"],
        "train": ["train", "training", "finetune", "fine-tune"],
        "evaluate": ["evaluate", "evaluation", "test", "benchmark"],
        "dataset": ["dataset", "data", "download"],
        "reproduce": ["reproduce", "checkpoint", "results", "pretrained"],
        "citation": ["citation", "bibtex", "cite"],
    }
    hits = {name: any(word in low for word in words) for name, words in groups.items()}
    code_blocks = len(re.findall(r"```", text)) // 2
    command_lines = len(
        re.findall(
            r"(?m)^\s*(python|pip|conda|bash|sh|CUDA_VISIBLE_DEVICES|torchrun)\b",
            text,
        )
    )
    quality_score = (
        (1 if len(text) >= 800 else 0)
        + (1 if len(text) >= 2000 else 0)
        + sum(hits.values())
        + (1 if code_blocks else 0)
        + (1 if command_lines else 0)
    )
    return {
        "readme_length": len(text),
        "readme_keyword_hits": hits,
        "readme_code_blocks": code_blocks,
        "readme_command_like_lines": command_lines,
        "readme_quality_score": int(quality_score),
    }


def _light_probe_repo(repo: dict[str, Any]) -> dict[str, Any]:
    full_name = str(repo.get("repo_full_name") or "")
    branch = str(repo.get("default_branch") or "main")
    tree = _repo_tree(full_name, branch) if full_name else []
    files = [node for node in tree if node.get("type") == "blob"]
    directories = [node for node in tree if node.get("type") == "tree"]
    readme_file = _readme_path(tree)
    readme_text = (
        _gh_text(f"https://raw.githubusercontent.com/{full_name}/{branch}/{readme_file}")
        if readme_file and full_name
        else ""
    )
    readme_info = _readme_quality(readme_text)

    stars = int(repo.get("repo_stars") or 0)
    size_kb = int(repo.get("repo_size_kb") or 0)
    star_score = 4 if stars >= 1000 else 3 if stars >= 300 else 2 if stars >= 50 else 1 if stars >= 10 else 0
    file_score = 2 if 10 <= len(files) <= 500 else 1 if len(files) >= 3 else 0
    size_score = 2 if 50 <= size_kb <= 300000 else 1 if size_kb >= 10 else 0
    score = min(readme_info["readme_quality_score"], 8) + star_score + file_score + size_score

    return {
        "mode": "light_check",
        "verified_runnable": False,
        "has_readme": bool(readme_file),
        "readme_path": readme_file,
        **readme_info,
        "repo_stars": stars,
        "repo_forks": int(repo.get("repo_forks") or 0),
        "repo_size_kb": size_kb,
        "tree_file_count": len(files),
        "tree_dir_count": len(directories),
        "feasibility_score": int(score),
        "feasibility_hint": "high" if score >= 11 else "medium" if score >= 7 else "low",
        "basis": "README content + stars + repository size + recursive file count",
        "note": "Lightweight feasibility probe only; not a reproducibility proof.",
    }


def _paper_code_repos_for_baseline(
    baseline: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    id_to_paper = {paper["paper_id"]: paper for paper in evidence}
    repositories: list[dict[str, Any]] = []
    for citation in _as_list(baseline.get("citations")):
        if not isinstance(citation, dict):
            continue
        paper_id = citation.get("paper_id")
        paper = id_to_paper.get(paper_id)
        if not paper:
            continue
        for url in _as_list(paper.get("code_urls")):
            if isinstance(url, str):
                repositories.append(
                    {
                        "url": url,
                        "source": "paper_code_link",
                        "from_paper_id": paper_id,
                        "note": "Directly extracted from cited Step1 paper metadata.",
                    }
                )
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for repository in repositories:
        if repository["url"] not in seen:
            seen.add(repository["url"])
            unique.append(repository)
    return unique


def _enrich_repositories(
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Recommend repositories with paper-code-link-first policy."""
    report: list[dict[str, Any]] = []
    allow_search = mode in {"recommend", "light_check", "deep_check"}
    allow_probe = mode in {"light_check", "deep_check"}

    for baseline in _as_list(plan.get("baseline_candidates")):
        if not isinstance(baseline, dict):
            continue

        existing = [x for x in _as_list(baseline.get("repo_candidates")) if isinstance(x, dict)]
        paper_repos = _paper_code_repos_for_baseline(baseline, evidence)

        raw_candidates: list[dict[str, Any]] = []
        for candidate in paper_repos + existing:
            url = candidate.get("url") or candidate.get("repo_url")
            if isinstance(url, str) and "github.com" in url:
                raw_candidates.append(
                    {
                        "url": url,
                        "source": candidate.get("source", "paper_code_link"),
                        "from_paper_id": candidate.get("from_paper_id"),
                        "note": candidate.get("note", ""),
                    }
                )

        seen_urls: set[str] = set()
        unique_candidates: list[dict[str, Any]] = []
        for candidate in raw_candidates:
            if candidate["url"] not in seen_urls:
                seen_urls.add(candidate["url"])
                unique_candidates.append(candidate)

        recommended: list[dict[str, Any]] = []

        # off/recommend 模式直接返回论文代码链接，不额外请求 API。
        for candidate in unique_candidates:
            repository: dict[str, Any] = {
                "repo_full_name": _repo_full_name_from_url(candidate["url"]),
                "repo_url": candidate["url"],
                "recommendation_source": candidate.get("source", "paper_code_link"),
                "from_paper_id": candidate.get("from_paper_id"),
                "confidence": "paper_provided_url",
                "verified_runnable": False,
                "note": "Paper-provided repository URL; not executed in Step2.",
            }
            if allow_probe:
                metadata = _repo_metadata_from_url(candidate["url"])
                repository.update(metadata)
                repository["recommendation_source"] = candidate.get("source", "paper_code_link")
                repository["from_paper_id"] = candidate.get("from_paper_id")
                repository["confidence"] = "paper_provided_url"
                repository["verified_runnable"] = False
                repository["repo_probe"] = _light_probe_repo(repository)
            recommended.append(repository)

        # 论文未提供链接时才搜索 GitHub。
        if not recommended and allow_search:
            query = str(baseline.get("open_source_query") or baseline.get("name") or "").strip()
            if query:
                for search_query in [f"{query} machine learning", f"{query} pytorch", query]:
                    repositories = _search_repos(search_query)
                    if repositories:
                        for repository in repositories[:3]:
                            repository.update(
                                {
                                    "recommendation_source": "github_search",
                                    "confidence": "metadata_only",
                                    "verified_runnable": False,
                                    "note": "GitHub metadata recommendation only; not executed in Step2.",
                                }
                            )
                            if allow_probe:
                                repository["repo_probe"] = _light_probe_repo(repository)
                            recommended.append(repository)
                        break

        baseline["github_check_mode"] = mode
        baseline["recommended_repositories"] = recommended
        baseline["recommended_repo"] = recommended[0] if recommended else None
        if recommended:
            baseline["repo_recommendation_status"] = recommended[0].get("recommendation_source", "recommended")
        else:
            baseline["repo_recommendation_status"] = "not_found_or_disabled"

        report.append(
            {
                "baseline": baseline.get("name"),
                "github_check_mode": mode,
                "effective_probe_mode": "light_check" if mode == "deep_check" else mode,
                "recommended_repositories": recommended,
                "status": baseline["repo_recommendation_status"],
            }
        )

    return plan, report


# =============================================================================
# 8. 数据集名称和本地缓存
# =============================================================================


def _dataset_variants(name: str, aliases: list[str] | None = None) -> list[str]:
    values = [name] + (aliases or [])
    variants: set[str] = set()
    for value in values:
        value = str(value or "").strip().lower()
        if not value:
            continue
        variants.update(
            [
                value,
                _slug(value),
                value.replace(" ", ""),
                value.replace("-", "_"),
                value.replace("_", "-"),
                value.split("/")[-1],
            ]
        )
        variants.update(token for token in re.split(r"[^a-zA-Z0-9]+", value) if len(token) >= 4)
    return sorted(variants)


def _data_dirs() -> list[Path]:
    home = Path.home()
    cwd = Path.cwd()
    return [
        cwd / "data",
        cwd / "datasets",
        cwd / ".cache",
        home / ".cache" / "huggingface" / "datasets",
        home / ".cache" / "huggingface" / "hub",
        home / ".cache" / "torch",
        home / ".cache",
        home / "data",
        home / "datasets",
    ]


def _dataset_cache(name: str, aliases: list[str] | None = None) -> dict[str, Any]:
    variants = _dataset_variants(name, aliases)
    hits: list[dict[str, Any]] = []
    searched: list[str] = []

    for base in _data_dirs():
        if not base.exists():
            continue
        searched.append(str(base))
        try:
            count = 0
            for child in base.rglob("*"):
                count += 1
                if count > 3000:
                    break
                path_text = str(child).lower()
                matched = [variant for variant in variants if variant and variant in path_text][:5]
                if matched:
                    hits.append(
                        {
                            "path": str(child),
                            "name": child.name,
                            "is_dir": child.is_dir(),
                            "is_file": child.is_file(),
                            "matched_variants": matched,
                        }
                    )
                    if len(hits) >= 10:
                        break
        except Exception:
            pass
        if len(hits) >= 10:
            break

    return {
        "dataset_name": name,
        "name_variants": variants[:20],
        "cached": bool(hits),
        "hits": hits,
        "searched_dirs": searched,
        "verification_note": "Name-based heuristic only; version and completeness are not verified.",
    }


def _enrich_datasets(plan: dict[str, Any]) -> dict[str, Any]:
    for dataset in _as_list(plan.get("dataset_candidates")):
        if not isinstance(dataset, dict):
            continue
        name = str(dataset.get("name") or "")
        aliases = [str(x) for x in _as_list(dataset.get("aliases"))]
        dataset["name_detection"] = {
            "canonical_name": name,
            "aliases": aliases,
            "variants": _dataset_variants(name, aliases)[:20],
        }
        dataset["local_cache"] = _dataset_cache(name, aliases)
        dataset.setdefault("storage_path_hint", f"data/{_slug(name)}")
    return plan


# =============================================================================
# 9. Schema 补全、baseline 选择和超参数建议
# =============================================================================


def _default_plan() -> dict[str, Any]:
    return {
        "schema_version": "2.5",
        "research_task": "",
        "method_family": "other",
        "hypothesis": "",
        "method_module_order": [],
        "baseline_candidates": [],
        "selected_baselines": [],
        "dropped_baselines": [],
        "dataset_candidates": [],
        "metric_candidates": [],
        "hyperparameter_policy": {
            "principle": "inherit cited baseline settings; use agent_suggested only when unknown",
            "parameters": [],
        },
        "experiment_matrix": {
            "mvp_plan": [],
            "main_plan": [],
            "ablation_plan": [],
            "diagnostic_plan": [],
        },
        "execution_plan": {
            "environment": {
                "framework": "PyTorch",
                "python_version": ">=3.10",
                "packages": [],
                "hardware_assumption": "",
            },
            "artifacts": {
                "results_json": "experiments/results.json",
                "run_log": ".watson/run_log.txt",
                "figures_dir": "paper/figures",
                "checkpoints_dir": "experiments/checkpoints",
            },
            "commands": [],
        },
        "iteration_hooks": {
            "what_to_record": [],
            "failure_signatures": [],
            "refine_rules": [],
            "pivot_rules": [],
        },
        "needs_human_confirm": [],
        "validation_report": {},
    }


def _merge_default(value: dict[str, Any]) -> dict[str, Any]:
    def merge(default: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        result = dict(default)
        for key, item in current.items():
            if isinstance(item, dict) and isinstance(result.get(key), dict):
                result[key] = merge(result[key], item)
            else:
                result[key] = item
        return result

    plan = merge(_default_plan(), value if isinstance(value, dict) else {})
    for field in [
        "baseline_candidates",
        "selected_baselines",
        "dropped_baselines",
        "dataset_candidates",
        "metric_candidates",
        "method_module_order",
        "needs_human_confirm",
    ]:
        if not isinstance(plan.get(field), list):
            plan[field] = []
    for field in ["mvp_plan", "main_plan", "ablation_plan", "diagnostic_plan"]:
        if not isinstance(plan["experiment_matrix"].get(field), list):
            plan["experiment_matrix"][field] = []
    if not isinstance(plan["execution_plan"].get("commands"), list):
        plan["execution_plan"]["commands"] = []
    return plan


def _select_baselines(plan: dict[str, Any]) -> dict[str, Any]:
    candidates = [x for x in _as_list(plan.get("baseline_candidates")) if isinstance(x, dict)]
    selected: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    for baseline in candidates:
        citations = _as_list(baseline.get("citations"))
        if citations:
            baseline["selection_status"] = (
                "candidate_with_repo" if baseline.get("recommended_repositories") else "candidate_no_repo"
            )
            baseline["selection_reason"] = (
                "valid Step1 citation and repository recommendation available"
                if baseline.get("recommended_repositories")
                else "valid Step1 citation; no repository recommendation found"
            )
        elif baseline.get("user_requested"):
            baseline["selection_status"] = "manual_pending_citation"
            baseline["selection_reason"] = "explicitly requested by user; citation requires confirmation"
            baseline["needs_human_confirm"] = True
        else:
            baseline["selection_status"] = "dropped"
            baseline["selection_reason"] = "missing valid Step1 citation"
            dropped.append(baseline)

    def pick(role: str) -> dict[str, Any] | None:
        role_items = [
            baseline
            for baseline in candidates
            if str(baseline.get("role", "")).lower() == role
            and baseline.get("selection_status") != "dropped"
        ]
        cited_with_repo = [
            baseline
            for baseline in role_items
            if baseline.get("citations") and baseline.get("recommended_repositories")
        ]
        cited = [baseline for baseline in role_items if baseline.get("citations")]
        return (cited_with_repo or cited or role_items or [None])[0]

    for role in ["classic", "strong", "sota", "open_source_alternative"]:
        chosen = pick(role)
        if chosen and chosen not in selected:
            chosen["selection_status"] = "selected"
            selected.append(chosen)

    # 用户可明确要求多个额外 baseline；保留这些对象，即使同一角色已有一个。
    for baseline in candidates:
        if baseline.get("user_requested") and baseline not in selected and baseline not in dropped:
            baseline["selection_status"] = "selected_manual_pending" if not baseline.get("citations") else "selected"
            selected.append(baseline)

    plan["selected_baselines"] = selected
    plan["dropped_baselines"] = dropped + [
        baseline for baseline in candidates if baseline not in selected and baseline not in dropped
    ]
    return plan


def _suggest_hparams(plan: dict[str, Any]) -> dict[str, Any]:
    policy = _as_dict(plan.get("hyperparameter_policy"))
    parameters = [x for x in _as_list(policy.get("parameters")) if isinstance(x, dict)]

    if not parameters:
        parameters = [
            {
                "name": "random_seed",
                "initial_value": "42",
                "source": "standard_default",
                "citations": [],
                "tunable": False,
                "search_space": "fixed",
                "fallback": "42",
                "confidence": "medium",
                "needs_human_confirm": False,
            },
            {
                "name": "learning_rate",
                "initial_value": "TBD",
                "source": "TBD",
                "citations": [],
                "tunable": True,
                "search_space": "TBD",
                "fallback": "Use the selected baseline implementation default if available.",
                "confidence": "low",
                "needs_human_confirm": True,
            },
        ]

    missing = [
        parameter
        for parameter in parameters
        if str(parameter.get("initial_value", "")).lower()
        in {"", "tbd", "unknown", "none", "null", "不确定"}
    ]

    if missing:
        raw = complete_chat(
            build_messages(
                HYPERPARAM_SYSTEM,
                _json(
                    {
                        "research_task": plan.get("research_task"),
                        "method_family": plan.get("method_family"),
                        "selected_baselines": plan.get("selected_baselines"),
                        "datasets": plan.get("dataset_candidates"),
                        "constraint_profile": plan.get("constraint_profile"),
                        "missing_parameters": missing,
                    }
                ),
            ),
            temperature=0.2,
            max_tokens=1800,
        )
        suggestions = {
            str(item.get("name", "")).lower(): item
            for item in _safe_json_list(raw)
        }
        for parameter in parameters:
            suggestion = suggestions.get(str(parameter.get("name", "")).lower())
            if suggestion:
                parameter.update(
                    {
                        "initial_value": suggestion.get("initial_value", parameter.get("initial_value")),
                        "source": suggestion.get("source", "agent_suggested"),
                        "search_space": suggestion.get("search_space", parameter.get("search_space")),
                        "fallback": suggestion.get("fallback", parameter.get("fallback")),
                        "confidence": suggestion.get("confidence", "low"),
                        "needs_human_confirm": True,
                        "agent_suggestion_rationale": suggestion.get("rationale", ""),
                    }
                )

    policy["parameters"] = parameters
    plan["hyperparameter_policy"] = policy
    needs = _as_list(plan.get("needs_human_confirm"))
    for parameter in parameters:
        if parameter.get("source") == "agent_suggested":
            needs.append(
                f"Hyperparameter `{parameter.get('name')}` is agent_suggested and should be confirmed."
            )
    plan["needs_human_confirm"] = sorted(set(map(str, needs)))
    return plan


# =============================================================================
# 10. 实验矩阵、命令计划和迭代历史
# =============================================================================


def _ensure_matrix_and_execution(
    plan: dict[str, Any],
    constraints: dict[str, Any],
    hardware: dict[str, Any],
) -> dict[str, Any]:
    baseline_names = [
        item.get("name")
        for item in _as_list(plan.get("selected_baselines"))
        if isinstance(item, dict)
    ]
    dataset_names = [
        item.get("name")
        for item in _as_list(plan.get("dataset_candidates"))
        if isinstance(item, dict)
    ]
    metric_names = [
        item.get("name")
        for item in _as_list(plan.get("metric_candidates"))
        if isinstance(item, dict)
    ]

    matrix = plan["experiment_matrix"]
    if not matrix.get("mvp_plan"):
        matrix["mvp_plan"] = [
            {
                "id": "mvp_01",
                "goal": "Verify data loading, model execution, metric computation, and result serialization.",
                "conditions": baseline_names[:1] + ["proposed_minimal"],
                "datasets": dataset_names[:1] or ["toy_subset"],
                "metrics": metric_names[:2] or ["primary_metric"],
                "max_runtime_hours": 2,
                "success_criteria": "The pipeline writes experiments/results.json without fatal errors.",
                "citations": [],
            }
        ]
    if not matrix.get("main_plan"):
        matrix["main_plan"] = [
            {
                "id": "main_01",
                "goal": "Fair comparison with selected must-cite baselines.",
                "conditions": baseline_names + ["proposed_method"],
                "datasets": dataset_names[:2] or ["main_dataset"],
                "metrics": metric_names or ["primary_metric"],
                "max_runtime_hours": constraints.get("time_budget_hours") or 8,
                "success_criteria": "The result supports or falsifies the main hypothesis.",
                "citations": [],
            }
        ]
    if not matrix.get("ablation_plan"):
        matrix["ablation_plan"] = [
            {
                "id": "abl_01",
                "goal": "Isolate the contribution of the core proposed module.",
                "conditions": ["proposed_full", "proposed_without_core_module"],
                "datasets": dataset_names[:1] or ["main_dataset"],
                "metrics": metric_names[:3] or ["primary_metric"],
                "max_runtime_hours": 4,
                "success_criteria": "Removing the module changes the primary or diagnostic metric.",
                "citations": [],
            }
        ]
    if not matrix.get("diagnostic_plan"):
        matrix["diagnostic_plan"] = [
            {
                "id": "diag_01",
                "goal": "Explain performance gains, failure cases, and efficiency trade-offs.",
                "conditions": ["proposed_method", "strongest_baseline"],
                "datasets": dataset_names[:1] or ["main_dataset"],
                "metrics": metric_names[:4] or ["primary_metric", "efficiency_metric"],
                "max_runtime_hours": 3,
                "success_criteria": "Produces interpretable subgroup, error, or efficiency analysis.",
                "citations": [],
            }
        ]

    execution = plan["execution_plan"]
    environment = execution["environment"]
    environment["framework"] = constraints.get("framework_hint") or environment.get("framework", "PyTorch")
    environment["hardware_assumption"] = (
        f"accelerator={hardware.get('accelerator')}; "
        f"gpu_model={constraints.get('gpu_model_hint')}; "
        f"gpu_ids={constraints.get('gpu_ids')}; "
        f"idle_gpu_ids={hardware.get('idle_gpu_ids')}"
    )

    if not execution.get("commands"):
        execution["commands"] = [
            {
                "id": "cmd_01",
                "name": "prepare_data",
                "cmd": "python experiments/experiment.py --stage prepare_data",
                "expected_outputs": ["data/<dataset>/"],
                "max_runtime_hours": 1,
                "depends_on": [],
            },
            {
                "id": "cmd_02",
                "name": "run_mvp",
                "cmd": "python experiments/experiment.py --stage mvp --output experiments/results.json",
                "expected_outputs": ["experiments/results.json"],
                "max_runtime_hours": 2,
                "depends_on": ["cmd_01"],
            },
            {
                "id": "cmd_03",
                "name": "run_main",
                "cmd": "python experiments/experiment.py --stage main --output experiments/results.json",
                "expected_outputs": ["experiments/results.json"],
                "max_runtime_hours": constraints.get("time_budget_hours") or 8,
                "depends_on": ["cmd_02"],
            },
            {
                "id": "cmd_04",
                "name": "run_ablation",
                "cmd": "python experiments/experiment.py --stage ablation --output experiments/results.json",
                "expected_outputs": ["experiments/results.json"],
                "max_runtime_hours": 4,
                "depends_on": ["cmd_03"],
            },
            {
                "id": "cmd_05",
                "name": "run_diagnostic",
                "cmd": "python experiments/experiment.py --stage diagnostic --output experiments/results.json",
                "expected_outputs": ["experiments/results.json", "paper/figures/"],
                "max_runtime_hours": 3,
                "depends_on": ["cmd_03"],
            },
        ]

    hooks = plan["iteration_hooks"]
    hooks.setdefault(
        "what_to_record",
        ["metrics", "runtime", "GPU id", "dataset path", "seed", "hyperparameters", "tracebacks"],
    )
    hooks.setdefault(
        "failure_signatures",
        ["NaN loss", "repository unavailable", "dataset mismatch", "metric mismatch", "out-of-memory"],
    )
    hooks.setdefault(
        "refine_rules",
        ["Tune only declared hyperparameters", "Use open-source alternative if the primary implementation fails"],
    )
    hooks.setdefault(
        "pivot_rules",
        ["Return to Step2 if no scientifically necessary baseline can be executed"],
    )
    return plan


def _download_plan(plan: dict[str, Any]) -> str:
    lines = ["# Download / Data Preparation Plan", ""]
    for dataset in _as_list(plan.get("dataset_candidates")):
        if not isinstance(dataset, dict):
            continue
        cache = _as_dict(dataset.get("local_cache"))
        detection = _as_dict(dataset.get("name_detection"))
        path = dataset.get("storage_path_hint", f"data/{_slug(dataset.get('name', 'dataset'))}")
        lines += [
            f"## {dataset.get('name', 'unknown')}",
            f"- Version: {dataset.get('version') or 'TBD'}",
            f"- Aliases: {', '.join(map(str, _as_list(dataset.get('aliases')))) or 'N/A'}",
            f"- Name variants: {', '.join(detection.get('variants', [])[:10])}",
            f"- Target path: `{path}`",
            f"- Cache detected: `{cache.get('cached', False)}`",
        ]
        for hit in _as_list(cache.get("hits"))[:5]:
            if isinstance(hit, dict):
                lines.append(f"  - `{hit.get('path')}` matched={hit.get('matched_variants')}")
        lines += [
            f"- Download hint: {dataset.get('download_hint') or 'TBD'}",
            f"- Suggested command: `python experiments/experiment.py --stage prepare_data --dataset \"{dataset.get('name')}\" --data_dir \"{path}\"`",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _iteration_context() -> dict[str, Any]:
    return {
        "has_previous_run": bool(S.load_run_log() or S.load_results() or S.load_analysis()),
        "run_log_tail": "\n".join((S.load_run_log() or "").splitlines()[-60:]),
        "results": _truncate(S.load_results(), 2400),
        "analysis": _truncate(S.load_analysis(), 2400),
    }


def _load_previous_plan() -> dict[str, Any]:
    data = _load_json_file(EXPERIMENT_JSON_FILE)
    return data if isinstance(data, dict) else {}


def _load_revision_history() -> list[dict[str, Any]]:
    data = _load_json_file(EXPERIMENT_REVISION_HISTORY_FILE)
    return data if isinstance(data, list) else []


def _record_revision(previous_plan: dict[str, Any], feedback: str, new_plan: dict[str, Any]) -> None:
    if not feedback.strip():
        return
    history = _load_revision_history()
    history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feedback": feedback.strip(),
            "previous_revision_round": _as_dict(previous_plan.get("revision")).get("round", 0),
            "new_revision_round": _as_dict(new_plan.get("revision")).get("round", 0),
            "previous_baselines": [
                item.get("name")
                for item in _as_list(previous_plan.get("selected_baselines"))
                if isinstance(item, dict)
            ],
            "new_baselines": [
                item.get("name")
                for item in _as_list(new_plan.get("selected_baselines"))
                if isinstance(item, dict)
            ],
            "previous_datasets": [
                item.get("name")
                for item in _as_list(previous_plan.get("dataset_candidates"))
                if isinstance(item, dict)
            ],
            "new_datasets": [
                item.get("name")
                for item in _as_list(new_plan.get("dataset_candidates"))
                if isinstance(item, dict)
            ],
        }
    )
    S.save_json(EXPERIMENT_REVISION_HISTORY_FILE, history[-30:])


# =============================================================================
# 11. 草案生成和最终总装
# =============================================================================


def _generate_draft(payload: dict[str, Any], revision_feedback: str) -> dict[str, Any]:
    if revision_feedback.strip():
        instruction = f"""这是一次实验方案修订任务。
请严格基于上一版 experiment_plan 和下面的用户意见重新生成完整 JSON，不要只输出差异。

用户修改意见：
{revision_feedback.strip()}

必须执行显式的增删要求；未被要求修改的内容尽量保留。"""
    else:
        instruction = "请根据以上 Step1 证据和约束生成第一版完整 experiment_plan JSON。"

    raw = complete_chat(
        build_messages_cached(
            EXTRACTION_SYSTEM,
            _json(payload),
            instruction,
        ),
        temperature=0.15,
        max_tokens=6500,
    )
    draft = _safe_json_dict(raw)

    # 第一次返回不是合法 JSON 时，用一个短修复请求重试。
    if not draft:
        repair_prompt = (
            "下面的输出没有被解析为 JSON。请只返回一个合法 JSON 对象，"
            "字段遵循 system schema，不要使用 Markdown。\n\n原始输出：\n"
            + _truncate(raw, 6000)
        )
        draft = _safe_json_dict(
            complete_chat(
                build_messages(EXTRACTION_SYSTEM, repair_prompt),
                temperature=0.0,
                max_tokens=6500,
            )
        )
    return draft


def _finalize(
    draft: dict[str, Any],
    evidence: list[dict[str, Any]],
    evidence_stats: dict[str, int],
    constraints: dict[str, Any],
    hardware: dict[str, Any],
    previous_plan: dict[str, Any],
    revision_feedback: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan = _merge_default(draft)
    current_round = int(_as_dict(previous_plan.get("revision")).get("round", 0) or 0)
    is_revision = bool(revision_feedback.strip())

    plan["_generated_at"] = datetime.now(timezone.utc).isoformat()
    plan["constraint_profile"] = constraints
    plan["local_hardware"] = hardware
    plan["paper_evidence"] = evidence
    plan["step1_evidence_stats"] = evidence_stats
    plan["step1_state_metrics"] = {
        key: S.load_state().get(key)
        for key in [
            "search_query",
            "relevant_total",
            "competitor_count",
            "background_count",
            "density",
            "avg_score",
            "avg_similarity",
            "max_similarity",
            "venue_fit_score",
            "venue_fit_label",
            "saturation_ratio",
            "saturation_label",
            "vitality_score",
            "vitality_label",
            "dimensions",
        ]
    }
    plan["resource_capacity"] = _capacity(constraints, hardware)
    plan["revision"] = {
        "is_revision": is_revision,
        "round": current_round + 1 if is_revision else current_round,
        "feedback": revision_feedback.strip(),
        "previous_plan_available": bool(previous_plan),
    }

    mode = _github_check_mode(constraints)
    plan["github_check_mode"] = mode

    plan = _must_cite(plan, evidence)
    plan, repo_report = _enrich_repositories(plan, evidence, mode)
    plan = _enrich_datasets(plan)
    plan = _select_baselines(plan)
    plan = _suggest_hparams(plan)
    plan = _ensure_matrix_and_execution(plan, constraints, hardware)

    validation = plan.setdefault("validation_report", {})
    validation["github_check_mode"] = mode
    validation["must_cite_baseline_count"] = sum(
        1
        for item in _as_list(plan.get("selected_baselines"))
        if isinstance(item, dict) and item.get("citations")
    )
    validation["manual_pending_baseline_count"] = sum(
        1
        for item in _as_list(plan.get("selected_baselines"))
        if isinstance(item, dict) and item.get("user_requested") and not item.get("citations")
    )
    validation["repository_recommended_baseline_count"] = sum(
        1
        for item in _as_list(plan.get("selected_baselines"))
        if isinstance(item, dict) and item.get("recommended_repositories")
    )
    validation["idle_gpu_ids"] = hardware.get("idle_gpu_ids")
    validation["recommended_gpu_ids"] = hardware.get("recommended_gpu_ids")
    validation["is_executable_plan_ready"] = bool(
        _as_list(_as_dict(plan.get("execution_plan")).get("commands"))
    )
    return plan, repo_report


# =============================================================================
# 12. Public entry point
# =============================================================================


def run(
    extra_constraints: str = "",
    revision_feedback: str = "",
    regenerate: bool = False,
) -> Generator[str, None, None]:
    """Generate or revise the Step2 experiment design.

    Parameters
    ----------
    extra_constraints:
        User-provided hardware, time, framework, or GitHub-mode constraints.
    revision_feedback:
        Natural-language requests such as adding/removing baselines, datasets,
        metrics, or ablation settings.
    regenerate:
        Kept for explicit UI semantics and backward compatibility. A non-empty
        ``revision_feedback`` automatically activates revision mode.
    """
    del regenerate  # revision mode is determined by revision_feedback.

    idea = S.load_idea()
    if not idea:
        yield "❌ 请先完成 Step 1（Idea Validation）。\n"
        return

    assessment = S.load_idea_assessment()
    step1_papers, step1_stats = _load_step1_papers()
    previous_plan = _load_previous_plan()
    revision_mode = bool(revision_feedback.strip())

    yield "🔍 **Step2.1 解析约束并探测本地 GPU / CPU 资源**\n\n"
    hardware = _detect_local_hardware()
    constraints = _parse_constraints(extra_constraints, hardware)
    mode = _github_check_mode(constraints)
    yield "```json\n" + _json(
        {
            "resource_capacity": _capacity(constraints, hardware),
            "github_check_mode": mode,
            "constraint_profile": constraints,
            "gpu_summary": {
                "accelerator": hardware.get("accelerator"),
                "gpu_count": hardware.get("gpu_count"),
                "gpu_models": hardware.get("gpu_models"),
                "gpu_ids": hardware.get("gpu_ids"),
                "idle_gpu_ids": hardware.get("idle_gpu_ids"),
                "busy_gpu_ids": hardware.get("busy_gpu_ids"),
                "max_free_memory_gpu_id": hardware.get("max_free_memory_gpu_id"),
                "recommended_gpu_ids": hardware.get("recommended_gpu_ids"),
            },
            "gpus": hardware.get("gpus"),
        }
    ) + "\n```\n\n"

    yield "📚 **Step2.2 适配新版 Step1，并构造 must-cite evidence pack**\n\n"
    evidence = _evidence_pack(step1_papers)
    code_link_count = sum(len(_as_list(paper.get("code_urls"))) for paper in evidence)
    yield f"- Step1 顶级候选论文：{step1_stats.get('top_annotated_count', 0)} 篇\n"
    yield f"- Step1 全部相关论文：{step1_stats.get('all_relevant_count', 0)} 篇\n"
    yield f"- 去重后可用论文：{step1_stats.get('deduplicated_count', 0)} 篇\n"
    yield f"- 进入 Step2 evidence pack：{len(evidence)} 篇\n"
    yield f"- Competitor / Background：{step1_stats.get('competitor_count', 0)} / {step1_stats.get('background_count', 0)}\n"
    yield f"- 从 Step1 元数据直接抽取 GitHub 链接：{code_link_count} 个\n\n"

    if not evidence:
        yield "⚠️ 未获得 Step1 论文证据；所有 baseline 均需要人工确认。\n\n"
    if _iteration_context().get("has_previous_run"):
        yield "♻️ **检测到 Step4/Step5 历史结果，本轮设计会包含迭代上下文。**\n\n"
    if revision_mode:
        yield "📝 **检测到用户修订意见，将在上一版方案基础上重新生成完整实验计划。**\n\n"
        yield f"> {revision_feedback.strip()}\n\n"

    yield "🧠 **Step2.3 单 Agent 生成结构化实验设计草案**\n\n"
    payload = {
        "idea": idea,
        "idea_assessment": _truncate(assessment, 2600),
        "step1_state_metrics": S.load_state(),
        "paper_evidence": evidence,
        "paper_evidence_stats": step1_stats,
        "constraint_profile": constraints,
        "local_hardware": hardware,
        "github_check_mode": mode,
        "iteration_context": _iteration_context(),
        "previous_experiment_plan": previous_plan if revision_mode else {},
        "revision_feedback": revision_feedback.strip(),
    }
    draft = _generate_draft(payload, revision_feedback)
    if not draft:
        yield "⚠️ Agent 未返回可解析 JSON，将使用默认 schema 继续生成，并标记人工确认。\n\n"
        draft = _default_plan()
        draft["needs_human_confirm"] = ["The LLM draft could not be parsed; regenerate Step2."]

    yield "🧪 **Step2.4 校验引用、推荐代码库、检测数据并补全执行计划**\n\n"
    plan, repo_report = _finalize(
        draft,
        evidence,
        step1_stats,
        constraints,
        hardware,
        previous_plan,
        revision_feedback,
    )

    preview = {
        "revision": plan.get("revision"),
        "github_check_mode": mode,
        "step1_evidence_stats": step1_stats,
        "must_cite_baseline_count": _as_dict(plan.get("validation_report")).get("must_cite_baseline_count"),
        "manual_pending_baseline_count": _as_dict(plan.get("validation_report")).get("manual_pending_baseline_count"),
        "repository_recommended_baseline_count": _as_dict(plan.get("validation_report")).get("repository_recommended_baseline_count"),
        "selected_baselines": [
            {
                "name": baseline.get("name"),
                "role": baseline.get("role"),
                "citations": [
                    citation.get("paper_id")
                    for citation in _as_list(baseline.get("citations"))
                    if isinstance(citation, dict)
                ],
                "user_requested": baseline.get("user_requested", False),
                "repo_status": baseline.get("repo_recommendation_status"),
                "recommended_repo": _as_dict(baseline.get("recommended_repo")).get("repo_url"),
                "verified_runnable": _as_dict(baseline.get("recommended_repo")).get("verified_runnable"),
                "selection_status": baseline.get("selection_status"),
            }
            for baseline in _as_list(plan.get("selected_baselines"))
            if isinstance(baseline, dict)
        ],
        "datasets": [
            {
                "name": dataset.get("name"),
                "version": dataset.get("version"),
                "cached": _as_dict(dataset.get("local_cache")).get("cached"),
                "storage_path": dataset.get("storage_path_hint"),
            }
            for dataset in _as_list(plan.get("dataset_candidates"))[:8]
            if isinstance(dataset, dict)
        ],
        "hyperparameters": _as_dict(plan.get("hyperparameter_policy")).get("parameters", [])[:10],
        "execution_commands": [
            {"id": command.get("id"), "cmd": command.get("cmd")}
            for command in _as_list(_as_dict(plan.get("execution_plan")).get("commands"))
            if isinstance(command, dict)
        ],
        "needs_human_confirm": _as_list(plan.get("needs_human_confirm"))[:12],
    }
    yield "```json\n" + _json(preview) + "\n```\n\n"

    yield "✍️ **Step2.5 生成最终 experiment.md 和机器可读 sidecar 文件**\n\n"
    markdown = ""
    for chunk in stream_chat(
        build_messages_cached(
            MARKDOWN_SYSTEM,
            _json(plan),
            "请依据上述最终 JSON 生成完整 experiment.md。",
        ),
        temperature=0.2,
        max_tokens=6000,
    ):
        markdown += chunk
        yield chunk

    if "## Structured Appendix" not in markdown:
        markdown = markdown.rstrip() + "\n\n## Structured Appendix\n\n```json\n" + _json(plan) + "\n```\n"

    S.save_file(EXPERIMENT_FILE, markdown.rstrip() + "\n")
    S.save_json(EXPERIMENT_JSON_FILE, plan)
    S.save_json(EXPERIMENT_EVIDENCE_FILE, evidence)
    S.save_json(EXPERIMENT_REPO_REPORT_FILE, repo_report)
    S.save_file(DOWNLOAD_DATA_PLAN_FILE, _download_plan(plan))
    _record_revision(previous_plan, revision_feedback, plan)

    S.save_state(
        {
            "last_step": "experiment",
            "experiment_schema_version": plan.get("schema_version", "2.5"),
            "experiment_revision_round": _as_dict(plan.get("revision")).get("round", 0),
            "experiment_last_feedback": revision_feedback.strip(),
            "experiment_approved": False,
            "experiment_stale": False,
            "downstream_stale": True,
            "experiment_resource_capacity": plan.get("resource_capacity"),
            "experiment_github_check_mode": mode,
            "experiment_gpu_ids": constraints.get("gpu_ids"),
            "experiment_idle_gpu_ids": hardware.get("idle_gpu_ids"),
            "experiment_gpu_models": hardware.get("gpu_models"),
            "experiment_must_cite_baseline_count": _as_dict(plan.get("validation_report")).get("must_cite_baseline_count", 0),
            "experiment_repository_recommended_baseline_count": _as_dict(plan.get("validation_report")).get("repository_recommended_baseline_count", 0),
            "experiment_plan_file": str(EXPERIMENT_JSON_FILE),
        }
    )

    yield "\n\n✅ **Step2 完成，可在页面底部填写修改意见或确认进入 Step3。**\n\n"
    yield (
        f"- Markdown: `{EXPERIMENT_FILE}`\n"
        f"- Machine-readable plan: `{EXPERIMENT_JSON_FILE}`\n"
        f"- Evidence pack: `{EXPERIMENT_EVIDENCE_FILE}`\n"
        f"- Repository report: `{EXPERIMENT_REPO_REPORT_FILE}`\n"
        f"- Data plan: `{DOWNLOAD_DATA_PLAN_FILE}`\n"
        f"- Revision history: `{EXPERIMENT_REVISION_HISTORY_FILE}`\n"
    )
