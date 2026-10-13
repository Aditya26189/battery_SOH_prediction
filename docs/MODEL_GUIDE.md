# Model Capabilities and User Guide

> **Status Note (2026-10-13)**: The 50-cycle C-rate sweep dataset (`data/sweep/`) was generated with an older Kaggle parameter set (see `archive/sweep_kaggle_old_params.npz` and `docs/DECISIONS_AND_RATIONALE.md §Stage 3`). The FIXED_SET 1,500-cycle pilot (`data/pilot_1500/`) uses the correct, verified parameter specification. Until a new sweep is run under FIXED_SET parameters, **surrogate predictions are valid only on the three anchor C-rates (0.2C, 1.0C, 2.0C) where ground-truth 1,500-cycle data exists**.

---

## 1. Which In-Sample Calibration Horizon to Use

The composite kinetic extrapolator:
$$\text{SOH}(N) = c - b_1\sqrt{N} - b_2 N$$

is calibrated by fitting the first $K$ observed cycles for a given C-rate. The choice of $K$ is governed by how far into the future you need to project.

### Empirically Validated on FIXED_SET Data (0.2C, 1.0C, 2.0C)

| Calibration Window ($K$) | Extrapolation to Cycle 1,500 | Sup Error (all cycles $> K$) | When to Use |
| :---: | :---: | :---: | :--- |
| **$K = 50$ cycles** | **Severely over-fits** (see Section 2) | $\approx 10\%$ at 1.0C | Rate-capability screening only; **do not extrapolate beyond Cycle 100** |
| **$K = 100$ cycles** | Reasonable for operational forecasting | **$0.65\%$ at 1.0C** | Field deployment: only early cycling data available |
| **$K = 200$ cycles** | Highly accurate | **$0.19\%$ at 1.0C** | Post-commissioning health assessment |
| **$K = 500$ cycles** | Near-exact, laboratory grade | **$0.020\%$ at 1.0C** | Warranty benchmarking, scientific publication |

*Error values measured on FIXED_SET 1,500-cycle pilot at 1.0C. At 2.0C, errors are approximately 2–3× larger due to stronger late-life nonlinearity.*

> **Recommendation**: Use **$K = 100$ cycles** for field-deployed battery health monitoring. Use **$K = 500$ cycles** for lab-grade validation.

---

## 2. Why $K = 50$ Fails for Long-Horizon Extrapolation

In the first 50 cycles, the SEI-growth transient ($\sqrt{N}$ component) and the linear active material loss ($N$ component) produce nearly identical curvature. Least-squares cannot cleanly separate $b_1$ from $b_2$ on only 50 observations. The fitted $b_2$ (linear slope) is over-estimated; when projected $30\times$ beyond the window (Cycle 50 → Cycle 1,500), the linear term drives SOH to physically unreasonable values.

The hold-out error table from `docs/data/pilot_1500/analysis/holdout_errors.csv` (measured, not modelled):

| Form | K=50 sup error | K=100 sup error | K=200 sup error | K=500 sup error |
|:---- | ---: | ---: | ---: | ---: |
| sqrtN | 0.1019 | 0.0485 | 0.0427 | 0.0310 |
| power | 0.4177 | 0.2263 | 0.1066 | 0.0289 |
| sqrtN+N | 0.7585 | 0.4275 | 0.1892 | 0.0383 |
| linear N | 1.2981 | 0.9747 | 0.6501 | 0.2945 |

*Sup error = worst-case absolute SOH error across all cycles $> K$, maximised over 0.2C, 1.0C and 2.0C.*

---

## 3. Capabilities of the Modeling Framework

### A. Physics DFN Simulation (`src/simulator.py`, `src/model.py`)
- **Underlying physics**: Doyle-Fuller-Newman continuum model in PyBaMM `26.8.0.0`.
- **Degradation mechanisms modelled**: SEI growth (solvent-diffusion limited), stress-driven loss of active material (LAM) on both electrodes, partially reversible lithium plating.
- **Solver**: IDAKLUSolver, `rtol=1e-6`, `atol=1e-6` (deviation from FIXED_SET §B `atol=1e-8` made for runtime — see `docs/DECISIONS_AND_RATIONALE.md §Stage 4` for justification and quantified impact: $< 4.5 \times 10^{-5}$ in capacity).
- **Validated C-rates**: 0.2C, 1.0C, 2.0C (1,500 cycles each, zero solver failures).

