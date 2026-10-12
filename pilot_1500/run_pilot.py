"""Pilot runner: ONE C-rate per invocation. Chunked, memory-light, resumable, honest status file.

  python run_pilot.py --crate 1.0 --n-cycles 1500 --out results/pilot
  python run_pilot.py --crate 1.0 --n-cycles 1500 --out results/pilot --resume     # after a crash

Outputs in --out:   {c}C_cycles.csv   {c}C_status.json   {c}C_state.pkl (resume checkpoint)
"""
import argparse, json, os, pickle, platform, sys, time, traceback
import numpy as np, pandas as pd, pybamm
from model_def import build, OVERRIDES

REQUIRED = ["Time [s]", "Voltage [V]", "Current [A]", "Discharge capacity [A.h]"]
OPTIONAL = {"porosity_neg_avg_end": "X-averaged negative electrode porosity"}

# ---- PROTOCOL: CONFIRM against the script that generated the existing 50-cycle CSVs ----
CHARGE_RATE_WHEN_VARYING_DISCHARGE = 0.3     # as in the pasted script
DISCHARGE_RATE_WHEN_VARYING_CHARGE = 1.0     # ASSUMPTION - confirm or replace


def step_tuple(c, vary):
    dis, chg = (c, CHARGE_RATE_WHEN_VARYING_DISCHARGE) if vary == "discharge" else (DISCHARGE_RATE_WHEN_VARYING_CHARGE, c)
    return (f"Discharge at {dis}C until 2.5V",
            f"Charge at {chg}C until 4.2V (3 minute period)",
            "Hold at 4.2V until C/100 (3 minute period)")


def make_solver(out_vars, a):
    kw = dict(rtol=a.rtol, atol=a.atol)
    if out_vars:
        kw["output_variables"] = out_vars
    return pybamm.IDAKLUSolver(**kw)


def extract(sol, i0, i1, optional_ok):
    rows = []
    for k in range(i0, i1):
        cyc = sol.cycles[k]
        row = {"cycle": k + 1, "discharge_capacity_Ah": float(np.max(cyc["Discharge capacity [A.h]"].entries))}
        if optional_ok:
            for col, var in OPTIONAL.items():
                row[col] = float(cyc[var].entries[-1])
        rows.append(row)
    return rows


