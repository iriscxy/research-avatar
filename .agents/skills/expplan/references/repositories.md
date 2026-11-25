### Repository candidate registry, interactive selection, and grounding contract

For the primary reference, the human-selected baselines, and implementation-critical modules, identify useful repositories from paper/project links, official author repositories, repository links found in retrieved full text, web search results, and any public GitHub URL, private Git URL, or local path supplied by the researcher. Repository discovery is a recommendation step, not proof that code is correct, complete, compatible, or runnable.

#### 0. Mandatory source-code architecture audit — before repository selection

Repository names and README claims are not enough to decide how the project
will be implemented. Before recommending repository selections, clone or open
every serious implementation candidate and read the relevant source code. At a
minimum inspect its executable entry points, core algorithm implementation,
model/provider abstraction, data interface, evaluator/metric interface,
configuration system, result schema, tests, dependency manifests, and license.
Also search for import-time side effects, global clients/files, hard-coded
models or paths, embedded credentials, demo values that override function
arguments, stale provider APIs, and assumptions that conflict with the
approved datasets, metrics, or target models. Record exact files and a pinned
commit when available. Static source inspection at this gate establishes an
architecture recommendation, not runnability; execution remains a later
`/goal` verification duty.

Use that evidence to compare these three project architectures explicitly:

1. build one local unified experiment framework and implement or adapt every
   method behind common model, data, evaluator, trace, and result interfaces;
2. extend one selected baseline repository as the project's primary framework;
3. execute baseline repositories independently with their native pipelines and
   implement the proposed method separately, normalizing results afterward.

Recommend exactly one architecture. A hybrid must still be assigned to one of
the three by naming what owns the shared execution and result contract. For
each selected baseline or module, state whether the implementation will be:
direct package reuse, a thin adapter around pinned upstream code, a local
reimplementation from the paper/source because upstream is unsuitable, or an
unchanged standalone run. State which code owns the proposed method. Never
infer that one baseline should become `PRIMARY_BASE` merely because it has the
most complete README or the easiest command line.

Present the source-backed architecture decision to the researcher, including
the decisive code findings and the exact per-baseline reuse boundary, and ask
them to `confirm architecture` or revise it. **STOP until the researcher
explicitly confirms the architecture.** Only then proceed to repository ID
selection, manual additions, and the repository grounding contract. Store the
confirmed architecture, source-audit evidence, shared interfaces, and
per-repository reuse boundaries in the hidden experiment-plan contract; do not
render a separate audit section in the final HTML.

#### 1. Build the complete repository candidate registry

Assign stable IDs `R1`, `R2`, `R3`, ... in recommendation order. Classify each candidate by its main implementation purpose:

- **Baseline implementation**;
- **Data / preprocessing**;
- **Evaluation / metrics / evaluator**;
- **Method-module reference**;
- **Training / serving / infrastructure**.

A repository may have secondary purposes, but it must have one primary purpose so that the researcher can understand why it is being recommended.

Maintain these internal fields for every candidate:

- repository name and direct link or local/private path;
- related paper, selected baseline, protocol, dataset pipeline, evaluator, or method module;
- primary purpose and secondary purposes;
- discovery source;
- official / author-provided / community / user-provided status;
- recommendation priority: `Preferred`, `Supplementary`, or `Background`;
- intended implementation scope;
- verification status: `paper-linked`, `metadata-checked`, `user-provided`, or `not verified runnable`;
- visible license, otherwise `pending`;
- visible branch/tag/commit, otherwise `to pin during /goal execution`;
- known environment/dependency notes;
- compatibility risks and fallback.

Keep all repository candidate/audit fields for the decision meeting and hidden contract; do not render candidate or audit tables in the final HTML.

Do not claim that a repository is runnable, paper-faithful, complete, compatible, or safe to reuse unless a later `/goal` pins a revision and verifies it. Do not silently treat every recommended repository as implementation authority.

#### 2. Mandatory interactive repository selection

