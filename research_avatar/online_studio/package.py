"""Build the bounded evidence ZIP accepted by Online Paper Studio."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


OPTIONAL_FILES = (
    "code/RESULTS_LEDGER.csv",
    "reports/01_LIT_SURVEY.html",
    "reports/04_RUN_PLAN.html",
)


def build_archive(root: Path, output: Path) -> list[str]:
    root = root.resolve()
    required = (
        root / "results",
        root / "researcher-profile/publications.json",
        root / "researcher-profile/fulltext",
    )
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required evidence: " + ", ".join(missing))
    files = [path for path in (root / "results").rglob("*") if path.is_file()]
    figures = root / "figures"
    if figures.is_dir():
        files.extend(path for path in figures.rglob("*") if path.is_file())
    files.append(root / "researcher-profile/publications.json")
    files.extend(path for path in (root / "researcher-profile/fulltext").rglob("*") if path.is_file())
    files.extend(root / value for value in OPTIONAL_FILES if (root / value).is_file())
    if not any(path.is_file() for path in (root / "results").rglob("*")):
        raise SystemExit("results/ is empty")
    if not any(path.suffix.lower() == ".txt" for path in (root / "researcher-profile/fulltext").rglob("*")):
        raise SystemExit("researcher-profile/fulltext/ has no extracted .txt reference")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path, path.relative_to(root).as_posix())
    return [path.relative_to(root).as_posix() for path in sorted(set(files))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("paper-studio-evidence.zip"))
    args = parser.parse_args()
    files = build_archive(args.root, args.output)
    print(f"Created {args.output.resolve()} with {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
