## Disruptive wildcard (opt-in; default off)

The standard profile · literature-gap slate is the primary output. The wildcard runs
**only when the user explicitly asks** (`— disruptive-wildcard: on` or a plain-language
request for a disruptive/paradigm-breaking idea). When on, append at most ONE
evidence-tethered survivor (`D1`) after the standard cards in the **same report** — never a
standalone disruptive report, and never merge the disruptive and standard rankings (their
scores mean different things). **When on, read
[`references/disruptive-branch.md`](references/disruptive-branch.md) completely before A1
and follow it as mandatory procedure** — it holds the full method (honesty boundary, D0
Route Gravity Map, D1–D3 blind incubation, D4 absorbability, D5 scoring, required report
fields). The steps below carry only one-line pointers into it.

## Step 1 — Lock MODE + direction + wildcard first
The mode decides what *kind* of standard contribution is generated; the wildcard switch decides whether one disruptive outlier is incubated and appended. Fix mode + direction BEFORE anything else — never infer silently, never start A1 first. **The wildcard defaults to `off`**: run it ONLY when the user explicitly passed `— disruptive-wildcard: on` or asked in plain language for a disruptive / paradigm-breaking / wildcard idea. Do NOT ask an ask the user directly about the wildcard and do NOT turn it on by default. If `— lens:` was passed use it; else **ask the user directly** for the missing values: mode (engineering = iterate habitual methods, reuse code · benchmark = survey / new dataset-eval / reproduce-and-beat · theory = a hypothesis/bound on the method-evolution fault line) and `<direction>` (offer her *Niche subfields* if none given). Only once mode + direction are fixed do A0/A1/A2/A3 run (A2 runs only if the wildcard was explicitly turned on).


## Step 2 — Ethics triage (conditional; do not create unnecessary prompts)
After direction and mode are fixed, screen the direction and every candidate idea for **material ethical risk**. This is a conditional annotation pass, not a generic disclaimer.

Flag only when the proposed research directly studies, predicts, manipulates, exposes, or deploys systems affecting people, communities, or socially consequential decisions. Trigger the screen for: human participants, consent or deception; children, patients, vulnerable groups, protected classes, or unequal outcomes; personal, sensitive, private, mobility, biometric, health, or re-identification data; political persuasion, public-opinion manipulation, polarization, propaganda, social influence, or mass behavior intervention; surveillance, profiling, high-stakes decisions, safety-critical deployment, or automated decisions about people; or dual-use capabilities with foreseeable harmful misuse.

Do **not** flag a generic method, dataset-free simulation, or ordinary model evaluation merely because it uses `agent`, `social`, `safety`, or `simulation`. If no concrete pathway is present, do not ask an ethics question and omit all ethics output from the report.

For each flagged candidate, assign exactly one level: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`, based on foreseeable harm, affected-party vulnerability, data sensitivity, scale, reversibility, and ease of misuse. Keep ethical risk separate from technical feasibility and publication risk. Do not make a legal or IRB determination without a verified source; use `[REQUIRES IRB/ETHICS REVIEW]` when institutional review may be required.

Each flagged card must include an **Ethics assessment** covering: affected parties and context; concrete harm pathways; data, consent, retention, and de-identification; misuse and dual use; safeguards; and residual risk/uncertainty. Do not invent laws, consent status, incidents, or empirical harms. Ethics is an annotation and human decision gate, never an automatic rejection.
