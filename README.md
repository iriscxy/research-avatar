# Research Buddy · 个性化科研助手

一个**轻量、个性化**的科研助手——给**有经验的研究者**用,不是全自动 autoresearch。

它的定位很明确:**机械活我来加速,关键决策你来拍板。** 所有动作都贴着你自己的研究记录(发表、写作风格、实验习惯),并在每个决策点**停下来给你审**——没有"AI 自己判断成功了"这种事,**你才是裁判**。

整套东西只有 **6 个 skill + 5 个工具 + 1 份画像**,没有任何框架依赖。

---

## 核心思想:单一真源

所有个性化都读一份文件:

```
aris-profile/PROFILE_AUTO.md      # 项目内(经 $ARIS_PROFILE 定位),不是全局 ~/aris-profile
```

它里面有:
- **Research Identity**(研究身份)
- **发表索引**(每篇标了 `task_type`:engineering / theory / benchmark)
- **BibTeX 库**(你自己的论文)
- **写作风格**(论证弧、贡献句习惯)
- **研究脉络**(Research Lineage)
- **Experiment Templates**:从历史 Claude session 挖出的**实验环境指纹**(惯用启动器 / 框架 / 底座模型 / 显卡 / OOM 记忆)——注意:**不存超参值**(超参由任务决定,不个性化)
- **Workflow Preferences (W1–W7)**:你**怎么做研究**的习惯(便宜步先行、缓存可恢复、一次只动一个变量……)

与它同目录:`enriched.json`(摘要 + BibTeX)、`habits.json` / `prefs_bundle.json`(内部挖掘)、`fulltext/`(每篇论文的 PDF + 抽取文本),以及 **`PROFILE_AUTO.zh.md`**——面向人的中文镜像(同一遍生成;**英文 `PROFILE_AUTO.md` 才是权威**,所有 skill 读的是它)。

> 这份画像由 `/profile-construct` 生成,其余五个 skill 只**读**它,不重复挖掘。缺失或过时就重跑 `/profile-construct`。

---

## 六个 skill(按顺序用 — W6)

每个都是 `.claude/skills/<name>/SKILL.md` 里的一个 Skill:对话匹配时 Claude 会自动触发,你也能用同名 `/<name>` 显式调用。

| 顺序 | Skill | 干什么 | 你在哪拍板 |
|---|---|---|---|
| 1 | `/profile-construct` | 从 Google Scholar + 历史 session 建/刷新 `PROFILE_AUTO.md` | 确认 Workflow Preferences |
| 2 | `/research-lit` | 多路并行、逐篇核验的 arXiv/web 检索 → 白底、母语中文、杂志风自包含 HTML 综述(`outputs/01_LIT_SURVEY.html`) | 看综述(可独立用) |
| 3 | `/ideagen` | **读 `outputs/01_LIT_SURVEY.html`**(不再自己 survey)→ 三透镜想 idea(方法优先)→ 对照自己工作 + 并行工作查新 → 排序 idea 榜(`outputs/02_IDEA_REPORT.html`) | **选一个 idea** |
| 4 | `/workplan` | 从选定 idea → claim 驱动的 `outputs/03_EXPERIMENT_PLAN.html`(从投影摘要倒推)。**论文骨架就在 `03` 的 §0.5 里**,不单出文件;只有你明确要更完整的可视化大纲时才出 `03b_PAPER_PLAN.html` | 批准 plan |
| 5 | `/run-plan` | 用 `/goal` 执行 plan,跑到关口停 | 每个结果块审"支不支持 claim" |
| 6 | `/paper-write` | 个性化写论文(套风格 / 自引 / 反自抄)。**自动串起四个审查子 skill**:`/paper-theorization`(统一理论骨架 + 机器验证)· `/paper-related-work`(广搜 + 逐个核对 arXiv id)· `/paper-gap-check`(每条 claim 回溯 `results/` → `paper/EXPERIMENT_PLAN.md`,绝不编数)· `/paper-logic-check`(另起 reviewer 查逻辑闭环)。四个也都能单独 `/paper-<name>` 调 | 逐节审稿 |

