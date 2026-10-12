#!/usr/bin/env python
"""Run extrapolation benchmarking on pilot data.

Usage
-----
    python scripts/run_analysis.py --dir data/pilot_1500 --out data/pilot_1500/analysis
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.extrapolator import main

if __name__ == "__main__":
    main()
