"""Convert TASA pipeline state into a satgenpy network state directory.

The output is the input contract for satgenpy (and downstream Hypatia ns-3).
See docs/internal/v2-feasibility.md §3.1 for the schema.

This module is *pure file-format conversion*. It does not run satgenpy or ns-3,
and does not import sgp4 — TLE lines are accepted as opaque strings. The
satgenpy step that consumes the directory is expected to be exercised in a
separate Docker image (docker/hypatia.Dockerfile in a future commit).
"""
from __future__ import annotations
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# WGS84 geodetic → ECEF (matches scripts/tle_windows.geodetic_to_ecef but in
# metres instead of km, matching satgenpy ground_stations.txt expectation)
# ---------------------------------------------------------------------------

def _geodetic_to_ecef_m(lat_deg: float, lon_deg: float, alt_m: float) -> Tuple[float, float, float]:
    """WGS84 geodetic to ECEF (X, Y, Z) in metres."""
    a = 6_378_137.0  # equatorial radius, m
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    n = a / math.sqrt(1 - e2 * (math.sin(lat) ** 2))
    x = (n + alt_m) * math.cos(lat) * math.cos(lon)
    y = (n + alt_m) * math.cos(lat) * math.sin(lon)
    z = (n * (1 - e2) + alt_m) * math.sin(lat)
    return x, y, z


# ---------------------------------------------------------------------------
# Individual file writers
# ---------------------------------------------------------------------------

def write_ground_stations_txt(
    stations: Sequence[Dict[str, Any]],
    out: Path,
    start_id: int = 0,
) -> None:
    """Write satgenpy `ground_stations.txt`.

    Schema (per row): id, name, lat, lon, alt_m, ECEF_x_m, ECEF_y_m, ECEF_z_m
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for i, s in enumerate(stations):
            gs_id = start_id + i
            x, y, z = _geodetic_to_ecef_m(s["lat"], s["lon"], float(s.get("alt", 0)))
            f.write(
                f"{gs_id},{s['name']},{s['lat']:.6f},{s['lon']:.6f},"
                f"{float(s.get('alt', 0)):.6f},{x:.6f},{y:.6f},{z:.6f}\n"
            )


def write_tles_txt(
    satellites: Sequence[Tuple[str, str, str]],
    n_orbits: int,
    n_sats_per_orbit: int,
    out: Path,
) -> None:
    """Write satgenpy `tles.txt`.

    Format: a header `<n_orbits> <n_sats_per_orbit>` followed by 3 lines per
    satellite (name, TLE line 1, TLE line 2).

    satgenpy's `read_tles.py:53` requires the satellite name to have the
    shape `<constellation_name> <numeric_id>` (it does `int(name.split()[1])`).
    To stay compatible, we append a sequential numeric index whenever the
    caller-supplied name is a single token (i.e. has no whitespace).
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        f.write(f"{n_orbits} {n_sats_per_orbit}\n")
        for idx, (name, line1, line2) in enumerate(satellites):
            qualified_name = name if " " in name.strip() else f"{name} {idx}"
            f.write(f"{qualified_name}\n{line1}\n{line2}\n")


def write_isls_txt(pairs: Iterable[Tuple[int, int]], out: Path) -> None:
    """Write satgenpy `isls.txt`: one `src dst` pair per line, space-separated."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for a, b in pairs:
            f.write(f"{a} {b}\n")


def write_gsl_interfaces_info(
    n_satellites: int,
    n_ground_stations: int,
    sat_iface_count: int,
    gs_iface_count: int,
    out: Path,
    bandwidth_factor: float = 1.0,
) -> None:
    """Write satgenpy `gsl_interfaces_info.txt`.

    Hypatia node-id convention: satellites first (ids 0..N-1), then ground
    stations (ids N..N+M-1). Each row is `node_id, num_interfaces, bw_factor`.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for i in range(n_satellites):
            f.write(f"{i},{sat_iface_count},{bandwidth_factor:.6f}\n")
        for j in range(n_ground_stations):
            node_id = n_satellites + j
            f.write(f"{node_id},{gs_iface_count},{bandwidth_factor:.6f}\n")


