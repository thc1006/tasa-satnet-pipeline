#!/usr/bin/env python3
"""Compute metrics and KPIs from NS-3 scenario."""
from __future__ import annotations
import json
import argparse
import csv
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import math
import sys

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.constants import (
    PhysicalConstants,
    LatencyConstants,
    NetworkConstants,
    PercentileConstants,
    ConstellationConstants,
)
from config.schemas import validate_scenario, validate_metrics, ValidationError


class MetricsCalculator:
    """Calculate network performance metrics."""

    def __init__(self, scenario: Dict, skip_validation: bool = False,
                 enable_constellation_metrics: bool = True):
        """Initialize with scenario data."""
        # Validate input scenario
        if not skip_validation:
            try:
                validate_scenario(scenario)
            except ValidationError as e:
                raise ValueError(f"Invalid scenario data: {e}") from e

        self.scenario = scenario
        self.mode = scenario.get('metadata', {}).get('mode', 'transparent')
        self.metrics: List[Dict] = []
        self.enable_constellation_metrics = enable_constellation_metrics

        # Per-constellation metrics tracking
        self.constellation_metrics: Dict[str, List[Dict]] = {}
        self.constellations = scenario.get('metadata', {}).get('constellations', [])
    
    def compute_all_metrics(self) -> List[Dict]:
        """Compute all metrics for scenario."""
        events = self.scenario.get('events', [])
        parameters = self.scenario.get('parameters', {})

        # Group events into sessions (link_up to link_down pairs)
        sessions = self._extract_sessions(events)

        for session in sessions:
            metrics = self._compute_session_metrics(session, parameters)
            self.metrics.append(metrics)

            # Track per-constellation metrics if enabled
            if self.enable_constellation_metrics:
                constellation = session.get('constellation', 'Unknown')
                if constellation not in self.constellation_metrics:
                    self.constellation_metrics[constellation] = []
                self.constellation_metrics[constellation].append(metrics)

        return self.metrics
    
    def _extract_sessions(self, events: List[Dict]) -> List[Dict]:
        """Extract communication sessions from events."""
        sessions = []
        active_links = {}

        for event in events:
            link_key = (event['source'], event['target'])

            if event['type'] == 'link_up':
                active_links[link_key] = {
                    'start': event['time'],
                    'source': event['source'],
                    'target': event['target'],
                    'window_type': event.get('window_type', 'unknown'),
                    'constellation': event.get('constellation', 'Unknown'),
                    'frequency_band': event.get('frequency_band', 'Unknown'),
                    'priority': event.get('priority', 'low')
                }
            elif event['type'] == 'link_down':
                if link_key in active_links:
                    session = active_links[link_key]
                    session['end'] = event['time']
                    sessions.append(session)
                    del active_links[link_key]

        return sessions
    
    def _compute_session_metrics(self, session: Dict, parameters: Dict) -> Dict:
        """Compute metrics for a single session."""
        # Parse times
        start = datetime.fromisoformat(session['start'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(session['end'].replace('Z', '+00:00'))
        duration_sec = (end - start).total_seconds()

        # Get constellation info
        constellation = session.get('constellation', 'Unknown')

        # Latency components with constellation-specific adjustments
        propagation_delay = self._compute_propagation_delay()
        processing_delay = parameters.get('processing_delay_ms', 0.0)

        # Add constellation-specific processing delay
        if self.enable_constellation_metrics and constellation != 'Unknown':
            constellation_delay = ConstellationConstants.CONSTELLATION_PROCESSING_DELAYS.get(
                constellation, 0.0
            )
            processing_delay += constellation_delay

        queuing_delay = self._estimate_queuing_delay(duration_sec)
        transmission_delay = self._compute_transmission_delay(parameters)

        total_latency = propagation_delay + processing_delay + queuing_delay + transmission_delay

        # Throughput
        data_rate_mbps = parameters.get('data_rate_mbps', NetworkConstants.DEFAULT_LINK_BANDWIDTH_MBPS)
        throughput_mbps = self._compute_throughput(duration_sec, data_rate_mbps)

        metrics = {
            'source': session['source'],
            'target': session['target'],
            'window_type': session['window_type'],
            'start': session['start'],
            'end': session['end'],
            'duration_sec': duration_sec,
            'latency': {
                'propagation_ms': round(propagation_delay, 2),
                'processing_ms': round(processing_delay, 2),
                'queuing_ms': round(queuing_delay, 2),
                'transmission_ms': round(transmission_delay, 2),
                'total_ms': round(total_latency, 2),
                'rtt_ms': round(total_latency * 2, 2)  # Round-trip time
            },
            'throughput': {
                'average_mbps': round(throughput_mbps, 2),
                'peak_mbps': data_rate_mbps,
                'utilization_percent': round(throughput_mbps / data_rate_mbps * 100, 2)
            },
            'mode': self.mode
        }

        # Add constellation metadata if enabled
        if self.enable_constellation_metrics:
            metrics.update({
                'constellation': constellation,
                'frequency_band': session.get('frequency_band', 'Unknown'),
                'priority': session.get('priority', 'low')
            })

        return metrics
    
    def _compute_propagation_delay(self, altitude_km: float = None) -> float:
        """Compute propagation delay for satellite link."""
        if altitude_km is None:
            altitude_km = PhysicalConstants.DEFAULT_ALTITUDE_KM
        # Simplified: distance to satellite and back
        distance_km = altitude_km * 2  # Up and down
        delay_ms = (distance_km / PhysicalConstants.SPEED_OF_LIGHT_KM_S) * 1000
        return delay_ms
    
    def _estimate_queuing_delay(self, duration_sec: float) -> float:
        """Estimate queuing delay based on traffic patterns."""
        # Simplified model: assume higher queuing during longer sessions
        if duration_sec < LatencyConstants.LOW_TRAFFIC_THRESHOLD_SEC:
            return LatencyConstants.MIN_QUEUING_DELAY_MS  # Low traffic
        elif duration_sec < LatencyConstants.MEDIUM_TRAFFIC_THRESHOLD_SEC:
            return LatencyConstants.MEDIUM_QUEUING_DELAY_MS  # Medium traffic
        else:
            return LatencyConstants.MAX_QUEUING_DELAY_MS  # High traffic
    
    def _compute_transmission_delay(self, parameters: Dict) -> float:
        """Compute transmission delay for packet."""
        packet_size_kb = NetworkConstants.PACKET_SIZE_KB
        data_rate_mbps = parameters.get('data_rate_mbps', NetworkConstants.DEFAULT_LINK_BANDWIDTH_MBPS)
        delay_ms = (packet_size_kb * 8) / (data_rate_mbps * 1000) * 1000
        return delay_ms
    
    def _compute_throughput(self, duration_sec: float, data_rate_mbps: float) -> float:
        """Compute average throughput."""
        # Simplified: assume default utilization during active session
        return data_rate_mbps * (NetworkConstants.DEFAULT_UTILIZATION_PERCENT / 100.0)
    
    def generate_summary(self) -> Dict:
        """Generate summary statistics."""
        if not self.metrics:
            return {}

        latencies = [m['latency']['total_ms'] for m in self.metrics]
        throughputs = [m['throughput']['average_mbps'] for m in self.metrics]

        summary = {
            'total_sessions': len(self.metrics),
            'mode': self.mode,
            'latency': {
                'mean_ms': round(sum(latencies) / len(latencies), 2),
                'min_ms': round(min(latencies), 2),
                'max_ms': round(max(latencies), 2),
                'p95_ms': round(self._percentile(latencies, PercentileConstants.P95), 2)
            },
            'throughput': {
                'mean_mbps': round(sum(throughputs) / len(throughputs), 2),
                'min_mbps': round(min(throughputs), 2),
                'max_mbps': round(max(throughputs), 2)
            },
            'total_duration_sec': sum(m['duration_sec'] for m in self.metrics)
        }

        # Add per-constellation statistics if enabled
        if self.enable_constellation_metrics and self.constellation_metrics:
            summary['constellation_stats'] = self._generate_constellation_stats()

        return summary

    def _generate_constellation_stats(self) -> Dict:
        """Generate per-constellation statistics."""
        stats = {}

        for constellation, metrics_list in self.constellation_metrics.items():
            if not metrics_list:
                continue

            latencies = [m['latency']['total_ms'] for m in metrics_list]
            throughputs = [m['throughput']['average_mbps'] for m in metrics_list]

            stats[constellation] = {
                'sessions': len(metrics_list),
                'latency': {
                    'mean_ms': round(sum(latencies) / len(latencies), 2),
                    'min_ms': round(min(latencies), 2),
                    'max_ms': round(max(latencies), 2),
                    'p95_ms': round(self._percentile(latencies, PercentileConstants.P95), 2)
                },
                'throughput': {
                    'mean_mbps': round(sum(throughputs) / len(throughputs), 2),
                    'min_mbps': round(min(throughputs), 2),
                    'max_mbps': round(max(throughputs), 2)
                },
                'total_duration_sec': sum(m['duration_sec'] for m in metrics_list)
            }

        return stats
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Compute percentile of data."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def export_csv(self, output_path: Path):
        """Export metrics to CSV."""
        if not self.metrics:
            return

        with output_path.open('w', newline='') as f:
            # Add constellation fields if enabled
            fieldnames = [
                'source', 'target', 'window_type', 'start', 'end', 'duration_sec',
                'latency_total_ms', 'latency_rtt_ms', 'throughput_mbps', 'utilization_percent', 'mode'
            ]

            if self.enable_constellation_metrics:
                fieldnames.extend(['constellation', 'frequency_band', 'priority'])

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for m in self.metrics:
                row = {
                    'source': m['source'],
                    'target': m['target'],
                    'window_type': m['window_type'],
                    'start': m['start'],
                    'end': m['end'],
                    'duration_sec': m['duration_sec'],
                    'latency_total_ms': m['latency']['total_ms'],
                    'latency_rtt_ms': m['latency']['rtt_ms'],
                    'throughput_mbps': m['throughput']['average_mbps'],
                    'utilization_percent': m['throughput']['utilization_percent'],
                    'mode': m['mode']
                }

                # Add constellation fields if enabled
                if self.enable_constellation_metrics:
                    row.update({
                        'constellation': m.get('constellation', 'Unknown'),
                        'frequency_band': m.get('frequency_band', 'Unknown'),
                        'priority': m.get('priority', 'low')
                    })

                writer.writerow(row)


def main():
    """CLI interface for metrics calculation."""
    ap = argparse.ArgumentParser(description="Compute metrics from NS-3 scenario")
    ap.add_argument("scenario", type=Path, help="Scenario JSON file")
    ap.add_argument("-o", "--output", type=Path, default=Path("reports/metrics.csv"))
    ap.add_argument("--summary", type=Path, default=Path("reports/summary.json"))
    ap.add_argument("--skip-validation", action="store_true", help="Skip schema validation (not recommended)")
    ap.add_argument("--visualize", action="store_true", help="Generate visualization charts and maps")
    ap.add_argument("--viz-output-dir", type=Path, default=Path("reports/viz"),
                   help="Output directory for visualizations (default: reports/viz/)")
    ap.add_argument(
        "--use-hypatia",
        type=Path,
        metavar="RUN_DIR",
        default=None,
        help="Path to a Hypatia ns-3 run directory (containing logs_ns3/). "
             "When set, derive metrics from real packet-level outputs instead "
             "of the physics formula. See docs/internal/v2-feasibility.md.",
    )

    args = ap.parse_args()

    # v2: --use-hypatia derives metrics from a real ns-3 run directory.
    # The scenario JSON is still consumed (mode/topology hints), but
    # MetricsCalculator's physics formulas are not used.
    if args.use_hypatia is not None:
        if not args.use_hypatia.exists():
            print(
                f"ERROR: --use-hypatia path does not exist: {args.use_hypatia}",
                file=sys.stderr,
            )
            return 1
        try:
            from adapters import from_hypatia
        except ImportError:
            from scripts.adapters import from_hypatia
        try:
            hypatia_metrics = from_hypatia.run_dir_to_tasa_metrics(args.use_hypatia)
        except from_hypatia.IncompleteRunError as e:
            print(f"ERROR: hypatia run incomplete: {e}", file=sys.stderr)
            return 1
        # Materialize a CSV with throughput_source column flagged 'hypatia'.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "source", "target", "duration_sec",
                    "throughput_mbps", "throughput_peak_mbps",
                    "throughput_source", "delivery_ratio",
                    "packets_sent", "bytes_sent",
                ],
            )
            writer.writeheader()
            for m in hypatia_metrics:
                writer.writerow({
                    "source": m["source"],
                    "target": m["target"],
                    "duration_sec": m["duration_sec"],
                    "throughput_mbps": m["throughput"]["average_mbps"],
                    "throughput_peak_mbps": m["throughput"]["peak_mbps"],
                    "throughput_source": m["throughput"]["source"],
                    "delivery_ratio": m["throughput"].get("delivery_ratio"),
                    "packets_sent": m["packets_sent"],
                    "bytes_sent": m["bytes_sent"],
                })
        # Light-weight summary; deliberately skips physics-formula latency.
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps({
            "metrics_source": "hypatia",
            "run_dir": str(args.use_hypatia),
            "flow_count": len(hypatia_metrics),
        }, indent=2))
        print(json.dumps({
            "metrics_computed": len(hypatia_metrics),
            "metrics_source": "hypatia",
            "output_csv": str(args.output),
            "output_summary": str(args.summary),
        }, indent=2))
        return 0

    # Load scenario
    with args.scenario.open() as f:
        scenario = json.load(f)

    # Compute metrics
    try:
        calculator = MetricsCalculator(scenario, skip_validation=args.skip_validation)
        metrics = calculator.compute_all_metrics()
        summary = calculator.generate_summary()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Validate output metrics summary
    if not args.skip_validation and summary:
        try:
            validate_metrics(summary)
            print(f"✓ Metrics validation passed", file=sys.stderr)
        except ValidationError as e:
            print(f"ERROR: Generated metrics validation failed: {e}", file=sys.stderr)
            return 1

    # Export
    args.output.parent.mkdir(parents=True, exist_ok=True)
    calculator.export_csv(args.output)

    args.summary.write_text(json.dumps(summary, indent=2))

    # Generate visualizations if requested
    viz_results = None
    if args.visualize:
        try:
            # Try importing from same directory first
            try:
                from metrics_visualization import MetricsVisualizer
            except ImportError:
                # If that fails, try with scripts prefix
                from scripts.metrics_visualization import MetricsVisualizer

            print("\n" + "="*60, file=sys.stderr)
            print("Generating visualizations...", file=sys.stderr)
            print("="*60, file=sys.stderr)

            visualizer = MetricsVisualizer(scenario, metrics)
            viz_results = visualizer.generate_all(args.viz_output_dir)

            print("\n" + "="*60, file=sys.stderr)
            print(f"✓ Visualizations saved to: {args.viz_output_dir}", file=sys.stderr)
            print("="*60 + "\n", file=sys.stderr)

        except ImportError as e:
            print(f"WARNING: Could not import metrics_visualization: {e}", file=sys.stderr)
            print("Install visualization dependencies: pip install matplotlib folium", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: Visualization generation failed: {e}", file=sys.stderr)

    # Build output response
    output_data = {
        'metrics_computed': len(metrics),
        'mode': summary.get('mode'),
        'mean_latency_ms': summary.get('latency', {}).get('mean_ms'),
        'mean_throughput_mbps': summary.get('throughput', {}).get('mean_mbps'),
        'output_csv': str(args.output),
        'output_summary': str(args.summary)
    }

    if viz_results:
        output_data['visualizations'] = {
            'enabled': True,
            'output_dir': str(args.viz_output_dir),
            'manifest': str(args.viz_output_dir / 'visualization_manifest.json'),
            'generated': list(viz_results.get('visualizations', {}).keys())
        }

    print(json.dumps(output_data, indent=2))

    return 0


if __name__ == "__main__":
    exit(main())
