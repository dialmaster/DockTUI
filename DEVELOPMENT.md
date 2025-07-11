# Development Guide

This guide covers the technical architecture, development setup, and contribution guidelines for DockTUI.

## Architecture

DockTUI is built using Python with the following core components:

### UI Layer (Textual)
- Main dashboard view with collapsible stack sections
- Container detail rows with resource usage information
- Rich log viewer with syntax highlighting and smart formatting
- Status bar for selection information
- Error display for showing error messages
- Interactive controls for log filtering and auto-follow
- Modal dialogs for actions and confirmations
- JSON/XML expansion support for structured data viewing

### Docker Integration Layer (docker-py SDK)
- Direct SDK integration without Docker CLI dependency
- Real-time container statistics collection using concurrent threading
- Docker Compose stack detection and grouping
- Container port mapping display
- Non-blocking container and stack operations (start/stop/restart/recreate)
- Real-time log streaming with configurable time ranges and tail limits
- Event monitoring for container state changes
- Thread-safe concurrent operations for improved performance
- Volume management with usage tracking and container associations
- Non-blocking image and volume removal operations

### State Management
- Container and stack state tracking
- User interface state (selections, expanded/collapsed sections)
- Performance optimizations for handling many containers

### Data Flow

```
Docker Engine <-> docker-py SDK <-> DockerManager (with threading) <-> UI Components
```

### Key Components

- **DockTUIApp** (`DockTUI/app.py`): Main Textual application class coordinating UI and actions
  - Uses **DockerActions** mixin for Docker operation handling
  - Uses **RefreshActions** mixin for UI refresh management
  - Provides command palette integration
- **ContainerList** (`DockTUI/ui/containers.py`): Navigable list of containers with real-time stats
  - Uses specialized managers for different Docker resources (images, networks, stacks, volumes)
  - Volumes displayed in table format with usage tracking and container associations
- **DockerManager** (`DockTUI/docker_mgmt/manager.py`): Handles direct Docker SDK integration with concurrent operations:
  - Thread-based non-blocking container operations
  - Parallel stats collection for all containers
  - Multi-stream log aggregation for stacks
- **LogPane** (`DockTUI/ui/viewers/log_pane.py`): Advanced real-time log viewer with:
  - Rich text rendering with smart syntax highlighting
  - Automatic pattern detection (timestamps, log levels, IPs, URLs, etc.)
  - JSON/XML expansion support (double-click to expand/collapse)
  - Virtual scrolling and lazy parsing for performance
  - Background pre-parsing thread for smooth scrolling
  - LRU cache for rendered log segments
  - Session-based log streaming to prevent duplicates
  - **Mark Log Position** feature with timestamped markers
  - Dynamic header showing container state
- **Action Mixins**: Modular action handling
  - **DockerActions**: Container/stack/volume/image operations with context awareness
  - **RefreshActions**: UI refresh and data update management
- **VolumeManager** (`DockTUI/ui/managers/volume_manager.py`): Volume display and operations:
  - Table-based UI showing volume details and usage
  - Real-time tracking of containers using each volume
  - Volume removal with safety checks
  - Unused volume pruning with space reclamation display

### Project Structure

```
DockTUI/
├── app.py                      # Main application and UI layout
├── docker_mgmt/               # Docker SDK integration layer
│   ├── manager.py            # Core Docker management
│   ├── log_streamer.py       # Log streaming functionality
│   └── stats_collector.py    # Concurrent stats collection
├── models/                    # Data models
│   └── log_line.py           # LogLine model for structured log representation
├── services/                  # Service layer for specialized functionality
│   ├── log_filter.py         # Log filtering with marker support
│   ├── log_streamer.py       # Log streaming from Docker containers
│   ├── log_parser.py         # Advanced log parsing with pattern detection
│   ├── log_formatter.py      # Main log formatting orchestrator
│   └── log/                  # Log formatting subsystem
│       ├── highlighter/      # Syntax highlighting components
│       │   ├── patterns.py   # Comprehensive pattern library
│       │   ├── smart.py      # Smart formatter with auto-detection
│       │   └── themes.py     # Color themes for log highlighting
│       ├── json_formatter.py # JSON pretty-printing and highlighting
│       └── xml_formatter.py  # XML pretty-printing and highlighting
├── ui/                        # UI components organized by function
│   ├── actions/              # Modular action handlers
│   ├── base/                 # Base classes and interfaces
│   ├── managers/             # Resource managers
│   ├── viewers/              # Content viewers
│   ├── dialogs/              # Modal dialogs
│   └── widgets/              # Reusable UI components
│       ├── rich_log_viewer.py      # Advanced log viewer widget
│       ├── log_renderer.py         # Log rendering engine
│       ├── log_selection_manager.py # Text selection handling
│       ├── mouse_event_handler.py   # Mouse interaction handling
│       ├── virtual_scroll_manager.py # Virtual scrolling implementation
│       └── parsing_coordinator.py   # Background parsing coordination
├── utils/                     # Utility modules
│   ├── clipboard.py          # Cross-platform clipboard support
│   ├── time_utils.py         # Time formatting utilities
│   ├── formatting.py         # Byte size formatting utilities
│   ├── text_processing.py   # Text processing utilities (ANSI stripping)
│   ├── logging.py            # Debug logging setup
│   └── mixins/               # Reusable mixins
│       └── cacheable.py      # Cache invalidation support
└── config.py                  # Configuration management
```

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Docker Engine installed and running
- Poetry (Python package manager)

