# Research plan and evidence gates

## Scope inherited from the proposal

The supplied master's proposal is titled **基于多源数据融合的安全室内无人机定位研究**. It contains two research lines: (1) UWB/INS localization with symmetric protection of sensitive data; and (2) UWB/vision localization, including an exploratory homomorphic-encryption idea. The supplied manuscript **研究内容一** develops the first line. This repository's first implementation and bilingual paper therefore address **research line 1 only**.

The English manuscript is the authoritative working version. The Chinese manuscript is a section-aligned translation, not an independent set of claims. A change to a mathematical convention, method, result, or limitation must be reflected in both versions.

The repository does not establish that the experiments described as completed in the supplied proposal actually took place. No raw real-flight sensor logs, calibration records, hardware inventory, ground-truth trajectories, or experimental analysis were supplied with the documents. Such statements are treated as claims requiring evidence. Original files should remain unchanged; corrections belong in the working manuscript and evidence ledger.

## Concrete research questions

1. Under the specified synthetic ranging-bias and outage model, how does a bounded innovation-based range update compare with fixed-covariance fusion, gate-only fusion, UWB-only multilateration, and inertial propagation?
2. What accuracy cost, if any, does the robust update introduce under line of sight? How does performance change during an outage and after measurements return?
3. How much does each component contribute? In particular, does covariance inflation improve on gating alone, and under what conditions does rejecting measurements cause drift?
4. Does the telemetry reference implementation reject altered and repeated messages under its stated session assumptions, and what host-side latency and byte overhead does it incur?

These questions are separate. Transport encryption does not lower ranging error, and a localization error metric does not measure cryptographic security.

## Current contribution and novelty boundary

The current deliverable is a reproducible research baseline: a three-dimensional error-state estimator, controlled synthetic data, comparators and ablations, an authenticated-telemetry reference implementation, source provenance, and bilingual manuscripts. Innovation gating, covariance adaptation, error-state filtering, and AES-GCM are established methods. Their combination is not by itself evidence of methodological novelty. A defensible submission must identify and test an advance beyond the closest existing approaches, or explicitly target a reproducibility/system-evaluation contribution acceptable to the chosen venue.

A possible subsequent contribution is a calibrated, observable model of correlated positive NLOS bias and recovery after outages, with decision thresholds validated on held-out trajectories. This is a research direction, not a feature or result claimed in the current implementation.

## Work packages and completion evidence

| Work package | Deliverable | Evidence required before it can be called complete |
|---|---|---|
| WP1: source audit | Unchanged source files, extraction notes, document hashes, corrected scope | Both documents traceable; unsupported original claims identified |
| WP2: estimator baseline | State conventions, propagation and range update, fixed and robust variants | Numerical Jacobian checks, inertial sanity checks, covariance checks, reproducible tests |
| WP3: synthetic study | Locked configuration, multiple seeds, full method/scenario table, diagnostics | Machine-readable per-run results and run provenance; failures retained; no ground-truth tuning on reported runs |
| WP4: telemetry protection | AES-GCM framing, replay policy, session assumptions, overhead report | Positive tests and tamper/replay/incorrect-key tests; no persisted operational keys |
| WP5: real-data adaptation | Dataset import, timing/extrinsic calibration, sensor-model mapping | Checksums, access/license record, verified units, timestamps and observation semantics |
| WP6: empirical comparison | Held-out real flights, sensitivity and ablations, closest available competitors | Frozen analysis plan, calibration/evaluation separation, confidence intervals, all exclusions justified |
| WP7: paper submission | English paper, faithful Chinese translation, source-verified references | Every numerical claim traceable to results; all remaining limitations stated; target-venue format and author review |

WP1–WP4 provide an initial executable artifact. WP5–WP7 are not implied to be complete by the existence of code or synthetic results. The dates in the original proposal are historical planning dates, not evidence that milestones were achieved. Update the schedule after hardware access and the target venue are established.

## Synthetic-study protocol

