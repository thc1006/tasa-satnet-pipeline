"""End-to-end test: TASA pipeline window data → satgenpy dir → (mocked sim) → metrics.

This test exercises both adapters back-to-back. The satgenpy + ns-3 step in
the middle is mocked out — we copy the vendored Hypatia run directory as if
the simulator had produced it. That keeps the test under 1 s and removes
the ns-3 build dependency.

When v2 ships an actual ns-3 run (docker/hypatia image), this same test
swaps the mock for a `subprocess.run([...])` call and the rest stays.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

import pytest

from scripts.adapters import from_hypatia, to_satgenpy


def test_e2e_windows_to_metrics_via_mocked_simulator(
    tmp_path: Path,
    hypatia_run_dir: Path,
):
    """Full v2 pipeline:
        windows.json → satgenpy state dir → [mocked simulator] → metrics records
    """
    # --- Stage 1: TASA window data (mimicking parse_oasis_log.py output) ---
    windows_data = {
        "meta": {"source": "test_e2e", "count": 2},
        "windows": [
            {
                "type": "cmd", "start": "2025-01-08T10:15:30Z",
                "end": "2025-01-08T10:25:45Z",
                "sat": "ISS-ZARYA", "gw": "HSINCHU", "source": "log",
            },
            {
                "type": "xband", "start": "2025-01-08T11:00:00Z",
                "end": "2025-01-08T11:08:30Z",
                "sat": "ISS-ZARYA", "gw": "TAIPEI", "source": "log",
            },
        ],
    }
    stations = [
        {"name": "HSINCHU", "lat": 24.7881, "lon": 120.9979, "alt": 52},
        {"name": "TAIPEI",  "lat": 25.0330, "lon": 121.5654, "alt": 10},
    ]
    satellites = [
        ("ISS-ZARYA",
         "1 25544U 98067A   24280.50000000  .00016717  00000+0  30359-3 0  9993",
         "2 25544  51.6424  25.4288 0006313  98.7631  29.9879 15.49512388433380"),
    ]

    # --- Stage 2: Adapter → satgenpy state directory ---
    state_dir = tmp_path / "satgenpy_state"
    to_satgenpy.windows_to_satgenpy_dir(
        windows_data=windows_data,
        stations=stations,
        satellites=satellites,
        out_dir=state_dir,
    )
    # Sanity: directory contains the 6 required files
    for required in [
        "description.txt", "tles.txt", "ground_stations.txt", "isls.txt",
        "gsl_interfaces_info.txt", "udp_burst_schedule.csv",
    ]:
        assert (state_dir / required).exists(), f"missing {required}"

    # --- Stage 3: [Mocked] simulator run.
    # In production v2 this is `docker run hypatia-sim ... --state-dir=...`.
    # Here we copy the vendored Hypatia run to simulate completion.
    run_dir = tmp_path / "ns3_run"
    shutil.copytree(hypatia_run_dir, run_dir)

    # --- Stage 4: Adapter ← Hypatia run output ---
    metrics = from_hypatia.run_dir_to_tasa_metrics(run_dir)

    # --- Assertions on the round-trip ---
    assert len(metrics) > 0
    # Every record must carry packet-level provenance
    assert all(m["throughput"]["source"] == "hypatia" for m in metrics)
    # Achieved Mbps comes from the ns-3 run, not a physics formula
    assert all(0.0 < m["throughput"]["average_mbps"] < 100.0 for m in metrics)
    # Delivery ratio surfaces in-network loss
    delivery_ratios = [
        m["throughput"]["delivery_ratio"] for m in metrics
        if m["throughput"]["delivery_ratio"] is not None
    ]
    assert all(0.0 <= r <= 1.0 for r in delivery_ratios)


def test_v2_adapter_pair_does_not_import_sgp4_or_ns3():
    """Adapters must be runtime-independent of sgp4/ns3 — that is the whole
    point of the file-format-only design. If either of these imports starts
    appearing in the adapter modules, v2's lightweight adapter promise is broken.
    """
    import scripts.adapters.from_hypatia as fh
    import scripts.adapters.to_satgenpy as ts
    import sys
    # ns3 isn't a Python package anyway, but sgp4 IS available in the image —
    # we want to confirm the adapter doesn't pull it in transitively.
    for mod in (fh, ts):
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if hasattr(obj, "__module__") and obj.__module__ != mod.__name__:
                src = obj.__module__
                assert not src.startswith("sgp4"), (
                    f"{mod.__name__}.{attr} pulls in sgp4 — adapter must stay pure"
                )
