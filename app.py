"""
修订说明：
新增如下内容
- 安全的页面跳转
- Step2 证据摘要
- Step2 修改意见输入框
- 按意见重新生成按钮
- 确认进入 Step3 按钮
- Step2 审核状态
- Step1/Step2 过期状态管理
- Step3 进入前确认检查
"""
"""Watson — Streamlit Web UI.  Run:  streamlit run app.py"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from watson.config import STEP_NAMES, STEP_EMOJIS, STEPS, WATSON_DIR
from watson import state as S

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Watson · AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stExpander"] summary p {
    font-size: 1.1rem !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] button {
    white-space: nowrap !important;
}
[data-testid="stMetric"] {
    background: rgba(127, 127, 127, 0.06);
    border: 1px solid rgba(127, 127, 127, 0.16);
    border-radius: 14px;
    padding: 0.85rem 1rem;
}
[data-testid="stAlert"] {
    border-radius: 12px;
}
.step2-note {
    padding: 0.85rem 1rem;
    border-radius: 12px;
    border: 1px solid rgba(99, 102, 241, 0.22);
    background: rgba(99, 102, 241, 0.06);
    margin-bottom: 0.8rem;
}
</style>
""", unsafe_allow_html=True)

# ── LLM provider registry ────────────────────────────────────────────────────

PROVIDERS = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "env_key": "DEEPSEEK_API_KEY",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "env_key": "OPENAI_API_KEY",
    },
    "Anthropic (Claude)": {
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
        "env_key": "ANTHROPIC_API_KEY",
    },
    "本地 / 自定义": {
        "base_url": "",
        "models": [],
        "env_key": "",
    },
}


def _apply_llm_config():
    """Push sidebar LLM settings into watson.config at runtime."""
    import watson.config as cfg
    provider = st.session_state.get("llm_provider", "DeepSeek")
    info = PROVIDERS[provider]
    api_key  = st.session_state.get("llm_api_key",  "") or os.getenv(info["env_key"], "")
    base_url = st.session_state.get("llm_base_url", "") or info["base_url"]
    model    = st.session_state.get("llm_model",    "") or (info["models"][0] if info["models"] else "")
    cfg.DEEPSEEK_API_KEY  = api_key
    cfg.DEEPSEEK_MODEL    = model
    cfg.DEEPSEEK_BASE_URL = base_url


def _api_ok() -> bool:
    import watson.config as cfg
    return bool(cfg.DEEPSEEK_API_KEY)


# ── Navigation and workflow state helpers ────────────────────────────────────

PAGE_OPTIONS = ["📋 总览"] + [f"{STEP_EMOJIS[s]} {STEP_NAMES[s]}" for s in STEPS]


def invalidate_after_idea_change() -> None:
    """新版 Step1 生成后，只标记旧 Step2/后续产物过期，不删除任何文件。

    这样既保留用户之前的实验方案、代码和论文草稿供对照，也能阻止旧方案
    被误认为仍与新 Idea 一致。
    """
    S.save_state({
        "last_step": "idea",
        "experiment_approved": False,
        "experiment_stale": True,
        "downstream_stale": True,
    })


def invalidate_after_experiment_change() -> None:
    """Step2 新生成或修订后，保留旧 Step3-Step6 文件，但标记为待更新。"""
    S.save_state({
        "last_step": "experiment",
        "experiment_approved": False,
        "experiment_stale": False,
        "downstream_stale": True,
    })


def request_page_nav(target_page: str) -> None:
    """Navigate safely without mutating the already-instantiated radio widget."""
    if target_page not in PAGE_OPTIONS:
        return
    st.session_state["_pending_page_nav"] = target_page
    try:
        st.query_params["p"] = str(PAGE_OPTIONS.index(target_page))
    except Exception:
        pass
    st.rerun()


# Apply pending navigation before the page_nav widget is instantiated.
_pending_page_nav = st.session_state.pop("_pending_page_nav", None)
if _pending_page_nav in PAGE_OPTIONS:
    st.session_state["page_nav"] = _pending_page_nav
elif "page_nav" not in st.session_state:
    try:
        _p_idx = int(st.query_params.get("p", "0"))
        if 0 <= _p_idx < len(PAGE_OPTIONS):
            st.session_state["page_nav"] = PAGE_OPTIONS[_p_idx]
    except (ValueError, TypeError):
        pass

if "page_nav" not in st.session_state or st.session_state["page_nav"] not in PAGE_OPTIONS:
    st.session_state["page_nav"] = PAGE_OPTIONS[0]


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔬 Watson")
    st.caption("AI 科研助手 — 本地化版本")
    st.divider()

    # LLM provider — collapsible
    import watson.config as _cfg_check
    _key_configured = bool(_cfg_check.DEEPSEEK_API_KEY)
    _api_label = "🤖 大模型设置  ✅" if _key_configured else "🤖 大模型设置  ⚠️ 未配置"
    with st.expander(_api_label, expanded=not _key_configured):
        provider = st.selectbox("API 提供商", list(PROVIDERS.keys()), key="llm_provider")
        pinfo = PROVIDERS[provider]

        default_key = os.getenv(pinfo["env_key"], "") if pinfo["env_key"] else ""
        st.text_input("API Key", value=default_key, type="password",
                      placeholder=pinfo["env_key"] or "API Key", key="llm_api_key")

        if pinfo["models"]:
            st.selectbox("模型", pinfo["models"], key="llm_model")
        else:
            st.text_input("模型名称", placeholder="e.g. llama3", key="llm_model")

        st.text_input("Base URL（可选）", value=pinfo["base_url"],
                      placeholder=pinfo["base_url"] or "http://localhost:11434/v1",
                      key="llm_base_url")

    _apply_llm_config()

    st.divider()

    # Step navigation
    st.markdown("**研究进度**")
    page = st.radio("导航", PAGE_OPTIONS, label_visibility="collapsed", key="page_nav")

    # Keep URL in sync with the selected page.
    try:
        st.query_params["p"] = str(PAGE_OPTIONS.index(page))
    except ValueError:
        st.query_params["p"] = "0"



# ── Helpers ───────────────────────────────────────────────────────────────────

def stream_to_placeholder(generator, label: str = "Watson 正在思考...") -> str:
    placeholder = st.empty()
    full = ""
    with st.spinner(label):
        for chunk in generator:
            full += chunk
            placeholder.markdown(full + "▌")
    placeholder.markdown(full)
    return full


def _linkify_papers(text: str, papers: list[dict]) -> str:
    """Replace paper title/shortname mentions in text with markdown links."""
    import re as _re
    for p in papers:
        title = p.get("title", "").strip()
        url   = p.get("link", "") or p.get("pdf", "")
        if not title or not url:
            continue

        # Build candidate names: full title + short name before first ":" or "–"
        candidates = [title]
        short = _re.split(r"[:–]", title)[0].strip()
        if len(short) >= 4 and short != title:
            candidates.append(short)

        for name in candidates:
            if len(name) < 4:
                continue
            text = _re.sub(
                r"(?<!\[)" + _re.escape(name) + r"(?!\])",
                f"[{name}]({url})",
                text,
                flags=_re.IGNORECASE,
            )
    return text


def _paper_card(p: dict, idx: int):
    st.markdown(f'<a id="paper-{idx}"></a>', unsafe_allow_html=True)
    with st.container(border=True):
        # ── Title + venue/authors ─────────────────────────────────────────────
        st.markdown(f"**{p['title']}**")
        venue = p.get("venue", "")
        authors = ", ".join(p.get("authors", [])[:3])
        if len(p.get("authors", [])) > 3:
            authors += " et al."
        venue_str   = f"🏛️ **{venue}**" if venue else ""
        authors_str = f"👤 {authors}" if authors else ""
        meta = "　".join(filter(None, [venue_str, authors_str]))
        if meta:
            st.caption(meta)

        # ── Relevance + Similarity scores ─────────────────────────────────────
        rel = p.get("relevance_score", 0)
        sim = p.get("similarity_score")  # None = not yet annotated
        if rel or sim:
            sc1, sc2, _ = st.columns([1, 1, 2])
            with sc1:
                rel_stars = "★" * rel + "☆" * (5 - rel) if rel else "—"
                st.metric("相关性", f"{rel}/5",
                          help="BM25 关键词匹配分：越高说明与你的研究方向越相关")
                st.caption(rel_stars)
            with sc2:
                if sim is not None:
                    sim_stars = "★" * sim + "☆" * (5 - sim)
                    st.metric("相同性", f"{sim}/5",
                              help="LLM 判断：越低说明与你的 idea 区别越大，新颖性越强")
                    st.caption(sim_stars)
                else:
                    st.metric("相同性", "—",
                              help="运行「开始验证」后生成")
                    st.caption("待分析")

        # ── Abstract ──────────────────────────────────────────────────────────
        summary = p.get("summary", "")
        if summary:
            with st.expander("摘要"):
                st.write(summary[:400])

        # ── Relevance / Difference analysis ───────────────────────────────────
        relevance  = p.get("relevance", "")
        difference = p.get("difference", "")
        if relevance or difference:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("🔗 **与本研究的相关性**")
                st.info(relevance or "—")
            with c2:
                st.markdown("🆚 **与本研究的区别**")
                st.warning(difference or "—")
        else:
            st.caption("_运行「开始验证」后将自动生成相关性与区别分析_")

        # ── Links ─────────────────────────────────────────────────────────────
        if p.get("link"):
            st.link_button("查看论文 ↗", p["link"])


