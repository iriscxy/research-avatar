# Research Avatar: A Personalized Research Assistant

Research Avatar is a lightweight, personalized research assistant for experienced researchers. It is not a fully autonomous AutoResearch system and does not replace research judgment.

> **Let the assistant accelerate mechanical work while you retain control of important research decisions. Every acceleration step is adapted to your research taste, writing style, and experimental habits.**

---

[Online paper writing: register, upload, and start writing](https://research-avatar-studio.yingtaomj.workers.dev/)

---

## Highlights

- **Researcher control:** The system reads a researcher profile, the researcher selects the overall direction, and the assistant executes the approved work.
- **Personalization:** Configuration is grounded in the researcher's own profile rather than generic defaults.
- **Experiments:** The system derives experiments from paper requirements, decomposes them into verifiable goals, and keeps every reported number traceable.
- **Paper writing:** An interactive workspace follows the researcher's writing style and produces editable figures and tables.

### How it differs from AutoResearch

| Dimension | Common open-source AutoResearch focus | Research Avatar focus |
|---|---|---|
| Human-agent roles | End-to-end automated exploration | **The researcher approves the global plan before automatic execution** |
| Personalization | Task context and generic configuration | **Scholar profile plus working habits** |
| Literature review | Large collections of papers, abstracts, and isolated observations | **A concise field map organized around four decision-relevant dimensions** |
| Experiment organization | Search and execution from a task objective | **Ordered, independently verifiable goals** |
| Paper output | Automatic synthesis of intermediate results | **Writing adapted to the researcher's personal style** |

---

## Prerequisites

Before first use, manually save the complete HTML of a Google Scholar profile. Then provide its local path to `$profileconstruct`, for example:

```text
$profileconstruct using ~/Downloads/scholar_profile.html
```

You may use your own Scholar page or the page of a researcher whose research taste and paper organization you want to study.

Paper writing requires an LLM API. Configure the selected provider in a local terminal before use:

```bash
# Required for OpenAI
export OPENAI_API_KEY="your API key"

# Required for DeepSeek
export DEEPSEEK_API_KEY="your API key"
```

---

## Recommended workflow

Invoke the following research workflow from a coding agent in a terminal:

`$profileconstruct` -> `$researchlit` -> `$ideagen` -> `$expplan` -> `$runplan`

Each stage is visualized at <http://127.0.0.1:8780>. After completing the workflow, continue drafting in the paper-writing workspace on the same page.

## Implementation

### Personalization

The authoritative personalization artifact is:

```text
researcher-profile/PROFILE.html
```

`$profileconstruct` reads the researcher's Google Scholar publication list and uses available coding-agent history to extract experimental environments and working habits.

The profile contains:

- **Research Identity / Lineage:** research identity and the development of research themes;
- **Writing Style:** abstract-level argument structure, method naming, and contribution framing, plus document-level section organization and figure/table conventions;
- **Experiment Templates:** common launchers, training frameworks, base models, GPU configurations, and historical out-of-memory records;
- **Workflow Preferences:** habits such as starting with low-cost steps, caching intermediate results, and making experiments resumable.

The researcher chooses the Scholar profile. Local working habits still come from the current user.

### Experiments

1. **Plan the paper before deriving experiments.** Draft the expected abstract and paragraph architecture, then bind every claim to an experiment, metric, and fillable figure or table.
2. **Decompose the plan into verifiable goals.** Execute goals in dependency order, verify their completion criteria, and update result artifacts.
3. **Keep every number traceable.** Each result links to its raw record, execution command, calculation procedure, and verification status.

### Paper writing

1. **Two drafting modes.** Use the approved Experiment Planning architecture to generate a complete first draft or draft one paragraph at a time.
2. **Interactive paper workspace.** Generate and edit paragraphs, inspect reference structure and vector PDF previews, and write to LaTeX transactionally only after explicit acceptance.
3. **Personalized writing style.** Follow the target venue, the researcher's Writing Style, and document-level citation and logic checks.
4. **Publication-ready figure prompts.** Design a composition and convert it into editable PowerPoint and PDF artifacts.
5. **Real experimental figures and tables.** Read only traceable data under `results/`.

---

## Skills

| Skill | Purpose |
|---|---|
| `$profileconstruct` | Create or refresh the researcher profile from Google Scholar and available session history |
| `$researchlit "research topic"` | Retrieve and verify literature from several angles and create a structured survey |
| `$ideagen` | Generate and verify candidate ideas from the approved evidence base |
| `$expplan` | Plan the Projected Paper paragraph by paragraph and derive its experimental contracts |
| `$runplan` | Decompose the experiment into dependency-ordered executable goals |

Unless translation is explicitly requested, `$researchlit` does not call a translation API. The researcher must specify a target language before translation.

Paper writing is not started by a skill. The paper stage in Research Studio reads the approved architecture, structural reference, and experimental results, then calls the selected LLM API paragraph by paragraph in the browser before writing accepted content to LaTeX.

---

## Deliverables

Deliverables are organized into four groups:

```text
paper/
├── main.tex                 # 1. Paper: editable LaTeX source
└── main.pdf                 #    Compiled paper
results/                     # 2. Experiment results, raw records, metrics, and provenance
code/                        # 3. Reproducible code produced for each experiment goal
reports/
├── 01_LIT_SURVEY.html       # 4. Literature survey
├── 02_IDEA_REPORT.html      #    Idea selection report
├── 03_EXPERIMENT_PLAN.html  #    Experiment plan
├── 04_RUN_PLAN.html         #    Resumable run plan and goal status
└── 05_EXP_RESULT.html       #    Human-readable experiment results
```
