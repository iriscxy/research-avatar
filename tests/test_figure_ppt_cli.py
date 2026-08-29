import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from research_avatar.tools.figure_ppt import (
    cmd_buildshapes,
    validate_native_shape_spec,
)


class FigurePptCliTests(unittest.TestCase):
    def test_final_shape_contract_rejects_no_text(self):
        with self.assertRaisesRegex(ValueError, "no_text=true"):
            validate_native_shape_spec({"no_text": True, "shapes": []})

    def test_semantic_shape_contract_requires_input_operation_and_output(self):
        spec = {
            "semantic_contract_version": 2,
            "required_semantic_roles": ["input", "operation", "output"],
            "shapes": [
                {"kind": "textbox", "text": "Evidence", "semantic_role": "input", "font_size": 8},
                {"kind": "textbox", "text": "Revoke", "semantic_role": "operation", "font_size": 8},
                {"kind": "textbox", "text": "Still valid", "semantic_role": "annotation", "font_size": 8},
            ],
        }
        with self.assertRaisesRegex(ValueError, "missing roles: output"):
            validate_native_shape_spec(spec)

    def test_semantic_shape_contract_accepts_complete_roles_and_required_labels(self):
        spec = {
            "semantic_contract_version": 2,
            "required_semantic_roles": ["input", "operation", "output"],
            "required_labels": ["Evidence", "Revoke", "Valid"],
            "shapes": [
                {"kind": "textbox", "text": "Evidence", "semantic_role": "input", "font_size": 8},
                {"kind": "textbox", "text": "Revoke", "semantic_role": "operation", "font_size": 8},
                {"kind": "textbox", "text": "Valid", "semantic_role": "output", "font_size": 8},
            ],
        }
        self.assertIs(validate_native_shape_spec(spec), spec)

    def test_cli_exposes_only_native_shape_workflow(self):
        result = subprocess.run(
            [sys.executable, "-m", "research_avatar.tools.figure_ppt", "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("buildshapes", result.stdout)
        self.assertIn("pdfshapes", result.stdout)
        self.assertNotIn("genprompt", result.stdout)

    def test_native_shape_builder_preserves_dashed_connector_without_media(self):
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
            cmd_buildshapes(SimpleNamespace(spec=str(spec), out=str(output)))
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                slide = archive.read("ppt/slides/slide1.xml").decode("utf-8")
            self.assertIn('prstDash val="dash"', slide)
            self.assertFalse(any(name.startswith("ppt/media/") for name in names))


if __name__ == "__main__":
    unittest.main()
