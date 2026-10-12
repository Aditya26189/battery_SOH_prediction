"""Hold-out extrapolation analysis engine.

Merges per-C-rate pilot CSVs into ``pilot.npz``, benchmarks four
functional forms against ground truth, and generates publication-quality
figures and results tables.

Functional forms
----------------
- **linear**                : SOH(N) = c − b·N
- **sqrtN**                 : SOH(N) = c − b·√N  (diffusion-limited SEI)
- **composite_two_regime**  : SOH(N) = c − b₁·√N − b₂·N  (SEI + cracking)
- **logN**                  : SOH(N) = c − b·ln(N)
- **power**                 : SOH(N) = c − b·Nᵖ  (non-linear least squares)
- **bilinear_two_regime**   : piecewise linear with hinge search

Usage (from repo root)
----------------------
    python scripts/run_analysis.py --dir data/pilot_1500 --out data/pilot_1500/analysis
"""

import argparse
import glob
import json
import os
import re

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from scipy.optimize import curve_fit                         # noqa: E402


KS = [50, 100, 200, 500]           # fit-window sizes for hold-out test
MILESTONES = [50, 100, 200, 500, 1000, 1500]


# ------------------------------------------------------------------
# Basis forms (linear-in-parameters)
# ------------------------------------------------------------------
def forms():
    """Return dict of {name: basis_builder} for linear forms."""
    one = lambda n: np.ones_like(n)                          # noqa: E731
    return {
        "linear":               lambda n: np.column_stack([one(n), n]),
        "sqrtN":                lambda n: np.column_stack([one(n), np.sqrt(n)]),
        "composite_two_regime": lambda n: np.column_stack([one(n), np.sqrt(n), n]),
        "logN":                 lambda n: np.column_stack([one(n), np.log(n)]),
    }


# ------------------------------------------------------------------
# Fit & predict
# ------------------------------------------------------------------
def fit_predict(name, N, y, ktr):
    """Fit a functional form on cycles ≤ ktr and predict over all N.

    Parameters
    ----------
    name : str
        One of the supported form names.
    N : ndarray
        Cycle numbers (1-indexed, dtype float).
    y : ndarray
        SOH values aligned with *N*.
    ktr : int
        Fit-window cutoff — only cycles ≤ ktr are used for fitting.

    Returns
    -------
    ndarray
        Predicted SOH for all N.
    """
    tr = N <= ktr
    N_tr, y_tr = N[tr], y[tr]

    if name == "power":
        f = lambda n, c, b, p: c - b * n ** p                # noqa: E731
        try:
            p0 = [y_tr[0],
                   max(1e-6, y_tr[0] - y_tr[-1]) / N_tr[-1] ** 0.7,
                   0.7]
            popt, _ = curve_fit(
                f, N_tr, y_tr, p0=p0,
                bounds=([0.5, 0, 0.1], [1.5, 1, 2.0]),
                maxfev=20000,
            )
            return f(N, *popt)
        except Exception:
            return np.full_like(N, np.nan)

    if name == "bilinear_two_regime":
        one = np.ones_like
        B_lin = np.column_stack([one(N_tr), N_tr])
        c_lin, _, _, _ = np.linalg.lstsq(B_lin, y_tr, rcond=None)
        best_pred = np.column_stack([one(N), N]) @ c_lin
        best_sse = np.sum((y_tr - B_lin @ c_lin) ** 2)
        if len(N_tr) >= 20:
            cands = np.linspace(
                N_tr[int(len(N_tr) * 0.1)],
                N_tr[int(len(N_tr) * 0.9)], 25,
            )
            for nk in cands:
                hinge_tr = np.maximum(0, N_tr - nk)
                B_h = np.column_stack([one(N_tr), N_tr, hinge_tr])
                c_h, _, _, _ = np.linalg.lstsq(B_h, y_tr, rcond=None)
                sse = np.sum((y_tr - B_h @ c_h) ** 2)
                if sse < best_sse:
                    best_sse = sse
                    hinge_full = np.maximum(0, N - nk)
                    best_pred = np.column_stack(
                        [one(N), N, hinge_full]
                    ) @ c_h
        return best_pred

    # Linear-in-parameters forms
    B = forms()[name](N)
    a = np.linalg.lstsq(B[tr], y_tr, rcond=None)[0]
    return B @ a


