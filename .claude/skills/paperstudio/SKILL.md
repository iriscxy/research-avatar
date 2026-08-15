---
name: paperstudio
description: Internally maintain, debug, or regression-test this repository's fixed Paper Studio web application, including browser state transitions, API transactions, background jobs, PDF/PPTX composition, reset safety, and UI behavior. Use for reproducible bugs or product changes in paper_studio/, not for deciding how a paper should be written; paperwrite owns writing policy and project data.
---

# Paper Studio

At the first Skill action in this Codex project session, run
`python3 -m research_studio.server --ensure-studios` before substantive work.
This idempotent bootstrap starts or reuses both local Studio servers and opens
Research Studio (`http://127.0.0.1:8780`) plus Paper Studio
(`http://127.0.0.1:8765`). Run it once per session, never launch duplicates,
and surface any startup error.

Maintain the local research-paper editor as an evidence-preserving browser workflow. Read [references/web-regressions.md](references/web-regressions.md) before changing `paper_studio/`; it is the product contract accumulated from researcher feedback.

## Authority boundary

Treat this as an internal product-engineering skill, not a paper-writing skill. `/paperwrite` owns narrative order, title/framing decisions, evidence and citation policy, artifact roles, paragraph bindings, and single- versus two-column choices. Paper Studio reads those decisions from `paper/paper_studio.json` and `paper/paragraph_plan.json`, exposes them in the browser, and enforces them transactionally. Never invent or override a writing decision in reusable web code. Keep only the minimal cross-boundary invariant needed to implement or test the UI; link back to project data instead of copying writing guidance here.

Paper Studio is a permanent, paper-independent shell. It must start even when `paper/` or `paper/paper_studio.json` does not exist and show an explicit empty-project state. Start that shell with `python3 -m paper_studio.server --empty`; ordinary startup also falls back to the empty shell when no project config exists. `/paperwrite` populates `paper/` project data and never generates, copies, forks, or edits the web application.

## Workflow

