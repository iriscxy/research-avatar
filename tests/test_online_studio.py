import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import research_avatar.online_studio.server as online
from research_avatar.online_studio.package import build_archive
import research_avatar.paper_studio.server as paper_studio


PROFILE_HTML = """<!doctype html><html><body>
<h1>Researcher profile</h1>
<h2>Writing Style</h2><p>Concise, evidence-first prose.</p>
<script>doNotIncludeThisSecret()</script>
</body></html>"""

STRUCTURAL_REFERENCE_TEXT = """Reference Paper Title
Jane Researcher

Abstract

This actual abstract states the research problem, explains the proposed method, reports the central measured result, and closes with a carefully bounded implication. It is deliberately long enough to act as one complete rhetorical paragraph while remaining local to the Abstract section of the selected structural reference paper.

1

Introduction

This introduction paragraph establishes the concrete motivation and explains why the research problem matters to its intended readers. It supplies enough surrounding prose to form a useful local style example without depending on the topic of the new manuscript being written.

This second introduction paragraph identifies the unresolved gap and distinguishes it from the closest existing approaches. It models the transition from broad motivation to the precise question that the rest of the paper must answer with evidence.

This final introduction paragraph previews the approach, principal findings, and bounded contributions. It demonstrates how the reference paper closes its opening argument before moving into prior work and technical definitions.

2

Related Work

This related work paragraph organizes the first research thread, synthesizes representative findings, and explains the boundary of those studies. It provides a complete comparison pattern instead of a disconnected bibliography or a list of publication metadata.

This second related work paragraph covers the closest task and evaluation literature before stating the distinction occupied by the present paper. The claims remain calibrated and the paragraph ends by making the research gap explicit.

3

Method

This method paragraph defines the central objects and formal problem setting in a reproducible order. It introduces notation only after the reader understands the operational goal and it keeps every claim tied to a concrete component of the proposed approach.

This method paragraph explains the main algorithm and its design choices step by step. It clarifies the information available to each component, the constraints enforced during selection, and the output consumed by the following stage.

This final method paragraph specifies the decision rule and implementation boundary. It distinguishes required behavior from optional engineering choices so that another researcher could reproduce the procedure without guessing hidden assumptions.

4

Experiments

This experimental paragraph defines datasets, models, metrics, baselines, and repeated trials. It makes the comparison protocol explicit before any result is interpreted and separates measured evidence from hypotheses about the underlying mechanism.

This results paragraph reports the primary comparison and describes the direction and magnitude of the observed change. It avoids unsupported generalization and connects each numeric statement to the controlled evaluation described immediately above.

This analysis paragraph checks whether the main result remains stable across evaluation conditions. It explains the relevant uncertainty and names the cases that do not support a broader claim, preserving an honest boundary around the evidence.

This ablation paragraph isolates the contribution of individual components under matched settings. It interprets the pattern cautiously and distinguishes a component association from a demonstrated causal mechanism.

This final results paragraph examines sensitivity and failure cases before summarizing what the full evaluation establishes. It gives the discussion a clear evidence base without repeating the abstract or conclusion verbatim.

5

Discussion

This discussion paragraph interprets the aggregate evidence and separates direct observations from possible explanations. It connects the findings back to the motivating gap while making clear which mechanism questions remain unresolved.

This second discussion paragraph considers practical scope, counterexamples, and efficiency tradeoffs. It avoids turning a narrow benchmark result into a universal claim and identifies the conditions under which the conclusion should change.

6

Conclusion

This conclusion closes the paper by restating the supported finding, the contribution established by the experiments, and the most important scope condition. It is concise, does not introduce new evidence, and points to a concrete next step.

7

Limitations

This limitations paragraph states the dataset, model, language, measurement, and external-validity constraints directly. It explains why each boundary matters and avoids presenting future work as though it had already been tested.

References

Wrong Author. 2025. This reference-list entry contains words such as abstract, method, results, and conclusion but must never be selected as manuscript reference context.

A

Additional Analyses

This appendix paragraph records reproducibility details and additional analyses that support the main paper without changing its central claim. It is a legitimate Appendix match but must never be used as the Abstract or another body section.
"""


def fake_online_reference_alignment(
    _root, plan, source, *, section_titles, api_key, model
):
    """Deterministic Agent double; production never uses this selector."""
    del api_key, model
    assignments = []
    lines = source.splitlines()
    selected = next(
        (index for index, line in enumerate(lines, 1) if "This actual abstract states" in line),
        next((index for index, line in enumerate(lines, 1) if len(line.strip()) >= 60), 1),
    )
    for section_id, paragraphs in plan["sections"].items():
        for paragraph in paragraphs:
            assignments.append({
                "section_id": section_id,
                "paragraph_id": paragraph["id"],
                "start_line": selected,
                "end_line": selected,
                "rhetorical_match": "Test Agent selected the corresponding rhetorical paragraph.",
            })
    return align_plan_with_agent(
        plan,
        source,
        section_titles=section_titles,
        invoke=lambda _prompt: json.dumps({"assignments": assignments}),
    )

PLAN_CONTRACT = {
    "schema_version": "1.2",
    "approval_status": "approved",
    "paper_title": "Evidence Writing",
    "target": {"venue": "ACL 2027", "submission_content_pages": 8},
    "references": {
        "confirmed_at": "2026-08-19",
        "researcher_owned_logic": {
            "title": "Reference Structure Paper",
            "authors": "A. Researcher",
            "venue": "ACL 2026",
            "publication_key": "reference2026",
            "local_full_text": "researcher-profile/fulltext/txt/reference.txt",
        }
    },
    "paper_outline": [
        {
            "id": "abstract",
            "title": "Abstract",
            "reference_context": {
                "source_heading": "Abstract",
                "logic_summary_zh": "测试摘要的论证顺序。",
                "excerpts": [{"reference_paragraph_id": "R-A1", "start_line": 1, "end_line": 1, "text": "Verified abstract reference excerpt."}],
            },
            "paragraphs": [
                {"id": "A1", "plan_sentence": "Summarize the supported paper.", "rhetorical_role": "summary", "relation_to_previous": "opening", "relation_to_next": "prepares evidence", "artifact_refs": []}
            ],
        },
        {
            "id": "experiments",
            "title": "Experiments",
            "reference_context": {
                "source_heading": "Experiments",
                "logic_summary_zh": "测试实验部分的论证顺序。",
                "excerpts": [{"reference_paragraph_id": "R-E1", "start_line": 1, "end_line": 1, "text": "Verified experiments reference excerpt."}],
            },
            "paragraphs": [
                {"id": "E1", "plan_sentence": "Report the verified comparison.", "rhetorical_role": "evidence", "relation_to_previous": "follows summary", "relation_to_next": "prepares conclusion", "artifact_refs": ["T1"]}
            ],
        },
        {
            "id": "conclusion",
            "title": "Conclusion",
            "reference_context": {
                "source_heading": "Conclusion",
                "logic_summary_zh": "测试结论部分的论证顺序。",
                "excerpts": [{"reference_paragraph_id": "R-C1", "start_line": 1, "end_line": 1, "text": "Verified conclusion reference excerpt."}],
            },
            "paragraphs": [
                {"id": "C1", "plan_sentence": "Close with supported findings.", "rhetorical_role": "conclusion", "relation_to_previous": "synthesizes evidence", "relation_to_next": "closing", "artifact_refs": []}
            ],
        },
    ],
    "paper_artifacts": [
        {
            "id": "T1", "kind": "table", "label": "tab:main", "span": "two-column",
            "placement": "body", "section_id": "experiments", "introduced_after": "E1",
            "shell": {"caption": "Verified main comparison.", "column_labels": ["Method", "Score"]},
        }
    ],
    "result_requirements": [
        {
            "id": "R1", "artifact_id": "T1", "cell_ids": ["t1-score"],
            "any_of": ["results/main.json:rows.*"],
        }
    ],
}


def pipeline_files(*, venue=None):
    contract = json.loads(json.dumps(PLAN_CONTRACT))
    if venue is not None:
        contract["target"]["venue"] = venue
    plan = (
        "<html><head><title>Experiment Plan</title></head><body><h1>Evidence Writing</h1>"
        '<script type="application/json" id="experiment-plan-contract">'
        + json.dumps(contract)
        + "</script></body></html>"
    )
    results = (
        '<html><body><section data-artifact-id="T1"><table>'
        '<tr><th>Method</th><th>Score</th></tr><tr><td>Ours</td>'
        '<td data-target-id="t1-score" data-result-id="R1">91.0</td>'
        "</tr></table></section></body></html>"
    )
    return [
        ("PROFILE.html", PROFILE_HTML),
        ("03_EXPERIMENT_PLAN.html", plan),
        ("05_EXP_RESULT.html", results),
    ]


def evidence_archive():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("results/main.json", json.dumps({"rows": [{"method": "Ours", "score": 91.0}]}))
        archive.writestr("researcher-profile/publications.json", "[]")
        archive.writestr("researcher-profile/fulltext/txt/reference.txt", STRUCTURAL_REFERENCE_TEXT)
        archive.writestr("references/logic-reference.txt", STRUCTURAL_REFERENCE_TEXT)
    return buffer.getvalue()


def lightweight_profile_fixture(root, *_args, **_kwargs):
    profile_dir = root / "researcher-profile"
    text_dir = profile_dir / "fulltext/txt"
    text_dir.mkdir(parents=True, exist_ok=True)
    (text_dir / "author2025reference.txt").write_text(
        STRUCTURAL_REFERENCE_TEXT, encoding="utf-8"
    )
    (profile_dir / "PROFILE.html").write_text(
        '<section data-report-section="writing-style"><h2>Writing Style</h2>'
        '<p>Measured from three author-owned full papers. Use calibrated claims.</p></section>',
        encoding="utf-8",
    )
    (profile_dir / "publications.json").write_text('{"publications": []}\n', encoding="utf-8")
    author_reference = {
        "title": "Author-Owned Reference Paper",
        "authors": "Jane Researcher",
        "venue": "ACL 2025",
        "year": "2025",
        "url": "https://example.test/author-paper",
        "bibtex_key": "author2025reference",
        "fulltext_txt": "researcher-profile/fulltext/txt/author2025reference.txt",
        "bibtex": "@inproceedings{author2025reference,\n  title = {Author-Owned Reference Paper}\n}",
    }
    reference = _kwargs.get("structural_reference") or author_reference
    return {
        "mode": "author_fulltext_reference",
        "name": "Jane Researcher",
        "affiliation": "",
        "publication_count": 4,
        "writing_style_inferred": True,
        "representative_papers": [author_reference] * 4,
        "reference_paper": reference,
    }


def lightweight_structure_fixture(_root, contract, _source, _reference, **_kwargs):
    outline = []
    for section in contract["paper_outline"]:
        paragraphs = []
        for index, paragraph in enumerate(section["paragraphs"]):
            paragraphs.append({
                "id": paragraph["id"],
                "plan_sentence": paragraph["plan_sentence"],
                "rhetorical_role": "approved test role",
                "relation_to_previous": "opening" if index == 0 else "continues prior paragraph",
                "relation_to_next": "closing" if index == len(section["paragraphs"]) - 1 else "prepares next paragraph",
                "covers": [paragraph["id"]],
                "supports": paragraph.get("supports", []),
                "evidence": paragraph.get("evidence", []),
                "artifact_refs": paragraph.get("artifact_refs", []),
            })
        outline.append({
            "section_id": section.get("section_id") or section.get("id"), "title": section["title"],
            "section_role": "approved test section",
            "relation_to_previous": "opening", "relation_to_next": "continues",
            "length_share": 1 / len(contract["paper_outline"]),
            "reference_context": {
                "source_heading": section["title"],
                "logic_summary_zh": "测试参考结构。",
                "excerpts": [{
                    "reference_paragraph_id": "R1",
                    "start_line": 1,
                    "end_line": 1,
                    "text": "Verified reference excerpt.",
                }],
            },
            "paragraphs": paragraphs,
        })
    return {"structure_reference_analysis": {}, "paper_outline": outline}


