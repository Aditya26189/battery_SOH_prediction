#!/usr/bin/env python
"""Extract SOH trajectories from raw PyBaMM degradation CSVs → sweep.npz.

Usage
-----
    python scripts/prepare_sweep.py --csv-dir data/sweep --output data/sweep/sweep.npz
"""
import argparse
import glob
import os
import re

import numpy as np
import pandas as pd
from scipy.signal import find_peaks


def extract_crate_from_filename(filename):
    """Parse the C-rate from a filename like ``0.2C_degradation_data.csv``."""
    match = re.match(
        r"^([\d\.]+)C_degradation_data\.csv$", os.path.basename(filename)
    )
    return float(match.group(1)) if match else None


def build_sweep_dataset(csv_dir="data/sweep", output_path="data/sweep/sweep.npz",
                        verbose=True):
    """Build the sweep.npz dataset from raw degradation CSVs.

    Parameters
    ----------
    csv_dir : str
        Directory containing ``*C_degradation_data.csv`` files.
    output_path : str
        Where to write the compressed NumPy archive.
    verbose : bool
    """
    pattern = os.path.join(csv_dir, "*C_degradation_data.csv")
    csv_files = glob.glob(pattern)
    if not csv_files:
        raise FileNotFoundError(f"No CSVs matching {pattern}")

    pairs = []
    for f in csv_files:
        crate = extract_crate_from_filename(f)
        if crate is not None:
            pairs.append((crate, f))
    pairs.sort(key=lambda x: x[0])
    crates = np.array([p[0] for p in pairs], dtype=float)

    if verbose:
        print(f"Found {len(crates)} CSVs, C-rates: "
              f"[{crates.min():.3f}, {crates.max():.3f}]")

    Q_peaks = []
    for crate, fpath in pairs:
        df = pd.read_csv(fpath)
        qd = df["Discharge capacity [A.h]"].values
        peaks, _ = find_peaks(qd, distance=1000, prominence=1.0)
        if len(peaks) != 50:
            raise ValueError(
                f"Expected 50 cycle peaks in {fpath}, got {len(peaks)}"
            )
        Q_peaks.append(qd[peaks])

    Q_peaks = np.array(Q_peaks, dtype=float)
    T = Q_peaks.shape[1]
    N = np.arange(1, T + 1, dtype=float)

    bol_capacity = float(Q_peaks[0, 0])
    Y = Q_peaks / bol_capacity
    Y_per_cell = Q_peaks / Q_peaks[:, [0]]

    np.savez(
        output_path,
        crates=crates, N=N, Y=Y,
        Q_peaks=Q_peaks, Y_per_cell=Y_per_cell,
        bol_capacity=bol_capacity,
    )

    if verbose:
        print(f"Created '{output_path}':")
        print(f"  crates  : {crates.shape}")
        print(f"  N       : {N.shape}")
        print(f"  Y       : {Y.shape}")
        print(f"  BoL cap : {bol_capacity:.6f} Ah")
        print(f"  SOH     : [{Y.min():.4f}, {Y.max():.4f}]")

    return crates, N, Y


def main():
    ap = argparse.ArgumentParser(
        description="Aggregate degradation CSVs into sweep.npz."
    )
    ap.add_argument("--csv-dir", default="data/sweep")
    ap.add_argument("--output", default="data/sweep/sweep.npz")
    a = ap.parse_args()
    build_sweep_dataset(a.csv_dir, a.output)


if __name__ == "__main__":
    main()
