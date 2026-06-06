"""Step 1: Idea Validation Agent.

Fetches acceptance lists from all major venues (ML / NLP / CV), scores relevance,
and produces a compact technical review with quantitative signals.

Two-phase:
  Phase 1 — annotate each paper with per-paper technical relevance & difference.
  Phase 2 — compact review report grounded in retrieved papers.
"""

import json
import re
from typing import Generator

from ..config import PAPERS_FILE, SIMILAR_PAPERS_FILE, TOP_CONF_PAPERS_FILE, ALL_RELEVANT_PAPERS_FILE, IDEA_FILE, IDEA_ASSESSMENT_FILE
from ..llm import build_messages, stream_chat, complete_chat
from ..tools.paper_search import search_all, format_papers
from .. import state as S

ALL_VENUES_QUERY = "NeurIPS OR ICML OR ICLR OR ACL OR EMNLP OR NAACL OR CVPR OR ICCV OR ECCV"
ALL_VENUES_LABEL = "顶会论文（NeurIPS / ICML / ICLR / ACL / EMNLP / NAACL / CVPR / ICCV / ECCV）"

# ── Phase 1: per-paper technical annotation ───────────────────────────────────

ANNOTATE_SYSTEM = """你是一位顶会技术审稿人。
给定研究 idea 和一批论文，对每篇论文从**技术层面**精确分析，输出 JSON 数组，每项字段：
- "index": 编号（从1开始）
- "relevance": 与该 idea 在技术层面的相关性（1-2句，具体到模型结构/任务/数据集/指标）
- "difference": 与该 idea 的核心技术区别（1-2句，指出 backbone、方法、目标函数或实验设置上的本质不同）
- "similarity_score": 与该 idea 的相同程度（整数1-5；5=几乎在做同一件事：相同任务+相同方法；3=相同任务但不同方法；1=同领域但核心贡献完全不同）

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
        raw = complete_chat(messages, temperature=0.2, max_tokens=6000)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return papers
        for item in json.loads(match.group()):
            try:
                idx = int(item.get("index", 0)) - 1
                if not (0 <= idx < len(papers)):
                    continue
                papers[idx]["relevance"]  = item.get("relevance", "")
                papers[idx]["difference"] = item.get("difference", "")
                raw_sim = item.get("similarity_score", 1)
                papers[idx]["similarity_score"] = max(1, min(5, int(float(str(raw_sim)))))
            except Exception:
                continue
    except Exception:
        pass
    return papers


# ── Phase 2 system prompt ─────────────────────────────────────────────────────

_IDEA_REVIEW_SYSTEM = """你是一位熟悉 ML（NeurIPS/ICML/ICLR）、NLP（ACL/EMNLP/NAACL）、CV（CVPR/ICCV/ECCV）的跨领域顶会资深 Area Chair，审稿风格严苛、直接。

你收到：研究 idea + 量化信号（主题密度/年度趋势/会议分布/领域契合度/相关性均值）+ 相关论文列表。
UI 已对每篇论文显示相关性与区别，**报告中不逐篇重复**，直接引用论文标题即可。

## 方法新颖性评分标准（必须严格执行）
注意：这里评的是**方法层面的贡献深度**，与"有没有人做过"（文献新颖性）无关。文献新颖性已由量化信号单独衡量。
- **5/5**：提出全新方法、架构或理论框架，解决了明确的开放问题
- **4/5**：对现有方法有实质性改动，针对具体技术瓶颈提出了新机制
- **3/5**：在现有方法上有有意义的适配或新组合，有一定技术贡献
- **2/5**：主要是把现有模型/架构应用到新领域或新数据集，技术贡献有限
- **1/5**：完全是已有工作的直接移植，换个数据集重新训练

⚠️ **方法堆砌陷阱**：如果 idea 的方法部分可以被概括为"用 A + B + C 三种技术组合"，但没有说清楚为什么这个组合能解决某个具体的技术瓶颈，这是典型的方法堆砌（method stacking）。堆砌越多流行技术（MoE、LoRA、RAG、Chain-of-Thought……），反而说明核心贡献越模糊。必须在🔴最大威胁或🟢真正新颖点中明确指出：这些方法的组合是否有内在的技术逻辑，还是仅仅为了"看起来全面"。方法堆砌不能提升新颖性评分，缺乏技术合理性的组合应直接降分。

