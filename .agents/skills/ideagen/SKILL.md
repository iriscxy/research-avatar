---
name: "ideagen"
description: "For one researcher-chosen research question and angle from the literature survey, generate a personalized (Jinghui Profile setting) or non-personalized (None setting) slate of research ideas; verify novelty, annotate material ethical risk, and stop for the researcher to select an idea. An evidence-tethered disruptive wildcard is available only when explicitly requested. Invoke explicitly as `$ideagen`."
---

# Idea Generation

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Read the whole survey: `reports/01_LIT_SURVEY.html` and its structured source
`reports/.build/01_LIT_SURVEY.source.json` — the Problem, every Approaches
family with its comparison and `failure_boundary`, the Evaluation regimes,
live debates, trends, gap-falsification evidence, the research questions, and
the verified paper records. Read the paired records in
`researcher-profile/profile_pairs.json`. Missing paired Idea records return to
`$profileconstruct`. A missing/off-topic survey, or one without research questions,
returns to `$researchlit`.

Treat the idea audit, verified sources, generation records, and selection
state as authoritative inputs; `reports/02_IDEA_REPORT.html` is rendered output.
Every rerun, prose rewrite, or selection change must render the complete report
to a temporary path, validate it, and atomically replace the canonical file.
Never inject a banner, rewrite isolated DOM nodes in the delivered file, or
preserve a manual correction by reading it back as source.

## Step 1 — Choose one research question

List the survey's research questions (`Q*`, keyword titles) and, when present,
its personalized ones (`PQ*`), and ask the researcher to pick one by ID or type
their own in a few words. The researcher makes only two choices before the
slate: this question and the angle in Step 1a.

If none fits, offer, in order:

1. Ask what is wrong — too broad, too narrow, outside their interests, already
   done, or the wrong kind of work — and write new questions from the same
   survey evidence that address the answer, add them to the survey source, and
   rerender the survey with its renderer.
2. Propose 2–3 adjacent broad topics from Research Identity and Research
   Lineage and rerun `$researchlit` on the chosen one.
3. Exploration: rerun `$researchlit — questions: personalized` so the questions
   continue the researcher's lineage. This lets the profile choose the
   question, so it is off in a user study that compares settings.

Record the choice in the idea source JSON as `research_direction`
(`{"id", "title", "origin": "neutral|personalized|researcher"}`; the field
name is historical, its content is the chosen research question).

## Step 1a — Ask for the angle

Ask the researcher from which angle they want to approach the chosen question,
and wait for the answer. Offer a few angles that fit this question and the
survey evidence — for example a new method, a theory or formal analysis, a
mechanistic or empirical analysis, a benchmark or evaluation protocol — and let
them name any other angle in their own words (such as efficiency, safety, or a
particular application). Do not pick the angle for them. Record it as `angle`
(`{"title", "origin": "offered|researcher"}`) in the idea source JSON. A
`— lens:` argument answers this step in advance.

## Step 1b — Split the question into sub-questions

The chosen question is a keyword, not a Jinghui input, and sampling one input
repeatedly collapses to one idea. So split it: in one fresh isolated context
given the chosen question, the angle, and the complete survey synthesis
(Problem, families with their comparisons and failure boundaries, Evaluation
regimes, live debates, trends, gap evidence, and the verified paper titles and
takeaways) — never the profile — write 3–5 sub-questions. Each sub-question is
the concrete problem one idea will tackle, in the Jinghui Idea input format
(one sentence ending with `?`, revealing no solution, distinctive method,
expected result, or author identity), within the chosen angle, and starting
from different survey evidence than the others (a different family failure
boundary, live debate, trend, or paper limitation). Check them pairwise and
rewrite one if two would lead to the same project.

Show each sub-question with its idea in `3. Ideas`, without a number or ID; the page's
only identifiers are the chosen question and the idea IDs `I<k>`. Sub-questions
are not a separate approval gate. With a user study that compares settings,
write the sub-questions once and reuse them for every setting.

## Step 2 — Setting, lens, and options

- `— setting: profile` (default) applies the Jinghui Profile setting with the
  Idea `author_differences` retrieved for each question. `— setting: none` is the
  non-personalized baseline: same questions, same task prompt, no profile.
- `— lens: <angle>` is optional and answers Step 1a in advance; every question
  and candidate stays within that angle.
- Accept an optional reference paper and fold its methods, results,
  limitations, and openings into the grounding. Never create a separate
  reference summary.

