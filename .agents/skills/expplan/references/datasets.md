# Dataset and benchmark selection

Read this file only during the dataset gate, before repository discovery or
HTML generation.

Treat dataset/benchmark selection as a separate human decision, not an
assistant inference hidden in Setup prose. After baselines are resolved and
before repository discovery or any `03` generation/re-generation:

1. Build a concise candidate slate from the confirmed references and selected
   baselines. Give each candidate a temporary conversation ID (`DS1`, `DS2`,
   ...), exact dataset/benchmark name and version when applicable, direct
   source and direct citation link, scientific role, compatible planned metrics, coverage gained,
   expected collection/reproduction burden, and any material access/license
   limitation. Do not discuss or choose train/dev/test splits here.
   Separate candidates visibly into (a) headline evaluation benchmarks, (b)
   mechanism/diagnostic datasets, and (c) construction corpora or baseline
   resources. Do not count all three categories as if each caused the same
   evaluation multiplier, but include their real collection, preprocessing,
   storage, and query burden in the recommendation.
   When matching the broader grounded literature's experiment breadth, compare
   and recommend the number of headline evaluation benchmarks against the
   strongest directly relevant papers' benchmark counts. Do not inflate this count with benign
   controls, diagnostic samples, retrieval corpora, or baseline-owned resources.
   List those supporting sources separately as analysis/method inputs, not as
   additional headline datasets.
   For every dataset/Claim pairing, audit the assumptions that make the
   dataset probative rather than merely topical. Record one structured
   `dataset_claim_applicability` entry with `dataset_name`, `claim_id`,
   `evidence_role`, `rationale`, and non-empty `required_conditions`. Each
   condition records `condition_id`, `statement`, an executable or inspectable
   `diagnostic`, a deterministic `acceptance_rule`, `assessment_status`
   (`VERIFIED_COMPATIBLE`, `PENDING_DIAGNOSTIC`, or `KNOWN_VIOLATION`), and a
   `failure_action` (`EXCLUDE_PRIMARY`, `RECLASSIFY_STRESS_TEST`,
   `NARROW_CLAIM`, or `PIVOT`). A pending condition also names its
   `diagnostic_result_target_ids`. Never use a known violation as PRIMARY
   evidence; an out-of-support dataset may remain as a stress test.
2. Mark each candidate `Required`, `Strongly recommended`, or `Optional`, and
   print the exact expansion of `required`, `recommended`, and `all` shortcuts.
   Before assigning tiers, estimate the full workload induced by
   `benchmarks × target models × baselines × conditions × repetitions/judges`.
   The `recommended` shortcut must be the smallest set that can support every
   approved headline and diagnostic claim within the rough budget; it is not a
   literature-coverage wishlist. More than two headline evaluation benchmarks
   requires an explicit non-redundancy justification and a feasible workload
   estimate. Prefer moving a redundant benchmark to `Optional` over silently
   multiplying the whole main table.
   Dataset shortcut IDs and their count refer to headline evaluation benchmarks
   only. Supporting diagnostic data and construction corpora require explicit
   provenance and burden notes, but must not be mixed into the shortcut as if
   they were full evaluation benchmarks.
3. Call `ask the user directly` and accept explicit IDs or one printed
   shortcut. Never silently add a candidate. If a Required dataset is omitted,
   show which claim/comparison becomes weaker and require explicit confirmation.
4. Summarize the exact selected dataset names and their role, then ask for a
   final `confirm datasets` when the preceding answer was not already an
   unambiguous explicit confirmation.
5. Stop until confirmation. Only after confirmation may repository discovery
   and HTML generation continue. Put selected dataset names directly in the
   Setup paragraph and result-table headers/captions. Do not create a dataset
   registry; record only a boolean/timestamp confirmation marker in the hidden
   contract because the visible tables remain the authority. In the generated
   HTML, link every selected dataset name in Setup, result-table headers/notes,
  and figure data-source tables to its original dataset/protocol paper or
   official repository; a dataset without a verified citation remains pending.

