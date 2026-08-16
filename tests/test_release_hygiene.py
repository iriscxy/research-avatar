import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from research_avatar.tools.rewrite_ideagen_html import provider_settings


ROOT = Path(__file__).resolve().parents[1]


class ReleaseHygieneTests(unittest.TestCase):
    def test_studios_use_launch_directory_as_project_root(self):
        with TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT)
            process = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import json, research_avatar.paper_studio.server as p, research_avatar.research_studio.server as r; "
                        "print(json.dumps({'paper': str(p.ROOT), 'research': str(r.ROOT), "
                        "'figure_tool': p.FIGURE_TOOL.is_file(), 'demo': r.DEMO.is_dir()}))"
                    ),
                ],
                cwd=directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            observed = json.loads(process.stdout)
            expected_root = Path(directory).resolve()
            self.assertEqual(Path(observed["paper"]).resolve(), expected_root)
            self.assertEqual(Path(observed["research"]).resolve(), expected_root)
            self.assertTrue(observed["figure_tool"])
            self.assertTrue(observed["demo"])

    def test_ideagen_provider_settings_do_not_cross_read_keys(self):
        with mock.patch.dict(
            "os.environ",
            {
                "OPENAI_BASE_URL": "https://openai.example/v1/",
                "DEEPSEEK_BASE_URL": "https://deepseek.example/",
                "IDEAGEN_REWRITE_MODEL": "openai-model",
                "DEEPSEEK_IDEAGEN_REWRITE_MODEL": "deepseek-model",
            },
            clear=True,
        ):
            self.assertEqual(
                provider_settings("openai"),
                {
                    "provider": "openai",
                    "receipt_provider": "openai-api",
                    "key_environment_variable": "OPENAI_API_KEY",
                    "base_url": "https://openai.example/v1",
                    "model": "openai-model",
                },
            )
            self.assertEqual(
                provider_settings("deepseek"),
                {
                    "provider": "deepseek",
                    "receipt_provider": "deepseek-api",
                    "key_environment_variable": "DEEPSEEK_API_KEY",
                    "base_url": "https://deepseek.example",
                    "model": "deepseek-model",
                },
            )

    def test_shipped_instructions_have_no_personal_absolute_paths(self):
        candidates = [ROOT / "README.md", ROOT / "Makefile"]
        for directory in (
            ROOT / ".agents",
            ROOT / ".claude",
            ROOT / "research_avatar" / "tools",
        ):
            candidates.extend(path for path in directory.rglob("*") if path.is_file())
        offenders = []
        for path in candidates:
            if "__pycache__" in path.parts:
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "/Users/" in source or "C:\\Users\\" in source:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
