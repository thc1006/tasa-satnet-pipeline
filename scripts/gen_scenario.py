#!/usr/bin/env python3
"""Generate NS-3/SNS3 scenario from parsed OASIS windows."""
from __future__ import annotations
import json
import argparse
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime, timezone
import sys

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.constants import (
    LatencyConstants,
    NetworkConstants,
    PhysicalConstants,
    ValidationConstants,
    ConstellationConstants,
)
from config.schemas import validate_windows, validate_scenario, ValidationError

# Try to import constellation manager for multi-constellation support
try:
    from scripts.constellation_manager import ConstellationManager
    CONSTELLATION_MANAGER_AVAILABLE = True
except ImportError:
    CONSTELLATION_MANAGER_AVAILABLE = False


class ScenarioGenerator:
    """Generate simulation scenario from parsed windows."""

    def __init__(self, mode: str = "transparent", enable_constellation_support: bool = True):
        """Initialize generator with relay mode."""
        self.mode = mode  # transparent or regenerative
        self.satellites: Set[str] = set()
        self.gateways: Set[str] = set()
        self.links: List[Dict] = []
        self.events: List[Dict] = []
        self.enable_constellation_support = enable_constellation_support
        self.constellation_manager = None

        # Multi-constellation tracking
        self.constellations: Dict[str, Set[str]] = {}  # constellation -> satellites
        self.satellite_metadata: Dict[str, Dict] = {}  # sat -> metadata
    
    def generate(self, windows_data: Dict, skip_validation: bool = False,
                 constellation_config: Optional[Path] = None) -> Dict:
        """Generate scenario from windows JSON."""
        # Validate input windows data
        if not skip_validation:
            try:
                validate_windows(windows_data)
            except ValidationError as e:
                raise ValueError(f"Invalid windows data: {e}") from e

        windows = windows_data.get('windows', [])

        # Extract nodes and constellation metadata
        for window in windows:
            # Legacy format support
            sat = window.get('satellite', window.get('sat'))
            gw = window.get('ground_station', window.get('gw'))

            if sat and gw:
                self.satellites.add(sat)
                self.gateways.add(gw)

                # Extract constellation metadata if available
                if self.enable_constellation_support:
                    constellation = window.get('constellation', 'Unknown')
                    if constellation not in self.constellations:
                        self.constellations[constellation] = set()
                    self.constellations[constellation].add(sat)

                    # Store satellite metadata
                    if sat not in self.satellite_metadata:
                        self.satellite_metadata[sat] = {
                            'constellation': constellation,
                            'frequency_band': window.get('frequency_band', 'Unknown'),
                            'priority': window.get('priority', 'low'),
                            'processing_delay_ms': ConstellationConstants.CONSTELLATION_PROCESSING_DELAYS.get(
                                constellation, 10.0
                            )
                        }

        # Load constellation configuration if provided
        if constellation_config and constellation_config.exists():
            self._load_constellation_config(constellation_config)

        # Generate topology
        topology = self._build_topology()

        # Generate events
        self._generate_events(windows)

        # Build scenario metadata
        metadata = {
            'name': f"OASIS Scenario - {self.mode}",
            'mode': self.mode,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source': windows_data.get('meta', {}).get('source', 'unknown')
        }

        # Add constellation metadata if enabled
        if self.enable_constellation_support and self.constellations:
            metadata['constellations'] = list(self.constellations.keys())
            metadata['constellation_count'] = len(self.constellations)
            metadata['multi_constellation'] = len(self.constellations) > 1

        # Build scenario
        scenario = {
            'metadata': metadata,
            'topology': topology,
            'events': self.events,
            'parameters': self._get_parameters()
        }

        return scenario

    def _load_constellation_config(self, config_path: Path):
        """Load constellation configuration from JSON file."""
        try:
            with config_path.open() as f:
                config = json.load(f)

            # Initialize constellation manager if available
            if CONSTELLATION_MANAGER_AVAILABLE:
                self.constellation_manager = ConstellationManager()

                # Load constellation metadata
                for constellation, metadata in config.get('constellations', {}).items():
                    satellites = metadata.get('satellites', [])
                    self.constellation_manager.add_constellation(
                        name=constellation,
                        satellites=satellites,
                        frequency_band=metadata.get('frequency_band'),
                        priority=metadata.get('priority'),
                        min_elevation=metadata.get('min_elevation')
                    )
        except Exception as e:
            print(f"Warning: Failed to load constellation config: {e}", file=sys.stderr)
    
    def _build_topology(self) -> Dict:
        """Build network topology."""
        satellites = []
        for sat in sorted(self.satellites):
            sat_info = {
                'id': sat,
                'type': 'satellite',
                'orbit': 'LEO',  # Default
                'altitude_km': PhysicalConstants.DEFAULT_ALTITUDE_KM,
            }

            # Add constellation metadata if available
            if sat in self.satellite_metadata:
                metadata = self.satellite_metadata[sat]
                sat_info.update({
                    'constellation': metadata.get('constellation', 'Unknown'),
                    'frequency_band': metadata.get('frequency_band', 'Unknown'),
                    'priority': metadata.get('priority', 'low'),
                    'processing_delay_ms': metadata.get('processing_delay_ms', 10.0)
                })

            satellites.append(sat_info)

        gateways = [
            {
                'id': gw,
                'type': 'gateway',
                'location': gw,  # Use name as location
                'capacity_mbps': NetworkConstants.DEFAULT_BANDWIDTH_MBPS
            }
            for gw in sorted(self.gateways)
        ]

        # Generate links between all sats and gateways
        links = []
        for sat in self.satellites:
            metadata = self.satellite_metadata.get(sat, {})
            constellation = metadata.get('constellation', 'Unknown')

            for gw in self.gateways:
                link_info = {
                    'source': sat,
                    'target': gw,
                    'type': 'sat-ground',
                    'bandwidth_mbps': NetworkConstants.DEFAULT_LINK_BANDWIDTH_MBPS,
                    'latency_ms': self._compute_base_latency(constellation)
                }

                # Add constellation-specific link metadata
                if metadata:
                    link_info.update({
                        'constellation': constellation,
                        'frequency_band': metadata.get('frequency_band', 'Unknown'),
                        'priority': metadata.get('priority', 'low')
                    })

                links.append(link_info)

        topology = {
            'satellites': satellites,
            'gateways': gateways,
            'links': links
        }

        # Add constellation summary if available
        if self.constellations:
            topology['constellation_summary'] = {
                constellation: len(sats)
                for constellation, sats in self.constellations.items()
            }

        return topology
    
    def _generate_events(self, windows: List[Dict]):
        """Generate timed events from windows."""
        for window in windows:
            start_time = datetime.fromisoformat(window['start'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(window['end'].replace('Z', '+00:00'))

            # Support both legacy and new window formats
            sat = window.get('satellite', window.get('sat'))
            gw = window.get('ground_station', window.get('gw'))

            # Base event info
            event_base = {
                'source': sat,
                'target': gw,
                'window_type': window.get('type', 'unknown')
            }

            # Add constellation metadata if available
            if self.enable_constellation_support:
                event_base.update({
                    'constellation': window.get('constellation', 'Unknown'),
                    'frequency_band': window.get('frequency_band', 'Unknown'),
                    'priority': window.get('priority', 'low')
                })

            # Link up event
            self.events.append({
                'time': start_time.isoformat(),
                'type': 'link_up',
                **event_base
            })

            # Link down event
            self.events.append({
                'time': end_time.isoformat(),
                'type': 'link_down',
                **event_base
            })

        # Sort events by time
        self.events.sort(key=lambda e: e['time'])
    
    def _compute_base_latency(self, constellation: str = 'Unknown') -> float:
        """Compute base propagation latency with constellation-specific adjustments."""
        # Base processing delay
        if self.mode == 'transparent':
            base_latency = LatencyConstants.TRANSPARENT_PROCESSING_MS
        else:  # regenerative
            base_latency = LatencyConstants.REGENERATIVE_PROCESSING_MS

        # Add constellation-specific processing if enabled
        if self.enable_constellation_support and constellation != 'Unknown':
            constellation_delay = ConstellationConstants.CONSTELLATION_PROCESSING_DELAYS.get(
                constellation, 0.0
            )
            base_latency += constellation_delay

        return base_latency
    
    def _get_parameters(self) -> Dict:
        """Get simulation parameters."""
        return {
            'relay_mode': self.mode,
            'propagation_model': 'free_space',
            'data_rate_mbps': NetworkConstants.DEFAULT_LINK_BANDWIDTH_MBPS,
            'simulation_duration_sec': ValidationConstants.DEFAULT_SIMULATION_DURATION_SEC,
            'processing_delay_ms': LatencyConstants.TRANSPARENT_PROCESSING_MS if self.mode == 'regenerative' else 0.0,
            'queuing_model': 'fifo',
            'buffer_size_mb': NetworkConstants.DEFAULT_BUFFER_SIZE_MB
        }
    
    def export_ns3(self, scenario: Dict) -> str:
        """Export as NS-3 Python script."""
        script = f"""#!/usr/bin/env python3
# NS-3 Scenario: {scenario['metadata']['name']}
# Generated: {scenario['metadata']['generated_at']}
# Mode: {scenario['metadata']['mode']}

import ns.core
import ns.network
import ns.point_to_point
import ns.applications

# Create nodes
satellites = ns.network.NodeContainer()
satellites.Create({len(scenario['topology']['satellites'])})

gateways = ns.network.NodeContainer()
gateways.Create({len(scenario['topology']['gateways'])})

# Configure links
p2p = ns.point_to_point.PointToPointHelper()
p2p.SetDeviceAttribute("DataRate", ns.core.StringValue("{scenario['parameters']['data_rate_mbps']}Mbps"))
p2p.SetChannelAttribute("Delay", ns.core.StringValue("{scenario['parameters']['propagation_model']}"))

# Install devices
devices = ns.network.NetDeviceContainer()
for sat_idx in range({len(scenario['topology']['satellites'])}):
    for gw_idx in range({len(scenario['topology']['gateways'])}):
        sat_node = satellites.Get(sat_idx)
        gw_node = gateways.Get(gw_idx)
        device = p2p.Install(sat_node, gw_node)
        devices.Add(device)

# Schedule events
"""
        
        for event in scenario['events']:
            script += f"""
ns.core.Simulator.Schedule(
    ns.core.Time("{event['time']}"),
    lambda: handle_event("{event['type']}", "{event['source']}", "{event['target']}")
)
"""
        
        script += """
# Run simulation
ns.core.Simulator.Stop(ns.core.Seconds({}))
ns.core.Simulator.Run()
ns.core.Simulator.Destroy()
""".format(scenario['parameters']['simulation_duration_sec'])
        
        return script


def main():
    """CLI interface for scenario generation."""
    ap = argparse.ArgumentParser(description="Generate NS-3 scenario from OASIS windows")
    ap.add_argument("windows", type=Path, help="Parsed windows JSON")
    ap.add_argument("-o", "--output", type=Path, default=Path("config/ns3_scenario.json"))
    ap.add_argument("--mode", choices=['transparent', 'regenerative'], default='transparent')
    ap.add_argument("--format", choices=['json', 'ns3'], default='json')
    ap.add_argument("--skip-validation", action="store_true", help="Skip schema validation (not recommended)")
    ap.add_argument("--constellation-config", type=Path, default=None,
                    help="Multi-constellation configuration JSON")
    ap.add_argument("--disable-constellation-support", action="store_true",
                    help="Disable multi-constellation support")

    args = ap.parse_args()

    # Load windows
    with args.windows.open() as f:
        windows_data = json.load(f)

    # Generate scenario
    generator = ScenarioGenerator(
        mode=args.mode,
        enable_constellation_support=not args.disable_constellation_support
    )
    try:
        scenario = generator.generate(
            windows_data,
            skip_validation=args.skip_validation,
            constellation_config=args.constellation_config
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Validate output scenario
    if not args.skip_validation:
        try:
            validate_scenario(scenario)
            print(f"✓ Scenario validation passed", file=sys.stderr)
        except ValidationError as e:
            print(f"ERROR: Generated scenario validation failed: {e}", file=sys.stderr)
            return 1

    # Output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.format == 'json':
        args.output.write_text(json.dumps(scenario, indent=2))
    else:  # ns3
        script = generator.export_ns3(scenario)
        args.output.write_text(script)

    print(json.dumps({
        'satellites': len(scenario['topology']['satellites']),
        'gateways': len(scenario['topology']['gateways']),
        'links': len(scenario['topology']['links']),
        'events': len(scenario['events']),
        'mode': scenario['metadata']['mode'],
        'output': str(args.output)
    }, indent=2))

    return 0


if __name__ == "__main__":
    exit(main())
