#!/usr/bin/env python
"""Run C-rate sweep simulations adhering strictly to FIXED_SET.md.

Runs 50-cycle simulations across C-rates in [0.2, 2.0] using the verified
src/model.py (FIXED_SET parameter specification, IDAKLUSolver rtol=1e-6, atol=1e-6).
Saves individual CSVs incrementally with resume capability, and compiles
data/sweep/sweep_fixedset.npz and data/sweep/sweep.npz for the GP surrogate.

Usage:
------
    # Test on a single C-rate:
    python scripts/run_fixedset_sweep.py --crates 1.0

    # Run full 60 C-rate sweep (50 cycles each, resumable):
    python scripts/run_fixedset_sweep.py --count 60

    # Include held-out zero-shot validation C-rate:
    python scripts/run_fixedset_sweep.py --test-crate 1.3338905
"""

import argparse
import json
import os
import sys
import time
import numpy as np
import pandas as pd
import pybamm

# Resolve repo root
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
from src.model import build  # noqa: E402

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

DEFAULT_60_CRATES = [
    0.2, 0.231, 0.261, 0.292, 0.322, 0.353, 0.383, 0.414, 0.444, 0.475,
    0.505, 0.536, 0.566, 0.597, 0.627, 0.658, 0.688, 0.719, 0.749, 0.78,
    0.81, 0.841, 0.871, 0.902, 0.932, 0.963, 0.993, 1.024, 1.054, 1.085,
    1.115, 1.146, 1.176, 1.207, 1.237, 1.268, 1.298, 1.329, 1.359, 1.39,
    1.42, 1.451, 1.481, 1.512, 1.542, 1.573, 1.603, 1.634, 1.664, 1.695,
    1.725, 1.756, 1.786, 1.817, 1.847, 1.878, 1.908, 1.939, 1.969, 2.0,
]


def step_tuple(crate):
    return (
        f"Discharge at {crate}C until 2.5V",
        "Charge at 0.3C until 4.2V (3 minute period)",
        "Hold at 4.2V until C/100 (3 minute period)",
    )


def run_single_crate(crate, n_cycles=50, out_dir="data/sweep_fixedset",
                     rtol=1e-6, atol=1e-6):
    os.makedirs(out_dir, exist_ok=True)
    csv_file = os.path.join(out_dir, f"{crate:g}C_cycles.csv")

    # Resume check
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            if len(df) == n_cycles and not df["discharge_capacity_Ah"].isna().any():
                print(f"[{crate:g}C] Already completed ({len(df)} cycles cached).", flush=True)
                return df
        except Exception:
            pass

    print(f"\n[{crate:g}C] Starting FIXED_SET simulation ({n_cycles} cycles)...", flush=True)
    model, pv = build()
    step = step_tuple(crate)
    exp = pybamm.Experiment([step] * n_cycles)
    solver = pybamm.IDAKLUSolver(rtol=rtol, atol=atol, output_variables=OUTPUT_VARS)
    sim = pybamm.Simulation(model, experiment=exp, parameter_values=pv, solver=solver)

    t0 = time.time()
    sol = sim.solve(calc_esoh=False)
    wall = time.time() - t0

    cycles_data = []
    for k, cyc in enumerate(sol.cycles):
        cap = float(np.max(cyc["Discharge capacity [A.h]"].entries))
        lli = float(cyc["Loss of lithium inventory [%]"].entries[-1])
        lam_pe = float(cyc["Loss of active material in positive electrode [%]"].entries[-1])
        lam_ne = float(cyc["Loss of active material in negative electrode [%]"].entries[-1])
        por = float(cyc["X-averaged negative electrode porosity"].entries[-1])
        cycles_data.append({
            "cycle": k + 1,
            "discharge_capacity_Ah": cap,
            "LLI_pc": lli,
            "LAM_pe_pc": lam_pe,
            "LAM_ne_pc": lam_ne,
            "porosity_neg_avg_end": por,
        })

    df = pd.DataFrame(cycles_data)
    df.to_csv(csv_file, index=False)

    q1 = df["discharge_capacity_Ah"].iloc[0]
    q_end = df["discharge_capacity_Ah"].iloc[-1]
    fade_pc = (1.0 - q_end / q1) * 100
    print(f"[{crate:g}C] Solved {len(df)} cycles in {wall:.1f}s ({wall/n_cycles:.2f} s/cyc) | "
          f"Q1={q1:.5f} Ah, Q{n_cycles}={q_end:.5f} Ah (fade={fade_pc:.3f}%)", flush=True)

    return df


