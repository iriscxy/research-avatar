import json
import unittest

from research_avatar.tools.validate_literature_report import validate


class LiteratureEvidenceTests(unittest.TestCase):
    def report(self, *, family_count=1, url="https://aclanthology.org/2024.test-1/"):
        contract = {
            "paper_count": 1,
            "family_count": family_count,
            "papers": [{
                "id": "P1", "title": "Verified Paper", "url": url,
                "final_url": url, "page_title": "Verified Paper - ACL Anthology",
                "verified_at": "2026-08-26",
            }],
            "families": [{"id": "F1", "title": "Methods", "paper_ids": ["P1"]}],
        }
        return (
            '<section data-family-id="F1"><article data-paper-id="P1">'
            f'<a href="{url}">Verified Paper</a></article></section>'
            '<script id="literature-verification" type="application/json">'
            + json.dumps(contract) + '</script>'
        )

    def test_accepts_records_rendered_from_one_source(self):
        self.assertEqual(validate(self.report()), [])

    def test_rejects_typed_family_count_and_placeholder_link(self):
        errors = validate(self.report(family_count=6, url="https://example.com/paper"))
        self.assertTrue(any("family_count" in error for error in errors))
        self.assertTrue(any("placeholder URL" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
