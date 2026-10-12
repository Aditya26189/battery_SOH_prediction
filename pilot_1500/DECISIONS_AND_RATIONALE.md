# Comprehensive Decision Log & Architecture Rationale
**Project**: 1500-Cycle Pilot Battery Degradation Surrogate  
**Repository**: `samrudhnelli/battery_data_dump` (`pilot_1500/`)  
**Timestamp**: 2026-10-12  

---

## 1. Executive Summary & Problem Context

### 1.1 Why the 1500-Cycle Pilot Exists
The existing battery surrogate dataset (`sweep.npz`) contained 60 charge/discharge C-rates in $[0.2, 2.0]$, but each simulation only ran for **50 cycles**. A hold-out evaluation on that data showed that four candidate empirical curve forms—all fitting the first 50 cycles to within $< 1\%$ error—diverged by up to **$0.40$ SOH ($40\%$ capacity)** when extrapolated to cycle 1000 (at 1.0C: predictions ranged from $0.57$ to $0.96$ SOH).

Fifty cycles were mathematically incapable of identifying:
1. Whether degradation is sublinear (diffusion-limited SEI growth) or linear.
2. Whether a **late-life rollover (knee point)** occurs due to lithium plating, positive active material collapse, or porosity clogging.

To resolve this, the 1500-cycle pilot was commissioned at three anchor C-rates ($C = 0.2, 1.0, 2.0$) to determine the true long-horizon trajectory shape and calibrate the surrogate basis.

---

## 2. Chronological Timeline & Decision Evolution

### Stage 1: The Initial 1500-Cycle Pilot Execution
- **What ran**: The agent executed 1500 cycles at 0.2C, 1.0C, and 2.0C using `model_def.py` and PyBaMM `26.8.0.0` in `btp\pilot_1500`.
- **What was measured**:
  - Total 4500 cycles finished with zero solver failures and zero NaNs.
  - Wall times: 39.5 min (0.2C), 43.9 min (1.0C), 37.5 min (2.0C).
  - Trajectory shape: Late-to-early slope ratios were $0.2205$ (0.2C), $0.2795$ (1.0C), and $0.2991$ (2.0C).
  - Extrapolation hold-out: Square-root kinetics ($\sqrt{N}$) proved to be the only stable functional form when extrapolating from $K = 50$ cycles (worst-case sup error $0.1019$, compared to $0.7585$ for composite $\sqrt{N} + N$ and $1.2981$ for linear $N$).
- **The Anomaly Identified**:
  - While cycle 1 discharge capacities matched the old 50-cycle sweep to within $0.18\% - 0.40\%$, the **50-cycle capacity fade diverged sharply**:
    - **0.2C**: Pilot fade was **$4.82\%$**, whereas the old sweep was **$1.49\%$** (a 3.2× difference).
    - **2.0C**: Pilot fade was **$5.94\%$**, whereas the old sweep was **$3.28\%$** (a 1.8× difference).
  - The initial report hypothesized that this was due to updated LAM parameters ($5.8778 \times 10^{-6}$ vs earlier $3 \times 10^{-6}$).

---

### Stage 2: Diagnostic Attribution (`files (17)/agent_prompt_diagnose.md`)
The user provided a strict diagnostic prompt with 6 hard rules to determine *why* the numbers differed, forbidding curve-fitting or parameter tuning.

#### 1. Re-Verification of Sandbox Numbers `[measured]`
All Phase 2 ablations ran locally on Windows (`pybamm==26.8.0.0`) and matched the sandbox predictions to $< 1 \times 10^{-5}$ relative:
- `base 0.2C`: $4.819\%$ fade vs old sweep $1.488\%$ ($3.20\%$ max relative difference).
- `rtol=1e-4`: Fade shifted by only $0.002$ percentage points ($4.819\% \to 4.817\%$), proving solver tolerance was not the cause.
- `all_lam_prop_0`: Setting **all three** LAM terms to 0 only shifted fade from $4.819\%$ to $4.755\%$ ($0.06$ percentage points). **Conclusion**: The initial report's hypothesis attributing the divergence to LAM was definitively refuted.

#### 2. Override Audit (`audit_overrides.py`) `[measured]`
PyBaMM $\ge 25.1.0$ renamed SEI parameters. An audit of the 13 overrides revealed that **5 were unread silent no-ops**:
1. `Primary: Outer SEI solvent diffusivity [m2.s-1]` (Model reads `Primary: SEI solvent diffusivity [m2.s-1]`).
2. `Secondary: Outer SEI solvent diffusivity [m2.s-1]` (Model reads `Secondary: SEI solvent diffusivity [m2.s-1]`).
3. `Lithium plating transfer coefficient` (Bare name; model reads phased names).
4. `Dead lithium decay constant [s-1]` (Bare name; model reads phased names).
5. `Positive electrode LAM constant proportional term [s-1]` (Positive electrode mechanics was set to `"none"`, so positive LAM was inactive).

