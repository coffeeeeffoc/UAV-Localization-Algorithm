# Research notes and evidence boundaries

Updated: 2026-10-23. Scope: research item one in the supplied proposal—indoor UWB/IMU localization and protected telemetry. This is a targeted initial review, not a systematic review or a claim of complete coverage through 2026. Vision, homomorphic encryption, and federated learning remain outside the implemented first study.

`references.json` is the source registry; `references.csv` is its compact review view. Citation keys resolve in `../paper/references.bib`. `metadata/` preserves selected Crossref bibliographic metadata (abstracts were inspected where supplied but are not redistributed). `access-log.json` records retrieved source URLs, access dates, response hashes and unsuccessful retrievals. Full papers were inspected in temporary working storage and are not redistributed here. No entry claims a complete full-text review or independent reproduction.

## Findings that affect the paper

| Question | Verified evidence | Consequence for this project |
| --- | --- | --- |
| Is UWB/IMU EKF fusion new? | Solà derives IMU error-state estimation; Li et al. discuss conventional EKF fusion and present a continuous-time alternative. | Describe the implemented ESKF as a reproducible baseline/building block. Establish novelty through a precise, falsifiable contribution and comparisons, not the sensor combination. |
| Is residual-based robustness or adaptive covariance new? | The published titles of Bordoy et al. (2017) and Briese et al. (2017) explicitly cover robust NLOS fusion and adaptive-covariance UWB fusion. Their detailed methods have not yet been read. | A first-in-literature claim is unsupported. Acquire and compare the full methods before asserting methodological distinction. |
| Does UWB remove NLOS errors? | The UTIL author website and preprint describe static/dynamic obstacles, biased/multimodal errors, and complete measurement blockage. | Model positive range bias and dropout explicitly, and avoid blanket “strong penetration” or “multipath immunity” claims. The sign of a **TDOA** error need not be positive. |
| Is a real UAV dataset available? | Zhao et al. provide a quadrotor dataset with TDOA, IMU, surveyed anchors and motion-capture pose. | UTIL is a promising next external-validation source. Its measurement equation differs from the implemented per-anchor range model. |
| Does AES alone make localization secure? | NIST SP 800-38D defines authenticated encryption and explicitly says GCM does not inherently prevent replay. RFC 5116 separates AEAD from protocol replay control. | Separate estimation robustness from telemetry confidentiality/integrity. Authenticate metadata and maintain replay state. Do not claim protection from physically spoofed measurements, compromised devices, jamming or denial of service. |

## Model derivation to cite

Solà (2017), Sections 5–6, defines a nominal state and a small local attitude error. In the local convention, the true rotation is `R_true = R_nominal Exp(delta_theta)`. Accelerometer measurements are body-frame **specific force**, not world-frame acceleration; velocity propagation needs the body-to-world rotation and gravity. The error correction is injected into the nominal state, then reset. Section 6.3 gives the first-order local orientation reset block `I - 0.5 [delta_theta]_x`. The manuscript and code must use the same quaternion ordering, multiplication convention, perturbation side, gravity direction, state ordering and units.

These are established estimation constructions. They do not by themselves establish observability of every state in every trajectory. Position-only or range-only updates can leave yaw and bias weakly observable under limited excitation. Initialization, anchor geometry, sensor offsets and time alignment must be reported rather than silently supplied by the truth trajectory.

The proposed residual policy is an engineering hypothesis to evaluate. A large innovation may reflect NLOS, a bad initial state, calibration error, clock error or incorrect process noise. Innovation inflation/gating must not be described as a reliable physical NLOS classifier without labeled-data evidence. If covariance is adapted from residuals, discuss selection effects, bounded variance, the contribution of predicted state uncertainty, and rejection/recovery behavior. Standard Gaussian NIS thresholds are nominal diagnostics after adaptive or truncated updates, not automatic proofs of consistency.

## Closest work to read before submission

- **Bordoy et al. (2017), `bordoy2017robust`:** robust EKF for NLOS mitigation and sensor fusion. Bibliographic verification only; acquire the full method before algorithm-level comparison.
- **Briese et al. (2017), `briese2017adaptive`:** adaptive-covariance Kalman filtering for UWB sensor fusion. Bibliographic verification only; especially relevant to claims about residual-driven covariance changes.
- **Li, Cao and Hanebeck (2023), `li2023continuous`:** quaternion cumulative B-splines and sliding-window fitting for asynchronous UWB-inertial fusion; abstract/introduction of the author manuscript inspected. Its public-data experiments motivate a stronger external baseline, but no performance numbers are imported into this repository as our results.
- **Oursland and Mehrabian (2024), `oursland2024invariant`:** invariant IMU-UWB EKF. Bibliographic verification only; a candidate modern filtering comparison.
- **Jiang et al. (2021), `jiang2021seamless`:** UWB-enhanced tightly coupled multisensor positioning; corresponds to proposal reference [24]. Metadata verified; detailed method not reviewed.
- **Huang et al. (2023 issue), `huang2023selftraining`:** self-training NLOS mitigation; corresponds to proposal [25]. Metadata verified; learned-model assumptions and datasets require full-text inspection.

