# PROFILE_AUTO — Xiuying Chen

> **Single source of truth** for the research buddy pipeline. English is canonical
> (tool-read); a human-facing Chinese mirror lives in `PROFILE_AUTO.zh.md`. All skills
> (`/research-lit`, `/ideagen`, `/workplan`, `/run-plan`, `/paper-write`) read this file.

| | |
|---|---|
| **Source** | Google Scholar (`mine.html`, exported 2026-07-05) |
| **Name** | Xiuying Chen |
| **Affiliation** | MBZUAI (Mohamed bin Zayed University of Artificial Intelligence) |
| **Stated interests** | Trustworthy NLP · Human-Centered NLP · Computational Social Science |
| **Citations (all)** | 5862 · **h-index** 32 · **i10** 77 |
| **Publications** | 131 (2018–2026) — complete page, **not truncated** ✅ |
| **Generated** | 2026-07-05 |
| **Corpus coverage** | abstracts **108/131**, local full-text **108/131** (the 23 without are conference-/journal-only papers with no arXiv version — recorded honestly, never fabricated) |

---

## Research Identity

Your record traces a clean two-act arc — from a **first-author text-generation methodologist**
into a **senior/corresponding author leading a trustworthy-and-social-LLM group** at MBZUAI.
You are first author on **22 papers (2018–2025)**; most 2024+ works place you as
senior/corresponding author over student first-authors (Gao, Wang, Guo, Song, Zhang, …).

Your three stated interests map onto three concrete, active clusters:

- **Trustworthy NLP** — jailbreak analysis & defense (safety-boundary / Activation-Boundary
  Defense, **AJailBench** audio jailbreak), LLM watermarking (**Invisible Entropy**), bias
  diagnosis (**BiasLens**, medical-fairness text generation), unlearning (**D²**), and the
  **TrustGen / trustworthiness** survey line.
- **Computational Social Science** — LLM-driven social simulation: fake-news evolution &
  propagation (**FUSE**, **FPS**, **TruEDebate**), echo chambers & opinion dynamics
  (**Decoding Echo Chambers**), influencer marketing (**SAGraph**, **TIS**), and social-reasoning
  benchmarks (**SocialMaze**, Werewolf social-deduction).
- **Human-Centered NLP & Interpretability** — dialogue/personalization, medical & scientific
  LLMs (**SkinGPT-4** and multimodal dermatology, *Nature Communications*; **MedAGI**;
  **ScholarChemQA**; **AutoBA** omics agent, *Advanced Science*), and mechanism-level
  interpretability (**Emotion Circuits**, **Cylindrical Representation Hypothesis**,
  word-form / Typoglycemia analysis).

Underpinning all three is your **foundational lineage in text summarization & generation**
(abstractive / timeline / multimodal / faithful summarization, dialogue response generation,
retrieval-augmented generation), which is where your most-cited first-author work sits.

**Task-type mix (auto-classified, 131 papers):** engineering **83** · benchmark **35** · theory **13**.
The mix shifts sharply by era — **early (<2022): 20 engineering / 2 benchmark** (pure method
era); **recent (2024+): 40 engineering / 28 benchmark / 12 theory** — i.e. you increasingly ship
**benchmarks and mechanism-level analyses** alongside methods.

**Signature / most-cited works** (citation counts from Scholar, 2026-07-05):
- *LLM-based Multi-Agents: A Survey* (IJCAI 2024) — **2011** cites (field-defining survey)
- *Opportunities & Challenges for ChatGPT/LLMs in Biomedicine and Health* — **531**
- *SkinGPT-4 / pre-trained multimodal LLM for dermatology* (**Nature Communications**) — **259 + 75**
- *Lift Yourself Up: Retrieval-Augmented Generation with **Self-Memory*** (NeurIPS 2023) — **205**
- *Injecting Domain-Specific Knowledge into LLMs: A Survey* (EMNLP Findings) — **150**
- *VMSMO: Multimodal Summary for Video-based News* (EMNLP 2020) — **116**
- *AutoBA: AI agent for automated multi-omic analyses* (**Advanced Science**) — **100**

**Active venues (last 3y):** ACL / EMNLP / NAACL (main + Findings), NeurIPS, ICML, ICLR,
IJCAI, SIGIR, AAAI, COLING — plus high-impact **journals** (*Nature Communications*, *Briefings
in Bioinformatics*, *Advanced Science*, TOIS, IEEE TKDE), reflecting the medical/scientific-LLM
strand.

**Niche subfields (ranked by recent volume × recency):** (1) LLM agents & multi-agent
systems · (2) LLM social simulation / computational social science · (3) trustworthiness &
safety (jailbreak / bias / watermark / unlearning) · (4) LLM interpretability & mechanism
discovery · (5) medical & scientific LLMs · (6) the enduring text-summarization / generation base.

---

## Research Lineage

- **Origin (2018–2021) — text generation & summarization methodologist.** First-author
  neural summarization and dialogue: abstractive summarization with reader comments (RASG,
  AAAI 2019), abstractive **timeline** summarization (IJCAI 2019), **VMSMO** multimodal
  video summary (EMNLP 2020), iterative/extractive summarization, sticker-response selection,
  e-commerce QA & product generation. Signature move even then: **name a model, release a
  large real-world dataset, validate with automatic + human eval.**
- **Evolution (2022–2023) — faithfulness, structure, and retrieval.** Faithfulness-enhanced
  summarization (FES, NeurIPS 2022), citation-graph / scientific-paper summarization,
  related-work generation (TAG), robustness (SummAttacker), and **retrieval-augmented
  generation with Self-Memory** (NeurIPS 2023) — the bridge from bespoke seq2seq into the LLM era.
- **Frontier (2024–2026) — trustworthy, social, and interpretable LLMs, as a group lead.**
  LLM agents & multi-agent systems (the 2k-cite survey; MACRS, DyFlow, MMAC-Copilot), social
  simulation (fake news, echo chambers, influencer marketing, SocialMaze), safety/trust
  (jailbreak, audio-jailbreak, watermarking, BiasLens, TrustGen), interpretability (emotion
  circuits, cylindrical representation), and medical/scientific LLMs. Output diversifies from
  pure methods into **benchmarks + mechanism analyses**.

---

## Writing Style

Mined across ~100 of your abstracts — the pattern is remarkably consistent and highly reusable
by `/paper-write`:

- **Argument arc: gap-first, not landscape-first.** Open with the task's importance in one or
  two sentences → pivot on **"However, …"** to a concrete limitation of prior work → **"Hence,
  in this paper, we propose …"** a named method. You rarely open with a broad literature survey.
- **Two-challenge framing.** Problems are very often decomposed into exactly two named
  challenges (*"Two main challenges are confronted… One is… Another is…"*), each then mapped to
  a module of the method.
- **Always name the method.** Nearly every paper introduces a pronounceable acronym
  (UTS, PESG, DAHG, MPAG, FES, TAG, SRS, PESRS, MoeSumm, SSG, DIMS, RASG, ITS, UMSE, QUIDS,
  DrICL, BiasLens, DyFlow, …). Method = named artifact.
- **"Concretely / Specifically, …"** introduces the mechanism, walking module by module.
- **Evaluation cadence.** Close on *"Extensive experiments conducted on … show that our model
  achieves state-of-the-art performance in terms of both automatic metrics and human
  evaluations,"* frequently followed by **"We release our large-scale dataset"** and, recently,
  **"We hope our work inspires further research on …"**.
- **Contribution phrasing** is compact and mechanism-anchored rather than claim-inflated;
  ablations "demonstrate the effectiveness of each module."

**How `/paper-write` should apply it:** gap-first intro; name the method; two-challenge → two-module
mapping; both automatic + human eval; dataset release when applicable; the closing "we hope…"
sentence. Keep ≤3 self-citations and run the anti-self-plagiarism check against this corpus.

---

## Experiment Templates

*Mined by `experiment_history.py` from **476 coding-agent sessions** across all
`~/.claude/projects/*` (64,940 lines scanned). Source: `habits.json`. **Adopted directly per
your confirmation (2026-07-05)** — these are machine-level coding habits on your working
environment, independent of the researcher identity above. Heuristic text scan; high-count
items are clean signal. Hyperparameter VALUES (lr/batch/epochs/seed) are intentionally NOT
mined — they are task-determined and decided by `/workplan`.*

**Habitual stack** (generated experiment code should match this — NOT the hyperparameters):
- **Launcher:** `deepspeed` (dominant, 171) › `srun` (78, Slurm) › `accelerate launch` (60) ›
  `modal run` (34) › `torchrun` (32) › `sbatch` (14). Default to DeepSpeed multi-GPU.
- **Framework / deps:** PyTorch-**Lightning** (top dep, 8509) + **TRL** (1367) + **vLLM** (996,
  inference) + `accelerate` (695) + `torch` (546) + `transformers` (477) + `peft` (326) +
  `deepspeed` + `fsdp` (127); also `jax`/`flax` (701/94). → LoRA/RLHF fine-tune + vLLM serving.
- **Default base model:** **Qwen3-4B-Instruct-2507** (125) and **Qwen3-7B-Instruct** (35) —
  Qwen3 is the habitual backbone; Mixtral-8x7B / Mistral-7B appear as secondary.

