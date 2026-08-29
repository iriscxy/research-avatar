import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_avatar.tools import generate_idea_candidates_api as generator


class GenerateIdeaCandidatesApiTests(unittest.TestCase):
    def test_deepseek_generation_returns_unverified_structured_seeds(self):
        ideas = [
            {
                "title": f"Idea {index}",
                "problem": "A verified gap remains.",
                "survey_anchor": "Gap G1",
                "core_mechanism": "Intervene on one registered state transition.",
                "method_steps": ["Freeze inputs", "Measure the signature"],
                "predicted_signature": "A paired output changes.",
                "falsifier": "No paired change occurs.",
                "feasibility": "One CPU run.",
                "strongest_objection": "The setting may be narrow.",
            }
            for index in range(1, 4)
        ]
        response = {
            "id": "idea-response",
            "choices": [{"message": {"content": json.dumps({"ideas": ideas})}}],
        }
        config = {
            "provider": "deepseek",
            "api_kind": "chat-completions",
            "url": "https://api.deepseek.test/chat/completions",
            "api_key": "secret",
            "model": "deepseek-test",
        }
        with patch.object(generator, "post_json", return_value=response) as request:
            response_id, generated = generator.generate_round(
                config=config, survey="Gap G1", profile="Python", round_index=1, count=3
            )
        self.assertEqual(response_id, "idea-response")
        self.assertEqual(generated, ideas)
        payload = request.call_args.args[1]
        self.assertEqual(payload["thinking"], {"type": "disabled"}) if config["model"].startswith("deepseek-v4-") else None
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_provider_requires_only_selected_provider_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}, clear=True):
            config = generator.provider_config("deepseek")
        self.assertEqual(config["provider"], "deepseek")
        self.assertEqual(config["model"], "deepseek-v4-flash")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                generator.provider_config("openai")

    def test_invalid_json_is_repaired_by_the_provider_before_returning(self):
        ideas = [
            {
                "title": f"Idea {index}",
                "problem": "A verified gap remains.",
                "survey_anchor": "Gap G1",
                "core_mechanism": "Intervene on one registered state transition.",
                "method_steps": ["Freeze inputs", "Measure the signature"],
                "predicted_signature": "A paired output changes.",
                "falsifier": "No paired change occurs.",
                "feasibility": "One CPU run.",
                "strongest_objection": "The setting may be narrow.",
            }
            for index in range(1, 4)
        ]
        responses = [
            {"id": "bad", "choices": [{"message": {"content": '{"ideas": [}'}}]},
            {"id": "fixed", "choices": [{"message": {"content": json.dumps({"ideas": ideas})}}]},
        ]
        config = {
            "provider": "deepseek",
            "api_kind": "chat-completions",
            "url": "https://api.deepseek.test/chat/completions",
            "api_key": "secret",
            "model": "deepseek-test",
        }
        with patch.object(generator, "post_json", side_effect=responses) as request:
            response_id, generated = generator.generate_round(
                config=config, survey="Gap G1", profile="Python", round_index=1, count=3
            )
        self.assertEqual(response_id, "fixed")
        self.assertEqual(generated, ideas)
        self.assertEqual(request.call_count, 2)
        repaired_payload = request.call_args.args[1]
        self.assertIn("strict JSON contract", repaired_payload["messages"][-1]["content"])

    def test_atomic_json_leaves_a_complete_parseable_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ideas.json"
            generator.atomic_json(path, {"ideas": [{"title": "A"}]})
            self.assertEqual(json.loads(path.read_text())["ideas"][0]["title"], "A")


if __name__ == "__main__":
    unittest.main()
