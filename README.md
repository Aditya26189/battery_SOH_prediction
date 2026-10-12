# Battery State-of-Health (SOH) Prediction

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyBaMM](https://img.shields.io/badge/PyBaMM-26.8-green.svg)](https://pybamm.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Physics-based electrochemical degradation modeling and surrogate prediction
> for composite graphite/silicon lithium-ion cells, built on **PyBaMM**.

---

## Overview

This project implements a complete pipeline for predicting battery
State-of-Health (SOH) across the full life of a lithium-ion cell:

1. **Physics Model** — A Doyle–Fuller–Newman (DFN) electrochemical model
   configured with the `FIXED_SET.md` specification (SEI growth, stress-driven
   LAM, lithium plating, porosity changes).

2. **Full-Life Simulation** — 1,500-cycle simulations at three C-rates
   (0.2C, 1.0C, 2.0C) with chunked execution and checkpointing.

3. **Composite Extrapolator** — A physics-informed functional form
   `SOH(N) = c − b₁√N − b₂N` that predicts 1,500-cycle life from only
   **100 early cycles** with < 0.64% error.

4. **GP Surrogate** — A Gaussian Process emulator mapping C-rate → SOH
   trajectory with leave-one-out conformal prediction bands (90% coverage).

---

## Key Results

| C-rate | SOH @ Cycle 1500 | Total Fade | EoL (80%) Crossing |
|:------:|:-----------------:|:----------:|:------------------:|
| 0.2C   | 96.47%            | 3.53%      | —                  |
| 1.0C   | 90.17%            | 9.83%      | —                  |
| 2.0C   | 79.74%            | 20.26%     | Cycle 1473         |

**No knee-rollover** was observed at any C-rate — late/early slope ratios
remain below 1.0 across all conditions, indicating smooth, sublinear fade.

### Extrapolation Accuracy (1.0C)

| Training Window | Composite Error | Power-Law Error |
|:---------------:|:---------------:|:---------------:|
| 50 cycles       | 0.119           | 0.033           |
| 100 cycles      | **0.064%**      | 0.034           |
| 200 cycles      | 0.075           | 0.040           |
| 500 cycles      | 0.037           | 0.023           |

---

## Project Structure

```
battery_SOH_prediction/
│
├── src/                            # Core Python modules
│   ├── model.py                    #   DFN model definition (FIXED_SET spec)
│   ├── simulator.py                #   Chunked full-life simulation runner
│   ├── extrapolator.py             #   Hold-out extrapolation benchmarking
│   └── gp_surrogate.py             #   GP emulator with conformal bands
│
├── scripts/                        # CLI entry-point scripts
│   ├── run_simulation.py           #   Run a new PyBaMM simulation
│   ├── run_analysis.py             #   Run extrapolation analysis
│   ├── run_surrogate.py            #   Train GP + conformal bands
│   ├── compare_model_vs_algo.py    #   Model vs Algorithm comparison
│   └── prepare_sweep.py            #   Aggregate raw CSVs → sweep.npz
│
├── data/                           # All datasets
│   ├── sweep/                      #   60-point C-rate sweep (50-cycle CSVs)
│   │   ├── sweep.npz               #   Pre-packaged sweep dataset
│   │   └── *.csv                   #   Raw degradation data (60 files)
│   └── pilot_1500/                 #   1500-cycle ground-truth results
│       ├── {c}C_cycles.csv         #   Per-C-rate trajectory data
│       └── analysis/               #   Extrapolation benchmark outputs
│
├── figures/                        # Publication-quality plots
│   ├── fig1_trajectories.png       #   SOH trajectory curves
│   ├── fig2_holdout_error.png      #   Extrapolation error vs window K
│   ├── fig3_extrapolation_*.png    #   Ground truth vs predicted curves
│   ├── comparison_1C_fit100.png    #   Model vs algorithm overlay
│   └── emulator_validation.png     #   GP diagnostics (4-panel)
│
├── docs/                           # Technical documentation
│   ├── PRESENTATION.md             #   Faculty technical dossier
│   ├── REPORT.md                   #   1500-cycle pilot report
│   ├── RESULTS.md                  #   Extrapolation benchmark tables
│   ├── DECISIONS_AND_RATIONALE.md  #   Architecture decisions log
│   └── DIAG_REPORT.md             #   Parameter ablation diagnostics
│
├── requirements.txt                # Python dependencies
├── LICENSE                         # MIT License
└── README.md                       # This file
```

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/Aditya26189/battery_SOH_prediction.git
cd battery_SOH_prediction
pip install -r requirements.txt
```

### 2. Compare Model vs Algorithm

See how the composite extrapolator trained on 100 early cycles predicts
the full 1,500-cycle trajectory:

```bash
python scripts/compare_model_vs_algo.py --crate 1.0 --fit-window 100
```

### 3. Run a New Simulation

Execute a custom PyBaMM simulation under the verified FIXED_SET specification:

```bash
python scripts/run_simulation.py --crate 1.0 --n-cycles 500 --chunk 50
```

### 4. Run Extrapolation Analysis

Benchmark all functional forms against the ground-truth trajectories:

```bash
python scripts/run_analysis.py --dir data/pilot_1500 --out data/pilot_1500/analysis
```

### 5. Train the GP Surrogate

Train the 1-D GP emulator across the 60-point C-rate sweep:

```bash
python scripts/run_surrogate.py
```

---

## Physics Model

The DFN model is configured with the `FIXED_SET.md` specification
(see [`src/model.py`](src/model.py)):

| Feature | Configuration |
|:--------|:-------------|
| Base parameter set | `Chen2020_composite` |
| Particle phases | Graphite (primary) + Silicon (secondary) |
| SEI | Solvent-diffusion limited |
| Loss of active material | Stress-driven (both electrodes) |
| Lithium plating | Partially reversible |
| Solver | IDAKLUSolver (rtol=1e-6, atol=1e-6) |
| Charging protocol | 0.3C CCCV to 4.2V (C/100 cutoff) |

---

## Extrapolation Method

The **composite two-regime** form captures both degradation mechanisms:

$$\text{SOH}(N) = c - b_1 \sqrt{N} - b_2 N$$

- **√N term** — diffusion-limited SEI film growth (parabolic kinetics)
- **N term** — stress-driven particle cracking and LAM (linear kinetics)

Coefficients are fitted via ordinary least squares on the first *K* cycles,
then extrapolated to predict the remaining life.

---

## Documentation

| Document | Description |
|:---------|:-----------|
| [`docs/MODEL_GUIDE.md`](docs/MODEL_GUIDE.md) | Model capabilities, horizon guide ($K=100$ vs $500$), and API usage |
| [`docs/PRESENTATION.md`](docs/PRESENTATION.md) | Faculty technical presentation dossier |
| [`docs/REPORT.md`](docs/REPORT.md) | Comprehensive 1,500-cycle pilot report |
| [`docs/DECISIONS_AND_RATIONALE.md`](docs/DECISIONS_AND_RATIONALE.md) | Architecture decisions log |
| [`docs/DIAG_REPORT.md`](docs/DIAG_REPORT.md) | Parameter ablation diagnostics |

---

## License

[MIT](LICENSE)
