# Hypatia sample fixtures

Minimal head-truncated samples extracted from `hypatia_paper_temp_data.tar.gz`
(SHA-256 `18d761a28706723b57772e0636fbc40b7d57161f4c54069eede0c8ae740cbe2d`,
released 2022-10-10 at https://github.com/snkas/hypatia/releases/tag/v1).

These exist so adapter tests can verify schema parsing without needing the
500 MB upstream archive. They are *not* runnable scenarios — fstate files
have been head-truncated to ~20 rows from the original ~125,500.

## Files

`run_minimal/` — output of one ns-3 packet-level run (Kuiper-630, 10 Mbps × 10 s UDP)
- `config_ns3.properties` — full run config (unmodified)
- `udp_burst_schedule.csv` — 5-row head of the 100-flow schedule
- `logs_ns3/udp_bursts_outgoing.csv` — 5-flow head (sender-side stats)
- `logs_ns3/udp_bursts_incoming.csv` — 5-flow head (receiver-side stats; note
  achieved Mbps is much lower than outgoing — packet loss in transit is real)
- `logs_ns3/isl_utilization.csv` — 100-row head (one row per ISL per time bucket)
- `logs_ns3/timing_results.{csv,txt}` — wall-clock breakdown (unmodified)
- `logs_ns3/finished.txt` — sentinel file (unmodified)

`satgenpy_state_minimal/` — input state ns-3 reads from satgenpy
- `description.txt`, `ground_stations.txt` (head 10), `isls.txt` (head 5),
  `tles.txt` (head: count header + first 2 satellites), `gsl_interfaces_info.txt` (head 10)
- `dynamic_state_100ms_for_2s/` — 2 fstate snapshots, 2 gsl_if_bandwidth snapshots,
  all head-truncated to ~20 rows; "for_2s" reflects only that we vendor 2 snapshots,
  not that the simulation duration is 2 s.

## Refresh procedure

If schema upstream changes:

```
cd ~/hypatia-sandbox/hypatia/paper
tar xzf hypatia_paper_temp_data.tar.gz <selected paths>
# then rerun the head -N truncations from this commit's git log
```

Do not commit the full 500 MB archive — the head-truncated samples are
sufficient for adapter contract tests.
