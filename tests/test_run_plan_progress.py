import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.run_plan_progress import goal_command, refresh, render_parts_and_goals


def fixture_state(proposed="G1.1"):
    statuses = {"G1.1": "completed" if proposed == "G2.1" else "proposed", "G2.1": "proposed" if proposed == "G2.1" else "locked"}
    goals = []
    for goal_id, part_id in (("G1.1", "P1"), ("G2.1", "P2")):
        goals.append({
            "id": goal_id,
            "part_id": part_id,
            "status": statuses[goal_id],
            "title": f"Title {goal_id}",
            "decision_question": f"Question {goal_id}",
            "visible_work": f"Work {goal_id}",
            "visible_evidence": f"Evidence {goal_id}",
            "completion_check": f"Check {goal_id}",
            "artifact_ids": [],
            "outputs": [f"results/{goal_id}.json"],
            "budget": "1 GPU-hour",
        })
    return {
        "proposed_goal_id": proposed,
        "active_goal": None,
        "goals": goals,
        "parts": [
            {"id": "P1", "title": "One", "decision": "D1", "goals": ["G1.1"]},
            {"id": "P2", "title": "Two", "decision": "D2", "goals": ["G2.1"]},
        ],
    }


class RunPlanProgressTests(unittest.TestCase):
    def test_current_goal_is_nested_in_matching_goal_card(self):
        rendered = render_parts_and_goals(fixture_state())
        self.assertEqual(rendered.count('class="current-goal"'), 1)
        g1 = re.search(r'<article[^>]+data-goal-id="G1\.1".*?</article>', rendered, re.S)
        g2 = re.search(r'<article[^>]+data-goal-id="G2\.1".*?</article>', rendered, re.S)
        self.assertIsNotNone(g1)
        self.assertIsNotNone(g2)
        self.assertIn('data-current-goal-id="G1.1"', g1.group(0))
        self.assertNotIn('class="current-goal"', g2.group(0))

    def test_current_goal_has_one_button_that_targets_the_full_command(self):
        state = fixture_state()
        rendered = render_parts_and_goals(state)
        expected = goal_command(state["goals"][0])
        self.assertEqual(rendered.count('data-copy-goal-target='), 1)
        self.assertIn('data-copy-goal-target="goal-command-G1-1"', rendered)
        self.assertIn('id="goal-command-G1-1">' + expected, rendered)
        self.assertIn('>复制 /goal</button>', rendered)
        self.assertIn('navigator.clipboard.writeText(value)', rendered)
        self.assertIn('research-studio-copy-goal', rendered)
        self.assertIn('research-studio-copy-goal-result', rendered)
        self.assertIn('aria-live="polite"', rendered)

    def test_refresh_moves_panel_after_state_advances(self):
        state = fixture_state(proposed="G2.1")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "04_RUN_PLAN.html"
            path.write_text(
                '<html><body><section data-report-section="parts-and-goals">'
                '<h2>4. Parts and Goals</h2><p>old</p></section>'
                '<section data-report-section="current-goal"><h2>5. Current Goal</h2>'
                '<p>legacy</p></section>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state)
                + '</script></body></html>',
                encoding="utf-8",
            )
            result = refresh(path)
            source = path.read_text(encoding="utf-8")
        self.assertEqual(result["current_goal"], "G2.1")
        self.assertEqual(result["copy_goal_button_count"], 1)
        self.assertNotIn('data-report-section="current-goal"', source)
        self.assertIn('data-current-goal-id="G2.1"', source)
        self.assertRegex(source, r'✅ G1\.1')
        self.assertRegex(source, r'→ G2\.1')

    def test_completed_goal_embeds_verified_artifact_with_cross_page_provenance(self):
        state = fixture_state(proposed="G2.1")
        state["goals"][0]["artifact_ids"] = ["T1"]
        state["acquisition_contracts"] = [{
            "id": "A-T1-1",
            "artifact_id": "T1",
            "target_id": "t1-cell",
            "source_type": "RUN_LOCAL",
            "producing_goal": "G1.1",
        }]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "04_RUN_PLAN.html"
            report = root / "05_EXP_RESULT.html"
            plan.write_text(
                '<html><body><section data-report-section="parts-and-goals">'
                '<h2>4. Parts and Goals</h2><p>old</p></section>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state)
                + '</script></body></html>',
                encoding="utf-8",
            )
            report.write_text(
                '<section class="table-result" data-artifact-id="T1">'
                '<h3>T1</h3><table><tbody><tr>'
                '<td data-target-id="t1-cell" data-result-id="R1">'
                '<a href="#provenance-R1" data-result-id="R1" '
                'data-provenance-summary="Goal: G1.1&#10;Raw: raw.json" '
                'title="Goal: G1.1&#10;Raw: raw.json">0.75</a>'
                '</td></tr></tbody></table></section>',
                encoding="utf-8",
            )
            result = refresh(plan)
            source = plan.read_text(encoding="utf-8")
        self.assertEqual(result["completed_artifact_snapshots"], 1)
        g1 = re.search(r'<article[^>]+data-goal-id="G1\.1".*?</article>', source, re.S)
        self.assertIsNotNone(g1)
        self.assertIn('class="goal-results"', g1.group(0))
        self.assertIn('data-artifact-id="T1"', g1.group(0))
        self.assertIn('href="05_EXP_RESULT.html#provenance-R1"', g1.group(0))
        self.assertIn('data-provenance-summary="Goal: G1.1', g1.group(0))
        self.assertIn('title="Goal: G1.1', g1.group(0))
        self.assertIn('.goal-results .result-value:hover::after', g1.group(0))

    def test_completed_goal_rejects_unlinked_target(self):
        state = fixture_state(proposed="G2.1")
        state["acquisition_contracts"] = [{
            "id": "A-T1-1",
            "artifact_id": "T1",
            "target_id": "t1-cell",
            "source_type": "RUN_LOCAL",
            "producing_goal": "G1.1",
        }]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "04_RUN_PLAN.html"
            report = root / "05_EXP_RESULT.html"
            plan.write_text(
                '<html><body><section data-report-section="parts-and-goals">'
                '<h2>4. Parts and Goals</h2><p>old</p></section>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state)
                + '</script></body></html>',
                encoding="utf-8",
            )
            report.write_text(
                '<section data-artifact-id="T1"><table><tr>'
                '<td data-target-id="t1-cell">0.75</td>'
                '</tr></table></section>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unlinked/unverified targets"):
                refresh(plan)


if __name__ == "__main__":
    unittest.main()
