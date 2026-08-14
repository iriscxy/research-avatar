import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoRunPlanMergeTests(unittest.TestCase):
    def test_completed_result_is_nested_in_goal_and_results_page_is_not_separate(self):
        source = (ROOT / "demo/app.js").read_text(encoding="utf-8")
        hierarchy = source[source.index("const goalHierarchy"):source.index("const completedF2Rows")]
        self.assertIn('completedExample ? resultProvenanceDemo() : ""', hierarchy)
        self.assertIn('goal.id === "G2.1"', hierarchy)
        self.assertNotIn('reportDocument("results"', source)
        self.assertIn("05 只保留完整 provenance，不再单独展示", source)

    def test_completed_goal_contains_source_table_plot_and_hover_process(self):
        source = (ROOT / "demo/app.js").read_text(encoding="utf-8")
        self.assertIn('class="result-shell source-table completed-source"', source)
        self.assertIn('class="completed-chart"', source)
        self.assertIn('class="provenance-tooltip"', source)
        self.assertIn("<strong>Command</strong>", source)
        style = (ROOT / "demo/style.css").read_text(encoding="utf-8")
        self.assertIn(".expanded-goal>.completed-result", style)


if __name__ == "__main__":
    unittest.main()
