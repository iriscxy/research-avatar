#!/usr/bin/env python3
"""paper_checks.py — deterministic paper-conformance gates (paperkit-equivalent).

Ported from watson `paperkit`'s check family, with NO external dependency: pure
stdlib, reads the LaTeX source + the compile log, emits JSON. These gates exist so a
draft cannot *claim* to be venue-ready without mechanically passing — never lower a
threshold to make one green; fix the paper.

Subcommands (each prints one JSON object with an `ok` bool + details):
  budget   per-section word-share vs paper/budget.json (±tol), seeded from the reference's
           MEASURED shares (refshares) — the analysis section is typically largest, NOT
           Experiments; the Conclusion share is small (the ref's is a short paragraph)
  style    LLM-tell budgets per 1k body words + zero contractions + equation floor
  length   Conclusion ends AT/NEAR the bottom of the target page (endconclusion==target; the
           following section may start on target+1, OR on the target page within ±5 lines of the
           bottom) — reached by BODY content, never by padding the Conclusion
  formal   theory/verify.py present + body equation count + derivations appendix
  scholarship claim-level citation obligations + Setup what/why evidence
  consistency canonical terminology + source-value + manuscript/verifier bindings
  format   overfull hboxes (from log) + widow/club penalty set + wide-table-as-table*
           + caption position (figures AND tables) matches the reference (--caption-pos)
  all      run every check; exit 1 if any fails

Run `python3 research_avatar/tools/paper_checks.py <sub> --help` for flags. Typical:
  python3 research_avatar/tools/paper_checks.py all --paper-dir paper --venue-pages 8 --body-target 8
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tokenize
from io import StringIO
from pathlib import Path

# ---- tunable thresholds (per 1000 words of body text unless noted) ----------
STYLE_BUDGETS = {
    "em_dash_per_1k": 2.0,     # '---' / '—' — LLM tell
    "paren_per_1k": 12.0,      # parenthetical asides
    "bold_per_1k": 1.0,        # \textbf as BODY emphasis (headings exempt)
    "italic_per_1k": 3.0,      # \emph/\textit as body emphasis
    "contractions_total": 0,   # don't / it's / we're — must be zero in a paper
}
EQUATION_FLOOR = 4             # numbered body equations a formal paper should carry
PARAGRAPH_SECTION_WORDS = 500  # a body section longer than this with NO \paragraph is flagged
BUDGET_TOL = 0.03             # ±3% per-section word-share band

# Real contractions only — NOT possessive 's (concept's, model's are fine in a paper).
CONTRACTION_RE = re.compile(
    r"\b([A-Za-z]+n['’]t|[A-Za-z]+['’](re|ve|ll|d|m)"
    r"|(it|that|there|here|what|who|he|she|let)['’]s)\b", re.I)
CTRL_SEQ_RE = re.compile(r"\\[A-Za-z@]+\*?")
WORD_RE = re.compile(r"[A-Za-z]{2,}")


# ---------- source loading / section splitting ----------
def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


class TexTreeError(RuntimeError):
    """Raised when the manuscript's modular LaTeX tree is not safely readable."""


def strip_inactive_tex(tex):
    r"""Remove simple/nested \iffalse branches so hidden evidence cannot satisfy gates."""
    token_re = re.compile(r"\\iffalse\b|\\iftrue\b|\\fi\b")
    output, stack, cursor = [], [], 0
    for match in token_re.finditer(tex):
        if all(stack):
            output.append(tex[cursor:match.start()])
        token = match.group(0)
        if token == r"\iffalse":
            stack.append(False)
        elif token == r"\iftrue":
            stack.append(True)
        elif stack:
            stack.pop()
        cursor = match.end()
    if all(stack):
        output.append(tex[cursor:])
    return "".join(output)


def read_tex_tree(main_path, *, root=None):
    r"""Recursively expand \input/\include from one workspace-contained TeX tree.

    Checks must inspect the manuscript that LaTeX compiles, not only main.tex.
    Commented includes are ignored; missing files, cycles, and paths escaping the
    paper directory fail closed instead of silently reducing checker coverage.
    """
    main = Path(main_path).resolve()
    boundary = Path(root).resolve() if root is not None else main.parent

    def expand(path, stack):
        resolved = path.resolve()
        try:
            resolved.relative_to(boundary)
        except ValueError as exc:
            raise TexTreeError(f"TeX include escapes paper directory: {resolved}") from exc
        if resolved in stack:
            cycle = " -> ".join(p.name for p in (*stack, resolved))
            raise TexTreeError(f"cyclic TeX include: {cycle}")
        if not resolved.is_file():
            raise TexTreeError(f"missing TeX include: {resolved}")
        source = strip_inactive_tex(strip_comments(read(resolved)))

        def replace(match):
            value = (match.group(1) or match.group(2)).strip()
            child = Path(value)
            if child.suffix == "":
                child = child.with_suffix(".tex")
            return expand(resolved.parent / child, (*stack, resolved))

        # TeX accepts both ``\input{file}`` and the primitive ``\input file`` form.
        return re.sub(
            r"\\(?:input|include)(?![A-Za-z@])\s*(?:\{([^}]+)\}|([^\s%]+))",
            replace,
            source,
        )

    return expand(main, ())


def manuscript_tex(args):
    return read_tex_tree(
        os.path.join(args.paper_dir, args.main), root=args.paper_dir
    )


def strip_comments(tex):
    out = []
    for line in tex.splitlines():
        # drop from an unescaped % to end of line
        m = re.search(r"(?<!\\)%", line)
        out.append(line[: m.start()] if m else line)
    return "\n".join(out)


def body_only(tex):
    """Text from \\begin{document} up to \\appendix / \\bibliography (main body)."""
    t = tex
    i = t.find(r"\begin{document}")
    if i != -1:
        t = t[i:]
    for marker in (r"\appendix", r"\bibliography", r"\begin{thebibliography}"):
        j = t.find(marker)
        if j != -1:
            t = t[:j]
    return t