def _render_metrics(state: dict, top_conf: list):
    relevant_total        = state.get("relevant_total", len(top_conf))
    competitor_count      = state.get("competitor_count")      # None = old state, not yet computed
    background_count      = state.get("background_count", 0)
    year_counts           = state.get("year_counts", {})
    venue_counts          = state.get("venue_counts", {})
    venue_counts_similar  = state.get("venue_counts_similar", {})
    max_similarity        = state.get("max_similarity", 0)
    avg_similarity        = state.get("avg_similarity", 0)
    vitality_score        = state.get("vitality_score", 0)
    vitality_label        = state.get("vitality_label", "")
    venue_fit_score       = state.get("venue_fit_score", 0)
    venue_fit_label       = state.get("venue_fit_label", "")
    # Novelty based on worst case (most similar paper), not average
    method_novelty        = max(1, 6 - max_similarity) if max_similarity else 0
    # For venue display: use similarity>=3 papers when available; else fall back to all relevant
    similar_total = sum(venue_counts_similar.values()) if venue_counts_similar else 0
    if venue_counts_similar:
        venue_counts_for_rec = venue_counts_similar
    else:
        venue_counts_for_rec = venue_counts
        similar_total        = relevant_total

    # ── Year trend ────────────────────────────────────────────────────────────
    import datetime as _dt
    _current_year = str(_dt.datetime.now().year)
    # Only 4-digit year keys; exclude current year; exclude sparse years
    # (< 5% of peak) to avoid API-only years distorting the comparison.
    years = sorted(y for y in year_counts if y.isdigit() and len(y) == 4)
    complete_years = [y for y in years if y < _current_year]
    if complete_years:
        _peak = max(year_counts.get(y, 0) for y in complete_years) or 1
        _min_count = max(5, _peak * 0.05)
        dense_years = [y for y in complete_years if year_counts.get(y, 0) >= _min_count]
    else:
        dense_years = []
    if len(dense_years) >= 2:
        _yoy = []
        for _i in range(1, len(dense_years)):
            _p = year_counts.get(dense_years[_i - 1], 1) or 1
            _c = year_counts.get(dense_years[_i], 0)
            _yoy.append((_c - _p) / _p * 100)
        avg_growth = sum(_yoy) / len(_yoy)
        trend_label = "快速升温" if avg_growth > 100 else "升温" if avg_growth > 30 else "降温" if avg_growth < -20 else "平稳"
        trend_str = f"年均增长 {avg_growth:+.0f}%（{trend_label}）"
    else:
        trend_str = "数据不足"

    with st.expander("📊 量化信号", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:  # 领域热度
            with st.container(border=True):
                st.metric("领域热度", f"{vitality_score}/5" if vitality_score else "—",
                          help=(
                              "综合竞争论文数量 + 年度增长趋势 + 会议覆盖广度，越高说明该问题越被业界重视。\n\n"
                              "**竞争论文**：同时命中 2 个及以上维度（任务 / 方法 / 领域 / 目标），是直接新颖性威胁。\n\n"
                              "**背景文献**：仅命中 1 个维度，说明该方向有人研究，但不直接威胁新颖性。"
                          ))
                if vitality_score:
                    if competitor_count is not None:
                        st.caption(f"{vitality_label}｜竞争论文 {competitor_count} 篇 + 背景文献 {background_count} 篇")
                        st.caption("竞争论文：2+ 维度重合｜背景文献：1 维度重合")
                    else:
                        st.caption(f"{vitality_label}｜共 {relevant_total} 篇相关文献")
                else:
                    st.caption("验证后显示")
                if complete_years:
                    import pandas as _pd
                    _yrs = complete_years[-4:]
                    _df = _pd.DataFrame(
                        {"篇数": [year_counts.get(yr, 0) for yr in _yrs]},
                        index=_yrs,
                    )
                    st.bar_chart(_df, height=120)

        with c2:  # 方案新颖性
            with st.container(border=True):
                st.metric("方案新颖性", f"{method_novelty}/5" if method_novelty else "—",
                          help="由 LLM 对比竞争论文计算（6 - 最高相同性），以最相近的一篇论文为准，越高说明与已有工作的方法差异越大")
                if max_similarity:
                    label = "方法差异显著" if method_novelty >= 4 else "有一定差异" if method_novelty >= 3 else "高度相似"
                    st.caption(f"{label}｜最高相同性 {max_similarity}/5")
                elif competitor_count:
                    st.caption(f"发现 {competitor_count} 篇竞争论文｜运行验证后显示")
                else:
                    st.caption("验证后显示")

        with c3:  # 最适会议
            with st.container(border=True):
                rec_total = sum(venue_counts_for_rec.values()) if venue_counts_for_rec else 0
                if venue_counts_for_rec and rec_total:
                    max_count  = max(venue_counts_for_rec.values())
                    top_venues = sorted(v for v, c in venue_counts_for_rec.items() if c == max_count)
                    top_pct    = f"{max_count / rec_total * 100:.0f}%"
                else:
                    top_venues, max_count, top_pct = [], 0, ""
                using_similar = venue_counts_for_rec is venue_counts_similar
                st.metric("最适合会议", " / ".join(top_venues) if top_venues else "—",
                          help="所有竞争论文（2+ 维度匹配）中发表最多的会议")
                if max_count and rec_total:
                    src = "竞争论文" if using_similar else "相关论文"
                    tie = "并列 " if len(top_venues) > 1 else ""
                    st.caption(f"{tie}{top_pct}（{max_count}/{rec_total} 篇）{src}来自此会议")
                else:
                    st.caption("—")
                if venue_counts_for_rec and rec_total:
                    venue_detail = "　".join(
                        f"{v} {c/rec_total*100:.0f}%"
                        for v, c in sorted(venue_counts_for_rec.items(), key=lambda x: -x[1])[:8]
                    )
                    st.caption(f"分布：{venue_detail}")

        # ── 综合解读：领域热度 × 方案新颖性 ──────────────────────────────────
        high_active = vitality_score >= 3 if vitality_score else None
        high_novel  = method_novelty >= 3 if max_similarity else None
        if high_novel is None:
            st.info("📊 综合解读将在验证完成后显示")
        elif high_active and high_novel:
            st.success("✅ 综合解读：方向活跃且方法差异显著，发表潜力强")
        elif high_active and not high_novel:
            st.warning("⚠️ 综合解读：方向活跃但方法与已有工作高度相似，竞争激烈")
        elif not high_active and high_novel:
            st.info("🔬 综合解读：方法差异化好，但方向尚未被广泛验证，需自证价值")
        else:
            st.error("❌ 综合解读：方向冷门且方法贡献有限，顶会发表难度高")


def _render_papers():
    top_conf = S.load_top_conf_papers()
    if not top_conf:
        return
    top_conf.sort(key=lambda p: p.get("similarity_score", 0), reverse=True)
    st.divider()
    state = S.load_state()
    search_query = state.get("search_query", "")
    idea_text    = state.get("idea", "")
    # ── Search query expander ─────────────────────────────────────────────────
    if search_query and search_query != idea_text:
        with st.expander("🔎 搜索关键词（由 Idea 自动扩展）", expanded=False):
            st.code(search_query, language=None)
            relevant_conf_counts = state.get("relevant_conf_counts", {})
            api_source_counts    = state.get("api_source_counts", {})
            if relevant_conf_counts:
                conf_str = "　".join(
                    f"**{v}** {n}篇"
                    for v, n in sorted(relevant_conf_counts.items(), key=lambda x: -x[1])
                    if n > 0
                )
                st.caption(f"顶会命中：{conf_str}")
            if api_source_counts:
                api_str = "　".join(
                    f"**{src}** {n}篇"
                    for src, n in api_source_counts.items()
                )
                st.caption(f"学术 API：{api_str}")

    # ── Dimension breakdown ───────────────────────────────────────────────────
    dimensions = state.get("dimensions")
    if dimensions:
        dim_labels = {"task": "任务", "method": "方法", "domain": "领域", "goal": "目标"}
        dim_lines = "\n\n".join(
            f"**{dim_labels.get(k, k)}**：{', '.join(v)}"
            for k, v in dimensions.items() if v
        )
        with st.expander("🧩 提炼维度", expanded=True):
            st.markdown(dim_lines)

    _render_metrics(state, top_conf)

    all_relevant     = S.load_all_relevant_papers()
    background_papers = [p for p in all_relevant if p.get("tier") == "background"]
    competitor_count  = state.get("competitor_count", len(top_conf))
    background_count  = state.get("background_count", len(background_papers))

    # ── Section 1: 直接竞争论文 ──────────────────────────────────────────────
    with st.expander(f"🔴 直接竞争论文（{competitor_count} 篇）", expanded=True):
        st.caption("满足 2 个及以上维度重合（任务 / 方法 / 领域 / 目标）即算竞争论文，是真正的新颖性威胁。")
        for i, p in enumerate(top_conf):
            _paper_card(p, i)

    # ── Section 2: 背景文献 ──────────────────────────────────────────────────
    if background_papers:
        with st.expander(f"📚 背景文献（{background_count} 篇，1 维度匹配）", expanded=True):
            st.caption("仅匹配单一维度（如只涉及 MoE 或只涉及医疗），说明该问题被研究，但不直接威胁新颖性。")
            for p in background_papers:
                venue = p.get("venue", "")
                link  = p.get("link", "")
                title_md = f"[{p['title']}]({link})" if link else p["title"]
                st.markdown(
                    f"`{venue}` &nbsp; {title_md}",
                    unsafe_allow_html=True,
                )


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_overview():
    st.title("📋 Watson · AI 科研助手")
    st.markdown("从 **Idea 验证** 到 **论文撰写** 的完整研究流程，全程本地运行。")

    state = S.load_state()
    step = state.get("last_step", "")

    cols = st.columns(3)
    completed = S.get_completed_steps()
    for i, s in enumerate(STEPS):
        with cols[i % 3]:
            done = s in completed
            st.metric(label=f"{STEP_EMOJIS[s]} {STEP_NAMES[s]}", value="✅" if done else "⬜")

    idea = S.load_idea()
    if idea:
        st.subheader("📌 当前研究方向")
        st.info(idea)

    if step:
        st.subheader("📂 已生成文件")
        file_map = {
            "idea_assessment.md": S.load_idea_assessment,
            "experiment.md": S.load_experiment,
            "experiment.py": S.load_code,
            "run_log.txt": S.load_run_log,
            "results.md": S.load_results,
            "analysis.md": S.load_analysis,
            "paper.tex": S.load_paper,
        }
        for fname, loader in file_map.items():
            content = loader()
            if content:
                with st.expander(f"📄 {fname}"):
                    lang = "python" if fname.endswith(".py") else ("latex" if fname.endswith(".tex") else None)
                    if lang:
                        st.code(content, language=lang)
                    else:
                        st.markdown(content)


def page_idea():
    st.title("💡 Step 1: Idea Validation")
    st.markdown(
        "输入研究方向，Watson 同时检索 ML / NLP / CV 顶会 acceptance list，"
        "逐篇对比后给出量化分析和评审意见。未通过可让 Watson 基于文献提出改进方向，循环迭代。"
    )

    if "idea_input" not in st.session_state:
        st.session_state["idea_input"] = S.load_idea() or ""
    if "idea_round" not in st.session_state:
        st.session_state["idea_round"] = 1
    # Apply any pending idea update BEFORE the widget is instantiated
    if "_pending_idea" in st.session_state:
        st.session_state["idea_input"] = st.session_state.pop("_pending_idea")

    idea_input = st.text_area(
        "研究方向 / 研究 Idea", key="idea_input", height=150,
        placeholder="例如：研究 MoE 架构在医疗文本摘要中的应用，通过专家路由让不同 expert 处理不同医学信息维度...",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        run_btn = st.button("🚀 开始验证", type="primary", use_container_width=True) \
                  or st.session_state.pop("trigger_validate", False)
    with c2:
        if st.button("🗑️ 清空重写", use_container_width=True):
            st.session_state["_pending_idea"] = ""
            st.session_state["idea_round"] = 1
            st.session_state.pop("idea_proposal", None)
            st.rerun()

    # Single placeholder owns everything below the buttons — clearing it is instant
    results_area = st.empty()

    # ── Run validation ────────────────────────────────────────────────────────
    if run_btn:
        if not idea_input.strip():
            st.error("请输入研究方向")
            return
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        st.session_state.pop("idea_proposal", None)
        results_area.empty()          # wipe old content the instant the button fires
        from watson.agents import idea as agent

        with results_area.container():
            st.divider()
            status_ph = st.empty()
            progress_text = ""
            report_text = ""
            report_ph = None

            with st.spinner("搜索论文并分析中..."):
                for chunk in agent.run(idea_input.strip()):
                    if "__PAPERS_READY__" in chunk:
                        status_ph.empty()
                        _render_papers()       # dashboard + papers first
                        st.divider()
                        report_ph = st.empty() # report streams below
                        continue
                    if report_ph is not None:
                        report_text += chunk
                        report_ph.markdown(report_text + "▌")
                    else:
                        progress_text += chunk
                        status_ph.markdown(progress_text + "▌")

            if report_ph is not None:
                top_conf_now = S.load_top_conf_papers()
                report_ph.markdown(_linkify_papers(report_text, top_conf_now))

            invalidate_after_idea_change()
            st.success("✅ Idea 验证完成！旧的 Step2-Step6 文件已保留，但已标记为过期。")
        st.rerun()

    # ── Show results ──────────────────────────────────────────────────────────
    if not run_btn:
        with results_area.container():
            _render_papers()

            if S.load_idea_assessment():
                round_tag = f"  第 {st.session_state['idea_round']} 轮" if st.session_state["idea_round"] > 1 else ""
                _top_conf = S.load_top_conf_papers()
                _assessment = S.load_idea_assessment()
                with st.expander(f"💬 深度技术评审报告{round_tag}", expanded=True):
                    st.markdown(_linkify_papers(_assessment, _top_conf))

                # ── Action buttons ────────────────────────────────────────────
                st.divider()
                act1, act2 = st.columns(2)
                with act1:
                    if st.button("✅ 接受，进入 Step 2", type="primary", use_container_width=True):
                        step2_key = f"{STEP_EMOJIS['experiment']} {STEP_NAMES['experiment']}"
                        request_page_nav(step2_key)
                with act2:
                    propose_btn = st.button("🔄 让 Watson 基于文献提出改进方向", use_container_width=True)

                if propose_btn:
                    if not _api_ok():
                        st.error("⚠️ 请先在左侧侧边栏输入 API Key")
                    else:
                        from watson.agents.idea import propose
                        papers = S.load_top_conf_papers()
                        proposal = stream_to_placeholder(
                            propose(idea_input.strip(), S.load_idea_assessment(), papers),
                            "Watson 正在分析文献，提出改进方向...",
                        )
                        st.session_state["idea_proposal"] = proposal
                        st.rerun()

            # ── Show Watson proposal ──────────────────────────────────────────
            proposal = st.session_state.get("idea_proposal")
            if proposal:
                st.divider()
                st.subheader("🧠 Watson 提出的改进方向")
                st.info(proposal)

                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("🔬 直接用这个 Idea 重新验证", type="primary", use_container_width=True):
                        import re as _re
                        m = _re.search(r"###\s*改进后的研究方向\s*\n(.*?)(?:\n###|$)", proposal, _re.DOTALL)
                        new_idea = m.group(1).strip() if m else proposal
                        st.session_state["_pending_idea"] = new_idea
                        st.session_state["idea_round"]   = st.session_state["idea_round"] + 1
                        st.session_state["trigger_validate"] = True
                        st.session_state.pop("idea_proposal", None)
                        st.rerun()
                with b2:
                    if st.button("✏️ 修改后再验证", use_container_width=True):
                        import re as _re
                        m = _re.search(r"###\s*改进后的研究方向\s*\n(.*?)(?:\n###|$)", proposal, _re.DOTALL)
                        new_idea = m.group(1).strip() if m else proposal
                        st.session_state["_pending_idea"] = new_idea
                        st.session_state.pop("idea_proposal", None)
                        st.rerun()
                with b3:
                    if st.button("↩️ 放弃，自己重写", use_container_width=True):
                        st.session_state.pop("idea_proposal", None)
                        st.rerun()


def page_experiment():
    st.title("🔬 Step 2: Experiment Design")
    st.markdown(
        "将 Step1 的竞争论文、背景文献与量化评审信号转换为"
        "**可追溯、可修订、可执行**的实验方案。"
    )

    if not S.load_idea():
        st.warning("请先完成 Step 1（Idea Validation）")
        return

    state = S.load_state()
    experiment_stale = bool(state.get("experiment_stale", False))
    top_conf = S.load_top_conf_papers()
    load_all = getattr(S, "load_all_relevant_papers", None)
    all_relevant = load_all() if callable(load_all) else []

    # ── Step1 evidence summary ───────────────────────────────────────────────
    with st.expander("📚 Step1 证据摘要", expanded=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("直接竞争论文", state.get("competitor_count", len(top_conf)))
        m2.metric("背景文献", state.get("background_count", 0))
        m3.metric("技术标注论文", len(top_conf))
        m4.metric("全部相关论文", len(all_relevant))

        dimensions = state.get("dimensions") or {}
        if dimensions:
            labels = {"task": "任务", "method": "方法", "domain": "领域", "goal": "目标"}
            dim_text = "　｜　".join(
                f"**{labels.get(key, key)}**：{', '.join(map(str, values[:4]))}"
                for key, values in dimensions.items()
                if isinstance(values, list) and values
            )
            if dim_text:
                st.markdown(dim_text)

        c1, c2, c3 = st.columns(3)
        c1.metric("领域热度", f"{state.get('vitality_score', '—')}/5" if state.get("vitality_score") else "—")
        c2.metric("最高相同性", f"{state.get('max_similarity', '—')}/5" if state.get("max_similarity") else "—")
        c3.metric("最适会议", state.get("venue_fit_label") or "—")

    # Apply pending text reset before the widget is instantiated.
    if "_pending_experiment_feedback" in st.session_state:
        st.session_state["experiment_feedback"] = st.session_state.pop("_pending_experiment_feedback")

    if experiment_stale:
        st.warning(
            "Step1 已重新生成，当前保存的实验方案属于旧 Idea。旧文件没有被删除，"
            "请点击下方按钮基于新版 Step1 重新生成后再确认进入 Step3。"
        )

    st.subheader("⚙️ 设计约束")
    constraints = st.text_input(
        "硬件、时间与框架约束（可选）",
        key="experiment_constraints",
        placeholder="例如：1 张 RTX 4090，24 小时，PyTorch，github:recommend",
        help=(
            "GitHub 模式可选：github:off / github:recommend / "
            "github:light_check / github:deep_check。默认 recommend。"
        ),
    )

    st.markdown(
        '<div class="step2-note">默认优先返回论文元数据中已有的代码库链接；'
        'GitHub 推荐不等于代码已验证可运行，真正运行验证留给 Step3/Step4。</div>',
        unsafe_allow_html=True,
    )

    experiment_markdown = S.load_experiment()
    plan_path = WATSON_DIR / "experiment_plan.json"
    plan = S.load_json(plan_path) if plan_path.exists() else None
    plan = plan if isinstance(plan, dict) else {}

    # ── Initial generation / full regeneration ──────────────────────────────
    if not experiment_markdown:
        generate_label = "🔬 生成实验方案"
    elif experiment_stale:
        generate_label = "🔄 基于新版 Step1 重新生成"
    else:
        generate_label = "♻️ 完整重新生成"
    g1, g2 = st.columns([1, 3])
    with g1:
        generate_btn = st.button(generate_label, type="primary", use_container_width=True)
    with g2:
        if experiment_markdown:
            revision_round = (plan.get("revision") or {}).get("round", state.get("experiment_revision_round", 0))
            if experiment_stale:
                approval = "已过期（来自旧 Step1）"
            else:
                approval = "已确认" if state.get("experiment_approved") else "待确认"
            st.caption(f"当前方案：修订轮次 {revision_round} · 状态 {approval}")

    generation_area = st.empty()

    if generate_btn:
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        from watson.agents import experiment as agent
        with generation_area.container():
            st.divider()
            stream_to_placeholder(
                agent.run(extra_constraints=constraints),
                "正在基于 Step1 证据设计实验方案...",
            )
            invalidate_after_experiment_change()
            st.success("✅ 实验设计完成！旧的 Step3-Step6 文件已保留，并标记为需要更新。")
        st.rerun()

    # ── Current plan ─────────────────────────────────────────────────────────
    experiment_markdown = S.load_experiment()
    plan = S.load_json(plan_path) if plan_path.exists() else {}
    plan = plan if isinstance(plan, dict) else {}

    if not experiment_markdown:
        st.info("尚未生成实验方案。点击上方“生成实验方案”开始 Step2。")
        return

    selected_baselines = [x for x in plan.get("selected_baselines", []) if isinstance(x, dict)]
    datasets = [x for x in plan.get("dataset_candidates", []) if isinstance(x, dict)]
    metrics = [x for x in plan.get("metric_candidates", []) if isinstance(x, dict)]
    validation = plan.get("validation_report") if isinstance(plan.get("validation_report"), dict) else {}

    st.divider()
    st.subheader("📋 当前实验方案")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("已选 Baseline", len(selected_baselines) or "—")
    s2.metric("数据集", len(datasets) or "—")
    s3.metric("评价指标", len(metrics) or "—")
    s4.metric("可追溯 Baseline", validation.get("must_cite_baseline_count", "—"))

    if selected_baselines:
        baseline_names = "　".join(
            f"`{item.get('role', 'baseline')}` {item.get('name', 'Unknown')}"
            for item in selected_baselines
        )
        st.caption(f"Baseline：{baseline_names}")

    with st.expander("📄 展开完整 experiment.md", expanded=True):
        st.markdown(experiment_markdown)

    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "⬇️ 下载 experiment.md",
            data=experiment_markdown,
            file_name="experiment.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with d2:
        if plan:
            import json as _json_module
            st.download_button(
                "⬇️ 下载 experiment_plan.json",
                data=_json_module.dumps(plan, ensure_ascii=False, indent=2),
                file_name="experiment_plan.json",
                mime="application/json",
                use_container_width=True,
            )

    # ── Human revision loop ──────────────────────────────────────────────────
    st.divider()
    st.subheader("🔁 修改或确认实验方案")
    st.markdown(
        "你可以直接描述需要修改的内容，例如："
        "“删除 BERT baseline，增加 Qwen2.5-7B；只保留两个数据集；增加效率指标和无路由消融实验”。"
    )

    feedback = st.text_area(
        "实验方案修改意见",
        key="experiment_feedback",
        height=130,
        placeholder=(
            "示例：\n"
            "1. 删除传统模型 baseline，仅保留 LLM-based 方法；\n"
            "2. 增加 XXX baseline；\n"
            "3. 删除数据集 A，增加数据集 B；\n"
            "4. 增加模块顺序和两组消融实验。"
        ),
    )

    r1, r2 = st.columns(2)
    with r1:
        revise_btn = st.button(
            "🔄 按意见重新生成",
            type="secondary",
            use_container_width=True,
            disabled=not feedback.strip(),
        )
    with r2:
        approve_btn = st.button(
            "✅ 方案无误，进入 Step 3",
            type="primary",
            use_container_width=True,
            disabled=experiment_stale,
            help="Step1 更新后必须先重新生成 Step2。" if experiment_stale else None,
        )

    if revise_btn:
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        from watson.agents import experiment as agent
        with generation_area.container():
            st.divider()
            stream_to_placeholder(
                agent.run(
                    extra_constraints=constraints,
                    revision_feedback=feedback.strip(),
                    regenerate=True,
                ),
                "正在依据修改意见重构完整实验方案...",
            )
            invalidate_after_experiment_change()
            st.success("✅ 实验方案已按意见重新生成。")
        st.session_state["_pending_experiment_feedback"] = ""
        st.rerun()

    if approve_btn:
        S.save_state(
            {
                "last_step": "experiment",
                "experiment_approved": True,
                "experiment_stale": False,
                "downstream_stale": True,
                "experiment_approved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        request_page_nav(f"{STEP_EMOJIS['code']} {STEP_NAMES['code']}")

def page_code():
    st.title("💻 Step 3: Code Generation")
    st.markdown("根据实验设计方案，生成可运行的 Python 实验脚本。")

    if not S.load_experiment():
        st.warning("请先完成 Step 2（Experiment Design）")
        return

    workflow_state = S.load_state()
    if workflow_state.get("experiment_stale", False):
        st.warning("Step1 已更新，当前实验方案已过期。请返回 Step2 重新生成并确认方案。")
        if st.button("↩️ 返回 Step 2", use_container_width=False):
            request_page_nav(f"{STEP_EMOJIS['experiment']} {STEP_NAMES['experiment']}")
        return

    if not workflow_state.get("experiment_approved", False):
        st.warning("当前实验方案尚未确认。请返回 Step2，在页面底部确认方案后再进入代码生成。")
        if st.button("↩️ 返回 Step 2", use_container_width=False):
            request_page_nav(f"{STEP_EMOJIS['experiment']} {STEP_NAMES['experiment']}")
        return

    if workflow_state.get("downstream_stale", False) and S.load_code():
        st.info("检测到旧版实验代码。该文件被保留用于对照，但应根据当前已确认方案重新生成。")

    ca, cb = st.columns(2)
    with ca:
        framework = st.selectbox("编程框架", ["PyTorch", "TensorFlow", "JAX", "HuggingFace Transformers"])
    with cb:
        extra = st.text_input("额外要求（可选）", placeholder="例如：使用 HuggingFace datasets")

    c1, c2 = st.columns([1, 4])
    with c1:
        run_btn = st.button("💻 生成代码", type="primary", use_container_width=True)
    with c2:
        if S.load_code() and st.button("📄 查看已有代码", use_container_width=True):
            st.code(S.load_code(), language="python")

    if run_btn:
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        st.divider()
        from watson.agents import code as agent
        stream_to_placeholder(agent.run(framework=framework, extra_notes=extra), "生成实验代码中...")
        S.save_state({"last_step": "code", "downstream_stale": False})
        st.success("✅ 代码生成完成！已保存至 experiments/experiment.py")
        st.rerun()
    elif S.load_code():
        st.divider()
        st.subheader("生成的实验代码")
        st.code(S.load_code(), language="python")


def page_run():
    st.title("▶️ Step 4: Run & Record")
    st.markdown("执行实验代码，实时捕获输出并记录结果。")

    if not S.load_code():
        st.warning("请先完成 Step 3（Code Generation）")
        return

    with st.expander("查看待执行代码"):
        st.code(S.load_code(), language="python")

    st.warning("⚠️ 即将在本地执行 Python 代码，请确认代码安全后点击下方按钮。")

    if st.button("▶️ 确认执行实验", type="primary"):
        st.divider()
        st.subheader("执行输出")
        output_placeholder = st.empty()
        full_output = ""
        from watson.agents import run as agent
        for chunk in agent.run(confirmed=True):
            full_output += chunk
            output_placeholder.code(full_output, language="text")
        st.success("✅ 实验执行完成！日志已保存至 .watson/run_log.txt")
        st.rerun()

    if S.load_run_log():
        st.divider()
        with st.expander("上次运行日志"):
            st.code(S.load_run_log(), language="text")

    if S.load_results():
        st.subheader("实验结果")
        st.markdown(S.load_results())


def page_analysis():
    st.title("📊 Step 5: Analysis & Iteration")
    st.markdown("分析实验结果，判断成功/失败，给出具体迭代建议。")

    if not S.load_run_log():
        st.warning("请先完成 Step 4（Run & Record）")
        return

    comment = st.text_area("补充说明（可选）",
                           placeholder="例如：训练损失正常但 ROUGE 低，怀疑过拟合...", height=80)

    c1, c2 = st.columns([1, 4])
    with c1:
        run_btn = st.button("📊 分析结果", type="primary", use_container_width=True)
    with c2:
        if S.load_analysis() and st.button("📄 查看已有分析", use_container_width=True):
            st.markdown(S.load_analysis())

    if run_btn:
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        st.divider()
        from watson.agents import analysis as agent
        stream_to_placeholder(agent.run(user_comment=comment), "分析实验结果中...")
        st.success("✅ 分析完成！")
        st.rerun()
    elif S.load_analysis():
        st.divider()
        st.subheader("分析报告")
        st.markdown(S.load_analysis())


def page_paper():
    import streamlit.components.v1 as _stc
    _stc.html("""<script>
(function(){
  function fit(el){
    var sy=window.parent.scrollY;
    el.style.overflowY='hidden';
    el.style.height='1px';
    el.style.height=Math.max(80,el.scrollHeight)+'px';
    window.parent.scrollTo({top:sy,behavior:'instant'});
  }
  function fitAll(){
    try{
      window.parent.document.querySelectorAll('textarea').forEach(function(el){
        fit(el);
        if(!el._ar){el._ar=true;el.addEventListener('input',function(){fit(this);});}
      });
    }catch(e){}
  }
  setTimeout(fitAll,150);setTimeout(fitAll,600);
  try{
    new MutationObserver(function(mutations){
      var hasNew=mutations.some(function(m){
        return Array.from(m.addedNodes).some(function(n){
          return n.nodeType===1&&(n.tagName==='TEXTAREA'||(n.querySelector&&n.querySelector('textarea')));
        });
      });
      if(hasNew)setTimeout(fitAll,80);
    }).observe(window.parent.document.body,{childList:true,subtree:true});
  }catch(e){}
})();
</script>""", height=0)

    from watson.agents.paper import SECTIONS, run_section, refine_section, assemble_paper

    st.title("📝 Step 6: Paper Writing")
    st.markdown("逐节生成 LaTeX 论文草稿，每节独立生成、可单独重写。")

    # ── Venue selector ────────────────────────────────────────────────────────
    target_venue = st.selectbox(
        "目标投稿 venue",
        ["NeurIPS", "ICML", "ICLR", "ACL", "EMNLP", "NAACL", "AAAI", "CVPR", "ICCV", "其他"],
        key="target_venue",
    )

    st.divider()

    # ── Template paper ────────────────────────────────────────────────────────
    st.subheader("📄 模板论文")

    # Auto-detect from Step 1: most similar paper (already sorted desc by similarity_score)
    top_conf = S.load_top_conf_papers()
    auto_template = top_conf[0] if top_conf else None

    use_custom = st.toggle("使用自定义模板论文", key="use_custom_template")

    if use_custom:
        ct1, ct2 = st.columns(2)
        with ct1:
            custom_title = st.text_input("论文标题", key="custom_tpl_title",
                                         placeholder="例：Attention Is All You Need")
        with ct2:
            custom_link  = st.text_input("论文链接（可选）", key="custom_tpl_link",
                                         placeholder="https://arxiv.org/abs/...")
        custom_abstract = st.text_area("摘要（可选，帮助风格仿写）", key="custom_tpl_abstract",
                                       height=80, placeholder="Paste abstract here...")
        if custom_title:
            template = {"title": custom_title, "link": custom_link,
                        "summary": custom_abstract, "venue": target_venue}
            S.save_paper_template(template)
        else:
            template = S.load_paper_template() or auto_template
    else:
        template = auto_template

    if template:
        sim = template.get("similarity_score")
        sim_str = f"　相同性 {sim}/5" if sim else ""
        st.caption(
            f"📌 **{template.get('title', '—')}**　`{template.get('venue','')}`{sim_str}"
            + (f"　[→ 查看]({template['link']})" if template.get("link") else "")
        )
    else:
        st.caption("⚠️ 未找到模板论文（请先完成 Step 1 或手动输入）")

    # ── LaTeX source download ─────────────────────────────────────────────────
    template_latex_sections: dict[str, str] = S.load_template_latex()
    _tpl_link = (template or {}).get("link", "")

    from watson.tools.arxiv_latex import extract_arxiv_id
    _has_arxiv = bool(extract_arxiv_id(_tpl_link)) if _tpl_link else False

    if _has_arxiv:
        _latex_cached = bool(template_latex_sections)
        _btn_label = "🔄 重新获取模板 LaTeX 源码" if _latex_cached else "📥 获取模板 LaTeX 源码"
        if st.button(_btn_label, use_container_width=False):
            from watson.tools.arxiv_latex import fetch_template_latex
            with st.spinner("正在从 arXiv 下载 LaTeX 源码..."):
                template_latex_sections = fetch_template_latex(_tpl_link)
            if template_latex_sections:
                S.save_template_latex(template_latex_sections)
                st.success(f"✅ 解析完成，找到 {len(template_latex_sections)} 个节")
                st.rerun()
            else:
                st.warning("⚠️ 下载失败或该论文未提供 LaTeX 源码（部分论文仅有 PDF）")
    elif _tpl_link:
        st.caption("_ℹ️ 该模板论文非 arXiv 链接，无法自动获取 LaTeX 源码_")

    st.divider()

    # ── Per-section generation ────────────────────────────────────────────────
    import re as _re
    from watson.tools.writing_tools import TOOLS, run_tool as _run_tool

    _INLINE_TOOLS = ["表达润色", "去 AI 味", "缩写", "扩写", "逻辑检查"]

    def _auto_height(text: str, min_h: int = 120) -> int:
        lines = text.count("\n") + 1 if text else 1
        return max(min_h, lines * 21 + 44)

    def _strip_latex(text: str) -> str:
        """Remove structural LaTeX commands, keep prose and math."""
        t = _re.sub(r'\\begin\{[^}]*\}', '', text)
        t = _re.sub(r'\\end\{[^}]*\}', '', t)
        t = _re.sub(r'\\(?:sub)*section\*?\{[^}]*\}', '', t)
        t = _re.sub(r'\\(?:documentclass|usepackage|title|author|date|maketitle)[^\n]*', '', t)
        t = _re.sub(r'\n{3,}', '\n\n', t)
        return t.strip()

    # Check on RAW text (before _strip_latex) so \begin{figure} is still present
    _SKIPPABLE_RE = _re.compile(
        r'\\begin\s*\{(?:figure|table|algorithm|algorithmic|listing|lstlisting'
        r'|tikzpicture|subfigure|wrapfigure)\*?\}'
        r'|\\(?:includegraphics|toprule|midrule|bottomrule)\b',
        _re.IGNORECASE,
    )

    def _is_skippable_para(text: str) -> bool:
        return bool(_SKIPPABLE_RE.search(text))

    _LABEL_PARA_RE = _re.compile(
        r'^\\(?:textbf|textit|emph|textsc|noindent)\s*\{',
    )

    def _is_label_para(text: str) -> bool:
        """Paragraph is a formatted inline label (bold/italic wrapper), not standalone prose."""
        return bool(_LABEL_PARA_RE.match(text.strip()))

    def _split_paras(text: str, short_threshold: int = 80) -> list[str]:
        t = _re.sub(r'\\par\b', '\n\n', text)
        raw_parts = [p for p in t.split("\n\n") if p.strip()]
        # Filter figure/table/algorithm blocks on raw text before stripping
        prose_parts = [p for p in raw_parts if not _is_skippable_para(p)]
        stripped = [_strip_latex(p) for p in prose_parts]
        stripped = [p for p in stripped if p]
        if not stripped:
            return [""]
        # Merge short paragraphs and formatted labels into the next paragraph
        merged: list[str] = []
        carry = ""
        for p in stripped:
            if len(p) < short_threshold or _is_label_para(p):
                carry = (carry + "\n\n" + p).strip() if carry else p
            else:
                if carry:
                    merged.append((carry + "\n\n" + p).strip())
                    carry = ""
                else:
                    merged.append(p)
        if carry:
            if merged:
                merged[-1] = (merged[-1] + "\n\n" + carry).strip()
            else:
                merged.append(carry)
        return merged or [""]

    def _section_complete(sk: str) -> bool:
        """True only when every paragraph in the section has content.
        Skippable paragraphs are already excluded from session_state by _split_paras."""
        if st.session_state.get("_active_section") == sk:
            count = st.session_state.get(f"para_count_{sk}", 0)
            if count == 0:
                return False
            return all(
                st.session_state.get(f"para_{sk}_{i}", "").strip()
                for i in range(count)
            )
        content = S.load_paper_section(sk)
        if not content:
            return False
        # Raw split so \begin{figure} etc. are still present for detection
        raw_parts = [p.strip() for p in _re.sub(r'\\par\b', '\n\n', content).split("\n\n") if p.strip()]
        prose_parts = [p for p in raw_parts if not _is_skippable_para(p)]
        if not prose_parts:
            return bool(raw_parts)
        return all(p for p in prose_parts)

    def _exec_fig_code(code: str) -> bytes:
        """Execute matplotlib code in a sandbox and return PNG bytes."""
        import io
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        matplotlib.rcParams.update({
            'font.size': 14, 'axes.labelsize': 14,
            'xtick.labelsize': 12, 'ytick.labelsize': 12,
            'legend.fontsize': 12, 'axes.titlesize': 14,
        })
        plt.close('all')
        exec(code, {'plt': plt, 'np': np, 'matplotlib': matplotlib})  # noqa: S102
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close('all')
        buf.seek(0)
        return buf.read()

    st.subheader("✍️ 论文各节")
    any_generated = any(S.load_paper_section(k) for k, _ in SECTIONS)

    # ── Section selector ──────────────────────────────────────────────────────
    _sec_idx = st.selectbox(
        "当前章节",
        range(len(SECTIONS)),
        format_func=lambda i: (
            f"{'✅' if _section_complete(SECTIONS[i][0]) else '⬜'}  {SECTIONS[i][1]}"
        ),
        key="section_selector",
        label_visibility="collapsed",
    )
    section_key, section_name = SECTIONS[_sec_idx]
    tpl_latex = template_latex_sections.get(section_key)

    # ── Initialize paragraph state for this section ───────────────────────────
    _count_key = f"para_count_{section_key}"

    # ── Split template into per-paragraph pieces (needed for init count) ─────
    _tpl_paras = _split_paras(tpl_latex) if tpl_latex else []

    # Always validate session_state count against what the file contains.
    _existing = S.load_paper_section(section_key)
    if _existing:
        _file_paras = _split_paras(_existing)
    else:
        # No generated content yet — pre-populate with one slot per template paragraph
        _file_paras = [""] * max(1, len(_tpl_paras))
    _file_count = len(_file_paras)

    _section_changed = st.session_state.get("_active_section") != section_key
    _count_stale = st.session_state.get(_count_key, 0) != _file_count

    _active_para_key = f"_active_para_{section_key}"
    if _section_changed or _count_stale or _count_key not in st.session_state:
        st.session_state["_active_section"] = section_key
        st.session_state[_count_key] = _file_count
        st.session_state[_active_para_key] = 0
        for _i, _p in enumerate(_file_paras):
            st.session_state[f"para_{section_key}_{_i}"] = _p

    # ── Apply any pending updates before widgets are instantiated ────────────
    _pending_key = f"_pending_replace_{section_key}"
    if _pending_key in st.session_state:
        _pr = st.session_state.pop(_pending_key)
        st.session_state[f"para_{section_key}_{_pr['idx']}"] = _pr["text"]

    _pending_gen_key = f"_pending_gen_{section_key}"
    if _pending_gen_key in st.session_state:
        _pg_paras = st.session_state.pop(_pending_gen_key)
        _old_count = st.session_state.get(_count_key, 0)
        st.session_state[_count_key] = len(_pg_paras)
        for _i, _p in enumerate(_pg_paras):
            st.session_state[f"para_{section_key}_{_i}"] = _p
        for _i in range(len(_pg_paras), _old_count):
            st.session_state.pop(f"para_{section_key}_{_i}", None)

    # ── Paragraph navigator ───────────────────────────────────────────────────
    _para_count = st.session_state[_count_key]
    if _active_para_key not in st.session_state:
        st.session_state[_active_para_key] = 0
    _cur = min(st.session_state[_active_para_key], _para_count - 1)

    # Use on_click callbacks to avoid st.rerun() inside button handlers,
    # which can cause the section selectbox to reset to index 0.
    def _nav_prev():
        st.session_state[_active_para_key] = _cur - 1
        st.session_state.pop(f"_tool_result_{section_key}", None)

    def _nav_next():
        st.session_state[_active_para_key] = _cur + 1
        st.session_state.pop(f"_tool_result_{section_key}", None)

    def _nav_add():
        st.session_state[f"para_{section_key}_{_para_count}"] = ""
        st.session_state[_count_key] = _para_count + 1
        st.session_state[_active_para_key] = _para_count

    def _nav_del():
        for _j in range(_cur, _para_count - 1):
            st.session_state[f"para_{section_key}_{_j}"] = \
                st.session_state.get(f"para_{section_key}_{_j + 1}", "")
        st.session_state.pop(f"para_{section_key}_{_para_count - 1}", None)
        st.session_state[_count_key] = _para_count - 1
        st.session_state[_active_para_key] = min(_cur, _para_count - 2)

    _nc1, _nc2, _nc3, _nc4, _nc5 = st.columns([1, 1, 3, 1, 1])
    with _nc1:
        st.button("◀", key=f"prev_{section_key}", disabled=_cur == 0,
                  on_click=_nav_prev, use_container_width=True)
    with _nc2:
        st.button("▶", key=f"next_{section_key}", disabled=_cur == _para_count - 1,
                  on_click=_nav_next, use_container_width=True)
    with _nc3:
        st.markdown(f"<div style='text-align:center;padding-top:6px'>第 {_cur+1} / {_para_count} 段</div>",
                    unsafe_allow_html=True)
    with _nc4:
        st.button("＋", key=f"add_{section_key}", help="在末尾新增一段",
                  on_click=_nav_add, use_container_width=True)
    with _nc5:
        if _para_count > 1:
            st.button("🗑️", key=f"del_{section_key}_{_cur}", help="删除本段",
                      on_click=_nav_del, use_container_width=True)

    _pk = f"para_{section_key}_{_cur}"

    # ── Template paragraph for current slot ───────────────────────────────────
    if _tpl_paras and _cur < len(_tpl_paras):
        _th1, _th2 = st.columns([6, 1])
        with _th1:
            st.caption(f"📄 模板第 {_cur+1} 段（{len(_tpl_paras[_cur])} 字符）")
        with _th2:
            _hint_btn = st.button("💡 思路", key=f"hint_btn_{section_key}_{_cur}",
                                  use_container_width=True)
        st.text_area(
            label="",
            value=_tpl_paras[_cur],
            disabled=True,
            key=f"tpl_para_{section_key}_{_cur}",
            label_visibility="collapsed",
        )
        _hint_key = f"_writing_hint_{section_key}_{_cur}"
        if _hint_btn:
            if not _api_ok():
                st.error("⚠️ 请先配置 API Key")
            else:
                _idea = S.load_idea() or ""
                _tpl_para_text = _tpl_paras[_cur]
                _hint_system = (
                    "你是一位资深 AI 科研论文写作顾问。"
                    "你的任务是：给定模板论文中某一段的原文，以及用户自己的研究方向，"
                    "用 2～4 句简洁的中文，告诉用户：\n"
                    "1. 这段模板在写什么（核心功能/逻辑）；\n"
                    "2. 对应到用户自己的工作，这段应该写什么内容（具体到论点或数据）。\n"
                    "输出直接给出两点分析，不要多余的客套话。"
                )
                _hint_user = (
                    f"【章节】{section_name}\n\n"
                    f"【模板段落】\n{_tpl_para_text}\n\n"
                    + (f"【用户研究方向/Idea】\n{_idea[:800]}\n\n" if _idea else "")
                    + "请给出写作思路分析。"
                )
                from watson.llm import build_messages, complete_chat
                with st.spinner("分析思路中..."):
                    _hint_msgs = build_messages(_hint_system, _hint_user)
                    _hint_result = complete_chat(_hint_msgs, temperature=0.4, max_tokens=300)
                st.session_state[_hint_key] = _hint_result
        _cur_hint_key = f"_writing_hint_{section_key}_{_cur}"
        if _cur_hint_key in st.session_state:
            st.info(st.session_state[_cur_hint_key])
            # ── Generate current paragraph using hint ─────────────────────────
            _gen_para_btn = st.button(
                "✍️ 结合思路生成本段",
                key=f"gen_para_{section_key}_{_cur}",
            )
            if _gen_para_btn:
                if not _api_ok():
                    st.error("⚠️ 请先配置 API Key")
                else:
                    _gp_system = (
                        f"你是一位顶级 AI 会议论文写手，正在为 {target_venue} 撰写论文的 {section_name} 节。"
                        "根据提供的模板段落、写作思路和研究 Idea，只输出当前段的 LaTeX 代码，"
                        "不要任何解释、标题或额外段落。风格仿照模板，内容替换为本研究。"
                    )
                    _gp_tpl = (_tpl_paras[_cur] if _tpl_paras and _cur < len(_tpl_paras) else "")
                    _gp_idea = S.load_idea() or ""
                    _gp_user = (
                        f"【写作思路】\n{st.session_state[_cur_hint_key]}\n\n"
                        + (f"【模板段落（仿写句式结构）】\n{_gp_tpl}\n\n" if _gp_tpl else "")
                        + (f"【研究 Idea】\n{_gp_idea[:600]}\n\n" if _gp_idea else "")
                        + "请输出本段的 LaTeX 代码。"
                    )
                    from watson.llm import build_messages as _bm, stream_chat as _sc
                    _gp_ph = st.empty()
                    _gp_text = ""
                    with st.spinner("正在生成本段..."):
                        for _gp_chunk in _sc(_bm(_gp_system, _gp_user), temperature=0.4, max_tokens=800):
                            _gp_text += _gp_chunk
                            _gp_ph.markdown(f"```latex\n{_gp_text}▌\n```")
                    _gp_ph.empty()
                    st.session_state[_pending_key] = {"idx": _cur, "text": _gp_text.strip()}
                    st.rerun()

    # ── Generate / Save ───────────────────────────────────────────────────────
    _ab2, _ab3, _ = st.columns([1, 1, 4])
    with _ab2:
        _gen_label = "🔄 重新生成" if S.load_paper_section(section_key) else "✍️ 生成整节"
        _gen_btn = st.button(_gen_label, key=f"gen_{section_key}", use_container_width=True)
    with _ab3:
        _save_btn = st.button("💾 保存整节", key=f"save_{section_key}", use_container_width=True)

    if tpl_latex:
        st.caption("✓ 生成时将参考上方模板原文的句式与结构")

    _hist_key = f"_section_history_{section_key}"

    if _gen_btn:
        if not _api_ok():
            st.error("⚠️ 请先配置 API Key")
        else:
            _gph = st.empty()
            _gtext = ""
            _out_hist: list = []
            with st.spinner(f"正在撰写 {section_name}..."):
                for chunk in run_section(section_key, template, target_venue,
                                         template_latex=tpl_latex,
                                         out_messages=_out_hist):
                    _gtext += chunk
                    _gph.markdown(f"```latex\n{_gtext}▌\n```")
            _gph.empty()
            S.save_paper_section(section_key, _gtext)
            st.session_state[_hist_key] = _out_hist
            st.session_state[_pending_gen_key] = _split_paras(_gtext)
            st.rerun()

    if _save_btn:
        _full = "\n\n".join(
            st.session_state.get(f"para_{section_key}_{_i}", "")
            for _i in range(st.session_state[_count_key])
            if st.session_state.get(f"para_{section_key}_{_i}", "").strip()
        )
        if _full:
            S.save_paper_section(section_key, _full)
            st.toast(f"✅ {section_name} 已保存")

    # ── Section-level refinement via conversation history ────────────────────
    _stored_hist = st.session_state.get(_hist_key)
    if _stored_hist:
        with st.expander(
            f"💬 对话改写（已有 {len(_stored_hist) // 2} 轮历史）",
            expanded=False,
        ):
            _refine_inst = st.text_area(
                "改写指令",
                key=f"refine_inst_{section_key}",
                placeholder=(
                    "例如：把这一节压缩约 200 词；"
                    "加强 Motivation 部分；突出与 XXX 方法的区别…"
                ),
                height=80,
            )
            _rr1, _rr2 = st.columns([2, 1])
            with _rr1:
                _refine_btn = st.button(
                    "✏️ 改写本节", key=f"refine_{section_key}", use_container_width=True
                )
            with _rr2:
                _reset_hist_btn = st.button(
                    "🔄 重置对话", key=f"reset_hist_{section_key}", use_container_width=True
                )

            if _refine_btn:
                if not _refine_inst.strip():
                    st.warning("请输入改写指令")
                elif not _api_ok():
                    st.error("⚠️ 请先配置 API Key")
                else:
                    _rout: list = []
                    _rph = st.empty()
                    _rtext = ""
                    with st.spinner(f"改写 {section_name} 中..."):
                        for _rchunk in refine_section(
                            section_key, _refine_inst,
                            _stored_hist, target_venue,
                            out_messages=_rout,
                        ):
                            _rtext += _rchunk
                            _rph.markdown(f"```latex\n{_rtext}▌\n```")
                    _rph.empty()
                    st.session_state[_hist_key] = _rout
                    st.session_state[_pending_gen_key] = _split_paras(_rtext)
                    st.rerun()

            if _reset_hist_btn:
                del st.session_state[_hist_key]
                st.toast("✅ 对话历史已清除")
                st.rerun()

    # ── Editing area ──────────────────────────────────────────────────────────
    st.caption(f"✏️ 第 {_cur+1} 段")
    _para_val = st.text_area(
        "段落内容",
        key=_pk,
        placeholder=f"在此输入第 {_cur+1} 段...",
        label_visibility="collapsed",
    )
    st.caption(f"{len(_para_val or '')} 字符")

    # ── Writing tools ─────────────────────────────────────────────────────────
    _tc1, _tc2 = st.columns([4, 1])
    with _tc1:
        _tool_sel = st.selectbox(
            "工具", _INLINE_TOOLS,
            key=f"tool_sel_{section_key}",
            label_visibility="collapsed",
        )
    with _tc2:
        _tool_btn = st.button("▶️ 运行", key=f"tool_btn_{section_key}",
                              use_container_width=True)

    if _tool_btn:
        _para_text = st.session_state.get(_pk, "")
        if not _para_text.strip():
            st.warning("请先输入段落内容")
        elif not _api_ok():
            st.error("⚠️ 请先配置 API Key")
        else:
            _tool_hint = ""
            if _tool_sel in ("扩写", "缩写") and tpl_latex:
                def _wc(t: str) -> int:
                    return len(t.split())
                _para_words = _wc(_para_text)
                _total_words = sum(
                    _wc(st.session_state.get(f"para_{section_key}_{_j}", ""))
                    for _j in range(_para_count)
                )
                _tpl_words = _wc(tpl_latex)
                _share = _para_words / _total_words if _total_words > 0 else 1.0 / max(_para_count, 1)
                _target_words = max(10, round(_tpl_words * _share))
                if _tool_sel == "扩写" and _para_words < _target_words:
                    _lo, _hi = _target_words - 30, _target_words + 30
                    _tool_hint = (
                        f"【词数硬约束】本段当前 {_para_words} 词，目标 {_target_words} 词。"
                        f"输出词数必须在 {_lo}～{_hi} 词之间，不得超出此范围。"
                        f"输出前请自行逐词统计，若词数不足 {_lo} 则继续补写，若超过 {_hi} 则删减，直至达标。"
                    )
                elif _tool_sel == "缩写" and _para_words > _target_words:
                    _lo, _hi = _target_words - 30, _target_words + 30
                    _tool_hint = (
                        f"【词数硬约束】本段当前 {_para_words} 词，目标 {_target_words} 词。"
                        f"输出词数必须在 {_lo}～{_hi} 词之间，不得超出此范围。"
                        f"输出前请自行逐词统计，若词数仍超过 {_hi} 则继续删减，若低于 {_lo} 则补回，直至达标。"
                    )
            _tres = ""
            _tph = st.empty()
            with st.spinner(f"正在运行「{_tool_sel}」（第 {_cur+1} 段）..."):
                for _chunk in _run_tool(_tool_sel, _para_text, hint=_tool_hint):
                    _tres += _chunk
                    _tph.markdown(_tres + "▌")
            _tph.empty()
            st.session_state[f"_tool_result_{section_key}"] = {"text": _tres, "para_idx": _cur}

    # ── Tool result ───────────────────────────────────────────────────────────
    _tr_data = st.session_state.get(f"_tool_result_{section_key}")
    if _tr_data and _tr_data["para_idx"] == _cur:
        _tr_text = _tr_data["text"]
        with st.expander(f"📋 工具输出", expanded=True):
            st.markdown(_tr_text)
            if st.button(f"↑ 替换第 {_cur+1} 段", key=f"apply_tool_{section_key}"):
                _m = _re.search(
                    r"Part\s*1\s*\[LaTeX\][^\n]*\n```(?:latex)?\n(.*?)```",
                    _tr_text, _re.DOTALL)
                if not _m:
                    _m = _re.search(
                        r"Part\s*1\s*\[LaTeX\][^\n]*\n(.*?)(?=\n\s*Part\s*2\b|\Z)",
                        _tr_text, _re.DOTALL)
                _apply = _m.group(1).strip() if _m else _tr_text
                st.session_state[_pending_key] = {"idx": _cur, "text": _apply}
                del st.session_state[f"_tool_result_{section_key}"]
                st.rerun()

    # ── Figure insertion (not for Abstract / Conclusion) ─────────────────────
    if section_key not in ("abstract", "conclusion"):
        _figs_dir     = S.PAPER_DIR / "figures"
        _section_figs = sorted(_figs_dir.glob(f"{section_key}_*.png")) if _figs_dir.exists() else []
        _fig_meta_key = f"_fig_meta_{section_key}"   # {fname: {"caption": ..., "desc": ...}}

        # Keys for the active drawing session
        _fig_desc_key        = f"_fig_desc_{section_key}"
        _fig_code_key        = f"_fig_code_{section_key}"
        _fig_img_key         = f"_fig_img_{section_key}"
        _fig_cap_pending_key = f"_fig_cap_pending_{section_key}"
        _fig_cap_done_key    = f"_fig_cap_done_{section_key}"
        _fig_caption_key     = f"fig_caption_{section_key}"
        _fig_clear_key       = f"_fig_clear_{section_key}"

        # Clear all drawing-session state after a successful insert
        if st.session_state.pop(_fig_clear_key, False):
            for _ck in [_fig_desc_key, _fig_code_key, _fig_img_key,
                        _fig_cap_pending_key, _fig_cap_done_key, _fig_caption_key,
                        f"fig_code_edit_{section_key}"]:
                st.session_state.pop(_ck, None)

        _expander_label = (
            f"📊 插入图片（本节已有 {len(_section_figs)} 张）"
            if _section_figs else "📊 插入图片"
        )
        with st.expander(_expander_label, expanded=False):

            # ── Existing figures list ─────────────────────────────────────────
            if _section_figs:
                _meta = st.session_state.get(_fig_meta_key, {})
                _thumb_cols = st.columns(min(len(_section_figs), 4))
                for _fi, _ff in enumerate(_section_figs):
                    with _thumb_cols[_fi % 4]:
                        st.image(str(_ff), use_container_width=True)
                        _info = _meta.get(_ff.name, {})
                        _cap_label = _info.get("caption", "")
                        _desc_label = _info.get("desc", "")
                        st.caption(
                            f"**Fig {_fi + 1}**"
                            + (f"  \n{_cap_label}" if _cap_label else "")
                            + (f"  \n_{_desc_label}_" if _desc_label and not _cap_label else "")
                        )
                st.divider()

            # ── New figure creation ───────────────────────────────────────────
            _fig_desc = st.text_area(
                "描述数据和图表类型",
                key=_fig_desc_key,
                placeholder=(
                    "例如：对比 4 个模型在 3 个数据集上的 F1 分数（给出具体数值），"
                    "画分组柱状图，每组对应一个数据集，每根柱子代表一个模型"
                ),
                height=80,
            )

            _fc1, _fc2 = st.columns([1, 3])
            with _fc1:
                _fig_gen_btn = st.button("🤖 生成代码", key=f"fig_gen_{section_key}",
                                         use_container_width=True)

            if _fig_gen_btn:
                if not _fig_desc.strip():
                    st.warning("请先描述图表内容")
                elif not _api_ok():
                    st.error("⚠️ 请先配置 API Key")
                else:
                    from watson.tools.writing_tools import generate_figure_code as _gfc
                    _fph = st.empty()
                    _fcode = ""
                    with st.spinner("生成代码中..."):
                        for _fchunk in _gfc(_fig_desc):
                            _fcode += _fchunk
                            _fph.code(_fcode, language="python")
                    _fph.empty()
                    _fcode = _re.sub(r'^```python\s*\n?', '', _fcode.strip(), flags=_re.MULTILINE)
                    _fcode = _re.sub(r'\n?```\s*$', '', _fcode.strip(), flags=_re.MULTILINE)
                    st.session_state[_fig_code_key] = _fcode.strip()
                    st.session_state.pop(_fig_img_key, None)
                    st.rerun()

            if _fig_code_key in st.session_state:
                _fig_code_edit = st.text_area(
                    "Python 代码（可修改后重新运行）",
                    value=st.session_state[_fig_code_key],
                    key=f"fig_code_edit_{section_key}",
                    height=220,
                )
                _fr1, _fr2 = st.columns([1, 3])
                with _fr1:
                    _fig_run_btn = st.button("▶️ 运行画图", key=f"fig_run_{section_key}",
                                             use_container_width=True)
                if _fig_run_btn:
                    try:
                        _fig_bytes = _exec_fig_code(_fig_code_edit)
                        st.session_state[_fig_img_key] = _fig_bytes
                        st.session_state.pop(_fig_cap_done_key, None)
                        st.session_state.pop(_fig_cap_pending_key, None)
                        st.rerun()
                    except Exception as _fe:
                        st.error(f"运行出错：{_fe}")

            if _fig_img_key in st.session_state:
                st.image(st.session_state[_fig_img_key], use_container_width=True)

                # Auto-generate caption once when image first appears
                if not st.session_state.get(_fig_cap_done_key) and _api_ok():
                    _cap_desc = st.session_state.get(_fig_desc_key, "").strip()
                    if _cap_desc:
                        from watson.llm import build_messages as _bm, complete_chat as _cc
                        _cap_sys = (
                            "你是一位学术论文编辑。根据图表描述，"
                            "输出一句符合顶级会议规范的英文图标题（Figure caption）。\n"
                            "- Sentence case，末尾加句号\n"
                            "- 不加 'Figure X:' 前缀\n"
                            "- 只输出标题文本"
                        )
                        with st.spinner("自动生成图标题..."):
                            _cap_auto = _cc(_bm(_cap_sys, _cap_desc),
                                            temperature=0.3, max_tokens=120)
                        st.session_state[_fig_cap_pending_key] = _cap_auto.strip()
                        st.session_state[_fig_cap_done_key] = True
                        st.rerun()

                # Apply pending caption BEFORE the widget renders
                if _fig_cap_pending_key in st.session_state:
                    st.session_state[_fig_caption_key] = st.session_state.pop(_fig_cap_pending_key)

                _cap1, _cap2 = st.columns([4, 1])
                with _cap1:
                    _fig_caption = st.text_input(
                        "图标题（英文，可编辑）",
                        key=_fig_caption_key,
                    )
                with _cap2:
                    _fig_ok_btn = st.button("✅ 插入", key=f"fig_ok_{section_key}",
                                            use_container_width=True)
                if _fig_ok_btn:
                    _figs_dir.mkdir(parents=True, exist_ok=True)
                    _existing = list(_figs_dir.glob(f"{section_key}_*.png"))
                    _fig_n = len(_existing) + 1
                    _fig_fname = f"{section_key}_{_fig_n}.png"
                    (_figs_dir / _fig_fname).write_bytes(st.session_state[_fig_img_key])
                    _caption_str = _fig_caption.strip() or "TODO: add caption."
                    # Save metadata for the figure list
                    _meta = st.session_state.get(_fig_meta_key, {})
                    _meta[_fig_fname] = {
                        "caption": _caption_str,
                        "desc": st.session_state.get(_fig_desc_key, "").strip(),
                    }
                    st.session_state[_fig_meta_key] = _meta
                    # Insert LaTeX into current paragraph
                    _fig_latex = (
                        f"\n\\begin{{figure}}[t]\n"
                        f"    \\centering\n"
                        f"    \\includegraphics[width=0.8\\linewidth]{{figures/{_fig_fname}}}\n"
                        f"    \\caption{{{_caption_str}}}\n"
                        f"    \\label{{fig:{section_key}_{_fig_n}}}\n"
                        f"\\end{{figure}}\n"
                    )
                    _cur_para_text = st.session_state.get(_pk, "")
                    st.session_state[_pending_key] = {
                        "idx": _cur,
                        "text": (_cur_para_text + _fig_latex).strip(),
                    }
                    # Schedule clear of drawing-session state on next run
                    st.session_state[_fig_clear_key] = True
                    st.toast(f"✅ 图片已保存并插入第 {_cur + 1} 段")
                    st.rerun()

    st.divider()

    # ── Writing Toolkit ───────────────────────────────────────────────────────
    with st.expander("✏️ 写作工具箱（图标题 / 表标题 / 实验分析）", expanded=False):
        st.caption("来自 awesome-ai-research-writing 的实战 prompt，复制即用。")
        tool_name = st.selectbox(
            "选择工具",
            list(TOOLS.keys()),
            format_func=lambda k: f"{k}　—　{TOOLS[k]['desc']}",
            key="writing_tool_select",
        )
        tool = TOOLS[tool_name]
        user_input = st.text_area(
            tool["input_label"],
            placeholder=tool["input_placeholder"],
            height=180,
            key="writing_tool_input",
        )
        if st.button("▶️ 运行", key="writing_tool_run", type="primary"):
            if not user_input.strip():
                st.warning("请先输入内容")
            elif not _api_ok():
                st.error("⚠️ 请先配置 API Key")
            else:
                ph = st.empty()
                result = ""
                with st.spinner(f"正在运行「{tool_name}」..."):
                    for chunk in _run_tool(tool_name, user_input.strip()):
                        result += chunk
                        ph.markdown(result + "▌")
                ph.markdown(result)

    st.divider()

    # ── Assemble & download ───────────────────────────────────────────────────
    if any_generated:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📦 合并为 paper.tex", use_container_width=True):
                full = assemble_paper(target_venue)
                st.success(f"✅ 已保存至 paper/paper.tex（{len(full)} 字符）")
        with col_b:
            paper_content = S.load_paper()
            if paper_content:
                st.download_button("⬇️ 下载 paper.tex", data=paper_content,
                                   file_name="paper.tex", mime="text/plain",
                                   use_container_width=True)


# ── Router ────────────────────────────────────────────────────────────────────

PAGES = {
    "📋 总览": page_overview,
    **{f"{STEP_EMOJIS[s]} {STEP_NAMES[s]}": globals()[f"page_{s}" if s != "run" else "page_run"]
       for s in STEPS},
}

# Manual mapping to avoid naming issues
PAGES = {
    "📋 总览":                                        page_overview,
    f"{STEP_EMOJIS['idea']} {STEP_NAMES['idea']}":         page_idea,
    f"{STEP_EMOJIS['experiment']} {STEP_NAMES['experiment']}": page_experiment,
    f"{STEP_EMOJIS['code']} {STEP_NAMES['code']}":         page_code,
    f"{STEP_EMOJIS['run']} {STEP_NAMES['run']}":           page_run,
    f"{STEP_EMOJIS['analysis']} {STEP_NAMES['analysis']}": page_analysis,
    f"{STEP_EMOJIS['paper']} {STEP_NAMES['paper']}":       page_paper,
}

PAGES[page]()
