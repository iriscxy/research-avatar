import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools import paper_checks


class TexTreeTests(unittest.TestCase):
    def test_recursively_expands_input_and_include(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sections").mkdir()
            (root / "main.tex").write_text(
                r"\begin{document}\input{sections/intro}\include{sections/method}\end{document}",
                encoding="utf-8",
            )
            (root / "sections/intro.tex").write_text(
                r"\section{Introduction}Visible intro.", encoding="utf-8"
            )
            (root / "sections/method.tex").write_text(
                r"\section{Method}\input{detail}", encoding="utf-8"
            )
            (root / "sections/detail.tex").write_text(
                "Nested method evidence.", encoding="utf-8"
            )
            expanded = paper_checks.read_tex_tree(root / "main.tex", root=root)
            self.assertIn(r"\section{Introduction}", expanded)
            self.assertIn("Nested method evidence.", expanded)
            self.assertNotIn(r"\input{", expanded)

    def test_ignores_commented_include(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tex").write_text(
                "% \\input{missing}\n\\begin{document}Body\\end{document}",
                encoding="utf-8",
            )
            self.assertIn("Body", paper_checks.read_tex_tree(root / "main.tex", root=root))

    def test_expands_unbraced_tex_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sections").mkdir()
            (root / "main.tex").write_text(r"\input sections/body", encoding="utf-8")
            (root / "sections/body.tex").write_text("Visible evidence", encoding="utf-8")
            self.assertIn("Visible evidence", paper_checks.read_tex_tree(root / "main.tex", root=root))

    def test_missing_include_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tex").write_text(r"\input{missing}", encoding="utf-8")
            with self.assertRaisesRegex(paper_checks.TexTreeError, "missing TeX include"):
                paper_checks.read_tex_tree(root / "main.tex", root=root)

    def test_cycle_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tex").write_text(r"\input{a}", encoding="utf-8")
            (root / "a.tex").write_text(r"\input{main}", encoding="utf-8")
            with self.assertRaisesRegex(paper_checks.TexTreeError, "cyclic TeX include"):
                paper_checks.read_tex_tree(root / "main.tex", root=root)

    def test_include_cannot_escape_paper_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "paper"
            root.mkdir()
            outside = root.parent / "outside.tex"
            outside.write_text("outside", encoding="utf-8")
            (root / "main.tex").write_text(r"\input{../outside}", encoding="utf-8")
            with self.assertRaisesRegex(paper_checks.TexTreeError, "escapes paper directory"):
                paper_checks.read_tex_tree(root / "main.tex", root=root)

    def test_style_rejects_internal_workflow_path_in_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            abstract = (
                "Agents rely on memory. Existing systems confuse old and current evidence. "
                "We introduce an authority mechanism. We evaluate three benchmark families. "
                "The method improves current-evidence accuracy. This makes memory decisions auditable."
            )
            (root / "main.tex").write_text(
                "\\begin{document}\\begin{abstract}" + abstract + "\\end{abstract}"
                "\\section{Method}The identity is checked by paper/theory/verify.py."
                + "\\begin{equation}x=x\\end{equation}" * 4
                + "\\end{document}",
                encoding="utf-8",
            )
            (root / "abstract_contract.json").write_text(
                json.dumps({
                    "min_words": 20,
                    "max_words": 80,
                    "source": "reference",
                    "slot_evidence": {
                        "motivation": "Agents rely on memory",
                        "gap": "confuse old and current evidence",
                        "method": "introduce an authority mechanism",
                        "evaluation_scope": "evaluate three benchmark families",
                        "principal_result": "improves current-evidence accuracy",
                        "takeaway": "makes memory decisions auditable",
                    },
                }),
                encoding="utf-8",
            )
            result = paper_checks.check_style(SimpleNamespace(paper_dir=str(root), main="main.tex"))
            self.assertTrue(any(item.get("metric") == "internal_workflow_leak"
                                for item in result["violations"]))

    def test_style_accepts_complete_abstract_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            abstract = (
                "Agents rely on memory. Existing systems confuse old and current evidence. "
                "We introduce an authority mechanism. We evaluate three benchmark families. "
                "The method improves current-evidence accuracy. This makes memory decisions auditable."
            )
            (root / "main.tex").write_text(
                "\\begin{document}\\begin{abstract}" + abstract + "\\end{abstract}"
                "\\section{Method}We derive the authority relation directly."
                + "\\begin{equation}x=x\\end{equation}" * 4
                + "\\end{document}",
                encoding="utf-8",
            )
            (root / "abstract_contract.json").write_text(
                json.dumps({
                    "min_words": 20,
                    "max_words": 80,
                    "source": "reference",
                    "slot_evidence": {
                        "motivation": "Agents rely on memory",
                        "gap": "confuse old and current evidence",
                        "method": "introduce an authority mechanism",
                        "evaluation_scope": "evaluate three benchmark families",
                        "principal_result": "improves current-evidence accuracy",
                        "takeaway": "makes memory decisions auditable",
                    },
                }),
                encoding="utf-8",
            )
            result = paper_checks.check_style(SimpleNamespace(paper_dir=str(root), main="main.tex"))
            abstract_metrics = {"abstract_contract", "abstract_length", "abstract_slots"}
            self.assertFalse(any(item.get("metric") in abstract_metrics
                                 for item in result["violations"]))


if __name__ == "__main__":
    unittest.main()
