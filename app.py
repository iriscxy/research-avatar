"""Watson — Streamlit Web UI.  Run:  streamlit run app.py"""

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from watson.config import STEP_NAMES, STEP_EMOJIS, STEPS
from watson import state as S

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Watson · AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    page_options = ["📋 总览"] + [f"{STEP_EMOJIS[s]} {STEP_NAMES[s]}" for s in STEPS]
    page = st.radio("导航", page_options, label_visibility="collapsed", key="page_nav")

    st.divider()

    # Editable current idea
    st.markdown("**当前研究方向**")
    if "sidebar_idea" not in st.session_state:
        st.session_state["sidebar_idea"] = S.load_idea() or ""
    sidebar_idea = st.text_area("研究方向", key="sidebar_idea", height=100,
                                label_visibility="collapsed",
                                placeholder="在此输入或修改研究方向...")
    if st.button("💾 保存研究方向", use_container_width=True):
        S.save_file(S.IDEA_FILE, f"# Research Idea\n\n{sidebar_idea}\n")
        S.save_state({"idea": sidebar_idea})
        st.session_state["idea_input"] = sidebar_idea   # sync Step-1 text area
        st.toast("✅ 研究方向已保存")


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


def _paper_card(p: dict):
    with st.container(border=True):
        st.markdown(f"**{p['title']}**")

        venue = p.get("venue", "")
        authors = ", ".join(p.get("authors", [])[:3])
        if len(p.get("authors", [])) > 3:
            authors += " et al."
        score = p.get("relevance_score", 0)
        stars = "★" * score + "☆" * (5 - score) if score else ""
        venue_str = f"🏛️ **{venue}**  ·  " if venue else ""
        authors_str = f"👤 {authors}" if authors else ""
        score_str = f"  ·  {stars} {score}/5" if score else ""
        st.caption(f"{venue_str}{authors_str}{score_str}")

        summary = p.get("summary", "")
        if summary:
            with st.expander("摘要"):
                st.write(summary[:400])

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

        link_cols = st.columns([1, 1, 4])
        if p.get("link"):
            with link_cols[0]:
                st.link_button("查看论文 ↗", p["link"])
        if p.get("pdf"):
            with link_cols[1]:
                st.link_button("📄 Camera-ready PDF", p["pdf"])


def _render_papers():
    top_conf = S.load_top_conf_papers()
    if not top_conf:
        return
    st.divider()
    state = S.load_state()
    relevant_total = state.get("relevant_total", len(top_conf))
    scores = [p["relevance_score"] for p in top_conf if p.get("relevance_score")]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    st.subheader("📚 顶会文献调研结果")
    st.caption(f"共找到 **{relevant_total}** 篇相关论文，按相关性展示最高的 **{len(top_conf)}** 篇  ·  展示论文平均相关性 **{avg_score}/5**")
    for p in top_conf:
        _paper_card(p)


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
    from watson.agents.idea import STYLE_CONFIG

    st.title("💡 Step 1: Idea Validation")
    st.markdown(
        "输入研究方向，选择审稿风格，Watson 从顶会 acceptance list 检索相关论文，"
        "逐篇对比后给出评审意见。未通过可让 Watson 基于文献提出改进方向，循环迭代。"
    )

    if "idea_input" not in st.session_state:
        st.session_state["idea_input"] = S.load_idea() or ""
    if "idea_style" not in st.session_state:
        st.session_state["idea_style"] = "ml"
    if "idea_round" not in st.session_state:
        st.session_state["idea_round"] = 1

    idea_input = st.text_area(
        "研究方向 / 研究 Idea", key="idea_input", height=150,
        placeholder="例如：研究 MoE 架构在医疗文本摘要中的应用，通过专家路由让不同 expert 处理不同医学信息维度...",
    )

    style_options = {
        "ml":  "🧠 ML（NeurIPS / ICML / ICLR）",
        "nlp": "📝 NLP（ACL / EMNLP）",
        "cv":  "👁️ CV（CVPR / ICCV）",
    }
    selected_label = st.radio(
        "审稿风格",
        options=list(style_options.values()),
        index=list(style_options.keys()).index(st.session_state["idea_style"]),
        horizontal=True,
    )
    selected_style = [k for k, v in style_options.items() if v == selected_label][0]
    st.session_state["idea_style"] = selected_style

    c1, c2 = st.columns([1, 1])
    with c1:
        run_btn = st.button("🚀 开始验证", type="primary", use_container_width=True) \
                  or st.session_state.pop("trigger_validate", False)
    with c2:
        if st.button("🗑️ 清空重写", use_container_width=True):
            st.session_state["idea_input"] = ""
            st.session_state["idea_round"] = 1
            st.session_state.pop("idea_proposal", None)
            st.rerun()

    # ── Run validation ────────────────────────────────────────────────────────
    if run_btn:
        if not idea_input.strip():
            st.error("请输入研究方向")
            return
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        st.session_state.pop("idea_proposal", None)
        st.divider()
        from watson.agents import idea as agent
        stream_to_placeholder(agent.run(idea_input.strip(), style=selected_style), "搜索论文并分析中...")
        st.success("✅ Idea 验证完成！")
        st.rerun()

    # ── Show results ──────────────────────────────────────────────────────────
    if not run_btn:
        _render_papers()

        if S.load_idea_assessment():
            cfg = STYLE_CONFIG.get(selected_style, STYLE_CONFIG["ml"])
            venues_str = " / ".join(cfg["venues"])
            round_tag  = f"  第 {st.session_state['idea_round']} 轮" if st.session_state["idea_round"] > 1 else ""
            st.divider()
            st.subheader(f"💬 Idea 评审意见（{venues_str}）{round_tag}")
            st.markdown(S.load_idea_assessment())

            # ── Action buttons ────────────────────────────────────────────────
            st.divider()
            act1, act2 = st.columns(2)
            with act1:
                if st.button("✅ 接受，进入 Step 2", type="primary", use_container_width=True):
                    step2_key = f"{STEP_EMOJIS['experiment']} {STEP_NAMES['experiment']}"
                    st.session_state["page_nav"] = step2_key
                    st.rerun()
            with act2:
                propose_btn = st.button("🔄 让 Watson 基于文献提出改进方向", use_container_width=True)

            if propose_btn:
                if not _api_ok():
                    st.error("⚠️ 请先在左侧侧边栏输入 API Key")
                else:
                    from watson.agents.idea import propose
                    papers = S.load_top_conf_papers()
                    proposal = stream_to_placeholder(
                        propose(idea_input.strip(), S.load_idea_assessment(), papers, style=selected_style),
                        "Watson 正在分析文献，提出改进方向...",
                    )
                    st.session_state["idea_proposal"] = proposal
                    st.rerun()

        # ── Show Watson proposal ──────────────────────────────────────────────
        proposal = st.session_state.get("idea_proposal")
        if proposal:
            st.divider()
            st.subheader("🧠 Watson 提出的改进方向")
            st.info(proposal)

            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("🔬 直接用这个 Idea 重新验证", type="primary", use_container_width=True):
                    # Extract "改进后的研究方向" section text if available
                    import re as _re
                    m = _re.search(r"###\s*改进后的研究方向\s*\n(.*?)(?:\n###|$)", proposal, _re.DOTALL)
                    new_idea = m.group(1).strip() if m else proposal
                    st.session_state["idea_input"]   = new_idea
                    st.session_state["idea_round"]   = st.session_state["idea_round"] + 1
                    st.session_state["trigger_validate"] = True
                    st.session_state.pop("idea_proposal", None)
                    st.rerun()
            with b2:
                if st.button("✏️ 修改后再验证", use_container_width=True):
                    import re as _re
                    m = _re.search(r"###\s*改进后的研究方向\s*\n(.*?)(?:\n###|$)", proposal, _re.DOTALL)
                    new_idea = m.group(1).strip() if m else proposal
                    st.session_state["idea_input"] = new_idea
                    st.session_state.pop("idea_proposal", None)
                    st.rerun()
            with b3:
                if st.button("↩️ 放弃，自己重写", use_container_width=True):
                    st.session_state.pop("idea_proposal", None)
                    st.rerun()


