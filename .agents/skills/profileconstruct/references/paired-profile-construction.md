# Paired profile construction

Use `demo_paper/jinghui_prompt.md` as the source of truth for task prompts,
Profile-setting text, input fields, and assembly order. Its Profile setting
**consumes** `author_differences`; it does not itself extract those differences.
Construct the real pairs below before applying that setting. Do not replace this
process with a direct summary of an author's habits.

Pairs cover the Idea, Abstract, and Introduction tasks, for every
pair paper chosen below. Do not construct pairs for other
sections; the other Writing Profile sections come directly from the verified
full texts.

## Select pair papers

The same papers serve the pairs and the full-text writing analysis: take the 8 most recent papers on which the researcher is the first author or the last author (by publication year, newest first; break same-year ties by Scholar order). Exclude middle-author papers. If fewer than 8 such papers exist, use all of them. Every chosen paper needs a verified transcript; a missing one means acquisition continues, not that a different paper is substituted.

## Construct a paper pair

For every pair paper, retain the author's actual
plan, abstract, and introduction and construct model counterparts
from a task-matched, author-independent input.

### Idea

1. Read the full paper and extract the research question separately from the
   author's chosen approach. Extract the author's actual plan into
   `research_focus`, `method`, `validation`, and `title`, preserving its
   contribution type and evidential scope.
2. Give a fresh model context only `{"research_question": "..."}`. The question
   must not reveal the author's solution, distinctive method, reported result,
   identity, or original title. Use the original `Idea` task prompt with setting
   `None`, followed by the source's data instruction. Do not supply an existing
   profile, retrieved history, the original paper, or the extracted author plan.
3. Save the actual returned four-field JSON. Compare it with the extracted
   author plan, separating choices of focus, mechanism, contribution type, and
   validation. Record both agreement and substantive departures; do not
   manufacture a departure when the two approaches agree.
4. Produce the Profile-mode entry exactly as the source specifies:
   `{"id": "...", "title": "...", "research_question": "...", "differences": ...}`.


### Abstract and Introduction

1. Extract the author's actual abstract or introduction and build a factual
   `content_brief` plus verified `references`. The brief must preserve the
   contribution, mechanisms, results and their conditions, uncertainty, and
   prior/current-work distinctions. Its groups are facts, not a paragraph
   outline. Do not supply original section sentences or instructions about the
   author's rhetorical order, length, tone, or style.
2. Give a fresh model context only
   `{"content_brief": ..., "references": ...}`. Use the corresponding original
   task prompt with setting `None`, then the structure rule and data instruction
   in the original order. Supply no original section, author identity,
   `retrieved_history`, profile, or `author_differences`.
3. Save the actual returned section. Verify that it follows the shared brief.
   A fabricated result or omitted essential condition is a generation error to
   repair, not an author style preference. Log any retry and retain the accepted
   response; do not cherry-pick among valid drafts to exaggerate differences.
4. Compare the original and generated sections for opening, organization,
   emphasis, contribution/result presentation, length and paragraphing,
   language, hedging, and closing. Tie differences to the actual texts.
5. Produce the Profile-mode entry
   `{"id": "...", "title": "...", "differences": ...}`. Keep separate lists for
   Abstract and Introduction. Apply the existing corpus/sample coverage rules.

## Isolation and provenance

The counterpart must be a real generation in a fresh context unable to inspect
the author version or other forbidden inputs. A same-conversation reconstruction
by an agent that has already read the paper does not satisfy isolation, even if
it says it will ignore that material. Use an available isolated generation
context; this skill does not mandate an external API or authorize a new paid
service. If isolation is unavailable, preserve completed extraction work and
report the paired stage incomplete. Do not invent response IDs, outputs, model
versions, or a completed call.

Store evidence in `researcher-profile/profile_pairs.json` as
`{"papers": {"<bibtex_key>": {"title": ..., "<task>": {...}}}}`, separate
from the publication records in `publications.json`. Keep, for each task:

- exact task prompt, setting, input JSON, and prompt-source version/hash;
- original author text or source location and extracted author plan;
- actual model output, model/runtime identifier, available response/session ID,
  and the isolation method;
- accepted comparison and the corresponding `author_differences` entry;
- factual validation, retries, and any missing/failed status.

Stage temporary inputs outside `researcher-profile/`; retain the audit record
in `profile_pairs.json` before cleanup. Preserve these fields through enrichment
and refresh. Do not silently reuse pairs when their source text, brief, question,
or task prompt changed.

## Assemble and publish the profile

Collect task-specific `author_differences` arrays from the accepted records.
Retain the exact keys prescribed in the original source. At downstream use, run
`research_avatar/tools/jinghui_prompt.py --task <idea|abstract|introduction> --setting <profile|none>`
with the current input. It assembles task prompt → matching Profile setting →
structure rule for writing → data instruction, and retrieves the top-k pair
entries most similar to the current `research_question` or `content_brief`. The None setting is the non-personalized counterpart. The
assembled request is generated in a fresh context that sees only that request.

Differences describe particular papers and contribution types, not mandatory
habits. Do not promote one paper's choice into a universal author preference or
reuse its factual results in a new project. Preserve contrary cases and choose
the closest task evidence when papers disagree.

Render concise, readable summaries of these paired differences into the
`idea_profile` and Writing Profile `abstract_profile`/`introduction_profile`
slots of `PROFILE.html`.
Organization-routed section profiles are synthesized from the full texts, not
from pairs. The machine-readable paired lists stay in the canonical publication
records; do not add an extra profile page or change the four-section page
structure.

Before publication, check that every claimed paired profile has its saved
input, original, actual isolated counterpart, factual check, and matching
`author_differences` entry. Missing pairs or generic observed-tendency prose are
not successful completion. Preserve the prior valid profile until the required
paired records and rendered replacement are complete.
