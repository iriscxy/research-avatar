# Research Avatar: A Personalized Research Assistant

Research Avatar gives experienced researchers personalized assistance that speeds up mechanical work while keeping key decisions yours, not a fully autonomous AutoResearch system. Every step follows your research taste, writing style, and experiment habits, learned from your Scholar profile. Try it online: [register, upload, and start writing](https://research-avatar-studio.yingtaomj.workers.dev/)

---

## Highlights

| | Common open-source AutoResearch | Research Avatar |
|---|---|---|
| 🧑‍🔬 **Human-agent roles** | End-to-end automated exploration | You approve the global plan before automatic execution |
| 💡 **Idea generation** | Generic brainstorming from a topic | Ideas tailored to your profile and the field map |
| 🧪 **Experiment organization** | Search and execution from a task objective | Verifiable goals executed through your coding agent's `/goal`, improving as the agent does; every number traceable |
| ✍️ **Paper output** | Automatic synthesis of intermediate results | Writing adapted to your personal style |

---

## See it in action

**1. Researcher profile.** Your research lineage and current frontier are extracted from your own publications, and every later stage builds on them.

![Research lineage extracted from the researcher's publications](docs/images/real-1-profile.png)

**2. Idea selection.** Each candidate is screened against the closest published work, with a concrete difference, the strongest objection, and a confidence level; you make the final choice.

![Decision slate with linked closest work](docs/images/real-3-ideas.png)

**3. Experiment plan.** Every projected figure comes with the source table that experiments must fill; no value is shown until it is measured.

![Projected figure and its pending source table](docs/images/real-4-experiment-plan.png)

**4. Paper writing.** Draft paragraph by paragraph, with the writing plan matched from the reference paper beside each paragraph and a live LaTeX PDF on the right.

![Paper Studio writing workspace](docs/images/real-paper-writing.png)

---

## Tutorial

**1. Prepare your inputs.** Save the complete HTML of a Google Scholar profile. You may use your own page, or that of a researcher whose research taste and paper organization you want to study. Paper writing also needs an LLM API key; set the one for your provider in a local terminal:

```bash
# Required for OpenAI
export OPENAI_API_KEY="your API key"

# Required for DeepSeek
export DEEPSEEK_API_KEY="your API key"
```

**2. Build your profile.** In a coding agent, run:

```text
$profileconstruct using ~/Downloads/scholar_profile.html
```

**3. Run the workflow.** Invoke the stages in order from the same coding agent:

`$researchlit "research topic"` -> `$ideagen` -> `$expplan` -> `$runplan`

Each stage stops for your approval before the next one starts.

**4. Follow along and write.** Open <http://127.0.0.1:8780> to inspect every stage. When the experiments are done, continue in the paper-writing workspace on the same page.

---

<details>
<summary><h2>Implementation</h2></summary>

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

</details>

---

## Skills

| Skill | Purpose |
|---|---|
| `$profileconstruct` | Create or refresh the researcher profile from Google Scholar and available session history |
| `$researchlit "research topic"` | Retrieve and verify literature from several angles and create a structured survey |
| `$ideagen` | Generate ideas tailored to your profile (research lineage, past publications) and the literature field map, then verify novelty |
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
