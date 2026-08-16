#!/usr/bin/env python3
import json
from decimal import Decimal
from pathlib import Path

root = Path(__file__).resolve().parents[2]
result = json.loads((root / "results/typo_margin/confirmatory_results.json").read_text())
primary = result["cases"]["primary-50"]
assert primary["budget"]["selection_balance"] == "equal per intent class"
assert primary["budget"]["selected_per_seed"] == 1250
assert primary["budget"]["full_mixture_per_seed"] == 5000
for case in result["cases"].values():
    assert Decimal(str(case["inference"]["margin_vs_random_noisy_mean"]["bootstrap_95_ci"][0])) > 0
noninferiority_lcb = Decimal(str(primary["inference"]["margin_vs_full_noisy_mean"]["bootstrap_95_ci"][0]))
assert noninferiority_lcb > Decimal("-0.01")
print(json.dumps({"checks": [{"id": "C2", "passed": True, "method": "numeric", "residual": float(noninferiority_lcb - Decimal("-0.01"))}]}))
