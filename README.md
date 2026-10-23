# UWB/IMU UAV localization and authenticated telemetry

A reproducible research repository continuing the author's master's proposal
and first paper draft. The English manuscript is primary; a corresponding
Chinese translation is maintained. Algorithms, source documents, literature,
synthetic sensor data, experiment configurations, and results live together here.

本仓库继续“基于多源数据融合的安全室内无人机定位研究”中的**研究内容一：
UWB/INS 定位与数据保护**。英文为主稿，中文逐节对应。当前是有代码、仿真和
证据记录的研究版本；真实飞行验证、明确的创新贡献和投稿定稿仍需继续完成。
开题中的 UWB/视觉及同态加密属于后续独立研究范围。

## Read the paper

| Version | Source | PDF | Editable Word |
|---|---|---|---|
| English (primary) | [Manuscript](paper/en/manuscript.md) | [PDF](paper/exports/manuscript-en.pdf) | [DOCX](paper/exports/manuscript-en.docx) |
| 中文译稿 | [正文](paper/zh/manuscript.md) | [PDF](paper/exports/manuscript-zh.pdf) | [DOCX](paper/exports/manuscript-zh.docx) |

The manuscript reports **synthetic experiments**, not measured UAV flights.
Standard ESKF, innovation gating, covariance inflation and AES-GCM are established
techniques; their integration is not presented as an established novel algorithm.
See [research scope and next steps](docs/research-plan.md) and the
[audit of the supplied drafts](docs/source-audit.md).

## What is implemented

- Three-dimensional, 15-state error-state EKF with body-frame IMU measurements,
  quaternion attitude, accelerometer/gyroscope bias, Joseph covariance updates
  and attitude-error reset.
- Six estimators: UWB-only nonlinear least squares, INS only, fixed ESKF,
  gate-only ESKF, bounded variance inflation, and gating plus inflation.
- Paired synthetic LOS, NLOS-bias, dropout and combined scenarios; a fixed
  10-seed reference protocol with per-run metrics and uncertainty across seeds.
- AES-256-GCM telemetry with authenticated headers, counter nonces, a strict
  replay policy and explicit fresh-key session requirements. This protects
  telemetry, not the physical authenticity of radio ranging.
- Source hashes, generated-data hashes, measurement/prediction files,
  diagnostics, figures, and source-verified literature metadata.

The recorded reference study contains **240 estimator runs** and all **40 synthetic
measurement datasets**, including the complete archive under
[`data/synthetic/reference-full/`](data/synthetic/reference-full/). The 27 unit
tests passed; independent numerical and artifact checks are recorded in
[`docs/validation-review.md`](docs/validation-review.md).

The simulator assumes synchronized sensors, surveyed non-coplanar anchors, zero
tag/IMU lever arm and a declared warm start. It is a kinematic sensor model, not a
quadrotor dynamics or RF propagation simulator. No real flight logs were supplied.

## Reproduce

Python 3.11+ is supported; the recorded environment uses Python 3.12.14. Install
the pinned direct dependencies and the package from the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
python -m unittest discover -s tests -v
make smoke
make verify
```

The small smoke run uses fresh temporary directories. Existing evidence is never
overwritten by the experiment runner. To reproduce all 240 estimator runs:

```sh
python scripts/run_experiments.py --config configs/reference.json \
  --output /tmp/uav-reference-results --data-output /tmp/uav-reference-data
python scripts/verify_artifacts.py /tmp/uav-reference-results/manifest.json --check-source
```

Choose new empty directories for another execution. Compare numerical outputs
with appropriate floating-point tolerances; host timings and rendered-file
metadata are not expected to be identical. [Metric definitions and the fixed
protocol](experiments/README.md) explain common-timestamp comparisons, missing
UWB fixes and the limits of the confidence intervals.

```sh
python scripts/security_demo.py --output /tmp/uav-security-benchmark.json
python scripts/secure_localization_demo.py --output /tmp/uav-secure-localization.json
python scripts/build_paper.py
```

PDF/Word export requires Pandoc; PDF also needs XeLaTeX and Noto fonts. See
[document build instructions](paper/README.md). No operational keys are stored.

## Repository map

| Directory | Contents |
|---|---|
| [`sources/`](sources/) | Unchanged supplied documents, equation-preserving extraction and provenance |
| [`src/uav_localization/`](src/uav_localization/) | Estimators, synthetic sensor model, rotations and telemetry protection |
| [`configs/`](configs/) | Explicit simulation/filter settings and reserved/evaluation seeds |
| [`data/`](data/) | Data schema, synthetic datasets and generation manifests |
| [`experiments/`](experiments/) | Evaluation protocol, machine-readable results and figures |
| [`results/security/`](results/security/) | Host-only timing, rejection checks and protected localization round-trip evidence |
| [`literature/`](literature/) | Bibliographic metadata, reading scope, source URLs and proposal-reference audit |
| [`paper/`](paper/) | English paper, Chinese translation, bibliography and exports |
| [`docs/`](docs/) | Mathematics, threat model, research plan and validation review |
| [`tests/`](tests/) | Estimation, geometry, data-leakage and security tests |

Start with the [reference result report](experiments/results/reference/report.md),
[algorithm definitions](docs/algorithm.md), [security boundaries](docs/security.md)
and [research evidence policy](docs/research-integrity.md). A candidate public
dataset, UTIL, uses **TDOA**; it has not been downloaded or evaluated here and
requires its own observation model and calibration adapter.
