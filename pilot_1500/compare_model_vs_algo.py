"""Compare Physics Model (PyBaMM DFN) Output vs Algorithm (Surrogate / Extrapolator) Output.
Usage:
    python compare_model_vs_algo.py --crate 1.0 --fit-window 100
"""
import argparse, os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = os.path.join(os.path.dirname(__file__), "results", "fixedset_1500")

def run_comparison(crate=1.0, k_fit=100, save_plot=True):
    tag = f"{crate:g}C"
    csv_file = os.path.join(DATA_DIR, f"{tag}_cycles.csv")
    
    if not os.path.exists(csv_file):
        print(f"Error: Simulation data for {tag} not found at {csv_file}")
        print("Available pre-computed simulations: 0.2C, 1C, 2C")
        return

    # 1. Load Physics Model Output
    df = pd.read_csv(csv_file)
    N_true = df["cycle"].values
    Q_true = df["discharge_capacity_Ah"].values
    soh_true = Q_true / Q_true[0]

    # 2. Run Algorithm (Composite Two-Regime Physics Extrapolator)
    # Basis: {1, sqrt(N), N} fitted on early window N <= k_fit
    mask = N_true <= k_fit
    N_train = N_true[mask]
    y_train = soh_true[mask]

    B_train = np.column_stack([np.ones_like(N_train), np.sqrt(N_train), N_train])
    theta, _, _, _ = np.linalg.lstsq(B_train, y_train, rcond=None)
    c, b1, b2 = theta

    # Predict full life across all N
    B_full = np.column_stack([np.ones_like(N_true), np.sqrt(N_true), N_true])
    soh_algo = B_full @ theta
    Q_algo = Q_true[0] * soh_algo

    # 3. Print Side-by-Side Comparison Table
    milestones = [10, 50, 100, 200, 500, 800, 1000, 1200, 1500]
    milestones = [m for m in milestones if m <= len(N_true)]

    print("=" * 80)
    print(f"COMPARISON: Physics DFN Model vs. Algorithm Output at {tag}")
    print(f"Algorithm fitted on first {k_fit} cycles -> Extrapolated to {len(N_true)} cycles")
    print("=" * 80)
    print(f"{'Cycle':>7} | {'Model Q [Ah]':>13} | {'Algo Q [Ah]':>13} | {'Delta [Ah]':>11} | {'SOH Model':>10} | {'SOH Algo':>10} | {'Error [%]':>9}")
    print("-" * 80)

    rows = []
    for m in milestones:
        idx = m - 1
        q_m = Q_true[idx]
        q_a = Q_algo[idx]
        s_m = soh_true[idx]
        s_a = soh_algo[idx]
        delta_q = q_a - q_m
        err_pct = abs(s_a - s_m) * 100

        mark = " (in-sample)" if m <= k_fit else " (extrapolated)"
        print(f"{m:>7} | {q_m:>13.5f} | {q_a:>13.5f} | {delta_q:>+11.5f} | {s_m:>10.4f} | {s_a:>10.4f} | {err_pct:>8.3f}%{mark}")
        rows.append(dict(Cycle=m, Model_Q=q_m, Algo_Q=q_a, Delta_Q=delta_q, Model_SOH=s_m, Algo_SOH=s_a, Error_Pct=err_pct))

    print("-" * 80)
    sup_err = np.max(np.abs(soh_algo[N_true > k_fit] - soh_true[N_true > k_fit])) * 100
    print(f"Worst-case extrapolation error on cycles > {k_fit}: {sup_err:.3f}% SOH")
    print(f"Fitted Equation: SOH(N) = {c:.6f} - ({b1:.6e})*sqrt(N) - ({b2:.6e})*N")
    print("=" * 80)

    # 4. Optional Plot
    if save_plot:
        out_png = os.path.join(os.path.dirname(__file__), f"comparison_{tag}_fit{k_fit}.png")
        plt.figure(figsize=(9, 5))
        plt.plot(N_true, Q_true, "k-", lw=2, label="Physics Model (PyBaMM DFN)")
        plt.plot(N_true, Q_algo, "r--", lw=2, label=f"Algorithm ({c:.4f} - b1*sqrt(N) - b2*N)")
        plt.axvline(k_fit, color="blue", ls=":", lw=1.5, label=f"Fit Window (K={k_fit} cycles)")
        plt.xlabel("Cycle Number")
        plt.ylabel("Discharge Capacity [A.h]")
        plt.title(f"Model vs. Algorithm Comparison at {tag} (Trained on {k_fit} Cycles)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(out_png, dpi=140)
        plt.close()
        print(f"Comparison plot saved to: {out_png}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--crate", type=float, default=1.0, help="C-rate: 0.2, 1.0, or 2.0")
    parser.add_argument("--fit-window", type=int, default=100, help="Number of early cycles to train algo (e.g. 50, 100, 200)")
    args = parser.parse_args()

    run_comparison(crate=args.crate, k_fit=args.fit_window)
