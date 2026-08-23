import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize
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

    def test_production_comments_and_docstrings_are_english(self):
        """Keep executable source readable while allowing localized UI strings."""
        offenders = []
        cjk = re.compile(r"[\u3400-\u9fff]")
        for path in (ROOT / "research_avatar").rglob("*.py"):
            if "demo_project" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.COMMENT and cjk.search(token.string):
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{token.start[0]} comment"
                    )
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(
                    node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    continue
                docstring = ast.get_docstring(node, clean=False)
                if docstring and cjk.search(docstring):
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', 1)} docstring"
                    )
        self.assertEqual(offenders, [])

    def test_frontend_source_comments_are_english(self):
        """Localized interface strings are allowed, but source commentary is not."""
        cjk = re.compile(r"[\u3400-\u9fff]")
        offenders = []
        for suffix in ("*.js", "*.ts", "*.css"):
            for path in (ROOT / "research_avatar").rglob(suffix):
                if "demo_project" in path.parts or "node_modules" in path.parts:
                    continue
                in_block_comment = False
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    stripped = line.lstrip()
                    is_comment = (
                        in_block_comment
                        or stripped.startswith("//")
                        or stripped.startswith("/*")
                        or stripped.startswith("*")
                    )
                    if is_comment and cjk.search(line):
                        offenders.append(f"{path.relative_to(ROOT)}:{line_number}")
                    if "/*" in stripped:
                        in_block_comment = True
                    if in_block_comment and "*/" in stripped:
                        in_block_comment = False
        self.assertEqual(offenders, [])

    def test_public_demo_contains_only_distilled_reference_moves(self):
        context_path = (
            ROOT
            / "research_avatar/online_studio/demo_project/paper/reference_context.json"
        )
        context = json.loads(context_path.read_text(encoding="utf-8"))
        self.assertTrue(context.get("public_demo_distilled"))
        self.assertEqual(context.get("reference_source"), "")
        excerpts = [
            excerpt
            for section in context["sections"].values()
            for excerpt in section["excerpts"]
        ]
        self.assertTrue(excerpts)
        self.assertTrue(all(excerpt.get("distilled") is True for excerpt in excerpts))
        self.assertLessEqual(max(len(excerpt["text"]) for excerpt in excerpts), 240)
        expplan = (
            ROOT / "research_avatar/web/demo/artifacts/expplan.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Distilled reference move", expplan)
        self.assertNotIn("Mapped reference move", expplan)

    def test_private_evidence_is_excluded_from_git_and_container_contexts(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("/uploaded-evidence/", gitignore)
        self.assertIn(
            "/research_avatar/online_studio/demo_project/uploaded-evidence/",
            gitignore,
        )
        self.assertIn("uploaded-evidence", dockerignore)
        self.assertIn(
            "research_avatar/online_studio/demo_project/uploaded-evidence",
            dockerignore,
        )

        packaging = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn('"demo_project/**/*"', packaging)
        self.assertIn('"demo_project/paper/.paper_studio/state.json"', packaging)
        self.assertIn("namespaces = false", packaging)

    def test_demo_main_tex_inputs_exist(self):
        paper = ROOT / "research_avatar/online_studio/demo_project/paper"
        source = (paper / "main.tex").read_text(encoding="utf-8")
        includes = re.findall(r"\\input\{([^}]+)\}", source)
        self.assertTrue(includes)
        missing = [
            name
            for name in includes
            if not (paper / (name if Path(name).suffix else name + ".tex")).is_file()
        ]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
