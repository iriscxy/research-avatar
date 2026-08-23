# Skills 维护规则

## Agents 为唯一源，Claude Code 为生成镜像

`.agents/skills/` 是唯一可编辑的 skill 源；`.claude/skills/` 是为 Claude Code 生成的平台适配镜像。

- 只修改 `.agents/skills/`，不要直接编辑 `.claude/skills/`。
- 修改后运行 `python3 research_avatar/tools/sync_skill_mirrors.py` 生成 Claude Code 镜像；脚本自动适配 `$skill-name`/`/skill-name` 及运行时专属的 Agent/Goal 语义。
- 完成前运行 `python3 research_avatar/tools/sync_skill_mirrors.py --check`；任何差异都视为未同步。
- 若某个 skill 仅支持一个运行时，必须在本文件中明确记录例外及原因。

## Canonical 产物必须从根源重生成

HTML、PDF、PPTX 和其他交付物都是渲染结果，不是修正的权威输入。

- 禁止为了修正已生成产物而手工改成品、做字符串/正则替换、注入 DOM 片段、覆盖单个数值，或在文件尾部追加修正块。
- 修正顺序固定为：定位产生错误的权威输入、schema、状态或生成器 → 修正根因 → 从该权威源完整重生成到临时路径 → 运行全部验证 → 原子替换 canonical 产物。
- 修改选择、审批、翻译、provenance、图表 span 或样式时，必须更新对应的结构化源并重跑同一生成路径；不得把当前成品反向当作新的源。
- 如果某产物没有可重现的完整生成路径，先修正或建立生成器；不得用一次性后处理脚本掩盖这个缺口。
