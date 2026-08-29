#!/usr/bin/env python3
"""Generate diverse, evidence-grounded idea seeds through a selected LLM API.

The output is deliberately not a novelty verdict.  IdeaGen's Code Agent still
verifies collisions, feasibility, and evidence before rendering selectable ideas.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_avatar.tools.translate_report_html import (
    endpoint,
    extract_output_text,
    post_json,
)


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and (text := re.sub(r"\s+", " ", data).strip()):
            self.parts.append(text)


def visible_text(path: Path, limit: int = 120_000) -> str:
    parser = VisibleText()
    parser.feed(path.read_text(encoding="utf-8"))
    return "\n".join(parser.parts)[:limit]


def provider_config(provider: str, model: str | None = None) -> dict[str, str]:
    if provider == "openai":
        values = {
            "api_kind": "responses",
            "key_env": "OPENAI_API_KEY",
            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "model": model or os.environ.get("IDEAGEN_MODEL", "gpt-5-mini"),
        }
    elif provider == "deepseek":
        values = {
            "api_kind": "chat-completions",
            "key_env": "DEEPSEEK_API_KEY",
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": model or os.environ.get("IDEAGEN_MODEL", "deepseek-v4-flash"),
        }
    else:
        raise ValueError(f"unsupported idea-generation provider: {provider}")
    key = os.environ.get(values["key_env"], "").strip()
    if not key:
        raise ValueError(f"{provider} idea generation requires {values['key_env']}")
    return {
        "provider": provider,
        "api_kind": values["api_kind"],
        "url": endpoint(values["base_url"], values["api_kind"]),
        "api_key": key,
        "model": values["model"],
    }


def response_text(response: dict[str, Any], api_kind: str) -> str:
    if api_kind == "responses":
        return extract_output_text(response)
    choices = response.get("choices") or []
    return str(choices[0].get("message", {}).get("content", "")) if choices else ""


def generate_round(
    *,
    config: dict[str, str],
    survey: str,
    profile: str,
    round_index: int,
    count: int,
) -> tuple[str, list[dict[str, Any]]]:
    instructions = (
        "Generate research idea seeds, not polished claims and not novelty verdicts. "
        "Use only the supplied verified survey gaps, live debates, failure boundaries, and "
        "researcher capabilities. Each seed must have one irreducible mechanism, a predicted "
        "observable signature, and a decisive falsifier. Reject cosmetic combinations such as "
        "adding a loss, router, validator, dataset, or domain without a new explanatory mechanism. "
        "Vary the causal primitive and evaluation regime across seeds. Never invent citations or "
        "claim that an idea is novel. Return strict JSON only."
    )
    prompt = json.dumps(
        {
            "round": round_index,
            "requested_count": count,
            "survey": survey,
            "researcher_profile": profile,
            "output_schema": {
                "ideas": [{
                    "title": "string",
                    "problem": "string",
                    "survey_anchor": "exact named gap/debate/failure boundary",
                    "core_mechanism": "one sentence",
                    "method_steps": ["2-4 concrete steps"],
                    "predicted_signature": "observable outcome",
                    "falsifier": "decisive negative result",
                    "feasibility": "data/compute/access assessment",
                    "strongest_objection": "string",
                }]
            },
        },
        ensure_ascii=False,
    )
    idea_schema = {
        "type": "object",
        "properties": {
            "ideas": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "problem": {"type": "string"},
                        "survey_anchor": {"type": "string"},
                        "core_mechanism": {"type": "string"},
                        "method_steps": {
                            "type": "array", "minItems": 2, "maxItems": 4,
                            "items": {"type": "string"},
                        },
                        "predicted_signature": {"type": "string"},
                        "falsifier": {"type": "string"},
                        "feasibility": {"type": "string"},
                        "strongest_objection": {"type": "string"},
                    },
                    "required": [
                        "title", "problem", "survey_anchor", "core_mechanism",
                        "method_steps", "predicted_signature", "falsifier",
                        "feasibility", "strongest_objection",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["ideas"],
        "additionalProperties": False,
    }
    if config["api_kind"] == "responses":
        payload = {
            "model": config["model"],
            "store": False,
            "instructions": instructions,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "idea_candidate_seeds",
                    "strict": True,
                    "schema": idea_schema,
                }
            },
        }
    else:
        payload = {
            "model": config["model"],
            "stream": False,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if config["model"].startswith("deepseek-v4-"):
            payload["thinking"] = {"type": "disabled"}
    failures: list[str] = []
    for attempt in range(1, 4):
        response = post_json(config["url"], payload, config["api_key"])
        response_id = str(response.get("id") or "").strip()
        raw = response_text(response, config["api_kind"])
        if not response_id or not raw:
            failures.append(f"attempt {attempt}: empty response id or body")
            continue
        try:
            parsed = json.loads(raw)
            ideas = parsed.get("ideas")
            if not isinstance(ideas, list) or len(ideas) != count:
                raise ValueError(f"expected exactly {count} ideas")
            required = {
                "title", "problem", "survey_anchor", "core_mechanism", "method_steps",
                "predicted_signature", "falsifier", "feasibility", "strongest_objection",
            }
            for index, idea in enumerate(ideas, 1):
                if not isinstance(idea, dict) or required - set(idea):
                    raise ValueError(f"idea {index} is missing required fields")
                if not isinstance(idea["method_steps"], list) or not 2 <= len(idea["method_steps"]) <= 4:
                    raise ValueError(f"idea {index} has invalid method steps")
            return response_id, ideas
        except (json.JSONDecodeError, ValueError) as exc:
            failures.append(f"attempt {attempt}: {exc}")
            repair = (
                "Your preceding response did not satisfy the requested strict JSON contract: "
                f"{exc}. Return the complete object again as valid JSON only. Do not use Markdown, "
                "comments, trailing commas, omitted fields, or ellipses."
            )
            if config["api_kind"] == "chat-completions":
                payload["messages"] = [
                    *payload["messages"],
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": repair},
                ]
            else:
                payload["input"] = f'{prompt}\n\n{repair}'
    raise RuntimeError("idea-generation API failed strict validation after 3 attempts: " + "; ".join(failures))


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey", type=Path, default=Path("reports/01_LIT_SURVEY.html"))
    parser.add_argument("--profile", type=Path, default=Path("researcher-profile/PROFILE.html"))
    parser.add_argument("--provider", choices=("openai", "deepseek"), required=True)
    parser.add_argument("--model")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--ideas-per-round", type=int, default=6)
    parser.add_argument("--output", type=Path, default=Path("reports/.build/02_IDEA_CANDIDATES.api.json"))
    args = parser.parse_args()
    if not 1 <= args.rounds <= 4 or not 3 <= args.ideas_per_round <= 10:
        parser.error("rounds must be 1-4 and ideas-per-round must be 3-10")
    try:
        config = provider_config(args.provider, args.model)
    except ValueError as exc:
        parser.error(str(exc))
    survey = visible_text(args.survey)
    profile = visible_text(args.profile, 40_000)
    if not survey or not profile:
        parser.error("survey and profile must contain readable text")
    response_ids: list[str] = []
    ideas: list[dict[str, Any]] = []
    for round_index in range(1, args.rounds + 1):
        response_id, generated = generate_round(
            config=config,
            survey=survey,
            profile=profile,
            round_index=round_index,
            count=args.ideas_per_round,
        )
        response_ids.append(response_id)
        for item in generated:
            ideas.append({**item, "api_round": round_index})
    payload = {
        "schema_version": "1.0",
        "status": "unverified_candidate_seeds",
        "provider": args.provider,
        "model": config["model"],
        "survey_sha256": hashlib.sha256(args.survey.read_bytes()).hexdigest(),
        "profile_sha256": hashlib.sha256(args.profile.read_bytes()).hexdigest(),
        "api_response_ids": response_ids,
        "ideas": ideas,
        "warning": "Candidate seeds are not novelty findings; IdeaGen must verify and rerank them.",
    }
    atomic_json(args.output, payload)
    print(json.dumps({"status": "PASS", "output": str(args.output), "ideas": len(ideas)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
