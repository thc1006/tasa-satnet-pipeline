"""Parse Hypatia ns-3 run output into TASA pipeline's metrics schema.

See docs/internal/v2-feasibility.md §3.2 for the input schema and §6.1 for
how this fits into v2 of the pipeline.
"""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Dict, List


class IncompleteRunError(RuntimeError):
    """Raised when an Hypatia run directory has finished.txt != 'Yes'."""


# ---------------------------------------------------------------------------
# Per-flow KPI parsers (udp_bursts_outgoing.csv / udp_bursts_incoming.csv)
# ---------------------------------------------------------------------------

# Schema (column order, observed in vendored fixture):
#   flow_id, src, dst, target_mbps, start_ns, end_ns,
#   runtime_s, achieved_mbps, packets_sent, bytes_target, bytes_sent
_UDP_BURST_COLUMNS = [
    ("flow_id", int),
    ("src", int),
    ("dst", int),
    ("target_mbps", float),
    ("start_ns", int),
    ("end_ns", int),
    ("runtime_s", float),
    ("achieved_mbps", float),
    ("packets_sent", int),
    ("bytes_target", int),
    ("bytes_sent", int),
]


def _parse_udp_burst_csv(path: Path) -> List[Dict[str, Any]]:
    """Shared parser for outgoing.csv and incoming.csv (same schema)."""
    if not path.exists():
        raise FileNotFoundError(f"Hypatia UDP burst log not found: {path}")
    rows = []
    with path.open() as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            # Hypatia's CSV has a trailing comma: "0,1214,...,12267648,"
            parts = raw.split(",")
            # Take the first N=len(_UDP_BURST_COLUMNS) fields, ignore trailing empty
            row = {}
            for (name, caster), value in zip(_UDP_BURST_COLUMNS, parts):
                row[name] = caster(value)
            rows.append(row)
    return rows


def parse_udp_bursts_outgoing(path: Path) -> List[Dict[str, Any]]:
    """Parse logs_ns3/udp_bursts_outgoing.csv (sender-side per-flow KPIs)."""
    return _parse_udp_burst_csv(path)


def parse_udp_bursts_incoming(path: Path) -> List[Dict[str, Any]]:
    """Parse logs_ns3/udp_bursts_incoming.csv (receiver-side per-flow KPIs).

    Achieved Mbps here is typically far lower than in the matching outgoing
    file — the gap is in-network packet loss. Both should be retained for KPI
    computation; throughput=outgoing's achieved vs delivery_ratio=incoming/outgoing.
    """
    return _parse_udp_burst_csv(path)


# ---------------------------------------------------------------------------
# Per-link utilization parser
# ---------------------------------------------------------------------------

# Schema: src_node, dst_node, t_start_ns, t_end_ns, utilization_fraction
_ISL_COLUMNS = [
    ("src_node", int),
    ("dst_node", int),
    ("t_start_ns", int),
    ("t_end_ns", int),
    ("utilization_fraction", float),
]


def parse_isl_utilization(path: Path) -> List[Dict[str, Any]]:
    """Parse logs_ns3/isl_utilization.csv (per-ISL per-time-bucket utilization)."""
    if not path.exists():
        raise FileNotFoundError(f"Hypatia ISL utilization log not found: {path}")
    rows = []
    with path.open() as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            parts = raw.split(",")
            row = {name: caster(parts[i]) for i, (name, caster) in enumerate(_ISL_COLUMNS)}
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Timing results
# ---------------------------------------------------------------------------

def parse_timing_results(path: Path) -> Dict[str, int]:
    """Parse logs_ns3/timing_results.csv into {step_name: duration_ns}."""
    if not path.exists():
        raise FileNotFoundError(f"Hypatia timing log not found: {path}")
    out: Dict[str, int] = {}
    with path.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            step_name = row[0].strip()
            duration_ns = int(row[1].strip())
            # If the same step appears twice (initial fwd state appears twice
            # in the trace), sum it — total wall is what matters.
            out[step_name] = out.get(step_name, 0) + duration_ns
    return out


# ---------------------------------------------------------------------------
# Run completion sentinel
# ---------------------------------------------------------------------------

def read_finished(path: Path) -> bool:
    """Read logs_ns3/finished.txt; True iff content is 'Yes'."""
    if not path.exists():
        raise FileNotFoundError(f"Hypatia finished sentinel not found: {path}")
    return path.read_text().strip().lower() == "yes"


# ---------------------------------------------------------------------------
# Top-level convertor: Hypatia run dir → TASA metrics records
# ---------------------------------------------------------------------------

def run_dir_to_tasa_metrics(run_dir: Path) -> List[Dict[str, Any]]:
    """Convert a complete Hypatia run directory into TASA pipeline's metrics schema.

    Refuses (raises IncompleteRunError) if logs_ns3/finished.txt is not 'Yes' —
    partial Hypatia output is worse than no Hypatia output. The TASA pipeline
    can fall back to physics-formula metrics in that case.

    The returned records share the shape of scripts/metrics.MetricsCalculator
    output so they can be written through the existing CSV exporter, with one
    addition: throughput.source='hypatia' to mark provenance.
    """
    logs_dir = run_dir / "logs_ns3"
    if not read_finished(logs_dir / "finished.txt"):
        raise IncompleteRunError(
            f"Hypatia run not complete (finished.txt != 'Yes'): {run_dir}"
        )

    outgoing = parse_udp_bursts_outgoing(logs_dir / "udp_bursts_outgoing.csv")
    incoming_by_id = {
        f["flow_id"]: f
        for f in parse_udp_bursts_incoming(logs_dir / "udp_bursts_incoming.csv")
    }

    metrics = []
    for flow in outgoing:
        inc = incoming_by_id.get(flow["flow_id"])
        delivery_ratio = (
            inc["bytes_sent"] / flow["bytes_sent"]
            if inc and flow["bytes_sent"] > 0
            else None
        )
        metrics.append({
            "source": flow["src"],
            "target": flow["dst"],
            "duration_sec": flow["runtime_s"],
            "throughput": {
                "average_mbps": flow["achieved_mbps"],
                "peak_mbps": flow["target_mbps"],
                "source": "hypatia",
                "delivery_ratio": delivery_ratio,
            },
            "packets_sent": flow["packets_sent"],
            "bytes_sent": flow["bytes_sent"],
        })
    return metrics
