import unittest
from unittest.mock import patch

from tools import experiment_history, profile_enrich


class ProfileToolTests(unittest.TestCase):
    def test_framework_names_require_token_boundaries(self):
        aggregate = {
            "_dep": experiment_history.Counter(),
            "_launch": experiment_history.Counter(),
            "_gpu": experiment_history.Counter(),
            "_model": experiment_history.Counter(),
            "_err": experiment_history.Counter(),
            "oom": 0,
            "wandb": 0,
            "ckpt": 0,
        }
        experiment_history._scan_text(
            "control centralization uses transformers, TRL, PyTorch and flash_attn",
            aggregate,
        )
        self.assertEqual(aggregate["_dep"]["trl"], 1)
        self.assertEqual(aggregate["_dep"]["transformers"], 1)
        self.assertEqual(aggregate["_dep"]["pytorch"], 1)
        self.assertEqual(aggregate["_dep"]["flash-attn"], 1)
        self.assertNotIn("torch", aggregate["_dep"])

        empty = {key: value.copy() if hasattr(value, "copy") else value for key, value in aggregate.items()}
        empty["_dep"].clear()
        experiment_history._scan_text("control and central policy", empty)
        self.assertNotIn("trl", empty["_dep"])

    def test_bibtex_escapes_plain_scholar_metadata(self):
        entry = profile_enrich._bibtex(
            {
                "title": "Safety & Utility: 100% under shift_model",
                "authors": "A_B Author, C Dollar$",
                "venue": "R&D #1",
                "year": "2026",
                "doi": "10.1000/raw_suffix",
            },
            "author2026safety",
        )
        self.assertIn(r"Safety \& Utility: 100\% under shift\_model", entry)
        self.assertIn(r"A\_B Author and C Dollar\$", entry)
        self.assertIn(r"R\&D \#1", entry)
        self.assertIn("10.1000/raw_suffix", entry)

    def test_semantic_scholar_helper_uses_active_python(self):
        completed = type("Completed", (), {"returncode": 0, "stdout": '{"data": []}', "stderr": ""})()
        with patch.object(profile_enrich.subprocess, "run", return_value=completed) as run:
            self.assertEqual(profile_enrich._s2_search("fetcher.py", "Title"), [])
        self.assertEqual(run.call_args.args[0][0], profile_enrich.sys.executable)


if __name__ == "__main__":
    unittest.main()
