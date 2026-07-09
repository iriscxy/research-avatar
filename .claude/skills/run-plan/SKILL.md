---
name: run-plan
description: Execute an approved EXPERIMENT_PLAN.html — implement against the researcher's habitual stack, smoke-test first, deploy runs, collect results into real files — stopping at every human gate (the researcher is the judge of success, never the assistant). Use when the user wants to run, execute, or carry out their experiment plan. Invocable as /run-plan.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

Execute the plan named in the arguments passed when invoking this skill (default `outputs/03_EXPERIMENT_PLAN.html`). Read the **English** `aris-profile/PROFILE_AUTO.md` (via `$ARIS_PROFILE`) for stack/OOM context — it is canonical (`PROFILE_AUTO.zh.md` is a human-facing Chinese mirror only, not for logic). Converse with the researcher in **Chinese**; keep code/logs/identifiers native. Drive the autonomous work with Claude Code's built-in **`/goal`** — but **you are NOT the judge of success; the researcher is.** Stop at every gate.

Set the `/goal` completion condition **mechanical and verifiable** — e.g. "every run in the plan has a result file under `results/` and a row in `outputs/04_EXPERIMENT_TRACKER.html`" — NOT "the experiments succeeded" (that's a human verdict).

**Output format — the human-facing deliverables are self-contained HTML files, never Markdown.** `outputs/04_EXPERIMENT_TRACKER.html` and `outputs/05_FINDINGS.html` are standalone `.html` with an inline `<style>` block, an HTML `<table>` for the tracker rows, and no external assets. Raw result files (`results/*.json|csv`) and logs stay in their native format. Every number in the HTML traces back to a raw result file. Any Chinese prose in these files must be **natural, native Chinese — never word-for-word machine translation** (no gibberish collocations); re-read each sentence for readability before writing.

## Run loop (in the plan's run order)

1. **Stack match** — generate code against the profile's habitual launcher / framework / base model. Hyperparameters come from the plan, not the profile.
2. **Smoke test FIRST** — smallest config end-to-end; fix setup before real GPU. **GATE: report smoke result.**
3. **Deploy** the planned runs — resume-safe, versioned outputs, never overwrite a prior result. If the profile records OOMs on the target GPU, default to a memory-safe setup (lower batch / raise grad-accum) and note it.
4. **Collect** into real files (`results/*.json|csv`) + an `outputs/04_EXPERIMENT_TRACKER.html` table. Every number traces to a file.

## Gates — STOP, human is judge

- **After smoke test** → pass/fail before launching the full set.
- **After each result block** (baseline / main / ablation) → present numbers *as read from result files*; ask "does this support its claim?" The researcher decides pivot / supplement / proceed. Never self-declare "it worked."
- **Before any run over the plan's flagged budget** → ask first.

## Do NOT

- Redesign the experiments (that was `/workplan`). If the plan is wrong, stop and say so — don't silently improvise a different study.
- Fabricate/estimate a number. Missing result = `MISSING`, not a guess.
- Mark a claim "supported" — that's the researcher's call at the gate.

## Output

`outputs/04_EXPERIMENT_TRACKER.html` + `results/` + a short `outputs/05_FINDINGS.html` the researcher signs off → input to `/paper-write`.
