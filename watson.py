#!/usr/bin/env python3
"""Watson — AI Research Assistant CLI.

Usage:
    python watson.py              # interactive REPL
    python watson.py idea "..."   # one-shot idea validation
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import print as rprint

# Ensure the package is importable when running from the project root
sys.path.insert(0, str(Path(__file__).parent))

from watson.config import STEP_NAMES, STEP_EMOJIS, STEPS, DEEPSEEK_API_KEY
from watson import state as S

console = Console()

BANNER = r"""
 ██╗    ██╗ █████╗ ████████╗███████╗ ██████╗ ███╗   ██╗
 ██║    ██║██╔══██╗╚══██╔══╝██╔════╝██╔═══██╗████╗  ██║
 ██║ █╗ ██║███████║   ██║   ███████╗██║   ██║██╔██╗ ██║
 ██║███╗██║██╔══██║   ██║   ╚════██║██║   ██║██║╚██╗██║
 ╚███╔███╔╝██║  ██║   ██║   ███████║╚██████╔╝██║ ╚████║
  ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝
"""

HELP_TEXT = """\
**可用命令：**

| 命令 | 说明 |
|------|------|
| `idea [描述]` | 💡 Step 1：输入研究方向，搜索论文并验证 idea |
| `design [约束]` | 🔬 Step 2：设计实验方案 |
| `code [框架]` | 💻 Step 3：生成实验代码（默认 PyTorch） |
| `run` | ▶️  Step 4：执行实验代码（需 `run --yes` 确认） |
| `analyze [备注]` | 📊 Step 5：分析实验结果并给出迭代建议 |
| `paper [风格提示]` | 📝 Step 6：生成 LaTeX 论文草稿 |
| `status` | 查看当前进度 |
| `papers` | 列出已找到的论文 |
| `show <文件名>` | 显示已生成的文件（idea/experiment/code/results/analysis/paper） |
| `help` | 显示此帮助 |
| `exit` / `quit` | 退出 |
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _stream_agent(generator):
    """Print streamed markdown chunks, then render the full output."""
    chunks = []
    for chunk in generator:
        console.print(chunk, end="", markup=False, highlight=False)
        chunks.append(chunk)
    console.print()  # newline after stream
    return "".join(chunks)


def _show_status():
    state = S.load_state()
    step = state.get("last_step", "")
    idea = state.get("idea", "")

    tbl = Table(show_header=False, box=None, padding=(0, 1))
    tbl.add_column("mark", style="bold")
    tbl.add_column("step")
    tbl.add_column("note", style="dim cyan")

    for s in STEPS:
        done = (step in STEPS) and STEPS.index(s) <= STEPS.index(step)
        current = s == step
        mark = "✅" if done else "⬜"
        note = "◀ 当前" if current else ""
        tbl.add_row(mark, f"{STEP_EMOJIS[s]} {STEP_NAMES[s]}", note)

    short_idea = (idea[:110] + "...") if len(idea) > 110 else idea
    header = f"[bold]研究方向：[/bold] {short_idea or '(未设置)'}\n"
    console.print(Panel(Text.from_markup(header), title="Watson 进度", border_style="cyan", expand=False))
    console.print(tbl)


def _show_papers():
    papers = S.load_papers()
    if not papers:
        console.print("[yellow]暂无论文记录，请先运行 `idea` 命令。[/yellow]")
        return
    from watson.tools.paper_search import format_papers
    similar = [p for p in papers if not p.get("is_top_conf")]
    top = [p for p in papers if p.get("is_top_conf")]
    text = format_papers(similar, "最相似论文") + "\n" + format_papers(top, "顶会论文")
    console.print(Markdown(text))


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
    loader = mapping.get(name.lower())
    if loader is None:
        console.print(f"[red]未知文件名：{name}。可选：{', '.join(mapping)}[/red]")
        return
    content = loader()
    if not content:
        console.print(f"[yellow]{name} 尚未生成。[/yellow]")
        return
    if name == "code":
        from rich.syntax import Syntax
        console.print(Syntax(content, "python", theme="monokai", line_numbers=True))
    else:
        console.print(Markdown(content))


# ── command dispatch ──────────────────────────────────────────────────────────

def _dispatch(line: str):
    parts = line.strip().split(None, 1)
    if not parts:
        return
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("exit", "quit"):
        console.print("[cyan]再见！[/cyan]")
        sys.exit(0)

    elif cmd == "help":
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

    elif cmd == "design":
        console.print(Rule("Step 2: Experiment Design", style="cyan"))
        from watson.agents import experiment as agent
        _stream_agent(agent.run(extra_constraints=arg))

    elif cmd == "code":
        framework = arg or "PyTorch"
        console.print(Rule("Step 3: Code Generation", style="cyan"))
        from watson.agents import code as agent
        _stream_agent(agent.run(framework=framework))

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


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if not DEEPSEEK_API_KEY:
        console.print(
            Panel(
                "[red]⚠️  未检测到 DEEPSEEK_API_KEY。\n"
                "请复制 .env.example 为 .env 并填入你的 API Key。[/red]",
                border_style="red",
            )
        )

    console.print(Text(BANNER, style="bold cyan"))
    console.print(Panel(
        "[bold]AI 科研助手[/bold] — 从 Idea 验证到论文撰写，全程本地运行\n"
        "输入 [cyan]help[/cyan] 查看命令，[cyan]status[/cyan] 查看当前进度",
        border_style="cyan",
    ))

    # One-shot mode: `python watson.py idea "..."`
    if len(sys.argv) > 1:
        _dispatch(" ".join(sys.argv[1:]))
        return

    # Show current state on startup (interactive mode only)
    if S.get_current_step():
        _show_status()

    # Interactive REPL
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
