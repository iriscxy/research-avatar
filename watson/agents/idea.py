"""Step 1: Idea Validation Agent — multi-venue review styles.

Styles: ml (NeurIPS/ICML/ICLR), nlp (ACL/EMNLP), cv (CVPR/ICCV)

Two-phase:
  Phase 1 — annotate each paper with per-paper technical relevance & difference.
  Phase 2 — deep technical validation at the selected venue standard,
             grounded in the retrieved papers (no opinions out of thin air).
"""

import json
import re
from typing import Generator

from ..config import PAPERS_FILE, SIMILAR_PAPERS_FILE, TOP_CONF_PAPERS_FILE, IDEA_FILE, IDEA_ASSESSMENT_FILE
from ..llm import build_messages, stream_chat, complete_chat
from ..tools.paper_search import search_all, format_papers
from .. import state as S

# ── Venue / style configuration ───────────────────────────────────────────────

STYLE_CONFIG: dict[str, dict] = {
    "ml": {
        "label": "ML（NeurIPS / ICML / ICLR）",
        "venues": ["NeurIPS", "ICML", "ICLR"],
        "venue_query": "NeurIPS OR ICML OR ICLR",
        "top_conf_label": "顶会论文（NeurIPS / ICML / ICLR）",
    },
    "nlp": {
        "label": "NLP（ACL / EMNLP）",
        "venues": ["ACL", "EMNLP", "NAACL"],
        "venue_query": "ACL OR EMNLP OR NAACL OR COLING",
        "top_conf_label": "顶会论文（ACL / EMNLP / NAACL）",
    },
    "cv": {
        "label": "CV（CVPR / ICCV）",
        "venues": ["CVPR", "ICCV", "ECCV"],
        "venue_query": "CVPR OR ICCV OR ECCV",
        "top_conf_label": "顶会论文（CVPR / ICCV / ECCV）",
    },
}

# ── Phase 1: per-paper technical annotation ───────────────────────────────────

ANNOTATE_SYSTEM = """你是一位顶会技术审稿人。
给定研究 idea 和一批论文，对每篇论文从**技术层面**精确分析，输出 JSON 数组，每项字段：
- "index": 编号（从1开始）
- "relevance": 与该 idea 在技术层面的相关性（1-2句，具体到模型结构/任务/数据集/指标）
- "difference": 与该 idea 的核心技术区别（1-2句，指出 backbone、方法、目标函数或实验设置上的本质不同）

只输出 JSON 数组，不要任何其他文字。"""


def _annotate_papers(idea: str, papers: list[dict]) -> list[dict]:
    if not papers:
        return papers
    numbered = "\n".join(
        f"{i+1}. {p['title']} ({p.get('published','')}) — {p.get('summary','')[:200]}"
        for i, p in enumerate(papers)
    )
    messages = build_messages(ANNOTATE_SYSTEM, f"研究 Idea：{idea}\n\n论文列表：\n{numbered}")
    try:
        raw = complete_chat(messages, temperature=0.2, max_tokens=2500)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            for item in json.loads(match.group()):
                idx = int(item.get("index", 0)) - 1
                if 0 <= idx < len(papers):
                    papers[idx]["relevance"]  = item.get("relevance", "")
                    papers[idx]["difference"] = item.get("difference", "")
    except Exception:
        pass
    return papers


# ── Phase 2 system prompts per style ─────────────────────────────────────────