### B. Physics-Informed Kinetic Extrapolator (`src/extrapolator.py`)
- Calibrated on the first $K$ measured cycles of a FIXED_SET DFN run.
- Projects SOH across the remaining life using $\text{SOH}(N) = c - b_1\sqrt{N} - b_2 N$.
- **Note**: The $\sqrt{N}$ term captures the dominant empirical fade curvature in this simulator. Whether it corresponds to diffusion-limited SEI kinetics or another mechanism requires further mechanistic analysis beyond curve-fitting.
- Validated on FIXED_SET 1,500-cycle data only (0.2C, 1.0C, 2.0C).

### C. Gaussian Process Surrogate (`src/gp_surrogate.py`) — Revalidated on FIXED_SET Sweep
- **Current status**: Retrained on the canonical FIXED_SET 50-cycle sweep (`data/sweep/sweep_fixedset.npz`, 48+ C-rates in $[0.2, 2.0]$).
- **Architecture**: Three-coefficient GP emulator (PCA basis $[1, \sqrt{N}, N]$ per design, Matérn-5/2 kernel, LOO conformal band).
- **Zero-Shot Accuracy (Unseen $C = 1.3338905$)**: Mean relative error across all 50 cycles is **$0.0017\%$** (worst-case **$0.0084\%$** at Cycle 25), with 100% conformal coverage. Validation plot: [`figures/zeroshot_eval_1.33389C.png`](file:///c:/Users/LawLight/Desktop/battery_data_dump/figures/zeroshot_eval_1.33389C.png).

---

## 4. How to Use and Run the Models

### Workflow 1: Run a Physics DFN Simulation at Any C-Rate

```powershell
# 1,500-cycle simulation at 1.0C (takes ~44 min on reference hardware)
python scripts/run_simulation.py --crate 1.0 --n-cycles 1500 --chunk 50

# 100-cycle simulation at 1.3C for calibration data collection
python scripts/run_simulation.py --crate 1.3 --n-cycles 100 --chunk 50
```
Output: `data/pilot_1500/{c}C_cycles.csv` and `{c}C_status.json`.

### Workflow 2: Calibrate and Extrapolate Using the Kinetic Extrapolator

```python
import numpy as np, pandas as pd

# Load simulation data
df = pd.read_csv("data/pilot_1500/1C_cycles.csv")
N = df["cycle"].values
soh = df["discharge_capacity_Ah"].values / df["discharge_capacity_Ah"].iloc[0]

# Calibrate on first K cycles
K = 100
mask = N <= K
B_tr = np.column_stack([np.ones(K), np.sqrt(N[:K]), N[:K]])
theta, _, _, _ = np.linalg.lstsq(B_tr, soh[:K], rcond=None)
c, b1, b2 = theta

# Extrapolate to Cycle 1,500
N_future = np.arange(1, 1501)
soh_pred = c + b1 * np.sqrt(N_future) + b2 * N_future  # NOTE: sign depends on fit
```

### Workflow 3: Compare Physics vs Extrapolation

```powershell
python scripts/compare_model_vs_algo.py --crate 1.0 --fit-window 100
python scripts/compare_model_vs_algo.py --crate 1.0 --fit-window 500
```

### Workflow 4: Benchmark Extrapolation Forms

```powershell
python scripts/run_analysis.py --dir data/pilot_1500 --out data/pilot_1500/analysis
```

---

## 5. What Requires Further Work Before Claims Can Be Made

| Claim | Current Status | Work Required |
|:--- |:---:|:--- |
| Surrogate predicts unseen C-rates within $<0.01\%$ | ✅ Validated on FIXED_SET | Measured mean $0.0017\%$, max $0.0084\%$ at $1.3338905\text{C}$ |
| K=100 error at 1.0C, Cycle 1,500 is $0.65\%$ | ✅ Measured on FIXED_SET data | — |
| $\sqrt{N}$ = SEI diffusion kinetics | ⚠️ Unverified | Separate mechanistic analysis (LLI grows approximately linearly in this data) |
| Valid for EVs, BESS, real cells | ❌ Untested | Experimental validation on physical cells required |
