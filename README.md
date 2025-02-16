# dockerview

An interactive terminal dashboard for monitoring and managing Docker Compose environments.
This is designed to replicate, somewhat, the main UI view from Docker Desktop.

## Overview

dockerview is a modern terminal user interface (TUI) for real-time monitoring and management of Docker containers and Docker Compose stacks. It provides an intuitive, keyboard-driven interface for viewing container status, resource usage, logs, and performing common Docker operations.

## Features

- Real-time monitoring of Docker containers and Docker Compose stacks
- Interactive terminal interface with keyboard navigation
- Collapsible/expandable Docker Compose stack views
- Live resource usage statistics (CPU, Memory)
- Low system resource footprint
- Cross-platform support (Linux, macOS, Windows)

## Technical Design

### Architecture

dockerview is built using Python with the following core components:

1. **UI Layer** (Textual)
   - Main dashboard view with collapsible stack sections
   - Container detail panels
   - Log viewing pane
   - Status bar for system info and keybindings
   - Modal dialogs for actions and confirmations

2. **Docker Integration Layer** (docker-py)
   - Real-time container statistics collection
   - Event monitoring for container state changes
   - Command execution (start/stop/restart)
   - Log streaming and management

3. **State Management**
   - Container and stack state tracking
   - User interface state (selections, expanded/collapsed sections)
   - Configuration management

### Data Flow

Docker Engine <-> Docker SDK <-> State Manager <-> UI Components

### Key Components

- **DashboardApp**: Main Textual application class
- **StacksWidget**: Manages collapsible Docker Compose stack views
- **ContainerList**: Navigable list of containers with real-time stats
- **LogViewer**: Split-pane view for container/stack logs
- **DockerManager**: Handles Docker SDK integration and event processing
- **StateManager**: Manages application state and configuration

## Development

### Requirements

- Python 3.8+
- Docker Engine
- Docker Compose

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/dockerview.git
cd dockerview

# Install Poetry if not already installed
# On Linux/macOS
pip install poetry

# Install dependencies and create virtual environment
poetry install

# Activate the virtual environment
poetry shell

# Run dockerview
python -m dockerview
