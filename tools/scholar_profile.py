#!/usr/bin/env python3
"""Read a Google Scholar profile into structured JSON.

Used by the ``profileconstruct`` skill (skills/profileconstruct/SKILL.md) — the
substrate for ARIS personalization. Google Scholar has no public API and blocks
script scrapers, so this helper reads the *rendered* page three ways:

Modes
-----
--from-html FILE   Parse a saved Scholar profile page (the live DOM the user
                   exported via DevTools "Copy outerHTML" / a Console download).
                   PRIMARY, most robust — no browser automation, no CAPTCHA.
--from-tab         Read the Scholar tab the user already has open (macOS, reads
                   the front Chrome/Safari tab's outerHTML via osascript).
--auto             Open the profile URL in Chrome and read it (macOS).

Output is JSON on stdout. On failure, a JSON object with an ``error`` key (and a
fix hint) is printed and the process exits non-zero.

Completeness
------------
Scholar serves only the first ~20 publications; the rest load via JavaScript when
the user clicks "Show more". A saved page or a tab that was not fully expanded is
*truncated*. We detect this from the "Show more" button (id ``gsc_bpf_more``):
present and NOT disabled => more papers exist that were not captured. The output
carries ``"truncated": true`` and a ``"warning"`` so callers never profile on a
partial record.

Examples
--------
python3 tools/scholar_profile.py --from-html gs_profile.html
python3 tools/scholar_profile.py --from-tab
python3 tools/scholar_profile.py --auto "https://scholar.google.com/citations?user=COUnAF4AAAAJ&hl=en"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path


# --------------------------------------------------------------------------- #
# URL helpers
# --------------------------------------------------------------------------- #
def _user_id_from(value: str) -> str | None:
    """Accept a bare user id or any Scholar URL; return the ?user= id."""
    if not value:
        return None
    m = re.search(r"[?&]user=([^&]+)", value)
    if m:
        return m.group(1)
    # bare id looks like 12 base64-ish chars
    if re.fullmatch(r"[A-Za-z0-9_-]{8,}", value):
        return value
    return None


def _profile_url(user_id: str, hl: str = "en", pagesize: int = 100) -> str:
    return (
        "https://scholar.google.com/citations"
        f"?user={user_id}&hl={hl}&cstart=0&pagesize={pagesize}"
    )


# --------------------------------------------------------------------------- #
# HTML parser
# --------------------------------------------------------------------------- #
class _ScholarParser(HTMLParser):
    """State-machine parser for a Google Scholar citations profile page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.profile: dict = {
            "name": "",
            "affiliation": "",
            "interests": [],
            "citations_all": 0,
            "h_index_all": 0,
            "i10_index_all": 0,
        }
        self.publications: list[dict] = []
        self.truncated: bool | None = None

        self._stats: list[str] = []
        self._affiliation_done = False

        # generic text capture (depth-tracked so nested tags don't end it early)
        self._cap: str | None = None
        self._cap_depth = 0
        self._buf: list[str] = []

        # row state
        self._in_row = False
        self._row: dict = {}
        self._gray_count = 0

    # -- capture helpers --------------------------------------------------- #
    def _start_cap(self, key: str) -> None:
        self._cap = key
        self._cap_depth = 1
        self._buf = []

    def _text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._buf)).strip()

    # -- tag handlers ------------------------------------------------------ #
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        cls = a.get("class", "")

        if self._cap is not None:
            self._cap_depth += 1
            return

        # truncation signal
        if a.get("id") == "gsc_bpf_more":
            self.truncated = "disabled" not in a

        # header fields
        if a.get("id") == "gsc_prf_in":
            self._start_cap("name")
            return
        if "gsc_prf_inta" in cls:
            self._start_cap("interest")
            return
        if "gsc_prf_il" in cls and not self._affiliation_done:
            self._start_cap("affiliation")
            return
        if "gsc_rsb_std" in cls:
            self._start_cap("stat")
            return

        # publication row
        if tag == "tr" and "gsc_a_tr" in cls:
            self._in_row = True
            self._row = {"title": "", "authors": "", "venue": "",
                         "year": "", "cited_by": 0, "url": ""}
            self._gray_count = 0
            return

        if self._in_row:
            if tag == "a" and "gsc_a_at" in cls:
                href = a.get("href", "")
                if href:
                    self._row["url"] = (
                        "https://scholar.google.com" + href
                        if href.startswith("/") else href
                    )
                self._start_cap("title")
                return
            if tag == "div" and "gs_gray" in cls:
                self._start_cap("gray")
                return
            if tag == "a" and "gsc_a_ac" in cls:
                self._start_cap("cites")
                return
            if tag == "span" and "gsc_a_h" in cls:
                self._start_cap("year")
                return

    def handle_data(self, data: str) -> None:
        if self._cap is not None:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._cap is not None:
            self._cap_depth -= 1
            if self._cap_depth > 0:
                return
            self._finish_cap()
            return
        if self._in_row and tag == "tr":
            self._in_row = False
            if self._row.get("title"):
                self.publications.append(self._row)
            self._row = {}

    def _finish_cap(self) -> None:
        key, text = self._cap, self._text()
        self._cap = None
        self._buf = []

        if key == "name":
            self.profile["name"] = text
        elif key == "affiliation":
            self.profile["affiliation"] = text
            self._affiliation_done = True
        elif key == "interest":
            if text:
                self.profile["interests"].append(text)
        elif key == "stat":
            self._stats.append(text)
        elif key == "title":
            self._row["title"] = text
        elif key == "gray":
            # first gs_gray = authors, second = venue
            if self._gray_count == 0:
                self._row["authors"] = text
            elif self._gray_count == 1:
                self._row["venue"] = text
            self._gray_count += 1
        elif key == "cites":
            self._row["cited_by"] = int(re.sub(r"\D", "", text) or 0)
        elif key == "year":
            m = re.search(r"\d{4}", text)
            if m:
                self._row["year"] = m.group(0)

    # -- finalize ---------------------------------------------------------- #
    def finalize(self) -> None:
        # stats order: [cit_all, cit_since, h_all, h_since, i10_all, i10_since]
        nums = [int(re.sub(r"\D", "", s) or 0) for s in self._stats]
        if len(nums) >= 1:
            self.profile["citations_all"] = nums[0]
        if len(nums) >= 3:
            self.profile["h_index_all"] = nums[2]
        if len(nums) >= 5:
            self.profile["i10_index_all"] = nums[4]
        # clean venue: strip the duplicate ", YYYY" the gs_oph span injects
        for p in self.publications:
            yr = p.get("year")
            if yr and p["venue"].endswith(f", {yr}"):
                p["venue"] = p["venue"][: -len(f", {yr}")].strip()


