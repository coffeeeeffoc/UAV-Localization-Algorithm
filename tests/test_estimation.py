"""Numerical invariants, model consistency and information-boundary tests."""

from dataclasses import replace
from types import SimpleNamespace
import unittest

import numpy as np
from scipy.spatial.transform import Rotation

from uav_localization.estimation import ErrorStateEKF, FilterConfig, range_model, run_estimator
from uav_localization.geometry import right_jacobian, skew
from uav_localization.simulation import SimulationConfig, simulate


class GeometryTests(unittest.TestCase):
    def test_skew_cross_product(self):
        a, b = np.array([1., 2., -3.]), np.array([-2., 1., 4.])
        np.testing.assert_allclose(skew(a) @ b, np.cross(a, b))

    def test_range_jacobian_finite_difference(self):
        position, anchor = np.array([2., 3., 1.]), np.array([-1., 1., 4.])
        _, h = range_model(position, anchor)
        eps = 1e-6
        numeric = np.array([(range_model(position + eps * axis, anchor)[0]
                             - range_model(position - eps * axis, anchor)[0]) / (2 * eps)
                            for axis in np.eye(3)])
        np.testing.assert_allclose(h[:3], numeric, atol=1e-8)
        np.testing.assert_array_equal(h[3:], np.zeros(12))

    def test_attitude_reset_jacobian_finite_difference(self):
        correction = np.array([0.2, -0.3, 0.1])
        eps = 1e-7
        baseline_inverse = Rotation.from_rotvec(correction).inv()
        columns = []
        for axis in np.eye(3):
            plus = (baseline_inverse * Rotation.from_rotvec(correction + eps * axis)).as_rotvec()
            minus = (baseline_inverse * Rotation.from_rotvec(correction - eps * axis)).as_rotvec()
            columns.append((plus - minus) / (2 * eps))
        np.testing.assert_allclose(right_jacobian(correction), np.column_stack(columns), atol=1e-8)


class MechanizationTests(unittest.TestCase):
    def test_stationary_specific_force_cancels_gravity(self):
        estimator = ErrorStateEKF([1, 2, 3], [0, 0, 0], [0, 0, 0, 1])
        for _ in range(100):
            estimator.predict([0, 0, 9.80665], [0, 0, 0], 0.01)
        np.testing.assert_allclose(estimator.position, [1, 2, 3], atol=1e-12)
        np.testing.assert_allclose(estimator.velocity, 0, atol=1e-12)

    def test_rotation_is_body_to_world_and_unit_length(self):
        estimator = ErrorStateEKF([0, 0, 0], [0, 0, 0], [0, 0, 0, 1])
        for _ in range(100):
            estimator.predict([0, 0, 0], [0, 0, np.pi / 2], 0.01)
        np.testing.assert_allclose(Rotation.from_quat(estimator.quaternion).apply([1, 0, 0]),
                                   [0, 1, 0], atol=1e-12)
        self.assertAlmostEqual(np.linalg.norm(estimator.quaternion), 1.0, places=14)

    def test_noise_units_and_position_velocity_cross_covariance(self):
        config = FilterConfig(accel_std_mps2=0.2, gyro_std_radps=0.0,
                              accel_bias_rw_mps2_sqrts=0.03, gyro_bias_rw_radps_sqrts=0.0)
        estimator = ErrorStateEKF([0, 0, 0], [0, 0, 0], [0, 0, 0, 1], config)
        estimator.covariance[:] = 0.0
        dt = 0.05
        estimator.predict([0, 0, 0], [0, 0, 0], dt)
        self.assertAlmostEqual(estimator.covariance[3, 3], 0.2**2 * dt**2)
        self.assertAlmostEqual(estimator.covariance[0, 0], 0.25 * 0.2**2 * dt**4)
        self.assertAlmostEqual(estimator.covariance[0, 3], 0.5 * 0.2**2 * dt**3)
        self.assertAlmostEqual(estimator.covariance[9, 9], 0.03**2 * dt)

    def test_noise_free_consistent_trajectory(self):
        dataset = simulate(SimulationConfig(
            duration_s=3.0, accel_std_mps2=0, gyro_std_radps=0,
            accel_bias_rw_mps2_sqrts=0, gyro_bias_rw_radps_sqrts=0,
            accel_bias_mps2=(0, 0, 0), gyro_bias_radps=(0, 0, 0),
            initial_position_error_m=(0, 0, 0), initial_velocity_error_mps=(0, 0, 0),
            initial_attitude_error_deg=(0, 0, 0)))
        result = run_estimator(dataset, "ins")
        self.assertLess(np.max(np.linalg.norm(result.position - dataset.position, axis=1)), 2e-5)
        attitude_error = (Rotation.from_quat(result.quaternion).inv()
                          * Rotation.from_quat(dataset.quaternion)).magnitude()
        self.assertLess(np.max(attitude_error), 1e-12)