1. Inspect `paper_studio/server.py`, `paper_studio/static/`, `paper/paragraph_plan.json`, the relevant `results/` data, and existing tests before editing.
2. Treat each researcher-visible transition as a state machine. Distinguish pending, running, candidate-ready, composed, and approved states; never infer readiness merely from a file left on disk.
   - Lock every foreground action synchronously before its first asynchronous request. Rapid double-clicks, Enter plus click, or two controls targeting the same artifact must produce at most one in-flight mutation; restore controls after both success and failure. Keep cancellation available only for an already-running cancellable background job.
   - When a ready data figure is first displayed without candidates, automatically generate all pending panels sequentially in configured order. Start only one panel Agent at a time, never auto-retry a failed panel, and keep final multi-panel composition manual.
   - Lay out multi-panel data work from top to bottom as panel `a`, panel `b`, remaining panels, then one grouped composition editor. Remove generic empty-preview placeholder blocks; display real previews only when candidates exist.
   - The manuscript title has its own current → candidate → confirmed transition. Read the current value from `paper/main.tex`; a Title GPT response is only an editable candidate and must never write source automatically.
   - For a mechanism figure, enforce project-configured `generation_requires_paragraphs`: an intro/motivation figure may require only its first citing paragraph, while a model/method figure should require every subsection needed to define the architecture. Show the missing subsection names before the Prompt editor. Independently, render a labelled placeholder with the real Caption as soon as the first citing paragraph is accepted, then replace it with the approved PDF while preserving Caption/label. Never infer the role or requirements from section/title strings in reusable web code.
   - Accept → LaTeX has two separately visible transitions: accepted/compiled, then optional next-paragraph generation. Render the newly compiled PDF immediately after acceptance succeeds; never hold that PDF update behind another GPT request.
   - Generated prose must be pdflatex-safe before it becomes an editable candidate: escape prose `%`, `&`, `#`, and `_`, put mathematics inside LaTeX math delimiters, and replace Unicode math glyphs with LaTeX commands. Correct hazards once in the same GPT conversation, then fail with an actionable preflight error before compilation if any remain. Apply the same preflight to direct edits of accepted prose.
   - Enforce the artifact-reference contract encoded by `paragraph.artifacts`: each listed artifact appears exactly once in that paragraph and configured unlisted artifacts appear zero times. Do not decide which paragraphs should bind an artifact; `/paperwrite` owns that project-data decision. Apply the same validation to GPT output, direct edits, and Accept.
   - Treat `[CITATION NEEDED]` as a reserved workflow token. Canonicalize decorated variants such as `[CITATION NEEDED; ...]` to that exact token before resolution so provisional notes or cite commands cannot leak into manuscript prose.
   - Search for a missing citation at most once during candidate generation. If verified search cannot support every marked clause, narrow it once in the same GPT conversation; if a marker still remains, deterministically drop the whole unsupported sentence. Never repeat the expensive search on Accept and never retain the unsupported claim merely to keep prose length.
   - A GPT Image job has a cancellable running transition. Show `⏸ 停止调用` at the right side of the running progress bar—not in the draw-command button group—and enable it only during image generation. Cancellation must terminate the child process, invalidate the job token, and preserve the current Prompt and previous completed draft.
   - Deduplicate GPT Image calls server-side. Before starting a draw job, compare the submitted Prompt with the exact Prompt archived for the current completed draft. If unchanged, make no API call, create no new iteration, preserve the current draft/approval/artifacts, and return the existing image with an explicit `Prompt 未变化` message. Do not rely only on a disabled browser button.
   - After GPT Image succeeds, automatically ask the local Agent to inspect it and reconstruct its modules, icons, arrows, and labels as native PowerPoint objects, then build the paper-sized PPTX and matching PDF in the same background job. Do not strand the state at `draft` or require a second confirmation. Keep the manual build action only as an explicit retry/rebuild path; insertion remains a separate researcher confirmation.
   - Once both candidates exist, default the mechanism preview to the paper-sized PPT/PDF version and show one explicit toggle that switches the same preview area between `GPT 原图` and `PPT/PDF 版`. Keep this choice browser-only; switching previews must never change the approved image, caption, insertion target, or manuscript source.
   - Treat an approved figure's Caption edit as a new transactional update. While clean, disable the mechanism confirmation action as `已插入正文`; once the Caption textarea differs, relabel it `更新 Caption → PDF`, submit that visible text, rewrite the float, compile, and only then restore the clean inserted state.
   - Preserve every unsaved Caption draft by project ID and artifact ID across preview toggles, figure/section/view switches, polling renders, and browser refresh. Clear only the matching draft after the server confirms a successful Caption save/compile; returning the textarea exactly to the canonical Caption also clears it without a request.
   - Apply that same project-and-artifact-scoped draft lifecycle to every figure/table workbench input: mechanism design Prompt and modification instruction, Caption GPT instruction, each data-panel Agent Prompt, multi-panel composition Prompt, table specification and Agent instruction, and editable Table LaTeX. A preview toggle, poll, artifact/section/view switch, or refresh must not discard researcher text. Reconcile and clear a field when the server returns that exact canonical value, its action succeeds, or the researcher returns exactly to it.
   - Preserve direct prose edits browser-locally by project, section, and paragraph, including accepted prose. Paragraph/section/view switches, polling, and refresh must not discard an unaccepted edit. Retain its original server baseline for stale-write protection, and clear the draft only after successful Generate/Accept or an exact revert.
   - Preserve each unsent prose revision comment by project, section, and paragraph across the same transitions; clear it after successful Generate/Accept or exact revert to blank. Preserve an unsaved model-field edit by project until the explicit model-apply transaction succeeds or the value returns to the persisted model.
   - Preserve unsaved title and Title GPT Prompt edits browser-locally by project across section/view switches and refresh. Keep them as candidates only; clear each field after its successful server transaction or exact revert.
3. Preserve data honesty. Match result gates to the approved experiment-plan schema and actual traceable data. Never invent a missing value to unlock a figure. If only qualitative evidence exists, show an explicitly qualitative candidate or a labelled evidence gap.
4. Implement the smallest general rule, not an artifact-specific patch. Examples: branch on panel count rather than `figure_id == "F6"`; bind prose to `paragraph.artifacts` rather than detecting “F” or “T” in titles.
5. Keep local-Agent and GPT roles explicit:
   - Use the local Codex Agent for reproducible plot authoring, safe layout interpretation, table editing, and the always-available help chat.
   - Use the section GPT conversation for prose, passing every bound artifact's title, purpose, caption, panels, label, and exact required LaTeX reference.
   - Budget LLM inputs explicitly. Bootstrap outline, working abstract, style, bibliography, and section evidence once per provider conversation; later turns send only mutable context while that conversation is available. Re-bootstrap Chat Completions providers after a server restart instead of trusting a stale local conversation ID. Title and mechanism-prompt revisions must not resend the full paper unnecessarily. Resend developer instructions every turn. Estimate text/reasoning tokens, OpenAI citation web searches, GPT Image size/quality, and redraws separately; image redraws usually dominate the bill.
   - Let the local Codex Agent semantically classify each ordinary chat turn from the current message and recent history as `read_only`, `execute`, or `confirmation_required`; never select read versus write mode from a hard-coded action-verb list. Keep a deterministic server-side confirmation gate only for deletion, clearing, broad overwrite, and similarly hard-to-recover operations. Detect success across both editable source files and researcher-visible PNG/PDF/PPTX/SVG artifacts. Run Codex in its own process group and terminate the whole group on timeout so a reported failure cannot continue mutating files in the background.
   - Show a local-Agent stop button only while a chat job is running. Stopping must persist a `cancelled` job and an `已停止` assistant turn, terminate the whole Codex process group, and make the worker ignore every late result.
   - Give every accepted local-Agent chat turn exactly one terminal assistant bubble. On completion, failure, cancellation, timeout, or server-restart recovery, persist a nonempty assistant reply with the corresponding execution badge. Never leave a user bubble unanswered merely because the job state became terminal; mark recovered replies so repeated reloads cannot duplicate them.
