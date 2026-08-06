# Research Buddy：个性化科研助手

Research Buddy 是一套面向**有经验研究者**的轻量级、个性化科研助手。它不是全自动的 AutoResearch 系统，也不会替你做研究判断——

> **机械性工作交给助手加速，关键研究决策由你完成；而"怎么加速"，全部围绕你自己的研究品味、写作风格和实验习惯来定制。**

---

## 项目亮点

### 🧭 整体思想
个性化主流程读取你的研究者画像（发表经历、写作风格、实验习惯），并在关键节点停下来等你审核。

### 🎭 个性化
一份权威画像驱动选题、实验和论文写作：从你的 Google Scholar 和可用的 coding-agent 历史中提炼研究脉络、写作风格与实验习惯，让产出贴近你，而不是套用通用模板。

### 🧪 实验：从想法到证据
1. **从论文反推实验**——先写预期摘要与论文骨架，再为每条 claim 设计能支持或证伪它的实验，倒推出 baseline / 数据集 / 指标；
2. **有计划的实验执行**——先出整体 plan，再一次给一个 goal，你确认后手动执行 `/goal`，做完一个再给下一个；
3. **重要决定始终由你做**——过程全程透明可控，每个节点的结果是否支持 claim、要不要补实验、要不要继续，都由你裁决。

### ✍️ 论文写作
1. **可交互论文工作台**——按 section 分对话逐段写作、改图、编译，随时看到 PDF 效果；
2. **写作风格个性化**——套用你在目标会议发表过的论文作结构参考，语气和篇章组织都贴你自己的风格；
3. **自动化可编辑图表**——intro/motivation 图和 model/method 图支持 GPT Image 构图、重绘及可编辑 PPT/PDF 导出；实验分析图由代码读取真实结果生成，不造假数据。

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

**1. 从论文反推实验**——`$expdesign` 从选定 idea 出发，先写出「预计的论文」：一段预期摘要 + 一份论文骨架（Intro 逻辑、Related Work 分节、Method 模块、打算跑哪些实验），再反向拆出每条 claim 需要的实验（一次只改一个变量），最后把 baseline/数据集/指标的选材依据整理成 grounding 表放在附录。

**2. 有计划的实验执行**——`$runplan` 先写整体决策图 `code/RUN_PLAN.md`（`code/RUN_STATE.json` 记录可恢复状态），默认顺序是：环境 smoke → 验证 hypothesis/motivation → 验证方法可行性 → 冻结调参 → 主结果 → 完整 baseline/消融/敏感性。每次只提出**一个当前 goal**，你认可后手动执行给出的 `/goal`；完成后停下展示证据和下一条 goal，不自动往下走。

**3. 重要决定由你做**——每个节点，当前结果是否支持 claim、是否需要补实验、是否继续下一阶段，都由你判断；结果不达预期时系统只会提出 refine / pivot / 停止三个选项，不会擅自开始调参或补实验。

### 论文写作：

**1. 可交互论文工作台**——`$paperwrite` 写作前先把大纲写进 `paper/outline.txt` 供你确认，承接 `$expdesign` 中已批准的论文骨架。确认后会自动启动 Paper Studio 并打开本地浏览器界面：左侧是可编辑的论文正文，右侧实时预览。写作的模型可自由配置 GPT、Claude 等 LLM API，走的是自然语言撰写而非 Codex 这类编程工具的代码生成路径。每个 section 有独立对话，可选参考段落、写 comment 修改，接受后自动同步 LaTeX、编译 PDF，全程不用离开这个界面手动改 `.tex`。

**2. 论文写作风格个性化**——以你在目标会议发表过的一篇论文作结构参考（章节/长度/图表布局），套用画像中的 Writing Style，自引 ≤3 篇，并比对你过往摘要防止无意自我重复。完整稿会自动检查理论是否统一、引用是否可靠、claim 是否能追溯到实验结果，以及全文逻辑是否闭环。

**3. 自动化可编辑图表**——intro/motivation 图在第一个引用它的段落确定后生成；model/method 图在定义模型结构所需的 Method 内容完成后生成。两类图都支持 GPT Image 构图、重绘以及可编辑 PPT/PDF 导出；实验分析图只读取 `results/` 中的真实结果，不生成虚假数据。

---

## Skills

| Skill | 作用 |
|---|---|
| `$profileconstruct` | 根据 Google Scholar 和历史 session 创建/更新研究者画像 |
| `$researchlit "你的研究主题"` | 多角度检索并生成文献综述；只收录实际检索核对过的论文，每条引用可回到原始来源 |
| `$ideagen` | 按 engineering / theory / benchmark 生成并核查候选 idea；可基于指定论文寻找突破口，也可显式开启 `--disruptive-wildcard on`，追加一个经证据、可证伪性和“不可被现有路线轻易吸收”检查的大胆候选 D1 |
| `$expdesign` | 先写预期摘要与论文骨架，再反推出实验计划 |
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
└── 04_EXP_RESULT.html       #    实验结果的人类可读汇总
```
