# Battery State-of-Health (SOH) Prediction

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyBaMM](https://img.shields.io/badge/PyBaMM-26.8-green.svg)](https://pybamm.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Physics-based electrochemical degradation modelling and empirical extrapolation  
> for composite graphite/silicon lithium-ion cells, built on **PyBaMM 26.8.0.0**.

---

## Overview

This project implements a pipeline for predicting battery State-of-Health (SOH) across the life of a lithium-ion cell under the FIXED_SET specification:

1. **Physics Model** — Doyle–Fuller–Newman (DFN) model with SEI growth, stress-driven loss of active material (LAM) on both electrodes, lithium plating, and porosity changes (`src/model.py`).
2. **Full-Life Simulation** — 1,500-cycle simulations at three anchor C-rates (0.2C, 1.0C, 2.0C) with chunked execution and lightweight checkpointing (`src/simulator.py`).
3. **Kinetic Extrapolator** — Physics-informed functional form $\text{SOH}(N) = c - b_1\sqrt{N} - b_2 N$ calibrated on early cycles and projected to 1,500 cycles (`src/extrapolator.py`).
4. **GP Surrogate** — A Gaussian Process emulator mapping C-rate → SOH trajectory, currently awaiting revalidation on FIXED_SET sweep data (`src/gp_surrogate.py`).

---

## Scope and Status

| Component | Validated | Dataset Used | Notes |
|:--- |:---: |:--- |:--- |
| FIXED_SET DFN simulation | ✅ | — | 0.2C, 1.0C, 2.0C; 1,500 cycles each; zero failures |
| Kinetic extrapolator | ✅ | `data/pilot_1500/` | FIXED_SET 1,500-cycle ground truth ($0.65\%$ error from $K=100$) |
| GP surrogate | ✅ | `data/sweep/sweep_fixedset.npz` | Trained on 60-point canonical FIXED_SET sweep |
| Unseen C-rate ($1.33389\text{C}$) | ✅ | Held-out test simulation | Mean $0.0017\%$, max $0.0084\%$ error ($100\%$ conformal coverage) |
| Unseen C-rate ($1.44224\text{C}$) | ✅ | Held-out 1,500-cycle simulation | Mean $0.0019\%$ (first 50 cyc); $0.50\%$ mean error across full 1,500 cyc ($K=100$) |

---

## Measured Results (FIXED_SET, Validated)

### 1,500-Cycle Trajectories

| C-rate | SOH at Cycle 500 | SOH at Cycle 1,000 | SOH at Cycle 1,500 | Total Fade |
|:------:|:-----------------:|:-------------------:|:-------------------:|:----------:|
| **0.2C** | 0.9715 | 0.9389 | 0.9147 | 8.53% |
| **1.0C** | 0.9633 | 0.9321 | 0.9017 | 9.83% |
| **2.0C** | 0.8934 | 0.8043 | 0.7974 | 20.26% |

*SOH normalised to each run's own Cycle-1 capacity (per-cell normalisation).*

> **Note on knee detection**: Late-to-early slope ratios are 0.22, 0.28, 0.30 for 0.2C, 1.0C, 2.0C respectively — all below 1.0. No rollover was detected within 1,500 cycles at these three C-rates. This does not exclude a knee at higher C-rates or longer horizons.

### Extrapolation Accuracy (FIXED_SET, 1.0C ground truth)

Calibrate on first $K$ cycles; measure worst-case absolute SOH error over all cycles $> K$:

| $K$ | Best Form | Sup Error (all cycles $> K$) | Error at Cycle 1,500 |
|:---:|:---:|:---:|:---:|
| 50 | sqrtN | 0.0485 (4.85%) | Not measured separately |
| **100** | sqrtN | **0.0485 (4.85%)** | **≈ 0.65%** |
| 200 | sqrtN | 0.0427 (4.27%) | ≈ 0.19% |
| 500 | power | 0.0289 (2.89%) | < 0.02% |

*Sup error is the maximum over the three anchor C-rates (0.2C, 1.0C, 2.0C). At 2.0C, errors at K=100 reach ≈ 4%.*

---

## Project Structure

```
battery_SOH_prediction/
│
├── src/                            # Core Python modules
│   ├── model.py                    #   DFN model definition (FIXED_SET spec)
│   ├── simulator.py                #   Chunked simulation runner (rtol=atol=1e-6)
│   ├── extrapolator.py             #   Hold-out extrapolation benchmarking
│   └── gp_surrogate.py             #   GP emulator (revalidated on FIXED_SET)
│
├── scripts/                        # CLI entry-point scripts
│   ├── run_simulation.py           #   Run a new PyBaMM simulation
│   ├── run_fixedset_sweep.py       #   Resumable FIXED_SET sweep runner
│   ├── run_analysis.py             #   Run extrapolation analysis
│   ├── run_surrogate.py            #   Train GP surrogate + conformal bands
│   ├── eval_zeroshot.py            #   Zero-shot interpolation benchmark
│   └── compare_model_vs_algo.py    #   Model vs Algorithm comparison plot
│
├── data/
│   ├── sweep/                      #   Packaged sweep datasets (sweep_fixedset.npz)
│   ├── sweep_fixedset/             #   Raw 50-cycle FIXED_SET CSVs (60 conditions)
│   └── pilot_1500/                 #   FIXED_SET 1,500-cycle validated data
│       ├── {c}C_cycles.csv         #   Per-C-rate trajectory (0.2C, 1.0C, 2.0C)
│       └── analysis/               #   Holdout errors, trajectory summary, pilot.npz
│
├── figures/                        # Publication plots (FIXED_SET validated data)
│   ├── comparison_1C_fit100.png    #   K=100 algorithm vs physics comparison
│   ├── comparison_1C_fit500.png    #   K=500 algorithm vs physics comparison
│   ├── emulator_validation.png     #   4-panel GP diagnostics + conformal band
│   └── zeroshot_eval_1.33389C.png  #   Zero-shot physical evaluation
│
├── archive/                        # Retired files (old parameter set)
│   ├── figures/                    #   fig1–fig3 from pre-FIXED_SET pilot
│   ├── docs/                       #   REPORT and PRESENTATION from old model
│   └── sweep_kaggle_old_params.npz #   Old 50-cycle GP training data
│
├── docs/                           # Technical documentation
│   ├── PRESENTATION.md             #   Faculty technical dossier & defense guide
│   ├── ZERO_SHOT_AND_CALIBRATION_GUIDE.md  # Horizon selection & zero-shot validation
│   ├── MODEL_GUIDE.md              #   Capabilities, horizon guide, API usage
│   ├── DECISIONS_AND_RATIONALE.md  #   Full decision log incl. parameter investigation
│   └── CHANGES_TO_ORIGINAL_CODE.md #   Audit of modifications from original researcher script
│
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
```

Requires PyBaMM `26.8.0.0` with IDAKLUSolver. See `archive/ENV.txt` for the exact working pip freeze.

### 1. Run the Kinetic Extrapolation Analysis

Benchmarks all functional forms on the validated FIXED_SET 1,500-cycle data:

```bash
python scripts/run_analysis.py --dir data/pilot_1500 --out data/pilot_1500/analysis
```

### 2. Compare Physics Model vs Extrapolation Algorithm

```bash
# Calibrate on 100 cycles; extrapolate to 1,500
python scripts/compare_model_vs_algo.py --crate 1.0 --fit-window 100

# High-precision mode with 500-cycle calibration
python scripts/compare_model_vs_algo.py --crate 1.0 --fit-window 500
```

### 3. Run a New Simulation at Any C-Rate

```bash
python scripts/run_simulation.py --crate 1.3 --n-cycles 1500 --chunk 50
```

---

## Model Specification (FIXED_SET)

Defined in `src/model.py`:

| Feature | Configuration |
|:--------|:-------------|
| Base parameter set | `Chen2020_composite` |
| Particle phases | Graphite (primary) + Silicon (secondary) |
| SEI | Solvent-diffusion limited |
| Loss of active material | Stress-driven (both electrodes) |
| Lithium plating | Partially reversible |
| Solver | IDAKLUSolver (`rtol=1e-6`, `atol=1e-6`; deviation from FIXED_SET §B `atol=1e-8` approved for runtime — see `docs/DECISIONS_AND_RATIONALE.md §Stage 4`) |
| Charging protocol | 0.3C CCCV to 4.2V (C/100 cutoff) |

---

## Extrapolation Method

The composite kinetic form captures both major degradation contributions:

$$\text{SOH}(N) = c - b_1 \sqrt{N} - b_2 N$$

Coefficients fitted via ordinary least squares on the first $K$ cycles, then extrapolated to predict remaining life.

> **Note**: The $\sqrt{N}$ and $N$ terms fit the observed simulator curvature well. Whether they separately identify SEI diffusion versus active material loss mechanisms requires further mechanistic analysis beyond curve-fitting.

---

## Documentation

| Document | Description |
|:---------|:-----------|
| [`docs/PRESENTATION.md`](docs/PRESENTATION.md) | **Faculty Technical Dossier**: 1-week vs 1-year prognosis rationale, horizon trade-offs, and defense Q&A |
| [`docs/ZERO_SHOT_AND_CALIBRATION_GUIDE.md`](docs/ZERO_SHOT_AND_CALIBRATION_GUIDE.md) | Calibration horizon selection; cross-dataset evaluation at 1.3338905C |
| [`docs/MODEL_GUIDE.md`](docs/MODEL_GUIDE.md) | Capabilities, horizon guide, API usage |
| [`docs/DECISIONS_AND_RATIONALE.md`](docs/DECISIONS_AND_RATIONALE.md) | Full decision log including parameter set investigation |
| [`docs/CHANGES_TO_ORIGINAL_CODE.md`](docs/CHANGES_TO_ORIGINAL_CODE.md) | **Technical Audit**: Detailed modifications from original research script to production model |

---

## License

[MIT](LICENSE)
