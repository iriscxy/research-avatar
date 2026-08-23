import unittest
from pathlib import Path

from research_avatar.tools.sync_skill_mirrors import adapt_markdown, is_disposable


class SkillMirrorTests(unittest.TestCase):
    def test_generated_python_cache_is_disposable(self):
        self.assertTrue(is_disposable(Path("runplan/scripts/__pycache__/check.cpython-312.pyc")))
        self.assertTrue(is_disposable(Path("runplan/scripts/check.pyo")))
        self.assertTrue(is_disposable(Path("runplan/.DS_Store")))
        self.assertFalse(is_disposable(Path("runplan/scripts/check.py")))

    def test_shared_readme_preserves_agents_as_the_canonical_source(self):
        source = "`.agents/skills/` is canonical; `$runplan` invokes the skill."
        mirrored = adapt_markdown(source, "", ("runplan",))
        self.assertIn("`.agents/skills/` is canonical", mirrored)
        self.assertIn("`/runplan` invokes", mirrored)

    def test_skill_body_adapts_runtime_specific_paths(self):
        source = "Edit `.agents/skills/runplan/SKILL.md` and invoke `$runplan`."
        mirrored = adapt_markdown(source, "runplan", ("runplan",))
        self.assertEqual(
            mirrored,
            "Edit `.claude/skills/runplan/SKILL.md` and invoke `/runplan`.",
        )


if __name__ == "__main__":
    unittest.main()
