import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from research_avatar.tools.prepare_reideation_handoff import build_handoff, load_checkpoint


class PrepareReideationHandoffTests(unittest.TestCase):
    def test_verified_anomaly_becomes_traceable_ideagen_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "results/anomaly.json"
            evidence.parent.mkdir()
            evidence.write_text('{"mismatch": true}', encoding="utf-8")
            checkpoint = {
                "status": "decision_required",
                "conformance_status": "VERIFIED",
                "anomaly_status": "VERIFIED_SCIENTIFIC_ANOMALY",
                "checked_goal_id": "G2.1",
                "evidence_artifact": "results/anomaly.json",
                "decision": "Return the anomaly to IdeaGen.",
                "command": "python code/reproduce.py",
                "observed_mismatch": "The baseline changes under a registered invariant.",
                "baseline_contract": "The baseline should preserve the invariant.",
            }
            payload = build_handoff(checkpoint, root)
        self.assertEqual(payload["status"], "decision_required")
        self.assertEqual(
            payload["evidence_sha256"],
            hashlib.sha256(b'{"mismatch": true}').hexdigest(),
        )
        self.assertIn("baseline should preserve", payload["baseline_contract"])

    def test_unverified_anomaly_cannot_trigger_handoff(self):
        checkpoint = {
            "status": "decision_required",
            "conformance_status": "FAILED",
            "anomaly_status": "VERIFIED_SCIENTIFIC_ANOMALY",
            "checked_goal_id": "G2.1",
            "evidence_artifact": "result.json",
            "decision": "retry",
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "verified conformance"):
                build_handoff(checkpoint, Path(directory))

    def test_loads_checkpoint_from_runplan_html(self):
        state = {"reideation_checkpoint": {"status": "not_triggered"}}
        html = (
            '<script type="application/json" id="run-plan-state">'
            + json.dumps(state)
            + "</script>"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "04_RUN_PLAN.html"
            path.write_text(html, encoding="utf-8")
            checkpoint = load_checkpoint(path)
        self.assertEqual(checkpoint["status"], "not_triggered")


if __name__ == "__main__":
    unittest.main()
