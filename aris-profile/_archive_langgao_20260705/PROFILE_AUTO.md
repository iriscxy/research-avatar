# PROFILE_AUTO — Lang Gao

**Source**: Google Scholar  ·  **Affiliation**: ByteDance | PhD Student in MBZUAI (verified email @mbzuai.ac.ae)
**Stats**: 363 citations · h-index 8 · i10 8
**Stated interests**: Mechanistic Interpretability · Trustworthy AI · Natural Language Processing
**Generated**: 2026-07-03 · **Publications**: 19 unique  ·  **task_type mix**: 2 engineering / 8 theory / 9 benchmark
**Corpus**: 18/19 abstracts · 18/19 local full-text (`fulltext/txt/`)
⚠ **Semantic Scholar was rate-limited this pass (HTTP 429)** — abstracts + arXiv ids were instead crawled **directly from arXiv** (via WebFetch, harness network) since sandboxed HTTP was throttled: **18/19 recovered** (only *GTA* is not on arXiv). BibTeX is built from Scholar metadata. The Scholar page itself is **complete** ("Show more" was disabled — 19 papers, not truncated). Full-text PDFs: 18/19 fetched (arXiv, by direct `arxiv.org/pdf/<id>` download + pdftotext); only *GTA* is missing (not on arXiv).

> `task_type` labels this pass are **abstract-informed** (18/19 abstracts crawled from arXiv). Lineage & Writing Style are informed inference from titles/venues/abstracts/coauthorship (Scholar exposes no advisor data).

## Research Identity

