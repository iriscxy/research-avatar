import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from research_studio.server import (
    build_state,
    ensure_research_studio,
    extract_script_json,
    idea_report_state,
    ledger_summary,
    record_idea_selection,
    record_expplan_approval,
    render_ledger_html,
    render_publications_html,
    render_profile_html,
)


class ResearchStudioTests(unittest.TestCase):
    @patch("research_studio.server.subprocess.Popen")
    @patch("research_studio.server.research_studio_status")
    def test_ensure_reuses_existing_workspace_server(self, status, popen):
        status.return_value = {
            "running": True,
            "same_workspace": True,
            "url": "http://127.0.0.1:8780",
        }
        result = ensure_research_studio()
        self.assertFalse(result["started"])
        popen.assert_not_called()

    @patch("research_studio.server.time.sleep")
    @patch("research_studio.server.subprocess.Popen")
    @patch("research_studio.server.research_studio_status")
    def test_ensure_starts_detached_server_once(self, status, popen, _sleep):
        status.side_effect = [
            {"running": False, "same_workspace": False, "url": "http://127.0.0.1:8780"},
            {"running": True, "same_workspace": True, "url": "http://127.0.0.1:8780"},
        ]
        process = MagicMock(pid=321)
        process.poll.return_value = None
        popen.return_value = process
        result = ensure_research_studio(wait_seconds=1)
        self.assertTrue(result["started"])
        self.assertEqual(result["pid"], 321)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    @patch("research_studio.server.subprocess.Popen")
    @patch("research_studio.server.research_studio_status")
    def test_ensure_rejects_a_different_workspace_on_the_port(self, status, popen):
        status.return_value = {
            "running": True,
            "same_workspace": False,
            "url": "http://127.0.0.1:8780",
        }
        with self.assertRaisesRegex(RuntimeError, "different workspace"):
            ensure_research_studio()
        popen.assert_not_called()

    def test_six_stage_shell_uses_direct_preview_and_terminal_missing_state(self):
        root = Path(__file__).resolve().parents[1]
        app_source = (root / "research_studio" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        index_source = (
            root / "research_studio" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn('id="sidebar-command"', index_source)
        self.assertNotIn('class="project-sidebar"', index_source)
        self.assertNotIn('id="project-root"', index_source)
        self.assertNotIn('class="pipeline-legend"', index_source)
        self.assertNotIn('id="stage-header"', index_source)
        self.assertNotIn('class="studio-header"', index_source)
        self.assertNotIn('class="pipeline-head"', index_source)
        self.assertIn('class="project-toolbar"', index_source)
        self.assertIn('class="stage-surface"', index_source)
        self.assertIn("missingStageMarkup", app_source)
        self.assertIn('document.querySelector(".artifact-preview").hidden = !primaryArtifact', app_source)
        self.assertNotIn("artifactMarkup", app_source)
        self.assertNotIn("该阶段尚未开始", app_source)
        self.assertNotIn("profileTerminalMarkup", app_source)
        self.assertIn("artifactSelectorMarkup", app_source)
        self.assertIn('data-artifact-key', app_source)
        self.assertIn("selectArtifact(artifact.dataset.artifactKey)", app_source)

    def test_live_demo_matches_the_local_six_stage_navigation(self):
        root = Path(__file__).resolve().parents[1]
        demo_source = (root / "demo" / "app.js").read_text(encoding="utf-8")
        demo_style = (root / "demo" / "style.css").read_text(encoding="utf-8")
        stage_positions = [
            demo_source.index(f'id: "{stage_id}"')
            for stage_id in ("profile", "literature", "ideas", "expplan", "runplan", "paper")
        ]
        self.assertEqual(stage_positions, sorted(stage_positions))
        self.assertIn("grid-template-columns:repeat(6,1fr)", demo_style)
        self.assertIn('id: "literature"', demo_source)
        self.assertIn("compare: null", demo_source)
        self.assertNotIn("README 对比", demo_source)
        self.assertNotIn("解析研究画像", demo_source)
        self.assertNotIn("upload-zone", demo_source)
        self.assertNotIn("paper/WRITING_STYLE.md", demo_source)
        self.assertIn("PROFILE.md · Writing Style", demo_source)
        self.assertIn("$profileconstruct 使用 ~/Downloads/scholar_profile.html", demo_source)
        self.assertIn('data-action="select-idea"', demo_source)
        self.assertIn('data-action="approve-expplan"', demo_source)
        self.assertIn("04_RUN_PLAN.html", demo_source)
        self.assertIn("05_EXP_RESULT.html", demo_source)
        self.assertNotIn("RESULTS_LEDGER.csv", demo_source)
        self.assertIn("data-provenance-trigger", demo_source)
        self.assertIn("scrollIntoView", demo_source)
        self.assertIn('data-action="paper-view"', demo_source)
        self.assertIn("overflow-y:auto", demo_style)

    def test_extract_script_json_reads_named_contract(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "plan.html"
            path.write_text(
                '<script type="application/json" id="contract">'
                '{"approval_status":"approved"}</script>',
                encoding="utf-8",
            )
            self.assertEqual(
                extract_script_json(path, "contract"),
                {"approval_status": "approved"},
            )

    def test_ledger_summary_counts_verification_states(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "RESULTS_LEDGER.csv"
            path.write_text(
                "result_id,verification_status\nR1,verified\nR2,failed\nR3,pass\n",
                encoding="utf-8",
            )
            self.assertEqual(
                ledger_summary(path), {"rows": 3, "verified": 2, "invalid": 1}
            )

    def test_profile_renderer_formats_markdown_and_escapes_html(self):
        rendered = render_profile_html(
            "# Researcher Profile — Ada\n\n"
            "| Field | Value |\n|---|---|\n| Name | **Ada** |\n\n"
            "## Identity\n\n- Safe `<script>`\n"
        )
        self.assertIn("<table>", rendered)
        self.assertIn("<h2>Identity</h2>", rendered)
        self.assertIn("<strong>Ada</strong>", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_idea_selection_is_recorded_inside_canonical_report(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "02_IDEA_REPORT.html"
            path.write_text(
                '<main><div data-selected-idea="I1"><b>Selected: I1 — First</b></div>'
                '<article class="idea" data-idea-id="I1"><h3>I1 · First</h3><p class="pitch">One</p></article>'
                '<article class="idea" data-idea-id="I2"><h3>I2 · Second</h3><p class="pitch">Two</p></article>'
                '<section class="gate"><h2>已选择 I1</h2></section></main></body>',
                encoding="utf-8",
            )
            saved = record_idea_selection(path, "I2", "Best falsifier")
            state = idea_report_state(path)
            updated = path.read_text(encoding="utf-8")
        self.assertEqual(saved["selected_id"], "I2")
        self.assertEqual(state["selected_id"], "I2")
        self.assertEqual(state["reason"], "Best falsifier")
        self.assertIn("Selected: I2 — Second", updated)
        self.assertIn("已选择 I2", updated)

    def test_ledger_renderer_keeps_headers_when_no_results_exist(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "RESULTS_LEDGER.csv"
            path.write_text("result_id,status,metric,value\n", encoding="utf-8")
            rendered = render_ledger_html(path)
        self.assertIn("<th>result_id</th>", rendered)
        self.assertIn("目前没有实验结果", rendered)
        self.assertIn("0 result rows · 4 fields", rendered)

    def test_publications_renderer_builds_searchable_cards(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "publications.json"
            path.write_text(json.dumps({
                "profile": {"name": "Ada Lovelace"},
                "publications": [{
                    "title": "Analytical Engine", "authors": "A. Lovelace",
                    "venue": "Notes", "year": "1843", "cited_by": 42,
                    "task_type": "theory", "url": "https://example.org/paper",
                    "fulltext_status": "downloaded",
                }],
            }), encoding="utf-8")
            rendered = render_publications_html(path)
        self.assertIn("Ada Lovelace", rendered)
        self.assertIn("Analytical Engine", rendered)
        self.assertIn('id="search"', rendered)
        self.assertIn("42", rendered)

    def test_expplan_approval_updates_embedded_contract(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "03_EXPERIMENT_PLAN.html"
            path.write_text(
                '<h2>3. Approval</h2><p>Awaiting approval.</p>'
                '<script id="experiment-plan-contract" type="application/json">'
                '{"approval_status":"pending","selected_idea":"Test"}</script>',
                encoding="utf-8",
            )
            approval = record_expplan_approval(path)
            contract = extract_script_json(path, "experiment-plan-contract")
            updated = path.read_text(encoding="utf-8")
        self.assertEqual(approval["approval_status"], "approved")
        self.assertEqual(contract["approval_status"], "approved")
        self.assertEqual(contract["approval_channel"], "Research Studio")
        self.assertIn("Approved by the researcher", updated)

    def test_build_state_uses_canonical_project_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "researcher-profile").mkdir()
            (root / "paper" / ".paper_studio").mkdir(parents=True)
            (root / "code").mkdir()
            (root / "researcher-profile" / "PROFILE.md").write_text(
                "# Researcher Profile — Ada Lovelace\n", encoding="utf-8"
            )
            (root / "researcher-profile" / "publications.json").write_text(
                json.dumps({"publications": [{"title": "A"}, {"title": "B"}]}),
                encoding="utf-8",
            )
            for filename in ("01_LIT_SURVEY.html", "02_IDEA_REPORT.html"):
                (root / "reports" / filename).write_text(
                    f"<title>{filename}</title>", encoding="utf-8"
                )
            exp_contract = {
                "approval_status": "approved",
                "selected_idea": "Testable Idea",
                "target": {"venue": "ACL"},
                "paper_artifacts": [{"id": "T1"}],
                "baseline_contract": {"selected": [{"name": "B1"}]},
            }
            (root / "reports" / "03_EXPERIMENT_PLAN.html").write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(exp_contract)
                + "</script>",
                encoding="utf-8",
            )
            run_state = {
                "state": "awaiting_goal_activation",
                "proposed_goal_id": "G1.1",
                "goals": [
                    {"id": "G1.0", "title": "Frozen", "status": "completed"},
                    {"id": "G1.1", "title": "Smoke", "status": "proposed"},
                ],
                "acquisition_contracts": [],
            }
            (root / "reports" / "04_RUN_PLAN.html").write_text(
                '<script id="run-plan-state" type="application/json">'
                + json.dumps(run_state)
                + "</script>",
                encoding="utf-8",
            )
            (root / "reports" / "05_EXP_RESULT.html").write_text(
                '<title>Experiment Results</title><a href="#provenance-R1">42.1</a>',
                encoding="utf-8",
            )
            (root / "code" / "RESULTS_LEDGER.csv").write_text(
                "result_id,value,verification_status\nR1,42.1,verified\n",
                encoding="utf-8",
            )
            (root / "paper" / "paper_studio.json").write_text(
                json.dumps(
                    {
                        "project": {"name": "Fixture Project"},
                        "figures": {"F1": {}},
                        "tables": {"T1": {}},
                    }
                ),
                encoding="utf-8",
            )
            state = build_state(root)

        self.assertEqual(state["project"]["name"], "Fixture Project")
        self.assertFalse(state["privacy"]["stores_ip"])
        self.assertEqual([item["id"] for item in state["stages"]], [
            "profile", "literature", "ideas", "expplan", "runplan", "paper"
        ])
        self.assertEqual(state["stages"][0]["metrics"][1]["value"], "2")
        self.assertEqual(state["stages"][1]["title"], "文献 Survey")
        self.assertEqual(state["stages"][2]["title"], "Idea 选择")
        self.assertEqual(state["stages"][3]["status"], "complete")
        self.assertEqual(state["stages"][4]["metrics"][1]["value"], "G1.1")
        self.assertEqual(state["stages"][4]["goals"][0]["status"], "completed")
        self.assertEqual(
            [item["key"] for item in state["stages"][4]["artifacts"]],
            ["runplan", "results"],
        )


if __name__ == "__main__":
    unittest.main()
