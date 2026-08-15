# Research Avatar：个性化科研助手

Research Avatar 是一套面向**有经验研究者**的轻量级、个性化科研助手。它不是全自动的 AutoResearch 系统，也不会替你做研究判断——

> **机械性工作交给助手加速，关键研究决策由你完成；而"怎么加速"，全部围绕你自己的研究品味、写作风格和实验习惯来定制。**

---

[Live Demo →](https://research-avatar-demo.pages.dev/)

---

## 项目亮点

- 🧭 **整体思想**：读取研究者画像，由你确定全局方案，助手负责执行。
- 🎭 **个性化**：一切定制都基于你自己的研究画像，而非通用配置（详见「具体实现 · 个性化」）。
- 🧪 **实验**：从论文反推实验、拆成可验证 Goals、所以结果数字可追溯（详见「具体实现 · 实验」）。
- ✍️ **论文写作**：可交互界面，模仿你的个人写作风格，配合可编辑图表产出（详见「具体实现 · 论文写作」）。

### 🔎 与 AutoResearch 的区别

| 对比维度 | 开源 AutoResearch 常见侧重 | Research Avatar 的侧重 |
|---|---|---|
| 🧭 人机分工 | 强调端到端自动探索 | **由使用者确定全局方案，再自动执行** |
| 🎭 个性化依据 | 以任务上下文和通用配置为主 | **Scholar + 工作习惯生成个人研究画像** |
| 🧪 实验组织 | 从任务目标出发搜索、运行实验 | **把整个任务拆成 Goals，按顺序逐项完成** |
| ✍️ 论文产出 | 自动汇总阶段性研究结果 | **模仿研究者的个性化写作风格** |

---

## 使用前准备

首次使用前，需要你**手动保存完整的 Google Scholar 个人主页 HTML**。随后把该 HTML 文件的本地路径交给 `$profileconstruct`，例如：

```text
$profileconstruct 使用 ~/Downloads/scholar_profile.html
```

你可以下载自己的 Scholar 主页，也可以下载希望模仿其研究品味和论文结构的研究者主页。

论文写作或翻译功能需要调用 LLM API。使用前，请在**本机终端中配置相应服务的 API Key**：

未明确请求翻译时，`$researchlit` 不会调用任何翻译 API；只有用户明确要求其他语言版本时才进行翻译。

```bash
# 使用 OpenAI 时需要
export OPENAI_API_KEY="粘贴你的 API key"

# 使用 DeepSeek 时需要
export DEEPSEEK_API_KEY="粘贴你的 API key"
```

---

## 推荐使用方式

推荐在**终端中的 Coding Agent** 执行科研流程：依次调用 `$profileconstruct`、`$researchlit`、`$ideagen`、`$expplan`、`$runplan`。

论文写作用网页端：**[http://127.0.0.1:8765](http://127.0.0.1:8765)**。

全部流程和生成文件可以在 **[http://127.0.0.1:8780](http://127.0.0.1:8780)** 看到。

---

## 具体实现

### 个性化：

个性化的入口是一份权威画像：

```text
researcher-profile/PROFILE.html
```

**数据来源**：`$profileconstruct` 会读取你的 Google Scholar 论文列表，并结合可用的 coding-agent 历史提取实验环境和工作习惯。

**画像里的个性化内容**包括：

- **Research Identity / Lineage**：你的研究身份，以及研究主题之间的发展脉络；
- **Writing Style**：摘要层（论证结构、方法命名、贡献表述等语气）+ 全文层（章节主干、Related Work 位置、图表写法等篇章结构）；
- **Experiment Templates**：常用启动器、训练框架、基础模型、GPU 配置、历史 OOM 记录；
- **Workflow Preferences**：个人科研习惯，如优先低成本步骤、缓存中间结果、保证实验可恢复。

> **Scholar 画像由你指定。** 可使用自己或希望参考的研究者；本机习惯仍来自你本人。

### 实验：

**1. 先规划论文，再反推实验**——先写预期摘要和段落框架，再为每条 claim 指定实验、指标和待填图表。

**2. 把计划拆成可验证的 Goals**——将整个实验任务拆开，按照依赖顺序逐项执行、核验并更新图表。

**3. 数字全程可追溯**——每个结果都链接到原始记录、运行命令、计算方式和验证状态。

### 论文写作：

**1. 两种正文生成方式**——先确认 `paper/outline.txt`。随后可一键生成全文再逐段修改，也可从第一段开始逐段写。

**2. 可交互论文工作台**——Paper Studio 支持逐段对话、参考段落和 PDF 预览；修改后自动同步 LaTeX。

**3. 论文写作风格个性化**——参考你的目标会议论文与 Writing Style，并检查自引、引用和全文逻辑。

**4. 高质量 Prompt 画图**——先生成构图，再转换为可编辑 PPT/PDF。

**5. 真实实验图表**——只读取 `results/` 中可追溯的实验数据。

---

## Skills

| Skill | 作用 |
|---|---|
| `$profileconstruct` | 根据 Google Scholar 和历史 session 创建/更新研究者画像 |
| `$researchlit "你的研究主题"` | 多角度检索并生成文献综述；只收录实际检索核对过的论文，每条引用可回到原始来源 |
| `$ideagen` | 生成并核查候选 idea；可基于指定论文，或显式加入大胆候选 D1 |
| `$expplan` | 逐段规划 Projected Paper 和待填图表，再反推出实验合同 |
| `$runplan` | 把整个实验拆成 Goals，按依赖顺序逐项执行 |
| `$paperwrite` | 模仿个人写作风格，完成正文、图表、编译与审查 |

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
