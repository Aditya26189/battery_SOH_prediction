import subprocess
import sys
import time

commands = [
    ["ablate.py", "--label", "base", "--crate", "0.2"],
    ["ablate.py", "--label", "base", "--crate", "2.0"],
    ["ablate.py", "--label", "rtol1e-4", "--crate", "0.2", "--rtol", "1e-4"],
    ["ablate.py", "--label", "lam_prim_3e-6", "--crate", "0.2", "--set", "Primary: Negative electrode LAM constant proportional term [s-1]=3e-6"],
    ["ablate.py", "--label", "all_lam_prop_0", "--crate", "0.2", "--set", "Primary: Negative electrode LAM constant proportional term [s-1]=0", "--set", "Secondary: Negative electrode LAM constant proportional term [s-1]=0", "--set", "Positive electrode LAM constant proportional term [s-1]=0"],
    ["ablate.py", "--label", "sei_old_names_x0.1", "--crate", "0.2", "--scale", "Primary: Outer SEI solvent diffusivity [m2.s-1]=0.1", "--scale", "Secondary: Outer SEI solvent diffusivity [m2.s-1]=0.1"],
    ["ablate.py", "--label", "sei_names_fixed", "--crate", "0.2", "--set", "Primary: SEI solvent diffusivity [m2.s-1]=2.5e-24", "--set", "Secondary: SEI solvent diffusivity [m2.s-1]=9.5e-22"],
    ["ablate.py", "--label", "sei_names_fixed", "--crate", "2.0", "--set", "Primary: SEI solvent diffusivity [m2.s-1]=2.5e-24", "--set", "Secondary: SEI solvent diffusivity [m2.s-1]=9.5e-22"],
]

python_exe = sys.executable

for idx, cmd in enumerate(commands, 1):
    full_cmd = [python_exe] + cmd
    print(f"\n[{idx}/{len(commands)}] Running: {' '.join(cmd)}", flush=True)
    t0 = time.time()
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    dt = time.time() - t0
    if res.returncode != 0:
        print(f"FAILED (code {res.returncode}) after {dt:.1f}s:\n{res.stderr}", flush=True)
        sys.exit(res.returncode)
    else:
        print(f"SUCCESS in {dt:.1f}s:\n{res.stdout.strip()}", flush=True)

print("\n--- ALL PHASE 2 ABLATIONS FINISHED ---", flush=True)
