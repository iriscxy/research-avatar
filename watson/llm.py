from __future__ import annotations

from typing import Generator

from openai import OpenAI

from . import config as cfg


def _client() -> OpenAI:
    """Create an OpenAI-compatible client using the latest runtime config.

    重要说明：
    app.py 的侧边栏会在运行时修改 watson.config 里的 API Key / Base URL / Model。
    因此这里不能写成：
        from .config import DEEPSEEK_API_KEY
    否则 llm.py 在第一次 import 时会把空字符串固定下来，后面网页里填写 API Key
    也不会同步到 llm.py。

    这里改为：
        from . import config as cfg
    并且每次调用 _client() 时动态读取 cfg.DEEPSEEK_API_KEY。
    """

    api_key = (cfg.DEEPSEEK_API_KEY or "").strip()
    base_url = (cfg.DEEPSEEK_BASE_URL or "").strip() or None
    timeout = cfg.DEEPSEEK_TIMEOUT

    if not api_key:
        raise RuntimeError(
            "Missing LLM API key. 请先在左侧侧边栏填写 API Key，"
            "或者在环境变量中设置 DEEPSEEK_API_KEY / OPENAI_API_KEY。"
        )

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )


def stream_chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """Yield text chunks from a streaming chat completion.

    model 默认也动态读取 cfg.DEEPSEEK_MODEL，保证网页侧边栏切换模型后立即生效。
    """

    chosen_model = model or cfg.DEEPSEEK_MODEL
    if not chosen_model:
        raise RuntimeError("Missing model name. 请先在左侧侧边栏选择或填写模型名称。")

    resp = _client().chat.completions.create(
        model=chosen_model,
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    for chunk in resp:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def complete_chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Return the full response text, using the streaming implementation."""

    return "".join(stream_chat(messages, model=model, temperature=temperature, max_tokens=max_tokens))


def build_messages(system: str, user: str, history: list[dict] | None = None) -> list[dict]:
    """Build OpenAI-compatible chat messages."""

    msgs: list[dict] = [{"role": "system", "content": system}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user})
    return msgs
