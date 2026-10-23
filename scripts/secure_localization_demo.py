#!/usr/bin/env python3
"""Send a synthetic robust-ESKF trajectory through authenticated telemetry.

Output records provenance and checks, never keys or ciphertext packets.
Encryption is applied after estimation and cannot improve localization accuracy.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

import cryptography
import numpy as np
import scipy

from uav_localization.estimation import FilterConfig, run_estimator
from uav_localization.security import (
    AuthenticationError, ReplayError, SessionSecrets, TelemetryReceiver, TelemetrySender,
)
from uav_localization.simulation import SimulationConfig, simulate


def encode_state(result, index):
    state = {
        "schema_version": 1,
        "t_s": float(result.t[index]),
        "position_m": result.position[index].tolist(),
        "velocity_mps": result.velocity[index].tolist(),
        "quaternion_xyzw_body_to_enu": result.quaternion[index].tolist(),
        "accel_bias_mps2": result.accel_bias[index].tolist(),
        "gyro_bias_radps": result.gyro_bias[index].tolist(),
    }
    return json.dumps(state, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def update_stream_hash(digest, payload):
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("results/security/localization_roundtrip.json"))
    parser.add_argument("--seed", type=int, default=20261023)
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("seed must be nonnegative")

    simulation_config = SimulationConfig(
        duration_s=4.0, imu_rate_hz=100.0, uwb_rate_hz=10.0,
        nlos_intervals_s=((1.0, 2.0),), nlos_anchor_groups=((0, 1),),
        dropout_interval_s=(2.5, 3.0),
    )
    filter_config = FilterConfig()
    dataset = simulate(simulation_config, seed=args.seed, scenario="combined")
    estimate = run_estimator(dataset, "robust_eskf", filter_config)
    session = SessionSecrets.generate("localization-demo-uav")
    sender, receiver = TelemetrySender(session), TelemetryReceiver(session)
    sent_digest, received_digest = hashlib.sha256(), hashlib.sha256()
    payload_lengths, packet_lengths, recovered_positions = [], [], []
    attacks = {}
    attack_index = 123

    for index in range(len(estimate.t)):
        payload = encode_state(estimate, index)
        packet = sender.seal(payload, message_type="localization_state")
        if index == attack_index:
            envelope = json.loads(packet)
            ciphertext_and_tag = bytearray(base64.b64decode(envelope["ciphertext"]))
            ciphertext_and_tag[0] ^= 1
            envelope["ciphertext"] = base64.b64encode(ciphertext_and_tag).decode("ascii")
            tampered = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")
            before = receiver.highest_counter
            try:
                receiver.open(tampered)
            except AuthenticationError:
                pass
            else:
                raise AssertionError("Tampered state was accepted")
            if receiver.highest_counter != before:
                raise AssertionError("Tampering advanced the replay watermark")
            attacks["tampering_before_valid_packet"] = {
                "counter": index, "rejected": True, "watermark_before": before,
                "watermark_after_rejection": receiver.highest_counter,
                "watermark_unchanged": True,
            }

        opened = receiver.open(packet)
        if opened.counter != index or opened.message_type != "localization_state":
            raise AssertionError("Authenticated routing metadata changed")
        if opened.payload != payload:
            raise AssertionError("Payload did not survive encryption byte for byte")
        recovered = json.loads(opened.payload)
        recovered_positions.append(recovered["position_m"])
        expected_vectors = {
            "position_m": estimate.position[index], "velocity_mps": estimate.velocity[index],
            "quaternion_xyzw_body_to_enu": estimate.quaternion[index],
            "accel_bias_mps2": estimate.accel_bias[index], "gyro_bias_radps": estimate.gyro_bias[index],
        }
        if recovered["t_s"] != float(estimate.t[index]):
            raise AssertionError("State time changed during JSON round-trip")
        for name, expected in expected_vectors.items():
            if not np.array_equal(np.asarray(recovered[name]), expected):
                raise AssertionError(f"State component changed: {name}")
        update_stream_hash(sent_digest, payload)
        update_stream_hash(received_digest, opened.payload)
        payload_lengths.append(len(payload))
        packet_lengths.append(len(packet))

        if index == attack_index:
            attacks["tampering_before_valid_packet"]["original_packet_accepted_after_rejection"] = True
            before = receiver.highest_counter
            try:
                receiver.open(packet)
            except ReplayError:
                pass
            else:
                raise AssertionError("Replayed state was accepted")
            if receiver.highest_counter != before:
                raise AssertionError("Replay changed the watermark")
            attacks["replay_after_valid_packet"] = {
                "counter": index, "rejected": True, "watermark_unchanged": True,
            }

    recovered_positions = np.asarray(recovered_positions)
    direct_errors = np.linalg.norm(estimate.position - dataset.position, axis=1)
    recovered_errors = np.linalg.norm(recovered_positions - dataset.position, axis=1)
    if not np.array_equal(direct_errors, recovered_errors):
        raise AssertionError("Post-encryption localization errors differ")
    payload_total, wire_total = sum(payload_lengths), sum(packet_lengths)
    count = len(estimate.t)
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__).resolve(), root / "src/uav_localization/security.py",
               root / "src/uav_localization/simulation.py", root / "src/uav_localization/estimation.py",
               root / "src/uav_localization/geometry.py"]
    report = {
        "schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_type": "synthetic_estimation_to_authenticated_telemetry_integration_demo",
        "pipeline": "simulate -> robust_eskf -> JSON state -> AES-256-GCM -> replay check -> JSON state",
        "seed": args.seed, "scenario": "combined", "method": "robust_eskf",
        "simulation_config": asdict(simulation_config), "filter_config": asdict(filter_config),
        "dataset_metadata": dataset.metadata,
        "sensor_counts": {
            "imu_intervals": len(dataset.accel), "finite_ranges": int(np.isfinite(dataset.ranges).sum()),
            "nlos_ranges": int(dataset.nlos_mask.sum()),
        },
        "telemetry": {
            "state_messages_sent_and_accepted": count, "first_counter": 0,
            "last_counter": receiver.highest_counter, "message_type": "localization_state",
            "payload_bytes_total": payload_total, "wire_bytes_total": wire_total,
            "wire_overhead_bytes_total": wire_total - payload_total,
            "wire_overhead_bytes_per_message_mean": (wire_total - payload_total) / count,
            "wire_to_payload_ratio": wire_total / payload_total,
            "payload_bytes_min": min(payload_lengths), "payload_bytes_max": max(payload_lengths),
            "packet_bytes_min": min(packet_lengths), "packet_bytes_max": max(packet_lengths),
            "gcm_tag_bytes_per_message": 16,
            "byte_accounting": "Original accepted messages only; excludes two injected attack deliveries.",
            "sent_payload_stream_sha256": sent_digest.hexdigest(),
            "received_payload_stream_sha256": received_digest.hexdigest(),
            "stream_hash_format": "For each payload: uint64 big-endian byte length followed by payload bytes.",
            "all_payloads_byte_identical": True,
            "all_numeric_state_fields_identical_after_json_decode": True,
        },
        "attack_checks": attacks,
        "localization_consistency": {
            "direct_position_rmse_m": float(np.sqrt(np.mean(direct_errors**2))),
            "decrypted_position_rmse_m": float(np.sqrt(np.mean(recovered_errors**2))),
            "max_position_difference_m": float(np.max(np.abs(recovered_positions - estimate.position))),
            "identical_per_epoch_position_errors": True,
            "interpretation": "Telemetry encryption preserves the estimated state; it does not improve its accuracy.",
        },
        "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sources},
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "scipy": scipy.__version__,
                        "cryptography": cryptography.__version__},
        "limitations": [
            "Four-second synthetic demonstration; not an additional localization benchmark or real flight.",
            "No network transport, packet-loss scheduling, flight hardware, or key provisioning measured.",
            "Physical ranging authenticity and resistance to relay attacks are outside this demonstration.",
            "Encryption runs after estimation; sensor ingress authentication is not implemented here.",
            "Fresh secrets are generated in memory and are not included in this artifact.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}: {count} byte-identical states; tampering and replay rejected.")
    print(f"Payload {payload_total} B; wire {wire_total} B; "
          f"unchanged position RMSE {report['localization_consistency']['direct_position_rmse_m']:.6f} m.")


if __name__ == "__main__":
    main()
