"""TDD tests for scripts.adapters.to_satgenpy.

Contract under test (see docs/internal/v2-feasibility.md §3.1):
  - write_ground_stations_txt : TASA stations → satgenpy ground_stations.txt
  - write_tles_txt            : TLE objects → satgenpy tles.txt with grid header
  - write_isls_txt            : ISL pairs (+grid topology) → satgenpy isls.txt
  - write_gsl_interfaces_info : node count + iface count → gsl_interfaces_info.txt
  - write_description_txt     : max ISL/GSL lengths → description.txt
  - write_udp_burst_schedule  : TASA windows → udp_burst_schedule.csv
  - windows_to_satgenpy_dir   : full convertor (windows + stations + tles → directory)
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from scripts.adapters import to_satgenpy


# ---------------------------------------------------------------------------
# Test fixtures: TASA-side inputs
# ---------------------------------------------------------------------------

@pytest.fixture
def taiwan_stations():
    """Minimal TASA ground station data (subset of taiwan_ground_stations.json)."""
    return [
        {"name": "HSINCHU",  "lat": 24.7881, "lon": 120.9979, "alt": 52},
        {"name": "TAIPEI",   "lat": 25.0330, "lon": 121.5654, "alt": 10},
        {"name": "TAICHUNG", "lat": 24.1477, "lon": 120.6736, "alt": 84},
    ]


@pytest.fixture
def sample_tle_lines():
    """One ISS satellite TLE (3-line)."""
    return [
        "ISS (ZARYA)",
        "1 25544U 98067A   24280.50000000  .00016717  00000+0  30359-3 0  9993",
        "2 25544  51.6424  25.4288 0006313  98.7631  29.9879 15.49512388433380",
    ]


@pytest.fixture
def sample_windows():
    """A TASA-style windows.json payload (post-parse_oasis_log.py shape)."""
    return {
        "meta": {"source": "test", "count": 2},
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


# ---------------------------------------------------------------------------
# write_ground_stations_txt
# ---------------------------------------------------------------------------

class TestGroundStations:
    def test_one_row_per_station(self, taiwan_stations, tmp_path):
        out = tmp_path / "ground_stations.txt"
        to_satgenpy.write_ground_stations_txt(taiwan_stations, out)
        assert len(out.read_text().strip().splitlines()) == 3

    def test_row_includes_id_name_lat_lon_alt_and_ecef(
        self, taiwan_stations, tmp_path
    ):
        out = tmp_path / "ground_stations.txt"
        to_satgenpy.write_ground_stations_txt(taiwan_stations, out)
        first_row = out.read_text().splitlines()[0].split(",")
        # Per Hypatia schema: id, name, lat, lon, alt, ECEF_x, ECEF_y, ECEF_z
        assert len(first_row) == 8
        assert first_row[0] == "0"
        assert first_row[1] == "HSINCHU"
        assert float(first_row[2]) == pytest.approx(24.7881)
        # ECEF coords should be ~6378km magnitude (Earth radius scale)
        x, y, z = float(first_row[5]), float(first_row[6]), float(first_row[7])
        magnitude_m = (x * x + y * y + z * z) ** 0.5
        assert 6_000_000 < magnitude_m < 6_500_000  # in metres


# ---------------------------------------------------------------------------
# write_tles_txt
# ---------------------------------------------------------------------------

class TestTles:
    def test_writes_grid_header_then_3_lines_per_satellite(
        self, sample_tle_lines, tmp_path
    ):
        out = tmp_path / "tles.txt"
        to_satgenpy.write_tles_txt(
            satellites=[("ISS-ZARYA", sample_tle_lines[1], sample_tle_lines[2])],
            n_orbits=1, n_sats_per_orbit=1, out=out,
        )
        lines = out.read_text().strip().splitlines()
        # First line is "<n_orbits> <n_sats_per_orbit>"
        assert lines[0] == "1 1"
        # Then satellite-name + line1 + line2
        # satgen.tles.read_tles requires `<constellation> <numeric_id>` shape:
        # the parser does `int(name.split()[1])`. We append a numeric index
        # whenever the caller-supplied name is a single token.
        assert lines[1] == "ISS-ZARYA 0"
        assert lines[2].startswith("1 ")
        assert lines[3].startswith("2 ")

    def test_satgen_compatible_naming_for_caller_with_space(
        self, sample_tle_lines, tmp_path
    ):
        """If the caller already provided `<name> <index>`, leave it alone."""
        out = tmp_path / "tles.txt"
        to_satgenpy.write_tles_txt(
            satellites=[("Starlink 42", sample_tle_lines[1], sample_tle_lines[2])],
            n_orbits=1, n_sats_per_orbit=1, out=out,
        )
        # Satellite name kept verbatim
        assert out.read_text().splitlines()[1] == "Starlink 42"


# ---------------------------------------------------------------------------
# write_isls_txt
# ---------------------------------------------------------------------------

class TestIsls:
    def test_each_pair_one_per_line_space_separated(self, tmp_path):
        out = tmp_path / "isls.txt"
        to_satgenpy.write_isls_txt(pairs=[(0, 1), (0, 34), (1, 2)], out=out)
        assert out.read_text() == "0 1\n0 34\n1 2\n"

    def test_no_isls_writes_empty_file(self, tmp_path):
        out = tmp_path / "isls.txt"
        to_satgenpy.write_isls_txt(pairs=[], out=out)
        assert out.read_text() == ""


# ---------------------------------------------------------------------------
# write_gsl_interfaces_info
# ---------------------------------------------------------------------------

class TestGslInterfacesInfo:
    def test_one_row_per_node_id(self, tmp_path):
        out = tmp_path / "gsl_interfaces_info.txt"
        # 2 satellites + 3 ground stations = 5 nodes
        to_satgenpy.write_gsl_interfaces_info(
            n_satellites=2, n_ground_stations=3,
            sat_iface_count=4, gs_iface_count=1,
            out=out,
        )
        lines = out.read_text().strip().splitlines()
        assert len(lines) == 5

    def test_satellites_first_then_ground_stations(self, tmp_path):
        out = tmp_path / "gsl_interfaces_info.txt"
        to_satgenpy.write_gsl_interfaces_info(
            n_satellites=2, n_ground_stations=1,
            sat_iface_count=4, gs_iface_count=1,
            out=out,
        )
        lines = out.read_text().strip().splitlines()
        # Sat ids 0..1 with 4 ifaces, then GS id 2 with 1 iface
        assert lines[0] == "0,4,1.000000"
        assert lines[1] == "1,4,1.000000"
        assert lines[2] == "2,1,1.000000"


# ---------------------------------------------------------------------------
# write_description_txt
# ---------------------------------------------------------------------------

class TestDescription:
    def test_writes_max_lengths_kv_format(self, tmp_path):
        out = tmp_path / "description.txt"
        to_satgenpy.write_description_txt(
            max_gsl_length_m=1_260_000.0,
            max_isl_length_m=5_442_958.20,
            out=out,
        )
        text = out.read_text()
        assert "max_gsl_length_m=1260000" in text
        assert "max_isl_length_m=5442958.2" in text


# ---------------------------------------------------------------------------
# write_udp_burst_schedule (TASA windows → traffic matrix)
# ---------------------------------------------------------------------------

class TestUdpBurstSchedule:
    def test_one_row_per_window(self, sample_windows, tmp_path):
        out = tmp_path / "udp_burst_schedule.csv"
        # node_id_of: lookup from (sat-or-gw name) → integer node id
        node_id_of = {"ISS-ZARYA": 0, "HSINCHU": 1, "TAIPEI": 2, "TAICHUNG": 3}
        to_satgenpy.write_udp_burst_schedule(
            windows=sample_windows["windows"],
            node_id_of=node_id_of,
            target_mbps=10.0,
            out=out,
        )
        lines = out.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_each_row_has_hypatia_schema(self, sample_windows, tmp_path):
        out = tmp_path / "udp_burst_schedule.csv"
        node_id_of = {"ISS-ZARYA": 0, "HSINCHU": 1, "TAIPEI": 2, "TAICHUNG": 3}
        to_satgenpy.write_udp_burst_schedule(
            windows=sample_windows["windows"],
            node_id_of=node_id_of,
            target_mbps=10.0,
            out=out,
        )
        first = out.read_text().splitlines()[0].split(",")
        # Schema: flow_id, src, dst, rate_mbps, start_ns, end_ns, ?, ?
        assert first[0] == "0"  # flow id
        assert first[1] == "0"  # ISS-ZARYA
        assert first[2] == "1"  # HSINCHU
        assert float(first[3]) == pytest.approx(10.0)
        # Window duration = 10:25:45 - 10:15:30 = 10 min 15 s = 615 s = 615e9 ns
        assert int(first[5]) - int(first[4]) == 615_000_000_000


# ---------------------------------------------------------------------------
# Top-level convertor
# ---------------------------------------------------------------------------

class TestWindowsToSatgenpyDir:
    def test_creates_all_required_files(
        self, sample_windows, taiwan_stations, sample_tle_lines, tmp_path,
    ):
        out_dir = tmp_path / "satgenpy_state"
        to_satgenpy.windows_to_satgenpy_dir(
            windows_data=sample_windows,
            stations=taiwan_stations,
            satellites=[(
                "ISS-ZARYA", sample_tle_lines[1], sample_tle_lines[2],
            )],
            out_dir=out_dir,
        )
        # All 5 contract files (per docs/internal/v2-feasibility.md §3.1)
        assert (out_dir / "description.txt").exists()
        assert (out_dir / "tles.txt").exists()
        assert (out_dir / "ground_stations.txt").exists()
        assert (out_dir / "isls.txt").exists()
        assert (out_dir / "gsl_interfaces_info.txt").exists()
        # And the traffic matrix
        assert (out_dir / "udp_burst_schedule.csv").exists()

    def test_node_id_assignment_is_satellites_first(
        self, sample_windows, taiwan_stations, sample_tle_lines, tmp_path,
    ):
        """Hypatia convention: satellite ids 0..N-1, ground station ids N..N+M-1."""
        out_dir = tmp_path / "satgenpy_state"
        to_satgenpy.windows_to_satgenpy_dir(
            windows_data=sample_windows,
            stations=taiwan_stations,
            satellites=[(
                "ISS-ZARYA", sample_tle_lines[1], sample_tle_lines[2],
            )],
            out_dir=out_dir,
        )
        gs_lines = (out_dir / "ground_stations.txt").read_text().splitlines()
        # First GS id should be 1 (after satellite id 0)
        assert gs_lines[0].split(",")[0] == "1"
