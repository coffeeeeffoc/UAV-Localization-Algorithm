# Complete synthetic reference measurement archive

This archive retains all 40 scenario/seed measurement datasets from the frozen reference evaluation. Every array-content SHA-256 was checked against the original reference data manifest before writing. No filter was rerun or retuned to create this archive. These are synthetic measurements, not real flights.

The initial experiment retained representative measurements under `../reference/`; this supplemental archive supplies every evaluation seed. The original experiment configuration and evidence remain unchanged.

The array dictionary is documented in `../../README.md`; load files with `numpy.load(path, allow_pickle=False)`. Generator parameters and sensor metadata are in the frozen `experiments/results/reference/config.resolved.json` and `data/synthetic/reference/manifest.json` at the repository root.

Reproduce in a new location with `python scripts/materialize_reference_data.py --output /tmp/uav-reference-full`, then run `python scripts/verify_artifacts.py /tmp/uav-reference-full/manifest.json --check-source`.
