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

## 2. Experiment B: Cross-Dataset Evaluation at Unseen $C = 1.3338905$ (Transparency Disclosure)

This section presents what was experimentally run and what the numbers actually mean.

### Setup

- **Surrogate training data**: Kaggle 50-cycle sweep (`archive/sweep_kaggle_old_params.npz`) — a different parameter configuration from FIXED_SET.
- **Ground truth**: A new FIXED_SET DFN simulation ran for 50 cycles at $C = 1.3338905$.
- **This is a cross-dataset comparison**: The two systems differ in SEI diffusivity naming/values, positive electrode mechanics, and negative LAM rate constants. See `docs/DECISIONS_AND_RATIONALE.md §Stage 3` for quantified differences.

### Measured Results

| Cycle | FIXED_SET DFN Truth ($Q$, SOH) | Kaggle-Surrogate Prediction (SOH) | Absolute Delta | Source of Error |
| :---: | :---: | :---: | :---: | :---: |
| **1** | $4.81282\text{ Ah}$, $\text{SOH}=0.98266$ | $0.97871$ | $0.00395$ (0.40%) | Parameter-set offset |
| **10** | $4.80414\text{ Ah}$, $\text{SOH}=0.98088$ | $0.97227$ | $0.00862$ (0.88%) | Offset + diverging fade |
| **30** | $4.78933\text{ Ah}$, $\text{SOH}=0.97786$ | $0.96246$ | $0.01540$ (1.58%) | Offset + diverging fade |
| **50** | $4.77665\text{ Ah}$, $\text{SOH}=0.97527$ | $0.95397$ | $0.02130$ (2.18%) | Offset + diverging fade |

- **Mean error over 50 cycles**: $1.36\%$ SOH
- **Worst-case error**: $2.13\%$ SOH (Cycle 50)
- **Cycle-1 error ($0.40\%$)**: Matches the cross-model capacity offset measured in `docs/DECISIONS_AND_RATIONALE.md §Stage 3` ($0.20\%$–$0.40\%$), confirming this is systematic offset, not interpolation error.
- **Error growth ($0.40\% \to 2.13\%$ over 50 cycles)**: Reflects the difference in 50-cycle fade rate between the two parameter sets (Kaggle: $\approx 1.49\%$ fade at 0.2C; FIXED_SET: $\approx 0.21\%$ fade at 0.2C).

### GP Interpolation Fidelity (Internal Consistency Only)

The surrogate's interpolation within its own (Kaggle) manifold was validated by leave-one-out at $1.268\text{C}$:
- **Mean error over 50 cycles**: **$0.0059\%$** (against the Kaggle sweep ground truth)
- **Worst-case error**: **$0.028\%$**

This measures how precisely the GP interpolates between its training points — not how well it predicts FIXED_SET physics.

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
