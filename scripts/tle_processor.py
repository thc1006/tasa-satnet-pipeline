#!/usr/bin/env python3
"""TLE (Two-Line Element) processor for satellite orbit calculations."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

try:
    from sgp4.api import jday, SGP4_ERRORS
    from sgp4.io import twoline2rv
    from sgp4.earth_gravity import wgs72
    from sgp4 import exporter
    SGP4_AVAILABLE = True
except ImportError:
    SGP4_AVAILABLE = False
    print("Warning: sgp4 not installed. TLE processing will be limited.")

import math


@dataclass
class GroundStation:
    """Ground station location."""
    name: str
    lat: float  # degrees
    lon: float  # degrees
    alt: float = 0.0  # meters


@dataclass
class PassWindow:
    """Satellite pass window over ground station."""
    start: datetime
    end: datetime
    max_elevation: float
    satellite: str
    ground_station: str


class TLEProcessor:
    """Process TLE data and compute satellite passes."""
    
    def __init__(self, tle_line1: str, tle_line2: str, satellite_name: str = ""):
        """Initialize with TLE data."""
        self.tle_line1 = tle_line1.strip()
        self.tle_line2 = tle_line2.strip()
        self.satellite_name = satellite_name or self._extract_sat_name()
        
        if SGP4_AVAILABLE:
            self.satellite = twoline2rv(self.tle_line1, self.tle_line2, wgs72)
        else:
            self.satellite = None
    
    def _extract_sat_name(self) -> str:
        """Extract satellite name from TLE."""
        return f"SAT-{self.tle_line1[2:7].strip()}"
    
    def compute_position(self, dt: datetime) -> Tuple[float, float, float]:
        """Compute satellite position at given time (ECI coordinates)."""
        if not SGP4_AVAILABLE or self.satellite is None:
            raise RuntimeError("SGP4 not available")
        
        jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        position, velocity = self.satellite.propagate(dt.year, dt.month, dt.day, 
                                                      dt.hour, dt.minute, dt.second)
        
        if self.satellite.error != 0:
            error_msg = SGP4_ERRORS.get(self.satellite.error, "Unknown error")
            raise RuntimeError(f"SGP4 error: {error_msg}")
        
        return position  # (x, y, z) in km
    
    def compute_passes(self, 
                       observer: GroundStation,
                       start_time: datetime,
                       end_time: datetime,
                       min_elevation: float = 10.0,
                       step_seconds: int = 60) -> List[PassWindow]:
        """Compute visible passes for observer."""
        if not SGP4_AVAILABLE:
            return []
        
        passes = []
        current_pass: Optional[Dict] = None
        current_time = start_time
        
        while current_time < end_time:
            elevation = self._compute_elevation(observer, current_time)
            
            if elevation >= min_elevation:
                if current_pass is None:
                    # Start of new pass
                    current_pass = {
                        'start': current_time,
                        'max_elevation': elevation,
                        'max_time': current_time
                    }
                else:
                    # Update max elevation
                    if elevation > current_pass['max_elevation']:
                        current_pass['max_elevation'] = elevation
                        current_pass['max_time'] = current_time
            else:
                if current_pass is not None:
                    # End of pass
                    passes.append(PassWindow(
                        start=current_pass['start'],
                        end=current_time,
                        max_elevation=current_pass['max_elevation'],
                        satellite=self.satellite_name,
                        ground_station=observer.name
                    ))
                    current_pass = None
            
            current_time += timedelta(seconds=step_seconds)
        
        # Handle pass at end of time window
        if current_pass is not None:
            passes.append(PassWindow(
                start=current_pass['start'],
                end=end_time,
                max_elevation=current_pass['max_elevation'],
                satellite=self.satellite_name,
                ground_station=observer.name
            ))
        
        return passes
    
    def _compute_elevation(self, observer: GroundStation, dt: datetime) -> float:
        """Compute satellite elevation angle from observer."""
        try:
            sat_pos = self.compute_position(dt)
            
            # Convert observer to ECEF
            obs_ecef = self._geodetic_to_ecef(observer.lat, observer.lon, observer.alt)
            
            # Satellite position relative to observer
            rel_x = sat_pos[0] - obs_ecef[0]
            rel_y = sat_pos[1] - obs_ecef[1]
            rel_z = sat_pos[2] - obs_ecef[2]
            
            # Convert to local horizontal coordinates
            lat_rad = math.radians(observer.lat)
            lon_rad = math.radians(observer.lon)
            
            # Simplified elevation calculation
            distance = math.sqrt(rel_x**2 + rel_y**2 + rel_z**2)
            elevation = math.degrees(math.asin(rel_z / distance)) if distance > 0 else 0
            
            return elevation
        except Exception:
            return 0.0
    
    def _geodetic_to_ecef(self, lat: float, lon: float, alt: float) -> Tuple[float, float, float]:
        """Convert geodetic coordinates to ECEF."""
        WGS84_A = 6378.137  # km
        WGS84_F = 1/298.257223563
        WGS84_B = WGS84_A * (1 - WGS84_F)
        
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        
        e2 = 1 - (WGS84_B / WGS84_A)**2
        N = WGS84_A / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
        
        x = (N + alt/1000) * math.cos(lat_rad) * math.cos(lon_rad)
        y = (N + alt/1000) * math.cos(lat_rad) * math.sin(lon_rad)
        z = (N * (1 - e2) + alt/1000) * math.sin(lat_rad)
        
        return (x, y, z)
    
    def validate_against_log(self, log_windows: List[Dict]) -> List[Dict]:
        """Cross-validate TLE-derived passes with OASIS log windows."""
        discrepancies = []
        
        for log_window in log_windows:
            if log_window.get('type') not in ['cmd', 'xband']:
                continue
            
            log_start = datetime.fromisoformat(log_window['start'].replace('Z', '+00:00'))
            log_end = datetime.fromisoformat(log_window['end'].replace('Z', '+00:00'))
            
            # Check if any TLE pass overlaps with this log window
            # (This would require observer location from log)
            # For now, just record the window
            discrepancies.append({
                'type': 'validation_needed',
                'log_window': log_window,
                'message': 'Observer location required for validation'
            })
        
        return discrepancies


def load_tle_file(tle_path: Path) -> List[TLEProcessor]:
    """Load TLE file and create processors."""
    processors = []
    
    with tle_path.open('r') as f:
        lines = [l.strip() for l in f if l.strip()]
    
    # TLE format: name, line1, line2
    for i in range(0, len(lines), 3):
        if i + 2 >= len(lines):
            break
        
        name = lines[i]
        line1 = lines[i + 1]
        line2 = lines[i + 2]
        
        if line1.startswith('1 ') and line2.startswith('2 '):
            processors.append(TLEProcessor(line1, line2, name))
    
    return processors


def main():
    """CLI interface for TLE processing."""
    import argparse
    
    ap = argparse.ArgumentParser(description="Process TLE and compute satellite passes")
    ap.add_argument("tle", type=Path, help="TLE file path")
    ap.add_argument("--observer-lat", type=float, required=True, help="Observer latitude")
    ap.add_argument("--observer-lon", type=float, required=True, help="Observer longitude")
    ap.add_argument("--observer-name", default="OBSERVER", help="Observer name")
    ap.add_argument("--start", help="Start time (ISO 8601)")
    ap.add_argument("--end", help="End time (ISO 8601)")
    ap.add_argument("--min-elevation", type=float, default=10.0, help="Minimum elevation (degrees)")
    ap.add_argument("-o", "--output", type=Path, default=Path("data/tle_passes.json"))
    
    args = ap.parse_args()
    
    if not SGP4_AVAILABLE:
        print("Error: sgp4 library required. Install with: pip install sgp4")
        return 1
    
    # Load TLE
    processors = load_tle_file(args.tle)
    print(f"Loaded {len(processors)} satellites")
    
    # Setup observer
    observer = GroundStation(args.observer_name, args.observer_lat, args.observer_lon)
    
    # Time range
    start_time = datetime.fromisoformat(args.start) if args.start else datetime.now(timezone.utc)
    end_time = datetime.fromisoformat(args.end) if args.end else start_time + timedelta(days=1)
    
    # Compute passes
    all_passes = []
    for proc in processors:
        passes = proc.compute_passes(observer, start_time, end_time, args.min_elevation)
        all_passes.extend(passes)
        print(f"{proc.satellite_name}: {len(passes)} passes")
    
    # Output
    output_data = {
        'meta': {
            'observer': observer.name,
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'count': len(all_passes)
        },
        'passes': [
            {
                'satellite': p.satellite,
                'ground_station': p.ground_station,
                'start': p.start.isoformat(),
                'end': p.end.isoformat(),
                'max_elevation': p.max_elevation,
                'duration_sec': int((p.end - p.start).total_seconds())
            }
            for p in all_passes
        ]
    }
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output_data, indent=2))
    print(f"Output written to: {args.output}")
    
    return 0


if __name__ == "__main__":
    exit(main())