Dardari et al. (2009) and Marano et al. (2010) are background reading candidates whose bibliographic records are verified. Their detailed claims have not been used as established evidence here.

## Candidate data: UTIL

Primary landing page: <https://learnsyslab.github.io/util-uwb-dataset/>. The original `utiasdsl.github.io` address redirects through an HTML refresh. Publication: `zhao2024util`, *IJRR* 43(10), 1443–1456, DOI <https://doi.org/10.1177/02783649241230640>. Author manuscript: <https://arxiv.org/abs/2203.14471>. The preprint identifier's year is not the journal issue year.

The author website reports approximately 150 minutes of flights, four anchor constellations, and static/dynamic obstacle scenarios. These are **dataset-author statements**, not measurements made in this repository. The paper's Eq. (4) includes the UWB lever arm:

\[
 d_{ij}=\|p+R r_{uv}-a_j\|-\|p+R r_{uv}-a_i\|.
\]

The paper reports `r_uv = [-0.012, 0.001, 0.091]` m. Table 3 gives milliseconds for CSV timestamps, acceleration in `G`, gyroscope in degrees/s, and ground-truth quaternion order `(qx,qy,qz,qw)`. A parser must explicitly convert to the estimator's seconds, m/s², radians/s and chosen quaternion order. Event streams have separate timestamps. Ground truth is sent to the onboard logger; the authors discuss approximately 10 ms communication latency and ignored clock drift on their approximately 120 s sequences. Treat those assumptions as part of the uncertainty budget.

Before claiming results on UTIL:

1. Record an exact release/commit, download URL, checksum, license or permission, and file inventory.
2. Implement the distance-difference observation and lever-arm Jacobian; verify the sign convention against the paper and raw samples.
3. Preserve asynchronous event ordering and calibrations. Never convert a TDOA observation into an invented absolute range.
4. Divide development/test data by whole trials and, preferably, held-out constellation/obstacle conditions. Freeze parameters before evaluating held-out trials.
5. Match initial-state information across baselines. Limit use of motion capture to a disclosed initialization window and scoring; no per-frame truth injection.
6. Report per-trial errors, failure rates, trajectory duration and uncertainty; retain all trial IDs and failures.

At this stage, dataset documentation has been inspected but **raw dataset files have not been downloaded, adapted or evaluated**. The GitHub repository API reported `license: null` on 2026-10-23; this is not proof that no license exists. Redistribution rights are unconfirmed. Keep upstream data external until the dataset terms are verified; store manifests and reproducible acquisition instructions in this repository.

## Cryptographic claims and tests

NIST SP 800-38D, Section 8, requires unique IVs under a key. Appendix A explains why reuse is dangerous; Appendix D explicitly separates authentication from replay prevention. RFC 5116, Sections 3.1–3.2, discusses distinct fixed/counter fields, device coordination and state across reboot. Section 5.1.1 describes severe consequences of GCM nonce reuse.

For the research prototype, report key size, nonce construction, tag length, serialized metadata, ciphertext length, session assumptions and receiver replay policy. A session counter is only safe when uniqueness and restart handling are enforced. Authenticated session/device identity and sequence counters can help prevent cross-session or duplicate acceptance; receiver state should advance only after successful authentication. Tamper, wrong-key, replay and malformed-message tests are implementation checks, not cryptographic proofs. Timing collected on a workstation is not evidence of embedded real-time suitability or energy use.

The NIST landing page includes a 2024 announcement of planned revision. The bibliography cites the identified 2007 final document; check for a superseding final standard when preparing submission.

## Contribution and evaluation boundary

A defensible initial contribution is an openly inspectable implementation and evaluation protocol integrating a specified robust range-update policy with authenticated telemetry. Whether the robust policy is a publishable methodological contribution remains open. The current combination of existing techniques must not be framed as a newly invented cryptographic primitive, a first fusion framework, or a validated flight-safety system.

The first experiment should answer limited questions: under fixed synthetic noise and outage models, how do inertial-only, UWB-only, fixed-noise fusion and the specified robust policy differ? An ablation should separate gating from covariance inflation. Multiple independently seeded trials, the same sensor streams across methods, held-out tuning seeds, and disclosure of all failures are needed. Real-data validation, calibrated sensor noise, modern baselines, hyperparameter sensitivity and embedded latency measurements remain prerequisites for stronger claims.

## 中文要点

英文稿是主稿；中文稿应翻译相同的证据等级和限制。已核验书目信息不等于已阅读全文；下载论文不等于复现实验。普通 UWB/IMU 融合、鲁棒 EKF、自适应协方差和 AES-GCM 均有既有工作，不能把组合本身写成首创。UTIL 是有价值的真实飞行数据候选，但其 TDOA 距离差模型、异步时间戳、传感器偏移和单位转换必须单独适配。仿真结果只能支持所设仿真条件下的结论，不能代替真实飞行验证；认证加密保障传输数据的保密性和完整性，不证明测量物理真实性。