- **Niche subfields** (recent volume × recency):
  1. **Mechanistic interpretability & representation analysis / steering** *(stated #1)* — LM steering geometry (**lead**: *Cylindrical Representation Hypothesis*), emotion circuits, concept-representation bias probing, single-pass reasoning bounds, semantic reconstruction under perturbation, cross-lingual reasoning structure. This is the intellectual center.
  2. **Trustworthy & safe LLMs** — jailbreak attack/defense (**lead**: *Shaping the Safety Boundaries*; *Audio Jailbreak*), machine-generated-text detection & its evasion (**lead**: *Feature-Inversion Trap*, ACL Oral), bias evaluation.
  3. **LLM evaluation & benchmark construction** — social reasoning (*SocialMaze*), social-deduction strategy (*Beyond Survival*), multi-agent debate (*M3MAD-Bench*), image gen/edit (*ServImage*), vulnerability detection (**co-lead**: *VulDetectBench*), medical multimodal (**co-lead**: *MedTrinity-25M*), algorithmic graph reasoning (*GTA*).
  4. **LLM agents & agentic reasoning** — dynamic agentic workflows (*DyFlow*), multi-agent debate, graph-theory agents, social-deduction agents.
  5. **Multimodal & domain LLMs** — medicine (*MedTrinity-25M*), audio (*Audio Jailbreak*), images (*ServImage*), code/security (*VulDetectBench*).
- **Dominant methods** (what `mode: engineering` iterates):
  representation analysis & steering / circuit discovery · benchmark & dataset construction · jailbreak attack & defense · multi-agent / agentic frameworks · reasoning analysis (information-theoretic bounds, cross-lingual probing).
- **Active venues (last ~2y)**: ICML, ICLR, ACL (main / findings / **Oral**), EMNLP, NeurIPS, KDD, arXiv preprints.
- **Frequent collaboration**: recurring co-authorship with X. Chen's group (many shared papers) and with Z. Song, C. Wang, Z. Xu, K. Wan, P. Nakov.

## Research Lineage

Early-career (first papers **2024**). Entered via **large-scale data & evaluation + safety** — co-first on **MedTrinity-25M** (25M-image medical multimodal dataset, 123 cites) and **VulDetectBench** (79 cites), and lead on **Shaping the Safety Boundaries** (jailbreak understanding/defense, 49 cites), the three works that seeded a reputation in benchmarks and trustworthy LLMs. Through **2025** the center of gravity shifted decisively toward **mechanistic interpretability & representation analysis** — concept-representation bias probing, emotion circuits, the Fano-style reasoning bound, Typoglycemia semantic reconstruction, and cross-lingual reasoning structure — while sustaining the trustworthy-LLM (audio jailbreak, MGT-detection evasion) and agentic/eval (DyFlow, SocialMaze) fronts. **2026** consolidates the interpretability identity with a **lead** theory/method paper on **LM steering geometry** (*Cylindrical Representation Hypothesis*) plus continued benchmark output. Trajectory: **benchmarks/safety → interpretability & controllable representations**, with steering as the current frontier.

## Writing Style

*Informed inference from titles/venues/abstracts (18/19 abstracts available).*
- **Argument arc**: benchmark/dataset papers open **landscape-first** ("open", "comprehensive", "large-scale", "first"); interpretability/method papers appear **gap-first** (name a concrete LLM failure/limit, then close it).
- **Titling**: evocative two-part titles with a question or metaphor + a precise technical subtitle — *"Do LLMs 'Feel'? Emotion Circuits Discovery and Control"*, *"Under the Shadow of Babel: How Language Shapes Reasoning"*, *"When Personalization Tricks Detectors: The Feature-Inversion Trap"*.
- **Contribution framing**: benchmark papers foreground the released artifact + scale; method papers foreground a named mechanism/hypothesis (Cylindrical Representation Hypothesis, Feature-Inversion Trap).

## Experiment Templates

*Mined by `experiment_history.py` from 476 coding-agent sessions across all
`~/.claude/projects/*` (64,940 lines scanned, 2026-07-03). Source of truth:
`aris-profile/habits.json` (in-repo). **Adopted directly as Lang's stack per
user confirmation (2026-07-03)** — these are machine-level coding habits on the
working environment. Heuristic text scan; high-count items are clean signal.*

**Habitual stack** (what generated experiment code should match — NOT hyperparameter
values, which the experiment plan decides):
- **Launcher**: `deepspeed` (dominant, 171 hits) › `srun` (78, Slurm) › `accelerate launch` (60) › `modal run` (34) › `torchrun` (32). Default to DeepSpeed multi-GPU.
- **Framework / deps**: PyTorch-**Lightning** (top dep, 8509) + **TRL** (1367) + **vLLM** (996, inference) + `accelerate` (695) + `torch`; also `jax` (701). → LoRA/RLHF fine-tune + vLLM serving stack.
- **Default base model**: **Qwen3-4B-Instruct-2507** (125) and **Qwen3-7B-Instruct** (35) — Qwen3 is the habitual backbone.

**Resource habits**: A100 (479) · RTX 4090 (~305 across `4090`/`rtx 4090`) · H100 (119) · 3090 (112) · TPU (82) · A800 (81) · V100 (63) · L40 (60) · A6000 · H800 · MI250.

**Failure memory** (feeds the resource-/failure-aware planner):
- **OOM is the #1 recurring failure — 1322 hits.** On the habitual GPUs, default to a memory-safe setup (lower batch / raise grad-accum).
- High-frequency error types: `ValueError` (568), `RuntimeError` (529), plus generic `Exception`/`Error`/`Traceback`.
- Success signals: 191 checkpoints saved, 48 wandb runs.

*Scope note: hyperparameter VALUES (lr/batch/epochs/seed) are intentionally NOT
mined — they're task-determined, decided by `/workplan`. `habits.json` holds only the
genuinely-personal axes: toolchain, base model, hardware, failure memory.*

**Domain priors**:
- Common baselines: open LLMs (Qwen/Llama family), task-specific SOTA per subfield.
- Common metrics: accuracy / F1, attack-success-rate (safety), interpretability control accuracy, human eval.
- Common data: constructed benchmarks (a signature of this author group), public safety/social/medical datasets.

## Known Dead-Ends

*From the tacit-knowledge interview (user-confirmed 2026-07-03).*
- **Interpretability "causal insufficiency."** The recurring top-venue pushback on this line is that steering / circuit / representation findings are merely **correlational, not causal**. Any interpretability claim must ship with **causal-intervention evidence** — ablation, activation patching, or steering that changes behavior — not just probe accuracy or a direction that correlates. Do not present an interpretability result without the intervention that closes the causal gap.

## Workflow Preferences

*Distilled from `workflow_prefs.py` (476 sessions, 479 candidate preference turns;
categories: prohibition 157, process 142, correction 119, cadence 59, mandate 26,
rigor 24). **Adopted in full per user confirmation (2026-07-03).** These are **how work
is run in this environment** — consumed by experiment/paper skills to match the process,
not hyperparameters.*

| # | Preference | Why it matters / how to apply |
|---|---|---|
| **W1** | **Cheap/deterministic step first, then the expensive/LLM step.** | Stage pipelines so a cheap filter runs before any LLM/GPU call. Don't lead with the expensive operation. |
| **W2** | **Cache aggressively; support resume / no recomputation.** | Persist every intermediate artifact; key it for lookup; never recompute what exists. Resumability is a hard requirement. |
| **W3** | **Never overwrite prior outputs; preserve history.** | Write timestamped/versioned outputs; stopping should not destroy in-flight or prior results. |
| **W4** | **Modular, section-by-section generation — not one monolithic pass.** | Decompose long generations into independently-regenerable units. |
| **W5** | **Idea validation is a human-checked loop, not one-shot.** | Build accept/reject as iterate-with-checkpoint; surface to the user between rounds rather than auto-accepting. |
| **W6** | **Fixed research order: idea → experiments → paper.** | Sequence the pipeline in this order; don't jump to writing before evidence. |
| **W7** | **Specify baseline / metric / dataset explicitly before running.** | At experiment-design time, force concrete baseline+metric+dataset choices up front; no implicit defaults. |

## Publications Index

*19 unique papers. Sorted by year, then citations. `task_type` is **abstract-informed**
(18/19 abstracts crawled from arXiv). `full-text`: ✓ = local text in `fulltext/txt/<key>.txt`,
`abs` = abstract only (in `enriched.json`), — = neither. **Bold lead authorship** noted in
Research Identity; `*` in BibTeX marks co-first. arXiv ids live in `enriched.json`.*

| # | Year | Title | Venue | Cites | task_type | full-text |
|---|------|-------|-------|-------|-----------|-----------|
| 1 | 2026 | M3MAD-Bench: Are Multi-Agent Debates Really Effective Across … | arXiv:2601.02854 | 4 | benchmark | ✓ |
| 2 | 2026 | ServImage: An Image Generation and Editing Benchmark from Rea… | ACL 2026 | 1 | benchmark | ✓ |
| 3 | 2026 | One Model, Multiple Goals: Adaptive Multi-Objective Learning … | KDD 2026 | 0 | engineering | ✓ |
| 4 | 2026 | The Cylindrical Representation Hypothesis for Language Model … | ICML 2026 | 0 | theory | ✓ |
| 5 | 2025 | Audio jailbreak: An open comprehensive benchmark for jailbrea… | ACL 2026 | 20 | benchmark | ✓ |
| 6 | 2025 | Socialmaze: A benchmark for evaluating social reasoning in la… | arXiv:2505.23713 | 16 | benchmark | ✓ |
| 7 | 2025 | DyFlow: Dynamic Workflow Framework for Agentic Reasoning | NeurIPS 2025 | 14 | engineering | ✓ |
| 8 | 2025 | Do LLMs "Feel"? Emotion Circuits Discovery and Control | ICML 2026 | 13 | theory | ✓ |
| 9 | 2025 | Word Form Matters: LLMs' Semantic Reconstruction under Typogl… | ACL 2025 findings | 11 | theory | ✓ |
| 10 | 2025 | Adversarial Cooperative Rationalization: The Risk of Spurious… | ICML 2025 | 8 | theory | ✓ |
| 11 | 2025 | Evaluate bias without manual test sets: A concept representat… | arXiv:2505.15524 | 7 | theory | ✓ |
| 12 | 2025 | Beyond Survival: Evaluating LLMs in Social Deduction Games wi… | arXiv:2510.11389 | 6 | benchmark | ✓ |
| 13 | 2025 | A fano-style accuracy upper bound for llm single-pass reasoni… | ICLR 2026 | 5 | theory | ✓ |
| 14 | 2025 | Under the Shadow of Babel: How Language Shapes Reasoning in L… | EMNLP 2025 findings | 3 | theory | ✓ |
| 15 | 2025 | Gta: Graph theory agent and benchmark for algorithmic graph r… | (preprint) | 3 | benchmark | — |
| 16 | 2025 | When Personalization Tricks Detectors: The Feature-Inversion … | [Oral] ACL 2026 | 1 | benchmark | ✓ |
| 17 | 2024 | Medtrinity-25m: A large-scale multimodal dataset with multigr… | ICLR 2025 | 123 | benchmark | ✓ |
| 18 | 2024 | Vuldetectbench: Evaluating the deep capability of vulnerabili… | arXiv:2406.07595 | 79 | benchmark | ✓ |
| 19 | 2024 | Shaping the Safety Boundaries: Understanding and Defending Ag… | ACL 2025 | 49 | theory | ✓ |

## BibTeX Bank

```bibtex
@misc{li2026m3mad,
  title = {M3MAD-Bench: Are Multi-Agent Debates Really Effective Across Domains and Modalities?},
  author = {A Li and J Zhang and L Li and Y Duan and L Gao and M Chen and W Qin and S Li and F Ji and N Liu and L Cui and ...},
  booktitle = {arXiv preprint arXiv:2601.02854},
  year = {2026}
}

@inproceedings{ji2026servimage,
  title = {ServImage: An Image Generation and Editing Benchmark from Real-world Commercial Imaging Services},
  author = {F Ji and J Yang and Z Song and L Gao and J Liang and Z Chen and J Zhang and X Chen},
  booktitle = {ACL 2026},
  year = {2026}
}

@inproceedings{li2026one,
  title = {One Model, Multiple Goals: Adaptive Multi-Objective Learning for E-commerce Dialogue Systems},
  author = {M Li and J Xiang and E Zhou and L Gao and T Li and Q Zhang and X Zhang and X Chen},
  booktitle = {KDD 2026},
  year = {2026}
}

@inproceedings{gao2026cylindrical,
  title = {The Cylindrical Representation Hypothesis for Language Model Steering},
  author = {L Gao and J Zhang and W Liu and F Ji and C Wang and Z Song and A Ghosh and Y Mohamed and ...},
  booktitle = {ICML 2026},
  year = {2026}
}

@inproceedings{song2025audio,
  title = {Audio jailbreak: An open comprehensive benchmark for jailbreaking large audio-language models},
  author = {Z Song and Q Jiang and M Cui and M Li and L Gao and Z Zhang and Z Xu and Y Wang and C Wang and ...},
  booktitle = {ACL 2026},
  year = {2025}
}

@misc{xu2025socialmaze,
  title = {Socialmaze: A benchmark for evaluating social reasoning in large language models},
  author = {Z Xu and Y Wang and Y Huang and J Ye and H Zhuang and Z Song and L Gao and C Wang and Z Chen and ...},
  booktitle = {arXiv preprint arXiv:2505.23713},
  year = {2025}
}

@inproceedings{wang2025dyflow,
  title = {DyFlow: Dynamic Workflow Framework for Agentic Reasoning},
  author = {Y Wang and Z Xu and Y Huang and X Wang and Z Song and L Gao and C Wang and X Tang and ...},
  booktitle = {NeurIPS 2025},
  year = {2025}
}

@inproceedings{wang2025do,
  title = {Do LLMs" Feel"? Emotion Circuits Discovery and Control},
  author = {C Wang and Y Zhang and R Yu and Y Zheng and L Gao and Z Song and Z Xu and G Xia and H Zhang and ...},
  booktitle = {ICML 2026},
  year = {2025}
}

@inproceedings{wang2025word,
  title = {Word Form Matters: LLMs' Semantic Reconstruction under Typoglycemia},
  author = {C Wang and T Gu and Z Wei and L Gao and Z Song and X Chen},
  booktitle = {ACL 2025 findings},
  year = {2025}
}

@inproceedings{liu2025adversarial,
  title = {Adversarial Cooperative Rationalization: The Risk of Spurious Correlations in Even Clean Datasets},
  author = {W Liu and Z Niu and L Gao and Z Deng and J Wang and H Wang and R Li},
  booktitle = {ICML 2025},
  year = {2025}
}

@misc{gao2025evaluate,
  title = {Evaluate bias without manual test sets: A concept representation perspective for llms},
  author = {L Gao and K Wan and W Liu and C Wang and Z Song and Z Xu and Y Wang and V Stoyanov and ...},
  booktitle = {arXiv preprint arXiv:2505.15524},
  year = {2025}
}

@misc{song2025beyond,
  title = {Beyond Survival: Evaluating LLMs in Social Deduction Games with Human-Aligned Strategies},
  author = {Z Song and Y Huang and J Liu and H Luo and C Wang and L Gao and Z Xu and M Han and X Chang and ...},
  booktitle = {arXiv preprint arXiv:2510.11389},
  year = {2025}
}

@inproceedings{wan2025fano,
  title = {A fano-style accuracy upper bound for llm single-pass reasoning in multi-hop qa},
  author = {K Wan and L Gao and H Mu and P Nakov and Y Wang and X Chen},
  booktitle = {ICLR 2026},
  year = {2025}
}

@inproceedings{wang2025under,
  title = {Under the Shadow of Babel: How Language Shapes Reasoning in LLMs},
  author = {C Wang and Y Zhang and L Gao and Z Xu and Z Song and Y Wang and X Chen},
  booktitle = {EMNLP 2025 findings},
  year = {2025}
}

@misc{xu2025gta,
  title = {Gta: Graph theory agent and benchmark for algorithmic graph reasoning with llms},
  author = {Z Xu and Y Wang and C Wang and L Gao and Z Song and Y Huang and Z Chen and X Zhang and ...},
  year = {2025}
}

@inproceedings{gao2025when,
  title = {When Personalization Tricks Detectors: The Feature-Inversion Trap in Machine-Generated Text Detection},
  author = {L Gao and X Li and C Wang and M Li and W Liu and Z Song and J Zhang and R Yan and P Nakov and ...},
  booktitle = {[Oral] ACL 2026},
  year = {2025}
}

@inproceedings{xie2024medtrinity,
  title = {Medtrinity-25m: A large-scale multimodal dataset with multigranular annotations for medicine},
  author = {Y Xie* and C Zhou* and L Gao* and J Wu* and X Li and HY Zhou and S Liu and L Xing and J Zou and C Xie and ...},
  booktitle = {ICLR 2025},
  year = {2024}
}

@misc{liu2024vuldetectbench,
  title = {Vuldetectbench: Evaluating the deep capability of vulnerability detection with large language models},
  author = {Y Liu* and L Gao* and M Yang* and Y Xie and P Chen and X Zhang and W Chen},
  booktitle = {arXiv preprint arXiv:2406.07595},
  year = {2024}
}

@inproceedings{gao2024shaping,
  title = {Shaping the Safety Boundaries: Understanding and Defending Against Jailbreaks in Large Language Models},
  author = {L Gao and J Geng and X Zhang and P Nakov and X Chen},
  booktitle = {ACL 2025},
  year = {2024}
}
```
