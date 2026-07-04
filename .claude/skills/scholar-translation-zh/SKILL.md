---
name: scholar-translation-zh
description: Translate English academic papers into fluent, accurate Chinese while preserving terminology, formulas, citations, and structure. In THIS project, these rules govern ALL English→Chinese translation, including every `.zh.html` / `.zh.md` mirror produced by /ideagen, /workplan, /profile-construct, and /paper-write.
---

# Scholar Translation (EN → ZH)

When invoked:

- Preserve technical terminology.
- Keep equations, symbols, references, figure/table numbers unchanged.
- Translate paragraph by paragraph.
- Use standard Chinese academic writing style.
- Do not omit any content.
- Do not summarize unless explicitly requested.
- Preserve Markdown/LaTeX formatting.
- If a term has multiple translations, use the most common translation in the field and keep it consistent.

## Project-wide rule (research-buddy)

**Whenever you translate anything in this project, follow the rules above.** This applies in
particular to the human-facing Chinese mirrors the pipeline emits — `outputs/*.zh.html`,
`PROFILE_AUTO.zh.md`, and any paper section rendered in Chinese. Consistent with the project's
existing Chinese-output discipline (CLAUDE.md #7): the mirror must read as native, idiomatic
Chinese written by a domain researcher (never word-for-word machine translation), address the
researcher in the SECOND person (你 / 你的, never 她), and keep code / identifiers / paper titles
native. The stricter case is the projected abstract, which stays a faithful sentence-for-sentence
translation of the canonical English (same claims, numbers, and order).
