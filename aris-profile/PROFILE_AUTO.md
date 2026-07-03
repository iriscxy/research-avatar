# PROFILE_AUTO — Xiuying Chen

**Source**: Google Scholar  ·  **Affiliation**: MBZUAI
**Stats**: 5714 citations · h-index 32 · i10 77
**Stated interests**: Trustworthy NLP · Human-Centered NLP · Computational Social Science
**Generated**: 2026-07-01 · **Publications**: 94 unique  ·  **task_type mix**: 67 engineering / 12 theory / 15 benchmark
**Corpus**: 81/94 have abstracts · 84/94 have local full-text (`fulltext/txt/`)
⚠ **Scholar was truncated at 100 raw rows** ('Show more' still active); those 100 deduplicated to 94 unique papers. Publications beyond the first ~100 Scholar rows may still be missing — re-export a fully-expanded `gs.html` for the complete record.

> `task_type` labels are abstract-informed this pass (81/94 abstracts fetched via
> arXiv/Crossref/S2). Lineage & Writing Style remain informed inference from
> titles/venues/abstracts (Scholar exposes no advisor data).

## Research Identity

- **Niche subfields** (recent volume × recency):
  1. **Trustworthy & Safe LLMs** *(stated #1)* — jailbreak attack/defense, bias eval & mitigation, watermarking, machine-text detection, unlearning, trustworthiness frameworks.
  2. **LLM multi-agent social simulation / computational social science** — misinformation & opinion-dynamics simulation, echo chambers, persona/society simulation. Anchored by the flagship multi-agent survey.
  3. **Domain LLMs for medicine & science** — dermatology (Nature Comms), chemistry/bioinformatics agents, medical reasoning RL.
  4. **LLM reasoning, robustness & interpretability** — distraction/robustness, emotion circuits, representation hypotheses, single-pass reasoning bounds.
  5. **(fading) Summarization / generation & generative IR** — the PhD-era backbone.
- **Dominant methods** (what `mode: engineering` iterates):
  benchmark/toolkit construction · LLM multi-agent simulation · representation analysis & steering · retrieval/memory augmentation · contrastive learning / KD / curriculum · graph modeling over text.
- **Active venues (last 3y)**: ACL (main/findings), arXiv preprints, SIGIR, IJCAI, EMNLP, NeurIPS, Nature Communications, ICML/ICLR.

## Research Lineage

Started in **text summarization & generation** (2018–2021, EMNLP/AAAI/IJCAI/SIGIR) with structure/graph/contrastive methods. Bridged into the LLM era via **retrieval/memory augmentation & faithfulness** (Self-Memory RAG @ NeurIPS) while opening a **medical/scientific** front. From 2024 the center shifted to **LLMs as social actors and objects of trust** — the multi-agent survey became the throughline, spawning (a) *simulating* society with LLM agents and (b) *auditing* LLMs for safety/bias/trust. Newest 2025–2026 work turns toward **mechanistic interpretability / steering** — from black-box evaluation to white-box control.

## Writing Style

- **Argument arc**: typically **gap-first** — name a concrete shortcoming in current LLM behavior, then position the contribution as closing it; survey/benchmark papers open **landscape-first**.
- **Contribution phrasing**: enumerated bullets, each leading with the artifact ("We propose / We build / We release"), benchmark papers foreground "first / comprehensive / unified".
- **Cadence**: dense related-work grounding; empirical papers lead Method with a one-paragraph overview before components.

## Experiment Templates

*Mined by `experiment_history.py` from 473 coding-agent sessions across all
`~/.claude/projects/*` (61,644 lines scanned, 2026-07-01). Source of truth:
`aris-profile/habits.json` (in-repo). Heuristic text scan — high-count clean
signal below; low-count items may be regex noise, not real habits.*

**Habitual stack** (what generated experiment code should match — NOT hyperparameter
values, which the experiment plan decides):
- **Launcher**: `deepspeed` (dominant, 137 hits) › `srun` (64, Slurm) › `accelerate launch` (37) › `modal run` (22) › `torchrun` (20). Default to DeepSpeed multi-GPU.
- **Framework / deps**: PyTorch-**Lightning** (top dep) + **TRL** (1287) + **vLLM** (936, inference) + **PEFT/LoRA** (278); also `accelerate`, `transformers`, `datasets`, `fsdp`. → LoRA/RLHF fine-tune + vLLM serving stack.
- **Default base model**: **Qwen3-4B-Instruct-2507** (125) and **Qwen3-7B-Instruct** (35) — Qwen3 is the habitual backbone; Mixtral/Mistral appear occasionally.

**Resource habits**: A100 (276) · RTX 4090 (~190) · 3090 (68) · TPU (62) · A800 (59) · H100 (55) · V100 (41) · L40 (38) · A6000 · H800 · MI250.

**Failure memory** (feeds the resource-/failure-aware planner):
- **OOM is the #1 recurring failure — 1127 hits.** On the habitual GPUs, default to a memory-safe setup (lower batch / raise grad-accum).
- High-frequency error types: `ValueError` (548), `RuntimeError` (509), `ImportError` (164).
- Success signals: 180 checkpoints saved, 36 wandb runs.

*Scope note: hyperparameter VALUES (lr/batch/epochs/seed) are intentionally NOT
mined — they're task-determined, not personal. `habits.json` holds only the
genuinely-personal axes: toolchain, base model, hardware, failure memory.*

**Domain priors**:
- Common baselines: open LLMs (Qwen/Llama family), task-specific SOTA per subfield.
- Common metrics: accuracy / F1, attack-success-rate (safety), citation/factuality scores, human eval.
- Common data: constructed benchmarks (this author's signature), public safety/social datasets.

## Workflow Preferences

*Distilled from `workflow_prefs.py` (473 sessions, 456 candidate preference turns;
categories: prohibition 149, process 139, correction 110, cadence 56, rigor/mandate 23
each) and **user-confirmed 2026-06-30**. These are **how the researcher likes to
work** — consumed by experiment/paper skills to match her process, not her
hyperparameters. The 2026-07-01 re-mine reproduced the same signal; W1–W7 unchanged.*

| # | Preference | Evidence | Why it matters / how to apply |
|---|---|---|---|
| **W1** | **Cheap/deterministic step first, then the expensive/LLM step.** | "先显示 survey 再出报告"; "先做确定性统计计算,再由 LLM 裁定"; "先验证 idea 再细化" | Stage pipelines so a cheap filter runs before any LLM/GPU call. Don't lead with the expensive operation. |
| **W2** | **Cache aggressively; support resume / no recomputation.** | "不要每次重新算 embedding"; "断点续写按 DOI 重排"; "candidate 单独存好,不然每次重新 retrieve" | Persist every intermediate artifact; key it for lookup; never recompute what exists. Resumability is a hard requirement. |
| **W3** | **Never overwrite prior outputs; preserve history.** | "每次不要覆盖之前的论文"; "立刻停止,不要等当前爬完" | Write timestamped/versioned outputs; stopping should not destroy in-flight or prior results. |
| **W4** | **Modular, section-by-section generation — not one monolithic pass.** | "分成摘要/intro/method/experiment 几节,每节单独生成" | Decompose long generations into independently-regenerable units. |
| **W5** | **Idea validation is a human-checked loop, not one-shot.** | "如果没通过,加入和大模型讨论…用户来检验,通过再走审稿" | Build accept/reject as iterate-with-checkpoint; surface to the user between rounds rather than auto-accepting. |
| **W6** | **Fixed research order: idea → experiments → paper.** | "应该是 idea 做实验 写论文 这个顺序" | Sequence the four commands in this order; don't jump to writing before evidence. |
| **W7** | **Specify baseline / metric / dataset explicitly before running.** | "我要比较的 baseline、要用的 metric、数据集等等" | At experiment-design time, force concrete baseline+metric+dataset choices up front; no implicit defaults. |

## Publications Index

*94 unique papers (after removing 6 Scholar duplicate-citation rows of the flagship
survey). Sorted by year, then citations. `full-text`: ✓ = local text in
`fulltext/txt/<key>.txt`, `abs` = abstract only, — = neither (closed venue / not on arXiv).*

| # | Year | Title | Venue | Cites | task_type | full-text |
|---|------|-------|-------|-------|-----------|-----------|
| 1 | 2026 | Do LLMs" Feel"? Emotion Circuits Discovery and Control | ICML | 13 | engineering | ✓ |
| 2 | 2026 | Audio jailbreak: An open comprehensive benchmark for jailbreaking  | ACL 2026 | 13 | benchmark | ✓ |
| 3 | 2026 | CURE-Med: Curriculum-Informed Reinforcement Learning for Multiling | ACL 2026 | 9 | engineering | ✓ |
| 4 | 2026 | A fano-style accuracy upper bound for llm single-pass reasoning in | ICLR | 5 | theory | ✓ |
| 5 | 2025 | Injecting domain-specific knowledge into large language models: a  | EMNLP findings, https://aclant | 142 | benchmark | ✓ |
| 6 | 2025 | On the trustworthiness of generative foundation models: Guideline, | arXiv preprint arXiv:2502.1429 | 57 | engineering | ✓ |
| 7 | 2025 | The Truth Becomes Clearer Through Debate! Multi-Agent Systems with | SIGIR 2025 | 49 | engineering | ✓ |
| 8 | 2025 | Maniplvm-r1: Reinforcement learning for reasoning in embodied mani | AAAI 2026 | 36 | engineering | ✓ |
| 9 | 2025 | From a tiny slip to a giant leap: An llm-based simulation for fake | EMNLP main conference | 27 | engineering | ✓ |
| 10 | 2025 | Unveiling the power of language models in chemical research questi | Communications Chemistry 8 (1) | 27 | engineering | ✓ |
| 11 | 2025 | A Cognitive Writing Perspective for Constrained Long-Form Text Gen | ACL finding 2025 | 22 | engineering | ✓ |
| 12 | 2025 | Breaking focus: Contextual distraction curse in large language mod | NeurIPS | 19 | theory | — |
| 13 | 2025 | The stepwise deception: Simulating the evolution from true news to | Proceedings of the 2025 Confer | 18 | engineering | ✓ |
| 14 | 2025 | CulFiT: A Fine-grained Cultural-aware LLM Training Paradigm via Mu | ACL 2025 main | 16 | engineering | ✓ |
| 15 | 2025 | Evaluating and mitigating bias in AI-based medical text generation | Nature Computational Science 5 | 16 | engineering | ✓ |
| 16 | 2025 | Socialmaze: A benchmark for evaluating social reasoning in large l | arXiv preprint arXiv:2505.2371 | 15 | benchmark | ✓ |
| 17 | 2025 | Peddet: Adaptive spectral optimization for multimodal pedestrian d | ECAI | 14 | engineering | ✓ |
| 18 | 2025 | Beyond Profile: From Surface-Level Facts to Deep Persona Simulatio | ACL finding 2025 | 13 | engineering | ✓ |
| 19 | 2025 | More is not always better? Enhancing Many-Shot In-Context Learning | ACL main 2025 | 13 | engineering | ✓ |
| 20 | 2025 | DyFlow: Dynamic Workflow Framework for Agentic Reasoning | NeurIPS 2025 | 12 | engineering | ✓ |
| 21 | 2025 | Cross-Lingual Pitfalls: Automatic Probing Cross-Lingual Weakness o | ACL main 2025 | 11 | theory | ✓ |
| 22 | 2025 | Trusteval: A dynamic evaluation toolkit on trustworthiness of gene | Proceedings of the 2025 Confer | 10 | benchmark | ✓ |
| 23 | 2025 | Word Form Matters: LLMs' Semantic Reconstruction under Typoglycemi | ACL finding 2025 | 10 | theory | ✓ |
| 24 | 2025 | Unifying search and recommendation: A generative paradigm inspired | arXiv e-prints, arXiv: 2504.06 | 9 | theory | — |
| 25 | 2025 | A Symbolic Adversarial Learning Framework for Evolving Fake News G | EMNLP main conference | 8 | engineering | ✓ |
| 26 | 2025 | Evaluate bias without manual test sets: A concept representation p | arXiv preprint arXiv:2505.1552 | 7 | theory | ✓ |
| 27 | 2025 | Beyond Survival: Evaluating LLMs in Social Deduction Games with Hu | arXiv preprint arXiv:2510.1138 | 6 | benchmark | ✓ |
| 28 | 2025 | FineState-Bench: A Comprehensive Benchmark for Fine-Grained State  | arXiv preprint arXiv:2508.0924 | 6 | benchmark | ✓ |
| 29 | 2025 | From Individuals to Crowds: Dual-Level Public Response Prediction  | ACM MM 2025 | 6 | engineering | ✓ |
| 30 | 2025 | Flipping Knowledge Distillation: Leveraging Small Models' Expertis | ACL main 2025 | 5 | engineering | ✓ |
| 31 | 2024 | Large language model based multi-agents: A survey of progress and  | IJCAI 2024 | 1950 | benchmark | ✓ |
| 32 | 2024 | Opportunities and challenges for ChatGPT and large language models | Briefings in Bioinformatics 25 | 525 | benchmark | ✓ |
| 33 | 2024 | Pre-trained multimodal large language model enhances dermatologica | Nature Communications 15 (1),  | 253 | engineering | abs |
| 34 | 2024 | From Skepticism to Acceptance: Simulating the Attitude Dynamics To | IJCAI 2024 | 97 | engineering | ✓ |
| 35 | 2024 | An AI agent for fully automated multi‐omic analyses | Advanced Science 11 (44), 2407 | 96 | engineering | abs |
| 36 | 2024 | A multi-agent conversational recommender system | arXiv preprint arXiv:2402.0113 | 84 | engineering | ✓ |
| 37 | 2024 | Decoding Echo Chambers: LLM-Powered Simulations Revealing Polariza | COLING 2025 | 58 | engineering | ✓ |
| 38 | 2024 | Shaping the Safety Boundaries: Understanding and Defending Against | ACL main 2025 | 47 | theory | ✓ |
| 39 | 2024 | Autobench-v: Can large vision-language models benchmark themselves | arXiv preprint arXiv:2410.2125 | 22 | benchmark | ✓ |
| 40 | 2024 | Hazards in Daily Life? Enabling Robots to Proactively Detect and R | NAACL main conference | 22 | engineering | ✓ |
| 41 | 2024 | Scholarchemqa: Unveiling the power of language models in chemical  | arXiv preprint arXiv:2407.1693 | 15 | benchmark | ✓ |
| 42 | 2024 | Unify graph learning with text: Unleashing llm potentials for sess | Proceedings of the ACM Web Con | 15 | engineering | ✓ |
| 43 | 2024 | LLM-driven agents for influencer selection in digital advertising  | arXiv preprint arXiv:2403.1510 | 13 | engineering | — |
| 44 | 2024 | Leveraging professional radiologists’ expertise to enhance LLMs’ e | ArXiv, arXiv: 2401.16578 v3 | 12 | benchmark | ✓ |
| 45 | 2024 | A large-scale time-aware agents simulation for influencer selectio | arXiv preprint arXiv:2411.0114 | 10 | engineering | ✓ |
| 46 | 2024 | Leveraging Professional Radiologists' Expertise to Enhance LLMs' E | 2024 IEEE 12th International C | 9 | benchmark | abs |
| 47 | 2024 | Thinking Before Running! Efficient Code Generation with Thorough E | ACL finding 2025 | 8 | engineering | ✓ |
| 48 | 2024 | What affects the stability of tool learning? an empirical study on | arXiv preprint arXiv:2407.0300 | 7 | theory | ✓ |
| 49 | 2024 | Mmac-copilot: Multi-modal agent collaboration operating copilot | arXiv preprint arXiv:2404.1807 | 7 | engineering | ✓ |
| 50 | 2024 | Unified multi-scenario summarization evaluation and explanation | IEEE Transactions on Knowledge | 6 | benchmark | — |
| 51 | 2024 | Flexible and Adaptable Summarization via Expertise Separation | SIGIR 2024 | 6 | engineering | ✓ |
| 52 | 2024 | Rethinking Scientific Summarization Evaluation: Grounding Explaina | TOIS | 6 | benchmark | ✓ |
| 53 | 2024 | Write Summary Step-by-Step: A Pilot Study of Stepwise Summarizatio | IEEE/ACM Transactions on Audio | 6 | engineering | ✓ |
| 54 | 2023 | Lift yourself up: Retrieval-augmented text generation with self-me | Advances in Neural Information | 202 | engineering | ✓ |
| 55 | 2023 | Interactive natural language processing | arXiv preprint arXiv:2305.1324 | 89 | benchmark | ✓ |
| 56 | 2023 | SkinGPT-4: an interactive dermatology diagnostic system with visua | Nature Communications | 75 | engineering | ✓ |
| 57 | 2023 | Follow the timeline! generating an abstractive and extractive time | ACM Transactions on Informatio | 33 | engineering | abs |
| 58 | 2023 | Dialogue summarization with static-dynamic structure fusion graph | Proceedings of the 61st Annual | 26 | engineering | ✓ |
| 59 | 2023 | EZInterviewer: To Improve Job Interview Performance with Mock Inte | WSDM 2023 | 26 | engineering | ✓ |
| 60 | 2023 | Towards a unified framework for reference retrieval and related wo | Findings of the Association fo | 25 | engineering | ✓ |
| 61 | 2023 | Improving the Robustness of Summarization Systems with Dual Augmen | ACL 2023 | 21 | theory | ✓ |
| 62 | 2023 | Path to medical agi: Unify domain-specific medical llms with the l | arXiv preprint arXiv:2306.1076 | 20 | engineering | ✓ |
| 63 | 2023 | A Topic-aware Summarization Framework with Different Modal Side In | SIGIR 2023 | 19 | engineering | ✓ |
| 64 | 2023 | Decouple knowledge from paramters for plug-and-play language model | Findings of the Association fo | 15 | engineering | ✓ |
| 65 | 2023 | Automated bioinformatics analysis via autoba | arXiv preprint arXiv:2309.0324 | 14 | engineering | ✓ |
| 66 | 2023 | Towards personalized review summarization by modeling historical r | arXiv preprint arXiv:2301.1168 | 12 | engineering | ✓ |
| 67 | 2023 | Learning towards Selective Data Augmentation for Dialogue Generati | AAAI 2023 | 10 | engineering | ✓ |
| 68 | 2023 | Unleashing the power of large models: Exploring human-machine conv | Proceedings of the 22nd Chines | 8 | engineering | — |
| 69 | 2023 | Stylized dialogue generation with feature-guided knowledge augment | Findings of the Association fo | 7 | engineering | ✓ |
| 70 | 2022 | Towards improving faithfulness in abstractive summarization | Advances in Neural Information | 61 | engineering | ✓ |
| 71 | 2022 | Target-aware Abstractive Related Work Generation with Contrastive  | SIGIR 2022 | 44 | engineering | ✓ |
| 72 | 2022 | Scientific Paper Extractive Summarization Enhanced by Citation Gra | EMNLP 2022 | 20 | engineering | ✓ |
| 73 | 2022 | Keywords and Instances: A Hierarchical Contrastive Learning Framew | ACL 2022 | 19 | engineering | ✓ |
| 74 | 2022 | HeteroQA: Learning towards question-and-answering through multiple | Proceedings of the Fifteenth A | 12 | engineering | ✓ |
| 75 | 2022 | Unsupervised mitigating gender bias by character components: A cas | Proceedings of the 4th Worksho | 11 | engineering | ✓ |
| 76 | 2021 | Capturing relations between scientific papers: An abstractive mode | Proceedings of the 59th Annual | 73 | engineering | ✓ |
| 77 | 2021 | Combining curriculum learning and knowledge distillation for dialo | Findings of the Association fo | 42 | engineering | ✓ |
| 78 | 2021 | How does Truth Evolve into Fake News? An Empirical Study of Fake N | The Web Conference 2021, Works | 13 | theory | ✓ |
| 79 | 2020 | VMSMO: Learning to Generate Multimodal Summary for Video-based New | EMNLP | 116 | engineering | ✓ |
| 80 | 2020 | Meaningful Answer Generation of E-Commerce Question-Answering | TOIS | 57 | engineering | ✓ |
| 81 | 2020 | Learning to respond with stickers: A framework of unifying multi-m | Proceedings of the Web Confere | 49 | engineering | ✓ |
| 82 | 2020 | From Standard Summarization to New Tasks and Beyond: Summarization | IJCAI 2020 | 40 | engineering | ✓ |
| 83 | 2020 | Selection and generation: Learning towards multi-product advertise | Proceedings of the 2020 Confer | 29 | engineering | ✓ |
| 84 | 2020 | The Style-Content Duality of Attractiveness: Learning to Write Eye | AAAI | 23 | engineering | ✓ |
| 85 | 2020 | Learning to Respond with Your Favorite Stickers: A Framework of Un | TOIS | 21 | engineering | ✓ |
| 86 | 2020 | Reasoning in Dialog: Improving Response Generation by Context Read | AAAI | 17 | theory | ✓ |
| 87 | 2020 | Infusing Sequential Information into Conditional Masked Translatio | COLING | 8 | engineering | ✓ |
| 88 | 2019 | Learning towards Abstractive Timeline Summarization | IJCAI, 4939-4945 | 60 | engineering | ✓ |
| 89 | 2019 | Modeling personalization in continuous space for response generati | EMNLP 2019, 1931-1940 | 51 | engineering | ✓ |
| 90 | 2019 | Stick to facts: Towards fidelity-oriented product description gene | EMNLP 2019 | 34 | engineering | ✓ |
| 91 | 2019 | How to Write Summaries with Patterns? Learning towards Abstractive | EMNLP 2019 | 33 | engineering | ✓ |
| 92 | 2018 | Abstractive Text Summarization by Incorporating Reader Comments | AAAI 2019 | 98 | engineering | ✓ |
| 93 | 2018 | Privacy-preserving collaborative model learning: The case of word  | IEEE Transactions on Knowledge | 76 | engineering | — |
| 94 | 2018 | Iterative Document Representation Learning Towards Summarization w | EMNLP 2018 | 50 | theory | ✓ |

## BibTeX Bank

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

@inproceedings{gao2018abstractive,
  title = {Abstractive Text Summarization by Incorporating Reader Comments},
  author = {S Gao and X Chen and P Li and Z Ren and L Bing and D Zhao and R Yan},
  booktitle = {AAAI 2019},
  year = {2018}
}

@inproceedings{liu2024skepticism,
  title = {From Skepticism to Acceptance: Simulating the Attitude Dynamics Toward Fake News},
  author = {Y Liu and X Chen and X Zhang and X Gao and J Zhang and R Yan},
  booktitle = {IJCAI 2024},
  year = {2024}
}

@inproceedings{zhou2024ai,
  title = {An AI agent for fully automated multi‐omic analyses},
  author = {J Zhou and B Zhang and G Li and X Chen and H Li and X Xu and S Chen and W He and C Xu and L Liu and ...},
  booktitle = {Advanced Science 11 (44), 2407094},
  year = {2024}
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

@inproceedings{wang2024decoding,
  title = {Decoding Echo Chambers: LLM-Powered Simulations Revealing Polarization in Social Networks},
  author = {C Wang and Z Liu and D Yang and X Chen},
  booktitle = {COLING 2025},
  year = {2024}
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

@inproceedings{liu2025truth,
  title = {The Truth Becomes Clearer Through Debate! Multi-Agent Systems with Large Language Models Unmask Fake News},
  author = {Y Liu and Y Liu and X Zhang and X Chen and R Yan},
  booktitle = {SIGIR 2025},
  year = {2025}
}

@inproceedings{gao2020learning,
  title = {Learning to respond with stickers: A framework of unifying multi-modality in multi-turn dialog},
  author = {S Gao and X Chen and C Liu and L Liu and D Zhao and R Yan},
  booktitle = {Proceedings of the Web Conference 2020, 1138-1148},
  year = {2020}
}

@inproceedings{gao2024shaping,
  title = {Shaping the Safety Boundaries: Understanding and Defending Against Jailbreaks in Large Language Models},
  author = {L Gao and X Zhang and P Nakov and X Chen},
  booktitle = {ACL main 2025},
  year = {2024}
}

@inproceedings{chen2022target,
  title = {Target-aware Abstractive Related Work Generation with Contrastive Learning},
  author = {X Chen and H Alamro and M Li and S Gao and R Yan and X Gao and X Zhang},
  booktitle = {SIGIR 2022},
  year = {2022}
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

@inproceedings{chan2019stick,
  title = {Stick to facts: Towards fidelity-oriented product description generation},
  author = {Z Chan and X Chen and Y Wang and J Li and Z Zhang and K Gai and D Zhao and R Yan},
  booktitle = {EMNLP 2019},
  year = {2019}
}

@article{chen2023follow,
  title = {Follow the timeline! generating an abstractive and extractive timeline summary in chronological order},
  author = {X Chen and M Li and S Gao and Z Chan and D Zhao and X Gao and X Zhang and R Yan},
  journal = {ACM Transactions on Information Systems 41 (1), 1-30},
  year = {2023}
}

@inproceedings{gao2019how,
  title = {How to Write Summaries with Patterns? Learning towards Abstractive Summarization through Prototype Editing},
  author = {S Gao and X Chen and P Li and Z Chan and D Zhao and R Yan},
  booktitle = {EMNLP 2019},
  year = {2019}
}

@inproceedings{chan2020selection,
  title = {Selection and generation: Learning towards multi-product advertisement post generation},
  author = {Z Chan and Y Zhang and X Chen and S Gao and Z Zhang and D Zhao and R Yan},
  booktitle = {Proceedings of the 2020 Conference on Empirical Methods in Natural Language …},
  year = {2020}
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

@inproceedings{shi2023towards,
  title = {Towards a unified framework for reference retrieval and related work generation},
  author = {Z Shi and S Gao and Z Zhang and X Chen and Z Chen and P Ren and Z Ren},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2023, 5785-5799},
  year = {2023}
}

@inproceedings{li2020style,
  title = {The Style-Content Duality of Attractiveness: Learning to Write Eye-Catching Headlines via Disentanglement},
  author = {M Li and X Chen and M Yang and S Gao and D Zhao and R Yan},
  booktitle = {AAAI},
  year = {2020}
}

@inproceedings{wan2025cognitive,
  title = {A Cognitive Writing Perspective for Constrained Long-Form Text Generation},
  author = {K Wan and H Mu and R Hao and H Luo and T Gu and X Chen},
  booktitle = {ACL finding 2025},
  year = {2025}
}

@misc{bao2024autobench,
  title = {Autobench-v: Can large vision-language models benchmark themselves?},
  author = {H Bao and Y Huang and Y Wang and J Ye and X Wang and X Chen and Y Zhao and T Zhou and ...},
  booktitle = {arXiv preprint arXiv:2410.21259},
  year = {2024}
}

@inproceedings{song2024hazards,
  title = {Hazards in Daily Life? Enabling Robots to Proactively Detect and Resolve Anomalies},
  author = {Z Song and G Ouyang and M Fang and H Na and Z Shi and Z Chen and Y Fu and Z Zhang and S Jiang and ...},
  booktitle = {NAACL main conference},
  year = {2024}
}

@inproceedings{chen2023improving,
  title = {Improving the Robustness of Summarization Systems with Dual Augmentation},
  author = {X Chen and G Long and C Tao and M Li and X Gao and C Zhang and X Zhang},
  booktitle = {ACL 2023},
  year = {2023}
}

@inproceedings{gao2020learningb,
  title = {Learning to Respond with Your Favorite Stickers: A Framework of Unifying Multi-Modality and User Preference in Multi-Turn Dialog},
  author = {S Gao and X Chen and L Liu and D Zhao and R Yan},
  booktitle = {TOIS},
  year = {2020}
}

@misc{zhou2023path,
  title = {Path to medical agi: Unify domain-specific medical llms with the lowest cost},
  author = {J Zhou and X Chen and X Gao},
  booktitle = {arXiv preprint arXiv:2306.10765},
  year = {2023}
}

@inproceedings{chen2022scientific,
  title = {Scientific Paper Extractive Summarization Enhanced by Citation Graphs},
  author = {X Chen and M Li and S Gao and R Yan and X Gao and X Zhang},
  booktitle = {EMNLP 2022},
  year = {2022}
}

@inproceedings{huang2025breaking,
  title = {Breaking focus: Contextual distraction curse in large language models},
  author = {Y Huang and Y Wang and Z Xu and C Gao and S Wu and J Ye and X Chen and PY Chen and X Zhang},
  booktitle = {NeurIPS},
  year = {2025}
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

@inproceedings{liu2025stepwise,
  title = {The stepwise deception: Simulating the evolution from true news to fake news with llm agents},
  author = {Y Liu and Z Song and J Zhang and X Zhang and X Chen and R Yan},
  booktitle = {Proceedings of the 2025 Conference on Empirical Methods in Natural Language …},
  year = {2025}
}

@inproceedings{chen2020reasoning,
  title = {Reasoning in Dialog: Improving Response Generation by Context Reading Comprehension},
  author = {X Chen and Z Cui and J Zhang and C Wei and J Cui and B Wang and D Zhao and R Yan},
  booktitle = {AAAI},
  year = {2020}
}

@inproceedings{feng2025culfit,
  title = {CulFiT: A Fine-grained Cultural-aware LLM Training Paradigm via Multilingual Critique Data Synthesis},
  author = {R Feng and S Gao and X Chen and L Chen and S Shang},
  booktitle = {ACL 2025 main},
  year = {2025}
}

@article{chen2025evaluating,
  title = {Evaluating and mitigating bias in AI-based medical text generation},
  author = {X Chen and T Wang and J Zhou and Z Song and X Gao and X Zhang},
  journal = {Nature Computational Science 5 (5), 388-396},
  year = {2025}
}

@misc{xu2025socialmaze,
  title = {Socialmaze: A benchmark for evaluating social reasoning in large language models},
  author = {Z Xu and Y Wang and Y Huang and J Ye and H Zhuang and Z Song and L Gao and C Wang and Z Chen and ...},
  booktitle = {arXiv preprint arXiv:2505.23713},
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

@inproceedings{zhao2025peddet,
  title = {Peddet: Adaptive spectral optimization for multimodal pedestrian detection},
  author = {R Zhao and Z Zhang and Y Xu and Y Yao and Y Huang and W Zhang and Z Song and X Chen and ...},
  booktitle = {ECAI},
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

@inproceedings{song2026audio,
  title = {Audio jailbreak: An open comprehensive benchmark for jailbreaking large audio-language models},
  author = {Z Song and Q Jiang and M Cui and M Li and L Gao and Z Zhang and Z Xu and Y Wang and C Wang and ...},
  booktitle = {ACL 2026},
  year = {2026}
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

@inproceedings{wang2025dyflow,
  title = {DyFlow: Dynamic Workflow Framework for Agentic Reasoning},
  author = {Y Wang and Z Xu and Y Huang and X Wang and Z Song and L Gao and C Wang and X Tang and ...},
  booktitle = {NeurIPS 2025},
  year = {2025}
}

@misc{zhu2024leveraging,
  title = {Leveraging professional radiologists’ expertise to enhance LLMs’ evaluation for radiology reports},
  author = {Q Zhu and X Chen and Q Jin and B Hou and TS Mathai and P Mukherjee and X Gao and ...},
  booktitle = {ArXiv, arXiv: 2401.16578 v3},
  year = {2024}
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

@inproceedings{wang2025word,
  title = {Word Form Matters: LLMs' Semantic Reconstruction under Typoglycemia},
  author = {C Wang and T Gu and Z Wei and L Gao and Z Song and X Chen},
  booktitle = {ACL finding 2025},
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

@misc{song2024mmac,
  title = {Mmac-copilot: Multi-modal agent collaboration operating copilot},
  author = {Z Song and Y Li and M Fang and Y Li and Z Chen and Z Shi and Y Huang and X Chen and L Chen},
  booktitle = {arXiv preprint arXiv:2404.18074},
  year = {2024}
}

@inproceedings{li2023stylized,
  title = {Stylized dialogue generation with feature-guided knowledge augmentation},
  author = {J Li and Z Zhang and X Chen and D Zhao and R Yan},
  booktitle = {Findings of the Association for Computational Linguistics: EMNLP 2023, 7144-7157},
  year = {2023}
}

@misc{song2025beyond,
  title = {Beyond Survival: Evaluating LLMs in Social Deduction Games with Human-Aligned Strategies},
  author = {Z Song and Y Huang and J Liu and H Luo and C Wang and L Gao and Z Xu and M Han and X Chang and ...},
  booktitle = {arXiv preprint arXiv:2510.11389},
  year = {2025}
}

@misc{ji2025finestate,
  title = {FineState-Bench: A Comprehensive Benchmark for Fine-Grained State Control in GUI Agents},
  author = {F Ji and J Yang and Z Song and Y Wang and Z Cui and Y Li and Q Jiang and M Fang and X Chen},
  booktitle = {arXiv preprint arXiv:2508.09241},
  year = {2025}
}

@inproceedings{zhang2025individuals,
  title = {From Individuals to Crowds: Dual-Level Public Response Prediction in Social Media},
  author = {J Zhang and K Wan and L Xu and A Li and Z Liu and X Chen},
  booktitle = {ACM MM 2025},
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

@inproceedings{chen2024rethinking,
  title = {Rethinking Scientific Summarization Evaluation: Grounding Explainable Metrics on Facet-aware Benchmark},
  author = {X Chen and T Wang and Q Zhu and T Guo and S Gao and Z Lu and X Gao and X Zhang},
  booktitle = {TOIS},
  year = {2024}
}

@article{chen2024write,
  title = {Write Summary Step-by-Step: A Pilot Study of Stepwise Summarization},
  author = {X Chen and S Gao and M Li and Q Zhu and X Gao and X Zhang},
  journal = {IEEE/ACM Transactions on Audio, Speech, and Language Processing 32, 1406-1415},
  year = {2024}
}

@inproceedings{wan2026fano,
  title = {A fano-style accuracy upper bound for llm single-pass reasoning in multi-hop qa},
  author = {K Wan and L Gao and H Mu and P Nakov and Y Wang and X Chen},
  booktitle = {ICLR},
  year = {2026}
}

@inproceedings{li2025flipping,
  title = {Flipping Knowledge Distillation: Leveraging Small Models' Expertise to Enhance LLMs in Text Matching},
  author = {M Li and J Xiang and Q Zhang and K Wan and X Chen},
  booktitle = {ACL main 2025},
  year = {2025}
}
```