#### 7. Baseline decisions in the minimal HTML

Do not render baseline taxonomy, candidate overview, selection contract, reuse
audit, or omitted-baseline audit as separate visible sections. Preserve the
full resolved decision in the hidden contract. In the visible Projected Paper:

- selected experimental baselines appear directly as rows/series in the
  relevant result shells;
- cite every selected baseline directly in the Setup paragraph. Keep result
  table row labels, figure legends, and adjacent figure data-source tables as
  plain method names without repeated links. A generic control with no unique
  original paper links in Setup to the grounded paper whose protocol defines
  that control and is visibly labeled `control`;
- in that Setup prose, introduce what each selected dataset/benchmark measures
  and why it tests a named claim, and introduce what each baseline family does
  and why it supplies a distinct control or comparison role. Describe an
  individual baseline separately only when its role is unique. Do not emit an
  unexplained list of names or invent one paragraph per method mechanically;
- immediately after the Setup prose, show a two-column implementation table:
  `Method` and `How it is implemented`. Each row directly commits to one
  implementation. If verified official code will actually be used, name the
  reused modules, the local adapter work, and link the direct official GitHub.
  Otherwise say `Local implementation` and name the components implemented;
  show no implementation-source link. Never expose separate mode, source-type,
  reuse/write-boundary, shared-boundary, or fallback columns to the reader.
  Make the common execution architecture explicit inside each row: baselines
  are implemented in the same local model/data/trace/generation/evaluator
  framework as the proposed method, while official modules are integrated into
  that framework through an adapter. Label the proposed row visibly as
  `Our method — <name>` so it cannot be mistaken for another baseline.
  Paper links remain scientific citations in Setup and never appear as code
  sources. Store the identical row order plus the full engineering details as
  `implementation_contract` in the embedded contract so `$runplan` can inherit
  it without reinterpretation. Each record requires `implementation_summary`.
  Official-code records use `OFFICIAL_GITHUB` plus
  `SOURCE_GUIDED_REIMPLEMENT` or `REUSE_OFFICIAL_MODULE` and a verified direct
  GitHub URL. Every other record uses `SELF_IMPLEMENT`, `LOCAL`, and an empty
  `source_url`; `PAPER_SPEC` and `PAPER_GUIDED_REIMPLEMENT` are not valid
  implementation-source decisions. Keep `paper_url`, `repository_status`,
  `upstream_reuse`, `local_implementation`, `shared_boundary`, and `fallback`
  only in the hidden contract for grounding and execution checks;
- approved metrics/datasets/settings appear directly as columns, axes, or
  panels;
- in Setup, give every metric its provenance class (`DIRECT`, `ADAPTED`, or
  `PROPOSED`), canonical name, exact formula or evaluator rule, score range,
  decision threshold/cutoff when one exists, aggregation rule, definition
  source, and direct citation. A proposed metric cites its closest grounding
  protocol while remaining visibly marked `PROPOSED`. Store the identical
  definitions in `metric_contract`; a citation without the operational
  definition it supports is incomplete. Add per-claim `claim_mappings` with
  `DIRECT`/`PROXY`, construct, limits, alternatives, and required companions;
  one metric may play different roles across claims, but a proxy cannot alone
  establish a stronger headline construct;
- a reused reported number is marked in its exact future cell/caption as
  `Reported result reused from <paper/table>; not rerun in this project.`;
- an omitted Required baseline is mentioned only in the paragraph/limitation
  whose interpretation it weakens.

After baseline and dataset interactions plus metric decisions are resolved,
freeze those choices into the Projected Paper's result
shells. Do not invent a provisional baseline row or metric column before the
decision. Every selected baseline that is approved for a reported comparison
must appear in the appropriate shell row; every approved dataset/setting and
metric must appear in its columns (or an explicitly designed multi-level
header). Reuse annotations remain attached to the exact affected cells.
