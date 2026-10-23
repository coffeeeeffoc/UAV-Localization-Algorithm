# Authenticated localization telemetry

This module protects the bytes of telemetry exchanged between a UAV and a
trusted manager. It is an application-layer reference implementation using
`cryptography`'s AES-256-GCM, not a new cryptographic primitive or a deployment
ready key-management service. The estimation code does not run inside encrypted
computation. The intended boundary is to authenticate/decrypt incoming packets
before any downstream consumer processes their contents; the current simulation
and the telemetry benchmark are evaluated separately.

## Claims and assumptions

With secret keys and unique nonces, AES-GCM supplies confidentiality and
authentication of the payload plus authentication of the cleartext header. The
receiver rejects replayed and older packets within a live provisioned session.
These are conditional properties of the protocol, not evidence of physical
position truth or certified flight safety. A legitimate sender can encrypt an
incorrect measurement. This design does not prevent UWB ranging relay attacks,
sensor compromise, malicious anchors, denial of service, endpoint/key compromise,
or traffic analysis. Device ID, session ID, message type, sequence number, packet
length, and traffic timing remain visible.

The key-management layer must supply **a newly generated 256-bit key for every
unidirectional session**, provisioned over an authenticated confidential channel.
The reference `SessionSecrets.generate(device_id)` uses the operating system
CSPRNG and holds its result only in memory. There is no built-in public-key
handshake, key rotation service, revocation, secure hardware storage, peer
attestation, or guaranteed memory zeroization. A two-way connection needs two
independent keys/sessions. Session secrets must never be included in experiment
artifacts or committed to Git.

## Wire format and nonce construction

The packet is a JSON object with exactly two fields:

```json
{
  "header": {
    "version": 1,
    "device_id": "uav-01",
    "session_id": "32-lowercase-hexadecimal-characters",
    "counter": 0,
    "message_type": "state"
  },
  "ciphertext": "base64(ciphertext || 16-byte GCM tag)"
}
```

The session-ID text above is explanatory; a real value contains exactly 32
lowercase hexadecimal digits. Header identifiers use bounded ASCII alphabets.
All five header fields are additional authenticated data (AAD), encoded as JSON
with sorted keys, no optional whitespace, ASCII escaping, and no non-finite
numbers. Duplicate fields, extra fields, unsupported versions, and non-integer
counters (including JSON booleans) are rejected. The sender emits this canonical
format. Receivers parse and reconstruct canonical header AAD, so harmless JSON
whitespace and field-order changes are allowed. The ciphertext includes the
128-bit GCM authentication tag and uses strict Base64 encoding.

For each session, the provisioned nonce prefix is a fixed four-byte value. The
96-bit nonce is

\[
N_c=\operatorname{prefix}_{32}\parallel\operatorname{BE64}(c),\qquad
0\le c\le 2^{64}-1.
\]

The prefix is part of trusted session configuration and is not transmitted per
packet. Each successful or attempted encryption reserves the next counter before
calling AES-GCM. A failed encryption never releases its counter for reuse. A
single object serializes access with a lock. This does **not** prevent a second
process or a reconstructed sender from reusing the key and nonce space.

The sender's default application budget is `2**20` messages, after which it
requires a new session. The mathematical counter limit is also checked; neither
budget implies that `2**64` GCM invocations are suitable for deployment. Maximum
plaintext length is 16,384 bytes. A production security profile must set its own
key-lifetime, aggregate encrypted-block, failed-verification, rate-limit, and
device resource budgets using its actual risk requirements.

## Replay and restart semantics

The receiver first checks the bounded packet schema and expected session
identity, then verifies the GCM tag. Only after successful authentication does it
check `counter > highest_counter` and release plaintext. The watermark advances
only for an authenticated accepted packet. A modified packet claiming a high
counter cannot suppress later valid traffic by advancing replay state.

The receiver permits gaps but rejects duplicates and out-of-order older packets.
For example, after accepting counter 12, counter 11 is rejected even if it was
delayed rather than malicious. This strict policy is intentional and may cause
availability loss on reordered links. A future sliding replay window would need
separate implementation and tests; it is not claimed here.

