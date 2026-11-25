# Scientific integrity contract

Use this contract while turning the selected idea into testable Claims,
measurements, and result requirements. Work backward from each Claim:

- Give each Claim a stable ID, precise scope, decisive falsifier, and a chain
  from observable to raw field, computation, and metric.
- Distinguish direct measurements from proxies. Narrow an unsupported Claim or
  add a companion direct test or control.
- Ground baselines, datasets, metrics, and protocols in retrieved experimental
  sections and result tables, not memory or titles.
- Mark variables `DIRECT`, `ADAPTED`, or `PROPOSED`; a proposed variable needs
  a feasibility check before it supports a headline Claim.
- Include Claim-complete baselines, ablations, robustness or sensitivity,
  failure analysis, and cost evidence.
- Record result-changing choices as `SEARCHED`, `FIXED_BY_SOURCE`,
  `FIXED_BY_DESIGN`, or `NOT_APPLICABLE`. `$runplan` owns execution splits and
  dev/final freezing; `$expplan` does not choose train/dev/test splits.
- Give every result target exactly one source action: `RUN_LOCAL` or explicitly
  approved `REUSE_REPORTED`.

Set `scientific_integrity_version=3` and enforce the following contracts.

## Metrics and gold state

Every metric records its unit, evidence source (`BENCHMARK_LABEL`,
`MODEL_OUTPUT`, `SYSTEM_TRACE`, `HUMAN_ANNOTATION`, `LLM_JUDGE`, or `DERIVED`),
raw input fields, executable calculation, implementation entrypoint, and
protocol checks. Claim-side `metric_ids` and metric-side `claim_mappings` are
exact inverses; do not bind every metric to every Claim for convenience.

Register a `gold_standard_contract` whenever a metric compares predictions
with gold state. The gold source is an official benchmark label, real human
annotation, or independent executable oracle. Its implementation entrypoint,
input/output schemas, fixtures, and conformance command remain distinct from
every evaluated method. A method output cannot create the labels used to claim
that the same method is superior. Reference-implementation conformance is not
an empirical performance contribution.

Every metric has a structured numeric `valid_range`, `sampling_unit`,
`comparison_population_id`, input schema, and aggregation contract containing
the estimator, resampling unit, interval, and repetitions. Difference metrics
admit the full signed domain. Timing metrics consume saved timing fields and
have no arbitrary accuracy-like upper bound. Measurements may support the same
Claim only when their population IDs match or an approved alignment rule makes
them commensurate.

## Claim outcomes and dataset applicability

Every Claim has a deterministic `outcome_rule`. A tie, missing value, interval
crossing the registered null, or failure to meet the registered margin becomes
`inconclusive` or `weakened` as specified, never automatically `supported` by
an LLM judgment. Preregister the authorized action for `supported`,
`weakened`, `falsified`, and `inconclusive`; a non-continue action is a real
execution boundary.

Create a structured `dataset_claim_applicability` record before assigning a
dataset to a Claim. Record its evidence role, every required method or
identification condition, diagnostic and acceptance rule, current assessment,
and failure action. A known violation cannot be `PRIMARY` evidence. A pending
diagnostic owns explicit result targets that `$runplan` executes before the
dataset supports the Claim. Treat extreme extrapolation or
assumption-violating data as `STRESS_TEST_ONLY` rather than headline evidence.

## Human evidence, implementations, and protocols

A human-named construct requires a real `HUMAN_ANNOTATION` contract with
annotator count, item count, blinding, rubric, annotation file, and agreement
calculation. An LLM judge is `LLM_JUDGE`, never human agreement.

Every baseline and proposed method has an `implementation_verification` record
that names the protocol source, required algorithmic components, and
conformance tests. `method_name_in_model_prompt` is false: putting a baseline
name in a model prompt is not an implementation of that baseline.

Represent a project-created unpublished dataset as `SELF_BUILT_UNPUBLISHED`,
with a collection/versioning contract and no external dataset URL. Never
fabricate a publication or repository link.

Every published or public benchmark carries a structured `protocol_contract`
with the official split source, prompt or input source, scorer source, a small
conformance fixture, and its executable conformance command. A title or prose
statement that the protocol is followed is not protocol evidence.
