"""TASA SatNet ↔ Hypatia / satgenpy adapters.

These modules bridge the TASA pipeline's window/scenario JSON formats to
the file-format contracts that satgenpy consumes (network state directory)
and that ns-3 / Hypatia produces (per-flow CSVs, ISL utilization). They are
pure file-format conversion: no satellite physics, no ns-3 dependency at
import time.

Schema reference: docs/internal/v2-feasibility.md §3.
"""
