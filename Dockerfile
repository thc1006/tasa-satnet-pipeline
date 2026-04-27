# TASA SatNet Pipeline - Dockerfile
# Multi-stage build for optimal image size

# Stage 1: Builder
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.10-slim

# Metadata
LABEL maintainer="TASA SatNet Pipeline Team"
LABEL description="OASIS to NS-3/SNS3 satellite communication pipeline"
LABEL version="1.0.0-alpha"

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY tests/ ./tests/
COPY data/sample_oasis.log ./data/sample_oasis.log
COPY pytest.ini .
COPY Makefile .

# Create output directories
RUN mkdir -p reports

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "scripts/healthcheck.py"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python scripts/healthcheck.py
