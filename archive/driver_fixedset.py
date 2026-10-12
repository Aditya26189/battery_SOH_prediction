"""Master driver script for FIXED_SET.md 1500-cycle pilot.
Runs sequentially across CRATES = [0.2, 1.0, 2.0], committing each result to git upon completion.
Then runs holdout analysis and compiles final report.
"""
import os, sys, time, subprocess, json
import pandas as pd, numpy as np

CRATES = [0.2, 1.0, 2.0]
N_CYCLES = 1500
CHUNK = 50
OUT_DIR = os.path.join("results", "fixedset_1500")
ANALYSIS_DIR = os.path.join(OUT_DIR, "analysis")
REPO_ROOT = r"c:\Users\LawLight\Desktop\battery_data_dump"
PYTHON_EXE = sys.executable

def git_commit(msg):
    # Auto-committing disabled per user instruction
    return

def run_crate(crate):
    tag = f"{crate:g}C"
    log_file = os.path.join(OUT_DIR, f"log_{tag}.txt")
    err_file = os.path.join(OUT_DIR, f"err_{tag}.txt")
    status_file = os.path.join(OUT_DIR, f"{tag}_status.json")

    print(f"\n=======================================================", flush=True)
    print(f"Starting FIXED_SET 1500-cycle pilot run for {tag}...", flush=True)
    print(f"=======================================================", flush=True)

    cmd = [
        PYTHON_EXE,
        "run_pilot_fixedset.py",
        "--crate", str(crate),
        "--n-cycles", str(N_CYCLES),
        "--chunk", str(CHUNK),
        "--out", OUT_DIR,
        "--rtol", "1e-6",
        "--atol", "1e-6",
    ]

    t0 = time.time()
    with open(log_file, "a", encoding="utf-8") as out_f, open(err_file, "a", encoding="utf-8") as err_f:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
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

    wall = time.time() - t0
    if os.path.exists(status_file):
        with open(status_file, "r") as sf:
            st = json.load(sf)
        print(f"\n[{tag}] Status: {st.get('status')} ({st.get('n_completed')}/{N_CYCLES} cycles) in {wall/60:.1f} min", flush=True)
        git_commit(f"feat(fixedset_1500): complete {tag} 1500-cycle simulation ({st.get('n_completed')}/{N_CYCLES} cycles)")
    else:
        print(f"\n[{tag}] WARNING: No status file found for {tag}!", flush=True)

def run_analysis():
    print(f"\n=======================================================", flush=True)
    print(f"Running merge_and_analyze.py for FIXED_SET...", flush=True)
    print(f"=======================================================", flush=True)

    cmd = [
        PYTHON_EXE,
        "merge_and_analyze.py",
        "--dir", OUT_DIR,
        "--out", ANALYSIS_DIR,
    ]
    subprocess.run(cmd, check=True)
    print("Analysis complete. Results written to:", ANALYSIS_DIR, flush=True)

    # Compile REPORT.md
    generate_report()
    git_commit("feat(fixedset_1500): complete holdout extrapolation analysis and generate REPORT.md")

def generate_report():
    npz_path = os.path.join(ANALYSIS_DIR, "pilot.npz")
    sum_path = os.path.join(ANALYSIS_DIR, "trajectory_summary.csv")
    err_path = os.path.join(ANALYSIS_DIR, "holdout_errors.csv")
    rep_path = os.path.join(OUT_DIR, "REPORT.md")

    if not (os.path.exists(sum_path) and os.path.exists(err_path)):
        return

    sum_df = pd.read_csv(sum_path)
    err_df = pd.read_csv(err_path)
    d = np.load(npz_path)

    lines = [
        "# 1500-Cycle Pilot Report: Canonical FIXED_SET.md Configuration",
        "",
        "## 1. Execution Summary [measured]",
        "- **Model Configuration**: `results/FIXED_SET.md` specification exact (options, rate constants, concentrations).",
        "- **Positive mechanics & LAM**: Active (`swelling only`, `stress-driven`).",
        "- **Negative mechanics & LAM**: Active (`swelling only`, `stress-driven`).",
        "- **Rate constants**: `Pos LAM = 1.7778e-07`, `Pri LAM = 3e-6`, `Sec LAM = 2.4e-8`, `SEI diffusivity = 2.5e-24 / 9.5e-22`.",
        "- **Solver**: IDAKLUSolver `rtol=1e-6, atol=1e-6`.",
        "",
        "## 2. Trajectory Checkpoints [measured]",
        "",
        sum_df.to_markdown(index=False),
        "",
        "## 3. Hold-Out Extrapolation Accuracy [measured]",
        "",
        err_df.to_markdown(index=False),
        "",
        "## 4. Key Findings [inferred & measured]",
        f"- **Slope Ratios (late/early)**: {', '.join([f'{c:.1f}C: {r:.4f}' for c, r in zip(sum_df['C'], sum_df['slope_late/early'])])}.",
        "- **Knee Rollover**: Check whether slope ratio exceeds 1.0 (indicating late-life rollover) or remains < 1.0 (sublinear fade).",
        "",
    ]
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated {rep_path}", flush=True)

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    t0_master = time.time()
    for c in CRATES:
        run_crate(c)
    run_analysis()
    total_min = (time.time() - t0_master) / 60
    print(f"\n=======================================================", flush=True)
    print(f"ALL FIXED_SET PILOT RUNS FINISHED in {total_min:.1f} minutes", flush=True)
    print(f"=======================================================", flush=True)