def sections(body):
    """List of (title, text) for each \\section in the body, in order."""
    parts = re.split(r"\\section\*?\{([^}]*)\}", body)
    out = []
    # parts = [pre, title1, text1, title2, text2, ...]
    for k in range(1, len(parts), 2):
        out.append((parts[k].strip(), parts[k + 1]))
    return out


def wordcount(text):
    return len(WORD_RE.findall(CTRL_SEQ_RE.sub(" ", strip_comments(text))))


def prose_text(body):
    """Body PROSE only: drop float environments (table/figure/algorithm/tabular) and the
    text of headings/captions, so emphasis budgets measure running prose — bold in a
    results table or a \\paragraph heading is legitimate, not a body-emphasis tell."""
    t = strip_comments(body)
    for env in ("table\\*?", "figure\\*?", "algorithm", "tabular", "align\\*?",
                "equation\\*?"):
        t = re.sub(r"\\begin\{" + env + r"\}.*?\\end\{" + env.replace("\\*?", "") + r"\*?\}",
                   " ", t, flags=re.S)
    # Parentheses inside inline mathematics are notation, not parenthetical prose.
    t = re.sub(r"\\\(.*?\\\)", " ", t, flags=re.S)
    t = re.sub(r"(?<!\\)\$.*?(?<!\\)\$", " ", t, flags=re.S)
    # remove the argument text of headings / captions (bold there is fine)
    t = re.sub(r"\\(paragraph|section|subsection|caption|title)\*?\{[^}]*\}", " ", t)
    return t


def log_pages(paper_dir, main_base):
    """Page count from the compile log ('Output written on main.pdf (N pages'), or None."""
    log = os.path.join(paper_dir, main_base + ".log")
    if not os.path.exists(log):
        return None
    m = re.search(r"Output written on .*\((\d+) pages?", read(log))
    return int(m.group(1)) if m else None


def log_overfull(paper_dir, main_base):
    log = os.path.join(paper_dir, main_base + ".log")
    if not os.path.exists(log):
        return None
    return len(re.findall(r"Overfull \\hbox", read(log)))


# ---------- checks ----------
def check_budget(args):
    tex = manuscript_tex(args)
    body = body_only(tex)
    secs = sections(body)
    counts = [(t, wordcount(x)) for t, x in secs]
    total = sum(c for _, c in counts) or 1
    shares = [(t, c, round(c / total, 4)) for t, c in counts]

    bpath = os.path.join(args.paper_dir, args.budget)
    budget = json.loads(Path(bpath).read_text(encoding="utf-8")) if os.path.exists(bpath) else None

    violations = []
    if budget:
        for key, target in budget.items():
            if key.startswith("_"):  # _comment etc. are not sections
                continue
            matched = [(t, s) for (t, c, s) in shares if key.lower() in t.lower()]
            if not matched:
                violations.append({"section": key, "issue": "missing", "target": target})
                continue
            _, s = matched[0]
            if abs(s - target) > BUDGET_TOL:
                violations.append({"section": key, "actual": s, "target": target,
                                   "delta": round(s - target, 4)})
    # NOTE: no hard "Experiments must be largest" rule — the per-section targets in budget.json
    # are MEASURED from the reference, whose analysis section may legitimately be the largest
    # block. The ±3% per-section band is the gate; it already encodes the reference's distribution.
    return {"check": "budget", "ok": not violations,
            "has_budget_json": bool(budget), "tol": BUDGET_TOL,
            "shares": [{"section": t, "words": c, "share": s} for t, c, s in shares],
            "violations": violations}


