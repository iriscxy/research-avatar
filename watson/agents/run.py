"""Step 4: Run & Record Agent.

Executes the generated experiment script, captures stdout/stderr in real time,
and saves the run log. The user is asked to confirm before execution.
"""

import os
import subprocess
import sys
import time
import json
import shutil
import venv
from pathlib import Path
from datetime import datetime
from typing import Generator
from pigar.core import RequirementsAnalyzer

from ..config import CODE_FILE, RUN_LOG_FILE, RESULTS_FILE, EXPERIMENTS_DIR
from .. import state as S

# ── 模块常量 ──────────────────────────────────────────────────────────────────

ARCHIVE_PREFIX = "experiment_"

def load_device() -> dict:
    """获取运行环境信息（GPU/CPU、内存、Python环境路径）。

    提供给步骤4使用，步骤4中规则：
    - 当 python_env 指定时，只生成 requirements.txt，不修改外部环境
    - 当 device 非 cpu（GPU）时，python_env 必须预先配置

    Returns:
        dict: 包含运行环境信息的字典，格式为：
            {
                "device": "cpu" 或 "cuda",
                "memory": None 或 内存大小（字节）,
                "python_env": None 或 Python环境路径（如 "D:/Code/venvs/venv_pyTorchCUDA11.8"）
            }
    """
    return {
        "device": "cpu",
        "memory": None,
        "python_env": ""
    }

# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def _pigar_dists_filter(import_name, locations, distributions, best_match):
    """Auto-select best match without interactive prompts."""
    if best_match:
        return [best_match]
    return distributions


def _utf8_env() -> dict:
    """返回设置了 UTF-8 编码和禁用输出缓冲的环境变量副本。"""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    return env


def _venv_bin(base_dir: Path, binary: str) -> str:
    """返回平台相关的 venv 二进制文件路径。

    Args:
        base_dir: venv 根目录
        binary: 二进制文件名（如 'python', 'pip'）
    """
    subdir = "Scripts" if sys.platform == "win32" else "bin"
    return str(base_dir / subdir / binary)


def _emit(log_lines: list[str], msg: str):
    """向 log_lines 追加消息并 yield 输出。"""
    yield msg
    log_lines.append(msg)


# ── 核心函数 ──────────────────────────────────────────────────────────────────

def buildRequirements(project_dir: Path, output_dir: Path) -> Path:
    """使用 pigar 分析指定目录下 Python 文件的依赖，生成 requirements.txt。

    Args:
        project_dir: 要分析的 Python 项目目录
        output_dir: requirements.txt 输出目录

    Returns:
        Path: 生成的 requirements.txt 文件路径
    """
    requirements_path = output_dir / "requirements.txt"

    analyzer = RequirementsAnalyzer(str(project_dir))
    analyzer.analyze_requirements(
        visit_doc_str=False,
        ignores=[f"{ARCHIVE_PREFIX}*"],
        dists_filter=_pigar_dists_filter,
        follow_symbolic_links=False,
        enable_requirement_annotations=False,
    )
    if analyzer.has_unknown_imports_or_uninstalled_annotations():
        analyzer.search_unknown_imports_from_index(
            dists_filter=_pigar_dists_filter,
            pypi_index_url='https://pypi.org/simple/',
            include_prereleases=False,
        )
    with open(requirements_path, 'w', encoding='utf-8') as f:
        analyzer.write_requirements(
            f,
            with_ref_comments=False,
            comparison_specifier='==',
            with_banner=True,
            with_unknown_imports=False,
        )
    return requirements_path


