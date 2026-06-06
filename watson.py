'''
修订说明：为命令行同步 Step2 的“生成—修订—确认”流程
'''

"""Watson — AI Research Assistant CLI.

Usage:
    python watson.py
    python watson.py idea "..."
    python watson.py design "1x RTX 4090, 24小时"
    python watson.py revise "删除 BERT baseline，增加 Qwen2.5"
    python watson.py approve
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent))

from watson import config as cfg
from watson.config import STEP_NAMES, STEP_EMOJIS, STEPS, WATSON_DIR
from watson import state as S

console = Console()

BANNER = r"""
 ██╗    ██╗ █████╗ ████████╗███████╗ ██████╗ ███╗   ██╗
 ██║    ██║██╔══██╗╚══██╔══╝██╔════╝██╔═══██╗████╗  ██║
 ██║ █╗ ██║███████║   ██║   ███████╗██║   ██║██╔██╗ ██║
 ██║███╗██║██╔══██║   ██║   ╚════██║██║   ██║██║╚██╗██║
 ╚███╔███╔╝██║  ██║   ██║   ███████║╚██████╔╝██║ ╚████║
  ╚══╝╚══╝ ╚═╝  ╚═╝   ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝
"""

HELP_TEXT = """\
**可用命令：**

| 命令 | 说明 |
|------|------|
| `idea [描述]` | 💡 Step 1：检索论文并验证 idea |
| `design [约束]` | 🔬 Step 2：生成第一版实验方案 |
| `revise [意见]` | 🔁 Step 2：按意见增删 baseline、数据集、指标或消融实验 |
| `approve` | ✅ 确认当前实验方案，可以进入 Step 3 |
| `code [框架]` | 💻 Step 3：生成实验代码（需先 approve） |
| `run` | ▶️ Step 4：执行实验代码（需 `run --yes`） |
| `analyze [备注]` | 📊 Step 5：分析实验结果并给出迭代建议 |
| `paper [风格提示]` | 📝 Step 6：生成论文草稿 |
| `status` | 查看当前进度 |
| `papers` | 列出 Step1 的竞争论文与背景文献 |
| `show <名称>` | 显示 idea/assessment/experiment/plan/code/log/results/analysis/paper |
| `help` | 显示帮助 |
| `exit` / `quit` | 退出 |
"""


def _stream_agent(generator):
    chunks = []
    for chunk in generator:
        console.print(chunk, end="", markup=False, highlight=False)
        chunks.append(chunk)
    console.print()
    return "".join(chunks)


def _invalidate_after_idea_change() -> None:
    """Keep previous artifacts, but mark Step2 and downstream results as stale."""
    S.save_state({
        "last_step": "idea",
        "experiment_approved": False,
        "experiment_stale": True,
        "downstream_stale": True,
    })


def _invalidate_after_experiment_change() -> None:
    """Keep previous code/results, but require Step2 approval and Step3 regeneration."""
    S.save_state({
        "last_step": "experiment",
        "experiment_approved": False,
        "experiment_stale": False,
        "downstream_stale": True,
    })


def _show_status():
    state = S.load_state()
    step = state.get("last_step", "")
    idea = state.get("idea", "")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("mark", style="bold")
    table.add_column("step")
    table.add_column("note", style="dim cyan")

    for item in STEPS:
        done = (step in STEPS) and STEPS.index(item) <= STEPS.index(step)
        current = item == step
        mark = "✅" if done else "⬜"
        note = "◀ 当前" if current else ""
        table.add_row(mark, f"{STEP_EMOJIS[item]} {STEP_NAMES[item]}", note)

    short_idea = (idea[:110] + "...") if len(idea) > 110 else idea
    if state.get("experiment_stale"):
        approval = "已过期（Step1 已更新）"
    else:
        approval = "已确认" if state.get("experiment_approved") else "待确认"
    header = (
        f"[bold]研究方向：[/bold] {short_idea or '(未设置)'}\n"
        f"[bold]Step2 方案：[/bold] {approval}"
    )
    console.print(Panel(Text.from_markup(header), title="Watson 进度", border_style="cyan", expand=False))
    console.print(table)


def _show_papers():
    top = S.load_top_conf_papers()
    load_all = getattr(S, "load_all_relevant_papers", None)
    all_relevant = load_all() if callable(load_all) else []
    background = [p for p in all_relevant if p.get("tier") == "background"]

    if not top and not background:
        console.print("[yellow]暂无论文记录，请先运行 `idea`。[/yellow]")
        return

    from watson.tools.paper_search import format_papers
    if top:
        console.print(Markdown(format_papers(top, "直接竞争论文")))
    if background:
        console.print(Markdown(format_papers(background[:20], "背景文献")))


def _show_file(name: str):
    mapping = {
        "idea": S.load_idea,
        "assessment": S.load_idea_assessment,
        "experiment": S.load_experiment,
        "code": S.load_code,
        "log": S.load_run_log,
        "results": S.load_results,
        "analysis": S.load_analysis,
        "paper": S.load_paper,
    }
    if name.lower() == "plan":
        data = S.load_json(WATSON_DIR / "experiment_plan.json")
        if not data:
            console.print("[yellow]experiment_plan.json 尚未生成。[/yellow]")
        else:
            import json
            console.print_json(json.dumps(data, ensure_ascii=False))
        return

    loader = mapping.get(name.lower())
    if loader is None:
        console.print(f"[red]未知文件名：{name}。可选：{', '.join(mapping)}, plan[/red]")
        return
    content = loader()
    if not content:
        console.print(f"[yellow]{name} 尚未生成。[/yellow]")
        return
    if name.lower() == "code":
        from rich.syntax import Syntax
        console.print(Syntax(content, "python", theme="monokai", line_numbers=True))
    else:
        console.print(Markdown(content))


def _dispatch(line: str):
    parts = line.strip().split(None, 1)
    if not parts:
        return
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("exit", "quit"):
        console.print("[cyan]再见！[/cyan]")
        sys.exit(0)
    if cmd == "help":
        console.print(Markdown(HELP_TEXT))
    elif cmd == "status":
        _show_status()
    elif cmd == "papers":
        _show_papers()
    elif cmd == "show":
        _show_file(arg or "idea")
    elif cmd == "idea":
        if not arg:
            arg = Prompt.ask("[cyan]请输入研究方向[/cyan]")
        if not arg:
            return
        console.print(Rule("Step 1: Idea Validation", style="cyan"))
        from watson.agents import idea as agent
        _stream_agent(agent.run(arg))
        _invalidate_after_idea_change()
        console.print("[green]Step1 完成。旧的 Step2-Step6 文件已保留，但已标记为过期。[/green]")
    elif cmd == "design":
        console.print(Rule("Step 2: Experiment Design", style="cyan"))
        from watson.agents import experiment as agent
        _stream_agent(agent.run(extra_constraints=arg))
        _invalidate_after_experiment_change()
        console.print("[yellow]方案尚未确认。旧的后续文件已保留但标记为待更新；检查后运行 `approve`。[/yellow]")
    elif cmd == "revise":
        if not S.load_experiment():
            console.print("[yellow]请先运行 `design` 生成第一版方案。[/yellow]")
            return
        if not arg:
            arg = Prompt.ask("[cyan]请输入实验方案修改意见[/cyan]")
        if not arg:
            return
        console.print(Rule("Step 2: Revise Experiment Design", style="cyan"))
        from watson.agents import experiment as agent
        _stream_agent(agent.run(revision_feedback=arg, regenerate=True))
        _invalidate_after_experiment_change()
        console.print("[yellow]修订方案尚未确认。旧的后续文件已保留但标记为待更新；检查后运行 `approve`。[/yellow]")
    elif cmd == "approve":
        if not S.load_experiment():
            console.print("[yellow]尚无实验方案，请先运行 `design`。[/yellow]")
            return
        if S.load_state().get("experiment_stale", False):
            console.print("[yellow]当前实验方案来自旧 Step1，请先运行 `design` 重新生成。[/yellow]")
            return
        from datetime import datetime, timezone
        S.save_state({
            "last_step": "experiment",
            "experiment_approved": True,
            "experiment_stale": False,
            "downstream_stale": True,
            "experiment_approved_at": datetime.now(timezone.utc).isoformat(),
        })
        console.print("[green]✅ 当前实验方案已确认，可以进入 Step3。[/green]")
    elif cmd == "code":
        workflow_state = S.load_state()
        if workflow_state.get("experiment_stale", False):
            console.print("[yellow]Step1 已更新，当前 Step2 方案已过期，请先运行 `design`。[/yellow]")
            return
        if not workflow_state.get("experiment_approved", False):
            console.print("[yellow]当前实验方案尚未确认，请先运行 `approve`。[/yellow]")
            return
        framework = arg or "PyTorch"
        console.print(Rule("Step 3: Code Generation", style="cyan"))
        from watson.agents import code as agent
        _stream_agent(agent.run(framework=framework))
        S.save_state({"last_step": "code", "downstream_stale": False})
    elif cmd == "run":
        confirmed = "--yes" in arg or "-y" in arg
        console.print(Rule("Step 4: Run & Record", style="cyan"))
        from watson.agents import run as agent
        _stream_agent(agent.run(confirmed=confirmed))
    elif cmd == "analyze":
        console.print(Rule("Step 5: Analysis & Iteration", style="cyan"))
        from watson.agents import analysis as agent
        _stream_agent(agent.run(user_comment=arg))
    elif cmd == "paper":
        console.print(Rule("Step 6: Paper Writing", style="cyan"))
        from watson.agents import paper as agent
        _stream_agent(agent.run(style_hint=arg))
    else:
        console.print(f"[red]未知命令：{cmd}。输入 `help` 查看帮助。[/red]")


def main():
    if not str(getattr(cfg, "DEEPSEEK_API_KEY", "") or "").strip():
        console.print(
            Panel(
                "[red]⚠️ 未检测到 LLM API Key。\n"
                "请复制 .env.example 为 .env 并填写 API Key。[/red]",
                border_style="red",
            )
        )

    console.print(Text(BANNER, style="bold cyan"))
    console.print(Panel(
        "[bold]AI 科研助手[/bold] — 从 Idea 验证到论文撰写，全程本地运行\n"
        "输入 [cyan]help[/cyan] 查看命令，[cyan]status[/cyan] 查看当前进度",
        border_style="cyan",
    ))

    if len(sys.argv) > 1:
        _dispatch(" ".join(sys.argv[1:]))
        return

    if S.get_current_step():
        _show_status()

    while True:
        try:
            line = Prompt.ask("\n[bold cyan]Watson[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]再见！[/cyan]")
            break
        if line.strip():
            try:
                _dispatch(line)
            except Exception as exc:
                console.print_exception()
                console.print(f"[red]错误：{exc}[/red]")


if __name__ == "__main__":
    main()

