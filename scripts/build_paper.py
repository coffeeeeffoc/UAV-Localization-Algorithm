#!/usr/bin/env python3
"""Export both reviewed manuscript sources with Pandoc; no cloud write involved."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formats", nargs="+", choices=("pdf", "docx", "html"),
                        default=["pdf", "docx"])
    args = parser.parse_args()
    if not shutil.which("pandoc"):
        raise SystemExit("Install Pandoc 3.1+ to export manuscripts.")
    if "pdf" in args.formats and not shutil.which("xelatex"):
        raise SystemExit("PDF export requires XeLaTeX and Noto Serif CJK SC fonts.")
    output = ROOT / "paper" / "exports"
    output.mkdir(parents=True, exist_ok=True)
    logs = []
    produced = []
    for language, locale in (("en", "en-US"), ("zh", "zh-CN")):
        source = ROOT / "paper" / language / "manuscript.md"
        for fmt in args.formats:
            dest = output / f"manuscript-{language}.{fmt}"
            cmd = ["pandoc", str(source), "--standalone", "--citeproc",
                   "--data-dir", str(ROOT / "paper/pandoc"),
                   "--bibliography", str(ROOT / "paper" / "references.bib"),
                   "--resource-path", ".:paper:paper/en:paper/zh:experiments/results/reference",
                   "--metadata", f"lang={locale}", "--output", str(dest)]
            if fmt == "pdf":
                cmd += ["--pdf-engine=xelatex", "-V", "geometry:margin=25mm",
                        "-V", "papersize:a4",
                        "-V", "fontsize:11pt", "-V", "mainfont:Noto Serif",
                        "-V", "CJKmainfont:Noto Serif CJK SC", "-V", "colorlinks:true"]
            if fmt == "html":
                cmd += ["--mathml"]
            result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
            logs.append(f"{language}/{fmt}: exit={result.returncode}\n{result.stdout}{result.stderr}")
            (output / "build-log.txt").write_text("\n".join(logs), encoding="utf-8")
            if result.returncode:
                raise SystemExit(f"Failed to build {dest.name}; see paper/exports/build-log.txt")
            if "citation" in result.stderr.lower() and "not found" in result.stderr.lower():
                raise SystemExit(f"Unresolved citation in {source}; see build log.")
            produced.append(dest)
            print(dest.relative_to(ROOT))
    sources = [ROOT / "paper" / language / "manuscript.md" for language in ("en", "zh")]
    sources += [ROOT / "paper/references.bib", Path(__file__).resolve()]
    sources += sorted(p for p in (ROOT / "paper/pandoc").rglob("*") if p.is_file())
    sources += sorted((ROOT / "experiments/results/reference").glob("*.png"))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "pandoc": subprocess.check_output(["pandoc", "--version"], text=True).splitlines()[0],
        "xelatex": (subprocess.check_output(["xelatex", "--version"], text=True).splitlines()[0]
                    if "pdf" in args.formats else None),
        "formats": args.formats,
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "artifacts": {p.name: digest(p) for p in produced},
    }
    (output / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
