# DIAGNOSTIC REPORT: Pilot vs Old 50-Cycle Sweep Mismatch Attribution

## 1. Re-verification of Section 0 [measured]

Executed locally on Windows (`pybamm==26.8.0.0`, Python 3.12.10, `rtol=atol=1e-6` unless noted, 50 cycles). Output recorded in `results/ablation/table.csv`.

| Run Label | C-rate | Local Q1 (Ah) | Local Q50 (Ah) | Local Fade | Max Rel vs Old Sweep | Max Rel vs Pilot | Sandbox Expected MaxRel vs Pilot |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **base** | 0.2 | 4.906894 | 4.670452 | 4.8186% | 0.032004 (3.20%) | 0.000000 | ~3e-6 |
| **base** | 2.0 | 4.709387 | 4.429706 | 5.9388% | 0.023600 (2.36%) | 0.000000 | ~1e-5 |
| **rtol1e-4** | 0.2 | 4.906942 | 4.670596 | 4.8166% | 0.031975 (3.20%) | 0.000052 | 4.5e-5 |
| **lam_prim_3e-6** | 0.2 | 4.906908 | 4.671541 | 4.7967% | 0.031779 (3.18%) | 0.000233 | 2.3e-4 |
| **all_lam_prop_0** | 0.2 | 4.906936 | 4.673610 | 4.7550% | 0.031350 (3.14%) | 0.000676 | 6.8e-4 |
| **sei_old_names_x0.1** | 0.2 | 4.906894 | 4.670452 | 4.8186% | 0.032004 (3.20%) | 0.000000 | ~0 |
| **sei_names_fixed** | 0.2 | 4.906992 | 4.567866 | 6.9111% | 0.053266 (5.33%) | 0.021965 | n/a |
| **sei_names_fixed** | 2.0 | 4.709245 | 4.337895 | 7.8856% | 0.043837 (4.38%) | 0.020726 | n/a |

- **Comparison to Sandbox Expectations**: All local measurements match the assistant sandbox numbers to within $< 1 \times 10^{-5}$ relative.
- **Key takeaways**:
  1. `rtol=1e-4` shifts fade by only $0.002$ percentage points (solver tolerance does not explain the delta).
  2. Setting all three LAM terms to zero only shifts fade from $4.819\%$ to $4.755\%$ (LAM contributes $< 0.07$ percentage points). The previous report's hypothesis attributing the divergence to LAM is definitively refuted.
  3. Scaling `Outer SEI solvent diffusivity` produces an identical result to 6 decimal places ($4.81856\%$), confirming it is completely unread by the model.
  4. Updating the parameter name to modern `SEI solvent diffusivity` causes fade to increase from $4.82\%$ to $6.91\%$ (0.2C), diverging even further from the old sweep's $1.49\%$.

---

## 2. Override Audit [measured]

Output of `audit_overrides.py` on PyBaMM `26.8.0.0` (100 parameters read by the model):

```
pybamm 26.8.0.0 | parameters read by the model: 100
  NOT READ  Lithium plating transfer coefficient = 0.5
  NOT READ  Dead lithium decay constant [s-1] = 0.0001
  READ      Primary: Maximum concentration in negative electrode [mol.m-3] = 28700
  READ      Primary: Initial concentration in negative electrode [mol.m-3] = 23000
  READ      Secondary: Initial concentration in negative electrode [mol.m-3] = 277000
  READ      Secondary: Maximum concentration in negative electrode [mol.m-3] = 278000
  NOT READ  Positive electrode LAM constant proportional term [s-1] = 1.7778e-07
  READ      Primary: Negative electrode LAM constant proportional term [s-1] = 5.8778e-06
  READ      Secondary: Negative electrode LAM constant proportional term [s-1] = 2.8778e-07
  NOT READ  Primary: Outer SEI solvent diffusivity [m2.s-1] = 2.5e-24
  NOT READ  Secondary: Outer SEI solvent diffusivity [m2.s-1] = 9.5e-22
  READ      Secondary: Negative electrode partial molar volume [m3.mol-1] = 1.2e-05
  READ      Positive electrode partial molar volume [m3.mol-1] = 1.2e-06
SEI diffusivity/thickness names the model reads: ['Primary: Initial SEI thickness [m]', 'Primary: SEI solvent diffusivity [m2.s-1]', 'Secondary: Initial SEI thickness [m]', 'Secondary: SEI solvent diffusivity [m2.s-1]']
```

---

## 3. Evidence About the Old Run [measured]

