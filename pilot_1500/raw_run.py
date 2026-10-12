"""Pasted-script model EXACTLY (no completion block) -> 50 cycles at one C-rate. For version probing."""
import sys, time, numpy as np, pybamm
from model_def import OVERRIDES
crate=float(sys.argv[1]); n=int(sys.argv[2])
model = pybamm.lithium_ion.DFN({"particle phases": ("2","1"),"open-circuit potential": (("single","current sigmoid"),"single"),
 "particle mechanics": ("swelling only","none"),"loss of active material": ("stress-driven","none"),"SEI": "solvent-diffusion limited",
 "SEI porosity change": "true","particle": "Fickian diffusion","cell geometry": "arbitrary","lithium plating": "partially reversible","lithium plating porosity change": "true"})
pv = pybamm.ParameterValues("Chen2020_composite"); pv.update(OVERRIDES, check_already_exists=False)
exp = pybamm.Experiment([(f"Discharge at {crate}C until 2.5V","Charge at 0.3C until 4.2V (3 minute period)","Hold at 4.2V until C/100 (3 minute period)")]*n)
sim = pybamm.Simulation(model, experiment=exp, parameter_values=pv, solver=pybamm.IDAKLUSolver(rtol=1e-6, atol=1e-6, output_variables=["Time [s]","Voltage [V]","Current [A]","Discharge capacity [A.h]"]))
t0=time.time(); sol=sim.solve(calc_esoh=False)
q=np.array([float(np.max(c["Discharge capacity [A.h]"].entries)) for c in sol.cycles])
old=np.load("sweep.npz"); i=int(np.argmin(abs(old["crates"]-crate))); o=old["Q_peaks"][i][:n]
print(pybamm.__version__, f"wall {time.time()-t0:.0f}s Q1={q[0]:.5f} Q{n}={q[-1]:.5f} fade={1-q[-1]/q[0]:.5f} | old Q1={o[0]:.5f} Q{n}={o[-1]:.5f} fade={1-o[-1]/o[0]:.5f} | maxrel_vs_old={np.max(np.abs(q/o-1)):.5f}")
