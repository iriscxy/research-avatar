"""Regression coverage for the September 2026 whole-repository review."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from research_avatar.online_studio import server as online
from research_avatar.paper_studio import server as studio
from research_avatar.paper_studio import account_usage as billing
from research_avatar.paper_studio.api_usage import append_usage


class ReviewRegressions(unittest.TestCase):
    def test_online_table_rejects_file_reads_before_starting_any_tool(self):
        source = r'\begin{table}\caption{QA}\label{tab:qa}\input{/tmp/qa-marker}\end{table}'
        with patch.object(studio, 'ONLINE_PROJECT_MODE', True), patch.object(studio, 'TABLES', {'TQA': {'label': 'tab:qa'}}), patch.object(studio, 'run_checked') as run:
            with self.assertRaisesRegex(studio.StudioError, 'Unsafe online table'):
                studio.validate_table_latex_source('TQA', source)
            with self.assertRaisesRegex(studio.StudioError, 'Unsafe online table'):
                studio.compile_table_preview('TQA', source)
            run.assert_not_called()

    def test_online_placeholder_table_cannot_be_saved_via_direct_api(self):
        handler = object.__new__(studio.Handler)
        with patch.object(studio, 'ONLINE_PROJECT_MODE', True), patch.object(studio, 'TABLES', {'TQA': {'online_placeholder': True}}), patch.object(studio, 'compile_table_preview') as compile_preview:
            with self.assertRaises(studio.StudioError):
                handler.handle_table_save({'table_id': 'TQA', 'latex': 'untrusted'})
            compile_preview.assert_not_called()

    def test_tex_environment_removes_secrets_and_search_path_overrides(self):
        with patch.object(studio, 'ONLINE_PROJECT_MODE', True), patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'fake', 'FUTURE_SERVICE_TOKEN': 'fake', 'TEXINPUTS': '/outside', 'shell_escape': '1'}):
            env = studio.latex_compile_environment()
        self.assertNotIn('DEEPSEEK_API_KEY', env)
        self.assertNotIn('FUTURE_SERVICE_TOKEN', env)
        self.assertNotIn('TEXINPUTS', env)
        self.assertEqual((env['openin_any'], env['openout_any'], env['shell_escape']), ('p', 'p', '0'))

    def test_slow_title_cannot_erase_new_batch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(studio, 'STATE_DIR', Path(tmp)), patch.object(studio, 'STATE_FILE', Path(tmp) / 'state.json'):
            studio.save_state(studio._default_state())
            def model(**_kwargs):
                latest = studio.load_state()
                latest['full_draft_job'] = {'token': 'new-batch', 'status': 'running', 'server_instance': studio.SERVER_INSTANCE_TOKEN, 'total': 1, 'completed': 0}
                studio.save_state(latest)
                return 'qa-response', 'QA title'
            handler = object.__new__(studio.Handler)
            handler.send_json = MagicMock()
            with patch.object(studio, 'call_openai_for_title', side_effect=model):
                with self.assertRaisesRegex(studio.StudioError, 'title candidate was discarded'):
                    handler.handle_title_generate({'prompt': 'QA title', 'current_title': 'Original'})
            self.assertEqual(studio.load_state()['full_draft_job']['token'], 'new-batch')

    def test_quota_survives_reset_and_repeated_legacy_import(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(online, 'DATA_ROOT', Path(tmp)), patch.dict(online.SESSIONS, {}, clear=True), patch.dict(os.environ, {'ONLINE_STUDIO_USAGE_URL': ''}):
            uid, token = 'qa-owner', 'qa-session'
            root = online.user_project_root(uid) / hashlib.sha256(token.encode()).hexdigest()
            ledger = root / 'paper/.paper_studio/api_usage.jsonl'
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({'estimated_cost_usd': 30.0}) + '\n')
            self.assertEqual(online.user_cumulative_cost_usd(uid), 30)
            self.assertEqual(online.user_cumulative_cost_usd(uid), 30)
            online.reset_session(f'{online.COOKIE_NAME}={token}', user_id=uid)
            self.assertFalse(root.exists())
            self.assertEqual(online.user_cumulative_cost_usd(uid), 30)
            with self.assertRaises(online.OnlineStudioError):
                online.require_under_spend_cap(uid)

    def test_charge_is_saved_before_project_disappears(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ONLINE_STUDIO_DATA_ROOT': tmp, 'ONLINE_STUDIO_USAGE_URL': ''}):
            root = Path(tmp)
            project = root / 'projects' / ('a' * 64) / 'qa-session'
            ledger = project / 'paper/.paper_studio/api_usage.jsonl'
            append_usage(ledger, {'estimated_cost_usd': 1.25})
            shutil.rmtree(project)
            self.assertEqual(billing.account_total(root, 'a' * 64), 1.25)

    def test_metering_identifies_its_client_to_cloudflare(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok":true,"amount":123}'
        with patch.dict(os.environ, {'ONLINE_STUDIO_USAGE_URL': 'https://example.invalid/internal/account-usage', 'DEEPSEEK_API_KEY': 'synthetic-key'}), patch.object(billing.urllib.request, 'urlopen', return_value=response) as request:
            self.assertEqual(billing._remote('a' * 64, []), 123)
            self.assertEqual(request.call_args.args[0].get_header('User-agent'), 'ResearchAvatar-AccountUsage/1.0')

    def test_durable_remote_total_survives_empty_local_container(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ONLINE_STUDIO_USAGE_URL': 'https://example.invalid/internal/account-usage'}), patch.object(billing, '_remote', return_value=30_000_000) as remote:
            self.assertEqual(billing.account_total(Path(tmp), 'a' * 64), 30)
            remote.assert_called_once_with('a' * 64, [])

    def test_failed_sync_retains_outbox_and_retries_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ONLINE_STUDIO_USAGE_URL': 'https://example.invalid/internal/account-usage'}):
            root = Path(tmp)
            billing.persist_project_cost(root, 'a' * 64, root / 'projects/a/b', 1.5)
            with patch.object(billing, '_remote', side_effect=billing.UsageUnavailable('offline')):
                with self.assertRaises(billing.UsageUnavailable):
                    billing.account_total(root, 'a' * 64)
            with patch.object(billing, '_remote', return_value=1_500_000) as remote:
                self.assertEqual(billing.account_total(root, 'a' * 64), 1.5)
                self.assertEqual(len(remote.call_args.args[1]), 1)
                billing.persist_project_cost(root, 'a' * 64, root / 'projects/a/b', 1.0)
                self.assertEqual(billing.account_total(root, 'a' * 64), 1.5)
                self.assertEqual(remote.call_args.args[1], [])

    def test_capacity_reserved_during_initialization_and_released_on_failure(self):
        entered, release = threading.Event(), threading.Event()
        def blocked_create(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(5))
            raise online.OnlineStudioError('synthetic initialization failure')
        with patch.dict(online.SESSIONS, {}, clear=True), patch.object(online, 'MAX_ACTIVE_SESSIONS', 1), patch.object(online, '_create_session', side_effect=blocked_create):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(online.create_session, {}, user_id='one')
                try:
                    self.assertTrue(entered.wait(5))
                    with self.assertRaisesRegex(online.OnlineStudioError, 'session is full'):
                        online.create_session({}, user_id='two')
                finally:
                    release.set()
                with self.assertRaises(online.OnlineStudioError):
                    first.result()
            self.assertEqual(online.SESSION_START_RESERVATIONS, 0)
            with patch.object(online, '_create_session', return_value='recovered'):
                self.assertEqual(online.create_session({}, user_id='three'), 'recovered')

    @unittest.skipUnless(shutil.which('node') and (Path(__file__).resolve().parents[1] / 'deploy/cloudflare/node_modules/esbuild').exists(), 'Worker test requires Node and installed deployment dependencies')
    def test_worker_usage_authentication_and_idempotency(self):
        subprocess.run(['node', str(Path(__file__).with_name('account_usage_worker.cjs'))], check=True, capture_output=True, text=True)
