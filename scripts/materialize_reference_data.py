#!/usr/bin/env python3
"""Archive every reference measurement dataset after checking its recorded hash.

This materializes measurements only. It never reruns or changes an estimator,
selects parameters, or replaces the frozen reference experiment evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_experiments import content_hash, dataset_arrays, dump_json, sha256  # noqa: E402
from uav_localization.simulation import SimulationConfig, simulate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-results", type=Path,
                        default=ROOT / "experiments/results/reference")
    parser.add_argument("--source-data", type=Path, default=ROOT / "data/synthetic/reference")
    parser.add_argument("--output", type=Path, default=ROOT / "data/synthetic/reference-full")
    args = parser.parse_args()
    results, source_data, output = (p.resolve() for p in
                                    (args.reference_results, args.source_data, args.output))
    reference_manifest_path = results / "manifest.json"
    dataset_manifest_path = source_data / "manifest.json"
    reference = json.loads(reference_manifest_path.read_text(encoding="utf-8"))
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    config = json.loads((results / "config.resolved.json").read_text(encoding="utf-8"))
    # Protect the parent evidence before deriving an additional archive from it.
    for name, expected in reference["artifacts"].items():
        path = results / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Reference artifact failed integrity verification: {name}")
    if sha256(dataset_manifest_path) not in reference["artifacts"].values():
        raise ValueError("Source dataset manifest is not part of the frozen reference evidence")
    for name, expected in reference["source_sha256"].items():
        path = ROOT / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Current source differs from frozen reference source: {name}")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing archive: {output}")
    output.mkdir(parents=True, exist_ok=True)
    simulation = SimulationConfig(**config["simulation"])
    records = []
    start = datetime.now(timezone.utc).isoformat()
    for original in dataset_manifest["datasets"]:
        scenario, seed = original["scenario"], original["seed"]
        dataset = simulate(simulation, seed=seed, scenario=scenario)
        arrays = dataset_arrays(dataset)
        actual_hash = content_hash(arrays)
        if actual_hash != original["array_sha256"]:
            raise ValueError(f"Generated dataset differs from recorded reference: {scenario}/{seed}")
        filename = f"{scenario}_seed{seed}.npz"
        np.savez_compressed(output / filename, **arrays)
        records.append({"scenario": scenario, "seed": seed, "status": "synthetic",
                        "file": filename, "array_sha256": actual_hash,
                        "file_sha256": sha256(output / filename),
                        "bytes": (output / filename).stat().st_size,
                        "matches_reference_array_hash": True})
        print(f"Verified and archived {scenario} seed={seed}", flush=True)
    expected_pairs = {(scenario, seed) for scenario in config["scenarios"]
                      for seed in config["evaluation_seeds"]}
    actual_pairs = {(row["scenario"], row["seed"]) for row in records}
    if actual_pairs != expected_pairs or len(records) != len(expected_pairs):
        raise ValueError("Reference dataset manifest is incomplete or has duplicate records")
    (output / "README.md").write_text(
        "# Complete synthetic reference measurement archive\n\n"
        f"This archive retains all {len(records)} scenario/seed measurement datasets from "
        "the frozen reference evaluation. Every array-content SHA-256 was checked against "
        "the original reference data manifest before writing. No filter was rerun or "
        "retuned to create this archive. These are synthetic measurements, not real flights.\n\n"
        "The initial experiment retained representative measurements under "
        "`../reference/`; this supplemental archive supplies every evaluation seed. "
        "The original experiment configuration and evidence remain unchanged.\n\n"
        "The array dictionary is documented in `../../README.md`; load files with "
        "`numpy.load(path, allow_pickle=False)`. Generator parameters and sensor metadata "
        "are in the frozen `experiments/results/reference/config.resolved.json` and "
        "`data/synthetic/reference/manifest.json` at the repository root.\n\n"
        "Reproduce in a new location with `python scripts/materialize_reference_data.py "
        "--output /tmp/uav-reference-full`, then run `python scripts/verify_artifacts.py "
        "/tmp/uav-reference-full/manifest.json --check-source`.\n", encoding="utf-8")
    source_hashes = dict(reference["source_sha256"])
    source_hashes[str(Path(__file__).resolve().relative_to(ROOT))] = sha256(Path(__file__).resolve())
    manifest = {"evidence_type": "synthetic_simulation", "archive_kind": "complete_reference_measurements",
                "started_utc": start, "finished_utc": datetime.now(timezone.utc).isoformat(),
                "reference_results_manifest_sha256": sha256(reference_manifest_path),
                "reference_dataset_manifest_sha256": sha256(dataset_manifest_path),
                "reference_git_commit": reference["git_commit_at_execution"],
                "source_sha256": source_hashes, "datasets": records,
                "artifacts": {path.name: sha256(path) for path in sorted(output.iterdir()) if path.is_file()}}
    dump_json(output / "manifest.json", manifest)
    print(f"Archived and verified {len(records)} synthetic datasets: {output}", flush=True)


if __name__ == "__main__":
    main()
