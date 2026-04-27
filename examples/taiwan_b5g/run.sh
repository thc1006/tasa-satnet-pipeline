#!/usr/bin/env bash
# Taiwan B5G LEO — Stage 2 example driver
#
# End-to-end run using the v1 + v2 pipeline against the synthetic 1A pathfinder
# constellation defined in taiwan_b5g.yaml. No Docker required for this script.
#
# Outputs land in ./outputs/.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
OUT="${HERE}/outputs"
mkdir -p "${OUT}"

# Materialize a TLE file from the YAML (no PyYAML to keep deps small — use sed).
TLE_FILE="${OUT}/taiwan_b5g.tle"
{
  echo "TASA-B5G-1A-01"
  echo "1 99001U 27001A   27152.50000000  .00000000  00000-0  00000+0 0    01"
  echo "2 99001  47.0000   0.0000 0001000   0.0000   0.0000 14.95000000    02"
  echo "TASA-B5G-1A-02"
  echo "1 99002U 27001B   27152.50000000  .00000000  00000-0  00000+0 0    03"
  echo "2 99002  47.0000  90.0000 0001000   0.0000   0.0000 14.95000000    04"
} > "${TLE_FILE}"

echo "=== Step 1: TLE → visibility windows for HSINCHU ==="
python3 "${ROOT}/scripts/tle_windows.py" \
    --tle "${TLE_FILE}" \
    --lat 24.7881 --lon 120.9979 --alt 0.052 \
    --start 2027-06-01T00:00:00Z \
    --end   2027-06-01T03:00:00Z \
    --step 30 \
    --min-elev 10.0 \
    --out "${OUT}/hsinchu_windows.json"

echo
echo "=== Step 2: convert to OASIS-style windows JSON ==="
# tle_windows.py output is already OASIS-shape; just symlink so the next
# step has the canonical filename.
cp "${OUT}/hsinchu_windows.json" "${OUT}/windows.json"

echo
echo "=== Step 3: scenario JSON for ns-3 / metrics ==="
python3 "${ROOT}/scripts/gen_scenario.py" \
    "${OUT}/windows.json" \
    -o "${OUT}/scenario.json" \
    --mode transparent \
    --skip-validation

echo
echo "=== Step 4: KPIs (v1 physics formula) ==="
python3 "${ROOT}/scripts/metrics.py" \
    "${OUT}/scenario.json" \
    -o "${OUT}/metrics_v1.csv" \
    --summary "${OUT}/summary_v1.json" \
    --skip-validation

echo
echo "=== Step 5 (optional): v2 packet-level KPIs from a Hypatia run ==="
echo "  Skipped by default. To exercise:"
echo "    bash ${ROOT}/docker/run-hypatia-sim.sh /tmp/hypatia-real-run"
echo "    python3 ${ROOT}/scripts/metrics.py ${OUT}/scenario.json \\"
echo "        --use-hypatia /tmp/hypatia-real-run/udp_variant_17_to_18 \\"
echo "        -o ${OUT}/metrics_v2.csv --skip-validation"

echo
echo "=== Done. Outputs in ${OUT} ==="
ls -la "${OUT}"
