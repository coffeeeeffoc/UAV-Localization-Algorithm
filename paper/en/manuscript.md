---
title: "UWB/INS Fusion with Innovation-Based Range Handling and Authenticated Telemetry for Indoor UAV Localization"
subtitle: "An executable research baseline and synthetic evaluation"
lang: en
---

> **Manuscript status.** This working manuscript develops research content 1 of the supplied master's proposal. The English text is the authoritative version; the Chinese file is its translation. The artifact is an initial reproducible research baseline, not a completed validation on a physical UAV. The novelty of the method combination has not been established. Authorship, target venue, and final submission formatting remain to be confirmed.

# Abstract

Indoor unmanned aerial vehicle localization requires continuous state estimation when satellite navigation is unavailable and radio measurements are degraded or interrupted. This study develops a reproducible baseline combining ultra-wideband (UWB) ranges with inertial measurements in a three-dimensional error-state extended Kalman filter. The estimator includes position, velocity, orientation, and inertial sensor biases. Scalar range updates use normalized innovations to reject severe inconsistencies or increase measurement variance within declared bounds. Fixed-covariance fusion, gating alone, variance inflation alone, UWB-only multilateration, and inertial propagation provide comparators and ablations. A controlled synthetic study separates line-of-sight ranging, positive ranging biases, complete UWB outages, and their combination. Across ten noise realizations of the prescribed NLOS trajectory, mean position RMSE at common observed epochs is 0.0666 m for the combined rule, 1.1345 m for fixed fusion, and 0.0657 m for gating alone; an additional gain from inflation is not established. The implementation also provides AES-256-GCM protection of transmitted telemetry with an explicit session and replay policy. Estimation robustness and communication protection are evaluated as distinct properties: authenticated encryption cannot establish the physical truth of a range observation. The repository records assumptions, executable configurations, sources, and experimental outputs. The resulting artifact supports investigation of the proposed research questions; synthetic performance cannot establish real-flight accuracy, deployment readiness, or superiority over contemporary state-of-the-art methods.

**Keywords:** indoor UAV localization; ultra-wideband; inertial navigation; error-state Kalman filter; innovation gating; authenticated encryption; reproducibility.

# 1. Introduction

A UAV operating indoors may lack usable global navigation satellite system measurements. An inertial measurement unit (IMU) can support high-rate state propagation, but errors in acceleration, angular velocity, initial orientation, and sensor biases accumulate through integration. Ranges to surveyed UWB anchors provide position-dependent constraints. Their utility depends on anchor geometry, measurement timing, calibration, and propagation conditions. A positive range bias caused by an obstructed path can be inconsistent with the zero-mean noise model of a conventional filter. If all UWB observations disappear, the estimator must propagate without external range corrections and its uncertainty should increase.

The supplied proposal identifies both UWB/INS and UWB/vision research directions. This paper addresses the UWB/INS direction. The implementation replaces an underspecified position–velocity–Euler-angle model with an explicit quaternion-based error-state formulation including accelerometer and gyroscope biases. It also makes the robust update rule, baseline definitions, synthetic data generation, and telemetry assumptions inspectable. The vision and homomorphic-encryption directions are outside the present implementation.

The research questions are whether innovation-based range handling improves the specified synthetic error metrics under biased ranging, what it costs under line of sight, and how gating and variance inflation contribute separately. A second, independent question concerns the correctness and overhead of authenticated telemetry under a defined network-adversary model. There is no hypothesis that encryption itself improves localization accuracy.

The contribution of this version is an executable, auditable baseline and an evaluation protocol. It does not claim that combining Kalman filtering, innovation tests, and AES-GCM is a new estimation or cryptographic method. A publication claiming methodological novelty will require a sharper advance and comparison with the closest applicable prior work.

# 2. Related work and positioning

Error-state inertial filtering requires consistent rotation conventions, error injection, and covariance reset. Solà provides a detailed treatment of quaternion kinematics and local error-state formulations [@sola2017quaternion]. We follow the right-multiplicative local attitude-error convention and state the implementation's propagation and noise approximations explicitly.

