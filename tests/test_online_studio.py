import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import research_avatar.online_studio.server as online
from research_avatar.online_studio.package import build_archive
import research_avatar.paper_studio.server as paper_studio


PROFILE_HTML = """<!doctype html><html><body>
<h1>Researcher profile</h1>
<h2>Writing Style</h2><p>Concise, evidence-first prose.</p>
<script>doNotIncludeThisSecret()</script>
</body></html>"""

PLAN_CONTRACT = {
    "schema_version": "1.1",
    "approval_status": "approved",
    "paper_title": "Evidence Writing",
    "target": {"venue": "ACL 2027", "submission_content_pages": 8},
    "references": {
        "researcher_owned_structure": {
            "title": "Reference Structure Paper",
            "authors": "A. Researcher",
            "venue": "ACL 2026",
            "publication_key": "reference2026",
            "local_full_text": "researcher-profile/fulltext/txt/reference.txt",
        }
    },
    "paper_outline": [
        {
            "id": "abstract",
            "title": "Abstract",
            "paragraphs": [
                {"id": "A1", "plan_sentence": "Summarize the supported paper.", "artifact_refs": []}
            ],
        },
        {
            "id": "experiments",
            "title": "Experiments",
            "paragraphs": [
                {"id": "E1", "plan_sentence": "Report the verified comparison.", "artifact_refs": ["T1"]}
            ],
        },
        {
            "id": "conclusion",
            "title": "Conclusion",
            "paragraphs": [
                {"id": "C1", "plan_sentence": "Close with supported findings.", "artifact_refs": []}
            ],
        },
    ],
    "paper_artifacts": [
        {
            "id": "T1", "kind": "table", "label": "tab:main", "span": "two-column",
            "placement": "body", "section_id": "experiments", "introduced_after": "E1",
            "shell": {"caption": "Verified main comparison.", "column_labels": ["Method", "Score"]},
        }
    ],
    "result_requirements": [
        {
            "id": "R1", "artifact_id": "T1", "cell_ids": ["t1-score"],
            "any_of": ["results/main.json:rows.*"],
        }
    ],
}


def pipeline_files(*, venue=None):
    contract = json.loads(json.dumps(PLAN_CONTRACT))
    if venue is not None:
        contract["target"]["venue"] = venue
    plan = (
        "<html><head><title>Experiment Plan</title></head><body><h1>Evidence Writing</h1>"
        '<script type="application/json" id="experiment-plan-contract">'
        + json.dumps(contract)
        + "</script></body></html>"
    )
    results = (
        '<html><body><section data-artifact-id="T1"><table>'
        '<tr><th>Method</th><th>Score</th></tr><tr><td>Ours</td>'
        '<td data-target-id="t1-score" data-result-id="R1">91.0</td>'
        "</tr></table></section></body></html>"
    )
    return [
        ("PROFILE.html", PROFILE_HTML),
        ("03_EXPERIMENT_PLAN.html", plan),
        ("05_EXP_RESULT.html", results),
    ]


def evidence_archive():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("results/main.json", json.dumps({"rows": [{"method": "Ours", "score": 91.0}]}))
        archive.writestr("researcher-profile/publications.json", "[]")
        archive.writestr("researcher-profile/fulltext/txt/reference.txt", "Reference paper structure and prose.")
    return buffer.getvalue()


