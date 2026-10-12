"""Merge pilot CSVs -> pilot.npz, run the cycle-count study, write RESULTS.md + figures.
  python merge_and_analyze.py --dir results/pilot --out results/analysis
"""
import argparse, glob, json, os, re
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

KS = [50, 100, 200, 500]            # fit-window sizes (cycles) for the hold-out test
MILESTONES = [50, 100, 200, 500, 1000, 1500]


def forms():
    one = lambda n: np.ones_like(n)
    lin = {"sqrtN": lambda n: np.column_stack([one(n), np.sqrt(n)]),
           "N": lambda n: np.column_stack([one(n), n]),
           "sqrtN+N": lambda n: np.column_stack([one(n), np.sqrt(n), n]),
           "logN": lambda n: np.column_stack([one(n), np.log(n)])}
    return lin


def fit_predict(name, N, y, ktr):
    tr = N <= ktr
    if name == "power":                                 # y = c - b * N^p
        f = lambda n, c, b, p: c - b * n ** p
        y0 = y[tr]
        try:
            popt, _ = curve_fit(f, N[tr], y0, p0=[y0[0], max(1e-6, y0[0] - y0[-1]) / N[tr][-1] ** 0.7, 0.7],
                                bounds=([0.5, 0, 0.1], [1.5, 1, 2.0]), maxfev=20000)
            return f(N, *popt)
        except Exception:
            return np.full_like(N, np.nan)
    B = forms()[name](N)
    a = np.linalg.lstsq(B[tr], y[tr], rcond=None)[0]
    return B @ a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/pilot")
    ap.add_argument("--out", default="results/analysis")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    # ---------- load + integrity ----------
    runs, flags = [], []
    for f in sorted(glob.glob(os.path.join(a.dir, "*C_cycles.csv"))):
        tag = re.match(r"(.+)C_cycles\.csv", os.path.basename(f)).group(1)
        crate = float(tag)
        st_p = f.replace("_cycles.csv", "_status.json")
        st = json.load(open(st_p)) if os.path.exists(st_p) else {"status": "NO STATUS FILE"}
        df = pd.read_csv(f)
        if st.get("status") != "complete":
            flags.append(f"{crate:g}C status={st.get('status')} ({len(df)} cycles) errors={st.get('errors', [])[-1:]}")
        if st.get("model") == "light":
            flags.append(f"{crate:g}C came from the LIGHT test model - not valid results")
        if df.isna().any().any():
            flags.append(f"{crate:g}C has NaNs")
        runs.append((crate, df, st))
    if not runs:
        raise SystemExit("no *C_cycles.csv found")
    runs.sort(key=lambda r: r[0])
    T = min(len(r[1]) for r in runs)
    crates = np.array([r[0] for r in runs])
    N = np.arange(1, T + 1, dtype=float)
    Q = np.array([r[1]["discharge_capacity_Ah"].values[:T] for r in runs])
    bol_ref = float(Q[0, 0])                            # cycle 1 at the lowest C-rate (NOT a fresh-cell reference)
    Y_bol, Y_pc = Q / bol_ref, Q / Q[:, [0]]
    extra = {}
    if all("porosity_neg_avg_end" in r[1] for r in runs):
        extra["porosity_neg_avg_end"] = np.array([r[1]["porosity_neg_avg_end"].values[:T] for r in runs])
    np.savez(os.path.join(a.out, "pilot.npz"), crates=crates, N=N, Q=Q, Y=Y_bol, Y_per_cell=Y_pc,
             bol_ref=bol_ref, **extra)

    # ---------- table 1: trajectories ----------
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
    t1.to_csv(os.path.join(a.out, "trajectory_summary.csv"), index=False)

    # ---------- table 2: hold-out extrapolation by form ----------
    names = list(forms().keys()) + ["power"]
    rec = []
    for i, c in enumerate(crates):
        for K in [k for k in KS if k < T - 10]:
            for nm in names:
                pred = fit_predict(nm, N, Y_pc[i], K)
                err = np.abs(pred[N > K] - Y_pc[i, N > K])
                rec.append(dict(C=c, K=K, form=nm, sup_err=float(np.nanmax(err)) if np.isfinite(err).any() else np.nan,
                                err_at_last_N=float(abs(pred[-1] - Y_pc[i, -1])), in_window_sup_err=float(np.nanmax(np.abs(pred[N <= K] - Y_pc[i, N <= K])))))
    h = pd.DataFrame(rec)
    h.to_csv(os.path.join(a.out, "holdout_errors.csv"), index=False)
    piv = h.pivot_table(index=["K", "form"], values="sup_err", aggfunc="max").reset_index()  # worst over C

    # ---------- figures ----------
    cm = plt.cm.viridis(np.linspace(0, 0.9, len(crates)))
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for i, c in enumerate(crates):
        ax[0].plot(N, Y_pc[i], color=cm[i], label=f"{c:g}C")
        ax[1].plot(N, Y_bol[i], color=cm[i], label=f"{c:g}C")
    ax[0].set_title("SOH, each run normalised to its own cycle 1"); ax[1].set_title(f"SOH vs cycle-1 @ lowest C ({bol_ref:.4f} Ah)")
    for x in ax:
        x.set_xlabel("cycle"); x.set_ylabel("SOH"); x.grid(alpha=.3); x.legend()
    plt.tight_layout(); plt.savefig(os.path.join(a.out, "fig1_trajectories.png"), dpi=140); plt.close()

    fig, ax = plt.subplots(figsize=(7, 4.8))
    for nm in names:
        s = piv[piv.form == nm]
        ax.plot(s.K, s.sup_err, "o-", label=nm)
    ax.set_yscale("log"); ax.set_xlabel("fit window K (cycles)"); ax.set_ylabel("worst-case sup error on cycles > K")
    ax.set_title("Hold-out extrapolation error (worst over C-rates)"); ax.grid(alpha=.3, which="both"); ax.legend()
    plt.tight_layout(); plt.savefig(os.path.join(a.out, "fig2_holdout_error.png"), dpi=140); plt.close()

    mid = len(crates) // 2
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(N, Y_pc[mid], "k", lw=2, label=f"truth {crates[mid]:g}C")
    K0 = min(KS)
    for nm in names:
        ax.plot(N, fit_predict(nm, N, Y_pc[mid], K0), "--", label=nm)
    ax.axvline(K0, color="gray", ls=":"); ax.set_ylim(max(0, Y_pc[mid].min() - .1), 1.02)
    ax.set_title(f"Fit on first {K0} cycles, extrapolate"); ax.set_xlabel("cycle"); ax.set_ylabel("SOH"); ax.legend(); ax.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(a.out, "fig3_extrapolation_from_first_K.png"), dpi=140); plt.close()

    # ---------- RESULTS.md ----------
    md = ["# Pilot results", "", f"- C-rates: {', '.join(f'{c:g}' for c in crates)}  |  cycles used: {T}  |  pybamm: {runs[0][2].get('pybamm')}",
          f"- protocol step (run 1): {runs[0][2].get('protocol_step')}", f"- vary: {runs[0][2].get('vary')}",
          f"- bol_ref = cycle-1 discharge capacity at lowest C = {bol_ref:.5f} Ah (a run's cycle 1, NOT a fresh-cell reference)", ""]
    md += (["## INTEGRITY FLAGS"] + [f"- {x}" for x in flags] + [""]) if flags else ["## Integrity: all runs status=complete, no NaNs", ""]
    md += ["## Trajectory summary (per-cell SOH)", "", t1.round(4).to_markdown(index=False), "",
           "slope_late/early > 1 means fade accelerating over the horizon; < 1 decelerating (heuristic, window = last/first 20% of cycles).", "",
           "## Hold-out extrapolation: sup-error of SOH on cycles > K, worst over C-rates", "",
           piv.pivot(index="form", columns="K", values="sup_err").round(4).to_markdown(), "",
           "Read: the K=50 column is what a 50-cycle sweep could have predicted for the remaining horizon.", "",
           "## Files", "- pilot.npz (crates, N, Q, Y, Y_per_cell, bol_ref[, porosity])", "- trajectory_summary.csv, holdout_errors.csv", "- fig1_trajectories.png, fig2_holdout_error.png, fig3_extrapolation_from_first_K.png"]
    open(os.path.join(a.out, "RESULTS.md"), "w", encoding="utf-8").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
