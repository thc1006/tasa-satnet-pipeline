"""Fixtures for adapter tests.

Each fixture returns a `Path` pointing into the vendored
`tests/fixtures/hypatia_samples/` tree. Tests should treat these as
read-only schema oracles — they are head-truncated extracts from the
official Hypatia paper-replication archive (see fixture README).
"""
from __future__ import annotations
from pathlib import Path

import pytest

FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "hypatia_samples"


@pytest.fixture
def hypatia_run_dir() -> Path:
    """Path to a Hypatia ns-3 run directory with logs_ns3/ inside."""
    return FIXTURES_ROOT / "run_minimal"


@pytest.fixture
def hypatia_logs_dir(hypatia_run_dir: Path) -> Path:
    """Path to logs_ns3/ subdirectory holding the per-flow CSVs."""
    return hypatia_run_dir / "logs_ns3"


@pytest.fixture
def satgenpy_state_dir() -> Path:
    """Path to a satgenpy network state directory (the input ns-3 reads)."""
    return FIXTURES_ROOT / "satgenpy_state_minimal"
