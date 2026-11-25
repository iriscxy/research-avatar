"""Shared visual theme for every generated report page.

The theme overrides colors and typography only. Page-specific layout classes
(``.hero``, ``.shell``, ``.part``, ``.goal``, ``.artifact`` ...) keep their own
rules; this stylesheet is appended after them so all reports share one look:
warm paper background, white cards, teal headings, orange accents, and a plain
page title instead of a display-size banner.
"""

from __future__ import annotations

import re

THEME_MARKER = "/*report-theme*/"

THEME_CSS = THEME_MARKER + """
:root{--ink:#18201d;--muted:#5e6a64;--line:#d8d5cb;--green:#0b6b59;--soft:#e5f1ed;--amber:#c65d32;--accent:#0b6b59;--accent2:#c65d32;--paper:#f5f3ec;--card:#fffefa}
body{background:var(--paper);color:var(--ink);font:16px/1.65 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer{max-width:1100px;padding-left:max(4vw,24px);padding-right:max(4vw,24px)}header{padding-top:36px;padding-bottom:10px}
header>.muted{font-size:.78rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent2)}
h1{font:700 1.7rem/1.2 Georgia,serif;margin:.15em 0 .2em;color:var(--accent)}header p{margin:.2em 0;color:var(--muted);font-size:.95rem}
h2{font:700 1.5rem/1.2 Georgia,serif;margin-top:44px;padding-bottom:6px;border-bottom:2px solid var(--accent);color:var(--ink)}h3{color:var(--accent)}h4{color:var(--accent)}h5{color:var(--ink)}
a{color:var(--accent)}.hero,.callout,.current{border-left:4px solid var(--accent);background:var(--soft);border-radius:5px}.current{border:2px solid var(--accent)}
.part,.goal,.artifact,.shell,.completion-card,.approval{background:var(--card);border-color:var(--line)}.approval{border-color:var(--accent)}.float-budget{border-color:var(--accent);background:var(--card)}
th{background:var(--soft)}td,th{border-color:var(--line)}table{background:var(--card)}.pending,.status{color:var(--accent2)}.badge{background:var(--soft);color:var(--accent)}
.copy{background:var(--accent)}.pending-plot{border-color:var(--line)}details>summary{cursor:pointer;color:var(--accent);font-weight:600}.paragraph{border-bottom-color:var(--line)}
"""


# One page background per report; cards stay white so layout and colors otherwise match.
# Tailwind-style single-hue schemes per report: page (50), highlight (100), accent (700).
PAPER = {
    "profile": ("#faf8f3", "#eef6f3", "#0b6b59"),
    "literature": ("#f6fefa", "#ecfdf5", "#047857"),
    "ideas": ("#fffdf5", "#fffbeb", "#b45309"),
    "expplan": ("#f7fcff", "#f0f9ff", "#0369a1"),
    "runplan": ("#faf9ff", "#f5f3ff", "#6d28d9"),
    "results": ("#fbfff3", "#f7fee7", "#4d7c0f"),
}


def with_theme(css: str, kind: str = "") -> str:
    """Return ``css`` followed by the shared theme (idempotent); ``kind`` picks the page background."""
    if THEME_MARKER in css:
        return css
    paper = ":root{--paper:%s;--soft:%s;--accent:%s;--green:%s}\n" % (*PAPER[kind], PAPER[kind][2]) if kind else ""
    return css.rstrip() + "\n" + THEME_CSS + paper


def apply_theme(html: str) -> str:
    """Inject the theme into the first <style> block of a rendered report."""
    if THEME_MARKER in html:
        return html
    return re.sub(r"</style>", THEME_CSS + "</style>", html, count=1)
