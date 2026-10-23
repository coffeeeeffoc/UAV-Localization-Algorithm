#!/usr/bin/env python3
"""Run paired, reproducible *synthetic* UWB/IMU experiments.

Run from the repository root: python scripts/run_experiments.py --config
configs/reference.json. Configuration is resolved before any evaluation data are
generated. No parameter selection is performed in this program.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import gzip
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import t as student_t

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uav_localization.estimation import FilterConfig, METHODS, run_estimator  # noqa: E402
from uav_localization.simulation import SimulationConfig, simulate  # noqa: E402


def jsonable(value):
    if dataclasses.is_dataclass(value):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    return value


def dump_json(path, value):
    path.write_text(json.dumps(jsonable(value), indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(arrays):
    """Hash array names, dtypes, shapes and bytes, independent of ZIP encoding."""
    digest = hashlib.sha256()
    for name, array in sorted(arrays.items()):
        value = np.ascontiguousarray(array)
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(str(value.dtype).encode("ascii") + b"\0")
        digest.update(json.dumps(value.shape).encode("ascii") + b"\0")
        digest.update(value.tobytes())
    return digest.hexdigest()


def dataset_arrays(dataset):
    return {
        "t_s": dataset.t,
        "truth_position_m": dataset.position,
        "truth_velocity_mps": dataset.velocity,
        "truth_quaternion_xyzw": dataset.quaternion,
        "accel_body_mps2": dataset.accel,
        "gyro_body_radps": dataset.gyro,
        "ranges_m": dataset.ranges,
        "anchors_m": dataset.anchors,
        "nlos_mask": dataset.nlos_mask,
        "initial_position_m": dataset.initial_position,
        "initial_velocity_mps": dataset.initial_velocity,
        "initial_quaternion_xyzw": dataset.initial_quaternion,
    }


def metrics(truth, estimate, mask):
    finite = np.all(np.isfinite(estimate), axis=1)
    valid = mask & finite
    count = int(np.count_nonzero(valid))
    denominator = int(np.count_nonzero(mask))
    error = np.linalg.norm(estimate[valid] - truth[valid], axis=1)
    return {
        "n_evaluated": count,
        "n_possible": denominator,
        "availability": count / denominator if denominator else None,
        "rmse_m": float(np.sqrt(np.mean(error ** 2))) if count else None,
        "p95_m": float(np.quantile(error, 0.95)) if count else None,
        "max_m": float(np.max(error)) if count else None,
    }


def mean_ci(values):
    """Student-t interval over independent simulation seeds, not timesteps."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n == 0:
        return {"n_seeds": 0, "mean": None, "sd": None, "ci95_low": None,
                "ci95_high": None}
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1)) if n > 1 else None
    half = float(student_t.ppf(0.975, n - 1) * sd / math.sqrt(n)) if n > 1 else None
    return {"n_seeds": n, "mean": mean, "sd": sd,
            "ci95_low": mean - half if half is not None else None,
            "ci95_high": mean + half if half is not None else None}


