# Data provenance and formats

This repository currently generates **synthetic** UWB/IMU measurements. It does
not contain real UAV flights or downloaded external benchmark recordings. Do not
describe synthetic samples as a measured hardware dataset.

`synthetic/reference/manifest.json` identifies every generated scenario and seed,
the resolved simulator metadata, and a deterministic array-content SHA-256. The
frozen experiment initially retains the first evaluation seed of each scenario.
The supplemental `synthetic/reference-full/` archive stores **all 40 evaluation
datasets**, each regenerated from the frozen config and checked against its original
array-content hash. Its independent manifest records the connection to the unchanged
reference experiment. Dataset ZIP file hashes are also recorded. Ground truth and
NLOS labels are for simulation evaluation only and are never inputs to filter decisions.

To reproduce the complete archive without overwriting the retained files:

```sh
python scripts/materialize_reference_data.py --output /tmp/uav-reference-full
python scripts/verify_artifacts.py /tmp/uav-reference-full/manifest.json --check-source
```

Load an NPZ file with `numpy.load(path, allow_pickle=False)`. No Python object arrays
are stored. The frame is ENU (right handed), metres and seconds; quaternions are
body-to-world in **xyzw** order. Let `N` be timestamp count and `M` anchor count:

| Array | Shape | Interpretation |
|---|---|---|
| `t_s` | `(N,)` | Strictly increasing simulator timestamps in seconds |
| `truth_position_m` | `(N,3)` | Analytic ground-truth position, world frame |
| `truth_velocity_mps` | `(N,3)` | Analytic ground-truth velocity, world frame |
| `truth_quaternion_xyzw` | `(N,4)` | Unit body-to-world quaternion |
| `accel_body_mps2` | `(N-1,3)` | Specific-force samples in body frame, including configured noise/bias |
| `gyro_body_radps` | `(N-1,3)` | Body angular-velocity samples, including configured noise/bias |
| `ranges_m` | `(N,M)` | Absolute tag-to-anchor distances; NaN means absent |
| `anchors_m` | `(M,3)` | Known non-coplanar anchor coordinates, world frame |
| `nlos_mask` | `(N,M)` | Synthetic bias labels; evaluator-only |
| `initial_position_m` | `(3,)` | Declared warm-start position supplied to the estimators |
| `initial_velocity_mps` | `(3,)` | Declared warm-start velocity supplied to the estimators |
| `initial_quaternion_xyzw` | `(4,)` | Declared warm-start attitude supplied to the estimators |

IMU sample `k` describes interval `[t_s[k], t_s[k+1]]` using midpoint specific
force and a relative-rotation increment. Ranges on row `k` are measured at `t_s[k]`.
The model assumes synchronized clocks, known anchor coordinates, and zero tag/IMU
lever arm. Refer to `docs/algorithm.md` for equations and limitations.

For external data, record the original URL/DOI, version, licence, acquisition date,
checksums, coordinate conventions, units, measurement type and split before adding
an adapter. Keep immutable raw measurements separate from derived arrays. A public
download link does not automatically grant redistribution rights. Candidate
sources and verification status are in `literature/`; no downloaded-data claim
should be made solely from a literature citation.
