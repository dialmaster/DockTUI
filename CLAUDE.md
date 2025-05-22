# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Installation
```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run the application
python -m dockerview
```

### Development Tools
```bash
# Code formatting
black .

# Import sorting
isort .

# Testing
pytest
```

### Debug Mode
Enable debug mode for detailed logging:
```bash
export DOCKERVIEW_DEBUG=1
python -m dockerview
```
Logs are written to `./logs/dockerview.log` when debug mode is enabled.

## Architecture Overview

dockerview is a terminal-based Docker monitoring tool built with Python and Textual. The architecture follows a layered approach:

### Core Components

**DockerViewApp** (dockerview/app.py): Main Textual application that orchestrates the UI and manages the refresh cycle. Handles keyboard bindings for container/stack commands (start/stop/restart).

**ContainerList** (dockerview/ui/containers.py): The main UI component that displays containers grouped by Docker Compose stacks. Features collapsible stack headers and real-time container information tables. Uses DataTable widgets for container display and StackHeader widgets for collapsible sections.

**DockerManager** (dockerview/docker_mgmt/manager.py): Handles all Docker API interactions. Key performance optimization: uses `docker stats --no-stream` subprocess call to get stats for all containers in a single batch operation rather than individual API calls per container.

### Key Design Patterns

**Batch Updates**: The UI uses `begin_update()` and `end_update()` methods to prevent flickering during data refreshes. All container data is fetched in background threads and applied to the UI in batches.

**Selection Management**: Tracks both container and stack selections with detailed status bar updates. Selection state is preserved across UI refreshes.

**Stack Grouping**: Containers are automatically grouped by Docker Compose project using container labels (`com.docker.compose.project`).

### Performance Considerations

- Container stats are fetched using a single subprocess call rather than individual Docker API calls
- UI updates are batched to prevent flickering
- Background threading for data fetching to keep UI responsive
- Extensive logging for performance monitoring when debug mode is enabled

### State Management

The application maintains several key state variables:
- `selected_item`: Currently selected container or stack
- `expanded_stacks`: Set of expanded stack names
- `container_rows`: Maps container IDs to their table positions
- Selection state is preserved across refreshes

### Docker Integration

Uses docker-py library for container management and subprocess calls for performance-critical stats collection. Supports both individual container commands and Docker Compose stack operations.