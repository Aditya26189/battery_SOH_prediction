"""Model + parameters. build_user_model() copies options and OVERRIDES from Adi's script,
with the canonical 39 OKane2022 mechanics/plating parameter completion from
src/soh_modes/model_setup.py (documented in docs/FIXED_SET.md SS E)."""
import pybamm

# --- FIXED_SET.md SS E: the 39 names taken from OKane2022 -------------------
_BARE = [
    "Dead lithium decay constant [s-1]",
    "Initial SEI thickness [m]",
    "Lithium metal partial molar volume [m3.mol-1]",
    "Lithium plating kinetic rate constant [m.s-1]",
]
_POS = [
    "Positive electrode LAM constant exponential term",
    "Positive electrode LAM constant proportional term [s-1]",
    "Positive electrode Poisson's ratio",
    "Positive electrode Young's modulus [Pa]",
    "Positive electrode critical stress [Pa]",
    "Positive electrode partial molar volume [m3.mol-1]",
    "Positive electrode reference concentration for free of deformation [mol.m-3]",
]
_PHASED = [
    "Dead lithium decay constant [s-1]",
    "Dead lithium decay rate [s-1]",
    "Exchange-current density for plating [A.m-2]",
    "Exchange-current density for stripping [A.m-2]",
    "Initial plated lithium concentration [mol.m-3]",
    "Lithium plating transfer coefficient",
    "Negative electrode LAM constant exponential term",
    "Negative electrode LAM constant proportional term [s-1]",
    "Negative electrode Poisson's ratio",
    "Negative electrode Young's modulus [Pa]",
    "Negative electrode critical stress [Pa]",
    "Negative electrode partial molar volume [m3.mol-1]",
    "Negative electrode reference concentration for free of deformation [mol.m-3]",
    "Typical plated lithium concentration [mol.m-3]",
]

OVERRIDES = {
    "Lithium plating transfer coefficient": 0.5,
    "Dead lithium decay constant [s-1]": 1e-4,
    "Primary: Maximum concentration in negative electrode [mol.m-3]": 28700,
    "Primary: Initial concentration in negative electrode [mol.m-3]": 23000,
    "Secondary: Initial concentration in negative electrode [mol.m-3]": 277000,
    "Secondary: Maximum concentration in negative electrode [mol.m-3]": 278000,
    # final updated parameter for BoL&EoL
    "Positive electrode LAM constant proportional term [s-1]": 1.7778e-07,
    "Primary: Negative electrode LAM constant proportional term [s-1]": 5.8778e-06,
    "Secondary: Negative electrode LAM constant proportional term [s-1]": 2.8778e-07,
    "Primary: Outer SEI solvent diffusivity [m2.s-1]": 2.5e-24,
    "Secondary: Outer SEI solvent diffusivity [m2.s-1]": 9.5e-22,
    "Secondary: Negative electrode partial molar volume [m3.mol-1]": 1.20e-05,
    "Positive electrode partial molar volume [m3.mol-1]": 1.2e-06,
}


def build_user_model():
    model = pybamm.lithium_ion.DFN({
        "particle phases": ("2", "1"),
        "open-circuit potential": (("single", "current sigmoid"), "single"),
        "particle mechanics": ("swelling only", "none"),
        "loss of active material": ("stress-driven", "none"),
        "SEI": "solvent-diffusion limited",
        "SEI porosity change": "true",
        "particle": "Fickian diffusion",
        "cell geometry": "arbitrary",
        "lithium plating": "partially reversible",
        "lithium plating porosity change": "true",
    })
    pv = pybamm.ParameterValues("Chen2020_composite")
    ok = pybamm.ParameterValues("OKane2022")

    fill = {}
    for k in _BARE + _POS:
        fill[k] = ok[k]
    for k in _PHASED:
        fill[f"Primary: {k}"] = ok[k]
        fill[f"Secondary: {k}"] = ok[k]
    pv.update(fill, check_already_exists=False)
    pv.update(OVERRIDES, check_already_exists=False)
    return model, pv


def build_light_model():
    """PLUMBING TEST ONLY."""
    model = pybamm.lithium_ion.DFN({
        "SEI": "solvent-diffusion limited", "lithium plating": "partially reversible",
        "SEI porosity change": "true", "lithium plating porosity change": "true"})
    return model, pybamm.ParameterValues("OKane2022")


def build(kind):
    return {"user": build_user_model, "light": build_light_model}[kind]()