def csv_write(path, rows):
    if not rows:
        raise ValueError(f"Refusing to write empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def diagnostics_write(path, estimates):
    """Keep full representative estimator diagnostics in deterministic gzip."""
    import io
    rows = [{"method": method, **row} for method, estimate in estimates.items()
            for row in estimate.diagnostics]
    fields = ["method"] + sorted({name for row in rows for name in row} - {"method"})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(gzip.compress(stream.getvalue().encode("utf-8"), mtime=0))


def aggregate(rows):
    groups = sorted({(r["scenario"], r["method"], r["grid"]) for r in rows})
    results = []
    for scenario, method, grid in groups:
        selected = [r for r in rows if (r["scenario"], r["method"], r["grid"]) ==
                    (scenario, method, grid)]
        for metric in ("rmse_m", "p95_m", "max_m", "availability"):
            values = [r[metric] for r in selected if r[metric] is not None]
            results.append({"scenario": scenario, "method": method, "grid": grid,
                            "metric": metric, **mean_ci(values)})
    return results


def paired_comparisons(rows, methods):
    results = []
    # The full estimator versus fixed ESKF and each single-component ablation.
    if "robust_eskf" not in methods:
        return results
    for scenario in sorted({r["scenario"] for r in rows}):
        selected = [r for r in rows if r["scenario"] == scenario and
                    r["grid"] == "common_observed_uwb"]
        proposed = {r["seed"]: r["rmse_m"] for r in selected
                    if r["method"] == "robust_eskf"}
        for baseline in ("uwb", "ins", "eskf", "gated_eskf", "adaptive_eskf"):
            if baseline not in methods:
                continue
            other = {r["seed"]: r["rmse_m"] for r in selected
                     if r["method"] == baseline}
            differences = [proposed[s] - other[s] for s in sorted(proposed.keys() & other.keys())
                           if proposed[s] is not None and other[s] is not None]
            results.append({"scenario": scenario, "method": "robust_eskf",
                            "baseline": baseline, "metric": "paired_rmse_difference_m",
                            "grid": "common_observed_uwb", **mean_ci(differences)})
    return results


def figures(representatives, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    count = len(representatives)
    columns = min(2, count)
    rows = math.ceil(count / columns)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 170})
    fig_xy, axes_xy = plt.subplots(rows, columns, figsize=(7 * columns, 4 * rows), squeeze=False)
    fig_error, axes_error = plt.subplots(rows, columns, figsize=(7 * columns, 4 * rows), squeeze=False)
    labels = {"uwb": "UWB least squares", "ins": "INS only", "eskf": "Fixed ESKF",
              "gated_eskf": "Gated ESKF", "adaptive_eskf": "Inflated-R ESKF",
              "robust_eskf": "Gated + inflated-R ESKF"}
    for index, (scenario, dataset, estimates) in enumerate(representatives):
        xy = axes_xy.flat[index]
        err = axes_error.flat[index]
        xy.plot(dataset.position[:, 0], dataset.position[:, 1], "k--", label="Ground truth", lw=1.7)
        xy.scatter(dataset.anchors[:, 0], dataset.anchors[:, 1], marker="^", color="gray", s=24,
                   label="UWB anchors (XY projection)")
        for method, estimate in estimates.items():
            if method in ("eskf", "robust_eskf", "uwb"):
                valid = np.all(np.isfinite(estimate.position), axis=1)
                xy.plot(estimate.position[valid, 0], estimate.position[valid, 1],
                        "." if method == "uwb" else "-", label=labels[method],
                        lw=1, markersize=2, alpha=0.8)
            error = np.linalg.norm(estimate.position - dataset.position, axis=1)
            err.semilogy(dataset.t, np.maximum(error, 1e-6),
                         "." if method == "uwb" else "-", label=labels.get(method, method),
                         lw=1, markersize=2, alpha=0.8)
        seed = dataset.metadata.get("seed", "first evaluation seed")
        for ax in (xy, err):
            ax.set_title(f"{scenario.upper()} — synthetic, seed {seed}")
            ax.grid(alpha=0.25)
        xy.set(xlabel="East / x (m)", ylabel="North / y (m)")
        xy.set_aspect("equal", adjustable="datalim")
        err.set(xlabel="Time (s)", ylabel="3D position error (m; log scale)")
        xy.legend(fontsize=7)
        err.legend(fontsize=7)
    for ax in list(axes_xy.flat)[count:] + list(axes_error.flat)[count:]:
        ax.set_visible(False)
    for fig, name in ((fig_xy, "trajectories_xy"), (fig_error, "position_errors")):
        fig.tight_layout()
        fig.savefig(output / f"{name}.png")
        fig.savefig(output / f"{name}.pdf")
        plt.close(fig)


