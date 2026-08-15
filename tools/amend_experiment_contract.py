#!/usr/bin/env python3
"""Create a reviewable experiment-contract amendment without forging reapproval."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path


CONTRACT_RE = re.compile(
    r'(<script\b[^>]*id=["\']experiment-plan-contract["\'][^>]*>)(.*?)(</script>)',
    re.S | re.I,
)
APPROVAL_FIELDS = {
    "approval_status", "approved_at", "approval_channel", "approval_contract_sha256",
    "approval_contract_version",
}


def digest(contract: dict) -> str:
    unsigned = {key: value for key, value in contract.items() if key not in APPROVAL_FIELDS}
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def amend(contract: dict, *, reason: str, compatibility: str,
          changed_fields: list[str], changed_at: str) -> dict:
    if contract.get("approval_status") != "approved":
        raise ValueError("only an approved contract can be amended")
    approved_digest = str(contract.get("approval_contract_sha256", ""))
    if not approved_digest or approved_digest != digest(contract):
        raise ValueError("current approval digest is missing or stale")
    if not reason.strip() or not compatibility.strip() or not changed_fields:
        raise ValueError("reason, compatibility, and changed_fields are required")
    previous_version = int(contract.get("contract_version", 1))
    history = list(contract.get("revision_history") or [{
        "version": previous_version,
        "changed_at": str(contract.get("generated_at") or changed_at),
        "reason": "Migrated approved version",
        "changed_fields": ["*"],
        "compatibility": "legacy contract imported before schema 1.1",
    }])
    revised = json.loads(json.dumps(contract))
    revised.update({
        "schema_version": "1.1",
        "contract_version": previous_version + 1,
        "parent_approval_sha256": approved_digest,
        "approval_status": "pending",
        "revision_history": history + [{
            "version": previous_version + 1,
            "changed_at": changed_at,
            "reason": reason.strip(),
            "changed_fields": changed_fields,
            "compatibility": compatibility.strip(),
        }],
    })
    for field in APPROVAL_FIELDS - {"approval_status"}:
        revised.pop(field, None)
    return revised


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="reports/03_EXPERIMENT_PLAN.html")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--compatibility", required=True)
    parser.add_argument("--changed-field", action="append", required=True)
    parser.add_argument("--date", default=dt.date.today().isoformat())
    args = parser.parse_args()
    path = Path(args.plan)
    source = path.read_text(encoding="utf-8")
    match = CONTRACT_RE.search(source)
    if not match:
        raise SystemExit("missing experiment-plan-contract")
    contract = json.loads(match.group(2))
    revised = amend(
        contract, reason=args.reason, compatibility=args.compatibility,
        changed_fields=args.changed_field, changed_at=args.date,
    )
    replacement = match.group(1) + json.dumps(revised, ensure_ascii=False, separators=(",", ":")) + match.group(3)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(source[:match.start()] + replacement + source[match.end():], encoding="utf-8")
    temporary.replace(path)
    print(json.dumps({"status": "pending_reapproval", "contract_version": revised["contract_version"],
                      "parent_approval_sha256": revised["parent_approval_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