def write_description_txt(
    max_gsl_length_m: float,
    max_isl_length_m: float,
    out: Path,
) -> None:
    """Write satgenpy `description.txt`."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"max_gsl_length_m={max_gsl_length_m}\n"
        f"max_isl_length_m={max_isl_length_m}\n"
    )


# ---------------------------------------------------------------------------
# Traffic matrix: TASA windows → udp_burst_schedule.csv
# ---------------------------------------------------------------------------

def _parse_iso8601_to_ns(ts: str) -> int:
    """Parse ISO 8601 timestamp to absolute ns since the unix epoch."""
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    return int(dt.timestamp() * 1_000_000_000)


def write_udp_burst_schedule(
    windows: Sequence[Dict[str, Any]],
    node_id_of: Dict[str, int],
    target_mbps: float,
    out: Path,
    sim_start_ns: int | None = None,
) -> None:
    """Write Hypatia `udp_burst_schedule.csv` from TASA windows.

    Each window becomes one UDP burst flow at the given target_mbps. Times are
    expressed relative to sim_start_ns (default: the earliest window's start
    time), so offsets are non-negative ns from t=0 of the simulation.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if sim_start_ns is None and windows:
        sim_start_ns = min(_parse_iso8601_to_ns(w["start"]) for w in windows)
    with out.open("w") as f:
        for flow_id, w in enumerate(windows):
            start_ns = _parse_iso8601_to_ns(w["start"]) - (sim_start_ns or 0)
            end_ns = _parse_iso8601_to_ns(w["end"]) - (sim_start_ns or 0)
            sat_key = w.get("sat") or w.get("satellite")
            gw_key = w.get("gw") or w.get("ground_station")
            src = node_id_of[sat_key]
            dst = node_id_of[gw_key]
            f.write(
                f"{flow_id},{src},{dst},{target_mbps:.10f},"
                f"{start_ns},{end_ns},,\n"
            )


# ---------------------------------------------------------------------------
# Top-level convertor
# ---------------------------------------------------------------------------

# Default LEO geometry constants — match scripts/tle_windows.py and the
# Kuiper-630 fixture. These are reasonable defaults for the smallest TASA case;
# callers can override via kwargs.
_DEFAULT_MAX_GSL_LENGTH_M = 1_260_000.0  # ~1260 km, matches Kuiper-630 fixture
_DEFAULT_MAX_ISL_LENGTH_M = 5_442_958.20  # matches Kuiper-630 fixture


def windows_to_satgenpy_dir(
    windows_data: Dict[str, Any],
    stations: Sequence[Dict[str, Any]],
    satellites: Sequence[Tuple[str, str, str]],
    out_dir: Path,
    *,
    n_orbits: int = 1,
    n_sats_per_orbit: int | None = None,
    sat_iface_count: int = 4,
    gs_iface_count: int = 1,
    target_mbps: float = 10.0,
    isl_pairs: Sequence[Tuple[int, int]] = (),
    max_gsl_length_m: float = _DEFAULT_MAX_GSL_LENGTH_M,
    max_isl_length_m: float = _DEFAULT_MAX_ISL_LENGTH_M,
) -> Path:
    """Materialize a complete satgenpy network state directory.

    Hypatia node-id convention is enforced: satellites take ids 0..N-1, ground
    stations take ids N..N+M-1. The returned Path is `out_dir`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    n_sats = len(satellites)
    n_gs = len(stations)

    if n_sats_per_orbit is None:
        n_sats_per_orbit = n_sats  # 1 orbit × n_sats default

    # Node-id mapping: sat names first, then station names
    node_id_of = {sat[0]: i for i, sat in enumerate(satellites)}
    node_id_of.update({s["name"]: n_sats + i for i, s in enumerate(stations)})

    write_description_txt(
        max_gsl_length_m=max_gsl_length_m,
        max_isl_length_m=max_isl_length_m,
        out=out_dir / "description.txt",
    )
    write_tles_txt(
        satellites=satellites,
        n_orbits=n_orbits,
        n_sats_per_orbit=n_sats_per_orbit,
        out=out_dir / "tles.txt",
    )
    write_ground_stations_txt(
        stations=stations,
        out=out_dir / "ground_stations.txt",
        start_id=n_sats,  # GS ids start after the satellite ids
    )
    write_isls_txt(pairs=isl_pairs, out=out_dir / "isls.txt")
    write_gsl_interfaces_info(
        n_satellites=n_sats,
        n_ground_stations=n_gs,
        sat_iface_count=sat_iface_count,
        gs_iface_count=gs_iface_count,
        out=out_dir / "gsl_interfaces_info.txt",
    )
    write_udp_burst_schedule(
        windows=windows_data["windows"],
        node_id_of=node_id_of,
        target_mbps=target_mbps,
        out=out_dir / "udp_burst_schedule.csv",
    )
    return out_dir
