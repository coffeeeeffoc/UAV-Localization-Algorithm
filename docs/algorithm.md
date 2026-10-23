# Implemented estimation model and assumptions

This document specifies the implementation in `src/uav_localization/estimation.py`
and the synthetic generator in `src/uav_localization/simulation.py`. It is a
research baseline, not a certified flight estimator. Standard ESKF, innovation
gating, and bounded variance inflation are not claimed as new algorithms.

## Frames, state, and observations

The world frame is a local right-handed ENU frame. Position is in metres, velocity
in metres per second, angular velocity in radians per second, and timestamps in
seconds. Gravity is fixed at $g=[0,0,-9.80665]^T\ \mathrm{m/s^2}$. The rotation
$R(q)$ maps body vectors to world vectors; stored quaternions are **xyzw** and are
normalized by SciPy's rotation operations.

The nominal state is $(p,v,q,b_a,b_g)$ and the local error state is

$$\delta x=[\delta p^T,\delta v^T,\delta\theta^T,\delta b_a^T,\delta b_g^T]^T
\in\mathbb R^{15},\qquad R_{\rm true}=R(q)\operatorname{Exp}([\delta\theta]_\times).$$

The IMU reports body-frame specific force and body angular velocity:

$$a_m=R^T(\ddot p-g)+b_a+n_a,\qquad \omega_m=\omega+b_g+n_g.$$

The UWB tag is assumed to coincide with the IMU origin. Each anchor $a_i$ is
known exactly and produces an independently perturbed synchronous range:

$$z_i=\|p-a_i\|+b_i^{\rm NLOS}+\epsilon_i,\qquad
\epsilon_i\sim\mathcal N(0,\sigma_r^2).$$

This implementation estimates neither anchor positions, lever arms, timing
offsets, gravity, nor a per-anchor NLOS bias. These omissions must be revisited
for real flights. Encryption cannot make the physical range measurement truthful.

## Nominal propagation and covariance

One IMU sample describes interval $[t_k,t_{k+1}]$ and is generated at its midpoint.
Let $\Delta t=t_{k+1}-t_k$, $f=a_m-\hat b_a$, and $w=\omega_m-\hat b_g$. The
implementation computes

$$q_{1/2}=q_k\otimes\operatorname{Exp}(w\Delta t/2),\quad
\hat a=R(q_{1/2})f+g,$$

$$p_{k+1}=p_k+v_k\Delta t+\tfrac12\hat a\Delta t^2,\quad
v_{k+1}=v_k+\hat a\Delta t,\quad
q_{k+1}=q_k\otimes\operatorname{Exp}(w\Delta t).$$

Nominal biases remain constant during prediction. With $R=R(q_{1/2})$, the
nonzero continuous error-transition blocks are

$$F_{pv}=I,\quad F_{v\theta}=-R[f]_\times,\quad F_{vb_a}=-R,
\quad F_{\theta\theta}=-[w]_\times,\quad F_{\theta b_g}=-I.$$

The frozen-coefficient transition is approximated by
$\Phi=I+F\Delta t+\tfrac12(F\Delta t)^2$. Covariance propagation is
$P^-=\Phi P\Phi^T+Q_d$.

Noise units are deliberately explicit. `accel_std_mps2` and `gyro_std_radps` are
**per-sample standard deviations**, not continuous noise densities. Bias random
walk amplitudes have units $(\mathrm{m/s^2})/\sqrt{\mathrm{s}}$ and
$(\mathrm{rad/s})/\sqrt{\mathrm{s}}$. Set

$$D=\operatorname{diag}(\sigma_a^2 I,\sigma_g^2 I,
\sigma_{b_a}^2 I,\sigma_{b_g}^2 I),\qquad Q_d=G_d D G_d^T,$$

where the nonzero blocks of $G_d$ are

$$G_{p,n_a}=\tfrac12R\Delta t^2,\quad G_{v,n_a}=R\Delta t,\quad
G_{\theta,n_g}=I\Delta t,\quad G_{b_a,n_{b_a}}=I\sqrt{\Delta t},\quad
G_{b_g,n_{b_g}}=I\sqrt{\Delta t}.$$

