"""Build the bounded evidence ZIP accepted by Online Paper Studio."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


REPORT_FILES = (
    "reports/01_LIT_SURVEY.html",
    "reports/02_IDEA_REPORT.html",
    "reports/03_EXPERIMENT_PLAN.html",
    "reports/04_RUN_PLAN.html",
    "reports/05_EXP_RESULT.html",
)
OPTIONAL_FILES = (
    "code/RESULTS_LEDGER.csv",
)


def _plan_contract(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    match = re.search(
        r'<script\b[^>]*\bid=["\']experiment-plan-contract["\'][^>]*>(.*?)</script>',
        source,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise SystemExit("reports/03_EXPERIMENT_PLAN.html has no experiment-plan-contract")
    try:
        contract = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise SystemExit("reports/03_EXPERIMENT_PLAN.html has invalid contract JSON") from exc
    if contract.get("approval_status") != "approved":
        raise SystemExit("reports/03_EXPERIMENT_PLAN.html is not approved")
    return contract


def _selected_references(root: Path, contract: dict) -> list[tuple[Path, str]]:
    references = contract.get("references") if isinstance(contract.get("references"), dict) else {}
    selected: list[tuple[Path, str]] = []
    for role, archive_name in (
        ("researcher_owned_structure", "references/structure.txt"),
        ("external_mechanism", "references/mechanism.txt"),
    ):
        record = references.get(role) if isinstance(references.get(role), dict) else {}
        value = str(record.get("local_full_text") or "").strip()
        if not value:
            if role == "researcher_owned_structure":
                raise SystemExit("03 contract does not name a researcher-owned structural reference")
            continue
        path = (root / value).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise SystemExit(f"Selected reference leaves project root: {value}") from exc
        if not path.is_file() or path.suffix.lower() != ".txt":
            raise SystemExit(f"Selected reference is missing: {value}")
        selected.append((path, archive_name))
    return selected


def _contract_file(root: Path, value: str, *, role: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"{role} leaves project root: {value}") from exc
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Missing {role}: {value}")
    return path


def _selected_result_files(root: Path, contract: dict) -> list[Path]:
    """Package only result files selected by the approved claim contract."""
    selected: set[Path] = set()
    for requirement in contract.get("result_requirements", []):
        if not isinstance(requirement, dict):
            continue
        for selector in requirement.get("any_of", []):
            file_name = str(selector).partition(":")[0].strip()
            if file_name.startswith("results/") and file_name.lower().endswith(".json"):
                selected.add(_contract_file(root, file_name, role="contract result"))
    if selected:
        return sorted(selected)
    return sorted(path for path in (root / "results").rglob("*") if path.is_file())


def _selected_plotting_files(root: Path, contract: dict) -> list[Path]:
    """Collect the exact plotting sources/assets required to validate approved 03."""
    selected: set[Path] = set()
    for artifact in contract.get("paper_artifacts", []):
        if not isinstance(artifact, dict):
            continue
        shell = artifact.get("shell") if isinstance(artifact.get("shell"), dict) else {}
        plotting = shell.get("plotting") if isinstance(shell.get("plotting"), dict) else {}
        for field in ("source", "schema", "fixture_generator", "fixture", "pdf", "png"):
            value = str(plotting.get(field) or "").strip()
            if value:
                selected.add(_contract_file(root, value, role=f"{artifact.get('id')} plotting {field}"))
        for panel in plotting.get("panels", {}).values():
            if not isinstance(panel, dict):
                continue
            for field in ("pdf", "png"):
                value = str(panel.get(field) or "").strip()
                if value:
                    selected.add(_contract_file(root, value, role=f"{artifact.get('id')} panel {field}"))
        source = str(plotting.get("source") or "").strip()
        if source:
            common = (root / source).resolve().with_name("_common.py")
            if common.is_file():
                selected.add(common)
    return sorted(selected)


def build_archive(root: Path, output: Path) -> list[str]:
    root = root.resolve()
    required = (root / "results", root / "researcher-profile/PROFILE.html", root / "researcher-profile/publications.json", *(root / value for value in REPORT_FILES))
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required evidence: " + ", ".join(missing))
    contract = _plan_contract(root / "reports/03_EXPERIMENT_PLAN.html")
    selected_references = _selected_references(root, contract)
    files = _selected_result_files(root, contract)
    files.extend(_selected_plotting_files(root, contract))
    # Keep each selected reference at its contract-declared project path for
    # approval validation, while also providing stable archive aliases consumed
    # by the online scaffold. This includes only the explicitly selected papers,
    # never the rest of researcher-profile/fulltext/.
    files.extend(path for path, _archive_name in selected_references)
    figures = root / "figures"
    if figures.is_dir():
        files.extend(path for path in figures.rglob("*") if path.is_file())
    files.extend((root / "researcher-profile/PROFILE.html", root / "researcher-profile/publications.json"))
    files.extend(root / value for value in REPORT_FILES)
    files.extend(root / value for value in OPTIONAL_FILES if (root / value).is_file())
    if not any(path.is_file() for path in files if "results" in path.relative_to(root).parts):
        raise SystemExit("results/ is empty")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    archive_names = [path.relative_to(root).as_posix() for path in sorted(set(files))]
    archive_names.extend(name for _path, name in selected_references)
    manifest = {
        "schema_version": "2.0",
        "kind": "research-avatar-paper-input",
        "files": {},
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            name = path.relative_to(root).as_posix()
            content = path.read_bytes()
            archive.writestr(name, content)
            manifest["files"][name] = hashlib.sha256(content).hexdigest()
        for path, name in selected_references:
            content = path.read_bytes()
            archive.writestr(name, content)
            manifest["files"][name] = hashlib.sha256(content).hexdigest()
        archive.writestr(
            "project-package.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
    return sorted([*archive_names, "project-package.json"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/paper-studio-evidence.zip"),
    )
    args = parser.parse_args()
    files = build_archive(args.root, args.output)
    print(f"Created {args.output.resolve()} with {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