Freeze the scenario generator, geometry, estimator settings, output metrics and seeds in version control before the final reported execution. Use the same generated trajectory and sensor realization for every comparator in a paired run. Keep all methods in all scenarios, including LOS and runs that favor a baseline. Use several independent seeds, and make the independent run—not individual temporally correlated samples—the uncertainty unit.

Report position RMSE, within-run tail error, maximum error and output availability. If recovery time is reported, define the outage-end timestamp, threshold, consecutive-duration rule and censoring before examining outcomes. Do not assign zero recovery time to runs that never recover or to runs with missing output. Report numerical failures and unavailable UWB-only solutions explicitly. UWB-only errors on measurement timestamps and continuously emitted fusion errors have different support; compare on common timestamps as well as reporting each method's native availability.

NIS is an innovation-consistency diagnostic under a local linear-Gaussian model. It is not a validated NLOS classifier. Empirical rejection rates and the distribution of pre-gate NIS should accompany accuracy. Any post-gate NIS distribution is selection-biased. Do not describe a nominal chi-square threshold as proof of calibrated false-alarm probability in biased, nonlinear or adapted-filter cases.

The initial synthetic evaluation is exploratory. Thresholds selected while developing the estimator are development choices; merely rerunning with new random seeds is not an independent real-world validation. A later confirmatory evaluation must reserve unseen trajectories, geometries, bias regimes and datasets.

## Public and collected data

UTIL is a promising public UAV dataset with IMU, ground truth and UWB **TDOA** measurements. TDOA is a difference between two ranges, with different Jacobians and possibly correlated observation errors. It must not be relabeled or directly ingested as a tag-to-anchor range. The current range estimator requires a verified adapter and a TDOA observation model before UTIL can support a reported result. Check the data license and actual download artifacts separately from the publication metadata.

For local data collection, retain raw IMU and UWB messages, clock information, anchor survey and uncertainty, tag-to-IMU extrinsics, accelerometer/gyroscope calibration, ground-truth calibration and sensor firmware settings. Record LOS/occlusion interventions independently of estimator residuals. Include static segments, multiple flight speeds, changed anchor layouts, several outage durations and repeat sessions. Keep calibration/tuning sessions distinct from evaluation flights. Do not align each test trajectory to ground truth in a way that removes the errors the estimator is meant to measure; disclose any fixed-frame calibration and its source.

The zero lever arm, synchronous observations and known-anchor geometry in the initial simulator are simplifying assumptions. Time offsets, anchor errors, imperfect initialization, vibration, bias variation, antenna delays and spatially correlated NLOS are required stress tests before operational claims.

## Security evaluation and deployment boundary

The reference protects transmitted telemetry from disclosure or alteration by a network adversary without the session key and applies a receiver replay policy. It does not establish physical distance authenticity, resistance to relay or early-detect/late-commit attacks, trustworthiness of a compromised endpoint, or confidentiality of packet timing and size. Denial of service remains possible. Safety assurance and flight certification are outside the artifact's scope.

Before deployment, define key provisioning, direction separation, rotation and revocation, restart/rollback behavior, authenticated session establishment, bounded message sizes, replay-state persistence or mandatory rekeying, and receiver recovery after packet loss. Measure CPU, energy, memory, latency and deadline misses on the intended onboard hardware. Host microbenchmarks cannot establish embedded real-time feasibility.

## Writing and review rules

- Maintain an evidence ledger connecting each result to a configuration, code revision, data hash and generated output.
- Use authoritative metadata for bibliographic details. Distinguish metadata-only inspection from abstract review and full-text review; do not infer an algorithm's performance from its title.
- Preserve negative findings, limitations and failed runs. Do not replace an unfavorable result with a claim about expected performance.
- Use “synthetic” or “simulation” wherever a reader might otherwise infer a physical experiment.
- Reserve “improves,” “outperforms” and numerical percentages for the stated metric, comparator, dataset and uncertainty estimate actually measured.
- Keep security tests separate from localization results. Neither a passed unit test nor use of a standard cipher is a proof of system security.
- Translate qualifications, exclusions and uncertainty into Chinese along with the numerical results; do not strengthen claims in translation.
