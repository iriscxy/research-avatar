---
name: "ideagen"
description: "Generate a personalized, literature-grounded slate of research ideas through one engineering, theory, or benchmark lens; verify novelty, annotate material ethical risk, and stop for the researcher to select an idea. An evidence-tethered disruptive wildcard is available only when explicitly requested. Invoke explicitly as `/ideagen`."
---

# Idea Generation

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Read `researcher-profile/PROFILE.html`, `researcher-profile/publications.json`,
and the verified landscape in `reports/01_LIT_SURVEY.html`. Missing profile
records return to `/profileconstruct`. A missing/off-topic survey returns to
`/researchlit` unless the researcher explicitly accepts thin profile-only
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

Use the profile and survey's structural gaps to generate six initial
candidates. Each candidate starts with one plain-language sentence stating the
problem, intervention/test, and observable outcome, followed by one core
mechanism, 2–4 concrete method steps, hypothesis, falsifier, feasibility, and
closest work.

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

## Canonical report and readability pass

Write one self-contained `reports/02_IDEA_REPORT.html`, linking the landscape
survey and only verified papers. Do not create a novelty dossier or standalone
wildcard report. Persist hidden per-idea novelty audits and an optional
structured selection record in this file.

After scientific content and links are fixed, the researcher must choose
`provider: openai|deepseek`, then the LLM API rewrites eligible visible prose:

```bash
python3 research_avatar/tools/rewrite_ideagen_html.py reports/02_IDEA_REPORT.html --provider "<provider>" [--model "<model>"]
```

The rewrite may improve clarity only; it cannot change claims, evidence,
citations, novelty status, scope, or uncertainty. Missing key, API failure,
partial coverage, or a missing `ideagen-readable-rewrite` receipt is a hard
stop. The Code Agent must not substitute its own final rewrite.

Read [`references/report-and-gate.md`](references/report-and-gate.md) while
rendering, rewriting, validating, and presenting the decision gate.

Run:

```bash
python3 research_avatar/tools/validate_ideagen_report.py reports/02_IDEA_REPORT.html
python3 research_avatar/tools/validate_ideagen_readability.py reports/02_IDEA_REPORT.html
python3 research_avatar/tools/validate_report_structure.py --kind ideas --html reports/02_IDEA_REPORT.html
```

When the wildcard is enabled, also run its dedicated validator. Ask the
researcher to pick, kill, or redirect by ID and stop. Never auto-proceed.
After a pick, update the structured selection state, then regenerate the complete
report so it contains `Selected: I<k> — <title>` or `Selected: D1 — <title>`
with the date and the chosen-row marker. Selection must use the same renderer as
initial generation, not a banner/row mutation path. The selected idea is the
input to `/expplan`.
