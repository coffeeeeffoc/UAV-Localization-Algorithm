# Research evidence and publication policy

The English manuscript is the authoritative research draft. The Chinese version
is a section-by-section translation, including qualifications and limitations.
Neither an implementation nor a simulation result establishes publication
novelty, hardware performance, or real-world flight safety.

## Evidence categories

| Category | Meaning | Required record |
|---|---|---|
| Source intention | A claim or proposed method in the supplied documents | Source file and location |
| Verified literature | A claim supported by an actually inspected source | DOI/URL, access date, inspected extent |
| Implemented | An executable algorithm exists | Code path and validation |
| Synthetic evidence | A run on generated sensor measurements | Generator, configuration, seed, hashes, outputs |
| Real-data evidence | A run on collected measurements | Data origin/license, calibration, time/frame conventions, ground truth |
| Hypothesis | A proposed effect that remains to be tested | Evaluation protocol and acceptance criteria |

Never turn an expected result into an observed result. Negative or inconclusive
findings belong in the result tables. Do not call a method novel until a focused
comparison supports a precise novelty claim. AES-GCM and standard robust
filtering are established techniques, not contributions by themselves.

## Experimental discipline

1. Fix the motion/noise model and algorithm parameters before evaluating held-out
   seeds. Record any later change as a new experiment with its rationale.
2. Use the same measurement realization and initial information for paired
   methods. Keep ground truth and simulated corruption labels out of the filter.
3. Report missing outputs and failures. An estimator returning positions at every
   time step has output availability, not necessarily accurate localization.
4. Compare methods on explicit common timestamps; label dense-rate results
   separately. Do not silently interpolate UWB-only outputs through outages.
5. Use independent runs, not correlated time steps, for uncertainty intervals.
   Repeated noise seeds on one trajectory do not represent independent flights
   across environments.
6. Record software versions, source hashes, seeds, configuration, and metrics.
   Wall-clock timing depends on the host and is not an embedded-system benchmark.
7. Public TDOA datasets require a distance-difference observation model. Do not
   treat TDOA observations as independent absolute ranges.

## Publication gates

- Audit the current literature and establish a narrowly defensible contribution.
- Validate calibration, initialization, observability, time alignment, lever
  arms, and sensor noise on real measurements.
- Add real-data/flight evaluation, justified recent baselines, sensitivity tests,
  failure analysis, and a protocol fixed before the confirmatory evaluation.
- Measure target-platform latency and energy if making real-time/efficiency claims.
- Specify key provisioning and durable session lifecycle before deployment.
- Complete author, affiliation, venue, funding, ethics/data, and contribution
  declarations using information supplied by the authors.

No invented author list, funding, ethics approval, measurement, citation, or
acceptance claim may be added to either language version.
