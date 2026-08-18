"""Auditable token and estimated-cost records for Paper Studio API calls."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRICING_AS_OF = "2026-08-16"
OPENAI_PRICING: dict[str, dict[str, Any]] = {
    "gpt-5": {
        "input": 1.25, "cached_input": 0.125, "output": 10.0,
        "source": "https://developers.openai.com/api/docs/models/gpt-5",
    },
    "gpt-5-mini": {
        "input": 0.25, "cached_input": 0.025, "output": 2.0,
        "source": "https://developers.openai.com/api/docs/models/gpt-5-mini",
    },
    "gpt-5-nano": {
        "input": 0.05, "cached_input": 0.005, "output": 0.40,
        "source": "https://developers.openai.com/api/docs/models/gpt-5-nano",
    },
    "gpt-4o-mini": {
        "input": 0.15, "cached_input": 0.075, "output": 0.60,
        "source": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
    },
}
# DeepSeek publishes off-peak (01:00-04:00 and 06:00-10:00 UTC) rates at half
# of peak; peak rates are used here so a spend cap computed from this table
# never underestimates a real bill.
DEEPSEEK_PRICING: dict[str, dict[str, Any]] = {
    "deepseek-v4-flash": {
        "input": 0.44, "cached_input": 0.014, "output": 1.32,
        "source": "https://api-docs.deepseek.com/quick_start/pricing",
    },
    "deepseek-v4-pro": {
        "input": 1.32, "cached_input": 0.044, "output": 3.96,
        "source": "https://api-docs.deepseek.com/quick_start/pricing",
    },
}
_LOCK = threading.RLock()


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def token_usage(response: dict[str, Any]) -> dict[str, int]:
    """Normalize Responses and Chat Completions token accounting."""
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    input_tokens = _integer(usage.get("input_tokens", usage.get("prompt_tokens")))
    output_tokens = _integer(usage.get("output_tokens", usage.get("completion_tokens")))
    input_details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or usage.get("completion_tokens_details") or {}
    cached_tokens = min(input_tokens, _integer(input_details.get("cached_tokens")))
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": _integer(output_details.get("reasoning_tokens")),
        "total_tokens": _integer(usage.get("total_tokens")) or input_tokens + output_tokens,
    }


PROVIDER_PRICING: dict[str, dict[str, dict[str, Any]]] = {
    "openai": OPENAI_PRICING,
    "deepseek": DEEPSEEK_PRICING,
}


def usage_record(
    response: dict[str, Any], *, provider: str, requested_model: str, operation: str
) -> dict[str, Any]:
    tokens = token_usage(response)
    actual_model = str(response.get("model") or requested_model)
    price = None
    table = PROVIDER_PRICING.get(provider)
    if table is not None:
        price = table.get(actual_model)
        if price is None:
            for alias in sorted(table, key=len, reverse=True):
                if actual_model.startswith(alias + "-"):
                    price = table[alias]
                    break
    estimated_cost_usd = None
    if price is not None:
        uncached = tokens["input_tokens"] - tokens["cached_input_tokens"]
        estimated_cost_usd = round(
            (
                uncached * price["input"]
                + tokens["cached_input_tokens"] * price["cached_input"]
                + tokens["output_tokens"] * price["output"]
            ) / 1_000_000,
            10,
        )
    return {
        "schema_version": "1.0",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": actual_model,
        "operation": operation,
        "response_id": str(response.get("id") or ""),
        **tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "pricing_as_of": PRICING_AS_OF if price else None,
        "pricing_source": price["source"] if price else None,
    }


def append_usage(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with _LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate ledger records without claiming prices for unknown models."""
    priced = [item for item in records if item.get("estimated_cost_usd") is not None]
    return {
        "api_calls": len(records),
        "input_tokens": sum(_integer(item.get("input_tokens")) for item in records),
        "cached_input_tokens": sum(_integer(item.get("cached_input_tokens")) for item in records),
        "output_tokens": sum(_integer(item.get("output_tokens")) for item in records),
        "reasoning_tokens": sum(_integer(item.get("reasoning_tokens")) for item in records),
        "total_tokens": sum(_integer(item.get("total_tokens")) for item in records),
        "estimated_cost_usd": round(sum(float(item["estimated_cost_usd"]) for item in priced), 10),
        "priced_calls": len(priced),
        "unpriced_calls": len(records) - len(priced),
        "is_complete_estimate": len(priced) == len(records),
    }


def usage_summary(path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if path.exists():
        with _LOCK:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    records.append(value)
    return {**summarize_records(records), "ledger": path.name}
