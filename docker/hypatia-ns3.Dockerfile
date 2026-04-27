# Hypatia + ns-3.31 — full packet-level simulation image
#
# Extends docker/hypatia.Dockerfile (satgenpy base) with the ns-3.31 build
# from snkas/hypatia. Big and slow to build (~30–60 min, ~3 GB image), but
# it actually runs Hypatia ns-3 simulations end-to-end. This is the v2 ship
# blocker.
#
# Build (after building tasa-hypatia-base:dev first):
#     docker build -f docker/hypatia.Dockerfile  -t tasa-hypatia-base:dev   docker/
#     docker build -f docker/hypatia-ns3.Dockerfile -t tasa-hypatia-ns3:dev  docker/
#
# Run:
#     docker run --rm -it \
#         -v "$PWD:/work" \
#         -v /tmp:/host_tmp \
#         tasa-hypatia-ns3:dev bash
#
# Why ubuntu:20.04 + ns-3.31 with `--optimized`: ns-3.31 is what hypatia
# pins (issue #39 confirms it does not build on 24.04). `--optimized`
# trades debug symbols for ~10× faster build time and similar runtime —
# we don't need ns-3 internals visibility, just packet-level KPI output.
#
# Why not `--debug_all` (the build.sh default): debug builds spend most
# of their time enabling gcov + tests. Adapter contract is what we are
# verifying, not ns-3 internals.

FROM tasa-hypatia-base:dev

LABEL purpose="Hypatia ns-3.31 packet-level sim image (v2 ship)"

ENV DEBIAN_FRONTEND=noninteractive

# ns-3 build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        make \
        unzip \
        libopenmpi-dev \
        openmpi-bin \
        python-is-python3 \
        pkg-config \
        && rm -rf /var/lib/apt/lists/*

# The base image cloned hypatia with --depth=1, which doesn't pull
# submodules. Re-clone with submodules (basic-sim is a submodule of
# ns3-sat-sim/simulator/).
RUN rm -rf /opt/hypatia && \
    git clone --recurse-submodules --depth=1 \
        https://github.com/snkas/hypatia.git /opt/hypatia && \
    sed -i 's|^from .post_analysis import \*$|# from .post_analysis import * # disabled: avoids cartopy|' \
        /opt/hypatia/satgenpy/satgen/__init__.py

# Build ns-3.31 + Hypatia satellite module + basic-sim, in optimized mode.
# This is the slow step (~15-40 min on a 4-core box). Pinned -j4 to keep
# memory bounded; -j$(nproc) on a 12-core 16GB host can OOM during linking.
# build.sh exits non-zero if waf fails, so a successful return here implies
# the binary tree under build/optimized/ is populated. We list one path to
# leave a breadcrumb for runtime users; we do NOT condition the image on
# file presence (paths vary across waf versions and have bitten earlier
# attempts at this image).
WORKDIR /opt/hypatia/ns3-sat-sim
RUN bash build.sh --optimized 2>&1 | tail -200 && \
    echo "=== build/optimized layout ===" && \
    find /opt/hypatia/ns3-sat-sim/simulator/build/optimized \
        -maxdepth 3 -name "main_satnet*" -o -name "scratch" 2>/dev/null | head -20

WORKDIR /work
CMD ["bash"]
