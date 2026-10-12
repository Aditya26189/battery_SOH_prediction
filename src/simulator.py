"""1500-cycle chunked simulation runner.

Runs the FIXED_SET.md DFN model in configurable chunks (default 50 cycles
per chunk), writing incremental CSV results and lightweight state checkpoints.

Usage (from repo root)
----------------------
    python scripts/run_simulation.py --crate 1.0 --n-cycles 1500 --chunk 50
"""

import argparse
import json
import os
import pickle
import platform
import sys
import time
import traceback

import numpy as np
import pandas as pd
import pybamm


# Resolve src/ relative to this file's location
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
from src.model import build                     # noqa: E402


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


def step_tuple(c_rate, vary="discharge"):
    """Build the three-step CCCV experiment tuple for a given C-rate.

    Parameters
    ----------
    c_rate : float
        Discharge C-rate (e.g. 0.2, 1.0, 2.0).
    vary : str
        Which half-cycle to vary — ``"discharge"`` (default) or ``"charge"``.

    Returns
    -------
    tuple[str, str, str]
        (discharge step, CC charge step, CV hold step).
    """
    dis, chg = (c_rate, 0.3) if vary == "discharge" else (1.0, c_rate)
    return (
        f"Discharge at {dis}C until 2.5V",
        f"Charge at {chg}C until 4.2V (3 minute period)",
        "Hold at 4.2V until C/100 (3 minute period)",
    )


def extract_cycle_data(sol, i_start, i_end):
    """Extract per-cycle summary metrics from a PyBaMM solution.

    Parameters
    ----------
    sol : pybamm.Solution
    i_start, i_end : int
        Cycle index range [i_start, i_end).

    Returns
    -------
    list[dict]
    """
    rows = []
    for k in range(i_start, i_end):
        cyc = sol.cycles[k]
        rows.append({
            "cycle": k + 1,
            "discharge_capacity_Ah": float(np.max(
                cyc["Discharge capacity [A.h]"].entries
            )),
            "LLI_pc": float(
                cyc["Loss of lithium inventory [%]"].entries[-1]
            ),
            "LAM_pe_pc": float(
                cyc["Loss of active material in positive electrode [%]"].entries[-1]
            ),
            "LAM_ne_pc": float(
                cyc["Loss of active material in negative electrode [%]"].entries[-1]
            ),
            "porosity_neg_avg_end": float(
                cyc["X-averaged negative electrode porosity"].entries[-1]
            ),
        })
    return rows


def _write_status(path, data):
    """Atomically write a JSON status file."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def simulate(c_rate, n_cycles=1500, chunk=50, vary="discharge",
             out_dir="data/pilot_1500", rtol=1e-6, atol=1e-6):
    """Run a full-life chunked simulation.

    Parameters
    ----------
    c_rate : float
    n_cycles : int
    chunk : int
    vary : str
    out_dir : str
    rtol, atol : float
    """
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{c_rate:g}C"
    csv_path = os.path.join(out_dir, f"{tag}_cycles.csv")
    status_path = os.path.join(out_dir, f"{tag}_status.json")
    pkl_path = os.path.join(out_dir, f"{tag}_state.pkl")

    model, pv = build()
    step = step_tuple(c_rate, vary)
    solver = pybamm.IDAKLUSolver(
        rtol=rtol, atol=atol, output_variables=OUTPUT_VARS
    )

    status = dict(
        crate=c_rate, vary=vary,
        configuration="FIXED_SET.md",
        protocol_step=list(step),
        n_requested=n_cycles, n_completed=0,
        status="running",
        pybamm=pybamm.__version__,
        python=sys.version.split()[0],
        platform=platform.platform(),
        argv=sys.argv,
        rtol=rtol, atol=atol,
        errors=[], chunk_wall_s=[],
        started=time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    rows = []
    done = 0
    start = None
    t_run = time.time()

    print(f"[{tag}] Starting FIXED_SET simulation "
          f"(n={n_cycles}, chunk={chunk}, rtol={rtol}, atol={atol})…",
          flush=True)

    while done < n_cycles:
        k = min(chunk, n_cycles - done)
        exp = pybamm.Experiment([step] * k)
        t0 = time.time()
        try:
            sim = pybamm.Simulation(
                model, experiment=exp,
                parameter_values=pv, solver=solver,
            )
            sol = sim.solve(calc_esoh=False, starting_solution=start)
            n_have = len(sol.cycles)
            new = extract_cycle_data(sol, done, min(n_have, done + k))
            rows += new
            done += len(new)
            start = sol

            wall = time.time() - t0
            status["chunk_wall_s"].append(round(wall, 1))
            status["n_completed"] = done

            # Incremental CSV
            pd.DataFrame(rows).to_csv(csv_path, index=False)

            # Lightweight checkpoint
            try:
                with open(pkl_path, "wb") as f:
                    pickle.dump(sol.last_state, f)
            except Exception:
                pass

            pct = done / n_cycles * 100
            q_curr = rows[-1]["discharge_capacity_Ah"]
            print(f"[{tag}] {done}/{n_cycles} ({pct:.1f}%) "
                  f"in {wall:.1f}s ({wall/k:.2f} s/cyc) | Q={q_curr:.5f} Ah",
                  flush=True)
            _write_status(status_path, status)

            if len(new) < k:
                status["errors"].append(
                    f"Simulation ended early: asked {k} cycles, got {len(new)}"
                )
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
    status["status"] = (
        "complete"
        if (done == n_cycles and not status["errors"] and nan_count == 0)
        else "incomplete"
    )
    _write_status(status_path, status)
    print(f"\n[{tag}] FINISHED: {status['status']} "
          f"({done}/{n_cycles} cycles) in {total_wall:.1f}s "
          f"({total_wall/60:.1f} min)", flush=True)


def main():
    p = argparse.ArgumentParser(
        description="Run a FIXED_SET.md DFN simulation."
    )
    p.add_argument("--crate", type=float, required=True,
                   help="Discharge C-rate (e.g. 0.2, 1.0, 2.0)")
    p.add_argument("--n-cycles", type=int, default=1500)
    p.add_argument("--chunk", type=int, default=50)
    p.add_argument("--vary", default="discharge")
    p.add_argument("--out", default="data/pilot_1500")
    p.add_argument("--rtol", type=float, default=1e-6)
    p.add_argument("--atol", type=float, default=1e-6)
    a = p.parse_args()
    simulate(a.crate, a.n_cycles, a.chunk, a.vary, a.out, a.rtol, a.atol)


if __name__ == "__main__":
    main()
