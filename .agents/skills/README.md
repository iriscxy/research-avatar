# Skills 维护规则

## Agents 为唯一源，Claude Code 为生成镜像

`.agents/skills/` 是唯一可编辑的 skill 源；`.claude/skills/` 是为 Claude Code 生成的平台适配镜像。

- 只修改 `.agents/skills/`，不要直接编辑 `.claude/skills/`。
- 修改后运行 `python3 research_avatar/tools/sync_skill_mirrors.py` 生成 Claude Code 镜像；脚本自动适配 `$skill-name`/`/skill-name` 及运行时专属的 Agent/Goal 语义。
- 完成前运行 `python3 research_avatar/tools/sync_skill_mirrors.py --check`；任何差异都视为未同步。
- 若某个 skill 仅支持一个运行时，必须在本文件中明确记录例外及原因。