def _prepare(log_lines: list[str], device: dict) -> tuple[Generator[str, None, None], bool, str]:
    """在 experiments/ 目录下准备实验环境。

    按需创建虚拟环境、生成 requirements.txt 并安装依赖。直接操作 EXPERIMENTS_DIR。

    Args:
        log_lines: 用于追加状态消息的列表
        device: 运行环境配置字典，含 python_env、device、memory 信息

    Returns:
        tuple: (output_generator, prepare_error, python_exec)
               prepare_error: True 表示 GPU 模式下缺少 python_env（步骤4需终止）
               python_exec: 用于执行 experiment.py 的 Python 解释器路径
    """
    # 同步确定 python_exec 和 prepare_error（在 generator 运行前确定值）
    if device.get("python_env"):
        python_env_dir = Path(device["python_env"])
        python_exec = _venv_bin(python_env_dir, "python")
        prepare_error = False
    elif device.get("device", "cpu") != "cpu":
        python_exec = ""
        prepare_error = True
    else:
        python_exec = _venv_bin(EXPERIMENTS_DIR / ".venv", "python")
        prepare_error = False

    def output_gen():
        if prepare_error:
            yield from _emit(log_lines, "❌ 错误: GPU 设备需要使用预先配置的 python_env\n\n")
            return

        # 配置 Python 运行环境
        if device.get("python_env"):
            yield from _emit(log_lines, f"使用指定Python环境: {python_env_dir}\n\n")
        else:
            venv_dir = EXPERIMENTS_DIR / ".venv"
            if venv_dir.exists():
                shutil.rmtree(venv_dir)
            venv.create(venv_dir, with_pip=True)
            yield from _emit(log_lines, f"创建虚拟环境: {venv_dir}\n\n")

        # 生成依赖文件
        requirements_path = buildRequirements(EXPERIMENTS_DIR, EXPERIMENTS_DIR)
        yield from _emit(log_lines, f"生成依赖文件: {requirements_path}\n\n")

        # 安装依赖
        if device.get("python_env"):
            yield from _emit(log_lines, "使用指定虚拟环境，跳过依赖安装（请手动安装依赖）\n\n")
        else:
            pip_path = _venv_bin(EXPERIMENTS_DIR / ".venv", "pip")
            yield from _emit(log_lines, f"使用虚拟环境的pip: {pip_path}\n\n")
            yield "安装依赖库中...\n"

            result = subprocess.run(
                [pip_path, "install", "-r", str(requirements_path)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=str(EXPERIMENTS_DIR),
                env=_utf8_env(),
            )

            if result.returncode == 0:
                yield from _emit(log_lines, "依赖安装成功\n\n")
            else:
                yield from _emit(log_lines, f"⚠️  依赖安装警告: {result.stderr}\n\n")

    return output_gen(), prepare_error, python_exec


def archive(from_dir: Path, to_dir: Path, log_lines: list[str]) -> Generator[str, None, None]:
    """归档或恢复实验文件。

    - 归档：from_dir=EXPERIMENTS_DIR 时，将非归档文件复制到 to_dir
    - 恢复：to_dir=EXPERIMENTS_DIR 时，先清空非归档内容，再从 from_dir 复制

    Args:
        from_dir: 源文件夹
        to_dir: 目标文件夹
        log_lines: 用于追加状态消息的列表
    """
    # 恢复模式：清空 EXPERIMENTS_DIR 中的非归档内容
    if to_dir == EXPERIMENTS_DIR:
        yield from _emit(log_lines, f"\n恢复实验文件: {from_dir}\n\n")
        for item in list(to_dir.iterdir()):
            if item.name.startswith(ARCHIVE_PREFIX):
                continue
            if item.is_dir():
                shutil.rmtree(str(item))
            else:
                item.unlink()

    # 归档模式
    if from_dir == EXPERIMENTS_DIR:
        yield from _emit(log_lines, f"\n归档实验文件至: {to_dir}\n\n")
    yield "# 复制文件中...\n"
    to_dir.mkdir(parents=True, exist_ok=True)
    for item in from_dir.iterdir():
        if item.name.startswith(ARCHIVE_PREFIX):
            continue
        dest = to_dir / item.name
        if item.is_dir():
            shutil.copytree(str(item), str(dest))
        else:
            shutil.copy2(str(item), str(dest))



def run(confirmed: bool = False) -> Generator[str, None, None]:
    """执行 experiment.py 并流式输出结果。"""
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

    # 记录实验开始时间
    start = time.time()

    # 准备隔离实验环境
    log_lines: list[str] = [f"# Watson Run Log — {datetime.fromtimestamp(start).strftime('%Y-%m-%d %H:%M:%S')}\n\n"]
    _device = load_device()
    prepare_output, prepare_error, python_exec = _prepare(log_lines, _device)

    # 输出准备阶段状态
    for output in prepare_output:
        yield output

    # GPU 无 python_env 时跳过子进程执行，但仍完成后续归档
    if prepare_error:
        proc = None
    else:
        yield f"代码执行中...\n"
        proc = subprocess.Popen(
            [python_exec, str(EXPERIMENTS_DIR / "experiment.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            cwd=str(EXPERIMENTS_DIR),
            env=_utf8_env(),
        )
        # 运行代码
        assert proc.stdout is not None
        log_lines.append("```\n")
        for line in proc.stdout:
            yield from _emit(log_lines,line)
        log_lines.append("```\n")
        proc.wait()

    # 加载 results.json 并保存到 .watson/results.md
    results_json = EXPERIMENTS_DIR / "results.json"
    if results_json.exists():
        try:
            with open(results_json, 'r', encoding='utf-8') as f:
                results = json.load(f)
            results_md = "# Experiment Results\n\n```json\n" + json.dumps(results, indent=2, ensure_ascii=False) + "\n```\n"
            S.save_file(RESULTS_FILE, results_md)
            yield "\n📊 结果已保存至 `.watson/results.md`\n"
        except Exception:
            pass

    # 归档：EXPERIMENTS_DIR下文件全部复制归档
    timestamp = datetime.fromtimestamp(start).strftime("%Y%m%d_%H%M%S_%f")[:-3]
    isolated_dir = EXPERIMENTS_DIR / f"{ARCHIVE_PREFIX}{timestamp}"
    yield from archive(EXPERIMENTS_DIR, isolated_dir, log_lines)

    # 实验总结
    elapsed = time.time() - start
    if proc is not None:
        status = "✅ 成功" if proc.returncode == 0 else f"❌ 失败（exit code {proc.returncode}）"
        exit_info = f"\n# Exit code: {proc.returncode} | Elapsed: {elapsed:.1f}s\n"
    else:
        status = "⚠️  环境准备失败，未执行实验"
        exit_info = f"\n# Exit code: -1 (准备失败) | Elapsed: {elapsed:.1f}s\n"

    summary = f"\n```\n\n**{status}**，耗时 {elapsed:.1f}s\n"
    yield summary
    log_lines.append(exit_info)

    # 保存 run_log.txt 到 .watson/
    log_text = "".join(log_lines)
    S.save_file(RUN_LOG_FILE, log_text)
    # 将最新的 run_log.txt 也复制到归档目录
    shutil.copy2(RUN_LOG_FILE, isolated_dir / "run_log.txt")

    # 保存步骤4结束状态
    exit_code = proc.returncode if proc is not None else -1
    S.save_state({"last_step": "run", "run_exit_code": exit_code})
