from __future__ import annotations

import csv
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTANCE_PATHS = (
    ROOT / "paper/figsrc/micro_typo_intent/result_fixture.json",
    ROOT / "code/RESULTS_LEDGER.csv",
    ROOT / "reports/05_EXP_RESULT.html",
    ROOT / "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.png",
    ROOT / "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.pdf",
)


@unittest.skipUnless(
    all(path.is_file() for path in INSTANCE_PATHS),
    "local completed micro-typo result instance is not included in a clean clone",
)
class MicroTypoCompletedResultTests(unittest.TestCase):
    def test_real_fixture_is_exactly_ledger_backed(self) -> None:
        fixture = json.loads((ROOT / "paper/figsrc/micro_typo_intent/result_fixture.json").read_text())
        with (ROOT / "code/RESULTS_LEDGER.csv").open(newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if row["artifact_id"] == "F2"]
        self.assertFalse(fixture["synthetic"])
        self.assertEqual(fixture["source"], "code/RESULTS_LEDGER.csv")
        self.assertEqual(set(fixture["source_result_ids"]), {row["result_id"] for row in rows})
        self.assertEqual(len(rows), 8)

    def test_final_plot_and_all_twenty_cells_are_traceable(self) -> None:
        report = (ROOT / "reports/05_EXP_RESULT.html").read_text()
        self.assertEqual(len(re.findall(r'<td\b[^>]*data-result-id="R-G[23]\.1-', report)), 20)
        self.assertNotIn('[PENDING]</td>', report)
        self.assertIn('class="result-plot"', report)
        generated = re.search(r'data-generated-from-target-ids="([^"]+)"', report)
        self.assertIsNotNone(generated)
        self.assertEqual(len(generated.group(1).split()), 8)
        self.assertIn('data:image/png;base64,', report)
        self.assertNotIn('result_fixture.json</code> →', report)
        self.assertNotIn('F2_typo_sensitivity.pdf</code></figcaption>', report)
        self.assertGreater((ROOT / "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.png").stat().st_size, 10_000)
        self.assertGreater((ROOT / "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.pdf").stat().st_size, 1_000)


if __name__ == "__main__":
    unittest.main()