Repository selection must happen **during the `$expplan` conversation, after the baseline contract is resolved and before the HTML is written**. The HTML records the decision; it is not the interface used to collect the decision.

1. **Show all repository candidates.**

   Group candidates by primary purpose and use a concise format:

   `R1. org/repo — purpose: evaluator — grounds: B4 / metric protocol — priority: Preferred — status: author-provided — verification: paper-linked`

   Include all candidates that may reasonably help implementation. If no useful repository is found, say so and continue directly to the manual-addition question.

2. **Ask the repository-selection question with `ask the user directly`.**

   Accept:

   - `R1,R3` or `1,3` to select specific repositories;
   - `all` to select every listed repository except those marked `Background`;
   - `none` to proceed without selecting a recommended repository.

   Multiple selections are allowed; never select a repository merely because it was recommended. Handle unknown IDs, contradictory forms such as `all,none`, or ambiguous prose by clarifying rather than guessing (same interaction guardrails as baseline selection).

3. **Ask the manual-addition question with `ask the user directly`.**

   Accept:

   - `none` / `no`;
   - one public GitHub URL per line;
   - one private Git URL per line;
   - one local project path per line;
   - an optional intended scope after `#`, for example:
     `/data/home/user/project # primary implementation base; reuse data pipeline and evaluator`.

   Assign stable IDs `M1`, `M2`, ... to manual additions. A repository or path explicitly supplied as an implementation reference is selected, but a URL merely mentioned as background is not automatically selected.

#### 3. Resolve an exact repository grounding contract

For every selected `R*` or `M*` reference, propose and resolve:

- exactly one **use mode**:
  - `PRIMARY_BASE`: the project or repository that the executing `/goal` should extend as the main implementation base;
  - `VERIFY_AND_USE`: clone/materialize, pin a revision, smoke-test, then use only for the approved scope;
  - `REFERENCE_ONLY`: inspect design/configuration/code, but do not execute it or copy it wholesale;
- one or more **allowed scopes**:
  - baseline implementation;
  - data/preprocessing;
  - evaluator/metric protocol;
  - method module;
  - training/serving infrastructure;
- an explicit **prohibited scope**, especially when only one component is authoritative;
- an **integration target** in the planned project;
- an **authority / precedence rule** when multiple selected references cover the same scope;
- an execution verification checklist for the relevant `/goal`;
- a fallback if verification fails.

After proposing these contracts, ask one compact `ask the user directly`:

- `approve repository contract`;
- or revisions such as
  `R4=PRIMARY_BASE; R1=REFERENCE_ONLY evaluator only; M1=data-pipeline authority`.

If two selected repositories claim authority over the same data pipeline, evaluator, baseline implementation, or module and no precedence is clear, the conflict must be resolved before HTML generation. Never merge conflicting implementations silently.

#### 4. Required `/goal` execution verification checklist

A selected repository is still **not verified runnable** at `$expplan` time. For every `PRIMARY_BASE` or `VERIFY_AND_USE` reference, the contract must require the executing `/goal` to:

- pin and record the exact commit/tag/revision;
- inspect license and redistribution constraints;
- inspect environment and dependency compatibility;
- run the smallest available smoke test;
- verify data-pipeline and evaluator behavior when those are approved scopes; do not add split selection or verification to `$expplan`;
- record files/configs actually reused or modified;
- keep user code and upstream code distinguishable;
- fall back to the approved alternative if verification fails.

`REFERENCE_ONLY` repositories do not need to be executed, but the executing `/goal` must record which design, configuration, or code location was consulted.

#### 5. Repository decisions in the minimal HTML

Do not render repository candidate, audit, or grounding-contract tables. Keep
the resolved selected references, use modes, scopes, precedence, verification,
and fallbacks in the hidden contract for `$runplan`. Only references selected
there may guide later execution; unselected candidates remain background.
Mention a repository visibly only when a projected-paper paragraph or artifact
caption genuinely needs to identify an implementation/evaluator source.
