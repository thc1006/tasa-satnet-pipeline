# Hypatia / satgenpy base image (v2 supporting infra)
#
# Scope of this Dockerfile: install satgenpy and its system dependencies on
# top of ubuntu:20.04. ns-3 build is *intentionally not included* — see
# docs/internal/v2-feasibility.md §6.1 for why ns-3 is a separate image
# decision. Building this image is a precondition for v2's adapter pipeline
# to be able to actually generate dynamic_state directories from TLEs.
#
# This image is NOT used by the production tasa-satnet-pipeline. It is a
# development tool. Build with:
#
#     docker build -f docker/hypatia.Dockerfile -t tasa-hypatia-base:dev docker/
#
# Then drop into a shell:
#
#     docker run --rm -it -v "$PWD:/work" tasa-hypatia-base:dev bash
#
# Why ubuntu:20.04 and not 24.04: hypatia issue #39 (open) confirms ns-3.31
# does not build on Ubuntu 24.04 + GCC 13. Pinning 20.04 here means later
# extending this image with ns-3 stays viable; switching to 24.04 closes
# that door.

FROM ubuntu:20.04

LABEL purpose="satgenpy base image for TASA SatNet v2 (no ns-3 yet)"
LABEL maintainer="thc1006"

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies. Cartopy is intentionally skipped — its libproj /
# libgeos build chain doubles install time and we don't need plotting in
# this image. If a downstream wants visualization it should build a separate
# image; that is the explicit design choice in v2-feasibility.md §7.3.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        git \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

# Python deps for satgenpy. astropy and statsmodels both appear inside
# satgen.* (not just paper-plot helpers — confirmed empirically by tracing
# import errors during this image's build). cartopy is still skipped because
# it's only loaded by satviz, which we don't run here.
RUN pip3 install --no-cache-dir \
        numpy==1.24.3 \
        astropy==5.2.2 \
        ephem==4.1.5 \
        networkx==3.1 \
        sgp4==2.22 \
        geopy==2.4.1 \
        statsmodels==0.14.0 \
        git+https://github.com/snkas/exputilpy.git@v1.6

WORKDIR /opt
RUN git clone --depth=1 https://github.com/snkas/hypatia.git /opt/hypatia

# satgen/__init__.py eagerly chains to satgen.post_analysis which import cartopy.
# We don't run plotting paths here, and adding cartopy doubles the build cost
# (libproj-dev, libgeos-dev). Comment out that single import line so satgen.*
# loads without cartopy. Verify the patch landed.
RUN sed -i 's|^from .post_analysis import \*$|# from .post_analysis import * # disabled: avoids cartopy dep|' \
    /opt/hypatia/satgenpy/satgen/__init__.py && \
    grep -F "post_analysis" /opt/hypatia/satgenpy/satgen/__init__.py

# Make satgenpy importable as a top-level package
ENV PYTHONPATH=/opt/hypatia/satgenpy

# Smoke test. NOTE: `import satgen` (the package) eagerly chains through to
# satgen.post_analysis, which imports cartopy — pulling cartopy in would mean
# also installing libproj-dev, libgeos-dev and ~10 minutes of build time we
# don't need. Adapter only needs the satgen.tles and satgen.dynamic_state_*
# submodules; load them directly to avoid the full eager import.
RUN python3 -c "from satgen.tles.read_tles import read_tles; print('satgen.tles importable')"
RUN python3 -c "from satgen.distance_tools import distance_m_between_satellites; print('satgen.distance_tools importable')"

WORKDIR /work
CMD ["bash"]
