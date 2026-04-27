"""TDD: scripts/metrics.py --use-hypatia flag.

Acceptance criterion #4 of v2 ship: metrics.py learns a `--use-hypatia
<run_dir>` flag that, when given, derives metrics from the Hypatia adapter
instead of the physics formula. Without the flag the existing behavior is
preserved (regression check baked into TestNoFlagPreservesPhysicsFormula).
"""
from __future__ import annotations
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
METRICS_PY = REPO_ROOT / "scripts" / "metrics.py"


@pytest.fixture
def minimal_scenario(tmp_path):
    """A minimal valid scenario JSON the metrics.py CLI accepts."""
    scenario = {
        "metadata": {
            "name": "test", "mode": "transparent",
            "generated_at": "2025-01-08T10:00:00Z", "source": "test",
        },
        "topology": {
            "satellites": [
                {"id": "SAT-1", "type": "satellite", "orbit": "LEO",
                 "altitude_km": 550},
            ],
            "gateways": [
                {"id": "HSINCHU", "type": "gateway", "location": "HSINCHU",
                 "capacity_mbps": 100},
            ],
            "links": [
                {"source": "SAT-1", "target": "HSINCHU", "type": "sat-ground",
                 "bandwidth_mbps": 50, "latency_ms": 5.0},
            ],
        },
        "events": [
            {"time": "2025-01-08T10:15:30+00:00", "type": "link_up",
             "source": "SAT-1", "target": "HSINCHU", "window_type": "cmd"},
            {"time": "2025-01-08T10:25:45+00:00", "type": "link_down",
             "source": "SAT-1", "target": "HSINCHU", "window_type": "cmd"},
        ],
        "parameters": {
            "relay_mode": "transparent", "propagation_model": "free_space",
            "data_rate_mbps": 50, "simulation_duration_sec": 86400,
            "processing_delay_ms": 0.0, "queuing_model": "fifo",
            "buffer_size_mb": 10,
        },
    }
    p = tmp_path / "scenario.json"
    p.write_text(json.dumps(scenario))
    return p


def _run_metrics(args, cwd):
    """Invoke scripts/metrics.py as a subprocess."""
    return subprocess.run(
        [sys.executable, str(METRICS_PY), *args],
        cwd=str(cwd), capture_output=True, text=True,
    )


class TestNoFlagPreservesPhysicsFormula:
    """Regression: without --use-hypatia, behavior is identical to v1."""

    def test_default_run_emits_physics_formula_metrics(
        self, minimal_scenario, tmp_path,
    ):
        out_csv = tmp_path / "out.csv"
        summary = tmp_path / "summary.json"
        result = _run_metrics(
            [str(minimal_scenario), "-o", str(out_csv),
             "--summary", str(summary)],
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        # Output stays in the v1 schema — has mode column from scenario
        rows = list(csv.DictReader(out_csv.open()))
        assert len(rows) >= 1
        assert rows[0]["mode"] == "transparent"
        # No throughput.source column in v1 — Hypatia provenance absent
        assert "throughput_source" not in rows[0]


class TestUseHypatiaFlagEmitsHypatiaMetrics:
    """When --use-hypatia <run_dir> is supplied, parse Hypatia outputs."""

    @pytest.fixture
    def vendored_run_dir(self, tmp_path):
        """Copy the vendored sample run into tmp_path so the CLI can read it."""
        src = (REPO_ROOT / "tests" / "fixtures" / "hypatia_samples"
               / "run_minimal")
        dst = tmp_path / "real_run"
        shutil.copytree(src, dst)
        return dst

    def test_flag_replaces_metrics_with_hypatia_data(
        self, minimal_scenario, vendored_run_dir, tmp_path,
    ):
        out_csv = tmp_path / "out.csv"
        summary = tmp_path / "summary.json"
        result = _run_metrics(
            [str(minimal_scenario),
             "-o", str(out_csv), "--summary", str(summary),
             "--use-hypatia", str(vendored_run_dir),
             "--skip-validation"],   # hypatia output schema differs from v1 metrics schema
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        rows = list(csv.DictReader(out_csv.open()))
        # Vendored fixture has 5 flows
        assert len(rows) == 5
        # Hypatia provenance must be present
        assert all(r.get("throughput_source") == "hypatia" for r in rows)
        # Real packet-level achieved Mbps (~9.81 in vendored sample), not the
        # physics formula's fixed value
        first_throughput = float(rows[0]["throughput_mbps"])
        assert 9.0 < first_throughput < 10.0

    def test_flag_with_missing_dir_errors_cleanly(
        self, minimal_scenario, tmp_path,
    ):
        out_csv = tmp_path / "out.csv"
        result = _run_metrics(
            [str(minimal_scenario), "-o", str(out_csv),
             "--use-hypatia", str(tmp_path / "does_not_exist")],
            cwd=tmp_path,
        )
        # Should exit non-zero with a useful message, not a Python traceback
        assert result.returncode != 0
        assert "hypatia" in result.stderr.lower() or "not" in result.stderr.lower()
