import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