The disruptive wildcard defaults to off and runs only when explicitly
requested. When enabled, read
[`references/disruptive-branch.md`](references/disruptive-branch.md) completely
before generation and append at most one eligible `D1`; never merge its score
with the standard ranking.

Read [`references/setup-and-ethics.md`](references/setup-and-ethics.md) while
screening material ethical risk. Do not emit generic ethics warnings for
ordinary model work without a concrete human-impact path.

## Step 3 — Generate the slate

For each sub-question from Step 1b, build its generation request:

```bash
python3 research_avatar/tools/jinghui_prompt.py --task idea --setting <profile|none> \
  --input '{"research_question": "<sub-question>"}' \
  --output reports/.build/02_IDEA_REQUEST.<setting>.<question id>.json
```

Generate exactly one candidate per sub-question: one independent call in a fresh,
isolated context (the Agent tool) that receives only that request's `system`
and `user` and returns the four-field JSON (`research_focus`, `method`,
`validation`, `title`). That context must not read the profile, the survey, or
other candidates; this matters most for the None setting. Do not resample the
same sub-question for variety: the slate's diversity comes from the
different sub-questions. If two returned candidates still share their `research_focus`,
rewrite the later sub-question in Step 1b and generate again for it, at most
twice. Never edit a returned JSON; keep it as the candidate's `generation`
record with the setting, `retrieved_ids`, `system_sha256`, and the context's
run ID, and store the sub-question as the candidate's `research_question`
(`{"id", "question"}`); the page shows its text without the ID.

The page shows each idea's generated title, research focus, method and
validation verbatim. For the decision slate and the hidden audit, also record
without changing the generated text: one plain-language summary sentence,
feasibility, closest work, concrete difference, and strongest objection.

Give every candidate a structured `source_grounding` that names the survey
evidence its sub-question starts from (a family failure boundary, live debate, or
gap) and one literature-family `failure_boundary`. Record them in the hidden audit. A generic claim
that the idea is "grounded in the survey" is not traceability.

Every paper named anywhere in the report, including the decision slate and
novelty-evidence tables, must be a direct `<a href>` to its source; render plain
text only for self-built unpublished datasets or when no verified link exists.

When a completed RunPlan records a verified baseline implementation anomaly,
read `reports/.build/reideation_input.json`, generated from its
`reideation_checkpoint`, as optional empirical grounding. Require the evidence
digest to match the current artifact. Preserve the command, artifact, observed
mismatch, and the baseline's intended contract;
generate an idea from it only when the anomaly survives conformance checks and
changes a testable mechanism. Never treat an adapter bug or failed reproduction
as evidence that a scientific idea works.

On rerun for the same question, angle and setting, load unrejected prior idea records
as structured inputs, draw new samples, and rerank the union before rendering
the whole report again. Never pad the slate with cosmetic variants or contrived
mashups. Every report needs at least two `novel` (Tier A) candidates, each
confirmed `novel` and not absorbable by the fresh-context review. While fewer
than two survive, run another round: split the question into new sub-questions
from survey evidence not used so far, generate one idea per sub-question, and
novelty-check and review them; keep every earlier candidate and rerank the
union. Stop after at most three extra rounds. Never relabel a `differentiable`
or weakly verified idea as `novel` to reach the target. If the target is still
not met, report the question as crowded in the ranking note, show the honest
slate, and offer another angle or another question.

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

Show at most ten ideas in the report: rank the pool and keep only the strongest,
selectable ideas first (Tier A, then Tier B). Ideas that are absorbed by
existing work, unverified, or weaker than the ten shown are omitted from the
page; their records stay in the build files for reruns.

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

`reports/02_IDEA_REPORT.html` is rendered output; never handwrite its HTML.
Write the content into `reports/.build/02_IDEA_REPORT.source.json` (schema in
[`references/report-and-gate.md`](references/report-and-gate.md)), linking the
landscape survey and only verified papers, then render it with:

```bash
python3 research_avatar/tools/render_idea_report.py \
  --source reports/.build/02_IDEA_REPORT.source.json \
  --output reports/02_IDEA_REPORT.html
```

The renderer owns the fixed layout (adaptive tables, numbered sections, hidden
per-idea novelty audits, and the structured selection record) and refuses
invalid output before atomic replacement. Do not create a novelty dossier or
standalone wildcard report.

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