def check_style(args):
    tex = manuscript_tex(args)
    body = body_only(tex)
    clean = strip_comments(body)       # for the equation floor (counts equation envs)
    prose = prose_text(body)           # for emphasis / em-dash / paren budgets
    words = len(WORD_RE.findall(CTRL_SEQ_RE.sub(" ", prose))) or 1
    per1k = lambda n: round(n * 1000 / words, 2)

    counts = {
        "em_dash": len(re.findall(r"---|—", prose)),
        "paren": prose.count("("),
        "bold": len(re.findall(r"\\textbf\{", prose)),
        "italic": len(re.findall(r"\\emph\{|\\textit\{", prose)),
        "contractions": len(CONTRACTION_RE.findall(prose)),
    }
    equations = len(re.findall(r"\\begin\{(equation|align|gather|multline)\*?\}", clean)) \
        + len(re.findall(r"(?<!\\)\\\[", clean))

    rates = {
        "em_dash_per_1k": per1k(counts["em_dash"]),
        "paren_per_1k": per1k(counts["paren"]),
        "bold_per_1k": per1k(counts["bold"]),
        "italic_per_1k": per1k(counts["italic"]),
    }
    viol = []
    for k, budget in STYLE_BUDGETS.items():
        if k == "contractions_total":
            if counts["contractions"] > budget:
                viol.append({"metric": k, "value": counts["contractions"], "budget": budget})
        elif rates[k] > budget:
            viol.append({"metric": k, "rate": rates[k], "budget": budget})
    if equations < EQUATION_FLOOR:
        viol.append({"metric": "equation_floor", "value": equations, "budget": EQUATION_FLOOR})

    # no bullet/numbered lists in the body — contributions and lists are written as prose
    bullets = len(re.findall(r"\\begin\{(itemize|enumerate)\}", clean))
    if bullets:
        viol.append({"metric": "body_bullets", "value": bullets, "budget": 0,
                     "note": "write contributions/lists as prose, not itemize/enumerate"})

    # Internal workflow artifacts belong in code/reproducibility records, never in
    # scientific prose. Inspect running prose rather than LaTeX include/figure paths.
    leak_patterns = {
        "workspace_path": r"\b(?:paper|results|reports|tools|code)/[A-Za-z0-9_.\-/]+",
        "implementation_file": r"\b[A-Za-z0-9_.-]+\.(?:py|json|csv|md)\b",
        "agent_command": r"(?:\$(?:expplan|runplan|ideagen)|/(?:goal|expplan|runplan|ideagen))\b",
        "workflow_jargon": r"\b(?:RUN_STATE|RESULTS_LEDGER|canonical artifact|Coding Agent)\b",
    }
    for kind, pattern in leak_patterns.items():
        hits = sorted(set(re.findall(pattern, prose, flags=re.I)))
        if hits:
            viol.append({"metric": "internal_workflow_leak", "kind": kind, "hits": hits})

    # Abstract length/completeness is venue/reference-derived and therefore stored
    # alongside the paper rather than hard-coded here.
    abstract_contract_path = os.path.join(args.paper_dir, "abstract_contract.json")
    abstract_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    if not os.path.exists(abstract_contract_path):
        viol.append({"metric": "abstract_contract", "issue": "missing abstract_contract.json"})
    elif not abstract_match:
        viol.append({"metric": "abstract_contract", "issue": "abstract environment not found"})
    else:
        with open(abstract_contract_path, encoding="utf-8") as contract_file:
            abstract_contract = json.load(contract_file)
        abstract = CTRL_SEQ_RE.sub(" ", strip_comments(abstract_match.group(1)))
        abstract_words = len(WORD_RE.findall(abstract))
        minimum = abstract_contract.get("min_words")
        maximum = abstract_contract.get("max_words")
        if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum <= 0 or maximum < minimum:
            viol.append({"metric": "abstract_contract", "issue": "invalid min_words/max_words"})
        elif not minimum <= abstract_words <= maximum:
            viol.append({"metric": "abstract_length", "words": abstract_words,
                         "allowed": [minimum, maximum]})
        required_slots = {"motivation", "gap", "method", "evaluation_scope", "principal_result", "takeaway"}
        evidence = abstract_contract.get("slot_evidence", {})
        if set(evidence) != required_slots:
            viol.append({"metric": "abstract_slots", "issue": "slot_evidence must contain all six roles",
                         "missing": sorted(required_slots - set(evidence))})
        else:
            normalized_abstract = re.sub(r"\s+", " ", abstract).strip().lower()
            missing_slots = [slot for slot, phrase in evidence.items()
                             if not str(phrase).strip() or re.sub(r"\s+", " ", str(phrase)).strip().lower()
                             not in normalized_abstract]
            if missing_slots:
                viol.append({"metric": "abstract_slots", "missing_or_stale": sorted(missing_slots)})

    # long section with no \paragraph subheading — exempt narrative sections that
    # conventionally have none (Intro/Conclusion/Limitations/Ethics/Discussion).
    NARRATIVE = ("introduction", "conclusion", "limitation", "ethic", "discussion", "future")
    for t, x in sections(body):
        if any(w in t.lower() for w in NARRATIVE):
            continue
        if wordcount(x) > PARAGRAPH_SECTION_WORDS and not re.search(
            r"\\(?:subsection|paragraph)\*?\{", strip_comments(x)
        ):
            viol.append({"metric": "no_subheading", "section": t, "words": wordcount(x)})

    return {"check": "style", "ok": not viol, "body_words": words,
            "counts": counts, "rates": rates, "equations": equations,
            "budgets": STYLE_BUDGETS, "violations": viol}


