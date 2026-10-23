# Synthetic experiment report

These are generated simulation results, not real UAV flight measurements.

Evaluation seeds: `[200, 201]`. No fitting or parameter search is performed by this run.

## Position RMSE at common observed UWB epochs

Each value is the mean of per-seed RMSEs (metres); uncertainty is a two-sided 95% Student-t interval across seeds. Common epochs have at least four observed ranges and finite outputs from every included method. This conditional comparison does not measure dropout continuity; see dense-grid availability and errors in CSV.

| Scenario | Method | Seeds | Mean RMSE (m) | 95% CI (m) |
|---|---|---:|---:|---:|
| combined | adaptive_eskf | 2 | 0.1042 | [-0.0972, 0.3056] |
| combined | eskf | 2 | 0.6117 | [0.5691, 0.6543] |
| combined | gated_eskf | 2 | 0.0982 | [-0.0449, 0.2412] |
| combined | ins | 2 | 0.8258 | [0.8116, 0.8399] |
| combined | robust_eskf | 2 | 0.0980 | [-0.0258, 0.2217] |
| combined | uwb | 2 | 0.8009 | [0.6801, 0.9218] |
| los | adaptive_eskf | 2 | 0.0766 | [-0.0077, 0.1609] |
| los | eskf | 2 | 0.0746 | [-0.0097, 0.1589] |
| los | gated_eskf | 2 | 0.0746 | [-0.0097, 0.1589] |
| los | ins | 2 | 0.8124 | [0.7967, 0.8280] |
| los | robust_eskf | 2 | 0.0766 | [-0.0077, 0.1609] |
| los | uwb | 2 | 0.1837 | [0.1547, 0.2127] |

## Paired differences

Negative values favour `robust_eskf`. Intervals are exploratory and unadjusted for multiple comparisons; do not treat interval exclusion as a confirmatory test.

| Scenario | Baseline | Mean difference (m) | 95% CI (m) |
|---|---|---:|---:|
| combined | uwb | -0.7030 | [-0.7059, -0.7001] |
| combined | ins | -0.7278 | [-0.8657, -0.5898] |
| combined | eskf | -0.5137 | [-0.5949, -0.4325] |
| combined | gated_eskf | -0.0002 | [-0.0194, 0.0190] |
| combined | adaptive_eskf | -0.0062 | [-0.3314, 0.3189] |
| los | uwb | -0.1071 | [-0.1624, -0.0518] |
| los | ins | -0.7358 | [-0.8045, -0.6671] |
| los | eskf | 0.0020 | [0.0019, 0.0020] |
| los | gated_eskf | 0.0020 | [0.0019, 0.0020] |
| los | adaptive_eskf | 0.0000 | [0.0000, 0.0000] |

## Interpretation limits

Seeds vary synthetic noise and biases, not environments or independent flights. Intervals describe this simulator and configuration only. Gate thresholds, initialization and geometry require independent real-data evaluation. Per-run runtime is a host wall-clock diagnostic, not a real-time flight guarantee.
