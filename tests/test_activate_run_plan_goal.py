import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


class ActivateRunPlanGoalTests(unittest.TestCase):
    def test_activation_replaces_balanced_section_with_nested_result_snapshot(self):
        state = {
            "state": "goal_proposed",
            "execution_mode": "manual_each_goal",
            "active_goal": None,
            "proposed_goal_id": "G1.1",
            "parts": [
                {"id": "P1", "title": "Part", "decision": "Question", "goals": ["G1.1"]}
            ],
            "goals": [
                {
                    "id": "G1.1",
                    "part_id": "P1",
                    "status": "proposed",
                    "title": "Goal",
                    "decision_question": "Question",
                    "visible_work": "Work",
                    "visible_evidence": "Evidence",
                    "completion_check": "Check",
                    "artifact_ids": [],
                    "outputs": [],
                }
            ],
            "acquisition_contracts": [],
        }
        with TemporaryDirectory() as directory:
            plan = Path(directory) / "04_RUN_PLAN.html"
            plan.write_text(
                '<html><body><section data-report-section="parts-and-goals">'
                '<article><section data-artifact-id="T1">STALE NESTED RESULT</section></article>'
                '</section><script type="application/json" id="run-plan-state">'
                + json.dumps(state)
                + '</script></body></html>',
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "activate_run_plan_goal.py"),
                    "G1.1",
                    "--plan",
                    str(plan),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            source = plan.read_text(encoding="utf-8")

        self.assertEqual(json.loads(process.stdout)["active_goal"], "G1.1")
        self.assertNotIn("STALE NESTED RESULT", source)
        self.assertEqual(
            len(re.findall(r'<section\b[^>]*data-report-section="parts-and-goals"', source)),
            1,
        )
        embedded = json.loads(
            source.split('id="run-plan-state">', 1)[1].split("</script>", 1)[0]
        )
        self.assertEqual(embedded["active_goal"], "G1.1")
        self.assertEqual(embedded["goals"][0]["status"], "running")


if __name__ == "__main__":
    unittest.main()
