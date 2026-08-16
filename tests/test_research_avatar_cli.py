import unittest
from unittest.mock import patch

from research_avatar.tools import research_buddy_cli


class ResearchAvatarCliTests(unittest.TestCase):
    def test_validate_covers_every_shipped_web_application(self):
        calls = []
        with (
            patch("sys.argv", ["research-avatar", "validate"]),
            patch.object(
                research_buddy_cli,
                "run",
                side_effect=lambda command, **kwargs: calls.append((command, kwargs)) or 0,
            ),
        ):
            self.assertEqual(research_buddy_cli.main(), 0)

        flattened = {" ".join(command) for command, _kwargs in calls}
        self.assertTrue(any("compileall" in item and "research_studio" in item for item in flattened))
        for source in (
            "web/demo/app.js",
            "research_avatar/paper_studio/static/app.js",
            "research_avatar/research_studio/static/app.js",
            "web/functions/_middleware.js",
        ):
            self.assertTrue(any(item.endswith(source) for item in flattened))
        self.assertTrue(
            all(kwargs.get("cwd") == research_buddy_cli.PACKAGE_ROOT for _, kwargs in calls)
        )


if __name__ == "__main__":
    unittest.main()
