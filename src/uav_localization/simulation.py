"""Synthetic sensor data with explicit frame, noise, and initialization assumptions.

This is a kinematic sensor simulation, not a quadrotor dynamics or radio simulator.
The estimator receives body-frame specific force and angular velocity, never true
world-frame acceleration or the NLOS labels.
"""

from dataclasses import asdict, dataclass, field

import numpy as np
from scipy.spatial.transform import Rotation

from .geometry import compose_quaternion

SCENARIOS = ("los", "nlos", "dropout", "combined")


def _anchors():
    return ((0.0, 0.0, 0.3), (10.0, 0.0, 2.8), (10.0, 8.0, 0.3),
            (0.0, 8.0, 2.8), (5.0, 0.0, 2.8), (5.0, 8.0, 0.3))


@dataclass(frozen=True)
class SimulationConfig:
    duration_s: float = 30.0
    imu_rate_hz: float = 100.0
    uwb_rate_hz: float = 10.0
    range_std_m: float = 0.08
    accel_std_mps2: float = 0.03
    gyro_std_radps: float = 0.001
    accel_bias_rw_mps2_sqrts: float = 0.0001
    gyro_bias_rw_radps_sqrts: float = 0.00002
    accel_bias_mps2: tuple = (0.03, -0.02, 0.015)
    gyro_bias_radps: tuple = (0.0008, -0.0006, 0.0004)
    initial_position_error_m: tuple = (0.25, -0.20, 0.15)
    initial_velocity_error_mps: tuple = (0.03, -0.02, 0.02)
    initial_attitude_error_deg: tuple = (0.7, -0.5, 1.5)
    nlos_intervals_s: tuple = ((8.0, 14.0), (20.0, 24.0))
    nlos_anchor_groups: tuple = ((0, 1), (3,))
    nlos_bias_floor_m: float = 0.6
    nlos_bias_exponential_mean_m: float = 0.25
    dropout_interval_s: tuple = (15.0, 19.0)
    anchors_m: tuple = field(default_factory=_anchors)

    def __post_init__(self):
        scalars = (self.duration_s, self.imu_rate_hz, self.uwb_rate_hz)
        if not np.all(np.isfinite(scalars)) or min(scalars) <= 0:
            raise ValueError("Duration and sample rates must be finite and positive")
        ratio = self.imu_rate_hz / self.uwb_rate_hz
        if ratio < 1 or not np.isclose(ratio, round(ratio), atol=1e-10, rtol=0):
            raise ValueError("IMU rate must be an integer multiple of UWB rate")
        n_steps = self.duration_s * self.imu_rate_hz
        if not np.isclose(n_steps, round(n_steps), atol=1e-8, rtol=0):
            raise ValueError("Duration must contain an integer number of IMU intervals")
        noises = (self.range_std_m, self.accel_std_mps2, self.gyro_std_radps,
                  self.accel_bias_rw_mps2_sqrts, self.gyro_bias_rw_radps_sqrts,
                  self.nlos_bias_floor_m, self.nlos_bias_exponential_mean_m)
        if not np.all(np.isfinite(noises)) or min(noises) < 0:
            raise ValueError("Noise and bias amplitudes must be finite and nonnegative")
        anchors = np.asarray(self.anchors_m, dtype=float)
        if anchors.ndim != 2 or anchors.shape[1] != 3 or anchors.shape[0] < 4:
            raise ValueError("At least four 3-D anchors are required")
        if not np.all(np.isfinite(anchors)) or np.linalg.matrix_rank(anchors[1:] - anchors[0]) < 3:
            raise ValueError("Anchors must be finite and non-coplanar")
        if len(self.nlos_intervals_s) != len(self.nlos_anchor_groups):
            raise ValueError("Each NLOS interval needs an anchor group")
        for start, end in (*self.nlos_intervals_s, self.dropout_interval_s):
            if not np.isfinite(start + end) or start < 0 or end <= start:
                raise ValueError("Corruption intervals must have 0 <= start < end")
        for group in self.nlos_anchor_groups:
            if any(int(index) != index or not 0 <= index < len(anchors) for index in group):
                raise ValueError("NLOS anchor index out of range")
        for vector in (self.accel_bias_mps2, self.gyro_bias_radps,
                       self.initial_position_error_m, self.initial_velocity_error_mps,
                       self.initial_attitude_error_deg):
            if np.shape(vector) != (3,) or not np.all(np.isfinite(vector)):
                raise ValueError("Bias and initialization vectors must be finite 3-vectors")


@dataclass
class Dataset:
    t: np.ndarray
    position: np.ndarray
    velocity: np.ndarray
    quaternion: np.ndarray
    accel: np.ndarray
    gyro: np.ndarray
    ranges: np.ndarray
    anchors: np.ndarray
    nlos_mask: np.ndarray
    initial_position: np.ndarray
    initial_velocity: np.ndarray
    initial_quaternion: np.ndarray
    metadata: dict


