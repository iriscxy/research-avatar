from __future__ import annotations

import unittest
from pathlib import Path

from code.micro_typo.core import (
    CharacterTrigramNaiveBayes,
    DatasetRecord,
    MajorityClassifier,
    WordUnigramNaiveBayes,
    accuracy,
    macro_f1,
    perturb_record,
    reconstruct_text,
    robustness_drop,
    stable_record_id,
)
from code.micro_typo.data import APPROVED_REVISION, build_manifest, load_manifest
from code.micro_typo.run import one_character_pass, one_word_level_pass


def record(text: str, label: str, index: int) -> DatasetRecord:
    return DatasetRecord(stable_record_id("train", label, text), "train", text, label, index)


class MicroTypoTests(unittest.TestCase):
    def test_perturbation_is_deterministic_and_reconstructable(self) -> None:
        item = record("weather restaurant balance changing", "weather", 0)
        first = perturb_record(item, 1.0, 20260814)
        second = perturb_record(item, 1.0, 20260814)
        self.assertEqual(first, second)
        self.assertTrue(first.edit_log)
        self.assertEqual(reconstruct_text(first), item.text)

    def test_majority_uses_lexical_tie_break(self) -> None:
        model = MajorityClassifier().fit([record("one", "weather", 0), record("two", "balance", 1)])
        self.assertEqual(model.predict("anything"), "balance")

    def test_shared_naive_bayes_interfaces_are_deterministic(self) -> None:
        train = [
            record("weather rain forecast", "weather", 0),
            record("restaurant food review", "restaurant_reviews", 1),
            record("change playback speed", "change_speed", 2),
            record("bank account balance", "balance", 3),
        ]
        for model in (WordUnigramNaiveBayes(), CharacterTrigramNaiveBayes()):
            model.fit(train)
            first = model.predict_with_scores("weather forecast")
            second = model.predict_with_scores("weather forecast")
            self.assertEqual(first, second)
            self.assertEqual(first[0], "weather")

    def test_exact_metrics(self) -> None:
        gold = ["a", "a", "b", "b"]
        predicted = ["a", "b", "b", "b"]
        self.assertEqual(accuracy(gold, predicted), 0.75)
        self.assertAlmostEqual(macro_f1(gold, predicted, ["a", "b"]), (2 / 3 + 4 / 5) / 2)
        self.assertEqual(robustness_drop(0.75, 0.5), 0.25)

    def test_workspace_manifest_is_frozen_and_reopenable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest_path = root / "data/micro_typo_intent/manifest.json"
        first = build_manifest(root / "data/micro_typo_intent/source", manifest_path)
        second = load_manifest(manifest_path)
        self.assertEqual(first, second)
        self.assertEqual(second["source"]["approved_revision"], APPROVED_REVISION)
        self.assertEqual(len(second["records"]), 120)
        self.assertEqual(sum(item["split"] == "train" for item in second["records"]), 80)
        self.assertEqual(sum(item["split"] == "test" for item in second["records"]), 40)
        for metadata in second["source"]["files"].values():
            self.assertTrue((root / metadata["path"]).is_file())

    def test_word_level_pass_has_only_the_twelve_owned_targets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(root / "data/micro_typo_intent/manifest.json")
        import json
        config = json.loads((root / "code/micro_typo/config.json").read_text())
        payload = one_word_level_pass(manifest, config)
        expected = {
            *(f"t1-{row:02d}-{column:02d}" for row in (0, 1) for column in range(4)),
            *(f"f2-typo_sensitivity-{rate:02d}-00" for rate in range(4)),
        }
        self.assertEqual(set(payload["paper_targets"]), expected)
        self.assertEqual(payload["methods"], ["majority", "word_unigram_nb"])
        self.assertEqual(len(payload["predictions"]), 320)
        self.assertEqual(len(payload["train_record_ids"]), 80)
        self.assertEqual(len(payload["test_record_ids"]), 40)

    def test_character_pass_has_only_the_eight_owned_targets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = load_manifest(root / "data/micro_typo_intent/manifest.json")
        import json
        config = json.loads((root / "code/micro_typo/config.json").read_text())
        payload = one_character_pass(manifest, config)
        expected = {
            *(f"t1-02-{column:02d}" for column in range(4)),
            *(f"f2-typo_sensitivity-{rate:02d}-01" for rate in range(4)),
        }
        self.assertEqual(set(payload["paper_targets"]), expected)
        self.assertEqual(payload["methods"], ["character_trigram_nb"])
        self.assertEqual(len(payload["predictions"]), 160)
        self.assertEqual(len(payload["train_record_ids"]), 80)
        self.assertEqual(len(payload["test_record_ids"]), 40)


if __name__ == "__main__":
    unittest.main()