def check_scholarship(args):
    """Check explicit citation and experimental-setup obligations without quotas."""
    tex = manuscript_tex(args)
    section_map = {title.lower(): text for title, text in sections(body_only(tex))}
    contract_path = os.path.join(args.paper_dir, "scholarship_contract.json")
    violations = []
    if not os.path.exists(contract_path):
        return {"check": "scholarship", "ok": False,
                "violations": [{"issue": "missing scholarship_contract.json"}]}
    with open(contract_path, encoding="utf-8") as contract_file:
        contract = json.load(contract_file)

    def section_text(label):
        matches = [text for title, text in section_map.items() if label.lower() in title]
        return "\n".join(matches)

    obligations = contract.get("citation_obligations", [])
    if not obligations:
        violations.append({"issue": "citation_obligations must be non-empty"})
    coverage = contract.get("nearest_neighbor_coverage")
    if contract.get("schema_version") == "1.1" and not isinstance(coverage, list):
        violations.append({"issue": "nearest_neighbor_coverage is required by schema 1.1"})
    for index, contribution in enumerate(coverage or []):
        required = ("contribution_id", "claim", "nearest_neighbors")
        missing = [field for field in required if not contribution.get(field)]
        if missing:
            violations.append({"issue": "nearest_neighbor_coverage_incomplete",
                               "index": index, "missing": missing})
            continue
        neighbors = contribution["nearest_neighbors"]
        if not isinstance(neighbors, list) or len(neighbors) < 2:
            violations.append({"issue": "too_few_nearest_neighbors",
                               "contribution_id": contribution["contribution_id"], "minimum": 2})
            continue
        keys = []
        for neighbor_index, neighbor in enumerate(neighbors):
            fields = ("citation_key", "overlap", "independent_difference", "source_url")
            missing_neighbor = [field for field in fields if not str(neighbor.get(field, "")).strip()]
            if missing_neighbor:
                violations.append({"issue": "nearest_neighbor_incomplete",
                                   "contribution_id": contribution["contribution_id"],
                                   "index": neighbor_index, "missing": missing_neighbor})
            keys.append(str(neighbor.get("citation_key", "")))
        if len(keys) != len(set(keys)):
            violations.append({"issue": "duplicate_nearest_neighbor",
                               "contribution_id": contribution["contribution_id"]})
    for index, item in enumerate(obligations):
        required = ("name", "kind", "section", "citation_key", "supported_clause",
                    "source_evidence_path", "source_evidence_excerpt")
        missing = [key for key in required if not str(item.get(key, "")).strip()]
        if missing:
            violations.append({"issue": "citation_obligation_incomplete", "index": index,
                               "missing": missing})
            continue
        evidence_path = (Path(args.paper_dir).resolve().parent / item["source_evidence_path"]).resolve()
        project_root = Path(args.paper_dir).resolve().parent
        try:
            evidence_path.relative_to(project_root)
            evidence_text = evidence_path.read_text(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            evidence_text = ""
        if str(item["source_evidence_excerpt"]).strip() not in evidence_text:
            violations.append({"issue": "citation_source_evidence_missing", "name": item["name"],
                               "path": str(item["source_evidence_path"])})
        text = section_text(item["section"])
        if not text:
            violations.append({"issue": "citation_section_missing", "name": item["name"],
                               "section": item["section"]})
        else:
            cited = {
                key.strip()
                for group in re.findall(r"\\cite\w*\{([^}]*)\}", text)
                for key in group.split(",")
            }
        if text and item["citation_key"] not in cited:
            violations.append({"issue": "citation_missing_at_use", "name": item["name"],
                               "section": item["section"], "citation_key": item["citation_key"]})
        elif text:
            clause = re.sub(r"\s+", " ", str(item["supported_clause"])).strip().lower()
            sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
            if not any(
                clause in sentence.lower()
                and item["citation_key"] in {
                    key.strip() for group in re.findall(r"\\cite\w*\{([^}]*)\}", sentence)
                    for key in group.split(",")
                }
                for sentence in sentences
            ):
                violations.append({"issue": "citation_not_bound_to_supported_clause",
                                   "name": item["name"], "section": item["section"],
                                   "citation_key": item["citation_key"]})

    normalized_obligations = [
        {
            "section": str(item.get("section", "")).lower(),
            "key": str(item.get("citation_key", "")),
            "clause": re.sub(r"\s+", " ", str(item.get("supported_clause", ""))).lower(),
            "name": str(item.get("name", "")).lower(),
        }
        for item in obligations if isinstance(item, dict)
    ]
    obligation_key_set = {item["key"] for item in normalized_obligations}
    for contribution in coverage or []:
        for neighbor in contribution.get("nearest_neighbors", []):
            key = str(neighbor.get("citation_key", ""))
            if key and key not in obligation_key_set:
                violations.append({"issue": "nearest_neighbor_missing_citation_obligation",
                                   "contribution_id": contribution.get("contribution_id"),
                                   "citation_key": key})
    for title, section in section_map.items():
        for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", section)):
            sentence_lower = sentence.lower()
            keys = {
                key.strip() for group in re.findall(r"\\cite\w*\{([^}]*)\}", sentence)
                for key in group.split(",")
            }
            for key in keys:
                if not any(item["section"] in title and item["key"] == key
                           and item["clause"] in sentence_lower for item in normalized_obligations):
                    violations.append({"issue": "cited_sentence_missing_support_obligation",
                                       "section": title, "citation_key": key})
            for item in normalized_obligations:
                if item["section"] in title and item["name"] and item["name"] in sentence_lower:
                    if item["key"] not in keys or item["clause"] not in sentence_lower:
                        violations.append({"issue": "named_source_claim_outside_supported_clause",
                                           "section": title, "name": item["name"]})

    audit = contract.get("independent_source_audit", {})
    audit_keys = {str(key) for key in audit.get("checked_keys", [])} if isinstance(audit, dict) else set()
    obligation_keys = {str(item.get("citation_key")) for item in obligations if isinstance(item, dict)}
    try:
        dt_value = __import__("datetime").date.fromisoformat(str(audit.get("reviewed_at", "")))
        del dt_value
        date_valid = True
    except (ValueError, TypeError):
        date_valid = False
    if not (
        isinstance(audit, dict) and audit.get("verdict") == "pass"
        and audit.get("metadata_verified") is True and date_valid
        and audit_keys == obligation_keys and audit.get("unsupported_clauses") == []
    ):
        violations.append({"issue": "independent_source_audit_incomplete_or_red"})

    entities = contract.get("setup_entities", [])
    if not entities:
        violations.append({"issue": "setup_entities must be non-empty"})
    for index, item in enumerate(entities):
        required = ("name", "kind", "section", "description_evidence",
                    "rationale_evidence", "claim_ids", "citation_key")
        missing = [key for key in required if key not in item or item[key] in (None, "", [])]
        if missing:
            violations.append({"issue": "setup_entity_incomplete", "index": index,
                               "missing": missing})
            continue
        text = re.sub(r"\s+", " ", section_text(item["section"])).lower()
        for field in ("description_evidence", "rationale_evidence"):
            phrase = re.sub(r"\s+", " ", str(item[field])).lower()
            if phrase not in text:
                violations.append({"issue": f"setup_{field}_missing", "name": item["name"],
                                   "section": item["section"]})
    return {"check": "scholarship", "ok": not violations,
            "citation_obligations": len(obligations), "setup_entities": len(entities),
            "violations": violations}


def _json_pointer(value, pointer):
    node = value
    for token in str(pointer).strip("/").split("/") if str(pointer).strip("/") else []:
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _decision_holds(value, operator, threshold):
    operators = {
        ">=": lambda left, right: left >= right,
        ">": lambda left, right: left > right,
        "<=": lambda left, right: left <= right,
        "<": lambda left, right: left < right,
        "==": lambda left, right: left == right,
    }
    if operator not in operators:
        raise ValueError(f"unsupported decision operator: {operator}")
    return operators[operator](value, threshold)


def check_consistency(args):
    """Bind canonical names, source values, and checked formulas across the paper."""
    paper_dir = Path(args.paper_dir).resolve()
    project_root = paper_dir.parent
    tex = manuscript_tex(args)
    contract_path = paper_dir / "scientific_consistency.json"
    violations = []
    if not contract_path.is_file():
        return {"check": "consistency", "ok": False,
                "violations": [{"issue": "missing scientific_consistency.json"}]}
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"check": "consistency", "ok": False,
                "violations": [{"issue": "invalid scientific_consistency.json", "error": str(exc)}]}

    terms = contract.get("canonical_terms", [])
    values = contract.get("source_values", [])
    formal_links = contract.get("formal_links", [])
    empirical_claims = contract.get("empirical_claims")
    if contract.get("schema_version") == "1.1" and not isinstance(empirical_claims, list):
        violations.append({"issue": "empirical_claims is required by schema 1.1"})
    source_plan_value = str(contract.get("source_plan", "")).strip()
    try:
        source_plan = (project_root / source_plan_value).resolve()
        source_plan.relative_to(project_root)
        plan_source = source_plan.read_text(encoding="utf-8")
        plan_match = re.search(
            r'<script\b[^>]*id=["\']experiment-plan-contract["\'][^>]*>(.*?)</script>',
            plan_source, re.S | re.I,
        )
        if not plan_match:
            raise ValueError("missing experiment-plan-contract")
        plan_contract = json.loads(plan_match.group(1))
        if plan_contract.get("approval_status") != "approved":
            raise ValueError("source experiment plan is not approved")
        required_ids = plan_contract.get("consistency_requirements", {})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        required_ids = {}
        violations.append({"issue": "consistency_source_plan_invalid", "error": str(exc)})

    actual_ids = {
        "canonical_terms": {str(item.get("id")) for item in terms if isinstance(item, dict)},
        "source_values": {str(item.get("id")) for item in values if isinstance(item, dict)},
        "formal_links": {str(item.get("id")) for item in formal_links if isinstance(item, dict)},
    }
    for key, actual in actual_ids.items():
        expected = {str(item) for item in required_ids.get(key, [])}
        if actual != expected:
            violations.append({"issue": "consistency_coverage_mismatch", "kind": key,
                               "expected": sorted(expected), "actual": sorted(actual)})
    if not terms:
        violations.append({"issue": "canonical_terms must be non-empty"})
    for index, item in enumerate(terms):
        if not all(key in item for key in ("id", "canonical", "forbidden_aliases")):
            violations.append({"issue": "canonical_term_incomplete", "index": index})
            continue
        canonical = str(item["canonical"])
        if canonical.lower() not in tex.lower():
            violations.append({"issue": "canonical_term_missing", "id": item["id"]})
        for alias in item["forbidden_aliases"]:
            if str(alias).lower() in tex.lower():
                violations.append({"issue": "forbidden_term_alias", "id": item["id"],
                                   "alias": alias})

    if not values:
        violations.append({"issue": "source_values must be non-empty"})
    for index, item in enumerate(values):
        required = ("id", "source_path", "source_locator", "expected_value",
                    "manuscript_evidence")
        if any(key not in item for key in required):
            violations.append({"issue": "source_value_incomplete", "index": index})
            continue
        source = (project_root / str(item["source_path"])).resolve()
        try:
            source.relative_to(project_root)
            observed = _json_pointer(json.loads(source.read_text(encoding="utf-8")),
                                     item["source_locator"])
        except (ValueError, OSError, KeyError, IndexError, json.JSONDecodeError) as exc:
            violations.append({"issue": "source_value_unreadable", "id": item["id"],
                               "error": str(exc)})
            continue
        if observed != item["expected_value"]:
            violations.append({"issue": "source_value_mismatch", "id": item["id"],
                               "expected": item["expected_value"], "observed": observed})
        if str(item["manuscript_evidence"]) not in tex:
            violations.append({"issue": "source_value_manuscript_evidence_missing",
                               "id": item["id"]})

    for index, item in enumerate(empirical_claims or []):
        required = ("id", "source_path", "source_locator", "operator", "threshold",
                    "supported_text", "not_supported_text")
        missing = [field for field in required if field not in item or item[field] == ""]
        if missing:
            violations.append({"issue": "empirical_claim_incomplete", "index": index,
                               "missing": missing})
            continue
        source = (project_root / str(item["source_path"])).resolve()
        try:
            source.relative_to(project_root)
            value = _json_pointer(json.loads(source.read_text(encoding="utf-8")),
                                  item["source_locator"])
            holds = _decision_holds(value, item["operator"], item["threshold"])
        except (ValueError, OSError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            violations.append({"issue": "empirical_claim_unreadable", "id": item.get("id"),
                               "error": str(exc)})
            continue
        expected = str(item["supported_text"] if holds else item["not_supported_text"])
        contradicted = str(item["not_supported_text"] if holds else item["supported_text"])
        if expected not in tex or contradicted in tex:
            violations.append({"issue": "empirical_claim_rendering_stale", "id": item["id"],
                               "observed": value, "operator": item["operator"],
                               "threshold": item["threshold"], "expected_text": expected})

    verifier = paper_dir / "theory" / "verify.py"
    for index, item in enumerate(formal_links):
        required = ("id", "manuscript_evidence", "verifier_evidence")
        if any(not str(item.get(key, "")).strip() for key in required):
            violations.append({"issue": "formal_link_incomplete", "index": index})
            continue
        if str(item["manuscript_evidence"]) not in tex:
            violations.append({"issue": "formal_manuscript_evidence_missing", "id": item["id"]})
        verifier_text = verifier.read_text(encoding="utf-8") if verifier.is_file() else ""
        try:
            verifier_text = tokenize.untokenize(
                token for token in tokenize.generate_tokens(StringIO(verifier_text).readline)
                if token.type != tokenize.COMMENT
            )
        except (tokenize.TokenError, IndentationError):
            verifier_text = ""
        if str(item["verifier_evidence"]) not in verifier_text:
            violations.append({"issue": "formal_verifier_evidence_missing", "id": item["id"]})
    return {"check": "consistency", "ok": not violations,
            "canonical_terms": len(terms), "source_values": len(values),
            "formal_links": len(formal_links), "violations": violations}


def label_page(paper_dir, main_base, label_substr):
    """Page of a \\label{...<substr>...} marker, read from the .aux."""
    aux = os.path.join(paper_dir, main_base + ".aux")
    if not os.path.exists(aux):
        return None
    m = re.search(r"\\newlabel\{[^}]*" + label_substr + r"[^}]*\}\{\{[^}]*\}\{(\d+)\}", read(aux))
    return int(m.group(1)) if m else None


def _references_page(paper_dir, main_base):
    """Page where the References section starts (used for venues with no Limitations section, where
    References is the thing that follows the Conclusion). Uses pdftotext; None if unavailable."""
    import subprocess
    pdf = os.path.join(paper_dir, main_base + ".pdf")
    if not os.path.exists(pdf):
        return None
    try:
        out = subprocess.run(["pdftotext", pdf, "-"], capture_output=True,
                             encoding="utf-8", errors="replace").stdout
    except Exception:
        return None
    for i, pg in enumerate(out.split("\f"), 1):
        if any(line.strip() == "References" for line in pg.splitlines()):
            return i
    return None


LENGTH_LINE_TOL = 5   # ±N text lines: the Conclusion may end within N lines of the target-page
                      # bottom instead of exactly at it (float repacking makes exact-bottom fragile;
                      # the researcher confirmed ±5 lines is acceptable, 2026-07-26).


def _page_bottom_slack(paper_dir, main_base, page, heading_regex):
    """How many text lines sit BELOW a heading on `page`, i.e. how far the heading is from the page
    bottom, measured with `pdftotext -layout` (columns kept side by side so vertical position is
    preserved). Returns None if it cannot be measured. A SMALL slack means the section that follows
    the Conclusion (e.g. Limitations) starts near the bottom, so the Conclusion filled the page to
    within `slack` lines of the bottom."""
    import subprocess
    pdf = os.path.join(paper_dir, main_base + ".pdf")
    if not os.path.exists(pdf):
        return None
    try:
        out = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"],
                             capture_output=True, encoding="utf-8", errors="replace").stdout
    except Exception:
        return None
    # strip a leading review-mode line number (e.g. "592   Limitations ...") before matching
    lines = [re.sub(r"^\s*\d{1,4}\s+", "", ln) for ln in out.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return None
    total = len(lines)
    for i, ln in enumerate(lines):
        if re.search(heading_regex, ln):
            return total - i - 1   # lines strictly below the heading on this page
    return None


def check_length(args):
    """Length is judged by WHERE THE CONCLUSION ENDS, not by a page count. The venue-counted
    content (Intro..Conclusion) must end EXACTLY on the target page (e.g. the ACL 8th page) —
    not a page earlier (under-written, page 8 not reached) and not a page later (over the
    limit). Put `\\label{paper:endconclusion}` at the very end of the Conclusion and
    `\\label{paper:limstart}` right after `\\section*{Limitations}`; pass = endconclusion==target
    AND limstart==target+1 (Limitations pushed to the next page proves the Conclusion filled the
    target page to its bottom).
    CRITICAL — the fill comes from the BODY, not the Conclusion. The Conclusion must MIRROR THE
    REFERENCE's (short) conclusion length; the budget gate caps its share. When the Conclusion
    ends above the page bottom, add ANALYSIS/EXPERIMENTS content (or move a discussion paragraph
    into the analysis section), never inflate the Conclusion with a checklist / recap padding."""
    total = log_pages(args.paper_dir, args.main_base)
    conc = label_page(args.paper_dir, args.main_base, "endconclusion")
    lim = label_page(args.paper_dir, args.main_base, "limstart")  # start of Limitations
    tgt = args.body_target
    tex = manuscript_tex(args)
    conclusion_match = re.search(
        r"\\section\*?\s*\{\s*Conclusion(?:[^}]*)\}", tex, re.I
    )
    limitations_match = re.search(
        r"\\section\*?\s*\{\s*Limitations\s*\}", tex, re.I
    )
    limitations_after_conclusion = bool(
        limitations_match
        and conclusion_match
        and limitations_match.start() > conclusion_match.start()
    )
    refs_pg = (
        None
        if limitations_after_conclusion
        else _references_page(args.paper_dir, args.main_base)
    )
    viol = []
    if total is None:
        return {"check": "length", "ok": False, "issue": "no compile log — build first"}
    if conc is None:
        viol.append({"issue": "no_endconclusion_label",
                     "fix": r"add \label{paper:endconclusion} at the END of the Conclusion"})
    elif tgt:
        # The Conclusion must end at the BOTTOM of the target page, i.e. the section that follows it
        # (Limitations) must START on page target+1. `limstart` is the real signal — where Ethics
        # ends does NOT prove the Conclusion filled the page.
        if conc < tgt:
            viol.append({"issue": "conclusion_ends_too_early", "conclusion_end_page": conc,
                         "target_page": tgt, "note": "Conclusion ends before the target page — expand."})
        elif conc > tgt:
            viol.append({"issue": "conclusion_past_limit", "conclusion_end_page": conc,
                         "target_page": tgt, "note": "content overflows the page limit — trim."})
        elif limitations_after_conclusion and lim is None:
            viol.append({"issue": "no_limstart_label",
                         "fix": r"add \label{paper:limstart} right after \section*{Limitations}"})
        elif limitations_after_conclusion and lim <= tgt:
            # Limitations starts ON the target page rather than target+1. That is acceptable IF the
            # Conclusion still ended within LENGTH_LINE_TOL lines of the page bottom (the ±5-line
            # tolerance) — measured by how few lines sit below the Limitations heading on the page.
            slack = _page_bottom_slack(args.paper_dir, args.main_base, tgt, r"^\s*Limitations\b")
            if slack is None or slack > LENGTH_LINE_TOL:
                viol.append({"issue": "conclusion_not_at_page_bottom", "conclusion_end_page": conc,
                             "limitations_start_page": lim, "target_page": tgt,
                             "lines_below_target_bottom": slack, "line_tolerance": LENGTH_LINE_TOL,
                             "note": "Conclusion ends on page %d but ABOVE its bottom by more than %d lines "
                                     "(Limitations starts on page %d). Add counted content so the Conclusion "
                                     "fills page %d to within %d lines of the bottom." %
                                     (tgt, LENGTH_LINE_TOL, lim, tgt, LENGTH_LINE_TOL)})
        elif not limitations_after_conclusion and refs_pg is not None and refs_pg <= tgt:
            # References follow the approved body, including when Limitations precedes Conclusion.
            # within LENGTH_LINE_TOL lines of the target-page bottom (±5-line tolerance).
            slack = _page_bottom_slack(args.paper_dir, args.main_base, tgt, r"^\s*References\b")
            if slack is None or slack > LENGTH_LINE_TOL:
                viol.append({"issue": "conclusion_not_at_page_bottom", "conclusion_end_page": conc,
                             "references_start_page": refs_pg, "target_page": tgt,
                             "lines_below_target_bottom": slack, "line_tolerance": LENGTH_LINE_TOL,
                             "note": "Conclusion ends on page %d but References start on the same page more than "
                                     "%d lines above the bottom. Add BODY content so References start on page %d "
                                     "(or within %d lines of the bottom)." % (tgt, LENGTH_LINE_TOL, tgt + 1, LENGTH_LINE_TOL)})
        # else: References start on target+1 (or no page data) — the Conclusion fills the target page.
    boundary = "limitations" if limitations_after_conclusion else "references"
    return {"check": "length", "ok": not viol, "conclusion_end_page": conc,
            "limitations_start_page": lim, "references_start_page": refs_pg, "total_pages": total, "target_page": tgt,
            "post_body_boundary": boundary,
            "note": f"pass = Conclusion ends on the target page and the approved following boundary ({boundary}) starts on target+1 or within the bottom-line tolerance",
            "violations": viol}


def check_formal(args):
    theory = os.path.join(args.paper_dir, "theory", "verify.py")
    lean = os.path.join(args.paper_dir, "theory")
    has_verify = os.path.exists(theory) or (
        os.path.isdir(lean) and any(f.endswith(".lean") for f in os.listdir(lean)))
    tex = manuscript_tex(args)
    body = strip_comments(body_only(tex))
    equations = len(re.findall(r"\\begin\{(equation|align|gather|multline)\*?\}", body)) \
        + len(re.findall(r"(?<!\\)\\\[", body))
    full = strip_comments(tex)
    has_deriv = bool(re.search(r"deriv|proof|app_deriv", full, re.I))
    viol = []
    if not has_verify:
        viol.append({"issue": "no_mechanical_check", "want": "paper/theory/verify.py or *.lean"})
    elif os.path.exists(theory):
        try:
            process = subprocess.run(
                [sys.executable, str(Path(theory).resolve())], cwd=args.paper_dir,
                encoding="utf-8", errors="replace",
                capture_output=True, timeout=30, check=False,
            )
            if process.returncode != 0:
                viol.append({"issue": "mechanical_check_failed", "returncode": process.returncode,
                             "output": (process.stdout + process.stderr)[-1000:]})
            else:
                consistency_path = Path(args.paper_dir) / "scientific_consistency.json"
                required_formal = []
                if consistency_path.is_file():
                    required_formal = [
                        str(item.get("id")) for item in json.loads(
                            consistency_path.read_text(encoding="utf-8")
                        ).get("formal_links", []) if isinstance(item, dict) and item.get("id")
                    ]
                if required_formal:
                    try:
                        payload = json.loads(process.stdout.strip().splitlines()[-1])
                        checks = payload.get("checks", [])
                        checked = {str(item.get("id")): item for item in checks if isinstance(item, dict)}
                        valid_methods = {"sympy", "lean", "numeric", "symbolic"}
                        if set(checked) != set(required_formal) or any(
                            item.get("passed") is not True
                            or item.get("method") not in valid_methods
                            or "residual" not in item
                            for item in checked.values()
                        ):
                            raise ValueError("formal check coverage/status is incomplete")
                    except (json.JSONDecodeError, IndexError, AttributeError, ValueError) as exc:
                        viol.append({"issue": "mechanical_check_protocol_invalid", "error": str(exc)})
        except (OSError, subprocess.TimeoutExpired) as exc:
            viol.append({"issue": "mechanical_check_failed", "error": str(exc)})
    if equations < EQUATION_FLOOR:
        viol.append({"issue": "too_few_equations", "value": equations, "want": EQUATION_FLOOR})
    if not has_deriv:
        viol.append({"issue": "no_derivations_appendix"})
    return {"check": "formal", "ok": not viol, "has_verify": has_verify,
            "equations": equations, "has_derivations": has_deriv, "violations": viol}


def check_format(args):
    tex = manuscript_tex(args)
    full = strip_comments(tex)
    overfull = log_overfull(args.paper_dir, args.main_base)
    widow = bool(re.search(r"\\widowpenalty\s*=?\s*10000", full))
    club = bool(re.search(r"\\clubpenalty\s*=?\s*10000", full))
    # single-column \begin{table} whose tabular has many COLUMNS (likely should be table*).
    # Count columns from the tabular preamble, not total '&' (which conflates rows).
    wide_singlecol = []
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", full, re.S):
        spec = re.search(r"\\begin\{tabular\}\{([^}]*)\}", m.group(1))
        cols = len(re.findall(r"[lcr]|p\{", spec.group(1))) if spec else 0
        if cols >= 6:  # a genuinely wide table belongs in a full-width table*
            wide_singlecol.append(cols)
    # caption placement must MATCH THE REFERENCE PAPER's convention (personalization, not a
    # default) — measure the reference once (see SKILL Step 0.4) and pass it as --caption-pos.
    # "below" = \caption AFTER the content (\end{tabular} for tables, \includegraphics for
    # figures); "above" = before it. This profile's reference puts BOTH figure and table
    # captions BELOW, so that is the default here.
    cap_bad = []
    if args.caption_pos in ("below", "above"):
        want_below = args.caption_pos == "below"
        envs = [("table", r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", r"\\end\{tabular\}"),
                ("figure", r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", r"\\includegraphics")]
        for kind, env_re, anchor_re in envs:
            for m in re.finditer(env_re, full, re.S):
                body = m.group(1)
                cap = re.search(r"\\caption\b", body)
                anc = re.search(anchor_re, body)
                if not cap or not anc:
                    continue
                is_below = cap.start() > anc.start()
                if is_below != want_below:
                    cap_bad.append({"env": kind, "found": "above" if not is_below else "below",
                                    "want": args.caption_pos})
    viol = []
    if overfull:
        viol.append({"issue": "overfull_hboxes", "count": overfull})
    if not (widow and club):
        viol.append({"issue": "widow_club_penalty_unset",
                     "want": r"\widowpenalty=\clubpenalty=10000"})
    if wide_singlecol:
        viol.append({"issue": "wide_table_not_starred",
                     "dense_single_column_tables": len(wide_singlecol),
                     "note": "a wide/dense results table should be a full-width table*"})
    if cap_bad:
        viol.append({"issue": "caption_placement_mismatch", "want": args.caption_pos,
                     "offenders": cap_bad,
                     "note": "match the reference paper's caption position for figures AND tables"})
    return {"check": "format", "ok": not viol, "overfull": overfull,
            "widow_club_set": widow and club, "caption_pos": args.caption_pos,
            "violations": viol}


def check_floats(args):
    """Each figure/table must be DEFINED in the source at/near the section that first
    REFERENCES it, and figures must appear in first-reference order. Catches the common
    failure where the model/architecture figure is \\ref'd in the Method but its
    \\begin{figure} is dropped among the results floats, so it renders a section too late
    (Fig 2 landing after the results teaser instead of beside the Method that introduces it).
    A float defined in a LATER section than its first reference is the signal."""
    tex = strip_comments(manuscript_tex(args))
    section_pos = [m.start() for m in re.finditer(r"\\section\b\*?\s*\{", tex)]

    def sections_between(a, b):
        lo, hi = (a, b) if a <= b else (b, a)
        return sum(1 for p in section_pos if lo < p < hi)

    floats = []
    for m in re.finditer(r"\\begin\{(figure|table)\*?\}(.*?)\\end\{\1\*?\}", tex, re.S):
        lab = re.search(r"\\label\{([^}]*)\}", m.group(2))
        if not lab:
            continue
        key = lab.group(1)
        refs = [r.start() for r in
                re.finditer(r"\\(?:ref|autoref|cref|Cref)\{" + re.escape(key) + r"\}", tex)]
        floats.append({"kind": m.group(1), "label": key, "def_pos": m.start(),
                       "first_ref": min(refs) if refs else None})
    viol = []
    for f in floats:
        if f["first_ref"] is None:
            viol.append({"issue": "float_never_referenced", "label": f["label"],
                         "fix": "add a \\ref to it in the text, or drop the float"})
        elif f["first_ref"] < f["def_pos"] and sections_between(f["first_ref"], f["def_pos"]) >= 1:
            viol.append({"issue": "float_defined_after_its_reference_section", "label": f["label"],
                         "sections_between_ref_and_def": sections_between(f["first_ref"], f["def_pos"]),
                         "fix": "move \\begin{%s}..\\end{%s} to right after the paragraph that first "
                                "\\ref's %s (the model figure belongs beside the Method, not the results)"
                                % (f["kind"], f["kind"], f["label"])})
    figs = [f for f in floats if f["kind"] == "figure" and f["first_ref"] is not None]
    by_def = [f["label"] for f in sorted(figs, key=lambda f: f["def_pos"])]
    by_ref = [f["label"] for f in sorted(figs, key=lambda f: f["first_ref"])]
    if by_def != by_ref:
        viol.append({"issue": "figures_out_of_first_reference_order",
                     "by_definition": by_def, "by_first_reference": by_ref,
                     "fix": "reorder figure environments so definition order matches first-reference order"})
    return {"check": "floats", "ok": not viol, "n_floats": len(floats), "violations": viol}


CHECKS = {"budget": check_budget, "style": check_style, "scholarship": check_scholarship,
          "consistency": check_consistency,
          "length": check_length, "formal": check_formal, "format": check_format,
          "floats": check_floats}


def measure_ref_shares(ref_txt):
    """MEASURE the reference paper's per-section word shares from its extracted full text —
    so `budget.json` is SEEDED FROM THE REAL REFERENCE, never guessed from a paper 'class'.
    Heuristic on PDF-extracted text: numbered/all-caps section headers. Returns a JSON with
    each section's word share; use it to set budget.json AND to see how the reference splits
    empirical content between its ANALYSIS section and its Experiments section (don't dump
    everything into Experiments)."""
    t = read(ref_txt)
    heads = [(m.start(), m.group(0).strip())
             for m in re.finditer(r"(?m)^\s*(\d)\s+[A-Z][A-Za-z].{0,45}$", t)]
    seen, secs = {}, []
    for pos, txt in heads:
        n = txt.split()[0]
        if n in "123456789" and n not in seen and len(txt.split()) <= 8:
            seen[n] = pos; secs.append((pos, txt))
    secs.sort()
    wc = lambda s: len(WORD_RE.findall(s))
    rows, tot = [], 0
    for i, (pos, txt) in enumerate(secs):
        end = secs[i + 1][0] if i + 1 < len(secs) else (t.find("References", pos) or len(t))
        w = wc(t[pos:end if end > 0 else len(t)])
        rows.append((txt, w)); tot += w
    tot = tot or 1
    return {"reference": os.path.basename(ref_txt), "body_words_approx": tot,
            "note": "PDF-extracted headers are approximate; seed budget.json from these MEASURED "
                    "shares, and mirror the reference's analysis-vs-Experiments split",
            "sections": [{"section": txt, "words": w, "share": round(w / tot, 3)} for txt, w in rows]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("check", choices=list(CHECKS) + ["all", "refshares"])
    ap.add_argument("--paper-dir", default="paper")
    ap.add_argument("--main", default="main.tex", help="main tex filename")
    ap.add_argument("--budget", default="budget.json", help="budget filename (in paper-dir)")
    ap.add_argument("--ref", help="reference paper .txt (for refshares — measure its section shares)")
    ap.add_argument("--venue-pages", type=int, default=0, help="venue body page limit")
    ap.add_argument("--body-target", type=int, default=0,
                    help="reference paper's main-body page count to fill")
    ap.add_argument("--ref-appendix-pages", type=int, default=6,
                    help="allowance for refs+appendix over the body limit")
    ap.add_argument("--caption-pos", default="below", choices=["below", "above", "off"],
                    help="required caption position for figures AND tables — set from the "
                         "reference paper's measured convention (this profile: below)")
    args = ap.parse_args()
    args.main_base = os.path.splitext(args.main)[0]

    if args.check == "refshares":
        if not args.ref:
            sys.exit("refshares needs --ref <reference .txt>")
        print(json.dumps(measure_ref_shares(args.ref), indent=2, ensure_ascii=False))
        return

    if args.check == "all":
        results = {name: fn(args) for name, fn in CHECKS.items()}
        ok = all(r.get("ok") for r in results.values())
        print(json.dumps({"ok": ok, "checks": results}, indent=2, ensure_ascii=False))
        sys.exit(0 if ok else 1)
    res = CHECKS[args.check](args)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
