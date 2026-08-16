#!/usr/bin/env python3
"""Rewrite Idea-report prose through a selected LLM API and leave a receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from openai import OpenAI


RECEIPT_ID = "ideagen-readable-rewrite"
SUPPORTED_PROVIDERS = {"openai", "deepseek"}
ALLOWED_PARENTS = {"p", "li", "dd", "td"}
EXCLUDED_ANCESTORS = {"a", "code", "pre", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6", "th", "dt"}
FIXED_LABELS = {
    "novel", "already exists", "differentiable", "differentiable (needs framing)",
    "essential", "evaluation_scope_only", "application_swap", "high", "medium", "low",
    "selected", "needs framing", "pending", "unverified",
}
LEGACY_SEMANTIC_REPAIRS: dict[str, str] = {}
PROTECTED_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Z][A-Z0-9_-]{1,}|[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]*)+|[A-Z]?\d+(?:\.\d+)?%?|[A-Z]\d+)(?![A-Za-z0-9_])|"
    r"\[[^\]]+\]|`[^`]+`"
)
NUMERIC_RE = re.compile(r"(?<!\w)\d+(?:\.\d+)?%?(?!\w)")
LOCK_RE = re.compile(f"(?:{PROTECTED_RE.pattern})|(?:{NUMERIC_RE.pattern})")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def eligible_string(node: NavigableString) -> bool:
    text = normalize(str(node))
    if not text or text.lower() in FIXED_LABELS:
        return False
    parent = node.parent
    if parent is None or parent.name not in ALLOWED_PARENTS:
        return False
    if parent.find_parent(EXCLUDED_ANCESTORS) or parent.name in EXCLUDED_ANCESTORS:
        return False
    if parent.find_parent(attrs={"data-gpt-rewrite-id": True}):
        return False
    if parent.get("class") and any(value in {"badge", "tag", "status", "selected-banner"} for value in parent.get("class", [])):
        return False
    # Treat compact table judgments as prose too. Six CJK characters reliably
    # separates explanatory content from IDs, tiers, badges, and terse labels.
    return len(re.findall(r"[\u3400-\u9fff]", text)) >= 6


def protected_tokens(text: str) -> list[str]:
    return sorted(PROTECTED_RE.findall(text), key=lambda value: (value.lower(), value))


def parent_context(node: NavigableString) -> str:
    # Never echo the fragment itself as context: doing so invites the editor to
    # remove protected acronyms as apparent duplication. A nearby heading is
    # sufficient to preserve local meaning and grammatical role.
    heading = node.parent.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
    return f"最近的小节标题：{normalize(heading.get_text(' ', strip=True))}" if heading else "研究想法报告正文"


def response_items(client: OpenAI, model: str, batch: list[dict], retry_note: str = "") -> tuple[str, dict[str, str]]:
    payload = []
    locks_by_id: dict[str, list[tuple[str, str]]] = {}
    for item in batch:
        # Expose real terms to the editor. Opaque placeholders were frequently
        # discarded as markup; exact preservation is enforced by the multiset check.
        mapping: list[tuple[str, str]] = []
        locked_text = item["text"]
        locks_by_id[item["id"]] = mapping
        payload.append({
            "id": item["id"],
            "text": locked_text,
            "context": item["context"],
            "required_protected_tokens": item["protected_tokens"],
        })
    system = (
        "You are the final readability editor for a Chinese research-idea webpage. "
        "Rewrite every supplied text fragment so an adjacent-area researcher understands it on first read. "
        "Use direct, concrete Chinese; make the actor, action, comparison, and observable consequence explicit. "
        "Explain necessary jargon briefly in the same fragment, split overloaded clauses, and remove noun piles. "
        "The fragment will be inserted back into its original context: do not repeat a neighboring label, heading, or linked paper title already present in context. "
        "Use the domain glossary consistently: linguistic register means 语域或文体, token means 词元, steering means 激活引导, false refusal means 误拒答, and representation means 内部表示. "
        "Also translate matched style counterfactuals as 语义相同但风格不同的配对反事实样本, actuation as 执行拒答动作, guard as 独立安全防护器, and Pareto as 安全—误拒答权衡. "
        "Preserve epistemic modality exactly: a proposed comparison, hypothesis, risk, or falsifier must never become a completed experiment or positive result. "
        "Do not write vague fragments such as 概念几何高 or Pareto过拒; state the concrete property or trade-off instead. "
        "Preserve the exact scientific meaning, uncertainty, novelty verdict, falsifier, scope, numbers, IDs, and every protected token. "
        "Do not add evidence, citations, claims, recommendations, or markdown. Context is only for grammar; output only the rewritten fragment. "
        "Return one JSON object with key items; items must be an array of objects with exactly id and text, in input order. "
        + retry_note
    )
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"items": payload}, ensure_ascii=False)},
        ],
    )
    raw = completion.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM API returned invalid JSON: {exc}") from exc
    values = parsed.get("items")
    if not isinstance(values, list) or len(values) != len(batch):
        raise RuntimeError("LLM API returned partial or malformed item coverage")
    output: dict[str, str] = {}
    for expected, actual in zip(batch, values):  # noqa: B905 - equal lengths checked above
        if not isinstance(actual, dict) or actual.get("id") != expected["id"]:
            raise RuntimeError(f"LLM API changed item order/id near {expected['id']}")
        text = normalize(str(actual.get("text", "")))
        if not text:
            raise RuntimeError(f"LLM API returned empty text for {expected['id']}")
        for placeholder, token in locks_by_id[expected["id"]]:
            # Some models copy a familiar acronym verbatim instead of retaining
            # its placeholder. That is safe only if the final multiset check below
            # proves every protected occurrence is still exactly present.
            if placeholder in text:
                text = text.replace(placeholder, token)
        expected_tokens = sorted(expected["protected_tokens"])
        actual_tokens = sorted(protected_tokens(text))
        expected_numbers = sorted(token for token in expected_tokens if NUMERIC_RE.fullmatch(token))
        actual_numbers = sorted(token for token in actual_tokens if NUMERIC_RE.fullmatch(token))
        expected_ids = {token for token in expected_tokens if not NUMERIC_RE.fullmatch(token)}
        actual_ids = {token for token in actual_tokens if not NUMERIC_RE.fullmatch(token)}
        # Numeric multiplicity is semantic. Repeating an acronym for clarity is not,
        # but introducing or deleting an identifier remains forbidden.
        if actual_numbers != expected_numbers or actual_ids != expected_ids:
            raise RuntimeError(
                f"LLM API changed protected tokens for {expected['id']}: "
                f"expected={expected_tokens!r}, actual={actual_tokens!r}"
            )
        output[expected["id"]] = text
    return completion.id, output


def provider_settings(provider: str, requested_model: str | None = None) -> dict[str, str]:
    """Resolve one explicitly selected provider without inspecting another key."""
    provider = provider.strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")
    if provider == "openai":
        return {
            "provider": provider,
            "receipt_provider": "openai-api",
            "key_environment_variable": "OPENAI_API_KEY",
            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            "model": requested_model or os.environ.get("IDEAGEN_REWRITE_MODEL", "gpt-4o-mini"),
        }
    return {
        "provider": provider,
        "receipt_provider": "deepseek-api",
        "key_environment_variable": "DEEPSEEK_API_KEY",
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        "model": requested_model or os.environ.get("DEEPSEEK_IDEAGEN_REWRITE_MODEL", "deepseek-v4-flash"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument(
        "--provider", choices=sorted(SUPPORTED_PROVIDERS),
        default=os.environ.get("IDEAGEN_REWRITE_PROVIDER", "openai").strip().lower(),
    )
    parser.add_argument("--model")
    parser.add_argument("--batch-size", type=int, default=18)
    args = parser.parse_args()
    settings = provider_settings(args.provider, args.model)
    key_name = settings["key_environment_variable"]
    api_key = os.environ.get(key_name)
    if not api_key:
        parser.error(f"{key_name} is required for --provider {args.provider}; no non-API fallback is allowed")
    model = settings["model"]
    source = args.html.read_text(encoding="utf-8")
    soup = BeautifulSoup(source, "html.parser")
    old_receipt = soup.find("script", id=RECEIPT_ID)
    if old_receipt:
        old_receipt.decompose()
    for span in list(soup.find_all("span", attrs={"data-gpt-rewrite-id": True})):
        span.unwrap()
    for node in list(soup.find_all(string=True)):
        repaired = LEGACY_SEMANTIC_REPAIRS.get(normalize(str(node)))
        if repaired:
            node.replace_with(repaired)

    nodes = [node for node in soup.find_all(string=True) if isinstance(node, NavigableString) and eligible_string(node)]
    if not nodes:
        raise RuntimeError("no eligible visible explanatory text was found")
    items = []
    for index, node in enumerate(nodes, 1):
        text = normalize(str(node))
        items.append({
            "id": f"rw-{index:04d}", "node": node, "text": text,
            "context": parent_context(node), "protected_tokens": protected_tokens(text),
            "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })

    client = OpenAI(api_key=api_key, base_url=settings["base_url"])
    response_ids: list[str] = []
    rewritten: dict[str, str] = {}
    for start in range(0, len(items), args.batch_size):
        batch = items[start : start + args.batch_size]
        try:
            response_id, values = response_items(client, model, batch)
            response_ids.append(response_id)
            rewritten.update(values)
        except RuntimeError:
            # Recover a malformed batch with strict, independently verifiable one-item calls.
            for item in batch:
                required = ", ".join(item["protected_tokens"]) or "（无）"
                last_error: RuntimeError | None = None
                for _attempt in range(3):
                    try:
                        response_id, values = response_items(
                            client,
                            model,
                            [item],
                            retry_note=(
                                "This is a correction request. Copy every required protected token verbatim, with the same occurrence count. "
                                "Do not merge clauses that contain repeated numbers or identifiers. The output must contain exactly "
                                f"the same protected-token multiset as the input. Required tokens: {required}."
                            ),
                        )
                        break
                    except RuntimeError as exc:
                        last_error = exc
                else:
                    raise RuntimeError(f"LLM API failed three protected-token retries for {item['id']}: {last_error}")
                response_ids.append(response_id)
                rewritten.update(values)

    records = []
    for item in items:
        value = rewritten[item["id"]]
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        wrapper = soup.new_tag("span")
        wrapper["data-gpt-rewrite-id"] = item["id"]
        wrapper["data-gpt-output-sha256"] = digest
        wrapper.string = value
        item["node"].replace_with(wrapper)
        records.append({
            "id": item["id"], "input_sha256": item["input_sha256"],
            "output_sha256": digest,
        })

    receipt = {
        "schema_version": "1.0",
        "status": "complete",
        "provider": settings["receipt_provider"],
        "model": model,
        "rewritten_at": datetime.now(timezone.utc).isoformat(),
        "eligible_nodes": len(items),
        "rewritten_nodes": len(records),
        "api_response_ids": response_ids,
        "nodes": records,
    }
    receipt_tag = soup.new_tag("script", type="application/json", id=RECEIPT_ID)
    receipt_tag.string = json.dumps(receipt, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    (soup.body or soup).append(receipt_tag)
    args.html.write_text(str(soup), encoding="utf-8")
    print(json.dumps({
        "status": "PASS", "file": str(args.html), "provider": settings["receipt_provider"], "model": model,
        "rewritten_nodes": len(records), "api_calls": len(response_ids),
        "response_ids": response_ids,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
