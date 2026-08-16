import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from research_avatar.tools import translate_report_html as translator


ROOT = Path(__file__).resolve().parents[1]


class TranslateReportHtmlTests(unittest.TestCase):
    @staticmethod
    def fake_response(_url, payload, _api_key):
        request = json.loads(payload.get("input") or payload["messages"][-1]["content"])
        values = [
            {"id": item["id"], "text": f"译：{item['text']}"}
            for item in request["items"]
        ]
        content = json.dumps({"items": values})
        if "messages" in payload:
            return {
                "id": "chat_translation_test",
                "choices": [{"message": {"content": content}}],
            }
        return {
            "id": "resp_translation_test",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": content}],
            }],
        }

    def test_translates_visible_text_but_preserves_paper_links_and_tokens(self):
        source = """<!doctype html><html><body>
        <h1>Survey overview</h1>
        <nav><a href="#scope">Scope and taxonomy</a></nav>
        <p>GPT safety evidence covers 12 studies.</p>
        <p>Read <a href="https://example.test/paper">Exact Paper Title</a> for evidence.</p>
        </body></html>"""
        config = {
            "name": "openai", "api_kind": "responses", "api_key": "secret",
            "url": "https://api.openai.com/v1/responses", "model": "test-model",
            "receipt_provider": "openai-responses-api", "key_env": "OPENAI_API_KEY",
        }
        with patch.object(translator, "post_json", side_effect=self.fake_response):
            output, receipt = translator.translate_html(
                source, "Chinese", config, batch_size=2
            )
        self.assertIn("译：Survey overview", output)
        self.assertIn('href="#scope">译：Scope and taxonomy</a>', output)
        self.assertIn("译：GPT safety evidence covers 12 studies.", output)
        self.assertIn(">Exact Paper Title</a>", output)
        self.assertNotIn("译：Exact Paper Title", output)
        self.assertEqual(receipt["provider"], "openai-responses-api")
        self.assertEqual(receipt["target_language"], "Chinese")
        self.assertEqual(receipt["translated_nodes"], 5)
        self.assertIn(f'id="{translator.RECEIPT_ID}"', output)

    def test_deepseek_uses_its_key_model_and_chat_completions(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "deepseek-secret"},
            clear=True,
        ):
            config = translator.provider_config("deepseek")
        self.assertEqual(config["api_key"], "deepseek-secret")
        self.assertEqual(config["model"], "deepseek-v4-flash")
        self.assertEqual(config["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(config["api_kind"], "chat-completions")
        with patch.object(translator, "post_json", side_effect=self.fake_response):
            output, receipt = translator.translate_html(
                "<html><body><p>Verified survey text.</p></body></html>",
                "Chinese",
                config,
                batch_size=4,
            )
        self.assertIn("译：Verified survey text.", output)
        self.assertEqual(receipt["provider"], "deepseek-chat-completions")

    def test_custom_compatible_provider_requires_explicit_connection_settings(self):
        with patch.dict(os.environ, {"LLM_API_KEY": "secret"}, clear=True):
            with self.assertRaisesRegex(ValueError, "LLM_BASE_URL, LLM_TRANSLATION_MODEL"):
                translator.provider_config("compatible")
        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "secret",
                "LLM_BASE_URL": "https://llm.example.test/v1",
                "LLM_TRANSLATION_MODEL": "example-model",
            },
            clear=True,
        ):
            config = translator.provider_config("compatible")
        self.assertEqual(config["url"], "https://llm.example.test/v1/chat/completions")
        self.assertEqual(config["model"], "example-model")

    def test_cli_refuses_code_agent_fallback_without_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.html"
            path.write_text("<html><body><p>Survey text.</p></body></html>", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch(
                "sys.argv", ["translate_report_html.py", str(path), "--target-language", "Chinese"]
            ):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    translator.main()
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "<html><body><p>Survey text.</p></body></html>",
            )

    def test_researchlit_translation_is_explicit_and_api_only(self):
        for skill in (
            ROOT / ".agents/skills/researchlit/SKILL.md",
            ROOT / ".claude/skills/researchlit/SKILL.md",
        ):
            source = skill.read_text(encoding="utf-8")
            normalized = " ".join(source.split())
            self.assertIn("explicitly requests a target language", normalized)
            self.assertIn("do not call any translation API", normalized)
            self.assertIn("must not translate the Survey itself", normalized)
            self.assertIn("research_avatar/tools/translate_report_html.py", normalized)
            self.assertIn("researchlit-llm-translation", normalized)
            self.assertIn("provider: openai|deepseek", normalized)
            self.assertNotIn("provider: openai|deepseek|compatible", normalized)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('DEEPSEEK_API_KEY="粘贴你的 API key"', readme)
        self.assertIn("未明确请求翻译时，`$researchlit` 不会调用任何翻译 API", readme)


if __name__ == "__main__":
    unittest.main()
