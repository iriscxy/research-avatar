import base64
import io
import json
import os
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


def pipeline_files():
    plan = (
        "<html><head><title>Experiment Plan</title></head><body><h1>Evidence Writing</h1>"
        '<script type="application/json" id="experiment-plan-contract">'
        + json.dumps(PLAN_CONTRACT)
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
            self.assertEqual(config["project"]["target"]["venue"], "ACL 2027")
            self.assertEqual(
                config["project"]["reference_paper"]["title"],
                "Reference Structure Paper",
            )
            self.assertEqual(
                config["project"]["decision_source"],
                "reports/03_EXPERIMENT_PLAN.html",
            )

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

    def test_demo_interaction_creates_private_writable_copy_after_key_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            demo = base / "demo-project"
            (demo / "paper").mkdir(parents=True)
            (demo / "paper/paper_studio.json").write_text(
                json.dumps({"project": {"id": "demo-paper"}}), encoding="utf-8"
            )
            process = MagicMock()
            process.poll.return_value = None
            with (
                patch.object(online, "DATA_ROOT", base / "runtime"),
                patch.object(online, "DEMO_PROJECT", demo),
                patch.object(
                    online,
                    "_start_worker",
                    return_value=(process, 39001),
                ) as start,
                patch.dict(online.SESSIONS, {}, clear=True),
            ):
                session = online.create_demo_copy_session(
                    {"api_key": "sk-test-demo-copy"}, user_id="demo-user"
                )
                self.assertEqual(session.kind, "demo-copy")
                self.assertTrue((session.root / "paper/paper_studio.json").is_file())
                start.assert_called_once_with(
                    session.root,
                    "openai",
                    "gpt-5-nano",
                    "sk-test-demo-copy",
                    demo_mode=False,
                )

    def test_online_shell_defers_demo_key_prompt_until_interaction(self):
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="demo-key-dialog"', html)
        self.assertIn("paper-studio-demo-api-key-required", script)
        self.assertIn("/api/online/demo-session", script)
        self.assertIn("demoFrame.src = '/demo/?authenticated='", script)
        self.assertIn("demo_key_required", script)
        self.assertIn("openRequestedDemoKeyDialog();", script)

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
        wrangler = (root / "wrangler.example.jsonc").read_text(encoding="utf-8")
        self.assertIn("env.CF_VERSION_METADATA.id", worker)
        self.assertIn('"version_metadata"', wrangler)
        self.assertIn('"binding": "CF_VERSION_METADATA"', wrangler)
        self.assertIn('"class_name": "OnlineStudioContainerV7"', wrangler)
        self.assertIn("export class OnlineStudioContainerV7", worker)
        self.assertNotIn('getContainer(env.ONLINE_STUDIO, "public-studio-', worker)

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

    def test_live_worker_hides_root_and_never_persists_api_key(self):
        key = "sk-online-test-never-write-this"
        encoded_files = [
            {"name": name, "data": base64.b64encode(source.encode()).decode()}
            for name, source in pipeline_files()
        ]
        encoded_archive = base64.b64encode(evidence_archive()).decode()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                session = online.create_session(
                    {
                        "api_key": key,
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
        self.assertIn("#setup-form { max-width: 1180px; }", style)
        self.assertIn("body.workspace-authenticated{height:100dvh", style)
        self.assertIn("#use-panel{overflow-y:auto", style)
        self.assertIn("#demo-panel{overflow:hidden", style)
        self.assertIn("selectProductPanel('demo-panel')", app)
        self.assertIn("document.body.classList.add('workspace-authenticated')", app)
        self.assertIn('name="project_package"', source)
        self.assertNotIn('name="profile_file"', source)
        self.assertNotIn('name="plan_file"', source)
        self.assertNotIn('name="result_file"', source)
        self.assertIn('name="api_key"', source)
        self.assertNotIn('name="project_name"', source)
        self.assertNotIn('name="outline"', source)
        self.assertNotIn('name="model"', source)

    def test_demo_uses_sticky_six_stage_header_and_one_vertical_scroll(self):
        root = Path(__file__).resolve().parents[1]
        style = (root / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        html = (root / "research_avatar/web/demo/index.html").read_text(encoding="utf-8")
        self.assertIn(".journey-nav{position:sticky;top:0", style)
        self.assertIn(".stage-content{min-height:calc(100dvh - 153px);max-height:none;overflow:visible", style)
        self.assertIn("style.css?v=20260817-single-scroll", html)


if __name__ == "__main__":
    unittest.main()
