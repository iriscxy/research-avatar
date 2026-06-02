"""Watson Step 2：实验设计 Agent（中文批注版）

这是 `watson/agents/experiment.py` 的完整替换文件。

设计目标：
1. 不修改 Step1，只读取 Step1 已经产生的 idea、papers、idea_assessment。
2. 保持原 Watson 接口不变：run(extra_constraints: str = "")。
3. 默认仍然生成 `.watson/experiment.md`，兼容原 Step3。
4. 额外生成机器可读 sidecar 文件，供后续 Step3/4/5 可选使用。
5. GitHub 代码库处理采用“可选探测模式”：
   - off：不访问 GitHub API，只抽取论文/摘要里已有的 GitHub 链接。
   - recommend：默认模式。优先返回论文中给出的代码链接；没有则用 GitHub 搜索推荐 repo，只记录元数据，不做健康评估。
   - light_check：在 recommend 基础上读取 README、stars、仓库大小、文件数量，给出轻量可行性提示。
   - deep_check：当前按 light_check 处理，不承诺完整阅读或验证整个代码库。

核心思想：Step2 负责“实验设计与代码库推荐”，不默认声称 repo 一定可运行；真正运行验证留给 Step3/Step4。
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Generator
from urllib.parse import urlparse

import requests

from ..config import EXPERIMENT_FILE, WATSON_DIR
from ..llm import build_messages, complete_chat, stream_chat
from .. import state as S


# =============================================================================
# 1. 输出文件路径
# =============================================================================

EXPERIMENT_JSON_FILE = WATSON_DIR / "experiment_plan.json"
EXPERIMENT_EVIDENCE_FILE = WATSON_DIR / "experiment_evidence.json"
EXPERIMENT_REPO_REPORT_FILE = WATSON_DIR / "experiment_repo_report.json"
DOWNLOAD_DATA_PLAN_FILE = WATSON_DIR / "download_data_plan.md"

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_REPOS_API = "https://api.github.com/repos"


# =============================================================================
# 2. Prompt：让 LLM 做结构化实验设计抽取
# =============================================================================

EXTRACTION_SYSTEM = """你是 Watson Step2 实验设计抽取器。请只输出严格 JSON，不要输出 Markdown。

你会收到：
1. 已验证的研究 idea；
2. Step1 检索到的 paper evidence pack，每篇论文都有 paper_id 和可能的 code_urls；
3. 用户硬件/时间约束；
4. 本地 GPU/CPU 资源探测结果；
5. 若存在，上一轮运行/分析结果。

任务：把研究 idea 转换成结构化实验设计草案。

硬性要求：
- baseline、dataset、metric、hyperparameter 尽可能引用 paper_id。
- 不得引用 evidence pack 中不存在的 paper_id。
- baseline 分为 classic / strong / sota / open_source_alternative。
- 不要因为计算资源太重删除 baseline；资源信息只作为执行提醒。
- 每个 baseline 给出 open_source_query。
- 如果某篇 cited paper 的 code_urls 非空，优先把它作为 repo_candidates。
- 数据集必须包含 name、aliases、download_hint、preprocessing、storage_path_hint。
- 超参数优先继承 baseline_paper / baseline_repo；不知道就写 TBD。
- 必须生成 experiment_matrix：mvp_plan / main_plan / ablation_plan / diagnostic_plan。
- 必须生成 execution_plan.commands，供 Step3 生成代码参考。
- 不确定的信息写入 needs_human_confirm，不要编造。

输出 JSON 顶层 schema：
{
  "schema_version": "2.4",
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
          "evidence": "short text"
        }
      ],
      "why_relevant": "string",
      "expected_comparison_value": "string",
      "compute_level": "low|medium|high",
      "open_source_query": "string",
      "repo_candidates": [
        {
          "url": "https://github.com/...",
          "source": "paper_code_link|github_search|manual|unknown",
          "from_paper_id": "P001",
          "note": "string"
        }
      ],
      "fallback_if_unavailable": "string",
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
    "parameters": []
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

你会收到当前 experiment_plan.json 和缺失初始值的超参数列表。
请为 TBD/unknown/空值的参数给出建议。

要求：
- source 必须是 agent_suggested 或 standard_default。
- 不要声称这些值来自论文，除非输入中已有 citations。
- confidence 只能是 low 或 medium。
- needs_human_confirm 必须是 true。
- search_space 给出小范围搜索空间，适合 MVP / main 实验。
- 输出 JSON 数组，不要 Markdown。
"""

MARKDOWN_SYSTEM = """你是 Watson Step2 实验设计报告生成器。
请把 experiment_plan.json 转写成人类可读的 experiment.md。

要求：
- 中文输出。
- 风格接近 KDD/ACL/ICLR 系统方法部分。
- baseline 部分必须显示 paper_id，例如 [P003]。
- 代码库部分要区分：
  1. paper_code_link：论文中直接给出的代码链接；
  2. github_search：GitHub API 推荐的代码库；
  3. light_probe：轻量 README/metadata 探测结果。
- 明确说明：repo 推荐不等于已经验证可运行，真正运行验证留给 Step3/Step4。
- 最后加 Structured Appendix，贴出最终 JSON。

必须包含标题：
# Experiment Design
## 1. Problem Framing
## 2. Local Resource Profile
## 3. Must-Cite Baseline Retrieval
## 4. Code Repository Recommendation
## 5. Dataset Name and Cache Detection
## 6. Metric Plan
## 7. Executable Experimental Matrix
## 8. Baseline-Anchored Hyperparameter Initialization
## 9. Execution Plan for Step 3/4
## 10. Iteration Hooks for Step 5
## 11. Risks and Human Checks
## Structured Appendix
"""


# =============================================================================
# 3. 通用工具函数
# =============================================================================

def _json(data: Any) -> str:
    """把 Python 对象转成美观 JSON 字符串。"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def _as_list(x: Any) -> list[Any]:
    """如果 x 不是 list，则返回空 list，避免后续循环报错。"""
    return x if isinstance(x, list) else []


