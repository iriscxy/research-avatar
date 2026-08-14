import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoSyncTests(unittest.TestCase):
    def test_committed_demo_snapshot_is_a_fixed_self_contained_example(self):
        actual = json.loads((ROOT / "demo/runplan-state.json").read_text(encoding="utf-8"))
        self.assertTrue(actual["parts"])
        self.assertTrue(actual["goals"])
        current = actual["active_goal"] or actual["proposed_goal_id"]
        current_goals = [goal for goal in actual["goals"] if goal["id"] == current]
        self.assertEqual(len(current_goals), 1)
        self.assertTrue(current_goals[0]["goal_command"].startswith(f"/goal Complete {current}:"))

    def test_paper_demo_uses_three_real_application_screenshots(self):
        source = (ROOT / "demo/app.js").read_text(encoding="utf-8")
        self.assertNotIn("data-paper-demo-view", source)
        self.assertIn("右侧 PDF 会在内容确认后自动重新编译", source)
        self.assertIn("正文由 LLM API 写作", source)
        self.assertIn("不是 Code Agent 生成正文", source)
        self.assertIn("正文调用 LLM API（不是 Code Agent）逐段生成", source)
        self.assertIn("制作论文图片", source)
        self.assertIn("编辑结果表格", source)
        self.assertIn("?v=20260814-reader-copy", source)
        for filename in ("writing.png", "figures.png", "tables.png"):
            self.assertIn(filename, source)
            image = ROOT / "demo/assets/paper-studio" / filename
            self.assertTrue(image.exists(), filename)
            self.assertGreater(image.stat().st_size, 10_000, filename)

    def test_demo_copy_has_a_legacy_fallback_and_plan_is_sampled(self):
        source = (ROOT / "demo/app.js").read_text(encoding="utf-8")
        self.assertIn('document.execCommand("copy")', source)
        self.assertIn('representativeGoalIds = [currentId, "G2.1", "G5.1"]', source)
        self.assertNotIn("执行当前唯一 Goal", source)
        self.assertNotIn("命令与真实 Run Plan 的 Current Goal 完全一致", source)
        self.assertNotIn("完整计划没有丢失", source)

    def test_demo_headings_use_reader_facing_copy(self):
        source = (ROOT / "demo/app.js").read_text(encoding="utf-8")
        for internal_copy in (
            "执行进度和已完成图表都在 04 Run Plan",
            "直接展示真实 Paper Studio 截图",
            "REAL SCREENSHOTS",
            "FIXED HTML STRUCTURE",
            "reports/03_EXPERIMENT_PLAN.html",
            "reports/04_RUN_PLAN.html",
        ):
            self.assertNotIn(internal_copy, source)
        for reader_copy in (
            "从论文主张反推实验和证据",
            "按里程碑推进实验并同步结果",
            "在统一工作区中完成正文、图片和表格",
        ):
            self.assertIn(reader_copy, source)


if __name__ == "__main__":
    unittest.main()
