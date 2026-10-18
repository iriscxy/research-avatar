import copy
import re
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from research_avatar.tools.render_idea_report import render
from research_avatar.tools.validate_ideagen_report import validate as validate_ideas
from research_avatar.tools.validate_report_structure import validate as validate_structure


def candidate(idea_id, title, tier, selectable=True):
    grounding = [{
        "kind": "Gap", "title": "Revised facts are rarely isolated.", "anchor": "gaps",
        "failure_boundary": "Gains may not carry to histories where facts are revised.",
    }]
    urls = ["https://arxiv.org/abs/2608.19652", "https://arxiv.org/abs/2607.12893"]
    return {
        "id": idea_id, "title": title,
        "summary": f"{title} varies one controlled factor to locate where answers go stale.",
        "research_focus": "Locate the revision count at which memory answers go stale.",
        "mechanism": "Generate controlled revision chains.",
        "validation": "Sweep revision count and distance and test for a cliff.",
        "generation": {
            "setting": "profile", "retrieved_ids": ["paper2025a"], "system_sha256": "0" * 64,
            "run_id": f"fresh-{idea_id.lower()}",
            "output": {"research_focus": "Stale answers.", "method": "Controlled chains.",
                       "validation": "Sweep revisions.", "title": title},
        },
        "steps": ["Generate chains.", "Evaluate systems.", "Report the cliff."],
        "hypothesis": "Accuracy drops sharply past a revision count.",
        "falsifier": "Accuracy declines smoothly with no cliff.",
        "closest_sources": [{"title": "StateMemBench", "url": urls[0]}],
        "difference": "No opened paper runs a controlled factorial sweep over revision count and distance. " * 3,
        "own_work_overlap": "Extends the researcher's stratified benchmark habit.",
        "scope_necessity": "EVALUATION_SCOPE_ONLY", "scope_action": "relabel",
        "scope_text": "Evaluation scope only.",
        "feasibility": "Runs on one GPU.", "reviewer_risk": "May look incremental.",
        "objection": "Recent benchmarks already evaluate stale-versus-current answering and abstention. " * 3,
        "effort": "Two weeks.", "contribution_type": "diagnostic benchmark",
        "novelty_status": "novel" if tier == "A" else "differentiable (needs framing)",
        "novelty_attribute": "novel" if tier == "A" else "differentiable",
        "tier": tier, "selectable": selectable, "confidence": "medium",
        "source_grounding": grounding,
        "audit": None if not selectable else {
            "idea_id": idea_id, "verdict": "novel" if tier == "A" else "differentiable",
            "absorbable": False, "closest_work": "StateMemBench",
            "overlap": "Stale-fact evaluation is covered.",
            "independent_difference": "No opened paper sweeps revision count and distance jointly.",
            "latest_search_date": "2026-10-12", "review_context": "fresh",
            "reviewer_run_id": f"test-fresh-{idea_id.lower()}", "source_urls": urls,
            "counterevidence_queries": ["revision chain memory benchmark", "retracted fact abstention",
                                        "stale value long dialogue 2026"],
            "recent_search_window": {"start": "2026-04-12", "end": "2026-10-12"},
            "dataset_assets": [{"name": "synthetic", "status": "SELF_BUILT_UNPUBLISHED", "url": "",
                                "availability": "Generated locally."}],
            "source_grounding": grounding,
        },
    }


def model(tiers=("B", "B")):
    return {
        "title": "Which question is worth testing?", "subtitle": "Decision slate.",
        "landscape_lead": "The field has many benchmarks.", "landscape_body": "Gaps remain in diagnostics.",
        "ranking_note": "Candidates need concrete framing.", "selection": {},
        "research_question": {"id": "Q1a", "question": "When do memory agents answer with revised facts?",
                              "origin": "neutral", "gap_id": "G1"},
        "setting": "profile",
        "crowded": sum(tier == "A" for tier in tiers) < 2,
        "candidates": [candidate(f"I{i + 1}", f"EvidenceDispersion{i + 1}", tier)
                       for i, tier in enumerate(tiers)],
    }