Robust EKF treatment of UWB non-line-of-sight (NLOS) measurements and adaptive covariance treatment in UWB fusion precede this work [@bordoy2017robust; @briese2017adaptive]. These two references have been checked at bibliographic-metadata level in the current literature audit. Their existence supports the limited observation that these research directions are established; it does not support a detailed reconstruction of their methods or a claim about comparative accuracy. A submission-quality related-work section must expand this audit to full texts and recent reproducible competitors.

The UTIL dataset offers a relevant route to real UAV evaluation, with UWB time-difference-of-arrival (TDOA), inertial measurements, and motion-capture ground truth [@zhao2024util]. A TDOA observation is a difference between ranges, not an independent tag-to-anchor range. Its observation model and possible cross-observation correlations differ from the present scalar range model. Consequently, publication metadata or dataset availability alone is not experimental evidence for this implementation; a verified adapter and suitable measurement model are prerequisites for using UTIL. Continuous-time UWB-inertial estimation also addresses asynchronous measurements using a different estimation formulation [@li2023continuous]; the present synchronized discrete-time baseline does not implement that approach.

AES-GCM is a standardized authenticated-encryption mode [@dworkin2007gcm]. The AEAD interface authenticates associated data as well as ciphertext and requires nonce handling consistent with the chosen construction [@mcgrew2008aead]. Neither the cryptographic primitive nor successful decryption automatically provides a replay policy or authenticates a physical propagation path. These responsibilities must be addressed separately.

# 3. State, sensor, and initialization models

## 3.1. Frames and state

Let the world frame be east–north–up (ENU), with gravity $g=[0,0,-9.80665]^T\,\mathrm{m\,s^{-2}}$. Position $p$ and velocity $v$ are expressed in this frame. The unit quaternion $q$ represents the body-to-world rotation $R(q)$; the implementation stores quaternion components in $(x,y,z,w)$ order. The nominal state is

$$
x=(p,v,q,b_a,b_g),
$$

where $b_a$ and $b_g$ are body-frame accelerometer and gyroscope biases. The 15-dimensional error state is

$$
\delta x=[\delta p^T,\delta v^T,\delta\theta^T,
\delta b_a^T,\delta b_g^T]^T,
\qquad q_{\mathrm{true}}=q\otimes\operatorname{Exp}(\delta\theta).
$$

Here $\operatorname{Exp}$ maps a rotation vector to a unit quaternion and $[u]_\times$ denotes the skew-symmetric matrix satisfying $[u]_\times w=u\times w$. The simulator assumes known, stationary anchors, synchronized measurement times, and a zero UWB-tag-to-IMU lever arm. These are modeling assumptions, not calibration achievements.

## 3.2. Inertial observations and propagation

The IMU produces body-frame specific force and angular velocity:

$$
f_m=R(q)^T(\ddot p-g)+b_a+n_a,
\qquad \omega_m=\omega+b_g+n_g.
$$

The simulator's white-noise standard deviations are **per sample**, not continuous-time noise densities. Bias increments follow random walks with specified standard deviations per square root of time. With $f=f_m-b_a$, $\omega=\omega_m-b_g$, and step $\Delta t$, the nominal propagation uses a midpoint orientation:

$$
q_{1/2}=q_k\otimes\operatorname{Exp}(\omega\Delta t/2),
\qquad a^w=R(q_{1/2})f+g,
$$

$$
p_{k+1}=p_k+v_k\Delta t+\tfrac12a^w\Delta t^2,
\quad v_{k+1}=v_k+a^w\Delta t,
\quad q_{k+1}=q_k\otimes\operatorname{Exp}(\omega\Delta t).
$$

Nominal biases remain constant during prediction and are corrected by measurement updates. For $R=R(q_{1/2})$, the local continuous-time error matrix used by the implementation is

