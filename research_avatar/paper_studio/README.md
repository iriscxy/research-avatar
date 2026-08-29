# Paper Studio

Section-aware drafting engine embedded in the local Research Studio. This is not
a separate user-facing local product page: researchers open
<http://127.0.0.1:8780>, then enter the paper-writing stage inside Research
Studio. Its loopback backend rejects direct page access and is reachable only
through Research Studio's same-origin proxy.

DeepSeek V4 Flash is the default low-cost writing provider. Choose OpenAI or DeepSeek
in the terminal, then configure the matching environment
before starting the server. The browser shows runtime status and provider-specific
an editable writing-model field with non-binding suggestions (GPT-5/mini/nano or DeepSeek V4 Pro/Flash), but no provider
or API-key settings panel:

```bash
# OpenAI
export OPENAI_API_KEY="your API key"

# DeepSeek
export DEEPSEEK_API_KEY="your API key"

python3 -m research_avatar.research_studio.server --ensure-studios
```

That command opens the single local user entry at <http://127.0.0.1:8780> and
starts the underlying writer service as needed. API keys remain in the server
process and are never sent to the browser. Enter them in the local terminal,
not in chat, a repository file, or a browser field. If the writer was already
running without the selected key, stop it and restart it after exporting the
project. Changing the writer provider resets incompatible conversation IDs.
Mechanism figures are rendered locally as editable native shapes by Codex and
do not require a separate image-provider key.

The application under `research_avatar/paper_studio/` is a reusable engine. Project-specific
identity, section order and LaTeX filenames, result bindings, Figure/Table
definitions, artifact order, and the metrics path live in
`paper/paper_studio.json`. A new paper keeps the same HTML/JavaScript/Python
application and supplies a new config with embedded paragraph architecture, manuscript
inputs, and `results/`. Changing `project.id` starts a fresh runtime state; editing
other config fields within the same project preserves the current state.

When `reports/04_RUN_PLAN.html` declares a completed run, every goal is
completed, and `reports/05_EXP_RESULT.html` exists, the Research Studio paper
tab displays one explicit initialization command. Running it follows the run
report's `source_plan` pointer, creates the Paper Studio project, and opens the
Research Studio page. A local or reduced experiment variant is therefore never
silently replaced by the canonical 03 plan. The generated metrics bundle keeps
`05_EXP_RESULT.html` as its provenance source, and paragraph prompts receive
only the result artifacts bound to that paragraph. The abstract is generated
last from the compact executed result tables.

The Studio is not a blank writing form. Each configured section carries the
target-paper architecture approved during Experiment Planning: ordered paragraph
tasks, each task's purpose and rhetorical role, its relation to the previous and
next paragraph, and artifact bindings. The top of each section shows this complete
blueprint. When a paragraph becomes current, the browser asks GPT to draft it from
that approved architecture, the working abstract, accepted section context, and
current experiment evidence. Reference-paper prose is never shown or sent during
writing. The researcher only comments on the generated candidate or
accepts it. Sections with multiple paragraphs expose a paragraph navigator:
pending or candidate paragraphs may be edited in any order, accepted paragraphs
remain selectable revision bases, and accepted prose is always assembled into
LaTeX in the approved plan order.

After the outline is approved, **Generate full first draft** provides an optional batch
path inside the existing **Prose** workspace. It uses the same LLM API, paragraph
plan, citation verification, result bindings, transactional LaTeX writes, and
compile checks as interactive drafting. It processes only unaccepted paragraphs,
in the `batch_writing_order` declared by `paper/paper_studio.json`; accepted prose
is never overwritten. Progress is persisted, the job can be stopped after the
current paragraph transaction, and a later click resumes from the remaining
paragraphs. This is a writing mode, not a separate paper state or a fourth tab.

To skip the web interface entirely, run the same batch path from the terminal:

```bash
python3 -m research_avatar.paper_studio.server --direct-full-draft --provider openai
# or: --provider deepseek
```

An explicit model override is optional: `--model deepseek-v4-flash`. The command exits
only after every pending paragraph has passed the normal write-and-compile
transaction, or reports the paragraph where the job failed. Opening Paper Studio
later shows the same accepted paragraphs and PDF because CLI and UI share one
canonical state.

