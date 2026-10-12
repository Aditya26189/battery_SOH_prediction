"""
1-D GP surrogate: C-rate -> SOH trajectory.
Basis {1, sqrt(N), N} per design, one Matern-5/2 GP per basis coefficient,
leave-one-out conformal sup-norm band (n is too small for a separate calibration set).

Expected data (sweep.npz):
    crates : (n,)    charge C-rates, e.g. n = 60 in [0.2, 2.0]
    N      : (T,)    cycle numbers, shared grid across designs (1 to 50)
    Y      : (n, T)  SOH normalised to true BoL
"""

import os
import warnings
import numpy as np
import matplotlib.pyplot as plt
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor as GPR
from sklearn.gaussian_process.kernels import Matern, ConstantKernel as C, WhiteKernel

warnings.filterwarnings("ignore", category=ConvergenceWarning)

ALPHA = 0.10          # 90% conformal coverage
USE_LOG_C = True      # GP input = log10(C-rate); set False for raw C-rate


# ---------------- basis ----------------
def make_basis(N):
    N = np.asarray(N, float)
    return np.column_stack([np.ones_like(N), np.sqrt(N), N])   # (T, 3)


def feat(c):
    c = np.asarray(c, float).reshape(-1, 1)
    return np.log10(c) if USE_LOG_C else c


# ---------------- emulator ----------------
class Emulator:
    def __init__(self, N):
        self.B = make_basis(N)
        self.A = None
        self.mu = None
        self.sd = None
        self.gps = []

    def fit(self, c, Y, n_restarts=10):
        # Per-design least squares onto basis -> (n, 3) coefficients
        self.A = np.linalg.lstsq(self.B, Y.T, rcond=None)[0].T
        self.mu = self.A.mean(0)
        self.sd = self.A.std(0) + 1e-12
        Z = (self.A - self.mu) / self.sd
        X = feat(c)
        self.gps = []
        for k in range(3):
            kern = (
                C(1.0, (1e-2, 1e3))
                * Matern(length_scale=0.5, length_scale_bounds=(5e-2, 1e1), nu=2.5)
                + WhiteKernel(1e-6, (1e-10, 1e-2))   # simulator is deterministic -> tiny noise
            )
            gpr = GPR(kern, n_restarts_optimizer=n_restarts, random_state=0)
            self.gps.append(gpr.fit(X, Z[:, k]))
        return self

    def coefs(self, c):
        X = feat(c)
        Z = np.column_stack([g.predict(X) for g in self.gps])
        return Z * self.sd + self.mu

    def predict(self, c):
        return self.coefs(c) @ self.B.T                     # (m, T)


# ---------------- conformal (LOO, sup-norm) ----------------
def loo_scores(c, N, Y, n_restarts=2):
    n = len(c)
    s = np.empty(n)
    for i in range(n):
        m = np.arange(n) != i
        em = Emulator(N).fit(c[m], Y[m], n_restarts=n_restarts)
        s[i] = np.max(np.abs(em.predict(c[i])[0] - Y[i]))
    return s


def conformal_halfwidth(scores, alpha=ALPHA):
    n = len(scores)
    k = int(np.ceil((n + 1) * (1 - alpha)))
    if k > n:
        return np.inf                                       # alpha too small for this n
    return np.sort(scores)[k - 1]


def load_data(npz_path="sweep.npz"):
    if not os.path.exists(npz_path):
        print(f"'{npz_path}' not found. Extracting from CSV files in current directory...")
        from prepare_sweep import build_sweep_dataset
        build_sweep_dataset(csv_dir=".", output_path=npz_path)

    d = np.load(npz_path)
    crates = d["crates"].astype(float)
    N = d["N"].astype(float)
    Y = d["Y"].astype(float)
    assert Y.shape == (len(crates), len(N)), f"Shape mismatch: Y {Y.shape} vs ({len(crates)}, {len(N)})"
    return crates, N, Y


