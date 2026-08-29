import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoRunPlanMergeTests(unittest.TestCase):
    def test_all_current_more_goals_are_shown_and_results_page_is_not_separate(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        hierarchy = source[source.index("const goalHierarchy"):source.index("const paperStudioScreenshots")]
        self.assertIn("representativeGoalIds = runPlanDemoState.goals.map", hierarchy)
        self.assertIn("runPlanDemoState.goals.length", hierarchy)
        self.assertNotIn("representativeGoalIds = [", hierarchy)
        self.assertNotIn("The complete plan has not been lost.", source)
        self.assertNotIn('class="runplan-omitted"', source)
        self.assertNotIn('reportDocument("results"', source)
        self.assertNotIn("05 Only complete provenance is retained; it is no longer shown separately.", source)
        self.assertNotIn("Execution progress and completed charts are in 04 Run Plan.", source)
        self.assertIn("Execute experiments according to evidence dependencies", source)
        self.assertIn("Confirm all tasks at once", source)
        self.assertIn("Itemized confirmation", source)
        self.assertNotIn("Copy /goal", source)

    def test_demo_uses_generic_evidence_examples(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertIn("Structure reference · Ref Paper", source)
        self.assertIn("F2 Full process for obtaining the value.", source)
        self.assertIn("Experiment results example · G4.1 completed.", source)
        self.assertNotIn("MORE", source)
        self.assertNotIn("ByteDance Offline comparison", source)
        self.assertNotIn("40/40 Data unit verified", source)
        self.assertNotIn("results/typo_margin", source)


if __name__ == "__main__":
    unittest.main()