# ------------------------------------------------------------------
# Main analysis pipeline
# ------------------------------------------------------------------
def run_analysis(data_dir="data/pilot_1500", out_dir="data/pilot_1500/analysis",
                 figure_dir="figures"):
    """Run the complete extrapolation benchmarking pipeline.

    Parameters
    ----------
    data_dir : str
        Directory containing ``{c}C_cycles.csv`` and ``{c}C_status.json``.
    out_dir : str
        Where to write analysis CSVs and ``pilot.npz``.
    figure_dir : str
        Where to write publication-quality PNG figures.
    """
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(figure_dir, exist_ok=True)

    # ---- load + integrity ----
    runs, flags = [], []
    for f in sorted(glob.glob(os.path.join(data_dir, "*C_cycles.csv"))):
        tag = re.match(r"(.+)C_cycles\.csv", os.path.basename(f)).group(1)
        crate = float(tag)
        st_p = f.replace("_cycles.csv", "_status.json")
        st = json.load(open(st_p)) if os.path.exists(st_p) else {"status": "NO STATUS FILE"}
        df = pd.read_csv(f)
        if st.get("status") != "complete":
            flags.append(
                f"{crate:g}C status={st.get('status')} "
                f"({len(df)} cycles) errors={st.get('errors', [])[-1:]}"
            )
        if st.get("model") == "light":
            flags.append(f"{crate:g}C came from the LIGHT test model — not valid")
        if df.isna().any().any():
            flags.append(f"{crate:g}C has NaNs")
        runs.append((crate, df, st))
    if not runs:
        raise SystemExit("No *C_cycles.csv files found in " + data_dir)
    runs.sort(key=lambda r: r[0])

    T = min(len(r[1]) for r in runs)
    crates = np.array([r[0] for r in runs])
    N = np.arange(1, T + 1, dtype=float)
    Q = np.array([r[1]["discharge_capacity_Ah"].values[:T] for r in runs])
    bol_ref = float(Q[0, 0])
    Y_bol = Q / bol_ref
    Y_pc = Q / Q[:, [0]]

    extra = {}
    if all("porosity_neg_avg_end" in r[1] for r in runs):
        extra["porosity_neg_avg_end"] = np.array(
            [r[1]["porosity_neg_avg_end"].values[:T] for r in runs]
        )
    np.savez(
        os.path.join(out_dir, "pilot.npz"),
        crates=crates, N=N, Q=Q, Y=Y_bol, Y_per_cell=Y_pc,
        bol_ref=bol_ref, **extra,
    )

    # ---- Table 1: trajectory summary ----
    rows = []
    for i, c in enumerate(crates):
        r = {"C": c, "Q_cycle1_Ah": Q[i, 0], "Y_bol_cycle1": Y_bol[i, 0]}
        for m in MILESTONES:
            if m <= T:
                r[f"SOH_pc@{m}"] = Y_pc[i, m - 1]
        for thr in (0.9, 0.8):
            hit = np.where(Y_pc[i] < thr)[0]
            r[f"first_N_below_{thr}"] = int(hit[0] + 1) if len(hit) else None
        w = max(10, T // 5)
        s_early = np.polyfit(N[:w], Y_pc[i, :w], 1)[0]
        s_late = np.polyfit(N[-w:], Y_pc[i, -w:], 1)[0]
        r["slope_late/early"] = s_late / s_early if s_early != 0 else np.nan
        rows.append(r)
    t1 = pd.DataFrame(rows)
    t1.to_csv(os.path.join(out_dir, "trajectory_summary.csv"), index=False)

    # ---- Table 2: hold-out extrapolation ----
    names = list(forms().keys()) + ["power", "bilinear_two_regime"]
    rec = []
    for i, c in enumerate(crates):
        for K in [k for k in KS if k < T - 10]:
            for nm in names:
                pred = fit_predict(nm, N, Y_pc[i], K)
                err = np.abs(pred[N > K] - Y_pc[i, N > K])
                rec.append(dict(
                    C=c, K=K, form=nm,
                    sup_err=float(np.nanmax(err)) if np.isfinite(err).any() else np.nan,
                    err_at_last_N=float(abs(pred[-1] - Y_pc[i, -1])),
                    in_window_sup_err=float(np.nanmax(
                        np.abs(pred[N <= K] - Y_pc[i, N <= K])
                    )),
                ))
    h = pd.DataFrame(rec)
    h.to_csv(os.path.join(out_dir, "holdout_errors.csv"), index=False)
    piv = h.pivot_table(
        index=["K", "form"], values="sup_err", aggfunc="max"
    ).reset_index()

    # ---- Figures ----
    cm = plt.cm.viridis(np.linspace(0, 0.9, len(crates)))

    # Fig 1 — Trajectories
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for i, c in enumerate(crates):
        ax[0].plot(N, Y_pc[i], color=cm[i], label=f"{c:g}C")
        ax[1].plot(N, Y_bol[i], color=cm[i], label=f"{c:g}C")
    ax[0].set_title("SOH (each run → own cycle 1)")
    ax[1].set_title(f"SOH vs cycle-1 @ lowest C ({bol_ref:.4f} Ah)")
    for x in ax:
        x.set_xlabel("Cycle")
        x.set_ylabel("SOH")
        x.grid(alpha=0.3)
        x.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(figure_dir, "fig1_trajectories.png"), dpi=140)
    plt.close()

    # Fig 2 — Hold-out error
    fig, ax = plt.subplots(figsize=(7, 4.8))
    for nm in names:
        s = piv[piv.form == nm]
        ax.plot(s.K, s.sup_err, "o-", label=nm)
    ax.set_yscale("log")
    ax.set_xlabel("Fit window K (cycles)")
    ax.set_ylabel("Worst-case sup error on cycles > K")
    ax.set_title("Hold-out extrapolation error (worst over C-rates)")
    ax.grid(alpha=0.3, which="both")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(figure_dir, "fig2_holdout_error.png"), dpi=140)
    plt.close()

    # Fig 3 — Extrapolation from first K
    mid = len(crates) // 2
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(N, Y_pc[mid], "k", lw=2, label=f"truth {crates[mid]:g}C")
    K0 = min(KS)
    for nm in names:
        ax.plot(N, fit_predict(nm, N, Y_pc[mid], K0), "--", label=nm)
    ax.axvline(K0, color="gray", ls=":")
    ax.set_ylim(max(0, Y_pc[mid].min() - 0.1), 1.02)
    ax.set_title(f"Fit on first {K0} cycles → extrapolate")
    ax.set_xlabel("Cycle")
    ax.set_ylabel("SOH")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(
        os.path.join(figure_dir, "fig3_extrapolation_from_first_K.png"),
        dpi=140,
    )
    plt.close()

    # ---- RESULTS.md ----
    md = [
        "# Extrapolation Benchmark Results", "",
        f"- C-rates: {', '.join(f'{c:g}' for c in crates)}  |  "
        f"cycles: {T}  |  PyBaMM: {runs[0][2].get('pybamm')}",
        f"- Protocol: {runs[0][2].get('protocol_step')}",
        f"- Vary: {runs[0][2].get('vary')}",
        f"- BoL ref = cycle-1 discharge capacity at lowest C = "
        f"{bol_ref:.5f} Ah", "",
    ]
    if flags:
        md += ["## Integrity Flags"] + [f"- {x}" for x in flags] + [""]
    else:
        md += ["## Integrity: all runs complete, no NaNs", ""]
    md += [
        "## Trajectory Summary (per-cell SOH)", "",
        t1.round(4).to_markdown(index=False), "",
        "slope_late/early > 1 ⇒ fade accelerating; < 1 ⇒ decelerating.", "",
        "## Hold-out Extrapolation: sup-error on cycles > K (worst over C)", "",
        piv.pivot(index="form", columns="K", values="sup_err")
           .round(4).to_markdown(), "",
    ]
    results_path = os.path.join(out_dir, "RESULTS.md")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Written {results_path}")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser(
        description="Run extrapolation benchmarking on pilot data."
    )
    ap.add_argument("--dir", default="data/pilot_1500")
    ap.add_argument("--out", default="data/pilot_1500/analysis")
    ap.add_argument("--figures", default="figures")
    a = ap.parse_args()
    run_analysis(a.dir, a.out, a.figures)


if __name__ == "__main__":
    main()