Each manuscript section stores its own provider-specific conversation ID in
`paper/.paper_studio/state.json`. The first request in a section bootstraps the
approved outline, the Writing Style section of `researcher-profile/PROFILE.html`,
and the complete BibTeX catalog. OpenAI uses server-hosted Responses chains;
Chat Completions providers keep the equivalent history in the running Studio
process and safely re-bootstrap after a restart. Developer instructions are sent
on every request.

Citation obligations apply in every manuscript section. The local editor selects only
real keys already present in `paper/references.bib` and verified by
`reports/01_LIT_SURVEY.html`; it never searches the web or appends BibTeX during
paragraph generation, and unresolved `\cite{}` cannot be accepted. The online editor
keeps the same obligations as literal `\cite{}` placeholders and never selects keys.

`Accept → LaTeX` is transactional: it rejects stale candidates and unknown
citation keys; writes only the section's fixed file under `paper/sections/`;
compiles immediately; and restores the previous file if compilation fails.

The writing panel also offers `Generate current Section`. It uses the same
paragraph generator, acceptance checks, citation constraints, transactional
LaTeX writes, and compilation path as ordinary paragraph writing, but limits
the task to unfinished paragraphs and bound figures/tables in the selected
Section. It has its own `/api/section-draft/start` endpoint and
`section_draft_job` state; it never creates, updates, or displays the
`full_draft_job` used by **Generate full first draft**. Accepted paragraphs and every
other Section remain unchanged.

The **Figures** workspace is section-aware: it uses each configured figure's
`source_sections`, paragraph dependencies, artifact dependencies, and result keys
to decide where the figure appears and when it becomes available.

Mechanism figures follow an explicit human gate from `$figureppt`: GPT first
turns the bound section prose into a drawing prompt automatically when
the ready figure is first opened. For later regeneration, the researcher supplies
a concrete instruction (for example, simplify the composition or make it
single-column); GPT receives the current Prompt plus that instruction and rewrites
the complete Prompt. Each mechanism figure owns a separate persistent Responses
API chain (`figure:F1`, `figure:F3`, and so on); it never reuses the manuscript
section's writing conversation. Only **Confirm Prompt → Codex drawing** starts drawing.
Prompt generation and native-shape composition run as background jobs with persisted
stage and progress messages in the browser. The composition is emitted directly as
editable PowerPoint shapes and exported to PDF. Result-driven data figures use the installed local Codex
agent to author a dedicated Python plotting program, then run that archived
program locally against `results/` to produce matching PDF and PNG candidates.
Each data panel is generated separately when the researcher requests it, and every
completed panel appears immediately as a PDF candidate. Plotting source remains local
and is not exposed as a browser code block. After all panels exist, a separate paper-layout Prompt
is interpreted by the installed local Codex Agent into a validated layout JSON. The
browser shows that plan for inspection. A deterministic local composition pass then
executes it: `pdfcrop` removes each PDF's outer whitespace; each panel is placed as a
separate vector object in an editable PPTX; and optional `(a)/(b)` labels remain editable
text boxes with Agent-selected font sizes. The final vector PDF is compiled from the
same validated geometry, so composition never triggers a macOS PowerPoint permission
dialog. Only that composed PDF/PPTX pair can be approved for insertion. A
missing result dimension stays visibly locked instead of being fabricated, and
All supported LLM API keys are removed from the Agent subprocess.

The **Tables** workspace has a separate editable local-Agent Prompt. Initial
generation and later result-related revisions are handled by the installed local
Codex agent using traceable result context. The browser preview is a PNG rasterized
from the table's real LaTeX-compiled PDF, not a separately styled HTML table. The
generated LaTeX remains directly editable before approval.

For free-form revisions, the table workspace also exposes **Revision prompt for the local Agent**.
That action launches the installed `codex exec` CLI in an ephemeral,
read-only sandbox, with the current LaTeX and traceable result matrix. Paper Studio
removes all supported LLM API keys from that subprocess and does not call a text LLM API.
The returned table must retain its fixed label and caption and compile successfully
before it replaces the draft.

Install the repository's frozen dependencies before using figure actions or tests:

```bash
make setup
```

Run the complete unit suite through the same root entry point, then run the
real-browser matrix when changing web behavior:

```bash
make test
python3 research_avatar/paper_studio/browser_matrix.py --url http://127.0.0.1:8780/paper-studio
```

The unit suite covers the empty embedded shell without exposing a second local
paper-editor page.
