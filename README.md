# Research Buddy · 个性化科研助手

一个**轻量、个性化**的科研助手——给**有经验的研究者**用,不是全自动 autoresearch。

它的定位很明确:**机械活我来加速,关键决策你来拍板。** 所有动作都贴着你自己的研究记录(发表、写作风格、实验习惯),并在每个决策点**停下来给你审**——没有"AI 自己判断成功了"这种事,**你才是裁判**。

整套东西只有 **4 个命令 + 5 个工具 + 1 份画像**,没有任何框架依赖。

---

## 核心思想:单一真源

所有个性化都读一份文件:

```
~/aris-profile/PROFILE_AUTO.md
```

它是**全局**的(所有项目共享),里面有:
- **发表索引**(每篇标了 `task_type`:工程 / 理论 / 资源)
- **BibTeX 库**(你自己的论文)
- **写作风格**(论证弧、贡献句习惯)
- **研究脉络**
- **Experiment Templates**:从历史 Claude session 挖出的**实验环境指纹**(惯用启动器 / 框架 / 底座模型 / 显卡 / OOM 记忆)——注意:**不存超参值**(超参由任务决定,不个性化)
- **Workflow Preferences (W1–W7)**:你**怎么做研究**的习惯(便宜步先行、缓存可恢复、一次只动一个变量……)

> 这份画像由 `/profile-construct` 生成,其余三个命令只**读**它,不重复挖掘。

---

## 四个命令(按顺序用)

| 顺序 | 命令 | 干什么 | 你在哪拍板 |
|---|---|---|---|
| 1 | `/profile-construct` | 从 Google Scholar + 历史 session 建/刷新画像 | 确认 Workflow Preferences |
| 2 | `/idea-plan` | 三透镜想 idea + 写 `EXPERIMENT_PLAN.md` | 选 idea、批准 plan |
| 3 | `/run-plan` | 用 `/goal` 自动跑实验,跑到关口停 | 每个结果块审"支不支持 claim" |
| 4 | `/paper-write` | 个性化写论文(套你的风格/自引/反自抄) | 逐节审稿 |

### `/profile-construct` — 建画像
```
/profile-construct gs.html
```
- 先去 Google Scholar 个人主页,点开 **Show more** 展开全部论文,然后 DevTools → 右键 `<html>` → Copy → **Copy outerHTML** → 存成 `gs.html`(直接 `Cmd+S` 只会存前 20 篇)。
- 命令会:抓文献 → 补摘要/DOI/BibTeX → 挖你历史 session 的实验习惯 → 让你**确认** Workflow Preferences → 写出 `PROFILE_AUTO.md`。

### `/idea-plan` — 想 idea + 写实验计划
```
/idea-plan "safety steering — lens: theory"
```
- `— lens:` 选 `engineering`(沿你惯用方法迭代)/ `theory`(读你脉络找断层)/ `benchmark`(综述 / 数据集 / 复现超越)。
- 出 5–7 个 idea(带假设、最小验证实验、对照你自己论文的查新)→ **你选一个** → 它写出 claim 驱动的 `EXPERIMENT_PLAN.md`(对照实验一次只动一个变量、baseline/metric/数据集都写明)→ **你批准**。

### `/run-plan` — 执行实验
```
/run-plan EXPERIMENT_PLAN.md
```
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

## 六条全局纪律(写在 `CLAUDE.md`,始终生效)

这些是赶 deadline 时最容易偷懒跳过、但最不该跳的:

1. **你是裁判** —— 不自动判 idea 新、实验成、claim 成立;每个关口停下等你。
2. **smoke test 先行** —— 跑全量前先跑最小版抓 setup bug。
3. **消融一次只动一个变量** —— 不把两个改动混在一次 run。
4. **数字必须追溯 raw 文件** —— 进 plan/论文的每个数都来自真实结果文件,否则标 `[UNVERIFIED]`,不许凭记忆写。
5. **匹配你的栈,不匹配你的超参** —— 代码贴你环境;lr/batch/seed 由实验计划定(任务决定)。
6. **缓存、不覆盖** —— 中间产物留存、可恢复、版本化输出,绝不覆盖既有结果。

---

## 目录结构

```
research-buddy/
├── README.md                  本文件
├── CLAUDE.md                  定位 + 单一真源 + 6 条纪律(开 CC 自动加载)
├── .claude/commands/          4 个 slash command
│   ├── profile-construct.md
│   ├── idea-plan.md
│   ├── run-plan.md
│   └── paper-write.md
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
# 之后每个项目:
/idea-plan "你的方向 — lens: engineering"
/run-plan EXPERIMENT_PLAN.md
/paper-write ICLR
```

画像在 `~/aris-profile/`(全局),所以你在**任何项目文件夹**里都能直接用这四个命令——不用每个项目重建。
> 想去掉 `aris` 字样:`mv ~/aris-profile ~/research-profile`,再把 `CLAUDE.md` 和各命令里的路径一并改掉即可。

---

## 设计取舍(为什么这么简单)

这类 agent 框架的本质 = **结构化提示 + 跨模型评审 + 编排胶水**,没有秘密算法。对有经验的研究者,真正值钱的只有两样:**你会偷懒跳过的纪律** 和 **你当不了的独立裁判**。

本助手保留了前者(6 条纪律),把后者**交给了你本人**(B 模式:人审,不引入第二个模型)。其余的全部砍掉——所以它只有 4 个命令,而不是几十个 skill。