def page_experiment():
    st.title("🔬 Step 2: Experiment Design")
    st.markdown("基于验证通过的研究方向，设计完整实验方案（Baseline、数据集、评价指标、消融实验等）。")

    if not S.load_idea():
        st.warning("请先完成 Step 1（Idea Validation）")
        return

    constraints = st.text_input("硬件/时间约束（可选）",
                                placeholder="例如：只有 1 张 RTX 3090，时间限制 1 周")

    c1, c2 = st.columns([1, 4])
    with c1:
        run_btn = st.button("🔬 设计实验", type="primary", use_container_width=True)
    with c2:
        if S.load_experiment() and st.button("📄 查看已有方案", use_container_width=True):
            st.markdown(S.load_experiment())

    if run_btn:
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        st.divider()
        from watson.agents import experiment as agent
        stream_to_placeholder(agent.run(extra_constraints=constraints), "设计实验方案中...")
        st.success("✅ 实验设计完成！")
        st.rerun()
    elif S.load_experiment():
        st.divider()
        st.subheader("实验设计方案")
        st.markdown(S.load_experiment())


def page_code():
    st.title("💻 Step 3: Code Generation")
    st.markdown("根据实验设计方案，生成可运行的 Python 实验脚本。")

    if not S.load_experiment():
        st.warning("请先完成 Step 2（Experiment Design）")
        return

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
    st.title("📝 Step 6: Paper Writing")
    st.markdown(
        "Watson 将找一篇**同 target venue 的模板论文**，从标题到每一节逐段仿写，"
        "生成完整 LaTeX 草稿。"
    )

    c1, c2 = st.columns(2)
    with c1:
        target_venue = st.selectbox(
            "目标投稿 venue",
            ["NeurIPS", "ICML", "ICLR", "ACL", "EMNLP", "NAACL", "AAAI", "CVPR", "ICCV", "其他"],
            key="target_venue",
        )
    with c2:
        style_hint = st.text_input("写作风格补充（可选）",
                                   placeholder="例如：简洁学术风，不超过 9 页")

    rc1, rc2 = st.columns([1, 4])
    with rc1:
        run_btn = st.button("📝 生成论文", type="primary", use_container_width=True)
    with rc2:
        if S.load_paper() and st.button("📄 查看已有草稿", use_container_width=True):
            st.code(S.load_paper(), language="latex")

    if run_btn:
        if not _api_ok():
            st.error("⚠️ 请先在左侧侧边栏输入 API Key")
            return
        st.divider()
        from watson.agents import paper as agent
        stream_to_placeholder(
            agent.run(target_venue=target_venue, style_hint=style_hint),
            "逐节撰写论文中..."
        )
        st.success("✅ 论文草稿生成完成！已保存至 paper/paper.tex")
        st.rerun()
    elif S.load_paper():
        st.divider()
        st.subheader("LaTeX 草稿")
        st.code(S.load_paper(), language="latex")
        paper_path = Path("paper/paper.tex")
        if paper_path.exists():
            st.download_button("⬇️ 下载 paper.tex", data=paper_path.read_text(encoding="utf-8"),
                               file_name="paper.tex", mime="text/plain")


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