$$
F=\begin{bmatrix}
0&I&0&0&0\\
0&0&-R[f]_\times&-R&0\\
0&0&-[\omega]_\times&0&-I\\
0&0&0&0&0\\
0&0&0&0&0
\end{bmatrix},
\qquad \Phi=I+F\Delta t+\tfrac12F^2\Delta t^2.
$$

For per-sample acceleration and angular-velocity noise, and bias random-walk amplitudes, define

$$
D=\operatorname{diag}(\sigma_a^2I,\sigma_g^2I,
\sigma_{ba}^2I,\sigma_{bg}^2I),
\quad
G_d=\begin{bmatrix}
\tfrac12 R\Delta t^2&0&0&0\\
R\Delta t&0&0&0\\
0&I\Delta t&0&0\\
0&0&I\sqrt{\Delta t}&0\\
0&0&0&I\sqrt{\Delta t}
\end{bmatrix}.
$$

The prediction is $P^-_{k+1}=\Phi P_k\Phi^T+G_dDG_d^T$. This is a declared finite-step approximation; it is not exact discretization of all coupled continuous-time noise terms. Sampling-rate sensitivity and higher-order propagation are subjects for subsequent evaluation.

## 3.3. UWB observations

For anchor position $a_i$, the simulated observation is

$$
z_i=\|p-a_i\|+\beta_i+\epsilon_i,
\qquad \epsilon_i\sim\mathcal N(0,\sigma_r^2).
$$

The synthetic bias $\beta_i$ is zero in LOS conditions and positive during the configured NLOS intervals. The filter does not receive $\beta_i$ or the NLOS labels and does not estimate a dedicated NLOS-bias state. It uses $h_i(x)=\|p-a_i\|$, with error-state Jacobian

$$
H_i=\left[\frac{(p-a_i)^T}{\|p-a_i\|}\quad 0\quad0\quad0\quad0\right].
$$

The zero lever arm makes the direct attitude derivative zero. A nonzero lever arm would introduce orientation dependence and requires a changed observation model. Coincidence with an anchor makes this Jacobian undefined and is not a valid update point.

## 3.4. Declared warm start and observability

The simulation initializes position, velocity and orientation from their true initial values plus fixed, disclosed errors. This is a controlled **warm-start assumption**, not an implementable initialization algorithm. The estimator receives the perturbed values, not subsequent truth or true biases. Initial bias estimates are zero. Real-data evaluation requires an independently justified initializer and covariance; the present study cannot demonstrate cold-start convergence.

Position information depends on anchor geometry. Orientation and inertial biases are constrained only indirectly through the dynamics and position updates; their observability depends on motion and initial conditions. Position accuracy alone does not establish accurate yaw or bias estimates. During complete UWB loss there is no external position constraint, even if the software continues to emit estimates.

# 4. Innovation-based range handling

## 4.1. Detection and variance inflation

Ranges are processed as sequential scalar updates in a fixed anchor order. Each innovation is computed from the state and covariance available at that point in the sequence. For baseline variance $R_0=\sigma_r^2$, define

$$
\nu_i=z_i-h_i(x^-),\qquad
S_{0,i}=H_iP^-H_i^T+R_0,\qquad
\eta_i=\nu_i^2/S_{0,i}.
$$

$\eta_i$ is the normalized innovation squared (NIS). Under the ideal local scalar Gaussian model it motivates a chi-square reference, but the nonlinear, biased and adapted filter need not satisfy that calibration. A large value indicates model–observation inconsistency. It does not identify NLOS uniquely: calibration errors, timing errors, poor initialization and model mismatch can also produce large innovations.

The gate rejects an observation when $\eta_i>\gamma_h$, with $\gamma_h=10.827566$. The inflation rule, when enabled, is

$$
\lambda_i=\operatorname{clip}(\eta_i/\gamma_s,1,\lambda_{\max}),
\qquad R_i=R_0\lambda_i,
$$

