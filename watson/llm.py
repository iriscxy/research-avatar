"""LLM client — routes to Anthropic or OpenAI-compatible providers.

The Streamlit sidebar updates ``watson.config`` at runtime.  This module must
therefore read config values dynamically instead of copying them at import time.|
修订说明：修复网页 API 配置不生效，同时保留新版 Anthropic 功能
"""

from __future__ import annotations

from typing import Generator

from . import config as cfg

_CACHE_THRESHOLD = 800


def _api_key() -> str:
    key = str(getattr(cfg, "DEEPSEEK_API_KEY", "") or "").strip()
    if not key:
        raise RuntimeError(
            "Missing LLM API key. 请在网页左侧填写 API Key，"
            "或在 .env 中设置相应提供商的 API Key。"
        )
    return key


def _base_url() -> str:
    return str(getattr(cfg, "DEEPSEEK_BASE_URL", "") or "").strip()


def _default_model() -> str:
    model = str(getattr(cfg, "DEEPSEEK_MODEL", "") or "").strip()
    if not model:
        raise RuntimeError("Missing model name. 请在网页左侧选择或填写模型名称。")
    return model


def _is_anthropic() -> bool:
    return "anthropic.com" in _base_url().lower()


def _openai_client():
    from openai import OpenAI

    kwargs = {
        "api_key": _api_key(),
        "timeout": getattr(cfg, "DEEPSEEK_TIMEOUT", 120),
    }
    base_url = _base_url()
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _anthropic_client():
    import anthropic

    return anthropic.Anthropic(
        api_key=_api_key(),
        timeout=getattr(cfg, "DEEPSEEK_TIMEOUT", 120),
    )


def _to_anthropic_args(messages: list[dict]) -> dict:
    """Convert OpenAI-format messages to Anthropic API kwargs."""
    system_blocks: list[dict] = []
    chat_messages: list[dict] = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            if isinstance(content, list):
                system_blocks.extend(content)
            else:
                text = str(content)
                block: dict = {"type": "text", "text": text}
                if len(text) >= _CACHE_THRESHOLD:
                    block["cache_control"] = {"type": "ephemeral"}
                system_blocks.append(block)
        else:
            chat_messages.append({"role": role, "content": content})

    kwargs: dict = {"messages": chat_messages}
    if system_blocks:
        kwargs["system"] = system_blocks
    return kwargs


def _openai_stream(
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Generator[str, None, None]:
    response = _openai_client().chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def _anthropic_stream(
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
) -> Generator[str, None, None]:
    kwargs = _to_anthropic_args(messages)
    kwargs.update(model=model, max_tokens=max_tokens, temperature=temperature)
    with _anthropic_client().messages.stream(**kwargs) as stream:
        yield from stream.text_stream


def stream_chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """Yield text chunks using the latest runtime provider configuration."""
    chosen_model = model or _default_model()
    if _is_anthropic():
        yield from _anthropic_stream(messages, chosen_model, temperature, max_tokens)
    else:
        yield from _openai_stream(messages, chosen_model, temperature, max_tokens)


def complete_chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    return "".join(
        stream_chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )


def build_messages(
    system: str,
    user: str,
    history: list[dict] | None = None,
) -> list[dict]:
    """Build a standard OpenAI-compatible message list."""
    messages: list[dict] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})
    return messages


def build_messages_cached(
    system: str,
    context: str,
    instruction: str,
    history: list[dict] | None = None,
) -> list[dict]:
    """Build messages with cacheable context blocks for Anthropic."""
    if not _is_anthropic():
        user = (context.strip() + "\n\n" + instruction).strip() if context.strip() else instruction
        return build_messages(system, user, history)

    system_block: dict = {"type": "text", "text": system}
    if len(system) >= _CACHE_THRESHOLD:
        system_block["cache_control"] = {"type": "ephemeral"}

    user_content: list[dict] = []
    if context.strip():
        context_block: dict = {"type": "text", "text": context}
        if len(context) >= _CACHE_THRESHOLD:
            context_block["cache_control"] = {"type": "ephemeral"}
        user_content.append(context_block)
    user_content.append({"type": "text", "text": instruction})

    messages: list[dict] = [{"role": "system", "content": [system_block]}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    return messages