def package_sweep_npz(crates=None, out_dir="data/sweep_fixedset",
                      npz_paths=("data/sweep/sweep_fixedset.npz", "data/sweep/sweep.npz"),
                      n_cycles=50,
                      exclude_crates=(1.3338905,)):
    """Automatically discover all completed C-rate CSVs and package into sweep.npz."""
    import glob
    pattern = os.path.join(out_dir, "*C_cycles.csv")
    csv_files = glob.glob(pattern)

    available = []
    for f in csv_files:
        base = os.path.basename(f)
        crate_str = base[:-len("C_cycles.csv")]
        try:
            crate = float(crate_str)
        except ValueError:
            continue
        # Ensure held-out zero-shot test rates are never included in training set
        if exclude_crates and any(abs(crate - exc) < 1e-4 for exc in exclude_crates):
            continue
        try:
            df = pd.read_csv(f)
            if len(df) >= n_cycles and not df["discharge_capacity_Ah"].isna().any():
                available.append((crate, df["discharge_capacity_Ah"].values[:n_cycles]))
        except Exception:
            pass

    if not available:
        print("No completed simulations to package yet.", flush=True)
        return None

    available.sort(key=lambda x: x[0])
    crates_arr = np.array([x[0] for x in available], dtype=float)
    Q_peaks = np.array([x[1] for x in available], dtype=float)

    N = np.arange(1, n_cycles + 1, dtype=float)
    bol_capacity = float(Q_peaks[0, 0])  # Normalise by lowest C-rate cycle 1
    Y = Q_peaks / bol_capacity
    Y_per_cell = Q_peaks / Q_peaks[:, [0]]

    for p in npz_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        np.savez(
            p,
            crates=crates_arr,
            N=N,
            Y=Y,
            Q_peaks=Q_peaks,
            Y_per_cell=Y_per_cell,
            bol_capacity=bol_capacity,
        )
        print(f"Saved sweep dataset: {p} ({len(crates_arr)} C-rates, {n_cycles} cycles)", flush=True)

    return crates_arr


def main():
    parser = argparse.ArgumentParser(description="Run FIXED_SET C-rate sweep simulations.")
    parser.add_argument("--crates", nargs="+", type=float, default=None,
                        help="Explicit list of C-rates (e.g. 0.2 1.0 2.0)")
    parser.add_argument("--count", type=int, default=60,
                        help="Number of C-rates if generated evenly in [0.2, 2.0] (default: 60)")
    parser.add_argument("--n-cycles", type=int, default=50,
                        help="Number of cycles per C-rate (default: 50)")
    parser.add_argument("--out-dir", default="data/sweep_fixedset",
                        help="Directory to save individual CSVs")
    parser.add_argument("--test-crate", type=float, default=None,
                        help="Optional held-out test C-rate (e.g. 1.3338905)")
    parser.add_argument("--repackage", action="store_true",
                        help="Only repackage available CSVs into sweep.npz and exit")
    parser.add_argument("--anchor-first", action="store_true", default=True,
                        help="Run spanning anchors (every 3rd C-rate) first, then fill intermediates")
    args = parser.parse_args()

    if args.repackage:
        package_sweep_npz(DEFAULT_60_CRATES, out_dir=args.out_dir, n_cycles=args.n_cycles)
        return

    if args.crates is not None:
        crates_to_run = args.crates
    elif args.count == 60:
        if args.anchor_first:
            anchors = DEFAULT_60_CRATES[::3]
            if DEFAULT_60_CRATES[-1] not in anchors:
                anchors.append(DEFAULT_60_CRATES[-1])
            remainder = [c for c in DEFAULT_60_CRATES if c not in anchors]
            crates_to_run = anchors + remainder
        else:
            crates_to_run = DEFAULT_60_CRATES
    else:
        crates_to_run = [round(x, 4) for x in np.linspace(0.2, 2.0, args.count).tolist()]

    print(f"=== FIXED_SET C-Rate Sweep Runner ===")
    print(f"Total C-rates: {len(crates_to_run)}")
    print(f"Cycles per C-rate: {args.n_cycles}")
    print(f"Output directory: {args.out_dir}")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    t_all_start = time.time()
    completed = 0

    for idx, c in enumerate(crates_to_run, 1):
        t_start = time.time()
        print(f"\n--- Progress: [{idx}/{len(crates_to_run)}] C-rate: {c:g}C ---", flush=True)
        try:
            run_single_crate(c, n_cycles=args.n_cycles, out_dir=args.out_dir)
            completed += 1
        except Exception as e:
            print(f"ERROR running {c}C: {e}", flush=True)

        # Update progress and package dataset
        elapsed = time.time() - t_all_start
        package_sweep_npz(crates_to_run, out_dir=args.out_dir, n_cycles=args.n_cycles)

        progress_file = os.path.join(args.out_dir, "sweep_progress.json")
        with open(progress_file, "w") as f:
            json.dump({
                "completed": completed,
                "total": len(crates_to_run),
                "elapsed_s": round(elapsed, 1),
                "last_crate": c,
                "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, f, indent=2)

    # If held-out test C-rate was requested, run it as well!
    if args.test_crate is not None:
        print(f"\n=== Running Held-Out Test C-Rate: {args.test_crate}C ({args.n_cycles} cycles) ===", flush=True)
        run_single_crate(args.test_crate, n_cycles=args.n_cycles, out_dir=args.out_dir)

    total_time = time.time() - t_all_start
    print(f"\n=== SWEEP COMPLETED: {completed}/{len(crates_to_run)} C-rates in {total_time/60:.1f} min ===", flush=True)


if __name__ == "__main__":
    main()
