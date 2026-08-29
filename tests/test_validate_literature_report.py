import json
import unittest

from research_avatar.tools.validate_literature_report import title_matches, validate


class LiteratureEvidenceTests(unittest.TestCase):
    def test_live_identity_title_matching_rejects_a_different_paper(self):
        self.assertTrue(title_matches(
            "Large Language Models Are Not Robust Multiple Choice Selectors",
            "Large Language Models Are Not Robust Multiple Choice Selectors | OpenReview",
        ))
        self.assertFalse(title_matches(
            "Large Language Models Are Not Robust Multiple Choice Selectors",
            "A Survey of Retrieval-Augmented Generation",
        ))

    def report(self, *, family_count=1, url="https://aclanthology.org/2024.test-1/"):
        contract = {
            "topic": "Provenance-aware agent memory",
            "search_date": "2026-08-27",
            "paper_count": 1,
            "family_count": family_count,
            "papers": [{
                "id": "P1", "title": "Verified Paper", "authors": ["A. Author"],
                "year": 2026, "publication_status": "published", "venue": "ACL 2026", "url": url,
                "final_url": url, "page_title": "Verified Paper - ACL Anthology",
                "verified_at": "2026-08-26",
            }],
            "families": [{"id": "F1", "title": "Methods", "paper_ids": ["P1"],
                          "failure_boundary": "Source authority may disappear during consolidation."}],
            "evidence_lanes": [
                {"id": "established", "paper_ids": []},
                {"id": "current-reviewed", "paper_ids": ["P1"]},
                {"id": "frontier-preprints", "paper_ids": []},
            ],
            "search_angles": [
                {"id": f"A{index}", "title": f"Angle {index}",
                 "queries": [f"query {index}"], "recency_queries": [f"recent {index}"],
                 "paper_ids": ["P1"]}
                for index in range(1, 5)
            ],
            "gap_falsification": {
                "queries": ["counter one", "counter two", "counter three"],
                "closest_collision_id": "P1",
                "bounded_difference": "The scoped intervention remains distinct.",
            },
        }
        return (
            '<section data-evidence-lane="established"></section>'
            '<section data-evidence-lane="current-reviewed"></section>'
            '<section data-evidence-lane="frontier-preprints"></section>'
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

    def test_rejects_missing_recency_and_gap_falsification(self):
        source = self.report()
        marker = '<script id="literature-verification" type="application/json">'
        prefix, payload = source.split(marker, 1)
        raw, suffix = payload.split("</script>", 1)
        contract = json.loads(raw)
        contract["search_angles"][0]["recency_queries"] = []
        contract["gap_falsification"]["queries"] = ["only one"]
        errors = validate(prefix + marker + json.dumps(contract) + "</script>" + suffix)
        self.assertTrue(any("recency_queries" in error for error in errors))
        self.assertTrue(any("three counterevidence" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