**Restart or state rollback of either endpoint requires a new key and session.**
Recreating a receiver with an old key erases its watermark and re-enables old
packets; recreating a sender with an old key can repeat GCM nonces. A fresh
session ID or randomly changed four-byte prefix alone is not an acceptable
replacement for a fresh key in this implementation. The library cannot enforce
freshness across independent processes. Sharing/cloning one session across
multiple senders or restoring it from a snapshot is outside the supported
contract. Provisioning new receiver state from an unauthenticated packet is
forbidden. An attacker cannot introduce a session merely by changing its header.

## Verification and host benchmark

After installing the repository package, run:

```bash
python -m unittest discover -s tests -p 'test_security.py' -v
python scripts/security_demo.py --output results/security/benchmark.json
```

Tests cover exact plaintext recovery, ciphertext/tag tampering, wrong key or
prefix, every AAD field, forged large counters without watermark poisoning,
replay, reordering, message/counter exhaustion, malformed input and duplicate
fields, payload boundaries, and concurrent sender counter allocation. Generated
keys stay in memory. Test success is functional evidence, not a cryptographic
proof or third-party audit.

The benchmark sends synthetic payloads of 128, 512, and 2,048 bytes, with 100
untimed warm-up packets followed by 2,000 measured packets per size. It records
raw nanosecond timings, descriptive median/p95/mean/standard deviation, wire
lengths, library and host versions, source SHA-256 hashes, and six adversarial
smoke-check outcomes. `seal` timings include canonical JSON/AAD serialization,
AES-GCM, and Base64/envelope encoding; `open` includes parsing, authentication,
and replay-state checks. This is a single-process **host microbenchmark**, not
flight-controller performance, network latency, power consumption, or a real-time
guarantee. Do not report its packets as independent UAV flight trials.

## 中文说明

本模块保护的是遥测数据的机密性、完整性及活动会话内的防重放属性，不证明物理
测距真实性，也不能替代抗中继攻击方案。每个单向会话必须使用全新密钥；重启、
状态回滚、复制发送者都会破坏计数器约束，必须重新建立会话并更换密钥。接收端
允许丢包但拒绝乱序旧包，只有认证成功后才推进防重放状态。基准测量仅来自当前
主机，不属于无人机平台实测。该边界应同时写入英文主稿和中文译稿。

## Integration with estimated localization states

`scripts/secure_localization_demo.py` runs `simulate` followed by `robust_eskf`,
serializes every resulting position, velocity, quaternion, and bias state, then
passes those payloads through `TelemetrySender` and `TelemetryReceiver`. Run:

```bash
python scripts/secure_localization_demo.py --output results/security/localization_roundtrip.json
```

The fixed demonstration uses four seconds at 100 Hz IMU / 10 Hz UWB, NLOS bias
on anchors 0 and 1 during `[1, 2)` seconds, and complete UWB dropout during
`[2.5, 3)` seconds, with seed 20261023. The 401 state messages include the initial
epoch. The demonstration checks byte-for-byte plaintext recovery and exact
numeric JSON round-trip for all transmitted state fields. At counter 123, an
altered ciphertext must fail without advancing receiver state; the original
packet must then succeed, and its replay must fail.

The artifact records exact simulator/filter configurations, code hashes,
message and byte counts, payload-stream hashes, attack outcomes, and identical
position errors before and after the telemetry path. It stores no keys or
ciphertext packets. Byte counts include the 401 original accepted messages and
exclude the two injected attack deliveries. GCM's 16-byte tag, Base64, and JSON
header/envelope all contribute to reported wire overhead.

This connects estimation output to authenticated telemetry in one executable
path. It does not authenticate raw sensors before fusion, execute on flight
hardware, or model a network. Encryption preserves the estimated state exactly
and therefore leaves its localization error unchanged. The four-second run is
an integration check, not an extra trial supporting the paper's localization
performance comparisons.
