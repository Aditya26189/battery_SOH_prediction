"""
Extracts SOH trajectories from all PyBaMM degradation CSV files in the directory
and saves them into sweep.npz.

Expected output arrays in sweep.npz:
    crates : (n,)    charge C-rates, sorted ascending
    N      : (T,)    cycle numbers (1 to 50)
    Y      : (n, T)  SOH normalized to true Beginning-of-Life (BoL) capacity
"""

import glob
import os
import re
import numpy as np
import pandas as pd
from scipy.signal import find_peaks


def extract_crate_from_filename(filename):
    basename = os.path.basename(filename)
    match = re.match(r"^([\d\.]+)C_degradation_data\.csv$", basename)
    if match:
        return float(match.group(1))
    return None


def build_sweep_dataset(csv_dir=".", output_path="sweep.npz", verbose=True):
    pattern = os.path.join(csv_dir, "*C_degradation_data.csv")
    csv_files = glob.glob(pattern)
    if not csv_files:
        raise FileNotFoundError(f"No degradation CSV files found matching {pattern}")

    pairs = []
    for f in csv_files:
        crate = extract_crate_from_filename(f)
        if crate is not None:
            pairs.append((crate, f))

    pairs.sort(key=lambda x: x[0])
    crates = np.array([p[0] for p in pairs], dtype=float)
    n = len(crates)
    if verbose:
        print(f"Found {n} simulation CSV files. C-rates range: [{crates.min():.3f}, {crates.max():.3f}]")

    Q_peaks = []
    for crate, fpath in pairs:
        df = pd.read_csv(fpath)
        qd = df["Discharge capacity [A.h]"].values
        peaks, _ = find_peaks(qd, distance=1000, prominence=1.0)
        if len(peaks) != 50:
            raise ValueError(f"Expected 50 cycle peaks in {fpath}, but found {len(peaks)}.")
        Q_peaks.append(qd[peaks])

    Q_peaks = np.array(Q_peaks, dtype=float)  # (n, 50)
    T = Q_peaks.shape[1]
    N = np.arange(1, T + 1, dtype=float)

    # True BoL is the fresh cell capacity at the lowest C-rate (cycle 1 of 0.2C)
    bol_capacity = float(Q_peaks[0, 0])
    Y = Q_peaks / bol_capacity
    Y_per_cell = Q_peaks / Q_peaks[:, [0]]

    np.savez(
        output_path,
        crates=crates,
        N=N,
        Y=Y,
        Q_peaks=Q_peaks,
        Y_per_cell=Y_per_cell,
        bol_capacity=bol_capacity,
    )

    if verbose:
        print(f"Successfully created '{output_path}':")
        print(f"  crates shape : {crates.shape}")
        print(f"  N shape      : {N.shape}")
        print(f"  Y shape      : {Y.shape}")
        print(f"  BoL capacity : {bol_capacity:.6f} Ah")
        print(f"  SOH (Y) range: [{Y.min():.4f}, {Y.max():.4f}]")

    return crates, N, Y


if __name__ == "__main__":
    build_sweep_dataset()
