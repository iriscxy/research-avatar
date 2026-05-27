"""Step 2: Experiment Design Agent."""

from typing import Generator

from ..config import EXPERIMENT_FILE
from ..llm import build_messages, stream_chat
from .. import state as S

SYSTEM = """你是 Watson，专注于实验设计的 AI 科研助手。

根据已验证的研究 idea 和相关论文，你需要设计一套完整的实验方案，包括：
1. **Baseline 模型**：列出对比方法名称、来源（论文/代码仓库）、选择理由
2. **数据集**：名称、版本/年份、获取方式、数据规模、预处理步骤
3. **评价指标**：每个指标的意义和计算方式
4. **实验对比设置**：主实验 + 消融实验（若有必要）
5. **硬件/时间估算**：大致 GPU 需求和训练时长
6. **实验代码结构**：建议的文件/模块组织

请输出可直接参考的、具体的实验设计文档（Markdown 格式），每项给出足够细节，让后续代码生成无歧义。"""


def run(extra_constraints: str = "") -> Generator[str, None, None]:
    """Design experiment based on current idea + papers. Yields text chunks."""
    idea = S.load_idea()
    if not idea:
        yield "❌ 请先完成 Step 1（Idea Validation）。\n"
        return

    papers = S.load_papers()
    assessment = S.load_idea_assessment()

    papers_brief = "\n".join(
        f"- {p['title']} ({p.get('published', '')})" for p in papers[:10]
    )

    constraint_section = f"\n\n**用户约束**：{extra_constraints}" if extra_constraints else ""

    user_prompt = f"""## 研究 Idea
{idea}

## Idea 验证结论摘要
{(assessment or '（无）')[:1000]}

## 相关论文（前 10 篇）
{papers_brief}
{constraint_section}

请输出完整的实验设计方案（Markdown）。"""

    messages = build_messages(SYSTEM, user_prompt)

    full = ""
    for chunk in stream_chat(messages, max_tokens=3000):
        full += chunk
        yield chunk

    S.save_file(EXPERIMENT_FILE, full)
    S.save_state({"last_step": "experiment"})
