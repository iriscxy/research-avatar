import json
import io
import os
import re
import signal
import subprocess
import threading
import time
import unittest
from html.parser import HTMLParser
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import research_avatar.paper_studio.server as studio
from research_avatar.tools.figure_ppt import shape_spec_html
from research_avatar.paper_studio.server import (
    FIGURES,
    Handler,
    StudioError,
    _default_state,
    call_openai,
    candidate_for_accept,
    citation_keys,
    compose_data_figure,
    create_data_figure_layout_with_local_agent,
    current_paragraph,
    data_figure_layout,
    compile_table_preview,
    default_table_prompt,
    edit_table_with_local_agent,
    extract_agent_table_latex,
    extract_agent_layout_json,
    enforce_required_heading,
    extract_output_text,
    figure_gate,
    figure_generation_gate,
    figure_insertion_gate,
    figure_latex,
    figure_public_state,
    generate_data_figure_agent_worker,
    generate_table_latex,
    has_uncited_named_attribution,
    needs_citation_resolution,
    next_unaccepted_index,
    manuscript_title_display,
    manuscript_title_tex,
    manuscript_entrypoint_errors,
    normalize_reference_excerpt,
    latex_prose_issues,
    normalize_latex_ready_text,
    normalize_mechanism_text_boxes,
    public_state,
    replace_manuscript_title_source,
    require_substantive_table_revision,
    render_section_source,
    response_source_urls,
    sync_verified_bibliography,
    save_manuscript_title,
    table_numeric_cells,
    validate_data_figure_layout,
    validate_mechanism_shape_spec,
)


