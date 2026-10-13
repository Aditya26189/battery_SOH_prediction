# Archive — Retired Model Artifacts

This directory contains files that were produced with an older, inconsistent parameter configuration and must not be cited as validated results.

## Why Were These Files Archived?

The `battery_data_dump` repository contains **two incompatible parameter configurations**:

### Old Kaggle Parameter Set (archived here)
- **Generating environment**: Automated Kaggle Linux container, 2026-10-11
- **Key differences from FIXED_SET**:
  - `Outer SEI solvent diffusivity` (unread by PyBaMM ≥ 25.1 → model fell back to stock `2.5e-22`)
  - Positive electrode mechanics: active in Kaggle; disabled in pilot script
  - Negative LAM rate: `3e-6` (Kaggle) vs `5.8778e-6` (pilot script)
  - 50-cycle capacity fade: `1.49%` (Kaggle 0.2C) vs `0.21%` (FIXED_SET 0.2C)
- **Result**: A GP surrogate trained on this sweep will systematically mis-predict FIXED_SET DFN simulations (offset `0.4%` at Cycle 1, growing to `2.1%` by Cycle 50)

### FIXED_SET Parameter Set (active in `src/model.py`)
- Full specification: `results/FIXED_SET.md` in the parent project
- Validated by 1,500-cycle pilot simulations at 0.2C, 1.0C, 2.0C (see `data/pilot_1500/`)

---

## Archived Files

| File | Original Location | Archived Because |
|:---- |:---- |:---- |
| `sweep_kaggle_old_params.npz` | `data/sweep/sweep.npz` | Kaggle parameter set; incompatible with FIXED_SET |
| `emulator_pred_old.npz` | `data/sweep/emulator_pred.npz` | GP predictions from Kaggle sweep |
| `figures/fig1_trajectories.png` | `figures/` | Generated from Kaggle sweep data, not FIXED_SET |
| `figures/fig2_holdout_error.png` | `figures/` | Generated from Kaggle sweep data |
| `figures/fig3_extrapolation_from_first_K.png` | `figures/` | Generated from Kaggle sweep data |
| `figures/emulator_validation.png` | `figures/` | GP diagnostics from Kaggle sweep |
| `figures/comparison_1C_fit100.png` | `figures/` | GP prediction vs FIXED_SET truth — cross-dataset comparison |
| `docs/REPORT_old_model.md` | `docs/REPORT.md` | Results from old pilot script (Script B parameters) |
| `docs/PRESENTATION_old_model.md` | `docs/PRESENTATION.md` | Faculty report citing mixed old/new results |

---

## How to Use the Archive

- **Do not delete**: These files document the diagnostic investigation (see `docs/DECISIONS_AND_RATIONALE.md §Stages 1–3`).
- **Do not cite**: These results should not appear in publications, reports, or benchmarks.
- **Reference only for provenance**: If tracing why old Kaggle and current FIXED_SET numbers differ, use these alongside `docs/DIAG_REPORT.md`.

---

## Reactivation Criteria

These files will never be moved back into active use. To replace them with correct equivalents:

1. Re-run the 60-point C-rate sweep under `src/model.py` (FIXED_SET parameters)
2. Retrain the GP surrogate on the new sweep
3. Save output to `data/sweep/sweep_fixedset.npz`
4. Store new figures in `figures/`
