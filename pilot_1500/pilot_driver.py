"""Driver script to execute Phase 4 (1500-cycle runs for C=0.2, 1.0, 2.0)
and Phase 5 (merge_and_analyze.py), followed by reporting.
Runs sequentially to avoid memory pressure and guarantee solver stability.
"""

import os
import sys
import time
import subprocess
import json
import pandas as pd
import numpy as np

CRATES = [0.2, 1.0, 2.0]
N_CYCLES = 1500
CHUNK = 50
OUT_DIR = os.path.join("results", "pilot")
ANALYSIS_DIR = os.path.join("results", "analysis")

PYTHON_EXE = sys.executable

def run_crate(crate):
    tag = f"{crate:g}C"
    log_file = os.path.join(OUT_DIR, f"log_{tag}.txt")
    err_file = os.path.join(OUT_DIR, f"err_{tag}.txt")
    status_file = os.path.join(OUT_DIR, f"{tag}_status.json")

    print(f"\n=======================================================", flush=True)
    print(f"Starting 1500-cycle pilot run for {tag}...", flush=True)
    print(f"=======================================================", flush=True)

    cmd = [
        PYTHON_EXE,
        "run_pilot.py",
        "--crate", str(crate),
        "--n-cycles", str(N_CYCLES),
        "--chunk", str(CHUNK),
        "--out", OUT_DIR,
    ]

    # Check if resume is possible
    csv_file = os.path.join(OUT_DIR, f"{tag}_cycles.csv")
    pkl_file = os.path.join(OUT_DIR, f"{tag}_state.pkl")
    if os.path.exists(csv_file) and os.path.exists(pkl_file):
        cmd.append("--resume")
        print(f"Checkpoints found for {tag}, running with --resume", flush=True)

    with open(log_file, "a", encoding="utf-8") as out_f, open(err_file, "a", encoding="utf-8") as err_f:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            out_f.write(line)
            out_f.flush()

        stderr_output = proc.stderr.read()
        if stderr_output:
            sys.stderr.write(stderr_output)
            err_f.write(stderr_output)

        proc.wait()

    if os.path.exists(status_file):
        with open(status_file, "r") as sf:
            st = json.load(sf)
        print(f"\n[{tag}] Final Status: {st.get('status')} ({st.get('n_completed')}/{N_CYCLES} cycles completed)")
        if st.get('errors'):
            print(f"[{tag}] Errors: {st.get('errors')}")
    else:
        print(f"\n[{tag}] WARNING: No status file found!")

def run_analysis():
    print(f"\n=======================================================", flush=True)
    print(f"Running merge_and_analyze.py...", flush=True)
    print(f"=======================================================", flush=True)

    cmd = [
        PYTHON_EXE,
        "merge_and_analyze.py",
        "--dir", OUT_DIR,
        "--out", ANALYSIS_DIR,
    ]

    subprocess.run(cmd, check=True)
    print("Analysis complete. Results written to:", ANALYSIS_DIR, flush=True)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    t0_all = time.time()

    for c in CRATES:
        run_crate(c)

    total_wall_s = time.time() - t0_all
    print(f"\nAll pilot runs finished in {total_wall_s/60:.1f} minutes.")

    run_analysis()
