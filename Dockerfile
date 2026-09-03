# Multi-stage build for DockTUI

# Docker CLI + compose plugin (static binaries) for Recreate/Down, which run
# 'docker compose' against the host's daemon socket.
FROM docker:28-cli AS dockercli

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install poetry (must be able to read the lock file format written by the
# version used for development)
RUN pip install --no-cache-dir poetry==2.1.3

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy the application code (README is referenced by pyproject and required
# by Poetry when installing the root package)
COPY DockTUI ./DockTUI
COPY README.md ./

# Install the application
RUN poetry install --no-interaction --no-ansi

# Final stage
FROM python:3.12-slim

# Create non-root user
RUN useradd -m -u 1000 docktui

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Docker CLI and compose plugin (the plugin directory is on the CLI's default search path)
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

# Copy application
COPY --from=builder /app/DockTUI ./DockTUI

# Create directories for config and logs
RUN mkdir -p /app/logs /config && \
    chown -R docktui:docktui /app /config

# Switch to non-root user
USER docktui

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TERM=xterm-256color
ENV DOCKTUI_IN_CONTAINER=1
# start.sh mounts the host filesystem read-only here so compose files can be
# read regardless of where they live on the host.
ENV DOCKTUI_HOST_ROOT=/host

# Entry point
ENTRYPOINT ["python", "-m", "DockTUI"]