class FilterTests(unittest.TestCase):
    def test_gate_rejects_without_changing_state_or_covariance(self):
        estimator = ErrorStateEKF([2, 2, 1], [0, 0, 0], [0, 0, 0, 1])
        p, covariance = estimator.position.copy(), estimator.covariance.copy()
        info = estimator.update_range(100., [0, 0, 0], "robust_eskf")
        self.assertFalse(info["accepted"])
        self.assertEqual(info["reason"], "nis_gate")
        np.testing.assert_array_equal(estimator.position, p)
        np.testing.assert_array_equal(estimator.covariance, covariance)

    def test_inflation_is_bounded(self):
        estimator = ErrorStateEKF([2, 2, 1], [0, 0, 0], [0, 0, 0, 1])
        info = estimator.update_range(100., [0, 0, 0], "adaptive_eskf")
        self.assertTrue(info["accepted"])
        self.assertEqual(info["variance_scale"], estimator.config.max_variance_scale)
        self.assertLess(info["effective_nis"], info["nominal_nis"])

    def test_covariance_psd_and_quaternion_norm_after_updates(self):
        dataset = simulate({"duration_s": 2.0}, seed=6)
        estimator = ErrorStateEKF(dataset.initial_position, dataset.initial_velocity,
                                  dataset.initial_quaternion)
        for k, time in enumerate(dataset.t):
            if k:
                estimator.predict(dataset.accel[k-1], dataset.gyro[k-1], time - dataset.t[k-1])
            for index in np.flatnonzero(np.isfinite(dataset.ranges[k])):
                estimator.update_range(dataset.ranges[k, index], dataset.anchors[index], "robust_eskf")
            self.assertLess(np.max(np.abs(estimator.covariance - estimator.covariance.T)), 1e-12)
            self.assertGreaterEqual(np.linalg.eigvalsh(estimator.covariance).min(), -1e-12)
            self.assertAlmostEqual(np.linalg.norm(estimator.quaternion), 1.0, places=12)

    def test_estimator_never_reads_ground_truth_or_nlos_labels(self):
        dataset = simulate({"duration_s": 0.2})
        observable = SimpleNamespace(**{name: getattr(dataset, name) for name in (
            "t", "accel", "gyro", "anchors", "ranges", "initial_position",
            "initial_velocity", "initial_quaternion")})
        expected = run_estimator(dataset, "robust_eskf")
        actual = run_estimator(observable, "robust_eskf")
        np.testing.assert_array_equal(actual.position, expected.position)

    def test_uwb_does_not_impute_missing_positions(self):
        dataset = simulate({"duration_s": 2.0, "dropout_interval_s": (0.5, 1.5)}, scenario="dropout")
        result = run_estimator(dataset, "uwb")
        unavailable = ~np.isfinite(dataset.ranges).any(axis=1)
        self.assertTrue(np.isnan(result.position[unavailable]).all())
        self.assertTrue(np.isfinite(result.position[~unavailable]).all())
        self.assertTrue(np.isnan(result.velocity).all())


class SimulationTests(unittest.TestCase):
    def test_seed_reproducibility_and_scenario_pairing(self):
        config = SimulationConfig(duration_s=2., nlos_intervals_s=((0.5, 1.5),),
                                  nlos_anchor_groups=((0, 1),))
        los = simulate(config, seed=7, scenario="los")
        duplicate = simulate(config, seed=7, scenario="los")
        nlos = simulate(config, seed=7, scenario="nlos")
        np.testing.assert_array_equal(los.ranges, duplicate.ranges)
        np.testing.assert_array_equal(los.accel, nlos.accel)
        np.testing.assert_array_equal(los.gyro, nlos.gyro)
        np.testing.assert_array_equal(los.ranges[~nlos.nlos_mask], nlos.ranges[~nlos.nlos_mask])
        self.assertTrue(np.all(nlos.ranges[nlos.nlos_mask] - los.ranges[nlos.nlos_mask]
                               >= config.nlos_bias_floor_m))

    def test_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):
            SimulationConfig(imu_rate_hz=99, uwb_rate_hz=10)
        with self.assertRaises(ValueError):
            SimulationConfig(range_std_m=-1)
        with self.assertRaises(ValueError):
            replace(SimulationConfig(), anchors_m=((0,0,0),(1,0,0),(0,1,0),(1,1,0)))
        with self.assertRaises(ValueError):
            FilterConfig(max_variance_scale=0.5)


if __name__ == "__main__":
    unittest.main()
