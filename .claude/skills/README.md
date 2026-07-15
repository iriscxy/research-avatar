# Skills 目录

Claude Code 只识别 `.claude/skills/` **下一层**的 `SKILL.md`,且 **slash 命令名 = 文件夹名**(不是 frontmatter 的 `name:`)。所以不能把 skill 塞进子文件夹分组——否则 `/paper-write` 会失效或被改名成 `/paper:paper-write`。因此这里全部 flat,靠**命名前缀**分组。

## 流程 skill(按 W6 顺序跑)

| 顺序 | Skill | 干什么 |
|---|---|---|
| 1 | `profile-construct` | 建/刷新 `PROFILE_AUTO.md` |
| 2 | `research-lit` | 文献综述 → `outputs/01_LIT_SURVEY.html` |
| 3 | `ideagen` | 读综述 → idea 榜 `outputs/02_IDEA_REPORT.html` |
| 4 | `workplan` | 选定 idea → `outputs/03_EXPERIMENT_PLAN.html`(§0.5 含论文骨架) |
| 5 | `run-plan` | 执行 plan,跑到关口停 |
| 6 | `paper-write` | 个性化写论文(见下面这组) |

## paper-writing 组(前缀 `paper-`,天然聚在一起)

`paper-write` 是**总编排**,在自己流程里自动调下面 4 个审查子 skill(每个也能单独 `/paper-<name>` 调);移植自 `watson-paper`,已去掉外部 `paperkit` 依赖。

| Skill | 角色 |
|---|---|
| `paper-write` | 总编排:定会议/模板/长度、以本人最相关论文为结构参照、self-cite ≤3、反自抄、编译 PDF |
| `paper-theorization` | 统一理论骨架 + Lean/sympy 机器验证 |
| `paper-related-work` | 广搜 + 逐个核对 arXiv id + `\paragraph` 分族 |
| `paper-gap-check` | 每条 claim 回溯 `results/` → `paper/EXPERIMENT_PLAN.md`,绝不编数 |
| `paper-logic-check` | grep 建 xref 图 + 另起 reviewer agent 查逻辑闭环 |

## 共享辅助 skill

| Skill | 干什么 |
|---|---|
| `figure-ppt` | 画模型图(Fig 1):meta-prompt+论文→GPT 生成 BioRender 提示词 → gpt-image 画图 → **agent 看图改提示词重画**(每轮存档)→ 转 **可编辑 PPT**(`buildshapes` 全原生形状全可编辑,或 `build` 图当底+标签框)→ soffice 导 PDF。画手可换(现 gpt-image,后 Gemini)。替代已删的 `method-figure` |
| `scholar-translation-zh` | 中文输出的翻译/术语规范 |