def write_status(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--crate", type=float, required=True)
    p.add_argument("--n-cycles", type=int, default=1500)
    p.add_argument("--chunk", type=int, default=50)
    p.add_argument("--vary", choices=["discharge", "charge"], default="discharge")
    p.add_argument("--model", choices=["user", "light"], default="user")
    p.add_argument("--out", default="results/pilot")
    p.add_argument("--rtol", type=float, default=1e-6)
    p.add_argument("--atol", type=float, default=1e-6)
    p.add_argument("--no-output-vars", action="store_true", help="debug: keep all variables (memory heavy)")
    p.add_argument("--stop-soh", type=float, default=0.0, help="stop when discharge capacity < this fraction of the run's cycle 1 (0 = off)")
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()

    os.makedirs(a.out, exist_ok=True)
    tag = f"{a.crate:g}C"
    csv_p, st_p, pkl_p = (os.path.join(a.out, f"{tag}_{s}") for s in ("cycles.csv", "status.json", "state.pkl"))

    model, pv = build(a.model)
    step = step_tuple(a.crate, a.vary)
    status = dict(crate=a.crate, vary=a.vary, model=a.model, protocol_step=list(step), n_requested=a.n_cycles,
                  n_completed=0, status="running", pybamm=pybamm.__version__, python=sys.version.split()[0],
                  platform=platform.platform(), argv=sys.argv, overrides=OVERRIDES if a.model == "user" else None,
                  rtol=a.rtol, atol=a.atol, optional_variables_ok=None, missing_variables=[], errors=[],
                  chunk_wall_s=[], started=time.strftime("%Y-%m-%d %H:%M:%S"))
    if a.model == "light":
        status["WARNING"] = "LIGHT MODEL - plumbing test only, NOT the user's model"

    rows, done, start, optional_ok = [], 0, None, None
    if a.resume:
        if not (os.path.exists(csv_p) and os.path.exists(pkl_p)):
            sys.exit("resume requested but csv/pkl checkpoint missing - rerun without --resume")
        rows = pd.read_csv(csv_p).to_dict("records")
        done = int(max(r["cycle"] for r in rows))
        with open(pkl_p, "rb") as f:
            start = pickle.load(f)
        optional_ok = "porosity_neg_avg_end" in rows[0]
        print(f"[resume] {done} cycles already done")

    q1 = rows[0]["discharge_capacity_Ah"] if rows else None
    done0 = done
    t_run = time.time()
    while done < a.n_cycles:
        k = min(a.chunk, a.n_cycles - done)
        exp = pybamm.Experiment([step] * k)
        t0 = time.time()
        try:
            candidates = ([REQUIRED + list(OPTIONAL.values()), REQUIRED] if optional_ok is None
                          else [REQUIRED + list(OPTIONAL.values()) if optional_ok else REQUIRED])
            if a.no_output_vars:
                candidates = [None]
            sol = None
            for out_vars in candidates:
                try:
                    sim = pybamm.Simulation(model, experiment=exp, parameter_values=pv, solver=make_solver(out_vars, a))
                    sol = sim.solve(calc_esoh=False, starting_solution=start)
                    if optional_ok is None:
                        optional_ok = out_vars is None or len(out_vars) > len(REQUIRED)
                    break
                except Exception as e:
                    if optional_ok is None and out_vars is not None and len(out_vars) > len(REQUIRED):
                        status["errors"].append(f"optional variables failed ({type(e).__name__}); retrying without: {str(e)[:200]}")
                        status["missing_variables"] = list(OPTIONAL.values())
                        continue
                    raise
            n_have = len(sol.cycles)
            new = extract(sol, done, min(n_have, done + k), bool(optional_ok))
            if len(new) < k:
                status["errors"].append(f"experiment ended early: asked {k} cycles in chunk, got {len(new)}")
            rows += new
            done += len(new)
            start = sol
            if len(new) < k:
                break
        except Exception as e:
            status["errors"].append(f"{type(e).__name__}: {str(e)[:500]}")
            status["traceback"] = traceback.format_exc()[-1500:]
            print("CHUNK FAILED:", e)
            break
        wall = time.time() - t0
        status["chunk_wall_s"].append(round(wall, 1))
        df = pd.DataFrame(rows)
        df.to_csv(csv_p, index=False)
        try:
            with open(pkl_p, "wb") as f:
                pickle.dump(start, f)
        except Exception as e:
            status["errors"].append(f"checkpoint pickle failed (resume unavailable): {type(e).__name__}")
        q1 = q1 or rows[0]["discharge_capacity_Ah"]
        status["n_completed"] = done
        write_status(st_p, status)
        eta = (time.time() - t_run) / max(1, done - done0) * (a.n_cycles - done)
        print(f"[{tag}] {done}/{a.n_cycles} cycles, chunk {wall:.0f}s, last Q={rows[-1]['discharge_capacity_Ah']:.5f}, ETA~{eta/60:.0f} min", flush=True)
        if a.stop_soh > 0 and rows[-1]["discharge_capacity_Ah"] < a.stop_soh * q1:
            status["errors"].append(f"stopped early: capacity below {a.stop_soh} of cycle 1")
            break

    # ---- honest final status ----
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["cycle", "discharge_capacity_Ah"])
    nan_ct = int(df.isna().sum().sum()) if len(df) else 0
    status["nan_count"] = nan_ct
    status["optional_variables_ok"] = bool(optional_ok)
    status["n_completed"] = done
    status["status"] = "complete" if (done == a.n_cycles and nan_ct == 0) else ("partial" if done > 0 else "failed")
    status["ended"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_status(st_p, status)
    print("FINAL:", status["status"], f"{done}/{a.n_cycles}", "| errors:", status["errors"][-1:] if status["errors"] else "none")
    sys.exit(0 if status["status"] == "complete" else 1)


if __name__ == "__main__":
    main()
