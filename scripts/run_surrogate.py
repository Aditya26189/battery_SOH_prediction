#!/usr/bin/env python
"""Train the GP emulator and compute conformal prediction intervals.

Usage
-----
    python scripts/run_surrogate.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from src.gp_surrogate import (
    Emulator, load_data, loo_scores, conformal_halfwidth,
    plot_diagnostics, ALPHA,
)


def main():
    crates, N, Y = load_data("data/sweep/sweep.npz")
    print(f"Loaded: {len(crates)} C-rates [{crates.min():.3f}, "
          f"{crates.max():.3f}], {len(N)} cycles.")

    # Fit GP emulator
    em = Emulator(N).fit(crates, Y, n_restarts=10)

    # Basis-only error
    basis_err = np.abs(em.A @ em.B.T - Y).max(axis=1)
    print(f"Basis reconstruction sup-err: "
          f"max {basis_err.max():.4f}, mean {basis_err.mean():.4f}")

    # LOO conformal scores
    scores = loo_scores(crates, N, Y, n_restarts=2)
    q = conformal_halfwidth(scores, alpha=ALPHA)
    print(f"LOO sup-err: median {np.median(scores):.4f}, "
          f"max {scores.max():.4f}")
    print(f"{int((1 - ALPHA) * 100)}% conformal half-width q = {q:.4f}")

    worst = np.argsort(scores)[-3:][::-1]
    print("Worst LOO C-rates:", crates[worst], scores[worst])

    # Predict on a new C-rate
    c_new = np.array([0.7])
    mean = em.predict(c_new)[0]
    lo, hi = mean - q, mean + q
    np.savez("data/sweep/emulator_pred.npz",
             N=N, c=c_new, mean=mean, lo=lo, hi=hi)
    print(f"Prediction saved for C-rate = {c_new[0]:.2f}")
    print(f"  Cycle 1  SOH: {mean[0]:.4f}  [{lo[0]:.4f}, {hi[0]:.4f}]")
    print(f"  Cycle {int(N[-1])} SOH: {mean[-1]:.4f}  [{lo[-1]:.4f}, {hi[-1]:.4f}]")

    # Diagnostic plot
    plot_diagnostics(crates, N, Y, em, scores, q, c_new, mean, lo, hi)


if __name__ == "__main__":
    main()
