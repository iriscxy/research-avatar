# PROFILE_AUTO — Lang Gao（人物画像）

> 本文件是给你看的中文镜像；逻辑与工具读取以英文 `PROFILE_AUTO.md` 为准。

**数据源**：Google Scholar  ·  **单位**：ByteDance | MBZUAI 博士生（验证邮箱 @mbzuai.ac.ae）
**指标**：363 引用 · h-index 8 · i10 8
**研究兴趣（自述）**：机制可解释性 · 可信 AI · 自然语言处理
**生成于**：2026-07-03 · **论文数**：19 篇  ·  **task_type 分布**：2 engineering / 8 theory / 9 benchmark
**语料**：18/19 摘要 · 18/19 本地全文（`fulltext/txt/`）
⚠ **这一轮 Semantic Scholar 被限流（HTTP 429）**——摘要 + arXiv id 改为**直接从 arXiv 爬**（走 harness 网络的 WebFetch，绕开被限流的 sandbox HTTP）：**18/19 拿到**（只有 *GTA* 不在 arXiv 上）。BibTeX 从 Scholar 元数据构建。Scholar 页面本身**完整**（"Show more" 已禁用——19 篇，未截断）。全文 PDF：已抓 18/19（arXiv，直接 `arxiv.org/pdf/<id>` 下载 + pdftotext）；只差 *GTA*（不在 arXiv 上）。

> 这一轮 `task_type` 是**摘要辅助**判定的（18/19 摘要已从 arXiv 爬到）。研究脉络与写作风格基于标题/会议/摘要/合作关系推断（Scholar 不暴露导师信息）。

## 研究身份

- **细分方向**（近期产量 × 时效）：
  1. **机制可解释性 & 表示分析 / steering** *（自述 #1）* —— LM steering 的几何结构（**一作**：*Cylindrical Representation Hypothesis*）、情绪电路、概念表示层面的偏见探测、单次推理的信息论上界、扰动下的语义重构、跨语言推理结构。这是你的智识重心。
  2. **可信与安全 LLM** —— 越狱攻防（**一作**：*Shaping the Safety Boundaries*；*Audio Jailbreak*）、机器生成文本检测及其规避（**一作**：*Feature-Inversion Trap*，ACL Oral）、偏见评测。
  3. **LLM 评测与 benchmark 构建** —— 社交推理（*SocialMaze*）、社交推理策略（*Beyond Survival*）、多智能体辩论（*M3MAD-Bench*）、图像生成/编辑（*ServImage*）、漏洞检测（**共一**：*VulDetectBench*）、医学多模态（**共一**：*MedTrinity-25M*）、算法图推理（*GTA*）。
  4. **LLM 智能体与 agentic 推理** —— 动态 agentic 工作流（*DyFlow*）、多智能体辩论、图论智能体、社交推理智能体。
  5. **多模态与领域 LLM** —— 医学（*MedTrinity-25M*）、音频（*Audio Jailbreak*）、图像（*ServImage*）、代码/安全（*VulDetectBench*）。
- **主导方法**（`mode: engineering` 迭代的对象）：
  表示分析与 steering / 电路发现 · benchmark 与数据集构建 · 越狱攻防 · 多智能体 / agentic 框架 · 推理分析（信息论上界、跨语言探测）。
- **活跃会议（近 2 年）**：ICML、ICLR、ACL（main / findings / **Oral**）、EMNLP、NeurIPS、KDD、arXiv。
- **高频合作**：与 X. Chen 组多篇合作，以及 Z. Song、C. Wang、Z. Xu、K. Wan、P. Nakov。

## 研究脉络

你是早期研究者（首批论文在 **2024**）。入场是从**大规模数据与评测 + 安全**切入的——共一的 **MedTrinity-25M**（2500 万图的医学多模态数据集，123 引用）和 **VulDetectBench**（79 引用），以及一作的 **Shaping the Safety Boundaries**（越狱理解/防御，49 引用），这三篇为你在 benchmark 与可信 LLM 上立住了名声。进入 **2025**，重心明显转向**机制可解释性与表示分析**——概念表示偏见探测、情绪电路、Fano 式推理上界、Typoglycemia 语义重构、跨语言推理结构——同时维持可信 LLM（音频越狱、MGT 检测规避）与 agentic/评测（DyFlow、SocialMaze）两条线。**2026** 用一篇**一作**的 LM steering 几何理论/方法（*Cylindrical Representation Hypothesis*）把可解释性身份坐实，并延续 benchmark 产出。轨迹是：**benchmark/安全 → 可解释性与可控表示**，而 steering 是你当前的前沿。

## 写作风格

*基于标题/会议/摘要的推断（18/19 摘要可用）。*
- **论证弧线**：benchmark/数据集论文**先铺全景**（"open"、"comprehensive"、"large-scale"、"first"）；可解释性/方法论文**先点缺口**（先指出 LLM 的一个具体失效/局限，再去补它）。
- **起标题**：偏爱"问句/隐喻 + 精确技术副标题"的两段式——*"Do LLMs 'Feel'? Emotion Circuits Discovery and Control"*、*"Under the Shadow of Babel: How Language Shapes Reasoning"*、*"When Personalization Tricks Detectors: The Feature-Inversion Trap"*。
- **贡献表述**：benchmark 论文突出释放的产物 + 规模；方法论文突出一个命名机制/假设（Cylindrical Representation Hypothesis、Feature-Inversion Trap）。

