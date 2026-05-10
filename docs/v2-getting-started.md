# v2 Getting Started — packet-level metrics with Hypatia

User-facing companion to [`docs/internal/v2-feasibility.md`](internal/v2-feasibility.md).
That document is the design memo (why v2 exists, what the I/O contract is). This
document is the *how-to* — fresh checkout to packet-level KPIs in five steps.

If you only want **v1** (physics-formula KPIs, ~1 second per run, no Docker
ns-3 build), the existing [README](../README.md) §Quickstart still works
unchanged. v2 is **opt-in**.

---

## What you get with v2

Instead of v1's

```
mean_latency_ms    : 8.91   ← computed from speed-of-light + 80% utilization formula
mean_throughput_mbps: 40.0  ← every session reports the same number
```

…v2 gives you

```
src,dst,target_mbps,achieved_mbps,packets_sent,bytes_sent,delivery_ratio
17, 18, 10.0,        9.813353,    166667,       245333824,  0.9813
```

— per-flow numbers from a real ns-3 packet-level simulation. That includes
queueing loss, ISL utilization tracking, and timing breakdown.

The cost: a one-time ~30 minute Docker build of ns-3.31 (5.92 GB image,
deferred to a separate Dockerfile so v1 stays lean).

---

## Five-step quickstart

### 1. Build the dev images (one-time, ~15 min total)

```bash
docker build -f docker/hypatia.Dockerfile     -t tasa-hypatia-base:dev   docker/
docker build -f docker/hypatia-ns3.Dockerfile -t tasa-hypatia-ns3:dev    docker/
```

The base image (`tasa-hypatia-base:dev`, 969 MB) contains satgenpy on
Ubuntu 20.04. The ns-3 image (`tasa-hypatia-ns3:dev`, 5.92 GB) extends
it with the full ns-3.31 build plus the `main_satnet` binary. See
[`docker/README.md`](../docker/README.md) for why these are split and
why we pin Ubuntu 20.04 (Hypatia issue #39: ns-3.31 does not build on 24.04).

### 2. Run a real Hypatia simulation

```bash
bash docker/run-hypatia-sim.sh /tmp/hypatia-real-run
```

Inside the container, this:

1. Generates a Kuiper-630 reduced-state network via satgenpy (~5 s).
2. Constructs a UDP variant of the smallest packaged run (1 flow,
   node 17 → node 18, 10 Mbps for 200 s sim time).
3. Invokes `main_satnet` (waf-built ns-3) directly (~9 s wall clock).
4. Copies the resulting run directory to your host path.

Expected output:

```
/tmp/hypatia-real-run/udp_variant_17_to_18/
├── config_ns3.properties
├── udp_burst_schedule.csv
└── logs_ns3/
    ├── finished.txt          ← contains "Yes"
    ├── udp_bursts_outgoing.csv  ← per-flow sender stats (1 row)
    ├── udp_bursts_incoming.csv  ← per-flow receiver stats (1 row)
    ├── isl_utilization.csv
    ├── timing_results.{csv,txt}
    └── console.txt
```

### 3. Feed the run output into the TASA metrics CLI

```bash
# Generate a scenario (or use any existing one)
python scripts/parse_oasis_log.py data/sample_oasis.log -o /tmp/windows.json
python scripts/gen_scenario.py /tmp/windows.json -o /tmp/scenario.json --skip-validation

# Compute v2 metrics
python scripts/metrics.py /tmp/scenario.json \
    --use-hypatia /tmp/hypatia-real-run/udp_variant_17_to_18 \
    -o /tmp/metrics_v2.csv \
    --summary /tmp/summary_v2.json \
    --skip-validation
```

The CSV at `/tmp/metrics_v2.csv` has nine columns including
`throughput_source=hypatia` for every row, distinguishing it from the
v1 physics-formula CSV.

### 4. (Optional) Run inside the cluster

If you have a Kubernetes cluster pointed at the project image, the
demo job ships the v2 path against the vendored Hypatia fixture (no
ns-3 image required for this — the fixture is a head-truncated copy of
the official paper-replication archive):

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/job-v2-pipeline.yaml
kubectl logs -n tasa-satnet job/tasa-v2-pipeline -f
```

Verified runtime: ~10 s. See [`k8s/job-v2-pipeline.yaml`](../k8s/job-v2-pipeline.yaml).

### 5. (Optional) Do it via the Taiwan B5G example

[`examples/taiwan_b5g/run.sh`](../examples/taiwan_b5g/run.sh) auto-detects
whether `tasa-hypatia-ns3:dev` exists and adds Step 5 (v2 path) if it does.
This is the easiest end-to-end flow:

```bash
bash examples/taiwan_b5g/run.sh
# outputs/ now contains both metrics_v1.csv (physics formula) and
# metrics_v2.csv (real packet-level), if the v2 image is built.
```

---

## When to use v1 vs v2

| Use case | v1 | v2 |
|---|---|---|
| Quick smoke / CI / "does the pipeline run" | ✓ | overkill |
| Compare relay modes (transparent vs regenerative) | ✓ | ✓ |
| Show realistic packet loss / queue dynamics | ✗ (formula returns flat 80% util) | ✓ |
| Submit as conference artifact reproducibility | ✗ (formula not citable) | ✓ |
| Run on machines without 5 GB free for ns-3 image | ✓ | ✗ |
| Run inside production K8s job | ✓ (v1 path of the same image) | ✓ (vendored-fixture demo only; full ns-3 sim is dev workstation territory) |

**v1 is not deprecated.** Both paths coexist on `main`. `--use-hypatia` is purely additive.

---

## Troubleshooting

### "tasa-hypatia-ns3:dev: No such image"

You haven't built it. Step 1 above. Or the build failed mid-way and
left no image — check `docker images | grep hypatia` and re-run.

### "Hypatia run incomplete: finished.txt != 'Yes'"

The ns-3 sim crashed or the run directory got truncated. Re-run
`bash docker/run-hypatia-sim.sh ...` and check the console output for
the failure line. Common causes: out of memory (give Docker ≥4 GB RAM),
out of disk (run directory copy needs ~50 MB free).

### `metrics.py --use-hypatia` errors with "No module named 'scripts'"

Run from the repo root, not from inside `scripts/`:

```bash
cd <repo-root>
python scripts/metrics.py ...    # ✓
```

### Real ns-3 sim is too slow

Hypatia is ~11× slower than real time at Kuiper-630 (1156-node) scale.
For TASA-scale simulations (tens of nodes), you can shrink the run by
modifying `docker/run-hypatia-sim.sh`'s `udp_burst_schedule.csv` line
to set a shorter `end_ns` (e.g. `10000000000` for 10 s sim instead of
the default 200 s). v2 metrics still parse correctly.

---

## Going further

The adapter modules in `scripts/adapters/` are designed to be reused
in other contexts. If you want to wire Hypatia output into a different
downstream (Pandas notebook, Grafana, custom plot pipeline), import
`from scripts.adapters.from_hypatia import run_dir_to_tasa_metrics`
directly and skip the metrics.py CLI entirely.

For the I/O contract reference (what each Hypatia file means, what
values are reasonable), see
[`docs/internal/v2-feasibility.md`](internal/v2-feasibility.md) §3.
