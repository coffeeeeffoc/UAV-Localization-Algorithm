#!/usr/bin/env python3
"""Record host-only AES-GCM telemetry timings and adversarial smoke checks.

No keys, plaintext telemetry records, or ciphertext packets are written to disk.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time

import cryptography
from cryptography.hazmat.backends.openssl.backend import backend

from uav_localization.security import (
    AuthenticationError, ReplayError, SessionSecrets, TelemetryReceiver, TelemetrySender,
)


def summarize(values_ns):
    values_us = [v / 1000.0 for v in values_ns]
    return {
        "median_us": statistics.median(values_us),
        "p95_us": statistics.quantiles(values_us, n=100, method="inclusive")[94],
        "mean_us": statistics.mean(values_us),
        "stdev_us": statistics.stdev(values_us),
    }


def benchmark(payload_size, repetitions, warmup):
    session = SessionSecrets.generate("benchmark-uav")
    sender = TelemetrySender(session, message_limit=repetitions + warmup)
    receiver = TelemetryReceiver(session)
    payload = bytes(i % 256 for i in range(payload_size))
    encryption_ns, decryption_ns, wire_sizes = [], [], []
    for i in range(warmup + repetitions):
        start = time.perf_counter_ns()
        packet = sender.seal(payload, message_type="state")
        sealed = time.perf_counter_ns()
        opened = receiver.open(packet)
        end = time.perf_counter_ns()
        if opened.payload != payload:
            raise AssertionError("Authenticated round-trip changed payload")
        if i >= warmup:
            encryption_ns.append(sealed - start)
            decryption_ns.append(end - sealed)
            wire_sizes.append(len(packet))
    return {
        "payload_bytes": payload_size,
        "repetitions": repetitions,
        "warmup_packets_excluded": warmup,
        "seal_including_json_and_base64": summarize(encryption_ns),
        "open_including_parse_and_replay_check": summarize(decryption_ns),
        "wire_bytes_min": min(wire_sizes),
        "wire_bytes_max": max(wire_sizes),
        "aead_tag_bytes": 16,
        "raw_seal_ns": encryption_ns,
        "raw_open_ns": decryption_ns,
    }


def adversarial_checks():
    session = SessionSecrets.generate("test-uav")
    sender, receiver = TelemetrySender(session), TelemetryReceiver(session)
    packet = sender.seal(b"synthetic test payload")
    outcomes = {}

    def rejected(label, candidate, error_type, target=receiver):
        before = target.highest_counter
        try:
            target.open(candidate)
        except error_type:
            outcomes[label] = {"rejected": True, "replay_state_unchanged": target.highest_counter == before}
        else:
            raise AssertionError(f"{label} was not rejected")

    envelope = json.loads(packet)
    altered = bytearray(base64.b64decode(envelope["ciphertext"]))
    altered[0] ^= 1
    envelope["ciphertext"] = base64.b64encode(altered).decode()
    rejected("ciphertext_tampering", json.dumps(envelope).encode(), AuthenticationError)
    envelope = json.loads(packet)
    envelope["header"]["message_type"] = "imu"
    rejected("aad_tampering", json.dumps(envelope).encode(), AuthenticationError)
    envelope = json.loads(packet)
    envelope["header"]["counter"] = (1 << 64) - 1
    rejected("forged_high_counter", json.dumps(envelope).encode(), AuthenticationError)
    wrong_key = SessionSecrets.generate("other").key
    wrong_receiver = TelemetryReceiver(replace(session, key=wrong_key))
    rejected("wrong_key", packet, AuthenticationError, wrong_receiver)
    receiver.open(packet)
    rejected("replay", packet, ReplayError)
    delayed, newer = sender.seal(b"delayed"), sender.seal(b"newer")
    receiver.open(newer)
    rejected("out_of_order", delayed, ReplayError)
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/security/benchmark.json"))
    parser.add_argument("--repetitions", type=int, default=2000)
    parser.add_argument("--warmup", type=int, default=100)
    args = parser.parse_args()
    if args.repetitions < 20 or args.warmup < 0:
        parser.error("repetitions must be >= 20; warmup must be >= 0")
    root = Path(__file__).resolve().parents[1]
    tracked_sources = [root / "src/uav_localization/security.py", Path(__file__).resolve()]
    cpu_model = platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    results = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_type": "host_microbenchmark_and_functional_smoke_checks",
        "scope": "AES-256-GCM telemetry envelope; no flight hardware or network measured",
        "limitations": [
            "Single process on a shared host; no hard real-time guarantee or energy measurement.",
            "Seal/open include JSON/base64; no transport, key provisioning, or disk persistence timing.",
            "One benchmark session per payload size; timings are descriptive, not independent flight trials.",
            "Functional rejection checks are not a proof of cryptographic or ranging security.",
        ],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_model": cpu_model,
            "cryptography": cryptography.__version__,
            "openssl": backend.openssl_version_text(),
            "clock": vars(time.get_clock_info("perf_counter")),
        },
        "source_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in tracked_sources},
        "adversarial_checks": adversarial_checks(),
        "benchmarks": [benchmark(size, args.repetitions, args.warmup) for size in (128, 512, 2048)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; six rejection checks passed; host timing only.")
    for result in results["benchmarks"]:
        print(f"{result['payload_bytes']} bytes: "
              f"seal median {result['seal_including_json_and_base64']['median_us']:.2f} us, "
              f"open median {result['open_including_parse_and_replay_check']['median_us']:.2f} us")


if __name__ == "__main__":
    main()
