"""List which parameter names the user's model actually READS, and flag overrides that are NOT read (silent no-ops)."""
import pybamm
from model_def import OVERRIDES
model = pybamm.lithium_ion.DFN({"particle phases": ("2","1"),"open-circuit potential": (("single","current sigmoid"),"single"),
 "particle mechanics": ("swelling only","none"),"loss of active material": ("stress-driven","none"),"SEI": "solvent-diffusion limited",
 "SEI porosity change": "true","particle": "Fickian diffusion","cell geometry": "arbitrary","lithium plating": "partially reversible","lithium plating porosity change": "true"})
used = {p.name for p in model.parameters}
print("pybamm", pybamm.__version__, "| parameters read by the model:", len(used))
for k, v in OVERRIDES.items():
    print(f"  {'READ   ' if k in used else 'NOT READ'}  {k} = {v}")
sei = sorted(n for n in used if "SEI" in n and ("diffusivity" in n or "thickness" in n))
print("SEI diffusivity/thickness names the model reads:", sei)
