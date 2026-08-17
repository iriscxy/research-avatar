import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoSyncTests(unittest.TestCase):
    def test_committed_paper_demo_is_the_positive_mta_project(self):
        project = ROOT / "research_avatar/online_studio/demo_project"
        config = json.loads((project / "paper/paper_studio.json").read_text(encoding="utf-8"))
        state = json.loads((project / "paper/.paper_studio/state.json").read_text(encoding="utf-8"))
        project_id = "margin-targeted-typo-coling-short-20260817"
        self.assertEqual(config["project"]["id"], project_id)
        self.assertEqual(state["project_id"], project_id)
        self.assertEqual(config["figure_order"], ["F1", "F2", "F3"])
        self.assertEqual(config["table_order"], ["T1", "T2"])
        self.assertEqual(config["project"]["target"]["venue"], "COLING 2027 Short Paper")
        self.assertEqual(
            config["project"]["reference_paper"]["publication_key"],
            "wang2025word",
        )
        for figure_id in config["figure_order"]:
            figure = state["figures"][figure_id]
            self.assertEqual(figure["status"], "approved")
            self.assertTrue(figure["draw_prompt"].strip())
        for table_id in config["table_order"]:
            self.assertEqual(state["tables"][table_id]["status"], "approved")
            self.assertTrue(state["tables"][table_id]["latex"].strip())
        self.assertTrue((project / "paper/main.pdf").is_file())
        self.assertTrue((project / "paper/fig/typo_margin/F1_motivation.pptx").is_file())
        self.assertTrue(
            (project / "paper/figsrc/motivation.bg.png").is_file()
        )
        self.assertTrue((project / "paper/fig/typo_margin/actual/F2_confirmation.png").is_file())
        self.assertTrue((project / "paper/fig/typo_margin/actual/F3_budget.png").is_file())
        stale = [path for path in project.rglob("*") if "typo_basis" in path.as_posix() or "micro_typo_intent" in path.as_posix()]
        self.assertEqual(stale, [])

    def test_committed_demo_snapshot_is_a_fixed_self_contained_example(self):
        actual = json.loads((ROOT / "research_avatar/web/demo/runplan-state.json").read_text(encoding="utf-8"))
        self.assertTrue(actual["parts"])
        self.assertTrue(actual["goals"])
        self.assertEqual(actual["state"], "completed")
        self.assertIsNone(actual["active_goal"])
        self.assertIsNone(actual["proposed_goal_id"])
        self.assertEqual([goal["id"] for goal in actual["goals"]], ["G1.1", "G2.1"])
        self.assertTrue(all(goal["status"] == "completed" for goal in actual["goals"]))
        self.assertEqual(actual["approved_artifact_ids"], ["F1", "T1", "F2", "T2", "F3"])

    def test_paper_demo_mounts_the_real_completed_application(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertNotIn("data-paper-demo-view", source)
        self.assertIn('iframe src="/demo-studio/"', source)
        self.assertIn("完成态 Demo · 只读", source)
        self.assertIn("建议在新页面打开", source)
        self.assertIn("打开 Paper Studio", source)
        self.assertIn('class="paper-studio-open-callout"', source)
        self.assertIn("正文调用 LLM API（不是 Code Agent）逐段生成", source)
        self.assertIn("paper-studio-demo-api-key-required", source)
        self.assertIn("window.parent.postMessage", source)
        self.assertNotIn("这就是完成论文后的真实 Paper Studio", source)
        self.assertNotIn("下面加载固定应用本身", source)
        self.assertNotIn("不会产生 API 费用", source)
        self.assertNotIn("?v=20260814-reader-copy", source)
        self.assertNotIn("writing.png", source)

    def test_six_stage_navigation_uses_the_available_desktop_width(self):
        style = (ROOT / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        self.assertIn("width:min(100%,1500px)", style)
        self.assertIn("min-height:104px", style)
        self.assertIn(".journey-step strong{font-size:16px}", style)

    def test_cloudflare_release_copies_the_matching_paper_studio(self):
        dockerfile = (ROOT / "deploy/cloudflare/Dockerfile.release").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "COPY research_avatar/paper_studio/ "
            "/opt/research-avatar/research_avatar/paper_studio/",
            dockerfile,
        )
        self.assertIn(
            "COPY research_avatar/paper_studio/ "
            "/usr/local/lib/python3.12/site-packages/research_avatar/paper_studio/",
            dockerfile,
        )
        self.assertIn("ARG CODEX_CLI_VERSION=", dockerfile)
        self.assertIn("codex --version", dockerfile)
        self.assertIn("COPY .agents/skills/paperstudio/", dockerfile)

    def test_demo_copy_has_a_legacy_fallback_and_plan_is_sampled(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertIn('document.execCommand("copy")', source)
        self.assertIn('representativeGoalIds = [currentId, "G1.1", "G2.1"]', source)
        self.assertNotIn("执行当前唯一 Goal", source)
        self.assertNotIn("命令与真实 Run Plan 的 Current Goal 完全一致", source)
        self.assertNotIn("完整计划没有丢失", source)

    def test_demo_headings_use_reader_facing_copy(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
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
            "按证据依赖执行实验",
            "一次确认全部任务",
            "逐项确认",
            "撰写正文并制作图表",
        ):
            self.assertIn(reader_copy, source)
        self.assertIn("先确定论文要证明什么，再为每个主张安排图表、指标和失败条件", source)


if __name__ == "__main__":
    unittest.main()