def summary_markdown(path, summary, comparisons, config):
    lines = ["# Synthetic experiment report", "",
             "These are generated simulation results, not real UAV flight measurements.", "",
             f"Evaluation seeds: `{config['evaluation_seeds']}`. "
             "No fitting or parameter search is performed by this run.", "",
             "## Position RMSE at common observed UWB epochs", "",
             "Each value is the mean of per-seed RMSEs (metres); uncertainty is a two-sided "
             "95% Student-t interval across seeds. Common epochs have at least four observed "
             "ranges and finite outputs from every included method. This conditional comparison "
             "does not measure dropout continuity; see dense-grid availability and errors in CSV.", "",
             "| Scenario | Method | Seeds | Mean RMSE (m) | 95% CI (m) |",
             "|---|---|---:|---:|---:|"]
    for row in summary:
        if row["grid"] == "common_observed_uwb" and row["metric"] == "rmse_m":
            mean = f"{row['mean']:.4f}" if row["mean"] is not None else "NA"
            ci = (f"[{row['ci95_low']:.4f}, {row['ci95_high']:.4f}]"
                  if row["ci95_low"] is not None else "Not estimable")
            lines.append(f"| {row['scenario']} | {row['method']} | {row['n_seeds']} | {mean} | {ci} |")
    lines += ["", "## Paired differences", "",
              "Negative values favour `robust_eskf`. Intervals are exploratory and unadjusted "
              "for multiple comparisons; do not treat interval exclusion as a confirmatory test.", "",
              "| Scenario | Baseline | Mean difference (m) | 95% CI (m) |",
              "|---|---|---:|---:|"]
    for row in comparisons:
        mean = f"{row['mean']:.4f}" if row["mean"] is not None else "NA"
        ci = (f"[{row['ci95_low']:.4f}, {row['ci95_high']:.4f}]"
              if row["ci95_low"] is not None else "Not estimable")
        lines.append(f"| {row['scenario']} | {row['baseline']} | {mean} | {ci} |")
    lines += ["", "## Interpretation limits", "",
              "Seeds vary synthetic noise and biases, not environments or independent flights. "
              "Intervals describe this simulator and configuration only. Gate thresholds, "
              "initialization and geometry require independent real-data evaluation. "
              "Per-run runtime is a host wall-clock diagnostic, not a real-time flight guarantee.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Override result directory")
    parser.add_argument("--data-output", type=Path, help="Override saved synthetic dataset directory")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    seeds = config["evaluation_seeds"]
    calibration = config.get("calibration_seeds", [])
    if not seeds or len(set(seeds)) != len(seeds) or set(seeds) & set(calibration):
        raise ValueError("Evaluation seeds must be nonempty, unique and disjoint from calibration seeds")
    if any(type(seed) is not int or seed < 0 for seed in seeds + calibration):
        raise ValueError("Seeds must be nonnegative integers")
    methods = config.get("methods", list(METHODS))
    scenarios = config.get("scenarios", ["los", "nlos", "dropout", "combined"])
    if not methods or len(set(methods)) != len(methods) or set(methods) - set(METHODS):
        raise ValueError("Invalid or duplicated estimator methods")
    if not scenarios or len(set(scenarios)) != len(scenarios) or set(scenarios) - {"los", "nlos", "dropout", "combined"}:
        raise ValueError("Invalid or duplicated scenarios")
    simulation_config = SimulationConfig(**config.get("simulation", {}))
    filter_config = FilterConfig(**config.get("filter", {}))
    output = (args.output or ROOT / config["output_directory"]).resolve()
    data_output = (args.data_output or ROOT / config["data_directory"]).resolve()
    for directory in (output, data_output):
        if directory.exists() and any(directory.iterdir()):
            raise FileExistsError(f"Refusing to overwrite nonempty evidence directory: {directory}")
    output.mkdir(parents=True, exist_ok=True)
    data_output.mkdir(parents=True, exist_ok=True)
    resolved = {**config, "simulation": jsonable(simulation_config), "filter": jsonable(filter_config)}
    dump_json(output / "config.resolved.json", resolved)
    (output / "config.requested.json").write_bytes(config_path.read_bytes())
    start = datetime.now(timezone.utc).isoformat()
    rows, datasets, representatives = [], [], []
    save_policy = config.get("save_datasets", "representative")
    if save_policy not in ("all", "representative", "none"):
        raise ValueError("save_datasets must be all, representative or none")
    source_files = [ROOT / "src" / "uav_localization" / name for name in
                    ("__init__.py", "estimation.py", "simulation.py", "geometry.py")]
    source_files.append(Path(__file__).resolve())
    source_hashes = {str(p.relative_to(ROOT)): sha256(p) for p in source_files}
    for scenario in scenarios:
        for seed in seeds:
            dataset = simulate(simulation_config, seed=seed, scenario=scenario)
            arrays = dataset_arrays(dataset)
            record = {"scenario": scenario, "seed": seed, "status": "synthetic",
                      "array_sha256": content_hash(arrays), "metadata": jsonable(dataset.metadata),
                      "retained": save_policy == "all" or (save_policy == "representative" and seed == seeds[0])}
            if record["retained"]:
                filename = f"{scenario}_seed{seed}.npz"
                np.savez_compressed(data_output / filename, **arrays)
                record.update(file=filename, file_sha256=sha256(data_output / filename),
                              bytes=(data_output / filename).stat().st_size)
            datasets.append(record)
            estimates, runtimes = {}, {}
            for method in methods:
                started = time.perf_counter()
                estimates[method] = run_estimator(dataset, method, filter_config)
                runtimes[method] = time.perf_counter() - started
                print(f"{scenario} seed={seed} method={method} seconds={runtimes[method]:.3f}", flush=True)
            dense = np.ones(len(dataset.t), dtype=bool)
            observed = np.sum(np.isfinite(dataset.ranges), axis=1) >= 4
            common = observed.copy()
            for estimate in estimates.values():
                if not np.array_equal(estimate.t, dataset.t):
                    raise ValueError("Estimator output timestamps differ from generated dataset")
                common &= np.all(np.isfinite(estimate.position), axis=1)
            for method, estimate in estimates.items():
                for grid, mask in (("dense", dense), ("observed_uwb", observed),
                                   ("common_observed_uwb", common)):
                    rows.append({"scenario": scenario, "seed": seed, "method": method,
                                 "grid": grid, **metrics(dataset.position, estimate.position, mask),
                                 "n_candidate_uwb_epochs": int(np.count_nonzero(observed)),
                                 "n_common_epochs": int(np.count_nonzero(common)),
                                 "runtime_s": runtimes[method]})
            if seed == seeds[0]:
                representatives.append((scenario, dataset, estimates))
                # Retain representative predictions as well as measurements to audit figures.
                prediction = {"t_s": dataset.t}
                for method, estimate in estimates.items():
                    prediction[f"{method}_position_m"] = estimate.position
                    prediction[f"{method}_position_covariance_m2"] = estimate.position_covariance
                np.savez_compressed(output / f"predictions_{scenario}_seed{seed}.npz", **prediction)
                diagnostics_write(output / f"diagnostics_{scenario}_seed{seed}.csv.gz", estimates)
    summary = aggregate(rows)
    comparisons = paired_comparisons(rows, methods)
    csv_write(output / "per_run_metrics.csv", rows)
    csv_write(output / "summary_metrics.csv", summary)
    if comparisons:
        csv_write(output / "paired_comparisons.csv", comparisons)
    dump_json(output / "summary.json", {"evidence_type": "synthetic_simulation",
                                        "summary": summary, "paired_comparisons": comparisons})
    dump_json(data_output / "manifest.json", {"evidence_type": "synthetic_simulation",
                                              "save_policy": save_policy,
                                              "datasets": datasets})
    figures(representatives, output)
    summary_markdown(output / "report.md", summary, comparisons, resolved)
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        git_dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        git_commit, git_dirty = None, None
    versions = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "matplotlib")}
    # Paths are relative to manifest parent; manifests are portable after cloning.
    import os
    artifact_files = sorted(p for folder in (output, data_output) for p in folder.iterdir() if p.is_file())
    manifest = {"evidence_type": "synthetic_simulation", "started_utc": start,
                "finished_utc": datetime.now(timezone.utc).isoformat(),
                "python": sys.version, "platform": platform.platform(), "versions": versions,
                "git_commit_at_execution": git_commit, "working_tree_dirty_at_execution": git_dirty,
                "source_sha256": source_hashes, "requested_config_sha256": sha256(config_path),
                "seed_policy": "Calibration seeds reserved; no training/tuning performed by runner. Evaluation seeds paired across all methods.",
                "uncertainty": "Two-sided Student-t intervals over independent seed-level metrics/differences; exploratory, no multiplicity correction.",
                "artifacts": {os.path.relpath(p, output): sha256(p) for p in artifact_files}}
    dump_json(output / "manifest.json", manifest)
    print(f"Completed synthetic experiment: {output}", flush=True)


if __name__ == "__main__":
    main()
