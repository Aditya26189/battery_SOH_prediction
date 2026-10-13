#!/usr/bin/env python
"""Compare 1500-cycle Physics Ground Truth vs Zero-Shot GP & Extrapolator for C = 1.4422357.

Usage:
------
    python scripts/compare_unseen_1500.py
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
CSV_PATH = "data/pilot_1500/1.44224C_cycles.csv"
OUT_FIG = "figures/comparison_1.44224C_1500.png"
C_RATE = 1.4422357


def main():
    if os.path.exists(CSV_PATH):
        csv_file = CSV_PATH
    elif os.path.exists("data/pilot_1500/1.4422357C_cycles.csv"):
        csv_file = "data/pilot_1500/1.4422357C_cycles.csv"
    elif os.path.exists("data/sweep_fixedset/1.44224C_cycles.csv"):
        csv_file = "data/sweep_fixedset/1.44224C_cycles.csv"
    else:
        print(f"Simulation file {CSV_PATH} not found yet (still running initial chunk).")
        return

    df = pd.read_csv(csv_file)
    n_have = len(df)
    print(f"--- Loaded {n_have} cycles of physical simulation for C = {C_RATE} ---")

    npz_data = np.load(SWEEP_NPZ if os.path.exists(SWEEP_NPZ) else "data/sweep/sweep.npz")
    bol_cap = float(npz_data["bol_capacity"]) if "bol_capacity" in npz_data else df["discharge_capacity_Ah"].iloc[0]

    q_true = df["discharge_capacity_Ah"].values
    soh_true = q_true / bol_cap
    N_true = df["cycle"].values

    # Train GP surrogate on 50-cycle sweep
    crates, N_sweep, Y_sweep = load_data(SWEEP_NPZ if os.path.exists(SWEEP_NPZ) else "data/sweep/sweep.npz")
    em = Emulator(N_sweep).fit(crates, Y_sweep, n_restarts=5)

    if "--fast" in sys.argv:
        q_conformal = 0.00009
    else:
        q_conformal = conformal_halfwidth(loo_scores(crates, N_sweep, Y_sweep, n_restarts=2), alpha=ALPHA)

    # GP Prediction over full 1,500 cycle horizon
    N_full = np.arange(1, 1501)
    coefs = em.coefs(np.array([C_RATE]))[0]
    c0, c1, c2 = coefs
    soh_gp_comp = c0 + c1 * np.sqrt(N_full) + c2 * N_full
    soh_gp_sqrt = c0 + c1 * np.sqrt(N_full)

    # Extrapolator fitted on K=50
    B50 = np.column_stack([np.ones(50), np.sqrt(N_true[:50]), N_true[:50]])
    theta50, _, _, _ = np.linalg.lstsq(B50, soh_true[:50], rcond=None)
    B_full = np.column_stack([np.ones(1500), np.sqrt(N_full), N_full])
    soh_extrap_50 = B_full @ theta50

    # Extrapolator fitted on K=100 (if >= 100 cycles available)
    soh_extrap_100 = None
    if n_have >= 100:
        B100 = np.column_stack([np.ones(100), np.sqrt(N_true[:100]), N_true[:100]])
        theta100, _, _, _ = np.linalg.lstsq(B100, soh_true[:100], rcond=None)
        soh_extrap_100 = B_full @ theta100

    # Print accuracy table for available cycles
    diff_gp = np.abs(soh_gp_comp[:n_have] - soh_true)
    rel_err_gp = (diff_gp / soh_true) * 100

    print(f"\n{'Cycle':<8} | {'Physical DFN':<14} | {'GP Pred':<14} | {'Abs Error':<12} | {'Rel Error %':<10}")
    print("-" * 68)
    sample_points = [1, 10, 25, 50, 75, 100, 150, 200, 300, 400, 500, 750, 1000, 1250, 1500]
    for pt in sample_points:
        if pt <= n_have:
            idx = pt - 1
            print(f"{pt:<8} | {soh_true[idx]:<14.5f} | {soh_gp_comp[idx]:<14.5f} | {diff_gp[idx]:<12.6f} | {rel_err_gp[idx]:<10.4f}%")

    print("-" * 68)
    print(f"Mean Relative Error (Cycles 1..{n_have}): {np.mean(rel_err_gp):.4f}%")
    print(f"Max Relative Error (Cycles 1..{n_have}):  {np.max(rel_err_gp):.4f}%")

    # Generate Publication Plot
    os.makedirs(os.path.dirname(OUT_FIG), exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5), dpi=150, sharex=True)

    # Top panel: Full trajectory overlay
    ax1.plot(N_true, soh_true, "k-", lw=2.5, label=f"Physical DFN Ground Truth ({n_have} cycles completed)")
    ax1.plot(N_full, soh_gp_comp, "r--", lw=2.0, label="GP Surrogate Zero-Shot Prediction (Composite)")
    ax1.plot(N_full, soh_gp_sqrt, "g:", lw=1.8, label="GP Surrogate (Stable Diffusion-Limited)")
    ax1.plot(N_full, soh_extrap_50, color="purple", ls="-.", lw=1.5, label="Kinetic Extrapolator (K=50 Cycles)")
    if soh_extrap_100 is not None:
        ax1.plot(N_full, soh_extrap_100, "b-.", lw=1.8, label="Kinetic Extrapolator (K=100 Cycles)")

    ax1.fill_between(N_full, soh_gp_comp - q_conformal, soh_gp_comp + q_conformal,
                     color="red", alpha=0.15, label=f"90% Conformal Band (±{q_conformal:.4f})")
    ax1.axhline(0.80, color="gray", ls="--", alpha=0.7, label="80% SOH (End of Life Threshold)")

    ax1.set_ylabel("State of Health (SOH)")
    ax1.set_title(f"1,500-Cycle SOH Prognosis: Physics DFN vs Surrogate Models (C = {C_RATE})", fontweight="bold")
    ax1.legend(loc="lower left", fontsize=8.5)
    ax1.grid(True, ls="--", alpha=0.5)

    # Bottom panel: Error curve
    ax2.plot(N_true, rel_err_gp, "r-", lw=1.5, label="GP Zero-Shot Relative Error (%)")
    diff_extrap_50 = np.abs(soh_extrap_50[:n_have] - soh_true)
    rel_extrap_50 = (diff_extrap_50 / soh_true) * 100
    ax2.plot(N_true, rel_extrap_50, color="purple", ls=":", lw=1.5, label="K=50 Extrapolator Relative Error (%)")

    if soh_extrap_100 is not None:
        diff_extrap_100 = np.abs(soh_extrap_100[:n_have] - soh_true)
        rel_extrap_100 = (diff_extrap_100 / soh_true) * 100
        ax2.plot(N_true, rel_extrap_100, "b--", lw=1.5, label="K=100 Extrapolator Relative Error (%)")

    ax2.axhline(np.mean(rel_err_gp), color="orange", ls=":", label=f"Mean GP Error: {np.mean(rel_err_gp):.4f}%")
    ax2.set_xlabel("Cycle Number (N)")
    ax2.set_ylabel("Relative Error [%]")
    ax2.set_title(f"Prognosis Error Across Available Cycles (1 to {n_have})", fontsize=11)
    ax2.legend(loc="upper left", fontsize=8.5)
    ax2.grid(True, ls="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(OUT_FIG, bbox_inches="tight")
    plt.close()
    print(f"\nGenerated comparison plot -> {OUT_FIG}")

    # Copy to artifacts directory if available
    art_dir = r"C:\Users\LawLight\.gemini\antigravity-ide\brain\f23cff77-8a53-4168-9762-6dbc9c20a4f7"
    if os.path.exists(art_dir):
        import shutil
        shutil.copy(OUT_FIG, os.path.join(art_dir, "comparison_1.44224C_1500.png"))
        print(f"Copied to artifact directory -> {art_dir}/comparison_1.44224C_1500.png")


if __name__ == "__main__":
    main()
