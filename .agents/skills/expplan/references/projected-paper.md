# Projected paper, artifacts, and approval

Design the paper claim-first and backward from the projected abstract.
**Reader-facing opening — write the conference and reference first, then the projected paper.** Use `1. Target Conference and Reference Paper` for exactly two entries: target conference and the sole researcher-owned reference. Keep the official-rules link inside the target-conference entry. Do not include the research question, object of study, implementation architecture, datasets, metrics, baselines, or any other setup material there. Immediately follow it with `2. Projected Paper`, containing parts (a)–(c). Do not create later top-level report sections for claims, implementation, budget, or approval; those are contract concerns whose paper-facing consequences belong in the projected structure.

(a) **Projected Title + Abstract** — immediately **above the abstract, draft a working paper title** (`<h2>`-sized, styled as a title): a concrete, non-generic title naming the idea's ONE core mechanism (a short name + a claim-bearing subtitle is fine, e.g. "ABD++: One Modality-Invariant Harmful Axis for Deployable Jailbreak Defense"), not a topic label. It should read like a real paper title and match the idea's single mechanism — if the best honest title still sounds like "technique A applied to domain B", that is a signal the idea is a mashup (flag it, don't dress it up). Then the **projected abstract** — the abstract the paper *would* have if the idea succeeds, in her *Writing Style* (gap-first, "We propose/release" bullets). Mark **PROJECTED — not results**; every number a placeholder `[X%]`, never fabricated.
   - Derive a target length band from the venue's official abstract rule when one
     exists; otherwise use the confirmed researcher-owned reference's measured
     abstract length as the center of a reasonable band. Do not impose one universal
     word count. Require the complete rhetorical sequence: motivation · precise gap ·
     method · evaluation scope · 1–2 result-with-placeholder sentences · takeaway;
     an abstract below the band or missing a role is incomplete, not merely concise.
   - **No em-dashes, no rare words**; use common words and keep only genuine terms of art.
   - **abstract↔claim self-check:** map each abstract claim-sentence to a §1 claim; a sentence with no backing experiment gets cut or gets an experiment.
(b) **Projected Paper Blueprint (write right after the abstract, INSIDE `03`)** — show the paper that will be written, not merely a list of experiments. Use the confirmed researcher-owned paper already named and linked in Section 1. Model the target architecture on its section order, paragraph progression, and figure/table rhythm, while filling that architecture only with the current idea and independently grounded scientific content. Do not copy the reference paper's subject matter, claims, results, or prose.

For **every planned section and subsection**, enumerate every paragraph in
order. Use stable paragraph IDs such as `I-P1`, `RW1-P2`, `M2-P3`, `E3-P2`,
`D-P1`, and `C-P1`. In the visible HTML, each paragraph row contains:

- the stable paragraph ID;
- **one concrete sentence saying what that paragraph will write**;
- its relation to the previous and next target paragraph;
- the mapped reference paragraph text and a concise explanation of the logical
  move being imitated; the reference text may be collapsible but must remain
  available to the browser writer;
- the artifact ID it introduces or interprets, only when applicable.

Subsection structure is part of the executable blueprint, not decoration.
Store each subsection title on its first paragraph as `heading`, with
`heading_style: subsection`; leave both fields empty on continuation
paragraphs. Method, Experiments/Evaluation, and Discussion/Analysis must use
these explicit boundaries whenever they contain multiple logical parts, so the
browser writer and final LaTeX preserve the approved hierarchy automatically.

The sentence must name the actual topic and argumentative move, not a generic
label such as “introduce the method” or a bundle of bullets disguised with
semicolons. It should be specific enough that the paragraph-writing API can draft the
paragraph from it, while remaining a plan rather than fabricated final prose.
Use exactly one grammatical planning sentence per paragraph row. Keep stable
source paragraph IDs, complete source text, source heading, source rhetorical
purpose, adaptation note, target rhetorical role, claims/variables,
evidence/citations, neighbor relations, and artifact bindings in that
paragraph's `paper_outline` record. The mapping may be many-to-one or
one-to-many; every target paragraph must have at least one mapped source
paragraph.

Do this for **all** sections, not only the Introduction: Abstract;
Introduction; each Related Work subsection; each Method subsection; every
Experiments subsection including setup prose, main results, ablations,
sensitivity/robustness, cost, qualitative/failure analysis; Discussion,
Limitations/Ethics when applicable; Conclusion; and planned appendices. For
Method paragraphs, additionally list inputs, outputs, variables, raw fields,
and evidence grade (`claim-grade`, `pilot-only`, `smoke-only`, or
`unavailable`). Mark the entire blueprint PROJECTED and keep unknown prose
numbers as `[X%]`.

Within the projected **Method** section, add one visible block marked
`data-model-design`. It must be detailed enough for the later browser writer to
draft the method without reverse-engineering scattered plan fields. Cover:

- inputs, outputs, and the end-to-end information flow;
- every named module and its responsibility;
- training phases and the boundary between trainable, frozen, teacher, and
  reference components;
- the objective/loss terms and any selection, aggregation, routing, or dynamic
  weighting equations that determine behavior;
- the inference path, including components used only during training;
- a component-to-evidence list naming the ablation, diagnostic, sensitivity,
  or result artifact that can weaken or falsify each material design claim.

Make this block concise but reproduction-grade: normally one 8--14-row table
or 250--500 English-word equivalent. It must contain an executable ordered
algorithm, define every symbol, state candidate/sampling construction,
preprocessing, objective normalization and parameter-update rules, list the
source-disclosed model-defining hyperparameters, and distinguish trainable,
frozen, teacher, and reference components. Put all source-undisclosed choices
in one explicit `Unknowns for exact reproduction` row and set
`reproducibility_status` to `partial_due_to_source_omissions`; never guess them.
Omit repeated motivation, results, and extended rationale from this block.

Mirror this exact specification in `grounding.model_design`; the visible block
and hidden contract may differ in presentation but not in scientific content.
Do not count this prose/table block as a result artifact. A generic pipeline
summary, method-module inventory without interactions, or conceptual-figure
caption does not satisfy the requirement.

For a **one-goal-paper reconstruction**, populate the block only from the goal
paper's verified full text, equations, captions, and method figures. Record the
goal paper as `source_authority`, label unreported implementation choices as
unknown, and do not borrow method content from the structural reference. The
structural reference remains limited to paragraph logic and figure/table
rhythm. Inspect the goal paper's equations, algorithm, implementation details,
appendices, captions, and method figures before judging reproducibility.

The visible order must begin with Abstract/Introduction and follow the target
paper from front to back. Experiment numbering belongs only inside the planned
Experiments section. In that section, show a clearly labeled experimental
setup block covering the concrete dataset/version, model, evaluation protocol,
metrics, seeds, and comparison rules. Follow it with a two-column **Baseline
Selection and Implementation** table that explains why each baseline is
selected and exactly how it and the proposed method will be implemented. Then
place all `[PENDING]` result tables and figure source tables at the paragraphs
that will introduce or interpret them. Never place `5.1 Setup` or `5.2 Results`
before the Abstract merely to satisfy a validator.

The setup block is a compact index, not manuscript prose or a registry dump.
Render exactly six rows in `<table class="setup-table">`: `Dataset`, `Model`,
`Baselines`, `Proposed method`, `Noise and runs`, and `Metrics`. Begin Dataset,
Baselines, and Proposed method values with their explicit counts. Do not add
setup paragraphs before or after this table. In the implementation table, use
one row per selected baseline plus one row for the proposed method; keep each
decision to one concise sentence or clause sequence and attach the supporting
paper link in the relevant baseline row. Full metric formulas and machine
provenance belong only in the embedded contract; method-defining equations
belong in the Method model-design block above when needed for an unambiguous
design.

## Routed details

Read [artifact-shells.md](artifact-shells.md) while defining count-only figures,
empirical figure/table shells, source tables, spans, fixtures, and the artifact
ledger.

Read [page-fill-and-contract.md](page-fill-and-contract.md) while checking venue
coverage, serializing the embedded contract, assigning identifiers, and
presenting the approval gate.
