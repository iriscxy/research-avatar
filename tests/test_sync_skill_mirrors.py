import unittest
from pathlib import Path

from research_avatar.tools.sync_skill_mirrors import is_disposable


class SkillMirrorTests(unittest.TestCase):
    def test_generated_python_cache_is_disposable(self):
        self.assertTrue(is_disposable(Path("runplan/scripts/__pycache__/check.cpython-312.pyc")))
        self.assertTrue(is_disposable(Path("runplan/scripts/check.pyo")))
        self.assertTrue(is_disposable(Path("runplan/.DS_Store")))
        self.assertFalse(is_disposable(Path("runplan/scripts/check.py")))


if __name__ == "__main__":
    unittest.main()
