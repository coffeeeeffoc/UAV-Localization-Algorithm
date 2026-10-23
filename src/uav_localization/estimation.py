"""15-state error-state EKF and declared sensor-only baselines.

The robust modes are engineering baselines based on innovation consistency,
not a novel NLOS classifier or an optimal adaptive covariance estimator.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .geometry import compose_quaternion, right_jacobian, skew

METHODS = ("uwb", "ins", "eskf", "gated_eskf", "adaptive_eskf", "robust_eskf")


@dataclass(frozen=True)
class FilterConfig:
    range_std_m: float = 0.08
    accel_std_mps2: float = 0.03
    gyro_std_radps: float = 0.001
    accel_bias_rw_mps2_sqrts: float = 0.0001
    gyro_bias_rw_radps_sqrts: float = 0.00002
    initial_position_std_m: float = 0.5
    initial_velocity_std_mps: float = 0.2
    initial_attitude_std_deg: float = 3.0
    initial_accel_bias_std_mps2: float = 0.1
    initial_gyro_bias_std_radps: float = 0.005
    soft_nis_threshold: float = 3.841458820694124
    hard_nis_threshold: float = 10.827566170662733
    max_variance_scale: float = 25.0

    def __post_init__(self):
        positive = (self.range_std_m, self.initial_position_std_m,
                    self.initial_velocity_std_mps, self.initial_attitude_std_deg,
                    self.initial_accel_bias_std_mps2, self.initial_gyro_bias_std_radps,
                    self.soft_nis_threshold, self.hard_nis_threshold)
        if not np.all(np.isfinite(positive)) or min(positive) <= 0:
            raise ValueError("Measurement, prior standard deviations and thresholds must be positive")
        noise = (self.accel_std_mps2, self.gyro_std_radps,
                 self.accel_bias_rw_mps2_sqrts, self.gyro_bias_rw_radps_sqrts)
        if not np.all(np.isfinite(noise)) or min(noise) < 0:
            raise ValueError("Process noise amplitudes must be finite and nonnegative")
        if self.hard_nis_threshold <= self.soft_nis_threshold:
            raise ValueError("Hard NIS threshold must exceed soft threshold")
        if not np.isfinite(self.max_variance_scale) or self.max_variance_scale < 1:
            raise ValueError("Maximum variance scale must be finite and >= 1")


@dataclass
class EstimationResult:
    t: np.ndarray
    position: np.ndarray
    velocity: np.ndarray
    quaternion: np.ndarray
    position_covariance: np.ndarray
    diagnostics: list
    accel_bias: np.ndarray
    gyro_bias: np.ndarray
    final_covariance: np.ndarray


def range_model(position, anchor):
    """Return distance and 1x15 Jacobian for a collocated tag (zero lever arm)."""
    delta = np.asarray(position, dtype=float) - np.asarray(anchor, dtype=float)
    distance = float(np.linalg.norm(delta))
    if distance <= 1e-10:
        raise ValueError("Range derivative undefined at an anchor")
    jacobian = np.zeros(15)
    jacobian[:3] = delta / distance
    return distance, jacobian


class ErrorStateEKF:
    """Nominal p, v, body-to-world q_xyzw, ba, bg; right local attitude error."""

    def __init__(self, position, velocity, quaternion, config=None):
        if config is None:
            config = FilterConfig()
        elif isinstance(config, dict):
            config = FilterConfig(**config)
        if not isinstance(config, FilterConfig):
            raise TypeError("config must be FilterConfig, dictionary, or None")
        self.config = config
        self.position = np.asarray(position, dtype=float).copy()
        self.velocity = np.asarray(velocity, dtype=float).copy()
        self.quaternion = Rotation.from_quat(quaternion).as_quat()
        if self.position.shape != (3,) or self.velocity.shape != (3,):
            raise ValueError("Initial position and velocity must be 3-vectors")
        if not np.all(np.isfinite(np.r_[self.position, self.velocity, self.quaternion])):
            raise ValueError("Initial state must be finite")
        self.accel_bias = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        standard_deviations = np.repeat([
            config.initial_position_std_m, config.initial_velocity_std_mps,
            np.deg2rad(config.initial_attitude_std_deg), config.initial_accel_bias_std_mps2,
            config.initial_gyro_bias_std_radps], 3)
        self.covariance = np.diag(standard_deviations**2)

    def predict(self, accel, gyro, dt):
        """Midpoint nominal integration; second-order frozen-F covariance transition."""
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("Prediction dt must be finite and positive")
        accel, gyro = np.asarray(accel), np.asarray(gyro)
        if accel.shape != (3,) or gyro.shape != (3,) or not np.all(np.isfinite(np.r_[accel, gyro])):
            raise ValueError("IMU inputs must be finite 3-vectors")
        force = accel - self.accel_bias
        omega = gyro - self.gyro_bias
        midpoint_q = compose_quaternion(self.quaternion, omega * dt / 2)
        rotation = Rotation.from_quat(midpoint_q).as_matrix()
        acceleration = rotation @ force + np.array([0.0, 0.0, -9.80665])
        self.position += self.velocity * dt + 0.5 * acceleration * dt**2
        self.velocity += acceleration * dt
        self.quaternion = compose_quaternion(self.quaternion, omega * dt)
        dynamics = np.zeros((15, 15))
        dynamics[:3, 3:6] = np.eye(3)
        dynamics[3:6, 6:9] = -rotation @ skew(force)
        dynamics[3:6, 9:12] = -rotation
        dynamics[6:9, 6:9] = -skew(omega)
        dynamics[6:9, 12:15] = -np.eye(3)
        fd = dynamics * dt
        transition = np.eye(15) + fd + 0.5 * fd @ fd
        # White IMU noise is a per-sample standard deviation. Bias noise is a
        # continuous random-walk amplitude, hence sqrt(dt), not dt.
        injection = np.zeros((15, 12))
        injection[:3, :3] = 0.5 * rotation * dt**2
        injection[3:6, :3] = rotation * dt
        injection[6:9, 3:6] = np.eye(3) * dt
        injection[9:12, 6:9] = np.eye(3) * np.sqrt(dt)
        injection[12:15, 9:12] = np.eye(3) * np.sqrt(dt)
        standard_deviations = np.repeat([
            self.config.accel_std_mps2, self.config.gyro_std_radps,
            self.config.accel_bias_rw_mps2_sqrts, self.config.gyro_bias_rw_radps_sqrts], 3)
        noise_map = injection * standard_deviations
        self.covariance = transition @ self.covariance @ transition.T + noise_map @ noise_map.T
        self.covariance = (self.covariance + self.covariance.T) / 2

    def update_range(self, measurement, anchor, method="eskf"):
        """Sequential scalar update. Gating uses nominal, pre-inflation NIS."""
        if method not in METHODS[2:]:
            raise ValueError("Range update requires an ESKF method")
        if not np.isfinite(measurement) or measurement <= 0:
            return {"innovation_m": float("nan"), "nominal_nis": float("nan"),
                    "effective_nis": float("nan"), "accepted": False,
                    "variance_scale": 1.0, "reason": "invalid_range"}
        try:
            prediction, h = range_model(self.position, anchor)
        except ValueError:
            return {"innovation_m": float("nan"), "nominal_nis": float("nan"),
                    "effective_nis": float("nan"), "accepted": False,
                    "variance_scale": 1.0, "reason": "singular_geometry"}
        innovation = float(measurement - prediction)
        base_variance = self.config.range_std_m**2
        ph = self.covariance @ h
        predicted_variance = float(h @ ph)
        nominal_nis = innovation**2 / (predicted_variance + base_variance)
        diagnostic = {"innovation_m": innovation, "nominal_nis": nominal_nis,
                      "effective_nis": nominal_nis, "accepted": True,
                      "variance_scale": 1.0, "reason": "accepted"}
        if method in ("gated_eskf", "robust_eskf") and nominal_nis > self.config.hard_nis_threshold:
            diagnostic.update(accepted=False, reason="nis_gate")
            return diagnostic
        variance_scale = 1.0
        if method in ("adaptive_eskf", "robust_eskf"):
            variance_scale = float(np.clip(nominal_nis / self.config.soft_nis_threshold,
                                          1.0, self.config.max_variance_scale))
        variance = base_variance * variance_scale
        innovation_variance = predicted_variance + variance
        gain = ph / innovation_variance
        correction = gain * innovation
        self.position += correction[:3]
        self.velocity += correction[3:6]
        self.quaternion = compose_quaternion(self.quaternion, correction[6:9])
        self.accel_bias += correction[9:12]
        self.gyro_bias += correction[12:15]
        residual_map = np.eye(15) - np.outer(gain, h)
        # Joseph form avoids the cancellation in (I-KH)P; the attitude reset is
        # required because the estimated local error has just been injected.
        covariance = (residual_map @ self.covariance @ residual_map.T
                      + variance * np.outer(gain, gain))
        reset = np.eye(15)
        reset[6:9, 6:9] = right_jacobian(correction[6:9])
        self.covariance = reset @ covariance @ reset.T
        self.covariance = (self.covariance + self.covariance.T) / 2
        diagnostic.update(variance_scale=variance_scale,
                          effective_nis=innovation**2 / innovation_variance)
        return diagnostic


def _validate_dataset(dataset):
    t = np.asarray(dataset.t)
    n = len(t)
    if t.ndim != 1 or n < 2 or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError("Dataset must have strictly increasing finite times")
    if dataset.accel.shape != (n - 1, 3) or dataset.gyro.shape != (n - 1, 3):
        raise ValueError("IMU measurements must have shape (len(t)-1, 3)")
    if not np.all(np.isfinite(dataset.accel)) or not np.all(np.isfinite(dataset.gyro)):
        raise ValueError("IMU measurements must be finite")
    if dataset.anchors.ndim != 2 or dataset.anchors.shape[1] != 3 or not np.all(np.isfinite(dataset.anchors)):
        raise ValueError("Anchors must be finite 3-D coordinates")
    if dataset.ranges.shape != (n, len(dataset.anchors)):
        raise ValueError("Range shape must be (len(t), number of anchors)")
    if np.any(np.isinf(dataset.ranges)):
        raise ValueError("Infinite ranges are invalid; represent missing data with NaN")


def run_estimator(dataset, method, config=None):
    """Run a method without accessing true states, labels, or scenario metadata.

    UWB-only has no prediction step: epochs without a position fix remain NaN.
    Its velocity, attitude and biases are unestimated and remain NaN throughout.
    """
    if method not in METHODS:
        raise ValueError(f"Unknown method {method!r}; choose from {METHODS}")
    if config is None:
        config = FilterConfig()
    elif isinstance(config, dict):
        config = FilterConfig(**config)
    if not isinstance(config, FilterConfig):
        raise TypeError("config must be FilterConfig, dictionary, or None")
    _validate_dataset(dataset)
    n = len(dataset.t)
    position = np.full((n, 3), np.nan)
    velocity = np.full((n, 3), np.nan)
    quaternion = np.full((n, 4), np.nan)
    position_covariance = np.full((n, 3, 3), np.nan)
    accel_bias = np.full((n, 3), np.nan)
    gyro_bias = np.full((n, 3), np.nan)
    diagnostics = []
    final_covariance = np.full((15, 15), np.nan)
    if method == "uwb":
        last_position = np.asarray(dataset.initial_position, dtype=float).copy()
        for k, ranges in enumerate(dataset.ranges):
            mask = np.isfinite(ranges) & (ranges > 0)
            if not mask.any():
                continue
            anchors, measurements = dataset.anchors[mask], ranges[mask]
            success = False
            if len(anchors) >= 4 and np.linalg.matrix_rank(anchors[1:] - anchors[0]) == 3:
                solution = least_squares(lambda p: np.linalg.norm(p - anchors, axis=1) - measurements,
                                         last_position, method="trf", max_nfev=100,
                                         ftol=1e-10, xtol=1e-10, gtol=1e-10)
                success = bool(solution.success and np.all(np.isfinite(solution.x)))
                if success:
                    position[k] = last_position = solution.x
                    information = solution.jac.T @ solution.jac
                    if np.linalg.matrix_rank(information) == 3:
                        position_covariance[k] = np.linalg.inv(information) * config.range_std_m**2
            diagnostics.append({"time_s": float(dataset.t[k]),
                                "available_ranges": int(mask.sum()), "success": success})
    else:
        estimator = ErrorStateEKF(dataset.initial_position, dataset.initial_velocity,
                                  dataset.initial_quaternion, config)
        for k, time in enumerate(dataset.t):
            if k:
                estimator.predict(dataset.accel[k - 1], dataset.gyro[k - 1],
                                  float(time - dataset.t[k - 1]))
            if method != "ins":
                for anchor_index in np.flatnonzero(np.isfinite(dataset.ranges[k])):
                    diagnostic = estimator.update_range(dataset.ranges[k, anchor_index],
                                                        dataset.anchors[anchor_index], method)
                    diagnostic.update(time_s=float(time), anchor=int(anchor_index))
                    diagnostics.append(diagnostic)
            position[k], velocity[k], quaternion[k] = (
                estimator.position, estimator.velocity, estimator.quaternion)
            position_covariance[k] = estimator.covariance[:3, :3]
            accel_bias[k], gyro_bias[k] = estimator.accel_bias, estimator.gyro_bias
        final_covariance = estimator.covariance.copy()
    return EstimationResult(dataset.t.copy(), position, velocity, quaternion,
                            position_covariance, diagnostics, accel_bias, gyro_bias, final_covariance)
