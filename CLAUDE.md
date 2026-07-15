# Research Buddy — personalized assistant for an experienced researcher

This is a **lean, personalized** research assistant — NOT a full autoresearch system.
The researcher has judgment; the assistant's job is to **accelerate the mechanical
parts, grounded in the researcher's own record**, and to **stop at decision gates so
the human reviews** (the human is the judge — there is no autonomous accept/reject).

## Single source of truth

All personalization reads from **`aris-profile/PROFILE_AUTO.md`** in this project
(resolved via `$ARIS_PROFILE`, set in `.claude/settings.json` — NOT the user-global
`~/aris-profile/`, which has been removed for this project). It holds: Research
Identity, Publications Index (with per-paper `task_type` ∈ {engineering, theory,
benchmark}), BibTeX Bank, Writing Style, Research Lineage, **Experiment Templates**
(toolchain / base model / GPUs / OOM memory — mined, NOT hyperparameter values), and
**Workflow Preferences (W1–W7)**. Alongside it: `enriched.json` (abstracts + BibTeX),
`habits.json` / `prefs_bundle.json` (internal mining), `fulltext/` (per-paper PDFs +
extracted text), and **`PROFILE_AUTO.zh.md`** — a human-facing Chinese mirror
(regenerated in the same pass; the **English `PROFILE_AUTO.md` stays canonical** and is
what all skills read). If it is missing or stale, run the **profile-construct** skill.

## The six skills (run in this order — W6)

Each is a Skill in `.claude/skills/<name>/SKILL.md` — Claude may auto-invoke one
when the conversation matches its description, and the user can invoke it
explicitly with the same `/<name>` slash:

| | Skill | What |
|---|---|---|
| 1 | `/profile-construct` | Build / refresh `PROFILE_AUTO.md` from Google Scholar + Claude-session habits |
| 2 | `/research-lit` | Literature survey: many parallel verified arXiv/web search angles → self-contained **white-background, natively-Chinese** magazine-style HTML `outputs/01_LIT_SURVEY.html` (hero · taxonomy · card grids · landscape table · trends/gaps · grouped refs). Standalone, or the grounding step for `/ideagen` |
| 3 | `/ideagen` | **Reads `outputs/01_LIT_SURVEY.html`** (does NOT re-survey) → 3-lens idea generation (method-first) → novelty check vs own work + concurrent work → ranked idea slate (`outputs/02_IDEA_REPORT.html`). Optional `— ref paper:` to build on a paper. Human picks the idea |
| 4 | `/workplan` | From the chosen idea → claim-driven `outputs/03_EXPERIMENT_PLAN.html` (backward from the projected abstract). **The projected paper skeleton is a section (§0.5) INSIDE `03`, not a separate file** — a standalone `outputs/03b_PAPER_PLAN.html` is written ONLY if the researcher explicitly asks for a fuller/visual outline |
| 5 | `/run-plan` | Execute the plan with `/goal`, stopping at gates for human review |
| 6 | `/paper-write` | Personalized paper writing (style-ref / self-cite / anti-self-plagiarism). **Orchestrates four review sub-skills automatically** in its loop: `/paper-theorization` (unified formal spine, mechanically checked) · `/paper-related-work` (broad, id-verified citations) · `/paper-gap-check` (claim→`results/` audit → `paper/EXPERIMENT_PLAN.md`, never fabricate) · `/paper-logic-check` (fresh-reviewer narrative-loop check). Each is also a standalone `/paper-<name>` skill |

**All pipeline deliverables are self-contained HTML in one `outputs/` folder, numbered by
workflow step:** `01_LIT_SURVEY` · `00_REF_PAPER_SUMMARY` (optional) · `02_IDEA_REPORT` · `03_EXPERIMENT_PLAN` (paper
skeleton lives inside it as §0.5) · `03b_PAPER_PLAN` (rare — only on explicit request) ·
`04_EXPERIMENT_TRACKER` · `05_FINDINGS`. Never emit `.md`
versions of these. Exceptions that keep their native format: `PROFILE_AUTO.md` (source of
truth, tool-read), `results/*.json|csv` + logs (raw data), and the paper manuscript
(`paper/main.tex`).

## Global disciplines (always on — these are the non-negotiables a deadline would skip)

1. **Human is the judge.** Never auto-declare an idea novel, an experiment
   successful, or a result claim-supporting. At each gate, present the evidence and
   **stop for the researcher's verdict** (their Workflow Preference W5).
2. **Smoke-test first (W1).** Before any full run, execute the smallest/fastest
   version to catch setup bugs. Cheap/deterministic step before expensive/GPU step.
3. **One variable per ablation.** An ablation run changes exactly one thing vs its
   baseline; never confound two changes in one run.
4. **Numbers trace to raw files.** Every number that reaches a plan, a slide, or a
   paper must come from a real result file (JSON/CSV/log) — never from memory or
   estimation. If you cannot point to the file, mark it `[UNVERIFIED]`, don't write it.
5. **Match the researcher's stack, not their hyperparameters.** Generate code against
   their habitual toolchain/base-model (Experiment Templates); let `outputs/03_EXPERIMENT_PLAN.html`
   decide lr/batch/seed — those are task-determined.
6. **Cache & don't overwrite (W2/W3).** Persist intermediate artifacts, support
   resume, write versioned/timestamped outputs; never clobber a prior result.
7. **Output language follows the user — never hard-coded, never pre-decided.** No skill
   fixes a deliverable's language in advance. Pick it, in order: (a) an explicit
   `— lang:` directive · (b) the language the user wrote the request in · (c) if
   genuinely ambiguous, ask. Whatever language is chosen, write it **natively** — as a
   domain researcher would, never a word-for-word machine translation (re-read each
   sentence for readability); keep code / identifiers / paper-titles native (English).
   **Write deliverables TO the researcher — address her in the second person** (你/你的
   in Chinese, "you/your" in English), never the third person (a stray 她 / "she" reads
   as discussing a stranger and is a defect). Produce a **second-language mirror only if
   the user wants both**; a mirror must be a faithful native translation (the projected
   abstract, when mirrored, stays a faithful sentence-for-sentence translation). By
   default emit ONE file in the chosen language. Downstream skills read the **primary**
   deliverable regardless of its language — they parse structure/ids, not prose — so
   "canonical" names the file downstream reads, not a fixed language. (`PROFILE_AUTO.md`
   is the one exception: it stays English-canonical because it is tool-read, with an
   optional `PROFILE_AUTO.zh.md` human mirror.)

## Tools (stdlib Python, no dependencies, no framework)

`tools/` — `scholar_profile.py` · `profile_enrich.py` · `experiment_history.py` ·
`workflow_prefs.py` · `bib_manager.py` · `paper_checks.py` (deterministic paper-conformance
gates — budget/style/length/formal/format — the `paperkit`-equivalent for `/paper-write`).
Each takes argparse args and emits JSON; run `python3 tools/<name>.py --help` for the interface.
