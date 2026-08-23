import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoSyncTests(unittest.TestCase):
    def test_direct_demo_exposes_the_shared_language_selector(self):
        index = (ROOT / "research_avatar/web/demo/index.html").read_text(encoding="utf-8")
        app = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        style = (ROOT / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        self.assertIn('id="demo-language-select"', index)
        self.assertIn('id="demo-language-label"', index)
        self.assertIn('url.searchParams.set("lang", language)', app)
        self.assertIn('localStorage.setItem("research-avatar-language", language)', app)
        self.assertIn('<div class="demo-top-row">', index)
        self.assertIn(".demo-top-row{position:sticky;top:0", style)
        self.assertNotIn(".demo-language-control{position:fixed", style)

    def test_workflow_demo_summaries_point_to_canonical_local_reports(self):
        manifest = json.loads(
            (ROOT / "research_avatar/web/demo/artifact-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        expected = {
            "profile": ROOT / "research_avatar/online_studio/demo_project/researcher-profile/PROFILE.html",
            "literature": ROOT / "research_avatar/online_studio/demo_project/reports/01_LIT_SURVEY.html",
            "ideas": ROOT / "research_avatar/online_studio/demo_project/reports/02_IDEA_REPORT.html",
            "expplan": ROOT / "research_avatar/online_studio/demo_project/reports/03_EXPERIMENT_PLAN.html",
            "runplan": ROOT / "research_avatar/online_studio/demo_project/reports/04_RUN_PLAN.html",
        }
        self.assertEqual(set(manifest), set(expected))
        for key, source in expected.items():
            self.assertEqual(manifest[key]["source"], str(source.relative_to(ROOT)))
            self.assertTrue(source.is_file())

        app = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertIn("artifact-manifest.json", app)
        self.assertNotIn("canonical-artifact iframe", app)
        self.assertIn("<span>内容总结</span>", app)
        self.assertNotIn("功能展示", app)
        self.assertNotIn("调研范围与分类", app)

    def test_committed_paper_demo_matches_the_option_order_project(self):
        project = ROOT / "research_avatar/online_studio/demo_project"
        config = json.loads((project / "paper/paper_studio.json").read_text(encoding="utf-8"))
        state = json.loads((project / "paper/.paper_studio/state.json").read_text(encoding="utf-8"))
        project_id = "does-random-option-ordering-change-language-model-answers-a-stud-581d43e4"
        self.assertEqual(config["project"]["id"], project_id)
        self.assertEqual(state["project_id"], project_id)
        self.assertEqual(config["figure_order"], ["F1", "F2"])
        self.assertEqual(config["table_order"], ["T1"])
        self.assertEqual(config["project"]["target"]["venue"], "ACL")
        self.assertEqual(
            config["project"]["reference_paper"]["publication_key"],
            "uploadedstructuralreference",
        )
        self.assertEqual(
            [state["figures"][figure_id]["status"] for figure_id in config["figure_order"]],
            ["pending", "pending"],
        )
        self.assertEqual(
            [state["tables"][table_id]["status"] for table_id in config["table_order"]],
            ["pending"],
        )
        self.assertTrue((project / "paper/main.pdf").is_file())
        self.assertIn("Option Ordering", config["project"]["name"])
        reference_context = json.loads(
            (project / "paper/reference_context.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            reference_context["reference_title"],
            config["project"]["reference_paper"]["title"],
        )
        self.assertEqual(
            set(reference_context["sections"]),
            {section["id"] for section in config["sections"]},
        )
        stale = [path for path in project.rglob("*") if "typo_margin" in path.as_posix() or "margin-targeted" in path.as_posix()]
        self.assertEqual(stale, [])

    def test_committed_demo_snapshot_is_a_fixed_self_contained_example(self):
        actual = json.loads((ROOT / "research_avatar/web/demo/runplan-state.json").read_text(encoding="utf-8"))
        self.assertTrue(actual["parts"])
        self.assertTrue(actual["goals"])
        self.assertEqual(actual["state"], "completed")
        self.assertIsNone(actual["active_goal"])
        self.assertIsNone(actual["proposed_goal_id"])
        self.assertEqual(
            [goal["id"] for goal in actual["goals"]],
            ["G1.1", "G2.1", "G3.1", "G4.1", "G5.1"],
        )
        self.assertTrue(all(goal["status"] == "completed" for goal in actual["goals"]))
        self.assertEqual(
            actual["approved_artifact_ids"],
            ["F1", "F2", "T1"],
        )

    def test_paper_demo_mounts_the_real_completed_application(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertNotIn("data-paper-demo-view", source)
        self.assertIn('iframe src="/demo-studio/"', source)
        self.assertIn("本地当前状态快照 · 只读，输入与写入操作均已锁定", source)
        self.assertNotIn("建议在新页面打开", source)
        self.assertNotIn('class="paper-studio-open-callout"', source)
        self.assertNotIn('href="/demo-studio/"', source)
        self.assertIn("正文调用 LLM API（不是 Code Agent）逐段生成", source)
        self.assertNotIn("paper-studio-demo-api-key-required", source)
        self.assertIn(
            'window.parent.postMessage({type: "research-avatar-language", language}',
            source,
        )
        self.assertEqual(source.count("window.parent.postMessage"), 1)
        self.assertNotIn("这就是完成论文后的真实 Paper Studio", source)
        self.assertNotIn("下面加载固定应用本身", source)
        self.assertNotIn("不会产生 API 费用", source)
        self.assertNotIn("?v=20260814-reader-copy", source)
        self.assertNotIn("writing.png", source)
        self.assertIn('document.body.classList.toggle("paper-focus", stage.id === "paper")', source)
        style = (ROOT / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        self.assertIn(".paper-focus .browser-bar", style)
        self.assertIn(".paper-focus .paper-studio-frame-shell iframe{height:100%", style)

    def test_six_stage_navigation_uses_the_available_desktop_width(self):
        style = (ROOT / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        self.assertIn("width:min(100%,1500px)", style)
        self.assertIn("grid-template-columns:repeat(6,minmax(112px,1fr))", style)
        self.assertIn(".journey-step{position:relative;min-height:40px;padding:6px 9px", style)
        self.assertIn(".journey-step strong{font-size:11px", style)

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
        self.assertNotIn(".agents/skills", dockerfile)
        self.assertIn("research_avatar/tools/plan_conformance.py", dockerfile)
        self.assertIn("research_avatar/tools/validate_experiment_plan.py", dockerfile)

    def test_demo_copy_has_a_legacy_fallback_and_plan_is_sampled(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertIn('document.execCommand("copy")', source)
        self.assertIn("representativeGoalIds = runPlanDemoState.goals.map", source)
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

    def test_experiment_demo_pairs_one_projected_shell_with_one_filled_result(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        style = (ROOT / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        summary = (ROOT / "research_avatar/web/demo/report-structures.json").read_text(encoding="utf-8")
        self.assertIn('data-demo-example="projected-f2"', source)
        self.assertIn("结构参考 · Ref Paper", source)
        self.assertIn("loadExpPlanParagraphMappings", source)
        self.assertIn("artifactManifest.expplan", source)
        self.assertIn("参考论文各部分均对应到 Rough Paper", source)
        self.assertIn("先显示全部 Section 的覆盖关系，再展开两个段落示例", source)
        self.assertIn('class="section-coverage-map"', source)
        self.assertIn('class="paragraph-map-grid example-paragraph-map"', source)
        self.assertNotIn("Ref Paper · §1 P3", source)
        self.assertNotIn("Ref Paper · §3.1", source)
        self.assertNotIn("MORE", source)
        self.assertNotIn("MORE", summary)
        self.assertIn("等待左侧四个坐标点完成后自动绘图", source)
        self.assertNotIn("等待右侧合同", source)
        self.assertIn("F2 待填坐标表", source)
        self.assertIn("横坐标 x · 纳入的随机排列数量", source)
        self.assertIn("纵坐标 y · 答案始终一致的题目比例", source)
        self.assertIn(".projected-example-pair .table-scroll{overflow:visible}", style)
        self.assertIn(".projected-f2-table{width:100%;min-width:0;table-layout:fixed}", style)
        self.assertIn('data-demo-example="completed-f2"', source)
        self.assertIn("94.0%", source)
        self.assertIn("88.0%", source)
        self.assertIn('points="70,127 220,163 370,187 520,199"', source)
        self.assertIn('data-provenance-target="demo-f2-provenance"', source)
        self.assertIn("点击查看完整实验过程", source)
        self.assertIn("target.open = true", source)
        self.assertIn("code/run_option_permutations.py", source)
        self.assertIn("results/option_order/run_manifest.json", source)
        self.assertIn("goalHierarchy()", source)
        self.assertNotIn("G2.1 · 组件消融", source)
        self.assertNotIn("G3.1 · 效率约束", source)
        expplan_stage = source.index('id: "expplan"')
        self.assertLess(
            source.index('${canonicalArtifact("expplan")}', expplan_stage),
            source.index("${projectedPaperStructure()}", expplan_stage),
        )
        self.assertLess(
            source.index('${canonicalArtifact("runplan")}'),
            source.index("${completedExperimentExample()}", source.index('id: "runplan"')),
        )
        self.assertIn(".provenance-number:hover .provenance-tooltip", style)
        self.assertIn(".paragraph-map-grid", style)

        from bs4 import BeautifulSoup

        plan = BeautifulSoup(
            (ROOT / "research_avatar/web/demo/artifacts/expplan.html").read_text(
                encoding="utf-8"
            ),
            "html.parser",
        )
        paragraph_ids = [
            paragraph.find("b").get_text(strip=True)
            for paragraph in plan.select(
                '[data-report-subsection="projected-paper-structure"] .paragraph'
            )
        ]
        self.assertEqual(len(paragraph_ids), 19)
        self.assertEqual(paragraph_ids[0], "ABS-P1")
        self.assertEqual(paragraph_ids[-1], "C-P1")

    def test_paper_tab_omits_redundant_entry_strip(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertNotIn("论文写作入口", source)
        self.assertNotIn("Research Studio · 论文写作阶段", source)
        self.assertNotIn("逐段调用 LLM API；不依赖 Skill。", source)


if __name__ == "__main__":
    unittest.main()
