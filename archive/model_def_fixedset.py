"""Model definition adhering strictly to results/FIXED_SET.md.

Every option and parameter is cited directly from FIXED_SET.md:
- Section A: Model Options (enables particle mechanics and stress-driven LAM on BOTH electrodes)
- Section B: Solver settings (IDAKLUSolver atol=1e-8, rtol=1e-6)
- Section C: Degradation rate constants (including modern SEI solvent diffusivity names)
- Section D: Concentrations
- Section E: 39 parameters imported from OKane2022 to complete Chen2020_composite
"""
import pybamm

# ---------------------------------------------------------------------------
# Section A: Model Options (FIXED_SET.md §A)
# ---------------------------------------------------------------------------
OPTIONS = {
    "particle phases": ("2", "1"),
    "open-circuit potential": (("single", "current sigmoid"), "single"),
    "particle mechanics": ("swelling only", "swelling only"),  # §A: both electrodes active
    "loss of active material": ("stress-driven", "stress-driven"),  # §A: both electrodes active
    "SEI": "solvent-diffusion limited",  # §A: ('solvent-diffusion limited', 'none')
    "SEI porosity change": "true",
    "particle": "Fickian diffusion",
    "cell geometry": "arbitrary",
    "lithium plating": "partially reversible",  # §A: ('partially reversible', 'none')
    "lithium plating porosity change": "true",
}

BASE_SET = "Chen2020_composite"

# ---------------------------------------------------------------------------
# Section E: 39 parameters imported from OKane2022 (FIXED_SET.md §E)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Sections C, D & Supervisor Overrides (FIXED_SET.md §C, §D)
# ---------------------------------------------------------------------------
# SEI diffusivities use modern names read by installed PyBaMM (SEI solvent diffusivity,
# not obsolete Outer SEI)
SUPERVISOR_PARAMS = {
    # Section C: Degradation rate constants
    "Positive electrode LAM constant proportional term [s-1]": 1.7778e-07,   # §C
    "Primary: Negative electrode LAM constant proportional term [s-1]": 3e-6, # §C
    "Secondary: Negative electrode LAM constant proportional term [s-1]": 2.4e-8, # §C
    "Primary: Dead lithium decay constant [s-1]": 8e-06,                     # §C
    "Secondary: Dead lithium decay constant [s-1]": 6e-06,                   # §C
    "Primary: SEI solvent diffusivity [m2.s-1]": 2.5e-24,                    # §C (modern read name)
    "Secondary: SEI solvent diffusivity [m2.s-1]": 9.5e-22,                  # §C (modern read name)

    # Section D: Concentrations
    "Primary: Initial concentration in negative electrode [mol.m-3]": 23000,   # §D
    "Primary: Maximum concentration in negative electrode [mol.m-3]": 28700,   # §D
    "Secondary: Initial concentration in negative electrode [mol.m-3]": 277000, # §D
    "Secondary: Maximum concentration in negative electrode [mol.m-3]": 278000, # §D

    # Molar volumes and plating transfer coefficients (phased)
    "Secondary: Negative electrode partial molar volume [m3.mol-1]": 1.20e-05,
    "Positive electrode partial molar volume [m3.mol-1]": 1.2e-06,
    "Primary: Lithium plating transfer coefficient": 0.5,
    "Secondary: Lithium plating transfer coefficient": 0.5,
}


def build():
    """Build the DFN model and parameter values adhering strictly to results/FIXED_SET.md."""
    model = pybamm.lithium_ion.DFN(OPTIONS)
    pv = pybamm.ParameterValues(BASE_SET)
    ok = pybamm.ParameterValues("OKane2022")

    # Step 1: Fill the 39 parameters from OKane2022 (§E)
    fill = {}
    for k in _BARE + _POS:
        fill[k] = ok[k]
    for k in _PHASED:
        fill[f"Primary: {k}"] = ok[k]
        fill[f"Secondary: {k}"] = ok[k]
    pv.update(fill, check_already_exists=False)

    # Step 2: Apply supervisor degradation constants and concentrations (§C, §D)
    pv.update(SUPERVISOR_PARAMS, check_already_exists=False)

    return model, pv