def _as_dict(x: Any) -> dict[str, Any]:
    """如果 x 不是 dict，则返回空 dict，避免 .get 报错。"""
    return x if isinstance(x, dict) else {}


def _safe_json_dict(text: str) -> dict[str, Any]:
    """从 LLM 输出中尽量解析 JSON dict。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        candidates.append(match.group(0))
    for cand in candidates:
        if not cand:
            continue
        try:
            obj = json.loads(cand)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
    return {}


def _safe_json_list(text: str) -> list[dict[str, Any]]:
    """从 LLM 输出中尽量解析 JSON list。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\[.*\]", text, re.S)
    if match:
        candidates.append(match.group(0))
    for cand in candidates:
        if not cand:
            continue
        try:
            obj = json.loads(cand)
            return [x for x in obj if isinstance(x, dict)] if isinstance(obj, list) else []
        except Exception:
            pass
    return []


def _truncate(x: Any, n: int) -> str:
    """截断长文本，避免 prompt 太长。"""
    s = "" if x is None else str(x).replace("\x00", "")
    return s if len(s) <= n else s[:n] + "..."


def _slug(s: str) -> str:
    """把文本转成适合文件路径的短 slug。"""
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", str(s).lower()).strip("_")
    return s[:80] or "unknown"


def _run_cmd(cmd: list[str], timeout: int = 8) -> tuple[int, str]:
    """安全运行系统命令，例如 nvidia-smi。"""
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 1, str(e)


def _memory_gb() -> float | None:
    """获取本机内存大小。psutil 不存在时返回 None。"""
    try:
        import psutil  # type: ignore
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return None


# =============================================================================
# 4. 论文代码链接抽取：优先使用论文自己提供的 GitHub 链接
# =============================================================================

def _extract_github_urls(text: str) -> list[str]:
    """从任意文本中抽取 GitHub 仓库 URL。"""
    if not text:
        return []
    pattern = r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?"
    urls = re.findall(pattern, text)
    cleaned: list[str] = []
    for url in urls:
        url = url.rstrip(").,;，。；、")
        parts = urlparse(url)
        path_parts = [p for p in parts.path.split("/") if p]
        if len(path_parts) >= 2:
            normalized = f"https://github.com/{path_parts[0]}/{path_parts[1]}"
            if normalized not in cleaned:
                cleaned.append(normalized)
    return cleaned


def _collect_paper_text_for_code_urls(p: dict[str, Any]) -> str:
    """把论文 dict 中可能包含代码链接的字段拼起来。"""
    fields = [
        "title", "summary", "abstract", "relevance", "difference", "link", "url",
        "paper_url", "project_url", "code_url", "github", "repo", "repository",
    ]
    parts: list[str] = []
    for key in fields:
        value = p.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif isinstance(value, dict):
            parts.append(_json(value))
    return "\n".join(parts)


# =============================================================================
# 5. 本地硬件与用户约束解析
# =============================================================================