### Quick Start for Development

```bash
# Clone the repository
git clone https://github.com/dialmaster/DockTUI.git
cd DockTUI

# Run in development mode (automatically handles Poetry setup)
./scripts-dev/start-dev.sh
```

The `scripts-dev/start-dev.sh` script automatically:
- Checks for Poetry installation
- Installs dependencies
- Runs DockTUI in the local Python environment

### Manual Development Setup

```bash
# Install Poetry if not already installed
pip install poetry

# Install dependencies
poetry install

# Install pre-commit hooks (recommended)
poetry run pre-commit install

# Activate the virtual environment
poetry shell

# Run DockTUI
python -m DockTUI
```

### Running in Development

```bash
# Using scripts-dev/start-dev.sh
./scripts-dev/start-dev.sh           # Run normally
./scripts-dev/start-dev.sh -d        # Run with debug logging
./scripts-dev/start-dev.sh -h        # Show help

# Or manually after poetry shell
python -m DockTUI

# With debug logging
export DOCKTUI_DEBUG=1
python -m DockTUI
```

Debug logs are written to `./logs/DockTUI_debug.log`.

### Testing Docker Builds Locally

To test your changes in a Docker container before pushing:

```bash
# Build local Docker image
./scripts-dev/build-local.sh

# Run the locally built image
./scripts-dev/start-local.sh
./scripts-dev/start-local.sh -d  # With debug logging
```

### Development Scripts

All development scripts are in the `scripts-dev/` directory:
- `start-dev.sh` - Run DockTUI with Poetry (Python environment)
- `build-local.sh` - Build Docker image locally for testing
- `start-local.sh` - Run the locally built Docker image

## Code Quality and Testing

DockTUI uses automated tools to maintain code quality:

- **Black**: Code formatting (line length 88)
- **isort**: Import sorting (black profile)
- **pytest**: Unit testing
- **pre-commit**: Git hooks for automatic checks

### Using Make Commands

The project includes a Makefile for common development tasks:

```bash
make help       # Show all available commands
make format     # Auto-format code with black and isort
make lint       # Check code formatting without changes
make test       # Run unit tests
make check      # Run all checks (lint + test) - ALWAYS run before committing
make all        # Format code and run tests
make clean      # Remove cache files
```

### Manual Commands

If you prefer running commands directly:

```bash
# Format code
poetry run black DockTUI/
poetry run isort DockTUI/

# Check formatting
poetry run black --check DockTUI/
poetry run isort --check-only DockTUI/

# Run tests
poetry run pytest
poetry run pytest -v  # Verbose output
poetry run pytest tests/test_config.py  # Run specific test file

# Run pre-commit on all files
poetry run pre-commit run --all-files
```

### Important Development Practices

- **ALWAYS** run `make check` after making ANY code changes
- If `make check` fails, run `make format` to auto-fix formatting issues
- Never commit code without passing `make check`
- Add tests for new features and ensure existing tests pass
- Follow existing code conventions and patterns
- Wait for user confirmation that features work correctly before considering tasks complete

## Contributing Guidelines

### Code Style

