# Taiwan B5G LEO — Stage 2 Reference Example

> **Status (2026-04)**: scaffold / preview. The orbital parameters here are
> taken from public TASA / NSPO procurement documents and news releases
> (cited inline). This example is **not endorsed by TASA** and **does not
> connect to any real spacecraft, payload, or ground segment**. It exists
> so that a Taiwanese reviewer searching GitHub for "Taiwan B5G LEO
> simulator" finds at least one open-source pipeline pre-configured to
> the program's announced constellation parameters.

## What this example does

End-to-end, using the v1 + v2 pipeline already in this repo:

1. Generate a synthetic 1A pathfinder TLE (~600 km, 44–50° inclination,
   matching CesiumAstro Vireo Ka payload announcement)
2. Use the existing 6 Taiwan ground stations from
   `data/taiwan_ground_stations.json` (HSINCHU / TAIPEI / KAOHSIUNG /
   TAICHUNG / TAINAN / HUALIEN)
3. Compute visibility windows via `scripts/tle_windows.py`
4. Convert to a TASA scenario JSON via `scripts/gen_scenario.py`
5. Optionally feed the v2 `--use-hypatia` flag to obtain real
   packet-level KPIs instead of the v1 physics-formula KPIs

The synthetic TLE intentionally uses placeholder NORAD catalog numbers
(`99001U` / `99002U`) — when official TASA TLEs become available
(post-launch, 2027–), drop them into `data/` and rerun.

## Constellation parameters (sources cited in `taiwan_b5g.yaml`)

```
Mission        : TASA Beyond-5G LEO Satellite — 1A Pathfinder
Altitude       : ~600 km (CesiumAstro Vireo Ka announcement, 2025-04)
Inclination    : 44–50° (program docs)
Payload        : Ka-band SDR (CesiumAstro Vireo on 1A; YTTEK on 1B)
Mass class     : ~400 kg
Planned launch : 1A 2027 / 1B 2030 / full constellation 2031
Manufacturing  : Compal + Wistron (NT$2.357 B contract, 2025-09)
```

## How to run

```bash
# Pre-conditions: repo cloned, requirements installed.
cd examples/taiwan_b5g
bash run.sh                      # writes outputs/ in this directory
```

`run.sh` is a thin shell driver — read it before running. It does not
need root or Docker; everything is host Python.

## Why this skeleton matters

- The TASA Industrialization Platform tender (2025-08, NT$2.49 B program)
  explicitly names "satellite body simulation, payload-body integration
  platform, end-to-end system testing" as required deliverables.
- No open-source TASA / NSPO / ITRI / NCKU release has filled this niche
  as of April 2026 (verified via independent research).
- This skeleton lets a TASA-program-adjacent engineer demo a working
  pipeline configured to the announced 1A spec, without committing the
  project to any specific TASA contract path.

## Sources

- [TASA — Beyond-5G LEO Satellite mission page](https://www.tasa.org.tw/en-US/missions/detail/Beyond-5G-LEO-Satellite)
- [Focus Taiwan, "CesiumAstro to Deliver Space Payloads…", 2025-04](https://focustaiwan.tw/sci-tech/202504010012)
- [Manila Times via PR Newswire, "YTTEK joins Taiwan's National B5G LEO…", 2026-01-16](https://www.manilatimes.net/2026/01/16/tmt-newswire/pr-newswire/yttek-joins-taiwans-national-b5g-leo-satellite-program-accelerating-indigenous-space-communications/2260101)
- [TASA Industrialization Platform tender notice](https://www.tasa.org.tw/zh-TW/announcements/detail/d89efe62-d15f-45fa-9e26-f54813cfb660)
- [CTEE, "Compal/Wistron NT$23.57 億 standpoint", 2025-09-26](https://www.ctee.com.tw/news/20250926700095-439901)
- [Focus Taiwan, "Formosat-8A launch", 2025-11-29](https://focustaiwan.tw/sci-tech/202511290004)

## What this example deliberately does not do

- Does not include a real payload model (RF link budget, SDR processing
  delay, encryption stages) — only the placeholder geometric simulation
- Does not implement TT&C / authentication / mission control protocols
- Does not benchmark against a real measurement (no flight data exists yet)
- Does not assert any particular schedule for v2.1 release of this
  example — open-ended preview; ETA aligns to TASA program milestones
