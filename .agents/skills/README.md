# Skill maintenance rules

## Agents is canonical; Claude Code is a generated mirror

`.agents/skills/` is the only editable skill source. `.claude/skills/` is the generated platform-adapted mirror for Claude Code.

- Edit only `.agents/skills/`; never edit `.claude/skills/` directly.
- After an edit, run `python3 research_avatar/tools/sync_skill_mirrors.py` to generate the Claude Code mirror. The script adapts `$skill-name`/`/skill-name` and runtime-specific Agent/Goal semantics.
- Before completion, run `python3 research_avatar/tools/sync_skill_mirrors.py --check`; any difference means the mirrors are not synchronized.
- If a skill supports only one runtime, document the exception and reason here.

## Regenerate canonical artifacts from their authoritative source

HTML, PDF, PPTX, and other deliverables are rendered outputs, not authoritative correction inputs.

- Do not correct generated artifacts by hand-editing the deliverable, applying string or regular-expression replacements, injecting DOM fragments, overriding individual values, or appending correction blocks.
- Follow this correction order: locate the authoritative input, schema, state, or generator that caused the error; fix the root cause; regenerate completely into a temporary path; run all validation; atomically replace the canonical artifact.
- When changing selection, approval, translation, provenance, figure/table span, or styling, update the corresponding structured source and rerun the same generation path. Never treat the current rendered output as a new source.
- If an artifact lacks a complete reproducible generation path, fix or create the generator first. Do not conceal the gap with a one-off post-processing script.
