# Pilot results

- C-rates: 0.2, 1, 2  |  cycles used: 1500  |  pybamm: 26.8.0.0
- protocol step (run 1): ['Discharge at 0.2C until 2.5V', 'Charge at 0.3C until 4.2V (3 minute period)', 'Hold at 4.2V until C/100 (3 minute period)']
- vary: discharge
- bol_ref = cycle-1 discharge capacity at lowest C = 4.90689 Ah (a run's cycle 1, NOT a fresh-cell reference)

## Integrity: all runs status=complete, no NaNs

## Trajectory summary (per-cell SOH)

|   C |   Q_cycle1_Ah |   Y_bol_cycle1 |   SOH_pc@50 |   SOH_pc@100 |   SOH_pc@200 |   SOH_pc@500 |   SOH_pc@1000 |   SOH_pc@1500 |   first_N_below_0.9 |   first_N_below_0.8 |   slope_late/early |
|----:|--------------:|---------------:|------------:|-------------:|-------------:|-------------:|--------------:|--------------:|--------------------:|--------------------:|-------------------:|
| 0.2 |        4.9069 |         1      |      0.9518 |       0.9237 |       0.8854 |       0.8168 |        0.7483 |        0.6992 |                 158 |                 602 |             0.2205 |
| 1   |        4.8447 |         0.9873 |      0.9481 |       0.9145 |       0.8668 |       0.7765 |        0.6794 |        0.6044 |                 127 |                 408 |             0.2795 |
| 2   |        4.7094 |         0.9597 |      0.9406 |       0.9005 |       0.842  |       0.7273 |        0.604  |        0.5078 |                 101 |                 294 |             0.2991 |

slope_late/early > 1 means fade accelerating over the horizon; < 1 decelerating (heuristic, window = last/first 20% of cycles).

## Hold-out extrapolation: sup-error of SOH on cycles > K, worst over C-rates

| form    |     50 |    100 |    200 |    500 |
|:--------|-------:|-------:|-------:|-------:|
| N       | 1.2981 | 0.9747 | 0.6501 | 0.2945 |
| logN    | 0.3801 | 0.3305 | 0.2697 | 0.1763 |
| power   | 0.4177 | 0.2263 | 0.1066 | 0.0289 |
| sqrtN   | 0.1019 | 0.0485 | 0.0427 | 0.031  |
| sqrtN+N | 0.7585 | 0.4275 | 0.1892 | 0.0383 |

Read: the K=50 column is what a 50-cycle sweep could have predicted for the remaining horizon.

## Files
- pilot.npz (crates, N, Q, Y, Y_per_cell, bol_ref[, porosity])
- trajectory_summary.csv, holdout_errors.csv
- fig1_trajectories.png, fig2_holdout_error.png, fig3_extrapolation_from_first_K.png