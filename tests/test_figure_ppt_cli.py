import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from research_avatar.tools.figure_ppt import cmd_build


class FigurePptCliTests(unittest.TestCase):
    def test_all_command_argument_shape_is_accepted_by_legacy_build(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            spec = root / "spec.json"
            output = root / "figure.pptx"
            spec.write_text(
                json.dumps(
                    {
                        "figure_id": "fixture",
                        "canvas_in": [4.0, 2.0],
                        "labels": [],
                    }
                ),
                encoding="utf-8",
            )
            # `all` defines spec/out/provider/paper/model but has no `img` option.
            args = SimpleNamespace(spec=str(spec), out=str(output))
            cmd_build(args)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