_IDEA_REVIEW_TEMPLATE = """你是一位 {venue_desc} 资深 Area Chair，审稿风格严苛、直接。

你收到的是一个处于**构思阶段的研究方向**（不是完整论文），以及从该领域顶会中检索到的相关论文列表。
你的任务是评估这个方向是否值得深入推进。

**注意**：上方 UI 已经为每篇论文单独展示了与 idea 的相关性和区别，报告中**不要逐篇重复**，直接在论证中引用论文名即可。

**搜索信号规则**：用户消息末尾会提供"文献覆盖统计"。如果关键词相关性 > 0 的论文**少于 10 篇**，
这是一个重要的预警信号——该方向与顶会主流研究交集很小。你**必须**在 Go/No-Go 部分明确分析其含义：
是过于超前的新兴方向（机会），还是与领域主流脱节（风险）。

---

## 一、创新核心定位
用 2-4 句话说清楚：这个 idea 声称要解决什么问题，核心切入点是什么。
基于提供的文献，判断这个切入点在当前研究版图中处于什么位置——是全新方向、现有方向的扩展、还是已有工作的重复？
引用最相关的 1-3 篇论文支撑判断，不逐篇列举。

## 二、新颖性评分（1-5）
- **评分 + 理由**：哪一点是真正新的，哪一点已有工作覆盖（引用具体论文）
- **最大竞争威胁**：提供的文献中哪篇最接近、最可能让 reviewer 质疑新颖性？说明两者的本质差异（或缺乏差异）

## 三、方向可行性评分（1-5）
不要求细化技术方案，评估方向层面的可行性：
- 这个方向有没有合适的数据/benchmark 支撑验证？
- 现有工具链（模型、框架）能否支持？
- 最大的未知风险是什么？

## 四、{venue_short} 投稿预判
- 如果做出来，最可能投哪个 venue（给 1-2 个选项）及理由
- 当前 idea 阶段最可能被 reject 的**2 条核心质疑**（写成 reviewer 口吻，引用具体论文）

## 五、Go / No-Go 建议
明确给出：**Go** / **Conditional Go** / **No-Go**
- Go：直接说可以推进到实验设计
- Conditional Go：列出 2-3 个**在进入实验设计前必须想清楚的关键问题**（不是要求补实验，是要求 idea 本身更清晰）
- No-Go：说明根本性障碍
- **若文献覆盖统计显示相关论文 < 10 篇，必须在此处附一段"文献稀疏警告"，说明这对该方向的含义**

---
语气：直接，不安慰。引用论文时用论文标题，不重复卡片里已有的逐篇介绍。用中文。"""


def _make_system(style: str) -> str:
    descs = {
        "ml":  ("NeurIPS / ICML / ICLR", "NeurIPS/ICML/ICLR"),
        "nlp": ("ACL / EMNLP / NAACL", "ACL/EMNLP"),
        "cv":  ("CVPR / ICCV / ECCV", "CVPR/ICCV"),
    }
    venue_desc, venue_short = descs.get(style, descs["ml"])
    return _IDEA_REVIEW_TEMPLATE.format(venue_desc=venue_desc, venue_short=venue_short)


_STYLE_SYSTEMS: dict[str, str] = {
    "ml":  _make_system("ml"),
    "nlp": _make_system("nlp"),
    "cv":  _make_system("cv"),
}

# ── Proposal prompt ───────────────────────────────────────────────────────────

_PROPOSE_SYSTEM = """你是一位有创造力的顶会研究员，擅长从文献空白中发现有价值的新方向。

你会收到：用户的原始 idea、针对该 idea 的评审意见、以及从相关顶会中检索到的论文。
你的目标是提出一个更有区分度、更可能通过评审的研究方向。

严格按以下格式输出（用中文）：

### 文献空白分析
（2-3句）基于提供的论文，指出目前领域存在的明显空白或矛盾。引用 1-2 篇具体论文说明空白所在。

### 改进后的研究方向
清晰描述新的研究 idea（4-6句）：
- 核心问题是什么
- 关键技术思路（有实质内容，但无需完整方案）
- 与现有工作的差异化定位

### 与原 idea 的核心区别
（1-2句）改变了什么，为什么这个改变能解决评审中指出的问题。"""


def propose(original_idea: str, assessment: str, papers: list[dict], style: str = "ml") -> Generator[str, None, None]:
    """Propose a refined idea based on assessment and retrieved papers."""
    papers_text = format_papers(papers[:8], "相关顶会论文")
    user_msg = f"""## 原始研究 Idea
{original_idea}

## 评审意见（不通过的原因）
{assessment}

## 相关顶会论文
{papers_text}

请基于以上内容，提出一个改进的研究方向。"""

    messages = build_messages(_PROPOSE_SYSTEM, user_msg)
    for chunk in stream_chat(messages, max_tokens=1200):
        yield chunk


