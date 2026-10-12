"""1500-Cycle Pilot Runner for FIXED_SET.md configuration.
Runs chunked (50 cycles/chunk), writes {c}C_cycles.csv, {c}C_status.json,
and a lightweight checkpoint {c}C_state.pkl (saving sol.last_state ~35MB to protect drive space).
"""
import argparse, json, os, pickle, platform, sys, time, traceback
import numpy as np, pandas as pd, pybamm
from model_def_fixedset import build

OUTPUT_VARS = [
    "Time [s]",
    "Voltage [V]",
    "Current [A]",
    "Discharge capacity [A.h]",
    "Loss of lithium inventory [%]",
    "Loss of active material in positive electrode [%]",
    "Loss of active material in negative electrode [%]",
    "X-averaged negative electrode porosity",
]

def step_tuple(c, vary="discharge"):
    dis, chg = (c, 0.3) if vary == "discharge" else (1.0, c)
    return (
        f"Discharge at {dis}C until 2.5V",
        f"Charge at {chg}C until 4.2V (3 minute period)",
        "Hold at 4.2V until C/100 (3 minute period)",
    )

def extract(sol, i0, i1):
    rows = []
    for k in range(i0, i1):
        cyc = sol.cycles[k]
        row = {
            "cycle": k + 1,
            "discharge_capacity_Ah": float(np.max(cyc["Discharge capacity [A.h]"].entries)),
            "LLI_pc": float(cyc["Loss of lithium inventory [%]"].entries[-1]),
            "LAM_pe_pc": float(cyc["Loss of active material in positive electrode [%]"].entries[-1]),
            "LAM_ne_pc": float(cyc["Loss of active material in negative electrode [%]"].entries[-1]),
            "porosity_neg_avg_end": float(cyc["X-averaged negative electrode porosity"].entries[-1]),
        }
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
    p.add_argument("--vary", default="discharge")
    p.add_argument("--out", default="results/fixedset_1500")
    p.add_argument("--rtol", type=float, default=1e-6)
    p.add_argument("--atol", type=float, default=1e-6)
    a = p.parse_args()

    os.makedirs(a.out, exist_ok=True)
    tag = f"{a.crate:g}C"
    csv_p = os.path.join(a.out, f"{tag}_cycles.csv")
    st_p = os.path.join(a.out, f"{tag}_status.json")
    pkl_p = os.path.join(a.out, f"{tag}_state.pkl")

    model, pv = build()
    step = step_tuple(a.crate, a.vary)
    solver = pybamm.IDAKLUSolver(rtol=a.rtol, atol=a.atol, output_variables=OUTPUT_VARS)

    status = dict(
        crate=a.crate,
        vary=a.vary,
        configuration="FIXED_SET.md",
        protocol_step=list(step),
        n_requested=a.n_cycles,
        n_completed=0,
        status="running",
        pybamm=pybamm.__version__,
        python=sys.version.split()[0],
        platform=platform.platform(),
        argv=sys.argv,
        rtol=a.rtol,
        atol=a.atol,
        errors=[],
        chunk_wall_s=[],
        started=time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    rows = []
    done = 0
    start = None
    t_run = time.time()

    print(f"[{tag}] Starting FIXED_SET 1500-cycle run (chunk={a.chunk}, rtol={a.rtol}, atol={a.atol})...", flush=True)

    while done < a.n_cycles:
        k = min(a.chunk, a.n_cycles - done)
        exp = pybamm.Experiment([step] * k)
        t0 = time.time()
        try:
            sim = pybamm.Simulation(model, experiment=exp, parameter_values=pv, solver=solver)
            sol = sim.solve(calc_esoh=False, starting_solution=start)
            n_have = len(sol.cycles)
            new = extract(sol, done, min(n_have, done + k))
            rows += new
            done += len(new)
            start = sol  # chained Solution in RAM
            wall = time.time() - t0
            status["chunk_wall_s"].append(round(wall, 1))
            status["n_completed"] = done

            # Write incremental CSV
            df = pd.DataFrame(rows)
            df.to_csv(csv_p, index=False)

            # Write lightweight checkpoint (~35MB)
            try:
                with open(pkl_p, "wb") as f:
                    pickle.dump(sol.last_state, f)
            except Exception as pe:
                pass

            pct = done / a.n_cycles * 100
            q_curr = rows[-1]["discharge_capacity_Ah"]
            print(f"[{tag}] Chunk done: {done}/{a.n_cycles} cycles ({pct:.1f}%) in {wall:.1f}s ({wall/k:.2f} s/cyc) | Q={q_curr:.5f} Ah", flush=True)

            write_status(st_p, status)
            if len(new) < k:
                status["errors"].append(f"Simulation ended early: asked {k} cycles, got {len(new)}")
                break

        except Exception as e:
            status["errors"].append(f"{type(e).__name__}: {str(e)[:500]}")
            status["traceback"] = traceback.format_exc()[-1500:]
            print(f"[{tag}] CHUNK FAILED at cycle {done}: {e}", flush=True)
            break

    total_wall = time.time() - t_run
    status["wall_total_s"] = round(total_wall, 1)
    status["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")

    df = pd.DataFrame(rows)
    nan_count = int(df.isna().sum().sum()) if not df.empty else -1
    status["nan_count"] = nan_count
    status["status"] = "complete" if (done == a.n_cycles and not status["errors"] and nan_count == 0) else "incomplete"

    write_status(st_p, status)
    print(f"\n[{tag}] FINISHED: {status['status']} ({done}/{a.n_cycles} cycles) in {total_wall:.1f}s ({total_wall/60:.1f} min)", flush=True)

if __name__ == "__main__":
    main()
