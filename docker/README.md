# `docker/` — supporting Docker images for development

The main project image (`Dockerfile` at repo root) is the production
artifact: it has no satgenpy / ns-3 / Hypatia dependencies and is what
`k8s/job-test-real.yaml` runs.

This directory holds *development-only* images that exist to make v2 work
possible without bloating the production image.

## `hypatia.Dockerfile` — satgenpy base

Installs `satgenpy` (the Python network-state generator from snkas/hypatia)
on Ubuntu 20.04. Does *not* build ns-3 — that is a separate, much larger
build step deferred to a follow-up image.

This image lets v2's `scripts/adapters/to_satgenpy.py` output be exercised
end-to-end: feed the directory the adapter wrote into the satgenpy CLI
running inside this image, and you get a `dynamic_state_*` directory back.

### Build

```
docker build -f docker/hypatia.Dockerfile -t tasa-hypatia-base:dev docker/
```

### Use

```
docker run --rm -it \
    -v "$PWD:/work" \
    tasa-hypatia-base:dev \
    python3 -c "import satgen; print(satgen.__file__)"
```

### Why ubuntu:20.04

Hypatia issue
[#39](https://github.com/snkas/hypatia/issues/39) (open as of 2026-04)
confirms ns-3.31, the version Hypatia pins, does not build on
Ubuntu 24.04 + GCC 13. We standardize this base image on 20.04 so a
follow-up commit can extend it with ns-3 build steps without changing
the base. Switching to 24.04 would close that door.

### Why no cartopy

Cartopy doubles install time via libproj / libgeos compilation and is
only needed for plotting paths the v2 adapter does not exercise. See
`docs/internal/v2-feasibility.md` §7.3.
