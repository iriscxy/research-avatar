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
        self.assertNotIn("完整计划没有丢失", source)
        self.assertNotIn('class="runplan-omitted"', source)
        self.assertNotIn('reportDocument("results"', source)
        self.assertNotIn("05 只保留完整 provenance，不再单独展示", source)
        self.assertNotIn("执行进度和已完成图表都在 04 Run Plan", source)
        self.assertIn("按证据依赖执行实验", source)
        self.assertIn("一次确认全部任务", source)
        self.assertIn("逐项确认", source)
        self.assertNotIn("复制 /goal", source)

    def test_demo_uses_generic_evidence_examples(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertIn("结构参考 · Ref Paper", source)
        self.assertIn("F2 数值的完整得到过程", source)
        self.assertIn("实验结果示例 · G4.1 已完成", source)
        self.assertNotIn("MORE", source)
        self.assertNotIn("ByteDance 离线比较", source)
        self.assertNotIn("40/40 数据单元已核验", source)
        self.assertNotIn("results/typo_margin", source)


if __name__ == "__main__":
    unittest.main()