**Resource habits:** A100 (479) · RTX 4090 (~305 across `4090`/`rtx 4090`) · H100 (119) ·
3090 (112) · TPU (82) · A800 (81) · V100 (63) · L40 (60) · A6000 (48) · H800 (44) · MI250 (44).

**Failure memory** (feeds the resource-/failure-aware planner):
- **OOM is the #1 recurring failure — 1322 hits.** On the habitual GPUs, default to a
  memory-safe setup (lower batch / raise grad-accum / enable gradient checkpointing).
- High-frequency error types: `ValueError` (568), `RuntimeError` (529), `ImportError` (184),
  plus generic `Exception`/`Error`/`Traceback`.
- Success signals: 191 checkpoints saved, 48 wandb runs.

**Domain priors** (from the publication corpus above):
- **Baselines:** open LLMs (Qwen / Llama / Mistral families), task-specific SOTA per subfield,
  and — for social/trust work — GPT-4o / Gemini as strong reference models.
- **Metrics:** ROUGE / BERTScore + **human evaluation** (a constant in your work),
  attack-success-rate & defense-success-rate (safety), Spearman-vs-human (evaluation papers),
  Pass@k (agent/code), interpretability control accuracy.
- **Data:** **constructed benchmarks** are a signature of your group (you frequently ship the
  dataset with the paper); plus public safety / social / medical / summarization corpora.

---

## Known Dead-Ends

*From the tacit-knowledge interview (your confirmation, 2026-07-05).*

- **Novelty / incrementalism is your #1 reviewer pushback.** The recurring rejection theme is
  "incremental — insufficiently distinct from prior work." Any idea reaching `/ideagen`'s pick
  gate must clear an explicit **single-mechanism-novelty** bar and be positioned sharply against
  the closest prior work (including your own — this corpus is dense, so self-overlap is a real
  risk). Do not advance an A+B mashup that lacks one genuinely new mechanism.
- **Avoid large-scale manual annotation / human evaluation as the load-bearing contribution.**
  You do not want to re-run experiments whose cost is dominated by large manual-annotation or
  human-eval campaigns. Prefer **automatic / verifiable / model-based evaluation** (e.g. the
  BiasLens "test-set-free", AutoBench-V "self-benchmarking", facet-aware LLM-eval direction).
  Human eval stays as a *confirmatory* slice, never the primary engine of a plan.

---

## Workflow Preferences (W1–W7)

*Distilled from `workflow_prefs.py` (476 sessions, 479 candidate preference turns). **Adopted in
full per your confirmation (2026-07-05).** These describe **how work is run in your
environment** — consumed by the experiment/paper skills to match your process.*

| # | Preference | Why it matters / how to apply |
|---|---|---|
| **W1** | **Cheap / deterministic step first, then the expensive / LLM-GPU step.** | Stage pipelines so a cheap filter or smoke-test runs before any LLM/GPU call. Never lead with the expensive operation. |
| **W2** | **Cache aggressively; support resume / no recomputation.** | Persist every intermediate artifact and key it for lookup; never recompute what exists. Resumability is a hard requirement. |
| **W3** | **Never overwrite prior outputs; preserve history.** | Write timestamped / versioned outputs; stopping must not destroy prior or in-flight results. |
| **W4** | **Modular, section-by-section generation — not one monolithic pass.** | Decompose long generations into independently-regenerable units. |
| **W5** | **Idea / result validation is a human-checked loop, not one-shot.** | Build accept/reject as iterate-with-checkpoint; surface to you between rounds — never auto-accept. You are the judge. |
| **W6** | **Fixed research order: idea → experiments → paper.** | Sequence the pipeline in this order; don't jump to writing before evidence exists. |
| **W7** | **Specify baseline / metric / dataset explicitly before running.** | At design time, force concrete baseline + metric + dataset choices up front; no implicit defaults. |

---

## Publications Index

*131 papers, sorted by year then citations. `task_type` ∈ {engineering, theory, benchmark} is
abstract-informed (auto-classified, 108/131 with abstract). `full-text`: ✓ = local text in
`fulltext/txt/<key>.txt` · `abs` = abstract only (in `enriched.json`) · — = neither (arXiv id
unavailable). arXiv ids, abstracts, and BibTeX live in `enriched.json`.*

