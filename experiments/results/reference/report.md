# Synthetic experiment report

These are generated simulation results, not real UAV flight measurements.

Evaluation seeds: `[100, 101, 102, 103, 104, 105, 106, 107, 108, 109]`. No fitting or parameter search is performed by this run.

## Position RMSE at common observed UWB epochs

Each value is the mean of per-seed RMSEs (metres); uncertainty is a two-sided 95% Student-t interval across seeds. Common epochs have at least four observed ranges and finite outputs from every included method. This conditional comparison does not measure dropout continuity; see dense-grid availability and errors in CSV.

| Scenario | Method | Seeds | Mean RMSE (m) | 95% CI (m) |
|---|---|---:|---:|---:|
| combined | adaptive_eskf | 10 | 0.5311 | [0.2283, 0.8339] |
| combined | eskf | 10 | 1.1860 | [1.1605, 1.2115] |
| combined | gated_eskf | 10 | 0.0679 | [0.0583, 0.0776] |
| combined | ins | 10 | 42.1378 | [41.7397, 42.5359] |
| combined | robust_eskf | 10 | 0.0690 | [0.0587, 0.0792] |
| combined | uwb | 10 | 0.9634 | [0.9427, 0.9841] |
| dropout | adaptive_eskf | 10 | 0.0611 | [0.0557, 0.0665] |
| dropout | eskf | 10 | 0.0607 | [0.0553, 0.0660] |
| dropout | gated_eskf | 10 | 0.0611 | [0.0553, 0.0668] |
| dropout | ins | 10 | 42.1235 | [41.7235, 42.5235] |
| dropout | robust_eskf | 10 | 0.0613 | [0.0558, 0.0668] |
| dropout | uwb | 10 | 0.1873 | [0.1849, 0.1896] |
| los | adaptive_eskf | 10 | 0.0597 | [0.0543, 0.0651] |
| los | eskf | 10 | 0.0594 | [0.0541, 0.0647] |
| los | gated_eskf | 10 | 0.0597 | [0.0540, 0.0654] |
| los | ins | 10 | 40.4813 | [40.1046, 40.8581] |
| los | robust_eskf | 10 | 0.0599 | [0.0543, 0.0654] |
| los | uwb | 10 | 0.1839 | [0.1816, 0.1862] |
| nlos | adaptive_eskf | 10 | 0.4609 | [0.2037, 0.7182] |
| nlos | eskf | 10 | 1.1345 | [1.1099, 1.1592] |
| nlos | gated_eskf | 10 | 0.0657 | [0.0565, 0.0748] |
| nlos | ins | 10 | 40.4931 | [40.1179, 40.8684] |
| nlos | robust_eskf | 10 | 0.0666 | [0.0568, 0.0763] |
| nlos | uwb | 10 | 0.8989 | [0.8797, 0.9182] |

## Paired differences

Negative values favour `robust_eskf`. Intervals are exploratory and unadjusted for multiple comparisons; do not treat interval exclusion as a confirmatory test.

| Scenario | Baseline | Mean difference (m) | 95% CI (m) |
|---|---|---:|---:|
| combined | uwb | -0.8944 | [-0.9125, -0.8763] |
| combined | ins | -42.0689 | [-42.4613, -41.6764] |
| combined | eskf | -1.1170 | [-1.1381, -1.0959] |
| combined | gated_eskf | 0.0010 | [-0.0005, 0.0025] |
| combined | adaptive_eskf | -0.4621 | [-0.7617, -0.1626] |
| dropout | uwb | -0.1260 | [-0.1318, -0.1201] |
| dropout | ins | -42.0622 | [-42.4589, -41.6656] |
| dropout | eskf | 0.0007 | [-0.0009, 0.0022] |
| dropout | gated_eskf | 0.0003 | [-0.0012, 0.0017] |
| dropout | adaptive_eskf | 0.0002 | [-0.0000, 0.0005] |
| los | uwb | -0.1240 | [-0.1289, -0.1192] |
| los | ins | -40.4215 | [-40.7948, -40.0481] |
| los | eskf | 0.0004 | [-0.0010, 0.0019] |
| los | gated_eskf | 0.0002 | [-0.0014, 0.0018] |
| los | adaptive_eskf | 0.0002 | [-0.0001, 0.0004] |
| nlos | uwb | -0.8324 | [-0.8485, -0.8162] |
| nlos | ins | -40.4266 | [-40.7964, -40.0567] |
| nlos | eskf | -1.0680 | [-1.0887, -1.0472] |
| nlos | gated_eskf | 0.0009 | [-0.0006, 0.0023] |
| nlos | adaptive_eskf | -0.3944 | [-0.6486, -0.1401] |

## Interpretation limits

Seeds vary synthetic noise and biases, not environments or independent flights. Intervals describe this simulator and configuration only. Gate thresholds, initialization and geometry require independent real-data evaluation. Per-run runtime is a host wall-clock diagnostic, not a real-time flight guarantee.
