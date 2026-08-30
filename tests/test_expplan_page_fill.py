import copy
import unittest

from research_avatar.tools.validate_experiment_plan import validate_page_fill_contract


def complete_contract() -> dict:
    sections = [
        ("abstract", 0.05, ["A-P1"]),
        ("introduction", 0.20, ["I-P1", "I-P2"]),
        ("method", 0.25, ["M1-P1", "M2-P1"]),
        ("experiments", 0.35, ["E1-P1", "E2-P1", "E3-P1", "E4-P1"]),
        ("discussion", 0.10, ["D1-P1"]),
        ("conclusion", 0.05, ["C-P1"]),
    ]
    return {
        "target": {"submission_content_pages": 4},
        "paper_outline": [
            {
                "id": section_id,
                "length_share": share,
                "paragraphs": [{"id": paragraph_id} for paragraph_id in paragraph_ids],
            }
            for section_id, share, paragraph_ids in sections
        ],
        "paper_artifacts": [
            {"id": "F1", "kind": "figure", "shell": {"data_driven": False}},
            {"id": "T1", "kind": "table", "shell": {}},
            {"id": "F2", "kind": "figure", "shell": {"data_driven": True}},
            {"id": "T2", "kind": "table", "shell": {}},
        ],
        "experiment_contracts": [
            {"id": "E-MAIN"}, {"id": "E-ROBUST"}, {"id": "E-ABLATE"},
            {"id": "E-COST"},
        ],
        "page_fill_contract": {
            "target_body_pages": 4,
            "minimum_last_page_fill": 0.85,
            "section_length_shares": {
                section_id: share for section_id, share, _ in sections
            },
            "experiment_paragraph_ids": ["E1-P1", "E2-P1", "E3-P1", "E4-P1"],
            "result_artifact_ids": ["T1", "F2", "T2"],
            "evidence_blocks": [
                {"kind": "main_comparison", "paragraph_ids": ["E2-P1"],
                 "experiment_ids": ["E-MAIN"], "artifact_ids": ["T1"]},
                {"kind": "robustness_or_sensitivity", "paragraph_ids": ["E3-P1"],
                 "experiment_ids": ["E-ROBUST"], "artifact_ids": ["F2"]},
                {"kind": "ablation", "paragraph_ids": ["E4-P1"],
                 "experiment_ids": ["E-ABLATE"], "artifact_ids": ["T2"]},
                {"kind": "cost_or_efficiency", "paragraph_ids": ["E4-P1"],
                 "experiment_ids": ["E-COST"], "artifact_ids": ["T2"]},
            ],
            "expected_body_pages": {"min": 3.9, "max": 4.1},
            "feasibility_status": "credible_full_length",
            "micro_study_override": False,
            "estimation_basis": "Section shares, four experiment paragraphs, and three result floats.",
        },
    }


class ExpPlanPageFillTests(unittest.TestCase):
    def test_complete_short_paper_program_passes(self):
        self.assertEqual(validate_page_fill_contract(complete_contract()), [])

    def test_thin_experiment_program_is_rejected(self):
        contract = complete_contract()
        contract["page_fill_contract"]["experiment_paragraph_ids"] = ["E1-P1"]
        contract["page_fill_contract"]["result_artifact_ids"] = ["T1"]
        contract["paper_artifacts"] = [contract["paper_artifacts"][1]]
        contract["page_fill_contract"]["evidence_blocks"] = [
            contract["page_fill_contract"]["evidence_blocks"][0]
        ]
        contract["page_fill_contract"]["expected_body_pages"] = {"min": 2.0, "max": 2.5}
        errors = validate_page_fill_contract(contract)
        self.assertTrue(any("result-bearing artifacts" in error for error in errors))
        self.assertTrue(any("experiment/result paragraphs" in error for error in errors))
        self.assertTrue(any("three distinct diagnostic" in error for error in errors))
        self.assertTrue(any("97.5%" in error for error in errors))

    def test_micro_study_requires_an_explicit_shortfall(self):
        contract = complete_contract()
        contract["page_fill_contract"].update(
            micro_study_override=True,
            feasibility_status="credible_full_length",
            expected_body_pages={"min": 2.0, "max": 2.5},
        )
        errors = validate_page_fill_contract(contract)
        self.assertTrue(any("declare a shortfall" in error for error in errors))
        self.assertTrue(any("expected_page_shortfall" in error for error in errors))

    def test_section_share_mismatch_is_rejected(self):
        contract = copy.deepcopy(complete_contract())
        contract["page_fill_contract"]["section_length_shares"]["experiments"] = 0.20
        errors = validate_page_fill_contract(contract)
        self.assertTrue(any("sum to 1.0" in error for error in errors))
        self.assertTrue(any("disagrees with paper_outline" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
