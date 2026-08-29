import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from research_avatar.tools.render_literature_report import DEFAULT_STYLE, render
from research_avatar.tools.validate_literature_report import validate as validate_evidence
from research_avatar.tools.validate_report_structure import validate as validate_structure


class LiteratureRendererTests(unittest.TestCase):
    def model(self):
        paper = {
            "id": "P1", "title": "Verified Paper", "authors": ["A. Author"],
            "year": 2026, "publication_status": "published", "venue": "ACL 2026",
            "url": "https://aclanthology.org/2026.test-1/",
            "final_url": "https://aclanthology.org/2026.test-1/",
            "page_title": "Verified Paper", "verified_at": "2026-08-27",
            "primary_family": "Methods", "takeaway": "A verified contribution.",
        }
        return {
            "topic": "Provenance-aware agent memory", "search_date": "2026-08-27",
            "coverage_years": "2023–2026", "sources": ["ACL Anthology"],
            "title": "A Verified Survey", "subtitle": "Evidence-led synthesis.",
            "taxonomy": ["Input", "Memory", "Action"],
            "problem": {"lead": "A concrete problem with durable consequences.",
                        "paragraphs": ["This paragraph defines the scope and assumptions."],
                        "callout": "The central distinction is operational."},
            "approaches_lead": "Methods differ in the decisions they make.",
            "evaluation_lead": "Evaluation must test both retrieval and action.",
            "gaps_lead": "The remaining gaps are bounded by verified collisions.",
            "papers": [paper],
            "families": [{"id": "F1", "title": "Methods", "inclusion_rule": "Writes memory.",
                          "comparison": "The methods differ in source handling.",
                          "failure_boundary": "Source authority may disappear during consolidation.",
                          "paper_ids": ["P1"]}],
            "search_angles": [{"id": f"A{i}", "title": f"Angle {i}",
                               "queries": [f"query {i}"], "recency_queries": [f"recent {i}"],
                               "paper_ids": ["P1"]} for i in range(1, 5)],
            "gap_falsification": {"queries": ["counter 1", "counter 2", "counter 3"],
                                  "closest_collision_id": "P1",
                                  "bounded_difference": "Only the joint contract remains open."},
            "verification_notes": ["Verified against the official page."],
            "evaluation_regimes": [{"title": "Action evaluation",
                                    "description": "Tests whether memory changes behavior.",
                                    "paper_ids": ["P1"]}],
            "debates": [{"title": "Ownership", "text": "Authority and attribution differ."}],
            "trends": ["Write policies are becoming explicit."],
            "openings": ["Evaluate authority-preserving action under invalidation."],
        }

    def test_one_source_drives_counts_cards_and_contract(self):
        result = render(self.model(), DEFAULT_STYLE)
        soup = BeautifulSoup(result, "html.parser")
        self.assertIn("1 verified papers", soup.get_text(" ", strip=True))
        self.assertEqual(len(soup.select("[data-paper-id]")), 1)
        contract = json.loads(soup.select_one("#literature-verification").string)
        self.assertEqual(contract["paper_count"], 1)
        self.assertEqual(contract["family_count"], 1)
        self.assertEqual(validate_evidence(result), [])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "survey.html"
            output.write_text(result, encoding="utf-8")
            self.assertEqual(validate_structure("literature", output), [])


if __name__ == "__main__":
    unittest.main()