where $\gamma_s=3.841459$ and $\lambda_{\max}=25$. The thresholds correspond to conventional 99.9% and 95% scalar chi-square quantiles and are fixed development settings; they are not learned or claimed to be optimal. The gate is evaluated using $S_{0,i}$ **before** inflation. In the combined variant, an accepted observation therefore has $\lambda_i\leq\gamma_h/\gamma_s\approx2.82$; the cap of 25 can become active in the inflation-only ablation but not in an accepted combined update with these defaults.

This bounded rule differs from the unbounded residual outer-product smoothing suggested in the supplied draft. It is a per-observation robust weighting heuristic, not a consistent estimator of measurement covariance and not a proof that an unknown positive bias has been compensated. The process-noise model remains fixed.

## 4.2. Correction and covariance reset

For an accepted observation,

$$
K_i=P^-H_i^T(H_iP^-H_i^T+R_i)^{-1},
\qquad \widehat{\delta x}=K_i\nu_i.
$$

Position, velocity and biases receive additive corrections, whereas orientation is corrected by $q^+=q^-\otimes\operatorname{Exp}(\widehat{\delta\theta})$. Before resetting the local error to zero, the covariance is updated in Joseph form:

$$
\widetilde P=(I-K_iH_i)P^-(I-K_iH_i)^T+K_iR_iK_i^T.
$$

The reset uses $P^+=J\widetilde P J^T$, where

$$
J=\operatorname{diag}(I,I,J_r(\widehat{\delta\theta}),I,I),
$$

$$
J_r(u)=I-\frac{1-\cos\theta}{\theta^2}[u]_\times
+\frac{\theta-\sin\theta}{\theta^3}[u]_\times^2,
\qquad \theta=\|u\|,
$$

with the small-angle limit evaluated numerically. This reset is necessary to keep covariance expressed about the corrected nominal orientation [@sola2017quaternion]. Symmetrization removes floating-point asymmetry; it does not make an incorrectly specified model statistically consistent.

If an observation is rejected, the corresponding update is skipped. If all measurements are absent or rejected, the filter relies on inertial propagation. Reacquisition is not guaranteed: a gate can reject valid measurements after sufficient drift. This failure mode belongs in the evaluation rather than being assumed away.

## 4.3. Comparators and ablations

| Repository identifier | Estimation rule | Purpose |
|---|---|---|
| `uwb` | Epoch-wise nonlinear least-squares multilateration without a dynamic prior | Ranging-only comparator; output absent without sufficient usable ranges |
| `ins` | Inertial propagation from the same warm start | Drift comparator without UWB corrections |
| `eskf` | ESKF with fixed $R_0$ | Conventional fusion reference |
| `gated_eskf` | Fixed $R_0$ and hard NIS rejection | Isolate gating |
| `adaptive_eskf` | Bounded variance inflation without hard rejection | Isolate per-observation inflation |
| `robust_eskf` | Hard rejection followed by bounded inflation | Combined robust baseline |

These are implementations within one common framework, not reproductions of named external competitors. The UWB optimizer uses the previous successful solution as its numerical starting point and requires at least four noncoplanar anchors; its objective contains only the current ranges. All fusion variants share initialization, process noise and sensor realizations. In particular, a favorable comparison against fixed fusion is insufficient to establish that inflation adds value beyond gating alone.

# 5. Authenticated telemetry and threat model

We consider a network adversary able to observe, alter, inject, drop, duplicate or reorder telemetry packets, but unable to obtain the current session key or compromise trusted endpoints. Local sensor measurements enter the estimator before telemetry encryption. A separate module protects serialized outgoing payloads with AES-256-GCM; filtering is performed in plaintext at the trusted endpoint. This is not homomorphic computation.

For session key $K$, unique nonce $N$, associated-data header $A$ and payload $M$,

$$
(C,T)=\operatorname{GCM.Enc}_K(N,M,A),
\qquad
M=\operatorname{GCM.Dec}_K(N,C,T,A)
$$

