# Research Buddy：个性化科研助手

Research Buddy 是一套面向**有经验研究者**的轻量级、个性化科研助手。它不是全自动的 AutoResearch 系统，也不会替你做研究判断——

> **机械性工作交给助手加速，关键研究决策由你完成；而"怎么加速"，全部围绕你自己的研究品味、写作风格和实验习惯来定制。**

---

## 交互 Demo

**[在线打开交互 Demo →](https://research-buddy-demo.pages.dev/)**

---

## 项目亮点

### 🧭 整体思想
个性化主流程读取你的研究者画像（发表经历、写作风格、实验习惯），并在关键节点停下来等你审核。

### 🎭 个性化
一份权威画像驱动选题、实验和论文写作：从你的 Google Scholar 和可用的 coding-agent 历史中提炼研究脉络、写作风格与实验习惯，让产出贴近你，而不是套用通用模板。

### 🧪 实验：从想法到证据
1. **从论文反推实验**——先起草预期摘要与逐段论文框架，明确每项核心论点所需的实验、图表和证据；所有结果均保留为空，等待实际实验数据填充；
2. **有计划的实验执行**——先出整体 plan，再一次给一个 goal，你确认后手动执行 `/goal`；每完成一项就在计划网页上标记一个 ✅，整理对应代码和文件后才给下一项；
3. **重要决定始终由你做**——过程全程透明可控，每个节点的结果是否支持 claim、要不要补实验、要不要继续，都由你裁决。

### ✍️ 论文写作
1. **可交互论文工作台**——按 section 分对话逐段写作、改图、编译，随时看到 PDF 效果；
2. **写作风格个性化**——套用你在目标会议发表过的论文作结构参考，语气和篇章组织都贴你自己的风格；
3. **自动化可编辑图表**——intro/motivation 图和 model/method 图支持 GPT Image 构图、重绘及可编辑 PPT/PDF 导出；实验分析图由代码读取真实结果生成，不造假数据。

| 对比维度 | 开源 AutoResearch 常见侧重 | Research Buddy 的侧重 |
|---|---|---|
| 🧭 人机分工 | 强调端到端自动探索 | **关键节点停下，由研究者拍板** |
| 🎭 个性化依据 | 以任务上下文和通用配置为主 | **Scholar + 工作习惯生成个人研究画像** |
| 🧪 实验组织 | 从任务目标出发搜索、运行实验 | **拆成多层 Goals，实验任务实质为逐项填表作图** |
| ✍️ 论文产出 | 自动汇总阶段性研究结果 | **逐段交互写作，图表可编辑，结果可追溯** |

---

## 使用前准备

首次使用前，需要你**手动下载完整的 Google Scholar 个人主页 HTML**：打开目标 Scholar 主页，持续点击 **Show more**，直到全部论文都已加载，再通过浏览器开发者工具复制页面的 `outerHTML` 并保存为 `.html` 文件。普通 `Cmd/Ctrl+S` 可能只保存最初加载的约 20 篇论文，因此不要使用未完整展开的页面建立画像。

随后把该 HTML 文件的本地路径交给 `$profileconstruct`，例如：

```text
$profileconstruct 使用 ~/Downloads/scholar_profile.html
```

你可以下载自己的 Scholar 主页，也可以下载希望模仿其研究品味和论文结构的研究者主页。

---

## 推荐使用方式

推荐在**终端中的 Coding Agent** 执行科研流程：依次调用 `$profileconstruct`、`$researchlit`、`$ideagen`、`$expplan`、`$runplan`。

论文写作用网页端：**[http://127.0.0.1:8765](http://127.0.0.1:8765)**。

全部流程和生成文件可以在 **[http://127.0.0.1:8780](http://127.0.0.1:8780)** 看到。

---

## 亮点是怎么实现的

### 个性化：

个性化的入口是一份权威画像：

```text
researcher-profile/PROFILE.md
```

**数据来源**：`$profileconstruct` 会读取你的 Google Scholar 论文列表，并结合可用的 coding-agent 历史提取实验环境和工作习惯。

**画像里的个性化内容**包括：

- **Research Identity / Lineage**：你的研究身份，以及研究主题之间的发展脉络；
- **Writing Style**：摘要层（论证结构、方法命名、贡献表述等语气）+ 全文层（章节主干、Related Work 位置、图表写法等篇章结构）；
- **Experiment Templates**：常用启动器、训练框架、基础模型、GPU 配置、历史 OOM 记录；
- **Workflow Preferences**：个人科研习惯，如优先低成本步骤、缓存中间结果、保证实验可恢复。

> **用谁的 Scholar 由你定。** 默认建自己的画像，也可以指向一位你想学习的前辈——idea 品味和论文写法会照着他来（Workflow Preferences 仍取自你本机历史）。对刚起步、还没什么发表的 junior 尤其有用。

### 实验：

**1. 先规划论文，再反推实验**——`$expplan` 从选定 idea 出发，先写预期摘要，再写出 Projected Paper：每个 section 的每个段落用一句话说明要写什么。随后逐条冻结 claim，为每条 claim 明确“什么结果支持它、什么结果证伪它”，再据此设计实验并倒推出 baseline、数据集、指标和待填图表。实验不是独立清单，而是为论文中明确的证据空位服务。

**2. 有计划的实验执行**——`$runplan` 把已批准的证据需求写成自然语言计划网页 `reports/04_RUN_PLAN.html`，默认顺序是：环境 smoke → 验证 hypothesis/motivation → 验证方法可行性 → 冻结调参 → 主结果 → 完整 baseline/消融/敏感性。每次只提出**一个当前 goal**，你认可后手动执行给出的 `/goal`；每完成一项，先整理该 goal 的代码和文件，再在网页上标记 **✅**，然后才提出下一项。可恢复状态嵌入同一个网页，不再维护单独的 `RUN_STATE.json`。

**3. 重要决定由你做**——每个节点，当前结果是否支持 claim、是否需要补实验、是否继续下一阶段，都由你判断；结果不达预期时系统只会提出 refine / pivot / 停止三个选项，不会擅自开始调参或补实验。

### 论文写作：

**1. 可交互论文工作台**——`$paperwrite` 写作前先把大纲写进 `paper/outline.txt` 供你确认，承接 `$expplan` 中已批准的论文骨架。确认后会自动打开本地网页写作界面：左侧是可编辑的论文正文，右侧实时预览。写作的模型可自由配置 GPT、Claude 等 LLM API，走的是自然语言撰写而非 Codex 这类编程工具的代码生成路径。每个 section 有独立对话，可选参考段落、写 comment 修改，接受后自动同步 LaTeX、编译 PDF，全程不用离开这个界面手动改 `.tex`。

**2. 论文写作风格个性化**——以你在目标会议发表过的一篇论文作结构参考（章节/长度/图表布局），套用画像中的 Writing Style，自引 ≤3 篇，并比对你过往摘要防止无意自我重复。完整稿会自动检查理论是否统一、引用是否可靠、claim 是否能追溯到实验结果，以及全文逻辑是否闭环。

**3. 自动化可编辑图表**——intro/motivation 图在第一个引用它的段落确定后生成；model/method 图在定义模型结构所需的 Method 内容完成后生成。两类图都支持 GPT Image 构图、重绘以及可编辑 PPT/PDF 导出；实验分析图只读取 `results/` 中的真实结果，不生成虚假数据。

---

## Skills

| Skill | 作用 |
|---|---|
| `$profileconstruct` | 根据 Google Scholar 和历史 session 创建/更新研究者画像 |
| `$researchlit "你的研究主题"` | 多角度检索并生成文献综述；只收录实际检索核对过的论文，每条引用可回到原始来源 |
| `$ideagen` | 按 engineering / theory / benchmark 生成并核查候选 idea；可基于指定论文寻找突破口，也可显式开启 `--disruptive-wildcard on`，追加一个经证据、可证伪性和“不可被现有路线轻易吸收”检查的大胆候选 D1 |
| `$expplan` | 逐段规划 Projected Paper 和待填图表，再反推出实验合同 |
| `$runplan` | 生成整体 plan，然后提示你逐个 `/goal` 完成 |
| `$paperwrite` | 交互写作、作图、编译与审查 |

---

## 交付文件

交付物分四类：

```text
paper/
├── main.tex                 # 1. 论文——可编辑的 LaTeX 源文件
└── main.pdf                 #    编译后的最终论文
results/                     # 2. 实验结果——原始记录、指标、配置与 provenance
code/                        # 3. 代码——每个实验 goal 生成，贴合你的技术栈，可重跑
reports/
├── 01_LIT_SURVEY.html       # 4. 过程报告——文献综述
├── 02_IDEA_REPORT.html      #    Idea 排序与选择
├── 03_EXPERIMENT_PLAN.html  #    实验计划
├── 04_RUN_PLAN.html         #    可恢复的实验执行计划与 goal 进度
└── 05_EXP_RESULT.html       #    实验结果的人类可读汇总
```
