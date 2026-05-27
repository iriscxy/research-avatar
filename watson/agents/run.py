"""Step 4: Run & Record Agent.

Executes the generated experiment script, captures stdout/stderr in real time,
and saves the run log. The user is asked to confirm before execution.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

from ..config import CODE_FILE, RUN_LOG_FILE, RESULTS_FILE, EXPERIMENTS_DIR
from .. import state as S


def run(confirmed: bool = False) -> Generator[str, None, None]:
    """Execute experiments/experiment.py and stream its output."""
    code = S.load_code()
    if not code:
        yield "❌ 请先完成 Step 3（Code Generation）。\n"
        return

    if not confirmed:
        yield (
            f"⚠️  即将执行：`{CODE_FILE}`\n\n"
            "请在 CLI 中输入 `run --yes` 或在 Web UI 中点击「确认执行」按钮来运行。\n"
        )
        return

    yield f"▶️  **开始执行** `{CODE_FILE}`\n\n```\n"

    start = time.time()
    log_lines: list[str] = [f"# Watson Run Log — {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"]

    proc = subprocess.Popen(
        [sys.executable, str(CODE_FILE)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(EXPERIMENTS_DIR.parent),
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        log_lines.append(line)
        yield line

    proc.wait()
    elapsed = time.time() - start
    status = "✅ 成功" if proc.returncode == 0 else f"❌ 失败（exit code {proc.returncode}）"

    summary = f"\n```\n\n**{status}**，耗时 {elapsed:.1f}s\n"
    yield summary
    log_lines.append(f"\n# Exit code: {proc.returncode} | Elapsed: {elapsed:.1f}s\n")

    log_text = "".join(log_lines)
    S.save_file(RUN_LOG_FILE, log_text)

    # Try to load results.json if the script produced one
    results_json = EXPERIMENTS_DIR / "results.json"
    if results_json.exists():
        import json
        try:
            results = json.loads(results_json.read_text())
            results_md = "# Experiment Results\n\n```json\n" + json.dumps(results, indent=2, ensure_ascii=False) + "\n```\n"
            S.save_file(RESULTS_FILE, results_md)
            yield "\n📊 结果已保存至 `.watson/results.md`\n"
        except Exception:
            pass

    S.save_state({"last_step": "run", "run_exit_code": proc.returncode})
