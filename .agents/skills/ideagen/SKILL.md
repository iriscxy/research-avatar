---
name: "ideagen"
description: "Generate a personalized, literature-grounded slate of research ideas through one engineering, theory, or benchmark lens; verify novelty, annotate material ethical risk, and stop for the researcher to select an idea. An evidence-tethered disruptive wildcard is available only when explicitly requested. Invoke explicitly as `$ideagen`."
---

# Idea Generation

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Read `researcher-profile/PROFILE.html`, `researcher-profile/publications.json`,
and the verified landscape in `reports/01_LIT_SURVEY.html`. Missing profile
records return to `$profileconstruct`. A missing/off-topic survey returns to
`$researchlit` unless the researcher explicitly accepts thin profile-only
grounding.

Treat the idea audit, verified sources, and selection state as authoritative
inputs; `reports/02_IDEA_REPORT.html` is rendered output. Every rerun, prose
rewrite, or selection change must render the complete report to a temporary
path, validate it, and atomically replace the canonical file. Never inject a
banner, rewrite isolated DOM nodes in the delivered file, or preserve a manual
correction by reading it back as source.

## Invocation decisions

Resolve the direction and exactly one lens before generating ideas:

- `engineering`: iterate or recombine habitual methods with reusable code;
- `theory`: target a hypothesis or bound at a research-line fault line;
- `benchmark`: survey, dataset/evaluation, or reproduce-and-beat work.

Accept an optional reference paper and fold its methods, results, limitations,
and openings into the grounding. Never create a separate reference summary.

The disruptive wildcard defaults to off and runs only when explicitly
requested. When enabled, read
[`references/disruptive-branch.md`](references/disruptive-branch.md) completely
before generation and append at most one eligible `D1`; never merge its score
with the standard ranking.

Read [`references/setup-and-ethics.md`](references/setup-and-ethics.md) while
locking mode/direction and screening material ethical risk. Do not emit generic
ethics warnings for ordinary model work without a concrete human-impact path.

## Generate the slate

Use an API-assisted candidate-diversification pass when a supported provider is
configured. If the researcher named OpenAI or DeepSeek, use that provider; if
exactly one of `OPENAI_API_KEY` and `DEEPSEEK_API_KEY` is configured, use it;
otherwise ask for the provider instead of exposing or copying a key. Run:

```bash
python3 research_avatar/tools/generate_idea_candidates_api.py \
  --provider <openai-or-deepseek> \
  --output reports/.build/02_IDEA_CANDIDATES.api.json
```

The two API rounds deliberately vary mechanisms and evaluation regimes. Their
output is an unverified seed pool, never a novelty result: retain its response
IDs and survey/profile digests, then independently apply the collision,
feasibility, scope-necessity, and devil's-advocate checks below. If no supported
API is configured, retain the existing Code Agent generation path and label the
report provenance `code-agent-only`; never imply that an API was called.

Use the profile and survey's structural gaps to select six initial candidates
from the verified API seed pool plus any genuinely distinct Code Agent seeds.
Each candidate starts with one plain-language sentence stating the
problem, intervention/test, and observable outcome, followed by one core
mechanism, 2–4 concrete method steps, hypothesis, falsifier, feasibility, and
closest work.

Give every candidate a structured `source_grounding` that names at least one
exact Survey Gap/Opening or Live Debate and one literature-family
`failure_boundary`. Render these links in the candidate card. A generic claim
that the idea is "grounded in the survey" is not traceability.

When a completed RunPlan records a verified baseline implementation anomaly,
read `reports/.build/reideation_input.json`, generated from its
`reideation_checkpoint`, as optional empirical grounding. Require the evidence
digest to match the current artifact. Preserve the command, artifact, observed
mismatch, and the baseline's intended contract;
generate an idea from it only when the anomaly survives conformance checks and
changes a testable mechanism. Never treat an adapter bug or failed reproduction
as evidence that a scientific idea works.

On rerun, load unrejected prior idea records as structured inputs, add genuinely
new angles, and rerank the union before rendering the whole report again. Never
pad the slate with cosmetic variants or contrived mashups. If
fewer than three selectable candidates survive, make one additional pass using
unused gaps/profile assets; if the field remains crowded, report the smaller
honest slate.

## Novelty and ranking

For every candidate:

- compare against the researcher's own publications;
- run 2–3 targeted searches, including the latest six months;
- inspect the closest 3–5 papers beyond snippets;
- record overlap, concrete difference, evidence gaps, and confidence;
- assign exactly one status: `novel`, `differentiable (needs framing)`,
  `already exists`, or `[UNVERIFIED]`;
- apply a single-mechanism test and scope-necessity test;
- conduct a separate same-model devil's-advocate pass.

Use an objective feasibility gate only for proven unavailable data or clearly
impossible compute. Rank qualitatively, not by a weighted novelty score.
Tier A contains high-confidence novel ideas; Tier B contains selectable
differentiable ideas with a concrete reframe and falsifier. Exact duplicates,
unverified ideas, unresolved A+B mashups, and application swaps are not pick
options.

Read
[`references/generation-and-novelty.md`](references/generation-and-novelty.md)
for the complete generation, collision-check, scope, and ranking procedure.

## Canonical report

Write one self-contained `reports/02_IDEA_REPORT.html`, linking the landscape
survey and only verified papers. Do not create a novelty dossier or standalone
wildcard report. Persist hidden per-idea novelty audits and an optional
structured selection record in this file.

Read [`references/report-and-gate.md`](references/report-and-gate.md) while
rendering, validating, and presenting the decision gate.

Run:

```bash
python3 research_avatar/tools/validate_ideagen_report.py reports/02_IDEA_REPORT.html
python3 research_avatar/tools/validate_report_structure.py --kind ideas --html reports/02_IDEA_REPORT.html
```

When the wildcard is enabled, also run its dedicated validator. Ask the
researcher to pick, kill, or redirect by ID and stop. Never auto-proceed.
After a pick, update the structured selection state, then regenerate the complete
report so it contains `Selected: I<k> — <title>` or `Selected: D1 — <title>`
with the date and the chosen-row marker. Selection must use the same renderer as
initial generation, not a banner/row mutation path. The selected idea is the
input to `$expplan`.
