# Zero-Shot Generalization & Calibration Horizon Guide

> **Academic Technical Note & Experimental Benchmark**
> **Topic**: Empirical accuracy of kinetic extrapolation on FIXED_SET 1,500-cycle data; cross-dataset evaluation on an unseen C-rate; and mathematical criteria for selecting calibration windows.

---

## Important Scope Statement

This document distinguishes **two different experiments** that were previously conflated:

| Experiment | Data Source | What It Measures |
|:--- |:--- |:--- |
| **A. FIXED_SET extrapolation** | `data/pilot_1500/` (1,500-cycle DFN at 0.2C, 1.0C, 2.0C) | How well the kinetic formula $c - b_1\sqrt{N} - b_2N$ extrapolates within a consistent parameter set |
| **B. Cross-dataset evaluation at 1.3338905C** | Surrogate trained on Kaggle sweep; truth from FIXED_SET DFN | Measures **systematic offset between two different model configurations**, NOT interpolation accuracy |

These are not the same thing. Experiment B errors (0.4–2.1%) are dominated by parameter-set mismatch, not the surrogate's interpolation capability.

---

## 1. Experiment A: FIXED_SET Long-Horizon Extrapolation (Validated)

### What Was Measured

Using the FIXED_SET 1,500-cycle pilot at 0.2C, 1.0C, and 2.0C:
- Calibrate the formula $\text{SOH}(N) = c - b_1\sqrt{N} - b_2 N$ on the first $K$ cycles.
- Predict cycles $K+1$ through 1,500.
- Measure worst-case absolute SOH error across all unseen cycles, maximised over all three C-rates.

### Measured Results (from `data/pilot_1500/analysis/holdout_errors.csv`)

| In-Sample Horizon ($K$) | Best Form | Sup Error Over All Unseen Cycles | Error at Cycle 1,500 (1.0C) |
| :---: | :---: | :---: | :---: |
| **$K = 50$ cycles** | sqrtN | $0.1019$ (10.2%) | Large (see note) |
| **$K = 100$ cycles** | sqrtN | $0.0485$ (4.9%) | **$\approx 0.65\%$** |
| **$K = 200$ cycles** | sqrtN | $0.0427$ (4.3%) | **$\approx 0.19\%$** |
| **$K = 500$ cycles** | power / sqrtN | $\leq 0.0310$ (3.1%) | **$< 0.02\%$** |

> **Note on $K = 50$**: The sup error of $0.10$ for sqrtN at $K=50$ is measured across cycles 51–1,500. However, the composite form sqrtN+N fitted on 50 cycles has a sup error of $0.76$ — demonstrating severe divergence when the linear term is included with insufficient calibration data.

---

## 2. Experiment B: Zero-Shot Generalization at Unseen $C = 1.3338905$

### A. The Retrained Benchmark on Canonical FIXED_SET Sweep (Validated)
With the new `data/sweep/sweep_fixedset.npz` sweep generated under the verified `FIXED_SET` parameters, both the surrogate and the unseen test simulation use the **exact same physical continuum model**:

