import copy
import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from research_avatar.tools.render_literature_report import DEFAULT_STYLE, check_model, render
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
            "gaps": [
                {"id": f"G{g}", "text": f"Gap {g} is bounded by verified evidence.",
                 "research_questions": [{"id": f"Q{g}", "question": f"How does memory behave under condition {g}?"}]}
                for g in range(1, 4)
            ],
            "personalized_questions": [
                {"id": "PQ1", "question": "Can source authority survive consolidation?", "gap_id": "G1", "anchor": "Extends the 2025 provenance line."},
                {"id": "PQ2", "question": "Which invalidated facts still steer actions?", "gap_id": "G2", "anchor": "Follows the invalidation benchmark."},
            ],
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
        self.assertEqual([e for e in check_model(self.model()) if "question" in e or "gap" in e], [])
        broken = self.model()
        broken["gaps"][0]["research_questions"] = []
        self.assertIn("gap G1 needs exactly one research question", check_model(broken))
        self.assertEqual(len(soup.select("[data-gap-id] a")), 0)
        self.assertEqual(contract["gap_falsification"]["per_gap"], [])
        bad_closest = self.model()
        bad_closest["gaps"][0]["closest_work"] = {"paper_id": "missing", "difference": "x"}
        self.assertTrue(any("closest_work" in e for e in check_model(bad_closest)))
        self.assertIn("4. Research Questions", soup.get_text(" ", strip=True))
        self.assertNotIn("Gap 1 is bounded", soup.select_one("#gaps").get_text(" ", strip=True))
        origins = [q["origin"] for q in contract["research_questions"]]
        self.assertEqual(origins.count("neutral"), 3)
        self.assertEqual(origins.count("personalized"), 2)
        self.assertEqual(len(soup.select('[data-question-origin="personalized"]')), 2)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "survey.html"
            output.write_text(result, encoding="utf-8")
            self.assertEqual(validate_structure("literature", output), [])

    def test_research_directions_are_short_titles_with_one_sentence(self):
        source = self.model()
        source.pop("gaps")
        source.pop("personalized_questions", None)
        source["directions"] = [
            {"id": f"Q{k}", "title": f"Memory direction {k}"}
            for k in range(1, 4)
        ]
        self.assertEqual([e for e in check_model(source) if "direction" in e], [])
        html = render(source, DEFAULT_STYLE)
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select('#gaps [data-question-origin="neutral"]')
        self.assertEqual(len(items), 3)
        self.assertIn("Memory direction 1", items[0].get_text())
        self.assertEqual(validate_evidence(html), [])
        too_long = copy.deepcopy(source)
        too_long["directions"][0]["title"] = "A very long title that reads like a whole question?"
        self.assertTrue(any("short keyword" in e for e in check_model(too_long)))
        with_summary = copy.deepcopy(source)
        with_summary["directions"][0]["summary"] = "An extra sentence."
        self.assertTrue(any("needs exactly" in e for e in check_model(with_summary)))


if __name__ == "__main__":
    unittest.main()