only if authentication succeeds. The reference construction uses a 96-bit nonce comprising a four-byte session prefix and a big-endian 64-bit counter, with a 128-bit authentication tag. A fresh 256-bit key is required for every unidirectional session with one sender; restarting or rolling back either endpoint requires a new key and session. The protocol binds `version`, `device_id`, `session_id`, `message_type` and `counter` as associated data, encoded as sorted-key ASCII JSON without optional whitespace. The receiver authenticates first and then requires the counter to exceed its accepted watermark. It permits gaps but rejects repeated or out-of-order older packets, including legitimately delayed packets. An invalid packet cannot advance replay state. Counter exhaustion is rejected rather than wrapped; the reference also applies a default budget of $2^{20}$ messages and a 16,384-byte payload cap. These application limits are not a complete deployment key-lifetime policy.

GCM's confidentiality and integrity guarantees depend on its assumptions, including nonce uniqueness for a key [@dworkin2007gcm; @mcgrew2008aead]. The replay policy is an additional protocol mechanism. Tests of packet alteration, wrong keys, repeated packets and state handling provide implementation evidence, not a new security proof.

This mechanism does not authenticate the physical distance between tag and anchor. A compromised sensor can authenticate false values; a range manipulation occurring before encryption is not repaired by encryption. The reference does not establish resistance to UWB relay attacks, traffic analysis, key compromise, denial of service, or unsafe control decisions. It also does not provide key distribution, secure storage or deployment certification. End-to-end latency, power and memory must be measured on the target hardware before making real-time deployment claims.

# 6. Experimental protocol

## 6.1. Synthetic data and scenarios

The simulator generates kinematically consistent positions, velocities, attitudes, body-frame specific force and angular increments. It is not a quadrotor dynamics model or an electromagnetic propagation simulator. The default duration is 30 s, with 100 Hz IMU and 10 Hz UWB observations. A three-dimensional sinusoidal trajectory lies within a $10\times8$ m horizontal anchor layout. Six anchors alternate between heights of 0.3 m and 2.8 m. Exact anchor coordinates, trajectory equations, seeds and all parameter values are stored with the executable configuration.

Default standard deviations are 0.08 m for LOS ranges, $0.03\,\mathrm{m\,s^{-2}}$ per accelerometer sample, and $0.001\,\mathrm{rad\,s^{-1}}$ per gyroscope sample. Accelerometer and gyroscope bias random-walk amplitudes are respectively $0.0001\,\mathrm{m\,s^{-2}/\sqrt{s}}$ and $0.00002\,\mathrm{rad\,s^{-1}/\sqrt{s}}$. The filter is given these same nominal noise amplitudes; they are not estimated from a calibration dataset. This matched-noise setting is an additional idealization. The initial position error is $(0.25,-0.20,0.15)$ m, initial velocity error is $(0.03,-0.02,0.02)$ m/s, and the initial local attitude rotation-vector perturbation is $(0.7,-0.5,1.5)$ degrees. Initial covariance is diagonal, with standard deviations of 0.5 m, 0.2 m/s, 3 degrees, $0.1\,\mathrm{m\,s^{-2}}$ and $0.005\,\mathrm{rad\,s^{-1}}$ for each component of position, velocity, attitude error, accelerometer bias and gyroscope bias, respectively. These are synthetic conditions, not measurements from a particular IMU or UWB product.

| Scenario | Controlled corruption |
|---|---|
| `los` | Zero-mean ranging noise only |
| `nlos` | Add $0.6+E$ m, $E\sim\operatorname{Exponential}(\text{mean }0.25\,\mathrm m)$, to anchors 0 and 1 during $[8,14)$ s and anchor 3 during $[20,24)$ s |
| `dropout` | Remove every UWB observation during $[15,19)$ s |
| `combined` | Apply the configured positive biases and complete outage |

The NLOS intervals persist, but the added exponential component is sampled independently for affected observations. This simplified process does not capture all temporal or cross-anchor correlations of real obstruction. Within a seed, comparators use exactly the same dataset. Random streams separate IMU noise, bias walks, range noise and NLOS corruption so that scenario changes do not silently replace the underlying IMU realization.