## Experiment Templates（实验模板）

*由 `experiment_history.py` 从 `~/.claude/projects/*` 的 476 个 coding-agent 会话中挖掘
（扫描 64,940 行，2026-07-03）。真源：`aris-profile/habits.json`。**经你确认（2026-07-03）
直接采用为你的技术栈**——这是本工作环境的机器级 coding 习惯。启发式文本扫描，高频项是干净信号。*

**惯用技术栈**（生成的实验代码要匹配这个——不是超参数值，那些由实验计划决定）：
- **启动器**：`deepspeed`（主导，171）› `srun`（78，Slurm）› `accelerate launch`（60）› `modal run`（34）› `torchrun`（32）。默认 DeepSpeed 多卡。
- **框架 / 依赖**：PyTorch-**Lightning**（首位依赖，8509）+ **TRL**（1367）+ **vLLM**（996，推理）+ `accelerate`（695）+ `torch`；也有 `jax`（701）。→ LoRA/RLHF 微调 + vLLM 部署栈。
- **默认基座模型**：**Qwen3-4B-Instruct-2507**（125）与 **Qwen3-7B-Instruct**（35）——Qwen3 是惯用 backbone。

**资源习惯**：A100（479）· RTX 4090（约 305）· H100（119）· 3090（112）· TPU（82）· A800（81）· V100（63）· L40（60）· A6000 · H800 · MI250。

**失败记忆**（喂给资源/失败感知的 planner）：
- **OOM 是头号复发失败——1322 次。** 在惯用 GPU 上默认走省显存配置（降 batch / 提梯度累积）。
- 高频错误类型：`ValueError`（568）、`RuntimeError`（529），以及通用的 `Exception`/`Error`/`Traceback`。
- 成功信号：191 次 checkpoint、48 个 wandb run。

*范围说明：超参数**值**（lr/batch/epochs/seed）刻意不挖——它们由任务决定，交给 `/workplan`。
`habits.json` 只保留真正个人化的轴：工具链、基座模型、硬件、失败记忆。*

**领域先验**：
- 常用 baseline：开源 LLM（Qwen/Llama 系）、各细分方向的 task-specific SOTA。
- 常用指标：accuracy / F1、attack-success-rate（安全）、可解释性控制准确率、人评。
- 常用数据：自建 benchmark（这个作者群的招牌）、公开安全/社会/医学数据集。

## Known Dead-Ends（已知死胡同）

*来自 tacit-knowledge 访谈（你已确认，2026-07-03）。*
- **可解释性的"因果不足"。** 这条线在顶会最常挨的一刀，就是 steering / 电路 / 表示的结论只是**相关、不是因果**。任何可解释性论断都得配上**因果干预证据**——ablation、activation patching，或能真正改变行为的 steering——而不是只给探针准确率或一个相关的方向。别在没有那个"补上因果缺口"的干预时就抛出一个可解释性结论。

## Workflow Preferences（工作流偏好）

*由 `workflow_prefs.py` 蒸馏（476 会话，479 个候选偏好轮次；类别：prohibition 157、
process 142、correction 119、cadence 59、mandate 26、rigor 24）。**经你确认（2026-07-03）
全部采用。** 这是**本环境里活儿怎么跑**——被实验/论文技能消费以匹配流程，而非超参数。*

| # | 偏好 | 为什么重要 / 怎么落地 |
|---|---|---|
| **W1** | **先做便宜/确定性的步，再做贵/LLM 的步。** | 流水线里先跑便宜过滤，再调 LLM/GPU。别拿贵操作打头。 |
| **W2** | **激进缓存；支持断点续跑 / 不重算。** | 每个中间产物都持久化并建索引；已有的绝不重算。可续跑是硬要求。 |
| **W3** | **绝不覆盖旧输出；保留历史。** | 写带时间戳/版本的输出；中途停止不能毁掉在跑或已有的结果。 |
| **W4** | **分节生成，不要一次成篇。** | 把长生成拆成可独立重生成的单元。 |
| **W5** | **idea 验证是人工检验的循环，不是一次性。** | accept/reject 做成"迭代 + 检查点"，轮次之间交给你，而非自动接受。 |
| **W6** | **固定研究顺序：idea → 实验 → 论文。** | 按这个顺序推进；没证据前别跳去写作。 |
| **W7** | **跑之前先明确 baseline / metric / dataset。** | 实验设计阶段就强制敲定具体的 baseline+metric+dataset，不留隐式默认。 |

## 论文索引

*19 篇。按年份、再按引用排序。`task_type` 为**摘要辅助**判定（18/19 摘要已从 arXiv 爬到）。
`full-text`：✓ = 本地全文在 `fulltext/txt/<key>.txt`，`abs` = 仅摘要（在 `enriched.json`），— = 都没有。
一作/共一见"研究身份"（BibTeX 里 `*` 标共一）。arXiv id 存在 `enriched.json`。*

| # | 年 | 标题 | 会议 | 引用 | task_type | 全文 |
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

> BibTeX Bank 见英文 `PROFILE_AUTO.md`（条目原样，标题保持英文原文）。
