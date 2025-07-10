#!/bin/bash

# Run DockTUI using locally built Docker image
# This script runs the 'docktui:local' image built by build-local.sh

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
DEBUG_MODE=false
HELP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--debug)
            DEBUG_MODE=true
            shift
            ;;
        -h|--help)
            HELP=true
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
    echo "Run DockTUI using locally built Docker image."
    echo "Build the image first with: ./scripts-dev/build-local.sh"
    echo ""
    echo "Options:"
    echo "  -d, --debug    Enable debug mode with detailed logging"
    echo "  -h, --help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Run normally"
    echo "  $0 -d           # Run with debug logging"
    exit 0
fi

# Configuration
IMAGE_NAME="docktui:local"
CONTAINER_NAME="docktui-app"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE=""
LOG_DIR="${PROJECT_DIR}/logs"

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon is not running. Please start Docker.${NC}"
    exit 1
fi

# Check if local image exists
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    echo -e "${RED}Error: Local image '$IMAGE_NAME' not found.${NC}"
    echo -e "${YELLOW}Build it first with: ./scripts-dev/build-local.sh${NC}"
    exit 1
fi

# Find configuration file
if [[ -f "$PROJECT_DIR/DockTUI.yaml" ]]; then
    CONFIG_FILE="$PROJECT_DIR/DockTUI.yaml"
elif [[ -f "$HOME/.config/DockTUI/DockTUI.yaml" ]]; then
    CONFIG_FILE="$HOME/.config/DockTUI/DockTUI.yaml"
fi

# Create logs directory if in debug mode
if [[ "$DEBUG_MODE" == true ]]; then
    mkdir -p "$LOG_DIR"
fi

# Clean up any existing container
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Prepare Docker run command
DOCKER_CMD="docker run --rm"
DOCKER_CMD="$DOCKER_CMD --name $CONTAINER_NAME"
DOCKER_CMD="$DOCKER_CMD -it"  # Interactive and TTY for terminal UI
DOCKER_CMD="$DOCKER_CMD -v /var/run/docker.sock:/var/run/docker.sock"  # Docker socket
DOCKER_CMD="$DOCKER_CMD -v /:/host:ro"  # Mount entire filesystem read-only for compose files
DOCKER_CMD="$DOCKER_CMD -v $HOME:$HOME:ro"  # Mount home directory for better compatibility
DOCKER_CMD="$DOCKER_CMD -w /host$(pwd)"  # Set working directory to current directory

# Add config file mount if found
if [[ -n "$CONFIG_FILE" ]]; then
    DOCKER_CMD="$DOCKER_CMD -v $CONFIG_FILE:/config/DockTUI.yaml:ro"
    DOCKER_CMD="$DOCKER_CMD -e DOCKTUI_CONFIG=/config/DockTUI.yaml"
fi

# Add log directory mount if in debug mode
if [[ "$DEBUG_MODE" == true ]]; then
    DOCKER_CMD="$DOCKER_CMD -v $LOG_DIR:/app/logs"
    DOCKER_CMD="$DOCKER_CMD -e DOCKTUI_DEBUG=1"
    echo -e "${YELLOW}Debug mode enabled. Logs will be written to: $LOG_DIR${NC}"
fi

# Add user/group mapping for proper file permissions
DOCKER_CMD="$DOCKER_CMD --user $(id -u):$(id -g)"

# Add Docker group if available (for socket access)
if getent group docker &>/dev/null; then
    DOCKER_CMD="$DOCKER_CMD --group-add $(getent group docker | cut -d: -f3)"
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

# Run the container
echo -e "${GREEN}Starting DockTUI (local build)...${NC}"
$DOCKER_CMD "$IMAGE_NAME"

# Return to normal terminal
echo -e "${GREEN}DockTUI exited. Returning to normal terminal.${NC}"