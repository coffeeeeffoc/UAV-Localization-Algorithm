#!/usr/bin/env python3
"""Check committed experiment artifacts against their SHA-256 manifest."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check-source", action="store_true", help="Also require current source hashes to match")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text())
    failures = []
    for name, expected in manifest["artifacts"].items():
        file = manifest_path.parent / name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            failures.append(f"artifact mismatch: {name}")
    if args.check_source:
        root = Path(__file__).resolve().parents[1]
        for name, expected in manifest["source_sha256"].items():
            file = root / name
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                failures.append(f"source mismatch: {name}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Verified {len(manifest['artifacts'])} artifacts" +
          (f" and {len(manifest['source_sha256'])} source files" if args.check_source else ""))


if __name__ == "__main__":
    main()
