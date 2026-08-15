import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import paper_preflight


class PaperPreflightTests(unittest.TestCase):
    def test_rejects_duplicate_bibliography_style_across_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            paper = Path(directory)
            main = paper / "main.tex"
            main.write_text(
                r"\documentclass{article}\input{sections/body}\bibliographystyle{plain}",
                encoding="utf-8",
            )
            (paper / "sections").mkdir()
            (paper / "sections/body.tex").write_text(
                r"\bibliographystyle{abbrv}", encoding="utf-8"
            )
            with patch.object(paper_preflight, "run") as probe:
                probe.return_value.returncode = 0
                probe.return_value.stdout = "/tex/article.cls\n"
                issues = paper_preflight.source_checks(paper, main)
            self.assertIn("duplicate_bibliographystyle", {item["issue"] for item in issues})

    def test_rejects_non_utf8_tex(self):
        with tempfile.TemporaryDirectory() as directory:
            paper = Path(directory)
            main = paper / "main.tex"
            main.write_bytes(b"\\documentclass{article}\xff")
            _, issues = paper_preflight.read_tex_tree(main, paper)
            self.assertIn("tex_not_utf8_or_unreadable", {item["issue"] for item in issues})

    def test_flags_unicode_math_that_breaks_pdflatex(self):
        with tempfile.TemporaryDirectory() as directory:
            paper = Path(directory)
            main = paper / "main.tex"
            main.write_text(r"\documentclass{article}\begin{document}a ≤ b\end{document}",
                            encoding="utf-8")
            with patch.object(paper_preflight, "run") as probe:
                probe.return_value.returncode = 0
                probe.return_value.stdout = "/tex/article.cls\n"
                issues = paper_preflight.source_checks(paper, main)
            self.assertIn("pdflatex_unsafe_unicode_math", {item["issue"] for item in issues})


if __name__ == "__main__":
    unittest.main()
