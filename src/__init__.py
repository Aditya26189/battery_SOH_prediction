"""Battery SOH Prediction — core modules.

This package contains the canonical source code for the battery
State-of-Health prediction pipeline built on PyBaMM.

Modules
-------
model       : DFN electrochemical model definition (FIXED_SET specification).
simulator   : Chunked 1500-cycle pilot simulation runner.
extrapolator: Hold-out extrapolation analysis across functional forms.
gp_surrogate: Gaussian Process emulator with conformal prediction bands.
"""
