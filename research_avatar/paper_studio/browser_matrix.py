#!/usr/bin/env python3
"""Run the non-mutating Paper Studio browser state matrix against a live shell."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.request
from typing import Any, Callable

from playwright.sync_api import Browser, Page, sync_playwright


def load_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def safe_fixture(state: dict[str, Any]) -> dict[str, Any]:
    fixture = copy.deepcopy(state)
    for section in fixture.get("sections", {}).values():
        paragraph = section.get("current_paragraph")
        if paragraph:
            paragraph["candidate"] = None
            paragraph["accepted_text"] = paragraph.get("accepted_text") or "Browser matrix fixture."
    for artifact in fixture.get("figures", []) + fixture.get("tables", []):
        artifact.update(ready=False, status="failed", gate_reason="browser matrix fixture")
        for panel in artifact.get("panels", []):
            panel["status"] = "failed"
    return fixture


class Matrix:
    def __init__(self, browser: Browser, base_url: str, state: dict[str, Any]) -> None:
        self.browser = browser
        self.base_url = base_url.rstrip("/")
        self.state = state
        self.results: dict[str, Any] = {}

    def page(self, state: dict[str, Any] | None = None) -> tuple[Page, list[str], list[str]]:
        page = self.browser.new_page()
        errors: list[str] = []
        posts: list[str] = []
        fixture = state or self.state
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route) -> None:
            if route.request.method != "GET":
                posts.append(route.request.url)
                payload = {"ok": False, "error": "browser matrix blocked mutation"}
                route.fulfill(status=409, content_type="application/json", body=json.dumps(payload))
                return
            route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))

        page.route("**/api/**", api)
        return page, errors, posts

    def empty_shell(self) -> None:
        page, errors, posts = self.page(self.state)
        self.visit(page, "", "!document.querySelector('#empty-project').hidden")
        assert page.locator("#empty-project").is_visible()
        assert page.locator("#model-runtime-config").is_visible()
        assert page.locator("#model").input_value() == "gpt-5-nano"
        controls = (
            "model", "model-apply", "reset-generated", "writing-view",
            "figures-view", "tables-view", "compile", "section-draft-start", "full-draft-start",
            "full-draft-cancel", "runtime-key-open",
        )
        assert all(page.locator("#" + item).is_disabled() for item in controls)
        assert page.locator("#studio-language-select").input_value() in {"zh", "en"}
        assert page.locator("#writing-workspace").is_hidden()
        assert page.locator("#figures-workspace").is_hidden()
        expected_banner = not bool(self.state.get("api_key_configured"))
        assert page.locator("#api-key-setup").is_visible() == expected_banner
        assert not posts and not errors, {"posts": posts, "errors": errors}
        self.results["empty_shell"] = True
        page.close()

    def api_key_setup_banner(self) -> None:
        missing = copy.deepcopy(self.state)
        missing["api_key_configured"] = False
        missing["api_key_setup"] = {
            "setup_command": 'export OPENAI_API_KEY="粘贴你的 API key"',
            "restart_command": "python3 -m research_avatar.paper_studio.server",
        }
        page, errors, posts = self.page(missing)
        self.visit(page, "/?view=writing", "!document.querySelector('#api-key-setup').hidden")
        assert page.locator("#api-key-setup").is_visible()
        assert "export OPENAI_API_KEY" in page.locator("#api-key-setup-command").inner_text()
        assert "python3 -m research_avatar.paper_studio.server" in page.locator("#api-key-restart-command").inner_text()
        assert not posts and not errors
        page.close()

        ready = copy.deepcopy(missing)
        ready["api_key_configured"] = True
        page, errors, posts = self.page(ready)
        self.visit(page, "/?view=writing", "document.querySelector('#api-key-setup').hidden")
        assert page.locator("#api-key-setup").is_hidden()
        assert not posts and not errors
        self.results["api_key_setup_banner"] = True
        page.close()

    def visit(self, page: Page, path: str, ready: str) -> None:
        page.goto(self.base_url + path, wait_until="domcontentloaded")
        page.wait_for_function(ready)

    def all_views(self) -> None:
        fixture = safe_fixture(self.state)
        page, errors, posts = self.page(fixture)
        visited = []
        for section in fixture["sections"]:
            for view in ("writing", "figures", "tables"):
                self.visit(
                    page,
                    f"/?view={view}&section={section}",
                    "document.querySelector('#section-title').textContent !== 'Loading…'",
                )
                visited.append((section, view))
                online_project = bool(fixture.get("online_project"))
                assert page.locator("#model-runtime-config").is_visible() == (
                    not online_project
                )
                if not online_project:
                    assert page.locator("#model-suggestions option").count() >= 2
        assert not posts, posts
        assert not errors, errors
        self.results["all_views"] = len(visited)
        page.close()

    def initial_failure(self) -> None:
        page = self.browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route(
            "**/api/state",
            lambda route: route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"error": "matrix state unavailable"}),
            ),
        )
        self.visit(page, "", "!document.querySelector('#load-error').hidden")
        controls = ("model", "model-apply", "reset-generated", "writing-view", "figures-view", "tables-view", "compile", "section-draft-start", "full-draft-start", "full-draft-cancel", "runtime-key-open")
        assert all(page.locator("#" + item).is_disabled() for item in controls)
        assert page.locator("#writing-workspace").is_hidden()
        assert page.locator("#figures-workspace").is_hidden()
        assert not errors, errors
        self.results["initial_failure"] = True
        page.close()

    def modal_and_responsive_layout(self) -> None:
        if self.state.get("online_project"):
            page, errors, posts = self.page()
            self.visit(page, "/?view=writing", "document.querySelector('#runtime-key-open').hidden")
            assert page.locator("#runtime-key-open").is_hidden()
            assert not posts and not errors
            self.results["modal_and_responsive_layout"] = (
                "online: runtime-key and local mechanism layout hidden"
            )
            page.close()
            return
        mechanism = next((item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"), None)
        if not mechanism:
            self.results["modal_and_responsive_layout"] = "skipped: no mechanism figure"
            return
        section = mechanism["source_sections"][0]
        page, errors, posts = self.page()
        self.visit(
            page,
            f"/?view=figures&section={section}",
            f"document.querySelector('#figure-title').textContent.startsWith('{mechanism['id']}')",
        )
        desktop_columns = page.locator(".mechanism-prompt-workbench").evaluate(
            "node => getComputedStyle(node).gridTemplateColumns"
        )
        assert len(desktop_columns.split()) >= 2, desktop_columns
        page.locator("#runtime-key-open").click()
        page.wait_for_timeout(20)
        assert page.evaluate("document.activeElement.id") == "runtime-key-input"
        page.locator("#runtime-key-close").click()
        assert page.locator("#runtime-key-dialog").is_hidden()
        page.locator("#runtime-key-open").click()
        page.keyboard.press("Escape")
        assert page.locator("#runtime-key-dialog").is_hidden()
        page.locator("#runtime-key-open").click()
        page.locator("#runtime-key-provider").select_option("deepseek")
        page.locator("#runtime-key-input").fill("browser-matrix-placeholder-key")
        page.locator("#runtime-key-submit").click()
        page.wait_for_timeout(100)
        assert any(item.endswith("/api/runtime-key") for item in posts), posts
        posts.clear()
        page.locator("#runtime-key-cancel").click()
        assert page.locator("#runtime-key-dialog").is_hidden()
        page.locator("#reset-generated").click()
        selection = page.locator("#reset-project-id").evaluate(
            "node => [node.selectionStart, node.selectionEnd, node.value.length]"
        )
        assert selection == [0, selection[2], selection[2]], selection
        page.locator("#reset-generated-cancel").click()
        assert not posts and not errors
        page.close()

        page, errors, posts = self.page()
        page.set_viewport_size({"width": 600, "height": 900})
        self.visit(
            page,
            f"/?view=figures&section={section}",
            f"document.querySelector('#figure-title').textContent.startsWith('{mechanism['id']}')",
        )
        mobile_columns = page.locator(".mechanism-prompt-workbench").evaluate(
            "node => getComputedStyle(node).gridTemplateColumns"
        )
        assert len(mobile_columns.split()) == 1, mobile_columns
        assert not posts and not errors
        self.results["modal_and_responsive_layout"] = True
        page.close()

    def mechanism_buttons(self) -> None:
        if self.state.get("online_project"):
            self.results["mechanism_buttons"] = "skipped: online placeholders"
            return
        mechanism = next((item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"), None)
        if not mechanism:
            self.results["mechanism_buttons"] = "skipped"
            return
        fixture = copy.deepcopy(self.state)
        target = next(item for item in fixture["figures"] if item["id"] == mechanism["id"])
        target.update(ready=True, generation_ready=True, status="built", draw_prompt="", prompt_instruction="")
        page, errors, posts = self.page(fixture)
        section = target["source_sections"][0]
        self.visit(
            page,
            f"/?view=figures&section={section}",
            f"document.querySelector('#figure-title').textContent.startsWith('{target['id']}')",
        )
        assert page.locator("#figure-prompt").is_enabled()
        assert page.locator("#figure-draw").is_disabled()
        page.locator("#draw-prompt").fill("PASTED COMPLETE PROMPT")
        assert page.locator("#figure-draw").is_enabled()
        assert page.locator("#figure-prompt").is_disabled()
        page.locator("#prompt-instruction").fill("make simpler")
        assert page.locator("#figure-prompt").is_enabled()
        assert not posts and not errors
        self.results["mechanism_buttons"] = True
        page.close()

    def online_placeholder_only_figures(self) -> None:
        mechanism = next(
            (item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"),
            None,
        )
        if not mechanism:
            self.results["online_placeholder_only_figures"] = "skipped"
            return
        fixture = copy.deepcopy(self.state)
        fixture["online_project"] = True
        target = next(item for item in fixture["figures"] if item["id"] == mechanism["id"])
        target["placeholder_only"] = True
        target["placeholder_message"] = "线上不提供画图表功能，完整功能请使用本地版。"
        page, errors, posts = self.page(fixture)
        section = target["source_sections"][0]
        self.visit(
            page,
            f"/?view=figures&section={section}",
            "!document.querySelector('#online-figure-placeholder').hidden",
        )
        page.wait_for_timeout(150)
        assert page.locator("#online-figure-placeholder").is_visible()
        assert target["placeholder_message"] in page.locator("#online-figure-placeholder").inner_text()
        assert page.locator("#figure-phase").is_hidden()
        assert page.locator("#figure-title").is_hidden()
        assert page.locator("#figure-description").is_hidden()
        assert page.locator("#figure-gate").is_hidden()
        assert page.locator("#mechanism-controls").is_hidden()
        assert page.locator("#figure-caption-box").is_hidden()
        assert page.locator("#figure-placement-row").is_hidden()
        assert page.locator("#figure-preview-image").is_hidden()
        assert page.locator("#figure-preview-pdf").is_hidden()
        assert not posts, posts
        assert not errors, errors
        self.results["online_placeholder_only_figures"] = True
        page.close()

    def direct_full_draft_states(self) -> None:
        # The real controls bind these persisted background-job endpoints.
        assert "/api/full-draft/start" in (self.base_url + "/api/full-draft/start")
        assert "/api/full-draft/cancel" in (self.base_url + "/api/full-draft/cancel")
        assert "/api/llm-provider" in (self.base_url + "/api/llm-provider")
        assert "/api/llm-model" in (self.base_url + "/api/llm-model")
        fixture = safe_fixture(self.state)
        fixture["outline_confirmed"] = True
        fixture["api_key_configured"] = True
        fixture["full_draft"] = {
            "available": True,
            "pending_paragraphs": 2,
            "total_paragraphs": 7,
            "writing_order": list(fixture.get("sections", {})),
            "job": None,
        }
        page, errors, posts = self.page(fixture)
        self.visit(page, "/?view=writing", "!document.querySelector('#writing-workspace').hidden")
        assert page.locator("#full-draft-start").is_enabled()
        assert page.locator("#full-draft-cancel").is_hidden()
        assert "2 / 7" in page.locator("#full-draft-summary").inner_text()
        assert not posts and not errors
        page.close()

        running = copy.deepcopy(fixture)
        running["full_draft"]["job"] = {
            "status": "running",
            "completed": 1,
            "total": 2,
            "progress": 50,
            "progress_message": "正在生成 Method · M2",
        }
        page, errors, posts = self.page(running)
        self.visit(page, "/?view=writing", "!document.querySelector('#full-draft-cancel').hidden")
        assert page.locator("#full-draft-start").is_disabled()
        assert page.locator("#full-draft-cancel").is_visible()
        assert page.locator("#candidate").is_disabled()
        assert page.locator("#full-draft-progress").get_attribute("value") == "50"
        assert not posts and not errors
        self.results["direct_full_draft_states"] = True
        page.close()

    def section_draft_state_is_independent(self) -> None:
        assert "/api/section-draft/start" in (
            self.base_url + "/api/section-draft/start"
        )
        fixture = safe_fixture(self.state)
        fixture["outline_confirmed"] = True
        fixture["api_key_configured"] = True
        fixture["section_draft"] = {"job": None}
        fixture["full_draft"]["job"] = None
        section_id = next(iter(fixture["sections"]))
        section = fixture["sections"][section_id]
        section["paragraph_navigation"][0]["status"] = "pending"
        section["current_paragraph"]["accepted_text"] = ""
        page, errors, posts = self.page(fixture)
        self.visit(
            page,
            f"/?view=writing&section={section_id}",
            "!document.querySelector('#writing-workspace').hidden",
        )
        assert page.locator("#section-draft-start").is_enabled()
        assert page.locator("#full-draft-progress-row").is_hidden()
        page.locator("#section-draft-start").click()
        page.wait_for_timeout(80)
        assert any(url.endswith("/api/section-draft/start") for url in posts), posts
        assert not any(url.endswith("/api/full-draft/start") for url in posts), posts
        assert not errors, errors
        self.results["section_draft_state_is_independent"] = True
        page.close()

    def blocked_mechanism(self) -> None:
        if self.state.get("online_project"):
            self.results["blocked_mechanism"] = "skipped: online placeholders"
            return
        mechanism = next((item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"), None)
        if not mechanism:
            self.results["blocked_mechanism"] = "skipped"
            return
        fixture = copy.deepcopy(self.state)
        target = next(item for item in fixture["figures"] if item["id"] == mechanism["id"])
        target.update(
            ready=True,
            generation_ready=False,
            generation_gate_reason="matrix prerequisite",
            status="pending",
        )
        page, errors, posts = self.page(fixture)
        section = target["source_sections"][0]
        self.visit(
            page,
            f"/?view=figures&section={section}",
            f"document.querySelector('#figure-title').textContent.startsWith('{target['id']}')",
        )
        assert page.locator("#mechanism-generation-prerequisite").is_visible()
        assert all(page.locator("#" + item).is_disabled() for item in ("figure-prompt", "figure-draw", "figure-build"))
        page.wait_for_timeout(120)
        assert not posts and not errors
        self.results["blocked_mechanism"] = True
        page.close()

    def table_buttons(self) -> None:
        table = next(iter(self.state.get("tables", [])), None)
        if not table:
            self.results["table_buttons"] = "skipped"
            return
        fixture = copy.deepcopy(self.state)
        target = next(item for item in fixture["tables"] if item["id"] == table["id"])
        target.update(
            ready=True,
            status="approved",
            latex=target.get("latex") or "\\begin{table}fixture\\end{table}",
        )
        page, errors, posts = self.page(fixture)
        section = target["source_sections"][0]
        self.visit(
            page,
            f"/?view=tables&section={section}",
            f"document.querySelector('#figure-title').textContent.startsWith('{target['id']}')",
        )
        assert page.locator("#table-save").is_disabled()
        assert page.locator("#table-approve").is_disabled()
        assert page.locator("#table-approve").inner_text() == "已插入正文"
        page.locator("#table-latex").fill(page.locator("#table-latex").input_value() + "\n% revision")
        assert page.locator("#table-save").is_enabled()
        assert page.locator("#table-approve").is_enabled()
        assert page.locator("#table-approve").inner_text() == "更新表格 → PDF"
        assert not posts and not errors
        self.results["table_buttons"] = True
        page.close()

    def approved_caption_update(self) -> None:
        figure = next(
            (
                item
                for item in self.state.get("figures", [])
                if not item.get("placeholder_only")
            ),
            None,
        )
        if not figure:
            self.results["approved_caption_update"] = "skipped"
            return
        fixture = copy.deepcopy(self.state)
        target = next(item for item in fixture["figures"] if item["id"] == figure["id"])
        original_caption = target.get("caption") or "Original matrix caption."
        revised_caption = original_caption + " Researcher revision."
        target.update(
            ready=True,
            insertion_ready=True,
            status="approved",
            caption=original_caption,
            downloads={"pdf": "/download/matrix.pdf", "pptx": "/download/matrix.pptx"},
        )
        page = self.browser.new_page()
        errors: list[str] = []
        posts: list[dict[str, Any]] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                return
            body = route.request.post_data_json
            posts.append({"url": route.request.url, "body": body})
            assert route.request.url.endswith("/api/figure/caption"), route.request.url
            assert body == {"figure_id": target["id"], "caption": revised_caption}, body
            target["caption"] = revised_caption
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "message": "Caption 已保存并重新编译正文。",
                        "state": fixture,
                    }
                ),
            )

        page.route("**/api/**", api)
        section = target["source_sections"][0]
        self.visit(
            page,
            f"/?view=figures&section={section}",
            f"document.querySelector('#figure-title').textContent.startsWith('{target['id']}')",
        )
        approve_selector = (
            "#data-approve" if target.get("kind") == "data" else "#figure-approve"
        )
        if target.get("kind") == "data":
            assert page.locator(approve_selector).is_enabled()
            assert page.locator(approve_selector).inner_text() == "重新插入"
        else:
            assert page.locator(approve_selector).is_disabled()
            assert page.locator(approve_selector).inner_text() == "已插入正文"
        page.locator("#figure-caption").fill(revised_caption)
        assert page.locator("#figure-caption-save").is_enabled()
        assert page.locator(approve_selector).is_enabled()
        assert page.locator(approve_selector).inner_text() == "更新 Caption → PDF"
        page.locator(approve_selector).click()
        page.wait_for_timeout(100)
        expected_final_label = (
            "重新插入" if target.get("kind") == "data" else "已插入正文"
        )
        assert page.locator(approve_selector).inner_text() == expected_final_label, {
            "label": page.locator(approve_selector).inner_text(),
            "message": page.locator("#figure-message").inner_text(),
            "posts": posts,
            "errors": errors,
        }
        assert page.locator("#figure-caption").input_value() == revised_caption
        assert page.locator("#figure-caption-save").is_disabled()
        assert len(posts) == 1, posts
        assert not errors, errors
        self.results["approved_caption_update"] = True
        page.close()

    def foreground_double_dispatch(self) -> None:
        fixture = safe_fixture(self.state)

        def run_case(
            name: str,
            selector: str,
            expected_path: str,
            prepare: Callable[[Page], None] | None = None,
            path: str = "/?view=writing&section=abstract",
        ) -> None:
            page = self.browser.new_page()
            errors: list[str] = []
            requests: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def api(route) -> None:
                if route.request.method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                    return
                requests.append(route.request.url.split("?", 1)[0])
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "state": fixture,
                            "candidate": {"citations_added": []},
                            "message": "matrix success",
                        }
                    ),
                )

            page.route("**/api/**", api)
            self.visit(page, path, "document.querySelector('#section-title').textContent !== 'Loading…'")
            if prepare:
                prepare(page)
            page.eval_on_selector(
                selector,
                "node => { node.dispatchEvent(new MouseEvent('click', {bubbles: true})); "
                "node.dispatchEvent(new MouseEvent('click', {bubbles: true})); }",
            )
            # Accept performs a freshness GET before its mutation POST.  Give
            # that two-request transaction enough time to reach the routed
            # endpoint before asserting the double-click guard.
            page.wait_for_timeout(500)
            matching = [item for item in requests if item.endswith(expected_path)]
            assert len(matching) == 1, {"case": name, "requests": requests, "errors": errors}
            assert not errors, {"case": name, "errors": errors}
            page.close()

        run_case("prose_generate", "#generate", "/api/generate")
        run_case(
            "title_generate",
            "#title-generate",
            "/api/title/generate",
            lambda page: page.locator("#title-gpt-prompt").fill("Revise the title."),
        )
        run_case(
            "title_save",
            "#title-save",
            "/api/title/save",
            lambda page: page.locator("#paper-title").fill("A Different Matrix Title"),
        )
        run_case("compile", "#compile", "/api/compile")
        run_case(
            "accept",
            "#accept",
            "/api/accept",
            lambda page: page.locator("#candidate").fill("Manually revised accepted paragraph."),
        )

        navigation_section = next(
            (
                key
                for key, section in fixture["sections"].items()
                if len(section.get("paragraph_navigation", [])) > 1
            ),
            None,
        )
        if navigation_section:
            run_case(
                "paragraph_select",
                ".paragraph-nav button:not(.selected)",
                "/api/select-paragraph",
                path=f"/?view=writing&section={navigation_section}",
            )
        self.results["foreground_double_dispatch"] = 7 if navigation_section else 6

    def title_and_prose_transactions(self) -> None:
        title_fixture = safe_fixture(self.state)
        title_fixture["title_editor"]["current_title"] = "Original Matrix Title"
        title_fixture["title_editor"]["candidate"] = ""
        revised_title = "Revised Matrix Title"
        page = self.browser.new_page()
        errors: list[str] = []
        posts: list[dict[str, Any]] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def title_api(route) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(title_fixture))
                return
            body = route.request.post_data_json
            posts.append({"url": route.request.url, "body": body})
            assert route.request.url.endswith("/api/title/save"), route.request.url
            assert body == {"title": revised_title}, body
            title_fixture["title_editor"]["current_title"] = revised_title
            title_fixture["title_editor"]["candidate"] = ""
            title_fixture["title_editor"]["last_message"] = "标题已写入 LaTeX 并重新编译 PDF。"
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"ok": True, "state": title_fixture}),
            )

        page.route("**/api/**", title_api)
        self.visit(page, "/?view=writing&section=abstract", "!document.querySelector('#title-editor').hidden")
        page.locator("#paper-title").fill(revised_title)
        assert page.locator("#title-save").is_enabled()
        page.locator("#title-save").click()
        page.wait_for_function(
            "() => document.querySelector('#title-save').disabled "
            "&& document.querySelector('#title-save').textContent === '已写入 PDF'",
            timeout=2000,
        )
        assert page.locator("#paper-title").input_value() == revised_title
        assert page.locator("#title-save").is_disabled()
        assert page.locator("#title-save").inner_text() == "已写入 PDF"
        assert len(posts) == 1 and not errors, {"posts": posts, "errors": errors}
        page.close()

        prose_fixture = safe_fixture(self.state)
        paragraph = prose_fixture["sections"]["abstract"]["current_paragraph"]
        paragraph["candidate"] = None
        paragraph["accepted_text"] = "Original accepted matrix paragraph."
        prose_fixture["sections"]["abstract"]["accepted_text"] = paragraph["accepted_text"]
        revised_prose = "Researcher revised accepted matrix paragraph."
        page = self.browser.new_page()
        errors = []
        posts = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def prose_api(route) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(prose_fixture))
                return
            body = route.request.post_data_json
            posts.append({"url": route.request.url, "body": body})
            assert route.request.url.endswith("/api/accept"), route.request.url
            assert body["candidate_text"] == revised_prose, body
            paragraph["accepted_text"] = revised_prose
            prose_fixture["sections"]["abstract"]["accepted_text"] = revised_prose
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"ok": True, "state": prose_fixture}),
            )

        page.route("**/api/**", prose_api)
        self.visit(page, "/?view=writing&section=abstract", "document.querySelector('#candidate').value.length > 0")
        page.locator("#candidate").fill(revised_prose)
        assert page.locator("#accept").is_enabled()
        page.locator("#accept").click()
        page.wait_for_function(
            "() => document.querySelector('#accept').disabled "
            "&& document.querySelector('#accept').textContent === '已写入 LaTeX'",
            timeout=2000,
        )
        assert page.locator("#candidate").input_value() == revised_prose
        assert page.locator("#accept").is_disabled()
        assert page.locator("#accept").inner_text() == "已写入 LaTeX"
        assert len(posts) == 1 and not errors, {"posts": posts, "errors": errors}
        page.close()
        self.results["title_and_prose_transactions"] = True

    def approved_table_update(self) -> None:
        table = next(iter(self.state.get("tables", [])), None)
        if not table:
            self.results["approved_table_update"] = "skipped"
            return
        fixture = copy.deepcopy(self.state)
        target = next(item for item in fixture["tables"] if item["id"] == table["id"])
        original = target.get("latex") or "\\begin{table}Original matrix table.\\end{table}"
        revised = original + "\n% matrix revision"
        target.update(ready=True, status="approved", latex=original)
        page = self.browser.new_page()
        errors: list[str] = []
        posts: list[dict[str, Any]] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                return
            body = route.request.post_data_json
            posts.append({"url": route.request.url, "body": body})
            assert route.request.url.endswith("/api/table/approve"), route.request.url
            assert body == {"table_id": target["id"], "latex": revised}, body
            target["latex"] = revised
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"ok": True, "message": "matrix success", "state": fixture}),
            )

        page.route("**/api/**", api)
        section = target["source_sections"][0]
        self.visit(
            page,
            f"/?view=tables&section={section}",
            f"document.querySelector('#figure-title').textContent.startsWith('{target['id']}')",
        )
        page.locator("#table-latex").fill(revised)
        assert page.locator("#table-approve").inner_text() == "更新表格 → PDF"
        page.locator("#table-approve").click()
        page.wait_for_timeout(100)
        assert page.locator("#table-latex").input_value() == revised
        assert page.locator("#table-save").is_disabled()
        assert page.locator("#table-approve").is_disabled()
        assert page.locator("#table-approve").inner_text() == "已插入正文"
        assert len(posts) == 1 and not errors, {"posts": posts, "errors": errors}
        self.results["approved_table_update"] = True
        page.close()

    def failure_restores_visible_drafts(self) -> None:
        fixture = safe_fixture(self.state)

        def run_case(
            name: str,
            path: str,
            ready: str,
            prepare: Callable[[Page], tuple[str, str]],
            action: str,
            expected_path: str,
            status_selector: str,
        ) -> None:
            page = self.browser.new_page()
            errors: list[str] = []
            posts: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def api(route) -> None:
                if route.request.method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                    return
                posts.append(route.request.url)
                route.fulfill(
                    status=409,
                    content_type="application/json",
                    body=json.dumps({"ok": False, "error": f"matrix {name} failure"}),
                )

            page.route("**/api/**", api)
            self.visit(page, path, ready)
            input_selector, expected_value = prepare(page)
            page.locator(action).click()
            page.wait_for_function(
                "selector => !document.querySelector(selector).disabled",
                arg=action,
                timeout=2000,
            )
            assert len([url for url in posts if url.endswith(expected_path)]) == 1, posts
            assert page.locator(input_selector).input_value() == expected_value
            assert page.locator(action).is_enabled(), {"case": name, "action": action}
            assert f"matrix {name} failure" in page.locator(status_selector).inner_text()
            assert not errors, {"case": name, "errors": errors}
            page.close()

        prose_value = "Browser matrix fixture. researcher draft"
        run_case(
            "prose",
            "/?view=writing&section=abstract",
            "document.querySelector('#section-title').textContent !== 'Loading…'",
            lambda page: (
                page.locator("#candidate").fill(prose_value),
                ("#candidate", prose_value),
            )[1],
            "#generate",
            "/api/generate",
            "#message",
        )

        title_value = "Unsaved Matrix Title"
        run_case(
            "title",
            "/?view=writing&section=abstract",
            "!document.querySelector('#title-editor').hidden",
            lambda page: (
                page.locator("#paper-title").fill(title_value),
                ("#paper-title", title_value),
            )[1],
            "#title-save",
            "/api/title/save",
            "#title-status",
        )

        figure = next(
            (
                item
                for item in fixture.get("figures", [])
                if not item.get("placeholder_only")
            ),
            None,
        )
        if figure:
            figure.update(
                ready=True,
                insertion_ready=True,
                status="approved",
                downloads={"pdf": "/download/matrix.pdf", "pptx": "/download/matrix.pptx"},
            )
            caption_value = (figure.get("caption") or "Matrix caption.") + " unsaved"
            run_case(
                "caption",
                f"/?view=figures&section={figure['source_sections'][0]}",
                f"document.querySelector('#figure-title').textContent.startsWith('{figure['id']}')",
                lambda page: (
                    page.locator("#figure-caption").fill(caption_value),
                    ("#figure-caption", caption_value),
                )[1],
                "#figure-caption-save",
                "/api/figure/caption",
                "#figure-caption-status",
            )

        table = next(iter(fixture.get("tables", [])), None)
        if table:
            table.update(
                ready=True,
                status="approved",
                latex=table.get("latex") or "\\begin{table}matrix\\end{table}",
            )
            latex_value = table["latex"] + "\n% unsaved"
            run_case(
                "table",
                f"/?view=tables&section={table['source_sections'][0]}",
                f"document.querySelector('#figure-title').textContent.startsWith('{table['id']}')",
                lambda page: (
                    page.locator("#table-latex").fill(latex_value),
                    ("#table-latex", latex_value),
                )[1],
                "#table-save",
                "/api/table/save",
                "#figure-message",
            )
        self.results["failure_restores_visible_drafts"] = 2 + int(bool(figure)) + int(bool(table))

    def generated_reset_dialog(self) -> None:
        fixture = safe_fixture(self.state)
        project_id = fixture["project"]["id"]
        page = self.browser.new_page()
        errors: list[str] = []
        posts: list[dict[str, Any]] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                return
            body = route.request.post_data_json
            posts.append({"url": route.request.url, "body": body})
            assert route.request.url.endswith("/api/reset-generated-paper"), route.request.url
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"ok": True, "message": "matrix reset", "state": fixture}),
            )

        page.route("**/api/**", api)
        self.visit(page, "/?view=writing&section=abstract", "document.querySelector('#section-title').textContent !== 'Loading…'")
        page.evaluate(
            "([projectId]) => {"
            " localStorage.setItem('paperstudio.caption-drafts.' + projectId, '{\"F1\":\"draft\"}');"
            " localStorage.setItem('paperstudio.figure-editor-drafts.' + projectId, '{\"F1\":{\"draw_prompt\":\"draft\"}}');"
            " localStorage.setItem('paperstudio.prose-drafts.' + projectId, '{\"abstract:A1\":{\"value\":\"draft\",\"baseline\":\"\"}}');"
            " localStorage.setItem('paperstudio.title-drafts.' + projectId, '{\"title\":\"draft\"}');"
            "}",
            [project_id],
        )
        page.locator("#reset-generated").click()
        page.locator("#reset-generated-close").click()
        assert not page.locator("#reset-generated-dialog").evaluate("node => node.open")
        page.locator("#reset-generated").click()
        page.locator("#reset-project-confirm").fill("wrong-id")
        page.locator("#reset-generated-confirm").click()
        assert not posts
        assert "项目 ID 不匹配" in page.locator("#reset-project-copy-status").inner_text()
        selection = page.locator("#reset-project-confirm").evaluate(
            "node => [node.selectionStart, node.selectionEnd, node.value.length]"
        )
        assert selection == [0, selection[2], selection[2]], selection

        page.evaluate(
            "() => {"
            " Object.defineProperty(navigator, 'clipboard', {value: {writeText: async () => {throw new Error('blocked')}}, configurable: true});"
            " document.execCommand = () => false;"
            "}"
        )
        page.locator("#reset-project-copy").click()
        assert "自动复制失败" in page.locator("#reset-project-copy-status").inner_text()
        selection = page.locator("#reset-project-id").evaluate(
            "node => [node.selectionStart, node.selectionEnd, node.value.length]"
        )
        assert selection == [0, selection[2], selection[2]], selection

        page.locator("#reset-project-confirm").fill(project_id)
        page.eval_on_selector(
            "#reset-project-confirm",
            "node => { node.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); "
            "document.querySelector('#reset-generated-confirm').dispatchEvent(new MouseEvent('click', {bubbles: true})); }",
        )
        page.wait_for_timeout(100)
        assert len(posts) == 1, posts
        assert posts[0]["body"]["project_id"] == project_id
        remaining = page.evaluate(
            "([projectId]) => ["
            " 'paperstudio.caption-drafts.', 'paperstudio.figure-editor-drafts.',"
            " 'paperstudio.prose-drafts.', 'paperstudio.title-drafts.'"
            "].filter(prefix => localStorage.getItem(prefix + projectId) !== null)",
            [project_id],
        )
        assert remaining == [], remaining
        assert not errors, errors
        self.results["generated_reset_dialog"] = True
        page.close()

    def artifact_double_dispatch(self) -> None:
        mechanism = next((item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"), None)
        if self.state.get("online_project"):
            mechanism = None
        multi_data = next((item for item in self.state.get("figures", []) if item.get("kind") == "data" and len(item.get("panels", [])) > 1), None)
        single_data = next((item for item in self.state.get("figures", []) if item.get("kind") == "data" and len(item.get("panels", [])) == 1), None)
        table = next(iter(self.state.get("tables", [])), None)
        completed: list[str] = []

        def base_fixture() -> dict[str, Any]:
            fixture = copy.deepcopy(self.state)
            for artifact in fixture.get("figures", []) + fixture.get("tables", []):
                artifact.update(ready=False, status="failed")
                for panel in artifact.get("panels", []):
                    panel["status"] = "failed"
            return fixture

        def run_case(
            name: str,
            artifact_id: str,
            collection: str,
            view: str,
            expected_path: str,
            configure: Callable[[dict[str, Any]], None],
            prepare: Callable[[Page], None],
            selector: str,
            event: str = "click",
        ) -> None:
            fixture = base_fixture()
            target = next(item for item in fixture[collection] if item["id"] == artifact_id)
            configure(target)
            page = self.browser.new_page()
            errors: list[str] = []
            posts: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def api(route) -> None:
                if route.request.method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                    return
                posts.append(route.request.url)
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "state": fixture,
                            "caption": "Matrix generated caption.",
                            "message": "matrix success",
                        }
                    ),
                )

            page.route("**/api/**", api)
            section = target["source_sections"][0]
            self.visit(page, f"/?view={view}&section={section}", "document.querySelector('#section-title').textContent !== 'Loading…'")
            card = page.locator(".figure-card", has_text=artifact_id)
            if card.count() and "selected" not in (card.get_attribute("class") or ""):
                card.click()
            prepare(page)
            page.eval_on_selector(
                selector,
                f"node => {{ node.dispatchEvent(new Event('{event}', {{bubbles: true}})); "
                f"node.dispatchEvent(new Event('{event}', {{bubbles: true}})); }}",
            )
            page.wait_for_timeout(100)
            matching = [url for url in posts if url.endswith(expected_path)]
            assert len(matching) == 1, {"case": name, "posts": posts, "errors": errors}
            assert not errors, {"case": name, "errors": errors}
            completed.append(name)
            page.close()

        if mechanism:
            def mechanism_ready(target: dict[str, Any]) -> None:
                target.update(
                    ready=True,
                    generation_ready=True,
                    insertion_ready=True,
                    status="built",
                    draw_prompt="Existing matrix prompt",
                    prompt_instruction="",
                    preview_url="/paper.pdf",
                    paper_preview_url="/paper.pdf",
                    gpt_preview_url="/static/matrix.png",
                    downloads={"pdf": "/download/matrix.pdf", "pptx": "/download/matrix.pptx"},
                    placement_options=[
                        {"id": "P1", "accepted": True},
                        {"id": "P2", "accepted": True},
                    ],
                    placement_after="P1",
                )

            run_case("mechanism_prompt", mechanism["id"], "figures", "figures", "/api/figure/prompt", mechanism_ready, lambda page: page.locator("#prompt-instruction").fill("Simplify it."), "#figure-prompt")
            run_case("mechanism_draw", mechanism["id"], "figures", "figures", "/api/figure/draw", mechanism_ready, lambda page: None, "#figure-draw")
            run_case("mechanism_build", mechanism["id"], "figures", "figures", "/api/figure/build", mechanism_ready, lambda page: None, "#figure-build")
            run_case("mechanism_approve", mechanism["id"], "figures", "figures", "/api/figure/approve", mechanism_ready, lambda page: None, "#figure-approve")
            run_case("caption_generate", mechanism["id"], "figures", "figures", "/api/figure/caption/generate", mechanism_ready, lambda page: page.locator("#figure-caption-prompt").fill("Shorten."), "#figure-caption-generate")
            run_case("caption_save", mechanism["id"], "figures", "figures", "/api/figure/caption", mechanism_ready, lambda page: page.locator("#figure-caption").fill((mechanism.get("caption") or "Matrix caption") + " revised"), "#figure-caption-save")

            def image_running(target: dict[str, Any]) -> None:
                mechanism_ready(target)
                target.update(status="image_generating", progress=30, progress_message="drawing")

            run_case("mechanism_cancel", mechanism["id"], "figures", "figures", "/api/figure/cancel", image_running, lambda page: None, "#figure-cancel")
            run_case(
                "figure_placement",
                mechanism["id"], "figures", "figures", "/api/figure/placement", mechanism_ready,
                lambda page: page.locator("#figure-placement").evaluate("node => { node.value = 'P2'; }"),
                "#figure-placement", "change",
            )
            run_case(
                "figure_layout",
                mechanism["id"], "figures", "figures", "/api/figure/placement", mechanism_ready,
                lambda page: page.locator("#figure-layout-mode").evaluate("node => { node.value = 'two-column'; }"),
                "#figure-layout-mode", "change",
            )

        if multi_data:
            def multi_ready(target: dict[str, Any]) -> None:
                target.update(
                    ready=True,
                    insertion_ready=True,
                    status="built",
                    composition_ready=True,
                    preview_url="/paper.pdf",
                    preview_type="pdf",
                    downloads={"pdf": "/download/matrix.pdf", "pptx": "/download/matrix.pptx"},
                )
                for panel in target.get("panels", []):
                    panel.update(status="built", preview_url="/paper.pdf", preview_type="pdf")

            run_case("data_panel_generate", multi_data["id"], "figures", "figures", "/api/figure/panel/generate", multi_ready, lambda page: None, ".data-panel-generate")
            run_case("data_compose", multi_data["id"], "figures", "figures", "/api/figure/compose", multi_ready, lambda page: page.locator("#data-layout-prompt").fill("Place panels horizontally."), "#data-compose")
            run_case(
                "data_approve", multi_data["id"], "figures", "figures", "/api/figure/approve", multi_ready,
                lambda page: page.wait_for_function("!document.querySelector('#data-approve-after-placement').hidden"),
                "#data-approve",
            )

        if single_data:
            def single_ready(target: dict[str, Any]) -> None:
                target.update(ready=True, status="built", composition_ready=False)
                target["panels"][0].update(status="built", preview_url="/paper.pdf", preview_type="pdf")

            run_case("single_data_generate", single_data["id"], "figures", "figures", "/api/figure/panel/generate", single_ready, lambda page: page.locator("#single-data-prompt").fill("Move the legend."), "#single-data-generate")

        if table:
            def table_ready(target: dict[str, Any]) -> None:
                target.update(
                    ready=True,
                    status="built",
                    latex=target.get("latex") or "\\begin{table}matrix\\end{table}",
                    placement_options=[
                        {"id": "P1", "accepted": True},
                        {"id": "P2", "accepted": True},
                    ],
                    placement_after="P1",
                )

            run_case(
                "table_generate", table["id"], "tables", "tables", "/api/table/generate", table_ready,
                lambda page: (
                    page.locator(".table-advanced").evaluate("node => { node.open = true; }"),
                    page.locator("#table-prompt").fill("Columns: Method | Score"),
                ),
                "#table-generate",
            )
            if not self.state.get("online_project"):
                run_case("table_agent_edit", table["id"], "tables", "tables", "/api/table/agent-edit", table_ready, lambda page: page.locator("#table-agent-prompt").fill("Reformat."), "#table-agent-edit")
            run_case("table_save", table["id"], "tables", "tables", "/api/table/save", table_ready, lambda page: page.locator("#table-latex").fill((table.get("latex") or "matrix") + " revised"), "#table-save")
            run_case("table_approve", table["id"], "tables", "tables", "/api/table/approve", table_ready, lambda page: None, "#table-approve")
            run_case(
                "table_placement", table["id"], "tables", "tables", "/api/table/placement", table_ready,
                lambda page: page.locator("#figure-placement").evaluate("node => { node.value = 'P2'; }"),
                "#figure-placement", "change",
            )

        self.results["artifact_double_dispatch"] = completed

    def automatic_generation_sequence(self) -> None:
        mechanism = next((item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"), None)
        if self.state.get("online_project"):
            mechanism = None
        multi_data = next((item for item in self.state.get("figures", []) if item.get("kind") == "data" and len(item.get("panels", [])) > 1), None)
        single_data = next((item for item in self.state.get("figures", []) if item.get("kind") == "data" and len(item.get("panels", [])) == 1), None)
        results: dict[str, Any] = {}

        def isolated_fixture() -> dict[str, Any]:
            fixture = copy.deepcopy(self.state)
            for artifact in fixture.get("figures", []) + fixture.get("tables", []):
                artifact.update(ready=False, status="failed")
                for panel in artifact.get("panels", []):
                    panel.update(status="failed", preview_url="")
            return fixture

        if mechanism:
            fixture = isolated_fixture()
            target = next(item for item in fixture["figures"] if item["id"] == mechanism["id"])
            target.update(ready=True, generation_ready=True, status="pending", draw_prompt="")
            page = self.browser.new_page()
            posts: list[str] = []
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def api(route) -> None:
                if route.request.method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                    return
                posts.append(route.request.url)
                target.update(status="prompt_generating", progress=10)
                route.fulfill(status=202, content_type="application/json", body=json.dumps({"ok": True, "state": fixture}))

            page.route("**/api/**", api)
            self.visit(page, f"/?view=figures&section={target['source_sections'][0]}", "document.querySelector('#section-title').textContent !== 'Loading…'")
            card = page.locator(".figure-card", has_text=target["id"])
            if card.count() and "selected" not in (card.get_attribute("class") or ""):
                card.click()
            page.wait_for_timeout(180)
            assert len([url for url in posts if url.endswith("/api/figure/prompt")]) == 1, posts
            assert not errors, errors
            results["mechanism_prompt"] = 1
            page.close()

        for source, label, blocked in (
            (multi_data, "multi_data", False),
            (single_data, "single_data", False),
            (multi_data, "blocked_data", True),
        ):
            if not source:
                continue
            fixture = isolated_fixture()
            target = next(item for item in fixture["figures"] if item["id"] == source["id"])
            target.update(
                ready=True,
                generation_ready=not blocked,
                generation_gate_reason="matrix blocked" if blocked else "",
                status="pending",
                composition_ready=False,
                preview_url="",
            )
            for panel in target["panels"]:
                panel.update(status="pending", preview_url="")
            page = self.browser.new_page()
            posts: list[dict[str, Any]] = []
            errors: list[str] = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

            def panel_api(
                route, _request=None, *, fixture=fixture, posts=posts, target=target
            ) -> None:
                if route.request.method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                    return
                body = route.request.post_data_json
                posts.append({"url": route.request.url, "body": body})
                assert route.request.url.endswith("/api/figure/panel/generate"), route.request.url
                panel = next(item for item in target["panels"] if item["id"] == body["panel_id"])
                panel.update(status="built", preview_url="/paper.pdf", preview_type="pdf")
                route.fulfill(status=202, content_type="application/json", body=json.dumps({"ok": True, "state": fixture}))

            page.route("**/api/**", panel_api)
            self.visit(page, f"/?view=figures&section={target['source_sections'][0]}", "document.querySelector('#section-title').textContent !== 'Loading…'")
            card = page.locator(".figure-card", has_text=target["id"])
            if card.count() and "selected" not in (card.get_attribute("class") or ""):
                card.click()
            page.wait_for_timeout(350)
            panel_posts = [item for item in posts if item["url"].endswith("/api/figure/panel/generate")]
            if blocked:
                assert panel_posts == [], panel_posts
                results[label] = 0
            else:
                expected = [panel["id"] for panel in target["panels"]]
                observed = [item["body"]["panel_id"] for item in panel_posts]
                assert observed == expected, {"expected": expected, "observed": observed, "posts": posts}
                assert not any(item["url"].endswith("/api/figure/compose") for item in posts), posts
                results[label] = observed
            assert not errors, errors
            page.close()

        table = next(iter(self.state.get("tables", [])), None)
        if table:
            fixture = isolated_fixture()
            target = next(item for item in fixture["tables"] if item["id"] == table["id"])
            target.update(ready=True, status="pending", latex="")
            page = self.browser.new_page()
            posts: list[str] = []
            errors: list[str] = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

            def table_api(route, _request=None, *, fixture=fixture, posts=posts, target=target) -> None:
                if route.request.method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                    return
                posts.append(route.request.url)
                target.update(status="built", latex="\\begin{table}fixture\\end{table}")
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "state": fixture}))

            page.route("**/api/**", table_api)
            self.visit(page, f"/?view=tables&section={target['source_sections'][0]}", "document.querySelector('#section-title').textContent !== 'Loading…'")
            card = page.locator(".figure-card", has_text=target["id"])
            if card.count() and "selected" not in (card.get_attribute("class") or ""):
                card.click()
            page.wait_for_timeout(180)
            assert len([url for url in posts if url.endswith("/api/table/generate")]) == 1, posts
            assert not errors, errors
            results["table_generate"] = 1
            page.close()
        self.results["automatic_generation_sequence"] = results

    def table_generate_survives_a_busy_lock_race(self) -> None:
        # Reported directly: navigating into one pending table (auto
        # -generate fires) then immediately clicking a second pending table
        # left the second stuck "pending" forever. Every figure/table
        # action shares one JS-side busy lock; the second table's
        # scheduled auto-generate call landed while the first's request was
        # still in flight, silently no-op'd against that lock, but had
        # already been marked "attempted" -- so it could never retry.
        tables = [item for item in self.state.get("tables", []) if item.get("kind") == "table"]
        if len(tables) < 2:
            self.results["table_generate_survives_a_busy_lock_race"] = "skipped: needs 2+ tables"
            return
        fixture = copy.deepcopy(self.state)
        for artifact in fixture.get("figures", []) + fixture.get("tables", []):
            artifact.update(ready=False, status="failed")
        first, second = tables[0]["id"], tables[1]["id"]
        for table_id in (first, second):
            target = next(item for item in fixture["tables"] if item["id"] == table_id)
            target.update(ready=True, status="pending", latex="")
        page = self.browser.new_page()
        posts: list[str] = []
        errors: list[str] = []
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

        def api(route, _request=None, *, fixture=fixture, posts=posts) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                return
            body = route.request.post_data_json
            table_id = body.get("table_id")
            posts.append(table_id)
            if table_id == first:
                # Hold the first table's response open long enough for the
                # second table's own scheduled auto-generate to fire while
                # this one is still in flight.
                page.wait_for_timeout(400)
            target = next(item for item in fixture["tables"] if item["id"] == table_id)
            target.update(status="built", latex="\\begin{table}fixture\\end{table}")
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "state": fixture}))

        page.route("**/api/**", api)
        section = next(item for item in fixture["tables"] if item["id"] == first)["source_sections"][0]
        self.visit(page, f"/?view=tables&section={section}", "document.querySelector('#section-title').textContent !== 'Loading…'")
        page.wait_for_timeout(80)
        second_card = page.locator(".figure-card", has_text=second)
        if second_card.count():
            second_card.click()
        page.wait_for_timeout(2000)
        assert posts.count(first) == 1, posts
        assert posts.count(second) == 1, posts
        assert not errors, errors
        final_first = next(item for item in fixture["tables"] if item["id"] == first)
        final_second = next(item for item in fixture["tables"] if item["id"] == second)
        assert final_first["status"] == "built", final_first
        assert final_second["status"] == "built", final_second
        self.results["table_generate_survives_a_busy_lock_race"] = True
        page.close()

    def preview_validation_and_toggle(self) -> None:
        data = next((item for item in self.state.get("figures", []) if item.get("kind") == "data" and len(item.get("panels", [])) > 1), None)
        mechanism = next((item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"), None)
        if self.state.get("online_project"):
            mechanism = None
        results: dict[str, Any] = {}

        if data:
            for label, preview_url, should_unlock in (
                ("valid_pdf", "/paper.pdf", True),
                ("missing_pdf", "/missing-matrix.pdf", False),
            ):
                fixture = copy.deepcopy(self.state)
                for artifact in fixture.get("figures", []) + fixture.get("tables", []):
                    artifact.update(ready=False, status="failed")
                target = next(item for item in fixture["figures"] if item["id"] == data["id"])
                target.update(
                    ready=True,
                    insertion_ready=True,
                    status="built",
                    composition_ready=True,
                    preview_url=preview_url,
                    preview_type="pdf",
                    downloads={"pdf": preview_url, "pptx": "/download/matrix.pptx"},
                )
                for panel in target.get("panels", []):
                    panel.update(status="built", preview_url="/paper.pdf", preview_type="pdf")
                page, errors, posts = self.page(fixture)
                self.visit(page, f"/?view=figures&section={target['source_sections'][0]}", "document.querySelector('#section-title').textContent !== 'Loading…'")
                card = page.locator(".figure-card", has_text=target["id"])
                if card.count() and "selected" not in (card.get_attribute("class") or ""):
                    card.click()
                page.wait_for_timeout(500)
                hidden = page.locator("#data-approve-after-placement").is_hidden()
                disabled = page.locator("#data-approve").is_disabled()
                assert hidden is (not should_unlock), {"case": label, "hidden": hidden}
                assert disabled is (not should_unlock), {"case": label, "disabled": disabled}
                page.evaluate("window.__matrixPdfFrame = document.querySelector('#figure-preview-pdf'); renderFigures();")
                assert page.evaluate("window.__matrixPdfFrame === document.querySelector('#figure-preview-pdf')")
                assert not posts and not errors, {"case": label, "posts": posts, "errors": errors}
                results[label] = should_unlock
                page.close()

        if mechanism:
            fixture = copy.deepcopy(self.state)
            target = next(item for item in fixture["figures"] if item["id"] == mechanism["id"])
            target.update(
                ready=True,
                status="built",
                gpt_preview_url="/static/matrix-reference.png",
                paper_preview_url="/paper.pdf",
                preview_url="/paper.pdf",
                preview_type="pdf",
                # Pin explicitly rather than inherit whatever the live figure
                # happens to have: a real project with gpt_preview_no_text
                # already true made this fixture silently assume the wrong
                # toggle-button copy and fail with an unhelpful bare assert.
                gpt_preview_no_text=False,
            )
            page, errors, posts = self.page(fixture)
            self.visit(page, f"/?view=figures&section={target['source_sections'][0]}", "document.querySelector('#section-title').textContent !== 'Loading…'")
            card = page.locator(".figure-card", has_text=target["id"])
            if card.count() and "selected" not in (card.get_attribute("class") or ""):
                card.click()
            assert page.locator("#mechanism-preview-toggle").inner_text() == "显示 GPT 原图"
            assert page.locator("#figure-preview-pdf").is_visible()
            page.locator("#mechanism-preview-toggle").click()
            assert page.locator("#mechanism-preview-toggle").inner_text() == "显示可编辑 PPT/PDF 完整版"
            assert page.locator("#figure-preview-image").is_visible()
            page.locator("#mechanism-preview-toggle").click()
            assert page.locator("#figure-preview-pdf").is_visible()
            assert not posts and not errors, {"posts": posts, "errors": errors}
            results["mechanism_toggle"] = True
            page.close()
        self.results["preview_validation_and_toggle"] = results

    def navigation_and_draft_isolation(self) -> None:
        fixture = safe_fixture(self.state)
        sections = list(fixture["sections"])
        if len(sections) < 2:
            self.results["navigation_and_draft_isolation"] = "skipped"
            return
        first = "abstract" if "abstract" in fixture["sections"] else sections[0]
        second = next(key for key in sections if key != first)
        page, errors, posts = self.page(fixture)
        self.visit(page, f"/?view=writing&section={first}", "document.querySelector('#section-title').textContent !== 'Loading…'")
        prose_value = "Unsaved navigation prose draft."
        comment_value = "Unsaved navigation comment."
        page.locator("#candidate").fill(prose_value)
        page.locator("#comment").fill(comment_value)
        if first == "abstract":
            page.locator("#paper-title").fill("Unsaved navigation title")
            page.locator("#title-gpt-prompt").fill("Unsaved navigation title prompt")
        page.locator(".section-button", has_text=fixture["sections"][second]["title"]).click()
        assert page.locator("#section-title").inner_text() == fixture["sections"][second]["title"]
        page.locator(".section-button", has_text=fixture["sections"][first]["title"]).click()
        assert page.locator("#candidate").input_value() == prose_value
        assert page.locator("#comment").input_value() == comment_value
        if first == "abstract":
            assert page.locator("#paper-title").input_value() == "Unsaved navigation title"
            assert page.locator("#title-gpt-prompt").input_value() == "Unsaved navigation title prompt"
        assert not posts and not errors, {"posts": posts, "errors": errors}
        page.close()

        mechanisms = [item for item in self.state.get("figures", []) if item.get("kind") == "mechanism"]
        if len(mechanisms) >= 2:
            fixture = copy.deepcopy(self.state)
            shared_section = mechanisms[0]["source_sections"][0]
            for item in fixture["figures"]:
                if item["id"] in {mechanisms[0]["id"], mechanisms[1]["id"]}:
                    item.update(
                        source_sections=[shared_section],
                        ready=True,
                        generation_ready=True,
                        status="built",
                        draw_prompt=f"Canonical {item['id']} prompt",
                    )
            page, errors, posts = self.page(fixture)
            self.visit(page, f"/?view=figures&section={shared_section}", "document.querySelector('#section-title').textContent !== 'Loading…'")
            first_id, second_id = mechanisms[0]["id"], mechanisms[1]["id"]
            page.locator(".figure-card", has_text=first_id).click()
            page.locator("#draw-prompt").fill(f"Draft {first_id} prompt")
            page.locator("#figure-caption").fill(f"Draft {first_id} caption")
            page.locator(".figure-card", has_text=second_id).click()
            assert page.locator("#draw-prompt").input_value() == f"Canonical {second_id} prompt"
            assert page.locator("#figure-caption").input_value() != f"Draft {first_id} caption"
            page.locator("#draw-prompt").fill(f"Draft {second_id} prompt")
            page.locator(".figure-card", has_text=first_id).click()
            assert page.locator("#draw-prompt").input_value() == f"Draft {first_id} prompt"
            assert page.locator("#figure-caption").input_value() == f"Draft {first_id} caption"
            page.locator(".figure-card", has_text=second_id).click()
            assert page.locator("#draw-prompt").input_value() == f"Draft {second_id} prompt"
            assert not posts and not errors, {"posts": posts, "errors": errors}
            page.close()

        fixture = safe_fixture(self.state)
        fixture["pdf"]["exists"] = True
        fixture["pdf"]["page_count"] = max(2, int(fixture["pdf"].get("page_count") or 0))
        page, errors, posts = self.page(fixture)
        self.visit(page, f"/?view=writing&section={first}", "document.querySelectorAll('.pdf-page').length > 0")
        assert page.locator("#pdf-navigation").is_hidden()
        page.locator("#pdf-navigation-toggle").click()
        assert page.locator("#pdf-navigation").is_visible()
        assert page.locator(".pdf-thumbnail").count() == fixture["pdf"]["page_count"]
        page.locator(".pdf-thumbnail").last.click()
        page.locator("#pdf-navigation-toggle").click()
        assert page.locator("#pdf-navigation").is_hidden()
        assert not posts and not errors, {"posts": posts, "errors": errors}
        page.close()
        self.results["navigation_and_draft_isolation"] = True

    def project_draft_isolation(self) -> None:
        fixture_a = safe_fixture(self.state)
        fixture_b = copy.deepcopy(fixture_a)
        project_a = fixture_a["project"]["id"]
        project_b = project_a + "-matrix-other"
        fixture_b["project"]["id"] = project_b
        fixture_b["project_id"] = project_b
        fixture_b["title_editor"]["current_title"] = "Canonical Project B Title"
        current = {"state": fixture_a}
        page = self.browser.new_page()
        errors: list[str] = []
        posts: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(current["state"]))
                return
            posts.append(route.request.url)
            route.fulfill(status=409, content_type="application/json", body=json.dumps({"error": "matrix blocked"}))

        page.route("**/api/**", api)
        self.visit(page, "/?view=writing&section=abstract", "!document.querySelector('#title-editor').hidden")
        page.locator("#paper-title").fill("Unsaved Project A Title")
        page.locator("#candidate").fill("Unsaved Project A Prose")
        current["state"] = fixture_b
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("!document.querySelector('#title-editor').hidden")
        assert page.locator("#paper-title").input_value() == "Canonical Project B Title"
        assert page.locator("#candidate").input_value() != "Unsaved Project A Prose"
        current["state"] = fixture_a
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("!document.querySelector('#title-editor').hidden")
        assert page.locator("#paper-title").input_value() == "Unsaved Project A Title"
        assert page.locator("#candidate").input_value() == "Unsaved Project A Prose"
        assert not posts and not errors, {"posts": posts, "errors": errors}
        self.results["project_draft_isolation"] = True
        page.close()

    def compile_failure_recovers(self) -> None:
        fixture = safe_fixture(self.state)
        page = self.browser.new_page()
        errors: list[str] = []
        posts: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api(route) -> None:
            if route.request.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                return
            posts.append(route.request.url)
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"ok": False, "error": "matrix compile failure"}),
            )

        page.route("**/api/**", api)
        self.visit(page, "/?view=writing&section=abstract", "document.querySelector('#section-title').textContent !== 'Loading…'")
        page.locator("#compile").click()
        page.wait_for_function(
            "document.querySelector('#compile').disabled === false "
            "&& document.querySelector('#message').textContent.includes('matrix compile failure')"
        )
        diagnostic = {
            "posts": posts,
            "enabled": page.locator("#compile").is_enabled(),
            "message": page.locator("#message").inner_text(),
            "errors": errors,
        }
        assert len([url for url in posts if url.endswith("/api/compile")]) == 1, diagnostic
        assert diagnostic["enabled"], diagnostic
        assert "matrix compile failure" in diagnostic["message"], diagnostic
        assert not errors, errors
        self.results["compile_failure_recovers"] = True
        page.close()

    def pdf_reverse_navigation(self) -> None:
        figure = next(iter(self.state.get("figures", [])), None)
        if not figure or not self.state.get("pdf", {}).get("exists"):
            self.results["pdf_reverse_navigation"] = "skipped"
            return

        for label, target in (
            (
                "figure",
                {
                    "view": "figures",
                    "section": figure["source_sections"][0],
                    "artifact_id": figure["id"],
                },
            ),
            (
                "writing",
                {
                    "view": "writing",
                    "section": "abstract" if "abstract" in self.state["sections"] else next(iter(self.state["sections"])),
                    "paragraph_id": (
                        self.state["sections"]["abstract" if "abstract" in self.state["sections"] else next(iter(self.state["sections"]))]["current_paragraph"]["id"]
                    ),
                },
            ),
        ):
            fixture = copy.deepcopy(self.state)
            page = self.browser.new_page()
            errors: list[str] = []
            posts: list[str] = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

            def api(
                route, _request=None, *, fixture=fixture, posts=posts, target=target
            ) -> None:
                if route.request.method == "GET":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture))
                    return
                posts.append(route.request.url)
                if route.request.url.endswith("/api/pdf/locate"):
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "target": target}))
                elif route.request.url.endswith("/api/select-paragraph"):
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "state": fixture}))
                else:
                    raise AssertionError(route.request.url)

            page.route("**/api/**", api)
            self.visit(page, "/?view=writing&section=abstract", "document.querySelectorAll('.pdf-page').length > 0")
            page.locator(".pdf-page").first.dblclick(position={"x": 100, "y": 100})
            for _ in range(20):
                if any(url.endswith("/api/pdf/locate") for url in posts):
                    break
                page.wait_for_timeout(50)
            if label == "figure":
                page.wait_for_function(
                    "artifactId => !document.querySelector('#figures-workspace').hidden "
                    "&& document.querySelector('#figure-title').textContent.startsWith(artifactId)",
                    arg=figure["id"],
                )
                assert page.locator("#figures-workspace").is_visible()
                assert page.locator("#figure-title").inner_text().startswith(figure["id"])
            else:
                page.wait_for_function(
                    "paragraphId => !document.querySelector('#writing-workspace').hidden "
                    "&& document.querySelector('#paragraph-id').textContent === paragraphId",
                    arg=target["paragraph_id"],
                )
                assert page.locator("#writing-workspace").is_visible()
                assert page.locator("#paragraph-id").inner_text() == target["paragraph_id"]
            assert len([url for url in posts if url.endswith("/api/pdf/locate")]) == 1, posts
            assert not errors, {"case": label, "errors": errors}
            page.close()
        self.results["pdf_reverse_navigation"] = True

    def run(self) -> dict[str, Any]:
        if self.state.get("project", {}).get("loaded") is False:
            self.empty_shell()
            return self.results
        checks: tuple[Callable[[], None], ...] = (
            self.api_key_setup_banner,
            self.all_views,
            self.initial_failure,
            self.modal_and_responsive_layout,
            self.mechanism_buttons,
            self.online_placeholder_only_figures,
            self.direct_full_draft_states,
            self.section_draft_state_is_independent,
            self.blocked_mechanism,
            self.table_buttons,
            self.approved_caption_update,
            self.foreground_double_dispatch,
            self.title_and_prose_transactions,
            self.approved_table_update,
            self.failure_restores_visible_drafts,
            self.generated_reset_dialog,
            self.artifact_double_dispatch,
            self.automatic_generation_sequence,
            self.table_generate_survives_a_busy_lock_race,
            self.preview_validation_and_toggle,
            self.navigation_and_draft_isolation,
            self.project_draft_isolation,
            self.pdf_reverse_navigation,
            self.compile_failure_recovers,
        )
        for check in checks:
            try:
                check()
            except Exception as error:
                raise AssertionError(f"{check.__name__}: {error}") from error
        return self.results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8780/paper-studio")
    args = parser.parse_args()
    try:
        state = load_json(args.url.rstrip("/") + "/api/state")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                results = Matrix(browser, args.url, state).run()
            finally:
                browser.close()
        print(json.dumps({"ok": True, "checks": results}, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
