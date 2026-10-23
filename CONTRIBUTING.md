# Working on this research

Read `docs/research-integrity.md` before changing claims or experiments. Preserve
the originals under `sources/original/`. Update the English paper first and the
Chinese translation in the same change. Bibliographic facts must be verified
against an identifiable source; distinguish metadata inspection from full-text
review.

Keep sensor units, coordinate frames, quaternion order, random seeds, and missing
measurement conventions explicit. A change to dynamics, Jacobians, stochastic
models, or cryptographic state needs a meaningful test. Never commit real keys,
tokens, or environment files. Do not fit parameters to the evaluation seeds.

Store small, reproducible reference artifacts with their provenance. Large raw
datasets should use documented retrieval instructions and content hashes (or Git
LFS when deliberately configured), rather than arbitrary binary commits. Check
the dataset license before redistributing third-party data.

Before a push, run the unit tests, a smoke experiment, the artifact integrity
check, and manuscript exports relevant to the change. Report limitations with
the same precision as successful results.
