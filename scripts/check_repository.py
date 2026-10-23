#!/usr/bin/env python3
"""Check source provenance, evidence source hashes and bilingual citation keys."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check_hash(path: Path, expected: str) -> None:
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"Checksum mismatch: {path.relative_to(ROOT)}")


def main() -> None:
    sources = json.loads((ROOT / "sources/manifest.json").read_text())
    for source in sources["sources"]:
        check_hash(ROOT / source["path"], source["sha256"])
        check_hash(ROOT / source["extracted_path"], source["extracted_sha256"])
    for report in (ROOT / "results/security").glob("*.json"):
        data = json.loads(report.read_text())
        for filename, expected in data.get("source_sha256", {}).items():
            check_hash(ROOT / filename, expected)
    bibliography = (ROOT / "paper/references.bib").read_text()
    keys = set(re.findall(r"@\w+\{([^,]+),", bibliography))
    citations = {}
    for language in ("en", "zh"):
        path = ROOT / "paper" / language / "manuscript.md"
        citations[language] = set(re.findall(r"(?<!\w)@([A-Za-z][A-Za-z0-9_:-]*)", path.read_text()))
        missing = citations[language] - keys
        if missing:
            raise SystemExit(f"Unknown {language} citations: {sorted(missing)}")
    if citations["en"] != citations["zh"]:
        raise SystemExit("English and Chinese manuscripts have different citation sets")
    export_manifest = ROOT / "paper/exports/build-manifest.json"
    if export_manifest.is_file():
        data = json.loads(export_manifest.read_text())
        for filename, expected in data["source_sha256"].items():
            check_hash(ROOT / filename, expected)
        for filename, expected in data["artifacts"].items():
            check_hash(export_manifest.parent / filename, expected)
    print(f"Verified {len(sources['sources'])} source archives, security source hashes, "
          f"and {len(citations['en'])} shared manuscript citations.")


if __name__ == "__main__":
    main()
