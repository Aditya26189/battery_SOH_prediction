"""1-D Gaussian Process surrogate: C-rate → SOH trajectory.

Basis {1, √N, N} per design, one Matérn-5/2 GP per basis coefficient,
leave-one-out conformal sup-norm band (n is too small for a separate
calibration set).

Expected input (``data/sweep/sweep.npz``)::

    crates : (n,)    charge C-rates (e.g. n = 60 in [0.2, 2.0])
    N      : (T,)    cycle numbers, shared grid across designs (1 … 50)
    Y      : (n, T)  SOH normalised to true Beginning-of-Life

Usage (from repo root)
----------------------
    python scripts/run_surrogate.py
"""

import os
import warnings

import numpy as np
import matplotlib.pyplot as plt
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor as GPR
from sklearn.gaussian_process.kernels import (
    ConstantKernel as C,
    Matern,
    WhiteKernel,
)

warnings.filterwarnings("ignore", category=ConvergenceWarning)

ALPHA = 0.10          # 90 % conformal coverage
USE_LOG_C = True      # GP input = log₁₀(C-rate)


# ------------------------------------------------------------------ basis
def make_basis(N):
    """Build the [1, √N, N] design matrix."""
    N = np.asarray(N, float)
    return np.column_stack([np.ones_like(N), np.sqrt(N), N])


def feat(c):
    """Transform C-rate for GP input."""
    c = np.asarray(c, float).reshape(-1, 1)
    return np.log10(c) if USE_LOG_C else c


# --------------------------------------------------------------- emulator
class Emulator:
    """Three-coefficient GP emulator for SOH trajectories.

    Parameters
    ----------
    N : array-like
        Cycle numbers used as the shared temporal grid.
    """

    def __init__(self, N):
        self.B = make_basis(N)
        self.A = None       # (n, 3) OLS coefficients per design
        self.mu = None
        self.sd = None
        self.gps = []

    def fit(self, c, Y, n_restarts=10):
        """Fit GPs on basis coefficients.

        Parameters
        ----------
        c : array-like, shape (n,)
            C-rates for each design.
        Y : array-like, shape (n, T)
            SOH trajectories.
        n_restarts : int
            Number of kernel-optimiser restarts.
        """
        self.A = np.linalg.lstsq(self.B, Y.T, rcond=None)[0].T
        self.mu = self.A.mean(0)
        self.sd = self.A.std(0) + 1e-12
        Z = (self.A - self.mu) / self.sd
        X = feat(c)
        self.gps = []
        for k in range(3):
            kern = (
                C(1.0, (1e-2, 1e3))
                * Matern(length_scale=0.5,
                         length_scale_bounds=(5e-2, 1e1), nu=2.5)
                + WhiteKernel(1e-6, (1e-10, 1e-2))
            )
            gpr = GPR(kern, n_restarts_optimizer=n_restarts, random_state=0)
            self.gps.append(gpr.fit(X, Z[:, k]))
        return self

    def coefs(self, c):
        """Predict basis coefficients for new C-rates."""
        X = feat(c)
        Z = np.column_stack([g.predict(X) for g in self.gps])
        return Z * self.sd + self.mu

    def predict(self, c):
        """Predict SOH trajectories for new C-rates."""
        return self.coefs(c) @ self.B.T


# ----------------------------------------------------- conformal (LOO)
def loo_scores(c, N, Y, n_restarts=2):
    """Compute leave-one-out sup-norm scores."""
    n = len(c)
    s = np.empty(n)
    for i in range(n):
        m = np.arange(n) != i
        em = Emulator(N).fit(c[m], Y[m], n_restarts=n_restarts)
        s[i] = np.max(np.abs(em.predict(c[i])[0] - Y[i]))
    return s


def conformal_halfwidth(scores, alpha=ALPHA):
    """Compute the conformal half-width at coverage 1 − α."""
    n = len(scores)
    k = int(np.ceil((n + 1) * (1 - alpha)))
    if k > n:
        return np.inf
    return np.sort(scores)[k - 1]


