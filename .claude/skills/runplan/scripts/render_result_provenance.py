#!/usr/bin/env python3
"""Attach clickable, ledger-grounded provenance to an EXP_RESULT report."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from pathlib import Path


STATE_RE = re.compile(
    r'<script type="application/json" id="run-plan-state">(.*?)</script>', re.S
)
START = "<!-- RESULT_PROVENANCE_START -->"
END = "<!-- RESULT_PROVENANCE_END -->"


def load_acquisitions(plan: Path) -> dict[str, dict[str, object]]:
    match = STATE_RE.search(plan.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("run plan lacks embedded run-plan-state JSON")
    state = json.loads(match.group(1))
    contracts = state.get("acquisition_contracts", [])
    return {
        str(item["id"]): item
        for item in contracts
        if isinstance(item, dict) and item.get("id")
    }


def provenance_payload(ledger: Path, plan: Path) -> dict[str, dict[str, object]]:
    acquisitions = load_acquisitions(plan)
    payload: dict[str, dict[str, object]] = {}
    with ledger.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if (
                row.get("status") != "REAL"
                or row.get("verification_status") != "VERIFIED"
                or not row.get("artifact_id", "").strip()
            ):
                continue
            result_id = row["result_id"].strip()
            contract = acquisitions.get(row.get("acquisition_id", ""), {})
            kind = contract.get("atomic_or_aggregate")
            record: dict[str, object] = {
                "result_id": result_id,
                "goal_id": row.get("goal_id", ""),
                "metric": row.get("metric", ""),
                "value": row.get("value", ""),
                "unit": row.get("unit", ""),
                "dimensions": json.loads(row.get("dimensions_json") or "{}"),
                "source_type": row.get("source_type", ""),
                "acquisition_kind": kind,
                "calculation": (
                    contract.get("derivation")
                    if kind == "derived"
                    else {"kind": "atomic"}
                ),
                "obtained_at": row.get("obtained_at", ""),
                "verified_at": row.get("verified_at", ""),
                "verification_status": row.get("verification_status", ""),
            }
            if row.get("source_type") == "RUN_LOCAL":
                for field in (
                    "raw_artifact", "raw_locator", "command", "code_files",
                    "config_files", "environment_files", "code_revision",
                ):
                    record[field] = row.get(field, "")
            elif row.get("source_type") == "REUSE_REPORTED":
                record["source_reference"] = row.get("source_reference", "")
                record["source_locator"] = row.get("source_locator", "")
                record["reuse_notice"] = "not rerun locally"
            payload[result_id] = record
    return payload


def provenance_summary(record: dict[str, object]) -> str:
    """Build the compact hover/focus explanation copied with every value."""
    dimensions = json.dumps(record.get("dimensions", {}), ensure_ascii=False, sort_keys=True)
    calculation = json.dumps(record.get("calculation", {}), ensure_ascii=False, sort_keys=True)
    lines = [
        "生成过程",
        f"Goal: {record.get('goal_id', '')}",
        f"Metric: {record.get('metric', '')} = {record.get('value', '')} {record.get('unit', '')}".rstrip(),
        f"Dimensions: {dimensions}",
        f"Source: {record.get('source_type', '')}",
        f"Calculation: {calculation}",
    ]
    if record.get("source_type") == "RUN_LOCAL":
        lines.extend([
            f"Raw: {record.get('raw_artifact', '')} · {record.get('raw_locator', '')}",
            f"Command: {record.get('command', '')}",
            f"Code/config: {record.get('code_files', '')} · {record.get('config_files', '')}",
            f"Environment: {record.get('environment_files', '')}",
            f"Revision: {record.get('code_revision', '')}",
        ])
    else:
        lines.extend([
            f"Reported source: {record.get('source_reference', '')}",
            f"Locator: {record.get('source_locator', '')}",
            "Notice: not rerun locally",
        ])
    lines.append(
        f"Verified: {record.get('verification_status', '')} · {record.get('verified_at', '')}"
    )
    return "\n".join(lines)


def linkify_values(report: str, payload: dict[str, dict[str, object]]) -> str:
    for result_id, record in payload.items():
        escaped = html.escape(result_id, quote=True)
        summary = html.escape(provenance_summary(record), quote=True)
        existing_pattern = re.compile(
            rf'<a\b(?=[^>]*data-result-id="{re.escape(escaped)}")'
            rf'(?=[^>]*data-provenance-trigger="{re.escape(escaped)}")[^>]*>'
        )
        existing = existing_pattern.search(report)
        if existing:
            opening = existing.group(0)
            opening = re.sub(r'\sdata-provenance-summary="[^"]*"', "", opening)
            opening = re.sub(r'\stitle="[^"]*"', "", opening)
            opening = opening[:-1] + (
                f' data-provenance-summary="{summary}" title="{summary}">'
            )
            report = report[:existing.start()] + opening + report[existing.end():]
            continue
        cell = re.compile(
            rf'(<td\b(?=[^>]*data-result-id="{re.escape(escaped)}")[^>]*>)(.*?)(</td>)',
            re.S,
        )
        if not cell.search(report):
            raise ValueError(
                f"filled result {result_id} lacks a table cell carrying data-result-id"
            )
        report = cell.sub(
            lambda match: (
                match.group(1)
                + f'<a class="result-value" href="#provenance-{escaped}" '
                  f'data-result-id="{escaped}" data-provenance-trigger="{escaped}" '
                  f'data-provenance-summary="{summary}" title="{summary}">'
                + match.group(2)
                + "</a>"
                + match.group(3)
            ),
            report,
            count=1,
        )
    return report


INTERACTION = r"""
<style>
.result-value{position:relative;display:inline-block;color:inherit;font-weight:800;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px;cursor:help}
.result-value::after{content:attr(data-provenance-summary);position:absolute;z-index:80;left:50%;bottom:calc(100% + 9px);display:none;width:min(430px,72vw);max-height:320px;overflow:auto;padding:11px 13px;border:1px solid #8fbeb6;border-radius:8px;background:#102e3b;color:#f2fbf9;text-align:left;white-space:pre-line;box-shadow:0 12px 28px #102e3b3d;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;transform:translateX(-50%)}
.result-value:hover::after,.result-value:focus-visible::after{display:block}
#result-provenance-index{margin:34px 0;padding-top:18px;border-top:1px solid #d8e1df}
#result-provenance-index>h2{margin:0 0 12px;font-size:18px}
.provenance-card{margin:8px 0;border:1px solid #d8e1df;border-radius:9px;background:#fff;scroll-margin-top:18px}
.provenance-card:target{border-color:#087d70;box-shadow:0 0 0 3px #087d7022}
.provenance-card summary{padding:11px 13px;cursor:pointer;font-weight:800}
.provenance-fields{display:grid;grid-template-columns:140px minmax(0,1fr);gap:7px 12px;padding:0 13px 13px}
.provenance-fields dt{color:#667983;font-size:11px}.provenance-fields dd{margin:0;overflow-wrap:anywhere;font:11px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
.reuse-notice{color:#9a5b00;font-weight:900}
@media(max-width:640px){.provenance-fields{grid-template-columns:1fr}.provenance-fields dd{margin-bottom:5px}}
</style>
<section id="result-provenance-index" aria-label="结果生成过程"><h2>生成过程</h2></section>
<script>
(()=>{
  const payload=JSON.parse(document.getElementById("result-provenance").textContent);
  const root=document.getElementById("result-provenance-index");
  const labels={goal_id:"Goal",metric:"Metric",value:"Value",unit:"Unit",dimensions:"Dimensions",source_type:"Source type",acquisition_kind:"Acquisition kind",calculation:"Calculation / aggregation",obtained_at:"Obtained",verified_at:"Verified",verification_status:"Verification",raw_artifact:"Raw artifact",raw_locator:"Raw locator",command:"Command actually run",code_files:"Code files",config_files:"Config files",environment_files:"Environment files",code_revision:"Code revision",source_reference:"Reported source",source_locator:"Reported locator",reuse_notice:"Reuse notice"};
  const order=["goal_id","metric","value","unit","dimensions","source_type","acquisition_kind","calculation","obtained_at","verified_at","verification_status","raw_artifact","raw_locator","command","code_files","config_files","environment_files","code_revision","source_reference","source_locator","reuse_notice"];
  const text=value=>typeof value==="object"?JSON.stringify(value,null,2):String(value??"");
  Object.entries(payload).forEach(([id,record])=>{
    const card=document.createElement("details");card.className="provenance-card";card.id="provenance-"+id;card.tabIndex=-1;card.dataset.provenanceRecord=id;
    const summary=document.createElement("summary");summary.textContent=`${record.metric} · ${record.value}${record.unit?" "+record.unit:""} · ${record.goal_id}`;card.appendChild(summary);
    const fields=document.createElement("dl");fields.className="provenance-fields";
    order.forEach(key=>{if(!(key in record)||record[key]==="")return;const dt=document.createElement("dt");dt.textContent=labels[key];const dd=document.createElement("dd");dd.textContent=key==="reuse_notice"?"该数值来自已批准的论文复用，未在本地重跑。":text(record[key]);if(key==="reuse_notice")dd.className="reuse-notice";fields.append(dt,dd);});
    card.appendChild(fields);root.appendChild(card);
  });
  const reveal=()=>{if(!location.hash.startsWith("#provenance-"))return;const target=document.getElementById(location.hash.slice(1));if(!target)return;target.open=true;target.focus({preventScroll:true});target.scrollIntoView({behavior:"smooth",block:"start"});};
  document.addEventListener("click",event=>{if(event.target.closest("[data-provenance-trigger]"))setTimeout(reveal,0);});
  addEventListener("hashchange",reveal);reveal();
})();
</script>
""".strip()


def provenance_block(payload: dict[str, dict[str, object]]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    serialized = serialized.replace("<", "\\u003c")
    return (
        START
        + '\n<script type="application/json" id="result-provenance">'
        + serialized
        + "</script>\n"
        + INTERACTION
        + "\n"
        + END
    )


def update_report(report: Path, ledger: Path, plan: Path) -> int:
    payload = provenance_payload(ledger, plan)
    source = linkify_values(report.read_text(encoding="utf-8"), payload)
    block = provenance_block(payload)
    if START in source and END in source:
        source = re.sub(
            re.escape(START) + r".*?" + re.escape(END),
            lambda _match: block,
            source,
            flags=re.S,
        )
    elif "</body>" in source:
        source = source.replace("</body>", block + "\n</body>", 1)
    else:
        source += "\n" + block + "\n"
    report.write_text(source, encoding="utf-8")
    return len(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=Path("code/RESULTS_LEDGER.csv"))
    parser.add_argument("--plan", type=Path, default=Path("reports/04_RUN_PLAN.html"))
    parser.add_argument("--report", type=Path, default=Path("reports/05_EXP_RESULT.html"))
    args = parser.parse_args()
    count = update_report(args.report, args.ledger, args.plan)
    print(json.dumps({"status": "PASS", "clickable_results": count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
