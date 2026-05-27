"""Step 3: Code Generation Agent."""

from typing import Generator

from ..config import CODE_FILE, EXPERIMENTS_DIR
from ..llm import build_messages, stream_chat
from .. import state as S

SYSTEM = """你是 Watson，专注于生成可运行实验代码的 AI 科研助手。

根据实验设计方案，生成完整、可直接运行的 Python 实验脚本，要求：
- 使用 Python + PyTorch（或用户指定框架）
- 包含：数据加载、模型定义、训练循环、评估、结果保存
- 代码清晰，有必要的注释，关键超参数用变量或 argparse 统一管理
- 结果保存为 JSON 或 CSV，供后续分析使用
- 脚本末尾打印关键指标，如 ROUGE、accuracy 等
- 若数据集不可直接获取，提供模拟数据（小规模）用于测试流程正确性
- 只输出完整 Python 代码，不要额外说明文字（代码注释除外）"""


def run(framework: str = "PyTorch", extra_notes: str = "") -> Generator[str, None, None]:
    """Generate experiment code. Yields text chunks."""
    idea = S.load_idea()
    design = S.load_experiment()

    if not design:
        yield "❌ 请先完成 Step 2（Experiment Design）。\n"
        return

    extra_section = f"\n\n**额外要求**：{extra_notes}" if extra_notes else ""

    user_prompt = f"""## 研究 Idea
{idea or '（见实验设计）'}

## 实验设计方案
{design}

## 要求
- 框架：{framework}
- 结果保存到 `experiments/results.json`
- 使用小规模模拟数据保证代码可运行（实际数据获取在注释中说明）
{extra_section}

请输出完整 Python 脚本，只输出代码。"""

    messages = build_messages(SYSTEM, user_prompt)

    yield "```python\n"
    full = "```python\n"
    for chunk in stream_chat(messages, temperature=0.3, max_tokens=4000):
        full += chunk
        yield chunk
    yield "\n```\n"
    full += "\n```\n"

    # Strip markdown fences for the saved .py file
    code = full.replace("```python\n", "").replace("```python", "").replace("```\n", "").replace("```", "").strip()
    S.save_file(CODE_FILE, code + "\n")
    S.save_state({"last_step": "code"})
