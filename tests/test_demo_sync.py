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
        self.assertIn('document.body.classList.toggle("embedded-demo", embeddedDemo)', app)
        self.assertIn(".embedded-demo .demo-language-control{display:none}", style)
        self.assertIn('url.searchParams.set("lang", language)', app)
        self.assertIn('localStorage.setItem("research-avatar-language", language)', app)
        self.assertIn(
            'src="/demo-studio/?lang=${encodeURIComponent(uiLanguage)}&embedded=research-studio"',
            app,
        )
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
        self.assertIn("<span>Content summary</span>", app)
        self.assertNotIn("Feature demonstration", app)
        self.assertNotIn("Research scope and classification", app)

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
            ["approved", "approved"],
        )
        self.assertEqual(
            [state["tables"][table_id]["status"] for table_id in config["table_order"]],
            ["approved"],
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
        self.assertIn(
            'iframe src="/demo-studio/?lang=${encodeURIComponent(uiLanguage)}&embedded=research-studio"',
            source,
        )
        self.assertIn("Local status snapshot is read only; input and write operations are locked.", source)
        self.assertNotIn("Recommended to open in a new page.", source)
        self.assertNotIn('class="paper-studio-open-callout"', source)
        self.assertNotIn('href="/demo-studio/"', source)
        self.assertIn("LLM API (not Code Agent) to generate content paragraph by paragraph", source)
        self.assertNotIn("paper-studio-demo-api-key-required", source)
        self.assertIn(
            'window.parent.postMessage({type: "research-avatar-language", language}',
            source,
        )
        self.assertEqual(source.count("window.parent.postMessage"), 1)
        self.assertNotIn("This is the real Paper Studio after completing the paper", source)
        self.assertNotIn("The following loads the fixed application itself.", source)
        self.assertNotIn("API fees will not be incurred.", source)
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
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
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
        self.assertNotIn(
            "research_avatar/online_studio/demo_project/paper/metrics.json",
            dockerignore.splitlines(),
        )
        self.assertIn(
            "Demo paper_studio.json references files absent from the container image",
            dockerfile,
        )

    def test_demo_copy_has_a_legacy_fallback_and_plan_is_sampled(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        self.assertIn('document.execCommand("copy")', source)
        self.assertIn("representativeGoalIds = runPlanDemoState.goals.map", source)
        self.assertNotIn("Execute the current single Goal.", source)
        self.assertNotIn("The command is fully aligned with the Current Goal in the real Run Plan.", source)
        self.assertNotIn("The complete plan has not been lost.", source)

    def test_demo_headings_use_reader_facing_copy(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        for internal_copy in (
            "Execution progress and completed charts are in 04 Run Plan.",
            "Directly display real Paper Studio screenshots.",
            "REAL SCREENSHOTS",
            "FIXED HTML STRUCTURE",
            "reports/03_EXPERIMENT_PLAN.html",
            "reports/04_RUN_PLAN.html",
        ):
            self.assertNotIn(internal_copy, source)
        for reader_copy in (
            "Infer experiments and evidence from the paper claims.",
            "Execute experiments according to evidence dependencies",
            "Confirm all tasks at once",
            "Itemized confirmation",
            "Drafting the main text and creating charts",
        ):
            self.assertIn(reader_copy, source)
        self.assertIn("First determine what the paper must prove, then assign charts, metrics, and failure conditions for each claim.", source)

    def test_experiment_demo_pairs_one_projected_shell_with_one_filled_result(self):
        source = (ROOT / "research_avatar/web/demo/app.js").read_text(encoding="utf-8")
        style = (ROOT / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        summary = (ROOT / "research_avatar/web/demo/report-structures.json").read_text(encoding="utf-8")
        self.assertIn('data-demo-example="projected-f2"', source)
        self.assertIn("Structure reference · Ref Paper", source)
        self.assertIn("loadExpPlanParagraphMappings", source)
        self.assertIn("artifactManifest.expplan", source)
        self.assertIn("All parts of the reference paper map to Rough Paper.", source)
        self.assertIn("First display the coverage relationships of all sections, then expand two paragraph examples.", source)
        self.assertIn('class="section-coverage-map"', source)
        self.assertIn('class="paragraph-map-grid example-paragraph-map"', source)
        self.assertNotIn("Ref Paper · §1 P3", source)
        self.assertNotIn("Ref Paper · §3.1", source)
        self.assertNotIn("MORE", source)
        self.assertNotIn("MORE", summary)
        self.assertIn("Wait for the four coordinates on the left to complete before automatic plotting.", source)
        self.assertNotIn("Waiting for the contract on the right.", source)
        self.assertIn("F2 Pending coordinate table.", source)
        self.assertIn("X axis x · number of included random permutations.", source)
        self.assertIn("Proportion of questions where the answer on the Y axis is always the same.", source)
        self.assertIn(".projected-example-pair .table-scroll{overflow:visible}", style)
        self.assertIn(".projected-f2-table{width:100%;min-width:0;table-layout:fixed}", style)
        self.assertIn('data-demo-example="completed-f2"', source)
        self.assertIn("94.0%", source)
        self.assertIn("88.0%", source)
        self.assertIn('points="70,127 220,163 370,187 520,199"', source)
        self.assertIn('data-provenance-target="demo-f2-provenance"', source)
        self.assertIn("Click to view the full experimental process.", source)
        self.assertIn("target.open = true", source)
        self.assertIn("code/run_option_permutations.py", source)
        self.assertIn("results/option_order/run_manifest.json", source)
        self.assertIn("goalHierarchy()", source)
        self.assertNotIn("G2.1 · Component ablation", source)
        self.assertNotIn("G3.1 · Efficiency constraints", source)
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
        self.assertNotIn("Paper writing portal", source)
        self.assertNotIn("Research Studio · Paper writing phase.", source)
        self.assertNotIn("Call LLM API per paragraph; do not rely on Skill.", source)


if __name__ == "__main__":
    unittest.main()