⚠️ **应用型论文陷阱**：如果 idea 的核心贡献可以被概括为"用模型 X 在领域/数据集 Y 上训练"，这是顶会最常见的 reject 理由之一。必须在🔴最大威胁中**首先**点明这一根本性问题，不能绕过。

⚠️ **技术时效性检查**：必须判断 idea 中提到的模型/架构是否过时。过时信号包括：以 BERT、BART、T5、RoBERTa、GPT-2 等前 LLM 时代模型作为核心 backbone，而未考虑 LLaMA、GPT-4、Claude、Qwen 等现代大模型。若存在此问题，必须在🔴最大威胁中明确指出"技术选型已落后于领域现状"，并说明当前主流做法是什么。

⚠️ **投稿建议约束**：首选会议必须与评分中"最适会议"一致，不得另选其他会议。

**严格按以下格式输出，总字数控制在 420 字以内：**

---

### 一句话定位
[这个 idea 在当前研究版图中的位置：全新方向 / 现有方向扩展 / 应用移植，引用 1-2 篇最相关论文]

### 评分
- 方案新颖性：{NOVELTY_SCORE}/5 — [一句话解释：对应哪条 rubric，核心依据是什么。此分数由量化信号固定，不得修改]
- 领域热度：{VITALITY_SCORE}/5 — [一句话解释该方向活跃程度。此分数由量化信号固定，不得修改]
- 最适会议：{TOP_VENUE} — [一句话说明为何适合，引用会议分布数字]

### 三个关键判断

🔴 **最大威胁**：[若存在应用型论文问题，必须首先指出；否则指出最接近的竞争论文及本质差异]

🟢 **真正新颖点**：[若有的话；若 idea 是纯应用移植则明确写"暂无方法层面新颖点"]

🟡 **最大风险**：[可行性角度：数据 / benchmark / 工具链 / 计算资源上最大的未知或障碍]

### 投稿建议

首选 **[具体会议名]** · 备选 **[具体会议名]**

理由：[一句话，引用领域契合度和会议分布数字]

Reviewer 质疑①：[一句话]

Reviewer 质疑②：[一句话]

### 结论
**[Go / Conditional Go / No-Go]**
若 Conditional Go：进实验前必须想清楚——
1. [关键问题]
2. [关键问题（可选）]
若 No-Go：说明根本性障碍（如纯应用移植无法通过顶会审稿）
若文献覆盖 < 10 篇：附一句文献稀疏警告及其含义

---
语气直接不安慰。量化信号中的数字必须在报告中被引用。用中文。"""

# ── Query polish ─────────────────────────────────────────────────────────────

_QUERY_POLISH_SYSTEM = """你是一位信息检索专家。
将用户的研究 idea 提炼为最核心的英文搜索关键词，用于学术论文检索。

步骤一：识别隐含技术上下文，必须补充以下词：
- idea 涉及 MoE / LoRA / PEFT / instruction tuning / fine-tuning / alignment → 必须加 "large language model"
- idea 涉及 RAG / retrieval augmented → 必须加 "retrieval augmented generation"
- idea 涉及 prompt / chain-of-thought / in-context learning → 必须加 "large language model"

步骤二：提炼核心词，规则：
- 展开缩写（MoE → mixture of experts，LLM → large language model）
- 只保留最核心的 3-5 个技术概念，不堆砌同义词
- 不添加 idea 中未涉及的新方向

输出：纯关键词，空格分隔，不超过 10 个词，不要解释"""


def _polish_query(idea: str) -> str:
    messages = build_messages(_QUERY_POLISH_SYSTEM, idea)
    try:
        result = complete_chat(messages, temperature=0.1, max_tokens=80).strip()
        return result if result else idea
    except Exception:
        return idea


# ── Dimension extraction ──────────────────────────────────────────────────────

_DIMENSION_EXTRACT_SYSTEM = """你是信息检索专家。将研究 idea 拆解为 4 个维度的英文关键词组。
输出 JSON（不要任何其他文字）：
{
  "task":   ["..."],  // 任务/问题类型（如 visual question answering, text summarization）
  "method": ["..."],  // 核心技术/方法（如 mixture of experts, contrastive learning）
  "domain": ["..."],  // 应用领域（如 medical, legal, autonomous driving）
  "goal":   ["..."]   // 优化目标（如 efficiency, lightweight, robustness, accuracy）
}
每组 2-4 个关键词，包含同义词和缩写展开。只输出 JSON。"""


def _extract_dimensions(idea: str) -> dict | None:
    messages = build_messages(_DIMENSION_EXTRACT_SYSTEM, idea)
    try:
        raw = complete_chat(messages, temperature=0.1, max_tokens=200).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        dims = json.loads(match.group())
        if not isinstance(dims, dict) or not any(isinstance(v, list) for v in dims.values()):
            return None
        return dims
    except Exception:
        return None


# ── Proposal prompt ───────────────────────────────────────────────────────────

_PROPOSE_SYSTEM = """你是一位顶会研究员，擅长从文献空白中发现有价值的新方向。