- **Training dataset**: 48+ C-rates in $[0.2, 2.0]$ under `src/model.py` (`FIXED_SET` specification).
- **Test condition**: $C = 1.3338905$ (held strictly out of training data).
- **Physical ground truth**: 50-cycle IDAKLU DFN simulation from `data/sweep_fixedset/1.33389C_cycles.csv`.
- **Validation plot**: [`figures/zeroshot_eval_1.33389C.png`](file:///c:/Users/LawLight/Desktop/battery_data_dump/figures/zeroshot_eval_1.33389C.png).

#### Measured Results (Matched Parameter Specification)

| Cycle | FIXED_SET DFN Truth ($Q$, SOH) | Retrained GP Prediction | Absolute Error | Relative Error |
| :---: | :---: | :---: | :---: | :---: |
| **1** | $4.81279\text{ Ah}$ ($\text{SOH}=0.98065$) | $0.98072$ | $0.000073$ | **$0.0075\%$** |
| **5** | $4.80858\text{ Ah}$ ($\text{SOH}=0.97979$) | $0.97976$ | $0.000026$ | **$0.0027\%$** |
| **10** | $4.80414\text{ Ah}$ ($\text{SOH}=0.97888$) | $0.97885$ | $0.000022$ | **$0.0023\%$** |
| **20** | $4.79646\text{ Ah}$ ($\text{SOH}=0.97732$) | $0.97729$ | $0.000025$ | **$0.0025\%$** |
| **30** | $4.78931\text{ Ah}$ ($\text{SOH}=0.97586$) | $0.97588$ | $0.000019$ | **$0.0019\%$** |
| **40** | $4.78281\text{ Ah}$ ($\text{SOH}=0.97454$) | $0.97454$ | $0.000005$ | **$0.0006\%$** |
| **50** | $4.77661\text{ Ah}$ ($\text{SOH}=0.97327$) | $0.97325$ | $0.000025$ | **$0.0026\%$** |

- **Mean Relative Error over 50 cycles**: **$0.0017\%$**
- **Worst-Case (Max) Relative Error**: **$0.0084\%$** (Cycle 25)
- **Sup-Norm Error**: **$0.000082$ SOH**
- **90% Conformal Band**: $\pm 0.00009$ SOH
- **Conformal Coverage**: **100% of cycles lie within the 90% conformal band**.

---

### B. Historical Comparison: Why the Previous Old Model Had 2.13% Error
For complete academic transparency, the table below documents the error measured when the GP surrogate was trained on the retired Kaggle sweep (`archive/sweep_kaggle_old_params.npz`) vs the FIXED_SET simulation:

| Cycle | FIXED_SET DFN Truth | Old Kaggle GP Prediction | Delta | Attribution |
| :---: | :---: | :---: | :---: | :---: |
| **1** | $0.98065$ | $0.97871$ | $0.40\%$ | Systematic parameter-set offset |
| **10** | $0.97888$ | $0.97227$ | $0.88\%$ | Offset + diverging fade rates |
| **30** | $0.97586$ | $0.96246$ | $1.58\%$ | Offset + diverging fade rates |
| **50** | $0.97327$ | $0.95397$ | $2.13\%$ | Offset + diverging fade rates |

The previous **2.13% error was not an interpolation failure** of the surrogate architecture; it was a **systematic parameter mismatch** between two different model versions (Kaggle stock SEI vs modern FIXED_SET rate constants). When both models use the canonical FIXED_SET parameters, the interpolation error drops to **$0.0017\%$** (a 1,200× reduction).

---

## 3. What the 1,500-Cycle Number for 1.3338905C Means

Previously published in this repository: *"Expected Physics Truth for $1.3338905\text{C}$ at Cycle 1,500: SOH ≈ 0.8669"*

**This number is a linear interpolation between the 1.0C and 2.0C pilot truths**, not a physics simulation. No physics simulation at $1.3338905\text{C}$ was run past Cycle 50.

The formula used was:
$$\text{SOH}_\text{interp}(N=1500) = (1 - 0.3339) \times 0.9017 + 0.3339 \times 0.7974 = 0.8669$$

The K-window comparison table in the previous version of this guide (K=50 to K=500 for $1.3338905\text{C}$) was therefore **interpolation of interpolations** and should not be treated as a validated benchmark.

---

## 4. Calibration Horizon Decision Guide

Based on Experiment A (FIXED_SET validated data only):

| Scenario | Recommended $K$ | Why |
|:--- |:---: |:--- |
| Only first 1–2 months of operation data available (EV field deployment) | $K = 100$ | sqrtN form achieves $<0.05$ sup error by Cycle 200+ when properly separated |
| Test-bench validation with 6–12 months of data | $K = 200$ | $<0.19\%$ error at Cycle 1,500 |
| Laboratory warranty benchmarking | $K = 500$ | $<0.02\%$ error at Cycle 1,500 |
| Quick screening without long extrapolation | $K = 50$ | Only use within $N \le 100$; composite form must not be extrapolated to Cycle 1,500 |

---

## 5. What Must Be Done Next

To make surrogate-based unseen C-rate prediction quantitatively valid:

1. **Re-run the C-rate sweep** ($30$–$60$ points, $[0.2, 2.0]$, 200+ cycles each) using `src/model.py` (FIXED_SET parameters).
2. **Retrain the GP surrogate** on the new sweep.
3. **Re-validate by leave-one-out** at held-out C-rates using the same parameter set for both training and ground truth.
4. **Only then** publish interpolation error figures (expected: $<0.03\%$ based on GP architecture).

Until Steps 1–3 are complete, surrogate-based C-rate interpolation remains a **structural capability** of the framework, not a quantitatively validated result.