# --------------------------------------------------------------- I/O
def load_data(npz_path="data/sweep/sweep.npz"):
    """Load sweep dataset, building it on-the-fly if missing."""
    if not os.path.exists(npz_path):
        print(f"'{npz_path}' not found — extracting from CSVs…")
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
        from scripts.prepare_sweep import build_sweep_dataset
        build_sweep_dataset(
            csv_dir=os.path.dirname(npz_path),
            output_path=npz_path,
        )

    d = np.load(npz_path)
    crates = d["crates"].astype(float)
    N = d["N"].astype(float)
    Y = d["Y"].astype(float)
    assert Y.shape == (len(crates), len(N))
    return crates, N, Y


# ---------------------------------------------------------- diagnostics
def plot_diagnostics(crates, N, Y, em, scores, q,
                     c_new, mean_new, lo_new, hi_new,
                     save_path="figures/emulator_validation.png"):
    """Generate a 2×2 diagnostic validation plot."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), dpi=150)

    # 1. Training SOH profiles
    ax = axes[0, 0]
    cmap = plt.cm.plasma
    norm = plt.Normalize(vmin=crates.min(), vmax=crates.max())
    for i in range(0, len(crates), 3):
        ax.plot(N, Y[i], color=cmap(norm(crates[i])), alpha=0.7, lw=1.2)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=ax).set_label("C-rate")
    ax.set_title("Training Trajectories (True BoL SOH)", fontweight="bold")
    ax.set_xlabel("Cycle N")
    ax.set_ylabel("SOH [Q / Q_BoL]")
    ax.grid(True, ls="--", alpha=0.5)

    # 2. Prediction + conformal band
    ax = axes[0, 1]
    ax.plot(N, mean_new, color="crimson", lw=2.2,
            label=f"GP Mean (C = {c_new[0]:.2f})")
    ax.fill_between(N, lo_new, hi_new, color="crimson", alpha=0.25,
                    label=f"90 % Conformal Band (±{q:.4f})")
    for idx in np.argsort(np.abs(crates - c_new[0]))[:2]:
        ax.plot(N, Y[idx], "--", lw=1.2, alpha=0.7,
                label=f"Truth @ {crates[idx]:.3f}C")
    ax.set_title(f"Prediction & Conformal Band (C = {c_new[0]:.2f})",
                 fontweight="bold")
    ax.set_xlabel("Cycle N")
    ax.set_ylabel("SOH")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(True, ls="--", alpha=0.5)

    # 3. LOO scores
    ax = axes[1, 0]
    ax.scatter(crates, scores, color="teal", edgecolors="k", s=40, zorder=3,
               label="LOO Sup-error")
    ax.axhline(q, color="darkorange", ls="--", lw=1.8,
               label=f"90 % Cutoff q = {q:.4f}")
    ax.set_title("LOO Sup-Norm Error Distribution", fontweight="bold")
    ax.set_xlabel("C-rate")
    ax.set_ylabel("Max |error| across cycles")
    ax.legend(fontsize=9)
    ax.grid(True, ls="--", alpha=0.5)

    # 4. Basis coefficients
    ax = axes[1, 1]
    c_grid = np.linspace(crates.min(), crates.max(), 100)
    coefs_grid = em.coefs(c_grid)
    labels = ["c₀ (Intercept)", "c₁ (√N)", "c₂ (N)"]
    for k in range(3):
        ax.scatter(crates, em.A[:, k], s=25, alpha=0.6,
                   label=f"OLS {labels[k]}")
        ax.plot(c_grid, coefs_grid[:, k], lw=1.8,
                label=f"GP  {labels[k]}")
    ax.set_title("Basis Coefficients A(c) Emulator", fontweight="bold")
    ax.set_xlabel("C-rate")
    ax.set_ylabel("Coefficient value")
    ax.legend(fontsize=8)
    ax.grid(True, ls="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    print(f"Diagnostic plot → {save_path}")
