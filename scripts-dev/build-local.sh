#!/bin/bash

# Build DockTUI Docker image locally for development testing
# This script builds the image from local source code

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="docktui:local"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Show help
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    echo "Usage: $0"
    echo ""
    echo "Builds DockTUI Docker image locally for development testing."
    echo "The image will be tagged as 'docktui:local'"
    exit 0
fi

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon is not running. Please start Docker.${NC}"
    exit 1
fi

# Build the Docker image
echo -e "${GREEN}Building DockTUI Docker image locally...${NC}"
cd "$PROJECT_DIR"

if docker build -t "$IMAGE_NAME" .; then
    echo -e "${GREEN}✓ Docker image built successfully!${NC}"
    echo -e "${GREEN}Image tagged as: $IMAGE_NAME${NC}"
    echo ""
    echo "To run the locally built image, use:"
    echo "  ./scripts-dev/start-local.sh"
else
    echo -e "${RED}Failed to build Docker image${NC}"
    exit 1
fi