import json
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, call, patch

import research_avatar.research_studio.server as studio
from research_avatar.research_studio.server import (
    Handler,
    build_state,
    ensure_project_studios,
    ensure_research_studio,
    extract_script_json,
    idea_report_state,
    ledger_summary,
    record_idea_selection,
    record_expplan_approval,
    render_ledger_html,
    render_publications_html,
    start_paper_studio,
)


class ResearchStudioTests(unittest.TestCase):
    def test_http_server_accepts_browser_asset_bursts(self):
        self.assertGreaterEqual(studio.StudioHTTPServer.request_queue_size, 32)

    @patch.object(studio.LOCAL_URL_OPENER, "open")
    def test_paper_studio_status_uses_state_independent_health_endpoint(self, open_url):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"ok": True, "project": {"root": str(studio.ROOT)}}
        ).encode("utf-8")
        open_url.return_value.__enter__.return_value = response

        status = studio.paper_studio_status()

        self.assertTrue(status["running"])
        self.assertTrue(status["same_workspace"])
        open_url.assert_called_once_with(
            f"{studio.PAPER_STUDIO_URL}/api/health", timeout=1.2
        )

    def test_profile_job_state_is_initialized_and_uses_profile_html_only(self):
        source = Path(studio.__file__).read_text(encoding="utf-8")
        self.assertNotIn("researcher-profile/profile.md", source.lower())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "researcher-profile" / "PROFILE.html"
            profile.parent.mkdir(parents=True)
            profile.write_text("<html><body>Writing Style</body></html>", encoding="utf-8")
            with patch.dict(
                studio.PROFILE_JOB,
                {"status": "complete", "message": "done", "logs": []},
                clear=True,
            ):
                state = studio.profile_job_state()
                progress = studio.profile_progress_state(state, root)
        self.assertEqual(state["status"], "complete")
        self.assertEqual(progress["percent"], 100)
        self.assertEqual(progress["current_phase"], 8)

    @patch("research_avatar.research_studio.server.subprocess.Popen")
    @patch("research_avatar.research_studio.server.paper_studio_status")
    def test_paper_studio_rejects_a_different_workspace_on_the_port(self, status, popen):
        status.return_value = {
            "running": True,
            "same_workspace": False,
            "url": "http://127.0.0.1:8765",
        }
        result = start_paper_studio()
        self.assertFalse(result["ok"])
        self.assertIn("different workspace", result["error"])
        popen.assert_not_called()

    @patch("research_avatar.research_studio.server.time.sleep")
    @patch("research_avatar.research_studio.server.subprocess.Popen")
    @patch("research_avatar.research_studio.server.paper_studio_status")
    def test_paper_studio_waits_for_delayed_readiness(self, status, popen, sleep):
        status.side_effect = [
            {"running": False, "same_workspace": False, "url": studio.PAPER_STUDIO_URL},
            {"running": False, "same_workspace": False, "url": studio.PAPER_STUDIO_URL},
            {"running": True, "same_workspace": True, "url": studio.PAPER_STUDIO_URL},
        ]
        process = MagicMock()
        process.poll.return_value = None
        popen.return_value = process

        with patch.object(studio, "PAPER_STUDIO_PROCESS", None):
            result = start_paper_studio()

        self.assertTrue(result["ok"])
        self.assertFalse(result["already_running"])
        sleep.assert_called_once_with(0.15)

    @patch("research_avatar.research_studio.server.time.sleep")
    @patch("research_avatar.research_studio.server.subprocess.Popen")
    @patch("research_avatar.research_studio.server.paper_studio_status")
    def test_paper_studio_reports_log_when_process_exits(self, status, popen, sleep):
        status.return_value = {
            "running": False,
            "same_workspace": False,
            "url": studio.PAPER_STUDIO_URL,
        }
        process = MagicMock()
        process.poll.return_value = 1
        popen.return_value = process

        with patch.object(studio, "PAPER_STUDIO_PROCESS", None):
            result = start_paper_studio()

        self.assertFalse(result["ok"])
        self.assertIn("exited during startup", result["error"])
        self.assertIn("paper-studio-", result["error"])
        sleep.assert_not_called()

    def test_request_body_rejects_arrays_and_oversized_payloads(self):
        handler = object.__new__(Handler)
        handler.headers = {"Content-Length": "2"}
        handler.rfile = io.BytesIO(b"[]")
        with self.assertRaisesRegex(ValueError, "JSON object"):
            handler.read_json()

        handler.headers = {"Content-Length": "20000"}
        handler.rfile = io.BytesIO(b"{}")
        with self.assertRaisesRegex(ValueError, "body size"):
            handler.read_json()

    def test_cancelled_response_does_not_emit_handler_traceback(self):
        class ClosedSocket:
            def write(self, _data):
                raise BrokenPipeError("browser closed preview")

        handler = object.__new__(Handler)
        handler.wfile = ClosedSocket()
        handler.close_connection = False
        handler.write_body(b"preview")
        self.assertTrue(handler.close_connection)

    @patch("research_avatar.research_studio.server.subprocess.Popen")
    @patch("research_avatar.research_studio.server.research_studio_status")
    def test_ensure_reuses_existing_workspace_server(self, status, popen):
        status.return_value = {
            "running": True,
            "same_workspace": True,
            "url": "http://127.0.0.1:8780",
        }
        result = ensure_research_studio()
        self.assertFalse(result["started"])
        popen.assert_not_called()

    @patch("research_avatar.research_studio.server.time.sleep")
    @patch("research_avatar.research_studio.server.subprocess.Popen")
    @patch("research_avatar.research_studio.server.research_studio_status")
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

    @patch("research_avatar.research_studio.server.subprocess.Popen")
    @patch("research_avatar.research_studio.server.research_studio_status")
    def test_ensure_rejects_a_different_workspace_on_the_port(self, status, popen):
        status.return_value = {
            "running": True,
            "same_workspace": False,
            "url": "http://127.0.0.1:8780",
        }
        with self.assertRaisesRegex(RuntimeError, "different workspace"):
            ensure_research_studio()
        popen.assert_not_called()

    @patch("research_avatar.research_studio.server.webbrowser.open")
    @patch("research_avatar.research_studio.server.start_paper_studio")
    @patch("research_avatar.research_studio.server.ensure_research_studio")
    def test_ensure_project_studios_reuses_both_and_opens_pages(
        self, ensure_research, start_paper, open_browser
    ):
        ensure_research.return_value = {
            "url": "http://127.0.0.1:8780",
            "started": False,
        }
        start_paper.return_value = {
            "ok": True,
            "url": "http://127.0.0.1:8765",
            "already_running": True,
        }

        result = ensure_project_studios()

        self.assertEqual(
            result["urls"],
            ["http://127.0.0.1:8780", "http://127.0.0.1:8765"],
        )
        self.assertEqual(
            open_browser.call_args_list,
            [call("http://127.0.0.1:8780"), call("http://127.0.0.1:8765")],
        )

    @patch("research_avatar.research_studio.server.webbrowser.open")
    @patch("research_avatar.research_studio.server.start_paper_studio")
    @patch("research_avatar.research_studio.server.ensure_research_studio")
    def test_ensure_project_studios_can_skip_browser(
        self, ensure_research, start_paper, open_browser
    ):
        ensure_research.return_value = {"url": "http://127.0.0.1:8780"}
        start_paper.return_value = {"ok": True, "url": "http://127.0.0.1:8765"}

        ensure_project_studios(open_browser=False)

        open_browser.assert_not_called()

    def test_six_stage_shell_is_a_minimal_direct_preview(self):
        root = Path(__file__).resolve().parents[1]
        app_source = (
            root / "research_avatar" / "research_studio" / "static" / "app.js"
        ).read_text(
            encoding="utf-8"
        )
        index_source = (
            root / "research_avatar" / "research_studio" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn('id="sidebar-command"', index_source)
        self.assertNotIn('class="project-sidebar"', index_source)
        self.assertNotIn('id="project-root"', index_source)
        self.assertNotIn('class="pipeline-legend"', index_source)
        self.assertNotIn('id="stage-header"', index_source)
        self.assertNotIn('class="studio-header"', index_source)
        self.assertNotIn('class="pipeline-head"', index_source)
        self.assertNotIn('class="project-toolbar"', index_source)
        self.assertNotIn('id="refresh"', index_source)
        self.assertNotIn('id="stage-body"', index_source)
        self.assertIn('class="stage-surface"', index_source)
        self.assertNotIn("missingStageMarkup", app_source)
        self.assertNotIn("goalMarkup", app_source)
        self.assertNotIn("ideaMarkup", app_source)
        self.assertNotIn("expplanApprovalMarkup", app_source)
        self.assertNotIn("artifactMarkup", app_source)
        self.assertNotIn("该阶段尚未开始", app_source)
        self.assertNotIn("profileTerminalMarkup", app_source)
        self.assertNotIn("artifactSelectorMarkup", app_source)
        self.assertIn("selectArtifact(primaryArtifact.key)", app_source)
        self.assertIn('id="preview-open"', index_source)
        self.assertIn('id="preview-command"', index_source)
        self.assertIn("请在终端运行以下命令", index_source)
        self.assertIn('previewCommand.textContent = stage.command', app_source)

    def test_pipeline_tabs_use_readable_typography_and_bumped_cache(self):
        root = Path(__file__).resolve().parents[1]
        style_source = (
            root / "research_avatar" / "research_studio" / "static" / "style.css"
        ).read_text(encoding="utf-8")
        index_source = (
            root / "research_avatar" / "research_studio" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(".pipeline-button strong{font-size:14px", style_source)
        self.assertIn("font:750 10px var(--serif)", style_source)
        self.assertIn("/style.css?v=20260810-typography", index_source)

    def test_live_demo_matches_the_local_six_stage_navigation(self):
        root = Path(__file__).resolve().parents[1]
        demo_source = (
            root / "research_avatar" / "web" / "demo" / "app.js"
        ).read_text(encoding="utf-8")
        demo_style = (
            root / "research_avatar" / "web" / "demo" / "style.css"
        ).read_text(encoding="utf-8")
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
        self.assertNotIn("PROFILE.md", demo_source)
        self.assertNotIn('data-action="profile-section"', demo_source)
        self.assertIn('reportDocument("profile"', demo_source)
        self.assertNotIn("profileDocument", demo_source)
        self.assertNotIn('class="profile-output"', demo_source)
        self.assertIn("$profileconstruct 使用 ~/Downloads/scholar_profile.html", demo_source)
        for report_key in (
            "profile",
            "literature",
            "ideas",
            "runplan",
        ):
            self.assertIn(f'reportDocument("{report_key}"', demo_source)
        self.assertNotIn('reportDocument("results"', demo_source)
        self.assertNotIn('reportDocument("paper-studio"', demo_source)
        self.assertIn("experimentPlanDemo()", demo_source)
        self.assertIn("研究目标与参考依据", demo_source)
        self.assertIn("代表性图表 · 轨迹首次偏离", demo_source)
        self.assertIn("代表性结果表", demo_source)
        self.assertNotIn("F3A · Only the first-exit layer", demo_source)
        self.assertNotIn("F4 · Safety–utility sensitivity", demo_source)
        self.assertIn("provenance-number", demo_source)
        self.assertIn("provenance-tooltip", demo_source)
        self.assertIn('"全部 Goals 已确认"', demo_source)
        self.assertIn("一次确认全部 Goals", demo_source)
        self.assertIn("逐个查看并确认", demo_source)
        self.assertNotIn('data-action="select-idea"', demo_source)
        self.assertNotIn('data-action="approve-expplan"', demo_source)
        self.assertNotIn('data-action="run-view"', demo_source)
        self.assertNotIn('data-action="paper-view"', demo_source)
        self.assertNotIn("RESULTS_LEDGER.csv", demo_source)
        self.assertNotIn("data-provenance-trigger", demo_source)
        self.assertNotIn("scrollIntoView", demo_source)
        self.assertIn("Research Avatar", demo_source)
        self.assertNotIn("RESEARCH BUDDY", demo_source)
        self.assertIn("overflow-y:auto", demo_style)
        self.assertIn(".report-document>section", demo_style)
        self.assertNotIn(".profile-document>section", demo_style)
        self.assertNotIn(".profile-detail-grid", demo_style)

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
            (root / "researcher-profile" / "PROFILE.html").write_text(
                "<title>Researcher Profile — Ada Lovelace</title>\n", encoding="utf-8"
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
            ["runplan"],
        )
        self.assertEqual(state["stages"][4]["results_backend"]["key"], "results")


if __name__ == "__main__":
    unittest.main()
