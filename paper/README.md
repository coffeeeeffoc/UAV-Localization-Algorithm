# Manuscripts

- [`en/manuscript.md`](en/manuscript.md): authoritative English research draft.
- [`zh/manuscript.md`](zh/manuscript.md): corresponding Chinese translation.
- [`references.bib`](references.bib): curated references; inspection records are
  in [`../literature/`](../literature/).
- `exports/`: generated PDF and editable Word versions, plus build diagnostics.

Run from the repository root:

```sh
python scripts/build_paper.py
# Optional standalone HTML with embedded MathML:
python scripts/build_paper.py --formats html
```

Exports require Pandoc 3.1+; PDF additionally requires XeLaTeX, Noto Serif and
Noto Serif CJK SC. On Debian/Ubuntu the relevant packages include `pandoc`,
`texlive-xetex`, `texlive-lang-cjk` (including xeCJK), `texlive-lang-chinese`,
`fonts-noto-core`, and `fonts-noto-cjk`.
The Python runtime dependency lock does not install this document toolchain.

The current manuscript is an executable research draft, not a completed
submission. All reported numerical localization results must be explicitly
identified as synthetic. Authorship, affiliations and a target venue are not
invented. See the research plan and publication gates before submission.