def project_archive():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "results").mkdir()
        (root / "results/main.json").write_text(
            json.dumps({"rows": [{"method": "Ours", "score": 91.0}]})
        )
        (root / "researcher-profile/fulltext/txt").mkdir(parents=True)
        (root / "researcher-profile/PROFILE.html").write_text(PROFILE_HTML)
        (root / "researcher-profile/publications.json").write_text("[]")
        (root / "researcher-profile/fulltext/txt/ref.txt").write_text(
            STRUCTURAL_REFERENCE_TEXT
        )
        (root / "reports").mkdir()
        sources = dict(pipeline_files())
        contract = {
            **PLAN_CONTRACT,
            "references": {
                "confirmed_at": "2026-08-19",
                "researcher_owned_logic": {
                    **PLAN_CONTRACT["references"]["researcher_owned_logic"],
                    "local_full_text": "researcher-profile/fulltext/txt/ref.txt"
                }
            },
        }
        sources["03_EXPERIMENT_PLAN.html"] = (
            '<html><body><script id="experiment-plan-contract" type="application/json">'
            + json.dumps(contract)
            + "</script></body></html>"
        )
        (root / "reports/01_LIT_SURVEY.html").write_text("<html><body>Survey</body></html>")
        (root / "reports/02_IDEA_REPORT.html").write_text("<html><body>Ideas</body></html>")
        (root / "reports/04_RUN_PLAN.html").write_text("<html><body>Run plan</body></html>")
        for name in ("03_EXPERIMENT_PLAN.html", "05_EXP_RESULT.html"):
            (root / "reports" / name).write_text(sources[name])
        output = root / "project.zip"
        build_archive(root, output)
        return output.read_bytes()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class OnlineStudioTests(unittest.TestCase):
    def setUp(self):
        self.structure_patcher = patch.object(
            online, "_design_lightweight_structure_online",
            side_effect=lightweight_structure_fixture,
        )
        self.structure_patcher.start()

    def tearDown(self):
        self.structure_patcher.stop()
        with online.SESSIONS_LOCK:
            sessions = list(online.SESSIONS.values())
            online.SESSIONS.clear()
        for session in sessions:
            if session.process.poll() is None:
                session.process.terminate()
                session.process.wait(timeout=5)
        with online.ONBOARDING_JOBS_LOCK:
            online.ONBOARDING_JOBS.clear()

    def test_html_decoder_rejects_non_html_and_oversized_shape(self):
        payload = [{"name": "notes.txt", "data": base64.b64encode(b"x").decode()}]
        with self.assertRaisesRegex(online.OnlineStudioError, r"\.html"):
            online._decode_html_files(payload)

    def test_visible_text_excludes_scripts(self):
        text = online._source_text([("PROFILE.html", PROFILE_HTML)])
        self.assertIn("Concise, evidence-first prose.", text)
        self.assertNotIn("doNotIncludeThisSecret", text)

    def test_cancelled_gateway_response_does_not_emit_handler_traceback(self):
        class ClosedSocket:
            def write(self, _data):
                raise BrokenPipeError("browser closed online response")

        handler = object.__new__(online.Handler)
        handler.wfile = ClosedSocket()
        handler.close_connection = False
        handler._write_body(b"response")
        self.assertTrue(handler.close_connection)

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_shared_reference_matcher_scopes_abstract_before_introduction(self):
        plan = {
            "sections": {
                "abstract": [{
                    "id": "A1", "purpose": "Summarize the paper.",
                    "reference_lines": [1, 1], "artifacts": [],
                }]
            }
        }
        aligned = fake_online_reference_alignment(
            None,
            plan,
            STRUCTURAL_REFERENCE_TEXT,
            section_titles={"abstract": "Abstract"},
            api_key="test",
            model="test",
        )
        lines = STRUCTURAL_REFERENCE_TEXT.splitlines()
        matched = aligned["sections"]["abstract"][0]["reference_lines"]
        excerpt = " ".join(lines[matched[0] - 1 : matched[1]])
        self.assertIn("This actual abstract states the research problem", excerpt)
        self.assertNotIn("Wrong Author", excerpt)
        self.assertNotIn("appendix paragraph", excerpt)

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_shared_reference_matcher_handles_real_pdftotext_form_feeds(self):
        reference = (
            Path(__file__).resolve().parents[1]
            / "paper/reference_wang2025word.txt"
        ).read_text(encoding="utf-8", errors="replace")
        plan = {
            "sections": {
                "abstract": [{
                    "id": "A1", "purpose": "Abstract rhetorical arc.",
                    "reference_lines": [1, 1], "artifacts": [],
                }]
            }
        }
        aligned = align_plan_with_agent(
            plan,
            reference,
            section_titles={"abstract": "Abstract"},
            invoke=lambda _prompt: json.dumps({"assignments": [{
                "section_id": "abstract", "paragraph_id": "A1",
                "start_line": 15, "end_line": 44,
                "rhetorical_match": "Complete problem-method-result-implication abstract arc.",
            }]}),
        )
        matched = aligned["sections"]["abstract"][0]["reference_lines"]
        excerpt = " ".join(reference.splitlines()[matched[0] - 1 : matched[1]])
        self.assertEqual(matched, [15, 44])
        self.assertIn("Human readers can efficiently comprehend", excerpt)
        self.assertNotIn("In Proceedings of the 2021 Conference", excerpt)
        self.assertNotIn("Semantic reconstruction performance", excerpt)

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_agent_alignment_preserves_plan_decisions_in_one_call(self):
        plan = {
            "reference_file": "paper/reference.txt",
            "sections": {
                "abstract": [{
                    "id": "A1", "purpose": "Summarize the paper.",
                    "reference_lines": [1, 999], "artifacts": ["F1"],
                }],
                "conclusion": [{
                    "id": "C1", "purpose": "Close the paper.",
                    "reference_lines": [1, 999], "artifacts": [],
                }],
            },
        }
        valid = {
            "assignments": [
                {
                    "section_id": "abstract", "paragraph_id": "A1",
                    "start_line": 6, "end_line": 6,
                    "rhetorical_match": "Complete abstract rhetorical arc.",
                },
                {
                    "section_id": "conclusion", "paragraph_id": "C1",
                    "start_line": 62, "end_line": 62,
                    "rhetorical_match": "Concise supported conclusion and scope.",
                },
            ]
        }
        calls = []
        rematched = align_plan_with_agent(
            plan,
            STRUCTURAL_REFERENCE_TEXT,
            section_titles={"abstract": "Abstract", "conclusion": "Conclusion"},
            invoke=lambda prompt: calls.append(prompt) or json.dumps(valid),
        )
        expected = [6, 6]
        self.assertEqual(rematched["sections"]["abstract"][0]["reference_lines"], expected)
        self.assertEqual(rematched["sections"]["abstract"][0]["artifacts"], ["F1"])
        self.assertEqual(rematched["reference_alignment"]["method"], "agent-single-pass-v2")
        self.assertEqual(
            rematched["reference_alignment"]["transaction"],
            "whole-document-one-request-one-response",
        )
        self.assertEqual(
            rematched["reference_alignment"]["semantic_preprocessing"], "none"
        )
        self.assertEqual(len(calls), 1)

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_alignment_prompt_contains_the_whole_document_and_all_tasks(self):
        plan = {
            "sections": {
                "abstract": [{"id": "A1", "purpose": "Abstract arc."}],
                "conclusion": [{"id": "C1", "purpose": "Bounded close."}],
            }
        }
        source = "PDF-FIRST-SENTINEL\nbody\nPDF-LAST-SENTINEL"
        prompt = alignment_prompt(
            plan,
            source,
            section_titles={"abstract": "Abstract", "conclusion": "Conclusion"},
        )
        self.assertIn("PDF-FIRST-SENTINEL", prompt)
        self.assertIn("PDF-LAST-SENTINEL", prompt)
        self.assertIn('"paragraph_id": "A1"', prompt)
        self.assertIn('"paragraph_id": "C1"', prompt)
        self.assertIn("single call", prompt)
        self.assertIn("emit it once", prompt)

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_reference_matcher_has_no_rule_based_splitter(self):
        for obsolete_name in (
            "DIRECT_HEADINGS",
            "section_role",
            "heading_records",
            "section_bounds",
            "paragraph_ranges",
        ):
            self.assertFalse(hasattr(reference_matching, obsolete_name), obsolete_name)

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_local_alignment_hands_pdf_and_complete_task_to_agent_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "reference.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            calls = []

            def fake_run(command, **kwargs):
                calls.append((command, kwargs["input"]))
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text('{"assignments": []}', encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                patch.object(reference_matching.shutil, "which", return_value="/usr/bin/codex"),
                patch.object(reference_matching.subprocess, "run", side_effect=fake_run),
            ):
                response = reference_matching.codex_alignment_invoker(
                    root, reference_pdf=pdf
                )("COMPLETE-TASK-SENTINEL")
            self.assertEqual(response, '{"assignments": []}')
            self.assertEqual(len(calls), 1)
            self.assertIn("<reference_pdf>reference.pdf</reference_pdf>", calls[0][1])
            self.assertIn("COMPLETE-TASK-SENTINEL", calls[0][1])

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_online_alignment_sends_whole_document_in_one_api_request(self):
        source = "FIRST-PDF-LINE\nabstract text\nconclusion text\nLAST-PDF-LINE"
        plan = {
            "sections": {
                "abstract": [{"id": "A1", "purpose": "Abstract arc."}],
                "conclusion": [{"id": "C1", "purpose": "Bounded close."}],
            }
        }
        result = {
            "assignments": [
                {
                    "section_id": "abstract", "paragraph_id": "A1",
                    "source_section": "Abstract", "start_line": 2, "end_line": 2,
                    "rhetorical_match": "abstract",
                },
                {
                    "section_id": "conclusion", "paragraph_id": "C1",
                    "source_section": "Conclusion", "start_line": 3, "end_line": 3,
                    "rhetorical_match": "conclusion",
                },
            ]
        }
        response_body = json.dumps({
            "id": "one-request",
            "model": "deepseek-v4-pro",
            "usage": {},
            "choices": [{"message": {"content": json.dumps(result)}}],
        }).encode()
        requests = []

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse(response_body)

        self.reference_alignment_patcher.stop()
        try:
            with tempfile.TemporaryDirectory() as temporary, patch.object(
                online.urllib.request, "urlopen", side_effect=fake_urlopen
            ):
                aligned = online._align_reference_plan_online(
                    Path(temporary), plan, source,
                    section_titles={"abstract": "Abstract", "conclusion": "Conclusion"},
                    api_key="test-key", model="ignored-writing-model",
                )
        finally:
            self.reference_alignment_patcher.start()
        self.assertEqual(len(requests), 1)
        request_payload = json.loads(requests[0][0].data)
        user_prompt = request_payload["messages"][1]["content"]
        self.assertIn("FIRST-PDF-LINE", user_prompt)
        self.assertIn("LAST-PDF-LINE", user_prompt)
        self.assertIn('"paragraph_id": "A1"', user_prompt)
        self.assertIn('"paragraph_id": "C1"', user_prompt)
        self.assertEqual(
            aligned["reference_alignment"]["transaction"],
            "whole-document-one-request-one-response",
        )

    @unittest.skip("obsolete target-to-reference matching was removed")
    def test_packaged_single_pass_alignment_is_reused_exactly(self):
        target = {
            "sections": {
                "abstract": [{"id": "A1", "purpose": "Summarize.", "reference_lines": [1, 1]}]
            }
        }
        saved = {
            "sections": {
                "abstract": [{
                    "id": "A1",
                    "reference_lines": [6, 6],
                    "reference_rationale": "Agent selected the actual abstract.",
                    "reference_source_section": "Abstract",
                }]
            },
            "reference_alignment": {
                "method": "agent-single-pass-v2",
                "paper_sections": [{
                    "role": "abstract", "heading": "Abstract",
                    "start_line": 5, "end_line": 6,
                }],
            },
        }
        reused = reuse_validated_alignment(target, saved, STRUCTURAL_REFERENCE_TEXT)
        self.assertEqual(reused["sections"]["abstract"][0]["reference_lines"], [6, 6])
        self.assertEqual(
            reused["sections"]["abstract"][0]["reference_source_section"], "Abstract"
        )
        self.assertTrue(reused["reference_alignment"]["reused_from_package"])
        self.assertEqual(len(reused["reference_alignment"]["paper_sections"]), 1)

    def test_project_identity_comes_from_approved_plan(self):
        plan = pipeline_files()[1][1]
        self.assertEqual(
            online._project_identity(plan, PLAN_CONTRACT),
            ("Evidence Writing · ACL 2027", "Evidence Writing"),
        )

    def test_artifact_rows_recovers_a_leading_identifier_column_from_the_raw_header(self):
        # Regression: a real batch-writing run completed all 19 paragraphs
        # and compiled a full paper PDF, but Table 2 rendered with its own
        # scraped header row ("Method Swap Delete Insert Keyboard") printed
        # as if it were a data row, and the last declared column label
        # replaced by a meaningless "Value 5". 03's column_labels for this
        # table only names the four metric columns ("Swap", "Delete",
        # "Insert", "Keyboard") since every row already carries the method
        # name -- it never needs to declare that identifier column
        # separately. The old code always padded *missing* headers by
        # appending synthetic "Value N" placeholders at the end, silently
        # shifting every declared label one column out of alignment with
        # its data, and breaking the duplicate-header-row strip check
        # (which compared against the wrong, shifted header list).
        raw_rows = [
            ["Method", "Swap", "Delete", "Insert", "Keyboard"],
            ["Class-balanced random-budget augmentation", "0.8114", "0.8052", "0.7922", "0.7968"],
            ["Our method — Margin-Targeted Typo Augmentation (MTA)", "0.8327", "0.8275", "0.8017", "0.8107"],
        ]
        records, columns = online._artifact_rows(raw_rows, ["Swap", "Delete", "Insert", "Keyboard"])
        self.assertEqual(
            [column["label"] for column in columns],
            ["Method", "Swap", "Delete", "Insert", "Keyboard"],
        )
        self.assertEqual(len(records), 2, "the real header row must be stripped, not kept as data")
        self.assertEqual(records[0]["method"], "Class-balanced random-budget augmentation")
        self.assertEqual(records[0]["swap"], "0.8114")
        self.assertEqual(records[0]["keyboard"], "0.7968")

    def test_artifact_rows_preserves_positive_and_negative_condition_signs(self):
        raw_rows = [
            ["Behavior", "Multiplier 0", "Multiplier +1", "Multiplier -1"],
            ["Refusal", ".63", ".59", ".64"],
        ]

        records, columns = online._artifact_rows(raw_rows, raw_rows[0])

        self.assertEqual(
            [column["key"] for column in columns],
            ["behavior", "multiplier_0", "multiplier_plus_1", "multiplier_minus_1"],
        )
        self.assertEqual(records[0]["multiplier_plus_1"], ".59")
        self.assertEqual(records[0]["multiplier_minus_1"], ".64")

    def test_pipeline_sources_require_profile_plan_and_results(self):
        sources = online._canonical_pipeline_sources(pipeline_files())
        self.assertEqual(set(sources), {
            "PROFILE.html", "03_EXPERIMENT_PLAN.html", "05_EXP_RESULT.html",
        })
        with self.assertRaisesRegex(online.OnlineStudioError, "05_EXP_RESULT"):
            online._canonical_pipeline_sources(pipeline_files()[:2])

    def test_evidence_zip_rejects_path_traversal(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escape.json", "{}")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(online.OnlineStudioError, "不允许的路径"):
                online._extract_evidence_archive(buffer.getvalue(), Path(directory))

    def test_result_parser_survives_void_tags_inside_artifact(self):
        parser = online._ResultArtifactTables()
        parser.feed(
            '<section data-artifact-id="T1"><img src="preview.png">'
            '<table><tr><th>Method</th><th>Score</th></tr>'
            '<tr><td>Ours<br>final</td><td data-target-id="t1-score">91.0</td></tr>'
            '</table></section><section data-artifact-id="T2"></section>'
        )
        parser.close()
        self.assertEqual(parser.artifact_ids, ["T1", "T2"])
        self.assertEqual(parser.rows["T1"][1], ["Ours final", "91.0"])

    def test_required_artifact_never_receives_fabricated_placeholder_rows(self):
        contract = {**PLAN_CONTRACT, "_result_tables": {"T1": []}}
        sections = online._outline_sections(contract)
        with self.assertRaisesRegex(online.OnlineStudioError, "不会用占位值"):
            online._artifact_definitions(contract, sections)

    def test_online_materials_keep_empty_result_figure_as_non_data_placeholder(self):
        contract = {**PLAN_CONTRACT, "_result_tables": {"T1": []}}
        contract["paper_artifacts"] = [{
            **contract["paper_artifacts"][0],
            "id": "F3",
            "kind": "figure",
        }]
        contract["result_requirements"] = [{"artifact_id": "F3"}]
        contract["paper_outline"] = json.loads(json.dumps(PLAN_CONTRACT["paper_outline"]))
        contract["paper_outline"][0]["paragraphs"][0]["artifact_refs"] = ["F3"]
        sections = online._outline_sections(contract)
        figures, _tables, metrics = online._artifact_definitions(
            contract, sections, allow_empty_result_artifacts=True
        )
        self.assertEqual(figures["F3"]["kind"], "mechanism")
        self.assertEqual(figures["F3"]["result_keys"], [])
        self.assertNotIn("F3", metrics["artifacts"])

    def test_artifact_width_reads_expplan_shell_span(self):
        contract = json.loads(json.dumps(PLAN_CONTRACT))
        artifact = contract["paper_artifacts"][0]
        artifact.pop("span", None)
        artifact["shell"]["span"] = "double_column"
        contract["_result_tables"] = {
            "T1": [["Method", "Score"], ["Ours", "91.0"]]
        }
        sections = online._outline_sections(contract)

        _figures, tables, _metrics = online._artifact_definitions(contract, sections)

        self.assertEqual(tables["T1"]["width"], "two-column")

    def test_figure_axis_labels_survive_pipeline_scaffolding(self):
        contract = json.loads(json.dumps(PLAN_CONTRACT))
        artifact = contract["paper_artifacts"][0]
        artifact["kind"] = "figure"
        artifact["x_axis_label"] = "Behavior"
        artifact["shell"]["y_axis_label"] = "Target-answer probability"
        contract["_result_tables"] = {
            "T1": [["Behavior", "Score"], ["Refusal", ".86"]]
        }
        sections = online._outline_sections(contract)

        figures, _tables, _metrics = online._artifact_definitions(contract, sections)

        self.assertEqual(figures["T1"]["x_axis_label"], "Behavior")
        self.assertEqual(
            figures["T1"]["y_axis_label"], "Target-answer probability"
        )

    def test_source_figure_preserves_verified_asset_without_fake_metrics(self):
        contract = json.loads(json.dumps(PLAN_CONTRACT))
        artifact = contract["paper_artifacts"][0]
        artifact["kind"] = "figure"
        artifact["source_asset"] = "source/figures/F1.pdf"
        contract["result_requirements"] = []
        contract["_result_tables"] = {}
        sections = online._outline_sections(contract)

        figures, _tables, metrics = online._artifact_definitions(contract, sections)

        self.assertEqual(figures["T1"]["kind"], "source")
        self.assertEqual(
            figures["T1"]["source_asset"], "source/figures/F1.pdf"
        )
        self.assertNotIn("T1", metrics["artifacts"])

    def test_outline_preserves_compact_per_paragraph_reference_mapping(self):
        contract = json.loads(json.dumps(PLAN_CONTRACT))
        contract["paper_outline"][0]["paragraphs"][0]["reference_mapping"] = [
            {"source_paragraph_id": "R-A1", "source_text": "Must not enter config."}
        ]

        paragraph = online._outline_sections(contract)[0]["paragraphs"][0]

        self.assertEqual(paragraph["reference_paragraph_ids"], ["R-A1"])
        self.assertNotIn("reference_mapping", paragraph)

    def test_verified_survey_cards_seed_the_online_citation_bank(self):
        source = """
        <article class="card"><span class="verified">✅ 已验证</span>
          <h4><a href="https://aclanthology.org/D19-1131/">Intent Dataset</a></h4>
          <div class="who">Larson et al. · EMNLP 2019 · DOI 10.1/test</div>
        </article>
        <article class="card"><h4><a href="https://example.test/unverified">Skip</a></h4></article>
        """
        bibliography = online.verified_survey_bibliography(source)

        self.assertIn("@misc{survey2019d191131", bibliography)
        self.assertIn("https://aclanthology.org/D19-1131/", bibliography)
        self.assertIn("author = {Larson and others}", bibliography)
        self.assertNotIn("unverified", bibliography)

    def test_verified_survey_bibliography_prefers_full_machine_readable_authors(self):
        source = """
        <article class="card"
          data-authors="Larson, Stefan and Mahendran, Anish and Peper, Joseph">
          <span class="verified">✅ 已验证</span>
          <h4><a href="https://aclanthology.org/D19-1131/">Intent Dataset</a></h4>
          <div class="who">Larson et al. · EMNLP 2019</div>
        </article>
        """

        bibliography = online.verified_survey_bibliography(source)

        self.assertIn(
            "author = {Larson, Stefan and Mahendran, Anish and Peper, Joseph}",
            bibliography,
        )

    def test_verified_survey_bibliography_drops_non_ascii_ui_metadata_note(self):
        source = """
        <article class="card" data-authors="Larson, Stefan and Mahendran, Anish">
          <h4><a href="https://aclanthology.org/D19-1131/">Intent Dataset</a></h4>
          <div class="who">Larson et al. · EMNLP 2019 · 已验证</div>
        </article>
        """

        bibliography = online.verified_survey_bibliography(source)

        self.assertIn("author = {Larson, Stefan and Mahendran, Anish}", bibliography)
        self.assertNotIn("note =", bibliography)
        self.assertNotIn("已验证", bibliography)

    def test_verified_survey_bibliography_rejects_authorless_verified_card(self):
        source = """
        <article class="card"><span class="verified">✅ 已验证</span>
          <h4><a href="https://example.org/paper">Authorless Paper</a></h4>
          <div class="who">ACL 2025</div>
        </article>
        """

        with self.assertRaisesRegex(ValueError, "missing author metadata"):
            online.verified_survey_bibliography(source)

    def test_verified_survey_bibliography_preserves_compound_display_surnames(self):
        source = """
        <article class="card"><span class="verified">✅ 已验证</span>
          <h4><a href="https://example.org/paper">Two-author Paper</a></h4>
          <div class="who">Goyal &amp; Daumé III · EACL 2026</div>
        </article>
        """

        bibliography = online.verified_survey_bibliography(source)

        self.assertIn("author = {{Goyal} and {Daumé III}}", bibliography)

    def test_contract_accepts_unapproved_plan_but_rejects_incomplete_results(self):
        plan = pipeline_files()[1][1]
        pending = plan.replace('"approval_status": "approved"', '"approval_status": "pending"')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "results").mkdir()
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(pending)
            (root / "reports/05_EXP_RESULT.html").write_text(pipeline_files()[2][1])
            with patch.object(
                online.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ):
                contract = online._validated_upstream_contract(
                    root, pending, pipeline_files()[2][1]
                )
            self.assertEqual(contract["approval_status"], "pending")
        incomplete = pipeline_files()[2][1].replace(' data-target-id="t1-score"', "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "results").mkdir()
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(plan)
            (root / "reports/05_EXP_RESULT.html").write_text(incomplete)
            with self.assertRaisesRegex(online.OnlineStudioError, "尚未填满"):
                online._validated_upstream_contract(root, plan, incomplete)

    def test_evidence_packager_emits_only_supported_project_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "results/main.json").write_text("{}")
            (root / "researcher-profile/fulltext/txt").mkdir(parents=True)
            (root / "researcher-profile/PROFILE.html").write_text(PROFILE_HTML)
            (root / "researcher-profile/publications.json").write_text("[]")
            (root / "researcher-profile/fulltext/txt/ref.txt").write_text("reference")
            (root / "paper").mkdir()
            (root / "reports").mkdir()
            contract = {
                **PLAN_CONTRACT,
                "references": {
                    "confirmed_at": "2026-08-19",
                    "researcher_owned_logic": {
                        "local_full_text": "researcher-profile/fulltext/txt/ref.txt"
                    }
                },
            }
            for name in (
                "01_LIT_SURVEY.html", "02_IDEA_REPORT.html", "04_RUN_PLAN.html", "05_EXP_RESULT.html"
            ):
                (root / "reports" / name).write_text(f"<html><body>{name}</body></html>")
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(contract)
                + "</script>"
            )
            output = root / "bundle.zip"
            files = build_archive(root, output)
            self.assertEqual(
                files,
                [
                    "project-package.json",
                    "references/logic-reference.txt",
                    "reports/01_LIT_SURVEY.html",
                    "reports/02_IDEA_REPORT.html",
                    "reports/03_EXPERIMENT_PLAN.html",
                    "reports/04_RUN_PLAN.html",
                    "reports/05_EXP_RESULT.html",
                    "researcher-profile/PROFILE.html",
                    "researcher-profile/fulltext/txt/ref.txt",
                    "researcher-profile/publications.json",
                    "results/main.json",
                ],
            )
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(sorted(archive.namelist()), files)
                self.assertIn("researcher-profile/fulltext/txt/ref.txt", files)
                manifest = json.loads(archive.read("project-package.json"))
                self.assertEqual(manifest["schema_version"], "2.0")
                self.assertNotIn("references/structure-alignment.json", archive.namelist())

    def test_evidence_packager_includes_only_contract_selected_plotting_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "results/main.json").write_text("{}")
            (root / "results/stale.json").write_text("{}")
            (root / "paper/figsrc/example").mkdir(parents=True)
            (root / "paper/fig").mkdir(parents=True)
            for relative, content in {
                "paper/fig/make_figs.py": "--schema --figure --panel --metrics --pdf --png matplotlib.use(\"Agg\") validate_rendered_marks",
                "paper/figsrc/example/schema.json": "{}",
                "paper/figsrc/example/make_fixture.py": "print('fixture')",
                "paper/figsrc/example/fixture.json": "{}",
                "paper/figsrc/example/F2.pdf": "%PDF-test",
                "paper/figsrc/example/F2.png": "png",
            }.items():
                (root / relative).write_text(content)
            (root / "researcher-profile/fulltext/txt").mkdir(parents=True)
            (root / "researcher-profile/PROFILE.html").write_text(PROFILE_HTML)
            (root / "researcher-profile/publications.json").write_text("[]")
            (root / "researcher-profile/fulltext/txt/ref.txt").write_text("reference")
            (root / "reports").mkdir()
            plotting = {
                "source": "paper/fig/make_figs.py",
                "schema": "paper/figsrc/example/schema.json",
                "fixture_generator": "paper/figsrc/example/make_fixture.py",
                "fixture": "paper/figsrc/example/fixture.json",
                "pdf": "paper/figsrc/example/F2.pdf",
                "png": "paper/figsrc/example/F2.png",
                "panels": {},
            }
            contract = {
                **PLAN_CONTRACT,
                "references": {"confirmed_at": "2026-08-19", "researcher_owned_logic": {"local_full_text": "researcher-profile/fulltext/txt/ref.txt"}},
                "paper_artifacts": [
                    *PLAN_CONTRACT["paper_artifacts"],
                    {"id": "F2", "kind": "figure", "shell": {"plotting": plotting}},
                ],
            }
            for name in ("01_LIT_SURVEY.html", "02_IDEA_REPORT.html", "04_RUN_PLAN.html", "05_EXP_RESULT.html"):
                (root / "reports" / name).write_text(f"<html><body>{name}</body></html>")
            (root / "reports/03_EXPERIMENT_PLAN.html").write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(contract)
                + "</script>"
            )
            output = root / "bundle.zip"
            files = build_archive(root, output)
            self.assertIn("paper/fig/make_figs.py", files)
            self.assertIn("paper/figsrc/example/schema.json", files)
            self.assertIn("results/main.json", files)
            self.assertNotIn("results/stale.json", files)

    def test_online_latex_blocks_file_and_execution_primitives(self):
        with patch.object(paper_studio, "ONLINE_PROJECT_MODE", True):
            issues = paper_studio.online_latex_security_issues(
                r"Safe prose. \input{/etc/passwd} \csname input\endcsname ^^69"
            )
        self.assertIn(r"\input", issues)
        self.assertIn(r"\csname", issues)
        self.assertIn("TeX ^^ character encoding", issues)
        with patch.object(paper_studio, "ONLINE_PROJECT_MODE", True):
            self.assertEqual(
                paper_studio.online_latex_security_issues(
                    r"Evidence supports 91\% accuracy; see \cite{verified2026}."
                ),
                [],
            )

    def test_custom_outline_is_validated_before_scaffolding(self):
        sections = online._validated_sections(
            [
                {"title": "Abstract", "purpose": "Summarize only supported evidence."},
                {"title": "Evaluation Protocol", "purpose": "Define datasets, metrics, and reproducible settings."},
            ]
        )
        self.assertEqual([item[0] for item in sections], ["abstract", "evaluation_protocol"])
        with self.assertRaisesRegex(online.OnlineStudioError, "第一个"):
            online._validated_sections(
                [
                    {"title": "Introduction", "purpose": "Explain the paper motivation carefully."},
                    {"title": "Method", "purpose": "Explain the complete technical method."},
                ]
            )

    def test_local_signup_login_session_and_logout(self):
        password = "abc123"
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            with self.assertRaisesRegex(online.OnlineStudioError, "6–1024"):
                online.create_local_user("short@example.org", "abc12")
            user = online.create_local_user("Researcher@Example.org", password)
            self.assertEqual(user["email"], "researcher@example.org")
            logged_in = online.authenticate_local_user(
                "researcher@example.org", password
            )
            self.assertEqual(logged_in["id"], user["id"])
            with self.assertRaisesRegex(online.OnlineStudioError, "不正确"):
                online.authenticate_local_user(
                    "researcher@example.org", "wrong-password-value"
                )
            token = online.create_auth_session(user["id"])
            header = f"{online.AUTH_COOKIE_NAME}={token}"
            self.assertEqual(online.authenticated_user(header)["id"], user["id"])
            online.revoke_auth_session(header)
            self.assertIsNone(online.authenticated_user(header))
            self.assertNotIn(
                password.encode(),
                (Path(directory) / "auth.sqlite3").read_bytes(),
            )

    def test_onboarding_runs_in_background_and_reports_real_progress(self):
        def fake_create(_payload, *, user_id, progress):
            self.assertEqual(user_id, "user-1")
            progress("reference_analysis", "正在逐段匹配…", 38)
            return SimpleNamespace(session_id="ready-session")

        with patch.object(online, "create_session", side_effect=fake_create):
            job = online.start_onboarding_job({"mode": "materials"}, user_id="user-1")
            deadline = time.time() + 2
            while job.status == "running" and time.time() < deadline:
                time.sleep(0.01)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.session_id, "ready-session")
        self.assertIs(online.onboarding_job(job.job_id, user_id="user-1"), job)
        self.assertIsNone(online.onboarding_job(job.job_id, user_id="other-user"))

    def test_logout_closes_the_researchers_own_writing_session(self):
        # Regression: a session's spawned paper_studio.server child process
        # previously only ever stopped via the four-hour idle reaper, so a
        # researcher who logged out immediately still left a live subprocess
        # running in the shared per-Worker-version container for hours,
        # starving concurrent researchers' memory. close_session() is what
        # the edge Worker's logout handler now calls before deleting the
        # auth row (POST /api/online/session/close, proxyIdentified in
        # deploy/cloudflare/index.ts).
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        )
        try:
            session = online.Session(
                "close-me", "user-1", Path("/tmp/unused"), "openai", "gpt-5-nano",
                process, 0,
            )
            with online.SESSIONS_LOCK:
                online.SESSIONS["close-me"] = session
            header = f"{online.COOKIE_NAME}=close-me"

            # A foreign user_id must not be able to close someone else's session.
            self.assertFalse(online.close_session(header, user_id="not-the-owner"))
            self.assertIsNone(process.poll())
            with online.SESSIONS_LOCK:
                self.assertIn("close-me", online.SESSIONS)

            self.assertTrue(online.close_session(header, user_id="user-1"))
            process.wait(timeout=5)
            self.assertIsNotNone(process.poll())
            with online.SESSIONS_LOCK:
                self.assertNotIn("close-me", online.SESSIONS)

            # Idempotent: closing an already-closed/unknown session is a no-op.
            self.assertFalse(online.close_session(header, user_id="user-1"))
        finally:
            with online.SESSIONS_LOCK:
                online.SESSIONS.pop("close-me", None)
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def test_gateway_logout_handler_closes_writer_before_revoking_auth(self):
        source = Path(online.__file__).read_text(encoding="utf-8")
        branch = source[source.index('elif path == "/api/auth/logout":') :]
        branch = branch[: branch.index('elif path == "/api/online/session/close":')]
        self.assertLess(branch.index("close_session("), branch.index("revoke_auth_session("))
        self.assertIn("self._clear_paper_session_cookie()", branch)

    def test_authenticated_owner_recovers_live_writer_without_writer_cookie(self):
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        )
        try:
            session = online.Session(
                "recover-me", "user-1", Path("/tmp/unused"), "deepseek",
                "deepseek-v4-flash", process, 0,
            )
            with online.SESSIONS_LOCK:
                online.SESSIONS[session.session_id] = session
            auth_only_header = f"{online.AUTH_COOKIE_NAME}=new-browser-login"
            self.assertIs(
                online._session_from_cookie(auth_only_header, user_id="user-1"),
                session,
            )
            self.assertIsNone(
                online._session_from_cookie(auth_only_header, user_id="other-user")
            )
            self.assertTrue(online.close_session(None, user_id="user-1"))
            process.wait(timeout=5)
        finally:
            with online.SESSIONS_LOCK:
                online.SESSIONS.pop("recover-me", None)
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def test_gateway_restart_recovers_cookie_bound_project_from_disk(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            session_id = "durable-session"
            root = online.user_project_root("user-1") / hashlib.sha256(
                session_id.encode("utf-8")
            ).hexdigest()
            (root / "paper").mkdir(parents=True)
            (root / "paper/paper_studio.json").write_text("{}")
            process = MagicMock()
            process.poll.return_value = None
            with patch.object(
                online, "shared_deepseek_api_key", return_value="server-key"
            ), patch.object(
                online, "_start_worker", return_value=(process, 61234)
            ) as start:
                recovered = online._session_from_cookie(
                    f"{online.COOKIE_NAME}={session_id}", user_id="user-1"
                )
            self.assertIsNotNone(recovered)
            self.assertEqual(recovered.root, root)
            self.assertEqual(recovered.port, 61234)
            start.assert_called_once()

    def test_google_authorization_code_callback_creates_authenticated_user(self):
        opener = urllib.request.build_opener(_NoRedirect())
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            server = online.OnlineServer(("127.0.0.1", 0), online.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            environment = {
                "GOOGLE_OAUTH_CLIENT_ID": "test-client.apps.googleusercontent.com",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
                "ONLINE_STUDIO_PUBLIC_URL": base,
            }
            try:
                with patch.dict(os.environ, environment, clear=False):
                    with self.assertRaises(urllib.error.HTTPError) as start_error:
                        opener.open(base + "/auth/google/start")
                    self.assertEqual(start_error.exception.code, 302)
                    location = start_error.exception.headers["Location"]
                    query = urllib.parse.parse_qs(
                        urllib.parse.urlparse(location).query
                    )
                    state = query["state"][0]
                    nonce = query["nonce"][0]
                    state_cookie = start_error.exception.headers["Set-Cookie"].split(
                        ";", 1
                    )[0]
                    callback = (
                        base
                        + "/auth/google/callback?"
                        + urllib.parse.urlencode({"state": state, "code": "test-code"})
                    )
                    request = urllib.request.Request(
                        callback, headers={"Cookie": state_cookie}
                    )
                    with patch.object(
                        online, "exchange_google_code", return_value="signed-id-token"
                    ), patch.object(
                        online,
                        "verify_google_id_token",
                        return_value={
                            "sub": "google-subject-123",
                            "email": "google-user@example.org",
                            "email_verified": True,
                            "nonce": nonce,
                        },
                    ):
                        with self.assertRaises(urllib.error.HTTPError) as callback_error:
                            opener.open(request)
                    self.assertEqual(callback_error.exception.code, 302)
                    cookies = callback_error.exception.headers.get_all("Set-Cookie")
                    auth_cookie = next(
                        value.split(";", 1)[0]
                        for value in cookies
                        if value.startswith(online.AUTH_COOKIE_NAME + "=")
                    )
                    user = online.authenticated_user(auth_cookie)
                    self.assertEqual(user["email"], "google-user@example.org")
                    self.assertEqual(user["provider"], "google")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_scaffold_is_a_valid_paper_studio_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(
                    root, files=pipeline_files(), archive=evidence_archive()
                )
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(r"\title{Evidence Writing}", (root / "paper/main.tex").read_text())
            self.assertIn(
                r"\input{sections/bibliography}", (root / "paper/main.tex").read_text()
            )
            self.assertTrue((root / "paper/.outline-approved").is_file())
            config = json.loads((root / "paper/paper_studio.json").read_text())
            plan = {"sections": {
                item["id"]: item["paragraphs"] for item in config["sections"]
            }}
            self.assertEqual(set(plan["sections"]), {"abstract", "experiments", "conclusion"})
            self.assertEqual(config["table_order"], ["T1"])
            self.assertEqual(config["tables"]["T1"]["label"], "tab:main")
            # Regression: a real full-draft batch run completed all 19
            # paragraphs, then failed at the final table-materialization step
            # with "表格 Prompt 含未知行：保持 05 的已验证顺序" -- the
            # scaffolder hardcoded that phrase as the row directive, but
            # paper_studio's row-directive parser (default_table_prompt /
            # its "keep everything" branch) only recognizes the literal
            # keywords "source"/"all"/"保持 results/ 顺序"/"全部", so it
            # misread the phrase as a literal (unknown) row name and failed
            # every online project's final materialization step.
            self.assertEqual(config["tables"]["T1"]["prompt"]["rows"], "source")
            # Regression: the same materialization step then failed a second
            # time with "最优值仅支持 none、max 或 min。" -- the scaffolder
            # also hardcoded a "best_values" phrase
            # ("仅按 03 指定的 metric direction 标记") that the same parser's
            # best-value directive never recognizes, and no per-column
            # metric direction is actually read from "03" to derive a real
            # one, so it must default to the verified-safe "none".
            self.assertEqual(config["tables"]["T1"]["prompt"]["best_values"], "none")
            self.assertEqual(config["project"]["target"]["venue"], "ACL 2027")
            self.assertEqual(
                config["project"]["reference_paper"]["title"],
                "Reference Structure Paper",
            )
            self.assertEqual(
                config["project"]["decision_source"],
                "reports/03_EXPERIMENT_PLAN.html",
            )

    def test_lightweight_scaffold_is_a_valid_paper_studio_project(self):
        # Regression coverage for the no-GitHub-repo onboarding path: a
        # researcher who never ran package.py, has no approved 03/05
        # contract, no RESULTS_LEDGER -- just a required Scholar profile page,
        # a project brief, and result material. This must still produce a
        # project research_avatar.paper_studio.server accepts as valid,
        # same bar as the full pipeline's scaffold.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scholar_html = [
                (
                    "scholar.html",
                    "<html><body><h1>Jane Researcher</h1>"
                    "<div>Prior work on margin-targeted augmentation.</div>"
                    "</body></html>",
                )
            ]
            project_brief = [
                (
                    "project.md",
                    "# Project\nTypo robustness in intent classification is the research problem.",
                )
            ]
            results = {
                "caption": "Primary accuracy comparison.",
                "columns": [
                    {"key": "method", "label": "Method"},
                    {"key": "accuracy", "label": "Accuracy"},
                ],
                "rows": [
                    {"method": "Baseline", "accuracy": "81.2"},
                    {"method": "Ours", "accuracy": "84.5"},
                ],
            }
            with patch.object(
                online,
                "_write_lightweight_researcher_profile",
                side_effect=lightweight_profile_fixture,
            ):
                online._write_lightweight_workspace(
                    root,
                    venue="ACL 2027",
                    project_name="Margin Targeted Augmentation",
                    title="Margin-Targeted Augmentation for Robust Intent Classification",
                    scholar_files=scholar_html,
                    project_brief_files=project_brief,
                    results_files=[("results.json", json.dumps(results))],
                    reference_paper_files=[
                        ("uploaded-reference.txt", "# Uploaded Model Reference\n" + STRUCTURAL_REFERENCE_TEXT)
                    ],
                    api_key="test-key",
                    model="test-model",
                )
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            main_tex = (root / "paper/main.tex").read_text()
            self.assertIn(
                r"\title{Margin-Targeted Augmentation for Robust Intent Classification}",
                main_tex,
            )
            self.assertIn(r"\input{sections/bibliography}", main_tex)
            self.assertLess(main_tex.index(r"\maketitle"), main_tex.index(r"\begin{abstract}"))
            self.assertLess(
                main_tex.index(r"\begin{abstract}"),
                main_tex.index(r"\input{sections/introduction}"),
            )
            config = json.loads((root / "paper/paper_studio.json").read_text())
            plan = {"sections": {
                item["id"]: item["paragraphs"] for item in config["sections"]
            }}
            self.assertEqual(
                set(plan["sections"]),
                {
                    "abstract", "introduction", "related_work", "method",
                    "experiments", "discussion", "conclusion",
                },
            )
            self.assertEqual(plan["sections"]["experiments"][0]["artifacts"], [])
            self.assertEqual(plan["sections"]["introduction"][0]["artifacts"], ["F1"])
            self.assertEqual(plan["sections"]["experiments"][1]["artifacts"], ["T1", "F2"])
            self.assertEqual(plan["sections"]["discussion"][0]["artifacts"], ["T1", "F2"])
            self.assertIn(
                "cite the bound result table and data figure",
                plan["sections"]["discussion"][0]["purpose"],
            )
            self.assertEqual(sum(map(len, plan["sections"].values())), 19)
            self.assertEqual(config["table_order"], ["T1"])
            self.assertEqual(config["figure_order"], ["F1", "F2"])
            self.assertEqual(
                next(item for item in config["sections"] if item["id"] == "experiments")["start_label"],
                "sec:experiments",
            )
            self.assertEqual(config["figures"]["F1"]["kind"], "mechanism")
            self.assertEqual(config["figures"]["F1"]["source_sections"], ["introduction"])
            self.assertEqual(config["figures"]["F2"]["kind"], "data")
            self.assertEqual(config["figures"]["F2"]["phase"], 1)
            self.assertEqual(config["figures"]["F2"]["panels"][0]["id"], "a")
            self.assertEqual(config["tables"]["T1"]["phase"], 1)
            metrics = json.loads((root / "paper/metrics.json").read_text())
            self.assertEqual(
                metrics["lightweight_results"]["rows"],
                [
                    {"method": "Baseline", "accuracy": "81.2"},
                    {"method": "Ours", "accuracy": "84.5"},
                ],
            )
            reference_text = (root / "paper/uploaded_sources.txt").read_text()
            self.assertIn("Jane Researcher", reference_text)
            self.assertIn("Typo robustness", reference_text)
            self.assertEqual(
                config["project"]["reference_paper"]["title"],
                "Uploaded Model Reference",
            )
            self.assertNotIn("reference", config["paths"])
            self.assertNotIn("reference_file", plan)
            bibliography = (root / "paper/references.bib").read_text()
            self.assertIn("author2025reference", bibliography)
            self.assertNotIn("uploadedstructuralreference", bibliography)
            self.assertEqual(
                metrics["lightweight_project"]["structural_reference_file"],
                "uploaded-reference.txt",
            )
            self.assertIn(
                "Uploaded Model Reference",
                (root / "uploaded-evidence/reference/structural-reference.txt").read_text(),
            )
            self.assertEqual(
                metrics["lightweight_project"]["citation_policy"],
                "verified_bibliography_with_required_audit",
            )
            personalization = metrics["lightweight_project"]["personalization"]
            self.assertEqual(personalization["mode"], "author_fulltext_reference")
            self.assertTrue(personalization["writing_style_inferred"])
            profile = (root / "researcher-profile/PROFILE.html").read_text()
            self.assertIn('data-report-section="writing-style"', profile)
            self.assertIn("Measured from three author-owned full papers", profile)
            self.assertTrue((root / "researcher-profile/publications.json").is_file())

    def test_lightweight_scaffold_requires_exactly_one_structural_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                online.OnlineStudioError,
                "请上传一篇完整的结构参考论文",
            ):
                online._write_lightweight_workspace(
                    Path(directory),
                    venue="ACL 2027",
                    project_name="Reference required",
                    title="Reference Required",
                    scholar_files=[(
                        "scholar.html",
                        '<html><div id="gsc_prf_in">Researcher</div></html>',
                    )],
                    project_brief_files=[("project.md", "Complete project brief.")],
                    results_files=[("results.json", '{"rows": []}')],
                    reference_paper_files=None,
                    api_key="test-key",
                    model="deepseek-v4-flash",
                )

    def test_materials_scaffold_adds_model_placeholder_and_python_result_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = {
                "caption": "Accuracy by model variant.",
                "columns": [
                    {"key": "model", "label": "Model"},
                    {"key": "accuracy", "label": "Accuracy"},
                ],
                "rows": [
                    {"model": "Base encoder", "accuracy": 0.81},
                    {"model": "Gated residual encoder", "accuracy": 0.84},
                ],
            }
            with patch.object(
                online,
                "_write_lightweight_researcher_profile",
                side_effect=lightweight_profile_fixture,
            ):
                online._write_lightweight_workspace(
                    root,
                    venue="ACL 2027",
                    project_name="Gated Residual Encoder",
                    title="A Gated Residual Encoder for Robust Classification",
                    scholar_files=[("scholar.html", "<html><body>Jane Researcher</body></html>")],
                    project_brief_files=[(
                        "overview.md",
                        "We improve the classifier architecture with a gated residual fusion module.",
                    )],
                    results_files=[("results.json", json.dumps(results))],
                    reference_paper_files=[(
                        "reference.txt",
                        "# Uploaded Architecture Paper\n" + STRUCTURAL_REFERENCE_TEXT,
                    )],
                    api_key="test-key",
                    model="deepseek-v4-flash",
                )
            config = json.loads((root / "paper/paper_studio.json").read_text())
            self.assertEqual(config["figure_order"], ["F1", "F2", "F3"])
            self.assertEqual(config["figures"]["F1"]["kind"], "mechanism")
            self.assertEqual(config["figures"]["F1"]["source_sections"], ["introduction"])
            self.assertEqual(config["figures"]["F2"]["kind"], "mechanism")
            self.assertEqual(config["figures"]["F3"]["kind"], "data")
            self.assertEqual(config["table_order"], ["T1"])
            method = next(item for item in config["sections"] if item["id"] == "method")
            self.assertIn("F2", [artifact for p in method["paragraphs"] for artifact in p["artifacts"]])
            model_paragraphs = [
                p["id"] for p in method["paragraphs"] if "F2" in p["artifacts"]
            ]
            self.assertEqual(
                config["figures"]["F2"]["generation_requires_paragraphs"],
                {"method": model_paragraphs},
            )

    def test_lightweight_nested_aggregate_results_become_a_provenance_bound_grid(self):
        payload = {
            "status": "PASS",
            "aggregate": {
                "baseline": {"clean": 0.91, "noisy_mean": 0.79, "notes": "control"},
                "ours": {"clean": 0.92, "noisy_mean": 0.84, "notes": "method"},
            },
            "elapsed_seconds": 12.0,
        }
        caption, columns, rows, path = online._infer_results_records(
            "main_results.json", payload
        )
        self.assertEqual(path, "aggregate")
        self.assertEqual(
            columns,
            [
                {"key": "condition", "label": "Condition"},
                {"key": "clean", "label": "Clean"},
                {"key": "noisy_mean", "label": "Noisy Mean"},
            ],
        )
        self.assertEqual(rows[1], {"condition": "ours", "clean": 0.92, "noisy_mean": 0.84})
        self.assertEqual(
            caption,
            "Clean and Noisy Mean across experimental conditions.",
        )

        qualified = {**payload, "config": {"intent_count": 20, "severity": 0.45, "augmentation_budget_fraction": 0.25}}
        qualified_caption, _columns, _rows, _path = online._infer_results_records(
            "main_results.json", qualified
        )
        self.assertIn("20-class scope; severity 0.45; 25% budget", qualified_caption)

    def test_lightweight_approved_plan_preserves_all_contract_artifacts(self):
        contract = json.loads(json.dumps(PLAN_CONTRACT))
        contract["paper_outline"][1]["paragraphs"][0]["artifact_refs"] = [
            "F1", "T1", "F2"
        ]
        contract["paper_artifacts"] = [
            {
                "id": "F1", "kind": "figure", "label": "fig:mechanism",
                "span": "single_column", "section_id": "experiments",
                "introduced_after": "E1",
                "shell": {
                    "data_driven": False,
                    "caption": "A conceptual mechanism that remains a placeholder online.",
                    "panels": ["mechanism"],
                },
            },
            *contract["paper_artifacts"],
            {
                "id": "F2", "kind": "figure", "label": "fig:confirmation",
                "span": "single_column", "section_id": "experiments",
                "introduced_after": "E1",
                "shell": {
                    "data_driven": True,
                    "caption": "Confirmation gains with paired intervals.",
                    "panels": ["confirmation"],
                },
            },
        ]
        contract["result_requirements"].append({
            "id": "R2", "artifact_id": "F2", "cell_ids": ["f2-00"],
            "any_of": ["results.json:F2.confirmation"],
        })
        contract["result_requirements"].append({
            "id": "R3", "artifact_id": "F2", "cell_ids": ["f2-00"],
            "any_of": ["results/experiment/studio_metrics.json:F2.confirmation"],
        })
        plan_html = (
            '<html><body><h1>Approved plan</h1><script type="application/json" '
            'id="experiment-plan-contract">'
            + json.dumps(contract)
            + "</script></body></html>"
        )
        extracted_plan = online._extract_document_text(
            "03_EXPERIMENT_PLAN.html", plan_html.encode()
        )
        self.assertIn("<experiment-plan-contract>", extracted_plan)
        results = {
            "table": {
                "T1": {"studio_rows": [{"method": "Ours", "score": 0.91}]}
            },
            "figure": {
                "F2": {
                    "confirmation": {
                        "categories": ["Setting A", "Setting B"],
                        "series": [{
                            "name": "Gain", "values": [0.02, 0.03],
                            "ci_low": [0.01, 0.02], "ci_high": [0.03, 0.04],
                        }],
                    }
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                online,
                "_write_lightweight_researcher_profile",
                side_effect=lightweight_profile_fixture,
            ):
                online._write_lightweight_workspace(
                    root,
                    venue="ACL 2027",
                    project_name="Contract project",
                    title="Contract-Grounded Paper",
                    scholar_files=[("scholar.html", "<html><body>Researcher.</body></html>")],
                    project_brief_files=[("03_EXPERIMENT_PLAN.html", extracted_plan)],
                    results_files=[("studio_metrics.json", json.dumps(results))],
                    reference_paper_files=[(
                        "reference.txt",
                        "# Required Structural Reference\n" + STRUCTURAL_REFERENCE_TEXT,
                    )],
                    api_key="test-key",
                    model="test-model",
                )
            config = json.loads((root / "paper/paper_studio.json").read_text())
            metrics = json.loads((root / "paper/metrics.json").read_text())
            plan = {"sections": {
                item["id"]: item["paragraphs"] for item in config["sections"]
            }}
            self.assertEqual(config["figure_order"], ["F1", "F2"])
            self.assertEqual(config["table_order"], ["T1"])
            self.assertEqual(config["figures"]["F1"]["kind"], "mechanism")
            self.assertEqual(config["figures"]["F2"]["kind"], "data")
            self.assertEqual(config["figures"]["F2"]["label"], "fig:confirmation")
            self.assertEqual(config["figures"]["F2"]["panels"][0]["id"], "confirmation")
            self.assertEqual(
                config["figures"]["F2"]["data_grid"]["columns"][0]["label"],
                "Setting",
            )
            self.assertEqual(config["tables"]["T1"]["label"], "tab:main")
            self.assertEqual(
                plan["sections"]["experiments"][0]["artifacts"],
                ["F1", "T1", "F2"],
            )
            self.assertEqual(metrics["artifacts"]["F2"]["rows"][0]["gain"], "0.02")
            self.assertTrue(metrics["lightweight_project"]["approved_plan_contract"])
            self.assertTrue((root / "reports/03_EXPERIMENT_PLAN.html").is_file())
            self.assertTrue((root / "uploaded-evidence/results/studio_metrics.json").is_file())
            self.assertEqual(
                (root / "results/experiment/studio_metrics.json").read_text(),
                json.dumps(results),
            )

    def test_lightweight_result_prompt_summary_keeps_headlines_but_bounds_raw_runs(self):
        summary = online._result_prompt_summary({
            "headline": {"gain": 0.01675, "interval": [0.013, 0.021]},
            "per_seed": {str(index): {"large": list(range(100))} for index in range(10)},
            "selected_examples": [{"text": "sample"}] * 400,
        })
        self.assertEqual(summary["headline"]["gain"], 0.01675)
        self.assertEqual(summary["per_seed"]["count"], 10)
        self.assertEqual(summary["selected_examples"]["count"], 400)
        self.assertNotIn("sample", json.dumps(summary))

        audited = online._result_prompt_summary({
            "selected_examples_audit": [
                {"edit_count": 0}, {"edit_count": 2}, {"edit_count": 0}
            ]
        })
        self.assertEqual(
            audited["selected_examples_audit"]["zero_value_audit"]["edit_count"],
            {"observed": 3, "zero": 2},
        )

    def test_lightweight_nested_result_inference_rejects_ambiguous_numbers(self):
        self.assertEqual(
            online._infer_results_records(
                "metadata.json",
                {"runs": {"one": {"elapsed": 1.0}, "two": {"elapsed": 2.0}}},
            ),
            ("", [], [], ""),
        )

    def test_lightweight_profile_reuses_canonical_scholar_metadata_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scholar_html = (
                Path(__file__).resolve().parents[1]
                / "inputs/google-scholar/example.html"
            ).read_text(encoding="utf-8")
            from research_avatar.tools.scholar_profile import parse_html
            publications = parse_html(scholar_html)["publications"]

            def fake_acquire(target_root, _publications, **_kwargs):
                self.assertEqual(len(_publications), len(publications))
                text_dir = target_root / "researcher-profile/fulltext/txt"
                text_dir.mkdir(parents=True, exist_ok=True)
                selected = []
                for index, publication in enumerate(publications[:4], 1):
                    key = f"author{index}"
                    (text_dir / f"{key}.txt").write_text("Full paper text.\n" * 80)
                    selected.append({
                        **publication,
                        "bibtex_key": key,
                        "fulltext_txt": f"researcher-profile/fulltext/txt/{key}.txt",
                    })
                return selected

            style = (
                "Lead abstracts through problem, method, evidence, and conclusion. "
                "Use role-specific introduction paragraphs and calibrated result claims. "
                "Do not copy wording from the reference papers."
            )
            with patch.object(online, "_acquire_author_fulltexts", side_effect=fake_acquire), patch.object(
                online, "_summarize_author_writing_style",
                return_value={"reference": fake_acquire(root, publications)[0], "selection_reason": "Closest argumentative logic for the target study.", "writing_style": style},
            ):
                summary = online._write_lightweight_researcher_profile(
                    root,
                    scholar_html,
                    venue="ACL 2027",
                    project_text="typoglycemia robustness",
                    api_key="test-key",
                    model="test-model",
                )
            self.assertEqual(summary["name"], "Lang Gao")
            self.assertEqual(summary["publication_count"], 19)
            self.assertEqual(len(summary["representative_papers"]), 4)
            self.assertTrue(summary["writing_style_inferred"])
            profile = (root / "researcher-profile/PROFILE.html").read_text()
            self.assertIn("Lang Gao", profile)
            self.assertIn("Lead abstracts through problem", profile)
            self.assertNotIn("Scholar-listed interests", profile)

    def test_author_style_agent_receives_each_selected_full_paper_not_just_its_opening(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text_dir = root / "researcher-profile/fulltext/txt"
            text_dir.mkdir(parents=True)
            (root / "paper").mkdir()
            papers = []
            endings = []
            for index in range(1, 4):
                ending = f"UNIQUE_END_OF_AUTHOR_PAPER_{index}"
                endings.append(ending)
                text = (f"Paper {index} body sentence.\n" * 900) + ending
                path = text_dir / f"paper{index}.txt"
                path.write_text(text, encoding="utf-8")
                papers.append(
                    {
                        "title": f"Author paper {index}",
                        "fulltext_txt": str(path.relative_to(root)),
                    }
                )
            response = MagicMock()
            response.read.return_value = json.dumps(
                {
                    "id": "style-response",
                    "model": "test-model",
                    "usage": {},
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({
                                    "selected_reference_index": 1,
                                    "selection_reason": "Its argumentative progression most closely matches the target project.",
                                    "writing_style": "Observed writing guide. " * 20,
                                })
                            }
                        }
                    ],
                }
            ).encode()
            response.__enter__.return_value = response
            with patch.object(online.urllib.request, "urlopen", return_value=response) as call:
                online._summarize_author_writing_style(
                    root, papers, api_key="test-key", model="test-model",
                    project_text="target project", venue="ACL 2027",
                )
            request = call.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            supplied = payload["messages"][1]["content"]
            for ending in endings:
                self.assertIn(ending, supplied)

    def test_lightweight_document_upload_extracts_common_material_formats(self):
        self.assertIn("Project method", online._extract_document_text("brief.md", b"# Project method"))
        self.assertIn("value", online._extract_document_text("results.json", b'{"value": 3}'))
        self.assertEqual(
            online._extract_document_text("notes.html", b"<p>Visible evidence</p>"),
            "Visible evidence",
        )
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(
                "word/document.xml",
                '<?xml version="1.0"?><w:document xmlns:w="urn:test"><w:body>'
                '<w:p><w:r><w:t>DOCX project description</w:t></w:r></w:p>'
                '</w:body></w:document>',
            )
        self.assertIn(
            "DOCX project description",
            online._extract_document_text("brief.docx", stream.getvalue()),
        )

    def test_pdf_layout_text_is_semantically_ordered_by_deepseek(self):
        transcript = (
            "Paper title\n\nAbstract\n\nAbstract paragraph.\n\n"
            "1 Introduction\n\nFirst paragraph.\n\nSecond paragraph. " * 8
        )
        layout_text = ("Left column text                 Right column text\n" * 12).encode()
        extracted = MagicMock(returncode=0, stdout=layout_text, stderr=b"")
        response = MagicMock()
        response.read.return_value = json.dumps({
            "choices": [{"message": {"content": transcript}}],
        }).encode()
        response.__enter__.return_value = response
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test-key", "DEEPSEEK_PDF_EXTRACTION_MODEL": "deepseek-test"},
        ), patch.object(online.urllib.request, "urlopen", return_value=response) as call, patch.object(
            online.subprocess, "run", return_value=extracted
        ) as local_extract, patch.object(online.shutil, "which", return_value="/usr/bin/pdftotext"):
            text = online._extract_document_text("reference.pdf", b"%PDF-test")

        command = local_extract.call_args.args[0]
        self.assertEqual(command[:2], ["/usr/bin/pdftotext", "-layout"])
        self.assertEqual(command[-1], "-")
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "deepseek-test")
        self.assertIn(layout_text.decode().strip(), payload["messages"][1]["content"])
        self.assertNotIn("input_file", json.dumps(payload))
        self.assertEqual(text, transcript.strip())

    def test_pdf_llm_extraction_requires_server_deepseek_key(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
            online.OnlineStudioError, "DEEPSEEK_API_KEY"
        ):
            online._extract_document_text("reference.pdf", b"%PDF-test")

    def test_structure_generated_title_replaces_upload_filename(self):
        self.assertEqual(
            online._generated_structure_title(
                {
                    "target_paper_title": (
                        "Permutation Invariance of Multiple-Choice Answers in "
                        "Large Language Models"
                    )
                },
                "try",
            ),
            "Permutation Invariance of Multiple-Choice Answers in Large Language Models",
        )
        self.assertEqual(
            online._generated_structure_title(
                {"target_paper_title": "Draft xx"}, "Safe Fallback Title"
            ),
            "Safe Fallback Title",
        )

    def test_lightweight_scaffold_without_results_has_main_table_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                online,
                "_write_lightweight_researcher_profile",
                side_effect=lightweight_profile_fixture,
            ):
                online._write_lightweight_workspace(
                    root,
                    venue="ACL 2027",
                    project_name="Text Only Project",
                    title="A Text Only Paper",
                    scholar_files=[("scholar.html", "<html><body>Researcher profile.</body></html>")],
                    project_brief_files=[("project.txt", "Complete project description." )],
                    results_files=[],
                    reference_paper_files=[(
                        "reference.txt",
                        "# Required Structural Reference\n" + STRUCTURAL_REFERENCE_TEXT,
                    )],
                    api_key="test-key",
                    model="test-model",
                )
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable, "-m", "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            config = json.loads((root / "paper/paper_studio.json").read_text())
            self.assertEqual(config["figure_order"], ["F1", "F2"])
            self.assertEqual(config["figures"]["F1"]["kind"], "mechanism")
            self.assertEqual(config["figures"]["F1"]["source_sections"], ["introduction"])
            self.assertEqual(config["figures"]["F2"]["kind"], "data")
            self.assertTrue(config["figures"]["F2"]["online_placeholder"])
            self.assertEqual(config["table_order"], ["T1"])
            self.assertTrue(config["tables"]["T1"]["online_placeholder"])
            plan = {"sections": {
                item["id"]: item["paragraphs"] for item in config["sections"]
            }}
            self.assertEqual(plan["sections"]["experiments"][0]["artifacts"], [])
            self.assertEqual(plan["sections"]["experiments"][1]["artifacts"], ["T1", "F2"])
            self.assertEqual(plan["sections"]["discussion"][0]["artifacts"], ["T1", "F2"])
            self.assertIn(
                "Cite the bound result-table and data-figure placeholders",
                plan["sections"]["discussion"][0]["purpose"],
            )
            modes = {item["id"]: item["writing_mode"] for item in config["sections"]}
            ordered = [item["id"] for item in config["sections"]]
            self.assertTrue(all(modes[item] == "draft" for item in ordered))

    def test_legacy_no_result_project_is_upgraded_with_bound_figure_and_table_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "paper"
            paper.mkdir()
            (paper / "metrics.json").write_text(json.dumps({
                "lightweight_project": {
                    "numeric_policy": "replace_quantitative_values_with_xx"
                }
            }))
            (paper / "paper_studio.json").write_text(json.dumps({
                "figure_order": ["F1"],
                "figures": {"F1": {"kind": "mechanism"}},
                "table_order": ["T1"],
                "tables": {"T1": {"online_placeholder": True}},
                "sections": [
                    {"id": "experiments", "paragraphs": [
                        {"id": "E-P1", "artifacts": []},
                        {"id": "E-P2", "artifacts": ["T1"]},
                    ]},
                    {"id": "discussion", "paragraphs": [
                        {"id": "D-P1", "artifacts": []},
                    ]},
                ],
            }))

            self.assertTrue(online._ensure_unexecuted_result_placeholders(root))
            config = json.loads((paper / "paper_studio.json").read_text())
            self.assertEqual(config["figure_order"], ["F1", "F2"])
            self.assertTrue(config["figures"]["F2"]["online_placeholder"])
            sections = {item["id"]: item for item in config["sections"]}
            self.assertEqual(
                sections["experiments"]["paragraphs"][1]["artifacts"],
                ["T1", "F2"],
            )
            self.assertEqual(
                sections["discussion"]["paragraphs"][0]["artifacts"],
                ["T1", "F2"],
            )

    def test_lightweight_scaffold_rejects_an_unrecognized_venue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(online.OnlineStudioError):
                online._write_lightweight_workspace(
                    root,
                    venue="Some Made Up Workshop",
                    project_name="X",
                    title="X",
                    scholar_files=[],
                    project_brief_files=[],
                    results_files=[],
                    api_key="test-key",
                    model="test-model",
                )

    def test_scaffold_uses_the_target_venues_real_official_latex_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(
                    root, files=pipeline_files(venue="EMNLP 2026 Findings"),
                    archive=evidence_archive(),
                )
            main_tex = (root / "paper/main.tex").read_text()
            # The real ACL-family class, not a hand-rolled generic article.
            self.assertIn(r"\usepackage[review]{acl}", main_tex)
            self.assertNotIn(r"\usepackage[margin=1in]{geometry}", main_tex)
            # acl.sty emits its own \bibliographystyle; a manual one breaks bibtex.
            self.assertNotIn(r"\bibliographystyle", main_tex)
            self.assertTrue((root / "paper/acl.sty").is_file())
            self.assertTrue((root / "paper/acl_natbib.bst").is_file())
            environment = {**os.environ, "RESEARCH_AVATAR_ROOT": str(root)}
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_avatar.paper_studio.server",
                    "--validate-project",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_venue_template_preamble_actually_compiles_generated_math_prose(self):
        # Regression: the acl template preamble originally omitted amsmath/amssymb,
        # so ordinary generated math like \text{...} inside \( \) failed pdflatex
        # with "Undefined control sequence" mid-batch-draft, well after the
        # scaffold itself looked correct. Verify with real pdflatex, not just a
        # package-name substring check, since substring checks would not have
        # caught this class of bug.
        pdflatex = shutil.which("pdflatex")
        if not pdflatex:
            self.skipTest("pdflatex not available in this environment")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(
                    root, files=pipeline_files(venue="COLING 2027 Short Paper"),
                    archive=evidence_archive(),
                )
            paper = root / "paper"
            (paper / "sections/experiments.tex").write_text(
                r"\section{Experiments}" "\n"
                r"Consider candidate perturbations, with "
                r"\(C_{\text{clean}} = \{c \in C \mid \text{valid}(c)\}\)."
                "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                cwd=paper,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((paper / "main.pdf").is_file())

    def test_scaffold_rejects_a_venue_with_no_bundled_official_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                with self.assertRaisesRegex(online.OnlineStudioError, "官方 LaTeX 模板"):
                    online._write_workspace(
                        root,
                        files=pipeline_files(venue="Some Unlisted Workshop 2099"),
                        archive=evidence_archive(),
                    )
            # Fail closed: no partially-scaffolded generic-template paper/ survives.
            self.assertFalse((root / "paper/main.tex").is_file())

    def test_scaffold_accepts_one_complete_project_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                online._write_workspace(root, files=[], archive=project_archive())
            self.assertTrue((root / "paper/paper_studio.json").is_file())
            config = json.loads((root / "paper/paper_studio.json").read_text())
            plan = {"sections": {
                item["id"]: item["paragraphs"] for item in config["sections"]
            }}
            self.assertFalse((root / "paper/uploaded_sources.txt").exists())
            architecture = plan["sections"]["abstract"][0]
            self.assertEqual(architecture["rhetorical_role"], "summary")
            self.assertNotIn("reference_lines", architecture)

    def test_online_shell_has_no_demo_interaction_or_key_prompt(self):
        # Regression: the Demo tab used to let a visitor click an
        # interactive control, fail, and get redirected into a "type your
        # OpenAI key to get an editable copy" dialog. The demo is view-only
        # now -- there is no key prompt to defer, and no route left that
        # would create a private writable copy of it.
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("demo-key-dialog", html)
        self.assertNotIn("demo-key-dialog", script)
        self.assertNotIn("paper-studio-demo-api-key-required", script)
        self.assertNotIn("/api/online/demo-session", script)
        self.assertFalse(hasattr(online, "create_demo_copy_session"))

    def test_online_onboarding_describes_xx_and_placeholder_policy(self):
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("定量值统一使用 xx", html)
        self.assertIn("Introduction 默认保留 Motivation 图位", html)
        self.assertIn("在本地终端继续完成", html)
        self.assertIn("placeholder", html)
        self.assertNotIn("机制图仍需完整项目包中的绘图 Agent", html)

    def test_page_refresh_always_shows_landing_tabs_not_an_auto_redirect(self):
        # Regression: the landing page used to auto-redirect straight into
        # /studio whenever a researcher had an active writing session,
        # which meant the site's root URL could never actually reach the
        # landing-page shell again once a session existed -- a real user
        # reported this. The resume link inside the PaperWrite tab
        # (#session-actions) is now how you get back into an active
        # session: an explicit choice, not automatic.
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn(">免费纯文字 PaperWrite 版</button>", html)
        self.assertNotIn(">Use it</button>", html)
        self.assertIn("免费纯文字 PaperWrite 版", script)
        self.assertNotIn("window.location.assign('/studio')", script)
        self.assertIn(": 'demo-panel'", script)
        self.assertIn("get('open') === 'use'", script)
        session_check = script.index("fetch('/api/online/session'")
        demo_panel_select = script.index("selectProductPanel(requestedPanel)")
        self.assertLess(
            demo_panel_select, session_check,
            "the Demo tab must render unconditionally before the active-"
            "session check only decides whether to reveal the resume link",
        )
        self.assertIn("activeStudioSession = Boolean(state.active)", script)
        self.assertIn("sessionActions.classList.remove('hidden')", script)
        self.assertIn("studioFrame.src = '/studio'", script)
        self.assertNotIn("window.location.assign(result.redirect)", script)

    def test_free_paperwrite_uses_the_shared_section_draft_surface(self):
        """The hosted writer must not lag behind the reusable Paper Studio UI."""
        html = (
            Path(__file__).resolve().parents[1]
            / "research_avatar/paper_studio/static/index.html"
        ).read_text(encoding="utf-8")
        script = (
            Path(__file__).resolve().parents[1]
            / "research_avatar/paper_studio/static/app.js"
        ).read_text(encoding="utf-8")
        self.assertIn('id="section-draft-start"', html)
        self.assertIn("一键生成当前 Section", html)
        self.assertIn('request("/api/section-draft/start"', script)
        self.assertIn("section_draft", script)
        self.assertIn("请在本地终端运行 Code Agent", html)

    def test_studio_navigation_redirects_to_html_with_actionable_notice(self):
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        worker = (
            Path(__file__).resolve().parents[1] / "deploy/cloudflare/index.ts"
        ).read_text(encoding="utf-8")
        self.assertIn('id="session-notice"', html)
        self.assertIn("session_expired", script)
        self.assertIn("login_required", script)
        self.assertIn("上一次临时写作会话已结束", script)
        self.assertIn('new URL("/?login_required=1", request.url)', worker)
        self.assertIn('path === "/studio"', worker)
        self.assertIn('"/?session_expired=1"', Path(online.__file__).read_text(encoding="utf-8"))

    def test_local_debug_studio_navigation_redirects_unauthenticated_browser(self):
        opener = urllib.request.build_opener(_NoRedirect())
        server = online.OnlineServer(("127.0.0.1", 0), online.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as response:
                opener.open(f"http://127.0.0.1:{server.server_port}/studio")
            self.assertEqual(response.exception.code, 302)
            self.assertEqual(response.exception.headers["Location"], "/?login_required=1")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_cloudflare_release_uses_version_scoped_container(self):
        """A deploy must not keep serving the prior image's demo snapshot."""
        root = Path(__file__).resolve().parents[1]
        worker = (root / "deploy/cloudflare/index.ts").read_text(encoding="utf-8")
        wrangler = (root / "deploy/cloudflare/wrangler.example.jsonc").read_text(
            encoding="utf-8"
        )
        self.assertIn("env.CF_VERSION_METADATA.id", worker)
        self.assertIn('"version_metadata"', wrangler)
        self.assertIn('"binding": "CF_VERSION_METADATA"', wrangler)
        self.assertIn('"class_name": "OnlineStudioContainerV49"', wrangler)
        self.assertIn("export class OnlineStudioContainerV49", worker)
        self.assertNotIn('getContainer(env.ONLINE_STUDIO, "public-studio-', worker)

    def test_cloudflare_worker_forwards_only_deepseek_secret_to_container(self):
        worker = (
            Path(__file__).resolve().parents[1] / "deploy/cloudflare/index.ts"
        ).read_text(encoding="utf-8")
        self.assertIn("if (env.DEEPSEEK_API_KEY)", worker)
        self.assertIn("DEEPSEEK_API_KEY: env.DEEPSEEK_API_KEY", worker)
        self.assertNotIn("env.OPENAI_API_KEY", worker)

    def test_cloudflare_release_copies_shared_runtime_modules(self):
        """The incremental release image must contain every newly imported module."""
        dockerfile = (
            Path(__file__).resolve().parents[1]
            / "deploy/cloudflare/Dockerfile.release"
        ).read_text(encoding="utf-8")
        for module in ("paper_structure.py", "survey_bibliography.py"):
            self.assertIn(f"COPY research_avatar/{module} ", dockerfile)
            self.assertIn(
                f"/usr/local/lib/python3.12/site-packages/research_avatar/{module}",
                dockerfile,
            )

    def test_deployment_access_token_field_and_protocol_are_removed(self):
        root = Path(__file__).resolve().parents[1]
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        server = Path(online.__file__).read_text(encoding="utf-8")
        worker = (root / "deploy/cloudflare/index.ts").read_text(encoding="utf-8")
        for source in (html, script, server, worker):
            self.assertNotIn("access_token_required", source)
        self.assertNotIn('name="access_token"', html)
        self.assertNotIn("部署访问口令", html)
        self.assertNotIn("payload.get(\"access_token\")", server)

    def test_container_image_installs_every_tool_compile_table_preview_requires(self):
        # Regression: a real batch-writing run finished all 19 paragraphs,
        # then failed at the final table-materialization step with "无法生成
        # LaTeX 表格预览：缺少 pdfcrop。" -- the base container image
        # installed poppler-utils (pdftoppm/pdfinfo/pdftocairo) and latexmk,
        # but never texlive-extra-utils, which is what actually provides the
        # pdfcrop binary compile_table_preview() shells out to. The
        # application code already checked for and reported the missing
        # tool correctly; the tool itself just wasn't installed.
        #
        # Fixing that surfaced a second, one-level-deeper failure: "LaTeX 表格
        # 预览编译失败" / "Ghostscript exited with error code 127" --
        # pdfcrop itself shells out to `gs` to compute the bounding box, and
        # `--no-install-recommends` (set just above this loop's apt-get
        # command) suppresses ghostscript, which texlive-extra-utils only
        # Recommends rather than Depends on. Both must be installed
        # explicitly.
        dockerfile = (
            Path(__file__).resolve().parents[1] / "deploy/online-paper-studio/Dockerfile"
        ).read_text(encoding="utf-8")
        for package in ("ghostscript", "texlive-extra-utils", "poppler-utils", "latexmk", "nodejs"):
            self.assertIn(package, dockerfile)

    def test_upload_page_has_one_two_material_entry(self):
        html = (online.STATIC / "index.html").read_text(encoding="utf-8")
        script = (online.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertEqual(html.count('<form id="setup-form"'), 1)
        self.assertEqual(html.count('class="step-index"'), 1)
        for field in ("project_brief_file", "reference_paper_file"):
            self.assertIn(f'name="{field}"', html)
        self.assertNotIn('name="results_file"', html)
        self.assertNotIn("results_files:", script)
        self.assertNotIn('name="scholar_file"', html)
        self.assertNotIn("scholar_files:", script)
        self.assertNotIn('name="title"', html)
        self.assertNotIn("title: elements.title.value", script)
        self.assertIn("/api/online/session/job?job_id=", script)
        self.assertIn("const jobId = result.job_id", script)
        self.assertIn("encodeURIComponent(jobId)", script)
        self.assertIn("已等待 ${elapsed} 秒", script)
        self.assertIn("（预计 2–3 min）", script)
        self.assertNotIn('name="project_package"', html)
        self.assertLess(
            html.index('name="project_brief_file"'),
            html.index('name="reference_paper_file"'),
        )
        reference_label = html[html.rfind("<label", 0, html.index('name="reference_paper_file"')):
                               html.index('name="reference_paper_file"')]
        self.assertNotIn('class="upload-field"', reference_label)

    def test_use_it_title_is_derived_from_approved_experiment_plan(self):
        contract = {
            "paper_title": "Automatically Inherited Paper Title",
            "selected_idea": {"title": "Fallback Idea Title"},
        }
        self.assertEqual(
            online._lightweight_paper_title(
                "",
                "SOURCE ROLE: PROJECT BRIEF\nSOURCE: 03_EXPERIMENT_PLAN.html",
                contract,
                "03_EXPERIMENT_PLAN.html",
            ),
            "Automatically Inherited Paper Title",
        )

    def test_use_it_title_falls_back_to_project_brief_heading(self):
        self.assertEqual(
            online._lightweight_paper_title(
                "",
                "SOURCE ROLE: PROJECT BRIEF\n# Adaptive Dialogue Learning",
                None,
                "project-brief.md",
            ),
            "Adaptive Dialogue Learning",
        )

    def test_use_it_title_keeps_compilable_prefix_from_bilingual_plan_title(self):
        self.assertEqual(
            online._lightweight_paper_title(
                "",
                "SOURCE ROLE: PROJECT BRIEF",
                {"paper_title": "Steering Commutator：干预顺序何时改变结果？"},
                "project-brief.html",
            ),
            "Steering Commutator",
        )

    def test_use_it_title_prefers_projected_english_title_over_bilingual_idea(self):
        self.assertEqual(
            online._lightweight_paper_title(
                "",
                "2.1 Projected Title and Abstract\n"
                "Steering Commutator: When Intervention Order Changes Language Models\n"
                "PROJECTED — not results",
                {"selected_idea": {"title": "Steering Commutator：干预顺序何时改变结果？"}},
                "03_EXPERIMENT_PLAN.html",
            ),
            "Steering Commutator: When Intervention Order Changes Language Models",
        )

    def test_use_it_title_uses_safe_default_for_non_ascii_only_title(self):
        self.assertEqual(
            online._lightweight_paper_title(
                "", "# 纯中文标题", None, "项目说明.html"
            ),
            "Research Paper Draft",
        )

    def test_plan_bibliography_excludes_structural_reference_and_resolves_declared_sources(self):
        contract = {
            "references": {"researcher_owned_logic": {"url": "https://arxiv.org/abs/2605.01844"}},
            "dataset_citations": [{"url": "https://arxiv.org/abs/2505.24535"}],
            "baseline_contract": {"selected": [
                {"url": "https://aclanthology.org/2024.acl-long.828/"},
                {"url": "https://arxiv.org/abs/2605.01844"},
            ]},
        }
        with patch.object(
            online,
            "_scholarly_bibtex_from_url",
            side_effect=lambda url: (url.rsplit("/", 1)[-1], "@misc{x}"),
        ) as fetch:
            records = online._verified_contract_bibliography(contract)
        self.assertEqual(len(records), 2)
        self.assertEqual(
            [call.args[0] for call in fetch.call_args_list],
            ["https://arxiv.org/abs/2505.24535", "https://aclanthology.org/2024.acl-long.828"],
        )

    def test_use_it_accepts_unapproved_experiment_plan_as_writing_material(self):
        contract = {
            "schema_version": "1.2",
            "approval_status": "pending",
            "paper_outline": [{
                "id": "introduction",
                "title": "Introduction",
                "paragraphs": [{
                    "id": "I-P1",
                    "plan_sentence": "Introduce the research problem.",
                    "rhetorical_role": "problem framing",
                    "relation_to_previous": "paper opening",
                    "relation_to_next": "introduces the method",
                    "supports": [],
                    "evidence": [],
                    "artifact_refs": [],
                }],
            }],
            "paper_artifacts": [],
            "references": {
                "researcher_owned_logic": {"title": "Uploaded reference"}
            },
        }
        project_text = (
            "<experiment-plan-contract>\n"
            + json.dumps(contract)
            + "\n</experiment-plan-contract>"
        )
        parsed = online._approved_contract_from_project_text(project_text)
        self.assertEqual(parsed["approval_status"], "pending")

    def test_project_export_is_a_zip_and_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "paper").mkdir()
            (root / "paper/main.tex").write_text("paper", encoding="utf-8")
            outside = root.parent / (root.name + "-outside-secret.txt")
            outside.write_text("must-not-export", encoding="utf-8")
            link = root / "paper/outside.txt"
            try:
                link.symlink_to(outside)
                data = online._project_zip_bytes(root)
            finally:
                outside.unlink(missing_ok=True)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertEqual(archive.namelist(), ["paper/main.tex"])
                self.assertEqual(archive.read("paper/main.tex"), b"paper")

    def test_project_export_excludes_build_and_cache_artifacts(self):
        # Regression: a real production export downloaded by a researcher
        # (via /api/online/export) contained a compiled
        # a nested tooling "__pycache__/*.pyc" file --
        # _project_zip_bytes walked the whole session root with no
        # exclusions, so any build/cache byproduct left in the workspace
        # (from running local-Agent tooling inside the session) leaked
        # straight into the user-facing ZIP.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "paper").mkdir()
            (root / "paper/main.tex").write_text("paper", encoding="utf-8")
            (root / "scripts/__pycache__").mkdir(parents=True)
            (root / "scripts/__pycache__/tool.cpython-312.pyc").write_bytes(b"\x00")
            (root / "scripts/tool.pyc").write_bytes(b"\x00")
            (root / ".git").mkdir()
            (root / ".git/HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
            (root / ".DS_Store").write_bytes(b"\x00")
            data = online._project_zip_bytes(root)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertEqual(archive.namelist(), ["paper/main.tex"])

    def test_project_export_survives_a_preview_file_disappearing_mid_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "paper/.paper_studio/table-t1-test").mkdir(parents=True)
            stable = root / "paper/main.tex"
            volatile = root / "paper/.paper_studio/table-t1-test/preview.log"
            stable.write_text("paper", encoding="utf-8")
            volatile.write_text("temporary", encoding="utf-8")
            original_write = zipfile.ZipFile.write

            def racing_write(archive, filename, arcname=None, compress_type=None, compresslevel=None):
                path = Path(filename)
                if path.name == "preview.log":
                    path.unlink(missing_ok=True)
                return original_write(
                    archive, filename, arcname, compress_type, compresslevel
                )

            with patch.object(zipfile.ZipFile, "write", new=racing_write):
                data = online._project_zip_bytes(root)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertEqual(archive.namelist(), ["paper/main.tex"])

    def test_live_worker_hides_root_and_never_persists_api_key(self):
        key = "sk-online-test-never-write-this"
        encoded_files = [
            {"name": name, "data": base64.b64encode(source.encode()).decode()}
            for name, source in pipeline_files()
        ]
        encoded_archive = base64.b64encode(evidence_archive()).decode()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(online, "DATA_ROOT", Path(directory)),
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": key}),
        ):
            validator = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch.object(online.subprocess, "run", return_value=validator):
                session = online.create_session(
                    {
                        "files": encoded_files,
                        "evidence_archive": {"name": "evidence.zip", "data": encoded_archive},
                    },
                    user_id="test-user",
                )
            with urllib.request.urlopen(
                f"http://127.0.0.1:{session.port}/api/state", timeout=5
            ) as response:
                state = json.loads(response.read())
            self.assertEqual(state["project"]["root"], "")
            self.assertEqual(state["api_key_setup"]["setup_command"], "")
            self.assertTrue(state["api_key_configured"])
            session_cookie = f"{online.COOKIE_NAME}={session.session_id}"
            self.assertIs(
                online._session_from_cookie(session_cookie, user_id="test-user"),
                session,
            )
            self.assertIsNone(
                online._session_from_cookie(session_cookie, user_id="other-user")
            )
            for path in session.root.rglob("*"):
                if path.is_file():
                    self.assertNotIn(key.encode(), path.read_bytes(), path)

    def test_create_session_fails_clearly_when_shared_key_is_unconfigured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEEK_API_KEY", None)
            with self.assertRaises(online.OnlineStudioError):
                online.shared_deepseek_api_key()

    def test_user_cumulative_cost_sums_every_session_ledger_for_that_user(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            user_root = online.user_project_root("cap-user")
            for session_name, cost in (("session-a", 3.5), ("session-b", 4.0)):
                ledger = user_root / session_name / "paper/.paper_studio/api_usage.jsonl"
                ledger.parent.mkdir(parents=True)
                ledger.write_text(
                    json.dumps({"estimated_cost_usd": cost}) + "\n", encoding="utf-8"
                )
            self.assertAlmostEqual(
                online.user_cumulative_cost_usd("cap-user"), 7.5
            )
            self.assertAlmostEqual(online.user_cumulative_cost_usd("other-user"), 0.0)

    def test_spend_cap_blocks_new_sessions_once_a_user_is_over_the_rmb_limit(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            online, "DATA_ROOT", Path(directory)
        ):
            # USER_SPEND_CAP_RMB=200 / USD_TO_RMB_RATE=7.2 -> ~27.8 USD trips it.
            ledger = (
                online.user_project_root("over-cap-user")
                / "session-a/paper/.paper_studio/api_usage.jsonl"
            )
            ledger.parent.mkdir(parents=True)
            ledger.write_text(
                json.dumps({"estimated_cost_usd": 30.0}) + "\n", encoding="utf-8"
            )
            with self.assertRaises(online.OnlineStudioError):
                online.require_under_spend_cap("over-cap-user")
            online.require_under_spend_cap("fresh-user")

    def test_proxy_blocks_writes_once_a_user_session_is_over_the_spend_cap(self):
        handler = object.__new__(online.Handler)
        handler.command = "POST"
        recorded = {}

        def fake_json(payload, status=200, cookie=None):
            recorded["payload"] = payload
            recorded["status"] = status

        handler._json = fake_json
        session = online.Session(
            "session-id", "over-cap-user", Path("/tmp/does-not-matter"),
            "deepseek", "deepseek-v4-flash", MagicMock(), 0, kind="user",
        )
        with patch.object(online, "user_cumulative_cost_usd", return_value=1000.0):
            handler._proxy(session, "/api/generate")
        self.assertFalse(recorded["payload"]["ok"])
        self.assertEqual(recorded["status"], 402)

    def test_demo_read_only_gate_still_blocks_generic_writes(self):
        handler = object.__new__(online.Handler)
        handler.command = "POST"
        recorded = {}
        handler._json = lambda payload, status=200, cookie=None: recorded.update(
            {"payload": payload, "status": status}
        )
        session = online.Session(
            "demo", "*", Path("/tmp/does-not-matter"),
            "openai", "gpt-5-nano", MagicMock(), 0, kind="demo",
        )
        handler._proxy(session, "/api/generate", read_only=True)
        self.assertFalse(recorded["payload"]["ok"])
        self.assertEqual(recorded["status"], 405)

    def test_demo_uses_full_local_figure_capabilities_not_online_placeholders(self):
        source = Path(online.__file__).read_text(encoding="utf-8")
        self.assertIn('"PAPER_STUDIO_ONLINE": "0" if demo_mode else "1"', source)
        self.assertIn('"PAPER_STUDIO_DEMO_MODE": "1" if demo_mode else "0"', source)

    def test_pdf_locate_reaches_a_demo_session_despite_being_a_post(self):
        # Regression: double-click-to-source-line on the PDF preview posts
        # to /api/pdf/locate (click coordinates in the body), which is a
        # pure lookup -- it never mutates the manuscript. The demo's
        # blanket read_only=True gate blocked it like any other write, so
        # the feature silently did nothing on the read-only Demo tab.
        handler = object.__new__(online.Handler)
        handler.command = "POST"
        handler.headers = {}
        handler.rfile = io.BytesIO(b"")
        session = online.Session(
            "demo", "*", Path("/tmp/does-not-matter"),
            "openai", "gpt-5-nano", MagicMock(), 0, kind="demo",
        )
        with patch.object(online.http.client, "HTTPConnection") as connection_cls:
            connection = connection_cls.return_value
            response = MagicMock()
            response.status = 200
            response.read.return_value = b'{"ok": true}'
            response.getheaders.return_value = []
            connection.getresponse.return_value = response
            handler.send_response = MagicMock()
            handler.send_header = MagicMock()
            handler.end_headers = MagicMock()
            handler.wfile = MagicMock()
            handler._proxy(session, "/api/pdf/locate", read_only=True)
        connection.request.assert_called_once()
        handler.send_response.assert_called_once_with(200)

    def test_setup_page_only_asks_for_generated_html_and_openai_key(self):
        source = (online.STATIC / "index.html").read_text(encoding="utf-8")
        app = (online.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="demo-tab"', source)
        self.assertIn('id="use-tab"', source)
        # Do not request the authenticated Demo iframe before auth state is
        # known: that produced a visible 401 console error on every fresh
        # login page. showAuthenticated() assigns the real URL afterward.
        self.assertIn('id="demo-frame" class="demo-frame" src="about:blank"', source)
        self.assertIn("demoFrame.src = '/demo/?authenticated='", app)
        self.assertNotIn("先看看一篇论文是怎样完成的。", source)
        self.assertNotIn("这是完整 Research Avatar 流程的可交互示例。", source)
        self.assertNotIn("上传完整项目，开始自己的论文。", source)
        self.assertNotIn("上传由 Research Avatar 生成的必要研究证据。", source)
        style = (online.STATIC / "style.css").read_text(encoding="utf-8")
        self.assertIn("width: min(1500px, calc(100% - 32px))", style)
        self.assertIn(".use-columns { max-width: 1500px; align-items: start; }", style)
        self.assertIn("body.workspace-authenticated{height:100dvh", style)
        self.assertIn("#use-panel{overflow-y:auto", style)
        self.assertIn("#demo-panel{overflow:hidden", style)
        self.assertIn(": 'demo-panel'", app)
        self.assertIn("selectProductPanel(requestedPanel)", app)
        self.assertIn("document.body.classList.add('workspace-authenticated')", app)
        self.assertNotIn('name="project_package"', source)
        self.assertNotIn('name="profile_file"', source)
        self.assertNotIn('name="plan_file"', source)
        self.assertNotIn('name="result_file"', source)
        self.assertNotIn('name="api_key"', source)
        self.assertNotIn('name="project_name"', source)
        self.assertNotIn('name="outline"', source)
        self.assertNotIn('name="model"', source)
        # Every online session shares one server-held DeepSeek key now; the
        # landing page never asks a researcher for their own key or lets
        # them pick a provider.
        self.assertNotIn("api_key", app)
        self.assertNotIn("provider:", app)
        self.assertNotIn('id="lightweight-form"', source)
        self.assertEqual(source.count('class="upload-field"'), 0)
        self.assertEqual(source.count('<p class="step-index">01</p>'), 1)
        self.assertNotIn('<p class="step-index">02</p>', source)
        self.assertNotIn('name="scholar_file"', source)
        self.assertNotIn("（必传）", source)
        self.assertIn('name="project_brief_file"', source)
        self.assertNotIn('name="results_file"', source)
        self.assertNotIn('name="results_files"', source)
        self.assertNotIn('name="results_file" type="file" accept=".doc,.docx,.txt,.pdf,.md,.markdown,.json,.html,.htm" multiple', source)
        self.assertIn('name="reference_paper_file"', source)
        self.assertNotIn('class="export" href="/api/online/export"', source)
        paper_studio_html = (
            Path(__file__).resolve().parents[1]
            / "research_avatar/paper_studio/static/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn('id="project-export"', paper_studio_html)

    def test_three_material_scaffold_skips_scholar_download_and_style_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                online,
                "_write_lightweight_researcher_profile",
                side_effect=AssertionError("Scholar path must not run"),
            ):
                online._write_lightweight_workspace(
                    root,
                    venue="ACL 2027",
                    project_name="",
                    title="",
                    scholar_files=[],
                    project_brief_files=[(
                        "current-work.md",
                        "# Current Work\nWe evaluate a compact dialogue model.",
                    )],
                    results_files=[(
                        "experiment-result.json",
                        json.dumps({
                            "caption": "Main results.",
                            "columns": [
                                {"key": "method", "label": "Method"},
                                {"key": "score", "label": "Score"},
                            ],
                            "rows": [{"method": "Ours", "score": 0.9}],
                        }),
                    )],
                    reference_paper_files=[(
                        "reference.txt",
                        "# Structural Reference\n" + STRUCTURAL_REFERENCE_TEXT,
                    )],
                    api_key="test-key",
                    model="deepseek-v4-flash",
                )
            metrics = json.loads((root / "paper/metrics.json").read_text())
            profile = metrics["lightweight_project"]["personalization"]
            self.assertEqual(profile["mode"], "uploaded_reference_only")
            self.assertFalse(profile["writing_style_inferred"])
            self.assertEqual(profile["representative_papers"], [])
            self.assertEqual((root / "paper/references.bib").read_text(), "\n")

    def test_demo_uses_sticky_six_stage_header_and_one_vertical_scroll(self):
        root = Path(__file__).resolve().parents[1]
        style = (root / "research_avatar/web/demo/style.css").read_text(encoding="utf-8")
        html = (root / "research_avatar/web/demo/index.html").read_text(encoding="utf-8")
        self.assertIn(".journey-nav{position:sticky;top:0", style)
        self.assertIn(".stage-content{min-height:calc(100dvh - 117px);max-height:none;overflow:visible", style)
        self.assertIn("style.css?v=20260822-generic-workflow", html)


if __name__ == "__main__":
    unittest.main()