This retains the acceleration-induced position/velocity covariance and is
positive semidefinite by construction. It is a small-step approximation, not an
exact continuous-time Van Loan discretization. Higher-order coupling of gyro
noise into translation and of within-step bias noise into other states is
omitted. Reported covariance should therefore be checked by consistency
experiments before using it for safety decisions. Changing the sample rate while
holding a per-sample noise standard deviation fixed changes its implied noise
density; sensor-rate comparisons require an explicit noise conversion.

## Range update, gating, and inflation

Ranges at an epoch are processed sequentially in ascending anchor-index order,
relinearizing after every accepted measurement. For a nonzero predicted range,

$$h_i=\|p-a_i\|,\qquad
H_i=[(p-a_i)^T/h_i,\ 0_{1\times12}],\quad
\nu_i=z_i-h_i,$$

$$R_0=\sigma_r^2,\quad S_0=H_iP^-H_i^T+R_0,\quad
\eta_i=\nu_i^2/S_0.$$

`nominal_nis` records $\eta_i$ **before** any gate or variance inflation. Under
an appropriate linearized Gaussian model it is compared with nominal
one-degree-of-freedom chi-square thresholds. These are reference thresholds,
not a proven NLOS classification false-alarm rate for this nonlinear,
sequential, contaminated system.

| Method | Rule |
| --- | --- |
| `eskf` | Use $R_0$, without gating. |
| `gated_eskf` | Reject if $\eta_i>\tau_h$; otherwise use $R_0$. |
| `adaptive_eskf` | Use $R_i=R_0\min(c_{\max},\max(1,\eta_i/\tau_s))$; no gate. |
| `robust_eskf` | Apply the hard gate first; inflate the variance of retained ranges with the same formula. |

Defaults are $\tau_s=3.841458820694124$ (nominal 95th percentile),
$\tau_h=10.827566170662733$ (nominal 99.9th percentile), and $c_{\max}=25$.
Because gating happens first, the default `robust_eskf` can inflate an accepted
measurement by at most $\tau_h/\tau_s\simeq2.8186$. The factor-25 cap is relevant
to `adaptive_eskf`; it is not reached by accepted default robust updates.

The rule inflates variance for a currently inconsistent measurement, without
learning a physical NLOS probability or subtracting a known bias. It has no
EWMA, oracle NLOS label, fitted covariance optimizer, or guarantee against
slowly varying, coordinated, or covariance-masked outliers. Gating may reject
valid data during initialization or recovery from a long outage; all-rejected
epochs become inertial propagation. There is no automatic reinitialization.

For accepted measurements,

$$S=H_iP^-H_i^T+R_i,\quad K=P^-H_i^T/S,\quad \widehat{\delta x}=K\nu_i.$$

Add the position, velocity, and bias corrections to their nominal states, and
inject the attitude error on the right:
$q^+=q^-\otimes\operatorname{Exp}(\widehat{\delta\theta})$. The covariance uses
Joseph form and a tangent-space reset:

$$\widetilde P=(I-KH_i)P^-(I-KH_i)^T+KR_iK^T,\qquad
P^+=J\widetilde P J^T,$$

where $J$ is identity except $J_{\theta\theta}=J_r(\widehat{\delta\theta})$,
the SO(3) right Jacobian. For $u=\widehat{\delta\theta}$ and $\alpha=\|u\|$,

$$J_r(u)=I-\frac{1-\cos\alpha}{\alpha^2}[u]_\times+
\frac{\alpha-\sin\alpha}{\alpha^3}[u]_\times^2.$$

A small-angle series is used near zero. Covariance is symmetrized after
prediction and update. Numerical tests check positive semidefiniteness; the
implementation does not clip eigenvalues to hide failures.

## Sensor-only baselines and evaluation boundaries

`ins` uses the same propagation and initial conditions but never updates from
ranges. It starts with zero estimated biases. It is a deliberately unaided INS,
so long-term drift should not be interpreted as an unexpected finding.

`uwb` solves unweighted nonlinear least squares independently at each available
range epoch, initialized from the preceding position solution. At least four
non-coplanar available anchors are required. No temporal prediction, imputation,
or trajectory smoothing is applied. A missing fix is represented by `NaN`;
velocity, attitude, and biases are unestimated. Its covariance is the local
LOS approximation $\sigma_r^2(J^TJ)^{-1}$, not a calibrated NLOS uncertainty.