1. **The Generating Script / Data Location `[measured]`**:
   - Location: 60 CSV files `{c}C_degradation_data.csv` in `samrudhnelli/battery_data_dump`.
   - Git Commit Log:
     - `commit 6084931c137e628235f396fba435abc072dd127a` (2026-10-11 10:08 UTC): `System check: Kaggle simulation starting` (`run_status.txt`: `"Kaggle PyBaMM simulation started..."`).
     - `commit f40001ccdfd72059b91eab09dc1ce0c13b5678b4` (2026-10-11 11:40 UTC): `Auto-push: 60 PyBaMM degradation CSVs completed` (all 60 CSVs committed automatically).
2. **The Environment That Ran It `[measured & inferred]`**:
   - The old 60-point sweep ran in an automated headless Kaggle Linux container on 2026-10-11. Total run duration was 1 hour 32 minutes for 60 C-rates ($~1.5$ minutes per 50-cycle run).
3. **The Old CSV Column Inspection `[measured]`**:
   - Inspecting `0.2C_degradation_data.csv`:
     - Columns: `['Time [s]', 'Throughput capacity [A.h]', 'Discharge capacity [A.h]', 'Loss of lithium inventory [%]', 'Loss of active material in negative electrode [%]', 'Loss of active material in positive electrode [%]', 'X-averaged negative electrode porosity', 'X-averaged negative primary particle surface displacement [m]', 'X-averaged negative secondary particle surface displacement [m]']`
     - Median $\Delta t$: $11.81$ s; Total points: $124,991$; Total time: $1,565,883$ s.
     - **Discrepancy 1**: `Loss of active material in positive electrode [%]` is recorded and reaches **0.3736%** at cycle 50. In the pilot model, positive mechanics is `"none"`, so positive LAM is structurally zero. The old run had positive mechanics/LAM enabled.
     - **Discrepancy 2**: At cycle 50, `Loss of lithium inventory [%]` is only **1.3290%** (total fade 1.488%), compared to **4.8186%** in the pilot model. SEI growth was drastically slower in the Kaggle environment.
