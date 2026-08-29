#!/usr/bin/env python3
"""Translate visible report HTML through an LLM API without changing evidence links."""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any
import urllib.error
import urllib.request


RECEIPT_ID = "researchlit-llm-translation"
CHECKPOINT_SCHEMA_VERSION = "1.0"
DEFAULT_GLOSSARY = {
    "Problem": "\u95ee\u9898",
    "Approaches": "\u65b9\u6cd5",
    "Evaluation": "\u8bc4\u4f30",
    "Gaps": "\u7814\u7a76\u7a7a\u767d",
    "preprint": "\u9884\u5370\u672c",
    "peer-reviewed": "\u540c\u884c\u8bc4\u5ba1",
    "baseline": "\u57fa\u7ebf",
    "benchmark": "\u57fa\u51c6",
}
EXCLUDED_TAGS = {"code", "pre", "script", "style", "svg", "math"}
EXCLUDED_CLASSES = {"who", "doi", "arxiv", "paper-meta", "citation-key", "external-link"}
PROTECTED_RE = re.compile(
    r"https?://[^\s<>\"']+|"
    r"(?:doi:)?10\.\d{4,9}/[-._;()/:A-Za-z0-9]+|"
    r"arXiv:\d{4}\.\d{4,5}|"
    r"\[[^\]]+\]|`[^`]+`|"
    r"(?<![A-Za-z0-9_])(?:[A-Z](?:[A-Z0-9_-]*[A-Z0-9])s?|[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]*)+|[A-Z]\d+)(?![A-Za-z0-9_])|"
    r"(?<![A-Za-z0-9_])\d+(?:[.,]\d+)*%?(?![A-Za-z0-9_])"
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def protected_tokens(text: str) -> list[str]:
    tokens = PROTECTED_RE.findall(text)
    # English prose commonly pluralizes acronyms ("SAEs"), while a Chinese
    # translation correctly drops that grammatical suffix ("SAE"). Preserve
    # the acronym and its occurrence count, but do not treat the English-only
    # plural marker as scientific metadata.
    normalized = [
        token[:-1]
        if token.endswith("s") and re.fullmatch(r"[A-Z][A-Z0-9_-]{1,}s", token)
        else token
        for token in tokens
    ]
    return sorted(normalized, key=lambda value: (value.lower(), value))


def protected_only_fragment(item: dict[str, Any]) -> bool:
    """Return true when the API has nothing translatable around protected tokens."""
    remaining = str(item.get("text") or "")
    tokens = item.get("protected_tokens") or []
    if not tokens:
        return False
    for token in tokens:
        remaining = remaining.replace(str(token), "", 1)
    month_words = {
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    }
    if re.sub(r"[^A-Za-z]", "", remaining).lower() in month_words:
        return True
    return re.search(r"[A-Za-z0-9\u4e00-\u9fff]", remaining) is None


class VisibleTextParser(HTMLParser):
    """Preserve HTML source while exposing only translatable visible text nodes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str | dict[str, str]] = []
        self.stack: list[tuple[str, set[str]]] = []
        self.items: list[dict[str, Any]] = []

    def _excluded(self) -> bool:
        return any(tag in EXCLUDED_TAGS or classes & EXCLUDED_CLASSES for tag, classes in self.stack)

    def _push(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes: set[str] = set()
        attributes = dict(attrs)
        for key, value in attrs:
            if key == "class" and value:
                classes.update(value.split())
        if tag.lower() == "a" and not str(attributes.get("href") or "").startswith("#"):
            classes.add("external-link")
        self.stack.append((tag.lower(), classes))

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text())
        self._push(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        lowered = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == lowered:
                del self.stack[index:]
                break

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_data(self, data: str) -> None:
        text = normalize(data)
        if self._excluded() or not text or not re.search(r"[A-Za-z\u3400-\u9fff]", text):
            self.parts.append(data)
            return
        leading = data[: len(data) - len(data.lstrip())]
        trailing = data[len(data.rstrip()) :]
        item_id = f"tr-{len(self.items) + 1:04d}"
        item = {
            "id": item_id,
            "text": text,
            "context": self.stack[-1][0] if self.stack else "document",
            "protected_tokens": protected_tokens(text),
            "leading": leading,
            "trailing": trailing,
        }
        self.items.append(item)
        self.parts.append({"id": item_id})

    def render(self, translations: dict[str, str]) -> str:
        rendered: list[str] = []
        by_id = {item["id"]: item for item in self.items}
        for part in self.parts:
            if isinstance(part, str):
                rendered.append(part)
                continue
            item = by_id[part["id"]]
            translated = translations[item["id"]]
            rendered.append(item["leading"] + html.escape(translated, quote=False) + item["trailing"])
        return "".join(rendered)


PROVIDER_DEFAULTS = {
    "openai": {
        "api_kind": "responses",
        "key_env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE_URL",
        "base_url": "https://api.openai.com/v1",
        "model_env": "RESEARCHLIT_TRANSLATION_MODEL",
        "model": "gpt-4o-mini",
        "receipt_provider": "openai-responses-api",
    },
    "deepseek": {
        "api_kind": "chat-completions",
        "key_env": "DEEPSEEK_API_KEY",
        "base_env": "DEEPSEEK_BASE_URL",
        "base_url": "https://api.deepseek.com",
        "model_env": "DEEPSEEK_TRANSLATION_MODEL",
        "model": "deepseek-v4-flash",
        "receipt_provider": "deepseek-chat-completions",
    },
    "compatible": {
        "api_kind": "chat-completions",
        "key_env": "LLM_API_KEY",
        "base_env": "LLM_BASE_URL",
        "base_url": "",
        "model_env": "LLM_TRANSLATION_MODEL",
        "model": "",
        "receipt_provider": "openai-compatible-chat-completions",
    },
}


def endpoint(base_url: str, api_kind: str) -> str:
    base = base_url.rstrip("/")
    suffix = "/responses" if api_kind == "responses" else "/chat/completions"
    return base if base.endswith(suffix) else base + suffix


def provider_config(provider: str, requested_model: str | None = None) -> dict[str, str]:
    if provider not in PROVIDER_DEFAULTS:
        raise ValueError(f"unsupported LLM provider: {provider}")
    defaults = PROVIDER_DEFAULTS[provider]
    key_env = defaults["key_env"]
    base_env = defaults["base_env"]
    model_env = defaults["model_env"]
    api_key = os.environ.get(key_env, "").strip()
    base_url = os.environ.get(base_env, defaults["base_url"]).strip()
    model = (requested_model or os.environ.get(model_env) or defaults["model"]).strip()
    missing = [name for name, value in ((key_env, api_key), (base_env, base_url), (model_env, model)) if not value]
    if missing:
        setup = "; ".join(f'export {name}="<value>"' for name in missing)
        raise ValueError(
            f"{provider} translation requires {', '.join(missing)}; "
            f"configure locally with {setup}. "
            "Code Agent translation is forbidden as a fallback"
        )
    return {
        "name": provider,
        "api_kind": defaults["api_kind"],
        "api_key": api_key,
        "url": endpoint(base_url, defaults["api_kind"]),
        "model": model,
        "receipt_provider": defaults["receipt_provider"],
        "key_env": key_env,
    }


def extract_output_text(response: dict[str, Any]) -> str:
    pieces: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                pieces.append(content.get("text", ""))
    return "\n".join(piece for piece in pieces if piece).strip()


def semantic_node_keys(items: list[dict[str, Any]]) -> None:
    """Attach stable keys that survive whitespace and unrelated DOM changes."""
    occurrences: dict[str, int] = {}
    for item in items:
        semantic = json.dumps(
            {
                "context": str(item.get("context") or ""),
                "text": normalize(str(item.get("text") or "")),
                "protected_tokens": item.get("protected_tokens") or [],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(semantic.encode("utf-8")).hexdigest()
        occurrence = occurrences.get(digest, 0) + 1
        occurrences[digest] = occurrence
        item["resume_key"] = f"{digest}:{occurrence}"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def glossary_from_path(path: Path | None, target_language: str) -> dict[str, str]:
    glossary = dict(DEFAULT_GLOSSARY) if "chinese" in target_language.casefold() else {}
    if path is None:
        return glossary
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in payload.items()
    ):
        raise ValueError("translation glossary must be a JSON object of string pairs")
    glossary.update({key.strip(): value.strip() for key, value in payload.items() if key.strip()})
    return glossary


def checkpoint_identity(
    target_language: str, config: dict[str, str], glossary: dict[str, str]
) -> dict[str, str]:
    glossary_json = json.dumps(
        glossary, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "target_language": normalize(target_language).casefold(),
        "provider": config["receipt_provider"],
        "model": config["model"],
        "glossary_sha256": hashlib.sha256(glossary_json.encode("utf-8")).hexdigest(),
    }


def load_reusable_translations(
    checkpoint_path: Path | None,
    identity: dict[str, str],
    items: list[dict[str, Any]],
) -> tuple[dict[str, str], list[str]]:
    if checkpoint_path is None or not checkpoint_path.is_file():
        return {}, []
    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []
    if checkpoint.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        return {}, []
    if any(checkpoint.get(key) != value for key, value in identity.items()):
        return {}, []
    saved = checkpoint.get("translations")
    if not isinstance(saved, dict):
        return {}, []
    translations: dict[str, str] = {}
    for item in items:
        record = saved.get(item["resume_key"])
        if not isinstance(record, dict):
            continue
        if normalize(str(record.get("source_text") or "")) != item["text"]:
            continue
        translated = normalize(str(record.get("translated_text") or ""))
        if translated and protected_tokens(translated) == item["protected_tokens"]:
            translations[item["id"]] = translated
    response_ids = [
        str(value) for value in checkpoint.get("api_response_ids", []) if str(value)
    ]
    return translations, response_ids


def save_translation_checkpoint(
    checkpoint_path: Path | None,
    identity: dict[str, str],
    items: list[dict[str, Any]],
    translations: dict[str, str],
    response_ids: list[str],
) -> None:
    if checkpoint_path is None:
        return
    records = {
        item["resume_key"]: {
            "source_text": item["text"],
            "translated_text": translations[item["id"]],
        }
        for item in items
        if item["id"] in translations
    }
    atomic_write_text(
        checkpoint_path,
        json.dumps(
            {
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                **identity,
                "translations": records,
                "api_response_ids": response_ids,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def post_json(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API returned HTTP {exc.code}: {detail[:1200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM API request failed: {exc.reason}") from exc


def translate_batch(
    items: list[dict[str, Any]], target_language: str, config: dict[str, str]
) -> tuple[str, dict[str, str]]:
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                    "required": ["id", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }
    instructions = (
        f"Translate every supplied HTML text fragment into {target_language}. "
        "Write fluent academic prose for a researcher. Preserve scientific meaning, uncertainty, "
        "claim strength, all numbers, IDs, acronyms, dataset/model/method names, and protected tokens exactly. "
        "For each item, copy every string listed in protected_tokens verbatim into the translated text, "
        "with the same spelling and count. If a fragment consists only of protected tokens plus punctuation "
        "or separators, return that fragment unchanged. "
        "Translate short ordinary English interface labels and section headings too; do not leave words such "
        "as Problem, Approaches, Evaluation, or Gaps in English unless they appear in protected_tokens. "
        "Do not add, remove, summarize, explain, or invent evidence. Do not output HTML or Markdown. "
        "Return JSON with one items array. Return every item exactly once, in input order."
    )
    glossary = config.get("_glossary") or {}
    if glossary:
        instructions += (
            " Apply this fixed project glossary whenever the source term occurs with the same "
            "meaning; do not create alternative translations: "
            + json.dumps(glossary, ensure_ascii=False, sort_keys=True)
            + "."
        )
    request_input = json.dumps(
        {"target_language": target_language, "items": [
            {"id": item["id"], "text": item["text"], "context": item["context"],
             "protected_tokens": item["protected_tokens"]}
            for item in items
        ]},
        ensure_ascii=False,
    )
    if config["api_kind"] == "responses":
        payload = {
            "model": config["model"],
            "store": False,
            "instructions": instructions,
            "input": request_input,
            "text": {"format": {"type": "json_schema", "name": "report_translation", "strict": True, "schema": schema}},
        }
    else:
        payload = {
            "model": config["model"],
            "stream": False,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": request_input},
            ],
            "response_format": {"type": "json_object"},
        }
        if config["name"] == "deepseek":
            payload["thinking"] = {"type": "disabled"}
    response = post_json(config["url"], payload, config["api_key"])
    response_id = str(response.get("id") or "")
    if config["api_kind"] == "responses":
        raw = extract_output_text(response)
    else:
        choices = response.get("choices") or []
        raw = str(choices[0].get("message", {}).get("content", "")) if choices else ""
    if not response_id or not raw:
        raise RuntimeError("LLM API response did not contain an id and translated text")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM API returned invalid translation JSON: {exc}") from exc
    values = parsed.get("items")
    if not isinstance(values, list) or len(values) != len(items):
        raise RuntimeError("LLM API returned partial translation coverage")
    translations: dict[str, str] = {}
    for expected, actual in zip(items, values):  # noqa: B905 - equal lengths checked above
        if not isinstance(actual, dict) or actual.get("id") != expected["id"]:
            raise RuntimeError(f"LLM API changed translation item order near {expected['id']}")
        translated = normalize(str(actual.get("text", "")))
        if not translated:
            raise RuntimeError(f"LLM API returned an empty translation for {expected['id']}")
        actual_tokens = protected_tokens(translated)
        if actual_tokens != expected["protected_tokens"]:
            raise RuntimeError(
                f"LLM API changed protected tokens for {expected['id']}: "
                f"expected={expected['protected_tokens']!r}, actual={actual_tokens!r}, "
                f"translation={translated!r}"
            )
        translations[expected["id"]] = translated
    return response_id, translations


def translate_html(
    source: str,
    target_language: str,
    config: dict[str, str],
    batch_size: int,
    *,
    checkpoint_path: Path | None = None,
    glossary: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    source = re.sub(
        rf'<script\b[^>]*\bid=["\']{re.escape(RECEIPT_ID)}["\'][^>]*>.*?</script>',
        "",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    parser = VisibleTextParser()
    parser.feed(source)
    parser.close()
    if not parser.items:
        raise RuntimeError("no translatable visible text was found")
    semantic_node_keys(parser.items)
    glossary = dict(glossary or {})
    config = {**config, "_glossary": glossary}
    identity = checkpoint_identity(target_language, config, glossary)
    translations, response_ids = load_reusable_translations(
        checkpoint_path, identity, parser.items
    )
    translations.update({
        item["id"]: item["text"] for item in parser.items if protected_only_fragment(item)
    })
    api_items = [item for item in parser.items if item["id"] not in translations]
    for start in range(0, len(api_items), batch_size):
        response_id, translated = translate_batch(
            api_items[start : start + batch_size], target_language, config
        )
        response_ids.append(response_id)
        translations.update(translated)
        save_translation_checkpoint(
            checkpoint_path, identity, parser.items, translations, response_ids
        )
    rendered = parser.render(translations)
    receipt = {
        "schema_version": "1.0",
        "status": "complete",
        "provider": config["receipt_provider"],
        "model": config["model"],
        "target_language": target_language,
        "translated_nodes": len(translations),
        "resumed_nodes": len(parser.items) - len(api_items),
        "api_response_ids": response_ids,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "translated_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
    }
    tag = (
        f'<script type="application/json" id="{RECEIPT_ID}">'
        + json.dumps(receipt, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        + "</script>"
    )
    if re.search(r"</body\s*>", rendered, flags=re.IGNORECASE):
        rendered = re.sub(r"</body\s*>", tag + "</body>", rendered, count=1, flags=re.IGNORECASE)
    else:
        rendered += tag
    return rendered, receipt


def main() -> int:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("html", type=Path)
    argument_parser.add_argument("--target-language", required=True)
    argument_parser.add_argument(
        "--provider",
        choices=sorted(PROVIDER_DEFAULTS),
        default=os.environ.get("RESEARCHLIT_TRANSLATION_PROVIDER", "openai"),
    )
    argument_parser.add_argument("--model")
    argument_parser.add_argument("--batch-size", type=int, default=24)
    argument_parser.add_argument(
        "--glossary",
        type=Path,
        help="optional JSON glossary merged over the built-in target-language glossary",
    )
    argument_parser.add_argument(
        "--checkpoint",
        type=Path,
        help="optional resumable checkpoint path; defaults to reports/.build/",
    )
    args = argument_parser.parse_args()
    try:
        config = provider_config(args.provider, args.model)
    except ValueError as exc:
        argument_parser.error(str(exc))
    source = args.html.read_text(encoding="utf-8")
    target_language = args.target_language.strip()
    glossary = glossary_from_path(args.glossary, target_language)
    checkpoint_path = args.checkpoint
    if checkpoint_path is None:
        checkpoint_path = (
            args.html.parent
            / ".build"
            / f"{args.html.name}.translation-{re.sub(r'[^a-z0-9]+', '-', target_language.casefold()).strip('-') or 'target'}.json"
        )
    translated, receipt = translate_html(
        source,
        target_language,
        config,
        args.batch_size,
        checkpoint_path=checkpoint_path,
        glossary=glossary,
    )
    atomic_write_text(args.html, translated)
    print(json.dumps({"status": "PASS", "file": str(args.html), "checkpoint": str(checkpoint_path), **receipt}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
