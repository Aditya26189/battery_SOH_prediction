#!/usr/bin/env python
"""Run a FIXED_SET.md DFN simulation.

Usage
-----
    python scripts/run_simulation.py --crate 1.0 --n-cycles 1500
    python scripts/run_simulation.py --crate 2.0 --n-cycles 100 --chunk 50
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.simulator import main

if __name__ == "__main__":
    main()
