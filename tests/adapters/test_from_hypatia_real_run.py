"""TDD: from_hypatia parses output of an actual ns-3 run, not just a head-truncated fixture.

This test exists to enforce DoD criterion #3 of v2 ship: the adapter must
work on real Hypatia output, not only on the vendored 5-flow head fixture.

It is opt-in via the TASA_HYPATIA_REAL_RUN_DIR env var. CI on machines
without an ns-3 build will skip; the real-run capture step (V2-SHIP-2)
populates the directory and exports the env var before invoking pytest.
"""
from __future__ import annotations
import os
from pathlib import Path

import pytest

from scripts.adapters import from_hypatia


REAL_RUN_DIR_ENV = "TASA_HYPATIA_REAL_RUN_DIR"


def _real_run_dir() -> Path | None:
    raw = os.environ.get(REAL_RUN_DIR_ENV)
    if not raw:
        return None
    p = Path(raw)
    return p if p.exists() else None


real_run = pytest.mark.skipif(
    _real_run_dir() is None,
    reason=(
        f"{REAL_RUN_DIR_ENV} not set or directory missing — run "
        f"docker/hypatia-ns3.Dockerfile, execute a sim, then point "
        f"this env var at the run directory."
    ),
)


@real_run
class TestFromHypatiaRealRun:
    """Verify the adapter behaves on output produced by a live ns-3 simulation."""

    def test_finished_sentinel_is_yes(self):
        run_dir = _real_run_dir()
        assert from_hypatia.read_finished(run_dir / "logs_ns3" / "finished.txt") is True

    def test_outgoing_csv_has_at_least_one_flow(self):
        run_dir = _real_run_dir()
        flows = from_hypatia.parse_udp_bursts_outgoing(
            run_dir / "logs_ns3" / "udp_bursts_outgoing.csv"
        )
        assert len(flows) >= 1
        # Every record must satisfy the documented schema
        f0 = flows[0]
        assert f0["packets_sent"] >= 0
        assert 0.0 <= f0["achieved_mbps"] <= f0["target_mbps"] + 0.1
        assert f0["bytes_sent"] <= f0["bytes_target"]

    def test_run_dir_to_tasa_metrics_succeeds_on_real_output(self):
        run_dir = _real_run_dir()
        metrics = from_hypatia.run_dir_to_tasa_metrics(run_dir)
        assert len(metrics) >= 1
        assert all(m["throughput"]["source"] == "hypatia" for m in metrics)
        # Real numbers (not the 40 Mbps physics formula constant)
        for m in metrics:
            assert m["throughput"]["average_mbps"] >= 0
            # delivery_ratio surfaces real packet loss
            dr = m["throughput"]["delivery_ratio"]
            if dr is not None:
                assert 0.0 <= dr <= 1.0