4. **Documented Calibration Target `[measured]`**:
   - Located in [`docs/SCRIPT_AUDIT.md:L87-93`](file:///C:/Users/LawLight/Desktop/btp/docs/SCRIPT_AUDIT.md#L87-L93) and [`results/FIXED_SET.md`](file:///C:/Users/LawLight/Desktop/btp/results/FIXED_SET.md):
     > *"Script A's own comments confirm the direction: `# Reduced from 5.8778e-06`, `# Reduced from 2.8778e-07` — Script B's exact values. And Script A declares `pri_lam = [3e-06]` / `sec_lam = [2.4e-08]` as lists at the top, the residue of a sweep over these very parameters. The block is headed `# final updated parameter for BoL&EoL`."*
   - Furthermore, `docs/SCRIPT_AUDIT.md` documents:
     > *"Script B sets `"particle mechanics": ("swelling only", "none")` and `"loss of active material": ("stress-driven", "none")`. The positive electrode therefore has no mechanics and no LAM... Harmless in a 2-cycle BoL run — but it means Script B's parameter block is not a valid template for Script A [the long run]."*
5. **Where `3e-6` Came From `[measured]`**:
   - [`scripts/11_verify_parameter_set.py:L34`](file:///C:/Users/LawLight/Desktop/btp/scripts/11_verify_parameter_set.py#L34): `"Primary: Negative electrode LAM constant proportional term [s-1]": 3e-6`
   - [`results/FIXED_SET.md:L42`](file:///C:/Users/LawLight/Desktop/btp/results/FIXED_SET.md#L42): `Primary: Negative electrode LAM constant proportional term [s-1]     3e-6`
   - It is the hand-calibrated EoL rate constant from Script A.

---

## 4. Version/Build Probe Table [measured]

| Version / Environment | Builds Pasted Model (`raw_run.py`)? | Names Read | 0.2C Q1, Q50, Fade | Max Rel vs Old Sweep |
| :--- | :---: | :---: | :---: | :---: |
| **PyBaMM 26.8.0.0** (pilot env) | **FAIL** (`KeyError: Primary: Negative electrode partial molar volume [m3.mol-1]`) | 100 read; 5 overrides unread | Q1=4.9069, Q50=4.6705 (4.82% fade via completion block) | 0.0320 (0.2C), 0.0236 (2.0C) |
| **PyBaMM 26.10.0.0** (sandbox) | **FAIL** (`KeyError: Primary: Negative electrode partial molar volume [m3.mol-1]`) | Same | Identical to 26.8.0.0 to $< 10^{-5}$ | Same |
| **PyBaMM 24.11.2** (sandbox) | **FAIL** (`ModelError: Missing variable: Negative total SEI thickness [m]`) | Uses `Initial inner/outer SEI thickness` | N/A (model build aborted) | N/A |
| **PyBaMM 24.9.0** (sandbox) | **FAIL** (`OptionError: multiple particle phases cannot have particle mechanics / LAM`) | N/A | N/A (options rejected) | N/A |

---

## 5. Parameter Diff Summary [measured]

- Generated parameter dump `p_26.8.0.0.json` (161 parameters).
- In modern PyBaMM (>= 25.1.0), `Chen2020_composite` defaults `Primary/Secondary: SEI solvent diffusivity [m2.s-1]` to stock `2.5e-22 m2.s-1`.
- Because the pasted script specified `Outer SEI solvent diffusivity`, those overrides were ignored, and PyBaMM solved with the stock value `2.5e-22`, yielding ~4.8% fade over 50 cycles.

---

## 6. Root Cause: Why Pilot and Old Sweep Differ [hypothesised: measured & inferred]

The pilot and the old 50-cycle sweep diverge because of two structural model discrepancies between the pasted pilot script and the environment that generated the old Kaggle sweep:

1. **Different Model Options `[measured]`**:
   - The old Kaggle CSVs explicitly modeled positive electrode degradation (`Loss of active material in positive electrode [%] = 0.3736%` at cycle 50).
   - The pilot script pasted options with `"none"` for positive electrode mechanics and LAM (`("swelling only", "none")`).
2. **SEI Submodel & Kinetics Incompatibility `[measured & inferred]`**:
   - In modern PyBaMM (>= 25.1), `Outer SEI solvent diffusivity` is not a valid parameter name; the pilot fell back to PyBaMM's stock SEI diffusivity ($2.5 \times 10^{-22}$), producing $4.82\%$ fade over 50 cycles.
   - The old Kaggle run accumulated only $1.329\%$ LLI over 50 cycles (yielding $1.488\%$ total fade).
   - When the user's intended values ($2.5 \times 10^{-24}$ and $9.5 \times 10^{-22}$) are applied under the modern parameter name (`SEI solvent diffusivity`), fade increases to $6.91\%$, proving that the old Kaggle run was not simply modern PyBaMM with fixed names. It used an older/custom SEI parameterization or code branch.

---

## 7. Which Trajectory is the Intended Model? [measured]

Per [`results/FIXED_SET.md`](file:///C:/Users/LawLight/Desktop/btp/results/FIXED_SET.md) (the canonical frozen reference contract generated for this project):

- **Intended Model Options** (`FIXED_SET.md` §A):
  ```
  loss of active material: ('stress-driven', 'stress-driven')
  particle mechanics:      ('swelling only', 'swelling only')
  SEI:                     ('solvent-diffusion limited', 'none')
  ```
- **Intended Degradation Rate Constants** (`FIXED_SET.md` §C):
  ```
  Primary: Negative electrode LAM constant proportional term [s-1]:   3e-06
  Secondary: Negative electrode LAM constant proportional term [s-1]: 2.4e-08
  Positive electrode LAM constant proportional term [s-1]:            1.7778e-07
  Primary: SEI solvent diffusivity [m2.s-1]:                          2.5e-24
  Secondary: SEI solvent diffusivity [m2.s-1]:                        9.5e-22
  Primary: Dead lithium decay constant [s-1]:                         8e-06
  Secondary: Dead lithium decay constant [s-1]:                       6e-06
  ```

The pasted pilot script used Script B (a short 2-cycle BoL template with half-disabled options and legacy `Outer SEI` naming) rather than the canonical `FIXED_SET.md` specification.

---

## 8. Decision for the User

1. **Retire the old 50-cycle Kaggle sweep (`sweep.npz`)**: It was produced under an unrecoverable older remote environment with mismatched positive-electrode options and unknown SEI thickness scaling.
2. **Align the model definition with `results/FIXED_SET.md`**: Update `model_def.py` to use the canonical options (`('swelling only', 'swelling only')`, `('stress-driven', 'stress-driven')`), modern SEI names (`SEI solvent diffusivity`), and the intended rate constants (`3e-6`, `2.4e-8`, `1.7778e-07`).
3. **Decision needed**: Confirm whether you would like to run a verified 50-cycle / 1500-cycle calibration run under the canonical `FIXED_SET.md` configuration.

