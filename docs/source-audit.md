# Audit of the supplied proposal and draft

Audit date: 2026-10-23. Inputs and SHA-256 hashes are in
[`sources/manifest.json`](../sources/manifest.json). The following is a research
audit of unpublished drafts, not an assertion that the proposed work has already
been completed.

| Source statement or omission | Assessment | Treatment in this repository |
|---|---|---|
| Proposal has UWB/INS and UWB/vision research streams | The supplied paper draft covers research content one | Implement and write the UWB/INS paper first; keep vision and homomorphic computation as separate future research |
| Draft abstract says “研究表明”; conclusion says accuracy and robustness improve | No measurement files, configurations, executable code, or result tables were supplied | Replace unsupported completed-result claims with bounded, recorded simulation evidence |
| Proposal feasibility section refers to laboratory and field validation | Source assertion cannot be independently verified from the attachments | Do not repeat as real-flight evidence |
| Draft alternates between EKF and UKF | The actual estimator is not specified | Implement one explicit error-state EKF and its ablations |
| State contains position, velocity and Euler angles, but does not model IMU bias | Insufficient for an auditable inertial estimator | Define nominal quaternion state and 15-dimensional position/velocity/attitude/bias error state |
| Acceleration propagation omits explicit specific-force and gravity conventions | A body accelerometer cannot directly be integrated as world acceleration | Define body-to-world rotation, ENU gravity, body specific force, units and time indices |
| Covariance adaptation and abnormal-measurement handling are described qualitatively | Thresholds and statistical assumptions are unspecified | Document bounded inflation and normalized innovation gating; compare each component separately |
| UWB penetration/multipath resistance is described as generally advantageous | Indoor materials and NLOS propagation can cause bias, attenuation and failure | Use conditional statements; positive range-bias simulation is a controlled abstraction |
| AES is described as protecting sensitive data | Encryption alone does not specify authentication, nonce handling, or replay protection | Implement AEAD, explicit session requirements and replay policy; exclude physical ranging authenticity from the claim |
| Parameter “optimization” is claimed | No objective, search procedure or independent validation is supplied | Describe the implemented fixed settings and residual rule precisely, without claiming optimality |
| Mean/max error and continuity are proposed | Availability can hide poor accuracy; baselines have unequal output rates | Report available-time and common-time errors separately with availability and independent-seed uncertainty |
| Novelty is implied by combining standard techniques | Existing robust UWB filtering and covariance adaptation predate this draft | Treat the code as a reproducible research baseline until a distinct contribution is established |
| Proposal timeline contains expected completion dates | A schedule is not proof of completed work | Track current evidence and remaining publication gates explicitly |

The DOCX contains 36 Office Math objects. The archived Markdown extraction uses
Pandoc to preserve them; paragraph-only extraction would produce blank equations.
The `.doc` text extraction does not guarantee retention of embedded mathematics
or drawings. Read the original when a transcription is ambiguous.

The proposal's long reference list is preserved as source material, but is not
automatically admitted into the paper bibliography. The curated literature
registry records what was actually verified, the inspection depth, and missing
verification. This avoids propagating inaccurate bibliographic entries or
unsupported comparative claims.
