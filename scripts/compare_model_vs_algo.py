#!/usr/bin/env python
"""Compare Physics Model (PyBaMM DFN) vs Algorithm (Composite Extrapolator).

Usage
-----
    python scripts/compare_model_vs_algo.py --crate 1.0 --fit-window 100
    python scripts/compare_model_vs_algo.py --crate 2.0 --fit-window 200
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                               # noqa: E402

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "pilot_1500",
)
FIGURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "figures",
)


def run_comparison(crate=1.0, k_fit=100, save_plot=True):
    """Run model-vs-algorithm comparison for a given C-rate.

    Parameters
    ----------
    crate : float
        C-rate to compare (must have a pre-computed simulation CSV).
    k_fit : int
        Number of early cycles to train the algorithm.
    save_plot : bool
        Whether to write a PNG comparison plot.
    """
    tag = f"{crate:g}C"
    csv_file = os.path.join(DATA_DIR, f"{tag}_cycles.csv")

    if not os.path.exists(csv_file):
        print(f"Error: simulation data for {tag} not found at {csv_file}")
        print("Available pre-computed simulations: 0.2C, 1C, 2C")
        return

    # 1. Load physics model output
    df = pd.read_csv(csv_file)
    N_true = df["cycle"].values
    Q_true = df["discharge_capacity_Ah"].values
    soh_true = Q_true / Q_true[0]

    # 2. Fit algorithm (composite two-regime)
    mask = N_true <= k_fit
    N_train, y_train = N_true[mask], soh_true[mask]
    B_train = np.column_stack([
        np.ones_like(N_train), np.sqrt(N_train), N_train
    ])
    theta, _, _, _ = np.linalg.lstsq(B_train, y_train, rcond=None)
    c, b1, b2 = theta

    B_full = np.column_stack([
        np.ones_like(N_true), np.sqrt(N_true), N_true
    ])
    soh_algo = B_full @ theta
    Q_algo = Q_true[0] * soh_algo

    # 3. Comparison table
    milestones = [m for m in [10, 50, 100, 200, 500, 800, 1000, 1200, 1500]
                  if m <= len(N_true)]

    print("=" * 80)
    print(f"COMPARISON: Physics DFN Model vs Algorithm at {tag}")
    print(f"Algorithm fitted on first {k_fit} cycles → "
          f"Extrapolated to {len(N_true)} cycles")
    print("=" * 80)
    header = (f"{'Cycle':>7} | {'Model Q [Ah]':>13} | {'Algo Q [Ah]':>13} | "
              f"{'Δ [Ah]':>11} | {'SOH Model':>10} | {'SOH Algo':>10} | "
              f"{'Error [%]':>9}")
    print(header)
    print("-" * 80)

    for m in milestones:
        idx = m - 1
        q_m, q_a = Q_true[idx], Q_algo[idx]
        s_m, s_a = soh_true[idx], soh_algo[idx]
        delta_q = q_a - q_m
        err_pct = abs(s_a - s_m) * 100
        mark = " (in-sample)" if m <= k_fit else " (extrapolated)"
        print(f"{m:>7} | {q_m:>13.5f} | {q_a:>13.5f} | {delta_q:>+11.5f} | "
              f"{s_m:>10.4f} | {s_a:>10.4f} | {err_pct:>8.3f}%{mark}")

    print("-" * 80)
    ext_mask = N_true > k_fit
    sup_err = np.max(np.abs(soh_algo[ext_mask] - soh_true[ext_mask])) * 100
    print(f"Worst-case extrapolation error on cycles > {k_fit}: "
          f"{sup_err:.3f}% SOH")
    print(f"Equation: SOH(N) = {c:.6f} − ({b1:.6e})·√N − ({b2:.6e})·N")
    print("=" * 80)

    # 4. Plot
    if save_plot:
        os.makedirs(FIGURE_DIR, exist_ok=True)
        out_png = os.path.join(
            FIGURE_DIR, f"comparison_{tag}_fit{k_fit}.png"
        )
        plt.figure(figsize=(9, 5))
        plt.plot(N_true, Q_true, "k-", lw=2,
                 label="Physics Model (PyBaMM DFN)")
        plt.plot(N_true, Q_algo, "r--", lw=2,
                 label=f"Algorithm ({c:.4f} − b₁√N − b₂N)")
        plt.axvline(k_fit, color="blue", ls=":", lw=1.5,
                    label=f"Fit Window (K = {k_fit})")
        plt.xlabel("Cycle Number")
        plt.ylabel("Discharge Capacity [A·h]")
        plt.title(f"Model vs Algorithm at {tag} "
                  f"(trained on {k_fit} cycles)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(out_png, dpi=140)
        plt.close()
        print(f"Plot → {out_png}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare PyBaMM DFN model output against "
                    "composite extrapolator predictions."
    )
    parser.add_argument("--crate", type=float, default=1.0,
                        help="C-rate: 0.2, 1.0, or 2.0")
    parser.add_argument("--fit-window", type=int, default=100,
                        help="Early cycles to train algorithm")
    args = parser.parse_args()
    run_comparison(crate=args.crate, k_fit=args.fit_window)


if __name__ == "__main__":
    main()