Position-error comparisons across all methods should use common range epochs
and report coverage separately. Fusion/INS also permit a full-rate error metric.
Do not compare a sparse UWB error statistic directly with a dense full-rate
statistic without labeling the different evaluation grids.

## Synthetic data and declared default configuration

The fixed trajectory is

$$p(t)=\begin{bmatrix}5+2\sin(0.28t)\\4+1.5\sin(0.41t+0.3)\\1.5+0.3\sin(0.33t)\end{bmatrix}.$$

Velocity and acceleration are analytic derivatives. Roll, pitch, and yaw are
$0.06\sin(0.37t)$, $0.05\sin(0.29t+0.2)$, and
$0.25\sin(0.18t)+0.08t$, respectively, in radians with SciPy extrinsic `xyz`
composition. Body rates are interval rotation increments divided by the interval
duration. Midpoint specific force uses the same interpolated orientation as the
nominal mechanization. This is an internally consistent **kinematic** sensor
model; it does not enforce a quadrotor's thrust, actuator, aerodynamic, or
closed-loop flight dynamics.

| Quantity | Default |
| --- | --- |
| Duration; IMU rate; UWB rate | 30 s; 100 Hz; 10 Hz |
| Range white noise | 0.08 m per measurement |
| Accelerometer; gyro white noise | 0.03 m/s²; 0.001 rad/s per sample |
| Accelerometer; gyro bias RW | 0.0001 (m/s²)/√s; 0.00002 (rad/s)/√s |
| Initial true accelerometer bias | (0.03, −0.02, 0.015) m/s² |
| Initial true gyro bias | (0.0008, −0.0006, 0.0004) rad/s |
| Initial position error | (0.25, −0.20, 0.15) m |
| Initial velocity error | (0.03, −0.02, 0.02) m/s |
| Initial right attitude error vector | (0.7, −0.5, 1.5) degrees |
| Prior position; velocity standard deviation | 0.5 m; 0.2 m/s per axis |
| Prior attitude standard deviation | 3 degrees per axis |
| Prior accelerometer; gyro bias standard deviation | 0.1 m/s²; 0.005 rad/s per axis |

Anchors, in metres, are `(0,0,0.3)`, `(10,0,2.8)`, `(10,8,0.3)`,
`(0,8,2.8)`, `(5,0,2.8)`, and `(5,8,0.3)`. They are deliberately non-coplanar;
observability and poor-geometry stress tests remain future work.

The `los` scenario includes only the nominal noise. `nlos` adds
$0.6+\operatorname{Exponential}(\text{mean}=0.25)$ metres to anchors 0 and 1
on $[8,14)$ seconds and anchor 3 on $[20,24)$ seconds. The exponential component
is independently resampled at affected range epochs; only the occurrence window
is temporally persistent. This is a stylized contamination model, not measured
indoor propagation. `dropout` removes all ranges on $[15,19)$ seconds;
`combined` includes both corruptions. The API accepts different windows and
amplitudes for sensitivity studies.

All methods use a **warm-start assumption**: the synthetic true initial state
plus fixed configured errors supplies the initial position, velocity, and
attitude. Those initial conditions model an external initialization procedure;
no such real-data procedure is implemented or validated. The estimator never
reads the true trajectory, corruption mask, or scenario name. Truth is used only
by the generator and evaluator. There is no per-seed tuning of initial values.

Independent random streams separate accelerometer noise, gyro noise, bias random
walks, nominal ranges, and NLOS bias. Identical seeds share the nominal sensor
noise across scenarios, enabling paired comparisons. Ten noise seeds still
represent **one trajectory and one anchor layout**; they do not establish
performance across buildings, flight dynamics, or independent real deployments.

## Verification

`tests/test_estimation.py` checks range and attitude-reset Jacobians by finite
differences, stationary gravity cancellation, quaternion direction and norm,
per-sample versus random-walk noise scaling, positive semidefinite covariance,
noise-free trajectory consistency, deterministic scenario pairing, gate behavior,
variance bounds, missing-data semantics, and absence of estimator access to
truth or NLOS labels. Tests establish implementation properties, not scientific
superiority or flight safety. Statistical consistency, sensitivity, calibration,
real data, and embedded timing are separate validation tasks.