def run(idea: str, style: str = "ml") -> Generator[str, None, None]:
    """Validate the research idea. Yields text chunks suitable for streaming.

    Args:
        idea:  The research idea text.
        style: Review style — "ml" (NeurIPS/ICML/ICLR), "nlp" (ACL/EMNLP), or "cv" (CVPR/ICCV).
    """
    from ..tools.conf_search import (
        fetch_cvf_year, fetch_acl_venue_year, fetch_openreview_iclr,
        fetch_neurips_year, fetch_pmlr_year, rank_and_trim,
        ACL_VENUE_CODES, ACL_VENUE_YEARS, RECENT_YEARS, PMLR_ICML_VOLS,
    )

    cfg = STYLE_CONFIG.get(style, STYLE_CONFIG["ml"])

    # ── Phase 0: fetch acceptance lists with per-year progress ────────────────
    yield f"🔍 **从 {cfg['label']} 会议官网获取近期论文...**\n\n"

    pool: list[dict] = []

    if style == "cv":
        for venue in ["CVPR", "ICCV", "ECCV"]:
            for year in RECENT_YEARS:
                if venue == "ICCV" and year % 2 == 0:
                    continue
                yield f"- 📂 正在打开 **{venue} {year}** acceptance list..."
                papers = fetch_cvf_year(venue, year)
                pool.extend(papers)
                yield f" ✓ {len(papers)} 篇\n"

    elif style == "nlp":
        for venue in ["ACL", "EMNLP", "NAACL"]:
            code = ACL_VENUE_CODES.get(venue, venue.lower())
            years = ACL_VENUE_YEARS.get(code, RECENT_YEARS)
            for year in years:
                yield f"- 📂 正在打开 **{venue} {year}** acceptance list..."
                papers = fetch_acl_venue_year(code, year)
                pool.extend(papers)
                yield f" ✓ {len(papers)} 篇\n"

    else:  # ml
        for year in RECENT_YEARS:
            yield f"- 📂 正在打开 **NeurIPS {year}** acceptance list..."
            papers = fetch_neurips_year(year)
            pool.extend(papers)
            yield f" ✓ {len(papers)} 篇\n"
        for year, vol in PMLR_ICML_VOLS.items():
            yield f"- 📂 正在打开 **ICML {year}** acceptance list (PMLR v{vol})..."
            papers = fetch_pmlr_year(year)
            pool.extend(papers)
            yield f" ✓ {len(papers)} 篇\n"
        for year in RECENT_YEARS:
            yield f"- 📂 正在打开 **ICLR {year}** acceptance list (OpenReview)..."
            papers = fetch_openreview_iclr(year, limit=200)
            pool.extend(papers)
            yield f" ✓ {len(papers)} 篇\n"

    top_conf, relevant_count = rank_and_trim(pool, idea, 10, return_stats=True)

    # Fallback if all conference sites failed
    if not top_conf:
        yield "\n⚠️ 会议官网暂时不可用，切换到 Semantic Scholar 备用搜索...\n\n"
        from ..tools.paper_search import search_top_conf
        fallback = search_top_conf(idea, max_results=10, venue_query=cfg["venue_query"])
        top_conf, relevant_count = fallback, len(fallback)

    for p in top_conf:
        p["group"] = "top_conf"

    S.save_file(IDEA_FILE, f"# Research Idea\n\n{idea}\n")

    coverage_note = ""
    if relevant_count < 10:
        coverage_note = f" ⚠️（关键词相关性 > 0 的论文仅 **{relevant_count}** 篇，覆盖较少）"
    yield f"\n✅ 从 {len(pool)} 篇论文中找到 **{relevant_count}** 篇相关（展示最高的 {len(top_conf)} 篇）{coverage_note}\n\n"

    # ── Phase 1: per-paper technical annotation ───────────────────────────────
    yield "🏷️ **逐篇生成技术相关性与区别分析...**\n\n"
    top_conf = _annotate_papers(idea, top_conf)

    S.save_json(SIMILAR_PAPERS_FILE, [])
    S.save_json(TOP_CONF_PAPERS_FILE, top_conf)
    S.save_json(PAPERS_FILE, top_conf)

    yield "---\n\n"

    # ── Phase 2: deep technical review ────────────────────────────────────────
    venues_str = " / ".join(cfg["venues"])
    yield f"## 📋 深度技术评审报告（{venues_str} 审稿标准）\n\n"

    top_conf_text = format_papers(top_conf, cfg["top_conf_label"])

    sparse_warning = (
        f"\n\n## 文献覆盖统计\n"
        f"- 从 {len(pool)} 篇 {cfg['label']} 顶会论文中，关键词相关性 > 0 的共 **{relevant_count}** 篇\n"
        f"- 实际展示（相关性最高）：**{len(top_conf)}** 篇\n"
        + (f"- ⚠️ 相关论文不足 10 篇，需在 Go/No-Go 部分明确分析含义\n" if relevant_count < 10 else "")
    )

    user_prompt = f"""## 研究 Idea
{idea}

## {cfg['top_conf_label']}
{top_conf_text}
{sparse_warning}
请按上述五个维度给出评审报告，所有判断引用上方具体论文。"""

    messages = build_messages(_STYLE_SYSTEMS[style], user_prompt)

    full = ""
    for chunk in stream_chat(messages, max_tokens=4096):
        full += chunk
        yield chunk

    S.save_file(IDEA_ASSESSMENT_FILE, full)
    S.save_state({"last_step": "idea", "idea": idea, "papers_count": len(top_conf),
                  "relevant_total": relevant_count, "style": style})
