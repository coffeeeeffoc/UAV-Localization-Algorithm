"""Threat-oriented tests; generated keys remain in memory."""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import unittest

from uav_localization.security import (
    AuthenticationError, CounterExhausted, MAX_COUNTER, MAX_PAYLOAD_BYTES,
    ProtocolError, ReplayError, SessionSecrets, TelemetryReceiver, TelemetrySender,
)


def edit_packet(packet, edit):
    envelope = json.loads(packet)
    edit(envelope)
    return json.dumps(envelope).encode()


class TelemetrySecurityTests(unittest.TestCase):
    def setUp(self):
        self.session = SessionSecrets.generate("uav-01")
        self.sender = TelemetrySender(self.session)
        self.receiver = TelemetryReceiver(self.session)

    def test_round_trip_and_visible_authenticated_metadata(self):
        payload = b'{"p_m":[1.0,2.0,3.0]}'
        packet = self.sender.seal(payload, message_type="state")
        message = self.receiver.open(packet)
        self.assertEqual(message.payload, payload)
        self.assertEqual(message.counter, 0)
        self.assertEqual(message.message_type, "state")
        self.assertEqual(self.receiver.highest_counter, 0)
        self.assertNotIn(payload, packet)

    def test_ciphertext_and_tag_tampering_rejected(self):
        packet = self.sender.seal(b"position")
        for index in [0, -1]:
            def tamper(envelope):
                data = bytearray(base64.b64decode(envelope["ciphertext"]))
                data[index] ^= 1
                envelope["ciphertext"] = base64.b64encode(data).decode()
            with self.assertRaises(AuthenticationError):
                self.receiver.open(edit_packet(packet, tamper))
        self.assertEqual(self.receiver.highest_counter, -1)
        self.assertEqual(self.receiver.open(packet).payload, b"position")

    def test_wrong_key_rejected(self):
        other = replace(self.session, key=SessionSecrets.generate("other").key)
        receiver = TelemetryReceiver(other)
        with self.assertRaises(AuthenticationError):
            receiver.open(self.sender.seal(b"position"))
        self.assertEqual(receiver.highest_counter, -1)

    def test_wrong_nonce_prefix_rejected(self):
        prefix = bytes([self.session.nonce_prefix[0] ^ 1]) + self.session.nonce_prefix[1:]
        receiver = TelemetryReceiver(replace(self.session, nonce_prefix=prefix))
        with self.assertRaises(AuthenticationError):
            receiver.open(self.sender.seal(b"position"))

    def test_every_aad_field_is_rejected_if_changed(self):
        packet = self.sender.seal(b"position")
        modifications = {"version": 2, "device_id": "uav-02", "session_id": "a" * 32,
                         "counter": 20, "message_type": "imu"}
        for field, value in modifications.items():
            with self.subTest(field=field):
                modified = edit_packet(packet, lambda e: e["header"].__setitem__(field, value))
                with self.assertRaises((AuthenticationError, ProtocolError)):
                    self.receiver.open(modified)
                self.assertEqual(self.receiver.highest_counter, -1)

    def test_invalid_high_counter_does_not_poison_replay_state(self):
        packet = self.sender.seal(b"valid")
        forged = edit_packet(packet, lambda e: e["header"].__setitem__("counter", MAX_COUNTER))
        with self.assertRaises(AuthenticationError):
            self.receiver.open(forged)
        self.assertEqual(self.receiver.highest_counter, -1)
        self.assertEqual(self.receiver.open(packet).payload, b"valid")

    def test_replay_rejected(self):
        packet = self.sender.seal(b"valid")
        self.receiver.open(packet)
        with self.assertRaises(ReplayError):
            self.receiver.open(packet)
        self.assertEqual(self.receiver.highest_counter, 0)

    def test_gaps_allowed_and_late_packets_rejected(self):
        packets = [self.sender.seal(bytes([i])) for i in range(3)]
        self.assertEqual(self.receiver.open(packets[2]).counter, 2)
        for packet in packets[:2]:
            with self.assertRaises(ReplayError):
                self.receiver.open(packet)

    def test_limit_and_counter_exhaustion_fail_closed(self):
        sender = TelemetrySender(self.session, message_limit=1)
        sender.seal(b"one")
        with self.assertRaises(CounterExhausted):
            sender.seal(b"two")
        sender = TelemetrySender(SessionSecrets.generate("uav-01"), message_limit=MAX_COUNTER + 1)
        sender._next_counter = MAX_COUNTER  # Boundary injection only; no production setter.
        last = json.loads(sender.seal(b"last"))
        self.assertEqual(last["header"]["counter"], MAX_COUNTER)
        with self.assertRaises(CounterExhausted):
            sender.seal(b"overflow")

    def test_invalid_packets_and_duplicate_fields(self):
        packet = self.sender.seal(b"x")
        malformed = [b"{", b"[]", b"null", b'\xff', b'{"header":{},"header":{},"ciphertext":""}']
        for field, value in [("counter", True), ("counter", -1), ("counter", MAX_COUNTER + 1),
                             ("version", True), ("message_type", "")]:
            malformed.append(edit_packet(packet, lambda e: e["header"].__setitem__(field, value)))
        malformed.append(edit_packet(packet, lambda e: e.__setitem__("ciphertext", "*")))
        malformed.append(edit_packet(packet, lambda e: e.__setitem__("extra", 1)))
        for bad in malformed:
            with self.subTest(packet=bad[:100]):
                with self.assertRaises(ProtocolError):
                    self.receiver.open(bad)
        self.assertEqual(self.receiver.highest_counter, -1)

    def test_payload_boundaries_and_validation_do_not_reserve_counter(self):
        with self.assertRaises(ProtocolError):
            self.sender.seal(b"x" * (MAX_PAYLOAD_BYTES + 1))
        self.assertEqual(self.sender.messages_reserved, 0)
        self.assertEqual(self.receiver.open(self.sender.seal(b"x" * MAX_PAYLOAD_BYTES)).payload,
                         b"x" * MAX_PAYLOAD_BYTES)
        self.assertEqual(self.receiver.open(self.sender.seal(b"")).payload, b"")

    def test_fresh_sessions_and_secrets_not_in_repr(self):
        other = SessionSecrets.generate("uav-01")
        self.assertNotEqual(self.session.key, other.key)
        self.assertNotEqual(self.session.session_id, other.session_id)
        self.assertNotIn(repr(self.session.key), repr(self.session))
        with self.assertRaises(ValueError):
            replace(self.session, key=b"short")

    def test_parallel_sender_calls_allocate_distinct_counters(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            packets = list(executor.map(lambda _: self.sender.seal(b"x"), range(100)))
        counters = [json.loads(p)["header"]["counter"] for p in packets]
        self.assertEqual(sorted(counters), list(range(100)))


if __name__ == "__main__":
    unittest.main()
