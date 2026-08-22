import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from research_avatar.tools.run_plan_progress import goal_command, refresh, render_parts_and_goals


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
    def test_sequential_execution_mode_is_visible_and_keeps_one_current_goal(self):
        state = fixture_state()
        state["execution_mode"] = "sequential_all_goals"
        rendered = render_parts_and_goals(state)
        self.assertIn('data-execution-mode="sequential_all_goals"', rendered)
        self.assertIn("自动依次执行全部 Goal", rendered)
        self.assertIn("任一检查失败会停止队列", rendered)
        self.assertEqual(rendered.count('class="current-goal"'), 1)

    def test_unknown_execution_mode_is_rejected(self):
        state = fixture_state()
        state["execution_mode"] = "skip_failed_goals"
        with self.assertRaisesRegex(ValueError, "unsupported run-plan execution_mode"):
            render_parts_and_goals(state)

    def test_confirmation_gate_shows_both_paths_before_any_goal_runs(self):
        state = fixture_state(proposed=None)
        state["execution_mode"] = "awaiting_goal_confirmation"
        rendered = render_parts_and_goals(state)
        self.assertIn('data-execution-mode="awaiting_goal_confirmation"', rendered)
        self.assertIn("一次确认全部 Goals", rendered)
        self.assertIn("逐个查看并确认", rendered)
        self.assertNotIn('class="current-goal"', rendered)

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
        self.assertIn('id="goal-command-G1-1">' + expected.replace("'", "&#x27;"), rendered)
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
        self.assertIn('href="/artifact/results#provenance-R1"', g1.group(0))
        self.assertIn('data-local-result-href="05_EXP_RESULT.html#provenance-R1"', g1.group(0))
        self.assertIn('location.protocol!=="file:"', g1.group(0))
        self.assertIn('class="result-value"', g1.group(0))
        self.assertIn('data-provenance-summary="Goal: G1.1', g1.group(0))
        self.assertIn('title="Goal: G1.1', g1.group(0))
        self.assertIn('.goal-results .result-value:hover::after', g1.group(0))

    def test_refresh_is_idempotent_when_completed_goal_contains_nested_section(self):
        state = fixture_state(proposed="G2.1")
        state["goals"][0]["artifact_ids"] = ["T1"]
        state["acquisition_contracts"] = [{
            "id": "A-T1-1", "artifact_id": "T1", "target_id": "t1-cell",
            "source_type": "RUN_LOCAL", "producing_goal": "G1.1",
        }]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "04_RUN_PLAN.html"
            report = root / "05_EXP_RESULT.html"
            plan.write_text(
                '<html><body><section data-report-section="parts-and-goals"><p>old</p></section>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state) + '</script></body></html>', encoding="utf-8",
            )
            report.write_text(
                '<section class="table-result" data-artifact-id="T1"><h3>T1</h3>'
                '<td data-target-id="t1-cell" data-result-id="R1"><a href="#provenance-R1" '
                'data-result-id="R1" data-provenance-summary="Goal: G1.1" '
                'title="Goal: G1.1">1</a></td></section>', encoding="utf-8",
            )
            refresh(plan)
            refresh(plan)
            source = plan.read_text(encoding="utf-8")
        self.assertEqual(source.count('data-current-goal-id="G2.1"'), 1)
        self.assertEqual(len(re.findall(r'<button[^>]*data-copy-goal-target=', source)), 1)
        self.assertEqual(source.count('class="goal-results"'), 1)

    def test_shared_artifact_is_rendered_once_under_earliest_owning_goal(self):
        state = fixture_state(proposed="G2.1")
        state["proposed_goal_id"] = None
        state["goals"][1]["status"] = "completed"
        state["goals"][0]["artifact_ids"] = ["T1"]
        state["goals"][1]["artifact_ids"] = ["T1"]
        state["acquisition_contracts"] = [
            {"id": "A-T1-1", "artifact_id": "T1", "target_id": "t1-first",
             "source_type": "RUN_LOCAL", "producing_goal": "G1.1"},
            {"id": "A-T1-2", "artifact_id": "T1", "target_id": "t1-later",
             "source_type": "RUN_LOCAL", "producing_goal": "G2.1"},
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "04_RUN_PLAN.html"
            report = root / "05_EXP_RESULT.html"
            plan.write_text(
                '<html><body><section data-report-section="parts-and-goals"><p>old</p></section>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state) + '</script></body></html>', encoding="utf-8",
            )
            report.write_text(
                '<section class="table-result" data-artifact-id="T1"><h3>T1</h3><table><tr>'
                '<td data-target-id="t1-first" data-result-id="R1"><a href="#provenance-R1" '
                'data-result-id="R1" data-provenance-summary="Goal: G1.1" title="Goal: G1.1">1</a></td>'
                '<td data-target-id="t1-later" data-result-id="R2"><a href="#provenance-R2" '
                'data-result-id="R2" data-provenance-summary="Goal: G2.1" title="Goal: G2.1">2</a></td>'
                '</tr></table></section>', encoding="utf-8",
            )
            result = refresh(plan)
            source = plan.read_text(encoding="utf-8")
        g1 = re.search(r'<article[^>]+data-goal-id="G1\.1".*?</article>', source, re.S)
        g2 = re.search(r'<article[^>]+data-goal-id="G2\.1".*?</article>', source, re.S)
        self.assertEqual(result["completed_artifact_snapshots"], 1)
        self.assertEqual(source.count('data-artifact-id="T1"'), 1)
        self.assertIn('class="goal-results"', g1.group(0))
        self.assertIn('data-target-id="t1-first"', g1.group(0))
        self.assertIn('data-target-id="t1-later"', g1.group(0))
        self.assertNotIn('class="goal-results"', g2.group(0))

    def test_refresh_removes_stale_tail_left_by_legacy_nested_section_regex(self):
        state = fixture_state(proposed="G2.1")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "04_RUN_PLAN.html"
            path.write_text(
                '<html><body><section data-report-section="parts-and-goals"><p>old</p></section>'
                '<article><div class="current-goal" data-current-goal-id="G1.1">stale</div>'
                '<button data-copy-goal-target="stale">stale</button></article>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state) + '</script></body></html>', encoding="utf-8",
            )
            refresh(path)
            source = path.read_text(encoding="utf-8")
        self.assertNotIn('data-copy-goal-target="stale"', source)
        self.assertEqual(source.count('data-current-goal-id="G2.1"'), 1)
        self.assertEqual(len(re.findall(r'<button[^>]*data-copy-goal-target=', source)), 1)

    def test_completed_goal_embeds_a_real_figure_with_its_source_table(self):
        state = fixture_state(proposed="G2.1")
        state["goals"][0]["artifact_ids"] = ["F2"]
        state["acquisition_contracts"] = [{
            "id": "A-F2-1",
            "artifact_id": "F2",
            "target_id": "f2-panel-a-00",
            "source_type": "RUN_LOCAL",
            "producing_goal": "G1.1",
            "figure_source_cell": True,
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
                '<section class="figure-result" data-artifact-id="F2" '
                'data-source-target-ids="f2-panel-a-00"><h3>F2</h3>'
                '<div class="result-panel"><h4>panel-a</h4><table><tr>'
                '<td data-target-id="f2-panel-a-00" data-result-id="R-F2-1">'
                '<a href="#provenance-R-F2-1" data-result-id="R-F2-1" '
                'data-provenance-summary="Goal: G1.1&#10;Command: python run.py" '
                'title="Goal: G1.1&#10;Command: python run.py">0.82</a></td>'
                '</tr></table><img class="result-plot" src="f2.svg" '
                'data-generated-from-target-ids="f2-panel-a-00"></div></section>',
                encoding="utf-8",
            )
            result = refresh(plan)
            source = plan.read_text(encoding="utf-8")
        self.assertEqual(result["completed_artifact_snapshots"], 1)
        self.assertIn('class="result-plot"', source)
        self.assertIn('data-target-id="f2-panel-a-00"', source)
        self.assertIn('href="/artifact/results#provenance-R-F2-1"', source)
        self.assertIn('data-local-result-href="05_EXP_RESULT.html#provenance-R-F2-1"', source)
        self.assertIn('class="result-value"', source)

    def test_completed_goal_embeds_every_figure_with_an_adjacent_table(self):
        state = fixture_state(proposed="G2.1")
        state["goals"][0]["artifact_ids"] = ["F1", "F2"]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "04_RUN_PLAN.html"
            report = root / "05_EXP_RESULT.html"
            plan.write_text(
                '<html><body><section data-report-section="parts-and-goals"><p>old</p></section>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state)
                + '</script></body></html>',
                encoding="utf-8",
            )
            report.write_text(
                '<section data-artifact-id="F1"><h3>Qualitative mechanism</h3>'
                '<svg></svg><table><tr><td>verified evidence input</td></tr></table></section>'
                '<section data-artifact-id="F2" '
                'data-provenance="ESTIMATED_ARRAY_CONSTRAINED_BY_REPORTED_SUMMARIES">'
                '<h3>Estimated curve</h3><svg></svg><table><tr><td>0</td>'
                '<td>0.717</td></tr></table></section>',
                encoding="utf-8",
            )
            result = refresh(plan)
            source = plan.read_text(encoding="utf-8")
        self.assertEqual(result["completed_artifact_snapshots"], 2)
        self.assertIn('data-artifact-id="F2"', source)
        self.assertIn("0.717", source)
        self.assertIn('data-artifact-id="F1"', source)
        self.assertIn("verified evidence input", source)

    def test_completed_goal_rejects_figure_without_adjacent_table(self):
        state = fixture_state(proposed="G2.1")
        state["goals"][0]["artifact_ids"] = ["F1"]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "04_RUN_PLAN.html"
            report = root / "05_EXP_RESULT.html"
            plan.write_text(
                '<html><body><section data-report-section="parts-and-goals"><p>old</p></section>'
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state) + '</script></body></html>', encoding="utf-8",
            )
            report.write_text(
                '<section data-artifact-id="F1"><h3>Figure only</h3><svg></svg></section>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "lacks its adjacent source/evidence table"):
                refresh(plan)

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
