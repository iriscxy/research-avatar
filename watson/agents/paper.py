"""Step 6: Paper Writing Agent.

Finds a template paper from the target venue, then writes the paper
section-by-section (title → abstract → introduction → … → conclusion).
Each section is streamed and saved incrementally.
"""

from typing import Generator

from ..config import PAPER_FILE, PAPER_DIR
from ..llm import build_messages, stream_chat, complete_chat
from ..tools.paper_search import search_similar
from .. import state as S

# ── Sections to write in order ────────────────────────────────────────────────

SECTIONS = [
    ("title",        "Title & Keywords"),
    ("abstract",     "Abstract"),
    ("introduction", "1. Introduction"),
    ("related",      "2. Related Work"),
    ("method",       "3. Method"),
    ("experiments",  "4. Experiments"),
    ("analysis",     "5. Analysis & Discussion"),
    ("conclusion",   "6. Conclusion"),
    ("references",   "References"),
]

# ── System prompts ─────────────────────────────────────────────────────────────

TEMPLATE_SEARCH_SYSTEM = """你是一位学术助手。给定目标 venue 和研究主题，
返回最适合作为写作模板的论文标题和摘要（一篇即可），用于仿写结构和风格。"""

SECTION_SYSTEM = """你是一位顶级 AI 会议论文写手，正在为 {venue} 撰写论文。
你有一篇模板论文作为风格和结构参考。请仿照模板的写作风格、句式密度和章节结构，
为当前研究撰写指定章节的 LaTeX 代码。

规则：
- 只输出该节的 LaTeX 代码（含 \\section{{}} 命令），不要其他文字
- 数学公式用 $$ 或 equation 环境
- 表格用 booktabs（\\toprule/\\midrule/\\bottomrule）
- 图片用 \\includegraphics[width=0.8\\linewidth]{{figures/fig.pdf}} 占位
- 引用用 \\cite{{key}} — key 取论文标题的驼峰缩写"""


def _find_template(idea: str, venue: str) -> dict | None:
    """Search for a recent paper from the target venue to use as template."""
    query = f"{idea} {venue}"
    papers = search_similar(query, max_results=5)
    # prefer papers that mention the venue
    for p in papers:
        v = p.get("venue", "").upper()
        if venue.upper() in v or any(tok in v for tok in venue.upper().split()):
            return p
    return papers[0] if papers else None


def _write_section(
    section_key: str,
    section_name: str,
    idea: str,
    design: str,
    results: str,
    analysis: str,
    papers_cite: str,
    template: dict | None,
    venue: str,
    full_paper_so_far: str,
) -> Generator[str, None, None]:
    """Stream one LaTeX section."""
    template_info = ""
    if template:
        template_info = (
            f"模板论文标题：{template['title']}\n"
            f"模板摘要：{template.get('summary','')[:400]}\n"
            f"模板 Venue：{template.get('venue', venue)}\n"
        )

    context = f"""## 研究 Idea
{idea}

## 实验设计（摘要）
{design[:800] if design else '（无）'}

## 实验结果
{results or '（请使用合理的占位数据）'}

## 分析结论
{analysis[:500] if analysis else '（无）'}

## 参考文献
{papers_cite}

## 模板论文（风格参考）
{template_info or '（无模板，请按 ' + venue + ' 标准写）'}

## 已写内容（前文）
{full_paper_so_far[-1500:] if full_paper_so_far else '（本节为第一节）'}

---
请现在撰写：**{section_name}**"""

    system = SECTION_SYSTEM.format(venue=venue)
    messages = build_messages(system, context)
    yield from stream_chat(messages, temperature=0.4, max_tokens=1500)


# ── Public entry point ─────────────────────────────────────────────────────────

def run(target_venue: str = "NeurIPS", style_hint: str = "") -> Generator[str, None, None]:
    """Write paper section-by-section. Yields text chunks."""

    idea     = S.load_idea()     or ""
    design   = S.load_experiment() or ""
    results  = S.load_results()  or ""
    analysis = S.load_analysis() or ""
    papers   = S.load_papers()

    papers_cite = "\n".join(
        f"- {p['title']} — {', '.join(p.get('authors', [])[:2])} ({p.get('published', '')})"
        for p in papers[:12]
    )

    # Find a template paper from the target venue
    yield f"🔍 **搜索 {target_venue} 模板论文...**\n\n"
    try:
        template = _find_template(idea, target_venue)
    except Exception:
        template = None

    if template:
        yield (
            f"📄 **模板论文：** {template['title']}  \n"
            f"Venue: `{template.get('venue', target_venue)}`  \n"
            f"链接: {template.get('link','')}\n\n"
        )
    else:
        yield f"⚠️ 未找到 {target_venue} 模板论文，按标准格式撰写。\n\n"

    if style_hint:
        yield f"📌 **风格提示：** {style_hint}\n\n"

    yield "---\n\n"

    # LaTeX document header
    header = (
        "\\documentclass[10pt]{article}\n"
        "\\usepackage{amsmath,amssymb,booktabs,graphicx,hyperref,xcolor}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\title{}\n\\author{}\n\\date{}\n"
        "\\begin{document}\n\\maketitle\n\n"
    )
    full_paper = header

    # Write each section
    for key, name in SECTIONS:
        yield f"### ✍️ 正在撰写：{name}\n\n```latex\n"

        section_text = ""
        for chunk in _write_section(
            key, name, idea, design, results, analysis,
            papers_cite, template, target_venue, full_paper
        ):
            section_text += chunk
            yield chunk

        yield "\n```\n\n"
        full_paper += section_text + "\n\n"

    full_paper += "\\end{document}\n"

    # Save
    S.save_file(PAPER_FILE, full_paper)

    # Figure script
    yield "📊 **生成绘图脚本...**\n\n"
    fig_msgs = build_messages(
        "你是 Python 数据可视化专家。生成 matplotlib 脚本绘制主要实验结果图。"
        "若无真实数据则用合理模拟数据，图片保存到 paper/figures/main_result.pdf。只输出 Python 代码。",
        f"实验结果：\n{results or '（无，用模拟数据）'}",
    )
    fig_code = complete_chat(fig_msgs, temperature=0.3, max_tokens=1000)
    fig_code = fig_code.replace("```python","").replace("```","").strip()
    fig_path = PAPER_DIR / "figures.py"
    S.save_file(fig_path, fig_code + "\n")
    yield f"✅ 绘图脚本已保存至 `{fig_path}`\n"

    S.save_state({"last_step": "paper"})
