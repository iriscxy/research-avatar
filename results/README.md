# ⚠️ SYNTHETIC PLACEHOLDER RESULTS — NOT REAL EXPERIMENTS

Every number in this folder is **fabricated** to test the research-buddy
pipeline end-to-end through `/paper-write`. **No experiment was run.** Do NOT
cite, report, or treat any value here as a real result.

- Project: I2 · Route-Then-Steer (CRH-in-MoE), see `outputs/02_EXPERIMENT_PLAN.html`
- Generated: 2026-07-05 as a pipeline test fixture
- Every JSON carries `"synthetic": true` and a `"warning"` field.
- Models named (OLMoE-1B-7B, Qwen1.5-MoE-A2.7B), metrics, and baselines mirror the
  plan so `/paper-write` has a coherent (but fake) story to draft from.

When real runs happen via `/run-plan`, these files get overwritten with real,
traceable numbers and the `synthetic` flag flips to `false`.
