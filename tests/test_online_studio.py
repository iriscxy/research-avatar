import base64
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
from pathlib import Path
from unittest.mock import patch

import research_avatar.online_studio.server as online
import research_avatar.paper_studio.server as paper_studio


PROFILE_HTML = """<!doctype html><html><body>
<h1>Researcher profile</h1>
<h2>Writing Style</h2><p>Concise, evidence-first prose.</p>
<script>doNotIncludeThisSecret()</script>
</body></html>"""


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
            online._write_workspace(
                root,
                project_name="Online Test",
                title="Evidence & Writing",
                files=[
                    ("PROFILE.html", PROFILE_HTML),
                    ("results.html", "<h1>Results</h1><p>Accuracy: 91%.</p>"),
                ],
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
            self.assertIn(r"\title{Evidence \& Writing}", (root / "paper/main.tex").read_text())
            self.assertIn(
                r"\input{sections/bibliography}", (root / "paper/main.tex").read_text()
            )
            self.assertTrue((root / "paper/.outline-approved").is_file())
            plan = json.loads((root / "paper/paragraph_plan.json").read_text())
            self.assertEqual(set(plan["sections"]), {item[0] for item in online.DEFAULT_SECTIONS})

    def test_live_worker_hides_root_and_never_persists_api_key(self):
        key = "sk-online-test-never-write-this"
        encoded_profile = base64.b64encode(PROFILE_HTML.encode()).decode()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            session = online.create_session(
                {
                    "provider": "openai",
                    "model": "gpt-5-nano",
                    "api_key": key,
                    "project_name": "Online Test",
                    "title": "Private Online Draft",
                    "outline_confirmed": True,
                    "files": [{"name": "PROFILE.html", "data": encoded_profile}],
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


if __name__ == "__main__":
    unittest.main()
