import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoRunPlanMergeTests(unittest.TestCase):
    def test_completed_result_is_nested_in_goal_and_results_page_is_not_separate(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        hierarchy = source[source.index("const goalHierarchy"):source.index("const completedF2Rows")]
        self.assertIn('completedExample ? resultProvenanceDemo() : ""', hierarchy)
        self.assertIn('goal.id === "G2.1"', hierarchy)
        self.assertNotIn("完整计划没有丢失", source)
        self.assertNotIn('class="runplan-omitted"', source)
        self.assertNotIn('reportDocument("results"', source)
        self.assertNotIn("05 只保留完整 provenance，不再单独展示", source)
        self.assertNotIn("执行进度和已完成图表都在 04 Run Plan", source)
        self.assertIn("把完整实验拆成一个个 Goal", source)
        self.assertIn("一次确认全部 Goals", source)
        self.assertIn("逐个查看并确认", source)
        self.assertNotIn("复制 /goal", source)

    def test_completed_goal_contains_source_table_plot_and_hover_process(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertIn('class="result-shell source-table completed-source"', source)
        self.assertIn('class="completed-chart"', source)
        self.assertIn('class="provenance-tooltip"', source)
        self.assertIn("40/40 数据单元已核验", source)
        self.assertIn("每个数字都能查看结果路径、计算方法、命令和验证状态", source)
        self.assertIn("<strong>运行命令</strong>", source)
        style = (ROOT / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        self.assertIn(".expanded-goal>.completed-result", style)


if __name__ == "__main__":
    unittest.main()