class PaperStudioTests(unittest.TestCase):
    def test_http_server_accepts_browser_asset_bursts(self):
        self.assertGreaterEqual(studio.StudioHTTPServer.request_queue_size, 32)

    @classmethod
    def setUpClass(cls):
        """Run project-level regressions against an isolated legacy fixture."""
        cls.fixture_directory = TemporaryDirectory(dir=studio.ROOT / "tests")
        root = Path(cls.fixture_directory.name)
        paper = root / "paper"
        paper.mkdir()
        (paper / "sections").mkdir()
        reference = paper / "reference_stylization_jailbreak.txt"
        reference_lines = [f"Reference line {index}" for index in range(1, 241)]
        reference_lines[146] = "DeepSeek GPT-4o Style Jailbreak 96.0 52.8"
        reference_lines[69] = "Conclusion and Future Work reference paragraph."
        reference.write_text("\n".join(reference_lines), encoding="utf-8")
        metrics = {
            "fixture": {
                "synthetic": True,
                "notice": "Synthetic fixture; not measured.",
            },
            "representation_analysis": {
                "local_probe": {"layers": [1, 2], "accuracy": [0.6, 0.7]},
            },
            "main_results": {
                "benchmarks": {
                    "AdvBench": {"rows": [{"method": "Style Jailbreak", "mean_asr": 96.0, "mean_sr": 52.8}]},
                    "TrustLLM": {"rows": [{"method": "Style Jailbreak", "mean_asr": 92.0, "mean_sr": 48.0}]},
                }
            },
            "defenses": {
                "rows": [{"defense": "Guard", "residual_asr": 12.0, "benign_utility": 90.0}]
            },
            "robustness": {
                "layerwise_values": {
                    "synthetic": True,
                    "notice": "Synthetic fixture; not measured.",
                    "series": [
                        {"model": "A", "values": [0.1, 0.2]},
                        {"model": "B", "values": [0.2, 0.3]},
                        {"model": "C", "values": [0.3, 0.4]},
                    ],
                }
            },
        }
        metrics_file = paper / "metrics.json"
        metrics_file.write_text(json.dumps(metrics), encoding="utf-8")
        section_specs = [
            {"id": "abstract", "title": "Abstract", "file": "abstract.tex", "render": "abstract", "result_keys": []},
            {"id": "introduction", "title": "Introduction", "latex_title": "Introduction", "file": "introduction.tex", "result_keys": []},
            {"id": "related_work", "title": "Related Work", "latex_title": "Related Work", "file": "related_work.tex", "result_keys": []},
            {"id": "method", "title": "Style Jailbreak", "latex_title": "Style Jailbreak", "file": "method.tex", "result_keys": []},
            {"id": "representation_analysis", "title": "Representation Analysis", "latex_title": "Representation Analysis", "file": "representation_analysis.tex", "result_keys": ["representation_analysis.local_probe"]},
            {"id": "experiments", "title": "Experiments", "latex_title": "Experiments", "file": "experiments.tex", "result_keys": ["main_results.benchmarks"]},
            {"id": "analysis_discussion", "title": "Analysis and Discussion", "latex_title": "Analysis and Discussion", "file": "analysis_discussion.tex", "result_keys": ["defenses.rows"]},
            {"id": "conclusion", "title": "Conclusion and Future Work", "latex_title": "Conclusion and Future Work", "end_label": "paper:endconclusion", "file": "conclusion.tex", "result_keys": []},
            {"id": "appendix", "title": "Appendix", "latex_title": "Appendix", "file": "appendix.tex", "result_keys": ["robustness.layerwise_values"]},
        ]
        figures = {
            "F1": {
                "title": "Motivation overview", "label": "fig:overview", "kind": "mechanism",
                "width": "single-column", "source_sections": ["introduction"],
                "description": "Motivation overview.", "caption": "Overview.", "phase": 1,
                "result_keys": [], "panels": [], "deliverable_stem": "overview_gpt",
                "depends_on_paragraphs": {"introduction": ["I1", "I2", "I3", "I4"]},
                "generation_requires_paragraphs": {"introduction": ["I1"]},
            },
            "F2": {
                "title": "Representation analysis", "label": "fig:representation", "kind": "data",
                "width": "two-column", "source_sections": ["representation_analysis"],
                "description": "Representation analysis.", "caption": "Representation analysis.", "phase": 2,
                "result_keys": ["representation_analysis.ok"],
                "depends_on_figures": ["F1", "F3"],
                "depends_on_paragraphs": {"representation_analysis": ["RA1", "RA2", "RA3", "RA4"]},
                "panels": [
                    {"id": "a", "title": "Probe", "goal": "Show the local probe.", "result_keys": ["representation_analysis.local_probe"]},
                    {"id": "b", "title": "Trajectory", "goal": "Show the trajectory.", "result_keys": ["representation_analysis.local_probe"]},
                ],
            },
            "F3": {
                "title": "Method", "label": "fig:method", "kind": "mechanism",
                "width": "two-column", "source_sections": ["method"],
                "description": "Method mechanism.", "caption": "Method overview.", "phase": 1,
                "result_keys": [], "panels": [], "deliverable_stem": "method_gpt",
                "depends_on_paragraphs": {"method": ["M1", "M2", "M3", "M4"]},
                "generation_requires_paragraphs": {"method": ["M1", "M2", "M3", "M4"]},
            },
            "F4": {
                "title": "Ablation and style analysis", "label": "fig:main_results", "kind": "data",
                "width": "two-column", "source_sections": ["experiments"],
                "description": "Main comparison.", "caption": "Main results.", "phase": 2,
                "result_keys": ["main_results.benchmarks"],
                "depends_on_paragraphs": {"experiments": ["E1", "E2", "E3"]},
                "panels": [
                    {"id": "a", "title": "Safety", "goal": "Show safety.", "result_keys": ["main_results.benchmarks"]},
                    {"id": "b", "title": "Utility", "goal": "Show utility.", "result_keys": ["main_results.benchmarks"]},
                ],
            },
            "F5": {
                "title": "Defense analysis", "label": "fig:defense", "kind": "data",
                "width": "single-column", "source_sections": ["analysis_discussion"],
                "description": "Defense analysis.", "caption": "Defense analysis.", "phase": 3,
                "result_keys": ["defenses.rows"],
                "depends_on_paragraphs": {"analysis_discussion": ["D1"]},
                "panels": [{"id": "a", "title": "Defense", "goal": "Show defense results.", "result_keys": ["defenses.rows"]}],
            },
            "F6": {
                "title": "Layer-wise robustness", "label": "fig:layerwise", "kind": "data",
                "width": "single-column", "source_sections": ["appendix"],
                "description": "Layer-wise robustness.", "caption": "[SYNTHETIC] Layer-wise robustness.", "phase": 3,
                "result_keys": ["robustness.layerwise_values"],
                "depends_on_figures": ["F1", "F3"],
                "depends_on_paragraphs": {"appendix": ["AP2"]},
                "panels": [{"id": "a", "title": "Layers", "goal": "Show layer values.", "result_keys": ["robustness.layerwise_values"]}],
            },
        }
        tables = {
            "T1": {
                "title": "Main comparison", "label": "tab:main", "kind": "table",
                "width": "two-column", "source_sections": ["experiments"],
                "description": "Main benchmark comparison.", "caption": "Main comparison.",
                "related_paragraphs": {"experiments": ["E2"]},
                "data_grid": {
                    "type": "benchmark_rows", "path": "main_results.benchmarks", "row_key": "method",
                    "benchmarks": ["AdvBench", "TrustLLM"],
                    "metrics": [{"key": "mean_asr", "label": "ASR"}, {"key": "mean_sr", "label": "StrongREJECT"}],
                },
                "prompt": {"columns": "Method | AdvBench ASR | AdvBench StrongREJECT | TrustLLM ASR | TrustLLM StrongREJECT", "rows": "source", "font_size": "small", "best_values": "none"},
            },
            "T2": {
                "title": "Defense comparison", "label": "tab:defense", "kind": "table",
                "width": "single-column", "source_sections": ["analysis_discussion"],
                "description": "Defense comparison.", "caption": "Defense comparison.",
                "related_paragraphs": {"analysis_discussion": ["D1"]},
                "data_grid": {
                    "type": "records", "path": "defenses.rows",
                    "columns": [{"key": "defense", "label": "Defense"}, {"key": "residual_asr", "label": "Residual ASR"}, {"key": "benign_utility", "label": "Benign utility"}],
                },
                "prompt": {"columns": "Defense | Residual ASR | Benign utility", "rows": "source", "font_size": "small", "best_values": "none"},
            },
        }
        config = {
            "schema_version": "1.0",
            "project": {
                "id": "style-jailbreak-test", "name": "Style Jailbreak",
                "initial_title": "Style Jailbreak", "venue": "ICLR",
                "target": {"venue": "ICLR"},
                "reference_paper": {"title": "Fixture reference"},
                "decision_source": "reports/03_EXPERIMENT_PLAN.html",
            },
            "sections": section_specs,
            "figure_order": ["F1", "F3", "F2", "F4", "F5", "F6"], "figures": figures,
            "table_order": ["T1", "T2"], "tables": tables,
            "paths": {"metrics": str(metrics_file), "main": str(paper / "main.tex"), "reference": str(reference)},
        }
        plan_sections = {
            "abstract": [{"id": "A1", "purpose": "Abstract.", "reference_lines": [1, 3], "artifacts": []}],
            "introduction": [{"id": f"I{i}", "purpose": f"Introduction {i}.", "reference_lines": [i + 3, i + 4], "artifacts": ["F1"] if i == 1 else []} for i in range(1, 7)],
            "related_work": [
                {"id": "R1", "heading": "Safety alignment and refusal behavior.", "heading_style": "textbf", "purpose": "Related work one.", "reference_lines": [20, 24], "artifacts": []},
                {"id": "R2", "heading": "Jailbreak attacks.", "heading_style": "textbf", "purpose": "Related work two.", "reference_lines": [25, 29], "artifacts": []},
            ],
            "method": [{"id": f"M{i}", "heading": ["Overview", "Style Representation", "Intervention", "Two-Turn Execution"][i-1], "heading_style": "subsection", "purpose": f"Method {i}.", "reference_lines": [30 + i, 31 + i], "artifacts": ["F3"] if i == 4 else []} for i in range(1, 5)],
            "representation_analysis": [{"id": f"RA{i}", "purpose": f"Representation {i}.", "reference_lines": [40 + i, 41 + i], "artifacts": ["F2"] if i == 4 else []} for i in range(1, 5)],
            "experiments": [
                {"id": "E1", "heading": "Experimental Setup", "heading_style": "subsection", "purpose": "Setup.", "reference_lines": [50, 52], "artifacts": []},
                {"id": "E2", "heading": "Main Results", "heading_style": "subsection", "purpose": "Main results.", "reference_lines": [53, 55], "artifacts": ["T1"]},
                {"id": "E3", "purpose": "Further analysis.", "reference_lines": [56, 58], "artifacts": ["F4"]},
            ],
            "analysis_discussion": [{"id": "D1", "purpose": "Defense analysis.", "reference_lines": [60, 64], "artifacts": ["F5", "T2"]}],
            "conclusion": [{"id": "C1", "purpose": "Conclusion.", "reference_lines": [70, 72], "artifacts": []}],
            "appendix": [{"id": "AP1", "purpose": "Appendix setup.", "reference_lines": [80, 82], "artifacts": []}, {"id": "AP2", "purpose": "Layerwise appendix.", "reference_lines": [83, 86], "artifacts": ["F6"]}],
        }
        for paragraphs in plan_sections.values():
            for index, paragraph in enumerate(paragraphs):
                paragraph.setdefault("rhetorical_role", "approved test role")
                paragraph.setdefault("relation_to_previous", "opening" if index == 0 else "continues prior paragraph")
                paragraph.setdefault("relation_to_next", "closing" if index == len(paragraphs) - 1 else "prepares next paragraph")
        for section in section_specs:
            section["paragraphs"] = plan_sections[section["id"]]
        config_file = paper / "paper_studio.json"
        reference_context_file = paper / "reference_context.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        reference_context_file.write_text(
            json.dumps(
                {
                    "sections": {
                        item["id"]: {
                            "source_heading": item["title"],
                            "logic_summary_zh": f"用于测试 {item['title']} 的节级参考上下文。",
                            "excerpts": [{"text": f"Reference context for {item['title']}."}],
                        }
                        for item in section_specs
                    },
                }
            ),
            encoding="utf-8",
        )
        inputs = []
        for section in section_specs:
            path = paper / "sections" / section["file"]
            path.write_text("% fixture\n", encoding="utf-8")
            if section["id"] == "abstract":
                inputs.append(f"\\begin{{abstract}}\\input{{sections/{Path(section['file']).stem}}}\\end{{abstract}}")
            else:
                inputs.append(f"\\input{{sections/{Path(section['file']).stem}}}")
        (paper / "main.tex").write_text(
            "\\documentclass{article}\n\\title{Style Jailbreak}\n\\begin{document}\n"
            + "\n".join(inputs) + "\n\\end{document}\n",
            encoding="utf-8",
        )
        cls.originals = {
            "PAPER": studio.PAPER, "STATE_DIR": studio.STATE_DIR, "STATE_FILE": studio.STATE_FILE,
            "PROJECT_CONFIG_FILE": studio.PROJECT_CONFIG_FILE,
            "REFERENCE_CONTEXT_FILE": studio.REFERENCE_CONTEXT_FILE,
            "FIGURE_DIR": studio.FIGURE_DIR, "FIGURE_SOURCE_DIR": studio.FIGURE_SOURCE_DIR,
            "DATA_FIGURE_AGENT_DIR": studio.DATA_FIGURE_AGENT_DIR, "TABLE_PREVIEW_DIR": studio.TABLE_PREVIEW_DIR,
            "PAPER_PAGE_DIR": studio.PAPER_PAGE_DIR, "METRICS_FILE": studio.METRICS_FILE,
            "PROJECT_ID": studio.PROJECT_ID, "EMPTY_PROJECT_MODE": studio.EMPTY_PROJECT_MODE,
        }
        studio.PAPER = paper
        studio.STATE_DIR = paper / ".paper_studio"
        studio.STATE_FILE = studio.STATE_DIR / "state.json"
        studio.PROJECT_CONFIG_FILE = config_file
        studio.REFERENCE_CONTEXT_FILE = reference_context_file
        studio.FIGURE_DIR = paper / "fig"
        studio.FIGURE_SOURCE_DIR = paper / "figsrc"
        studio.DATA_FIGURE_AGENT_DIR = studio.FIGURE_SOURCE_DIR / "data_agents"
        studio.TABLE_PREVIEW_DIR = studio.STATE_DIR / "table_previews"
        studio.PAPER_PAGE_DIR = studio.STATE_DIR / "paper_pages"
        studio.METRICS_FILE = metrics_file
        studio.PROJECT_ID = config["project"]["id"]
        studio.EMPTY_PROJECT_MODE = False
        studio.PROJECT_CONFIG.clear(); studio.PROJECT_CONFIG.update(config)
        studio.PROJECT_METADATA.clear(); studio.PROJECT_METADATA.update(config["project"])
        studio.SECTION_SPECS[:] = section_specs
        studio.SECTIONS[:] = [(item["id"], item["title"], item["file"]) for item in section_specs]
        studio.SECTION_MAP.clear(); studio.SECTION_MAP.update({item["id"]: {"title": item["title"], "file": item["file"], "render": item.get("render", "section"), "latex_title": item.get("latex_title", ""), "end_label": item.get("end_label", "")} for item in section_specs})
        studio.SECTION_LATEX_TITLES.clear(); studio.SECTION_LATEX_TITLES.update({item["id"]: item["latex_title"] for item in section_specs if item.get("latex_title")})
        studio.RESULT_KEYS.clear(); studio.RESULT_KEYS.update({item["id"]: item["result_keys"] for item in section_specs})
        studio.FIGURES.clear(); studio.FIGURES.update(figures)
        studio.FIGURE_ORDER[:] = config["figure_order"]
        studio.TABLES.clear(); studio.TABLES.update(tables)
        studio.TABLE_ORDER[:] = config["table_order"]

    @classmethod
    def tearDownClass(cls):
        for name, value in cls.originals.items():
            setattr(studio, name, value)
        cls.fixture_directory.cleanup()

    def test_api_key_setup_is_actionable_without_exposing_secret(self):
        with patch.dict(studio.os.environ, {}, clear=True):
            missing = public_state(_default_state())
            with self.assertRaisesRegex(StudioError, "启动 Paper Studio 的本机终端"):
                studio.post_openai({"model": "deepseek-v4-flash", "input": "test"})
        self.assertFalse(missing["api_key_configured"])
        self.assertEqual(
            missing["api_key_setup"]["environment_variable"], "DEEPSEEK_API_KEY"
        )
        self.assertIn("export DEEPSEEK_API_KEY", missing["api_key_setup"]["setup_command"])
        self.assertIn("python3 -m research_avatar.paper_studio.server", missing["api_key_setup"]["restart_command"])

        secret = "must-never-reach-public-state"
        with patch.dict(studio.os.environ, {"DEEPSEEK_API_KEY": secret}):
            configured = public_state(_default_state())
        self.assertTrue(configured["api_key_configured"])
        self.assertNotIn(secret, json.dumps(configured, ensure_ascii=False))

        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="model-runtime-config"', html)
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="api-key-setup"', html)
        self.assertIn("写论文需要 LLM API", html)
        self.assertNotIn('value="compatible"', html)
        self.assertEqual(
            [item["id"] for item in configured["llm_provider_options"]],
            ["openai", "deepseek"],
        )
        self.assertEqual(
            [item["id"] for item in configured["llm_model_options"]],
            ["deepseek-v4-pro", "deepseek-v4-flash"],
        )
        self.assertIn('$("api-key-setup").hidden = apiKeyReady', source)

    def test_deepseek_text_provider_uses_chat_completions_without_exposing_key(self):
        secret = "deepseek-secret-must-stay-server-side"
        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "id": "chatcmpl-test",
                "choices": [{"message": {"content": "Draft paragraph."}}],
            }
        ).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with (
            patch.dict(studio.os.environ, {"DEEPSEEK_API_KEY": secret}, clear=True),
            patch.object(studio.urllib.request, "urlopen", return_value=response) as urlopen,
        ):
            body = studio.post_openai(
                {
                    "model": "deepseek-v4-flash",
                    "instructions": "Return prose only.",
                    "input": "Write one paragraph.",
                },
                provider="deepseek",
            )
            state = _default_state()
            state["llm_provider"] = "deepseek"
            visible = public_state(state)
        request = urlopen.call_args.args[0]
        sent = json.loads(request.data.decode("utf-8"))
        self.assertTrue(request.full_url.endswith("/chat/completions"))
        self.assertEqual(sent["messages"][0]["role"], "system")
        self.assertEqual(sent["thinking"], {"type": "disabled"})
        self.assertEqual(sent["max_tokens"], studio.DEEPSEEK_PAPER_MAX_OUTPUT_TOKENS)
        self.assertEqual(extract_output_text(body), "Draft paragraph.")
        self.assertEqual(visible["api_key_setup"]["environment_variable"], "DEEPSEEK_API_KEY")
        self.assertNotIn(secret, json.dumps(visible, ensure_ascii=False))

    def test_provider_selection_is_limited_to_openai_and_deepseek(self):
        state = _default_state()
        state["llm_provider"] = "openai"
        state["model"] = studio.PROVIDER_DEFAULT_MODELS["openai"]
        state["title_editor"]["previous_response_id"] = "title-old"
        first_section = next(iter(state["sections"].values()))
        first_section["previous_response_id"] = "section-old"
        self.assertTrue(studio.select_llm_provider(state, "deepseek"))
        self.assertEqual(state["llm_provider"], "deepseek")
        self.assertEqual(state["model"], studio.PROVIDER_DEFAULT_MODELS["deepseek"])
        self.assertIsNone(state["title_editor"]["previous_response_id"])
        self.assertIsNone(first_section["previous_response_id"])
        with self.assertRaisesRegex(StudioError, "不支持的 LLM API"):
            studio.select_llm_provider(state, "compatible")

    def test_model_selection_accepts_researcher_input_and_resets_all_llm_chains(self):
        state = _default_state()
        state["title_editor"]["previous_response_id"] = "title-old"
        first_section = next(iter(state["sections"].values()))
        first_section["previous_response_id"] = "section-old"
        first_figure = next(iter(state["figures"].values()))
        first_figure["previous_response_id"] = "figure-old"
        self.assertTrue(studio.select_llm_model(state, "gpt-5-mini"))
        self.assertEqual(state["model"], "gpt-5-mini")
        self.assertIsNone(state["title_editor"]["previous_response_id"])
        self.assertIsNone(first_section["previous_response_id"])
        self.assertIsNone(first_figure["previous_response_id"])
        self.assertTrue(studio.select_llm_model(state, "gpt-5.9-research-preview"))
        self.assertEqual(state["model"], "gpt-5.9-research-preview")
        with self.assertRaisesRegex(StudioError, "不含空格"):
            studio.select_llm_model(state, "invalid model")

        state["llm_provider"] = "deepseek"
        state["model"] = "deepseek-v4-flash"
        self.assertEqual(
            [item["id"] for item in studio.model_options_for_provider("deepseek")],
            ["deepseek-v4-pro", "deepseek-v4-flash"],
        )

    def test_human_figure_label_produces_safe_paths_without_colon(self):
        original = FIGURES["F2"]["label"]
        try:
            FIGURES["F2"]["label"] = "Representation Analysis"
            paths = studio.figure_paths("F2")
            panel_paths = studio.data_panel_paths("F2", "a")
            self.assertEqual(paths["spec"].name, "Representation_Analysis_spec.json")
            self.assertIn("Representation_Analysis", panel_paths["source"].name)
        finally:
            FIGURES["F2"]["label"] = original

    def test_cancelled_preview_response_does_not_emit_handler_traceback(self):
        class ClosedSocket:
            def write(self, _data):
                raise BrokenPipeError("browser closed preview")

        handler = object.__new__(studio.Handler)
        handler.wfile = ClosedSocket()
        handler.close_connection = False
        handler.write_body(b"preview")
        self.assertTrue(handler.close_connection)

    def test_request_body_must_be_a_json_object(self):
        handler = object.__new__(studio.Handler)
        handler.headers = {"Content-Length": "2"}
        handler.rfile = io.BytesIO(b"[]")
        with self.assertRaisesRegex(StudioError, "JSON object"):
            handler.read_json()

    def test_browser_interaction_inventory_is_explicit_and_complete(self):
        class InteractionParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.control_ids = []

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag in {"button", "input", "select", "textarea"} and attributes.get("id"):
                    self.control_ids.append(attributes["id"])

        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        browser_matrix = (
            studio.ROOT / "research_avatar" / "paper_studio" / "browser_matrix.py"
        ).read_text(encoding="utf-8")
        parser = InteractionParser()
        parser.feed(html)
        expected_controls = {
            "model", "model-apply", "reset-generated", "writing-view", "figures-view",
            "tables-view", "compile", "paper-title", "title-gpt-prompt",
            "title-generate", "title-save", "candidate", "comment", "generate",
            "accept", "section-draft-start", "pdf-navigation-toggle", "table-agent-prompt", "table-agent-edit",
            "figure-cancel", "draw-prompt", "prompt-instruction", "figure-prompt",
            "figure-draw", "figure-build", "single-data-prompt", "single-data-generate",
            "data-layout-prompt", "data-compose", "mechanism-preview-toggle",
            "figure-caption", "figure-caption-prompt", "figure-caption-generate",
            "figure-caption-save", "figure-placement", "figure-layout-mode",
            "data-approve", "figure-approve", "table-prompt", "table-generate",
            "table-latex", "table-save", "table-approve", "reset-generated-close",
            "reset-project-id", "reset-project-copy", "reset-project-confirm",
            "reset-generated-cancel", "reset-generated-confirm",
            "full-draft-start", "full-draft-cancel",
            "runtime-key-open", "runtime-key-close", "runtime-key-provider",
            "runtime-key-input", "runtime-key-cancel", "runtime-key-submit",
            "studio-language-select",
        }
        self.assertEqual(set(parser.control_ids), expected_controls)
        self.assertEqual(len(parser.control_ids), len(expected_controls))
        for control_id in expected_controls:
            self.assertIn(f'$("{control_id}")', source, control_id)
            self.assertTrue(
                f'#{control_id}' in browser_matrix or f'"{control_id}"' in browser_matrix,
                f"{control_id} is missing from the real-browser matrix",
            )

        dynamic_controls = {
            ".section-button",
            ".paragraph-nav button",
            ".figure-card",
            ".data-panel-generate",
            ".pdf-thumbnail",
        }
        for selector in dynamic_controls:
            self.assertIn(selector, source)
            self.assertIn(selector, browser_matrix)

        browser_api_paths = set(re.findall(r'"(/api/[^"?]+)"', source))
        self.assertEqual(
            browser_api_paths,
            {
                "/api/accept",
                "/api/compile", "/api/figure/approve", "/api/figure/build",
                "/api/full-draft/start", "/api/full-draft/cancel",
                "/api/section-draft/start",
                "/api/figure/cancel", "/api/figure/caption",
                "/api/figure/caption/generate", "/api/figure/compose",
                "/api/figure/draw", "/api/figure/panel/generate",
                "/api/figure/placement", "/api/figure/prompt", "/api/generate",
                "/api/llm-model",
                "/api/pdf/locate",
                "/api/runtime-key",
                "/api/reset-generated-paper", "/api/select-paragraph", "/api/state",
                "/api/table/agent-edit", "/api/table/approve", "/api/table/generate",
                "/api/table/placement", "/api/table/save", "/api/title/generate",
                "/api/title/save",
            },
        )
        for api_path in browser_api_paths:
            self.assertIn(api_path, browser_matrix, api_path)

    def test_default_writing_provider_is_low_cost_deepseek_flash(self):
        self.assertEqual(studio.DEFAULT_MODEL, "gpt-5-nano")
        self.assertEqual(studio.DEFAULT_PROVIDER, "deepseek")
        self.assertEqual(_default_state()["model"], "deepseek-v4-flash")

    def test_latex_prose_preflight_flags_raw_specials_and_unicode_math(self):
        issues = latex_prose_issues(
            r"Accuracy is 86.0% for H_s and μ ∈ R, with R&D #1."
        )
        self.assertIn("raw percent sign", issues)
        self.assertIn("raw underscore", issues)
        self.assertIn("raw ampersand", issues)
        self.assertIn("raw hash sign", issues)
        self.assertTrue(any(item.startswith("Unicode math glyphs:") for item in issues))

    def test_latex_prose_preflight_flags_raw_caret(self):
        # Regression: a real batch-writing run crashed pdflatex with
        # "! Missing $ inserted." from GPT prose that wrote a superscript
        # outside math mode ("ground-truth label y^{*}" instead of
        # "$y^{*}$"). The specials dict already caught raw "_" (subscript
        # outside math) but was missing "^" (superscript outside math),
        # which is exactly as unsafe.
        issues = latex_prose_issues("the ground-truth label y^{*} is fixed")
        self.assertIn("raw caret (superscript outside math)", issues)
        self.assertEqual(latex_prose_issues(r"the label $y^{*}$ is fixed"), [])

    def test_latex_prose_preflight_accepts_safe_math_and_reference_keys(self):
        self.assertEqual(
            latex_prose_issues(
                r"Accuracy is 86.0\% for \(H_s \in \mathbb{R}\); see "
                r"Figure~\ref{fig:layer_wise} and \cite{safe_key}."
            ),
            [],
        )

    def test_latex_prose_preflight_flags_math_commands_outside_math_mode(self):
        issues = latex_prose_issues(
            r"Temperature is 0, resulting in 100 \times 5 = 500 API calls."
        )
        self.assertIn(r"math command outside math delimiters: \times", issues)
        self.assertEqual(
            latex_prose_issues(
                r"Temperature is 0, resulting in \(100 \times 5 = 500\) API calls."
            ),
            [],
        )
        self.assertEqual(
            latex_prose_issues(
                r"\begin{equation}e_i(r)=E_i(r)/L_i\end{equation}"
            ),
            [],
        )

    def test_latex_prose_preflight_flags_set_notation_glyphs_not_in_old_fixed_list(self):
        # Regression: a live batch-writing run crashed pdflatex mid-job with
        # "! LaTeX Error: Unicode character ⊆ (U+2286) not set up for use
        # with LaTeX" from GPT-written prose ("a subset C_rand ⊆ C(x)") that
        # the preflight should have caught and rejected before it ever
        # reached pdflatex. The old check was a manually curated fixed set
        # (∈∉≤≥≠≈⋆⋅×÷±μΣδκΦλ−→←⇒∞) that simply never included ⊆ or any other
        # set-operation glyph (⊂ ⊇ ⊃ ∪ ∩ ∅ ...).
        issues = latex_prose_issues("a subset C_rand ⊆ C(x) of size k")
        self.assertTrue(any("⊆" in item for item in issues))
        for glyph in "⊂⊇⊃∪∩∅∀∃∘⊗⊕":
            self.assertTrue(
                any(glyph in item for item in latex_prose_issues(f"x {glyph} y")),
                f"{glyph!r} should be flagged as an unsafe Unicode math glyph",
            )

    def test_latex_prose_preflight_does_not_flag_ascii_symbol_math_category_chars(self):
        # Unicode classifies plain ASCII + < = > | ~ as category "Sm" (the
        # same category as ⊆, ∈, etc.), but these are ordinary pdflatex-safe
        # characters -- notably ~ in the common "Figure~\ref{}" convention.
        # Only non-ASCII glyphs are an actual rendering hazard.
        self.assertEqual(latex_prose_issues("a + b < c = d > e | f ~ g"), [])

    def test_latex_prose_preflight_flags_unbalanced_math_delimiters(self):
        # Regression: a live batch-writing run crashed pdflatex with
        # "! Missing $ inserted." from GPT prose that opened a math
        # delimiter and never closed it. Because the masking step only
        # strips *correctly paired* math, a stray delimiter passed through
        # untouched and reached pdflatex, which then reported the error in
        # whatever file happened to compile next -- nowhere near the actual
        # cause. The preflight must catch delimiter imbalance directly.
        issues = latex_prose_issues(r"we compute $q = \lfloor B / |\mathcal{I}\rfloor")
        self.assertIn("unbalanced $ math delimiters (odd count)", issues)

        issues = latex_prose_issues(r"we compute \(q = \lfloor B / |\mathcal{I}\rfloor")
        self.assertIn("unbalanced \\( \\) math delimiters", issues)

        issues = latex_prose_issues(r"see \[x = y\] and also \[z = w")
        self.assertIn("unbalanced \\[ \\] math delimiters", issues)

        self.assertEqual(latex_prose_issues(r"a price of \$5 is fine"), [])
        self.assertEqual(latex_prose_issues(r"\(H_s \in \mathbb{R}\) is balanced"), [])

    def test_latex_normalization_canonicalizes_decorated_citation_placeholder(self):
        self.assertEqual(
            normalize_latex_ready_text(
                r"Claim [CITATION NEEDED; \cite{provisional_key}]."
            ),
            "Claim [CITATION NEEDED].",
        )

    def test_latex_normalization_removes_inline_delimiters_nested_in_display_math(self):
        self.assertEqual(
            normalize_latex_ready_text(r"Before. \[\(x = y\).\] After."),
            r"Before. \[x = y.\] After.",
        )
        self.assertEqual(
            normalize_latex_ready_text(
                r"\begin{equation}\(A(r)=A(0)-r\)\end{equation}"
            ),
            r"\begin{equation}A(r)=A(0)-r\end{equation}",
        )
        self.assertEqual(
            normalize_latex_ready_text(
                "\\begin{equation}\n\nA(r)=A(0)-r\n\n\\end{equation}"
            ),
            "\\begin{equation}\nA(r)=A(0)-r\n\\end{equation}",
        )
        self.assertEqual(
            normalize_latex_ready_text("\\[\n\nx=y\n\n\\]"),
            "\\[\nx=y\n\\]",
        )

    def test_latex_normalization_keeps_synthetic_marker_out_of_math_mode(self):
        self.assertEqual(
            normalize_latex_ready_text(r"Values are \[SYNTHETIC\] only."),
            "Values are [SYNTHETIC] only.",
        )
        self.assertEqual(
            normalize_latex_ready_text("The value is 0.73[SYNTHETIC]and bounded."),
            "The value is 0.73 [SYNTHETIC] and bounded.",
        )

    def test_latex_normalization_uses_breakable_path_for_repository_files(self):
        self.assertEqual(
            normalize_latex_ready_text(
                r"Stored in \texttt{results/steering\_commutator/metrics.json}."
            ),
            r"Stored in \path{results/steering_commutator/metrics.json}.",
        )
        self.assertEqual(
            normalize_latex_ready_text(r"Use \texttt{prompt_id} as the key."),
            r"Use \texttt{prompt\_id} as the key.",
        )

    def test_latex_normalization_escapes_prose_specials_but_preserves_math_and_keys(self):
        self.assertEqual(
            normalize_latex_ready_text(
                r"restaurant_reviews reaches 10% & see \(x_i=1\), \cite{safe_key}."
            ),
            r"restaurant\_reviews reaches 10\% \& see \(x_i=1\), \cite{safe_key}.",
        )

    def test_table_cell_escape_converts_direction_arrows_to_latex_math(self):
        self.assertEqual(
            studio.latex_escape_cell("Accuracy ↑ / Spearman ρ / Drop ↓ / ✓ / ≤"),
            r"Accuracy $\uparrow$ / Spearman $\rho$ / Drop $\downarrow$ / Yes / $\leq$",
        )

    def test_newer_accepted_section_survives_an_unrelated_stale_save(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
            ):
                initial = _default_state()
                studio.save_state(initial)
                stale_background_request = studio.load_state()

                accepted = studio.load_state()
                section = accepted["sections"]["introduction"]
                section["paragraphs"][0]["accepted_text"] = "Newest accepted prose."
                section["revision"] = int(section.get("revision", 0)) + 1
                studio.save_state(accepted)

                stale_background_request["model"] = "background-model"
                studio.save_state(stale_background_request)
                recovered = studio.load_state()

        self.assertEqual(recovered["model"], "background-model")
        self.assertEqual(
            recovered["sections"]["introduction"]["paragraphs"][0]["accepted_text"],
            "Newest accepted prose.",
        )

    def test_image_cancel_terminates_process_and_preserves_prompt_and_draft(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            state_file = state_dir / "state.json"
            source_dir = root / "figsrc"
            figure_dir = root / "fig"
            process = subprocess.Popen(
                ["python3", "-c", "import time; time.sleep(30)"],
                start_new_session=True,
            )
            token = "cancel-image-job"
            try:
                with (
                    patch.object(studio, "STATE_DIR", state_dir),
                    patch.object(studio, "STATE_FILE", state_file),
                    patch.object(studio, "FIGURE_SOURCE_DIR", source_dir),
                    patch.object(studio, "FIGURE_DIR", figure_dir),
                ):
                    paths = studio.figure_paths("F1")
                    paths["draft"].parent.mkdir(parents=True)
                    paths["draft"].write_bytes(b"previous completed draft")
                    state = _default_state()
                    figure = state["figures"]["F1"]
                    figure.update(
                        {
                            "status": "image_generating",
                            "draw_prompt": "Keep this researcher-approved prompt.",
                        }
                    )
                    studio.begin_figure_job(figure, token)
                    studio.save_state(state)
                    with studio.FIGURE_PROCESS_LOCK:
                        studio.RUNNING_FIGURE_PROCESSES[token] = process

                    cancelled = studio.cancel_figure_job("F1")
                    process.wait(timeout=3)

                recovered = cancelled["figures"]["F1"]
                self.assertEqual(recovered["status"], "draft")
                self.assertEqual(
                    recovered["draw_prompt"],
                    "Keep this researcher-approved prompt.",
                )
                self.assertIsNone(recovered["job_token"])
                self.assertIn("上一版草图", recovered["last_message"])
                self.assertIsNotNone(process.returncode)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=3)
                with studio.FIGURE_PROCESS_LOCK:
                    studio.RUNNING_FIGURE_PROCESSES.pop(token, None)
                    studio.CANCELLED_FIGURE_JOBS.discard(token)

    def test_image_cancel_control_is_bound_to_running_image_state(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="figure-cancel" class="danger" hidden', html)
        self.assertIn("⏸ 停止调用", html)
        progress_start = html.index('id="figure-progress"')
        progress_end = html.index('id="mechanism-controls"')
        self.assertTrue(progress_start < html.index('id="figure-cancel"') < progress_end)
        self.assertLess(html.index('id="figure-progress-bar"'), html.index('id="figure-cancel"'))
        self.assertIn(
            '$("figure-cancel").hidden = figure.status !== "image_generating"',
            source,
        )
        self.assertIn(
            '$("figure-cancel").disabled = figure.status !== "image_generating"',
            source,
        )
        self.assertIn('request("/api/figure/cancel"', source)

    def test_completed_gpt_image_automatically_builds_pptx_and_pdf(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            token = "draw-and-build"
            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(studio, "draw_mechanism_draft") as draw,
                patch.object(
                    studio,
                    "build_mechanism_figure",
                    return_value="PPTX/PDF ready.",
                ) as build,
            ):
                state = _default_state()
                figure = state["figures"]["F1"]
                figure["status"] = "image_generating"
                studio.begin_figure_job(figure, token)
                studio.save_state(state)

                studio.draw_figure_worker("F1", token, "approved image prompt")
                finished = studio.load_state()["figures"]["F1"]

            draw.assert_called_once_with(
                "F1", "approved image prompt", job_token=token
            )
            build.assert_called_once_with("F1", job_token=token)
            self.assertEqual(finished["status"], "built")
            self.assertIsNone(finished["job_token"])
            self.assertIn("直接确认插入正文", finished["last_message"])

    def test_manual_editable_build_button_only_appears_after_failure(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="figure-build" class="secondary" hidden', html)
        self.assertIn('figure.status === "failed"', source)
        self.assertIn('$("figure-build").hidden = !mechanismBuildFailed', source)
        self.assertNotIn("mechanismRebuildAvailable", source)

    def test_empty_shell_public_state_needs_no_paper_project(self):
        with patch.object(studio, "EMPTY_PROJECT_MODE", True):
            visible = public_state(_default_state())
        self.assertFalse(visible["project"]["loaded"])
        self.assertEqual(visible["sections"], {})
        self.assertEqual(visible["figures"], [])
        self.assertFalse(visible["pdf"]["exists"])
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('project.loaded === false', source)
        self.assertIn('id="empty-project"', html)
        self.assertIn("python3 -m research_avatar.paper_studio.server --empty", html)

    def test_missing_project_config_falls_back_to_empty_shell(self):
        with (
            patch.object(studio, "EMPTY_PROJECT_MODE", False),
            patch.object(
                studio,
                "PROJECT_CONFIG_FILE",
                studio.ROOT / "paper" / "missing-paper-studio-for-test.json",
            ),
        ):
            visible = public_state(_default_state())

        self.assertFalse(visible["project"]["loaded"])
        self.assertEqual(visible["project_id"], "__paper_studio_empty__")
        self.assertEqual(visible["sections"], {})

    def test_health_endpoint_does_not_load_paper_state(self):
        handler = object.__new__(Handler)
        handler.path = "/api/health"
        response = {}
        handler.send_json = lambda payload, status=200: response.update(payload)

        with patch.object(studio, "project_files_ready", return_value=False):
            handler.do_GET()

        self.assertTrue(response["ok"])
        self.assertEqual(Path(response["project"]["root"]), studio.ROOT)
        self.assertTrue(response["empty_project"])
        self.assertIsInstance(response["pid"], int)

    def test_newer_figure_job_state_survives_an_unrelated_stale_save(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
            ):
                initial = _default_state()
                studio.begin_figure_job(initial["figures"]["F1"], "job-1")
                initial["figures"]["F1"]["status"] = "image_generating"
                studio.save_state(initial)
                stale_prose_request = studio.load_state()

                completed = studio.load_state()
                completed_figure = completed["figures"]["F1"]
                completed_figure.update({"status": "draft", "job_token": None})
                completed_figure["job_revision"] += 1
                studio.save_state(completed)

                stale_prose_request["model"] = "prose-request-model"
                studio.save_state(stale_prose_request)
                recovered = studio.load_state()

        self.assertEqual(recovered["model"], "prose-request-model")
        self.assertEqual(recovered["figures"]["F1"]["status"], "draft")
        self.assertIsNone(recovered["figures"]["F1"]["job_token"])

    def test_restart_recovers_a_completed_image_artifact(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            state_file = state_dir / "state.json"
            source_dir = root / "figsrc"
            figure_dir = root / "fig"
            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(studio, "FIGURE_SOURCE_DIR", source_dir),
                patch.object(studio, "FIGURE_DIR", figure_dir),
            ):
                paths = studio.figure_paths("F1")
                paths["spec"].parent.mkdir(parents=True)
                paths["draft"].write_bytes(b"completed image")
                paths["spec"].write_text(
                    json.dumps({"figure_id": "recovery-test"}), encoding="utf-8"
                )
                iterations = source_dir / "iterations" / "recovery-test"
                iterations.mkdir(parents=True)
                (iterations / "round_01.prompt.txt").write_text(
                    "the approved prompt", encoding="utf-8"
                )
                state = _default_state()
                figure = state["figures"]["F1"]
                figure.update(
                    {
                        "status": "image_generating",
                        "draw_prompt": "the approved prompt",
                        "prompt_approved_at": 0,
                    }
                )
                studio.begin_figure_job(figure, "job-recovery")
                studio.save_state(state)
                studio.recover_interrupted_figure_jobs()
                recovered = studio.load_state()["figures"]["F1"]

        self.assertEqual(recovered["status"], "draft")
        self.assertEqual(recovered["progress"], 100)
        self.assertIn("恢复", recovered["last_message"])
        self.assertIsNone(recovered["job_token"])

    def test_json_double_escaped_latex_commands_are_normalized(self):
        source = r"Prior work \\cite{paper}. See Figure~\\ref{fig:one}."
        normalized = normalize_latex_ready_text(source)
        self.assertEqual(normalized, r"Prior work \cite{paper}. See Figure~\ref{fig:one}.")
        self.assertEqual(normalize_latex_ready_text(r"first\\second"), r"first\\second")

    def test_shape_spec_has_one_unattended_vector_pdf_source(self):
        source = shape_spec_html(
            {
                "canvas_in": [3.0, 2.0],
                "shapes": [
                    {
                        "kind": "rounded_rect",
                        "x": 0.1,
                        "y": 0.2,
                        "w": 0.8,
                        "h": 0.4,
                        "fill": "FFFFFF",
                        "line": "123456",
                        "text": "Editable source",
                    },
                    {
                        "kind": "arrow",
                        "x1": 0.2,
                        "y1": 0.8,
                        "x2": 0.8,
                        "y2": 0.8,
                    },
                ],
            }
        )
        self.assertIn("@page{size:3.0in 2.0in;margin:0}", source)
        self.assertIn("Editable source", source)
        self.assertIn("foreignObject", source)
        self.assertIn('marker-end="url(#arrowhead)"', source)

    def test_mechanism_shape_spec_rejects_placeholder_rebuild(self):
        with self.assertRaisesRegex(StudioError, "placeholder"):
            validate_mechanism_shape_spec(
                "F1",
                {
                    "canvas_in": [3.32, 2.35],
                    "shapes": [
                        {"kind": "textbox", "x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2},
                        {"kind": "rounded_rect", "x": 0.1, "y": 0.4, "w": 0.8, "h": 0.4},
                    ],
                },
            )

    def test_mechanism_shape_spec_accepts_rich_editable_rebuild(self):
        shapes = [
            {"kind": "rounded_rect", "x": 0.05 + i * 0.15, "y": 0.2, "w": 0.12, "h": 0.2}
            for i in range(4)
        ]
        shapes += [
            {"kind": "arrow", "x1": 0.17, "y1": 0.3, "x2": 0.2, "y2": 0.3},
            {"kind": "arrow", "x1": 0.32, "y1": 0.3, "x2": 0.35, "y2": 0.3},
        ]
        shapes += [
            {"kind": "textbox", "x": 0.05, "y": 0.5 + i * 0.04, "w": 0.8, "h": 0.03}
            for i in range(6)
        ]
        result = validate_mechanism_shape_spec(
            "F1", {"canvas_in": [99, 99], "shapes": shapes}
        )
        self.assertEqual(result["figure_id"], "overview_gpt")
        self.assertEqual(result["canvas_in"], studio.initial_mechanism_spec("F1")["canvas_in"])
        self.assertEqual(len(result["shapes"]), 12)

    def test_mechanism_shape_spec_rejects_unreadable_text(self):
        shapes = [
            {"kind": "rounded_rect", "x": 0.05 + i * 0.15, "y": 0.2, "w": 0.12, "h": 0.2}
            for i in range(4)
        ]
        shapes += [
            {"kind": "arrow", "x1": 0.17, "y1": 0.3, "x2": 0.2, "y2": 0.3},
            {"kind": "arrow", "x1": 0.32, "y1": 0.3, "x2": 0.35, "y2": 0.3},
        ]
        shapes += [
            {"kind": "textbox", "x": 0.05, "y": 0.5 + i * 0.04, "w": 0.8, "h": 0.03}
            for i in range(5)
        ]
        shapes.append(
            {
                "kind": "textbox",
                "x": 0.05,
                "y": 0.75,
                "w": 0.1,
                "h": 0.03,
                "text": "This label cannot fit",
                "font_size": 6,
            }
        )
        with self.assertRaisesRegex(StudioError, "小于 7pt"):
            validate_mechanism_shape_spec(
                "F1", {"canvas_in": [3.32, 2.35], "shapes": shapes}
            )

    def test_mechanism_text_normalization_expands_short_boxes(self):
        raw = {
            "shapes": [
                {
                    "kind": "textbox",
                    "x": 0.1,
                    "y": 0.2,
                    "w": 0.15,
                    "h": 0.02,
                    "text": "Two line label",
                    "font_size": 5,
                }
            ]
        }
        normalized = normalize_mechanism_text_boxes("F1", raw)
        self.assertEqual(normalized["shapes"][0]["font_size"], 7)
        self.assertGreater(normalized["shapes"][0]["h"], 0.02)
        self.assertEqual(raw["shapes"][0]["font_size"], 5)

    def test_external_traceback_is_not_exposed_to_the_browser(self):
        failed = CompletedProcess(
            ["figure-tool"],
            1,
            stdout="Traceback (most recent call last):\n  noisy internals\nRuntimeError: concise",
            stderr="",
        )
        with patch.object(studio.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(StudioError, "外部绘图工具执行失败：RuntimeError: concise") as caught:
                studio.run_checked(["figure-tool"], cwd=Path("."))
        self.assertNotIn("Traceback", str(caught.exception))

    def test_accepted_paragraph_can_be_edited_directly_and_accepted_again(self):
        paragraph = {
            "id": "P1",
            "purpose": "Revise prose.",
            "accepted_text": "Accepted original.",
            "candidate": None,
        }
        candidate, text = candidate_for_accept(
            paragraph,
            candidate_id="",
            submitted_text="Accepted revised.",
            base_text="Accepted original.",
        )
        self.assertEqual(text, "Accepted revised.")
        self.assertEqual(candidate["source"], "manual_edit")
        self.assertIs(paragraph["candidate"], candidate)

    def test_unaccepted_paragraph_can_be_drafted_directly(self):
        paragraph = {
            "id": "P1",
            "purpose": "Draft prose.",
            "accepted_text": "",
            "candidate": None,
        }
        candidate, text = candidate_for_accept(
            paragraph,
            candidate_id="",
            submitted_text="Researcher-authored first draft.",
            base_text="",
        )
        self.assertEqual(text, "Researcher-authored first draft.")
        self.assertEqual(candidate["source"], "manual_draft")
        self.assertIs(paragraph["candidate"], candidate)

    def test_browser_preserves_manual_text_against_automatic_generation(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('|| $("candidate").dataset.dirty === "true"', source)
        self.assertIn('automatic && $("candidate").dataset.dirty === "true"', source)
        self.assertIn("已保留你正在编辑的正文", source)

    def test_direct_edit_rejects_a_stale_accepted_base(self):
        paragraph = {
            "id": "P1",
            "purpose": "Revise prose.",
            "accepted_text": "New server version.",
            "candidate": None,
        }
        with self.assertRaisesRegex(StudioError, "已在别处更新"):
            candidate_for_accept(
                paragraph,
                candidate_id="",
                submitted_text="My revision.",
                base_text="Old browser version.",
            )

    def test_manual_edits_to_a_gpt_candidate_are_the_text_that_gets_accepted(self):
        paragraph = {
            "id": "P1",
            "accepted_text": "",
            "candidate": {"id": "candidate-1", "text": "GPT draft."},
        }
        candidate, text = candidate_for_accept(
            paragraph,
            candidate_id="candidate-1",
            submitted_text="Researcher-edited draft.",
            base_text="GPT draft.",
        )
        self.assertEqual(text, "Researcher-edited draft.")
        self.assertEqual(candidate["text"], text)

    def test_accept_rejects_a_candidate_that_breaks_artifact_reference_contract(self):
        state = _default_state()
        paragraph = state["sections"]["introduction"]["paragraphs"][0]
        paragraph["candidate"] = {
            "id": "candidate-without-f1",
            "text": "The motivation is clear without a cross-reference.",
            "citations_added": [],
        }
        handler = object.__new__(Handler)
        handler.require_section = lambda body: "introduction"

        with patch.object(studio, "load_state", return_value=state):
            with self.assertRaisesRegex(StudioError, r"缺少 Figure~\\ref\{fig:overview\}"):
                handler.handle_accept(
                    {
                        "section": "introduction",
                        "candidate_id": "candidate-without-f1",
                    }
                )

    def test_title_editor_is_visible_and_gpt_candidate_is_not_auto_saved(self):
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="paper-title"', html)
        self.assertIn('id="title-editor" class="title-editor" open hidden', html)
        self.assertIn('id="title-gpt-prompt"', html)
        self.assertIn('id="title-generate"', html)
        self.assertIn('id="title-save"', html)
        self.assertIn('"/api/title/generate"', source)
        self.assertIn('"/api/title/save"', source)
        self.assertIn("GPT candidate 尚未保存", source)
        self.assertIn("function updateTitleSaveButton()", source)
        self.assertIn('changed ? "确认写入 LaTeX" : "已写入 PDF"', source)
        self.assertIn("currentTitle", source)
        self.assertIn('$("title-editor").hidden = activeSection !== "abstract"', source)
        self.assertIn('if (activeSection === "abstract") renderTitleEditor()', source)
        self.assertLess(html.index('id="title-generate"'), html.index('id="title-save"'))

    def test_fresh_studio_navigation_starts_in_abstract_writing_view(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        index = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            'if (["writing", "figures", "tables"].includes(requested)) return requested;',
            source,
        )
        self.assertIn('return "writing";', source)
        self.assertIn('if (requested) return requested;', source)
        self.assertIn('return "abstract";', source)
        self.assertNotIn("paper-studio.active-section", source)
        self.assertNotIn("paper-studio.active-view", source)
        self.assertIn("static/app.js?v=20260823.14-table-layout", index)

    def test_full_draft_click_queues_behind_an_inflight_paragraph_generation(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn("let queuedFullDraftStart = false", source)
        self.assertIn("if (proseRequestBusy) {\n    queuedFullDraftStart = true;", source)
        self.assertIn("当前段落生成完成后将自动启动全文初稿任务", source)
        self.assertIn(
            "if (queuedFullDraftStart) {\n      queuedFullDraftStart = false;\n"
            "      void startFullDraftFromBrowser();",
            source,
        )
        self.assertIn(
            'fullDraftRequestBusy\n          || queuedFullDraftStart\n'
            '          || (job && job.status === "running")',
            source,
        )

    def test_full_draft_api_uses_persisted_provider_model_when_body_omits_model(self):
        handler = object.__new__(Handler)
        handler.send_json = MagicMock()
        persisted = {"model": "deepseek-v4-flash"}
        started = {"model": "deepseek-v4-flash"}
        with (
            patch.object(studio, "load_state", return_value=persisted),
            patch.object(
                studio,
                "start_full_draft_job",
                return_value=("job-token", started),
            ) as start,
            patch.object(studio.threading, "Thread") as thread,
            patch.object(studio, "public_state", return_value={}),
        ):
            handler.handle_full_draft_start({})

        start.assert_called_once_with("deepseek-v4-flash")
        thread.assert_called_once()

    def test_section_draft_api_passes_the_selected_section_to_the_batch_writer(self):
        handler = object.__new__(Handler)
        handler.send_json = MagicMock()
        section = studio.batch_writing_order()[0]
        persisted = {"model": "deepseek-v4-flash"}
        started = {"model": "deepseek-v4-flash"}
        with (
            patch.object(studio, "load_state", return_value=persisted),
            patch.object(
                studio,
                "start_section_draft_job",
                return_value=("job-token", started),
            ) as start,
            patch.object(studio.threading, "Thread") as thread,
            patch.object(studio, "public_state", return_value={}),
        ):
            handler.handle_section_draft_start({"section": section})

        start.assert_called_once_with("deepseek-v4-flash", section)
        thread.assert_called_once()

    def test_full_draft_uses_the_same_outline_approval_rule_as_public_state(self):
        source = Path(studio.__file__).read_text(encoding="utf-8")
        offset = source.index("def start_full_draft_job")
        start = source[offset : source.index("\ndef ", offset + 5)]
        self.assertIn("if not outline_is_confirmed():", start)
        self.assertNotIn('if not (PAPER / ".outline-approved").exists():', start)

    def test_accept_renders_compiled_pdf_before_waiting_for_next_gpt_candidate(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        accept = source[source.index("async function acceptCurrent()") : source.index(
            '$("accept").addEventListener'
        )]
        immediate_render = accept.index("state = payload.state;")
        next_generation = accept.index('request("/api/generate"', immediate_render)
        self.assertLess(accept.index("render();", immediate_render), next_generation)
        self.assertIn("正在后台准备", accept)

    def test_refresh_labels_an_accepted_paragraph_as_already_written(self):
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        candidate_tag = html[html.index('<textarea id="candidate"') : html.index("></textarea>", html.index('<textarea id="candidate"'))]
        self.assertNotIn("readonly", candidate_tag)
        self.assertIn("function updateAcceptButton()", source)
        self.assertIn('? "已写入 LaTeX"', source)
        self.assertIn('$("candidate").addEventListener("input"', source)
        self.assertIn("可直接修改正文", source)
        self.assertIn("base_text: visibleBaseText", source)

    def test_manuscript_entrypoint_requires_every_configured_section(self):
        complete = (studio.PAPER / "main.tex").read_text(encoding="utf-8")
        self.assertEqual(manuscript_entrypoint_errors(complete), [])
        missing_abstract = complete.replace(r"\input{sections/abstract}", "")
        errors = manuscript_entrypoint_errors(missing_abstract)
        self.assertTrue(any("section abstract" in error for error in errors))
        self.assertTrue(any("abstract environment" in error for error in errors))

    def test_balanced_title_parse_display_and_replacement(self):
        source = r"""\documentclass{article}
\title{Old \\ Title with \textbf{Nested Words}}
\author{Someone}
"""
        self.assertEqual(
            manuscript_title_tex(source), r"Old \\ Title with \textbf{Nested Words}"
        )
        self.assertEqual(manuscript_title_display(source), "Old Title with Nested Words")
        revised = replace_manuscript_title_source(source, "New & Safer_Title")
        self.assertIn(r"\title{New \& Safer\_Title}", revised)
        self.assertIn(r"\author{Someone}", revised)

    def test_title_save_compiles_transactionally_and_rolls_back_on_failure(self):
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            main = paper / "main.tex"
            original = "\\title{Original Title}\n\\begin{document}\n"
            main.write_text(original, encoding="utf-8")
            with patch.object(studio, "PAPER", paper), patch.object(
                studio, "compile_paper", return_value=studio.CompileResult(True, "ok")
            ):
                result = save_manuscript_title("Confirmed Title")
            self.assertTrue(result.ok)
            self.assertIn(r"\title{Confirmed Title}", main.read_text(encoding="utf-8"))

            main.write_text(original, encoding="utf-8")
            with patch.object(studio, "PAPER", paper), patch.object(
                studio,
                "compile_paper",
                side_effect=[
                    studio.CompileResult(False, "bad title"),
                    studio.CompileResult(True, "old title restored"),
                ],
            ):
                with self.assertRaisesRegex(StudioError, "title edit rolled back"):
                    save_manuscript_title("Broken Title")
            self.assertEqual(main.read_text(encoding="utf-8"), original)

    def test_title_gpt_returns_candidate_without_mutating_main_tex(self):
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            main = paper / "main.tex"
            original = "\\title{Original Title}\n"
            main.write_text(original, encoding="utf-8")
            (paper / "working_abstract.txt").write_text("Supported claims", encoding="utf-8")
            response = {"id": "resp_title", "output_text": "Candidate Title"}
            with patch.object(studio, "PAPER", paper), patch.object(
                studio, "post_openai", return_value=response
            ) as mocked:
                response_id, candidate = studio.call_openai_for_title(
                    model="gpt-5.6",
                    prompt="Make it shorter",
                    current_title="Original Title",
                    previous_response_id=None,
                )
            self.assertEqual((response_id, candidate), ("resp_title", "Candidate Title"))
            self.assertEqual(main.read_text(encoding="utf-8"), original)
            self.assertIn("editable candidate", mocked.call_args.args[0]["input"])

    def test_title_followup_does_not_resend_stable_paper_context(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp_title_2", "output_text": "Shorter Title"}

        with (
            patch.object(studio, "active_llm_provider", return_value="openai"),
            patch.object(studio, "post_openai", side_effect=fake_post),
        ):
            studio.call_openai_for_title(
                model="gpt-5-nano",
                prompt="Shorter",
                current_title="Candidate Title",
                previous_response_id="resp_title_1",
            )
        self.assertEqual(captured["previous_response_id"], "resp_title_1")
        self.assertNotIn("<approved_outline>", captured["input"])
        self.assertNotIn("<working_abstract>", captured["input"])

    def test_public_state_exposes_title_without_openai_chain(self):
        state = _default_state()
        state["title_editor"].update(
            {
                "prompt": "shorter",
                "candidate": "Candidate Title",
                "previous_response_id": "resp_123",
            }
        )
        visible = public_state(state)["title_editor"]
        self.assertTrue(visible["conversation_active"])
        self.assertNotIn("previous_response_id", visible)
        self.assertEqual(visible["candidate"], "Candidate Title")
        self.assertEqual(visible["current_title"], manuscript_title_display())

    def test_project_specific_web_data_is_loaded_from_paper_config(self):
        config = json.loads(
            (studio.PAPER / "paper_studio.json").read_text(encoding="utf-8")
        )
        self.assertEqual(studio.PROJECT_CONFIG, config)
        self.assertEqual(studio.PROJECT_METADATA["name"], "Style Jailbreak")
        self.assertEqual(
            studio.METRICS_FILE,
            studio.ROOT / config["paths"]["metrics"],
        )
        self.assertEqual(studio.FIGURE_ORDER, config["figure_order"])
        self.assertEqual(studio.TABLE_ORDER, config["table_order"])
        public = public_state(_default_state())
        self.assertEqual(
            public["project"]["config_file"],
            studio.PROJECT_CONFIG_FILE.relative_to(studio.ROOT).as_posix(),
        )
        studio.validate_project_workspace()

    def test_reference_excerpt_removes_pdf_line_wraps_but_keeps_paragraphs(self):
        self.assertEqual(
            normalize_reference_excerpt(
                [
                    "First visual line of the abstract",
                    "continues on the next PDF line.",
                    "",
                    "A real second paragraph remains separate.",
                ]
            ),
            "First visual line of the abstract continues on the next PDF line.\n\n"
            "A real second paragraph remains separate.",
        )

    def test_project_workspace_accepts_abstracted_reference_constraints_without_source_text(self):
        contexts = {
            section: {
                "mode": "abstracted",
                "source_heading": "Abstracted structure",
                "logic_summary_zh": "Only approved writing constraints are available.",
                "writing_constraints": [
                    {"id": paragraphs[0]["id"], "purpose": paragraphs[0]["purpose"]}
                ],
                "excerpts": [],
            }
            for section, paragraphs in studio.paragraph_plan()["sections"].items()
        }
        with patch.object(studio, "reference_contexts", return_value=contexts):
            studio.validate_project_workspace()

    def test_project_workspace_rejects_source_text_in_abstracted_reference_mode(self):
        contexts = {
            section: {
                "mode": "abstracted",
                "source_heading": "Abstracted structure",
                "logic_summary_zh": "Only approved writing constraints are available.",
                "writing_constraints": [
                    {"id": paragraphs[0]["id"], "purpose": paragraphs[0]["purpose"]}
                ],
                "excerpts": [{"text": "Source prose must not be present."}],
            }
            for section, paragraphs in studio.paragraph_plan()["sections"].items()
        }
        with patch.object(studio, "reference_contexts", return_value=contexts):
            with self.assertRaisesRegex(StudioError, "禁止携带原文片段"):
                studio.validate_project_workspace()

    def test_project_workspace_rejects_an_artifact_without_any_paragraph_binding(self):
        plan = studio.paragraph_plan()
        for paragraphs in plan["sections"].values():
            for paragraph in paragraphs:
                paragraph["artifacts"] = [
                    item for item in paragraph.get("artifacts", []) if item != "F1"
                ]
        section_specs = json.loads(json.dumps(studio.SECTION_SPECS))
        for section in section_specs:
            section["paragraphs"] = plan["sections"][section["id"]]
        with patch.object(studio, "SECTION_SPECS", section_specs):
            with self.assertRaisesRegex(StudioError, "当前未绑定：F1"):
                studio.validate_project_workspace()

    def test_fixed_web_application_contains_no_fixture_identity(self):
        production_files = [
            studio.STATIC / "index.html",
            studio.STATIC / "app.js",
            studio.STATIC / "style.css",
            Path(studio.__file__),
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in production_files)
        for fixture_term in (
            "Style Jailbreak",
            "AdvBench",
            "TrustLLM",
            "style_jailbreak",
            "representation_analysis.local_probe",
        ):
            self.assertNotIn(fixture_term, source)

    def test_project_config_rejects_paths_outside_workspace(self):
        config = {
            "schema_version": "1.0",
            "project": {"id": "sample", "name": "Sample"},
            "paths": {"metrics": "../outside.json"},
            "sections": [
                {
                    "id": "introduction",
                    "title": "Introduction",
                    "latex_title": "Introduction",
                    "file": "introduction.tex",
                    "result_keys": [],
                }
            ],
            "figure_order": [],
            "figures": {},
            "table_order": [],
            "tables": {},
        }
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "paper_studio.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "inside the workspace"):
                studio.load_project_config(path, root=root)

    @unittest.skip("reference paths are no longer part of Paper Studio")
    def test_project_config_requires_main_and_reference_paths(self):
        config = json.loads(
            (studio.PAPER / "paper_studio.json").read_text(encoding="utf-8")
        )
        config["paths"].pop("main")
        config["paths"].pop("reference")
        config["paths"]["metrics"] = "metrics.json"
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "metrics.json").write_text('{"ready": true}', encoding="utf-8")
            path = root / "paper_studio.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "paths.main is required"):
                studio.load_project_config(path, root=root)

    def test_project_config_requires_inherited_venue_and_reference_decisions(self):
        config = json.loads(
            (studio.PAPER / "paper_studio.json").read_text(encoding="utf-8")
        )
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "paper_studio.json"
            missing_target = json.loads(json.dumps(config))
            missing_target["project"].pop("target")
            path.write_text(json.dumps(missing_target), encoding="utf-8")
            with self.assertRaisesRegex(
                studio.ProjectConfigError, "approved 03 experiment plan"
            ):
                studio.load_project_config(path, root=studio.ROOT)

            missing_reference = json.loads(json.dumps(config))
            missing_reference["project"].pop("reference_paper")
            path.write_text(json.dumps(missing_reference), encoding="utf-8")
            with self.assertRaisesRegex(
                studio.ProjectConfigError, "structural reference selected"
            ):
                studio.load_project_config(path, root=studio.ROOT)

    def test_project_config_rejects_malformed_data_grid(self):
        config = json.loads(
            (studio.PAPER / "paper_studio.json").read_text(encoding="utf-8")
        )
        config["tables"]["T1"]["data_grid"]["metrics"] = "mean_asr"
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "paper_studio.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "metrics must be a non-empty list"):
                studio.load_project_config(path, root=root)

    def test_project_id_change_starts_fresh_runtime_state(self):
        state = _default_state()
        state["project_id"] = "old-project"
        state["sections"]["introduction"]["accepted_text"] = "old manuscript"
        with (
            TemporaryDirectory() as temporary,
            patch.object(studio, "STATE_FILE", Path(temporary) / "state.json"),
        ):
            studio.STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
            loaded = studio.load_state()
        self.assertEqual(loaded["project_id"], studio.PROJECT_ID)
        self.assertNotEqual(
            loaded["sections"]["introduction"]["accepted_text"], "old manuscript"
        )

    def test_data_panels_auto_generate_sequentially_but_composition_stays_manual(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('"agent_generating"', source)
        self.assertIn('"/api/figure/panel/generate"', source)
        self.assertIn("autoDataPanelAttempted.delete(attemptKey)", source)
        self.assertIn('"/api/figure/compose"', source)
        self.assertIn("renderDataPanels", source)
        self.assertNotIn("绘图代码", source)
        self.assertNotIn("panel.code", source)
        panel_renderer = source.split("function renderDataPanels", 1)[1].split(
            "function renderLayoutPrompt", 1
        )[0]
        self.assertNotIn('root.innerHTML = ""', panel_renderer)
        self.assertIn("pdf.dataset.source !== target", source)
        self.assertIn("frame.dataset.source !== target", source)
        self.assertIn("autoDataPanelAttempted", source)
        self.assertIn("scheduleAutomaticDataPanel(figure)", source)
        self.assertIn('figure.kind !== "data"', source)
        self.assertIn('panel.status === "pending" && !panel.preview_url', source)
        self.assertIn("正在自动生成 ${current.id} 最终单图 candidate", source)
        self.assertIn("完成后继续下一张", source)
        self.assertIn('panel.status !== "agent_generating"', source)
        self.assertIn("panel.progress_message", source)
        self.assertIn('panel.preview_type === "pdf"', source)
        self.assertIn("data-panel-pdf", source)
        self.assertNotIn("data-panel-download", source)
        self.assertNotIn("下载该子图 PDF", source)
        self.assertIn("#toolbar=0&navpanes=0&view=FitH", source)
        self.assertNotIn("replaceOnInput", source)
        self.assertNotIn("captureLayoutPromptRightClick", source)

        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertLess(
            html.index('id="data-panels"'),
            html.index('id="data-layout-prompt"'),
        )
        self.assertLess(
            html.index('id="data-panels"'),
            html.index('id="data-compose"'),
        )
        self.assertIn('id="data-composition-editor"', html)
        self.assertIn("全部满意后，再手动点击“合成图”", html)
        self.assertIn('<button id="data-compose" class="primary">合成图</button>', html)
        self.assertIn('id="data-compose-actions"', html)
        self.assertIn('id="data-layout-prompt-label"', html)
        self.assertIn('id="single-data-controls"', html)
        self.assertIn('id="single-data-generate"', html)
        self.assertIn('$("data-compose-actions").hidden = singlePanel', source)
        self.assertIn('$("data-panels").replaceChildren()', source)
        self.assertIn('renderSingleDataFigure(figure)', source)
        self.assertIn('? `${figure.id} · ${figure.title}`', source)
        self.assertIn('id="data-layout-prompt" rows="4" placeholder=""', html)
        self.assertNotIn('oncontextmenu="activateLayoutPrompt()', html)
        self.assertIn('src="static/app.js?v=20260823.14-table-layout"', html)
        self.assertIn('STUDIO_BASE_PATH', source)
        self.assertIn('return STUDIO_BASE_PATH + value', source)
        self.assertIn('id="writing-workspace" class="editor-grid" hidden', html)
        self.assertIn('id="figures-view" disabled', html)
        self.assertIn('id="compile" class="secondary" disabled', html)
        self.assertIn('id="load-error" class="empty-project" hidden', html)
        self.assertIn('id="load-error-message"', html)
        self.assertNotIn('id="project-eyebrow"', html)
        self.assertIn('id="studio-title"', html)
        self.assertIn('const project = state.project || {}', source)
        self.assertIn('project.name ? `${project.name} · Paper Studio`', source)
        self.assertNotIn('(figure.placement_options || []).filter(', source)
        self.assertIn('item.disabled = !option.accepted', source)
        self.assertIn('? "重新解析 Prompt 并生成合成图"', source)
        self.assertIn('id="figure-layout-mode"', html)
        self.assertIn('<option value="single-column">单栏</option>', html)
        self.assertIn('<option value="two-column">双栏</option>', html)
        self.assertIn(
            '<option value="wrapfigure" disabled>Wrapfigure（AAAI 禁用）</option>',
            html,
        )
        self.assertIn('layout_mode: $("figure-layout-mode").value', source)
        self.assertIn("const insertionReady = figure.insertion_ready", source)
        self.assertIn("figure.insertion_gate_reason", source)
        self.assertIn("const fallback = collection[0] || null", source)
        self.assertLess(
            html.index('class="figure-placement-row"'),
            html.index('id="data-approve-after-placement"'),
        )
        self.assertLess(
            html.index('id="figure-layout-mode"'),
            html.index('id="data-approve-after-placement"'),
        )
        self.assertLess(
            html.index('id="data-layout-prompt"'),
            html.index('id="figure-preview-pdf"'),
        )
        self.assertLess(
            html.index('id="figure-preview-pdf"'),
            html.index('id="data-approve-after-placement"'),
        )
        self.assertIn('? "补生成 Caption → PDF"', source)
        self.assertIn(': "重新插入"', source)
        self.assertIn('pdf.onload = () =>', source)
        self.assertIn('id="figure-caption-box"', html)
        self.assertIn('id="figure-caption"', html)
        self.assertIn('id="figure-caption-prompt"', html)
        self.assertIn('id="figure-caption-generate"', html)
        self.assertIn('id="figure-caption-save"', html)
        self.assertLess(
            html.index('id="figure-preview-pdf"'),
            html.index('id="figure-caption-box"'),
        )
        self.assertLess(
            html.index('id="figure-caption-box"'),
            html.index('class="figure-placement-row"'),
        )
        self.assertIn('"/api/figure/caption"', source)
        self.assertIn('"/api/figure/caption/generate"', source)
        self.assertIn('GPT candidate 尚未保存', source)
        self.assertIn('Caption 已修改，尚未更新到正文与 PDF', source)
        self.assertIn('function approveFigureOrSaveCaption()', source)
        self.assertIn('$("data-approve").onclick = approveFigureOrSaveCaption', source)
        self.assertIn(
            '(figure.status === "approved" && !captionDirty && !captionNeedsBackfill)',
            source,
        )
        self.assertIn('"补生成 Caption → PDF"', source)
        self.assertIn('const captionDrafts = new Map()', source)
        self.assertIn('function rememberCaptionDraft(figureId, caption)', source)
        self.assertIn('function forgetCaptionDraft(figureId)', source)
        self.assertIn('const automaticCaptionChanged = Boolean(', source)
        self.assertIn('String(captionDraftRecord.generatedAt || "") !== generatedAt', source)
        self.assertIn('forgetCaptionDraft(figure.id)', source)
        self.assertIn('captionInput.dataset.captionGeneratedAt = generatedAt', source)
        self.assertIn('const figureEditorDrafts = new Map()', source)
        self.assertIn('function renderFigureEditorInput(', source)
        self.assertIn('const proseDrafts = new Map()', source)
        self.assertIn('function rememberProseDraft(editorKey, value, baseline)', source)
        self.assertIn('forgetProseDraft(`${requestedSection}:${acceptedParagraphId}`)', source)
        self.assertIn('const titleDrafts = new Map()', source)
        self.assertIn('function renderTitleDraftInput(', source)
        self.assertIn('"caption_prompt", ""', source)
        self.assertIn('"table_generation_prompt"', source)
        self.assertIn('"table_agent_prompt"', source)
        self.assertIn('"table_latex"', source)
        self.assertIn('const commentDrafts = new Map()', source)
        self.assertIn('rememberCommentDraft(`${activeSection}:${paragraph.id}`', source)
        self.assertIn('const modelOptions = state.llm_model_options || []', source)
        self.assertIn('let acceptRequestBusy = false', source)
        self.assertIn('let proseRequestBusy = false', source)
        self.assertIn('let paragraphRequestBusy = false', source)
        self.assertIn('let compileRequestBusy = false', source)
        self.assertIn('let modelApplyBusy = false', source)
        self.assertIn('let figureRequestBusy = false', source)
        self.assertIn('if (figureRequestBusy) return null', source)
        self.assertIn('if (acceptRequestBusy) return', source)
        self.assertIn('let generatedResetBusy = false', source)
        self.assertIn('if (generatedResetBusy) return', source)
        self.assertIn('const requestedFigureId = activeFigure', source)
        self.assertIn('figure.id !== requestedFigureId', source)
        self.assertIn('let pdfLocateRequestId = 0', source)
        self.assertIn('const submittedPrompt = $("draw-prompt").value.trim()', source)
        self.assertIn('const visibleTableLatex = $("table-latex").value.trim()', source)
        self.assertIn('tableLatexDirty ? "更新表格 → PDF" : "已插入正文"', source)
        self.assertIn('$("candidate").disabled = busy', source)
        self.assertIn('$("paper-title").disabled = busy', source)
        self.assertIn('control.disabled = running || !figure.ready', source)
        self.assertIn('const generationReady = figure.generation_ready !== false', source)
        self.assertIn('|| figure.generation_ready === false', source)
        self.assertIn('&& figure.generation_ready !== false', source)
        self.assertIn('function verifyFigurePdfCandidate(', source)
        self.assertIn('function markFigurePdfLoaded(', source)
        self.assertIn('=== "%PDF-"', source)
        self.assertIn('|| loadedCandidate !== expectedCandidate', source)
        self.assertIn('function clearBrowserDraftsForProject(projectId)', source)
        self.assertIn('clearBrowserDraftsForProject(projectId)', source)
        self.assertIn('input.dataset.dirty = "false"', source)
        self.assertIn('"layout_prompt", figure.layout_prompt || ""', source)
        self.assertIn('`panel:${panel.id}`', source)
        self.assertIn(
            'captionInput.dataset.dirty = String(captionInput.value !== savedCaption)',
            source,
        )
        self.assertLess(
            html.index('id="mechanism-controls"'),
            html.index('id="figure-preview-pdf"'),
        )
        self.assertLess(
            html.index('class="figure-placement-row"'),
            html.index('id="mechanism-approve-after-placement"'),
        )
        self.assertIn('src="static/app.js?v=20260823.14-table-layout"', html)
        self.assertNotIn("系统确定的段落任务", html)
        self.assertNotIn('id="purpose"', html)
        self.assertNotIn('$("purpose")', source)
        self.assertIn('id="pdf-page-indicator"', html)
        self.assertIn("function updatePdfPageIndicator()", source)
        self.assertIn("pages.onscroll = updatePdfPageIndicator", source)
        self.assertIn('href="static/style.css?v=20260823.5-mobile-overflow"', html)
        self.assertLess(
            html.index('id="compile"'),
            html.index('id="reset-generated"'),
        )
        self.assertIn('id="reference-context-card" class="reference-context-card" open hidden', html)
        self.assertIn('id="reference-excerpts-toggle" class="reference-excerpts-toggle"', html)
        self.assertNotIn('<details class="structure-card">', html)
        self.assertIn('id="reset-generated-dialog"', html)
        self.assertIn('id="reset-project-id" readonly', html)
        self.assertIn('id="reset-project-copy"', html)
        self.assertIn('id="reset-project-confirm"', html)
        self.assertIn('id="reset-generated-confirm"', html)
        self.assertIn('navigator.clipboard.writeText(input.value)', source)
        self.assertIn('document.execCommand("copy")', source)
        self.assertNotIn("const typed = prompt(", source)
        self.assertIn(
            'const latestState = normalizeStateUrls(await request("/api/state"))',
            source,
        )
        self.assertIn("candidate_text: visibleCandidateText", source)
        self.assertNotIn("This candidate is stale", source)
        self.assertIn("&& !nextParagraph.accepted_text", source)
        self.assertNotIn("等待确认", source)
        self.assertIn('id="pdf-viewer"', html)
        self.assertIn('id="pdf-pages"', html)
        self.assertNotIn('id="pdf"', html)
        self.assertIn('page.ondblclick = (event) => locatePdfEditTarget(event, page)', source)
        self.assertIn('"/api/pdf/locate"', source)
        self.assertIn('studioPath(`/paper-page/${pageNumber}.svg', source)
        self.assertIn('function capturePdfPosition(pages)', source)
        self.assertIn('function restorePdfPosition(pages, position)', source)
        self.assertIn('const previousPosition = capturePdfPosition(pages)', source)
        self.assertIn('restorePdfPosition(pages, previousPosition)', source)
        self.assertIn('id="pdf-navigation-toggle"', html)
        self.assertIn('id="pdf-download"', html)
        self.assertIn('id="project-export"', html)
        self.assertNotIn('id="paper-contract"', html)
        self.assertNotIn("INHERITED FROM APPROVED PLAN", html)
        self.assertNotIn("写作阶段无需重新选择", source)
        self.assertNotIn('id="api-usage"', html)
        self.assertNotIn('id="api-status"', html)
        self.assertNotIn('id="conversation-status"', html)
        self.assertNotIn("New conversation", html)
        self.assertIn('projectExport.hidden = !project.export_url', source)
        self.assertIn('download.hidden = false', source)
        self.assertIn('download.href = studioPath(state.pdf.url || "/paper.pdf")', source)
        self.assertIn('paper-studio.pdf-navigation-visible', source)
        self.assertIn('pdfNavigationVisible ? "隐藏导航栏" : "显示导航栏"', source)
        self.assertIn('function uniqueArtifacts(artifacts = [])', source)
        self.assertIn('uniqueArtifacts(paragraph.artifacts || [])', source)
        self.assertNotIn('id="artifact-marker"', html)
        self.assertNotIn('artifactMarker', source)
        self.assertIn('badge.className = "nav-artifact"', source)

    def test_synctex_source_lines_map_to_paragraphs_and_artifacts(self):
        state = _default_state()
        state["sections"]["introduction"]["paragraphs"][0]["accepted_text"] = (
            "First accepted paragraph."
        )
        source = """\\section{Introduction}

First accepted paragraph.

\\begin{figure}[t]
  \\includegraphics{fig/overview.pdf}
  \\caption{Overview.}
  \\label{fig:overview}
\\end{figure}
"""
        with TemporaryDirectory() as temporary:
            paper = Path(temporary)
            (paper / "sections").mkdir()
            path = paper / "sections" / "introduction.tex"
            path.write_text(source, encoding="utf-8")
            with patch.object(studio, "PAPER", paper):
                paragraph = studio.source_edit_target(path, 3, state)
                figure = studio.source_edit_target(path, 7, state)
        self.assertEqual(
            paragraph,
            {"view": "writing", "section": "introduction", "paragraph_id": "I1"},
        )
        self.assertEqual(
            figure,
            {"view": "figures", "section": "introduction", "artifact_id": "F1"},
        )

    def test_synctex_edit_parser_uses_first_source_record(self):
        path, line = studio.parse_synctex_edit(
            "SyncTeX result begin\nInput:/tmp/paper/sections/method.tex\nLine:21\nColumn:-1\n"
        )
        self.assertEqual(path, Path("/tmp/paper/sections/method.tex"))
        self.assertEqual(line, 21)

    def test_synctex_maps_terminal_rewritten_prose_by_planned_heading(self):
        state = _default_state()
        state["sections"]["experiments"]["paragraphs"][0]["accepted_text"] = (
            "\\subsection{Experimental Setup}\n\nOld browser-state prose."
        )
        source = (
            "\\section{Experiments}\n\n"
            "\\subsection{Experimental Setup}\n\n"
            "Completely rewritten terminal prose that is not present in browser state.\n\n"
            "\\subsection{Main Results}\n\nAnother paragraph.\n"
        )
        with TemporaryDirectory() as temporary:
            paper = Path(temporary)
            (paper / "sections").mkdir()
            path = paper / "sections" / studio.SECTION_MAP["experiments"]["file"]
            path.write_text(source, encoding="utf-8")
            with patch.object(studio, "PAPER", paper):
                target = studio.source_edit_target(path, 5, state)
        self.assertEqual(target["view"], "writing")
        self.assertEqual(target["paragraph_id"], "E1")

    def test_pdf_reverse_lookup_rebuilds_a_missing_synctex_index(self):
        state = _default_state()
        paragraph = state["sections"]["introduction"]["paragraphs"][0]
        paragraph["accepted_text"] = "Recovered reverse-search paragraph."
        with TemporaryDirectory() as temporary:
            paper = Path(temporary)
            sections = paper / "sections"
            sections.mkdir()
            source_path = sections / studio.SECTION_MAP["introduction"]["file"]
            source_path.write_text(
                "\\section{Introduction}\n\nRecovered reverse-search paragraph.\n",
                encoding="utf-8",
            )
            (paper / "main.pdf").write_bytes(b"%PDF-fixture")

            def compile_with_synctex():
                (paper / "main.synctex.gz").write_bytes(b"fixture")
                return studio.CompileResult(True, "rebuilt")

            completed = CompletedProcess(
                args=["synctex"],
                returncode=0,
                stdout=f"Input:{source_path}\nLine:3\nColumn:-1\n",
                stderr="",
            )
            with (
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "compile_paper", side_effect=compile_with_synctex) as compile_mock,
                patch.object(studio, "shutil_which", return_value="/usr/bin/synctex"),
                patch.object(
                    studio,
                    "paper_pdf_metadata",
                    return_value={"page_count": 1, "page_width_pt": 600, "page_height_pt": 800},
                ),
                patch.object(studio.subprocess, "run", return_value=completed),
            ):
                target = studio.locate_pdf_source(1, 100, 100, state)

        compile_mock.assert_called_once_with()
        self.assertEqual(target["view"], "writing")
        self.assertEqual(target["paragraph_id"], paragraph["id"])

    def test_terminal_manuscript_recovers_figure_and_table_workbenches(self):
        state = _default_state()
        discussion = state["sections"]["analysis_discussion"]
        discussion["paragraphs"][0]["accepted_text"] = "Accepted discussion paragraph."
        table_latex = studio.generate_table_latex(
            "T2", studio.metrics_bundle(), studio.default_table_prompt("T2")
        )
        with TemporaryDirectory() as temporary:
            paper = Path(temporary)
            sections = paper / "sections"
            figure_dir = paper / "fig"
            figure_source_dir = paper / "figsrc"
            table_preview_dir = paper / ".paper_studio/table_previews"
            sections.mkdir(parents=True)
            figure_dir.mkdir()
            figure_source_dir.mkdir()
            with (
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "FIGURE_DIR", figure_dir),
                patch.object(studio, "FIGURE_SOURCE_DIR", figure_source_dir),
                patch.object(studio, "TABLE_PREVIEW_DIR", table_preview_dir),
            ):
                figure_pdf = studio.figure_paths("F5")["pdf"]
                figure_pdf.write_bytes(b"%PDF-recovered-figure")
                relative_figure = figure_pdf.relative_to(paper).as_posix()
                source_path = sections / studio.SECTION_MAP["analysis_discussion"]["file"]
                source_path.write_text(
                    "\\section{Analysis and Discussion}\n\n"
                    "Accepted discussion paragraph.\n\n"
                    + table_latex
                    + "\n\n\\begin{figure}[t]\n  \\centering\n"
                    + f"  \\includegraphics[width=\\columnwidth]{{{relative_figure}}}\n"
                    + "  \\caption{Recovered data figure.}\n"
                    + "  \\label{fig:defense}\n\\end{figure}\n",
                    encoding="utf-8",
                )

                changed = studio.synchronize_artifact_workbenches_from_manuscript(
                    state, build_table_previews=False
                )
                public_figure = next(
                    item for item in studio.figure_public_state(state) if item["id"] == "F5"
                )
                public_table = next(
                    item for item in studio.table_public_state(state) if item["id"] == "T2"
                )

        self.assertTrue(changed)
        self.assertEqual(state["figures"]["F5"]["status"], "approved")
        self.assertTrue(state["figures"]["F5"]["composed_at"])
        self.assertEqual(state["figures"]["F5"]["panels"]["a"]["status"], "built")
        self.assertEqual(public_figure["preview_url"].split("?", 1)[0], "/figure-file/F5/pdf")
        self.assertEqual(
            public_figure["panels"][0]["preview_url"].split("?", 1)[0],
            "/figure-file/F5/pdf",
        )
        self.assertEqual(state["tables"]["T2"]["status"], "approved")
        self.assertEqual(state["tables"]["T2"]["latex"], table_latex)
        self.assertEqual(public_table["latex"], table_latex)

    def test_custom_figure_caption_is_public_and_used_in_latex(self):
        state = _default_state()
        state["figures"]["F6"]["caption"] = "Researcher-edited caption."
        public = next(item for item in figure_public_state(state) if item["id"] == "F6")
        self.assertEqual(public["caption"], "Researcher-edited caption.")
        self.assertIn(
            r"\caption{Researcher-edited caption.}",
            figure_latex("F6", state["figures"]["F6"]),
        )

    def test_caption_latex_escaping_preserves_inline_scientific_notation(self):
        caption = r"Gap \(9.47\times10^{-7}\) at 90% depth & later tokens."
        escaped = studio.latex_escape_caption(caption)
        self.assertEqual(
            escaped,
            r"Gap \(9.47\times10^{-7}\) at 90\% depth \& later tokens.",
        )
        self.assertNotIn("textasciicircum", escaped)

    def test_completed_section_keeps_last_paragraph_and_architecture_visible(self):
        state = _default_state()
        conclusion = state["sections"]["conclusion"]
        conclusion["paragraphs"][0]["accepted_text"] = "Accepted conclusion."
        conclusion["current_index"] = len(conclusion["paragraphs"])
        with TemporaryDirectory() as temporary:
            state_file = Path(temporary) / "state.json"
            state_file.write_text(json.dumps(state), encoding="utf-8")
            with patch.object(studio, "STATE_FILE", state_file):
                loaded = studio.load_state()
                public = public_state(loaded)
        self.assertEqual(loaded["sections"]["conclusion"]["current_index"], 0)
        paragraph = public["sections"]["conclusion"]["current_paragraph"]
        self.assertEqual(paragraph["id"], "C1")
        self.assertEqual(paragraph["architecture"]["rhetorical_role"], "approved test role")
        self.assertNotIn("reference_text", paragraph)
        self.assertTrue(public["sections"]["conclusion"]["complete"])

    def test_custom_figure_caption_is_sent_to_bound_paragraph_gpt(self):
        context = studio.artifact_writing_context(
            ["F2"], {"F2": {"caption": "Researcher-edited representation caption."}}
        )
        self.assertEqual(
            context[0]["caption"], "Researcher-edited representation caption."
        )

    def test_artifact_references_follow_exact_paragraph_bindings(self):
        context = studio.artifact_writing_context(["F1"])
        self.assertEqual(
            studio.artifact_reference_error(
                r"Figure~\ref{fig:overview} motivates the method.", context
            ),
            "",
        )
        missing = studio.artifact_reference_error("No figure reference.", context)
        self.assertIn(r"缺少 Figure~\ref{fig:overview}", missing)
        repeated = studio.artifact_reference_error(
            r"Figure~\ref{fig:overview}; again Figure~\ref{fig:overview}.", context
        )
        self.assertIn("同段重复", repeated)
        unexpected = studio.artifact_reference_error(
            r"Figure~\ref{fig:method} is not bound here.", context
        )
        self.assertIn(r"本段未绑定 Figure~\ref{fig:method}", unexpected)

    def test_gpt_caption_candidate_is_grounded_and_preserves_synthetic_marker(self):
        state = _default_state()
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"output_text": "Figure 6: Layer-wise probe trends for direct and stylized inputs."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            caption = studio.generate_figure_caption(
                "F6",
                state,
                FIGURES["F6"]["caption"],
                "Shorten it and define the comparison.",
            )

        self.assertTrue(caption.startswith("[SYNTHETIC]"))
        self.assertNotIn("Figure 6:", caption)
        self.assertIn("Shorten it and define the comparison.", captured["input"])
        self.assertIn('"traceable_results"', captured["input"])
        self.assertIn('"synthetic": true', captured["input"])
        self.assertIn("do not invent measurements", captured["instructions"].lower())
        self.assertIn("Do not use em dashes", captured["instructions"])
        self.assertIn("exactly one", captured["instructions"])
        self.assertIn("no more than 40 words", captured["instructions"])
        self.assertIn("no minimum length", captured["instructions"])

    def test_oversized_gpt_caption_is_automatically_compressed_once(self):
        state = _default_state()
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"output_text": " ".join(["detail"] * 180)}
            return {
                "output_text": "Compact caption describing the compared panels and metric."
            }

        with patch.object(studio, "post_openai", side_effect=fake_post):
            caption = studio.generate_figure_caption(
                "F2", state, FIGURES["F2"]["caption"], ""
            )

        self.assertEqual(
            caption, "Compact caption describing the compared panels and metric."
        )
        self.assertEqual(len(payloads), 2)
        self.assertIn("Compress and polish", payloads[1]["instructions"])
        self.assertIn("at most 40 words", payloads[1]["instructions"])

    def test_multi_sentence_gpt_caption_is_repaired_to_one_sentence(self):
        state = _default_state()
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"output_text": "The upper panel shows the null. The lower panel shows transport."}
            return {"output_text": "The upper and lower panels contrast the additive null with nonlinear transport."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            caption = studio.generate_figure_caption(
                "F2", state, FIGURES["F2"]["caption"], "Use one sentence."
            )

        self.assertEqual(
            caption,
            "The upper and lower panels contrast the additive null with nonlinear transport.",
        )
        self.assertEqual(len(payloads), 2)
        self.assertIn("exactly one sentence", payloads[1]["instructions"])

    def test_caption_has_deterministic_bound_after_failed_api_compression(self):
        state = _default_state()
        long_two_sentence = (
            "The upper panel shows the exact additive null for two constant vectors. "
            + "The lower panel shows nonlinear transport across layers with matched positions "
            + "and fixed token paths while highlighting state evolution and token history "
            + "as the only remaining sources of observed order sensitivity."
        )
        with patch.object(
            studio,
            "post_openai",
            side_effect=[
                {"output_text": long_two_sentence},
                {"output_text": long_two_sentence},
            ],
        ):
            caption = studio.generate_figure_caption(
                "F2", state, FIGURES["F2"]["caption"], "Use one sentence."
            )
        self.assertFalse(studio.figure_caption_issues(caption))
        self.assertIn(";", caption)

    def test_unicode_scientific_notation_caption_is_repaired_for_pdflatex(self):
        state = _default_state()
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"output_text": "The gap declines to 9.47×10⁻⁷ at 90% depth."}
            return {
                "output_text": r"The gap declines to \(9.47 \times 10^{-7}\) at 90\% depth."
            }

        with patch.object(studio, "post_openai", side_effect=fake_post):
            caption = studio.generate_figure_caption(
                "F3", state, FIGURES["F3"]["caption"], ""
            )

        self.assertEqual(
            caption,
            r"The gap declines to \(9.47 \times 10^{-7}\) at 90\% depth.",
        )
        self.assertEqual(studio.figure_caption_issues(caption), [])
        self.assertIn("pdflatex-safe", payloads[1]["instructions"])

    def test_caption_normalization_removes_forbidden_dash_punctuation(self):
        normalized = studio.normalize_figure_caption_text(
            "Figure 4: Predicted–observed gaps — lower is better."
        )
        self.assertEqual(
            normalized,
            "Predicted to observed gaps; lower is better.",
        )
        self.assertNotIn("dash punctuation", " ".join(studio.figure_caption_issues(normalized)))

    def test_accepting_a_figure_bound_paragraph_generates_its_caption(self):
        state = _default_state()
        paragraph = {
            "id": "I2",
            "artifacts": ["F1"],
        }
        with patch.object(
            studio,
            "generate_figure_caption",
            return_value="Automatically grounded caption.",
        ) as generate:
            generated = studio.auto_generate_bound_figure_captions(
                state,
                "introduction",
                paragraph,
                r"Figure~\ref{fig:overview} motivates the method.",
            )

        self.assertEqual(generated, ["F1"])
        self.assertEqual(state["figures"]["F1"]["caption"], "Automatically grounded caption.")
        self.assertEqual(state["figures"]["F1"]["caption_source"], "paragraph_accept")
        self.assertEqual(
            state["figures"]["F1"]["caption_generated_from_paragraph"], "I2"
        )
        self.assertEqual(generate.call_args.kwargs["trigger_paragraph"]["section"], "introduction")

    def test_bound_paragraph_is_rejected_when_automatic_caption_fails(self):
        state = _default_state()
        paragraph = {"id": "I-P3", "artifacts": ["F1"]}
        with (
            patch.object(
                studio,
                "generate_figure_caption",
                side_effect=studio.StudioError("still exceeds one sentence"),
            ),
            self.assertRaisesRegex(
                studio.StudioError,
                r"I-P3.*F1 Caption 自动生成失败.*本段未接受",
            ),
        ):
            studio.auto_generate_bound_figure_captions(
                state,
                "introduction",
                paragraph,
                r"Figure~\ref{fig:overview} establishes the null.",
            )

        self.assertEqual(state["figures"]["F1"]["caption_source"], "configured")
        self.assertIn("one sentence", state["figures"]["F1"]["caption_last_error"])

    def test_figure_approval_backfills_caption_from_accepted_binding(self):
        state = _default_state()
        paragraph = {
            "id": "I-P3",
            "artifacts": ["F1"],
            "accepted_text": r"Figure~\ref{fig:overview} establishes the null.",
        }
        with (
            patch.object(studio, "first_artifact_binding", return_value=("introduction", "I-P3")),
            patch.object(studio, "paragraph_by_id", return_value=(paragraph, 2)),
            patch.object(
                studio,
                "generate_figure_caption",
                return_value="The figure contrasts the additive null with transported state effects.",
            ),
        ):
            studio.ensure_figure_caption_before_approval(state, "F1")

        self.assertEqual(state["figures"]["F1"]["caption_source"], "paragraph_accept")
        self.assertEqual(
            state["figures"]["F1"]["caption"],
            "The figure contrasts the additive null with transported state effects.",
        )

    def test_figure_approval_preserves_researcher_caption(self):
        state = _default_state()
        state["figures"]["F1"].update(
            caption="Researcher caption.", caption_source="researcher"
        )
        with patch.object(studio, "auto_generate_bound_figure_captions") as generate:
            studio.ensure_figure_caption_before_approval(state, "F1")
        generate.assert_not_called()
        self.assertEqual(state["figures"]["F1"]["caption"], "Researcher caption.")

    def test_automatic_caption_never_overwrites_researcher_caption(self):
        state = _default_state()
        state["figures"]["F1"].update(
            caption="Researcher caption.", caption_source="researcher"
        )
        paragraph = {
            "id": "I2",
            "artifacts": [{"id": "F1", "kind": "figure"}],
        }
        with patch.object(studio, "generate_figure_caption") as generate:
            generated = studio.auto_generate_bound_figure_captions(
                state, "introduction", paragraph, "Revised accepted prose."
            )

        self.assertEqual(generated, [])
        self.assertEqual(state["figures"]["F1"]["caption"], "Researcher caption.")
        generate.assert_not_called()

    def test_last_data_panel_waits_for_manual_composition(self):
        state = _default_state()
        figure = state["figures"]["F4"]
        figure["revision"] = 3
        figure["layout_prompt"] = ""
        figure["panels"]["a"]["status"] = "built"
        figure["panels"]["b"]["status"] = "agent_generating"
        updates = []
        def capture_update(_figure_id, _token, **kwargs):
            updates.append(kwargs)
            return state

        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "update_data_panel_job"),
            patch.object(studio, "update_figure_job", side_effect=capture_update),
            patch.object(
                studio,
                "generate_data_figure_with_local_agent",
                return_value="F4(b) built",
            ),
            patch.object(
                studio,
                "create_data_figure_layout_with_local_agent",
                return_value={},
            ) as layout_agent,
            patch.object(
                studio,
                "compose_data_figure",
                return_value="composition built",
            ) as composer,
        ):
            generate_data_figure_agent_worker("F4", "b", "job-token")

        layout_agent.assert_not_called()
        composer.assert_not_called()
        self.assertEqual(updates[-1]["status"], "panels_ready")
        self.assertIsNone(updates[-1]["composed_at"])
        self.assertIn("手动点击“合成图”", updates[-1]["progress_message"])

    def test_single_panel_figure_directly_builds_final_without_panel_label(self):
        state = _default_state()
        figure = state["figures"]["F5"]
        figure["panels"]["a"]["status"] = "agent_generating"
        updates = []

        def capture_update(_figure_id, _token, **kwargs):
            updates.append(kwargs)
            return state

        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "update_data_panel_job"),
            patch.object(studio, "update_figure_job", side_effect=capture_update),
            patch.object(
                studio,
                "generate_data_figure_with_local_agent",
                return_value="F5 built",
            ),
            patch.object(
                studio,
                "compose_data_figure",
                return_value="single figure packaged",
            ) as composer,
            patch.object(
                studio,
                "create_data_figure_layout_with_local_agent",
            ) as layout_agent,
        ):
            generate_data_figure_agent_worker("F5", "a", "job-token")

        layout_agent.assert_not_called()
        composer.assert_called_once()
        layout = composer.call_args.args[2]
        self.assertEqual(layout["panel_order"], ["a"])
        self.assertEqual(layout["labels"], [])
        self.assertEqual(layout["gap_pt"], 0.0)
        self.assertEqual(updates[-1]["status"], "built")
        self.assertIsNotNone(updates[-1]["composed_at"])
        self.assertIn("最终单图", updates[-1]["progress_message"])

    def test_data_figure_layout_prompt_controls_local_composition(self):
        horizontal = data_figure_layout(
            "两张图横向单栏，裁掉上下左右空白，左上角加 (a)/(b)"
        )
        self.assertEqual(horizontal["orientation"], "horizontal")
        self.assertEqual(horizontal["width"], "single-column")
        self.assertTrue(horizontal["labels"])
        vertical = data_figure_layout("上下排列，双栏，不要角标")
        self.assertEqual(vertical["orientation"], "vertical")
        self.assertEqual(vertical["width"], "two-column")
        self.assertFalse(vertical["labels"])

    def test_local_agent_translates_layout_prompt_to_validated_json(self):
        captured = {}
        raw_plan = {
            "orientation": "horizontal",
            "width": "single-column",
            "panel_order": ["b", "a"],
            "gap_pt": 0,
            "crop_margins_pt": 0,
            "labels": [
                {"panel_id": "a", "text": "(a)", "position": "top-left"},
                {"panel_id": "b", "text": "(b)", "position": "top-left"},
            ],
        }

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["prompt"] = kwargs["input"]
            captured["env"] = kwargs["env"]
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(json.dumps(raw_plan), encoding="utf-8")
            return CompletedProcess(command, 0, "", "")

        with (
            patch.object(studio, "shutil_which", return_value="/usr/local/bin/codex"),
            patch.object(studio.subprocess, "run", side_effect=fake_run),
            patch.dict(studio.os.environ, {"OPENAI_API_KEY": "must-not-leak"}),
        ):
            plan = create_data_figure_layout_with_local_agent(
                "F4", "把 b 放左边、a 放右边，横向单栏且零间距"
            )

        self.assertEqual(plan["panel_order"], ["b", "a"])
        self.assertEqual(plan["output_format"], "pptx-and-vector-pdf")
        self.assertEqual(plan["labels"][0]["font_size_pt"], 8)
        self.assertNotIn("OPENAI_API_KEY", captured["env"])
        self.assertIn("严格 schema", captured["prompt"])
        self.assertIn("作为可编辑文本框", captured["prompt"])

    def test_agent_layout_rejects_missing_or_duplicate_panels(self):
        raw = extract_agent_layout_json(
            '{"orientation":"horizontal","width":"single-column",'
            '"panel_order":["a","a"],"gap_pt":0,"crop_margins_pt":0,'
            '"labels":[]}'
        )
        with self.assertRaises(StudioError):
            validate_data_figure_layout(raw, ["a", "b"])

    def test_public_data_figure_exposes_atomic_panels_and_code(self):
        state = _default_state()
        figure = next(
            item for item in figure_public_state(state) if item["id"] == "F4"
        )
        self.assertEqual([item["id"] for item in figure["panels"]], ["a", "b"])
        self.assertIn("layout_prompt", figure)
        self.assertEqual(figure["layout_prompt"], "")
        self.assertFalse(figure["layout_prompt_is_default"])
        self.assertFalse(figure["composition_ready"])
        self.assertTrue(all("code" not in panel for panel in figure["panels"]))

    def test_local_composer_crops_and_joins_panel_pdfs_with_labels(self):
        if not studio.shutil_which("pdfcrop"):
            self.skipTest("pdfcrop is unavailable")
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is unavailable")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            panel_files = {}
            for panel_id, size in (("a", (180, 120)), ("b", (140, 190))):
                path = root / f"{panel_id}.pdf"
                document = fitz.open()
                page = document.new_page(width=size[0], height=size[1])
                page.draw_rect(fitz.Rect(15, 15, size[0] - 15, size[1] - 15))
                page.insert_text((22, 32), panel_id.upper(), fontsize=12)
                document.save(path)
                document.close()
                panel_files[panel_id] = path

            def panel_paths(_figure_id, panel_id):
                return {
                    "source": root / f"{panel_id}.py",
                    "pdf": panel_files[panel_id],
                    "preview": root / f"{panel_id}.png",
                }

            final_paths = {
                "pdf": root / "nested" / "combined.pdf",
                "pptx": root / "nested" / "combined.pptx",
                "preview": root / "nested" / "combined.png",
                "layout_source": root / "layout.json",
                "layout_prompt": root / "layout.txt",
            }
            with (
                patch.object(studio, "data_panel_paths", side_effect=panel_paths),
                patch.object(studio, "figure_paths", return_value=final_paths),
            ):
                layout = validate_data_figure_layout(
                    {
                        "orientation": "horizontal",
                        "width": "single-column",
                        "panel_order": ["a", "b"],
                        "gap_pt": 0,
                        "crop_margins_pt": 0,
                        "labels": [
                            {"panel_id": "a", "text": "(a)", "position": "top-left"},
                            {"panel_id": "b", "text": "(b)", "position": "top-left"},
                        ],
                    },
                    ["a", "b"],
                )
                message = compose_data_figure(
                    "F4",
                    "两张图横向单栏，裁掉上下左右空白，左上角加 (a)/(b)，中间不留空白",
                    layout,
                )

            result = fitz.open(final_paths["pdf"])
            rect = result[0].rect
            result.close()
            self.assertAlmostEqual(rect.width, 3.32 * 72, places=1)
            self.assertGreater(rect.width, rect.height)
            self.assertTrue(final_paths["preview"].exists())
            self.assertTrue(final_paths["pptx"].exists())
            layout = final_paths["layout_source"].read_text(encoding="utf-8")
            self.assertIn('"gap_pt": 0', layout)
            self.assertIn('"(a)"', layout)
            self.assertIn("无需 PowerPoint 权限确认", message)

    def test_data_figure_code_comes_from_codex_without_api_key(self):
        captured = {}
        program = """import argparse
import matplotlib
matplotlib.use("Agg")
parser = argparse.ArgumentParser()
parser.add_argument("--metrics")
parser.add_argument("--pdf")
parser.add_argument("--png")
args = parser.parse_args()
"""

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            captured["prompt"] = kwargs["input"]
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(program, encoding="utf-8")
            return CompletedProcess(command, 0, "", "")

        with (
            patch.object(studio, "shutil_which", return_value="/usr/local/bin/codex"),
            patch.object(studio.subprocess, "run", side_effect=fake_run),
            patch.dict(studio.os.environ, {"OPENAI_API_KEY": "must-not-leak"}),
        ):
            source = studio.create_data_figure_code_with_local_agent("F4")

        self.assertEqual(source, program)
        self.assertEqual(captured["command"][:2], ["/usr/local/bin/codex", "exec"])
        self.assertNotIn("OPENAI_API_KEY", captured["env"])
        self.assertIn("Ablation and style analysis", captured["prompt"])
        self.assertIn("<traceable_results>", captured["prompt"])

    def test_local_agent_table_prompt_is_not_html_hidden(self):
        source = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="table-agent-prompt"', source)
        self.assertIn('for="table-agent-prompt">修改命令</label>', source)
        self.assertIn("调用本地 Agent</button>", source)
        self.assertNotIn("（非 API）", source)
        # CSP-safe markup starts dynamic controls hidden; renderFigures removes
        # the native hidden attribute for local table editing.
        self.assertRegex(
            source,
            r'id="table-agent-controls"[^>]*\shidden(?:\s|>)',
        )
        app = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn(
            '$("table-agent-controls").hidden = !isTable || Boolean(state.online_project);',
            app,
        )

    def test_citation_keys(self):
        source = r"Prior work \\citep{alpha,beta} and \\citet[Sec. 2]{gamma}."
        self.assertEqual(citation_keys(source), {"alpha", "beta", "gamma"})

    def test_citation_key_counts_detects_repeated_section_uses(self):
        source = (
            r"First \\cite{alpha,beta}. Second \\citep{alpha}. "
            r"Third \\cite{alpha}."
        )
        self.assertEqual(
            studio.citation_key_counts(source), {"alpha": 3, "beta": 1}
        )

    def test_extract_response_text(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Draft paragraph."}],
                }
            ]
        }
        self.assertEqual(extract_output_text(response), "Draft paragraph.")

    def test_missing_or_unknown_citation_triggers_resolution(self):
        self.assertTrue(needs_citation_resolution("Claim. [CITATION NEEDED]"))
        self.assertTrue(needs_citation_resolution(r"Claim \\cite{}."))
        self.assertTrue(needs_citation_resolution(r"Claim \\cite{definitelyUnknownKey}."))
        self.assertTrue(
            needs_citation_resolution(
                r"Claim \\cite{[REFUSAL_DIRECTION_CITATION]}."
            )
        )

    def test_uncited_named_attribution_triggers_targeted_audit(self):
        self.assertTrue(has_uncited_named_attribution("Zhu et al. (2020) propose it."))
        self.assertFalse(
            has_uncited_named_attribution(
                r"Zhu et al. (2020) propose it \cite{zhu-etal-2020-multitask}."
            )
        )
        self.assertFalse(has_uncited_named_attribution("Our method uses four operators."))

    def test_citation_audit_covers_external_claims_even_without_placeholders(self):
        self.assertTrue(
            studio.paragraph_requires_citation_audit(
                "introduction", "Motivate the problem.", "Typos impair deployed systems."
            )
        )
        self.assertTrue(
            studio.paragraph_requires_citation_audit(
                "experiments", "Describe data.", "We evaluate on the CLINC150 benchmark."
            )
        )
        self.assertFalse(
            studio.paragraph_requires_citation_audit(
                "experiments", "Report our result.", "MTA improves the measured pilot mean."
            )
        )

    def test_display_alias_intro_always_receives_citation_audit(self):
        with patch.object(
            studio,
            "SECTION_MAP",
            {"i": {"title": "Introduction", "render": "section"}},
        ):
            self.assertTrue(
                studio.paragraph_requires_citation_audit(
                    "i", "Introduce the setting.", "Activation steering is efficient."
                )
            )
        self.assertFalse(
            studio.paragraph_requires_citation_audit(
                "abstract", "Summarize.", "We evaluate on CLINC150."
            )
        )

    def test_real_fixture_rejects_pending_result_language(self):
        with patch.object(
            studio,
            "metrics_bundle",
            return_value={"fixture": {"synthetic": False, "pilot_scale": True}},
        ):
            self.assertIn(
                "pending execution",
                studio.real_result_status_issues("All values are pending execution."),
            )
            self.assertEqual(
                studio.real_result_status_issues(
                    "The reduced-sample pilot measured a 0.01 effect."
                ),
                [],
            )

    def test_synthetic_fixture_does_not_apply_real_result_status_gate(self):
        with patch.object(
            studio,
            "metrics_bundle",
            return_value={"fixture": {"synthetic": True}},
        ):
            self.assertEqual(
                studio.real_result_status_issues("All values are pending execution."),
                [],
            )

    def test_local_accept_gate_rejects_empty_and_non_survey_citations(self):
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", False),
            patch.object(studio, "survey_bibliography_keys", return_value={"surveyKey"}),
        ):
            with self.assertRaisesRegex(StudioError, r"未解决的 \\cite\{\}"):
                studio.validate_citations_for_accept(r"Prior work \cite{}.")
            with self.assertRaisesRegex(StudioError, "notInSurvey"):
                studio.validate_citations_for_accept(r"Prior work \cite{notInSurvey}.")
            studio.validate_citations_for_accept(r"Prior work \cite{surveyKey}.")

    def test_online_accept_gate_allows_only_empty_citation_markers(self):
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "bibliography_keys", return_value=set()),
        ):
            studio.validate_citations_for_accept(r"Prior work \cite{}.")
            with self.assertRaisesRegex(StudioError, "known2020"):
                studio.validate_citations_for_accept(r"Prior work \cite{known2020}.")

    def test_empty_citation_repair_uses_only_a_verified_local_key(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {
                "id": "resp-citation-repair",
                "output_text": r"ORBIT studies sequence asymmetry \cite{orbit2026}.",
            }

        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", False),
            patch.object(studio, "survey_bibliography_keys", return_value={"orbit2026"}),
            patch.object(
                studio,
                "writing_bibliography_catalog",
                return_value="key=orbit2026 | title=ORBIT",
            ),
            patch.object(studio, "post_openai", side_effect=fake_post),
        ):
            response_id, repaired = studio.repair_empty_citation_placeholders(
                model="deepseek-v4-flash",
                previous_response_id="resp-audit",
                section="related_work",
                purpose="Contrast with ORBIT.",
                paragraph=r"ORBIT studies sequence asymmetry \cite{}.",
            )

        self.assertEqual(response_id, "resp-citation-repair")
        self.assertEqual(repaired, r"ORBIT studies sequence asymmetry \cite{orbit2026}.")
        self.assertIn("zero citations is valid", captured["instructions"].lower())
        self.assertIn("key=orbit2026", captured["input"])

    def test_empty_citation_repair_can_remove_an_unsupported_attribution(self):
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", False),
            patch.object(studio, "survey_bibliography_keys", return_value={"known2024"}),
            patch.object(
                studio,
                "writing_bibliography_catalog",
                return_value="key=known2024 | title=Unrelated Work",
            ),
            patch.object(
                studio,
                "post_openai",
                return_value={
                    "id": "resp-narrowed",
                    "output_text": "We instead isolate order effects with matched controls.",
                },
            ),
        ):
            _, repaired = studio.repair_empty_citation_placeholders(
                model="deepseek-v4-flash",
                previous_response_id="resp-audit",
                section="related_work",
                purpose="State the contribution boundary.",
                paragraph=r"An unsupported named method proves this claim \cite{}.",
            )

        self.assertEqual(
            repaired,
            "We instead isolate order effects with matched controls.",
        )
        self.assertFalse(studio.has_empty_citation_placeholder(repaired))

    def test_citation_obligations_become_empty_latex_placeholders(self):
        with patch.object(studio, "bibliography_keys", return_value={"known2020"}):
            text = studio.citation_placeholders(
                r"Missing [CITATION NEEDED]. Unknown \cite{invented2025}. "
                r"Approved \cite{known2020}."
            )
        self.assertEqual(text.count(r"\cite{}"), 2)
        self.assertIn(r"\cite{known2020}", text)
        self.assertNotIn("invented2025", text)

    def test_online_citation_markers_remove_every_key(self):
        text = studio.online_citation_markers(
            r"Known \cite{known2020}; unknown [CITATION NEEDED]."
        )
        self.assertEqual(text, r"Known \cite{}; unknown \cite{}.")

    def test_online_empty_citation_repair_preserves_marker_without_api(self):
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "post_openai") as post_openai,
        ):
            response_id, text = studio.repair_empty_citation_placeholders(
                model="deepseek-v4-flash",
                previous_response_id="resp-audit",
                section="introduction",
                purpose="Locate prior-work obligations.",
                paragraph=r"Prior work establishes this result \cite{}.",
            )
        self.assertEqual(response_id, "resp-audit")
        self.assertEqual(text, r"Prior work establishes this result \cite{}.")
        post_openai.assert_not_called()

    def test_online_citation_audit_marks_obligations_without_bibliography(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {
                "id": "resp-online-audit",
                "output_text": r"CLINC150 is the evaluation benchmark \cite{larson2019}.",
            }

        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "post_openai", side_effect=fake_post),
        ):
            response_id, text = studio.resolve_citations_from_online_bibliography(
                model="deepseek-v4-flash",
                previous_response_id="resp-draft",
                section="experiments",
                purpose="Describe the dataset.",
                paragraph=r"CLINC150 is the evaluation benchmark \cite{}.",
            )

        self.assertEqual(response_id, "resp-online-audit")
        self.assertEqual(text, r"CLINC150 is the evaluation benchmark \cite{}.")
        self.assertNotIn("<verified_catalog>", captured["input"])
        self.assertIn("has no\nbibliography", captured["instructions"])
        self.assertIn(r"literal marker \cite{}", captured["instructions"])
        self.assertNotIn("tools", captured)

    def test_online_intro_and_related_work_reserve_empty_citation_slots(self):
        self.assertEqual(studio.online_citation_placeholder_minimum("introduction", 0), 2)
        self.assertEqual(studio.online_citation_placeholder_minimum("introduction", 1), 2)
        self.assertEqual(studio.online_citation_placeholder_minimum("introduction", 2), 0)
        self.assertEqual(studio.online_citation_placeholder_minimum("related_work", 0), 2)
        self.assertEqual(studio.online_citation_placeholder_minimum("method", 0), 0)

    def test_online_required_citation_slot_is_retried_and_preserved(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"id": "resp-audit", "output_text": "Prior evaluations use fixed option orders."}
            return {
                "id": "resp-required-slot",
                "output_text": r"Prior evaluations use fixed option orders \cite{}.",
            }

        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "post_openai", side_effect=fake_post),
        ):
            response_id, text = studio.resolve_citations_from_online_bibliography(
                model="deepseek-v4-flash",
                previous_response_id="resp-draft",
                section="introduction",
                purpose="Establish the evaluation background.",
                paragraph="Prior evaluations use fixed option orders.",
                minimum_placeholders=1,
            )

        self.assertEqual(response_id, "resp-required-slot")
        self.assertEqual(text, r"Prior evaluations use fixed option orders \cite{}.")
        self.assertEqual(len(payloads), 2)
        self.assertIn("at least 1 literal", payloads[0]["instructions"])
        self.assertIn(r"exact literal \cite{}", payloads[1]["instructions"])

    def test_online_prompt_marks_citation_obligations_without_keys(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"id": "resp-draft", "output_text": "Background claim."}
            return {"id": "resp-audit", "output_text": r"Background claim \cite{}."}

        with (
            patch.object(studio, "post_openai", side_effect=fake_post),
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "bibliography_keys", return_value=set()),
        ):
            response_id, text, added = call_openai(
                section="method",
                model="gpt-5",
                previous_response_id=None,
                purpose="Establish the externally grounded problem.",
                required_heading=None,
                comment="",
                current_text="",
            )

        self.assertEqual((response_id, text, added), ("resp-audit", r"Background claim \cite{}.", []))
        writer = payloads[0]
        self.assertIn("a paragraph may legitimately contain zero citations", writer["instructions"])
        self.assertIn("generic motivation, common knowledge", writer["instructions"])
        self.assertIn("hosted workflow has no bibliography", writer["instructions"])
        self.assertIn(r"literal marker \cite{}", writer["instructions"])
        self.assertIn("<bibliography_catalog></bibliography_catalog>", writer["input"])
        self.assertIn("Never search the web", writer["instructions"])
        self.assertNotIn("tools", writer)
        self.assertEqual(len(payloads), 2)

    def test_online_intro_generation_enforces_a_fillable_citation_slot(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) < 3:
                return {
                    "id": f"resp-{len(payloads)}",
                    "output_text": "Multiple-choice benchmarks commonly use one fixed option order.",
                }
            return {
                "id": "resp-slot",
                "output_text": (
                    r"Multiple-choice benchmarks are widely used \cite{}. "
                    r"They commonly use one fixed option order \cite{}."
                ),
            }

        with (
            patch.object(studio, "post_openai", side_effect=fake_post),
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "bibliography_keys", return_value=set()),
        ):
            response_id, text, added = call_openai(
                section="introduction",
                model="deepseek-v4-flash",
                previous_response_id=None,
                purpose="Establish the benchmark evaluation background.",
                required_heading=None,
                comment="",
                current_text="",
                minimum_online_citation_placeholders=2,
            )

        self.assertEqual((response_id, added), ("resp-slot", []))
        self.assertEqual(text.count(r"\cite{}"), 2)
        self.assertEqual(len(payloads), 3)

    def test_local_prompt_decides_citations_and_uses_only_survey_verified_keys(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp-draft", "output_text": r"CLINC150 is an intent benchmark \cite{larson2019clinc}."}

        with (
            patch.object(studio, "post_openai", side_effect=fake_post),
            patch.object(studio, "survey_bibliography_keys", return_value={"larson2019clinc"}),
        ):
            response_id, text, added = call_openai(
                section="experiments",
                model="gpt-5",
                previous_response_id=None,
                purpose="Describe the evaluation benchmark.",
                required_heading=None,
                comment="",
                current_text="",
            )

        self.assertEqual(response_id, "resp-draft")
        self.assertEqual(text, r"CLINC150 is an intent benchmark \cite{larson2019clinc}.")
        self.assertEqual(added, [])
        self.assertIn("a paragraph may legitimately contain zero citations", captured["instructions"])
        self.assertIn("smallest directly supporting set", captured["instructions"])
        self.assertIn("reports/01_LIT_SURVEY.html", captured["instructions"])
        self.assertNotIn("tools", captured)

    def test_abstract_prompt_and_postprocessing_remove_citations(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {
                "id": "resp-abstract",
                "output_text": r"We study a fixed-budget selector \cite{sengupta2021robustness} and report supported results.",
            }

        with (
            patch.object(studio, "post_openai", side_effect=fake_post),
            patch.object(studio, "survey_bibliography_keys", return_value={"sengupta2021robustness"}),
        ):
            response_id, text, added = call_openai(
                section="abstract",
                model="gpt-5",
                previous_response_id=None,
                purpose="Summarize the paper.",
                required_heading=None,
                comment="",
                current_text="",
            )

        self.assertEqual(response_id, "resp-abstract")
        self.assertEqual(text, "We study a fixed-budget selector and report supported results.")
        self.assertEqual(added, [])
        self.assertIn("Abstract must contain no citation commands", captured["instructions"])

    def test_web_search_sources_are_collected(self):
        response = {
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"type": "url", "url": "https://arxiv.org/abs/1234.5678"}
                        ]
                    },
                }
            ]
        }
        self.assertEqual(
            response_source_urls(response),
            {"https://arxiv.org/abs/1234.5678"},
        )

    def test_web_search_url_citation_annotations_are_collected(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"paragraph": "Claim.", "citations": []}',
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://aclanthology.org/2023.emnlp-main.123",
                                    "title": "Verified paper",
                                    "start_index": 0,
                                    "end_index": 8,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        self.assertEqual(
            response_source_urls(response),
            {"https://aclanthology.org/2023.emnlp-main.123"},
        )

    def test_append_verified_citations_rejects_a_truncated_bibtex_entry(self):
        # Regression: a real batch-writing run's citation search returned a
        # bibtex string truncated mid-field (an accented author name cut
        # off at "Nicol{\") for one citation. The only check here was that
        # the string *opened* with a valid "@type{key," header; it never
        # confirmed the entry was actually complete. That one unbalanced
        # entry got written to references.bib verbatim and corrupted
        # bibtex's parse of every entry after it in the file -- three
        # unrelated, well-formed citations all failed to resolve too, and
        # the whole batch job died on the very first paragraph.
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            paper.mkdir(exist_ok=True)
            bib_path = paper / "references.bib"
            bib_path.write_text(
                "@article{existing2020,\n  title={Existing},\n}\n", encoding="utf-8"
            )
            truncated = (
                "@article{bressan2024marginbased,\n"
                "  title={Margin-Based Active Learning of Classifiers},\n"
                "  author={Bressan, Marco and Cesa-Bianchi, Nicol{\\"
            )
            complete = (
                "@article{gan2024reasoning,\n"
                "  title={Reasoning Robustness},\n"
                "  author={Gan, Esther},\n"
                "  year={2024}\n"
                "}"
            )
            with patch.object(studio, "PAPER", paper):
                added = studio.append_verified_citations(
                    [
                        {
                            "key": "bressan2024marginbased",
                            "bibtex": truncated,
                            "source_url": "https://example.org/bressan",
                        },
                        {
                            "key": "gan2024reasoning",
                            "bibtex": complete,
                            "source_url": "https://example.org/gan",
                        },
                    ],
                    {"https://example.org/bressan", "https://example.org/gan"},
                )
                final_bib = bib_path.read_text(encoding="utf-8")

        self.assertEqual(added, ["gan2024reasoning"])
        self.assertNotIn("bressan2024marginbased", final_bib)
        self.assertIn("gan2024reasoning", final_bib)
        self.assertEqual(final_bib.count("{"), final_bib.count("}"))

    def test_sync_bibliography_command_disables_and_reenables_a_hardcoded_bibliography(
        self,
    ):
        # Regression: the demo project (and any project scaffolded before
        # Paper Studio switched to the conditional \input{sections/
        # bibliography} pattern) hardcodes \bibliography{references}
        # directly in main.tex. Resetting such a project leaves zero
        # citations, so bibtex still runs unconditionally and produces a
        # genuinely empty thebibliography environment -- pdflatex then dies
        # with "Something's wrong--perhaps a missing \item." on
        # \end{thebibliography}. The sync helper must toggle main.tex's
        # hardcoded command off when there are no citations, and must
        # toggle it back on once a citation is accepted, so the
        # bibliography never gets stuck disabled after a real writing
        # session resumes.
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            (paper / "sections").mkdir()
            main_path = paper / "main.tex"
            main_path.write_text(
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "\\bibliography{references}\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            section_path = paper / "sections" / "body.tex"
            section_path.write_text("No citations yet.\n", encoding="utf-8")

            with patch.object(studio, "PAPER", paper):
                studio.sync_manuscript_bibliography_command()
                disabled = main_path.read_text(encoding="utf-8")
                self.assertNotIn("\\bibliography{references}", disabled)
                self.assertIn(
                    "% Paper Studio enables the bibliography after the first accepted citation.",
                    disabled,
                )

                section_path.write_text(
                    "See \\cite{smith2020} for details.\n", encoding="utf-8"
                )
                studio.sync_manuscript_bibliography_command()
                reenabled = main_path.read_text(encoding="utf-8")
                self.assertIn("\\bibliography{references}", reenabled)
                self.assertNotIn(
                    "% Paper Studio enables the bibliography after the first accepted citation.",
                    reenabled,
                )

    def test_abstract_starts_with_system_planned_paragraph(self):
        section = _default_state()["sections"]["abstract"]
        paragraph = current_paragraph(section)
        self.assertEqual(paragraph["id"], "A1")
        self.assertTrue(paragraph["purpose"])
        self.assertTrue(paragraph["rhetorical_role"])

    def test_public_state_exposes_target_architecture_but_not_mutable_plan(self):
        state = public_state(_default_state())
        section = state["sections"]["introduction"]
        self.assertNotIn("paragraphs", section)
        self.assertEqual(section["current_paragraph"]["id"], "I1")
        self.assertTrue(section["current_paragraph"]["architecture"]["relation_to_next"])
        self.assertEqual(len(section["structure_blueprint"]), 6)
        self.assertNotIn("reference_text", section["current_paragraph"])
        self.assertIsNone(section["current_paragraph"]["candidate"])
        self.assertEqual(len(section["paragraph_navigation"]), 6)
        self.assertTrue(section["paragraph_navigation"][0]["selected"])

    def test_structure_blueprint_does_not_render_internal_relation_hints(self):
        app_js = (
            Path(__file__).resolve().parents[1]
            / "research_avatar/paper_studio/static/app.js"
        ).read_text(encoding="utf-8")
        self.assertNotIn("RHETORICAL_ROLE_LABELS", app_js)
        self.assertNotIn("architectureRelationLabel", app_js)
        self.assertNotIn("段落作用：", app_js)
        self.assertNotIn("与前文：", app_js)
        self.assertNotIn("下一步：", app_js)

    def test_related_work_heading_is_explicit_plan_metadata(self):
        state = _default_state()
        paragraph = state["sections"]["related_work"]["paragraphs"][0]
        self.assertEqual(paragraph["heading"], "Safety alignment and refusal behavior.")
        self.assertEqual(paragraph["heading_style"], "textbf")
        visible = public_state(state)["sections"]["related_work"]["current_paragraph"]
        self.assertEqual(visible["heading"], "Safety alignment and refusal behavior.")
        self.assertEqual(visible["heading_style"], "textbf")

    def test_required_heading_is_enforced_without_duplication(self):
        heading = "Jailbreak attacks."
        expected = r"\paragraph{Jailbreak attacks.} Body prose."
        self.assertEqual(enforce_required_heading("Body prose.", heading), expected)
        self.assertEqual(enforce_required_heading(expected, heading), expected)
        self.assertEqual(
            enforce_required_heading(
                r"\paragraph{Wrong heading.} Body prose.", heading
            ),
            expected,
        )
        self.assertEqual(enforce_required_heading("", heading), "")

    def test_section_name_leadins_are_removed_before_planned_headings(self):
        self.assertEqual(
            studio.strip_redundant_section_name_leadin(
                "Related Work. Body prose.", "Related Work"
            ),
            "Body prose.",
        )
        self.assertEqual(
            studio.strip_redundant_section_name_leadin(
                "Abstract: Body prose.", "Abstract"
            ),
            "Body prose.",
        )
        self.assertEqual(
            studio.strip_redundant_section_name_leadin(
                "Abstrct. Body prose.", "Abstract"
            ),
            "Body prose.",
        )
        self.assertEqual(
            studio.strip_redundant_section_name_leadin(
                "Related work establishes a useful baseline.", "Related Work"
            ),
            "Related work establishes a useful baseline.",
        )

    def test_redundant_section_leadin_migration_rewrites_canonical_source(self):
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            sections = paper / "sections"
            sections.mkdir()
            state = studio._default_state()
            related = state["sections"]["related_work"]
            for index, paragraph in enumerate(related["paragraphs"], 1):
                paragraph["accepted_text"] = f"Body paragraph {index}."
            source = "\\section{Related Work}\n\n\\label{sec:related-work}\n\n" + "\n\n".join(
                f"% PAPER_STUDIO_PARAGRAPH:{paragraph['id']}\n\n"
                f"Related Work. {paragraph['accepted_text']}"
                for paragraph in related["paragraphs"]
            )
            target = sections / studio.SECTION_MAP["related_work"]["file"]
            target.write_text(source, encoding="utf-8")
            with patch.object(studio, "PAPER", paper):
                self.assertTrue(
                    studio.repair_redundant_section_leadins_in_manuscript(state)
                )
            repaired = target.read_text(encoding="utf-8")
            self.assertNotIn("Related Work. Body", repaired)
            self.assertIn("Body paragraph 1.", repaired)

    def test_online_placeholder_reference_migration_adds_missing_bound_reference(self):
        state = studio._default_state()
        section, paragraph_id = studio.first_artifact_binding("T1")
        paragraph, _index = studio.paragraph_by_id(state, section, paragraph_id)
        paragraph["accepted_text"] = "The planned comparison will test the hypothesis."
        paragraph["artifacts"] = ["T1"]
        with (
            TemporaryDirectory() as directory,
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "PAPER", Path(directory)),
            patch.dict(studio.TABLES["T1"], {"online_placeholder": True}),
        ):
            sections = Path(directory) / "sections"
            sections.mkdir()
            self.assertTrue(
                studio.repair_online_placeholder_references_in_manuscript(state)
            )
            self.assertIn(
                f"Table~\\ref{{{studio.TABLES['T1']['label']}}}",
                paragraph["accepted_text"],
            )

    def test_heading_styles_support_textbf_and_subsection_groups(self):
        self.assertEqual(
            enforce_required_heading("Body prose.", "Related topic.", "textbf"),
            r"\textbf{Related topic.} Body prose.",
        )
        self.assertEqual(
            enforce_required_heading(
                r"\paragraph{Wrong heading.} Body prose.",
                "Experimental Setup",
                "subsection",
            ),
            "\\subsection{Experimental Setup}\n\nBody prose.",
        )
        state = _default_state()
        experiment = state["sections"]["experiments"]["paragraphs"]
        self.assertEqual(experiment[0]["heading_style"], "subsection")
        self.assertEqual(experiment[1]["heading"], "Main Results")
        self.assertIsNone(experiment[2].get("heading"))

    def test_prose_api_receives_target_architecture_and_explicit_heading(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            return {"id": "resp-r1", "output_text": "Body prose."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, text, _ = call_openai(
                section="related_work",
                model="gpt-5.6",
                previous_response_id=None,
                purpose="Position prior safety-alignment work.",
                required_heading="Safety alignment and refusal behavior.",
                required_heading_style="textbf",
                architecture={
                    "purpose": "Position prior work.",
                    "rhetorical_role": "literature synthesis",
                    "relation_to_previous": "opening",
                    "relation_to_next": "narrows the gap",
                },
                comment="",
                current_text="",
            )

        self.assertEqual(response_id, "resp-r1")
        captured = payloads[0]
        self.assertIn(
            "<paragraph_architecture>",
            captured["input"],
        )
        self.assertNotIn("Reference-paper paragraph", captured["input"])
        self.assertIn(
            "<required_heading>Safety alignment and refusal behavior.",
            captured["input"],
        )
        self.assertIn(
            r"<required_heading_latex>\textbf{Safety alignment and refusal behavior.}",
            captured["input"],
        )
        self.assertIn("<writing_style>", captured["input"])
        self.assertIn("Do not use em dashes", captured["instructions"])
        self.assertIn("LaTeX double/triple hyphens", captured["instructions"])
        self.assertIn(
            "content-adversarial, structure-only material",
            captured["instructions"],
        )
        self.assertIn(
            'Never begin the prose with the section name',
            captured["instructions"],
        )
        self.assertIn(
            "The target project evidence is the sole content authority",
            captured["input"].replace("\n", " "),
        )
        self.assertTrue(
            text.startswith(r"\textbf{Safety alignment and refusal behavior.}")
        )

    def test_latex_prose_rejects_dash_punctuation_but_allows_compound_hyphens(self):
        self.assertIn("em dash", " ".join(studio.latex_prose_issues("Claim—detail.")))
        self.assertIn("en dash", " ".join(studio.latex_prose_issues("Claim–detail.")))
        self.assertIn(
            "double/triple-hyphen",
            " ".join(studio.latex_prose_issues("Claim---detail.")),
        )
        self.assertEqual(
            studio.latex_prose_issues(r"Inference-time control uses \(-1\)."),
            [],
        )

    def test_from_scratch_revision_breaks_the_old_response_chain(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp-fresh", "output_text": "Fresh evidence-only prose."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, text, _ = call_openai(
                section="related_work",
                model="gpt-5-nano",
                previous_response_id="resp-contaminated-history",
                purpose="Interpret only the verified selector evidence.",
                required_heading=None,
                required_heading_style=None,
                reference_paragraph="Unrelated reference-paper subject matter.",
                comment="Rewrite this paragraph from scratch using only current evidence.",
                current_text="OLD-CONTAMINATED-CANDIDATE",
            )

        self.assertEqual(response_id, "resp-fresh")
        self.assertEqual(text, "Fresh evidence-only prose.")
        self.assertNotIn("previous_response_id", captured)
        self.assertIn("<current_candidate></current_candidate>", captured["input"])

    def test_html_profile_writing_style_is_extracted(self):
        style = studio.writing_style_context()
        self.assertIn("Measured abstract tendencies", style)
        self.assertIn("Introduction architecture", style)
        self.assertNotIn("<section", style)

    def test_prompt_bibliography_is_compact_metadata(self):
        bibliography = studio.PAPER / "references.bib"
        previous = bibliography.read_text(encoding="utf-8") if bibliography.exists() else None
        try:
            bibliography.write_text(
                """@article{compact2026,
  author={Ada Author and Ben Writer},
  title={A Compact Citation Record},
  year={2026},
  journal={Journal of Prompt Economy},
  abstract={THIS ABSTRACT MUST NOT ENTER THE PROMPT},
  file={/private/fulltext.pdf}
}\n""",
                encoding="utf-8",
            )
            compact = studio.bibliography_prompt_catalog()
            self.assertIn("key=compact2026", compact)
            self.assertIn("title=A Compact Citation Record", compact)
            self.assertNotIn("THIS ABSTRACT", compact)
            self.assertNotIn("/private/fulltext.pdf", compact)
        finally:
            if previous is None:
                bibliography.unlink(missing_ok=True)
            else:
                bibliography.write_text(previous, encoding="utf-8")

    def test_paragraph_prompt_has_a_hard_cost_budget(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp-budgeted", "output_text": "Budgeted prose."}

        huge = "context " * 20_000
        with (
            patch.object(studio, "post_openai", side_effect=fake_post),
            patch.object(studio, "approved_outline_context", return_value=huge),
            patch.object(studio, "writing_style_context", return_value=huge),
            patch.object(studio, "section_evidence", return_value=huge),
            patch.object(studio, "writing_bibliography_catalog", return_value=huge),
            patch.object(studio, "artifact_writing_context", return_value=[]),
        ):
            call_openai(
                section="introduction",
                model="deepseek-v4-flash",
                previous_response_id=None,
                purpose=huge,
                required_heading=None,
                comment=huge,
                current_text=huge,
                architecture={"context": huge},
                reference_context={"context": huge},
            )

        self.assertLessEqual(
            len(captured["instructions"]) + len(captured["input"]),
            studio.PAPER_TEXT_PROMPT_MAX_CHARS,
        )
        self.assertIn("truncated to control API input cost", captured["input"])

    def test_prompt_bibliography_prefers_records_relevant_to_the_section(self):
        bibliography = studio.PAPER / "references.bib"
        previous = bibliography.read_text(encoding="utf-8") if bibliography.exists() else None
        try:
            records = [
                "@article{generic%02d, title={Generic Unrelated Topic %02d}, year={2025}}"
                % (index, index)
                for index in range(11)
            ]
            records.append(
                "@article{typorobust, title={Keyboard Typo Robustness for Intent Classification}, year={2026}}"
            )
            bibliography.write_text("\n".join(records) + "\n", encoding="utf-8")

            compact = studio.bibliography_prompt_catalog(
                "Measure keyboard typo robustness in intent classification."
            )

            self.assertTrue(compact.startswith("key=typorobust"))
            self.assertNotIn("key=generic10", compact)
            self.assertLessEqual(
                len(compact),
                studio.BIBLIOGRAPHY_PROMPT_MAX_CHARS + 100,
            )
        finally:
            if previous is None:
                bibliography.unlink(missing_ok=True)
            else:
                bibliography.write_text(previous, encoding="utf-8")

    @unittest.skip("reference excerpts are no longer part of Paper Studio")
    def test_reference_excerpt_does_not_override_agent_selected_length(self):
        reference = Path(studio.paragraph_plan()["reference_file"])
        original = reference.read_text(encoding="utf-8")
        try:
            reference.write_text("\n".join(["x" * 1000] * 8), encoding="utf-8")
            self.assertEqual(len(reference_excerpt([1, 8])), 8007)
        finally:
            reference.write_text(original, encoding="utf-8")

    def test_changed_bibliography_is_sent_to_an_existing_section_conversation(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp-next", "output_text": "Revised prose."}

        with (
            patch.object(studio, "active_llm_provider", return_value="openai"),
            patch.object(studio, "post_openai", side_effect=fake_post),
        ):
            call_openai(
                section="introduction",
                model="gpt-5.6",
                previous_response_id="resp-previous",
                purpose="Revise one paragraph.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="",
                current_text="Current prose.",
                bibliography_update="@article{new2026paper, title={New paper}}",
            )

        self.assertIn("<bibliography_update>@article{new2026paper", captured["input"])
        self.assertNotIn("<conversation_bootstrap>", captured["input"])
        self.assertNotIn("<working_abstract>", captured["input"])
        self.assertNotIn("<section_evidence>", captured["input"])

    def test_researcher_prompt_is_the_primary_editing_objective(self):
        payloads = []
        comment = "Remove all numbers and use exactly two sentences."

        def fake_post(payload):
            payloads.append(payload)
            return {"id": "resp-revised", "output_text": "Revised prose. Second sentence."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            call_openai(
                section="introduction",
                model="gpt-5-nano",
                previous_response_id="resp-previous",
                purpose="Revise one paragraph.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment=comment,
                current_text="Current prose contains 42 results.",
            )

        captured = payloads[0]
        self.assertIn("primary editing objective", captured["instructions"])
        self.assertIn("Do not weaken, reinterpret, or silently omit", captured["instructions"])
        self.assertIn(
            f"<researcher_comment>{comment}</researcher_comment>",
            captured["input"],
        )
        self.assertEqual(captured["input"].count(comment), 1)

    def test_existing_conversation_omits_unchanged_section_context(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp-next", "output_text": "Revised prose."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            call_openai(
                section="introduction",
                model="gpt-5.6",
                previous_response_id="resp-previous",
                purpose="Revise one paragraph.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="",
                current_text="Current prose.",
                include_section_context=False,
            )

        self.assertIn("<current_section_context></current_section_context>", captured["input"])
        self.assertNotIn("% fixture", captured["input"])

    def test_nonempty_revision_comment_retries_identical_gpt_output(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"id": "resp-noop", "output_text": "Current prose."}
            return {"id": "resp-retry", "output_text": "Materially revised prose."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, text, _ = call_openai(
                section="introduction",
                model="gpt-5-nano",
                previous_response_id="resp-previous",
                purpose="Revise one paragraph.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="Remove all numerical results.",
                current_text="Current prose.",
            )

        self.assertEqual((response_id, text), ("resp-retry", "Materially revised prose."))
        self.assertEqual(payloads[1]["previous_response_id"], "resp-noop")
        self.assertIn("previous response was unchanged", payloads[1]["instructions"])
        self.assertIn("Remove all numerical results.", payloads[1]["input"])

    def test_nonempty_revision_comment_rejects_second_identical_output(self):
        with (
            patch.object(
                studio,
                "post_openai",
                side_effect=[
                    {"id": "resp-noop", "output_text": "Current prose."},
                    {"id": "resp-still-noop", "output_text": "Current prose."},
                    {"id": "resp-audit", "output_text": "Current prose."},
                ],
            ),
            self.assertRaisesRegex(StudioError, "连续两次返回与当前版本相同"),
        ):
            call_openai(
                section="introduction",
                model="gpt-5-nano",
                previous_response_id="resp-previous",
                purpose="Revise one paragraph.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="Make a concrete revision.",
                current_text="Current prose.",
            )

    def test_unresolved_citation_is_narrowed_without_an_api_search(self):
        with (
            patch.object(
                studio,
                "post_openai",
                side_effect=[
                    {"id": "resp-draft", "output_text": "Broad claim [CITATION NEEDED]."},
                    {"id": "resp-repair", "output_text": "Supported framing."},
                ],
            ) as post,
            patch.object(
                studio,
                "resolve_citations",
                side_effect=AssertionError("citation search must not run"),
            ),
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "bibliography_keys", return_value=set()),
        ):
            response_id, text, added = call_openai(
                section="introduction",
                model="gpt-5.6",
                previous_response_id=None,
                purpose="State only supported context.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="",
                current_text="",
            )

        self.assertEqual((response_id, text, added), ("resp-repair", "Supported framing.", []))
        self.assertEqual(post.call_count, 2)

    def test_non_openai_provider_also_converts_an_invented_key_to_a_placeholder(self):
        with (
            patch.object(
                studio,
                "post_openai",
                side_effect=[
                    {"id": "resp-draft", "output_text": r"Broad claim \cite{invented2024}."},
                    {"id": "resp-repair", "output_text": "Supported positioning."},
                ],
            ) as post,
            patch.object(studio, "active_llm_provider", return_value="deepseek"),
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "bibliography_keys", return_value=set()),
        ):
            response_id, text, _ = call_openai(
                section="related_work",
                model="deepseek-v4-flash",
                previous_response_id=None,
                purpose="Position prior work.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="",
                current_text="",
            )

        self.assertEqual((response_id, text), ("resp-repair", "Supported positioning."))
        self.assertNotIn("invented2024", text)
        self.assertTrue(all("tools" not in call.args[0] for call in post.call_args_list))

    def test_unresolved_sentence_is_dropped_after_narrowing_still_leaves_marker(self):
        self.assertEqual(
            studio.drop_unresolved_citation_sentences(
                "Supported framing. Unsupported detail [CITATION NEEDED]. "
                "Supported conclusion."
            ),
            "Supported framing. Supported conclusion.",
        )

    def test_bound_figure_context_is_sent_and_missing_reference_is_corrected(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"id": "resp-missing-f2", "output_text": "Probe accuracy drops."}
            return {
                "id": "resp-with-f2",
                "output_text": (
                    r"As shown in Figure~\ref{fig:representation}, probe accuracy drops."
                ),
            }

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, text, _ = call_openai(
                section="representation_analysis",
                model="gpt-5.4-mini",
                previous_response_id="resp-s3",
                purpose="Report local linear separability.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="没有引用 F2",
                current_text="Probe accuracy drops.",
                artifacts=["F2"],
            )

        self.assertEqual(response_id, "resp-with-f2")
        self.assertIn(r"Figure~\ref{fig:representation}", text)
        self.assertIn('"id": "F2"', payloads[0]["input"])
        self.assertIn('"caption": "Representation analysis', payloads[0]["input"])
        self.assertIn(r'"required_reference": "Figure~\\ref{fig:representation}"', payloads[0]["input"])
        self.assertEqual(payloads[1]["previous_response_id"], "resp-missing-f2")

    def test_unbound_figure_reference_is_removed_by_one_gpt_correction(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {
                    "id": "resp-extra-f1",
                    "output_text": r"Figure~\ref{fig:overview} is unnecessary here.",
                }
            return {"id": "resp-clean", "output_text": "This paragraph stands alone."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, text, _ = call_openai(
                section="introduction",
                model="gpt-5-nano",
                previous_response_id="resp-i1",
                purpose="State a contribution without another figure mention.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="不要重复引用图1",
                current_text="",
                artifacts=[],
            )

        self.assertEqual((response_id, text), ("resp-clean", "This paragraph stands alone."))
        self.assertIn("allowed-and-required reference list", payloads[1]["input"])
        self.assertIn("[]", payloads[1]["input"])

    def test_verified_bibliography_sync_stays_in_the_same_conversation(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp-synced", "output_text": r"Claim \\cite{knownKey}."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, text = sync_verified_bibliography(
                model="gpt-5.6",
                previous_response_id="resp-resolver",
                section="Related Work",
                purpose="Support a representation claim.",
                paragraph="Claim.",
                added_keys=["knownKey"],
            )

        self.assertEqual(response_id, "resp-synced")
        self.assertEqual(captured["previous_response_id"], "resp-resolver")
        self.assertIn("<verified_bibliography>", captured["input"])
        self.assertEqual(text, r"Claim \\cite{knownKey}.")

    def test_accept_branches_between_online_placeholders_and_local_survey_keys(self):
        source = Path(studio.__file__).read_text(encoding="utf-8")
        accept_source = source.split("    def handle_accept(", 1)[1].split(
            "\n    def ", 1
        )[0]
        self.assertIn("online_citation_markers(text)", accept_source)
        self.assertIn("local_survey_citations(text)", accept_source)
        self.assertIn("validate_citations_for_accept(text", accept_source)
        self.assertNotIn("resolve_citations(", accept_source)
        self.assertNotIn("web_search", accept_source)

    def test_citation_resolver_starts_a_new_chain_when_previous_id_is_absent(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {
                "id": "resp-new-resolver",
                "output_text": json.dumps(
                    {"paragraph": "Supported claim.", "citations": []}
                ),
            }

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, paragraph, added = studio.resolve_citations(
                model="gpt-5.6",
                previous_response_id=None,
                section="Introduction",
                purpose="Support the claim.",
                paragraph="Claim [CITATION NEEDED].",
            )
        self.assertNotIn("previous_response_id", captured)
        self.assertEqual((response_id, paragraph, added), ("resp-new-resolver", "Supported claim.", []))

    def test_generated_paper_reset_requires_exact_project_id(self):
        handler = object.__new__(Handler)
        with patch.object(
            studio, "reset_generated_paper", side_effect=AssertionError("must not run")
        ):
            with self.assertRaisesRegex(StudioError, "项目 ID 不匹配"):
                handler.handle_reset_generated_paper(
                    {"project_id": "wrong-project", "model": "gpt-5.6"}
                )

    def test_generated_paper_reset_returns_fresh_public_state(self):
        handler = object.__new__(Handler)
        response = {}
        handler.send_json = lambda payload: response.update(payload)
        fresh = _default_state()
        with (
            patch.object(studio, "reset_generated_paper", return_value=fresh) as reset,
            patch.object(studio, "public_state", return_value={"fresh": True}),
        ):
            handler.handle_reset_generated_paper(
                {"project_id": studio.PROJECT_ID, "model": "gpt-5.6"}
            )
        reset.assert_called_once_with("gpt-5.6")
        self.assertTrue(response["ok"])
        self.assertEqual(response["state"], {"fresh": True})

    def test_generated_paper_reset_removes_legacy_names_and_preserves_configured_inputs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "paper"
            figure_dir = paper / "fig"
            figure_source_dir = paper / "figsrc"
            state_dir = paper / ".paper_studio"
            figure_dir.mkdir(parents=True)
            (figure_source_dir / "iterations" / "overview").mkdir(parents=True)
            (figure_source_dir / "iterations" / "method").mkdir(parents=True)
            state_dir.mkdir(parents=True)
            (paper / "main.tex").write_text(r"\title{Old Title}", encoding="utf-8")
            (paper / "paper_studio.json").write_text("{}", encoding="utf-8")
            (paper / "main.pdf").write_bytes(b"old pdf")
            (paper / "main.log").write_text("old log", encoding="utf-8")
            for filename in ("overview.pdf", "method.pptx", "unregistered-old.png"):
                (figure_dir / filename).write_text("legacy", encoding="utf-8")
            for name in ("overview", "method"):
                (figure_source_dir / "iterations" / name / "round_01.png").write_text(
                    "legacy", encoding="utf-8"
                )
            configured_shape = figure_source_dir / "seed_shapes.json"
            configured_shape.write_text("{}", encoding="utf-8")
            (state_dir / "legacy-cache.bin").write_text("legacy", encoding="utf-8")

            figures = {key: dict(value) for key, value in studio.FIGURES.items()}
            figures["F1"]["shape_spec"] = "paper/figsrc/seed_shapes.json"
            with (
                patch.multiple(
                    studio,
                    ROOT=root,
                    PAPER=paper,
                    STATE_DIR=state_dir,
                    STATE_FILE=state_dir / "state.json",
                    FIGURE_DIR=figure_dir,
                    FIGURE_SOURCE_DIR=figure_source_dir,
                    DATA_FIGURE_AGENT_DIR=figure_source_dir / "data_agents",
                    TABLE_PREVIEW_DIR=state_dir / "table_previews",
                    PAPER_PAGE_DIR=state_dir / "paper_pages",
                    PROJECT_CONFIG_FILE=paper / "paper_studio.json",
                    FIGURES=figures,
                ),
                patch.object(
                    studio,
                    "compile_paper",
                    return_value=studio.CompileResult(True, "empty scaffold compiled"),
                ),
            ):
                fresh = studio.reset_generated_paper("gpt-5-nano")

            self.assertFalse(figure_dir.exists())
            self.assertEqual(
                sorted(path.relative_to(figure_source_dir) for path in figure_source_dir.rglob("*")),
                [Path("seed_shapes.json")],
            )
            self.assertTrue(configured_shape.exists())
            self.assertFalse((state_dir / "legacy-cache.bin").exists())
            self.assertTrue((state_dir / "state.json").exists())
            self.assertFalse((paper / "main.log").exists())
            self.assertFalse((paper / "main.pdf").exists())
            self.assertTrue((paper / "main.tex").exists())
            self.assertEqual(fresh["model"], "gpt-5-nano")

    def test_table_float_environment_must_match_configured_width(self):
        source = (
            r"\begin{table}\caption{Main}\label{tab:main}"
            r"\begin{tabular}{l}x\end{tabular}\end{table}"
        )
        with self.assertRaisesRegex(StudioError, r"要求使用 table\*"):
            studio.validate_table_latex_source("T1", source)
        corrected = source.replace("{table}", "{table*}")
        self.assertEqual(studio.validate_table_latex_source("T1", corrected), corrected)

    def test_table_layout_conversion_preserves_cells_and_supports_both_spans(self):
        wide = (
            r"\begin{table*}[t]\caption{Main}\label{tab:main}"
            r"\begin{tabular}{lc}Method & Score \\ A & 0.5\end{tabular}"
            r"\end{table*}"
        )
        narrow = studio.convert_table_latex_layout("T1", wide, "single-column")
        self.assertIn(r"\begin{table}[tb]", narrow)
        self.assertIn(r"Method & Score \\ A & 0.5", narrow)
        self.assertNotIn(r"\begin{table*}", narrow)
        self.assertEqual(
            studio.table_layout_mode_from_latex(narrow),
            "single-column",
        )

        restored = studio.convert_table_latex_layout("T1", narrow, "two-column")
        self.assertIn(r"\begin{table*}[t]", restored)
        self.assertIn(r"Method & Score \\ A & 0.5", restored)
        self.assertEqual(studio.table_layout_mode_from_latex(restored), "two-column")

    def test_next_unaccepted_wraps_in_plan_order(self):
        paragraphs = [
            {"accepted_text": "done"},
            {"accepted_text": ""},
            {"accepted_text": "done"},
            {"accepted_text": ""},
        ]
        self.assertEqual(next_unaccepted_index(paragraphs, after=1), 3)
        self.assertEqual(next_unaccepted_index(paragraphs, after=3), 1)

    def test_accepted_paragraph_can_remain_selected_for_revision(self):
        state = _default_state()
        section = state["sections"]["introduction"]
        section["paragraphs"][0]["accepted_text"] = "Accepted version."
        section["current_index"] = 0

        self.assertEqual(current_paragraph(section)["accepted_text"], "Accepted version.")
        visible = public_state(state)["sections"]["introduction"]
        self.assertEqual(visible["current_paragraph"]["id"], "I1")
        self.assertEqual(visible["current_paragraph"]["accepted_text"], "Accepted version.")
        self.assertTrue(visible["paragraph_navigation"][0]["selected"])
        self.assertEqual(visible["paragraph_navigation"][0]["status"], "accepted")

    def test_revision_candidate_takes_navigation_status_over_accepted(self):
        state = _default_state()
        section = state["sections"]["introduction"]
        paragraph = section["paragraphs"][0]
        paragraph["accepted_text"] = "Accepted version."
        paragraph["candidate"] = {"id": "revision", "text": "Revised version."}
        visible = public_state(state)["sections"]["introduction"]
        self.assertEqual(visible["paragraph_navigation"][0]["status"], "candidate")
        self.assertEqual(visible["current_paragraph"]["candidate"]["id"], "revision")

    def test_paragraph_state_marks_related_figure_or_table(self):
        state = _default_state()
        visible_intro = public_state(state)["sections"]["introduction"]
        self.assertEqual(
            [item["id"] for item in visible_intro["current_paragraph"]["artifacts"]],
            ["F1"],
        )
        state["sections"]["experiments"]["current_index"] = 1
        visible_experiments = public_state(state)["sections"]["experiments"]
        self.assertEqual(
            [item["id"] for item in visible_experiments["current_paragraph"]["artifacts"]],
            ["T1"],
        )

    def test_case_sections_replace_actlock_sections(self):
        sections = _default_state()["sections"]
        self.assertIn("representation_analysis", sections)
        self.assertIn("analysis_discussion", sections)
        self.assertNotIn("diagnosis", sections)
        self.assertNotIn("limitations", sections)

    def test_section_source_preserves_heading_and_plan_order(self):
        section = _default_state()["sections"]["introduction"]
        section["paragraphs"][1]["accepted_text"] = "Second."
        section["paragraphs"][0]["accepted_text"] = "First."
        source, accepted = render_section_source("introduction", section)
        self.assertTrue(source.startswith("\\section{Introduction}\n"))
        self.assertIn("% PAPER_STUDIO_PARAGRAPH:I1", source)
        self.assertIn("% PAPER_STUDIO_PARAGRAPH:I2", source)
        self.assertLess(source.index("First."), source.index("Second."))
        self.assertEqual(accepted, "First.\n\nSecond.")

    def test_abstract_has_no_section_heading_and_conclusion_keeps_label(self):
        state = _default_state()["sections"]
        state["abstract"]["paragraphs"][0]["accepted_text"] = "Abstract prose."
        abstract_source, _ = render_section_source("abstract", state["abstract"])
        self.assertEqual(
            abstract_source,
            "% PAPER_STUDIO_PARAGRAPH:A1\nAbstract prose.\n",
        )

        state["conclusion"]["paragraphs"][0]["accepted_text"] = "Conclusion prose."
        conclusion_source, _ = render_section_source("conclusion", state["conclusion"])
        self.assertTrue(conclusion_source.startswith("\\section{Conclusion and Future Work}"))
        self.assertTrue(conclusion_source.rstrip().endswith("\\label{paper:endconclusion}"))

    def test_marked_terminal_prose_recovers_browser_editor_content(self):
        state = _default_state()
        source = (
            "\\section{Introduction}\n\n"
            "% PAPER_STUDIO_PARAGRAPH:I1\nFinal first paragraph.\n\n"
            "% PAPER_STUDIO_PARAGRAPH:I2\nFinal second paragraph.\n"
        )
        state["sections"]["introduction"]["paragraphs"] = state["sections"][
            "introduction"
        ]["paragraphs"][:2]

        recovered = studio.paragraph_texts_from_manuscript(
            "introduction", source, state
        )

        self.assertEqual(
            recovered,
            {"I1": "Final first paragraph.", "I2": "Final second paragraph."},
        )

    def test_markerless_heading_prose_stops_before_unplanned_heading(self):
        state = _default_state()
        paragraphs = state["sections"]["experiments"]["paragraphs"][:2]
        state["sections"]["experiments"]["paragraphs"] = paragraphs
        first = studio.heading_latex(
            paragraphs[0].get("heading"), paragraphs[0].get("heading_style")
        )
        second = studio.heading_latex(
            paragraphs[1].get("heading"), paragraphs[1].get("heading_style")
        )
        source = (
            f"\\section{{Experiments}}\n\n{first}\n\nFinal setup.\n\n"
            f"{second}\n\nFinal result.\n\n"
            "\\subsection{Extra terminal-only analysis}\n\nDo not absorb this.\n"
        )

        recovered = studio.paragraph_texts_from_manuscript(
            "experiments", source, state
        )

        self.assertEqual(recovered[paragraphs[0]["id"]], f"{first}\n\nFinal setup.")
        self.assertEqual(recovered[paragraphs[1]["id"]], f"{second}\n\nFinal result.")

    def test_markerless_unheaded_prose_recovers_around_float(self):
        state = _default_state()
        state["sections"]["introduction"]["paragraphs"] = state["sections"][
            "introduction"
        ]["paragraphs"][:2]
        source = (
            "\\section{Introduction}\n\nFinal first paragraph.\n\n"
            "\\begin{figure}[t]\n\\caption{Example}\n\\end{figure}\n\n"
            "Final second paragraph.\n"
        )

        recovered = studio.paragraph_texts_from_manuscript(
            "introduction", source, state
        )

        self.assertEqual(
            recovered,
            {"I1": "Final first paragraph.", "I2": "Final second paragraph."},
        )

    def test_ambiguous_markerless_prose_does_not_overwrite_state(self):
        state = _default_state()
        state["sections"]["introduction"]["paragraphs"] = state["sections"][
            "introduction"
        ]["paragraphs"][:2]
        recovered = studio.paragraph_texts_from_manuscript(
            "introduction",
            "\\section{Introduction}\n\nOnly one block.\n",
            state,
        )
        self.assertIsNone(recovered)

    def test_approved_figure_is_inserted_after_its_bound_paragraph(self):
        state = _default_state()
        section = state["sections"]["introduction"]
        for index in range(5):
            section["paragraphs"][index]["accepted_text"] = f"Paragraph {index + 1}."
        state["figures"]["F1"]["status"] = "approved"

        source, accepted = render_section_source(
            "introduction", section, state["figures"]
        )

        self.assertLess(source.index("Paragraph 4."), source.index(r"\begin{figure}[htbp]"))
        self.assertLess(source.index(r"\end{figure}"), source.index("Paragraph 5."))
        self.assertIn(r"\includegraphics[width=\columnwidth]{fig/overview_gpt.pdf}", source)
        self.assertIn(r"\label{fig:overview}", source)
        self.assertNotIn(r"Figure~\ref{fig:overview}", source)
        self.assertNotIn(r"\begin{figure}", accepted)

    def test_figure_rendering_is_idempotent(self):
        state = _default_state()
        section = state["sections"]["introduction"]
        for paragraph in section["paragraphs"][:4]:
            paragraph["accepted_text"] = "Accepted paragraph."
        state["figures"]["F1"]["status"] = "approved"

        first, _ = render_section_source("introduction", section, state["figures"])
        second, _ = render_section_source("introduction", section, state["figures"])

        self.assertEqual(first, second)
        self.assertEqual(first.count(r"\label{fig:overview}"), 1)
        self.assertNotIn(r"Figure~\ref{fig:overview}", first)

    def test_saved_figure_placement_overrides_default_anchor(self):
        state = _default_state()
        section = state["sections"]["introduction"]
        for index in range(4):
            section["paragraphs"][index]["accepted_text"] = f"Paragraph {index + 1}."
        state["figures"]["F1"].update(
            {"status": "approved", "placement_after": "I2"}
        )

        source, _ = render_section_source(
            "introduction", section, state["figures"]
        )

        self.assertLess(source.index("Paragraph 2."), source.index(r"\begin{figure}[htbp]"))
        self.assertLess(source.index(r"\end{figure}"), source.index("Paragraph 3."))

    def test_generated_table_is_editable_latex_with_fixed_label(self):
        metrics = {
            "main_results": {
                "benchmarks": {
                    "AdvBench": {
                        "rows": [
                            {"method": "Method A", "mean_asr": 12.0, "mean_sr": 3.0}
                        ]
                    },
                    "TrustLLM": {
                        "rows": [
                            {"method": "Method A", "mean_asr": 9.0, "mean_sr": 2.0}
                        ]
                    },
                }
            }
        }
        latex = generate_table_latex("T1", metrics)
        self.assertIn(r"\begin{table*}[t]", latex)
        self.assertIn(r"\label{tab:main}", latex)
        self.assertIn("Method A & 12.0 & 3.0 & 9.0 & 2.0", latex)

    def test_many_column_wide_table_wraps_repeated_condition_headers(self):
        definition = studio.TABLES["T2"]
        previous_width = definition["width"]
        previous_grid = definition["data_grid"]
        labels = ["Behavior"] + [
            f"{condition} {setting}"
            for condition in ("None", "Positive", "Negative")
            for setting in ("-1", "0", "+1")
        ]
        definition["width"] = "two-column"
        definition["data_grid"] = {
            "type": "records",
            "path": "rows",
            "columns": [
                {"key": f"c{index}", "label": label}
                for index, label in enumerate(labels)
            ],
        }
        try:
            latex = generate_table_latex(
                "T2",
                {"rows": [{f"c{index}": index for index in range(len(labels))}]},
                "行: source\nCaption: Wide table.\n字号: small\n最优值: none",
            )
        finally:
            definition["width"] = previous_width
            definition["data_grid"] = previous_grid
        self.assertIn(r"\setlength{\tabcolsep}{3.5pt}", latex)
        self.assertIn(r"\shortstack{Positive\\+1}", latex)
        self.assertIn(r"\shortstack{Negative\\-1}", latex)

    def test_renderer_strips_model_emitted_top_level_section_heading(self):
        state = _default_state()
        section_id = next(
            key
            for key, value in studio.SECTION_MAP.items()
            if value.get("render") != "abstract"
        )
        section = state["sections"][section_id]
        section["paragraphs"][0]["accepted_text"] = (
            rf"\section{{{studio.SECTION_LATEX_TITLES[section_id]}}} Body text."
        )
        source, _accepted = studio.render_section_source(
            section_id, section, state["figures"], state["tables"]
        )
        self.assertEqual(source.count(r"\section{"), 1)
        self.assertIn("Body text.", source)

    def test_placeholder_table_is_not_preserved_as_an_approved_result(self):
        placeholder = studio.table_placeholder_latex("T1")
        self.assertTrue(studio.table_latex_is_placeholder(placeholder))
        stored = {"status": "approved", "latex": placeholder}
        latex, _prompt, preserved = studio.direct_full_draft_table_source(
            "T1", stored, studio.metrics_bundle()
        )
        self.assertIn(r"\begin{tabular}", latex)
        self.assertFalse(preserved)

    def test_numeric_comparison_gate_rejects_inverted_values(self):
        issues = studio.numeric_comparison_issues(
            r"Prompt-all exceeds last-prompt (\(5.48\times10^{-6}\) versus "
            r"\(5.61\times10^{-6}\))."
        )
        self.assertTrue(issues)
        self.assertFalse(
            studio.numeric_comparison_issues(
                r"Last-prompt exceeds prompt-all (\(5.61\times10^{-6}\) versus "
                r"\(5.48\times10^{-6}\))."
            )
        )
        self.assertFalse(
            studio.numeric_comparison_issues(
                r"The error is lower than the tolerance (\(10^{-10}\) versus \(10^{-8}\))."
            )
        )
        self.assertFalse(
            studio.numeric_comparison_issues(
                "The score fell below 5.34, reaching 4.42 after steering."
            )
        )
        self.assertTrue(
            studio.numeric_comparison_issues("The score 5.34 is below 4.42.")
        )

    def test_appendix_gate_rejects_roadmap_but_accepts_content(self):
        appendix = next(
            key
            for key, value in studio.SECTION_MAP.items()
            if "append" in value.get("title", "").lower()
        )
        self.assertTrue(
            studio.appendix_content_issues(
                appendix, "Appendix A supplies the proof and notation table."
            )
        )
        self.assertFalse(
            studio.appendix_content_issues(
                appendix,
                r"For constant vectors, \(h+v_a+v_b=h+v_b+v_a\); therefore the states coincide.",
            )
        )

    def test_agent_table_metrics_are_normalized_to_three_decimal_places(self):
        latex = (
            r"\begin{table}\begin{tabular}{lc}A & 0.9133333333333333 \\ "
            r"B & -0.0035833333333333134 \\\end{tabular}"
            r"\caption{Result.}\label{tab:x}\end{table}"
        )
        normalized = studio.normalize_table_numeric_precision(latex)
        self.assertIn("0.913", normalized)
        self.assertIn("-0.004", normalized)
        self.assertNotIn("333333333333", normalized)

    def test_table_prompt_locally_reorders_and_styles_without_an_api_call(self):
        metrics = {
            "main_results": {
                "benchmarks": {
                    "AdvBench": {
                        "rows": [
                            {"method": "A", "mean_asr": 12.0, "mean_sr": 3.0},
                            {"method": "B", "mean_asr": 20.0, "mean_sr": 4.0},
                        ]
                    },
                    "TrustLLM": {
                        "rows": [
                            {"method": "A", "mean_asr": 9.0, "mean_sr": 2.0},
                            {"method": "B", "mean_asr": 15.0, "mean_sr": 5.0},
                        ]
                    },
                }
            }
        }
        prompt = "\n".join(
            [
                "数据源: results/",
                "列: Method | TrustLLM ASR | AdvBench ASR",
                "行: B | A",
                "Caption: Prompt-authored local table.",
                "字号: footnotesize",
                "最优值: max",
            ]
        )
        with patch.object(studio, "call_openai", side_effect=AssertionError("API called")):
            latex = generate_table_latex("T1", metrics, prompt)
        self.assertIn(r"\footnotesize", latex)
        self.assertIn(r"\caption{Prompt-authored local table.}", latex)
        self.assertLess(latex.index(r"B & \textbf{15.0}"), latex.index("A & 9.0"))
        self.assertNotIn("StrongREJECT", latex)

    def test_pipe_delimited_table_prompt_preserves_commas_inside_column_labels(self):
        metrics = {
            "defenses": {
                "rows": [
                    {"defense": "Baseline", "residual_asr": 31.4, "benign_utility": 78.6},
                    {"defense": "Boundary-aware", "residual_asr": 22.1, "benign_utility": 77.9},
                ]
            }
        }
        prompt = "\n".join(
            [
                "数据源: results/",
                "列: Defense | Residual ASR | Benign utility",
                "行: source",
                "Caption: Safety comparison, lower ASR is better.",
                "字号: small",
                "最优值: none",
            ]
        )
        with patch.dict(
            studio.TABLES["T2"]["data_grid"]["columns"][1],
            {"label": "Residual ASR (%, lower is better)"},
        ):
            prompt = prompt.replace(
                "Residual ASR", "Residual ASR (%, lower is better)", 1
            )
            latex = generate_table_latex("T2", metrics, prompt)
        self.assertIn("31.4", latex)
        self.assertIn("22.1", latex)

    def test_table_prompt_accepts_natural_language_best_values_phrasing(self):
        # Regression: the demo project's own default table briefs describe
        # "best" in natural English ("highest accuracy", "highest accuracy
        # and lowest count") instead of the grammar's literal none/max/min
        # tokens. Before this fix, generating T1 or T2 with their untouched
        # default prompt always 400'd with "最优值仅支持 none、max 或 min。"
        # -- reachable by any fresh project that never customizes the table
        # prompt.
        metrics = {
            "main_results": {
                "benchmarks": {
                    "AdvBench": {
                        "rows": [
                            {"method": "A", "mean_asr": 12.0, "mean_sr": 3.0},
                            {"method": "B", "mean_asr": 20.0, "mean_sr": 4.0},
                        ]
                    },
                    "TrustLLM": {
                        "rows": [
                            {"method": "A", "mean_asr": 9.0, "mean_sr": 2.0},
                            {"method": "B", "mean_asr": 15.0, "mean_sr": 5.0},
                        ]
                    },
                }
            }
        }
        uniform_prompt = "\n".join(
            [
                "数据源: results/",
                "列: Method | TrustLLM ASR | AdvBench ASR",
                "行: B | A",
                "Caption: Uniform best direction.",
                "字号: footnotesize",
                "最优值: highest accuracy",
            ]
        )
        latex = generate_table_latex("T1", metrics, uniform_prompt)
        self.assertIn(r"B & \textbf{15.0}", latex)

        mixed_prompt = uniform_prompt.replace(
            "最优值: highest accuracy",
            "最优值: highest accuracy and lowest count",
        )
        mixed_latex = generate_table_latex("T1", metrics, mixed_prompt)
        self.assertNotIn(r"\textbf", mixed_latex)

    def test_default_table_prompt_is_persisted_in_new_state(self):
        state = _default_state()
        self.assertEqual(
            state["tables"]["T1"]["generation_prompt"],
            default_table_prompt("T1"),
        )
        self.assertEqual(state["tables"]["T1"]["prompt_history"], [])
        self.assertEqual(state["tables"]["T1"]["agent_prompt"], "")
        self.assertEqual(state["tables"]["T1"]["agent_history"], [])

    def test_table_generate_stays_available_online_while_agent_edit_stays_blocked(self):
        # Regression: reported live by a real user -- clicking to generate a
        # table on the production site silently did nothing. "/api/table
        # /generate" was blanket-blocked online alongside every Agent
        # -subprocess endpoint, even though its default case only needs
        # generate_table_latex's deterministic structured-prompt parser (the
        # exact same safe, non-Agent path materialize_direct_full_draft
        # _artifacts() already relies on at the end of a batch run). Online
        # users had no way to populate a table outside that one full-batch
        # completion path. "/api/table/agent-edit" -- free-text revision of
        # already-approved LaTeX -- has no deterministic substitute and must
        # stay blocked.
        self.assertNotIn("/api/table/generate", studio.ONLINE_DISABLED_ARTIFACT_AGENT_PATHS)
        self.assertIn("/api/table/agent-edit", studio.ONLINE_DISABLED_ARTIFACT_AGENT_PATHS)

    def test_table_prompt_rejects_unknown_directives(self):
        metrics = {
            "defenses": {
                "rows": [
                    {"defense": "Guard", "residual_asr": 12, "benign_utility": 90}
                ]
            }
        }
        with self.assertRaises(StudioError):
            generate_table_latex("T2", metrics, "请随意发挥: yes")

    def test_compile_skips_force_rebuild_on_a_genuinely_fresh_checkout(self):
        # Regression: reported live -- a real project's very first "编译
        # PDF" click failed with "I found no \citation commands---while
        # reading file main.aux". compile_paper() added -g (force everyone
        # remade, ignoring timestamps) whenever main.synctex.gz was
        # missing, to protect a copied/restored project whose stale
        # main.aux/main.bbl might otherwise look falsely up-to-date. But on
        # a project that has genuinely never been compiled (no aux/bbl
        # either), -g makes latexmk run bibtex before any pdflatex pass has
        # ever produced a main.aux with \citation commands in it, so bibtex
        # reads an empty aux and fails outright. latexmk's own default
        # ordering already handles a from-scratch compile correctly
        # without -g; -g should only fire when there's actual stale state
        # (an existing aux/bbl) to protect against.
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            (paper / "main.tex").write_text("paper", encoding="utf-8")
            captured = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                return CompletedProcess(command, 0, "ok", "")

            with (
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "manuscript_entrypoint_errors", return_value=[]),
                patch.object(studio, "shutil_which", return_value="/usr/bin/latexmk"),
                patch.object(studio.subprocess, "run", side_effect=fake_run),
            ):
                studio.compile_paper()
            self.assertNotIn("-g", captured["command"])

            (paper / "main.aux").write_text("% stale aux from a copy", encoding="utf-8")
            with (
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "manuscript_entrypoint_errors", return_value=[]),
                patch.object(studio, "shutil_which", return_value="/usr/bin/latexmk"),
                patch.object(studio.subprocess, "run", side_effect=fake_run),
            ):
                studio.compile_paper()
            self.assertIn("-g", captured["command"])

    def test_compile_discards_stale_empty_bbl_when_first_citation_returns(self):
        # Clearing the only cited section can leave an empty generated .bbl.
        # When the next accepted paragraph adds citations, pdflatex must not
        # read that cache before latexmk has rerun BibTeX.
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            (paper / "sections").mkdir()
            (paper / "main.tex").write_text("paper", encoding="utf-8")
            (paper / "sections" / "body.tex").write_text(
                r"Supported claim \cite{smith2020}.", encoding="utf-8"
            )
            (paper / "main.bbl").write_text(
                "\\begin{thebibliography}{0}\n\\end{thebibliography}\n",
                encoding="utf-8",
            )

            def fake_run(command, **kwargs):
                self.assertFalse((paper / "main.bbl").exists())
                return CompletedProcess(command, 0, "ok", "")

            with (
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "manuscript_entrypoint_errors", return_value=[]),
                patch.object(studio, "shutil_which", return_value="/usr/bin/latexmk"),
                patch.object(studio.subprocess, "run", side_effect=fake_run),
            ):
                result = studio.compile_paper()

            self.assertTrue(result.ok)

    def test_concurrent_compiles_are_serialized_not_interleaved(self):
        # Regression: the HTTP server is threaded, and multiple callers can
        # trigger compile_paper() concurrently (the compile button, the
        # pdf/locate auto-rebuild fallback, a batch-writing job). On the
        # shared, long-lived Demo session in particular, two overlapping
        # latexmk/bibtex runs racing on the same main.aux/main.bbl can
        # corrupt each other's intermediate files -- a real user hit a
        # "missing \item" fatal error on an otherwise-correct manuscript
        # after the read-only pdf/locate fix let a second, concurrent
        # compile actually reach the container. compile_paper() must fully
        # serialize instead of letting two subprocess.run calls overlap.
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            (paper / "main.tex").write_text("paper", encoding="utf-8")
            active = 0
            max_concurrent = 0
            lock = threading.Lock()

            def fake_run(command, **kwargs):
                nonlocal active, max_concurrent
                with lock:
                    active += 1
                    max_concurrent = max(max_concurrent, active)
                time.sleep(0.05)
                with lock:
                    active -= 1
                return CompletedProcess(command, 0, "ok", "")

            with (
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "manuscript_entrypoint_errors", return_value=[]),
                patch.object(studio, "shutil_which", return_value="/usr/bin/latexmk"),
                patch.object(studio.subprocess, "run", side_effect=fake_run),
            ):
                threads = [
                    threading.Thread(target=studio.compile_paper) for _ in range(5)
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=5)
            self.assertEqual(max_concurrent, 1)

    def test_table_preview_is_compiled_from_latex(self):
        required = ("pdflatex", "pdfcrop", "pdftoppm")
        if not all(studio.shutil_which(command) for command in required):
            self.skipTest("LaTeX preview toolchain is unavailable")
        latex = "\n".join(
            [
                r"\begin{table}[tb]",
                r"\centering",
                r"\small",
                r"\begin{tabular}{lc}",
                r"\toprule",
                r"Method & ASR \\",
                r"\midrule",
                r"Local & 42.0 \\",
                r"\bottomrule",
                r"\end{tabular}",
                r"\caption{Compiled preview.}",
                r"\label{tab:defense}",
                r"\end{table}",
            ]
        )
        with TemporaryDirectory() as directory:
            paths = compile_table_preview("T2", latex, Path(directory))
            self.assertTrue(paths["pdf"].read_bytes().startswith(b"%PDF"))
            self.assertTrue(paths["preview"].read_bytes().startswith(b"\x89PNG"))

    def test_generated_table_with_a_long_row_label_shrinks_to_fit_and_compiles(self):
        # Regression: a real batch-writing run compiled a full 19/19 paper
        # where a "single-column" table's own row labels (long method
        # names) made the tabular wider than its column -- a plain "table"
        # environment has no way to know it needs extra horizontal space,
        # so it silently printed on top of the body text the two-column
        # layout had already flowed alongside it. generate_table_latex now
        # measures the tabular into a box and only \resizebox'es it down
        # when it's actually too wide (never stretching one that fits).
        required = ("pdflatex", "pdfcrop", "pdftoppm")
        if not all(studio.shutil_which(command) for command in required):
            self.skipTest("LaTeX preview toolchain is unavailable")
        metrics = {
            "main_results": {
                "benchmarks": {
                    "AdvBench": {
                        "rows": [
                            {
                                "method": "A method name so long it would overflow a "
                                "narrow single-column table width",
                                "mean_asr": 12.0,
                                "mean_sr": 3.0,
                            }
                        ]
                    },
                    "TrustLLM": {
                        "rows": [
                            {
                                "method": "A method name so long it would overflow a "
                                "narrow single-column table width",
                                "mean_asr": 9.0,
                                "mean_sr": 2.0,
                            }
                        ]
                    },
                }
            }
        }
        latex = generate_table_latex("T1", metrics)
        self.assertIn(r"\sbox0{", latex)
        self.assertIn(r"\ifdim\wd0>\linewidth\resizebox{\linewidth}{!}{\usebox0}", latex)
        with TemporaryDirectory() as directory:
            paths = compile_table_preview("T1", latex, Path(directory))
            self.assertTrue(paths["pdf"].read_bytes().startswith(b"%PDF"))

    def test_local_agent_table_edit_uses_codex_cli_without_api_key(self):
        current = "\n".join(
            [
                r"\begin{table}[tb]",
                r"\caption{Current.}",
                r"\label{tab:defense}",
                r"\end{table}",
            ]
        )
        revised = "\n".join(
            [
                r"\begin{table}[tb]",
                r"\centering",
                r"\caption{Revised locally.}",
                r"\label{tab:defense}",
                r"\end{table}",
            ]
        )
        observed = {}

        def fake_run(command, **kwargs):
            observed["command"] = command
            observed["env"] = kwargs["env"]
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(revised, encoding="utf-8")
            return studio.subprocess.CompletedProcess(command, 0, "", "")

        metrics = {
            "defenses": {
                "rows": [
                    {"defense": "Guard", "residual_asr": 12, "benign_utility": 90}
                ]
            }
        }
        with (
            patch.object(studio, "shutil_which", return_value="/usr/bin/codex"),
            patch.object(studio.subprocess, "run", side_effect=fake_run),
            patch.dict(studio.os.environ, {"OPENAI_API_KEY": "must-not-leak"}),
        ):
            result = edit_table_with_local_agent(
                "T2", current, "Improve the grouped header.", metrics=metrics
            )
        self.assertIn(r"\caption{Revised locally.}", result)
        self.assertEqual(observed["command"][1], "exec")
        self.assertIn("read-only", observed["command"])
        self.assertNotIn("OPENAI_API_KEY", observed["env"])

    def test_related_work_plan_contains_only_the_two_retained_groups(self):
        groups = studio.paragraph_plan()["sections"]["related_work"]
        self.assertEqual([item["id"] for item in groups], ["R1", "R2"])
        self.assertEqual(
            [item["heading_style"] for item in groups], ["textbf", "textbf"]
        )
        for item in groups:
            self.assertTrue(item["rhetorical_role"])

    def test_removed_plan_group_is_pruned_and_last_retained_group_is_selected(self):
        state = _default_state()
        related = state["sections"]["related_work"]
        related["paragraphs"].append(
            {
                "id": "R3",
                "heading": "Jailbreak Defenses and Evaluation.",
                "heading_style": "textbf",
                "purpose": "Removed group.",
                "reference_lines": [147, 151],
                "candidate": None,
                "accepted_text": "Accepted R3.",
                "history": [],
            }
        )
        for paragraph in related["paragraphs"]:
            paragraph["accepted_text"] = f"Accepted {paragraph['id']}."
        related["current_index"] = 2
        with TemporaryDirectory() as temporary:
            state_file = Path(temporary) / "state.json"
            state_file.write_text(json.dumps(state), encoding="utf-8")
            with patch.object(studio, "STATE_FILE", state_file):
                loaded = studio.load_state()
        self.assertEqual(loaded["sections"]["related_work"]["current_index"], 1)
        self.assertEqual(
            [
                item["id"]
                for item in loaded["sections"]["related_work"]["paragraphs"]
            ],
            ["R1", "R2"],
        )

    def test_local_agent_response_extracts_only_the_table(self):
        source = (
            "Here is the result:\n```latex\n"
            "\\begin{table}[tb]\\caption{X}\\label{tab:defense}\\end{table}"
            "\n```"
        )
        self.assertEqual(
            extract_agent_table_latex(source),
            r"\begin{table}[tb]\caption{X}\label{tab:defense}\end{table}",
        )

    @unittest.skip("table editing no longer reads reference-paper results")
    def test_reference_context_contains_the_full_case_table(self):
        path, source = table_reference_context()
        self.assertEqual(path, studio.PROJECT_CONFIG["paths"]["reference"])
        self.assertIn("DeepSeek GPT-4o", source)
        self.assertIn("Style Jailbreak 96.0 52.8", source)

    def test_more_numbers_prompt_rejects_caption_only_change(self):
        current = "\n".join(
            [
                r"\begin{table*}[t]",
                r"\begin{tabular}{lc}",
                r"Method & ASR \\",
                r"Style Jailbreak & 86.0 \\",
                r"\end{tabular}",
                r"\caption{Current.}",
                r"\label{tab:main}",
                r"\end{table*}",
            ]
        )
        revised = current.replace("Current.", "More traceable results.")
        with self.assertRaisesRegex(StudioError, "没有增加"):
            require_substantive_table_revision(
                current,
                revised,
                "PDF 里的实验结果不止这么多，还有更多数字",
            )

    @unittest.skip("table editing no longer reads reference-paper results")
    def test_more_numbers_prompt_accepts_added_reference_cells(self):
        current = (
            r"\begin{tabular}{lc}" "\n"
            r"Method & ASR \\" "\n"
            r"Style Jailbreak & 86.0 \\" "\n"
            r"\end{tabular}"
        )
        revised = current.replace(
            r"Style Jailbreak & 86.0 \\",
            "Style Jailbreak & 96.0 & 92.0 & 86.0 \\\\",
        )
        require_substantive_table_revision(
            current, revised, "Add the additional results from the reference PDF."
        )
        self.assertGreater(len(table_numeric_cells(revised)), len(table_numeric_cells(current)))

    def test_browser_job_polling_reschedules_until_terminal_state(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        match = studio.re.search(
            r"async function pollFigureJobs\(\).*?\n\}",
            source,
            flags=studio.re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertIn("finally", match.group(0))
        self.assertIn("ensureFigurePolling();", match.group(0))

    def test_approved_table_is_inserted_after_selected_paragraph(self):
        state = _default_state()
        section = state["sections"]["experiments"]
        for index in range(3):
            section["paragraphs"][index]["accepted_text"] = f"Paragraph {index + 1}."
        state["tables"]["T1"].update(
            {
                "status": "approved",
                "placement_after": "E2",
                "latex": (
                    "\\begin{table*}[t]\n"
                    "\\begin{tabular}{l}A \\\\\n"
                    "\\end{tabular}\n"
                    "\\caption{Main comparison.}\n"
                    "\\label{tab:main}\n"
                    "\\end{table*}"
                ),
            }
        )
        source, _ = render_section_source(
            "experiments", section, state["figures"], state["tables"]
        )
        self.assertLess(source.index("Paragraph 2."), source.index(r"\begin{table*}[t]"))
        self.assertLess(source.index(r"\end{table*}"), source.index("Paragraph 3."))
        self.assertEqual(source.count(r"\label{tab:main}"), 1)

    def test_figure_state_exposes_only_paragraph_placement_metadata(self):
        state = _default_state()
        for paragraph in state["sections"]["introduction"]["paragraphs"][:4]:
            paragraph["accepted_text"] = "Accepted."

        figure = figure_public_state(state)[0]

        self.assertEqual(figure["placement_after"], "I4")
        self.assertEqual(
            [option["id"] for option in figure["placement_options"]],
            ["I1", "I2", "I3", "I4", "I5", "I6"],
        )
        self.assertTrue(figure["placement_options"][3]["accepted"])
        self.assertFalse(figure["placement_options"][4]["accepted"])

    def test_two_column_mechanism_uses_figure_star(self):
        latex = figure_latex("F3")
        self.assertIn(r"\begin{figure*}[t]", latex)
        self.assertIn(r"\includegraphics[width=\textwidth]{fig/method_gpt.pdf}", latex)
        self.assertIn(r"\end{figure*}", latex)

    def test_mechanism_prompt_declares_intro_single_and_model_double_column(self):
        state = _default_state()
        intro = studio.mechanism_source("F1", state)
        model = studio.mechanism_source("F3", state)
        self.assertIn('"placement": "single-column figure"', intro)
        self.assertIn('"image_size": "1024x1024"', intro)
        self.assertIn('"role": "Introduction or motivation figure"', intro)
        self.assertIn("two or three aligned visual groups", intro)
        self.assertIn("pure white background", intro)
        self.assertIn("<bound_paragraph_evidence>", intro)
        self.assertIn("not a results figure", intro)
        self.assertIn("Do not request bar charts", intro)
        self.assertIn("maximum four words each", intro)
        self.assertIn("at most eight text labels", intro)
        self.assertIn('"placement": "two-column figure*"', model)
        self.assertIn('"image_size": "1536x1024"', model)
        self.assertIn("page-width ACL-style method schematic", model)
        self.assertIn("2–4 aligned regions", model)
        self.assertIn("flat modules", model)

    def test_mechanism_build_reconstructs_every_part_as_native_shapes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {
                "spec": root / "figure_spec.json",
                "shapes": root / "figure_shapes.json",
                "source": root / "figure_source.txt",
                "draft": root / "figure.bg.png",
                "preview": root / "figure.png",
                "pdf": root / "nested" / "figure.pdf",
                "pptx": root / "nested" / "figure.pptx",
                "agent_source": root / "agent.py",
                "layout_source": root / "layout.json",
                "layout_prompt": root / "layout_prompt.txt",
            }
            paths["draft"].write_bytes(b"real gpt image")
            paths["spec"].write_text(
                json.dumps({"draw_prompt": "approved prompt"}), encoding="utf-8"
            )
            shape_spec = {"canvas_in": [3.32, 1.8], "shapes": [{}] * 12}
            with (
                patch.object(studio, "FIGURE_SOURCE_DIR", root),
                patch.object(studio, "FIGURE_DIR", root),
                patch.object(studio, "figure_paths", return_value=paths),
                patch.object(studio, "mechanism_shape_spec", return_value=shape_spec),
                patch.object(studio, "run_checked") as run,
                patch.object(studio, "validate_editable_shape_deliverables") as validate,
            ):
                message = studio.build_mechanism_figure("F1")
                self.assertTrue(paths["pdf"].parent.is_dir())
                self.assertTrue(paths["pptx"].parent.is_dir())
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][2], "buildshapes")
        self.assertNotIn("--img", commands[0])
        self.assertEqual(commands[1][2], "pdfshapes")
        validate.assert_called_once_with(shape_spec, paths["pptx"], paths["pdf"])
        self.assertIn("12 个独立 PowerPoint 原生对象", message)

    def test_unchanged_prompt_reuses_existing_gpt_image_without_starting_job(self):
        state = _default_state()
        figure = state["figures"]["F1"]
        figure.update(
            {
                "status": "approved",
                "approved_at": 123,
                "draw_prompt": "same prompt",
                "revision": 4,
            }
        )
        handler = object.__new__(Handler)
        handler.require_figure = lambda body: "F1"
        response = {}
        handler.send_json = lambda payload, status=200: response.update(
            {"payload": payload, "status": status}
        )
        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(studio, "figure_generation_gate", return_value=(True, "")),
            patch.object(
                studio,
                "completed_mechanism_draft_matches_prompt",
                return_value=True,
            ),
            patch.object(studio, "public_state", side_effect=lambda current: current),
            patch.object(studio.threading, "Thread") as thread,
        ):
            handler.handle_figure_draw(
                {"figure_id": "F1", "draw_prompt": "same prompt"}
            )
        self.assertEqual(response["status"], 200)
        self.assertTrue(response["payload"]["reused"])
        self.assertEqual(figure["status"], "approved")
        self.assertEqual(figure["approved_at"], 123)
        self.assertIn("未调用 GPT Image", figure["last_message"])
        save.assert_called_once_with(state)
        thread.assert_not_called()

    def test_online_data_figure_generates_deterministically_without_an_agent(self):
        # Regression coverage for the lightweight (no-package) online
        # onboarding path: a "data" kind figure with one panel must render
        # straight from data_grid records with no Codex CLI Agent and no
        # pdfcrop/node/latexmk composition toolchain, since the shared
        # online container runs none of that.
        state = _default_state()
        figure_definition = dict(studio.FIGURES["F5"])
        figure_definition["data_grid"] = {
            "type": "records",
            "path": "defenses.rows",
            "columns": [
                {"key": "defense", "label": "Defense"},
                {"key": "residual_asr", "label": "Residual ASR"},
            ],
        }
        handler = object.__new__(Handler)
        handler.require_figure = lambda body: "F5"
        handler.require_panel = lambda figure_id, body: "a"
        response = {}
        handler.send_json = lambda payload, status=200: response.update(
            {"payload": payload, "status": status}
        )
        with (
            patch.dict(studio.FIGURES, {"F5": figure_definition}),
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(studio, "figure_generation_gate", return_value=(True, "")),
            patch.object(studio, "public_state", side_effect=lambda current: current),
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
        ):
            handler.handle_figure_generate(
                {"figure_id": "F5", "panel_id": "a", "layout_width": "single-column"}
            )
        self.assertEqual(response["status"], 200)
        self.assertTrue(response["payload"]["ok"])
        figure_state = state["figures"]["F5"]
        self.assertEqual(figure_state["status"], "built")
        self.assertEqual(figure_state["panels"]["a"]["status"], "built")
        self.assertIsNotNone(figure_state["composed_at"])
        pdf_path = studio.figure_paths("F5")["pdf"]
        self.assertTrue(pdf_path.is_file())
        self.assertGreater(pdf_path.stat().st_size, 0)
        save.assert_called_once_with(state)

    def test_online_data_figure_infers_records_grid_from_package_result_keys(self):
        # Evidence-package projects use result_keys for their local Agent
        # plots and do not necessarily carry the lightweight uploader's
        # explicit data_grid.  Online Python rendering must still work.
        figure_definition = dict(studio.FIGURES["F5"])
        figure_definition.pop("data_grid", None)
        figure_definition["result_keys"] = ["artifacts.F5.rows"]
        metrics = {
            "artifacts": {
                "F5": {
                    "rows": [
                        {"setting": "base", "random": "0.81", "ours": "0.84"},
                        {"setting": "hard", "random": "0.72", "ours": "0.79"},
                    ]
                }
            }
        }
        with patch.dict(studio.FIGURES, {"F5": figure_definition}):
            headers, rows = studio.figure_records_grid("F5", metrics)
        self.assertEqual(headers, ["Setting", "Random", "Ours"])
        self.assertEqual(rows[1], ["hard", "0.72", "0.79"])

    def test_data_figure_axis_label_never_uses_last_series_name(self):
        definition = {
            "visible_dimensions": [
                "Behavior",
                "No finetuning",
                "Positive finetuning",
                "Negative finetuning",
            ]
        }
        self.assertEqual(
            studio.data_figure_axis_labels(definition),
            ("Behavior", "Value"),
        )
        definition["y_axis_label"] = "Target-answer probability"
        self.assertEqual(
            studio.data_figure_axis_labels(definition),
            ("Behavior", "Target-answer probability"),
        )

    def test_data_layout_width_controls_paper_float(self):
        wide = figure_latex("F4", {"layout_width": "two-column"})
        narrow = figure_latex("F4", {"layout_width": "single-column"})
        self.assertIn(r"\begin{figure*}[t]", wide)
        self.assertIn(r"\includegraphics[width=\textwidth]", wide)
        self.assertIn(r"\begin{figure}[htbp]", narrow)
        self.assertIn(r"\includegraphics[width=\columnwidth]", narrow)

    def test_wrapfigure_mode_uses_right_side_column_wrap(self):
        latex = figure_latex("F4", {"layout_mode": "wrapfigure"})
        self.assertIn(r"\begin{wrapfigure}{r}{0.48\columnwidth}", latex)
        self.assertIn(r"\includegraphics[width=\linewidth]", latex)
        self.assertIn(r"\end{wrapfigure}", latex)

    def test_mechanism_figure_waits_for_only_its_first_citing_paragraph(self):
        state = _default_state()
        ready, reason = figure_generation_gate("F1", state, {})
        self.assertFalse(ready)
        self.assertIn("I1", reason)
        ready, reason = figure_insertion_gate("F1", state, {})
        self.assertFalse(ready)
        self.assertIn("I1", reason)

        state["sections"]["introduction"]["paragraphs"][0]["accepted_text"] = (
            r"Figure~\ref{fig:overview} motivates the problem."
        )
        ready, reason = figure_generation_gate("F1", state, {})
        self.assertTrue(ready)
        self.assertEqual(reason, "")
        ready, reason = figure_insertion_gate("F1", state, {})
        self.assertTrue(ready)
        self.assertEqual(reason, "")

        state["sections"]["representation_analysis"]["paragraphs"][3]["accepted_text"] = (
            r"Figure~\ref{fig:representation} reports the result."
        )
        ready, reason = figure_insertion_gate(
            "F2", state, {"representation_analysis": {"ok": True}}
        )
        self.assertFalse(ready)
        self.assertIn("F1", reason)
        state["figures"]["F1"]["status"] = "approved"
        state["figures"]["F3"]["status"] = "approved"
        ready, _ = figure_insertion_gate(
            "F2", state, {"representation_analysis": {"ok": True}}
        )
        self.assertTrue(ready)

    def test_model_figure_waits_for_every_configured_method_subsection(self):
        state = _default_state()
        method = state["sections"]["method"]["paragraphs"]
        for paragraph in method[:-1]:
            paragraph["accepted_text"] = "Accepted method subsection."
        ready, reason = figure_generation_gate("F3", state, {})
        self.assertFalse(ready)
        self.assertEqual(
            reason,
            "请先生成并写入 Style Jailbreak section 的 Two-Turn Execution subsection，"
            "然后再画图。",
        )
        method[-1]["accepted_text"] = "Accepted final method subsection."
        ready, reason = figure_generation_gate("F3", state, {})
        self.assertTrue(ready)
        self.assertEqual(reason, "")

    def test_first_reference_renders_placeholder_with_real_caption_and_label(self):
        state = _default_state()
        introduction = state["sections"]["introduction"]
        introduction["paragraphs"][0]["accepted_text"] = (
            r"Figure~\ref{fig:overview} motivates the problem."
        )
        source, _ = render_section_source(
            "introduction", introduction, state["figures"], state["tables"]
        )
        self.assertIn("F1 placeholder -- figure generation is in progress", source)
        self.assertIn(r"\label{fig:overview}", source)
        self.assertIn(
            rf"\caption{{{studio.FIGURES['F1']['caption']}}}",
            source,
        )
        self.assertNotIn(r"\includegraphics", source)

    def test_online_non_data_placeholder_does_not_claim_a_job_is_running(self):
        state = _default_state()
        introduction = state["sections"]["introduction"]
        introduction["paragraphs"][0]["accepted_text"] = (
            r"Figure~\ref{fig:overview} motivates the problem."
        )
        with patch.object(studio, "ONLINE_PROJECT_MODE", True):
            source, _ = render_section_source(
                "introduction", introduction, state["figures"], state["tables"]
            )
        self.assertIn("complete the final artwork after project export", source)
        self.assertNotIn("generation is in progress", source)
        self.assertIn(r"\begin{figure}[t]", source)
        self.assertNotIn(r"\begin{figure*}[t]", source)

    def test_section_rerender_preserves_configured_start_label(self):
        state = _default_state()
        section = state["sections"]["experiments"]
        metadata = dict(studio.SECTION_MAP["experiments"])
        metadata["start_label"] = "sec:experiments"
        with patch.dict(studio.SECTION_MAP, {"experiments": metadata}):
            source, _ = render_section_source("experiments", section)
        self.assertIn(r"\section{Experiments}", source)
        self.assertIn(r"\label{sec:experiments}", source)

    def test_first_table_reference_renders_placeholder_with_real_caption_and_label(self):
        # Regression: only figures had a placeholder mechanism, so a batch
        # -written paragraph citing a not-yet-approved table's \ref{} left a
        # genuinely undefined LaTeX reference for the rest of the run (table
        # materialization, like figure materialization, only happens once
        # the whole full-draft loop finishes).
        state = _default_state()
        experiments = state["sections"]["experiments"]
        experiments["paragraphs"][1]["accepted_text"] = (
            r"Table~\ref{tab:main} reports the main comparison."
        )
        source, _ = render_section_source(
            "experiments", experiments, state["figures"], state["tables"]
        )
        self.assertIn("T1 placeholder -- table generation is in progress", source)
        self.assertIn(r"\label{tab:main}", source)
        self.assertIn(rf"\caption{{{studio.TABLES['T1']['caption']}}}", source)
        self.assertIn(r"\begin{table*}[t]", source)
        self.assertNotIn(r"\begin{tabular}", source)

    def test_online_planned_table_reference_renders_export_placeholder(self):
        state = _default_state()
        experiments = state["sections"]["experiments"]
        experiments["paragraphs"][1]["accepted_text"] = (
            r"Table~\ref{tab:main} reports the planned comparison."
        )
        definition = {**studio.TABLES["T1"], "online_placeholder": True}
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.dict(studio.TABLES, {"T1": definition}),
        ):
            source, _ = render_section_source(
                "experiments", experiments, state["figures"], state["tables"]
            )
        self.assertIn("complete the final table after project export", source)
        self.assertIn(r"\label{tab:main}", source)
        self.assertNotIn("table generation is in progress", source)

    def test_figure_and_table_captions_escape_raw_percent_signs(self):
        # Regression: a real batch-writing run crashed pdflatex with
        # "Runaway argument?" / "Missing $ inserted." because a figure
        # caption like "accuracy at 10%, 25%, and 50% budgets" was written
        # straight into `\caption{...}` unescaped -- the raw "%" turned the
        # rest of the line (through `\label{}` and `\end{figure}`) into a
        # LaTeX comment, corrupting the whole float. Table cell captions
        # already escaped correctly (generate_table_latex uses
        # latex_escape_cell); figure/table placeholders and the approved
        # figure renderer did not.
        raw_caption = "accuracy at 10%, 25%, and 50% budgets & 100% coverage"
        escaped_caption = r"accuracy at 10\%, 25\%, and 50\% budgets \& 100\% coverage"

        placeholder = studio.figure_placeholder_latex("F1", {"caption": raw_caption})
        self.assertIn(rf"\caption{{{escaped_caption}}}", placeholder)
        self.assertNotIn(raw_caption, placeholder)

        recovered_placeholder = studio.figure_placeholder_latex(
            "F1", {"caption": escaped_caption}
        )
        self.assertEqual(recovered_placeholder, placeholder)

        approved = figure_latex("F1", {"caption": raw_caption})
        self.assertIn(rf"\caption{{{escaped_caption}}}", approved)
        self.assertNotIn(raw_caption, approved)
        self.assertEqual(
            figure_latex("F1", {"caption": escaped_caption}),
            approved,
        )

        table_placeholder = studio.table_placeholder_latex("T1", {"caption": raw_caption})
        self.assertIn(rf"\caption{{{escaped_caption}}}", table_placeholder)
        self.assertNotIn(raw_caption, table_placeholder)

    def test_local_agent_figure_deletion_is_visible_without_a_server_restart(self):
        # Reported directly: asking the local Agent chat to delete a figure
        # produced no visible change -- the PDF still showed the figure. The
        # Agent's file edit and recompile were actually correct (verified by
        # inspecting paper/paper_studio.json and paper/main.pdf directly on a
        # real repro), but FIGURES/FIGURE_ORDER/TABLES/TABLE_ORDER are only
        # ever loaded once at process startup, so the already-running server
        # kept reporting the old definition via /api/state until restarted --
        # indistinguishable, from the researcher's side, from the Agent
        # having done nothing at all.
        original_figures = dict(studio.FIGURES)
        original_figure_order = list(studio.FIGURE_ORDER)
        original_tables = dict(studio.TABLES)
        original_table_order = list(studio.TABLE_ORDER)
        try:
            self.assertIn("F1", studio.FIGURES)
            reduced_config = {
                "figures": {}, "figure_order": [],
                "tables": {}, "table_order": [],
            }
            with patch.object(studio, "load_project_config", return_value=reduced_config):
                # A turn that never touched paper_studio.json must not reload.
                studio.reload_figure_and_table_definitions_if_paper_studio_json_changed(
                    ["paper/sections/introduction.tex"]
                )
                self.assertIn("F1", studio.FIGURES)

                studio.reload_figure_and_table_definitions_if_paper_studio_json_changed(
                    ["paper/paper_studio.json"]
                )
            self.assertNotIn("F1", studio.FIGURES)
            self.assertEqual(studio.FIGURE_ORDER, [])
            self.assertEqual(studio.TABLES, {})
            self.assertEqual(studio.TABLE_ORDER, [])
            # Mutated in place, not rebound, so every already-imported
            # reference (including the direct `FIGURES` import used
            # throughout this test file) sees the same update.
            self.assertIs(studio.FIGURES, FIGURES)
            self.assertNotIn("F1", FIGURES)
        finally:
            studio.FIGURES.clear()
            studio.FIGURES.update(original_figures)
            studio.FIGURE_ORDER[:] = original_figure_order
            studio.TABLES.clear()
            studio.TABLES.update(original_tables)
            studio.TABLE_ORDER[:] = original_table_order

    def test_public_figure_state_exposes_separate_generation_and_insertion_gates(self):
        figure = figure_public_state(_default_state())[0]
        self.assertFalse(figure["generation_ready"])
        self.assertFalse(figure["insertion_ready"])
        self.assertEqual(figure["ready"], figure["generation_ready"])
        self.assertIn("I1", figure["insertion_gate_reason"])
        self.assertIn("gpt_preview_url", figure)
        self.assertIn("paper_preview_url", figure)

    def test_mechanism_preview_can_toggle_gpt_and_paper_versions(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="mechanism-preview-switch"', html)
        self.assertIn('id="mechanism-preview-toggle"', html)
        self.assertLess(
            html.index('id="mechanism-preview-toggle"'),
            html.index('id="figure-preview-image"'),
        )
        self.assertNotIn('id="figure-preview-empty"', html)
        self.assertNotIn('生成后在这里检查构图或数据图', html)
        self.assertIn("const mechanismPreviewModes = new Map()", source)
        self.assertIn('mechanismPreviewMode === "gpt"', source)
        self.assertIn('"显示 GPT 原图"', source)
        self.assertIn('"显示 GPT 构图底图（无文字）"', source)
        self.assertIn('"显示可编辑 PPT/PDF 完整版"', source)
        self.assertIn('id="mechanism-preview-note"', html)

    def test_approved_figure_preview_is_locked_to_inserted_paper_pdf(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('figure.status === "approved"', source)
        self.assertIn("paperVersionInserted", source)
        self.assertIn("? figure.paper_preview_url", source)
        self.assertIn('figure.status === "approved"\n    || !figure.gpt_preview_url', source)
        self.assertIn("当前预览与正文 PDF 使用同一个图文件。", source)

    def test_mechanism_prompt_editor_has_two_columns_and_adjacent_draw_flow(self):
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        style = (studio.STATIC / "style.css").read_text(encoding="utf-8")
        self.assertIn('class="mechanism-prompt-workbench"', html)
        self.assertIn('class="mechanism-editor-card mechanism-prompt-card"', html)
        self.assertIn('class="mechanism-editor-card mechanism-revision-card"', html)
        self.assertIn('id="mechanism-draw-stage"', html)
        self.assertIn('id="mechanism-generation-prerequisite"', html)
        self.assertIn('id="mechanism-generation-prerequisite-text"', html)
        self.assertIn('id="mechanism-build-status"', html)
        self.assertIn("mechanismPrerequisiteBlocked", source)
        self.assertIn("可编辑 PPT/PDF 正在后台重建", source)
        self.assertIn("可编辑 PPT/PDF 重建失败", source)
        self.assertLess(html.index('id="draw-prompt"'), html.index('id="prompt-instruction"'))
        self.assertLess(html.index('id="prompt-instruction"'), html.index('id="mechanism-draw-stage"'))
        self.assertLess(html.index('id="mechanism-draw-stage"'), html.index('id="figure-preview-image"'))
        self.assertIn('id="mechanism-flow-prompt"', html)
        self.assertIn('id="mechanism-flow-image"', html)
        self.assertIn('id="mechanism-flow-paper"', html)
        self.assertIn("function updateMechanismFlow(figure)", source)
        self.assertIn('"按右侧指令更新 Prompt"', source)
        self.assertIn('$("mechanism-controls").hidden = !mechanism;', source)
        self.assertIn("grid-template-columns:minmax(0,1.35fr) minmax(240px,.8fr)", style)

    def test_mobile_layout_contains_document_overflow_guards(self):
        style = (studio.STATIC / "style.css").read_text(encoding="utf-8")
        self.assertIn("html,body,.app,.workspace{max-width:100%;overflow-x:hidden}", style)
        self.assertIn(".status-row{width:100%;max-width:100%;overflow-x:auto", style)
        self.assertIn(".paragraph-selector-head{align-items:stretch;flex-direction:column}", style)

    def test_built_mechanism_previews_final_pdf_instead_of_image_draft(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                "draft": root / "figure.bg.png",
                "preview": root / "figure.png",
                "pdf": root / "figure.pdf",
                "pptx": root / "figure.pptx",
            }
            paths["draft"].write_bytes(b"draft")
            paths["pdf"].write_bytes(b"%PDF final")
            state = _default_state()
            state["figures"]["F1"]["status"] = "built"
            with patch.object(studio, "figure_paths", return_value=paths):
                figure = figure_public_state(state)[0]
        self.assertEqual(figure["preview_type"], "pdf")
        self.assertIn("/pdf?", figure["preview_url"])

    def test_approved_mechanism_exposes_only_the_pdf_inserted_in_the_paper(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                "draft": root / "figure.bg.png",
                "preview": root / "figure.png",
                "pdf": root / "figure.pdf",
                "pptx": root / "figure.pptx",
            }
            paths["draft"].write_bytes(b"draft")
            paths["pdf"].write_bytes(b"%PDF final")
            state = _default_state()
            state["figures"]["F1"]["status"] = "approved"
            with (
                patch.object(studio, "figure_paths", return_value=paths),
                patch.object(studio, "mechanism_draft_path", return_value=paths["draft"]),
            ):
                figure = figure_public_state(state)[0]
        self.assertIsNone(figure["gpt_preview_url"])
        self.assertEqual(figure["preview_url"], figure["paper_preview_url"])
        self.assertEqual(figure["preview_type"], "pdf")

    def test_archived_gpt_iteration_restores_mechanism_preview_toggle(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "figsrc"
            figure_dir = root / "fig"
            with (
                patch.object(studio, "FIGURE_SOURCE_DIR", source_dir),
                patch.object(studio, "FIGURE_DIR", figure_dir),
            ):
                paths = studio.figure_paths("F1")
                relocated_spec = source_dir / (
                    str(studio.FIGURES["F1"]["deliverable_stem"]) + "_spec.json"
                )
                relocated_spec.parent.mkdir(parents=True)
                relocated_spec.write_text(
                    json.dumps({"figure_id": "archived-f1"}), encoding="utf-8"
                )
                iteration = relocated_spec.parent / "iterations" / "archived-f1"
                iteration.mkdir(parents=True)
                archived = iteration / "round_03.png"
                archived.write_bytes(b"archived gpt image")
                archived.with_suffix(".prompt.txt").write_text(
                    "approved prompt", encoding="utf-8"
                )
                paths["pdf"].parent.mkdir(parents=True)
                paths["pdf"].write_bytes(b"%PDF final")
                paths["pptx"].write_bytes(b"editable pptx")
                state = _default_state()
                state["figures"]["F1"]["status"] = "built"
                resolved = studio.mechanism_draft_path("F1")
                figure = figure_public_state(state)[0]

        self.assertEqual(resolved, archived)
        self.assertIn("/figure-file/F1/draft?", figure["gpt_preview_url"])
        self.assertIn("/figure-file/F1/pdf?", figure["paper_preview_url"])
        self.assertFalse(figure["gpt_preview_no_text"])

    def test_f6_requires_explicitly_marked_synthetic_layerwise_curves(self):
        state = _default_state()
        state["figures"]["F1"]["status"] = "approved"
        state["figures"]["F3"]["status"] = "approved"
        state["sections"]["appendix"]["paragraphs"][1]["accepted_text"] = (
            r"Figure~\ref{fig:layerwise} shows the synthetic fixture."
        )
        metrics = studio.metrics_bundle()
        ready, reason = figure_gate(
            "F6",
            state,
            metrics,
        )
        self.assertTrue(ready)
        self.assertEqual(reason, "")
        values = metrics["robustness"]["layerwise_values"]
        self.assertTrue(values["synthetic"])
        self.assertIn("not measured", values["notice"])
        self.assertEqual(len(values["series"]), 3)
        self.assertIn("robustness.layerwise_values", FIGURES["F6"]["result_keys"])
        self.assertIn("[SYNTHETIC]", FIGURES["F6"]["caption"])

        ready, reason = figure_gate(
            "F6",
            state,
            {"robustness": {"layerwise_models": ["Model A"]}},
        )
        self.assertFalse(ready)
        self.assertIn("layerwise_values", reason)

    def test_traceable_result_payload_flattens_configured_paths_with_provenance(self):
        metrics = studio.metrics_bundle()
        payload = studio.traceable_result_payload(
            ["representation_analysis.local_probe"], metrics
        )

        self.assertEqual(
            payload["traceable_results"]["representation_analysis.local_probe"],
            metrics["representation_analysis"]["local_probe"],
        )
        self.assertTrue(payload["synthetic"])
        self.assertEqual(payload["notice"], metrics["fixture"]["notice"])
        self.assertEqual(
            payload["source_metrics"],
            studio.PROJECT_CONFIG["paths"]["metrics"],
        )

    def test_data_panel_program_receives_only_its_traceable_result_mapping(self):
        captured = {}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                "source": root / "f2_a.py",
                "pdf": root / "f2_a.pdf",
                "preview": root / "f2_a.png",
            }

            def fake_run(command, *, cwd):
                metrics_path = Path(command[command.index("--metrics") + 1])
                captured.update(json.loads(metrics_path.read_text(encoding="utf-8")))
                paths["pdf"].write_bytes(b"%PDF traceable")
                paths["preview"].write_bytes(b"PNG traceable")

            with (
                patch.object(studio, "data_panel_paths", return_value=paths),
                patch.object(
                    studio,
                    "create_data_figure_code_with_local_agent",
                    return_value="print('plot')\n",
                ),
                patch.object(studio, "data_figure_python", return_value="python"),
                patch.object(studio, "run_checked", side_effect=fake_run),
            ):
                studio.generate_data_figure_with_local_agent("F2", "a")

        self.assertEqual(
            set(captured["traceable_results"]),
            {"representation_analysis.local_probe"},
        )
        self.assertTrue(captured["synthetic"])

    def test_experiment_setup_context_is_compact_and_includes_baseline_implementations(self):
        contract = {
            "dataset_citations": [{"name": "Bench", "url": "https://example.test"}],
            "baseline_contract": {
                "selected": [
                    {"name": "Clean only", "scientific_role": "floor"},
                    {"name": "Random", "scientific_role": "matched control"},
                ]
            },
            "implementation_contract": [
                {"method": "Clean only", "implementation_summary": "shared local path"},
                {"method": "Random", "implementation_summary": "matched local sampler"},
                {"method": "Ours", "implementation_summary": "rank then refit"},
            ],
            "metric_contract": [{"name": "Noisy accuracy"}],
        }
        with TemporaryDirectory() as directory:
            report = Path(directory) / "03_EXPERIMENT_PLAN.html"
            report.write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(contract)
                + "</script>",
                encoding="utf-8",
            )
            with patch.object(studio, "EXPERIMENT_PLAN_FILE", report):
                setup = studio.experiment_setup_context()

        self.assertEqual(setup["baseline_count"], 2)
        self.assertEqual(setup["baselines"][1]["implementation"], "matched local sampler")
        self.assertEqual(setup["proposed_methods"], [{"name": "Ours", "implementation": "rank then refit"}])

    def test_experiment_evidence_is_scoped_to_the_current_paragraph_artifact(self):
        metrics = {
            "result_source": "reports/05_EXP_RESULT.html",
            "evidence_grade": "smoke-only",
            "artifacts": {
                "T1": {"rows": [{"score": "0.1"}]},
                "T2": {"rows": [{"score": "0.2"}]},
            },
        }
        tables = {
            "T1": {"source_sections": ["e"], "data_grid": {"path": "artifacts.T1.rows"}},
            "T2": {"source_sections": ["e"], "data_grid": {"path": "artifacts.T2.rows"}},
        }
        with (
            patch.object(studio, "SECTION_MAP", {"e": {"title": "Experiments", "render": "section"}}),
            patch.object(studio, "RESULT_KEYS", {"e": ["artifacts.T1.rows", "artifacts.T2.rows"]}),
            patch.object(studio, "FIGURES", {}),
            patch.object(studio, "TABLES", tables),
            patch.object(studio, "metrics_bundle", return_value=metrics),
            patch.object(studio, "experiment_setup_context", return_value={"baseline_count": 2}),
        ):
            evidence = json.loads(studio.section_evidence("e", ["T1"]))

        self.assertEqual(evidence["result_source"], "reports/05_EXP_RESULT.html")
        self.assertEqual(evidence["experiment_setup_contract"]["baseline_count"], 2)
        self.assertIn("artifacts.T1.rows", evidence)
        self.assertNotIn("artifacts.T2.rows", evidence)

    def test_method_evidence_includes_the_approved_model_design(self):
        design = {
            "data_flow": "input -> policy -> reward -> update",
            "adaptive_rule": "rank gradient norms",
            "unknowns": ["group size"],
        }
        with (
            patch.object(studio, "SECTION_MAP", {
                "m": {"title": "Method", "render": "section"},
                "i": {"title": "Introduction", "render": "section"},
            }),
            patch.object(studio, "RESULT_KEYS", {"m": [], "i": []}),
            patch.object(studio, "FIGURES", {}),
            patch.object(studio, "TABLES", {}),
            patch.object(studio, "metrics_bundle", return_value={"model_design": design}),
        ):
            method = json.loads(studio.section_evidence("m", []))
            introduction = json.loads(studio.section_evidence("i", []))

        self.assertEqual(method["approved_model_design"], design)
        self.assertNotIn("approved_model_design", introduction)

    def test_setup_without_declared_external_items_does_not_require_three_citations(self):
        with (
            patch.object(
                studio,
                "SECTION_MAP",
                {"setup": {"title": "Experimental Setup", "render": "section"}},
            ),
            patch.object(studio, "experiment_setup_context", return_value={}),
            patch.object(studio, "metrics_bundle", return_value={"evaluation_protocol": {}}),
        ):
            issues = studio.experimental_setup_issues(
                "setup",
                "State the experimental setup and dataset protocol.",
                "We evaluate the configured model on the executed protocol.",
            )

        self.assertNotIn(
            "published datasets and baselines lack introducing citations", issues
        )

    def test_setup_citation_requirement_scales_with_declared_external_items(self):
        setup = {
            "datasets": [{"name": "Dataset A", "citation_key": "sourceA"}],
            "baselines": [{"name": "Method B", "citation_key": "sourceB"}],
        }
        with (
            patch.object(
                studio,
                "SECTION_MAP",
                {"setup": {"title": "Experimental Setup", "render": "section"}},
            ),
            patch.object(studio, "experiment_setup_context", return_value=setup),
            patch.object(studio, "metrics_bundle", return_value={"evaluation_protocol": {}}),
        ):
            one_citation = studio.experimental_setup_issues(
                "setup",
                "State the experimental setup, dataset, and baseline selection.",
                "Dataset A and Method B are used \\cite{sourceA}.",
            )
            two_citations = studio.experimental_setup_issues(
                "setup",
                "State the experimental setup, dataset, and baseline selection.",
                "Dataset A is used \\cite{sourceA}; Method B is used \\cite{sourceB}.",
            )

        self.assertIn(
            "published datasets and baselines lack introducing citations", one_citation
        )
        self.assertNotIn(
            "published datasets and baselines lack introducing citations", two_citations
        )

    def test_online_setup_counts_empty_citation_slots(self):
        setup = {
            "datasets": [{"name": "Dataset A", "url": "https://example.test/a"}],
            "baselines": [{"name": "Method B", "url": "https://example.test/b"}],
        }
        with (
            patch.object(
                studio,
                "SECTION_MAP",
                {"setup": {"title": "Experimental Setup", "render": "section"}},
            ),
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(studio, "experiment_setup_context", return_value=setup),
            patch.object(studio, "metrics_bundle", return_value={"evaluation_protocol": {}}),
        ):
            issues = studio.experimental_setup_issues(
                "setup",
                "State the experimental setup, dataset, and baseline selection.",
                r"Dataset A is used \cite{}; Method B is used \cite{}.",
            )
        self.assertNotIn(
            "published datasets and baselines lack introducing citations", issues
        )

    def test_split_setup_paragraph_checks_only_its_planned_models(self):
        protocol = {
            "models": ["Model Chat 7B", "Model Chat 13B", "Model Base 7B"]
        }
        with (
            patch.object(
                studio,
                "SECTION_MAP",
                {"setup": {"title": "Experimental Setup", "render": "section"}},
            ),
            patch.object(studio, "experiment_setup_context", return_value={}),
            patch.object(
                studio,
                "metrics_bundle",
                return_value={"evaluation_protocol": protocol},
            ),
        ):
            issues = studio.experimental_setup_issues(
                "setup",
                "State Model Chat 7B and Model Chat 13B with the dataset sizes.",
                "We evaluate Model Chat 7B and Model Chat 13B on the held-out sets.",
            )

        self.assertFalse(
            any("Model Base 7B" in issue for issue in issues),
            issues,
        )

    def test_abstract_receives_compact_executed_result_tables(self):
        metrics = {
            "result_source": "reports/05_EXP_RESULT.html",
            "artifacts": {"T1": {"rows": [{"score": "0.1"}]}},
        }
        tables = {
            "T1": {"source_sections": ["e"], "data_grid": {"path": "artifacts.T1.rows"}},
        }
        with (
            patch.object(studio, "SECTION_MAP", {"a": {"title": "Abstract", "render": "abstract"}}),
            patch.object(studio, "RESULT_KEYS", {"a": []}),
            patch.object(studio, "FIGURES", {}),
            patch.object(studio, "TABLES", tables),
            patch.object(studio, "metrics_bundle", return_value=metrics),
        ):
            evidence = json.loads(studio.section_evidence("a", []))

        self.assertEqual(evidence["artifacts.T1.rows"], [{"score": "0.1"}])

    def test_completed_abstract_numeric_placeholders_are_detected(self):
        self.assertEqual(
            studio.numerical_placeholder_issues(
                "Across [X] pairs, [X\\% of cases] passed; sample size was [N]."
            ),
            ["[X]", "[X\\% of cases]", "[N]"],
        )
        self.assertEqual(studio.numerical_placeholder_issues("Accuracy was 0.944."), [])

    def test_bound_artifact_row_gate_rejects_values_from_another_named_row(self):
        evidence = json.dumps({
            "artifacts.T2.rows": [
                {"behavior": "Corrigibility", "positive_0": ".79", "positive_plus_1": ".93"},
                {"behavior": "Refusal", "positive_0": ".95", "positive_plus_1": ".92"},
            ]
        })

        issues = studio.bound_artifact_row_value_issues(
            "Refusal rises from \\(0.79\\) to \\(0.93\\).", evidence
        )

        self.assertEqual(len(issues), 2)
        self.assertTrue(all("Refusal" in issue for issue in issues))

    def test_bound_artifact_row_gate_allows_exact_cells_and_direct_differences(self):
        evidence = json.dumps({
            "artifacts.T6.rows": [{
                "category": "Average",
                "positive": ".57",
                "negative": ".62",
                "none": ".60",
            }]
        })

        issues = studio.bound_artifact_row_value_issues(
            "For Average, positive steering is \\(0.57\\), no steering is "
            "\\(0.60\\), and their differences are \\(0.03\\) and \\(-0.03\\).",
            evidence,
        )

        self.assertEqual(issues, [])

    def test_latex_numeric_values_preserves_leading_decimal_scale(self):
        self.assertEqual(
            studio._latex_numeric_values(
                "Scores are \\(.63\\), \\(.00\\), and \\(1.00\\)."
            ),
            [0.63, 0.0, 1.0],
        )

    def test_writing_ui_does_not_display_raw_experiment_result_panel(self):
        root = Path(__file__).resolve().parents[1]
        index_source = (
            root / "research_avatar/paper_studio/static/index.html"
        ).read_text(encoding="utf-8")
        app_source = (
            root / "research_avatar/paper_studio/static/app.js"
        ).read_text(encoding="utf-8")
        self.assertNotIn('id="result-evidence-card"', index_source)
        self.assertNotIn("renderResultEvidence", app_source)

    def test_reference_original_is_filtered_to_the_selected_paragraph_mapping(self):
        context = {
            "source_heading": "Introduction",
            "logic_summary_zh": "Section-level logic summary.",
            "excerpts": [
                {"id": "REF-I-P1", "text": "First source paragraph."},
                {"id": "REF-I-P2", "text": "Second source paragraph."},
            ],
        }
        paragraph = {"id": "I-P2", "reference_paragraph_ids": ["REF-I-P2"]}
        with patch.object(studio, "section_reference_context", return_value=context):
            filtered = studio.paragraph_reference_context("introduction", paragraph)

        self.assertEqual(
            [item["id"] for item in filtered["excerpts"]],
            ["REF-I-P2"],
        )

    def test_abstracted_reference_constraints_are_filtered_to_current_paragraph(self):
        context = {
            "mode": "abstracted",
            "source_heading": "Abstracted structure",
            "logic_summary_zh": "No source prose.",
            "writing_constraints": [
                {"id": "I-P1", "purpose": "Frame the problem."},
                {"id": "I-P2", "purpose": "State the gap."},
            ],
            "excerpts": [],
        }
        paragraph = {"id": "I-P2", "reference_paragraph_ids": []}
        with patch.object(studio, "section_reference_context", return_value=context):
            filtered = studio.paragraph_reference_context("introduction", paragraph)

        self.assertEqual(filtered["excerpts"], [])
        self.assertEqual(
            filtered["writing_constraints"],
            [{"id": "I-P2", "purpose": "State the gap."}],
        )

    def test_reference_original_fails_closed_without_a_paragraph_mapping(self):
        context = {
            "source_heading": "Introduction",
            "logic_summary_zh": "Section-level logic summary.",
            "excerpts": [{"id": "REF-I-P1", "text": "Do not leak this excerpt."}],
        }
        with (
            patch.object(studio, "section_reference_context", return_value=context),
            patch.object(studio, "_approved_contract", return_value={}),
        ):
            filtered = studio.paragraph_reference_context(
                "introduction", {"id": "I-P1"}
            )

        self.assertEqual(filtered["excerpts"], [])

    def test_reference_mapping_survives_a_display_section_alias(self):
        contract = {
            "paper_outline": [
                {
                    "section_id": "discussion_limitations",
                    "paragraphs": [
                        {
                            "id": "D-P1",
                            "reference_mapping": [
                                {"source_paragraph_id": "REF-D-P1"}
                            ],
                        }
                    ],
                }
            ]
        }
        with patch.object(studio, "_approved_contract", return_value=contract):
            ids = studio.paragraph_reference_ids(
                "discussion_and_limitations", {"id": "D-P1"}
            )

        self.assertEqual(ids, ["REF-D-P1"])

    def test_llm_generation_uses_paragraph_scoped_reference_context(self):
        source = Path(studio.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            source.count(
                "reference_context=paragraph_reference_context(section, paragraph)"
            ),
            2,
        )
        self.assertNotIn(
            "reference_context=section_reference_context(section)",
            source,
        )

    def test_public_figure_order_matches_workflow(self):
        figures = figure_public_state(_default_state())
        self.assertEqual(
            [item["id"] for item in figures],
            ["F1", "F3", "F2", "F4", "F5", "F6"],
        )
        self.assertEqual(figures[0]["phase"], 1)
        self.assertEqual(figures[2]["phase"], 2)

    def test_artifact_card_labels_data_figures_by_kind_not_phase(self):
        app = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn(
            'figure.kind === "mechanism" ? "机制图 · 先完成" : "数据图 · results/ 驱动"',
            app,
        )
        self.assertNotIn(
            'figure.phase === 1 ? "机制图 · 先完成" : "数据图 · results/ 驱动"',
            app,
        )

    def test_every_figure_is_bound_to_its_first_prose_section(self):
        self.assertEqual(FIGURES["F1"]["source_sections"], ["introduction"])
        self.assertEqual(FIGURES["F3"]["source_sections"], ["method"])
        for definition in FIGURES.values():
            self.assertTrue(definition["source_sections"])

    def test_mechanism_figure_exposes_prompt_and_progress_state(self):
        state = _default_state()
        stored = state["figures"]["F1"]
        stored.update(
            {
                "status": "prompt_generating",
                "progress": 45,
                "progress_message": "GPT is composing the prompt.",
            }
        )
        figure = figure_public_state(state)[0]
        self.assertEqual(figure["status"], "prompt_generating")
        self.assertEqual(figure["progress"], 45)
        self.assertEqual(figure["progress_message"], "GPT is composing the prompt.")

    def test_recovered_completed_figures_have_honest_nonempty_prompts(self):
        mechanism = studio.recovered_mechanism_prompt("F1")
        data = studio.recovered_data_panel_prompt("F2", "a")

        self.assertIn("原始生成 Prompt 未归档", mechanism)
        self.assertIn(studio.FIGURES["F1"]["title"], mechanism)
        self.assertIn("原始 Agent Prompt 未归档", data)
        self.assertIn(studio.FIGURES["F2"]["panels"][0]["goal"], data)

    def test_outline_confirmation_recovers_from_canonical_approval_record(self):
        with TemporaryDirectory() as directory:
            paper = Path(directory)
            (paper / "outline_approval.json").write_text(
                json.dumps({"status": "approved"}), encoding="utf-8"
            )
            with patch.object(studio, "PAPER", paper):
                self.assertTrue(studio.outline_is_confirmed())

    def test_sidebar_shows_the_structural_reference_paper(self):
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="project-reference-paper"', html)
        self.assertIn("网页未提供的功能或其他需求，请在本地终端运行 Code Agent。", html)
        self.assertNotIn('id="project-subtitle"', html)
        self.assertNotIn("逐段对话、确认后写入 LaTeX", html + source)
        self.assertIn('$("project-reference-paper")', source)
        self.assertIn("project.reference_paper", source)
        self.assertNotIn("referencePaper.authors", source)
        # A project with no reference_paper.title (e.g. the lightweight
        # onboarding path with no single structural reference) must hide
        # the line rather than show an empty "参考论文：".
        self.assertIn("referenceEl.hidden = true", source)

    def test_online_project_flag_hides_provider_and_key_controls(self):
        # Every online session (real or demo) now shares one server-held
        # DeepSeek key -- there is nothing for that researcher to pick,
        # rotate, or type a model name for, so the model input and the
        # runtime-key dialog trigger stay hidden there. A local desktop
        # install (online_project False) keeps both.
        with patch.object(studio, "ONLINE_PROJECT_MODE", True):
            online_state = public_state(_default_state())
        with patch.object(studio, "ONLINE_PROJECT_MODE", False):
            local_state = public_state(_default_state())
        self.assertTrue(online_state["online_project"])
        self.assertFalse(local_state["online_project"])
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn(
            '$("model-runtime-config").hidden = Boolean(state.online_project);', source,
        )
        self.assertIn(
            '$("runtime-key-open").hidden = Boolean(state.online_project);', source,
        )

    def test_online_mechanism_figures_are_placeholder_only(self):
        state = _default_state()
        with patch.object(studio, "ONLINE_PROJECT_MODE", True):
            visible = public_state(state)
        mechanism = next(item for item in visible["figures"] if item["kind"] == "mechanism")
        data = next(item for item in visible["figures"] if item["kind"] == "data")
        self.assertTrue(mechanism["placeholder_only"])
        self.assertEqual(
            mechanism["placeholder_message"],
            studio.ONLINE_PLACEHOLDER_FIGURE_MESSAGE,
        )
        self.assertFalse(data["placeholder_only"])

        handler = object.__new__(studio.Handler)
        with patch.object(studio, "ONLINE_PROJECT_MODE", True), patch.dict(
            studio.FIGURES[data["id"]], {"online_placeholder": True}
        ):
            hosted_data = next(
                item
                for item in public_state(_default_state())["figures"]
                if item["id"] == data["id"]
            )
            self.assertTrue(hosted_data["placeholder_only"])
            with self.assertRaisesRegex(StudioError, "线上版以带 Caption"):
                handler.reject_online_placeholder_figure(data["id"])

        with patch.object(studio, "ONLINE_PROJECT_MODE", True):
            with self.assertRaisesRegex(StudioError, "线上版以带 Caption"):
                handler.reject_online_placeholder_figure(mechanism["id"])
            handler.reject_online_placeholder_figure(data["id"])

        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="online-figure-placeholder"', html)
        self.assertIn("figure.placeholder_only", source)
        self.assertIn('"PHASE PLACEHOLDER"', source)
        self.assertIn('$("figure-placement-row").hidden = placeholderOnly;', source)
        self.assertIn(
            '$("table-agent-controls").hidden = !isTable || Boolean(state.online_project);',
            source,
        )

    def test_online_verified_source_figure_is_not_a_placeholder(self):
        state = _default_state()
        figure_id = studio.FIGURE_ORDER[0]
        definition = {**studio.FIGURES[figure_id], "kind": "source"}
        with (
            patch.dict(studio.FIGURES, {figure_id: definition}),
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
        ):
            visible = figure_public_state(state)

        source_figure = next(item for item in visible if item["id"] == figure_id)
        self.assertFalse(source_figure["placeholder_only"])

    def test_online_planned_result_table_is_placeholder_only(self):
        state = _default_state()
        table_id = studio.TABLE_ORDER[0]
        definition = {**studio.TABLES[table_id], "online_placeholder": True}
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.dict(studio.TABLES, {table_id: definition}),
            patch.object(studio, "TABLE_ORDER", [table_id]),
        ):
            table = studio.table_public_state(state)[0]
        self.assertTrue(table["placeholder_only"])
        self.assertEqual(
            table["placeholder_message"],
            studio.ONLINE_PLACEHOLDER_TABLE_MESSAGE,
        )

    def test_read_only_demo_control_list_covers_every_mutating_action(self):
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        for control_id in (
            "generate", "accept", "comment", "reset-generated",
            "title-generate", "title-save", "figure-approve", "table-generate",
            "table-approve",
        ):
            self.assertIn(f'"{control_id}"', source)
        self.assertIn("const DEMO_READ_ONLY_CONTROL_IDS = [", source)
        self.assertIn(
            'document.querySelectorAll(".figure-card, .figure-actions button, .paragraph-nav button")',
            source,
        )
        self.assertIn(
            'document.querySelectorAll("input, textarea, select, [contenteditable=\'true\']")',
            source,
        )
        for control_id in ("compile", "model", "model-apply", "runtime-key-open"):
            self.assertIn(f'"{control_id}"', source)

    def test_demo_mode_is_public_but_never_exposes_a_key(self):
        with patch.object(studio, "DEMO_MODE", True):
            visible = public_state(_default_state())
        self.assertTrue(visible["demo_mode"])
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        # Regression: the demo used to let a visitor click an interactive
        # control, fail, and get redirected into a "bring your own key"
        # dialog that no longer exists. The demo is view-only now -- no
        # API-key postMessage escape hatch, no redirect, just a disabled control
        # surface and a plain blocked-request fallback. The sole parent message
        # synchronizes the non-sensitive interface-language preference.
        self.assertNotIn("paper-studio-demo-api-key-required", source)
        self.assertIn(
            'window.parent.postMessage({type: "research-avatar-language", language}',
            source,
        )
        self.assertEqual(source.count("window.parent.postMessage"), 1)
        self.assertNotIn('demo_key_required: "1"', source)
        self.assertIn("function applyReadOnlyDemoRestrictions()", source)
        self.assertIn('if (!state || !state.demo_mode) return;', source)
        self.assertIn('$("figure-prompt").disabled = state.demo_mode', source)

    def test_each_figure_has_an_independent_hidden_conversation_id(self):
        state = _default_state()
        state["figures"]["F1"]["previous_response_id"] = "resp-f1"
        state["figures"]["F3"]["previous_response_id"] = "resp-f3"
        figures = {item["id"]: item for item in figure_public_state(state)}
        self.assertTrue(figures["F1"]["conversation_active"])
        self.assertTrue(figures["F3"]["conversation_active"])
        self.assertNotIn("previous_response_id", figures["F1"])
        self.assertNotIn("previous_response_id", figures["F3"])

    def test_prompt_background_job_stops_at_human_gate(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            state = _default_state()
            state["figures"]["F1"].update(
                {
                    "status": "prompt_generating",
                    "job_token": "job-1",
                    "progress": 5,
                }
            )
            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(
                    studio,
                    "generate_mechanism_prompt",
                    return_value=("resp-figure-1", "Generated drawing prompt."),
                ),
            ):
                studio.save_state(state)
                studio.generate_prompt_worker(
                    "F1",
                    "job-1",
                    "Simplify to a single-column figure.",
                    "Previous dense prompt.",
                )
                finished = studio.load_state()["figures"]["F1"]

            self.assertEqual(finished["status"], "prompt_ready")
            self.assertEqual(finished["previous_response_id"], "resp-figure-1")
            self.assertEqual(finished["draw_prompt"], "Generated drawing prompt.")
            self.assertEqual(
                finished["prompt_instruction"],
                "Simplify to a single-column figure.",
            )
            self.assertEqual(len(finished["prompt_history"]), 1)
            self.assertEqual(
                finished["prompt_history"][0]["previous_prompt"],
                "Previous dense prompt.",
            )
            self.assertIsNone(finished["prompt_approved_at"])
            self.assertEqual(finished["progress"], 100)

    def test_figure_prompt_continues_only_its_own_responses_chain(self):
        with TemporaryDirectory() as directory:
            source_dir = Path(directory)
            state = _default_state()
            state["llm_provider"] = "openai"
            state["model"] = "gpt-5-nano"
            state["figures"]["F1"]["previous_response_id"] = "resp-f1-previous"
            state["figures"]["F3"]["previous_response_id"] = "resp-f3-unrelated"
            captured = {}

            def fake_post(payload):
                captured.update(payload)
                return {
                    "id": "resp-f1-next",
                    "output_text": "A simpler single-column drawing prompt with at most eight text labels.",
                }

            with (
                patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-placeholder"}),
                patch.object(studio, "FIGURE_SOURCE_DIR", source_dir),
                patch.object(studio, "active_llm_provider", return_value="openai"),
                patch.object(studio, "post_openai", side_effect=fake_post),
            ):
                response_id, prompt = studio.generate_mechanism_prompt(
                    "F1",
                    state,
                    prompt_instruction="Make it single-column and simpler.",
                    current_prompt="Previous dense prompt.",
                )

            self.assertEqual(captured["previous_response_id"], "resp-f1-previous")
            self.assertNotEqual(captured["previous_response_id"], "resp-f3-unrelated")
            self.assertTrue(captured["store"])
            self.assertIn("<paper_figure_format>", captured["input"])
            self.assertIn("Previous dense prompt.", captured["input"])
            self.assertNotIn("Approved outline:", captured["input"])
            self.assertEqual(response_id, "resp-f1-next")
            self.assertTrue(
                prompt.startswith(
                    "A simpler single-column drawing prompt with at most eight text labels."
                )
            )
            self.assertIn("use no more than eight text labels total", prompt)

    def test_mechanism_prompt_contract_rejects_results_captions_and_analysis_leaks(self):
        invalid = (
            "Draw a bar chart with an inline caption and make one bar appear higher. "
            "</analysis>"
        )
        issues = studio.mechanism_prompt_contract_issues("F1", invalid)
        self.assertIn("contains analysis markup", issues)
        self.assertIn("requests explanatory captions inside the figure", issues)
        self.assertIn("encodes empirical results in a mechanism figure", issues)
        self.assertIn("does not explicitly enforce the configured text-label limit", issues)

        valid = (
            "Show input tokens, the selection mechanism, and a refit-ready pool; "
            "no empirical results or inline captions. Use no more than 8 text labels."
        )
        self.assertEqual(studio.mechanism_prompt_contract_issues("F1", valid), [])

    def test_full_draft_worker_fills_only_pending_paragraph_and_finishes(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            state = _default_state()
            for section in state["sections"].values():
                for paragraph in section["paragraphs"]:
                    paragraph["accepted_text"] = "Already accepted."
            target_section = studio.batch_writing_order()[0]
            target = state["sections"][target_section]["paragraphs"][0]
            target["accepted_text"] = ""
            token = "full-draft-test"
            state["full_draft_job"] = {
                "token": token,
                "status": "running",
                "server_instance": studio.SERVER_INSTANCE_TOKEN,
                "total": 1,
                "completed": 0,
                "progress": 0,
            }

            def fake_accept(current_state, section, paragraph, text):
                paragraph["accepted_text"] = text
                paragraph["candidate"] = None
                current_state["sections"][section]["accepted_text"] = text
                current_state["compile"] = {"status": "ok", "message": "compiled"}
                return studio.CompileResult(True, "compiled")

            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(
                    studio,
                    "call_openai",
                    return_value=("resp-batch", "Batch draft.", []),
                ) as generate,
                patch.object(
                    studio,
                    "accept_full_draft_paragraph",
                    side_effect=fake_accept,
                ),
                patch.object(
                    studio,
                    "materialize_batch_artifacts",
                    return_value=False,
                ) as materialize,
                patch.object(
                    studio,
                    "pending_batch_artifacts",
                    return_value=[],
                ),
                patch.object(studio, "completed_manuscript_issues", return_value=[]),
            ):
                studio.save_state(state)
                studio.full_draft_worker(token, "gpt-5-nano")
                finished = studio.load_state()

            self.assertEqual(finished["full_draft_job"]["status"], "completed")
            self.assertEqual(finished["full_draft_job"]["completed"], 1)
            accepted, _ = studio.paragraph_by_id(
                finished, target_section, target["id"]
            )
            self.assertEqual(accepted["accepted_text"], "Batch draft.")
            self.assertEqual(generate.call_count, 1)
            materialize.assert_called_once()

    def test_section_draft_targets_only_the_selected_section(self):
        state = _default_state()
        selected = studio.batch_writing_order()[0]
        other = studio.batch_writing_order()[1]
        for section in state["sections"].values():
            for paragraph in section["paragraphs"]:
                paragraph["accepted_text"] = "Already accepted."
        state["sections"][selected]["paragraphs"][0]["accepted_text"] = ""
        state["sections"][other]["paragraphs"][0]["accepted_text"] = ""

        targets = studio.full_draft_targets(state, selected)

        self.assertEqual(targets, [(selected, state["sections"][selected]["paragraphs"][0]["id"])])

    def test_section_draft_worker_materializes_only_selected_section_artifacts(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            state = _default_state()
            for section in state["sections"].values():
                for paragraph in section["paragraphs"]:
                    paragraph["accepted_text"] = "Already accepted."
            selected = next(
                section
                for section in studio.batch_writing_order()
                if any(
                    paragraph.get("artifacts")
                    for paragraph in state["sections"][section]["paragraphs"]
                )
            )
            other = next(
                section for section in studio.batch_writing_order() if section != selected
            )
            selected_paragraph = next(
                paragraph
                for paragraph in state["sections"][selected]["paragraphs"]
                if paragraph.get("artifacts")
            )
            other_paragraph = state["sections"][other]["paragraphs"][0]
            selected_paragraph["accepted_text"] = ""
            other_paragraph["accepted_text"] = ""
            token = "section-draft-test"
            state["section_draft_job"] = {
                "token": token,
                "status": "running",
                "server_instance": studio.SERVER_INSTANCE_TOKEN,
                "section": selected,
                "artifact_ids": studio.section_artifact_ids(state, selected),
                "total": 1,
                "completed": 0,
                "progress": 0,
            }

            def fake_accept(current_state, section, paragraph, text):
                paragraph["accepted_text"] = text
                paragraph["candidate"] = None
                current_state["sections"][section]["accepted_text"] = text
                current_state["compile"] = {"status": "ok", "message": "compiled"}
                return studio.CompileResult(True, "compiled")

            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(studio, "call_openai", return_value=("resp", "Section draft.", [])) as generate,
                patch.object(studio, "accept_full_draft_paragraph", side_effect=fake_accept),
                patch.object(studio, "materialize_batch_artifacts") as materialize,
                patch.object(studio, "pending_batch_artifacts", return_value=[]),
                patch.object(studio, "synchronize_paragraph_editors_from_manuscript"),
                patch.object(studio, "synchronize_artifact_workbenches_from_manuscript"),
            ):
                studio.save_state(state)
                studio.section_draft_worker(token, "gpt-5-nano", selected)
                finished = studio.load_state()

            self.assertEqual(finished["section_draft_job"]["status"], "completed")
            self.assertIsNone(finished["full_draft_job"])
            self.assertEqual(finished["sections"][selected]["paragraphs"][0]["accepted_text"], "Section draft.")
            self.assertEqual(finished["sections"][other]["paragraphs"][0]["accepted_text"], "")
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(materialize.call_count, 1)
            self.assertEqual(
                materialize.call_args.args[1],
                studio.section_artifact_ids(state, selected),
            )

    def test_section_draft_ui_shows_real_paragraph_progress_while_running(self):
        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        source = (studio.STATIC / "app.js").read_text(encoding="utf-8")
        style = (studio.STATIC / "style.css").read_text(encoding="utf-8")
        self.assertIn('id="section-draft-progress-row"', html)
        self.assertIn('id="section-draft-progress"', html)
        self.assertIn('id="section-draft-progress-text" aria-live="polite"', html)
        self.assertIn('["running", "artifacts_pending"].includes(sectionDraftJob.status)', source)
        self.assertIn('sectionDraftJob.completed || 0', source)
        self.assertIn('sectionDraftJob.total || sectionPending', source)
        self.assertIn('sectionDraftJob.progress_message', source)
        self.assertIn('.section-draft-progress progress', style)

    def test_section_artifact_status_ignores_other_sections_and_blocks_completion(self):
        state = _default_state()
        for section in state["sections"].values():
            for paragraph in section["paragraphs"]:
                paragraph["accepted_text"] = "Accepted prose."
        selected = next(
            section
            for section in studio.batch_writing_order()
            if studio.section_artifact_ids(state, section)
        )
        scoped = studio.section_artifact_ids(state, selected)
        selected_artifact = scoped[0]
        other_artifact = next(
            artifact_id
            for artifact_id in [*studio.FIGURE_ORDER, *studio.TABLE_ORDER]
            if artifact_id not in scoped
        )
        for figure_id in studio.FIGURE_ORDER:
            state["figures"][figure_id]["status"] = "approved"
        for table_id in studio.TABLE_ORDER:
            state["tables"][table_id]["status"] = "approved"
        selected_collection = "figures" if selected_artifact in studio.FIGURES else "tables"
        other_collection = "figures" if other_artifact in studio.FIGURES else "tables"
        state[selected_collection][selected_artifact]["status"] = "pending"
        state[other_collection][other_artifact]["status"] = "pending"
        state["section_draft_job"] = {
            "status": "artifacts_pending",
            "section": selected,
            "artifact_ids": scoped,
        }

        status_ready = lambda current, figure_id: (
            current["figures"][figure_id]["status"] == "approved"
        )
        with patch.object(
            studio, "batch_figure_has_real_deliverables", side_effect=status_ready
        ):
            studio.refresh_full_draft_artifact_status(state)

            self.assertEqual(
                state["section_draft_job"]["pending_artifacts"], [selected_artifact]
            )
            self.assertEqual(state["section_draft_job"]["status"], "artifacts_pending")
            state[selected_collection][selected_artifact]["status"] = "approved"
            studio.refresh_full_draft_artifact_status(state)
            self.assertEqual(state["section_draft_job"]["status"], "completed")
            self.assertEqual(state["section_draft_job"]["pending_artifacts"], [])
            self.assertIsNone(state["full_draft_job"])
            state[selected_collection][selected_artifact]["status"] = "pending"
            studio.refresh_full_draft_artifact_status(state)
        self.assertEqual(
            state["section_draft_job"]["pending_artifacts"], [selected_artifact]
        )

    def test_slow_single_paragraph_generation_cannot_erase_new_full_draft_job(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            state = _default_state()
            section = studio.batch_writing_order()[0]
            paragraph = studio.current_paragraph(state["sections"][section])
            self.assertIsNotNone(paragraph)
            token = "newer-batch-job"

            def model_returns_after_batch_started(**_kwargs):
                latest = studio.load_state()
                latest["full_draft_job"] = {
                    "token": token,
                    "status": "running",
                    "server_instance": studio.SERVER_INSTANCE_TOKEN,
                    "total": 1,
                    "completed": 0,
                }
                studio.save_state(latest)
                return "stale-response", "Stale single paragraph.", []

            handler = object.__new__(Handler)
            handler.send_json = MagicMock()
            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(studio, "call_openai", side_effect=model_returns_after_batch_started),
                patch.object(studio, "bibliography_fingerprint", return_value="bib"),
                patch.object(studio, "section_source_fingerprint", return_value="source"),
            ):
                studio.save_state(state)
                with self.assertRaisesRegex(StudioError, "过时候选"):
                    handler.handle_generate({
                        "section": section,
                        "paragraph_id": paragraph["id"],
                        "model": "test-model",
                        "current_text": "",
                        "comment": "",
                    })
                finished = studio.load_state()

            self.assertEqual(finished["full_draft_job"]["token"], token)
            self.assertEqual(finished["full_draft_job"]["status"], "running")
            current = studio.current_paragraph(finished["sections"][section])
            self.assertIsNone(current.get("candidate"))

    def test_full_draft_reports_bound_artifacts_instead_of_false_completion(self):
        state = _default_state()
        for section in state["sections"].values():
            for paragraph in section["paragraphs"]:
                paragraph["accepted_text"] = "Accepted prose."
        for figure_id in studio.FIGURE_ORDER:
            state["figures"][figure_id]["status"] = "approved"
        state["figures"]["F1"]["status"] = "pending"
        for table_id in ("T1", "T2"):
            state["tables"][table_id]["status"] = "approved"

        status_ready = lambda current, figure_id: (
            current["figures"][figure_id]["status"] == "approved"
        )
        with patch.object(
            studio, "batch_figure_has_real_deliverables", side_effect=status_ready
        ):
            self.assertEqual(studio.pending_batch_artifacts(state), ["F1"])
            state["full_draft_job"] = {"status": "artifacts_pending"}
            studio.refresh_full_draft_artifact_status(state)
            self.assertEqual(state["full_draft_job"]["pending_artifacts"], ["F1"])
            state["figures"]["F1"]["status"] = "approved"
            studio.refresh_full_draft_artifact_status(state)
        self.assertEqual(state["full_draft_job"]["status"], "completed")
        self.assertEqual(state["full_draft_job"]["pending_artifacts"], [])

    def test_full_draft_can_resume_artifact_only_failure(self):
        state = _default_state()
        for section in state["sections"].values():
            for paragraph in section["paragraphs"]:
                paragraph["accepted_text"] = "Accepted prose."
        first_table = studio.TABLE_ORDER[0]
        state["tables"][first_table]["status"] = "pending"
        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state"),
            patch.object(studio, "outline_is_confirmed", return_value=True),
            patch.object(studio, "active_llm_provider", return_value="deepseek"),
            patch.object(
                studio,
                "api_setup_for_provider",
                return_value={"configured": True},
            ),
            patch.object(studio, "PAPER") as paper,
        ):
            paper.__truediv__.return_value.exists.return_value = True
            _token, started = studio.start_full_draft_job("deepseek-v4-flash")
        self.assertEqual(started["full_draft_job"]["total"], 0)
        self.assertEqual(started["full_draft_job"]["status"], "running")

    def test_online_full_draft_treats_non_data_placeholder_as_complete(self):
        state = _default_state()
        for section in state["sections"].values():
            for paragraph in section["paragraphs"]:
                paragraph["accepted_text"] = "Accepted prose."
        for figure_id in studio.FIGURE_ORDER:
            state["figures"][figure_id]["status"] = "approved"
        state["figures"]["F1"]["status"] = "pending"
        for table_id in studio.TABLE_ORDER:
            state["tables"][table_id]["status"] = "approved"

        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.object(
                studio,
                "batch_figure_has_real_deliverables",
                side_effect=lambda current, figure_id: (
                    studio.is_hosted_placeholder_artifact(figure_id)
                    or current["figures"][figure_id]["status"] == "approved"
                ),
            ),
        ):
            self.assertEqual(studio.pending_batch_artifacts(state), [])

    def test_local_full_draft_rejects_approved_figure_without_real_files(self):
        state = _default_state()
        figure_id = studio.FIGURE_ORDER[0]
        state["figures"][figure_id]["status"] = "approved"
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", False),
            patch.object(
                studio,
                "figure_paths",
                return_value={
                    "pdf": Path("/definitely/missing/figure.pdf"),
                    "preview": Path("/definitely/missing/figure.png"),
                    "shapes": Path("/definitely/missing/figure_shapes.json"),
                    "pptx": Path("/definitely/missing/figure.pptx"),
                },
            ),
        ):
            self.assertFalse(
                studio.batch_figure_has_real_deliverables(state, figure_id)
            )

    def test_online_full_draft_treats_explicit_data_and_table_placeholders_as_complete(self):
        state = _default_state()
        for section in state["sections"].values():
            for paragraph in section["paragraphs"]:
                paragraph["accepted_text"] = "Accepted prose."
        figure_id = studio.FIGURE_ORDER[0]
        table_id = studio.TABLE_ORDER[0]
        state["figures"][figure_id]["status"] = "pending"
        state["tables"][table_id]["status"] = "pending"
        with (
            patch.object(studio, "ONLINE_PROJECT_MODE", True),
            patch.dict(studio.FIGURES[figure_id], {"online_placeholder": True}),
            patch.dict(studio.TABLES[table_id], {"online_placeholder": True}),
        ):
            self.assertNotIn(
                figure_id,
                studio.pending_batch_artifacts(state, [figure_id, table_id]),
            )
            self.assertNotIn(
                table_id,
                studio.pending_batch_artifacts(state, [figure_id, table_id]),
            )

    def test_full_draft_preserves_researcher_approved_table_latex(self):
        custom = studio.generate_table_latex("T1", studio.metrics_bundle()).replace(
            "Main safety comparison across both benchmarks.",
            "Researcher-approved caption, preserving a manual clarification.",
        )
        stored = {
            "status": "approved",
            "latex": custom,
            "generation_prompt": "Researcher-approved prompt",
        }
        with patch.object(
            studio, "generate_table_latex", side_effect=AssertionError("overwritten")
        ):
            latex, prompt, preserved = studio.direct_full_draft_table_source(
                "T1", stored, studio.metrics_bundle()
            )
        self.assertTrue(preserved)
        self.assertEqual(latex, custom)
        self.assertEqual(prompt, "Researcher-approved prompt")

    def test_stuck_running_job_from_a_dead_process_self_heals_on_next_load(self):
        # Regression: a real production batch job hung mid-generation
        # (progress silently froze for 7+ minutes with no failure) and the
        # underlying container was later found to have restarted, orphaning
        # the session -- exactly the scenario load_state()'s server_instance
        # check exists to recover from, but it had zero test coverage. If a
        # "running" job's server_instance token doesn't match the current
        # process (a fresh SERVER_INSTANCE_TOKEN each process start), the
        # very next load_state() call anywhere must turn it into a clean,
        # actionable "服务已重启" failure instead of leaving it stuck at
        # "running" forever with no way for the researcher to tell.
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_file = state_dir / "state.json"
            with (
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
            ):
                stuck = _default_state()
                stuck["full_draft_job"] = {
                    "token": "orphaned-token",
                    "status": "running",
                    "server_instance": "a-previous-process-instance",
                    "total": 19,
                    "completed": 13,
                    "progress": 68,
                    "progress_message": "正在生成 Experiments · E-P5",
                }
                studio.save_state(stuck)

                recovered = studio.load_state()

            job = recovered["full_draft_job"]
            self.assertEqual(job["status"], "failed")
            self.assertIsNone(job["token"])
            self.assertIn("服务已重启", job["progress_message"])
            self.assertIn("可从未完成段落继续", job["progress_message"])
            # The 13 already-completed paragraphs are real accepted LaTeX
            # (persisted per-paragraph as they land), not job-state --
            # recovery must not touch or reset that count/progress.
            self.assertEqual(job["completed"], 13)

    def test_direct_full_draft_uses_same_job_without_opening_browser(self):
        with TemporaryDirectory() as directory:
            paper = Path(directory) / "paper"
            state_dir = paper / ".paper_studio"
            state_file = state_dir / "state.json"
            paper.mkdir()
            (paper / ".outline-approved").write_text("approved\n", encoding="utf-8")
            (paper / "main.tex").write_text("paper\n", encoding="utf-8")
            state = _default_state()
            for section in state["sections"].values():
                for paragraph in section["paragraphs"]:
                    paragraph["accepted_text"] = "Already accepted."
            section = studio.batch_writing_order()[0]
            state["sections"][section]["paragraphs"][0]["accepted_text"] = ""

            def fake_worker(token, _model):
                current = studio.load_state()
                for figure in current["figures"].values():
                    figure["status"] = "approved"
                for table in current["tables"].values():
                    table["status"] = "approved"
                current["full_draft_job"].update(
                    status="completed",
                    token=None,
                    completed=1,
                    progress=100,
                    progress_message="done",
                )
                studio.save_state(current)

            with (
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(studio, "full_draft_worker", side_effect=fake_worker) as worker,
                patch.object(
                    studio,
                    "batch_figure_has_real_deliverables",
                    return_value=True,
                ),
                patch.dict(studio.os.environ, {studio.API_KEY_ENVIRONMENT_VARIABLE: "secret"}),
                patch("builtins.print"),
            ):
                studio.save_state(state)
                studio.run_direct_full_draft("gpt-5-nano")

            worker.assert_called_once()

    def test_project_config_rejects_incomplete_batch_writing_order(self):
        config = json.loads(studio.PROJECT_CONFIG_FILE.read_text(encoding="utf-8"))
        config["batch_writing_order"] = [config["sections"][0]["id"]]
        with TemporaryDirectory(dir=studio.ROOT / "tests") as directory:
            path = Path(directory) / "paper_studio.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "batch_writing_order"):
                studio.load_project_config(path, root=studio.ROOT)

    def test_unexecuted_experiment_tense_guard_rejects_result_like_present_tense(self):
        with patch.dict(
            studio.SECTION_MAP,
            {"e": {"title": "Proposed Experiments"}},
            clear=True,
        ):
            issues = studio.unexecuted_experiment_tense_issues(
                "e",
                "Table~\\ref{tab:main} compares the methods, and we report AUROC.",
            )
        self.assertIn("first-person present-tense experiment claim", issues)
        self.assertIn("present-tense artifact result claim", issues)

    def test_unexecuted_experiment_tense_guard_accepts_future_protocol(self):
        with patch.dict(
            studio.SECTION_MAP,
            {"e": {"title": "Proposed Experiments"}},
            clear=True,
        ):
            issues = studio.unexecuted_experiment_tense_issues(
                "e",
                "Table~\\ref{tab:main} will compare the methods, and we will report AUROC.",
            )
        self.assertEqual(issues, [])

    def test_no_result_guard_rejects_completed_conclusion_and_threshold(self):
        issues = studio.unexecuted_result_claim_issues(
            "The results support the method under conditions tested at \\(10^{-6}\\)."
        )
        self.assertIn("result-support claim", issues)
        self.assertIn("claimed tested condition", issues)
        self.assertIn("concrete unavailable numerical threshold", issues)

    def test_latex_guard_requires_long_display_equation_to_be_split(self):
        source = (
            r"\[ C(v_1,v_2;h)=\|J_{l_1\to l^*}(h)v_1+J_{l_2\to l^*}(h)v_2"
            r"-(J_{l_2\to l^*}(h)v_2+J_{l_1\to l^*}(h)v_1)\| \]"
        )
        self.assertTrue(
            any("too long" in item for item in studio.latex_prose_issues(source))
        )

    def test_normalizer_removes_standalone_latex_fences(self):
        self.assertEqual(
            studio.normalize_latex_ready_text("```latex\nA paragraph.\n```"),
            "A paragraph.",
        )


if __name__ == "__main__":
    unittest.main()
