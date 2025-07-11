#!/bin/bash

# Start script for DockTUI - pulls and runs from Docker Hub
# This script pulls the latest DockTUI image from Docker Hub and runs it

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
DEBUG_MODE=false
UPDATE=false
VERSION="latest"
HELP=false
SKIP_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--debug)
            DEBUG_MODE=true
            shift
            ;;
        -u|--update)
            UPDATE=true
            shift
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -h|--help)
            HELP=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Show help if requested
if [[ "$HELP" == true ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Run DockTUI from Docker Hub image."
    echo ""
    echo "Options:"
    echo "  -d, --debug           Enable debug mode with detailed logging"
    echo "  -u, --update          Force pull the latest image"
    echo "  -v, --version TAG     Use specific version tag (default: latest)"
    echo "  -h, --help            Show this help message"
    echo "  --skip-tests          Skip Docker socket connectivity tests"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run latest version"
    echo "  $0 -d                 # Run with debug logging"
    echo "  $0 -u                 # Update to latest version"
    echo "  $0 -v 1.0.0          # Run specific version"
    echo ""
    echo "Notes for macOS users:"
    echo "  - For Colima: Ensure 'docker context use colima' is set"
    echo "  - For Docker Desktop: Should work out of the box"
    echo "  - Mouse support: If mouse doesn't work in iTerm2, check Preferences > Profiles > Terminal"
    echo "  - Hold Option/Alt key to temporarily disable mouse reporting for text selection"
    exit 0
fi

# Configuration
IMAGE_NAME="docktui:local"
CONTAINER_NAME="docktui-app"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE=""
LOG_DIR="${SCRIPT_DIR}/logs"

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon is not running. Please start Docker.${NC}"
    exit 1
fi

# Detect OS and set Docker socket path accordingly
DOCKER_SOCKET="/var/run/docker.sock"
DOCKER_SOCKET_SOURCE=""  # Track the actual source socket for macOS
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS - Check for various Docker socket locations
    if [[ -S "$HOME/.colima/default/docker.sock" ]]; then
        # Colima socket location
        DOCKER_SOCKET_SOURCE="$HOME/.colima/default/docker.sock"
        DOCKER_SOCKET="/var/run/docker.sock"
    elif [[ -S "$HOME/.colima/docker.sock" ]]; then
        # Alternative Colima socket location
        DOCKER_SOCKET_SOURCE="$HOME/.colima/docker.sock"
        DOCKER_SOCKET="/var/run/docker.sock"
    elif [[ -S "$HOME/.docker/run/docker.sock" ]]; then
        # Docker Desktop socket location
        DOCKER_SOCKET_SOURCE="$HOME/.docker/run/docker.sock"
        DOCKER_SOCKET="/var/run/docker.sock"
    elif [[ -S "/var/run/docker.sock" ]]; then
        # Standard location (often a symlink on macOS)
        # For Docker Desktop on macOS, we need to use the special mount
        DOCKER_SOCKET_SOURCE="/var/run/docker.sock"
        DOCKER_SOCKET="/var/run/docker.sock"
    else
        echo -e "${RED}Error: Cannot find Docker socket. Is Docker daemon running?${NC}"
        echo -e "${YELLOW}Tip: For Docker Desktop, make sure it's running.${NC}"
        echo -e "${YELLOW}     For Colima, run: colima status${NC}"
        exit 1
    fi
else
    # Linux/WSL - Use standard socket location
    DOCKER_SOCKET_SOURCE="/var/run/docker.sock"
fi

# Verify socket exists and is accessible
if [[ -n "$DOCKER_SOCKET_SOURCE" ]] && [[ ! -S "$DOCKER_SOCKET_SOURCE" ]]; then
    echo -e "${RED}Error: Docker socket not found at $DOCKER_SOCKET_SOURCE${NC}"
    exit 1
elif [[ -z "$DOCKER_SOCKET_SOURCE" ]] && [[ ! -S "$DOCKER_SOCKET" ]]; then
    echo -e "${RED}Error: Docker socket not found at $DOCKER_SOCKET${NC}"
    exit 1
fi

# Pull the image if update requested or image doesn't exist
if [[ "$UPDATE" == true ]] || ! docker image inspect "$IMAGE_NAME" &> /dev/null 2>&1; then
    echo -e "${GREEN}Pulling DockTUI image from Docker Hub...${NC}"
    if ! docker pull "$IMAGE_NAME"; then
        echo -e "${RED}Failed to pull Docker image${NC}"
        echo -e "${YELLOW}Check your internet connection or try a different version with -v${NC}"
        exit 1
    fi
fi

# Find configuration file
if [[ -f "$SCRIPT_DIR/DockTUI.yaml" ]]; then
    CONFIG_FILE="$SCRIPT_DIR/DockTUI.yaml"
elif [[ -f "$HOME/.config/DockTUI/DockTUI.yaml" ]]; then
    CONFIG_FILE="$HOME/.config/DockTUI/DockTUI.yaml"
fi

# Clean up any existing container
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Prepare Docker run command
DOCKER_CMD="docker run --rm"
DOCKER_CMD="$DOCKER_CMD --name $CONTAINER_NAME"
DOCKER_CMD="$DOCKER_CMD -it"  # Interactive and TTY for terminal UI

# Handle Docker socket mounting based on OS
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS - Always mount /var/run/docker.sock (the VM's socket)
    # This should work for both Docker Desktop and Colima
    DOCKER_CMD="$DOCKER_CMD -v /var/run/docker.sock:/var/run/docker.sock"

    # For Colima, we also need to ensure the socket permissions are correct
    if [[ "$DOCKER_SOCKET_SOURCE" =~ \.colima ]]; then
        DOCKER_CMD="$DOCKER_CMD --group-add 0"  # Add root group for socket access
    fi
else
    # Linux/WSL - Standard socket mounting
    DOCKER_CMD="$DOCKER_CMD -v $DOCKER_SOCKET:/var/run/docker.sock"
fi

DOCKER_CMD="$DOCKER_CMD -v /:/host:ro"  # Mount entire filesystem read-only for compose files
DOCKER_CMD="$DOCKER_CMD -v $HOME:$HOME:ro"  # Mount home directory for better compatibility
DOCKER_CMD="$DOCKER_CMD -w /host$(pwd)"  # Set working directory to current directory

# Create logs directory on host if it doesn't exist (for debug mode)
if [[ "$DEBUG_MODE" == true ]]; then
    mkdir -p "$LOG_DIR"
fi

# Force the Docker host path for clients inside the container
# This is often necessary for Colima/macOS to resolve the proxied socket correctly.
DOCKER_CMD="$DOCKER_CMD -e DOCKER_HOST=unix:///var/run/docker.sock"

# Pass TERM environment variable for proper terminal capabilities (including mouse support)
# This is crucial for mouse events to work properly in terminal applications
if [[ -n "$TERM" ]]; then
    DOCKER_CMD="$DOCKER_CMD -e TERM=$TERM"
else
    # Fallback to xterm-256color which supports both colors and mouse events
    DOCKER_CMD="$DOCKER_CMD -e TERM=xterm-256color"
fi

# Add config file mount if found
if [[ -n "$CONFIG_FILE" ]]; then
    DOCKER_CMD="$DOCKER_CMD -v $CONFIG_FILE:/config/DockTUI.yaml:ro"
    DOCKER_CMD="$DOCKER_CMD -e DOCKTUI_CONFIG=/config/DockTUI.yaml"
fi

# Add log directory mount and environment if in debug mode
if [[ "$DEBUG_MODE" == true ]]; then
    # Create a writable logs directory inside container at /app/logs
    # and mount the host logs directory there for easy access
    DOCKER_CMD="$DOCKER_CMD -v $LOG_DIR:/app/logs:rw"
    # Set DOCKTUI_LOG_DIR to tell the app to use /app/logs instead of ./logs
    DOCKER_CMD="$DOCKER_CMD -e DOCKTUI_LOG_DIR=/app/logs"
    DOCKER_CMD="$DOCKER_CMD -e DOCKTUI_DEBUG=1"
    echo -e "${YELLOW}Debug mode enabled. Logs will be written to: $LOG_DIR${NC}"
fi

# Handle user permissions based on OS
if [[ "$(uname)" == "Darwin" ]]; then
    # On macOS, run as root to access Docker socket
    DOCKER_CMD="$DOCKER_CMD --user root"
    # Add privileged flag for Docker Desktop socket access on macOS
    if [[ "$DOCKER_SOCKET_SOURCE" == "/var/run/docker.sock" ]] || [[ "$DOCKER_SOCKET_SOURCE" == "$HOME/.docker/run/docker.sock" ]]; then
        DOCKER_CMD="$DOCKER_CMD --privileged"
        echo -e "${YELLOW}Note: Using privileged mode for Docker Desktop socket access${NC}"
    elif [[ "$DOCKER_SOCKET_SOURCE" =~ \.colima ]]; then
        DOCKER_CMD="$DOCKER_CMD --privileged"
        echo -e "${YELLOW}Note: Using privileged mode for Colima socket access${NC}"
    fi
else
    # On Linux, use host user for proper file permissions
    DOCKER_CMD="$DOCKER_CMD --user $(id -u):$(id -g)"
    # Add Docker group if available (for socket access)
    if getent group docker &>/dev/null; then
        DOCKER_CMD="$DOCKER_CMD --group-add $(getent group docker | cut -d: -f3)"
    fi
fi

# Add clipboard support through file sharing
CLIPBOARD_FILE="/tmp/docktui_clipboard_$$"
touch "$CLIPBOARD_FILE"
chmod 666 "$CLIPBOARD_FILE"
DOCKER_CMD="$DOCKER_CMD -v $CLIPBOARD_FILE:/tmp/clipboard:rw"
DOCKER_CMD="$DOCKER_CMD -e DOCKTUI_CLIPBOARD_FILE=/tmp/clipboard"

# Show clipboard file info in debug mode only
if [[ "$DEBUG_MODE" == true ]]; then
    echo -e "${YELLOW}Clipboard file: $CLIPBOARD_FILE${NC}"
    if [[ "$(uname)" == "Darwin" ]]; then
        echo -e "${YELLOW}Docker socket detected at: $DOCKER_SOCKET_SOURCE${NC}"
        echo -e "${YELLOW}Mounting VM socket: /var/run/docker.sock -> /var/run/docker.sock${NC}"
    else
        echo -e "${YELLOW}Docker socket: $DOCKER_SOCKET${NC}"
    fi
    echo -e "${YELLOW}Terminal type (TERM): ${TERM:-not set}${NC}"
    # Test socket connectivity
    if docker version &> /dev/null; then
        echo -e "${GREEN}Host Docker connection: OK${NC}"
    else
        echo -e "${RED}Host Docker connection: FAILED${NC}"
    fi
fi

# Start clipboard monitor in background
monitor_clipboard() {
    local last_content=""
    while [ -f "$CLIPBOARD_FILE" ]; do
        if [ -r "$CLIPBOARD_FILE" ]; then
            current_content=$(cat "$CLIPBOARD_FILE" 2>/dev/null || true)
            if [ -n "$current_content" ] && [ "$current_content" != "$last_content" ]; then
                # Copy to host clipboard
                if command -v pbcopy &> /dev/null; then
                    echo -n "$current_content" | pbcopy
                elif command -v xclip &> /dev/null; then
                    echo -n "$current_content" | xclip -selection clipboard
                elif command -v xsel &> /dev/null; then
                    echo -n "$current_content" | xsel --clipboard --input
                elif command -v wl-copy &> /dev/null; then
                    echo -n "$current_content" | wl-copy
                fi
                last_content="$current_content"
            fi
        fi
        sleep 0.1
    done
}

# Start clipboard monitor
monitor_clipboard &
MONITOR_PID=$!

# Cleanup function
cleanup() {
    kill $MONITOR_PID 2>/dev/null || true
    rm -f "$CLIPBOARD_FILE" 2>/dev/null || true
}
trap cleanup EXIT

# Test Docker socket connectivity before running main app
echo -e "${GREEN}Testing Docker socket connectivity...${NC}"
TEST_CMD="$DOCKER_CMD --entrypoint /bin/sh"
if ! $TEST_CMD "$IMAGE_NAME" -c "ls -la /var/run/docker.sock && echo 'Socket found' || echo 'Socket NOT found'"; then
    echo -e "${RED}Failed to test Docker socket${NC}"
fi

# Run the container
echo -e "${GREEN}Starting DockTUI...${NC}"
if [[ "$DEBUG_MODE" == true ]]; then
    echo -e "${YELLOW}Docker command: $DOCKER_CMD \"$IMAGE_NAME\"${NC}"
fi

if ! $DOCKER_CMD "$IMAGE_NAME"; then
    EXIT_CODE=$?
    echo -e "${RED}DockTUI exited with error code: $EXIT_CODE${NC}"

    # Provide helpful error messages for common issues
    if [[ "$(uname)" == "Darwin" ]]; then
        echo -e "${YELLOW}Troubleshooting tips for macOS:${NC}"
        echo -e "${YELLOW}1. Verify Colima is running:${NC}"
        echo -e "   colima status"
        echo -e "${YELLOW}2. Check Docker context:${NC}"
        echo -e "   docker context ls"
        echo -e "${YELLOW}3. Test Docker from host:${NC}"
        echo -e "   docker ps"
        echo -e "${YELLOW}4. Ensure Docker context is set to Colima:${NC}"
        echo -e "   docker context use colima"
        echo -e "${YELLOW}5. Try restarting Colima:${NC}"
        echo -e "   colima stop && colima start"
        echo -e "${YELLOW}6. If using virtiofs, try sshfs mount type:${NC}"
        echo -e "   colima stop && colima start --mount-type sshfs"
        echo -e "${YELLOW}7. Mouse not working? Check your terminal:${NC}"
        echo -e "   - iTerm2: Enable mouse reporting in Preferences > Profiles > Terminal"
        echo -e "   - Try running: export TERM=xterm-256color"
        echo -e "   - Hold Option/Alt key while clicking to bypass mouse reporting"
    fi
fi

# Return to normal terminal
echo -e "${GREEN}DockTUI exited. Returning to normal terminal.${NC}"
