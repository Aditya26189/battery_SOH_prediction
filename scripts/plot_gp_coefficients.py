#!/usr/bin/env python
"""Generate publication-grade plots showing how kinetic coefficients (c, b1, b2)
depend on C-rate, as trained and predicted by the Gaussian Process (GP) emulator.

Formula convention:
    SOH(N) = c - b1 * sqrt(N) - b2 * N
where:
    c  = c0  (Beginning-of-Life accessible capacity)
    b1 = -c1 (Parabolic SEI diffusion-limited growth rate)
    b2 = -c2 (Linear mechanical fatigue & particle cracking rate)

Outputs:
    figures/gp_coefficients_vs_crate.png
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
from src.gp_surrogate import Emulator, load_data, feat

SWEEP_NPZ = "data/sweep/sweep_fixedset.npz"
OUT_FIG = "figures/gp_coefficients_vs_crate.png"
ARTIFACT_DIR = r"C:\Users\LawLight\.gemini\antigravity-ide\brain\f23cff77-8a53-4168-9762-6dbc9c20a4f7"

# Held-out validation points
HELD_OUT_FILES = [
    ("data/sweep_fixedset/1.33389C_cycles.csv", 1.3338905, "Held-out 1.334C"),
    ("data/pilot_1500/1.44224C_cycles.csv", 1.4422357, "Held-out 1.442C"),
]


def fit_50_cycles(csv_path, bol_cap=4.90778):
    """Fit OLS [1, sqrt(N), N] on first 50 cycles of a CSV."""
    df = pd.read_csv(csv_path)
    df50 = df.iloc[:50]
    N = df50["cycle"].values
    soh = df50["discharge_capacity_Ah"].values / bol_cap
    B = np.column_stack([np.ones(len(N)), np.sqrt(N), N])
    theta = np.linalg.lstsq(B, soh, rcond=None)[0]
    # theta = [c0, c1, c2] -> c = c0, b1 = -c1, b2 = -c2
    return theta[0], -theta[1], -theta[2]


def main():
    print(f"Loading sweep dataset from {SWEEP_NPZ}...")
    crates, N, Y = load_data(SWEEP_NPZ if os.path.exists(SWEEP_NPZ) else "data/sweep/sweep.npz")
    print(f"Loaded {len(crates)} C-rates across [{crates.min():.2f}C, {crates.max():.2f}C].")

    # Fit Gaussian Process Emulator
    em = Emulator(N).fit(crates, Y, n_restarts=10)

    # Training OLS coefficients: A has columns [c0, c1, c2]
    # In convention SOH = c - b1*sqrt(N) - b2*N:
    c_train = em.A[:, 0]
    b1_train = -em.A[:, 1]
    b2_train = -em.A[:, 2]

    # Continuous dense C-rate grid for GP evaluation
    c_grid = np.linspace(0.20, 2.00, 300)
    X_grid = feat(c_grid)

    # GP predictions with standard deviations for each coefficient
    means = []
    stds = []
    for k in range(3):
        m, s = em.gps[k].predict(X_grid, return_std=True)
        # Denormalize
        m_phys = m * em.sd[k] + em.mu[k]
        s_phys = s * em.sd[k]
        means.append(m_phys)
        stds.append(s_phys)

    # Convert to c, b1, b2 convention
    c_gp_mean = means[0]
    c_gp_std = stds[0]

    b1_gp_mean = -means[1]
    b1_gp_std = stds[1]

    b2_gp_mean = -means[2]
    b2_gp_std = stds[2]

    # Evaluate held-out validation points
    held_out_pts = []
    for path, crate, label in HELD_OUT_FILES:
        if os.path.exists(path):
            c_val, b1_val, b2_val = fit_50_cycles(path)
            held_out_pts.append({
                "crate": crate,
                "label": label,
                "c": c_val,
                "b1": b1_val,
                "b2": b2_val,
            })
            print(f"Extracted {label}: c={c_val:.5f}, b1={b1_val*1e4:.3f}e-4, b2={b2_val*1e4:.3f}e-4")

    # -------------------------------------------------------------
    # Plotting: Publication-Grade 3-Panel Stack
    # -------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(11, 12), dpi=200, sharex=True)
    plt.rcParams["font.family"] = "DejaVu Sans"

    # Style colors
    col_train = "#2c3e50"     # Dark Slate
    col_gp = "#d9534f"        # Crimson Red
    col_band = "#f2dede"      # Soft Pink
    col_test = "#27ae60"      # Emerald Green

    # ---------------- Panel 1: c (Beginning of Life Capacity) ----------------
    ax1 = axes[0]
    ax1.plot(c_grid, c_gp_mean, color=col_gp, lw=2.4, label=r"GP Mean $c(C)$")
    ax1.fill_between(c_grid, c_gp_mean - 2 * c_gp_std, c_gp_mean + 2 * c_gp_std,
                     color=col_gp, alpha=0.18, label=r"GP 95% Confidence Band ($\pm 2\sigma$)")
    ax1.scatter(crates, c_train, color=col_train, s=30, alpha=0.75, edgecolors="none",
                label=f"Training Conditions ($n={len(crates)}$ Sweeps)")

    for i, pt in enumerate(held_out_pts):
        lbl = f"Held-out DFN Benchmark ({pt['label']})" if i == 0 else f"Held-out DFN Benchmark ({pt['label']})"
        ax1.scatter(pt["crate"], pt["c"], color=col_test, marker="*", s=170, zorder=5,
                    edgecolors="black", linewidth=1.2, label=lbl)

    ax1.set_ylabel("Parameter $c$ (or $c_0$)\n[Beginning-of-Life SOH]", fontsize=11, fontweight="bold")
    ax1.set_title("Gaussian Process Parameter Mapping: Kinetic Basis Coefficients vs. Discharge C-Rate",
                  fontsize=13, fontweight="bold", pad=12)
    ax1.legend(loc="upper right", fontsize=8.5, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
    ax1.grid(True, ls="--", alpha=0.5)
    ax1.text(0.03, 0.12, "Physics Mechanism:\nOhmic $IR$ drop & solid-state diffusion overpotentials reduce accessible\nBeginning-of-Life discharge capacity monotonically as C-rate increases.",
             transform=ax1.transAxes, fontsize=9.2, fontstyle="italic", va="bottom",
             bbox=dict(boxstyle="round,pad=0.5", fc="#f8f9fa", ec="#ced4da", alpha=0.95))

    # ---------------- Panel 2: b1 (Diffusion-Limited SEI Growth) ----------------
    ax2 = axes[1]
    scale_b1 = 1e4
    ax2.plot(c_grid, b1_gp_mean * scale_b1, color="#2980b9", lw=2.4, label=r"GP Mean $b_1(C)$")
    ax2.fill_between(c_grid, (b1_gp_mean - 2 * b1_gp_std) * scale_b1, (b1_gp_mean + 2 * b1_gp_std) * scale_b1,
                     color="#2980b9", alpha=0.18, label=r"GP 95% Confidence Band ($\pm 2\sigma$)")
    ax2.scatter(crates, b1_train * scale_b1, color=col_train, s=30, alpha=0.75, edgecolors="none",
                label="Training Conditions")

    for pt in held_out_pts:
        ax2.scatter(pt["crate"], pt["b1"] * scale_b1, color=col_test, marker="*", s=170, zorder=5,
                    edgecolors="black", linewidth=1.2, label=f"Held-out Benchmark ({pt['label']})")

    ax2.set_ylabel("Parameter $b_1$ (or $-c_1$) [$\\times 10^{-4}$]\n[Parabolic SEI Diffusion Rate, $\\sqrt{N}$]",
                   fontsize=11, fontweight="bold")
    ax2.legend(loc="upper left", fontsize=8.5, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
    ax2.grid(True, ls="--", alpha=0.5)
    ax2.text(0.97, 0.12, "Physics Mechanism:\nDiffusion-limited solvent reduction & SEI film thickening on graphite/silicon composite\nanode particles; growth rate scales strongly with cycling operating rate.",
             transform=ax2.transAxes, fontsize=9.2, fontstyle="italic", ha="right", va="bottom",
             bbox=dict(boxstyle="round,pad=0.5", fc="#f8f9fa", ec="#ced4da", alpha=0.95))

    # ---------------- Panel 3: b2 (Linear Mechanical Fatigue & LAM) ----------------
    ax3 = axes[2]
    scale_b2 = 1e4
    ax3.plot(c_grid, b2_gp_mean * scale_b2, color="#8e44ad", lw=2.4, label=r"GP Mean $b_2(C)$")
    ax3.fill_between(c_grid, (b2_gp_mean - 2 * b2_gp_std) * scale_b2, (b2_gp_mean + 2 * b2_gp_std) * scale_b2,
                     color="#8e44ad", alpha=0.18, label=r"GP 95% Confidence Band ($\pm 2\sigma$)")
    ax3.scatter(crates, b2_train * scale_b2, color=col_train, s=30, alpha=0.75, edgecolors="none",
                label="Training Conditions")

    for pt in held_out_pts:
        ax3.scatter(pt["crate"], pt["b2"] * scale_b2, color=col_test, marker="*", s=170, zorder=5,
                    edgecolors="black", linewidth=1.2, label=f"Held-out Benchmark ({pt['label']})")

    ax3.set_ylabel("Parameter $b_2$ (or $-c_2$) [$\\times 10^{-4}$]\n[Mechanical Fatigue / LAM Rate, $N$]",
                   fontsize=11, fontweight="bold")
    ax3.set_xlabel("Discharge C-Rate [C]", fontsize=12, fontweight="bold")
    ax3.legend(loc="upper left", fontsize=8.5, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
    ax3.grid(True, ls="--", alpha=0.5)
    ax3.text(0.97, 0.12, "Physics Mechanism:\nCyclic lithiation-induced mechanical shear strain, particle micro-cracking, and Loss of Active\nMaterial (LAM) accelerate $>6\\times$ from 0.2C ($0.28\\times 10^{-4}$) to 2.0C ($1.81\\times 10^{-4}$).",
             transform=ax3.transAxes, fontsize=9.2, fontstyle="italic", ha="right", va="bottom",
             bbox=dict(boxstyle="round,pad=0.5", fc="#f8f9fa", ec="#ced4da", alpha=0.95))

    # Common formatting
    for ax in axes:
        ax.set_xlim(0.18, 2.02)
        ax.tick_params(axis="both", which="major", labelsize=10.5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(OUT_FIG), exist_ok=True)
    plt.savefig(OUT_FIG, bbox_inches="tight")
    plt.close()
    print(f"\nGenerated publication figure -> {OUT_FIG}")

    # Copy to artifacts directory
    if os.path.exists(ARTIFACT_DIR):
        import shutil
        art_dest = os.path.join(ARTIFACT_DIR, "gp_coefficients_vs_crate.png")
        shutil.copy(OUT_FIG, art_dest)
        print(f"Copied to artifact directory -> {art_dest}")


if __name__ == "__main__":
    main()
