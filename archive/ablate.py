"""One ablation variant: N cycles at one C-rate with parameter patches; appends a row to results/ablation/table.csv.
  python ablate.py --label base --crate 0.2
  python ablate.py --label rtol1e-4 --crate 0.2 --rtol 1e-4
  python ablate.py --label lam_prim_3e-6 --crate 0.2 --set "Primary: Negative electrode LAM constant proportional term [s-1]=3e-6"
  python ablate.py --label lam_x0.5 --crate 0.2 --scale "Primary: Negative electrode LAM constant proportional term [s-1]=0.5"
Patches are applied AFTER model_def.build('user'), so model_def.py itself is never edited.
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd, pybamm
from model_def import build
from run_pilot import step_tuple

OUT = ["Time [s]", "Voltage [V]", "Current [A]", "Discharge capacity [A.h]"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--crate", type=float, required=True)
    p.add_argument("--n-cycles", type=int, default=50)
    p.add_argument("--vary", default="discharge")
    p.add_argument("--rtol", type=float, default=1e-6)
    p.add_argument("--atol", type=float, default=1e-6)
    p.add_argument("--set", action="append", default=[], help='"Param name=value"')
    p.add_argument("--scale", action="append", default=[], help='"Param name=factor"')
    p.add_argument("--no-output-vars", action="store_true")
    p.add_argument("--old", default="sweep.npz", help="old sweep (Q_peaks, crates) for the comparison")
    p.add_argument("--pilot", default="pilot.npz")
    p.add_argument("--out", default="results/ablation")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)

    model, pv = build("user")
    patches = {}
    for s in a.set:
        k, v = s.rsplit("=", 1); patches[k] = float(v)
    for s in a.scale:
        k, f = s.rsplit("=", 1); patches[k] = float(pv[k]) * float(f)
    if patches:
        pv.update(patches, check_already_exists=False)

    step = step_tuple(a.crate, a.vary)
    kw = dict(rtol=a.rtol, atol=a.atol)
    if not a.no_output_vars:
        kw["output_variables"] = OUT
    sim = pybamm.Simulation(model, experiment=pybamm.Experiment([step] * a.n_cycles), parameter_values=pv,
                            solver=pybamm.IDAKLUSolver(**kw))
    t0 = time.time(); sol = sim.solve(calc_esoh=False); wall = time.time() - t0
    q = np.array([float(np.max(c["Discharge capacity [A.h]"].entries)) for c in sol.cycles])
    row = dict(label=a.label, crate=a.crate, n=len(q), pybamm=pybamm.__version__, rtol=a.rtol, atol=a.atol,
               patches=json.dumps(patches), Q1=q[0], Q_last=q[-1], fade_pc=1 - q[-1] / q[0], wall_s=round(wall, 1))
    if os.path.exists(a.old):
        d = np.load(a.old); i = int(np.argmin(abs(d["crates"] - a.crate)))
        if abs(d["crates"][i] - a.crate) < 1e-6:
            old = d["Q_peaks"][i][: len(q)]
            row.update(old_Q1=old[0], old_Q_last=old[-1], old_fade_pc=1 - old[-1] / old[0],
                       Q1_reldiff=q[0] / old[0] - 1, maxrel_vs_old=float(np.max(np.abs(q[: len(old)] / old - 1))))
    if os.path.exists(a.pilot):
        d = np.load(a.pilot); i = int(np.argmin(abs(d["crates"] - a.crate)))
        if abs(d["crates"][i] - a.crate) < 1e-6:
            pq = d["Q"][i][: len(q)]
            row.update(maxrel_vs_pilot=float(np.max(np.abs(q / pq - 1))))
    pd.DataFrame([row]).to_csv(os.path.join(a.out, "table.csv"), mode="a", header=not os.path.exists(os.path.join(a.out, "table.csv")), index=False)
    pd.DataFrame({"cycle": np.arange(1, len(q) + 1), "Q": q}).to_csv(os.path.join(a.out, f"{a.label}_{a.crate:g}C.csv"), index=False)
    print(json.dumps({k: (round(v, 6) if isinstance(v, float) else v) for k, v in row.items()}))


if __name__ == "__main__":
    main()
