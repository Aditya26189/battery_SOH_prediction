#!/usr/bin/env python
"""Evaluate Zero-Shot Interpolation Error at Unseen C-rate 1.3338905C.

Compares GP Surrogate prediction against genuine FIXED_SET DFN ground truth
(both using the exact same physical parameter specification).

Usage:
------
    python scripts/eval_zeroshot.py
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
from src.gp_surrogate import Emulator, load_data, loo_scores, conformal_halfwidth, ALPHA

SWEEP_NPZ = "data/sweep/sweep_fixedset.npz"
TEST_CSV = "data/sweep_fixedset/1.33389C_cycles.csv"
OUT_FIG = "figures/zeroshot_eval_1.33389C.png"


def evaluate_zeroshot(crate_test=1.3338905, sweep_path=SWEEP_NPZ, test_csv=TEST_CSV, fig_out=OUT_FIG):
    if not os.path.exists(sweep_path):
        sweep_path = "data/sweep/sweep.npz"

    if not os.path.exists(sweep_path):
        print(f"Error: Sweep dataset {sweep_path} not found.")
        return

    if not os.path.exists(test_csv):
        print(f"Error: Physical ground-truth test CSV {test_csv} not found.")
        return

    # 1. Load training sweep
    crates, N, Y = load_data(sweep_path)
    print(f"--- Training GP Surrogate on FIXED_SET Sweep ---")
    print(f"Available training C-rates: {len(crates)} (range: [{crates.min():.3f}, {crates.max():.3f}])")

    if len(crates) < 3:
        print(f"Note: Only {len(crates)} C-rate(s) available in {sweep_path}. Need at least 3 for multi-point GP.")
        return

    # Fit GP emulator
    em = Emulator(N).fit(crates, Y, n_restarts=10)

    # Conformal band half-width
    scores = loo_scores(crates, N, Y, n_restarts=2)
    q = conformal_halfwidth(scores, alpha=ALPHA)

    # 2. Predict at test C-rate
    c_eval = np.array([crate_test])
    pred_soh = em.predict(c_eval)[0]
    lo_soh = pred_soh - q
    hi_soh = pred_soh + q

    # 3. Load Physics Ground Truth
    npz_data = np.load(sweep_path)
    bol_cap = float(npz_data["bol_capacity"]) if "bol_capacity" in npz_data else Y[0, 0]

    df_true = pd.read_csv(test_csv)
    q_true = df_true["discharge_capacity_Ah"].values
    soh_true = q_true / bol_cap  # SOH relative to true Beginning-of-Life (0.2C Cycle 1)

    # Calculate errors
    diff = np.abs(pred_soh - soh_true)
    rel_err_pct = (diff / soh_true) * 100

    print(f"\n=== Zero-Shot Generalization Benchmark at {crate_test}C ===")
    print(f"{'Cycle':<8} | {'DFN Physics':<14} | {'GP Prediction':<14} | {'Abs Error':<12} | {'Rel Error %':<10}")
    print("-" * 68)
    for k in [1, 5, 10, 20, 30, 40, 50]:
        if k <= len(soh_true):
            print(f"{k:<8} | {soh_true[k-1]:<14.5f} | {pred_soh[k-1]:<14.5f} | {diff[k-1]:<12.6f} | {rel_err_pct[k-1]:<10.4f}%")

    mean_rel_err = np.mean(rel_err_pct)
    max_rel_err = np.max(rel_err_pct)
    sup_err = np.max(diff)

    print("-" * 68)
    print(f"Mean Relative Error: {mean_rel_err:.4f}%")
    print(f"Max Relative Error:  {max_rel_err:.4f}% (Cycle {np.argmax(rel_err_pct)+1})")
    print(f"Sup-norm Error:      {sup_err:.6f}")
    print(f"90% Conformal Band:  ±{q:.5f}")

    in_band = np.all((soh_true >= lo_soh) & (soh_true <= hi_soh))
    print(f"Inside Conformal Band across ALL 50 cycles: {'YES (Valid Coverage)' if in_band else 'NO'}")

    # 4. Plot Comparison
    os.makedirs(os.path.dirname(fig_out), exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), dpi=150, sharex=True)

    # Trajectory overlay
    ax1.plot(N, soh_true, "k-", lw=2.2, label=f"DFN Physics Ground Truth ({crate_test}C)")
    ax1.plot(N, pred_soh, "r--", lw=2.0, label=f"GP Surrogate Zero-Shot Prediction")
    ax1.fill_between(N, lo_soh, hi_soh, color="red", alpha=0.2, label=f"90% Conformal Band (±{q:.4f})")

    # Show nearest training C-rates
    nearest_idx = np.argsort(np.abs(crates - crate_test))[:2]
    for idx in nearest_idx:
        ax1.plot(N, Y[idx], ":", alpha=0.6, label=f"Training C-rate ({crates[idx]:.3f}C)")

    ax1.set_ylabel("State of Health (SOH)")
    ax1.set_title(f"Zero-Shot SOH Trajectory Prediction at Unseen C-rate {crate_test}C", fontweight="bold")
    ax1.legend(loc="lower left", fontsize=9)
    ax1.grid(True, ls="--", alpha=0.5)

    # Error curve
    ax2.plot(N, rel_err_pct, "b-o", markersize=3, lw=1.5, label="Relative Error (%)")
    ax2.axhline(mean_rel_err, color="orange", ls="--", label=f"Mean Error: {mean_rel_err:.4f}%")
    ax2.set_xlabel("Cycle Number")
    ax2.set_ylabel("Relative Error [%]")
    ax2.set_title("Zero-Shot Interpolation Error Across 50 Cycles", fontsize=11)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, ls="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(fig_out, bbox_inches="tight")
    plt.close()
    print(f"\nGenerated validation plot: {fig_out}")


if __name__ == "__main__":
    evaluate_zeroshot()