## 6.2. Metrics and statistical unit

For valid estimates at timestamps in set $\mathcal T$, define $e_k=\|\widehat p_k-p_k\|_2$ and

$$
\operatorname{RMSE}=\sqrt{\frac{1}{|\mathcal T|}\sum_{k\in\mathcal T}e_k^2}.
$$

Tail error, maximum error, output availability and accepted/rejected range counts complement RMSE. Availability denotes the fraction of scheduled timestamps with a valid numerical output; it is not a guarantee that the output is accurate. A UWB-only method emits estimates at solvable ranging epochs, whereas the inertial and fusion methods emit at the IMU rate. Native-rate errors therefore have different temporal support. Cross-method comparisons must also use common valid ranging epochs, and missing UWB-only output during outages must remain visible.

The reference protocol specifies ten evaluation seeds, 100–109, for each scenario. Seeds 0–4 are reserved for calibration/development, but no fitting step is implemented or claimed. An independent simulated run is the statistical unit; densely sampled trajectory points are temporally correlated and must not be treated as independent replications. Scenario summaries use the mean of per-run RMSEs and two-sided 95% Student-$t$ intervals across seeds. Pairwise differences use the same-seed RMSE of `robust_eskf` minus that of a comparator, again with a Student-$t$ interval. Comparisons are exploratory without multiplicity correction. They quantify variation under this generator, not uncertainty over all rooms, trajectories or radio conditions. Thresholds are fixed development choices, and no held-out physical dataset has been used to validate them.

## 6.3. Reproducibility and checks

The repository retains code, configuration, sensor-generation assumptions, data provenance and result files. Numerical checks cover the range Jacobian and state conventions; controlled trajectories check propagation and updates. Security checks are reported separately. A successful software test indicates behavior for the tested conditions; it is not evidence of convergence for arbitrary motion, calibrated covariance, or system safety.

Every numerical table must be generated from a recorded run and identify its configuration and data support. Runtime measurements must state platform and what is timed. Host-side Python timings cannot establish onboard throughput or latency bounds. Data from public sources require verified units, clock alignment, extrinsics and observation semantics before entering the analysis.

# 7. Results and evidence status

## 7.1. Synthetic localization study

<!-- RESULTS:START -->

The reference study completed on 23 October 2026 with four scenarios, ten paired noise seeds per scenario and six estimators (240 estimator runs). The execution manifest records code revision `4686451a6923c579e971c84ba7b5b367b6e814b9`, the resolved configuration and source hashes. Writing and result-generation activity made the repository working tree non-clean; the recorded estimator, simulator, geometry and runner hashes identify the executed implementation. Results are synthetic, using one prescribed trajectory with noise and bias-walk variation, not 40 independent physical flights.

Table 1 reports the mean of per-run position RMSEs in metres on `common_observed_uwb` timestamps. Each included timestamp has at least four observed ranges and finite position estimates from all six methods. Complete intervals for all entries are retained in `summary_metrics.csv`.

| Method | LOS | NLOS | Dropout | Combined |
|---|---:|---:|---:|---:|
| `uwb` | 0.1839 | 0.8989 | 0.1873 | 0.9634 |
| `ins` | 40.4813 | 40.4931 | 42.1235 | 42.1378 |
| `eskf` | 0.0594 | 1.1345 | 0.0607 | 1.1860 |
| `gated_eskf` | 0.0597 | 0.0657 | 0.0611 | 0.0679 |
| `adaptive_eskf` | 0.0597 | 0.4609 | 0.0611 | 0.5311 |
| `robust_eskf` | 0.0599 | 0.0666 | 0.0613 | 0.0690 |

