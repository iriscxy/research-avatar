# Paper Studio

Local, section-aware drafting UI for `$paperwrite`.

Choose OpenAI or DeepSeek in the terminal, then configure the matching environment
before starting the server. The browser shows runtime status and provider-specific
an editable writing-model field with non-binding suggestions (GPT-5/mini/nano or DeepSeek V4 Pro/Flash), but no provider
or API-key settings panel:

```bash
# OpenAI
export OPENAI_API_KEY="粘贴你的 API key"

# DeepSeek
export DEEPSEEK_API_KEY="粘贴你的 API key"

python3 -m paper_studio.server --provider openai
# or: --provider deepseek
```

The system browser opens <http://127.0.0.1:8765> automatically unless startup
explicitly includes `--no-browser`. API keys remain in the server process
and is never sent to the browser. Enter it in the local terminal that launches
Paper Studio, not in chat, a repository file, or a browser field. If the server
was already running without the selected key, stop it and restart it after the export.
Changing the provider at startup resets incompatible conversation IDs. GPT Image remains OpenAI-only.

The application under `paper_studio/` is a reusable engine. Project-specific
identity, section order and LaTeX filenames, result bindings, Figure/Table
definitions, artifact order, and the metrics path live in
`paper/paper_studio.json`. A new paper keeps the same HTML/JavaScript/Python
application and supplies a new config plus `paper/paragraph_plan.json`, manuscript
inputs, and `results/`. Changing `project.id` starts a fresh runtime state; editing
other config fields within the same project preserves the current state.

The Studio is not a blank writing form. `paper/paragraph_plan.json` divides each
section into ordered paragraph tasks and maps every task to the corresponding
passage in the reference paper. When a paragraph becomes current, the browser
automatically asks GPT to draft it from that reference passage, the working
abstract, the approved outline, the accepted section context, and the current
experiment evidence. The researcher only comments on the generated candidate or
accepts it. Sections with multiple paragraphs expose a paragraph navigator:
pending or candidate paragraphs may be edited in any order, accepted paragraphs
remain selectable revision bases, and accepted prose is always assembled into
LaTeX in the approved plan order.

After the outline is approved, **直接生成全文初稿** provides an optional batch
path inside the existing **正文** workspace. It uses the same LLM API, paragraph
plan, citation verification, result bindings, transactional LaTeX writes, and
compile checks as interactive drafting. It processes only unaccepted paragraphs,
in the `batch_writing_order` declared by `paper/paper_studio.json`; accepted prose
is never overwritten. Progress is persisted, the job can be stopped after the
current paragraph transaction, and a later click resumes from the remaining
paragraphs. This is a writing mode, not a separate paper state or a fourth tab.

To skip the web interface entirely, run the same batch path from the terminal:

```bash
python3 -m paper_studio.server --direct-full-draft --provider openai
# or: --provider deepseek
```

An explicit model override is optional: `--model gpt-5-nano`. The command exits
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

If a generated paragraph contains `[CITATION NEEDED]` or an unknown citation key,
the OpenAI provider can continue the same section conversation with the Responses
API `web_search` tool. DeepSeek reports that this
OpenAI-only citation-verification step requires switching providers. The resolver
accepts only structured citation records whose scholarly
source URL appears in the search response, appends their BibTeX entries to
`paper/references.bib`, and returns the revised paragraph. Unverified citations
remain explicit placeholders.

`Accept → LaTeX` is transactional: it rejects stale candidates and unknown
citation keys; writes only the section's fixed file under `paper/sections/`;
compiles immediately; and restores the previous file if compilation fails.

The **Figures** workspace is section-aware: it uses each configured figure's
`source_sections`, paragraph dependencies, artifact dependencies, and result keys
to decide where the figure appears and when it becomes available.

Mechanism figures follow an explicit human gate from `$figureppt`: GPT first
turns the bound section prose into a BioRender design prompt automatically when
the ready figure is first opened. For later regeneration, the researcher supplies
a concrete instruction (for example, simplify the composition or make it
single-column); GPT receives the current Prompt plus that instruction and rewrites
the complete Prompt. Each mechanism figure owns a separate persistent Responses
API chain (`figure:F1`, `figure:F3`, and so on); it never reuses the manuscript
section's writing conversation. Only **Confirm Prompt → GPT Image** starts drawing.
Prompt generation and image drawing run as background jobs with persisted stage
and progress messages in the browser. The resulting raster is a composition
draft, then the confirmed composition is rebuilt internally as editable PowerPoint shapes
and exported to PDF. Result-driven data figures use the installed local Codex
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

For free-form revisions, the table workspace also exposes **给本地 Agent 的修改
Prompt**. That action launches the installed `codex exec` CLI in an ephemeral,
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
python3 .agents/skills/paperstudio/scripts/browser_matrix.py --url http://127.0.0.1:8765
```

Run the same matrix against an empty shell started on another port; it verifies
that the reusable Studio opens without `paper/` while all mutation controls stay
disabled:

```bash
python3 -m paper_studio.server --empty --port 8766
python3 .agents/skills/paperstudio/scripts/browser_matrix.py --url http://127.0.0.1:8766
```
