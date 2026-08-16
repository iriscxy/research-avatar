import json
import tempfile
import unittest
from pathlib import Path

from research_avatar.paper_studio.api_usage import (
    append_usage,
    summarize_records,
    token_usage,
    usage_record,
    usage_summary,
)


class ApiUsageTests(unittest.TestCase):
    def test_responses_usage_and_cached_cost(self):
        response = {
            "id": "resp_1",
            "model": "gpt-5-nano",
            "usage": {
                "input_tokens": 1000,
                "input_tokens_details": {"cached_tokens": 400},
                "output_tokens": 100,
                "output_tokens_details": {"reasoning_tokens": 25},
                "total_tokens": 1100,
            },
        }
        record = usage_record(
            response, provider="openai", requested_model="gpt-5-nano", operation="test"
        )
        self.assertEqual(token_usage(response)["cached_input_tokens"], 400)
        self.assertEqual(record["estimated_cost_usd"], 0.000072)
        self.assertEqual(record["reasoning_tokens"], 25)
        self.assertNotIn("prompt", record)

    def test_chat_usage_is_normalized_and_unknown_price_is_explicit(self):
        record = usage_record(
            {
                "id": "chat_1",
                "model": "deepseek-v4-flash",
                "usage": {
                    "prompt_tokens": 12,
                    "prompt_tokens_details": {"cached_tokens": 2},
                    "completion_tokens": 3,
                    "total_tokens": 15,
                },
            },
            provider="deepseek",
            requested_model="deepseek-v4-flash",
            operation="test",
        )
        self.assertEqual(record["input_tokens"], 12)
        self.assertIsNone(record["estimated_cost_usd"])
        summary = summarize_records([record])
        self.assertFalse(summary["is_complete_estimate"])
        self.assertEqual(summary["unpriced_calls"], 1)

    def test_snapshot_uses_longest_matching_model_alias(self):
        record = usage_record(
            {
                "id": "resp_snapshot",
                "model": "gpt-5-nano-2025-08-07",
                "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
            },
            provider="openai",
            requested_model="gpt-5-nano",
            operation="test",
        )
        self.assertEqual(record["estimated_cost_usd"], 0.05)
        self.assertTrue(record["pricing_source"].endswith("/gpt-5-nano"))

    def test_jsonl_ledger_survives_one_malformed_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api_usage.jsonl"
            append_usage(path, {"total_tokens": 7, "estimated_cost_usd": 0.01})
            with path.open("a", encoding="utf-8") as handle:
                handle.write("not-json\n")
            summary = usage_summary(path)
            self.assertEqual(summary["api_calls"], 1)
            self.assertEqual(summary["total_tokens"], 7)
            self.assertEqual(summary["ledger"], "api_usage.jsonl")
            json.loads(path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
