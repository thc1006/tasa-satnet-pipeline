"""TDD tests for scripts.adapters.from_hypatia.

Contract under test (see docs/internal/v2-feasibility.md §3.2):
  - parse_udp_bursts_outgoing  : per-flow KPI from Hypatia ns-3 sender side
  - parse_udp_bursts_incoming  : per-flow KPI from Hypatia ns-3 receiver side
  - parse_isl_utilization      : per-link per-time-bucket utilization
  - parse_timing_results       : wall-clock breakdown of the ns-3 run
  - read_finished              : run completion sentinel
  - run_dir_to_tasa_metrics    : entire run dir → TASA metrics.csv schema
"""
from __future__ import annotations
from pathlib import Path

import pytest

from scripts.adapters import from_hypatia


# ---------------------------------------------------------------------------
# parse_udp_bursts_outgoing / incoming
# ---------------------------------------------------------------------------

class TestParseUdpBurstsOutgoing:
    def test_returns_one_record_per_flow(self, hypatia_logs_dir):
        flows = from_hypatia.parse_udp_bursts_outgoing(
            hypatia_logs_dir / "udp_bursts_outgoing.csv"
        )
        assert len(flows) == 5  # vendored fixture has 5 head rows

    def test_each_record_has_full_kpi_schema(self, hypatia_logs_dir):
        flows = from_hypatia.parse_udp_bursts_outgoing(
            hypatia_logs_dir / "udp_bursts_outgoing.csv"
        )
        f0 = flows[0]
        # Schema from docs/internal/v2-feasibility.md §3.2
        assert f0["flow_id"] == 0
        assert f0["src"] == 1214
        assert f0["dst"] == 1250
        assert f0["target_mbps"] == pytest.approx(10.0)
        assert f0["start_ns"] == 0
        assert f0["end_ns"] == 1_000_000_000_000
        assert f0["runtime_s"] == pytest.approx(10.000800)
        assert f0["achieved_mbps"] == pytest.approx(9.814118)
        assert f0["packets_sent"] == 8334
        assert f0["bytes_target"] == 12_501_000
        assert f0["bytes_sent"] == 12_267_648

    def test_empty_file_returns_empty_list(self, tmp_path):
        empty = tmp_path / "udp_bursts_outgoing.csv"
        empty.write_text("")
        assert from_hypatia.parse_udp_bursts_outgoing(empty) == []

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            from_hypatia.parse_udp_bursts_outgoing(tmp_path / "nope.csv")


class TestParseUdpBurstsIncoming:
    def test_incoming_achieved_mbps_differs_from_outgoing(self, hypatia_logs_dir):
        """Incoming achieved Mbps is typically much lower than outgoing
        because of in-network packet loss — the adapter must surface both."""
        out = from_hypatia.parse_udp_bursts_outgoing(
            hypatia_logs_dir / "udp_bursts_outgoing.csv"
        )
        inc = from_hypatia.parse_udp_bursts_incoming(
            hypatia_logs_dir / "udp_bursts_incoming.csv"
        )
        # Same flow_id, but incoming achieved < outgoing achieved
        out_by_id = {f["flow_id"]: f for f in out}
        inc_by_id = {f["flow_id"]: f for f in inc}
        for fid in [0, 1, 2, 3, 4]:
            assert inc_by_id[fid]["achieved_mbps"] < out_by_id[fid]["achieved_mbps"]


# ---------------------------------------------------------------------------
# parse_isl_utilization
# ---------------------------------------------------------------------------

class TestParseIslUtilization:
    def test_returns_records_with_link_and_time(self, hypatia_logs_dir):
        rows = from_hypatia.parse_isl_utilization(
            hypatia_logs_dir / "isl_utilization.csv"
        )
        assert len(rows) == 100  # head-truncated to 100
        r0 = rows[0]
        assert r0["src_node"] == 0
        assert r0["dst_node"] == 1
        assert r0["t_start_ns"] == 0
        assert r0["t_end_ns"] == 10_000_000_000
        assert r0["utilization_fraction"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# parse_timing_results
# ---------------------------------------------------------------------------

class TestParseTimingResults:
    def test_extracts_run_simulation_step(self, hypatia_logs_dir):
        timing = from_hypatia.parse_timing_results(
            hypatia_logs_dir / "timing_results.csv"
        )
        assert "Run simulation" in timing
        # 107408790859 ns from the vendored sample
        assert timing["Run simulation"] == 107_408_790_859

    def test_total_wall_time_summable(self, hypatia_logs_dir):
        timing = from_hypatia.parse_timing_results(
            hypatia_logs_dir / "timing_results.csv"
        )
        total_ns = sum(timing.values())
        # ~111.9 s for the vendored sample
        assert 110_000_000_000 < total_ns < 115_000_000_000


# ---------------------------------------------------------------------------
# read_finished
# ---------------------------------------------------------------------------

class TestReadFinished:
    def test_yes_returns_true(self, hypatia_logs_dir):
        assert from_hypatia.read_finished(hypatia_logs_dir / "finished.txt") is True

    def test_no_returns_false(self, tmp_path):
        f = tmp_path / "finished.txt"
        f.write_text("No\n")
        assert from_hypatia.read_finished(f) is False

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            from_hypatia.read_finished(tmp_path / "nope.txt")


# ---------------------------------------------------------------------------
# run_dir_to_tasa_metrics — full convertor
# ---------------------------------------------------------------------------

class TestRunDirToTasaMetrics:
    def test_returns_tasa_compatible_metrics_records(self, hypatia_run_dir):
        metrics = from_hypatia.run_dir_to_tasa_metrics(hypatia_run_dir)
        # One TASA-style metric record per Hypatia flow
        assert len(metrics) == 5
        m0 = metrics[0]
        # TASA metrics.csv columns from scripts/metrics.py:262-268
        assert "source" in m0
        assert "target" in m0
        assert "throughput" in m0
        # Real packet-level values, not the 40 Mbps physics formula
        assert m0["throughput"]["average_mbps"] == pytest.approx(9.814118)
        # Mark provenance so downstream knows this came from Hypatia, not formula
        assert m0["throughput"]["source"] == "hypatia"

    def test_raises_on_unfinished_run(self, hypatia_run_dir, tmp_path):
        """If finished.txt says No, refuse to emit metrics — bad data is
        worse than no data."""
        bad_run = tmp_path / "bad_run"
        # Copy structure but mark as unfinished
        import shutil
        shutil.copytree(hypatia_run_dir, bad_run)
        (bad_run / "logs_ns3" / "finished.txt").write_text("No\n")
        with pytest.raises(from_hypatia.IncompleteRunError):
            from_hypatia.run_dir_to_tasa_metrics(bad_run)