### `/profile-construct` — 建画像
- 去 Google Scholar 个人主页,点开 **Show more** 展开全部论文,DevTools → 右键 `<html>` → Copy → **Copy outerHTML** → 存成 HTML(直接 `Cmd+S` 只会存前 20 篇)。
- 命令会:抓文献 → 补摘要/DOI/BibTeX → 抓全文 PDF → 挖历史 session 的实验习惯 → 让你**确认** Workflow Preferences → 写出 `PROFILE_AUTO.md`(+ 中文镜像)。

### `/research-lit` — 文献综述
```
/research-lit "MoE 机制可解释与 steering"
/research-lit "… — angles: 6"          # 并行检索角度数(默认 5)
/research-lit "… — for: ideagen"       # 顺带把 landscape 交给 ideagen 接地
```
- 把主题拆成多路子方向,**并行** fan-out 检索(arXiv + web),逐篇核验 id,只引真正检索到的论文(其余标 `[UNVERIFIED]`,绝不编造)。
- 出一份**白底、直接中文、杂志风**的自包含 HTML 综述 `outputs/01_LIT_SURVEY.html`(hero + 目录 + taxonomy 流程图 + 卡片 + 总览表 + 趋势/空白 + 分组参考文献)。可独立用,也是 `/ideagen` 的接地。

### `/ideagen` — 想 idea
```
/ideagen "safety steering — lens: engineering"
/ideagen "… — ref paper: <某篇论文>"     # 可选:在某篇论文上做增量
```
- **先读 `outputs/01_LIT_SURVEY.html`**(不再自己 survey;综述缺失/跑题时会先替你跑 `/research-lit`)。
- `— lens:` 选 `engineering`(沿你惯用方法迭代)/ `theory`(读你脉络找断层)/ `benchmark`(综述 / 数据集 / 复现超越)。
- 出一份排序 idea 榜(带假设、最小验证实验、对照你自己论文 + 并行工作的查新)→ **你选一个**。

### `/workplan` — 写实验计划
- 从你选的 idea 出发,**先读最接近的几篇论文全文**扎根 baseline/数据集/指标 → 从投影摘要**倒推**出 claim 驱动的 `outputs/03_EXPERIMENT_PLAN.html`(对照实验一次只动一个变量;可选嵌入论文骨架)→ **你批准**。

### `/run-plan` — 执行实验
- 用 CC 自带的 `/goal` 自动干活:**先 smoke test** → 部署 → 收结果到真实文件。
- 贴你的栈(DeepSpeed/Qwen3…),按你 OOM 历史默认降 batch。
- **每个关口停下来给你看真实数字**,你来判"支不支持 claim / 要不要继续"。**它绝不自己宣布成功,也不会编数。**

### `/paper-write` — 写论文
```
/paper-write ICLR
```
- 自动套你的写作风格、建议自引(你自己的论文)、反自抄(比对你过往摘要)、逐节生成。
- 每个数字都追溯到 `results/` 真实文件。**逐节给你审**。

---

## 交付物:全部是 `outputs/` 里的自包含 HTML

按工作流步骤编号:

```
outputs/
├── 01_LIT_SURVEY.html          /research-lit 的文献综述(白底中文)
├── 00_REF_PAPER_SUMMARY.html   (可选)ref paper 摘读
├── 02_IDEA_REPORT.html         /ideagen 的 idea 榜
├── 03_EXPERIMENT_PLAN.html     /workplan 的实验计划(论文骨架在 §0.5)
├── 03b_PAPER_PLAN.html          (少见)仅你明确要更完整可视化大纲时才出
├── 04_EXPERIMENT_TRACKER.html  /run-plan 的实验追踪
└── 05_FINDINGS.html            结果汇总
```

默认按你的 instruction 输出**单一语言**一份;要双语时才另出 `.zh.html` 镜像(母语级、非逐字机翻,第二人称"你/你的")。
**例外**(保留原生格式):`PROFILE_AUTO.md`(真源,工具读)、`results/*.json|csv` + 日志(原始数据)、论文稿(`paper/main.tex`)。

---

## 七条全局纪律(写在 `CLAUDE.md`,始终生效)