class IdeaRendererTests(unittest.TestCase):
    def slate(self, html):
        return BeautifulSoup(html, "html.parser").select_one('[data-report-section="ranked-slate"] table')

    def test_slate_columns_drop_scope_and_show_summary(self):
        source = model()
        table = self.slate(render(source))
        headers = [th.get_text(strip=True) for th in table.select("thead th")]
        self.assertEqual(headers, ["ID", "Tier", "Idea", "Novelty", "Closest work",
                                   "Difference", "Strongest objection", "Confidence"])
        for row, item in zip(table.select("tbody tr"), source["candidates"]):
            self.assertEqual(len(row.find_all("td")), len(headers))
            self.assertIn(item["summary"], row.find_all("td")[2].get_text())

    def test_tables_use_adaptive_layout(self):
        html = render(model())
        self.assertIsNone(self.slate(html).find("colgroup"))
        self.assertNotRegex(html, r"table-layout:\s*fixed")
        self.assertRegex(html, r"table\{[^}]*table-layout:auto")
        self.assertNotRegex(html, r"table\.slate\{[^}]*(transform|100vw)")
        self.assertIn("Evidence<wbr>Dispersion1", html)

    def test_callout_follows_tier(self):
        self.assertIn("No high-confidence novel recommendation", render(model(("B", "B"))))
        tier_a = render(model(("A", "B")))
        self.assertNotIn("No high-confidence novel recommendation", tier_a)
        self.assertNotIn("Choose one Tier B candidate only", tier_a)

    def test_rendered_report_passes_validators(self):
        for tiers in (("B", "B"), ("A", "B")):
            source = copy.deepcopy(model(tiers))
            html = render(source)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "02_IDEA_REPORT.html"
                path.write_text(html, encoding="utf-8")
                self.assertEqual(validate_ideas(html) + validate_structure("ideas", path), [])


    def test_generation_record_matches_setting(self):
        html = render(model())
        self.assertIn('data-setting="profile"', html)
        self.assertIn("When do memory agents answer with revised facts?", html)
        baseline = model()
        baseline["setting"] = "none"
        errors = validate_ideas(render(baseline))
        self.assertIn("I1: generation setting differs from the slate setting", errors)
        for item in baseline["candidates"]:
            item["generation"]["setting"] = "none"
        self.assertIn("I1: the None setting cannot retrieve author_differences", validate_ideas(render(baseline)))
        for item in baseline["candidates"]:
            item["generation"]["retrieved_ids"] = []
        self.assertEqual(validate_ideas(render(baseline)), [])

    def test_direction_slate_gives_each_idea_its_own_question(self):
        source = model()
        source.pop("research_question")
        source["research_direction"] = {"id": "Q2", "title": "Memory revision", "origin": "neutral"}
        for k, item in enumerate(source["candidates"], 1):
            item["research_question"] = {"id": f"Q2.{k}", "question": f"When does revision {k} go stale?"}
        html = render(source)
        self.assertIn('data-research-direction="Q2"', html)
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(len(soup.select("[data-candidate-question]")), 2)
        self.assertIn("When does revision 1 go stale?", soup.get_text())
        for tag in soup(["script", "style"]):
            tag.decompose()
        self.assertNotIn("Q2.1", soup.get_text())
        self.assertEqual(validate_ideas(html), [])
        source["candidates"][1]["research_question"]["question"] = "When does revision 1 go stale?"
        self.assertIn("I2: research_question repeats another candidate's question", validate_ideas(render(source)))

    def test_slate_needs_two_novel_ideas_unless_marked_crowded(self):
        self.assertEqual(validate_ideas(render(model(("A", "A")))), [])
        source = model(("A", "B"))
        source["crowded"] = False
        self.assertTrue(any("at least two independently confirmed novel" in e for e in validate_ideas(render(source))))
        source["crowded"] = True
        self.assertEqual(validate_ideas(render(source)), [])


if __name__ == "__main__":
    unittest.main()