| # | Year | Title | Venue | Cites | task_type | full-text |
|---|------|-------|-------|-------|-----------|-----------|
| 1 | 2026 | Audio jailbreak: An open comprehensive benchmark fo… | ACL 2026 | 14 | benchmark | ✓ |
| 2 | 2026 | Do LLMs" Feel"? Emotion Circuits Discovery and Cont… | ICML | 13 | theory | ✓ |
| 3 | 2026 | CURE-Med: Curriculum-Informed Reinforcement Learnin… | ACL 2026 | 9 | engineering | ✓ |
| 4 | 2026 | A fano-style accuracy upper bound for llm single-pa… | ICLR | 5 | theory | ✓ |
| 5 | 2026 | ServImage: An Image Generation and Editing Benchmar… | ACL | 1 | benchmark | ✓ |
| 6 | 2026 | When Background Matters: Breaking Medical Vision La… | ACL, oral | 1 | engineering | ✓ |
| 7 | 2026 | Pastiche Novel Generation Creating: Fan Fiction You… | ACL finding 2026 | 1 | engineering | ✓ |
| 8 | 2026 | When Personalization Tricks Detectors: The Feature-… | ACL 2026, oral | 1 | benchmark | ✓ |
| 9 | 2026 | Distinguishable Deletion: Unifying Knowledge Erasur… | ICML | 0 | engineering | ✓ |
| 10 | 2026 | The Cylindrical Representation Hypothesis for Langu… | ICML | 0 | theory | ✓ |
| 11 | 2025 | Injecting domain-specific knowledge into large lang… | EMNLP findings | 150 | benchmark | ✓ |
| 12 | 2025 | On the trustworthiness of generative foundation mod… | arXiv:2502.14296 | 60 | benchmark | ✓ |
| 13 | 2025 | The Truth Becomes Clearer Through Debate! Multi-Age… | SIGIR 2025 | 53 | engineering | ✓ |
| 14 | 2025 | Maniplvm-r1: Reinforcement learning for reasoning i… | AAAI 2026 | 37 | engineering | ✓ |
| 15 | 2025 | From a tiny slip to a giant leap: An llm-based simu… | EMNLP main conference | 29 | engineering | ✓ |
| 16 | 2025 | Unveiling the power of language models in chemical … | Communications Chemistry 8 (1), 4 | 29 | benchmark | ✓ |
| 17 | 2025 | A Cognitive Writing Perspective for Constrained Lon… | ACL finding 2025 | 25 | engineering | ✓ |
| 18 | 2025 | The stepwise deception: Simulating the evolution fr… | Proceedings of the 2025 Conference on  | 20 | engineering | ✓ |
| 19 | 2025 | CulFiT: A Fine-grained Cultural-aware LLM Training … | ACL 2025 main | 20 | engineering | ✓ |
| 20 | 2025 | Breaking focus: Contextual distraction curse in lar… | NeurIPS | 20 | theory | ✓ |
| 21 | 2025 | Socialmaze: A benchmark for evaluating social reaso… | arXiv:2505.23713 | 16 | benchmark | ✓ |
| 22 | 2025 | Evaluating and mitigating bias in AI-based medical … | Nature Computational Science 5 (5), 38 | 16 | theory | ✓ |
| 23 | 2025 | DyFlow: Dynamic Workflow Framework for Agentic Reas… | NeurIPS 2025 | 15 | engineering | ✓ |
| 24 | 2025 | Peddet: Adaptive spectral optimization for multimod… | ECAI | 14 | engineering | ✓ |
| 25 | 2025 | Beyond Profile: From Surface-Level Facts to Deep Pe… | ACL finding 2025 | 14 | engineering | ✓ |
| 26 | 2025 | More is not always better? Enhancing Many-Shot In-C… | ACL main 2025 | 14 | engineering | ✓ |
| 27 | 2025 | Cross-Lingual Pitfalls: Automatic Probing Cross-Lin… | ACL main 2025 | 11 | theory | ✓ |
| 28 | 2025 | Word Form Matters: LLMs' Semantic Reconstruction un… | ACL finding 2025 | 11 | theory | ✓ |
| 29 | 2025 | Trusteval: A dynamic evaluation toolkit on trustwor… | Proceedings of the 2025 Conference of  | 10 | benchmark | — |
| 30 | 2025 | Unifying search and recommendation: A generative pa… | arXiv:2504.06714 | 9 | engineering | ✓ |
| 31 | 2025 | A Symbolic Adversarial Learning Framework for Evolv… | EMNLP main conference | 8 | engineering | ✓ |
| 32 | 2025 | FineState-Bench: A Comprehensive Benchmark for Fine… | arXiv:2508.09241 | 7 | benchmark | ✓ |
| 33 | 2025 | Evaluate bias without manual test sets: A concept r… | arXiv:2505.15524 | 7 | theory | ✓ |
| 34 | 2025 | Beyond Survival: Evaluating LLMs in Social Deductio… | arXiv:2510.11389 | 6 | benchmark | ✓ |
| 35 | 2025 | From Individuals to Crowds: Dual-Level Public Respo… | ACM MM 2025 | 6 | engineering | ✓ |
| 36 | 2025 | Flipping Knowledge Distillation: Leveraging Small M… | ACL main 2025 | 6 | engineering | ✓ |
| 37 | 2025 | Invisible Entropy: Towards Safe and Efficient Low-E… | EMNLP main conference | 6 | engineering | ✓ |
| 38 | 2025 | VSCBench: Bridging the Gap in Vision-Language Model… | ACL 2025 findings | 4 | benchmark | ✓ |
| 39 | 2025 | Adaptive Distraction: Probing LLM Contextual Robust… | arXiv:2502.01609 | 4 | theory | ✓ |
| 40 | 2025 | QUIDS: Query intent generation via dual space model… | EMNLP main conference | 3 | engineering | ✓ |
| 41 | 2025 | Under the Shadow of Babel: How Language Shapes Reas… | EMNLP findings | 3 | theory | ✓ |
| 42 | 2025 | Gta: Graph theory agent and benchmark for algorithm… |  | 3 | benchmark | — |
| 43 | 2025 | New Paradigm for Evaluating Scholar Summaries: A Fa… | ACM Transactions on Information System | 2 | benchmark | ✓ |
| 44 | 2025 | ReactionTeam: Teaming Experts for Divergent Thinkin… | 2025 IEEE International Conference on  | 1 | engineering | ✓ |
| 45 | 2025 | QUIDS: Query Intent Description for Exploratory Sea… | Proceedings of the 2025 Conference on  | 1 | engineering | ✓ |
| 46 | 2025 | Unifying Search and Recommendation with Dual-View R… | arXiv:2504.06714 | 0 | engineering | ✓ |
| 47 | 2025 | Injecting domain-specific knowledge into large lang… | EMNLP findings | 0 | benchmark | ✓ |
| 48 | 2024 | Large language model based multi-agents: A survey o… | IJCAI 2024 | 2011 | benchmark | ✓ |
| 49 | 2024 | Opportunities and challenges for ChatGPT and large … | Briefings in Bioinformatics 25 (1), bb | 531 | benchmark | ✓ |
| 50 | 2024 | Pre-trained multimodal large language model enhance… | Nature Communications 15 (1), 5649 | 259 | engineering | — |
| 51 | 2024 | An AI agent for fully automated multi‐omic analyses | Advanced Science 11 (44), 2407094 | 100 | engineering | — |
| 52 | 2024 | From Skepticism to Acceptance: Simulating the Attit… | IJCAI 2024 | 99 | engineering | ✓ |
| 53 | 2024 | A multi-agent conversational recommender system | arXiv:2402.01135 | 87 | engineering | ✓ |
| 54 | 2024 | Decoding Echo Chambers: LLM-Powered Simulations Rev… | COLING 2025 | 62 | engineering | ✓ |
| 55 | 2024 | Shaping the Safety Boundaries: Understanding and De… | ACL main 2025 | 49 | theory | ✓ |
| 56 | 2024 | Large language model based multi-agents: A survey o… | arXiv:2402.01680 | 42 | benchmark | ✓ |
| 57 | 2024 | Large language model based multi-agents: A survey o… | arXiv:2402.01680 | 29 | benchmark | ✓ |
| 58 | 2024 | Hazards in Daily Life? Enabling Robots to Proactive… | NAACL main conference | 23 | engineering | ✓ |
| 59 | 2024 | Autobench-v: Can large vision-language models bench… | arXiv:2410.21259 | 22 | benchmark | ✓ |
| 60 | 2024 | Scholarchemqa: Unveiling the power of language mode… | arXiv:2407.16931 | 15 | benchmark | ✓ |
| 61 | 2024 | Unify graph learning with text: Unleashing llm pote… | Proceedings of the ACM Web Conference  | 15 | engineering | ✓ |
| 62 | 2024 | Leveraging professional radiologists’ expertise to … | arXiv:2401.16578 | 13 | benchmark | ✓ |
| 63 | 2024 | LLM-driven agents for influencer selection in digit… | arXiv:2403.15105 | 13 | engineering | ✓ |
| 64 | 2024 | Large Language Model based Multi-Agents: A Survey o… | arXiv:2402.01680 | 11 | benchmark | ✓ |
| 65 | 2024 | A large-scale time-aware agents simulation for infl… | arXiv:2411.01143 | 10 | engineering | ✓ |
| 66 | 2024 | Leveraging Professional Radiologists' Expertise to … | 2024 IEEE 12th International Conferenc | 9 | benchmark | ✓ |
| 67 | 2024 | Mmac-copilot: Multi-modal agent collaboration opera… | arXiv:2404.18074 | 9 | engineering | ✓ |
| 68 | 2024 | Thinking Before Running! Efficient Code Generation … | ACL finding 2025 | 8 | engineering | ✓ |
| 69 | 2024 | What affects the stability of tool learning? an emp… | arXiv:2407.03007 | 7 | theory | ✓ |
| 70 | 2024 | Rethinking Scientific Summarization Evaluation: Gro… | TOIS | 7 | benchmark | ✓ |
| 71 | 2024 | Unified multi-scenario summarization evaluation and… | IEEE Transactions on Knowledge and Dat | 6 | benchmark | — |
| 72 | 2024 | Flexible and Adaptable Summarization via Expertise … | SIGIR 2024 | 6 | engineering | ✓ |
| 73 | 2024 | Write Summary Step-by-Step: A Pilot Study of Stepwi… | IEEE/ACM Transactions on Audio, Speech | 6 | engineering | ✓ |
| 74 | 2024 | Large language model based multi-agents: A survey o… | arXiv:2402.01680 | 6 | benchmark | ✓ |
| 75 | 2024 | Multi-Intent Attribute-Aware Text Matching in Searc… | Proceedings of the 17th ACM Internatio | 5 | engineering | ✓ |
| 76 | 2024 | SAGraph: A Large-scale Text-Rich Social Graph Datas… | SIGIR 2025 dataset track | 4 | benchmark | ✓ |
| 77 | 2024 | Iad: In-context learning ability decoupler of large… | Proceedings of the 2024 Joint Internat | 3 | engineering | — |
| 78 | 2024 | Selecting query-bag as pseudo relevance feedback fo… | arXiv:2404.04272 | 2 | engineering | ✓ |
| 79 | 2024 | Decomposing vision-based LLM predictions for auto-e… | arXiv:2403.05680 | 2 | benchmark | ✓ |
| 80 | 2024 | Think as People: Context-Driven Multi-Image News Ca… | ICASSP 2024-2024 IEEE International Co | 1 | engineering | — |
| 81 | 2023 | Lift yourself up: Retrieval-augmented text generati… | Advances in Neural Information Process | 205 | engineering | ✓ |
| 82 | 2023 | Interactive natural language processing | arXiv:2305.13246 | 89 | benchmark | ✓ |
| 83 | 2023 | SkinGPT-4: an interactive dermatology diagnostic sy… | Nature Communications | 75 | engineering | ✓ |
| 84 | 2023 | Follow the timeline! generating an abstractive and … | ACM Transactions on Information System | 34 | engineering | ✓ |
| 85 | 2023 | Towards a unified framework for reference retrieval… | Findings of the Association for Comput | 26 | engineering | — |
| 86 | 2023 | Dialogue summarization with static-dynamic structur… | Proceedings of the 61st Annual Meeting | 26 | engineering | — |
| 87 | 2023 | EZInterviewer: To Improve Job Interview Performance… | WSDM 2023 | 26 | engineering | ✓ |
| 88 | 2023 | Improving the Robustness of Summarization Systems w… | ACL 2023 | 21 | engineering | ✓ |
| 89 | 2023 | Path to medical agi: Unify domain-specific medical … | arXiv:2306.10765 | 20 | engineering | ✓ |
| 90 | 2023 | A Topic-aware Summarization Framework with Differen… | SIGIR 2023 | 19 | engineering | ✓ |
| 91 | 2023 | Decouple knowledge from paramters for plug-and-play… | Findings of the Association for Comput | 15 | engineering | ✓ |
| 92 | 2023 | Automated bioinformatics analysis via autoba | arXiv:2309.03242 | 14 | engineering | ✓ |
| 93 | 2023 | Towards personalized review summarization by modeli… | arXiv:2301.11682 | 12 | engineering | ✓ |
| 94 | 2023 | Learning towards Selective Data Augmentation for Di… | AAAI 2023 | 10 | engineering | ✓ |
| 95 | 2023 | Stylized dialogue generation with feature-guided kn… | Findings of the Association for Comput | 8 | engineering | — |
| 96 | 2023 | Unleashing the power of large models: Exploring hum… | Proceedings of the 22nd Chinese Nation | 8 | benchmark | — |
| 97 | 2023 | Modeling non-uniform uncertainty in Reaction Predic… |  | 6 | engineering | — |
| 98 | 2023 | UMSE: Unified Multi-scenario Summarization Evaluati… | ACL 2023 findings | 4 | benchmark | ✓ |
| 99 | 2023 | A Trend of AI Conference Convergence in Similarity:… | IEEE Transactions on Knowledge and Dat | 1 | theory | — |
| 100 | 2023 | Beyond the Typical: Modeling Rare Plausible Pattern… | arXiv:2310.04674 | 0 | engineering | ✓ |
| 101 | 2022 | Towards improving faithfulness in abstractive summa… | Advances in Neural Information Process | 61 | engineering | ✓ |
| 102 | 2022 | Target-aware Abstractive Related Work Generation wi… | SIGIR 2022 | 46 | engineering | ✓ |
| 103 | 2022 | Scientific Paper Extractive Summarization Enhanced … | EMNLP 2022 | 21 | engineering | ✓ |
| 104 | 2022 | Keywords and Instances: A Hierarchical Contrastive … | ACL 2022 | 19 | engineering | ✓ |
| 105 | 2022 | HeteroQA: Learning towards question-and-answering t… | Proceedings of the Fifteenth ACM Inter | 12 | engineering | ✓ |
| 106 | 2022 | Unsupervised mitigating gender bias by character co… | Proceedings of the 4th Workshop on Gen | 11 | engineering | — |
| 107 | 2022 | Summarizing Procedural Text: Data and Approach | Findings of the Association for Comput | 3 | engineering | — |
| 108 | 2021 | Capturing relations between scientific papers: An a… | Proceedings of the 59th Annual Meeting | 74 | engineering | — |
| 109 | 2021 | Combining curriculum learning and knowledge distill… | Findings of the Association for Comput | 42 | engineering | — |
| 110 | 2021 | How does Truth Evolve into Fake News? An Empirical … | The Web Conference 2021, Workshop on N | 13 | benchmark | ✓ |
| 111 | 2021 | BioGen: Generating biography summary under table gu… | Findings of the Association for Comput | 5 | engineering | — |
| 112 | 2020 | VMSMO: Learning to Generate Multimodal Summary for … | EMNLP | 116 | engineering | ✓ |
| 113 | 2020 | Meaningful Answer Generation of E-Commerce Question… | TOIS | 57 | engineering | ✓ |
| 114 | 2020 | Learning to respond with stickers: A framework of u… | Proceedings of the Web Conference 2020 | 49 | engineering | ✓ |
| 115 | 2020 | From Standard Summarization to New Tasks and Beyond… | IJCAI 2020 | 40 | benchmark | ✓ |
| 116 | 2020 | Selection and generation: Learning towards multi-pr… | Proceedings of the 2020 Conference on  | 29 | engineering | — |
| 117 | 2020 | The Style-Content Duality of Attractiveness: Learni… | AAAI | 23 | engineering | ✓ |
| 118 | 2020 | Learning to Respond with Your Favorite Stickers: A … | TOIS | 21 | engineering | ✓ |
| 119 | 2020 | Reasoning in Dialog: Improving Response Generation … | AAAI | 17 | engineering | ✓ |
| 120 | 2020 | Infusing Sequential Information into Conditional Ma… | COLING | 8 | engineering | ✓ |
| 121 | 2020 | RPM-Oriented Query Rewriting Framework for E-commer… | Proceedings of the AAAI Conference on  | 3 | engineering | ✓ |
| 122 | 2019 | Learning towards Abstractive Timeline Summarization | IJCAI, 4939-4945 | 61 | engineering | — |
| 123 | 2019 | Modeling personalization in continuous space for re… | EMNLP 2019, 1931-1940 | 52 | engineering | — |
| 124 | 2019 | Stick to facts: Towards fidelity-oriented product d… | EMNLP 2019 | 34 | engineering | ✓ |
| 125 | 2019 | How to Write Summaries with Patterns? Learning towa… | EMNLP 2019 | 33 | engineering | ✓ |
| 126 | 2018 | Abstractive Text Summarization by Incorporating Rea… | AAAI 2019 | 98 | engineering | ✓ |
| 127 | 2018 | Privacy-preserving collaborative model learning: Th… | IEEE Transactions on Knowledge and Dat | 76 | engineering | — |
| 128 | 2018 | Iterative Document Representation Learning Towards … | EMNLP 2018 | 50 | engineering | ✓ |
| 129 | 2018 | An Evolutionary Energy Prediction Model for Solar E… | International Conference of Pioneering | 0 | engineering | — |
| 130 | n/a | Large language model based multi-agents: A survey o… | arXiv:2402.01680 | 6 | benchmark | ✓ |
| 131 | n/a | Large language model based multi-agents: A survey o… | arXiv:2402.01680 | 6 | benchmark | ✓ |

