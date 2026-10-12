# Pilot results

- C-rates: 0.2, 1, 2  |  cycles used: 1500  |  pybamm: 26.8.0.0
- protocol step (run 1): ['Discharge at 0.2C until 2.5V', 'Charge at 0.3C until 4.2V (3 minute period)', 'Hold at 4.2V until C/100 (3 minute period)']
- vary: discharge
- bol_ref = cycle-1 discharge capacity at lowest C = 4.90778 Ah (a run's cycle 1, NOT a fresh-cell reference)

## Integrity: all runs status=complete, no NaNs

## Trajectory summary (per-cell SOH)

|   C |   Q_cycle1_Ah |   Y_bol_cycle1 |   SOH_pc@50 |   SOH_pc@100 |   SOH_pc@200 |   SOH_pc@500 |   SOH_pc@1000 |   SOH_pc@1500 |   first_N_below_0.9 |   first_N_below_0.8 |   slope_late/early |
|----:|--------------:|---------------:|------------:|-------------:|-------------:|-------------:|--------------:|--------------:|--------------------:|--------------------:|-------------------:|
| 0.2 |        4.9078 |         1      |      0.9979 |       0.9963 |       0.9933 |       0.9855 |        0.9744 |        0.9647 |                 nan |                 nan |             0.6209 |
| 1   |        4.8448 |         0.9872 |      0.9948 |       0.9907 |       0.9833 |       0.9633 |        0.9321 |        0.9017 |                 nan |                 nan |             0.8005 |
| 2   |        4.7095 |         0.9596 |      0.9846 |       0.9728 |       0.9521 |       0.9033 |        0.8457 |        0.7974 |                 525 |                1473 |             0.447  |

slope_late/early > 1 means fade accelerating over the horizon; < 1 decelerating (heuristic, window = last/first 20% of cycles).

## Hold-out extrapolation: sup-error of SOH on cycles > K, worst over C-rates

| form                 |     50 |    100 |    200 |    500 |
|:---------------------|-------:|-------:|-------:|-------:|
| bilinear_two_regime  | 0.2155 | 0.1651 | 0.1229 | 0.0574 |
| composite_two_regime | 0.1192 | 0.0924 | 0.0754 | 0.0373 |
| linear               | 0.2545 | 0.1951 | 0.1465 | 0.0849 |
| logN                 | 0.1738 | 0.1595 | 0.1377 | 0.0949 |
| power                | 0.033  | 0.0343 | 0.0403 | 0.0231 |
| sqrtN                | 0.1028 | 0.0832 | 0.0592 | 0.0328 |

Read: the K=50 column is what a 50-cycle sweep could have predicted for the remaining horizon.

## Files
- pilot.npz (crates, N, Q, Y, Y_per_cell, bol_ref[, porosity])
- trajectory_summary.csv, holdout_errors.csv
- fig1_trajectories.png, fig2_holdout_error.png, fig3_extrapolation_from_first_K.png