def trajectory(t):
    """Analytic 3-D position, velocity, acceleration and body-to-world rotation."""
    t = np.asarray(t, dtype=float)
    position = np.column_stack((5 + 2 * np.sin(0.28 * t),
                                4 + 1.5 * np.sin(0.41 * t + 0.3),
                                1.5 + 0.3 * np.sin(0.33 * t)))
    velocity = np.column_stack((0.56 * np.cos(0.28 * t),
                                0.615 * np.cos(0.41 * t + 0.3),
                                0.099 * np.cos(0.33 * t)))
    acceleration = np.column_stack((-0.1568 * np.sin(0.28 * t),
                                    -0.25215 * np.sin(0.41 * t + 0.3),
                                    -0.03267 * np.sin(0.33 * t)))
    angles = np.column_stack((0.06 * np.sin(0.37 * t),
                              0.05 * np.sin(0.29 * t + 0.2),
                              0.25 * np.sin(0.18 * t) + 0.08 * t))
    rotation = Rotation.from_euler("xyz", angles)
    return position, velocity, acceleration, rotation


def simulate(config=None, seed=0, scenario="los"):
    """Generate paired-scenario data with independent reproducible RNG streams.

    IMU element k describes [t[k], t[k+1]]; ranges[k] is observed at t[k].
    Bias random walks have amplitude per sqrt(second); white IMU standard
    deviations are per sample, not noise density. Initial values are a declared
    warm start: true initial state plus fixed errors, not a solved initializer.
    """
    if config is None:
        config = SimulationConfig()
    elif isinstance(config, dict):
        config = SimulationConfig(**config)
    if not isinstance(config, SimulationConfig):
        raise TypeError("config must be SimulationConfig, a dictionary, or None")
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; choose from {SCENARIOS}")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    accel_rng, gyro_rng, bias_rng, range_rng, nlos_rng = [
        np.random.default_rng(child) for child in np.random.SeedSequence(seed).spawn(5)]
    count = round(config.duration_s * config.imu_rate_hz)
    dt = 1 / config.imu_rate_hz
    t = np.arange(count + 1, dtype=float) * dt
    position, velocity, _, rotation = trajectory(t)
    _, _, acceleration_mid, _ = trajectory(t[:-1] + dt / 2)
    relative = rotation[:-1].inv() * rotation[1:]
    increments = relative.as_rotvec()
    rotation_mid = rotation[:-1] * Rotation.from_rotvec(increments / 2)
    gravity = np.array([0.0, 0.0, -9.80665])
    specific_force = rotation_mid.inv().apply(acceleration_mid - gravity)
    accel_bias = np.tile(np.asarray(config.accel_bias_mps2, dtype=float), (count, 1))
    gyro_bias = np.tile(np.asarray(config.gyro_bias_radps, dtype=float), (count, 1))
    if count > 1:
        accel_bias[1:] += np.cumsum(bias_rng.normal(size=(count - 1, 3))
                                   * config.accel_bias_rw_mps2_sqrts * np.sqrt(dt), axis=0)
        gyro_bias[1:] += np.cumsum(bias_rng.normal(size=(count - 1, 3))
                                  * config.gyro_bias_rw_radps_sqrts * np.sqrt(dt), axis=0)
    accel = specific_force + accel_bias + accel_rng.normal(size=(count, 3)) * config.accel_std_mps2
    gyro = increments / dt + gyro_bias + gyro_rng.normal(size=(count, 3)) * config.gyro_std_radps
    anchors = np.asarray(config.anchors_m, dtype=float)
    stride = round(config.imu_rate_hz / config.uwb_rate_hz)
    epochs = np.arange(0, count + 1, stride)
    ranges = np.full((count + 1, len(anchors)), np.nan)
    ranges[epochs] = (np.linalg.norm(position[epochs, None, :] - anchors[None, :, :], axis=2)
                      + range_rng.normal(size=(len(epochs), len(anchors))) * config.range_std_m)
    nlos_mask = np.zeros(ranges.shape, dtype=bool)
    if scenario in ("nlos", "combined"):
        for (start, end), group in zip(config.nlos_intervals_s, config.nlos_anchor_groups):
            affected = epochs[(t[epochs] >= start) & (t[epochs] < end)]
            for anchor in group:
                nlos_mask[affected, anchor] = True
                ranges[affected, anchor] += (config.nlos_bias_floor_m + nlos_rng.exponential(
                    config.nlos_bias_exponential_mean_m, size=len(affected)))
    if scenario in ("dropout", "combined"):
        start, end = config.dropout_interval_s
        missing = (t >= start) & (t < end)
        ranges[missing] = np.nan
        nlos_mask[missing] = False
    metadata = {"data_kind": "synthetic", "seed": int(seed), "scenario": scenario,
                "config": asdict(config), "frame": "ENU; body-to-world quaternion xyzw",
                "gravity_mps2": gravity.tolist(),
                "initialization": "true initial state plus fixed configured errors (warm-start assumption)",
                "imu_timing": "sample k is interval-average at midpoint of [t[k], t[k+1]]",
                "uwb_timing": "synchronous range epochs at t[k]; NaN means no measurement"}
    return Dataset(t=t, position=position, velocity=velocity, quaternion=rotation.as_quat(),
                   accel=accel, gyro=gyro, ranges=ranges, anchors=anchors, nlos_mask=nlos_mask,
                   initial_position=position[0] + np.asarray(config.initial_position_error_m),
                   initial_velocity=velocity[0] + np.asarray(config.initial_velocity_error_mps),
                   initial_quaternion=compose_quaternion(rotation[0].as_quat(),
                                                         np.deg2rad(config.initial_attitude_error_deg)),
                   metadata=metadata)