---

## BibTeX Bank

*131 entries, built offline from Scholar metadata by `profile_enrich.py`. Keys match the
Publications Index and `enriched.json`. Use for `/paper-write` citations (≤3 self-citations;
run the anti-self-plagiarism check against this corpus).*

```bibtex
@inproceedings{guo2024large,
  title = {Large language model based multi-agents: A survey of progress and challenges},
  author = {T Guo and X Chen and Y Wang and R Chang and S Pei and NV Chawla and O Wiest and X Zhang},
  booktitle = {IJCAI 2024},
  year = {2024}
}

@article{tian2024opportunities,
  title = {Opportunities and challenges for ChatGPT and large language models in biomedicine and health},
  author = {S Tian and Q Jin and L Yeganova and PT Lai and Q Zhu and X Chen and Y Yang and Q Chen and ...},
  journal = {Briefings in Bioinformatics 25 (1), bbad493},
  year = {2024}
}

@article{zhou2024pre,
  title = {Pre-trained multimodal large language model enhances dermatological diagnosis using SkinGPT-4},
  author = {J Zhou and X He and L Sun and J Xu and X Chen and Y Chu and L Zhou and X Liao and B Zhang and ...},
  journal = {Nature Communications 15 (1), 5649},
  year = {2024}
}

@inproceedings{cheng2023lift,
  title = {Lift yourself up: Retrieval-augmented text generation with self-memory},
  author = {X Cheng and D Luo and X Chen and L Liu and D Zhao and R Yan},
  booktitle = {Advances in Neural Information Processing Systems 36, 43780-43799},
  year = {2023}
}

@inproceedings{song2025injecting,
  title = {Injecting domain-specific knowledge into large language models: a comprehensive survey},
  author = {XC Zirui Song and Bin Yan and Yuhan Liu and Miao Fang and Mingzhe Li and Rui Yan},
  booktitle = {EMNLP findings, https://aclanthology.org/2025.findings-emnlp.1379/},
  year = {2025}
}

@inproceedings{li2020vmsmo,
  title = {VMSMO: Learning to Generate Multimodal Summary for Video-based News Articles},
  author = {M Li and X Chen and S Gao and Z Chan and D Zhao and R Yan},
  booktitle = {EMNLP},
  year = {2020}
}

@inproceedings{zhou2024ai,
  title = {An AI agent for fully automated multi‐omic analyses},
  author = {J Zhou and B Zhang and G Li and X Chen and H Li and X Xu and S Chen and W He and C Xu and L Liu and ...},
  booktitle = {Advanced Science 11 (44), 2407094},
  year = {2024}
}

@inproceedings{liu2024skepticism,
  title = {From Skepticism to Acceptance: Simulating the Attitude Dynamics Toward Fake News},
  author = {Y Liu and X Chen and X Zhang and X Gao and J Zhang and R Yan},
  booktitle = {IJCAI 2024},
  year = {2024}
}

@inproceedings{gao2018abstractive,
  title = {Abstractive Text Summarization by Incorporating Reader Comments},
  author = {S Gao and X Chen and P Li and Z Ren and L Bing and D Zhao and R Yan},
  booktitle = {AAAI 2019},
  year = {2018}
}

@misc{wang2023interactive,
  title = {Interactive natural language processing},
  author = {Z Wang and G Zhang and K Yang and N Shi and W Zhou and S Hao and G Xiong and Y Li and MY Sim and ...},
  booktitle = {arXiv preprint arXiv:2305.13246},
  year = {2023}
}

@misc{fang2024multi,
  title = {A multi-agent conversational recommender system},
  author = {J Fang and S Gao and P Ren and X Chen and S Verberne and Z Ren},
  booktitle = {arXiv preprint arXiv:2402.01135},
  year = {2024}
}

@article{wang2018privacy,
  title = {Privacy-preserving collaborative model learning: The case of word vector training},
  author = {Q Wang and M Du and X Chen and Y Chen and P Zhou and X Chen and X Huang},
  journal = {IEEE Transactions on Knowledge and Data Engineering 30 (12), 2381-2393},
  year = {2018}
}

@article{zhou2023skingpt,
  title = {SkinGPT-4: an interactive dermatology diagnostic system with visual large language model},
  author = {J Zhou and X He and L Sun and J Xu and X Chen and Y Chu and L Zhou and X Liao and B Zhang and ...},
  journal = {Nature Communications},
  year = {2023}
}

@inproceedings{chen2021capturing,
  title = {Capturing relations between scientific papers: An abstractive model for related work section generation},
  author = {X Chen and H Alamro and M Li and S Gao and X Zhang and D Zhao and R Yan},
  booktitle = {Proceedings of the 59th Annual Meeting of the Association for Computational …},
  year = {2021}
}

@inproceedings{wang2024decoding,
  title = {Decoding Echo Chambers: LLM-Powered Simulations Revealing Polarization in Social Networks},
  author = {C Wang and Z Liu and D Yang and X Chen},
  booktitle = {COLING 2025},
  year = {2024}
}

@inproceedings{chen2022towards,
  title = {Towards improving faithfulness in abstractive summarization},
  author = {X Chen and M Li and X Gao and X Zhang},
  booktitle = {Advances in Neural Information Processing Systems 35, 24516-24528},
  year = {2022}
}

@inproceedings{chen2019learning,
  title = {Learning towards Abstractive Timeline Summarization},
  author = {X Chen and Z Chan and S Gao and MH Yu and D Zhao and R Yan},
  booktitle = {IJCAI, 4939-4945},
  year = {2019}
}

@misc{huang2025trustworthiness,
  title = {On the trustworthiness of generative foundation models: Guideline, assessment, and perspective},
  author = {Y Huang and C Gao and S Wu and H Wang and X Wang and Y Zhou and Y Wang and J Ye and J Shi and ...},
  booktitle = {arXiv preprint arXiv:2502.14296},
  year = {2025}
}

@inproceedings{gao2020meaningful,
  title = {Meaningful Answer Generation of E-Commerce Question-Answering},
  author = {S Gao and X Chen and Z Ren and D Zhao and R Yan},
  booktitle = {TOIS},
  year = {2020}
}

@inproceedings{liu2025truth,
  title = {The Truth Becomes Clearer Through Debate! Multi-Agent Systems with Large Language Models Unmask Fake News},
  author = {Y Liu and Y Liu and X Zhang and X Chen and R Yan},
  booktitle = {SIGIR 2025},
  year = {2025}
}

@inproceedings{chan2019modeling,
  title = {Modeling personalization in continuous space for response generation via augmented wasserstein autoencoders},
  author = {Z Chan and J Li and X Yang and X Chen and W Hu and D Zhao and R Yan},
  booktitle = {EMNLP 2019, 1931-1940},
  year = {2019}
}

@inproceedings{chen2018iterative,
  title = {Iterative Document Representation Learning Towards Summarization with Polishing},
  author = {X Chen and S Gao and C Tao and Y Song and D Zhao and R Yan},
  booktitle = {EMNLP 2018},
  year = {2018}
}

@inproceedings{gao2024shaping,
  title = {Shaping the Safety Boundaries: Understanding and Defending Against Jailbreaks in Large Language Models},
  author = {L Gao and X Zhang and P Nakov and X Chen},
  booktitle = {ACL main 2025},
  year = {2024}
}

@inproceedings{gao2020learning,
  title = {Learning to respond with stickers: A framework of unifying multi-modality in multi-turn dialog},
  author = {S Gao and X Chen and C Liu and L Liu and D Zhao and R Yan},
  booktitle = {Proceedings of the Web Conference 2020, 1138-1148},
  year = {2020}
}

@inproceedings{chen2022target,
  title = {Target-aware Abstractive Related Work Generation with Contrastive Learning},
  author = {X Chen and H Alamro and M Li and S Gao and R Yan and X Gao and X Zhang},
  booktitle = {SIGIR 2022},
  year = {2022}
}

@misc{guo2024largeb,
  title = {Large language model based multi-agents: A survey of progress and challenges. arXiv 2024},
  author = {T Guo and X Chen and Y Wang and R Chang and S Pei and NV Chawla and O Wiest and X Zhang},
  booktitle = {arXiv preprint arXiv:2402.01680 10},
  year = {2024}
}

@inproceedings{zhu2021combining,
  title = {Combining curriculum learning and knowledge distillation for dialogue generation},
  author = {Q Zhu and X Chen and P Wu and JF Liu and D Zhao},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2021, 1284-1295},
  year = {2021}
}

@inproceedings{gao2020standard,
  title = {From Standard Summarization to New Tasks and Beyond: Summarization with Manifold Information},
  author = {S Gao and X Chen and Z Ren and D Zhao and R Yan},
  booktitle = {IJCAI 2020},
  year = {2020}
}

@inproceedings{song2025maniplvm,
  title = {Maniplvm-r1: Reinforcement learning for reasoning in embodied manipulation with large vision-language models},
  author = {Z Song and G Ouyang and M Li and Y Ji and C Wang and Z Xu and Z Zhang and X Zhang and Q Jiang and ...},
  booktitle = {AAAI 2026},
  year = {2025}
}

@article{chen2023follow,
  title = {Follow the timeline! generating an abstractive and extractive timeline summary in chronological order},
  author = {X Chen and M Li and S Gao and Z Chan and D Zhao and X Gao and X Zhang and R Yan},
  journal = {ACM Transactions on Information Systems 41 (1), 1-30},
  year = {2023}
}

@inproceedings{chan2019stick,
  title = {Stick to facts: Towards fidelity-oriented product description generation},
  author = {Z Chan and X Chen and Y Wang and J Li and Z Zhang and K Gai and D Zhao and R Yan},
  booktitle = {EMNLP 2019},
  year = {2019}
}

@inproceedings{gao2019how,
  title = {How to Write Summaries with Patterns? Learning towards Abstractive Summarization through Prototype Editing},
  author = {S Gao and X Chen and P Li and Z Chan and D Zhao and R Yan},
  booktitle = {EMNLP 2019},
  year = {2019}
}

@inproceedings{liu2025tiny,
  title = {From a tiny slip to a giant leap: An llm-based simulation for fake news evolution},
  author = {Y Liu and Z Song and X Zhang and X Chen and R Yan},
  booktitle = {EMNLP main conference},
  year = {2025}
}

@article{chen2025unveiling,
  title = {Unveiling the power of language models in chemical research question answering},
  author = {X Chen and T Wang and T Guo and K Guo and J Zhou and H Li and Z Song and X Gao and X Zhang},
  journal = {Communications Chemistry 8 (1), 4},
  year = {2025}
}

@misc{guo2024largec,
  title = {Large language model based multi-agents: A survey of progress and challenges. arXiv},
  author = {T Guo and X Chen and Y Wang and R Chang and S Pei and NV Chawla and O Wiest and X Zhang},
  booktitle = {arXiv preprint arXiv:2402.01680},
  year = {2024}
}

@inproceedings{chan2020selection,
  title = {Selection and generation: Learning towards multi-product advertisement post generation},
  author = {Z Chan and Y Zhang and X Chen and S Gao and Z Zhang and D Zhao and R Yan},
  booktitle = {Proceedings of the 2020 Conference on Empirical Methods in Natural Language …},
  year = {2020}
}

@inproceedings{shi2023towards,
  title = {Towards a unified framework for reference retrieval and related work generation},
  author = {Z Shi and S Gao and Z Zhang and X Chen and Z Chen and P Ren and Z Ren},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2023, 5785-5799},
  year = {2023}
}

@inproceedings{gao2023dialogue,
  title = {Dialogue summarization with static-dynamic structure fusion graph},
  author = {S Gao and X Cheng and M Li and X Chen and J Li and D Zhao and R Yan},
  booktitle = {Proceedings of the 61st Annual Meeting of the Association for Computational …},
  year = {2023}
}

@inproceedings{li2023ezinterviewer,
  title = {EZInterviewer: To Improve Job Interview Performance with Mock Interview Generator},
  author = {M Li and X Chen and W Liao and Y Song and T Zhang and D Zhao and R Yan},
  booktitle = {WSDM 2023},
  year = {2023}
}

@inproceedings{wan2025cognitive,
  title = {A Cognitive Writing Perspective for Constrained Long-Form Text Generation},
  author = {K Wan and H Mu and R Hao and H Luo and T Gu and X Chen},
  booktitle = {ACL finding 2025},
  year = {2025}
}

@inproceedings{song2024hazards,
  title = {Hazards in Daily Life? Enabling Robots to Proactively Detect and Resolve Anomalies},
  author = {Z Song and G Ouyang and M Fang and H Na and Z Shi and Z Chen and Y Fu and Z Zhang and S Jiang and ...},
  booktitle = {NAACL main conference},
  year = {2024}
}

@inproceedings{li2020style,
  title = {The Style-Content Duality of Attractiveness: Learning to Write Eye-Catching Headlines via Disentanglement},
  author = {M Li and X Chen and M Yang and S Gao and D Zhao and R Yan},
  booktitle = {AAAI},
  year = {2020}
}

@misc{bao2024autobench,
  title = {Autobench-v: Can large vision-language models benchmark themselves?},
  author = {H Bao and Y Huang and Y Wang and J Ye and X Wang and X Chen and Y Zhao and T Zhou and ...},
  booktitle = {arXiv preprint arXiv:2410.21259},
  year = {2024}
}

@inproceedings{chen2023improving,
  title = {Improving the Robustness of Summarization Systems with Dual Augmentation},
  author = {X Chen and G Long and C Tao and M Li and X Gao and C Zhang and X Zhang},
  booktitle = {ACL 2023},
  year = {2023}
}

@inproceedings{chen2022scientific,
  title = {Scientific Paper Extractive Summarization Enhanced by Citation Graphs},
  author = {X Chen and M Li and S Gao and R Yan and X Gao and X Zhang},
  booktitle = {EMNLP 2022},
  year = {2022}
}

@inproceedings{gao2020learningb,
  title = {Learning to Respond with Your Favorite Stickers: A Framework of Unifying Multi-Modality and User Preference in Multi-Turn Dialog},
  author = {S Gao and X Chen and L Liu and D Zhao and R Yan},
  booktitle = {TOIS},
  year = {2020}
}

@inproceedings{liu2025stepwise,
  title = {The stepwise deception: Simulating the evolution from true news to fake news with llm agents},
  author = {Y Liu and Z Song and J Zhang and X Zhang and X Chen and R Yan},
  booktitle = {Proceedings of the 2025 Conference on Empirical Methods in Natural Language …},
  year = {2025}
}

@inproceedings{feng2025culfit,
  title = {CulFiT: A Fine-grained Cultural-aware LLM Training Paradigm via Multilingual Critique Data Synthesis},
  author = {R Feng and S Gao and X Chen and L Chen and S Shang},
  booktitle = {ACL 2025 main},
  year = {2025}
}

@inproceedings{huang2025breaking,
  title = {Breaking focus: Contextual distraction curse in large language models},
  author = {Y Huang and Y Wang and Z Xu and C Gao and S Wu and J Ye and X Chen and PY Chen and X Zhang},
  booktitle = {NeurIPS},
  year = {2025}
}

@misc{zhou2023path,
  title = {Path to medical agi: Unify domain-specific medical llms with the lowest cost},
  author = {J Zhou and X Chen and X Gao},
  booktitle = {arXiv preprint arXiv:2306.10765},
  year = {2023}
}

@inproceedings{chen2023topic,
  title = {A Topic-aware Summarization Framework with Different Modal Side Information},
  author = {X Chen and M Li and S Gao and X Cheng and Q Yang and Q Zhang and X Gao and X Zhang},
  booktitle = {SIGIR 2023},
  year = {2023}
}

@inproceedings{li2022keywords,
  title = {Keywords and Instances: A Hierarchical Contrastive Learning Framework Unifying Hybrid Granularities for Text Generation},
  author = {M Li and XX Lin and X Chen and J Chang and Q Zhang and F Wang and T Wang and Z Liu and W Chu and ...},
  booktitle = {ACL 2022},
  year = {2022}
}

@inproceedings{chen2020reasoning,
  title = {Reasoning in Dialog: Improving Response Generation by Context Reading Comprehension},
  author = {X Chen and Z Cui and J Zhang and C Wei and J Cui and B Wang and D Zhao and R Yan},
  booktitle = {AAAI},
  year = {2020}
}

@misc{xu2025socialmaze,
  title = {Socialmaze: A benchmark for evaluating social reasoning in large language models},
  author = {Z Xu and Y Wang and Y Huang and J Ye and H Zhuang and Z Song and L Gao and C Wang and Z Chen and ...},
  booktitle = {arXiv preprint arXiv:2505.23713},
  year = {2025}
}

@article{chen2025evaluating,
  title = {Evaluating and mitigating bias in AI-based medical text generation},
  author = {X Chen and T Wang and J Zhou and Z Song and X Gao and X Zhang},
  journal = {Nature Computational Science 5 (5), 388-396},
  year = {2025}
}

@inproceedings{wang2025dyflow,
  title = {DyFlow: Dynamic Workflow Framework for Agentic Reasoning},
  author = {Y Wang and Z Xu and Y Huang and X Wang and Z Song and L Gao and C Wang and X Tang and ...},
  booktitle = {NeurIPS 2025},
  year = {2025}
}

@misc{chen2024scholarchemqa,
  title = {Scholarchemqa: Unveiling the power of language models in chemical research question answering},
  author = {X Chen and T Wang and T Guo and K Guo and J Zhou and H Li and M Zhuge and J Schmidhuber and ...},
  booktitle = {arXiv preprint arXiv:2407.16931},
  year = {2024}
}

@inproceedings{wu2024unify,
  title = {Unify graph learning with text: Unleashing llm potentials for session search},
  author = {S Wu and Q Tu and H Liu and J Xu and Z Liu and G Zhang and R Wang and X Chen and R Yan},
  booktitle = {Proceedings of the ACM Web Conference 2024, 1509-1518},
  year = {2024}
}

@inproceedings{cheng2023decouple,
  title = {Decouple knowledge from paramters for plug-and-play language modeling},
  author = {X Cheng and Y Lin and X Chen and D Zhao and R Yan},
  booktitle = {Findings of the Association for Computational Linguistics: ACL 2023, 14288-14308},
  year = {2023}
}

@inproceedings{song2026audio,
  title = {Audio jailbreak: An open comprehensive benchmark for jailbreaking large audio-language models},
  author = {Z Song and Q Jiang and M Cui and M Li and L Gao and Z Zhang and Z Xu and Y Wang and C Wang and ...},
  booktitle = {ACL 2026},
  year = {2026}
}

@inproceedings{zhao2025peddet,
  title = {Peddet: Adaptive spectral optimization for multimodal pedestrian detection},
  author = {R Zhao and Z Zhang and Y Xu and Y Yao and Y Huang and W Zhang and Z Song and X Chen and ...},
  booktitle = {ECAI},
  year = {2025}
}

@inproceedings{wang2025beyond,
  title = {Beyond Profile: From Surface-Level Facts to Deep Persona Simulation in LLMs},
  author = {Z Wang and D Zhang and I Agrawal and S Gao and L Song and X Chen},
  booktitle = {ACL finding 2025},
  year = {2025}
}

@inproceedings{zhang2025more,
  title = {More is not always better? Enhancing Many-Shot In-Context Learning with Differentiated and Reweighting Objectives},
  author = {X Zhang and A Lv and Y Liu and F Sung and W Liu and S Shang and X Chen and R Yan},
  booktitle = {ACL main 2025},
  year = {2025}
}

@misc{zhou2023automated,
  title = {Automated bioinformatics analysis via autoba},
  author = {J Zhou and B Zhang and X Chen and H Li and X Xu and S Chen and X Gao},
  booktitle = {arXiv preprint arXiv:2309.03242},
  year = {2023}
}

@inproceedings{wang2026do,
  title = {Do LLMs" Feel"? Emotion Circuits Discovery and Control},
  author = {C Wang and Y Zhang and R Yu and Y Zheng and L Gao and Z Song and Z Xu and G Xia and H Zhang and ...},
  booktitle = {ICML},
  year = {2026}
}

@misc{zhu2024leveraging,
  title = {Leveraging professional radiologists’ expertise to enhance LLMs’ evaluation for radiology reports},
  author = {Q Zhu and X Chen and Q Jin and B Hou and TS Mathai and P Mukherjee and X Gao and ...},
  booktitle = {ArXiv, arXiv: 2401.16578 v3},
  year = {2024}
}

@misc{zhang2024llm,
  title = {LLM-driven agents for influencer selection in digital advertising campaigns},
  author = {X Zhang and X Chen and Y Liu and J Wang and Z Hu and R Yan},
  booktitle = {arXiv preprint arXiv:2403.15105},
  year = {2024}
}

@inproceedings{guo2021how,
  title = {How does Truth Evolve into Fake News? An Empirical Study of Fake News Evolution},
  author = {M Guo and X Chen and J Li and D Zhao and R Yan},
  booktitle = {The Web Conference 2021, Workshop on News Recommendation and Intelligence},
  year = {2021}
}

@misc{cheng2023towards,
  title = {Towards personalized review summarization by modeling historical reviews from customer and product separately},
  author = {X Cheng and S Gao and Y Zhang and Y Wang and X Chen and M Li and D Zhao and R Yan},
  booktitle = {arXiv preprint arXiv:2301.11682},
  year = {2023}
}

@inproceedings{gao2022heteroqa,
  title = {HeteroQA: Learning towards question-and-answering through multiple information sources via heterogeneous graph modeling},
  author = {S Gao and Y Zhang and Y Wang and Y Dong and X Chen and D Zhao and R Yan},
  booktitle = {Proceedings of the Fifteenth ACM International Conference on Web Search and …},
  year = {2022}
}

@inproceedings{xu2025cross,
  title = {Cross-Lingual Pitfalls: Automatic Probing Cross-Lingual Weakness of Multilingual Large Language Models},
  author = {Z Xu and Y Wang and Y Huang and X Chen and J Zhao and M Jiang and X Zhang},
  booktitle = {ACL main 2025},
  year = {2025}
}

@inproceedings{wang2025word,
  title = {Word Form Matters: LLMs' Semantic Reconstruction under Typoglycemia},
  author = {C Wang and T Gu and Z Wei and L Gao and Z Song and X Chen},
  booktitle = {ACL finding 2025},
  year = {2025}
}

@misc{guo2024larged,
  title = {Large Language Model based Multi-Agents: A Survey of Progress and Challenges (arXiv: 2402.01680). arXiv},
  author = {T Guo and X Chen and Y Wang and R Chang and S Pei and NV Chawla and O Wiest and X Zhang},
  year = {2024}
}

@inproceedings{chen2022unsupervised,
  title = {Unsupervised mitigating gender bias by character components: A case study of Chinese word embedding},
  author = {X Chen and M Li and R Yan and X Gao and X Zhang},
  booktitle = {Proceedings of the 4th Workshop on Gender Bias in Natural Language …},
  year = {2022}
}

@inproceedings{wang2025trusteval,
  title = {Trusteval: A dynamic evaluation toolkit on trustworthiness of generative foundation models},
  author = {Y Wang and J Ye and S Wu and C Gao and Y Huang and X Chen and Y Zhao and X Zhang},
  booktitle = {Proceedings of the 2025 Conference of the Nations of the Americas Chapter of …},
  year = {2025}
}

@misc{zhang2024large,
  title = {A large-scale time-aware agents simulation for influencer selection in digital advertising campaigns},
  author = {X Zhang and X Chen and Y Liu and J Wang and Z Hu and R Yan},
  booktitle = {arXiv preprint arXiv:2411.01143},
  year = {2024}
}

@inproceedings{chen2023learning,
  title = {Learning towards Selective Data Augmentation for Dialogue Generation},
  author = {X Chen and M Li and J Zhang and X Xia and C Wei and J Cui and X Gao and X Zhang and R Yan},
  booktitle = {AAAI 2023},
  year = {2023}
}

@inproceedings{onyame2026cure,
  title = {CURE-Med: Curriculum-Informed Reinforcement Learning for Multilingual Medical Reasoning},
  author = {E Onyame and A Ghosh and S Baidya and S Saha and X Chen and C Agarwal},
  booktitle = {ACL 2026},
  year = {2026}
}

@misc{zhao2025unifying,
  title = {Unifying search and recommendation: A generative paradigm inspired by information theory},
  author = {J Zhao and W Wang and C Xu and X Wang and Z Ren and S Verberne},
  booktitle = {arXiv e-prints, arXiv: 2504.06714},
  year = {2025}
}

@inproceedings{zhu2024leveragingb,
  title = {Leveraging Professional Radiologists' Expertise to Enhance LLMs' Evaluation for AI-generated Radiology Reports},
  author = {Q Zhu and X Chen and Q Jin and B Hou and TS Mathai and P Mukherjee and X Gao and ...},
  booktitle = {2024 IEEE 12th International Conference on Healthcare Informatics (ICHI …},
  year = {2024}
}

@misc{song2024mmac,
  title = {Mmac-copilot: Multi-modal agent collaboration operating copilot},
  author = {Z Song and Y Li and M Fang and Y Li and Z Chen and Z Shi and Y Huang and X Chen and L Chen},
  booktitle = {arXiv preprint arXiv:2404.18074},
  year = {2024}
}

@inproceedings{tian2025symbolic,
  title = {A Symbolic Adversarial Learning Framework for Evolving Fake News Generation and Detection},
  author = {C Tian and Q Ho and X Chen},
  booktitle = {EMNLP main conference},
  year = {2025}
}

@inproceedings{zhang2024thinking,
  title = {Thinking Before Running! Efficient Code Generation with Thorough Exploration and Optimal Refinement},
  author = {X Zhang and Y Liu and F Sung and X Chen and R Yan},
  booktitle = {ACL finding 2025},
  year = {2024}
}

@inproceedings{li2023stylized,
  title = {Stylized dialogue generation with feature-guided knowledge augmentation},
  author = {J Li and Z Zhang and X Chen and D Zhao and R Yan},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2023, 7144-7157},
  year = {2023}
}

@inproceedings{yuhan2023unleashing,
  title = {Unleashing the power of large models: Exploring human-machine conversations},
  author = {L Yuhan and C Xiuying and Y Rui},
  booktitle = {Proceedings of the 22nd Chinese National Conference on Computational …},
  year = {2023}
}

@inproceedings{xie2020infusing,
  title = {Infusing Sequential Information into Conditional Masked Translation Model with Self-Review Mechanism},
  author = {P Xie and Z Cui and X Chen and X Hu and J Cui and B Wang},
  booktitle = {COLING},
  year = {2020}
}

@misc{ji2025finestate,
  title = {FineState-Bench: A Comprehensive Benchmark for Fine-Grained State Control in GUI Agents},
  author = {F Ji and J Yang and Z Song and Y Wang and Z Cui and Y Li and Q Jiang and M Fang and X Chen},
  booktitle = {arXiv preprint arXiv:2508.09241},
  year = {2025}
}

@misc{gao2025evaluate,
  title = {Evaluate bias without manual test sets: A concept representation perspective for llms},
  author = {L Gao and K Wan and W Liu and C Wang and Z Song and Z Xu and Y Wang and V Stoyanov and ...},
  booktitle = {arXiv preprint arXiv:2505.15524},
  year = {2025}
}

@misc{huang2024what,
  title = {What affects the stability of tool learning? an empirical study on the robustness of tool learning frameworks},
  author = {C Huang and Z Shi and Y Wen and X Chen and P Han and S Gao and S Shang},
  booktitle = {arXiv preprint arXiv:2407.03007},
  year = {2024}
}

@inproceedings{chen2024rethinking,
  title = {Rethinking Scientific Summarization Evaluation: Grounding Explainable Metrics on Facet-aware Benchmark},
  author = {X Chen and T Wang and Q Zhu and T Guo and S Gao and Z Lu and X Gao and X Zhang},
  booktitle = {TOIS},
  year = {2024}
}

@misc{song2025beyond,
  title = {Beyond Survival: Evaluating LLMs in Social Deduction Games with Human-Aligned Strategies},
  author = {Z Song and Y Huang and J Liu and H Luo and C Wang and L Gao and Z Xu and M Han and X Chang and ...},
  booktitle = {arXiv preprint arXiv:2510.11389},
  year = {2025}
}

@inproceedings{zhang2025individuals,
  title = {From Individuals to Crowds: Dual-Level Public Response Prediction in Social Media},
  author = {J Zhang and K Wan and L Xu and A Li and Z Liu and X Chen},
  booktitle = {ACM MM 2025},
  year = {2025}
}

@inproceedings{li2025flipping,
  title = {Flipping Knowledge Distillation: Leveraging Small Models' Expertise to Enhance LLMs in Text Matching},
  author = {M Li and J Xiang and Q Zhang and K Wan and X Chen},
  booktitle = {ACL main 2025},
  year = {2025}
}

@inproceedings{gu2025invisible,
  title = {Invisible Entropy: Towards Safe and Efficient Low-Entropy LLM Watermarking},
  author = {T Gu and Z Wang and K Huang and Y Yao and X Zhang and Y Yang and X Chen},
  booktitle = {EMNLP main conference},
  year = {2025}
}

@article{shang2024unified,
  title = {Unified multi-scenario summarization evaluation and explanation},
  author = {S Shang and Z Yao and H Fu and C Tao and X Chen and F Wang and Y Wang and Z Ren and S Gao},
  journal = {IEEE Transactions on Knowledge and Data Engineering 37 (2), 991-1003},
  year = {2024}
}

@inproceedings{chen2024flexible,
  title = {Flexible and Adaptable Summarization via Expertise Separation},
  author = {X Chen and M Li and S Gao and X Cheng and Q Zhu and R Yan and X Gao and X Zhang},
  booktitle = {SIGIR 2024},
  year = {2024}
}

@article{chen2024write,
  title = {Write Summary Step-by-Step: A Pilot Study of Stepwise Summarization},
  author = {X Chen and S Gao and M Li and Q Zhu and X Gao and X Zhang},
  journal = {IEEE/ACM Transactions on Audio, Speech, and Language Processing 32, 1406-1415},
  year = {2024}
}

@misc{guo2024largee,
  title = {Large language model based multi-agents: A survey of progress and challenges [J/OL]},
  author = {T Guo and X Chen and Y Wang and R Chang and S Pei and NV Chawla and O Wiest and X Zhang},
  booktitle = {arXiv preprint arXiv:2402.01680},
  year = {2024}
}

@misc{guo2023modeling,
  title = {Modeling non-uniform uncertainty in Reaction Prediction via Boosting and Dropout},
  author = {T Guo and C Ma and X Chen and B Nan and K Guo and S Pei and L Yu and NV Chawla and O Wiest and ...},
  year = {2023}
}

@misc{guo0000large,
  title = {Large language model based multi-agents: A survey of progress and challenges. arXiv preprint, 2024},
  author = {T Guo and X Chen and Y Wang and R Chang and S Pei and NV Chawla and O Wiest and X Zhang},
  booktitle = {arXiv preprint arXiv:2402.01680, 0}
}

@misc{guo0000largeb,
  title = {Large language model based multi-agents: A survey of progress and challenges. arXiv. 2024 doi: 10.48550},
  author = {T Guo and X Chen and Y Wang and R Chang and S Pei and NV Chawla and O Wiest and X Zhang},
  booktitle = {arXiv preprint arXiv.2402.01680, 0}
}

@inproceedings{wan2026fano,
  title = {A fano-style accuracy upper bound for llm single-pass reasoning in multi-hop qa},
  author = {K Wan and L Gao and H Mu and P Nakov and Y Wang and X Chen},
  booktitle = {ICLR},
  year = {2026}
}

@inproceedings{li2024multi,
  title = {Multi-Intent Attribute-Aware Text Matching in Searching},
  author = {M Li and X Chen and J Xiang and Q Zhang and C Ma and C Dai and J Chang and Z Liu and G Zhang},
  booktitle = {Proceedings of the 17th ACM International Conference on Web Search and Data …},
  year = {2024}
}

@inproceedings{gao2021biogen,
  title = {BioGen: Generating biography summary under table guidance on Wikipedia},
  author = {S Gao and X Chen and C Liu and D Zhao and R Yan},
  booktitle = {Findings of the Association for Computational Linguistics: ACL-IJCNLP 2021 …},
  year = {2021}
}

@inproceedings{geng2025vscbench,
  title = {VSCBench: Bridging the Gap in Vision-Language Model Safety Calibration},
  author = {J Geng and Q Li and Z Chen and Y Wang and D Zhu and Z Xie and C Lyu and X Chen and P Nakov and ...},
  booktitle = {ACL 2025 findings},
  year = {2025}
}

@misc{wang2025adaptive,
  title = {Adaptive Distraction: Probing LLM Contextual Robustness with Automated Tree Search},
  author = {Y Wang and Z Xu and Y Huang and C Gao and S Wu and J Ye and PY Chen and X Chen and X Zhang},
  booktitle = {NeurIPS 2025, arXiv: 2502.01609},
  year = {2025}
}

@inproceedings{zhang2024sagraph,
  title = {SAGraph: A Large-scale Text-Rich Social Graph Dataset for Advertising Campaigns},
  author = {X Zhang and X Chen and Y Liu and J Wang and Z Hu and R Yan},
  booktitle = {SIGIR 2025 dataset track},
  year = {2024}
}

@inproceedings{gao2023umse,
  title = {UMSE: Unified Multi-scenario Summarization Evaluation},
  author = {S Gao and Z Yao and C Tao and X Chen and P Ren and Z Ren and Z Chen},
  booktitle = {ACL 2023 findings},
  year = {2023}
}

@inproceedings{wang2025quids,
  title = {QUIDS: Query intent generation via dual space modeling},
  author = {Y Wang and X Chen and S Verberne},
  booktitle = {EMNLP main conference},
  year = {2025}
}

@inproceedings{wang2025under,
  title = {Under the Shadow of Babel: How Language Shapes Reasoning in LLMs},
  author = {C Wang and Y Zhang and L Gao and Z Xu and Z Song and Y Wang and X Chen},
  booktitle = {EMNLP findings},
  year = {2025}
}

@misc{xu2025gta,
  title = {Gta: Graph theory agent and benchmark for algorithmic graph reasoning with llms},
  author = {Z Xu and Y Wang and C Wang and L Gao and Z Song and Y Huang and Z Chen and X Zhang and ...},
  year = {2025}
}

@inproceedings{liu2024iad,
  title = {Iad: In-context learning ability decoupler of large language models in meta-training},
  author = {Y Liu and X Chen and G Xing and J Zhang and R Yan},
  booktitle = {Proceedings of the 2024 Joint International Conference on Computational …},
  year = {2024}
}

@inproceedings{gao2022summarizing,
  title = {Summarizing Procedural Text: Data and Approach},
  author = {S Gao and H Zhang and X Chen and R Yan and D Zhao},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2022, 2216-2225},
  year = {2022}
}

@inproceedings{chen2020rpm,
  title = {RPM-Oriented Query Rewriting Framework for E-commerce Keyword-Based Sponsored Search (Student Abstract)},
  author = {X Chen and D Xiao and S Gao and G Liu and W Lin and B Zheng and D Zhao and R Yan},
  booktitle = {Proceedings of the AAAI Conference on Artificial Intelligence 34 (10), 13769 …},
  year = {2020}
}

@article{wang2025new,
  title = {New Paradigm for Evaluating Scholar Summaries: A Facet-aware Metric and A Meta-evaluation Benchmark},
  author = {T Wang and X Chen and Q Zhu and T Guo and S Gao and Z Lu and X Gao and X Zhang},
  journal = {ACM Transactions on Information Systems 43 (4), 1-25},
  year = {2025}
}

@misc{zhang2024selecting,
  title = {Selecting query-bag as pseudo relevance feedback for information-seeking conversations},
  author = {X Zhang and X Chen and S Gao and S Li and X Gao and JR Wen and R Yan},
  booktitle = {arXiv preprint arXiv:2404.04272},
  year = {2024}
}

@misc{zhu2024decomposing,
  title = {Decomposing vision-based LLM predictions for auto-evaluation with GPT-4},
  author = {Q Zhu and B Hou and TS Mathai and P Mukherjee and Q Jin and X Chen and Z Wang and R Cheng and ...},
  booktitle = {arXiv preprint arXiv:2403.05680},
  year = {2024}
}

@inproceedings{ji2026servimage,
  title = {ServImage: An Image Generation and Editing Benchmark from Real-world Commercial Imaging Services},
  author = {F Ji and J Yang and Z Song and L Gao and J Liang and Z Chen and J Zhang and X Chen},
  booktitle = {ACL},
  year = {2026}
}

@inproceedings{ghosh2026when,
  title = {When Background Matters: Breaking Medical Vision Language Models by Transferable Attack},
  author = {A Ghosh and S Baidya and S Saha and X Chen},
  booktitle = {ACL, oral},
  year = {2026}
}

@inproceedings{han2026pastiche,
  title = {Pastiche Novel Generation Creating: Fan Fiction You Love in Your Favorite Author's Style},
  author = {X Han and Y Liu and M Li and W Liu and S Hu and R Yan and Z Xu and X Chen},
  booktitle = {ACL finding 2026},
  year = {2026}
}

@inproceedings{gao2026when,
  title = {When Personalization Tricks Detectors: The Feature-Inversion Trap in Machine-Generated Text Detection},
  author = {L Gao and X Li and C Wang and M Li and W Liu and Z Song and J Zhang and R Yan and P Nakov and ...},
  booktitle = {ACL 2026, oral},
  year = {2026}
}

@inproceedings{guo2025reactionteam,
  title = {ReactionTeam: Teaming Experts for Divergent Thinking Beyond Typical Reaction Patterns},
  author = {T Guo and C Ma and X Chen and B Nan and K Guo and S Pei and O Wiest and NV Chawla and X Zhang},
  booktitle = {2025 IEEE International Conference on Big Data (BigData), 520-529},
  year = {2025}
}

@inproceedings{wang2025quidsb,
  title = {QUIDS: Query Intent Description for Exploratory Search via Dual Space Modeling},
  author = {Y Wang and X Chen and S Verberne},
  booktitle = {Proceedings of the 2025 Conference on Empirical Methods in Natural Language …},
  year = {2025}
}

@inproceedings{yang2024think,
  title = {Think as People: Context-Driven Multi-Image News Captioning with Adaptive Dual Attention},
  author = {Q Yang and X Wu and X Chen and X Gao and X Zhang},
  booktitle = {ICASSP 2024-2024 IEEE International Conference on Acoustics, Speech and …},
  year = {2024}
}

@article{gao2023trend,
  title = {A Trend of AI Conference Convergence in Similarity: An Empirical Study Through Trans-Temporal Heterogeneous Graph},
  author = {S Gao and H Zhang and X Chen and C Tao and D Zhao and R Yan},
  journal = {IEEE Transactions on Knowledge and Data Engineering 35 (9), 9642-9655},
  year = {2023}
}

@inproceedings{yang2026distinguishable,
  title = {Distinguishable Deletion: Unifying Knowledge Erasure and Refusal for Large Language Model Unlearning},
  author = {P Yang and J Yu and Q Wang and P Torr and B Han and X Chen},
  booktitle = {ICML},
  year = {2026}
}

@inproceedings{gao2026cylindrical,
  title = {The Cylindrical Representation Hypothesis for Language Model Steering},
  author = {L Gao and J Zhang and W Liu and F Ji and C Wang and Z Song and A Ghosh and Y Mohamed and ...},
  booktitle = {ICML},
  year = {2026}
}

@misc{zhao2025unifyingb,
  title = {Unifying Search and Recommendation with Dual-View Representation Learning in a Generative Paradigm},
  author = {J Zhao and W Wang and C Xu and X Chen and Z Ren and S Verberne},
  booktitle = {arXiv preprint arXiv:2504.06714},
  year = {2025}
}

@inproceedings{song2025injectingb,
  title = {Injecting domain-specific knowledge into large language models: a comprehensive survey},
  author = {Z Song and B Yan and Y Liu and M Fang and M Li and R Yan and X Chen},
  booktitle = {EMNLP findings},
  year = {2025}
}

@misc{guo2023beyond,
  title = {Beyond the Typical: Modeling Rare Plausible Patterns in Chemical Reactions by Leveraging Sequential Mixture-of-Experts},
  author = {T Guo and C Ma and X Chen and B Nan and K Guo and S Pei and NV Chawla and O Wiest and X Zhang},
  booktitle = {arXiv preprint arXiv:2310.04674},
  year = {2023}
}

@inproceedings{yang2018evolutionary,
  title = {An Evolutionary Energy Prediction Model for Solar Energy-Harvesting Wireless Sensor Networks},
  author = {G Yang and X Hu and X Chen},
  booktitle = {International Conference of Pioneering Computer Scientists, Engineers and …},
  year = {2018}
}
```
