"""Dump the user's final parameter set (after model_def.build_user_model) to JSON, for diffing across PyBaMM versions.
  python dump_params.py out.json           # run once per environment, then: python diff_params.py a.json b.json
Numbers are stored as floats; function-parameters as their function name."""
import json, sys, pybamm
from model_def import _BARE, _POS, _PHASED, OVERRIDES


def build_pv():   # same parameter logic as model_def.build_user_model, without constructing the model
    pv = pybamm.ParameterValues("Chen2020_composite"); ok = pybamm.ParameterValues("OKane2022")
    fill = {k: ok[k] for k in _BARE + _POS}
    for k in _PHASED:
        fill[f"Primary: {k}"] = ok[k]; fill[f"Secondary: {k}"] = ok[k]
    pv.update(fill, check_already_exists=False); pv.update(OVERRIDES, check_already_exists=False)
    return pv


pv = build_pv()
out = {}
for k in pv.keys():
    v = pv[k]
    out[k] = float(v) if isinstance(v, (int, float)) else (f"<fn {getattr(v, '__name__', type(v).__name__)}>" if callable(v) else str(v))
json.dump({"pybamm": pybamm.__version__, "params": out}, open(sys.argv[1], "w"), indent=0, sort_keys=True)
print(pybamm.__version__, len(out), "parameters ->", sys.argv[1])
