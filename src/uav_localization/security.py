"""Authenticated telemetry reference protocol (not a key-management system).

Each unidirectional session MUST receive a newly generated 256-bit key. Exactly
one sender may use that key; reconstructing or cloning a sender is forbidden.
Restarting either endpoint requires a fresh session/key. See docs/security.md.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
import json
import re
import secrets
import threading
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


PROTOCOL_VERSION = 1
MAX_COUNTER = (1 << 64) - 1
MAX_PAYLOAD_BYTES = 16_384
MAX_PACKET_BYTES = 24_000
DEFAULT_MESSAGE_LIMIT = 1 << 20
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_TYPE = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z")
_SESSION = re.compile(r"[0-9a-f]{32}\Z")


class TelemetryError(ValueError):
    """Rejected telemetry; no plaintext or replay-state change is returned."""


class ProtocolError(TelemetryError):
    """Malformed or unsupported packet."""


class AuthenticationError(TelemetryError):
    """Authentication failed or the packet belongs to a different session."""


class ReplayError(TelemetryError):
    """Counter is no newer than the last authenticated accepted packet."""


class CounterExhausted(TelemetryError):
    """Session message budget or nonce counter is exhausted; rekey required."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("Duplicate JSON field")
        result[key] = value
    return result


@dataclass(frozen=True)
class SessionSecrets:
    """Provisioned out of band; never serialize this object to a results file.

    Passing values explicitly is intended for a trusted provisioning layer.
    Use ``generate`` for an in-memory demonstration; this class cannot establish
    global key freshness or prevent reuse in another process.
    """

    device_id: str
    session_id: str
    key: bytes = field(repr=False)
    nonce_prefix: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not _IDENTIFIER.fullmatch(self.device_id):
            raise ValueError("device_id must be a 1..128 character ASCII identifier")
        if not isinstance(self.session_id, str) or not _SESSION.fullmatch(self.session_id):
            raise ValueError("session_id must contain 32 lowercase hexadecimal characters")
        if not isinstance(self.key, bytes) or len(self.key) != 32:
            raise ValueError("AES-256-GCM requires a 32-byte key")
        if not isinstance(self.nonce_prefix, bytes) or len(self.nonce_prefix) != 4:
            raise ValueError("nonce_prefix must contain 4 bytes")

    @classmethod
    def generate(cls, device_id: str) -> SessionSecrets:
        """Generate a fresh unidirectional session using the OS CSPRNG."""
        return cls(device_id, secrets.token_hex(16), AESGCM.generate_key(bit_length=256),
                   secrets.token_bytes(4))


@dataclass(frozen=True)
class ReceivedTelemetry:
    counter: int
    message_type: str
    payload: bytes


class TelemetrySender:
    """One sender per fresh session key; thread-safe within this object only."""

    def __init__(self, session: SessionSecrets, *, message_limit: int = DEFAULT_MESSAGE_LIMIT):
        if type(message_limit) is not int or not 1 <= message_limit <= MAX_COUNTER + 1:
            raise ValueError("message_limit must be an integer in [1, 2**64]")
        self._session = session
        self._aead = AESGCM(session.key)
        self._next_counter = 0
        self._message_limit = message_limit
        self._lock = threading.Lock()

    @property
    def messages_reserved(self) -> int:
        return self._next_counter

    def seal(self, payload: bytes, *, message_type: str = "state") -> bytes:
        """Return a UTF-8/ASCII JSON wire packet; all header fields are AAD.

        Counter reservations are never rolled back, including encryption errors.
        ``payload`` is opaque bytes. Applications must validate their own schema.
        """
        if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD_BYTES:
            raise ProtocolError(f"payload must be bytes of length <= {MAX_PAYLOAD_BYTES}")
        if not isinstance(message_type, str) or not _TYPE.fullmatch(message_type):
            raise ProtocolError("Invalid message_type")
        with self._lock:
            counter = self._next_counter
            if counter > MAX_COUNTER or counter >= self._message_limit:
                raise CounterExhausted("Start a new session with a fresh key")
            self._next_counter += 1
            header = {
                "version": PROTOCOL_VERSION,
                "device_id": self._session.device_id,
                "session_id": self._session.session_id,
                "counter": counter,
                "message_type": message_type,
            }
            nonce = self._session.nonce_prefix + counter.to_bytes(8, "big")
            ciphertext_and_tag = self._aead.encrypt(nonce, payload, _canonical_json(header))
            return _canonical_json({
                "header": header,
                "ciphertext": base64.b64encode(ciphertext_and_tag).decode("ascii"),
            })


class TelemetryReceiver:
    """Authenticate before releasing plaintext or advancing a monotone watermark.

    Gaps are allowed. Replayed and reordered older packets are rejected. A fresh
    receiver must not be created with an old key/session after a restart.
    """

    def __init__(self, session: SessionSecrets):
        self._session = session
        self._aead = AESGCM(session.key)
        self._highest_counter = -1
        self._lock = threading.Lock()

    @property
    def highest_counter(self) -> int:
        return self._highest_counter

    def open(self, packet: bytes) -> ReceivedTelemetry:
        if not isinstance(packet, bytes) or len(packet) > MAX_PACKET_BYTES:
            raise ProtocolError("Packet must be bounded bytes")
        try:
            envelope = json.loads(packet, object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise ProtocolError("Invalid packet encoding") from exc
        if not isinstance(envelope, dict) or set(envelope) != {"header", "ciphertext"}:
            raise ProtocolError("Invalid envelope fields")
        header = envelope["header"]
        if not isinstance(header, dict) or set(header) != {
            "version", "device_id", "session_id", "counter", "message_type"
        }:
            raise ProtocolError("Invalid header fields")
        if type(header["version"]) is not int or header["version"] != PROTOCOL_VERSION:
            raise ProtocolError("Unsupported protocol version")
        counter = header["counter"]
        if type(counter) is not int or not 0 <= counter <= MAX_COUNTER:
            raise ProtocolError("Invalid counter")
        if (not isinstance(header["message_type"], str)
                or not _TYPE.fullmatch(header["message_type"])):
            raise ProtocolError("Invalid message_type")
        if (header["device_id"] != self._session.device_id
                or header["session_id"] != self._session.session_id):
            raise AuthenticationError("Packet does not belong to this provisioned session")
        encoded = envelope["ciphertext"]
        if not isinstance(encoded, str):
            raise ProtocolError("Invalid ciphertext encoding")
        try:
            ciphertext_and_tag = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ProtocolError("Invalid ciphertext encoding") from exc
        if not 16 <= len(ciphertext_and_tag) <= MAX_PAYLOAD_BYTES + 16:
            raise ProtocolError("Invalid ciphertext size")
        nonce = self._session.nonce_prefix + counter.to_bytes(8, "big")
        with self._lock:
            try:
                plaintext = self._aead.decrypt(nonce, ciphertext_and_tag, _canonical_json(header))
            except InvalidTag as exc:
                raise AuthenticationError("GCM authentication failed") from exc
            # Even a correctly authenticated old packet must not escape to fusion.
            if counter <= self._highest_counter:
                raise ReplayError("Replayed or out-of-order packet")
            self._highest_counter = counter
            return ReceivedTelemetry(counter, header["message_type"], plaintext)
