import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from research_avatar.tools.figure_ppt import META_PROMPT, cmd_build, cmd_genprompt


class FigurePptCliTests(unittest.TestCase):
    def test_meta_prompt_requires_caption_free_semantic_decodability(self):
        self.assertIn("independently decodable by an unfamiliar reader", META_PROMPT)
        self.assertIn("mechanism or decision criterion", META_PROMPT)
        self.assertIn("never express the scientific difference only by color", META_PROMPT)
        self.assertIn("without the manuscript or caption", META_PROMPT)
        self.assertIn("unexplained arrows instead of the load-bearing mechanism", META_PROMPT)
        self.assertIn("reference-figure visual grammar", META_PROMPT)
        self.assertIn("rectangles whose only content is text", META_PROMPT)
        self.assertIn("training-only objects must remain in training", META_PROMPT)

    def test_genprompt_combines_manuscript_with_abstract_visual_grammar(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "method.tex"
            grammar = root / "grammar.json"
            spec = root / "spec.json"
            paper.write_text("CURRENT METHOD EVIDENCE", encoding="utf-8")
            grammar.write_text('{"shared_visual_grammar":["USE PICTOGRAMS"]}', encoding="utf-8")
            spec.write_text('{"figure_id":"fixture"}', encoding="utf-8")
            args = SimpleNamespace(
                paper=str(paper),
                visual_grammar=str(grammar),
                spec=str(spec),
                model="test-model",
            )
            with patch(
                "research_avatar.tools.figure_ppt._openai_chat",
                return_value="GENERATED DRAW PROMPT",
            ) as generate:
                cmd_genprompt(args)

            payload = generate.call_args.args[2]
            self.assertIn("CURRENT METHOD EVIDENCE", payload)
            self.assertIn("USE PICTOGRAMS", payload)
            self.assertIn("Do not copy", payload)
            self.assertEqual(
                json.loads(spec.read_text(encoding="utf-8"))["draw_prompt"],
                "GENERATED DRAW PROMPT",
            )

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

    def test_native_shape_builder_preserves_dashed_kl_connector(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            spec = root / "shapes.json"
            output = root / "figure.pptx"
            spec.write_text(
                json.dumps({
                    "figure_id": "fixture",
                    "canvas_in": [4.0, 2.0],
                    "shapes": [{
                        "kind": "arrow", "x1": 0.1, "y1": 0.5,
                        "x2": 0.9, "y2": 0.5, "color": "666666",
                        "weight": 1.2, "dash": True,
                    }],
                }),
                encoding="utf-8",
            )
            from research_avatar.tools.figure_ppt import cmd_buildshapes
            cmd_buildshapes(SimpleNamespace(spec=str(spec), out=str(output)))
            import zipfile
            with zipfile.ZipFile(output) as archive:
                slide = archive.read("ppt/slides/slide1.xml").decode("utf-8")
            self.assertIn('prstDash val="dash"', slide)


if __name__ == "__main__":
    unittest.main()
