# Experiment protocol and evidence

The reference study is a **synthetic, exploratory baseline**, not a real-flight
validation. All six estimators consume exactly the same generated measurements
within a scenario and seed. The runner never fits parameters or reads NLOS labels
to choose filter decisions. The analytic motion is kinematically consistent but
does not model quadrotor dynamics, radio propagation or synchronization errors.

Run from the repository root after installing the project dependencies:

```sh
python scripts/run_experiments.py --config configs/smoke.json
python scripts/run_experiments.py --config configs/reference.json
python scripts/verify_artifacts.py experiments/results/reference/manifest.json --check-source
```

Evidence directories are not overwritten. To reproduce an existing study without
changing the retained evidence, choose new directories:

```sh
python scripts/run_experiments.py --config configs/reference.json \
  --output /tmp/uav-reference-results --data-output /tmp/uav-reference-data
python scripts/verify_artifacts.py /tmp/uav-reference-results/manifest.json --check-source
```

## Fixed protocol

`configs/reference.json` specifies four scenarios (LOS, positive range-bias bursts,
complete UWB dropout, and both corruptions), ten independent random seeds
100–109, 30 seconds, 100 Hz IMU and 10 Hz UWB. Seeds 0–4 are reserved for future
calibration; no training or calibration has been performed in this version. The
initialization is deliberately a declared warm-start assumption: the simulator
adds fixed errors to the true initial state. It is not an experimentally validated
initializer. Every method uses the same initial state where applicable.

The tested methods are UWB nonlinear least squares, inertial propagation only,
fixed ESKF, hard-gated ESKF, bounded measurement-variance inflation, and both robust
components together. Thresholds are fixed before the evaluation run. The resolved
config records all defaults so that omitted values are still auditable.

## Metrics and comparison support

`per_run_metrics.csv` contains Euclidean 3D position RMSE, 95th-percentile error,
maximum error, count and availability for each seed, method and grid:

| Grid | Time support | Purpose |
|---|---|---|
| `dense` | Every simulator timestamp, including dropouts | Continuity/availability; error is conditional on finite outputs |
| `observed_uwb` | Timestamps with at least four observed ranges | Report each estimator's failures on comparable observation opportunities |
| `common_observed_uwb` | Observed UWB timestamps with finite outputs from **all** included methods | Paired accuracy comparison on identical timestamps |

UWB-only outputs are missing between range epochs and during dropouts; no held-last
position or interpolation is inserted. Its dense-grid RMSE therefore must not be
compared directly with dense ESKF or INS RMSE. The common-support comparison
excludes dropout intervals and is not a continuity claim. Both candidate and common
epoch counts are reported so that failure-dependent selection is visible. If any
method fails at many observation epochs, inspect `observed_uwb` availability before
interpreting common-support results.

Aggregates are means of seed-level metrics, not errors pooled over timestamps.
Two-sided 95% Student-t intervals use independent seeds as units. Paired comparisons
subtract each baseline's seed-level common-support RMSE from `robust_eskf` on the
same seed; negative differences favour the latter. These small-sample intervals
are exploratory, rely on a reasonable seed-level sampling approximation, and are
not corrected for multiple comparisons. Seeds sample noise and bias random walks
within one geometry/trajectory; they do not represent independent environments or
flights. No statistical significance or generalization claim is warranted.

Runtime is measured by host wall clock around each estimator run. It is a diagnostic
affected by hardware, load and libraries, not an embedded latency or real-time claim.

## Retained outputs

The result directory contains requested and fully resolved configs; per-run,
aggregate and paired CSV tables; `summary.json`; a generated report; XY trajectory
and 3D position-error figures; and representative predictions. The data directory
contains one compressed measurement dataset for the first evaluation seed of each
scenario, plus array-content hashes and metadata for **all** generated datasets.
The omitted measurement files can be regenerated from their config and seed;
`save_datasets: "all"` retains every generated dataset when storage permits.
The supplemental `data/synthetic/reference-full/` archive retains all 40 reference
measurement datasets. `scripts/materialize_reference_data.py` creates this archive
without rerunning any filter, checking every regenerated array hash against the
original dataset manifest. This storage addition leaves the frozen evaluation
configuration and original result manifest unchanged.

`manifest.json` records the UTC run interval, dependency versions, platform, source
SHA-256 values, Git commit at execution, whether the working tree was dirty, and
SHA-256 hashes of generated artifacts. The source hashes identify the executed code
even when a first-run experiment necessarily precedes its publication commit.
Neither runtime nor PDF/PNG metadata is expected to be byte-identical on a different
machine. Compare dataset array hashes and numerical tables with appropriate
floating-point tolerances; a matching artifact hash only establishes file integrity.

External recordings require separate data-specific adapters, calibration and split
protocols. In particular, UTIL TDOA measurements are range differences and cannot
be evaluated by substituting them into the current absolute-range measurement model.