1. Code is automatically formatted with black (line length 88)
2. Imports are organized with isort using the black profile
3. Follow existing patterns and conventions in the codebase
4. No unnecessary comments unless explicitly requested
5. Use type hints where appropriate

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat:` - New features (minor version bump)
- `fix:` - Bug fixes (patch version bump)
- `feat!:` or `BREAKING CHANGE:` - Breaking changes (major version bump)
- `refactor:` - Code refactoring
- `docs:` - Documentation updates
- `style:` - Code style changes
- `test:` - Test additions or changes
- `chore:` - Maintenance tasks

### Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes and ensure `make check` passes
3. Add or update tests as needed
4. Update documentation if adding new features
5. Submit a pull request with a clear description

### Design Patterns and Best Practices

#### Reactive Updates
Uses Textual's reactive properties for real-time UI updates

#### Concurrent Operations
All Docker operations use threading for non-blocking UI:
- Container operations (start/stop/restart) run in daemon threads
- Stats collection parallelized across all containers with thread safety
- Log streaming uses session IDs to prevent duplicate messages

#### Mixin Architecture
Separates concerns using mixins for actions and behaviors:
- DockerActions handles all Docker-related operations
- RefreshActions manages UI refresh and data updates
- Enables better testability and code organization

#### Context-Aware Actions
Actions dynamically enable/disable based on selection:
- Can't recreate without compose file
- Can't remove volumes that are in use
- Remove container action only available for stopped/exited containers
- Dynamic footer bindings update based on current selection

#### Lazy Loading and Caching
Performance optimization strategies:
- Configuration loaded on-demand to minimize import-time overhead
- Log lines parsed only when becoming visible
- LRU cache for rendered log segments in RichLogViewer
- Singleton pattern for compiled regex patterns
- Virtual scrolling to handle large log files efficiently

#### Smart Pattern Detection
Automatic detection and highlighting of:
- Log formats and levels
- JSON and XML structures
- Code snippets with language detection
- Network addresses and protocols
- Timestamps in various formats

## CI/CD

GitHub Actions automatically runs on all pull requests and pushes to main:

- Tests on Python 3.12 (minimum supported version)
- Code formatting checks (black and isort)
- Unit test execution
- Coverage reporting with detailed PR comments

All checks must pass before merging pull requests.

## Release Process

See [RELEASING.md](RELEASING.md) for detailed release instructions.

## Advanced Configuration

### Environment Variables

The following environment variables are available for development and debugging:

#### Configuration Overrides
- `DOCKTUI_CONFIG` - Path to custom configuration file
- `DOCKTUI_APP_REFRESH_INTERVAL` - Container refresh rate in seconds
- `DOCKTUI_LOG_MAX_LINES` - Maximum log lines in memory
- `DOCKTUI_LOG_TAIL` - Initial log lines to fetch
- `DOCKTUI_LOG_SINCE` - Time range for logs
- `DOCKTUI_DEBUG` - Enable debug logging (set to 1)

#### Container Support
- `DOCKTUI_IN_CONTAINER` - Set when running in a container
- `DOCKTUI_CLIPBOARD_FILE` - File path for container clipboard sharing

### Performance Considerations

- **Log Viewer Optimizations**:
  - Virtual scrolling renders only visible lines
  - Lazy parsing processes lines on-demand
  - Background thread pre-loads upcoming lines
  - LRU cache stores rendered segments
  - Memory limits prevent excessive resource usage
- **Docker Operations**:
  - Stats collection parallelized across all containers
  - Non-blocking operations ensure UI remains responsive
  - Session-based log streaming prevents duplicate messages
  - Thread pool manages concurrent operations
- **Configuration Tuning**:
  - `log.max_lines` controls memory usage
  - `log.tail` and `log.since` balance loading speed vs. history
  - `app.refresh_interval` adjusts CPU usage

## Debugging Tips

1. Enable debug logging with `DOCKTUI_DEBUG=1`
2. Check `./logs/DockTUI_debug.log` for detailed operation logs
3. Use the command palette (Ctrl+\) to test individual actions
4. Monitor the status bar for action availability and context

## Known Technical Limitations

- Must run on the same filesystem as Docker Compose files
- Requires Docker Compose v2 (`docker compose` command)
- Remote Docker daemon monitoring not currently supported
- Performance may degrade with hundreds of containers

## Getting Help

- Check existing issues on GitHub
- Review debug logs for error details
- Ensure Docker daemon is running and accessible
- Verify file permissions for Docker socket access