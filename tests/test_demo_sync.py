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

    def test_paper_demo_exposes_three_real_workbench_views(self):
        source = (ROOT / "demo/app.js").read_text(encoding="utf-8")
        for view, label in (
            ("writing", "正文写作"),
            ("figures", "图片工作台"),
            ("tables", "表格工作台"),
        ):
            self.assertIn(f'{view}: () =>', source)
            self.assertIn(label, source)
        self.assertIn("Accept → LaTeX", source)
        self.assertIn("可编辑 Table LaTeX", source)
        self.assertIn("确认并插入正文", source)


if __name__ == "__main__":
    unittest.main()
