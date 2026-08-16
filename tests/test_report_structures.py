import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from research_avatar.tools.validate_report_structure import REPORT_STRUCTURES, validate


ROOT = Path(__file__).resolve().parents[1]


class ReportStructureTests(unittest.TestCase):
    def test_validator_accepts_every_canonical_structure(self):
        with TemporaryDirectory() as directory:
            for kind, contract in REPORT_STRUCTURES.items():
                chunks = ["<!doctype html><html><body>"]
                for section_id, title in contract["sections"]:
                    chunks.append(
                        f'<section data-report-section="{section_id}"><h2>{title}</h2>'
                        f'<p>Filled illustrative content for {section_id}.</p>'
                    )
                    if kind == "expplan" and section_id == "projected-paper":
                        for subsection_id, subtitle in contract["subsections"]:
                            chunks.append(
                                f'<section data-report-subsection="{subsection_id}">'
                                f"<h3>{subtitle}</h3>"
                                f"<p>Filled illustrative content for {subsection_id}.</p></section>"
                            )
                    chunks.append("</section>")
                chunks.append("</body></html>")
                path = Path(directory) / f"{kind}.html"
                path.write_text("".join(chunks), encoding="utf-8")
                self.assertEqual(validate(kind, path), [], kind)

    def test_validator_rejects_reordered_sections(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.html"
            path.write_text(
                '<section data-report-section="theme-map"><h2>2. Theme Map</h2></section>'
                '<section data-report-section="scope-taxonomy"><h2>1. Scope and Taxonomy</h2></section>',
                encoding="utf-8",
            )
            self.assertTrue(validate("literature", path))

    def test_validator_rejects_title_only_sections(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "empty.html"
            path.write_text(
                "".join(
                    f'<section data-report-section="{section_id}"><h2>{title}</h2></section>'
                    for section_id, title in REPORT_STRUCTURES["ideas"]["sections"]
                ),
                encoding="utf-8",
            )
            errors = validate("ideas", path)
            self.assertTrue(any("no substantive content" in error for error in errors))

    def test_every_html_skill_names_the_shared_validator(self):
        expected = {
            "profileconstruct": "--kind profile",
            "researchlit": "--kind literature",
            "ideagen": "--kind ideas",
            "expplan": "--kind expplan",
            "runplan": "--kind runplan",
        }
        for skill, command in expected.items():
            source = (ROOT / ".agents" / "skills" / skill / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("research_avatar/tools/validate_report_structure.py", source)
            self.assertIn(command, source)
        runplan = (ROOT / ".agents/skills/runplan/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--kind results", runplan)

    @unittest.skipUnless(
        (ROOT / "researcher-profile/PROFILE.html").is_file(),
        "local researcher profile is not included in a clean clone",
    )
    def test_canonical_profile_html_matches_its_fixed_structure(self):
        self.assertEqual(validate("profile", ROOT / "researcher-profile/PROFILE.html"), [])

    def test_demo_names_every_fixed_visible_slot(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        structures = json.loads(
            (ROOT / "research_avatar/web/demo/report-structures.json").read_text(encoding="utf-8")
        )
        self.assertIn("内容预览", source)
        demo_keys = {
            "profile": "profile",
            "literature": "literature",
            "ideas": "ideas",
            "expplan": "expplan",
            "runplan": "runplan",
            "results": "results",
        }
        for report_kind, demo_key in demo_keys.items():
            expected = [
                re.sub(r"^\d+(?:\.\d+)?\.?\s*", "", title)
                for _section_id, title in REPORT_STRUCTURES[report_kind]["sections"]
            ]
            actual = [section["title"] for section in structures[demo_key]["sections"]]
            self.assertEqual(actual, expected, report_kind)
        expected_subsections = [
            re.sub(r"^\d+(?:\.\d+)?\.?\s*", "", title)
            for _section_id, title in REPORT_STRUCTURES["expplan"]["subsections"]
        ]
        self.assertEqual(
            [section["title"] for section in structures["projected-paper"]["sections"]],
            expected_subsections,
        )
        for key, contract in structures.items():
            self.assertTrue(contract["artifact"].strip(), key)
            self.assertTrue(contract["note"].strip(), key)
            for section in contract["sections"]:
                self.assertTrue(section["number"].strip(), f"{key} number")
                self.assertTrue(section["title"].strip(), f"{key} title")
                self.assertGreaterEqual(len(section["content"].strip()), 20, f"{key}:{section['title']}")
                if key == "profile":
                    self.assertEqual(len(section["details"]), 3, section["title"])
                    self.assertTrue(all(item.strip() for item in section["details"]))


if __name__ == "__main__":
    unittest.main()
