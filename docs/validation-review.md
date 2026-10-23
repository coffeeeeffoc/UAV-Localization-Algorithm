# Independent implementation review

Review date: 2026-10-23. The implementation freeze used for the reference
experiment is commit `4686451`. This review records software and synthetic-data
checks; it is not a theoretical convergence proof, cryptographic audit, or
physical-flight validation.

## Findings and resolution

The initial simulator accepted integer-valued bias vectors such as `(0, 0, 0)`
but allocated integer arrays before adding floating-point random-walk increments.
This caused a NumPy casting exception, including when the configured random-walk
amplitude was zero. The arrays now explicitly use floating-point dtype. The
noise-free trajectory test exercises this configuration and passed after the
fix. No parameter changes were made in response to measured estimator accuracy.

No remaining blocking issue was identified in the reviewed estimator, simulator,
telemetry protocol, or smoke-experiment statistics. This is a bounded review,
not a claim that arbitrary inputs or operating conditions have been verified.

## Checks performed

| Check | Observed outcome |
|---|---|
| Estimator and simulation unit tests | All 14 passed after the dtype fix |
| Telemetry security unit tests | All 13 passed |
| Independent finite-difference check of the attitude reset right Jacobian | Maximum absolute difference approximately `3.23e-10` for a nonzero rotation vector |
| Two-second noiseless inertial propagation with zero biases and exact initial state | Maximum position error approximately `1.63e-6` m; maximum rotation error approximately `6.44e-16` rad |
| Additional 30-second robust-filter runs, seed 111, all four scenarios | Final covariance symmetric; minimum eigenvalue approximately `2.16e-9` in each scenario |
| Smoke manifest integrity | 18 artifacts and 5 source-file hashes verified |
| Independent recomputation from retained smoke NPZ data and predictions | Seed 200 common-epoch RMSE matched the CSV for all six methods in LOS and combined scenarios to within `1e-12` m; 41 and 31 common epochs respectively |
| Estimator information boundary | Estimator uses supplied initial estimates and measurements; no subsequent true states or simulated NLOS labels enter its updates |

Seed 111 and the noiseless runs were diagnostic checks, not additions to the
reference evaluation sample. Their values must not be pooled into the paper's
Monte Carlo tables. The smoke runs test integration and evidence recording,
not a claim of comparative performance.

The checked commands include:

```sh
python -m unittest discover -s tests -p 'test_estimation.py' -v
python -m unittest discover -s tests -p 'test_security.py' -v
python scripts/verify_artifacts.py experiments/results/smoke/manifest.json --check-source
```

The independent metric calculation reads `truth_position_m` and `ranges_m` from
the retained dataset, and each method's position array from the corresponding
prediction NPZ. Its common mask requires at least four observed ranges and a
finite position from every method. For each method it computes
`sqrt(mean(sum((estimate - truth)**2, axis=1)))` on that mask and compares the
value with `per_run_metrics.csv`. This checks the recorded metrics without
calling the runner's metric function.

The zero-noise check uses `SimulationConfig(duration_s=2)` with acceleration and
gyroscope sample noise, both bias random walks, both constant biases, and all
initial errors set to zero, followed by `run_estimator(dataset, "ins")`.
The covariance diagnostic uses the unmodified defaults with `seed=111` and
`method="robust_eskf"` for `los`, `nlos`, `dropout`, and `combined`.

## Interpretation and approximation boundaries

- The right-multiplicative attitude convention, range Jacobian, Joseph update,
  and right-Jacobian covariance reset are consistent across the reviewed code
  and English manuscript.
- Nominal integration uses a midpoint orientation. Covariance propagation uses
  a frozen continuous-time error matrix and a second-order transition, together
  with a declared discrete noise map. It omits some within-step coupled noise
  terms and is **not** an exact stochastic discretization. The manuscript states
  this approximation; sample-rate sensitivity and statistical consistency remain
  open evaluations.
- The simulator distinguishes per-sample IMU white-noise standard deviations from
  bias random-walk amplitudes per square root of time. Its warm start and simplified
  sensor model limit the conclusions to the configured synthetic setting.
- In the combined robust method, gating occurs before variance inflation. With
  the default thresholds, accepted updates have a variance multiplier no larger
  than approximately 2.82. The configured cap of 25 can be reached by the
  inflation-only ablation, not an accepted combined update with those defaults.
- Seed-level confidence intervals and paired comparisons avoid counting
  correlated trajectory samples as independent experiments. Common-epoch errors
  are conditional on available outputs; dense-grid availability must accompany
  them when discussing outages.
- Telemetry tests establish tested rejection/state-transition behavior. Security
  remains conditional on fresh per-session keys, unique nonces, one sender per
  unidirectional session, and trusted endpoints. Either endpoint restarting or
  rolling back state requires a fresh key/session. The strict replay policy
  rejects older out-of-order packets, and does not prove physical range truth.

Subsequent changes to the scientific implementation require appropriate tests
and new source hashes. Changes affecting generated evidence require a new run,
not retrospective edits to an existing result table.
