# dockerview

An interactive terminal dashboard for monitoring and managing Docker Compose environments.
This is designed to replicate, somewhat, the main UI view from Docker Desktop.

## Overview

dockerview is a modern terminal user interface (TUI) for real-time monitoring and management of Docker containers and Docker Compose stacks. It provides an intuitive, keyboard-driven interface for viewing container status, resource usage, and container information.

## Features

- Real-time monitoring of Docker containers and Docker Compose stacks
- Interactive terminal interface with keyboard navigation
- Collapsible/expandable Docker Compose stack views
- Live resource usage statistics (CPU, Memory, PIDs)
- Container port mapping display
- Status bar with detailed selection information
- Low system resource footprint
- Cross-platform support (Linux, macOS, Windows)
- Debug mode with detailed logging

## Technical Design

### Architecture

dockerview is built using Python with the following core components:

1. **UI Layer** (Textual)
   - Main dashboard view with collapsible stack sections
   - Container detail rows with resource usage information
   - Status bar for selection information
   - Instructions widget with common Docker commands
   - Error display for showing error messages
   - Log viewing pane (Not implemented yet)
   - Modal dialogs for actions and confirmations (Not implemented yet)

2. **Docker Integration Layer** (docker-py)
   - Real-time container statistics collection
   - Docker Compose stack detection and grouping
   - Container port mapping display
   - Event monitoring for container state changes (Not implemented yet)
   - Command execution (start/stop/restart selected item) (Not implemented yet)
   - Log streaming and management for selected item (Not implemented yet)

3. **State Management**
   - Container and stack state tracking
   - User interface state (selections, expanded/collapsed sections)
   - Performance optimizations for handling many containers

### Data Flow

Docker Engine <-> Docker SDK <-> DockerManager <-> UI Components

### Key Components

- **DockerViewApp**: Main Textual application class
- **ContainerList**: Navigable list of containers with real-time stats, grouped by stacks
- **StackHeader**: Collapsible headers for Docker Compose stacks
- **StatusBar**: Displays detailed information about the selected container or stack
- **DockerManager**: Handles Docker SDK integration and container/stack data retrieval
- **LogViewer**: Split-pane view for container/stack logs (Not implemented yet)
- **StateManager**: Dedicated state management component (Not implemented yet)

## Development

### Requirements

- Python 3.8+
- Docker Engine
- Docker Compose
- Textual library

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/dockerview.git
cd dockerview

# Install Poetry if not already installed
# On Linux/macOS
pip install poetry

# Run dockerview (automatically installs dependencies)
./start.sh
```

### Alternative Setup (Manual)

```bash
# Install dependencies and create virtual environment
poetry install

# Activate the virtual environment
poetry shell

# Run dockerview
python -m dockerview
```

### Debug Mode

To enable debug mode with detailed logging:

```bash
# Using the start script (recommended)
./start.sh -d

# Or manually
export DOCKERVIEW_DEBUG=1
python -m dockerview
```

### Start Script Options

The `./start.sh` script supports the following options:

```bash
./start.sh           # Run normally
./start.sh -d        # Run with debug logging enabled
./start.sh --debug   # Same as -d
./start.sh -h        # Show help
./start.sh --help    # Show help