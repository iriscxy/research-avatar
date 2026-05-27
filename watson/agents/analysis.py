"""Step 5: Analysis & Iteration Agent."""

from typing import Generator

from ..config import ANALYSIS_FILE
from ..llm import build_messages, stream_chat
from .. import state as S

SYSTEM = """你是 Watson，专注于实验结果分析的 AI 科研助手。

根据实验设计方案和运行结果，完成以下分析：
1. **结果总结**：关键指标数值，与 baseline 对比
2. **成功 / 失败 / 部分有效** 的判断，以及理由
3. **异常诊断**：是否有训练不收敛、指标异常、代码错误等问题
4. **迭代建议**（至少 3 条）：
   - 若成功：如何进一步提升（调参、更大数据集、更多消融实验）
   - 若失败：根因分析 + 具体修改方向
5. **下一步行动**：继续迭代（返回 Step 2/3）或直接撰写论文（进入 Step 6）

请用中文，给出结构化的分析报告。"""


def run(user_comment: str = "") -> Generator[str, None, None]:
    """Analyze run results. Yields text chunks."""
    design = S.load_experiment()
    run_log = S.load_run_log()
    results = S.load_results()

    if not run_log:
        yield "❌ 请先完成 Step 4（Run & Record）。\n"
        return

    comment_section = f"\n\n**用户补充说明**：{user_comment}" if user_comment else ""

    user_prompt = f"""## 实验设计方案（摘要）
{(design or '（无）')[:1500]}

## 运行日志（最后 100 行）
```
{chr(10).join((run_log or '').splitlines()[-100:])}
```

## 结果文件
{results or '（结果文件不存在或为空）'}
{comment_section}

请给出完整分析报告。"""

    messages = build_messages(SYSTEM, user_prompt)

    full = ""
    for chunk in stream_chat(messages, max_tokens=3000):
        full += chunk
        yield chunk

    S.save_file(ANALYSIS_FILE, full)
    S.save_state({"last_step": "analysis"})