The common support contains 301 epochs for LOS and 261 for dropout. The UWB optimizer fails to return a successful solution at one epoch each for seeds 100 and 107 in both NLOS and combined scenarios. Those four failed solutions are retained as missing values and excluded from the common-support comparison; the affected runs therefore have 300 NLOS or 260 combined epochs, respectively, while the other seeds retain 301 or 261. This conditional comparison does not assess output during the complete outage. Different common-support masks also explain the small cross-scenario changes in the INS-only entries despite identical underlying inertial data within each seed.

Under these controlled positive biases, both methods with hard gating have substantially lower common-epoch RMSE than fixed-covariance fusion. In contrast, the combined rule does not demonstrate an incremental gain over gating alone. Table 2 shows paired mean RMSE differences and exploratory 95% intervals in metres; negative differences favor the combined rule. Its small positive differences from gate-only fusion have intervals containing zero in all four scenarios. The findings support retaining gating as the simpler reference, not asserting that the extra variance adaptation improves performance.

| Scenario | Combined minus fixed ESKF | Combined minus gate-only ESKF |
|---|---:|---:|
| `los` | 0.0004 [-0.0010, 0.0019] | 0.0002 [-0.0014, 0.0018] |
| `nlos` | -1.0680 [-1.0887, -1.0472] | 0.0009 [-0.0006, 0.0023] |
| `dropout` | 0.0007 [-0.0009, 0.0022] | 0.0003 [-0.0012, 0.0017] |
| `combined` | -1.1170 [-1.1381, -1.0959] | 0.0010 [-0.0005, 0.0025] |

For the combined robust method, Table 3 evaluates all 3,001 IMU-grid timestamps, including the outage. Tail and maximum columns are means of the corresponding within-run statistics, not the pooled 95th percentile or overall worst case. The larger dense-grid errors in dropout and combined scenarios show why the conditional UWB-epoch table cannot establish outage continuity or accuracy by itself.

| Scenario | RMSE mean [95% CI] (m) | Mean within-run P95 (m) | Mean within-run maximum (m) |
|---|---:|---:|---:|
| `los` | 0.0618 [0.0563, 0.0674] | 0.1154 | 0.1924 |
| `nlos` | 0.0686 [0.0588, 0.0783] | 0.1260 | 0.1984 |
| `dropout` | 0.1020 [0.0829, 0.1210] | 0.2346 | 0.4021 |
| `combined` | 0.1112 [0.0883, 0.1342] | 0.2502 | 0.4376 |

The inertial and fusion methods produce finite states at all scheduled IMU timestamps in this study. That 100% numerical availability does not mean that an estimate remains accurate: the INS-only comparator drifts markedly. UWB-only output is naturally at the lower ranging rate and is absent throughout the configured outage; its low availability on the 100 Hz grid is not itself a solver-failure rate. Recovery time and covariance consistency have not been evaluated as separate outcomes.

![Representative position-error traces for seed 100, the first preselected evaluation seed, across all four synthetic scenarios. The vertical axes are logarithmic. Lines denote inertial/fusion estimates; UWB-only estimates are points at solvable observation times. This figure is illustrative and does not replace the ten-seed summaries.](../../experiments/results/reference/position_errors.png){width=100%}

<!-- RESULTS:END -->

The reported tables retain all methods and scenarios, including LOS and the absence of a demonstrated improvement over gating alone. A lower mean RMSE is not sufficient by itself to claim reliable recovery, calibrated uncertainty, or better safety. Representative seed-100 diagnostic logs retain rejected measurements; selection after gating changes the innovation distribution and prevents a naive consistency interpretation.

## 7.2. Telemetry functionality and host overhead

The recorded telemetry microbenchmark in `results/security/benchmark.json` was run on an x86-64 host reporting an AMD EPYC 7763 processor, Python 3.12.14 and `cryptography` 50.0.0. For each payload size, 100 warm-up packets preceded 2,000 measured packets in a single process. Sealing includes JSON/AAD serialization, AES-GCM and Base64/envelope encoding; opening includes parsing, tag verification and replay checks. The following descriptive measurements exclude network transport, key provisioning and storage.