6. Preserve editability honestly. Data figures remain vector PDF plus editable PPTX. For GPT-drawn mechanism figures, treat the archived GPT Image as a composition reference and use a local vision-capable Agent to reconstruct every visible module, icon, arrow, and label as an independent native PowerPoint object. Build via `buildshapes`, export the matching paper PDF via `pdfshapes`, and reject any final PPTX containing a `ppt/media/` raster background or too few native objects. Keep the GPT original separately available in the preview toggle. Never launch Microsoft PowerPoint UI automation or require permission dialogs.
   - Honor the placement, canvas, aspect ratio, safe band, and density supplied by project config. Pass those values through prompt generation and rendering without inferring figure role from section names. Reject incomplete project data instead of silently substituting a writing decision.
7. Add or update deterministic unit tests, then run JavaScript syntax checking, Python compilation, the Paper Studio test suite, and a real headless-browser check of the affected DOM/state transition.
8. Restart the local server after Python changes and verify `/api/state` plus the visible webpage. Static-only changes still require a cache-version bump.
9. Treat a successful LaTeX process as insufficient when the entry point omits Studio-managed section files. Before reporting compile success, verify every configured `paper/sections/*.tex` is included by `paper/main.tex`, with the configured abstract input inside `\begin{abstract}...\end{abstract}`.
10. A same-project clean rerun must use the Studio's project-ID-confirmed “清空生成内容” transition. Clear the entire generated namespaces (`paper/fig/`, unprotected contents of `paper/figsrc/`, and `paper/.paper_studio/`) rather than enumerating current filenames, so legacy deliverable stems and iteration directories cannot survive. Preserve configured input files such as an explicitly referenced `shape_spec`, plus the fixed web application, skills, project config, paragraph plan, working abstract/outline, bibliography input, reference text, and result data. Reset section outputs/title, remove every `main.*` build artifact except `main.tex`, recompile an empty PDF, and replace state intentionally rather than letting monotonic stale-save guards restore deleted content.
   - After the server confirms reset, remove every browser-local draft namespace for that same project ID (Caption, figure/table editor, prose, comment, title/model) plus browser-only preview choices before rendering the fresh state. A clean rerun must not resurrect pre-reset unsaved text from localStorage.
   - Present the required project ID in a selectable read-only input with a dedicated copy button, alongside a separate confirmation input. Never put the only copy of the ID inside a native prompt message or other unselectable text.
11. Table validation must enforce the configured float width: two-column tables use a matched `table*` environment and single-column tables use `table`. Keep this invariant alongside fixed label/caption and traceable numeric-cell validation across initial generation, Agent edits, saves, and approval.
   - Drive table Agent/edit/save/approve controls from the visible LaTeX textarea. Enable save only for a nonempty dirty value; keep clean approved `已插入正文` disabled, and expose a dirty approved table as `更新表格 → PDF` so the visible revision can be compiled transactionally.
12. Use `gpt-5-nano` as the default text GPT API model for a new or empty Paper Studio state. Keep the model field editable and preserve `PAPER_STUDIO_MODEL` as an explicit deployment override; a persisted project selection still takes precedence over the default.
13. Keep text-LLM API selection and key setup explicit without moving secrets into
    browser state. Ask for OpenAI or DeepSeek in the terminal workflow and pass the choice at server startup; do not show provider or key settings in the webpage. Do show a free-text writing-model field with provider-specific suggestions (for example GPT mini/nano or DeepSeek V4 Pro/Flash); suggestions must not restrict researcher-entered model identifiers. Applying it resets incompatible LLM conversation chains without changing accepted prose. Persist only the provider and model; public state
    exposes only whether that provider's environment configuration is ready plus
    safe setup commands. Switching providers resets incompatible response chains
    and selects that provider's default model. Never render, accept, persist, log,
    or return a key. Remove `OPENAI_API_KEY` and `DEEPSEEK_API_KEY`
    from local-Agent subprocesses. Keep GPT Image explicitly OpenAI-only.
