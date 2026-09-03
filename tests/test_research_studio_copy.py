import unittest
from pathlib import Path

from research_avatar.tools.run_plan_progress import render_parts_and_goals


ROOT = Path(__file__).resolve().parents[1]


class ResearchStudioCopyTests(unittest.TestCase):
    def test_pipeline_tabs_keep_paper_workspace_compact_dimensions(self):
        css = (ROOT / "research_avatar/research_studio/static/style.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns:repeat(6,minmax(112px,1fr))", css)
        self.assertIn(".pipeline-button{position:relative;min-height:40px;padding:6px 9px", css)
        self.assertNotIn("grid-template-columns:1fr 1fr", css)

    def test_parent_copy_bridge_keeps_the_artifact_sandbox(self):
        app = (ROOT / "research_avatar/research_studio/static/app.js").read_text(encoding="utf-8")
        index = (ROOT / "research_avatar/research_studio/static/index.html").read_text(encoding="utf-8")
        self.assertIn('event.source !== previewFrame.contentWindow', app)
        self.assertIn('message.type !== "research-studio-copy-goal"', app)
        self.assertIn('value.startsWith("/goal ")', app)
        self.assertIn('type: "research-studio-copy-goal-result"', app)
        self.assertIn('document.execCommand("copy")', app)
        self.assertIn('sandbox="allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-downloads"', index)
        self.assertNotIn("allow-same-origin", index)
        self.assertIn("/app.js?v=20260903.1-claim-gates", index)

    def test_run_plan_button_can_request_the_parent_bridge(self):
        state = {
            "proposed_goal_id": "G1.1",
            "active_goal": None,
            "parts": [{"id": "P1", "title": "One", "decision": "Check", "goals": ["G1.1"]}],
            "goals": [{
                "id": "G1.1", "title": "Smoke", "status": "proposed",
                "visible_work": "Run smoke.", "visible_evidence": "Save evidence.",
                "completion_check": "Reopen paths.", "artifact_ids": [],
            }],
        }
        rendered = render_parts_and_goals(state)
        self.assertIn('research-studio-copy-goal"', rendered)
        self.assertIn('research-studio-copy-goal-result', rendered)
        self.assertIn("const value=source.textContent;try", rendered)


if __name__ == "__main__":
    unittest.main()