def project_archive():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "results").mkdir()
        (root / "results/main.json").write_text(
            json.dumps({"rows": [{"method": "Ours", "score": 91.0}]})
        )
        (root / "researcher-profile/fulltext/txt").mkdir(parents=True)
        (root / "researcher-profile/PROFILE.html").write_text(PROFILE_HTML)
        (root / "researcher-profile/publications.json").write_text("[]")
        (root / "researcher-profile/fulltext/txt/ref.txt").write_text(
            "Abstract structure.\n\nExperiments report a verified comparison.\n\nConclusion closes the evidence loop."
        )
        (root / "reports").mkdir()
        sources = dict(pipeline_files())
        contract = {
            **PLAN_CONTRACT,
            "references": {
                "researcher_owned_structure": {
                    **PLAN_CONTRACT["references"]["researcher_owned_structure"],
                    "local_full_text": "researcher-profile/fulltext/txt/ref.txt"
                }
            },
        }
        sources["03_EXPERIMENT_PLAN.html"] = (
            '<html><body><script id="experiment-plan-contract" type="application/json">'
            + json.dumps(contract)
            + "</script></body></html>"
        )
        (root / "reports/01_LIT_SURVEY.html").write_text("<html><body>Survey</body></html>")
        (root / "reports/02_IDEA_REPORT.html").write_text("<html><body>Ideas</body></html>")
        (root / "reports/04_RUN_PLAN.html").write_text("<html><body>Run plan</body></html>")
        for name in ("03_EXPERIMENT_PLAN.html", "05_EXP_RESULT.html"):
            (root / "reports" / name).write_text(sources[name])
        output = root / "project.zip"
        build_archive(root, output)
        return output.read_bytes()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class OnlineStudioTests(unittest.TestCase):
    def tearDown(self):
        with online.SESSIONS_LOCK:
            sessions = list(online.SESSIONS.values())
            online.SESSIONS.clear()
        for session in sessions:
            if session.process.poll() is None:
                session.process.terminate()
                session.process.wait(timeout=5)

    def test_html_decoder_rejects_non_html_and_oversized_shape(self):
        payload = [{"name": "notes.txt", "data": base64.b64encode(b"x").decode()}]
        with self.assertRaisesRegex(online.OnlineStudioError, r"\.html"):
            online._decode_html_files(payload)

    def test_visible_text_excludes_scripts(self):
        text = online._source_text([("PROFILE.html", PROFILE_HTML)])
        self.assertIn("Concise, evidence-first prose.", text)
        self.assertNotIn("doNotIncludeThisSecret", text)

    def test_project_identity_comes_from_approved_plan(self):
        plan = pipeline_files()[1][1]
        self.assertEqual(
            online._project_identity(plan, PLAN_CONTRACT),
            ("Evidence Writing · ACL 2027", "Evidence Writing"),
        )

    def test_artifact_rows_recovers_a_leading_identifier_column_from_the_raw_header(self):
        # Regression: a real batch-writing run completed all 19 paragraphs
        # and compiled a full paper PDF, but Table 2 rendered with its own
        # scraped header row ("Method Swap Delete Insert Keyboard") printed
        # as if it were a data row, and the last declared column label
        # replaced by a meaningless "Value 5". 03's column_labels for this
        # table only names the four metric columns ("Swap", "Delete",
        # "Insert", "Keyboard") since every row already carries the method
        # name -- it never needs to declare that identifier column
        # separately. The old code always padded *missing* headers by
        # appending synthetic "Value N" placeholders at the end, silently
        # shifting every declared label one column out of alignment with
        # its data, and breaking the duplicate-header-row strip check
        # (which compared against the wrong, shifted header list).
        raw_rows = [
            ["Method", "Swap", "Delete", "Insert", "Keyboard"],
            ["Class-balanced random-budget augmentation", "0.8114", "0.8052", "0.7922", "0.7968"],
            ["Our method — Margin-Targeted Typo Augmentation (MTA)", "0.8327", "0.8275", "0.8017", "0.8107"],
        ]
        records, columns = online._artifact_rows(raw_rows, ["Swap", "Delete", "Insert", "Keyboard"])
        self.assertEqual(
            [column["label"] for column in columns],
            ["Method", "Swap", "Delete", "Insert", "Keyboard"],
        )
        self.assertEqual(len(records), 2, "the real header row must be stripped, not kept as data")
        self.assertEqual(records[0]["method"], "Class-balanced random-budget augmentation")
        self.assertEqual(records[0]["swap"], "0.8114")
        self.assertEqual(records[0]["keyboard"], "0.7968")

    def test_pipeline_sources_require_profile_plan_and_results(self):
        sources = online._canonical_pipeline_sources(pipeline_files())
        self.assertEqual(set(sources), {
            "PROFILE.html", "03_EXPERIMENT_PLAN.html", "05_EXP_RESULT.html",
        })
        with self.assertRaisesRegex(online.OnlineStudioError, "05_EXP_RESULT"):
            online._canonical_pipeline_sources(pipeline_files()[:2])

    def test_evidence_zip_rejects_path_traversal(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escape.json", "{}")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(online.OnlineStudioError, "不允许的路径"):
                online._extract_evidence_archive(buffer.getvalue(), Path(directory))

    def test_result_parser_survives_void_tags_inside_artifact(self):
        parser = online._ResultArtifactTables()
        parser.feed(
            '<section data-artifact-id="T1"><img src="preview.png">'
            '<table><tr><th>Method</th><th>Score</th></tr>'
            '<tr><td>Ours<br>final</td><td data-target-id="t1-score">91.0</td></tr>'
            '</table></section><section data-artifact-id="T2"></section>'
        )
        parser.close()
        self.assertEqual(parser.artifact_ids, ["T1", "T2"])
        self.assertEqual(parser.rows["T1"][1], ["Ours final", "91.0"])

    def test_required_artifact_never_receives_fabricated_placeholder_rows(self):
        contract = {**PLAN_CONTRACT, "_result_tables": {"T1": []}}
        sections = online._outline_sections(contract)
        with self.assertRaisesRegex(online.OnlineStudioError, "不会用占位值"):
            online._artifact_definitions(contract, sections)

    def test_contract_rejects_unapproved_or_incomplete_results(self):
        plan = pipeline_files()[1][1]
        pending = plan.replace('"approval_status": "approved"', '"approval_status": "pending"')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "results").mkdir()
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(pending)
            (root / "reports/05_EXP_RESULT.html").write_text(pipeline_files()[2][1])
            with self.assertRaisesRegex(online.OnlineStudioError, "尚未批准"):
                online._validated_upstream_contract(root, pending, pipeline_files()[2][1])
        incomplete = pipeline_files()[2][1].replace(' data-target-id="t1-score"', "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "results").mkdir()
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(plan)
            (root / "reports/05_EXP_RESULT.html").write_text(incomplete)
            with self.assertRaisesRegex(online.OnlineStudioError, "尚未填满"):
                online._validated_upstream_contract(root, plan, incomplete)

    def test_evidence_packager_emits_only_supported_project_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "results/main.json").write_text("{}")
            (root / "researcher-profile/fulltext/txt").mkdir(parents=True)
            (root / "researcher-profile/PROFILE.html").write_text(PROFILE_HTML)
            (root / "researcher-profile/publications.json").write_text("[]")
            (root / "researcher-profile/fulltext/txt/ref.txt").write_text("reference")
            (root / "reports").mkdir()
            contract = {
                **PLAN_CONTRACT,
                "references": {
                    "researcher_owned_structure": {
                        "local_full_text": "researcher-profile/fulltext/txt/ref.txt"
                    }
                },
            }
            for name in (
                "01_LIT_SURVEY.html", "02_IDEA_REPORT.html", "04_RUN_PLAN.html", "05_EXP_RESULT.html"
            ):
                (root / "reports" / name).write_text(f"<html><body>{name}</body></html>")
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(contract)
                + "</script>"
            )
            output = root / "bundle.zip"
            files = build_archive(root, output)
            self.assertEqual(
                files,
                [
                    "project-package.json",
                    "references/structure.txt",
                    "reports/01_LIT_SURVEY.html",
                    "reports/02_IDEA_REPORT.html",
                    "reports/03_EXPERIMENT_PLAN.html",
                    "reports/04_RUN_PLAN.html",
                    "reports/05_EXP_RESULT.html",
                    "researcher-profile/PROFILE.html",
                    "researcher-profile/fulltext/txt/ref.txt",
                    "researcher-profile/publications.json",
                    "results/main.json",
                ],
            )
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(sorted(archive.namelist()), files)
                self.assertIn("researcher-profile/fulltext/txt/ref.txt", files)
                manifest = json.loads(archive.read("project-package.json"))
                self.assertEqual(manifest["schema_version"], "2.0")

    def test_evidence_packager_includes_only_contract_selected_plotting_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "results/main.json").write_text("{}")
            (root / "results/stale.json").write_text("{}")
            (root / "paper/figsrc/example").mkdir(parents=True)
            (root / "paper/fig").mkdir(parents=True)
            for relative, content in {
                "paper/fig/make_figs.py": "--schema --figure --panel --metrics --pdf --png matplotlib.use(\"Agg\") validate_rendered_marks",
                "paper/figsrc/example/schema.json": "{}",
                "paper/figsrc/example/make_fixture.py": "print('fixture')",
                "paper/figsrc/example/fixture.json": "{}",
                "paper/figsrc/example/F2.pdf": "%PDF-test",
                "paper/figsrc/example/F2.png": "png",
            }.items():
                (root / relative).write_text(content)
            (root / "researcher-profile/fulltext/txt").mkdir(parents=True)
            (root / "researcher-profile/PROFILE.html").write_text(PROFILE_HTML)
            (root / "researcher-profile/publications.json").write_text("[]")
            (root / "researcher-profile/fulltext/txt/ref.txt").write_text("reference")
            (root / "reports").mkdir()
            plotting = {
                "source": "paper/fig/make_figs.py",
                "schema": "paper/figsrc/example/schema.json",
                "fixture_generator": "paper/figsrc/example/make_fixture.py",
                "fixture": "paper/figsrc/example/fixture.json",
                "pdf": "paper/figsrc/example/F2.pdf",
                "png": "paper/figsrc/example/F2.png",
                "panels": {},
            }
            contract = {
                **PLAN_CONTRACT,
                "references": {"researcher_owned_structure": {"local_full_text": "researcher-profile/fulltext/txt/ref.txt"}},
                "paper_artifacts": [
                    *PLAN_CONTRACT["paper_artifacts"],
                    {"id": "F2", "kind": "figure", "shell": {"plotting": plotting}},
                ],
            }
            for name in ("01_LIT_SURVEY.html", "02_IDEA_REPORT.html", "04_RUN_PLAN.html", "05_EXP_RESULT.html"):
                (root / "reports" / name).write_text(f"<html><body>{name}</body></html>")
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(contract)
                + "</script>"
            )
            output = root / "bundle.zip"
            files = build_archive(root, output)
            self.assertIn("paper/fig/make_figs.py", files)
            self.assertIn("paper/figsrc/example/schema.json", files)
            self.assertIn("results/main.json", files)
            self.assertNotIn("results/stale.json", files)

    def test_online_latex_blocks_file_and_execution_primitives(self):
        with patch.object(paper_studio, "ONLINE_PROJECT_MODE", True):
            issues = paper_studio.online_latex_security_issues(
                r"Safe prose. \input{/etc/passwd} \csname input\endcsname ^^69"
            )
        self.assertIn(r"\input", issues)
        self.assertIn(r"\csname", issues)
        self.assertIn("TeX ^^ character encoding", issues)
        with patch.object(paper_studio, "ONLINE_PROJECT_MODE", True):
            self.assertEqual(
                paper_studio.online_latex_security_issues(
                    r"Evidence supports 91\% accuracy; see \cite{verified2026}."
                ),
                [],
            )

    def test_custom_outline_is_validated_before_scaffolding(self):
        sections = online._validated_sections(
            [
                {"title": "Abstract", "purpose": "Summarize only supported evidence."},
                {"title": "Evaluation Protocol", "purpose": "Define datasets, metrics, and reproducible settings."},
            ]
        )
        self.assertEqual([item[0] for item in sections], ["abstract", "evaluation_protocol"])
        with self.assertRaisesRegex(online.OnlineStudioError, "第一个"):
            online._validated_sections(
                [
                    {"title": "Introduction", "purpose": "Explain the paper motivation carefully."},
                    {"title": "Method", "purpose": "Explain the complete technical method."},
                ]
            )

    def test_local_signup_login_session_and_logout(self):
        password = "abc123"
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            with self.assertRaisesRegex(online.OnlineStudioError, "6–1024"):
                online.create_local_user("short@example.org", "abc12")
            user = online.create_local_user("Researcher@Example.org", password)
            self.assertEqual(user["email"], "researcher@example.org")
            logged_in = online.authenticate_local_user(
                "researcher@example.org", password
            )
            self.assertEqual(logged_in["id"], user["id"])
            with self.assertRaisesRegex(online.OnlineStudioError, "不正确"):
                online.authenticate_local_user(
                    "researcher@example.org", "wrong-password-value"
                )
            token = online.create_auth_session(user["id"])
            header = f"{online.AUTH_COOKIE_NAME}={token}"
            self.assertEqual(online.authenticated_user(header)["id"], user["id"])
            online.revoke_auth_session(header)
            self.assertIsNone(online.authenticated_user(header))
            self.assertNotIn(
                password.encode(),
                (Path(directory) / "auth.sqlite3").read_bytes(),
            )

    def test_logout_closes_the_researchers_own_writing_session(self):
        # Regression: a session's spawned paper_studio.server child process
        # previously only ever stopped via the four-hour idle reaper, so a
        # researcher who logged out immediately still left a live subprocess
        # running in the shared per-Worker-version container for hours,
        # starving concurrent researchers' memory. close_session() is what
        # the edge Worker's logout handler now calls before deleting the
        # auth row (POST /api/online/session/close, proxyIdentified in
        # deploy/cloudflare/index.ts).
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        )
        try:
            session = online.Session(
                "close-me", "user-1", Path("/tmp/unused"), "openai", "gpt-5-nano",
                process, 0,
            )
            with online.SESSIONS_LOCK:
                online.SESSIONS["close-me"] = session
            header = f"{online.COOKIE_NAME}=close-me"

            # A foreign user_id must not be able to close someone else's session.
            self.assertFalse(online.close_session(header, user_id="not-the-owner"))
            self.assertIsNone(process.poll())
            with online.SESSIONS_LOCK:
                self.assertIn("close-me", online.SESSIONS)

            self.assertTrue(online.close_session(header, user_id="user-1"))
            process.wait(timeout=5)
            self.assertIsNotNone(process.poll())
            with online.SESSIONS_LOCK:
                self.assertNotIn("close-me", online.SESSIONS)

            # Idempotent: closing an already-closed/unknown session is a no-op.
            self.assertFalse(online.close_session(header, user_id="user-1"))
        finally:
            with online.SESSIONS_LOCK:
                online.SESSIONS.pop("close-me", None)
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def test_google_authorization_code_callback_creates_authenticated_user(self):
        opener = urllib.request.build_opener(_NoRedirect())
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            server = online.OnlineServer(("127.0.0.1", 0), online.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            environment = {
                "GOOGLE_OAUTH_CLIENT_ID": "test-client.apps.googleusercontent.com",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
                "ONLINE_STUDIO_PUBLIC_URL": base,
            }
            try:
                with patch.dict(os.environ, environment, clear=False):
                    with self.assertRaises(urllib.error.HTTPError) as start_error:
                        opener.open(base + "/auth/google/start")
                    self.assertEqual(start_error.exception.code, 302)
                    location = start_error.exception.headers["Location"]
                    query = urllib.parse.parse_qs(
                        urllib.parse.urlparse(location).query
                    )
                    state = query["state"][0]
                    nonce = query["nonce"][0]
                    state_cookie = start_error.exception.headers["Set-Cookie"].split(
                        ";", 1
                    )[0]
                    callback = (
                        base
                        + "/auth/google/callback?"
                        + urllib.parse.urlencode({"state": state, "code": "test-code"})
                    )
                    request = urllib.request.Request(
                        callback, headers={"Cookie": state_cookie}
                    )
                    with patch.object(
                        online, "exchange_google_code", return_value="signed-id-token"
                    ), patch.object(
                        online,
                        "verify_google_id_token",
                        return_value={
                            "sub": "google-subject-123",
                            "email": "google-user@example.org",
                            "email_verified": True,
                            "nonce": nonce,
                        },
                    ):
                        with self.assertRaises(urllib.error.HTTPError) as callback_error:
                            opener.open(request)
                    self.assertEqual(callback_error.exception.code, 302)
                    cookies = callback_error.exception.headers.get_all("Set-Cookie")
                    auth_cookie = next(
                        value.split(";", 1)[0]
                        for value in cookies
                        if value.startswith(online.AUTH_COOKIE_NAME + "=")
                    )
                    user = online.authenticated_user(auth_cookie)
                    self.assertEqual(user["email"], "google-user@example.org")
                    self.assertEqual(user["provider"], "google")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_scaffold_is_a_valid_paper_studio_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(
                    root, files=pipeline_files(), archive=evidence_archive()
                )
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(r"\title{Evidence Writing}", (root / "paper/main.tex").read_text())
            self.assertIn(
                r"\input{sections/bibliography}", (root / "paper/main.tex").read_text()
            )
            self.assertTrue((root / "paper/.outline-approved").is_file())
            plan = json.loads((root / "paper/paragraph_plan.json").read_text())
            self.assertEqual(set(plan["sections"]), {"abstract", "experiments", "conclusion"})
            config = json.loads((root / "paper/paper_studio.json").read_text())
            self.assertEqual(config["table_order"], ["T1"])
            self.assertEqual(config["tables"]["T1"]["label"], "tab:main")
            # Regression: a real full-draft batch run completed all 19
            # paragraphs, then failed at the final table-materialization step
            # with "表格 Prompt 含未知行：保持 05 的已验证顺序" -- the
            # scaffolder hardcoded that phrase as the row directive, but
            # paper_studio's row-directive parser (default_table_prompt /
            # its "keep everything" branch) only recognizes the literal
            # keywords "source"/"all"/"保持 results/ 顺序"/"全部", so it
            # misread the phrase as a literal (unknown) row name and failed
            # every online project's final materialization step.
            self.assertEqual(config["tables"]["T1"]["prompt"]["rows"], "source")
            # Regression: the same materialization step then failed a second
            # time with "最优值仅支持 none、max 或 min。" -- the scaffolder
            # also hardcoded a "best_values" phrase
            # ("仅按 03 指定的 metric direction 标记") that the same parser's
            # best-value directive never recognizes, and no per-column
            # metric direction is actually read from "03" to derive a real
            # one, so it must default to the verified-safe "none".
            self.assertEqual(config["tables"]["T1"]["prompt"]["best_values"], "none")
            self.assertEqual(config["project"]["target"]["venue"], "ACL 2027")
            self.assertEqual(
                config["project"]["reference_paper"]["title"],
                "Reference Structure Paper",
            )
            self.assertEqual(
                config["project"]["decision_source"],
                "reports/03_EXPERIMENT_PLAN.html",
            )

    def test_lightweight_scaffold_is_a_valid_paper_studio_project(self):
        # Regression coverage for the no-GitHub-repo onboarding path: a
        # researcher who never ran package.py, has no approved 03/05
        # contract, no RESULTS_LEDGER -- just a Scholar profile page, some
        # reference papers, and a results table. This must still produce a
        # project research_avatar.paper_studio.server accepts as valid,
        # same bar as the full pipeline's scaffold.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scholar_html = [
                (
                    "scholar.html",
                    "<html><body><h1>Jane Researcher</h1>"
                    "<div>Prior work on margin-targeted augmentation.</div>"
                    "</body></html>",
                )
            ]
            reference_html = [
                (
                    "reference1.html",
                    "<html><body><p>Typo robustness in intent classification "
                    "has been studied extensively.</p></body></html>",
                )
            ]
            results = {
                "caption": "Primary accuracy comparison.",
                "columns": [
                    {"key": "method", "label": "Method"},
                    {"key": "accuracy", "label": "Accuracy"},
                ],
                "rows": [
                    {"method": "Baseline", "accuracy": "81.2"},
                    {"method": "Ours", "accuracy": "84.5"},
                ],
            }
            online._write_lightweight_workspace(
                root,
                venue="ACL 2027",
                project_name="Margin Targeted Augmentation",
                title="Margin-Targeted Augmentation for Robust Intent Classification",
                scholar_files=scholar_html,
                reference_files=reference_html,
                results=results,
            )
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            main_tex = (root / "paper/main.tex").read_text()
            self.assertIn(
                r"\title{Margin-Targeted Augmentation for Robust Intent Classification}",
                main_tex,
            )
            self.assertIn(r"\input{sections/bibliography}", main_tex)
            plan = json.loads((root / "paper/paragraph_plan.json").read_text())
            self.assertEqual(
                set(plan["sections"]),
                {
                    "abstract", "introduction", "related_work", "method",
                    "experiments", "discussion", "conclusion",
                },
            )
            self.assertEqual(plan["sections"]["experiments"][0]["artifacts"], ["T1", "F1"])
            config = json.loads((root / "paper/paper_studio.json").read_text())
            self.assertEqual(config["table_order"], ["T1"])
            self.assertEqual(config["figure_order"], ["F1"])
            self.assertEqual(config["figures"]["F1"]["kind"], "data")
            self.assertEqual(config["figures"]["F1"]["panels"][0]["id"], "a")
            metrics = json.loads((root / "paper/metrics.json").read_text())
            self.assertEqual(
                metrics["lightweight_results"]["rows"],
                [
                    {"method": "Baseline", "accuracy": "81.2"},
                    {"method": "Ours", "accuracy": "84.5"},
                ],
            )
            reference_text = (root / "paper/uploaded_sources.txt").read_text()
            self.assertIn("Jane Researcher", reference_text)
            self.assertIn("Typo robustness", reference_text)

    def test_lightweight_scaffold_without_results_has_no_figures_or_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            online._write_lightweight_workspace(
                root,
                venue="ACL 2027",
                project_name="Text Only Project",
                title="A Text Only Paper",
                scholar_files=[],
                reference_files=[("ref.html", "<html><body>Some reference text.</body></html>")],
                results=None,
            )
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable, "-m", "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            config = json.loads((root / "paper/paper_studio.json").read_text())
            self.assertEqual(config["figures"], {})
            self.assertEqual(config["tables"], {})
            self.assertEqual(config["figure_order"], [])
            self.assertEqual(config["table_order"], [])
            plan = json.loads((root / "paper/paragraph_plan.json").read_text())
            self.assertEqual(plan["sections"]["experiments"][0]["artifacts"], [])

    def test_lightweight_scaffold_rejects_an_unrecognized_venue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(online.OnlineStudioError):
                online._write_lightweight_workspace(
                    root,
                    venue="Some Made Up Workshop",
                    project_name="X",
                    title="X",
                    scholar_files=[],
                    reference_files=[],
                    results=None,
                )

    def test_scaffold_uses_the_target_venues_real_official_latex_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(
                    root, files=pipeline_files(venue="EMNLP 2026 Findings"),
                    archive=evidence_archive(),
                )
            main_tex = (root / "paper/main.tex").read_text()
            # The real ACL-family class, not a hand-rolled generic article.
            self.assertIn(r"\usepackage[review]{acl}", main_tex)
            self.assertNotIn(r"\usepackage[margin=1in]{geometry}", main_tex)
            # acl.sty emits its own \bibliographystyle; a manual one breaks bibtex.
            self.assertNotIn(r"\bibliographystyle", main_tex)
            self.assertTrue((root / "paper/acl.sty").is_file())
            self.assertTrue((root / "paper/acl_natbib.bst").is_file())
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_venue_template_preamble_actually_compiles_generated_math_prose(self):
        # Regression: the acl template preamble originally omitted amsmath/amssymb,
        # so ordinary generated math like \text{...} inside \( \) failed pdflatex
        # with "Undefined control sequence" mid-batch-draft, well after the
        # scaffold itself looked correct. Verify with real pdflatex, not just a
        # package-name substring check, since substring checks would not have
        # caught this class of bug.
        pdflatex = shutil.which("pdflatex")
        if not pdflatex:
            self.skipTest("pdflatex not available in this environment")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(
                    root, files=pipeline_files(venue="COLING 2027 Short Paper"),
                    archive=evidence_archive(),
                )
            paper = root / "paper"
            (paper / "sections/experiments.tex").write_text(
                r"\section{Experiments}" "\n"
                r"Consider candidate perturbations, with "
                r"\(C_{\text{clean}} = \{c \in C \mid \text{valid}(c)\}\)."
                "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                cwd=paper,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((paper / "main.pdf").is_file())

    def test_scaffold_rejects_a_venue_with_no_bundled_official_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                with self.assertRaisesRegex(online.OnlineStudioError, "官方 LaTeX 模板"):
                    online._write_workspace(
                        root,
                        files=pipeline_files(venue="Some Unlisted Workshop 2099"),
                        archive=evidence_archive(),
                    )
            # Fail closed: no partially-scaffolded generic-template paper/ survives.
            self.assertFalse((root / "paper/main.tex").is_file())

    def test_scaffold_accepts_one_complete_project_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(root, files=[], archive=project_archive())
            self.assertTrue((root / "paper/paper_studio.json").is_file())
            plan = json.loads((root / "paper/paragraph_plan.json").read_text())
            for paragraphs in plan["sections"].values():
                for paragraph in paragraphs:
                    self.assertEqual(paragraph["reference_lines"][0], paragraph["reference_lines"][1])
            reference = (root / "paper/uploaded_sources.txt").read_text()
            self.assertNotIn("Concise, evidence-first prose", reference)

    def test_online_shell_has_no_demo_interaction_or_key_prompt(self):
        # Regression: the Demo tab used to let a visitor click an
        # interactive control, fail, and get redirected into a "type your
        # OpenAI key to get an editable copy" dialog. The demo is view-only
        # now -- there is no key prompt to defer, and no route left that
        # would create a private writable copy of it.
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("demo-key-dialog", html)
        self.assertNotIn("demo-key-dialog", script)
        self.assertNotIn("paper-studio-demo-api-key-required", script)
        self.assertNotIn("/api/online/demo-session", script)
        self.assertFalse(hasattr(online, "create_demo_copy_session"))

    def test_page_refresh_returns_to_the_researchers_own_active_session(self):
        # A refresh (or reopening the bare site URL) always re-runs the
        # landing page's own auth bootstrap first, even for a researcher
        # mid-way through a real "Use it" writing session — that landing
        # page has no memory of which tab was last selected. Without
        # checking for an active per-user session before rendering, it
        # always reset to the Demo tab and buried the resume link one click
        # away inside the Use it tab instead of returning the researcher
        # straight to /studio. A researcher with no active session (just
        # browsing the read-only Demo, which never creates a per-user
        # session) correctly keeps landing on the Demo tab by default.
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        session_check = script.index("fetch('/api/online/session'")
        redirect = script.index("window.location.assign('/studio')")
        demo_panel_select = script.rindex("selectProductPanel('demo-panel')")
        self.assertLess(
            session_check, redirect,
            "must check for an active session before deciding to redirect",
        )
        self.assertLess(
            redirect, demo_panel_select,
            "the active-session redirect must be checked before falling "
            "back to rendering the Demo tab",
        )
        self.assertIn("if (state.active)", script)

    def test_studio_navigation_redirects_to_html_with_actionable_notice(self):
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        worker = (
            Path(__file__).resolve().parents[1] / "deploy/cloudflare/index.ts"
        ).read_text(encoding="utf-8")
        self.assertIn('id="session-notice"', html)
        self.assertIn("session_expired", script)
        self.assertIn("login_required", script)
        self.assertIn("上一次临时写作会话已结束", script)
        self.assertIn('new URL("/?login_required=1", request.url)', worker)
        self.assertIn('path === "/studio"', worker)
        self.assertIn('"/?session_expired=1"', Path(online.__file__).read_text(encoding="utf-8"))

    def test_cloudflare_release_uses_version_scoped_container(self):
        """A deploy must not keep serving the prior image's demo snapshot."""
        root = Path(__file__).resolve().parents[1]
        worker = (root / "deploy/cloudflare/index.ts").read_text(encoding="utf-8")
        wrangler = (root / "deploy/cloudflare/wrangler.example.jsonc").read_text(
            encoding="utf-8"
        )
        self.assertIn("env.CF_VERSION_METADATA.id", worker)
        self.assertIn('"version_metadata"', wrangler)
        self.assertIn('"binding": "CF_VERSION_METADATA"', wrangler)
        self.assertIn('"class_name": "OnlineStudioContainerV30"', wrangler)
        self.assertIn("export class OnlineStudioContainerV30", worker)
        self.assertNotIn('getContainer(env.ONLINE_STUDIO, "public-studio-', worker)

    def test_container_image_installs_every_tool_compile_table_preview_requires(self):
        # Regression: a real batch-writing run finished all 19 paragraphs,
        # then failed at the final table-materialization step with "无法生成
        # LaTeX 表格预览：缺少 pdfcrop。" -- the base container image
        # installed poppler-utils (pdftoppm/pdfinfo/pdftocairo) and latexmk,
        # but never texlive-extra-utils, which is what actually provides the
        # pdfcrop binary compile_table_preview() shells out to. The
        # application code already checked for and reported the missing
        # tool correctly; the tool itself just wasn't installed.
        #
        # Fixing that surfaced a second, one-level-deeper failure: "LaTeX 表格
        # 预览编译失败" / "Ghostscript exited with error code 127" --
        # pdfcrop itself shells out to `gs` to compute the bounding box, and
        # `--no-install-recommends` (set just above this loop's apt-get
        # command) suppresses ghostscript, which texlive-extra-utils only
        # Recommends rather than Depends on. Both must be installed
        # explicitly.
        dockerfile = (
            Path(__file__).resolve().parents[1] / "deploy/online-paper-studio/Dockerfile"
        ).read_text(encoding="utf-8")
        for package in ("ghostscript", "texlive-extra-utils", "poppler-utils", "latexmk", "nodejs"):
            self.assertIn(package, dockerfile)

    def test_upload_page_names_the_default_package_output(self):
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("outputs/paper-studio-evidence.zip", html)
        self.assertIn("点击上方选择框上传这个文件", html)

    def test_project_export_is_a_zip_and_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "paper").mkdir()
            (root / "paper/main.tex").write_text("paper", encoding="utf-8")
            outside = root.parent / (root.name + "-outside-secret.txt")
            outside.write_text("must-not-export", encoding="utf-8")
            link = root / "paper/outside.txt"
            try:
                link.symlink_to(outside)
                data = online._project_zip_bytes(root)
            finally:
                outside.unlink(missing_ok=True)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertEqual(archive.namelist(), ["paper/main.tex"])
                self.assertEqual(archive.read("paper/main.tex"), b"paper")

    def test_project_export_excludes_build_and_cache_artifacts(self):
        # Regression: a real production export downloaded by a researcher
        # (via /api/online/export) contained a compiled
        # ".agents/skills/paperstudio/scripts/__pycache__/*.pyc" file --
        # _project_zip_bytes walked the whole session root with no
        # exclusions, so any build/cache byproduct left in the workspace
        # (from running local-Agent tooling inside the session) leaked
        # straight into the user-facing ZIP.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "paper").mkdir()
            (root / "paper/main.tex").write_text("paper", encoding="utf-8")
            (root / "scripts/__pycache__").mkdir(parents=True)
            (root / "scripts/__pycache__/tool.cpython-312.pyc").write_bytes(b"\x00")
            (root / "scripts/tool.pyc").write_bytes(b"\x00")
            (root / ".git").mkdir()
            (root / ".git/HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
            (root / ".DS_Store").write_bytes(b"\x00")
            data = online._project_zip_bytes(root)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertEqual(archive.namelist(), ["paper/main.tex"])

    def test_live_worker_hides_root_and_never_persists_api_key(self):
        key = "sk-online-test-never-write-this"
        encoded_files = [
            {"name": name, "data": base64.b64encode(source.encode()).decode()}
            for name, source in pipeline_files()
        ]
        encoded_archive = base64.b64encode(evidence_archive()).decode()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(online, "DATA_ROOT", Path(directory)),
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": key}),
        ):
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                session = online.create_session(
                    {
                        "files": encoded_files,
                        "evidence_archive": {"name": "evidence.zip", "data": encoded_archive},
                    },
                    user_id="test-user",
                )
            with urllib.request.urlopen(
                f"http://127.0.0.1:{session.port}/api/state", timeout=5
            ) as response:
                state = json.loads(response.read())
            self.assertEqual(state["project"]["root"], "")
            self.assertEqual(state["api_key_setup"]["setup_command"], "")
            self.assertTrue(state["api_key_configured"])
            session_cookie = f"{online.COOKIE_NAME}={session.session_id}"
            self.assertIs(
                online._session_from_cookie(session_cookie, user_id="test-user"),
                session,
            )
            self.assertIsNone(
                online._session_from_cookie(session_cookie, user_id="other-user")
            )
            for path in session.root.rglob("*"):
                if path.is_file():
                    self.assertNotIn(key.encode(), path.read_bytes(), path)

    def test_create_session_fails_clearly_when_shared_key_is_unconfigured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            with self.assertRaises(online.OnlineStudioError):
                online.shared_deepseek_api_key()

    def test_user_cumulative_cost_sums_every_session_ledger_for_that_user(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            user_root = online.user_project_root("cap-user")
            for session_name, cost in (("session-a", 3.5), ("session-b", 4.0)):
                ledger = user_root / session_name / "paper/.paper_studio/api_usage.jsonl"
                ledger.parent.mkdir(parents=True)
                ledger.write_text(
                    json.dumps({"estimated_cost_usd": cost}) + "\n", encoding="utf-8"
                )
            self.assertAlmostEqual(
                online.user_cumulative_cost_usd("cap-user"), 7.5
            )
            self.assertAlmostEqual(online.user_cumulative_cost_usd("other-user"), 0.0)

    def test_spend_cap_blocks_new_sessions_once_a_user_is_over_the_rmb_limit(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            # USER_SPEND_CAP_RMB=200 / USD_TO_RMB_RATE=7.2 -> ~27.8 USD trips it.
            ledger = (
                online.user_project_root("over-cap-user")
                / "session-a/paper/.paper_studio/api_usage.jsonl"
            )
            ledger.parent.mkdir(parents=True)
            ledger.write_text(
                json.dumps({"estimated_cost_usd": 30.0}) + "\n", encoding="utf-8"
            )
            with self.assertRaises(online.OnlineStudioError):
                online.require_under_spend_cap("over-cap-user")
            online.require_under_spend_cap("fresh-user")

    def test_proxy_blocks_writes_once_a_user_session_is_over_the_spend_cap(self):
        handler = object.__new__(online.Handler)
        handler.command = "POST"
        recorded = {}

        def fake_json(payload, status=200, cookie=None):
            recorded["payload"] = payload
            recorded["status"] = status

        handler._json = fake_json
        session = online.Session(
            "session-id", "over-cap-user", Path("/tmp/does-not-matter"),
            "deepseek", "deepseek-v4-flash", MagicMock(), 0, kind="user",
        )
        with patch.object(online, "user_cumulative_cost_usd", return_value=1000.0):
            handler._proxy(session, "/api/generate")
        self.assertFalse(recorded["payload"]["ok"])
        self.assertEqual(recorded["status"], 402)

    def test_setup_page_only_asks_for_generated_html_and_openai_key(self):
        source = (online.STATIC / "index.html").read_text(encoding="utf-8")
        app = (online.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="demo-tab"', source)
        self.assertIn('id="use-tab"', source)
        self.assertIn('src="/demo/"', source)
        self.assertNotIn("先看看一篇论文是怎样完成的。", source)
        self.assertNotIn("这是完整 Research Avatar 流程的可交互示例。", source)
        self.assertNotIn("上传完整项目，开始自己的论文。", source)
        self.assertNotIn("上传由 Research Avatar 生成的必要研究证据。", source)
        style = (online.STATIC / "style.css").read_text(encoding="utf-8")
        self.assertIn("width: min(1500px, calc(100% - 32px))", style)
        self.assertIn(".use-columns { max-width: 1500px; align-items: start; }", style)
        self.assertIn("body.workspace-authenticated{height:100dvh", style)
        self.assertIn("#use-panel{overflow-y:auto", style)
        self.assertIn("#demo-panel{overflow:hidden", style)
        self.assertIn("selectProductPanel('demo-panel')", app)
        self.assertIn("document.body.classList.add('workspace-authenticated')", app)
        self.assertIn('name="project_package"', source)
        self.assertNotIn('name="profile_file"', source)
        self.assertNotIn('name="plan_file"', source)
        self.assertNotIn('name="result_file"', source)
        self.assertNotIn('name="api_key"', source)
        self.assertNotIn('name="project_name"', source)
        self.assertNotIn('name="outline"', source)
        self.assertNotIn('name="model"', source)
        # Every online session shares one server-held DeepSeek key now; the
        # landing page never asks a researcher for their own key or lets
        # them pick a provider.
        self.assertNotIn("api_key", app)
        self.assertNotIn("provider:", app)
        self.assertIn('id="lightweight-form"', source)
        self.assertIn('name="scholar_file"', source)
        self.assertIn('name="reference_files"', source)
        self.assertIn('name="results_file"', source)

    def test_demo_uses_sticky_six_stage_header_and_one_vertical_scroll(self):
        root = Path(__file__).resolve().parents[1]
        style = (root / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        html = (root / "research_avatar/web/demo/index.html").read_text(encoding="utf-8")
        self.assertIn(".journey-nav{position:sticky;top:0", style)
        self.assertIn(".stage-content{min-height:calc(100dvh - 153px);max-height:none;overflow:visible", style)
        self.assertIn("style.css?v=20260817-single-scroll", html)


if __name__ == "__main__":
    unittest.main()
