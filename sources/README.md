# Author-supplied material

`original/` preserves the two documents supplied on 2026-10-23 without changes.
`manifest.json` maps their original filenames to stable repository paths and
records SHA-256 checksums. These unpublished documents establish the intended
research scope; their assertions are not experimental evidence.

`extracted/research-draft.md` was converted by Pandoc 3.1.11.1 and preserves the
36 Office Math objects as mathematical text. A paragraph-only DOCX extraction
would lose these equations. `extracted/thesis-proposal.txt` was extracted using
Antiword 0.37; layout, embedded objects, and some mathematical formatting may be
lost. The original files remain authoritative for transcription checks.

To regenerate the text, install Pandoc and Antiword, then run:

```sh
pandoc sources/original/research-draft.docx -t markdown -o sources/extracted/research-draft.md
antiword sources/original/thesis-proposal.doc > sources/extracted/thesis-proposal.txt
```

Changing extraction tools can change whitespace and checksums; record the new
tool version before updating the manifest. Do not edit the archived originals.
The proposal contains the author's identifying academic information. The source
documents do not grant a license to redistribute third-party publications.