def plot_diagnostics(crates, N, Y, em, scores, q, c_new, mean_new, lo_new, hi_new, save_path="emulator_validation.png"):
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), dpi=150)

    # 1. Training SOH degradation profiles
    ax = axes[0, 0]
    cmap = plt.cm.plasma
    norm = plt.Normalize(vmin=crates.min(), vmax=crates.max())
    for i in range(0, len(crates), 3):
        color = cmap(norm(crates[i]))
        ax.plot(N, Y[i], color=color, alpha=0.7, lw=1.2)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax)
    cbar.set_label("C-rate", fontsize=10)
    ax.set_title("Training Trajectories (True BoL SOH)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Cycle number (N)")
    ax.set_ylabel("SOH [Q / Q_BoL]")
    ax.grid(True, linestyle="--", alpha=0.5)

    # 2. Prediction on test C-rate with Conformal Band
    ax = axes[0, 1]
    ax.plot(N, mean_new, color="crimson", lw=2.2, label=f"GP Mean (C = {c_new[0]:.2f})")
    ax.fill_between(N, lo_new, hi_new, color="crimson", alpha=0.25, label=f"90% Conformal Band (±{q:.4f})")
    # Plot closest known training points for visual reference
    idx_closest = np.argsort(np.abs(crates - c_new[0]))[:2]
    for idx in idx_closest:
        ax.plot(N, Y[idx], "--", lw=1.2, alpha=0.7, label=f"PyBaMM Truth @ {crates[idx]:.3f}C")
    ax.set_title(f"Prediction & Conformal Band at C = {c_new[0]:.2f}", fontsize=11, fontweight="bold")
    ax.set_xlabel("Cycle number (N)")
    ax.set_ylabel("SOH [Q / Q_BoL]")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(True, linestyle="--", alpha=0.5)

    # 3. LOO Nonconformity Scores vs C-rate
    ax = axes[1, 0]
    ax.scatter(crates, scores, color="teal", edgecolors="k", s=40, zorder=3, label="LOO Sup-error")
    ax.axhline(q, color="darkorange", linestyle="--", lw=1.8, label=f"90% Cutoff q = {q:.4f}")
    ax.set_title("Leave-One-Out Sup-Norm Error Distribution", fontsize=11, fontweight="bold")
    ax.set_xlabel("C-rate")
    ax.set_ylabel("Max Abs Error across Cycles")
    ax.legend(fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.5)

    # 4. Basis coefficients vs C-rate
    ax = axes[1, 1]
    c_grid = np.linspace(crates.min(), crates.max(), 100)
    coefs_grid = em.coefs(c_grid)
    labels = ["c0 (Intercept)", "c1 (sqrt(N))", "c2 (N)"]
    for k in range(3):
        ax.scatter(crates, em.A[:, k], s=25, alpha=0.6, label=f"OLS {labels[k]}")
        ax.plot(c_grid, coefs_grid[:, k], lw=1.8, label=f"GP Fit {labels[k]}")
    ax.set_title("Basis Coefficients A(c) Emulator", fontsize=11, fontweight="bold")
    ax.set_xlabel("C-rate")
    ax.set_ylabel("Coefficient Value")
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    print(f"Diagnostic validation plot saved to '{save_path}'")


if __name__ == "__main__":
    crates, N, Y = load_data("sweep.npz")
    print(f"Loaded dataset: {len(crates)} C-rates in [{crates.min():.3f}, {crates.max():.3f}], {len(N)} cycles.")

    # Fit GP emulator on all designs
    em = Emulator(N).fit(crates, Y, n_restarts=10)

    # 1) Basis-only error: if this is large, the basis (not the GP) is the bottleneck
    basis_err = np.abs(em.A @ em.B.T - Y).max(axis=1)
    print(f"basis reconstruction sup-err: max {basis_err.max():.4f}, mean {basis_err.mean():.4f}")

    # 2) LOO sup-norm errors vs TRUE trajectory (includes basis misfit + GP error)
    scores = loo_scores(crates, N, Y, n_restarts=2)
    q = conformal_halfwidth(scores, alpha=ALPHA)
    print(f"LOO sup-err: median {np.median(scores):.4f}, max {scores.max():.4f}")
    print(f"{int((1 - ALPHA) * 100)}% conformal half-width q = {q:.4f}")
    worst = np.argsort(scores)[-3:][::-1]
    print("worst LOO C-rates:", crates[worst], scores[worst])

    # 3) Predict on a new C-rate
    c_new = np.array([0.7])
    mean = em.predict(c_new)[0]
    lo, hi = mean - q, mean + q
    np.savez("emulator_pred.npz", N=N, c=c_new, mean=mean, lo=lo, hi=hi)
    print(f"Prediction saved to 'emulator_pred.npz' for C-rate = {c_new[0]:.2f}")
    print(f"  Cycle 1  predicted SOH: {mean[0]:.4f} [90% band: {lo[0]:.4f}, {hi[0]:.4f}]")
    print(f"  Cycle 50 predicted SOH: {mean[-1]:.4f} [90% band: {lo[-1]:.4f}, {hi[-1]:.4f}]")

    # 4) Save diagnostic plot
    plot_diagnostics(crates, N, Y, em, scores, q, c_new, mean, lo, hi)