def _looks_blocked(html: str) -> bool:
    low = html.lower()
    return (
        "unusual traffic" in low
        or "captcha" in low
        or ("not a robot" in low and "gsc_a_tr" not in html)
    )


def parse_html(html: str) -> dict:
    if _looks_blocked(html):
        raise RuntimeError(
            "Google Scholar returned a CAPTCHA / 'unusual traffic' wall — the "
            "page was not the real profile. Open the profile in your own logged-in "
            "browser and export the page (DevTools > Elements > right-click <html> "
            "> Copy outerHTML), then pass it with --from-html."
        )
    p = _ScholarParser()
    p.feed(html)
    p.finalize()
    if not p.publications and not p.profile["name"]:
        raise RuntimeError(
            "No profile data found in the HTML — is this actually a Scholar "
            "citations page? Expected nodes like 'gsc_a_tr' / 'gsc_prf_in'."
        )
    out = {
        "source": "google_scholar",
        "profile": p.profile,
        "publications": p.publications,
        "publication_count": len(p.publications),
        "truncated": bool(p.truncated),
    }
    if p.truncated:
        out["warning"] = (
            f"Only {len(p.publications)} publications captured and Scholar's "
            "'Show more' button is still active — the page was NOT fully expanded. "
            "In the browser, click 'Show more' until it greys out, then re-export "
            "the page. Profiling on a partial record is disabled by the skill."
        )
    return out


