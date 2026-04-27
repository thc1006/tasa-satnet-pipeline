#!/usr/bin/env bash
# Run a real Hypatia ns-3 simulation in tasa-hypatia-ns3:dev and capture the
# output directory to a host path.
#
# Usage:
#     bash docker/run-hypatia-sim.sh /tmp/hypatia-real-run
#
# This is the hello-world v2 ship procedure. The captured directory is what
# `scripts/metrics.py --use-hypatia <dir>` consumes. The procedure was
# discovered while shipping v2 — see git log for the back-and-forth.
#
# Steps performed inside the image:
#   1. integration_tests/test_manila_dalian_over_kuiper/step_1+2 — generate
#      Kuiper-630 reduced satellite network state
#   2. Construct a UDP variant of the smallest run by overriding config_ns3
#      and writing a 1-flow udp_burst_schedule.csv from node 17 → node 18
#   3. Invoke the built main_satnet binary directly via waf (skipping
#      step_3_run.py because it requires `screen` which the base image lacks)
#   4. Copy the resulting run directory (config + logs_ns3/) to $1 on the host
set -e

OUT="${1:?usage: $0 <output_dir_on_host>}"
mkdir -p "${OUT}"

docker run --rm -v "${OUT}:/host_out" tasa-hypatia-ns3:dev bash -c '
  set -e
  cd /opt/hypatia/integration_tests/test_manila_dalian_over_kuiper
  python3 step_1_generate_satellite_networks_state.py 2>&1 | tail -2
  python3 step_2_generate_runs.py 2>&1 | tail -2
  SRC=temp/runs/kuiper_630_isls_sat_one_17_to_18_with_TcpNewReno_at_10_Mbps
  UDP=temp/runs/udp_variant_17_to_18
  rm -rf "${UDP}"; cp -r "${SRC}" "${UDP}"
  rm -rf "${UDP}/logs_ns3" && mkdir -p "${UDP}/logs_ns3"
  rm -f "${UDP}/schedule.csv"
  echo "0,17,18,10.0,0,200000000000,," > "${UDP}/udp_burst_schedule.csv"
  python3 - <<PY
import re
p = "${UDP}/config_ns3.properties"
s = open(p).read()
s = re.sub(r"^enable_tcp_flow_scheduler=.*$", "enable_tcp_flow_scheduler=false", s, flags=re.M)
s = re.sub(r"^tcp_flow_schedule_filename=.*$", "", s, flags=re.M)
s = re.sub(r"^tcp_flow_enable_logging_for_tcp_flow_ids=.*$", "", s, flags=re.M)
s += "\nenable_udp_burst_scheduler=true\nudp_burst_schedule_filename=\"udp_burst_schedule.csv\"\n"
open(p, "w").write(s)
PY
  cd /opt/hypatia/ns3-sat-sim/simulator
  ./waf --run="main_satnet --run_dir=../../integration_tests/test_manila_dalian_over_kuiper/${UDP}" 2>&1 | tail -8
  cp -r "/opt/hypatia/integration_tests/test_manila_dalian_over_kuiper/${UDP}" /host_out/
'

echo
echo "Run directory captured at: ${OUT}/udp_variant_17_to_18"
echo "Now feed it into the v2 metrics flag:"
echo "  python scripts/metrics.py <scenario.json> --use-hypatia ${OUT}/udp_variant_17_to_18 -o reports/v2_metrics.csv --skip-validation"
