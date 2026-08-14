import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.sync_demo_runplan import export


ROOT = Path(__file__).resolve().parents[1]


class DemoSyncTests(unittest.TestCase):
    def test_committed_demo_snapshot_matches_canonical_run_plan(self):
        with TemporaryDirectory() as directory:
            generated = Path(directory) / "runplan-state.json"
            expected = export(ROOT / "reports/04_RUN_PLAN.html", generated)
        actual = json.loads((ROOT / "demo/runplan-state.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)
        current = actual["active_goal"] or actual["proposed_goal_id"]
        current_goals = [goal for goal in actual["goals"] if goal["id"] == current]
        self.assertEqual(len(current_goals), 1)
        self.assertTrue(current_goals[0]["goal_command"].startswith(f"/goal Complete {current}:"))

    def test_paper_demo_uses_three_real_application_screenshots(self):
        source = (ROOT / "demo/app.js").read_text(encoding="utf-8")
        self.assertNotIn("data-paper-demo-view", source)
        self.assertIn("右侧真实 Live PDF", source)
        self.assertIn("正文由 LLM API 写作", source)
        self.assertIn("不是 Code Agent 生成正文", source)
        self.assertIn("正文调用 LLM API（不是 Code Agent）逐段生成", source)
        self.assertIn("真实 GPT Image 已生成并显示", source)
        self.assertIn("真实 DEMO DATA 已通过 LaTeX 编译", source)
        self.assertIn("?v=20260814-real-artifacts", source)
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


if __name__ == "__main__":
    unittest.main()
