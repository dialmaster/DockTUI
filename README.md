# dockerview

An interactive terminal dashboard for monitoring and managing Docker Compose environments.
This is designed to replicate, somewhat, the main UI view from Docker Desktop.

## Overview

dockerview is a modern terminal user interface (TUI) for real-time monitoring and management of Docker containers and Docker Compose stacks. It provides an intuitive, keyboard-driven interface for viewing container status, resource usage, logs, and container management.

## Features

- Real-time monitoring of Docker containers and Docker Compose stacks
- Interactive terminal interface with keyboard navigation
- Collapsible/expandable Docker Compose stack views
- Live resource usage statistics (CPU, Memory, PIDs)
- Container port mapping display
- Split-pane log viewer with real-time log streaming
- Container and stack management (start/stop/restart/recreate)
- Log filtering and auto-follow functionality
- Text selection and clipboard support in log viewer
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
   - Split-pane log viewer with real-time streaming
   - Status bar for selection information
   - Error display for showing error messages
   - Interactive controls for log filtering and auto-follow
   - Modal dialogs for actions and confirmations

2. **Docker Integration Layer** (docker-py)
   - Real-time container statistics collection
   - Docker Compose stack detection and grouping
   - Container port mapping display
   - Container and stack command execution (start/stop/restart/recreate)
   - Real-time log streaming for containers and stacks
   - Event monitoring for container state changes

3. **State Management**
   - Container and stack state tracking
   - User interface state (selections, expanded/collapsed sections)
   - Performance optimizations for handling many containers

### Data Flow

Docker Engine <-> Docker SDK <-> DockerManager <-> UI Components

### Key Components

- **DockerViewApp**: Main Textual application class with keyboard bindings for container management
- **ContainerList**: Navigable list of containers with real-time stats, grouped by stacks
- **StackHeader**: Collapsible headers for Docker Compose stacks
- **StatusBar**: Displays detailed information about the selected container or stack
- **DockerManager**: Handles Docker SDK integration, container/stack data retrieval, and command execution
- **LogPane**: Split-pane view for real-time container/stack log streaming with filtering
- **StateManager**: Dedicated state management component

## Usage

### Keyboard Shortcuts

#### Navigation
- `↑/↓`: Navigate through containers and stacks
- `←/→`: Collapse/expand stacks
- `Tab`: Switch focus between panes
- `q`: Quit the application

#### Container/Stack Management
- `s`: Start selected container or stack
- `t`: Stop selected container or stack
- `e`: Restart selected container or stack
- `u`: Recreate selected container or stack (docker compose up -d)

#### Log Viewer
- Click and drag: Select text in log viewer
- Right-click: Copy selected text to clipboard
- Filter box: Type to filter log entries in real-time
- Auto-follow checkbox: Toggle automatic scrolling of new log entries

## Development

### Requirements

- Python 3.8+
- Docker Engine
- Docker Compose
- Textual library

#### WSL2 Clipboard Support

If you're running dockerview in WSL2 and want to use the clipboard functionality (right-click copy in log pane), you may need to install `xclip`:

```bash
sudo apt-get install xclip
```

This is optional - dockerview will attempt to use PowerShell's clipboard integration first, but xclip provides a fallback.

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

### Screenshots
![dockerview_shot1](https://github.com/user-attachments/assets/2aa27bdf-345f-43dd-9b03-28843ffb72a2)
![dockerview_shot2](https://github.com/user-attachments/assets/87a61238-33d5-4f2a-9c17-58f3b34c5815)