def _detect_local_hardware() -> dict[str, Any]:
    """检测本地 CPU/GPU，包含 GPU 型号、空闲 GPU id、推荐 GPU id。"""
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

    rc, out = _run_cmd(
        [
            nvidia_smi,
            "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ],
        timeout=10,
    )
    if rc != 0 or not out:
        info["notes"].append(f"nvidia-smi failed: {out[:200]}")
        return info

    gpus: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 9:
            continue

        def to_i(v: str, default: int = 0) -> int:
            try:
                return int(float(v))
            except Exception:
                return default

        gid = to_i(parts[0], len(gpus))
        total = to_i(parts[3])
        used = to_i(parts[4])
        free = to_i(parts[5])
        util = to_i(parts[6], 100)
        ratio = free / total if total else 0.0
        gpus.append(
            {
                "id": gid,
                "uuid": parts[1],
                "model": parts[2],
                "memory_total_mb": total,
                "memory_used_mb": used,
                "memory_free_mb": free,
                "memory_free_ratio": round(ratio, 3),
                "utilization_gpu_percent": util,
                "temperature_c": to_i(parts[7]),
                "power_draw_w": parts[8],
                "is_idle": bool(total and ratio >= 0.55 and util <= 30),
            }
        )

    if not gpus:
        return info

    idle = [g for g in gpus if g["is_idle"]]
    busy = [g for g in gpus if not g["is_idle"]]
    by_free = sorted(gpus, key=lambda g: g["memory_free_mb"], reverse=True)
    recommended = idle if idle else by_free[:1]

    info.update(
        {
            "accelerator": "cuda",
            "gpu_count": len(gpus),
            "gpu_models": sorted({g["model"] for g in gpus}),
            "gpu_ids": [g["id"] for g in gpus],
            "idle_gpu_ids": [g["id"] for g in idle],
            "busy_gpu_ids": [g["id"] for g in busy],
            "max_free_memory_gpu_id": by_free[0]["id"],
            "recommended_gpu_ids": [g["id"] for g in recommended],
            "recommended_parallel_gpus": len(recommended),
            "gpus": gpus,
            "notes": ["hardware_detected_by=nvidia-smi"],
        }
    )
    return info


def _parse_constraints(text: str, hardware: dict[str, Any]) -> dict[str, Any]:
    """解析用户在 Step2 输入框里写的约束。"""
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

    for pat, mul in [
        (r"(\d+(?:\.\d+)?)\s*(?:小时|h|hr|hrs|hour|hours)\b", 1),
        (r"(\d+(?:\.\d+)?)\s*(?:天|day|days)\b", 24),
        (r"(\d+(?:\.\d+)?)\s*(?:周|week|weeks)\b", 168),
    ]:
        m = re.search(pat, low)
        if m:
            constraints["time_budget_hours"] = round(float(m.group(1)) * mul, 2)
            break

    m = re.search(r"(\d+)\s*[x×*]?\s*(?:张|块)?\s*(?:gpu|卡|a100|h100|v100|4090|3090|l40s|l40|t4)?", low)
    if m and ("gpu" in low or "卡" in low or "4090" in low or "3090" in low or "a100" in low):
        constraints["gpu_budget_count"] = int(m.group(1))

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
        constraints["github_check_mode"] = {"light": "light_check", "deep": "deep_check"}.get(mode, mode)

    if constraints["gpu_budget_count"] is None and hardware.get("gpu_count"):
        constraints["gpu_budget_count"] = hardware.get("recommended_parallel_gpus") or hardware.get("gpu_count")
    if not constraints["gpu_ids"] and hardware.get("recommended_gpu_ids"):
        constraints["gpu_ids"] = list(hardware["recommended_gpu_ids"])
    if constraints["gpu_model_hint"] is None and hardware.get("gpu_models"):
        constraints["gpu_model_hint"] = hardware["gpu_models"][0]

    constraints["max_seeds"] = 1 if (constraints.get("time_budget_hours") or 0) <= 12 else 3
    return constraints


def _capacity(constraints: dict[str, Any], hardware: dict[str, Any]) -> str:
    """粗略资源档位。这里只记录，不用于删除 baseline。"""
    if hardware.get("accelerator") == "cpu" or not (constraints.get("gpu_budget_count") or hardware.get("gpu_count")):
        return "low"
    if (constraints.get("gpu_budget_count") or 0) >= 4 or (constraints.get("time_budget_hours") or 0) >= 72:
        return "high"
    if (constraints.get("gpu_budget_count") or 0) >= 2 or (constraints.get("time_budget_hours") or 0) >= 24:
        return "medium"
    return "low"


def _github_check_mode(constraints: dict[str, Any]) -> str:
    """确定 GitHub 检查模式。默认 recommend。"""
    mode = constraints.get("github_check_mode") or os.getenv("WATSON_GITHUB_CHECK_MODE", "recommend")
    mode = str(mode).lower().strip()
    mode = {"light": "light_check", "deep": "deep_check"}.get(mode, mode)
    return mode if mode in {"off", "recommend", "light_check", "deep_check"} else "recommend"


# =============================================================================
# 6. Step1 论文 evidence pack
# =============================================================================

def _evidence_pack(papers: list[dict[str, Any]], limit: int = 18) -> list[dict[str, Any]]:
    """把 Step1 论文列表变成带 paper_id 和 code_urls 的 evidence pack。"""
    def key(p: dict[str, Any]) -> tuple[Any, ...]:
        try:
            year = int(str(p.get("published", ""))[:4])
        except Exception:
            year = 0
        return (0 if p.get("is_top_conf") else 1, -(p.get("relevance_score") or 0), -year, p.get("title", ""))

    evidence = []
    for i, p in enumerate(sorted(papers, key=key)[:limit], 1):
        code_urls = _extract_github_urls(_collect_paper_text_for_code_urls(p))
        evidence.append(
            {
                "paper_id": f"P{i:03d}",
                "title": p.get("title", ""),
                "venue": p.get("venue", ""),
                "published": p.get("published", ""),
                "summary": _truncate(p.get("summary", ""), 700),
                "relevance_score": p.get("relevance_score"),
                "relevance": _truncate(p.get("relevance", ""), 320),
                "difference": _truncate(p.get("difference", ""), 320),
                "link": p.get("link", ""),
                "pdf": p.get("pdf", ""),
                "is_top_conf": bool(p.get("is_top_conf", False)),
                "code_urls": code_urls,
            }
        )
    return evidence


# =============================================================================
# 7. Citation 校验
# =============================================================================

def _normalize_citations(item: dict[str, Any], valid_ids: set[str], title_to_id: dict[str, str], id_to_title: dict[str, str]) -> list[dict[str, Any]]:
    """规范化 item.citations，并删除无效 paper_id。"""
    normalized = []
    for c in _as_list(item.get("citations")):
        if not isinstance(c, dict):
            continue
        pid = str(c.get("paper_id", "")).strip()
        title = str(c.get("paper_title", "")).strip()
        if pid not in valid_ids and title:
            pid = title_to_id.get(title.lower().strip(), "")
        if pid in valid_ids:
            normalized.append(
                {
                    "paper_id": pid,
                    "paper_title": id_to_title.get(pid, title),
                    "evidence_type": str(c.get("evidence_type", "related_method")),
                    "evidence": _truncate(c.get("evidence", ""), 260),
                }
            )
    item["citations"] = normalized
    return normalized


def _must_cite(plan: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """强制 baseline/dataset/metric 引用 Step1 evidence 里的合法 paper_id。"""
    valid_ids = {p["paper_id"] for p in evidence}
    title_to_id = {p.get("title", "").lower().strip(): p["paper_id"] for p in evidence}
    id_to_title = {p["paper_id"]: p.get("title", "") for p in evidence}
    errors = []

    for section in ["baseline_candidates", "dataset_candidates", "metric_candidates"]:
        for item in _as_list(plan.get(section)):
            if not isinstance(item, dict):
                continue
            cites = _normalize_citations(item, valid_ids, title_to_id, id_to_title)
            item["citation_status"] = "valid" if cites else "missing"
            item["usable_as_anchor"] = bool(cites)
            if not cites:
                errors.append(f"{section}:{item.get('name', 'unknown')} missing valid Step1 citation")

    hp = _as_dict(plan.get("hyperparameter_policy"))
    for param in _as_list(hp.get("parameters")):
        if isinstance(param, dict):
            cites = _normalize_citations(param, valid_ids, title_to_id, id_to_title)
            source = str(param.get("source", "")).lower()
            if cites:
                param["citation_status"] = "valid"
            elif source in {"baseline_paper", "baseline_repo"}:
                param["citation_status"] = "missing"
                errors.append(f"hyperparameter:{param.get('name', 'unknown')} missing citation")
            else:
                param["citation_status"] = "not_required"

    report = plan.setdefault("validation_report", {})
    report["citation_errors"] = errors
    report["valid_paper_ids"] = sorted(valid_ids)
    plan["needs_human_confirm"] = sorted(set(map(str, _as_list(plan.get("needs_human_confirm")) + errors[:8])))
    return plan


# =============================================================================
# 8. GitHub 推荐与可选轻量探测
# =============================================================================

def _gh_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Watson-Experiment-Designer"}
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
        parts = [p for p in parsed.path.split("/") if p]
        return f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else None
    except Exception:
        return None


def _repo_metadata_from_url(url: str) -> dict[str, Any]:
    """根据论文直接给出的 GitHub URL 尝试获取元数据；失败也保留 URL。"""
    full_name = _repo_full_name_from_url(url)
    metadata: dict[str, Any] = {
        "repo_full_name": full_name,
        "repo_url": url,
        "source": "paper_code_link",
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
    """用 GitHub Search API 推荐候选 repo。推荐不等于验证可运行。"""
    data = _gh_json(GITHUB_SEARCH_API, {"q": query, "sort": "stars", "order": "desc", "per_page": 4})
    if not isinstance(data, dict):
        return []
    repos = []
    for x in data.get("items", []):
        if isinstance(x, dict) and not x.get("archived"):
            repos.append(
                {
                    "repo_full_name": x.get("full_name"),
                    "repo_url": x.get("html_url"),
                    "repo_stars": int(x.get("stargazers_count") or 0),
                    "repo_forks": int(x.get("forks_count") or 0),
                    "repo_size_kb": int(x.get("size") or 0),
                    "repo_language": x.get("language"),
                    "repo_description": x.get("description") or "",
                    "default_branch": x.get("default_branch") or "main",
                    "updated_at": x.get("updated_at"),
                    "source": "github_search",
                }
            )
    return repos


def _repo_tree(full_name: str, branch: str) -> list[dict[str, Any]]:
    data = _gh_json(f"{GITHUB_REPOS_API}/{full_name}/git/trees/{branch}", {"recursive": "1"}, timeout=20)
    return data.get("tree", [])[:5000] if isinstance(data, dict) and isinstance(data.get("tree"), list) else []


def _readme_path(tree: list[dict[str, Any]]) -> str | None:
    candidates = []
    for node in tree:
        path = str(node.get("path", ""))
        low = path.lower()
        if "/" not in path and low.startswith("readme"):
            return path
        if low.endswith(("/readme.md", "/readme.rst", "/readme.txt")):
            candidates.append(path)
    return sorted(candidates, key=len)[0] if candidates else None


def _readme_quality(text: str) -> dict[str, Any]:
    """轻量检查 README 内容。不是运行验证。"""
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
    hits = {k: any(w in low for w in words) for k, words in groups.items()}
    code_blocks = len(re.findall(r"```", text)) // 2
    commands = len(re.findall(r"(?m)^\s*(python|pip|conda|bash|sh|CUDA_VISIBLE_DEVICES|torchrun)\b", text))
    score = (1 if len(text) >= 800 else 0) + (1 if len(text) >= 2000 else 0) + sum(hits.values()) + (1 if code_blocks else 0) + (1 if commands else 0)
    return {
        "readme_length": len(text),
        "readme_keyword_hits": hits,
        "readme_code_blocks": code_blocks,
        "readme_command_like_lines": commands,
        "readme_quality_score": int(score),
    }


def _light_probe_repo(repo: dict[str, Any]) -> dict[str, Any]:
    """轻量 repo 探测：README + stars + size + file_count。"""
    full_name = str(repo.get("repo_full_name") or "")
    branch = str(repo.get("default_branch") or "main")
    tree = _repo_tree(full_name, branch) if full_name else []
    files = [n for n in tree if n.get("type") == "blob"]
    dirs = [n for n in tree if n.get("type") == "tree"]
    readme_file = _readme_path(tree)
    readme_text = _gh_text(f"https://raw.githubusercontent.com/{full_name}/{branch}/{readme_file}") if readme_file and full_name else ""
    readme_score = _readme_quality(readme_text)

    stars = int(repo.get("repo_stars") or 0)
    size_kb = int(repo.get("repo_size_kb") or 0)
    star_score = 4 if stars >= 1000 else 3 if stars >= 300 else 2 if stars >= 50 else 1 if stars >= 10 else 0
    file_score = 2 if 10 <= len(files) <= 500 else 1 if len(files) >= 3 else 0
    size_score = 2 if 50 <= size_kb <= 300000 else 1 if size_kb >= 10 else 0
    score = min(readme_score["readme_quality_score"], 8) + star_score + file_score + size_score

    return {
        "mode": "light_check",
        "verified_runnable": False,
        "has_readme": bool(readme_file),
        "readme_path": readme_file,
        **readme_score,
        "repo_stars": stars,
        "repo_forks": int(repo.get("repo_forks") or 0),
        "repo_size_kb": size_kb,
        "tree_file_count": len(files),
        "tree_dir_count": len(dirs),
        "feasibility_score": int(score),
        "feasibility_hint": "high" if score >= 11 else "medium" if score >= 7 else "low",
        "basis": "README content + stars + repository size + recursive file count",
        "note": "This is only a lightweight feasibility probe, not a reproducibility proof.",
    }


def _paper_code_repos_for_baseline(baseline: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """根据 baseline citations，从被引用论文里直接拿 code_urls。"""
    id_to_paper = {p["paper_id"]: p for p in evidence}
    repos: list[dict[str, Any]] = []
    for cit in _as_list(baseline.get("citations")):
        if not isinstance(cit, dict):
            continue
        paper = id_to_paper.get(cit.get("paper_id"))
        if not paper:
            continue
        for url in _as_list(paper.get("code_urls")):
            if isinstance(url, str):
                repos.append({"url": url, "source": "paper_code_link", "from_paper_id": cit.get("paper_id"), "note": "Code URL was directly extracted from the cited paper evidence."})
    unique = []
    seen = set()
    for r in repos:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique


def _enrich_repositories(plan: dict[str, Any], evidence: list[dict[str, Any]], mode: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """为 baseline 推荐代码库：优先论文 code link，其次 GitHub 搜索。"""
    repo_report: list[dict[str, Any]] = []
    allow_search = mode in {"recommend", "light_check", "deep_check"}
    allow_probe = mode in {"light_check", "deep_check"}

    for baseline in _as_list(plan.get("baseline_candidates")):
        if not isinstance(baseline, dict):
            continue

        existing = [r for r in _as_list(baseline.get("repo_candidates")) if isinstance(r, dict)]
        paper_repos = _paper_code_repos_for_baseline(baseline, evidence)
        merged: list[dict[str, Any]] = []

        for r in paper_repos + existing:
            url = r.get("url") or r.get("repo_url")
            if isinstance(url, str) and "github.com" in url:
                merged.append({"url": url, "source": r.get("source", "paper_code_link"), "from_paper_id": r.get("from_paper_id"), "note": r.get("note", "")})

        seen_urls = set()
        merged_unique = []
        for r in merged:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                merged_unique.append(r)

        recommended: list[dict[str, Any]] = []

        for r in merged_unique:
            meta = _repo_metadata_from_url(r["url"])
            meta.update(
                {
                    "recommendation_source": r.get("source", "paper_code_link"),
                    "from_paper_id": r.get("from_paper_id"),
                    "confidence": "paper_provided_url",
                    "verified_runnable": False,
                    "note": "Repository URL is provided by cited paper evidence; not executed in Step2.",
                }
            )
            if allow_probe and meta.get("repo_full_name"):
                meta["repo_probe"] = _light_probe_repo(meta)
            recommended.append(meta)

        if not recommended and allow_search:
            query = str(baseline.get("open_source_query") or baseline.get("name") or "").strip()
            if query:
                for q in [f"{query} machine learning", f"{query} pytorch", query]:
                    repos = _search_repos(q)
                    if repos:
                        for repo in repos[:3]:
                            repo.update({"recommendation_source": "github_search", "confidence": "metadata_only", "verified_runnable": False, "note": "Repository is recommended by GitHub search metadata only; not executed in Step2."})
                            if allow_probe:
                                repo["repo_probe"] = _light_probe_repo(repo)
                            recommended.append(repo)
                        break

        baseline["github_check_mode"] = mode
        baseline["recommended_repositories"] = recommended
        baseline["recommended_repo"] = recommended[0] if recommended else None
        baseline["repo_recommendation_status"] = "paper_code_link" if recommended and recommended[0].get("recommendation_source") == "paper_code_link" else "github_search" if recommended else "not_found_or_disabled"

        repo_report.append({"baseline": baseline.get("name"), "github_check_mode": mode, "recommended_repositories": recommended, "status": baseline["repo_recommendation_status"]})

    return plan, repo_report


# =============================================================================
# 9. 数据集名称和本地缓存检测
# =============================================================================

def _dataset_variants(name: str, aliases: list[str] | None = None) -> list[str]:
    values = [name] + (aliases or [])
    out = set()
    for value in values:
        value = str(value or "").strip().lower()
        if not value:
            continue
        out.update([value, _slug(value), value.replace(" ", ""), value.replace("-", "_"), value.replace("_", "-"), value.split("/")[-1]])
        out.update(t for t in re.split(r"[^a-zA-Z0-9]+", value) if len(t) >= 4)
    return sorted(out)


def _data_dirs() -> list[Path]:
    home = Path.home()
    cwd = Path.cwd()
    return [cwd / "data", cwd / "datasets", cwd / ".cache", home / ".cache" / "huggingface" / "datasets", home / ".cache" / "huggingface" / "hub", home / ".cache" / "torch", home / ".cache", home / "data", home / "datasets"]


def _dataset_cache(name: str, aliases: list[str] | None = None) -> dict[str, Any]:
    variants = _dataset_variants(name, aliases)
    hits = []
    searched = []
    for base in _data_dirs():
        if not base.exists():
            continue
        searched.append(str(base))
        try:
            for child in list(base.rglob("*"))[:3000]:
                path_text = str(child).lower()
                matched = [v for v in variants if v in path_text][:5]
                if matched:
                    hits.append({"path": str(child), "name": child.name, "is_dir": child.is_dir(), "is_file": child.is_file(), "matched_variants": matched})
                    if len(hits) >= 10:
                        break
        except Exception:
            pass
        if len(hits) >= 10:
            break
    return {"dataset_name": name, "name_variants": variants[:20], "cached": bool(hits), "hits": hits, "searched_dirs": searched}


def _enrich_datasets(plan: dict[str, Any]) -> dict[str, Any]:
    for dataset in _as_list(plan.get("dataset_candidates")):
        if not isinstance(dataset, dict):
            continue
        name = str(dataset.get("name") or "")
        aliases = [str(x) for x in _as_list(dataset.get("aliases"))]
        dataset["name_detection"] = {"canonical_name": name, "aliases": aliases, "variants": _dataset_variants(name, aliases)[:20]}
        dataset["local_cache"] = _dataset_cache(name, aliases)
        dataset.setdefault("storage_path_hint", f"data/{_slug(name)}")
    return plan


# =============================================================================
# 10. 默认 plan、baseline 选择、超参数建议
# =============================================================================

def _default_plan() -> dict[str, Any]:
    return {
        "schema_version": "2.4",
        "research_task": "",
        "method_family": "other",
        "hypothesis": "",
        "method_module_order": [],
        "baseline_candidates": [],
        "selected_baselines": [],
        "dropped_baselines": [],
        "dataset_candidates": [],
        "metric_candidates": [],
        "hyperparameter_policy": {"principle": "inherit cited baseline settings; use agent_suggested only when unknown", "parameters": []},
        "experiment_matrix": {"mvp_plan": [], "main_plan": [], "ablation_plan": [], "diagnostic_plan": []},
        "execution_plan": {
            "environment": {"framework": "PyTorch", "python_version": ">=3.10", "packages": [], "hardware_assumption": ""},
            "artifacts": {"results_json": "experiments/results.json", "run_log": ".watson/run_log.txt", "figures_dir": "paper/figures", "checkpoints_dir": "experiments/checkpoints"},
            "commands": [],
        },
        "iteration_hooks": {"what_to_record": [], "failure_signatures": [], "refine_rules": [], "pivot_rules": []},
        "needs_human_confirm": [],
        "validation_report": {},
    }


def _merge_default(x: dict[str, Any]) -> dict[str, Any]:
    def merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        result = dict(a)
        for k, v in b.items():
            result[k] = merge(result[k], v) if isinstance(v, dict) and isinstance(result.get(k), dict) else v
        return result

    plan = merge(_default_plan(), x if isinstance(x, dict) else {})
    for k in ["baseline_candidates", "selected_baselines", "dropped_baselines", "dataset_candidates", "metric_candidates", "method_module_order", "needs_human_confirm"]:
        if not isinstance(plan.get(k), list):
            plan[k] = []
    for k in ["mvp_plan", "main_plan", "ablation_plan", "diagnostic_plan"]:
        if not isinstance(plan["experiment_matrix"].get(k), list):
            plan["experiment_matrix"][k] = []
    if not isinstance(plan["execution_plan"].get("commands"), list):
        plan["execution_plan"]["commands"] = []
    return plan


def _select_baselines(plan: dict[str, Any]) -> dict[str, Any]:
    """分层选择 baseline：不因资源太重删除，只因缺 citation 删除。"""
    candidates = [b for b in _as_list(plan.get("baseline_candidates")) if isinstance(b, dict)]
    selected = []
    dropped = []

    for baseline in candidates:
        if not baseline.get("citations"):
            baseline["selection_status"] = "dropped"
            baseline["selection_reason"] = "missing valid Step1 citation"
            dropped.append(baseline)
        elif baseline.get("recommended_repositories"):
            baseline["selection_status"] = "candidate_with_repo"
            baseline["selection_reason"] = "valid citation and repository recommendation available"
        else:
            baseline["selection_status"] = "candidate_no_repo"
            baseline["selection_reason"] = "valid citation but no repository recommendation found"

    def pick(role: str) -> dict[str, Any] | None:
        matches = [b for b in candidates if str(b.get("role", "")).lower() == role and str(b.get("selection_status", "")).startswith("candidate")]
        with_repo = [b for b in matches if b.get("recommended_repositories")]
        return (with_repo or matches or [None])[0]

    for role in ["classic", "strong", "sota", "open_source_alternative"]:
        chosen = pick(role)
        if chosen and chosen not in selected:
            chosen["selection_status"] = "selected"
            selected.append(chosen)

    plan["selected_baselines"] = selected
    plan["dropped_baselines"] = dropped + [b for b in candidates if b not in selected and b not in dropped]
    return plan


def _suggest_hparams(plan: dict[str, Any]) -> dict[str, Any]:
    """对未知超参数调用同一个 agent 给建议，并标记为 agent_suggested。"""
    hp = _as_dict(plan.get("hyperparameter_policy"))
    params = [p for p in _as_list(hp.get("parameters")) if isinstance(p, dict)]
    if not params:
        params = [
            {"name": "random_seed", "initial_value": "42", "source": "standard_default", "citations": [], "tunable": False, "search_space": "fixed", "fallback": "42", "confidence": "medium", "needs_human_confirm": False},
            {"name": "learning_rate", "initial_value": "TBD", "source": "TBD", "citations": [], "tunable": True, "search_space": "TBD", "fallback": "Use baseline default if available", "confidence": "low", "needs_human_confirm": True},
        ]

    missing = [p for p in params if str(p.get("initial_value", "")).lower() in {"", "tbd", "unknown", "none", "null", "不确定"}]
    if missing:
        raw = complete_chat(build_messages(HYPERPARAM_SYSTEM, _json({"plan": plan, "missing_parameters": missing})), temperature=0.25, max_tokens=1500)
        suggestions = {str(s.get("name", "")).lower(): s for s in _safe_json_list(raw)}
        for param in params:
            suggestion = suggestions.get(str(param.get("name", "")).lower())
            if suggestion:
                param.update(
                    {
                        "initial_value": suggestion.get("initial_value", param.get("initial_value")),
                        "source": suggestion.get("source", "agent_suggested"),
                        "search_space": suggestion.get("search_space", param.get("search_space")),
                        "fallback": suggestion.get("fallback", param.get("fallback")),
                        "confidence": suggestion.get("confidence", "low"),
                        "needs_human_confirm": True,
                        "agent_suggestion_rationale": suggestion.get("rationale", ""),
                    }
                )

    hp["parameters"] = params
    plan["hyperparameter_policy"] = hp
    needs = _as_list(plan.get("needs_human_confirm"))
    for param in params:
        if param.get("source") == "agent_suggested":
            needs.append(f"Hyperparameter `{param.get('name')}` is agent_suggested and should be confirmed.")
    plan["needs_human_confirm"] = sorted(set(map(str, needs)))
    return plan


# =============================================================================
# 11. 实验矩阵、执行计划、下载计划
# =============================================================================

def _ensure_matrix_and_execution(plan: dict[str, Any], constraints: dict[str, Any], hardware: dict[str, Any]) -> dict[str, Any]:
    baselines = [b.get("name") for b in _as_list(plan.get("selected_baselines")) if isinstance(b, dict)]
    datasets = [d.get("name") for d in _as_list(plan.get("dataset_candidates")) if isinstance(d, dict)]
    metrics = [m.get("name") for m in _as_list(plan.get("metric_candidates")) if isinstance(m, dict)]

    matrix = plan["experiment_matrix"]
    if not matrix.get("mvp_plan"):
        matrix["mvp_plan"] = [{"id": "mvp_01", "goal": "End-to-end smoke test before main experiments.", "conditions": baselines[:1] + ["proposed_minimal"], "datasets": datasets[:1] or ["toy_subset"], "metrics": metrics[:2] or ["primary_metric"], "max_runtime_hours": 2, "success_criteria": "Code runs and writes experiments/results.json.", "citations": []}]
    if not matrix.get("main_plan"):
        matrix["main_plan"] = [{"id": "main_01", "goal": "Fair comparison with must-cite baselines.", "conditions": baselines + ["proposed_method"], "datasets": datasets[:2] or ["main_dataset"], "metrics": metrics or ["primary_metric"], "max_runtime_hours": constraints.get("time_budget_hours") or 8, "success_criteria": "Supports or falsifies the main hypothesis.", "citations": []}]
    if not matrix.get("ablation_plan"):
        matrix["ablation_plan"] = [{"id": "abl_01", "goal": "Isolate the contribution of the core module.", "conditions": ["proposed_full", "proposed_without_core_module"], "datasets": datasets[:1] or ["main_dataset"], "metrics": metrics[:3] or ["primary_metric"], "max_runtime_hours": 4, "success_criteria": "Ablation changes primary or diagnostic metric.", "citations": []}]

    execution = plan["execution_plan"]
    env = execution["environment"]
    env["framework"] = constraints.get("framework_hint") or env.get("framework", "PyTorch")
    env["hardware_assumption"] = f"accelerator={hardware.get('accelerator')}; gpu_model={constraints.get('gpu_model_hint')}; gpu_ids={constraints.get('gpu_ids')}; idle_gpu_ids={hardware.get('idle_gpu_ids')}"

    if not execution.get("commands"):
        execution["commands"] = [
            {"id": "cmd_01", "name": "prepare_data", "cmd": "python experiments/experiment.py --stage prepare_data", "expected_outputs": ["data/<dataset>/"], "max_runtime_hours": 1, "depends_on": []},
            {"id": "cmd_02", "name": "run_mvp", "cmd": "python experiments/experiment.py --stage mvp --output experiments/results.json", "expected_outputs": ["experiments/results.json"], "max_runtime_hours": 2, "depends_on": ["cmd_01"]},
            {"id": "cmd_03", "name": "run_main", "cmd": "python experiments/experiment.py --stage main --output experiments/results.json", "expected_outputs": ["experiments/results.json"], "max_runtime_hours": constraints.get("time_budget_hours") or 8, "depends_on": ["cmd_02"]},
            {"id": "cmd_04", "name": "run_ablation", "cmd": "python experiments/experiment.py --stage ablation --output experiments/results.json", "expected_outputs": ["experiments/results.json"], "max_runtime_hours": 4, "depends_on": ["cmd_03"]},
        ]

    hooks = plan["iteration_hooks"]
    hooks.setdefault("what_to_record", ["metrics", "runtime", "GPU id", "dataset path", "seed", "hyperparameters", "tracebacks"])
    hooks.setdefault("failure_signatures", ["NaN loss", "repo missing", "dataset cache mismatch", "metric mismatch"])
    hooks.setdefault("refine_rules", ["Tune only declared hyperparameters", "Use open_source_alternative if recommended repo fails"])
    hooks.setdefault("pivot_rules", ["Return to Step2 if no must-cite baseline is runnable"])
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
            f"- Aliases: {', '.join(map(str, _as_list(dataset.get('aliases')))) or 'N/A'}",
            f"- Variants: {', '.join(detection.get('variants', [])[:10])}",
            f"- Target path: `{path}`",
            f"- Cache detected: `{cache.get('cached', False)}`",
        ]
        for hit in _as_list(cache.get("hits"))[:5]:
            if isinstance(hit, dict):
                lines.append(f"  - `{hit.get('path')}` matched={hit.get('matched_variants')}")
        lines += [f"- Download hint: {dataset.get('download_hint') or 'TBD'}", f"- Suggested command: `python experiments/experiment.py --stage prepare_data --dataset \"{dataset.get('name')}\" --data_dir \"{path}\"`", ""]
    return "\n".join(lines).rstrip() + "\n"


def _iteration_context() -> dict[str, Any]:
    return {"has_previous_run": bool(S.load_run_log() or S.load_results() or S.load_analysis()), "run_log_tail": "\n".join((S.load_run_log() or "").splitlines()[-60:]), "results": _truncate(S.load_results(), 2500), "analysis": _truncate(S.load_analysis(), 2500)}


# =============================================================================
# 12. 总装：LLM 草案 -> 最终实验计划
# =============================================================================

def _finalize(draft: dict[str, Any], evidence: list[dict[str, Any]], constraints: dict[str, Any], hardware: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan = _merge_default(draft)
    plan["_generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    plan["constraint_profile"] = constraints
    plan["local_hardware"] = hardware
    plan["paper_evidence"] = evidence
    plan["resource_capacity"] = _capacity(constraints, hardware)

    mode = _github_check_mode(constraints)
    plan["github_check_mode"] = mode

    plan = _must_cite(plan, evidence)
    plan, repo_report = _enrich_repositories(plan, evidence, mode)
    plan = _enrich_datasets(plan)
    plan = _select_baselines(plan)
    plan = _suggest_hparams(plan)
    plan = _ensure_matrix_and_execution(plan, constraints, hardware)

    report = plan.setdefault("validation_report", {})
    report["github_check_mode"] = mode
    report["must_cite_baseline_count"] = sum(1 for b in _as_list(plan.get("selected_baselines")) if isinstance(b, dict) and b.get("citations"))
    report["repository_recommended_baseline_count"] = sum(1 for b in _as_list(plan.get("selected_baselines")) if isinstance(b, dict) and b.get("recommended_repositories"))
    report["idle_gpu_ids"] = hardware.get("idle_gpu_ids")
    report["recommended_gpu_ids"] = hardware.get("recommended_gpu_ids")
    report["is_executable_plan_ready"] = bool(_as_list(plan.get("execution_plan", {}).get("commands")))
    return plan, repo_report


# =============================================================================
# 13. Public entry point：保持原 Watson 接口不变
# =============================================================================

def run(extra_constraints: str = "") -> Generator[str, None, None]:
    """Run Step 2: design a structured, must-cite, executable experiment plan."""
    idea = S.load_idea()
    if not idea:
        yield "❌ 请先完成 Step 1（Idea Validation）。\n"
        return

    papers = S.load_papers()
    assessment = S.load_idea_assessment()

    yield "🔍 **Step2.1 解析约束并探测本地 GPU / CPU 资源**\n\n"
    hardware = _detect_local_hardware()
    constraints = _parse_constraints(extra_constraints, hardware)
    cap = _capacity(constraints, hardware)
    mode = _github_check_mode(constraints)

    yield "```json\n" + _json({"resource_capacity": cap, "github_check_mode": mode, "constraint_profile": constraints, "gpu_summary": {"accelerator": hardware.get("accelerator"), "gpu_count": hardware.get("gpu_count"), "gpu_models": hardware.get("gpu_models"), "gpu_ids": hardware.get("gpu_ids"), "idle_gpu_ids": hardware.get("idle_gpu_ids"), "busy_gpu_ids": hardware.get("busy_gpu_ids"), "max_free_memory_gpu_id": hardware.get("max_free_memory_gpu_id"), "recommended_gpu_ids": hardware.get("recommended_gpu_ids")}, "gpus": hardware.get("gpus")}) + "\n```\n\n"

    yield "📚 **Step2.2 构造带 paper_id 与 code_urls 的 must-cite evidence pack**\n\n"
    evidence = _evidence_pack(papers)
    code_link_count = sum(len(_as_list(p.get("code_urls"))) for p in evidence)
    yield f"- 已载入 Step1 论文证据：{len(evidence)} 篇\n"
    yield f"- 从论文证据中直接抽取到 GitHub 代码链接：{code_link_count} 个\n\n"
    if not evidence:
        yield "- ⚠️ 未发现 Step1 论文证据，baseline 将需要人工确认。\n\n"

    if _iteration_context().get("has_previous_run"):
        yield "♻️ **检测到已有运行/分析结果：本次 Step2 将作为迭代式实验重设计。**\n\n"

    yield "🧠 **Step2.3 单 agent 抽取 baseline / dataset / metric / execution plan 草案**\n\n"
    payload = {"idea": idea, "idea_assessment_summary": _truncate(assessment, 1800), "paper_evidence": evidence, "constraint_profile": constraints, "local_hardware": hardware, "github_check_mode": mode, "iteration_context": _iteration_context()}
    draft_raw = complete_chat(build_messages(EXTRACTION_SYSTEM, _json(payload)), temperature=0.15, max_tokens=5500)
    draft = _safe_json_dict(draft_raw)

    yield "🧪 **Step2.4 执行 must-cite 校验、代码库推荐、数据名/缓存检测、超参数建议与执行计划补全**\n\n"
    plan, repo_report = _finalize(draft, evidence, constraints, hardware)

    preview = {
        "github_check_mode": mode,
        "must_cite_baseline_count": plan.get("validation_report", {}).get("must_cite_baseline_count"),
        "repository_recommended_baseline_count": plan.get("validation_report", {}).get("repository_recommended_baseline_count"),
        "selected_baselines": [
            {"name": b.get("name"), "role": b.get("role"), "citations": [c.get("paper_id") for c in _as_list(b.get("citations"))], "repo_status": b.get("repo_recommendation_status"), "recommended_repo": _as_dict(b.get("recommended_repo")).get("repo_url"), "recommendation_source": _as_dict(b.get("recommended_repo")).get("recommendation_source"), "verified_runnable": _as_dict(b.get("recommended_repo")).get("verified_runnable"), "selection_status": b.get("selection_status")}
            for b in _as_list(plan.get("selected_baselines"))
            if isinstance(b, dict)
        ],
        "datasets": [
            {"name": d.get("name"), "aliases": d.get("aliases"), "variants": _as_dict(d.get("name_detection")).get("variants", [])[:5], "cached": _as_dict(d.get("local_cache")).get("cached"), "hits": _as_dict(d.get("local_cache")).get("hits", [])[:2]}
            for d in _as_list(plan.get("dataset_candidates"))[:5]
            if isinstance(d, dict)
        ],
        "hyperparameters": _as_dict(plan.get("hyperparameter_policy")).get("parameters", [])[:8],
        "execution_commands": [{"id": c.get("id"), "cmd": c.get("cmd")} for c in _as_list(_as_dict(plan.get("execution_plan")).get("commands")) if isinstance(c, dict)],
        "needs_human_confirm": plan.get("needs_human_confirm", [])[:10],
    }
    yield "```json\n" + _json(preview) + "\n```\n\n"

    yield "✍️ **Step2.5 生成 experiment.md 与机器可读 sidecar 文件**\n\n"
    markdown = ""
    for chunk in stream_chat(build_messages(MARKDOWN_SYSTEM, "请把下面的 experiment_plan.json 转写成人类可读的 experiment.md。\n\n" + _json(plan)), temperature=0.25, max_tokens=5200):
        markdown += chunk
        yield chunk

    if "## Structured Appendix" not in markdown:
        markdown = markdown.rstrip() + "\n\n## Structured Appendix\n\n```json\n" + _json(plan) + "\n```\n"

    S.save_file(EXPERIMENT_FILE, markdown.rstrip() + "\n")
    S.save_file(EXPERIMENT_JSON_FILE, _json(plan) + "\n")
    S.save_file(EXPERIMENT_EVIDENCE_FILE, _json(evidence) + "\n")
    S.save_file(EXPERIMENT_REPO_REPORT_FILE, _json(repo_report) + "\n")
    S.save_file(DOWNLOAD_DATA_PLAN_FILE, _download_plan(plan))

    S.save_state(
        {
            "last_step": "experiment",
            "experiment_schema_version": plan.get("schema_version", "2.4"),
            "experiment_resource_capacity": plan.get("resource_capacity"),
            "experiment_github_check_mode": mode,
            "experiment_gpu_ids": constraints.get("gpu_ids"),
            "experiment_idle_gpu_ids": hardware.get("idle_gpu_ids"),
            "experiment_gpu_models": hardware.get("gpu_models"),
            "experiment_must_cite_baseline_count": plan.get("validation_report", {}).get("must_cite_baseline_count", 0),
            "experiment_repository_recommended_baseline_count": plan.get("validation_report", {}).get("repository_recommended_baseline_count", 0),
            "experiment_plan_file": str(EXPERIMENT_JSON_FILE),
        }
    )

    yield "\n\n✅ **Step2 完成**\n\n"
    yield f"- Markdown: `{EXPERIMENT_FILE}`\n"
    yield f"- Machine-readable plan: `{EXPERIMENT_JSON_FILE}`\n"
    yield f"- Evidence pack: `{EXPERIMENT_EVIDENCE_FILE}`\n"
    yield f"- Repo report: `{EXPERIMENT_REPO_REPORT_FILE}`\n"
    yield f"- Data plan: `{DOWNLOAD_DATA_PLAN_FILE}`\n"