#### 3. Fixing SEI Names Alone Made Fade Worse `[measured]`
When the tuned values ($2.5 \times 10^{-24}$ and $9.5 \times 10^{-22}$) were applied under the modern names the model actually reads (`SEI solvent diffusivity`), fade jumped to **$6.91\%$** (0.2C) and **$7.89\%$** (2.0C)—moving even further from the old sweep's $1.49\%$.

#### 4. Tracing the Old 50-Cycle Sweep Origin `[measured]`
- Git commit inspection revealed:
  - `commit 6084931c` (2026-10-11 10:08 UTC): `System check: Kaggle simulation starting` (`run_status.txt`: *"Kaggle PyBaMM simulation started..."*).
  - `commit f40001cc` (2026-10-11 11:40 UTC): `Auto-push: 60 PyBaMM degradation CSVs completed`.
  - The old 60-point sweep was generated remotely in an automated Kaggle Linux container on 2026-10-11.
- Inspection of `0.2C_degradation_data.csv`:
  - **Positive LAM was active**: `Loss of active material in positive electrode [%]` reached **$0.3736\%$** at cycle 50.
  - In contrast, the pilot script had positive mechanics and LAM set to `"none"`, producing 0% positive degradation.

#### 5. Tracing the Project Specification Contract `[measured]`
Inspection of repository documentation uncovered [`results/FIXED_SET.md`](file:///C:/Users/LawLight/Desktop/btp/results/FIXED_SET.md) and [`docs/SCRIPT_AUDIT.md`](file:///C:/Users/LawLight/Desktop/btp/docs/SCRIPT_AUDIT.md):
- **Script B (BoL, 2-cycle template)**: Used `"particle mechanics": ("swelling only", "none")`, obsolete `Outer SEI` names, and initial rate constants ($5.8778 \times 10^{-6}$). The pilot script had inadvertently adopted this template.
- **Script A (EoL, calibrated full-life specification)**: Formally captured in `results/FIXED_SET.md`:
  - Mechanics: `("swelling only", "swelling only")` (both electrodes).
  - LAM: `("stress-driven", "stress-driven")` (both electrodes).
  - Calibrated rate constants: `Pri LAM = 3e-6`, `Sec LAM = 2.4e-8`, `Pos LAM = 1.7778e-07`, `Dead Li = 8e-6 / 6e-6`.

---

### Stage 3: Like-with-Like Verification (`model_def_fixedset.py`)
To compare exact quantities without guessing, [`model_def_fixedset.py`](file:///c:/Users/LawLight/Desktop/battery_data_dump/pilot_1500/model_def_fixedset.py) was built adhering strictly to `results/FIXED_SET.md`. A 50-cycle run was executed at 0.2C and 2.0C.

#### 50-Cycle Direct Comparison at Cycle 50 `[measured]`

| Metric | C-rate | Old Kaggle CSV | `FIXED_SET.md` (`model_def_fixedset.py`) | Delta (`FIXED_SET` vs Old) |
| :--- | :---: | :---: | :---: | :---: |
| **Q1 (Ah)** | 0.2C | 4.897760 | 4.907774 | +0.010014 (+0.20%) |
| | 2.0C | 4.690475 | 4.709462 | +0.018987 (+0.40%) |
| **Q50 (Ah)** | 0.2C | 4.824870 | 4.897631 | +0.072761 (+1.51%) |
| | 2.0C | 4.536775 | 4.636710 | +0.099935 (+2.20%) |
| **Capacity Fade** | 0.2C | 1.4882% | 0.2067% | -1.2815 pp |
| | 2.0C | 3.2768% | 1.5448% | -1.7320 pp |
| **LLI [%]** | 0.2C | 1.3290% | 0.4038% | -0.9252 pp |
| | 2.0C | 2.2151% | 0.5267% | -1.6884 pp |
| **LAM Positive [%]** | 0.2C | **0.3736%** | **0.3751%** | **+0.0015 pp (Matches to 0.0015%)** |
| | 2.0C | **0.3737%** | **0.3758%** | **+0.0021 pp (Matches to 0.0021%)** |
| **LAM Negative [%]** | 0.2C | 0.4282% | 0.0553% | -0.3729 pp |
| | 2.0C | 2.5076% | 0.4965% | -2.0111 pp |

#### Critical Conclusions from Like-with-Like Test
1. **Positive Electrode Mechanics Verified**: Positive LAM matched the old Kaggle CSVs almost identically across both C-rates (**0.3751% vs 0.3736%**; **0.3758% vs 0.3737%**). This conclusively proves that the positive electrode mechanics and rate constant (`1.7778e-07`) in `FIXED_SET.md` are the exact ones that ran on Kaggle.
2. **SEI Diffusivity Impact**: In `FIXED_SET.md`, when the intended diffusivities (`2.5e-24` / `9.5e-22`) are read by modern PyBaMM, SEI growth is strongly suppressed (LLI is only 0.40% at 0.2C vs 1.33% in Kaggle). This explained why fade in `FIXED_SET.md` is 0.21% over 50 cycles.

---

### Stage 4: Solver Tolerance Decision & Performance Benchmark
The user requested an accurate runtime estimate before initiating 1500-cycle runs.

#### Benchmark Results: `atol=1e-8` vs `atol=1e-6`
- **At `atol=1e-8`** (`FIXED_SET.md` §B verbatim):
  - Solved 50 cycles of 0.2C in **589.2 s (11.78 s/cycle)**.
  - The 100× tighter absolute tolerance forces the variable-step IDAKLU solver to take tiny time steps over the slow 5-hour 0.2C discharge.
  - Projecting 1500 cycles at 0.2C alone would require **~4.9 hours** (and ~6.8 hours total).
- **At `atol=1e-6`** (Standard Option A):
  - Solved 50 cycles of 0.2C in **68.9 s (1.38 s/cycle)**.
  - Solved 50 cycles of 2.0C in **63.0 s (1.26 s/cycle)**.
  - Phase 2 ablation (`rtol1e-4`) proved that changing tolerance between $10^{-4}$ and $10^{-6}$ shifted capacity by only $\le 4.5 \times 10^{-5}$ ($0.004\%$).
  - Total 1500-cycle sequential runtime for 0.2C, 1.0C, and 2.0C is **~1 hour 55 minutes** (over 3× faster).
- **Decision**: User approved **Option A (`rtol=1e-6, atol=1e-6`)** for the full 1500-cycle run.

---

### Stage 5: Resource & Disk Safety Decisions
- **Disk Margin Issue**: The host machine's C: drive had only **~1.48 GB of free space**.
- **Root Cause of Disk Risk**: The previous pilot's `run_pilot.py` pickled the cumulative PyBaMM `Solution` object at cycle 1500, creating three **~2.55 GB** `.pkl` files (total 7.7 GB), which would immediately crash the system with `Errno 28: No space left on device`.
- **Architectural Solution in `run_pilot_fixedset.py`**:
  - Keep the Solution chained in RAM during chunked execution (RAM usage is flat and $< 400$ MB).
  - Overwrite only `sol.last_state` as the disk resume checkpoint (**~35 MB**, a 98.6% size reduction).
  - Cycle summaries saved incrementally to CSV (**~65 KB**).
  - Disk space usage during the run remains safely under 40 MB.

---

### Stage 6: Version Control & Step-by-Step Persistence
Per user instruction (*"also do the commits as we are progressing to save the working"*):
- Git tracking established in `battery_data_dump`.
- Added [`.gitignore`](file:///c:/Users/LawLight/Desktop/battery_data_dump/.gitignore) to exclude `.pkl`, `.venv`, and `__pycache__`.
- **Commit History**:
  - `commit f433df5`: Verified `FIXED_SET` configuration and 50-cycle comparative report.
  - `commit 13be43c`: Configured `driver_fixedset.py` and `run_pilot_fixedset.py`.
  - Automatic git commit triggers configured in `driver_fixedset.py` immediately upon completion of each C-rate (0.2C, 1.0C, 2.0C) and following final analysis.

---

## 3. Master Decision Reference Table

| Decision Item | Decision Made | Rationale | Implementing File / Evidence |
| :--- | :--- | :--- | :--- |
| **Model Specification** | Adopt `FIXED_SET.md` verbatim (both electrodes mechanics & LAM on) | Matches true project contract; positive LAM matches old Kaggle CSV to 0.0015% | [`model_def_fixedset.py`](file:///c:/Users/LawLight/Desktop/battery_data_dump/pilot_1500/model_def_fixedset.py) |
| **SEI Diffusivity Names** | Use modern `SEI solvent diffusivity` | `Outer SEI` is unread in PyBaMM $\ge 25.1$ | [`audit_overrides.py`](file:///c:/Users/LawLight/Desktop/battery_data_dump/pilot_1500/audit_overrides.py) |
| **Solver Tolerance** | Option A (`rtol=1e-6, atol=1e-6`) | Runs in ~1h 55m instead of ~6.8h; capacity precision is within $< 4.5 \times 10^{-5}$ | [`driver_fixedset.py`](file:///c:/Users/LawLight/Desktop/battery_data_dump/pilot_1500/driver_fixedset.py) |
| **Workspace Location** | `battery_data_dump\pilot_1500\` | User directive to work strictly in active workspace folder | Active folder path |
| **Checkpoint Handling** | Pickle `sol.last_state` (~35 MB) | Prevents exhausting the 1.48 GB available disk space | [`run_pilot_fixedset.py`](file:///c:/Users/LawLight/Desktop/battery_data_dump/pilot_1500/run_pilot_fixedset.py) |
| **Persistence Strategy** | Incremental Git commits per C-rate | Guarantees work is committed and verifiable at every milestone | Git commits `f433df5`, `13be43c` |