14. Terminal one-shot full-draft generation and the webpage are one live workflow.
    `$paperwrite` keeps a same-project Paper Studio server/page open while
    `python3 -m paper_studio.server --direct-full-draft --provider <openai|deepseek>` runs as a separate process.
    Require the terminal workflow to ask the researcher which API to use and
    reject direct mode when `--provider` is omitted.
    Persist every paragraph's successful Accept-and-compile revision before moving
    on; make public-state reads detect external CLI revisions instead of serving a
    stale in-memory snapshot. Within one polling cycle and without reload, update
    the page's current paragraph, completed/total progress, accepted prose and
    navigation state, and compiled PDF revision. Never synchronize only at the end.

## Workspace data map

- `paper_studio/` is the fixed reusable web engine: server, frontend assets, empty-project shell, and PDF/PPTX composition implementation. It exists and starts independently of any paper. Do not regenerate or fork it for each paper, and do not put project-specific section, figure, table, branding, or result definitions there.
- `paper/paper_studio.json` is the single project configuration: stable project ID, identity/venue, ordered sections and LaTeX filenames, result bindings, Figure/Table definitions and order, typed data-grid mappings, mechanism shape-spec paths, and explicit `paths.main`, `paths.reference`, and `paths.metrics`. Starting another paper means supplying a new config and project data—not rewriting the web application. Change `project.id` for a genuinely different paper so persisted runtime state cannot leak across projects; preserve it for ordinary config revisions within the same paper.
- The fixed `paper_studio/` product must contain no paper title, method name, benchmark name, metric path, or project-specific mechanism fallback. Generic placeholders and config-driven fallback shapes are allowed; every paper-specific label, plotting program, or shape specification belongs under `paper/` or `results/`.
- `paper/paragraph_plan.json` is the canonical paragraph/subsection and artifact-binding plan. `paper/working_abstract.txt`, `paper/reference_stylization_jailbreak.txt`, and `paper/references.bib` are writing/reference inputs.
- `paper/sections/*.tex` contains accepted rendered manuscript text; `paper/main.tex` and `paper/main.pdf` are the manuscript entry point and compiled output.
- `paper/.paper_studio/state.json` contains persisted browser/workflow state; its sibling preview/page directories are generated caches. Only Paper Studio server workflows may mutate this state—local Agents must never edit it directly.
- `results/` contains traceable experiment evidence. Read the exact result path required by the figure/table definition instead of assuming all metrics live in one fixture.
- `paper/fig/` contains final figure PDF/PPTX artifacts. `paper/figsrc/` contains panel PDFs, plotting-agent sources, editable shape specifications, layout prompts, and composition metadata.
- `tests/test_paper_studio.py` contains deterministic regression coverage for these state transitions; browser behavior additionally requires a real headless-browser check.

Before opening a browser, run `python3 -m paper_studio.server --validate-project`. It must validate `paper/paper_studio.json` against `paper/paragraph_plan.json`: section sets, artifact IDs, dependencies, labels, panel IDs, project-local main/reference/metrics paths, typed `records` or `benchmark_rows` data grids, two-integer increasing `reference_lines`, exact `reference_file` agreement, and configured shape files. A red preflight blocks launch. Keep paper-specific plotting programs and mechanism shape specifications under `paper/figsrc/`. Modify `paper_studio/` only when adding or fixing a reusable product capability.

For a clean `/paperwrite` retest, stop the project-backed server and archive or remove only `paper/` after explicit confirmation. Preserve `paper_studio/`, skills, tools, `reports/`, `results/`, and `researcher-profile/`. The empty Paper Studio shell remains available while `paper/` is absent; the next `/paperwrite` scaffold only recreates paper-local config/content and then restarts the fixed engine in project-backed mode.

## Required validation

Run at minimum:

```bash
node --check paper_studio/static/app.js
python3 -m py_compile paper_studio/server.py
python3 -m unittest tests.test_paper_studio
```

Use a headless Chrome/Playwright pass for layout, visibility, click, focus, iframe-stability, or modal behavior. Test both sides of every conditional UI label, such as first composition versus recomposition and single-panel versus multi-panel figures.

Run the reusable non-mutating baseline matrix against the live project-backed server:

```bash
python3 -m pip install -r paper_studio/requirements-dev.txt
python3 -m playwright install chromium
python3 .claude/skills/paperstudio/scripts/browser_matrix.py --url http://127.0.0.1:8765
python3 .claude/skills/paperstudio/scripts/browser_matrix.py --url http://127.0.0.1:8766
```

Extend that script whenever a new static or dynamic interaction class is added; the unit-test interaction inventory intentionally fails when a control or browser API path is added without being catalogued.

Do not report success from source inspection alone. Confirm the server's public state and the rendered browser DOM.
