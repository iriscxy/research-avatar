import unittest
import copy

from research_avatar.paper_structure import (
    PaperStructureError,
    design_structure_with_agent,
    normalize_reference_line_ranges,
    normalize_structure_design,
    parse_structure_response,
    structure_prompt,
    validate_structure_design,
)


class PaperStructureTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "target": {"venue": "Example Short", "submission_content_pages": 4},
            "paper_title": "Target Work",
            "claims": [{"id": "C1", "claim": "The method improves robustness."}],
            "paper_outline": [{
                "section_id": "abstract",
                "paragraphs": [{
                    "id": "A1", "plan_sentence": "Summarize the work.",
                    "supports": ["C1"], "evidence": ["result"], "artifact_refs": [],
                }],
            }],
            "paper_artifacts": [],
        }
        self.source = "Title\nAbstract\nOne complete abstract paragraph.\n1 Introduction\nBody paragraph."
        self.payload = {
            "structure_reference_analysis": {
                "title": "Owned Paper",
                "global_argument_arc": "problem to method to evidence",
                "body_sections": [{
                    "heading": "Abstract", "section_role": "summary",
                    "relation_to_previous": "opening", "relation_to_next": "sets up introduction",
                    "paragraphs": [{
                        "id": "REF-A1", "start_line": 3, "end_line": 3,
                        "gist": "summarizes the paper", "rhetorical_role": "summary",
                        "relation_to_previous": "opening", "relation_to_next": "sets up introduction",
                    }],
                }],
                "appendix_structure": "none",
            },
            "paper_outline": [{
                "section_id": "abstract", "title": "Abstract",
                "section_role": "summary", "relation_to_previous": "opening",
                "relation_to_next": "sets up introduction", "length_share": 1.0,
                "reference_context": {
                    "source_heading": "Abstract",
                    "logic_summary_zh": "参考摘要压缩了问题、方法和结果。",
                    "reference_paragraph_ids": ["REF-A1"],
                },
                "paragraphs": [{
                    "id": "A1", "plan_sentence": "Summarize the method and supported robustness result.",
                    "rhetorical_role": "summary", "relation_to_previous": "opening",
                    "relation_to_next": "sets up introduction", "covers": ["A1"],
                    "supports": ["C1"], "evidence": ["result"], "artifact_refs": [],
                }],
            }],
        }

    def test_one_call_returns_target_architecture_without_reference_mapping(self):
        calls = []
        result = design_structure_with_agent(
            self.contract, self.source, reference={"publication_key": "owned"},
            invoke=lambda prompt: calls.append(prompt) or __import__("json").dumps(self.payload),
        )
        self.assertEqual(len(calls), 1)
        paragraph = result["paper_outline"][0]["paragraphs"][0]
        self.assertNotIn("reference_lines", paragraph)
        self.assertNotIn("reference_anchor", paragraph)
        context = result["paper_outline"][0]["reference_context"]
        self.assertEqual(context["excerpts"][0]["text"], "One complete abstract paragraph.")
        self.assertNotIn("reference_paragraph_ids", context)

    def test_prompt_makes_logic_similarity_and_no_mapping_explicit(self):
        prompt = structure_prompt(self.contract, self.source, reference={"publication_key": "owned"})
        self.assertIn("section-level context", prompt)
        self.assertIn("complete_line_numbered_structure_reference", prompt)
        self.assertIn("Enumerate the Abstract", prompt)

    def test_online_prompt_maps_each_target_paragraph_to_one_reference_paragraph(self):
        self.contract["writing_boundary"] = {
            "experiment_results_available": False,
            "numeric_policy": "replace_quantitative_values_with_xx",
        }
        prompt = structure_prompt(
            self.contract,
            self.source,
            reference={"publication_key": "owned"},
            paragraph_mapping=True,
            selected_reference_inventory=True,
        )
        self.assertIn("For every TARGET paragraph", prompt)
        self.assertIn('"reference_paragraph_ids": ["REF-I-P1"]', prompt)
        self.assertIn("Do not emit unused reference paragraphs", prompt)
        self.assertIn("minified JSON", prompt)
        self.assertIn("at most 12 English words", prompt)
        self.assertIn("at most 30 English words", prompt)
        self.assertIn("write the literal xx", prompt)
        self.assertIn("reference Abstract is mandatory", prompt)
        payload = copy.deepcopy(self.payload)
        target = payload["paper_outline"][0]["paragraphs"][0]
        target["reference_paragraph_ids"] = ["UNKNOWN"]
        normalize_structure_design(
            self.contract, payload, paragraph_mapping=True
        )
        self.assertEqual(target["reference_paragraph_ids"], ["REF-A1"])
        self.assertEqual(
            payload["paper_outline"][0]["reference_context"]["reference_paragraph_ids"],
            ["REF-A1"],
        )

    def test_target_abstract_cannot_map_to_reference_introduction(self):
        payload = copy.deepcopy(self.payload)
        payload["structure_reference_analysis"]["body_sections"].append({
            "heading": "1 Introduction",
            "section_role": "motivation",
            "relation_to_previous": "follows abstract",
            "relation_to_next": "narrows gap",
            "paragraphs": [{
                "id": "REF-I-P1", "start_line": 5, "end_line": 5,
                "gist": "motivates the topic", "rhetorical_role": "motivation",
                "relation_to_previous": "follows abstract",
                "relation_to_next": "narrows gap",
            }],
        })
        target_section = payload["paper_outline"][0]
        target_section["reference_context"].update({
            "source_heading": "1 Introduction",
            "reference_paragraph_ids": ["REF-I-P1"],
        })
        target_section["paragraphs"][0]["reference_paragraph_ids"] = ["REF-I-P1"]

        normalize_structure_design(self.contract, payload, paragraph_mapping=True)

        self.assertEqual(
            target_section["reference_context"]["reference_paragraph_ids"],
            ["REF-A1"],
        )
        self.assertEqual(
            target_section["paragraphs"][0]["reference_paragraph_ids"],
            ["REF-A1"],
        )
        validate_structure_design(
            self.contract, self.source, payload, require_paragraph_mapping=True
        )

    def test_structure_parser_repairs_only_trailing_commas(self):
        parsed = parse_structure_response(
            '{"structure_reference_analysis": {"body_sections": [],}, "paper_outline": [],}'
        )
        self.assertEqual(parsed["paper_outline"], [])
        with self.assertRaises(PaperStructureError):
            parse_structure_response('{"paper_outline": [missing]}')

    def test_missing_neighbor_relation_fails(self):
        self.payload["paper_outline"][0]["paragraphs"][0]["relation_to_next"] = ""
        with self.assertRaises(PaperStructureError):
            design_structure_with_agent(
                self.contract, self.source, reference={"publication_key": "owned"},
                invoke=lambda _prompt: __import__("json").dumps(self.payload),
            )

    def test_normalizes_relative_shares_without_changing_section_order(self):
        payload = copy.deepcopy(self.payload)
        payload["paper_outline"][0]["length_share"] = 1.1
        normalize_structure_design(self.contract, payload)
        self.assertAlmostEqual(payload["paper_outline"][0]["length_share"], 1.0)

    def test_normalizes_zero_or_missing_section_shares(self):
        payload = copy.deepcopy(self.payload)
        second = copy.deepcopy(payload["paper_outline"][0])
        payload["paper_outline"][0]["length_share"] = 0
        second["section_id"] = "introduction"
        second["title"] = "Introduction"
        second.pop("length_share")
        payload["paper_outline"].append(second)
        normalize_structure_design(self.contract, payload)
        self.assertAlmostEqual(
            sum(item["length_share"] for item in payload["paper_outline"]), 1.0
        )
        self.assertTrue(all(item["length_share"] > 0 for item in payload["paper_outline"]))

    def test_artifacts_are_inherited_from_covered_contract_obligations(self):
        contract = copy.deepcopy(self.contract)
        contract["paper_artifacts"] = [{"id": "F1", "kind": "figure"}]
        contract["paper_outline"][0]["paragraphs"][0]["artifact_refs"] = ["F1"]
        payload = copy.deepcopy(self.payload)
        payload["paper_outline"][0]["paragraphs"][0]["artifact_refs"] = []
        normalize_structure_design(contract, payload)
        self.assertEqual(
            payload["paper_outline"][0]["paragraphs"][0]["artifact_refs"],
            ["F1"],
        )

    def test_repeated_artifact_binding_materializes_one_float_at_introduction(self):
        contract = copy.deepcopy(self.contract)
        contract["paper_artifacts"] = [
            {"id": "F1", "kind": "figure", "introduced_after": "A2"}
        ]
        contract["paper_outline"][0]["paragraphs"] = [
            {"id": "A1", "artifact_refs": ["F1"]},
            {"id": "A2", "artifact_refs": ["F1"]},
        ]
        payload = copy.deepcopy(self.payload)
        first = payload["paper_outline"][0]["paragraphs"][0]
        payload["paper_outline"][0]["paragraphs"] = [
            {**first, "id": "P1", "covers": ["A1"], "artifact_refs": ["F1"]},
            {**first, "id": "P2", "covers": ["A2"], "artifact_refs": ["F1"]},
        ]
        normalize_structure_design(contract, payload)
        paragraphs = payload["paper_outline"][0]["paragraphs"]
        self.assertEqual(paragraphs[0]["artifact_refs"], [])
        self.assertEqual(paragraphs[1]["artifact_refs"], ["F1"])

    def test_repairs_missing_duplicate_and_unknown_obligation_bindings(self):
        contract = copy.deepcopy(self.contract)
        contract["paper_outline"][0]["paragraphs"] = [
            {"id": "A1", "artifact_refs": []},
            {"id": "A2", "artifact_refs": []},
        ]
        payload = copy.deepcopy(self.payload)
        payload["paper_outline"][0]["paragraphs"] = [
            {**payload["paper_outline"][0]["paragraphs"][0], "covers": ["A1", "UNKNOWN"]},
            {**payload["paper_outline"][0]["paragraphs"][0], "id": "A2", "covers": ["A1"]},
        ]
        normalize_structure_design(contract, payload)
        paragraphs = payload["paper_outline"][0]["paragraphs"]
        self.assertEqual(paragraphs[0]["covers"], ["A1"])
        self.assertEqual(paragraphs[1]["covers"], ["A2"])

    def test_repairs_reference_context_coordinate_transcription(self):
        payload = copy.deepcopy(self.payload)
        payload["paper_outline"][0]["reference_context"]["reference_paragraph_ids"] = [
            "UNKNOWN", "REF-A1", "REF-A1",
        ]
        normalize_structure_design(self.contract, payload)
        self.assertEqual(
            payload["paper_outline"][0]["reference_context"]["reference_paragraph_ids"],
            ["REF-A1"],
        )

    def test_repairs_empty_reference_selection_from_agent_named_section(self):
        payload = copy.deepcopy(self.payload)
        payload["paper_outline"][0]["reference_context"]["source_heading"] = "1 Abstract"
        payload["paper_outline"][0]["reference_context"]["reference_paragraph_ids"] = ["UNKNOWN"]
        normalize_structure_design(self.contract, payload)
        self.assertEqual(
            payload["paper_outline"][0]["reference_context"]["reference_paragraph_ids"],
            ["REF-A1"],
        )

    def test_invalid_named_reference_section_still_uses_extracted_coordinate(self):
        payload = copy.deepcopy(self.payload)
        context = payload["paper_outline"][0]["reference_context"]
        context["source_heading"] = "A heading absent from the inventory"
        context["reference_paragraph_ids"] = ["UNKNOWN"]
        normalize_structure_design(self.contract, payload)
        self.assertEqual(context["reference_paragraph_ids"], ["REF-A1"])

    def test_clips_reference_paragraph_end_to_real_source(self):
        payload = copy.deepcopy(self.payload)
        paragraph = payload["structure_reference_analysis"]["body_sections"][0]["paragraphs"][0]
        paragraph["end_line"] = 500
        normalize_reference_line_ranges(self.source, payload)
        self.assertEqual(paragraph["start_line"], 3)
        self.assertEqual(paragraph["end_line"], len(self.source.splitlines()))

    def test_drops_wholly_outside_reference_paragraph_and_rebinds_context(self):
        payload = copy.deepcopy(self.payload)
        valid = copy.deepcopy(
            payload["structure_reference_analysis"]["body_sections"][0]["paragraphs"][0]
        )
        valid["id"] = "REF-A2"
        invalid = copy.deepcopy(valid)
        invalid.update({"id": "REF-S8-P1", "start_line": 500, "end_line": 510})
        payload["structure_reference_analysis"]["body_sections"][0]["paragraphs"] = [
            invalid, valid
        ]
        payload["paper_outline"][0]["reference_context"]["reference_paragraph_ids"] = [
            "REF-S8-P1"
        ]
        normalize_reference_line_ranges(self.source, payload)
        normalize_structure_design(self.contract, payload)
        paragraphs = payload["structure_reference_analysis"]["body_sections"][0]["paragraphs"]
        self.assertEqual([item["id"] for item in paragraphs], ["REF-A2"])
        self.assertEqual(
            payload["paper_outline"][0]["reference_context"]["reference_paragraph_ids"],
            ["REF-A2"],
        )

if __name__ == "__main__":
    unittest.main()
