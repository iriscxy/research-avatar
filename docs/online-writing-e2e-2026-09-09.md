# Online writing end-to-end verification — 2026-09-09

The real Cloudflare writing service was exercised with an authenticated session,
self-authored synthetic Markdown materials, and real model calls. The test manuscript
is an evaluation **plan**, not research evidence: unavailable measurements remain
`xx` and unresolved citations remain placeholders.

## Real online browser coverage

| Workflow | Result |
| --- | --- |
| Required-field validation and two Markdown uploads | Passed |
| Material analysis and project creation | Passed; 16 planned paragraphs |
| Generate paragraph, accept, compile and preview | Passed |
| Revise accepted paragraph with model feedback | Passed |
| Submit deliberately undefined LaTeX command | Rejected; edit rolled back and existing PDF preserved |
| Generate a section and refresh the outer page during work | Passed; resumed session completed the section |
| Generate full draft, stop, then continue unfinished text | Passed; all 16 paragraphs accepted |
| Preserve a previously revised paragraph during batch generation | Exact text comparison passed |
| Generate a title, save it and recompile | Passed |
| Figures/Tables views and online placeholder behavior | Passed for the synthetic project's motivation figure and planned comparison table |
| PDF and project ZIP browser downloads | Passed; final PDF has 4 pages |
| ZIP integrity, required sources, unsafe archive paths and common credential patterns | Checks passed |
| Exported project rebuilt with local LaTeX | Passed |

The session usage ledger contained 51 model calls across material analysis,
structure design and writing. No user research files were used.

## Issues fixed from this test

- Restore title and title-instruction inputs after a background drafting job completes.
- Keep mutation controls disabled when switching workspaces or loading a figure
  preview during a background job; retain navigation, export and cancellation.
- Label an empty paragraph's action “Generate paragraph” and existing text's action
  “Revise paragraph”. Do not claim a title is written to PDF before a PDF exists.
- Replace acceptance progress copy that incorrectly promised online citation retrieval.
- Remove an exact standalone manuscript title echoed before a generated abstract;
  preserve ordinary prose and different headings.
- Exclude main-paper LaTeX build caches from exported ZIPs so server-specific
  dependency state cannot suppress a local rebuild.

## Regression verification

The full Python suite ran 680 tests with 13 skips and no failures. It includes a
Node regression harness executing the actual frontend functions, plus abstract
cleanup and export checks. An isolated browser fixture using the real application
assets verified the running-to-completed state transition without a page reload,
including switching to Figures and back. This fixture check is separate from the
real online model workflow above.

The new ZIP exporter was run against the downloaded synthetic project. Its ZIP
was extracted into a fresh directory and a normal `latexmk -pdf` rebuild succeeded,
without forcing the build or relying on server caches.

## Scope boundaries

This covers the online writing workflow and existing automated regression suite;
it is not a claim that every input format, provider, account transition, browser,
or concurrent-user combination was exercised live. Diagram-agent execution is
not offered by this online mode. The synthetic manuscript did not exercise every
editable-table or Python-data-plot path live; those paths retain automated coverage.
Thirteen skipped tests are not counted as passed. Generated references and planned
results require researcher verification before academic use.

Local test deliverables are saved under the ignored directory
`outputs/online-writing-e2e-20260909/`: `online-paper.pdf` and `online-project.zip`.
The ZIP there uses the corrected exporter; the PDF is the final browser download.