你会收到：用户的原始 idea、评审意见、以及相关顶会论文。
任务：提出一个真正有方法创新的改进方向。

**写作要求：简洁、直接、技术准确。禁止堆砌形容词，禁止用"创新性地"、"系统性地"、"全面地"等空洞修饰词。每句话都要有实质内容。**

严格按以下格式输出（用中文）：

### 文献空白
1-2句。指出领域里具体缺什么，引用 1 篇论文。

### 改进后的研究方向
3-4句，说清楚：① 解决什么问题 ② 核心方法是什么（具体到模型/机制层面）③ 和现有工作的本质区别。
不要写背景铺垫，直接说方案。

### 与原 idea 的核心区别
1句话。改了什么，解决了评审中哪条具体问题。"""


def propose(original_idea: str, assessment: str, papers: list[dict]) -> Generator[str, None, None]:
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


def run(idea: str) -> Generator[str, None, None]:
    """Validate the research idea against all major venues (ML/NLP/CV).
    Yields text chunks suitable for streaming.
    """
    from ..tools.conf_search import (
        fetch_cvf_year, fetch_ecva_year, fetch_acl_venue_year, fetch_openreview_iclr,
        fetch_neurips_year, fetch_pmlr_year, fetch_dblp_venue_year,
        fetch_aistats_year, fetch_uai_year, fetch_vldb_year, fetch_sigmod_year,
        compute_metrics,
        ACL_VENUE_CODES, ACL_VENUE_YEARS, RECENT_YEARS, PMLR_ICML_VOLS, DBLP_VENUES,
    )

    # ── Phase 0a: polish query + extract dimensions ──────────────────────────
    yield "🔎 **优化搜索关键词并拆解核心维度...**\n"
    search_query = _polish_query(idea)
    dimensions   = _extract_dimensions(idea)
    yield f"搜索词：`{search_query}`\n"
    if dimensions:
        dim_lines = "  |  ".join(
            f"**{k}**: {', '.join(v[:3])}" for k, v in dimensions.items() if v
        )
        yield f"核心维度：{dim_lines}\n\n"
    else:
        yield "（维度拆解失败，使用宽松关键词匹配）\n\n"

    # ── Phase 0b: fetch all conference acceptance lists ───────────────────────
    yield "🔍 **从顶会官网获取近期论文（ML / NLP / CV / IR / AI / DB）...**\n\n"

    pool: list[dict] = []
    conf_fetch_counts: dict[str, int] = {}  # venue → total papers fetched

    # ML: NeurIPS + ICML + ICLR
    for year in RECENT_YEARS:
        yield f"- 📂 正在打开 **NeurIPS {year}** acceptance list..."
        papers = fetch_neurips_year(year)
        pool.extend(papers)
        conf_fetch_counts["NeurIPS"] = conf_fetch_counts.get("NeurIPS", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"
    for year, vol in PMLR_ICML_VOLS.items():
        yield f"- 📂 正在打开 **ICML {year}** acceptance list (PMLR v{vol})..."
        papers = fetch_pmlr_year(year)
        pool.extend(papers)
        conf_fetch_counts["ICML"] = conf_fetch_counts.get("ICML", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"
    for year in RECENT_YEARS:
        yield f"- 📂 正在打开 **ICLR {year}** acceptance list (OpenReview)..."
        papers = fetch_openreview_iclr(year, limit=200)
        pool.extend(papers)
        conf_fetch_counts["ICLR"] = conf_fetch_counts.get("ICLR", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"

    # NLP: ACL + EMNLP + NAACL
    for venue in ["ACL", "EMNLP", "NAACL"]:
        code = ACL_VENUE_CODES.get(venue, venue.lower())
        years = ACL_VENUE_YEARS.get(code, RECENT_YEARS)
        for year in years:
            yield f"- 📂 正在打开 **{venue} {year}** acceptance list..."
            papers = fetch_acl_venue_year(code, year)
            pool.extend(papers)
            conf_fetch_counts[venue] = conf_fetch_counts.get(venue, 0) + len(papers)
            yield f" ✓ {len(papers)} 篇\n"

    # CV: CVPR + ICCV (CVF) + ECCV (ecva.net, even years only)
    for venue in ["CVPR", "ICCV"]:
        for year in RECENT_YEARS:
            if venue == "ICCV" and year % 2 == 0:
                continue
            yield f"- 📂 正在打开 **{venue} {year}** acceptance list..."
            papers = fetch_cvf_year(venue, year)
            pool.extend(papers)
            conf_fetch_counts[venue] = conf_fetch_counts.get(venue, 0) + len(papers)
            yield f" ✓ {len(papers)} 篇\n"
    for year in RECENT_YEARS:
        if year % 2 != 0:
            continue  # ECCV is biennial (even years only)
        yield f"- 📂 正在打开 **ECCV {year}** acceptance list (ecva.net)..."
        papers = fetch_ecva_year(year)
        pool.extend(papers)
        conf_fetch_counts["ECCV"] = conf_fetch_counts.get("ECCV", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"

    # CV extra: WACV (CVF, annual)
    for year in RECENT_YEARS:
        yield f"- 📂 正在打开 **WACV {year}** acceptance list..."
        papers = fetch_cvf_year("WACV", year)
        pool.extend(papers)
        conf_fetch_counts["WACV"] = conf_fetch_counts.get("WACV", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"

    # ML extra: AISTATS + UAI (PMLR)
    for year in RECENT_YEARS:
        yield f"- 📂 正在打开 **AISTATS {year}** acceptance list (PMLR)..."
        papers = fetch_aistats_year(year)
        pool.extend(papers)
        conf_fetch_counts["AISTATS"] = conf_fetch_counts.get("AISTATS", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"
    for year in RECENT_YEARS:
        yield f"- 📂 正在打开 **UAI {year}** acceptance list (PMLR)..."
        papers = fetch_uai_year(year)
        pool.extend(papers)
        conf_fetch_counts["UAI"] = conf_fetch_counts.get("UAI", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"

    # NLP extra: COLING + EACL (ACL Anthology)
    for venue in ["COLING", "EACL"]:
        code = ACL_VENUE_CODES.get(venue, venue.lower())
        years = ACL_VENUE_YEARS.get(code, RECENT_YEARS)
        for year in years:
            yield f"- 📂 正在打开 **{venue} {year}** acceptance list..."
            papers = fetch_acl_venue_year(code, year)
            pool.extend(papers)
            conf_fetch_counts[venue] = conf_fetch_counts.get(venue, 0) + len(papers)
            yield f" ✓ {len(papers)} 篇\n"

    # IR / Web / Data Mining / AI: SIGIR + KDD + WWW + AAAI + IJCAI (standard DBLP conf pages)
    for venue_name, dblp_key in DBLP_VENUES.items():
        for year in RECENT_YEARS:
            yield f"- 📂 正在打开 **{venue_name} {year}** acceptance list (DBLP)..."
            papers = fetch_dblp_venue_year(venue_name, dblp_key, year)
            pool.extend(papers)
            conf_fetch_counts[venue_name] = conf_fetch_counts.get(venue_name, 0) + len(papers)
            yield f" ✓ {len(papers)} 篇\n"

    # DB: VLDB (PVLDB journal) + SIGMOD (PACMMOD journal 2023+, conf proceedings 2022)
    for year in RECENT_YEARS:
        yield f"- 📂 正在打开 **VLDB {year}** acceptance list (PVLDB/DBLP)..."
        papers = fetch_vldb_year(year)
        pool.extend(papers)
        conf_fetch_counts["VLDB"] = conf_fetch_counts.get("VLDB", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"
    for year in RECENT_YEARS:
        yield f"- 📂 正在打开 **SIGMOD {year}** acceptance list (PACMMOD/DBLP)..."
        papers = fetch_sigmod_year(year)
        pool.extend(papers)
        conf_fetch_counts["SIGMOD"] = conf_fetch_counts.get("SIGMOD", 0) + len(papers)
        yield f" ✓ {len(papers)} 篇\n"

    # ── Phase 0c: supplement with three-API academic search ──────────────────
    yield "\n🌐 **通过 OpenAlex / S2 / arXiv API 补充学术数据库搜索...**\n"
    api_source_counts: dict[str, int] = {}
    try:
        from ..tools.paper_search import search_academic_apis
        api_papers, api_source_counts = search_academic_apis(search_query, max_results=150)
        pool.extend(api_papers)
        yield f"   API 搜索补充 **{len(api_papers)}** 篇论文\n\n"
    except Exception:
        yield "   （API 搜索失败，跳过）\n\n"

    # ── Deduplicate by normalized title (keep first occurrence) ──────────────
    _seen: set[str] = set()
    deduped: list[dict] = []
    for p in pool:
        norm = re.sub(r"[^a-z0-9]", "", p.get("title", "").lower())
        if norm and norm not in _seen:
            _seen.add(norm)
            deduped.append(p)
    pool = deduped

    m = compute_metrics(pool, search_query, 20, dimensions=dimensions)
    top_conf, relevant_count = m["top_papers"], m["relevant_count"]

    # Fallback if all conference sites failed
    if not top_conf:
        yield "\n⚠️ 会议官网暂时不可用，切换到 Semantic Scholar 备用搜索...\n\n"
        from ..tools.paper_search import search_top_conf
        fallback = search_top_conf(idea, max_results=20, venue_query=ALL_VENUES_QUERY)
        m = compute_metrics(fallback, search_query, 20, dimensions=dimensions)
        top_conf, relevant_count = m["top_papers"], m["relevant_count"]

    for p in top_conf:
        p["group"] = "top_conf"

    S.save_file(IDEA_FILE, f"# Research Idea\n\n{idea}\n")

    comp_count = m["competitor_count"]
    bg_count   = m["background_count"]
    coverage_note = "" if comp_count >= 5 else f" ⚠️（直接竞争论文仅 **{comp_count}** 篇，覆盖较少）"
    yield (
        f"\n✅ 从 {len(pool)} 篇论文中找到 "
        f"**{comp_count}** 篇直接竞争论文（2+ 维度匹配）"
        f" + **{bg_count}** 篇背景文献（1 维度匹配）"
        f"{coverage_note}\n\n"
    )

    # ── Phase 1: per-paper technical annotation ───────────────────────────────
    yield "🏷️ **逐篇生成技术相关性与区别分析...**\n\n"
    top_conf = _annotate_papers(idea, top_conf)

    # Post-annotation metrics: similarity scores are now available
    sim_scores = [p["similarity_score"] for p in top_conf if p.get("similarity_score")]
    avg_similarity = round(sum(sim_scores) / len(sim_scores), 1) if sim_scores else 0
    max_similarity = max(sim_scores) if sim_scores else 0
    high_sim = sum(1 for p in top_conf if p.get("similarity_score", 0) >= 4)
    saturation_ratio = high_sim / len(top_conf) if top_conf else 0.0
    saturation_label = (
        "竞争激烈" if saturation_ratio >= 0.6 else
        "竞争中等" if saturation_ratio >= 0.3 else
        "空间充足"
    )

    # Venue counts from ALL competitor papers (tier="competitor", 2+ dimension hits)
    all_competitors = [p for p in m["all_relevant_papers"] if p.get("tier") == "competitor"]
    venue_counts_similar: dict[str, int] = {}
    for p in all_competitors:
        venue = p.get("venue", "")
        conf = venue.split()[0] if venue else "Unknown"
        venue_counts_similar[conf] = venue_counts_similar.get(conf, 0) + 1

    # Count relevant papers (competitor + background) per source conference
    # (excludes API-only sources like arXiv / Scholar which have no fixed venue)
    _api_sources = {"arxiv", "semantic_scholar", "openalex", "google_scholar"}
    relevant_conf_counts: dict[str, int] = {}
    for p in m["all_relevant_papers"]:
        if p.get("source", "") in _api_sources:
            continue
        venue = p.get("venue", "")
        conf = venue.split()[0] if venue else ""
        if conf:
            relevant_conf_counts[conf] = relevant_conf_counts.get(conf, 0) + 1

    # Sort by similarity_score descending so highest-threat papers appear first
    top_conf.sort(key=lambda p: p.get("similarity_score", 0), reverse=True)

    S.save_json(SIMILAR_PAPERS_FILE, [])
    S.save_json(TOP_CONF_PAPERS_FILE, top_conf)
    S.save_json(ALL_RELEVANT_PAPERS_FILE, m["all_relevant_papers"])
    S.save_json(PAPERS_FILE, top_conf)

    # Save metrics to state for dashboard rendering
    S.save_state({
        "last_step": "idea", "idea": idea,
        "search_query": search_query,
        "papers_count": len(top_conf),
        "relevant_total": relevant_count,
        "competitor_count": comp_count,
        "background_count": bg_count,
        "dimensions": dimensions,
        "pool_size": len(pool),
        "density": m["density"],
        "year_counts": m["year_counts"],
        "venue_counts": m["venue_counts"],
        "venue_counts_similar": venue_counts_similar,
        "avg_score": m["avg_score"],
        "avg_similarity": avg_similarity,
        "max_similarity": max_similarity,
        "venue_fit_score": m["venue_fit_score"],
        "venue_fit_label": m["venue_fit_label"],
        "saturation_ratio": saturation_ratio,
        "saturation_label": saturation_label,
        "vitality_score": m["vitality_score"],
        "vitality_label": m["vitality_label"],
        "conf_fetch_counts": conf_fetch_counts,
        "relevant_conf_counts": relevant_conf_counts,
        "api_source_counts": api_source_counts,
    })

    # Sentinel: tells the UI that papers are saved and ready to render
    yield "\n__PAPERS_READY__\n"

    # ── Phase 2: deep technical review ────────────────────────────────────────

    top_conf_text = format_papers(top_conf, ALL_VENUES_LABEL)

    # Build quantitative signal block for LLM
    year_trend = "  →  ".join(
        f"{yr}年 {m['year_counts'].get(yr, 0)} 篇"
        for yr in sorted(m["year_counts"])
    )
    _vc = venue_counts_similar if venue_counts_similar else m["venue_counts"]
    venue_dist = "  ".join(
        f"{v} {c} 篇"
        for v, c in sorted(_vc.items(), key=lambda x: -x[1])[:6]
    )
    years = sorted(m["year_counts"])
    growth_note = ""
    if len(years) >= 2:
        oldest = m["year_counts"].get(years[0], 1) or 1
        newest = m["year_counts"].get(years[-1], 0)
        pct = (newest - oldest) / oldest * 100
        growth_note = f"，{years[0]}→{years[-1]} 增长 {pct:+.0f}%"

    method_novelty = max(1, 6 - max_similarity) if max_similarity else 0
    quant_signal = (
        f"\n\n## 量化信号（报告中必须引用这些数字）\n"
        f"- 直接竞争论文：**{comp_count}** 篇（同时满足 2+ 核心维度：task / method / domain / goal）\n"
        f"- 背景文献：**{bg_count}** 篇（单维度相关，验证问题有人研究）\n"
        f"- 方案新颖性（已固定，报告评分必须用此值）：**{method_novelty}/5**（最高相同性 {max_similarity}/5；以最相近竞争论文为准）\n"
        f"- 领域热度（已固定，报告评分必须用此值）：**{m['vitality_score']}/5**（{m['vitality_label']}）\n"
        f"- 年度趋势：{year_trend}{growth_note}\n"
        f"- 会议分布：{venue_dist}\n"
        f"- 领域契合度：**{m['venue_fit_score']}/5**（{m['venue_fit_label']}）\n"
        + ("- ⚠️ 直接竞争论文不足 5 篇，Go/No-Go 部分必须说明其含义（可能是空白方向，也可能是搜索词未覆盖）\n"
           if comp_count < 5 else "")
    )

    # Compute top venue (same logic as dashboard)
    _vc = venue_counts_similar if venue_counts_similar else m["venue_counts"]
    top_venue_name = max(_vc, key=_vc.get) if _vc else "待定"

    # Inject fixed dashboard scores into the system prompt so LLM uses them verbatim
    review_system = _IDEA_REVIEW_SYSTEM.replace(
        "{NOVELTY_SCORE}", str(method_novelty)
    ).replace(
        "{VITALITY_SCORE}", str(m["vitality_score"])
    ).replace(
        "{TOP_VENUE}", top_venue_name
    )

    user_prompt = f"""## 研究 Idea
{idea}

## {ALL_VENUES_LABEL}
{top_conf_text}
{quant_signal}
请严格按格式给出评审报告。"""

    messages = build_messages(review_system, user_prompt)

    full = ""
    for chunk in stream_chat(messages, max_tokens=1500):
        full += chunk
        yield chunk

    S.save_file(IDEA_ASSESSMENT_FILE, full)