| Payload (bytes) | Seal median / P95 ($\mu$s) | Open median / P95 ($\mu$s) | Serialized packet size (bytes) |
|---|---:|---:|---:|
| 128 | 9.94 / 13.24 | 13.40 / 17.65 | 345–346 |
| 512 | 11.57 / 14.42 | 15.13 / 21.27 | 857–858 |
| 2048 | 18.09 / 23.55 | 23.23 / 48.38 | 2905–2906 |

Packet size includes the example header and Base64 representation; the variation reflects counter encoding and is not solely cipher expansion. The same recorded execution rejected ciphertext alteration, associated-data alteration, a forged high counter, a wrong key, replay and out-of-order delivery, while leaving replay state unchanged on rejection. These functional checks and one benchmark session per payload size do not constitute a cryptographic proof, independent flight trials, a hard latency bound or evidence of onboard performance.

## 7.3. Localization-to-telemetry integration check

A separate four-second synthetic check, recorded in [the localization round-trip record](../../results/security/localization_roundtrip.json), sends 401 actual `robust_eskf` state outputs through the telemetry module. Every accepted payload is byte-identical after decryption, with zero change in decoded position. The position RMSE before and after transport is the same, 0.07791 m for that demonstration. Tampering at counter 123 is rejected without advancing the accepted watermark of 122; the authentic packet 123 is then accepted, and its replay is rejected. Serialized state payloads total 185,325 bytes and the corresponding wire packets total 325,844 bytes. This is an integration check with its own short scenario and seed, not an additional replicate in the localization study. It protects outgoing estimates and does not authenticate sensor ingress before fusion. Exact recovery demonstrates transport fidelity, not an accuracy gain from encryption.

# 8. Limitations and next empirical steps

The initial study uses one trajectory family, ideal synchronization, surveyed anchors without uncertainty, a zero lever arm, simplified independent sensor noise, prescribed positive ranging biases and a favorable warm start. These choices permit controlled debugging but restrict external validity. There is no vehicle dynamics, radio-channel or closed-loop flight-control model. No experiment supplied here establishes physical-UAV performance, energy use, or flight safety.

Subsequent evaluation should vary motion, anchor geometry, range quality, bias duration, outage length, initialization, timestamp error and calibration error. It should test longer outages and explicitly count reacquisition failures. Parameter tuning must use separate sessions or trajectories from those used for the final claims. Real-data work should implement the correct observation model for a selected dataset; for UTIL this means TDOA rather than relabeling a distance difference as a range [@zhao2024util]. An independent reference system and documented frame calibration are required for collected flights.

The current robustness rule does not model NLOS bias probabilistically and is vulnerable to plausible, slowly varying errors that remain below the gate. Hard rejection may also delay recovery after drift. Covariance inflation based on the same innovation used in the update complicates statistical consistency. Observability and NEES/NIS calibration require their own analyses, with the relevant selection effects and attitude-error convention accounted for.

The security component assumes provisioned session keys and trusted endpoints. Restart, rollback, bidirectional communication, key rotation and revocation need a deployment protocol. Authenticating a packet does not validate its contents as a physical measurement. These boundaries preclude claims of secure ranging or comprehensive UAV security.

# 9. Conclusion

This work specifies and implements a reproducible UWB/INS research baseline with a 15-dimensional error-state filter, explicit innovation-based range handling, common comparators, controlled synthetic data, and separately scoped authenticated telemetry. The artifact converts the supplied research outline into inspectable mathematical and software choices. On the configured synthetic trajectory, hard-gated methods reduce error under prescribed positive range biases, while an additional benefit from variance inflation over gating alone is not established. Telemetry tests demonstrate exact recovery of authenticated state payloads and rejection of the tested alterations and repeats. The evaluation must be read within the stated synthetic and protocol assumptions; it does not yet establish a novel algorithm, real-flight improvement, or deployment readiness. The next decisive steps are verified real-data adaptation, comparison with closely related methods, sensitivity analysis, and target-platform measurement.

# References