这些是赶 deadline 时最容易偷懒跳过、但最不该跳的:

1. **你是裁判** —— 不自动判 idea 新、实验成、claim 成立;每个关口停下等你(W5)。
2. **smoke test 先行(W1)** —— 跑全量前先跑最小版抓 setup bug;便宜/确定的步在贵/GPU 步之前。
3. **消融一次只动一个变量** —— 不把两个改动混在一次 run。
4. **数字必须追溯 raw 文件** —— 进 plan/幻灯/论文的每个数都来自真实结果文件,否则标 `[UNVERIFIED]`,不许凭记忆写。
5. **匹配你的栈,不匹配你的超参** —— 代码贴你环境(Experiment Templates);lr/batch/seed 由 `03_EXPERIMENT_PLAN.html` 定(任务决定)。
6. **缓存、不覆盖(W2/W3)** —— 中间产物留存、可恢复、版本化/时间戳输出,绝不覆盖既有结果。
7. **每份输出都是自然、母语的中文** —— HTML 里的中文读起来要像领域研究者写的,不是逐字机翻;面向研究者本人,用第二人称(你 / 你的),不用第三人称。

---

## 目录结构

```
research-buddy/
├── README.md                  本文件
├── CLAUDE.md                  定位 + 单一真源 + 7 条纪律(开 CC 自动加载)
├── .claude/
│   ├── settings.json          设 $ARIS_PROFILE 指向 aris-profile/
│   └── skills/                6 个流程 skill + paper-write 的 4 个审查子 skill
│       │                       (+ figure-ppt 画模型图、scholar-translation-zh 翻译规范)
│       ├── profile-construct/SKILL.md
│       ├── research-lit/SKILL.md
│       ├── ideagen/SKILL.md
│       ├── workplan/SKILL.md
│       ├── run-plan/SKILL.md
│       ├── paper-write/SKILL.md          总编排(自动调下面 4 个)
│       ├── paper-theorization/SKILL.md   统一理论骨架 + 机器验证
│       ├── paper-related-work/SKILL.md   广搜 + 逐个核对 arXiv id
│       ├── paper-gap-check/SKILL.md      查缺 → paper/EXPERIMENT_PLAN.md
│       └── paper-logic-check/SKILL.md    逻辑闭环(另起 reviewer)
├── aris-profile/              单一真源(画像 + 语料 + 全文)
│   ├── PROFILE_AUTO.md        权威画像(工具读)
│   ├── PROFILE_AUTO.zh.md     中文镜像
│   ├── enriched.json          摘要 + BibTeX
│   └── fulltext/              每篇论文 PDF + 抽取文本
├── outputs/                   自包含 HTML 交付物(见上)
└── tools/                     5 个 stdlib 工具(无第三方依赖)
    ├── scholar_profile.py     读 Google Scholar HTML → JSON
    ├── profile_enrich.py      补摘要/DOI + 建 BibTeX
    ├── experiment_history.py  挖历史 session 的实验环境指纹
    ├── workflow_prefs.py      挖候选 workflow 偏好
    └── bib_manager.py         导出 .bib / 查重 / 建议自引
```

---

## 快速开始

```bash
cd ~/code/research-buddy        # 在这里开 Claude Code
# 第一次:建画像
/profile-construct gs.html
# 然后按顺序:
/ideagen "你的方向 — lens: engineering"    # 选一个 idea
/workplan                                  # 批准实验计划
/run-plan                                  # 跑到关口停
/paper-write ICLR                          # 逐节审稿
```

画像在项目内 `aris-profile/`(经 `.claude/settings.json` 里的 `$ARIS_PROFILE` 定位),所有 skill 读的都是它。

---

## 设计取舍(为什么这么简单)

这类 agent 框架的本质 = **结构化提示 + 跨模型评审 + 编排胶水**,没有秘密算法。对有经验的研究者,真正值钱的只有两样:**你会偷懒跳过的纪律** 和 **你当不了的独立裁判**。

本助手保留了前者(7 条纪律),把后者**交给了你本人**(人审,不引入第二个模型当裁判)。其余的全部砍掉——所以它只有 6 个 skill,而不是几十个。
