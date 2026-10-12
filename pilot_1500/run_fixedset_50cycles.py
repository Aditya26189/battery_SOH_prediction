"""Run 50-cycle simulations at 0.2C and 2.0C using model_def_fixedset.py (FIXED_SET.md configuration).

Extracts and reports:
- Q1, Q50, Capacity fade
- Loss of lithium inventory [%]
- Loss of active material in positive electrode [%]
- Loss of active material in negative electrode [%]
- Max relative difference vs old sweep across 50 cycles
"""
import time, os, json
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
]

def run_crate(crate, n_cycles=50, atol=1e-8, rtol=1e-6):
    print(f"\n--- Starting FIXED_SET run at {crate}C ({n_cycles} cycles) ---", flush=True)
    model, pv = build()
    step = (
        f"Discharge at {crate}C until 2.5V",
        "Charge at 0.3C until 4.2V (3 minute period)",
        "Hold at 4.2V until C/100 (3 minute period)",
    )
    exp = pybamm.Experiment([step] * n_cycles)
    solver = pybamm.IDAKLUSolver(atol=atol, rtol=rtol, output_variables=OUTPUT_VARS)
    sim = pybamm.Simulation(model, experiment=exp, parameter_values=pv, solver=solver)

    t0 = time.time()
    sol = sim.solve(calc_esoh=False)
    wall = time.time() - t0
    print(f"Solved {crate}C in {wall:.1f}s ({wall/n_cycles:.2f} s/cycle)", flush=True)

    # Per cycle extraction
    q_cycles = []
    lli_cycles = []
    lam_pe_cycles = []
    lam_ne_cycles = []

    for c in sol.cycles:
        q_cycles.append(float(np.max(c["Discharge capacity [A.h]"].entries)))
        lli_cycles.append(float(c["Loss of lithium inventory [%]"].entries[-1]))
        lam_pe_cycles.append(float(c["Loss of active material in positive electrode [%]"].entries[-1]))
        lam_ne_cycles.append(float(c["Loss of active material in negative electrode [%]"].entries[-1]))

    q_cycles = np.array(q_cycles)
    lli_cycles = np.array(lli_cycles)
    lam_pe_cycles = np.array(lam_pe_cycles)
    lam_ne_cycles = np.array(lam_ne_cycles)

    # Load old sweep for comparison
    old_npz = "sweep.npz"
    if not os.path.exists(old_npz):
        old_npz = "../sweep.npz"
    old = np.load(old_npz)
    idx = int(np.argmin(abs(old["crates"] - crate)))
    old_q = old["Q_peaks"][idx][:n_cycles]

    # Save detailed CSV
    df = pd.DataFrame({
        "cycle": np.arange(1, n_cycles + 1),
        "Q_Ah": q_cycles,
        "old_Q_Ah": old_q,
        "rel_diff": np.abs(q_cycles / old_q - 1),
        "LLI_pc": lli_cycles,
        "LAM_pe_pc": lam_pe_cycles,
        "LAM_ne_pc": lam_ne_cycles,
    })
    out_dir = "results/fixed_set_50"
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, f"fixedset_{crate}C.csv"), index=False)

    q1 = q_cycles[0]
    q50 = q_cycles[-1]
    fade = 1.0 - q50 / q1
    maxrel = float(np.max(np.abs(q_cycles / old_q - 1)))

    res = {
        "crate": crate,
        "wall_s": wall,
        "Q1": q1,
        "Q50": q50,
        "fade_pc": fade * 100,
        "LLI_end_pc": lli_cycles[-1],
        "LAM_pe_end_pc": lam_pe_cycles[-1],
        "LAM_ne_end_pc": lam_ne_cycles[-1],
        "old_Q1": old_q[0],
        "old_Q50": old_q[-1],
        "old_fade_pc": (1.0 - old_q[-1] / old_q[0]) * 100,
        "maxrel_vs_old": maxrel,
    }
    print("Result:", json.dumps({k: (round(v, 6) if isinstance(v, float) else v) for k, v in res.items()}))
    return res

if __name__ == "__main__":
    results = []
    for c in [0.2, 2.0]:
        results.append(run_crate(c))
    
    res_df = pd.DataFrame(results)
    res_df.to_csv("results/fixed_set_50/summary.csv", index=False)
    print("\n--- ALL FIXED_SET RUNS COMPLETED ---")
    print(res_df.to_string())