# --------------------------------------------------------------------------- #
# macOS browser readers (osascript)
# --------------------------------------------------------------------------- #
_CHROME_READ_TAB = (
    'tell application "Google Chrome"\n'
    "  if (count of windows) = 0 then error \"no Chrome window open\"\n"
    "  set h to execute front window's active tab javascript "
    '"document.documentElement.outerHTML"\n'
    "  return h\n"
    "end tell"
)

_SAFARI_READ_TAB = (
    'tell application "Safari"\n'
    "  if (count of documents) = 0 then error \"no Safari document open\"\n"
    '  set h to (do JavaScript "document.documentElement.outerHTML" in front document)\n'
    "  return h\n"
    "end tell"
)


def _run_osa(script: str) -> str:
    proc = subprocess.run(
        ["osascript", "-"], input=script,
        capture_output=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "osascript failed").strip())
    return proc.stdout


def _js_toggle_hint(which: str) -> str:
    if which == "chrome":
        return ("Enable Chrome menu bar > View > Developer > "
                "'Allow JavaScript from Apple Events', then retry.")
    return ("Enable Safari Develop menu (Settings > Advanced), then "
            "Develop > 'Allow JavaScript from Apple Events', then retry.")


def fetch_from_tab() -> str:
    """Read the front Chrome tab, falling back to Safari (macOS)."""
    if sys.platform != "darwin":
        raise RuntimeError("--from-tab is macOS-only (needs osascript).")
    errors = []
    for name, script in (("chrome", _CHROME_READ_TAB), ("safari", _SAFARI_READ_TAB)):
        try:
            html = _run_osa(script)
            if html.strip():
                return html
            errors.append(f"{name}: empty response")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "Apple Events" in msg or "not allowed" in msg or "-1743" in msg:
                msg += " | " + _js_toggle_hint(name)
            errors.append(f"{name}: {msg}")
    raise RuntimeError("Could not read an open browser tab. " + " ; ".join(errors))


def fetch_auto(url: str) -> str:
    """Open the URL in Chrome and read it back (macOS)."""
    if sys.platform != "darwin":
        raise RuntimeError("--auto is macOS-only (needs osascript).")
    script = (
        'tell application "Google Chrome"\n'
        "  activate\n"
        "  if (count of windows) = 0 then make new window\n"
        f'  set URL of active tab of front window to "{url}"\n'
        "  delay 4\n"
        "  set h to execute front window's active tab javascript "
        '"document.documentElement.outerHTML"\n'
        "  return h\n"
        "end tell"
    )
    try:
        html = _run_osa(script)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "Apple Events" in msg or "-1743" in msg:
            msg += " | " + _js_toggle_hint("chrome")
        raise RuntimeError(msg) from exc
    if not html.strip():
        raise RuntimeError("Chrome returned an empty page for " + url)
    return html


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Read a Google Scholar profile to JSON.")
    ap.add_argument("profile", nargs="?", default="",
                    help="Scholar profile URL or bare user id (for --auto).")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--from-html", metavar="FILE",
                      help="Parse a saved/exported Scholar profile HTML file.")
    mode.add_argument("--from-tab", action="store_true",
                      help="Read the Scholar tab open in Chrome/Safari (macOS).")
    mode.add_argument("--auto", action="store_true",
                      help="Open the profile URL in Chrome and read it (macOS).")
    ap.add_argument("--dump-html", metavar="FILE",
                    help="Also write the raw HTML that was read to FILE.")
    args = ap.parse_args()

    try:
        if args.from_html:
            html = Path(args.from_html).read_text(encoding="utf-8", errors="ignore")
        elif args.from_tab:
            html = fetch_from_tab()
        elif args.auto:
            uid = _user_id_from(args.profile)
            if not uid:
                raise RuntimeError("--auto needs a Scholar URL or user id argument.")
            html = fetch_auto(_profile_url(uid))
        else:
            raise RuntimeError(
                "Pick a mode: --from-html FILE (recommended), --from-tab, or --auto URL."
            )

        if args.dump_html:
            Path(args.dump_html).write_text(html, encoding="utf-8")

        result = parse_html(html)
        if args.profile:
            uid = _user_id_from(args.profile)
            if uid:
                result["user_id"] = uid
                result["profile_url"] = _profile_url(uid)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
