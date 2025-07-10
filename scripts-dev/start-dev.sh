#!/bin/bash

# Start script for DockTUI
# This script activates the poetry environment and runs the application

set -e  # Exit on any error

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
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Show help if requested
if [[ "$HELP" == true ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -d, --debug    Enable debug mode with detailed logging"
    echo "  -h, --help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Run normally"
    echo "  $0 -d           # Run with debug logging enabled"
    exit 0
fi

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Error: Poetry is not installed. Please install poetry first:"
    echo "  pip install poetry"
    exit 1
fi

# Check if pyproject.toml exists
if [[ ! -f "pyproject.toml" ]]; then
    echo "Error: pyproject.toml not found. Make sure you're in the DockTUI directory."
    exit 1
fi

# Install dependencies if needed
echo "Ensuring dependencies are installed..."
poetry install

# Set debug environment variable if requested
if [[ "$DEBUG_MODE" == true ]]; then
    echo "Starting DockTUI in debug mode..."
    echo "Debug logs will be written to ./logs/DockTUI.log"
    export DOCKTUI_DEBUG=1
else
    echo "Starting DockTUI..."
fi

# Run the application using poetry
poetry run python -m DockTUI