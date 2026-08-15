import json
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import paper_studio.server as studio
from tools.figure_ppt import shape_spec_html
from paper_studio.server import (
    FIGURES,
    Handler,
    StudioError,
    _default_state,
    ask_figure_local_agent,
    call_openai,
    candidate_for_accept,
    citation_keys,
    compose_data_figure,
    create_data_figure_layout_with_local_agent,
    current_paragraph,
    data_figure_layout,
    compile_table_preview,
    default_table_prompt,
    default_data_figure_layout_prompt,
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
    needs_citation_resolution,
    next_unaccepted_index,
    manuscript_title_display,
    manuscript_title_tex,
    manuscript_entrypoint_errors,
    latex_prose_issues,
    normalize_latex_ready_text,
    normalize_mechanism_text_boxes,
    public_state,
    replace_manuscript_title_source,
    require_substantive_table_revision,
    reference_excerpt,
    render_section_source,
    response_source_urls,
    sync_verified_bibliography,
    save_manuscript_title,
    table_numeric_cells,
    table_reference_context,
    validate_data_figure_layout,
    validate_mechanism_shape_spec,
)


class PaperStudioTests(unittest.TestCase):
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
            "project": {"id": "style-jailbreak-test", "name": "Style Jailbreak", "initial_title": "Style Jailbreak", "venue": "ICLR"},
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
        plan = {"reference_file": str(reference), "sections": plan_sections}
        config_file = paper / "paper_studio.json"
        plan_file = paper / "paragraph_plan.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
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
            "PARAGRAPH_PLAN_FILE": studio.PARAGRAPH_PLAN_FILE, "PROJECT_CONFIG_FILE": studio.PROJECT_CONFIG_FILE,
            "FIGURE_DIR": studio.FIGURE_DIR, "FIGURE_SOURCE_DIR": studio.FIGURE_SOURCE_DIR,
            "DATA_FIGURE_AGENT_DIR": studio.DATA_FIGURE_AGENT_DIR, "TABLE_PREVIEW_DIR": studio.TABLE_PREVIEW_DIR,
            "PAPER_PAGE_DIR": studio.PAPER_PAGE_DIR, "METRICS_FILE": studio.METRICS_FILE,
            "PROJECT_ID": studio.PROJECT_ID, "EMPTY_PROJECT_MODE": studio.EMPTY_PROJECT_MODE,
        }
        studio.PAPER = paper
        studio.STATE_DIR = paper / ".paper_studio"
        studio.STATE_FILE = studio.STATE_DIR / "state.json"
        studio.PARAGRAPH_PLAN_FILE = plan_file
        studio.PROJECT_CONFIG_FILE = config_file
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
                studio.post_openai({"model": "gpt-5-nano", "input": "test"})
        self.assertFalse(missing["api_key_configured"])
        self.assertEqual(
            missing["api_key_setup"]["environment_variable"], "OPENAI_API_KEY"
        )
        self.assertIn("export OPENAI_API_KEY", missing["api_key_setup"]["setup_command"])
        self.assertIn("python3 -m paper_studio.server", missing["api_key_setup"]["restart_command"])

        secret = "must-never-reach-public-state"
        with patch.dict(studio.os.environ, {"OPENAI_API_KEY": secret}):
            configured = public_state(_default_state())
        self.assertTrue(configured["api_key_configured"])
        self.assertNotIn(secret, json.dumps(configured, ensure_ascii=False))

        html = (studio.STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="llm-runtime-config" hidden', html)
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
            ["gpt-5", "gpt-5-mini", "gpt-5-nano"],
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
        self.assertEqual(extract_output_text(body), "Draft paragraph.")
        self.assertEqual(visible["api_key_setup"]["environment_variable"], "DEEPSEEK_API_KEY")
        self.assertNotIn(secret, json.dumps(visible, ensure_ascii=False))

    def test_provider_selection_is_limited_to_openai_and_deepseek(self):
        state = _default_state()
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
            studio.ROOT / ".agents" / "skills" / "paperstudio" / "scripts" / "browser_matrix.py"
        ).read_text(encoding="utf-8")
        parser = InteractionParser()
        parser.feed(html)
        expected_controls = {
            "llm-provider", "model", "model-apply", "reset", "reset-generated", "writing-view", "figures-view",
            "tables-view", "compile", "paper-title", "title-gpt-prompt",
            "title-generate", "title-save", "candidate", "comment", "generate",
            "accept", "pdf-navigation-toggle", "table-agent-prompt", "table-agent-edit",
            "figure-cancel", "draw-prompt", "prompt-instruction", "figure-prompt",
            "figure-draw", "figure-build", "single-data-prompt", "single-data-generate",
            "data-layout-prompt", "data-compose", "mechanism-preview-toggle",
            "figure-caption", "figure-caption-prompt", "figure-caption-generate",
            "figure-caption-save", "figure-placement", "figure-layout-mode",
            "data-approve", "figure-approve", "table-prompt", "table-generate",
            "table-latex", "table-save", "table-approve", "reset-generated-close",
            "reset-project-id", "reset-project-copy", "reset-project-confirm",
            "reset-generated-cancel", "reset-generated-confirm", "agent-chat-launcher",
            "agent-chat-close", "figure-agent-chat-input", "figure-agent-chat-send",
            "agent-chat-cancel", "full-draft-start", "full-draft-cancel",
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
                "/api/accept", "/api/agent-chat", "/api/agent-chat/cancel",
                "/api/compile", "/api/figure/approve", "/api/figure/build",
                "/api/full-draft/start", "/api/full-draft/cancel",
                "/api/figure/cancel", "/api/figure/caption",
                "/api/figure/caption/generate", "/api/figure/compose",
                "/api/figure/draw", "/api/figure/panel/generate",
                "/api/figure/placement", "/api/figure/prompt", "/api/generate",
                "/api/llm-provider", "/api/llm-model",
                "/api/pdf/locate", "/api/reset-conversation",
                "/api/reset-generated-paper", "/api/select-paragraph", "/api/state",
                "/api/table/agent-edit", "/api/table/approve", "/api/table/generate",
                "/api/table/placement", "/api/table/save", "/api/title/generate",
                "/api/title/save",
            },
        )
        for api_path in browser_api_paths:
            self.assertIn(api_path, browser_matrix, api_path)

    def test_default_gpt_model_is_nano(self):
        self.assertEqual(studio.DEFAULT_MODEL, "gpt-5-nano")
        self.assertEqual(_default_state()["model"], "gpt-5-nano")

    def test_latex_prose_preflight_flags_raw_specials_and_unicode_math(self):
        issues = latex_prose_issues(
            r"Accuracy is 86.0% for H_s and μ ∈ R, with R&D #1."
        )
        self.assertIn("raw percent sign", issues)
        self.assertIn("raw underscore", issues)
        self.assertIn("raw ampersand", issues)
        self.assertIn("raw hash sign", issues)
        self.assertTrue(any(item.startswith("Unicode math glyphs:") for item in issues))

    def test_latex_prose_preflight_accepts_safe_math_and_reference_keys(self):
        self.assertEqual(
            latex_prose_issues(
                r"Accuracy is 86.0\% for \(H_s \in \mathbb{R}\); see "
                r"Figure~\ref{fig:layer_wise} and \cite{safe_key}."
            ),
            [],
        )

    def test_latex_normalization_canonicalizes_decorated_citation_placeholder(self):
        self.assertEqual(
            normalize_latex_ready_text(
                r"Claim [CITATION NEEDED; \cite{provisional_key}]."
            ),
            "Claim [CITATION NEEDED].",
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
        self.assertIn("python3 -m paper_studio.server --empty", html)

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
            (paper / "outline.txt").write_text("Approved framing", encoding="utf-8")
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

        with patch.object(studio, "post_openai", side_effect=fake_post):
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

    def test_project_workspace_rejects_an_artifact_without_any_paragraph_binding(self):
        plan = studio.paragraph_plan()
        for paragraphs in plan["sections"].values():
            for paragraph in paragraphs:
                paragraph["artifacts"] = [
                    item for item in paragraph.get("artifacts", []) if item != "F1"
                ]
        with TemporaryDirectory() as directory:
            plan_path = Path(directory) / "paragraph_plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with patch.object(studio, "PARAGRAPH_PLAN_FILE", plan_path):
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

    def test_project_workspace_rejects_invalid_reference_lines(self):
        plan = studio.paragraph_plan()
        plan["sections"]["abstract"][0]["reference_lines"] = [33, 6]
        with TemporaryDirectory() as directory:
            plan_path = Path(directory) / "paragraph_plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with patch.object(studio, "PARAGRAPH_PLAN_FILE", plan_path):
                with self.assertRaisesRegex(StudioError, "reference_lines"):
                    studio.validate_project_workspace()

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
        self.assertIn('input.value = ""', source)

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
        self.assertIn('/static/app.js?v=20260815.5', html)
        self.assertIn('id="writing-workspace" class="editor-grid" hidden', html)
        self.assertIn('id="figures-view" disabled', html)
        self.assertIn('id="compile" class="secondary" disabled', html)
        self.assertIn('title="本地 Agent 对话" hidden', html)
        self.assertIn('id="load-error" class="empty-project" hidden', html)
        self.assertIn('id="load-error-message"', html)
        self.assertIn('id="project-eyebrow"', html)
        self.assertIn('id="studio-title"', html)
        self.assertIn('const project = state.project || {}', source)
        self.assertIn('project.name ? `${project.name} · Paper Studio`', source)
        self.assertIn('id="agent-chat-launcher"', html)
        self.assertIn('id="agent-chat-overlay"', html)
        self.assertIn('id="figure-agent-chat-input"', html)
        self.assertIn('id="figure-agent-chat-send"', html)
        self.assertIn('id="agent-chat-cancel"', html)
        self.assertIn('"/api/agent-chat"', source)
        self.assertIn('"/api/agent-chat/cancel"', source)
        self.assertIn('state.agent_chat_history || []', source)
        self.assertIn('state.agent_chat_job || null', source)
        self.assertIn('function ensureAgentChatPolling()', source)
        self.assertIn('execution.textContent = "执行中"', source)
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
        self.assertIn('captionDirty ? "更新 Caption → PDF" : "重新插入"', source)
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
        self.assertIn('(figure.status === "approved" && !captionDirty)', source)
        self.assertIn('const captionDrafts = new Map()', source)
        self.assertIn('function rememberCaptionDraft(figureId, caption)', source)
        self.assertIn('function forgetCaptionDraft(figureId)', source)
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
        self.assertIn('let conversationResetBusy = false', source)
        self.assertIn('let agentChatRequestBusy = false', source)
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
        self.assertIn('/static/app.js?v=20260815.5', html)
        self.assertNotIn("系统确定的段落任务", html)
        self.assertNotIn('id="purpose"', html)
        self.assertNotIn('$("purpose")', source)
        self.assertIn('id="pdf-page-indicator"', html)
        self.assertIn("function updatePdfPageIndicator()", source)
        self.assertIn("pages.onscroll = updatePdfPageIndicator", source)
        self.assertIn('roundLabel.textContent = `第 ${round} 轮`', source)
        self.assertIn('message.className = `figure-agent-chat-message ${user ? "user" : "agent"}`', source)
        self.assertIn("agent-chat-round", source)
        self.assertIn('/static/style.css?v=20260815.5', html)
        self.assertIn('id="reset-generated-dialog"', html)
        self.assertIn('id="reset-project-id" readonly', html)
        self.assertIn('id="reset-project-copy"', html)
        self.assertIn('id="reset-project-confirm"', html)
        self.assertIn('id="reset-generated-confirm"', html)
        self.assertIn('navigator.clipboard.writeText(input.value)', source)
        self.assertIn('document.execCommand("copy")', source)
        self.assertNotIn("const typed = prompt(", source)
        self.assertIn('const latestState = await request("/api/state")', source)
        self.assertIn("candidate_text: visibleCandidateText", source)
        self.assertNotIn("This candidate is stale", source)
        self.assertIn("&& !nextParagraph.accepted_text", source)
        self.assertIn("agent-chat-execution", source)
        self.assertIn("已执行 · ${changedCount} 个文件", source)
        self.assertIn("等待确认", source)
        self.assertIn("已处理 · 无文件变更", source)
        self.assertIn('id="pdf-viewer"', html)
        self.assertIn('id="pdf-pages"', html)
        self.assertNotIn('id="pdf"', html)
        self.assertIn('page.ondblclick = (event) => locatePdfEditTarget(event, page)', source)
        self.assertIn('"/api/pdf/locate"', source)
        self.assertIn('/paper-page/${pageNumber}.svg', source)
        self.assertIn('function capturePdfPosition(pages)', source)
        self.assertIn('function restorePdfPosition(pages, position)', source)
        self.assertIn('const previousPosition = capturePdfPosition(pages)', source)
        self.assertIn('restorePdfPosition(pages, previousPosition)', source)
        self.assertIn('id="pdf-navigation-toggle"', html)
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

    def test_custom_figure_caption_is_public_and_used_in_latex(self):
        state = _default_state()
        state["figures"]["F6"]["caption"] = "Researcher-edited caption."
        public = next(item for item in figure_public_state(state) if item["id"] == "F6")
        self.assertEqual(public["caption"], "Researcher-edited caption.")
        self.assertIn(
            r"\caption{Researcher-edited caption.}",
            figure_latex("F6", state["figures"]["F6"]),
        )

    def test_completed_section_keeps_last_paragraph_and_reference_visible(self):
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
        self.assertTrue(paragraph["reference_text"].startswith("Conclusion and Future Work"))
        self.assertNotIn("Comparison with attacker-model", paragraph["reference_text"])
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
            return {"output_text": "Layer-wise probe trends for direct and stylized inputs."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            caption = studio.generate_figure_caption(
                "F6",
                state,
                FIGURES["F6"]["caption"],
                "Shorten it and define the comparison.",
            )

        self.assertTrue(caption.startswith("[SYNTHETIC]"))
        self.assertIn("Shorten it and define the comparison.", captured["input"])
        self.assertIn('"traceable_results"', captured["input"])
        self.assertIn('"synthetic": true', captured["input"])
        self.assertIn("do not invent measurements", captured["instructions"])

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
                "pdf": root / "combined.pdf",
                "pptx": root / "combined.pptx",
                "preview": root / "combined.png",
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
        self.assertNotRegex(
            source,
            r'id="table-agent-controls"[^>]*\shidden(?:\s|>)',
        )

    def test_citation_keys(self):
        source = r"Prior work \\citep{alpha,beta} and \\citet[Sec. 2]{gamma}."
        self.assertEqual(citation_keys(source), {"alpha", "beta", "gamma"})

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
        self.assertTrue(needs_citation_resolution(r"Claim \\cite{definitelyUnknownKey}."))
        self.assertTrue(
            needs_citation_resolution(
                r"Claim \\cite{[REFUSAL_DIRECTION_CITATION]}."
            )
        )

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

    def test_abstract_starts_with_system_planned_paragraph(self):
        section = _default_state()["sections"]["abstract"]
        paragraph = current_paragraph(section)
        self.assertEqual(paragraph["id"], "A1")
        self.assertTrue(paragraph["purpose"])
        self.assertTrue(reference_excerpt(paragraph["reference_lines"]))

    def test_public_state_exposes_reference_but_not_full_plan(self):
        state = public_state(_default_state())
        section = state["sections"]["introduction"]
        self.assertNotIn("paragraphs", section)
        self.assertEqual(section["current_paragraph"]["id"], "I1")
        self.assertTrue(section["current_paragraph"]["reference_text"])
        self.assertIsNone(section["current_paragraph"]["candidate"])
        self.assertEqual(len(section["paragraph_navigation"]), 6)
        self.assertTrue(section["paragraph_navigation"][0]["selected"])

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

    def test_prose_api_receives_reference_and_explicit_heading(self):
        captured = {}

        def fake_post(payload):
            captured.update(payload)
            return {"id": "resp-r1", "output_text": "Body prose."}

        with patch.object(studio, "post_openai", side_effect=fake_post):
            response_id, text, _ = call_openai(
                section="related_work",
                model="gpt-5.6",
                previous_response_id=None,
                purpose="Position prior safety-alignment work.",
                required_heading="Safety alignment and refusal behavior.",
                required_heading_style="textbf",
                reference_paragraph="Reference-paper paragraph with an inline heading.",
                comment="",
                current_text="",
            )

        self.assertEqual(response_id, "resp-r1")
        self.assertIn(
            "<reference_paragraph>Reference-paper paragraph with an inline heading.",
            captured["input"],
        )
        self.assertIn(
            "<required_heading>Safety alignment and refusal behavior.",
            captured["input"],
        )
        self.assertIn(
            r"<required_heading_latex>\textbf{Safety alignment and refusal behavior.}",
            captured["input"],
        )
        self.assertIn("<writing_style>", captured["input"])
        self.assertTrue(
            text.startswith(r"\textbf{Safety alignment and refusal behavior.}")
        )

    def test_changed_bibliography_is_sent_to_an_existing_section_conversation(self):
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
                bibliography_update="@article{new2026paper, title={New paper}}",
            )

        self.assertIn("<bibliography_update>@article{new2026paper", captured["input"])
        self.assertNotIn("<conversation_bootstrap>", captured["input"])
        self.assertNotIn("<working_abstract>", captured["input"])
        self.assertNotIn("<section_evidence>", captured["input"])

    def test_researcher_prompt_is_the_primary_editing_objective(self):
        captured = {}
        comment = "Remove all numbers and use exactly two sentences."

        def fake_post(payload):
            captured.update(payload)
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

        self.assertIn("primary editing objective", captured["instructions"])
        self.assertIn("Do not weaken, reinterpret, or silently omit", captured["instructions"])
        self.assertIn(
            f"<primary_editing_objective>{comment}</primary_editing_objective>",
            captured["input"],
        )
        self.assertGreater(
            captured["input"].rfind(comment),
            captured["input"].rfind("<current_candidate>"),
        )

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

    def test_unresolved_citation_is_narrowed_once_before_candidate_returns(self):
        payloads = []

        def fake_post(payload):
            payloads.append(payload)
            if len(payloads) == 1:
                return {"id": "resp-draft", "output_text": "Broad claim [CITATION NEEDED]."}
            return {"id": "resp-narrow", "output_text": "Narrow supported framing."}

        with (
            patch.object(studio, "post_openai", side_effect=fake_post),
            patch.object(
                studio,
                "resolve_citations",
                return_value=("resp-resolver", "Broad claim [CITATION NEEDED].", []),
            ) as resolver,
        ):
            response_id, text, _ = call_openai(
                section="introduction",
                model="gpt-5.6",
                previous_response_id=None,
                purpose="State only supported context.",
                required_heading=None,
                reference_paragraph="Reference prose.",
                comment="",
                current_text="",
            )

        resolver.assert_called_once()
        self.assertEqual((response_id, text), ("resp-narrow", "Narrow supported framing."))
        self.assertIn("Narrow or remove every unsupported clause", payloads[1]["instructions"])

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

    def test_accept_invokes_citation_research_for_an_old_candidate(self):
        state = _default_state()
        section = state["sections"]["related_work"]
        paragraph = section["paragraphs"][0]
        section["previous_response_id"] = "resp-old"
        paragraph["candidate"] = {
            "id": "candidate-old",
            "text": r"Claim \\cite{[MISSING_PAPER]}.",
            "citations_added": [],
        }
        handler = object.__new__(Handler)
        handler.require_section = lambda body: "related_work"

        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(
                studio,
                "resolve_citations",
                return_value=(
                    "resp-resolved",
                    "Claim [CITATION NEEDED].",
                    [],
                ),
            ) as resolve,
            patch.object(studio, "bibliography_fingerprint", return_value="bib-v2"),
        ):
            with self.assertRaisesRegex(StudioError, "没有找到可验证"):
                handler.handle_accept(
                    {
                        "section": "related_work",
                        "candidate_id": "candidate-old",
                    }
                )

        resolve.assert_called_once()
        save.assert_called_once_with(state)
        self.assertEqual(section["previous_response_id"], "resp-resolved")
        self.assertEqual(section["bibliography_fingerprint"], "bib-v2")
        self.assertIn("[CITATION NEEDED]", paragraph["candidate"]["text"])

    def test_accept_repairs_citations_even_when_section_conversation_is_missing(self):
        state = _default_state()
        section = state["sections"]["introduction"]
        section["current_index"] = 1
        paragraph = section["paragraphs"][1]
        paragraph["candidate"] = {
            "id": "candidate-stranded",
            "text": "Claim [CITATION NEEDED].",
            "citations_added": [],
        }
        handler = object.__new__(Handler)
        handler.require_section = lambda body: "introduction"
        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state"),
            patch.object(
                studio,
                "resolve_citations",
                return_value=("resp-new-chain", "Claim [CITATION NEEDED].", []),
            ) as resolve,
            patch.object(studio, "bibliography_fingerprint", return_value="bib-current"),
        ):
            with self.assertRaisesRegex(StudioError, "没有找到可验证"):
                handler.handle_accept(
                    {"section": "introduction", "candidate_id": "candidate-stranded"}
                )
        self.assertIsNone(resolve.call_args.kwargs["previous_response_id"])
        self.assertEqual(section["previous_response_id"], "resp-new-chain")

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

    def test_reset_persists_selected_model_and_clears_section_context(self):
        state = _default_state()
        section = state["sections"]["method"]
        section["previous_response_id"] = "resp-method"
        section["bibliography_fingerprint"] = "bib-v1"
        handler = object.__new__(Handler)
        handler.require_section = lambda body: "method"
        response = {}
        handler.send_json = lambda payload: response.update(payload)

        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(
                studio,
                "public_state",
                side_effect=lambda current: {"model": current["model"]},
            ),
        ):
            handler.handle_reset({"section": "method", "model": "gpt-5.4-mini"})

        save.assert_called_once_with(state)
        self.assertEqual(state["model"], "gpt-5.4-mini")
        self.assertIsNone(section["previous_response_id"])
        self.assertIsNone(section["bibliography_fingerprint"])
        self.assertEqual(response["state"]["model"], "gpt-5.4-mini")

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
            (paper / "paragraph_plan.json").write_text(
                json.dumps(studio.paragraph_plan()), encoding="utf-8"
            )
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
                    PARAGRAPH_PLAN_FILE=paper / "paragraph_plan.json",
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
        self.assertIn("First.\n\nSecond.", source)
        self.assertEqual(accepted, "First.\n\nSecond.")

    def test_abstract_has_no_section_heading_and_conclusion_keeps_label(self):
        state = _default_state()["sections"]
        state["abstract"]["paragraphs"][0]["accepted_text"] = "Abstract prose."
        abstract_source, _ = render_section_source("abstract", state["abstract"])
        self.assertEqual(abstract_source, "Abstract prose.\n")

        state["conclusion"]["paragraphs"][0]["accepted_text"] = "Conclusion prose."
        conclusion_source, _ = render_section_source("conclusion", state["conclusion"])
        self.assertTrue(conclusion_source.startswith("\\section{Conclusion and Future Work}"))
        self.assertTrue(conclusion_source.rstrip().endswith("\\label{paper:endconclusion}"))

    def test_approved_figure_is_inserted_after_its_bound_paragraph(self):
        state = _default_state()
        section = state["sections"]["introduction"]
        for index in range(5):
            section["paragraphs"][index]["accepted_text"] = f"Paragraph {index + 1}."
        state["figures"]["F1"]["status"] = "approved"

        source, accepted = render_section_source(
            "introduction", section, state["figures"]
        )

        self.assertLess(source.index("Paragraph 4."), source.index(r"\begin{figure}[t]"))
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

        self.assertLess(source.index("Paragraph 2."), source.index(r"\begin{figure}[t]"))
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

    def test_default_table_prompt_is_persisted_in_new_state(self):
        state = _default_state()
        self.assertEqual(
            state["tables"]["T1"]["generation_prompt"],
            default_table_prompt("T1"),
        )
        self.assertEqual(state["tables"]["T1"]["prompt_history"], [])
        self.assertEqual(state["tables"]["T1"]["agent_prompt"], "")
        self.assertEqual(state["tables"]["T1"]["agent_history"], [])

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

    def test_figure_agent_chat_uses_local_codex_and_carries_recent_history(self):
        observed = {}

        def fake_run(command, **kwargs):
            observed["command"] = command
            observed["prompt"] = kwargs["input"]
            observed["env"] = kwargs["env"]
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(
                json.dumps(
                    {
                        "intent": "read_only",
                        "answer": "建议先分别检查 a 和 b，再手动合成。",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return CompletedProcess(command, 0, "", "")

        with (
            patch.object(studio, "shutil_which", return_value="/usr/bin/codex"),
            patch.object(studio, "run_local_agent_process", side_effect=fake_run),
            patch.dict(studio.os.environ, {"OPENAI_API_KEY": "must-not-leak"}),
        ):
            answer = ask_figure_local_agent(
                "F4",
                "下一步怎么办？",
                [{"role": "user", "content": "两张图分开生成吗？"}],
            )

        self.assertIn("手动合成", answer)
        self.assertIn("两张图分开生成吗", observed["prompt"])
        self.assertIn("下一步怎么办", observed["prompt"])
        self.assertIn("workspace-write", observed["command"])
        self.assertIn("--output-schema", observed["command"])
        self.assertNotIn("OPENAI_API_KEY", observed["env"])

    def test_global_agent_chat_executes_explicit_safe_changes(self):
        observed = {}
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paper = root / "paper"
            state_dir = paper / ".paper_studio"
            paper.mkdir()
            plan = paper / "paragraph_plan.json"
            plan.write_text('{"sections": {"related_work": []}}\n', encoding="utf-8")

            def fake_run(command, **kwargs):
                observed["command"] = command
                observed["prompt"] = kwargs["input"]
                plan.write_text(
                    '{"sections": {"related_work": [{"id": "R3"}]}}\n',
                    encoding="utf-8",
                )
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text("已增加 R3 并验证 JSON。", encoding="utf-8")
                return CompletedProcess(command, 0, "", "")

            with (
                patch.object(studio, "ROOT", root),
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "shutil_which", return_value="/usr/bin/codex"),
                patch.object(studio, "run_local_agent_process", side_effect=fake_run),
            ):
                result = studio.ask_studio_local_agent(
                    "增加一个 related work subsection",
                    section="related_work",
                    return_details=True,
                )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["execution"], "executed")
        self.assertEqual(result["changed_files"], ["paper/paragraph_plan.json"])
        self.assertIn("workspace-write", observed["command"])
        self.assertIn("自行判断 intent", observed["prompt"])

    def test_local_agent_semantic_intent_is_parsed_from_codex_output(self):
        self.assertEqual(
            studio.parse_local_agent_answer(
                '{"intent":"execute","answer":"已经照前文处理。"}'
            ),
            ("execute", "已经照前文处理。"),
        )
        self.assertEqual(
            studio.parse_local_agent_answer(
                '{"intent":"read_only","answer":"这是一个问题。"}'
            ),
            ("read_only", "这是一个问题。"),
        )

    def test_global_agent_chat_uses_codex_semantics_without_action_whitelist(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paper = root / "paper"
            state_dir = paper / ".paper_studio"
            paper.mkdir()

            def fake_run(command, **kwargs):
                (paper / "semantic.md").write_text("done\n", encoding="utf-8")
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text(
                    '{"intent":"execute","answer":"已照前文处理。"}',
                    encoding="utf-8",
                )
                return CompletedProcess(command, 0, "", "")

            history = [
                {"role": "assistant", "content": "可以把候选保存到 semantic.md。"}
            ]
            with (
                patch.object(studio, "ROOT", root),
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "shutil_which", return_value="/usr/bin/codex"),
                patch.object(studio, "run_local_agent_process", side_effect=fake_run),
            ):
                result = studio.ask_studio_local_agent(
                    "那就照你刚才说的办", history, return_details=True
                )

        self.assertEqual(result["execution"], "executed")
        self.assertEqual(result["changed_files"], ["paper/semantic.md"])

    def test_agent_chat_snapshot_tracks_binary_paper_artifacts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paper = root / "paper"
            state_dir = paper / ".paper_studio"
            figures = paper / "fig"
            figures.mkdir(parents=True)
            artifact = figures / "overview.pdf"
            with (
                patch.object(studio, "ROOT", root),
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "STATE_DIR", state_dir),
            ):
                before = studio.chat_source_snapshot()
                artifact.write_bytes(b"%PDF-1.4\nfirst\n")
                created = studio.chat_source_snapshot()
                artifact.write_bytes(b"%PDF-1.4\nsecond\n")
                changed = studio.chat_source_snapshot()

        self.assertNotIn("paper/fig/overview.pdf", before)
        self.assertIn("paper/fig/overview.pdf", created)
        self.assertNotEqual(
            created["paper/fig/overview.pdf"], changed["paper/fig/overview.pdf"]
        )

    def test_local_agent_timeout_terminates_process_group(self):
        process = MagicMock()
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["codex"], 1),
            ("", ""),
        ]
        with (
            patch.object(studio.subprocess, "Popen", return_value=process),
            patch.object(studio, "_terminate_process_group") as terminate,
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                studio.run_local_agent_process(
                    ["codex"], input="test", env={}, timeout=1
                )
        terminate.assert_called_once_with(process)

    def test_global_agent_chat_http_request_starts_background_job_immediately(self):
        state = _default_state()
        response = {}
        started = {}

        class FakeThread:
            def __init__(self, **kwargs):
                started.update(kwargs)

            def start(self):
                started["started"] = True

        handler = object.__new__(Handler)
        handler.send_json = lambda payload, status=200: response.update(
            {"payload": payload, "status": status}
        )
        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(studio.threading, "Thread", FakeThread),
            patch.object(studio, "public_state", side_effect=lambda current: current),
        ):
            handler.handle_agent_chat(
                {"message": "再试", "section": "related_work", "view": "writing"}
            )

        self.assertEqual(response["status"], 202)
        self.assertEqual(state["agent_chat_job"]["status"], "running")
        self.assertEqual(state["agent_chat_history"][-1]["content"], "再试")
        self.assertTrue(started["started"])
        self.assertIs(started["target"], studio.agent_chat_worker)
        self.assertTrue(started["daemon"])
        save.assert_called_once_with(state)

    def test_global_agent_chat_worker_appends_completion(self):
        state = _default_state()
        state["agent_chat_history"] = [{"role": "user", "content": "再试"}]
        state["agent_chat_job"] = {"token": "job-1", "status": "running"}
        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(
                studio,
                "ask_studio_local_agent",
                return_value={
                    "answer": "已完成。",
                    "execution": "no_changes",
                    "changed_files": [],
                },
            ),
        ):
            studio.agent_chat_worker(
                "job-1", "再试", [], "related_work", "writing", ""
            )

        self.assertEqual(state["agent_chat_job"]["status"], "completed")
        self.assertEqual(state["agent_chat_history"][-1]["content"], "已完成。")
        self.assertEqual(state["agent_chat_history"][-1]["execution"], "no_changes")
        save.assert_called_once_with(state)

    def test_interrupted_agent_chat_gets_visible_failure_reply_once(self):
        with TemporaryDirectory() as temporary:
            state_file = Path(temporary) / "state.json"
            state = _default_state()
            state["agent_chat_history"] = [
                {
                    "role": "user",
                    "content": "intro不需要每一段都引用图1  一个段落引用就行了",
                }
            ]
            state["agent_chat_job"] = {
                "token": "old-job",
                "status": "running",
                "server_instance": "old-server",
                "message": "intro不需要每一段都引用图1  一个段落引用就行了",
            }
            state_file.write_text(json.dumps(state), encoding="utf-8")
            with (
                patch.object(studio, "STATE_FILE", state_file),
                patch.object(studio, "SERVER_INSTANCE_TOKEN", "new-server"),
            ):
                first = studio.load_state()
                state_file.write_text(json.dumps(first), encoding="utf-8")
                second = studio.load_state()

        self.assertEqual(first["agent_chat_job"]["status"], "failed")
        self.assertTrue(first["agent_chat_job"]["reply_recorded"])
        self.assertEqual(first["agent_chat_history"][-1]["role"], "assistant")
        self.assertEqual(first["agent_chat_history"][-1]["execution"], "failed")
        self.assertIn("请重试", first["agent_chat_history"][-1]["content"])
        self.assertEqual(len(second["agent_chat_history"]), 2)

    def test_local_agent_prompt_family_always_produces_terminal_reply(self):
        prompts = [
            "intro不需要每一段都引用图1，一个段落引用就行了",
            "检查 introduction 是否只引用一次 Figure 1",
            "为什么这里每段都引用图1？",
            "如果已经只引用一次就不要改文件",
        ]
        for index, prompt in enumerate(prompts):
            with self.subTest(prompt=prompt):
                state = _default_state()
                state["agent_chat_history"] = [{"role": "user", "content": prompt}]
                state["agent_chat_job"] = {
                    "token": f"job-{index}",
                    "status": "running",
                }
                execution = "read_only" if "为什么" in prompt else "no_changes"
                with (
                    patch.object(studio, "load_state", return_value=state),
                    patch.object(studio, "save_state") as save,
                    patch.object(
                        studio,
                        "ask_studio_local_agent",
                        return_value={
                            "answer": "已检查并返回明确结果。",
                            "execution": execution,
                            "changed_files": [],
                        },
                    ),
                ):
                    studio.agent_chat_worker(
                        f"job-{index}", prompt, [], "introduction", "writing", ""
                    )
                self.assertEqual(state["agent_chat_job"]["status"], "completed")
                self.assertTrue(state["agent_chat_job"]["reply_recorded"])
                self.assertEqual(state["agent_chat_history"][-1]["role"], "assistant")
                self.assertTrue(state["agent_chat_history"][-1]["content"])
                save.assert_called_once_with(state)

    def test_global_agent_chat_cancel_terminates_process_and_persists_state(self):
        state = _default_state()
        state["agent_chat_history"] = [{"role": "user", "content": "继续处理"}]
        state["agent_chat_job"] = {
            "token": "job-cancel",
            "status": "running",
            "progress_message": "执行中",
        }
        process = MagicMock()
        response = {}
        handler = object.__new__(Handler)
        handler.send_json = lambda payload, status=200: response.update(
            {"payload": payload, "status": status}
        )
        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(studio, "public_state", side_effect=lambda current: current),
            patch.object(studio, "_terminate_process_group") as terminate,
        ):
            with studio.AGENT_CHAT_PROCESS_LOCK:
                studio.RUNNING_AGENT_CHAT_PROCESSES["job-cancel"] = process
            try:
                handler.handle_agent_chat_cancel({})
            finally:
                with studio.AGENT_CHAT_PROCESS_LOCK:
                    studio.RUNNING_AGENT_CHAT_PROCESSES.pop("job-cancel", None)
                    studio.CANCELLED_AGENT_CHAT_JOBS.discard("job-cancel")

        self.assertEqual(state["agent_chat_job"]["status"], "cancelled")
        self.assertEqual(state["agent_chat_history"][-1]["execution"], "cancelled")
        self.assertIn("已停止", state["agent_chat_history"][-1]["content"])
        terminate.assert_called_once_with(process)
        save.assert_called_once_with(state)
        self.assertTrue(response["payload"]["ok"])

    def test_cancelled_agent_chat_worker_discards_late_completion(self):
        state = _default_state()
        state["agent_chat_job"] = {"token": "job-1", "status": "cancelled"}
        with (
            patch.object(studio, "load_state", return_value=state),
            patch.object(studio, "save_state") as save,
            patch.object(
                studio,
                "ask_studio_local_agent",
                return_value={
                    "answer": "迟到结果",
                    "execution": "executed",
                    "changed_files": ["paper/late.md"],
                },
            ),
        ):
            studio.agent_chat_worker(
                "job-1", "继续", [], "related_work", "writing", ""
            )
        save.assert_not_called()

    def test_global_agent_chat_requires_confirmation_for_destructive_changes(self):
        self.assertFalse(studio.chat_confirmation_required("那就照你刚才说的办"))
        self.assertTrue(studio.chat_confirmation_required("删除整个 Related Work"))
        history = [
            {"role": "user", "content": "删除整个 Related Work"},
            {"role": "assistant", "content": "请回复确认执行。"},
        ]
        self.assertFalse(studio.chat_confirmation_required("确认执行", history))

    def test_global_agent_chat_retry_recovers_prior_action_in_writable_prompt(self):
        observed = {}
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paper = root / "paper"
            state_dir = paper / ".paper_studio"
            paper.mkdir()

            def fake_run(command, **kwargs):
                observed["command"] = command
                observed["prompt"] = kwargs["input"]
                (paper / "retry.md").write_text("done\n", encoding="utf-8")
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text(
                    '{"intent":"execute","answer":"已重试并完成。"}',
                    encoding="utf-8",
                )
                return CompletedProcess(command, 0, "", "")

            history = [
                {"role": "user", "content": "related work再加一节"},
                {"role": "assistant", "content": "当前是只读模式。"},
            ]
            with (
                patch.object(studio, "ROOT", root),
                patch.object(studio, "PAPER", paper),
                patch.object(studio, "STATE_DIR", state_dir),
                patch.object(studio, "shutil_which", return_value="/usr/bin/codex"),
                patch.object(studio, "run_local_agent_process", side_effect=fake_run),
            ):
                result = studio.ask_studio_local_agent(
                    "再试", history, return_details=True
                )
        self.assertEqual(result["execution"], "executed")
        self.assertIn("workspace-write", observed["command"])
        self.assertIn("related work再加一节", observed["prompt"])
        self.assertIn("最近对话的语义", observed["prompt"])

    def test_related_work_plan_contains_only_the_two_retained_groups(self):
        groups = studio.paragraph_plan()["sections"]["related_work"]
        self.assertEqual([item["id"] for item in groups], ["R1", "R2"])
        self.assertEqual(
            [item["heading_style"] for item in groups], ["textbf", "textbf"]
        )
        for item in groups:
            self.assertTrue(studio.reference_excerpt(item["reference_lines"]))

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
        self.assertIn("compact ACL-style introduction/motivation schematic", intro)
        self.assertIn("2–3 aligned regions", intro)
        self.assertIn("pure white background", intro)
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
                "pdf": root / "figure.pdf",
                "pptx": root / "figure.pptx",
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

    def test_data_layout_width_controls_paper_float(self):
        wide = figure_latex("F4", {"layout_width": "two-column"})
        narrow = figure_latex("F4", {"layout_width": "single-column"})
        self.assertIn(r"\begin{figure*}[t]", wide)
        self.assertIn(r"\includegraphics[width=\textwidth]", wide)
        self.assertIn(r"\begin{figure}[t]", narrow)
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
        self.assertIn('"显示 PPT/PDF 版"', source)

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
        self.assertIn('style.display = mechanism ? "grid" : "none"', source)
        self.assertIn("grid-template-columns:minmax(0,1.35fr) minmax(240px,.8fr)", style)

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

    def test_public_figure_order_matches_workflow(self):
        figures = figure_public_state(_default_state())
        self.assertEqual(
            [item["id"] for item in figures],
            ["F1", "F3", "F2", "F4", "F5", "F6"],
        )
        self.assertEqual(figures[0]["phase"], 1)
        self.assertEqual(figures[2]["phase"], 2)

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
                    return_value=("resp-figure-1", "Generated BioRender prompt."),
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
            self.assertEqual(finished["draw_prompt"], "Generated BioRender prompt.")
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
            state["figures"]["F1"]["previous_response_id"] = "resp-f1-previous"
            state["figures"]["F3"]["previous_response_id"] = "resp-f3-unrelated"
            captured = {}

            def fake_post(payload):
                captured.update(payload)
                return {
                    "id": "resp-f1-next",
                    "output_text": "A simpler single-column BioRender prompt.",
                }

            with (
                patch.object(studio, "FIGURE_SOURCE_DIR", source_dir),
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
            self.assertEqual(prompt, "A simpler single-column BioRender prompt.")

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
                patch.object(studio.webbrowser, "open") as browser_open,
                patch.dict(studio.os.environ, {studio.API_KEY_ENVIRONMENT_VARIABLE: "secret"}),
                patch("builtins.print"),
            ):
                studio.save_state(state)
                studio.run_direct_full_draft("gpt-5-nano")

            worker.assert_called_once()
            browser_open.assert_not_called()

    def test_project_config_rejects_incomplete_batch_writing_order(self):
        config = json.loads(studio.PROJECT_CONFIG_FILE.read_text(encoding="utf-8"))
        config["batch_writing_order"] = [config["sections"][0]["id"]]
        with TemporaryDirectory(dir=studio.ROOT / "tests") as directory:
            path = Path(directory) / "paper_studio.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "batch_writing_order"):
                studio.load_project_config(path, root=studio.ROOT)


if __name__ == "__main__":
    unittest.main()
