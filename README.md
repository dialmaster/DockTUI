# DockTUI

An interactive terminal dashboard for monitoring and managing Docker containers and Docker Compose environments.

![DockTUI_screenshot_1](https://github.com/user-attachments/assets/f9936902-6240-414c-9530-65bfe1fbf457)
![DockTUI_screenshot_2](https://github.com/user-attachments/assets/fc9f58e2-ca3a-4acb-ba52-932433326562)
![DockTUI_screenshot_3](https://github.com/user-attachments/assets/68743925-7101-432f-90d3-c15df191515f)
![DockTUI_screenshot_4](https://github.com/user-attachments/assets/6d8c8eb2-a03f-4474-b4cb-a5e0be33e806)

## What is DockTUI?

DockTUI is a terminal user interface (TUI) that provides a real-time dashboard for your Docker containers, similar to Docker Desktop but in your terminal. It lets you monitor container status, view logs, manage containers and stacks, and track resource usage - all with simple keyboard shortcuts.

## Features

- 📊 **Real-time Monitoring** - Live updates of container status, CPU, memory, and resource usage
- 🎯 **Docker Compose Support** - Organized view of containers grouped by Compose stacks
- 📜 **Rich Log Viewer** - Advanced log viewing with syntax highlighting, JSON/XML expansion, and smart pattern detection
- ⚡ **Quick Actions** - Start, stop, restart, recreate containers and stacks with keyboard shortcuts
- 🗂️ **Resource Management** - Manage images, volumes, and networks with usage tracking
- 🎨 **Clean Interface** - Intuitive terminal UI with collapsible sections and status bar
- ⌨️ **Command Palette** - Quick access to all actions with Ctrl+\

## Installation

### Prerequisites

- Docker Engine installed and running
- Docker Compose v2 (the `docker compose` command)
- Unix-like terminal (Linux, macOS, or WSL2 on Windows)

> **Note:** No Python or other dependencies required! DockTUI runs entirely in Docker.

### Quick Start

```bash
# Option 1: Run directly (no clone needed)
curl -sSL https://raw.githubusercontent.com/dialmaster/DockTUI/main/start.sh | bash

# Option 2: Clone and run
git clone https://github.com/dialmaster/DockTUI.git
cd DockTUI
./start.sh
```

That's it! The script automatically pulls and runs DockTUI from Docker Hub.

### Start Options

```bash
./start.sh           # Run latest version
./start.sh -d        # Run with debug logging
./start.sh -u        # Update to latest version
./start.sh -v 1.0.0  # Run specific version
./start.sh -h        # Show help
```

### Features of Dockerized Setup

- **Zero build time** - Pre-built images from Docker Hub
- **Automatic updates** - Just use `-u` flag to get latest version
- **Multi-platform** - Works on AMD64 and ARM64 (including M1 Macs)
- **Version control** - Pin to specific versions with `-v`
- **Full functionality** - All features work including clipboard support

### For Developers

If you want to contribute or run DockTUI without Docker, see [DEVELOPMENT.md](DEVELOPMENT.md) for Python/Poetry setup instructions.

## Usage

### Keyboard Shortcuts

#### Navigation
- `↑/↓` - Navigate through items
- `←/→` or `Enter` - Collapse/expand sections
- `Tab` - Switch between panels
- `q` - Quit

#### Container/Stack Actions
- `s` - Start
- `t` - Stop (with 't' for 'terminate')
- `e` - Restart
- `u` - Recreate (docker compose up -d)
- `d` - Docker compose down
- `r` - Remove selected stopped/exited container

#### Image Management
- `r` - Remove selected unused image
- `R` - Remove all unused images

#### Volume Management
- `r` - Remove selected volume (when not in use)
- `p` - Prune all unused volumes

#### Quick Access
- `Ctrl+\` - Open command palette

### Log Viewer

#### Rich Syntax Highlighting
- Automatic detection and highlighting of:
  - Timestamps in various formats
  - Log levels (ERROR, WARN, INFO, DEBUG, TRACE) with color coding
  - Network data (IP addresses, ports, MAC addresses)
  - URLs and file paths
  - UUIDs and Kubernetes resources
  - HTTP methods and status codes
  - Code snippets with language-specific syntax highlighting

#### Interactive Features
- **Click and drag** to select text
- **Double-click** on JSON/XML lines to expand/collapse pretty-printed views
- **Filter box** to search logs in real-time
- **Auto-follow** checkbox to toggle automatic scrolling
- **Mark Log Position** - Add timestamped markers to track important events

#### Performance Optimizations
- Virtual scrolling for handling massive log files
- Lazy parsing - lines are only processed when visible
- Background pre-parsing of upcoming lines for smooth scrolling
- Configurable memory limits to prevent excessive resource usage

### Volume Management

DockTUI displays volumes in a table format showing:
- Volume name and driver
- Usage status (in-use or available)
- Container count and names using each volume

Volumes in use are shown first and cannot be removed. The status bar shows detailed information about which containers are using the selected volume.

## Configuration

DockTUI can be customized through a YAML configuration file. A default `DockTUI.yaml` is included.

### Configuration Locations

DockTUI looks for configuration in this order:
1. Path in `DOCKTUI_CONFIG` environment variable
2. `./DockTUI.yaml` (included default)
3. `~/.config/DockTUI/DockTUI.yaml`

### Basic Settings

```yaml
app:
  refresh_interval: 5.0  # How often to update container stats (seconds)

log:
  max_lines: 4000       # Max log lines to keep in memory
  tail: 400             # Initial lines to show when opening logs
  since: '30m'          # Time range for logs (e.g., '15m', '1h', '24h')
```

### Performance Tuning

The log viewer uses advanced optimization techniques:
- **Virtual scrolling** - Only renders visible lines for smooth performance
- **Lazy parsing** - Processes log lines on-demand as you scroll
- **Background pre-loading** - Prepares upcoming lines before you reach them

For containers with lots of logs:
- **Faster loading**: Use smaller `tail` (e.g., 100) and `since` (e.g., '5m')
- **More history**: Increase `tail` (e.g., 1000) and `since` (e.g., '1h')
- **Memory limit**: Adjust `max_lines` to control memory usage (default: 4000)

### Environment Variables

Override configuration with environment variables:

```bash
# Change refresh rate
export DOCKTUI_APP_REFRESH_INTERVAL=10.0

# Adjust log settings
export DOCKTUI_LOG_TAIL=500
export DOCKTUI_LOG_SINCE=1h

./start.sh
```

## Clipboard Support

DockTUI automatically handles clipboard integration. Selected text from logs can be copied to your system clipboard with:
- Click and drag to select text
- Right click to copy

The dockerized version automatically syncs the clipboard with your host system.

## Troubleshooting

### Common Issues

**"Cannot connect to Docker daemon"**
- Ensure Docker is running: `docker ps`
- Check permissions: You may need to add your user to the docker group

**"docker compose command not found"**
- DockTUI requires Docker Compose v2
- Update Docker to get the integrated `docker compose` command

**Clipboard not working**
- Ensure your host system has a clipboard tool (xclip, pbcopy, etc.)
- The Docker version handles clipboard sync automatically

**Performance issues with many containers**
- Adjust log settings in configuration
- Increase refresh interval for lower CPU usage

### Debug Mode

Enable detailed logging to troubleshoot issues:

```bash
./start.sh -d
```

Debug logs are saved to `./logs/DockTUI_debug.log`.

## Limitations

- Must run on the same machine/filesystem as your Docker Compose files
- Remote Docker daemon monitoring not currently supported
- Best experience in modern terminal emulators with mouse support

## Contributing

See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture details, development setup, and contribution guidelines.

## License

MIT License - see LICENSE file for details

## Acknowledgments

Built with:
- [Textual](https://github.com/Textualize/textual) - Terminal UI framework
- [docker-py](https://github.com/docker/docker-py) - Docker SDK for Python
- [Poetry](https://python-poetry.org/) - Dependency management