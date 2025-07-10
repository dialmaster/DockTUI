# Multi-stage build for DockTUI
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy the application code
COPY DockTUI ./DockTUI

# Install the application
RUN poetry install --no-interaction --no-ansi

# Final stage
FROM python:3.12-slim

# No runtime dependencies needed - we use file-based clipboard

# Create non-root user
RUN useradd -m -u 1000 docktui

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

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

# Entry point
ENTRYPOINT ["python", "-m", "DockTUI"]