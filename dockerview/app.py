import logging
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from rich.console import RenderableType
from textual.timer import Timer
from textual.worker import Worker, get_current_worker
import asyncio
from typing import Tuple, Dict, List
import sys
import os
import time
from pathlib import Path

from dockerview.ui.containers import ContainerList
from dockerview.docker_mgmt.manager import DockerManager

def setup_logging():
    """Configure logging to write to file in the user's home directory.

    Creates a .dockerview/logs directory in the user's home directory and sets up
    file-based logging with detailed formatting. Only enables logging if DEBUG mode
    is active.

    Returns:
        Path: Path to the log file, or None if logging is disabled
    """
    # Check if debug mode is enabled (env var must be "1")
    if os.environ.get('DOCKERVIEW_DEBUG') != "1":
        # Disable all logging
        logging.getLogger().setLevel(logging.CRITICAL)
        return None

    log_dir = Path('./logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'dockerview.log'

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s'
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    return log_file

# Initialize logging
log_file = setup_logging()
logger = logging.getLogger('dockerview')
if log_file:  # Only log if debug mode is enabled
    logger.info(f"Logging initialized. Log file: {log_file}")

# Flag to track if we've completed one refresh cycle in debug mode
DEBUG_REFRESH_COMPLETED = False

class ErrorDisplay(Static):
    """A widget that displays error messages with error styling.

    The widget is hidden when there is no error message to display.
    """

    DEFAULT_CSS = """
    ErrorDisplay {
        background: $error;
        color: $text;
        padding: 0 2;
        height: auto;
        display: none;
    }
    """

    def update(self, renderable: RenderableType) -> None:
        """Update the error message and visibility state.

        Args:
            renderable: The error message to display
        """
        super().update(renderable)
        self.styles.display = "block" if renderable else "none"

class Instructions(Static):
    """A widget that displays usage instructions."""

    DEFAULT_CSS = """
    Instructions {
        background: $surface-darken-2;
        color: $text-muted;
        padding: 0 1 1 1;
        height: auto;
        text-align: left;
    }
    """

    def __init__(self):
        instructions = (
            "• To follow logs for a docker compose stack:   docker compose -f <STACK_CONFIG_FILE> logs -f\n"
            "• To follow logs for a container:              docker logs -f <CONTAINER_ID>\n"
            "• To stop a docker compose stack:              docker compose -p <PROJECT_NAME> stop\n"
            "• To start a docker compose stack:             docker compose -p <PROJECT_NAME> start\n"
        )
        super().__init__(instructions)

class DockerViewApp(App):
    """A Textual TUI application for monitoring Docker containers and stacks."""

    CSS = """
    Screen {
        background: $surface-darken-1;
    }

    Container {
        height: auto;
    }

    Vertical {
        height: auto;
        width: 100%;
        padding: 0 1;
    }

    DataTable {
        background: $surface;
        border: none;
    }

    DataTable > .datatable--header {
        background: $surface;
        color: $text;
        text-style: bold;
        border-bottom: solid $primary-darken-2;
    }

    DataTable > .datatable--cursor {
        background: $primary-darken-3;
        color: $text;
    }

    DataTable:focus > .datatable--cursor {
        background: $primary-darken-2;
        color: $text;
    }

    Header {
        background: $surface-darken-2;
        color: $primary-lighten-2;
        border-bottom: solid $primary-darken-3;
        text-style: bold;
        height: 3;
        padding: 0 1;
    }

    Footer {
        background: $primary-darken-2;
        color: $primary-lighten-2;
        border-top: solid $primary-darken-3;
        text-style: bold;
        height: 2;
        padding: 0 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        """Initialize the application and Docker manager."""
        try:
            super().__init__(driver_class=None)
            self.docker = DockerManager()
            self.container_list: ContainerList | None = None
            self.error_display: ErrorDisplay | None = None
            self.refresh_timer: Timer | None = None
            self._current_worker: Worker | None = None
            self._refresh_count = 0
        except Exception as e:
            logger.error(f"Error during initialization: {str(e)}", exc_info=True)
            raise

    def compose(self) -> ComposeResult:
        """Create the application's widget hierarchy.

        Returns:
            ComposeResult: The composed widget tree
        """
        try:
            yield Header()
            yield Instructions()
            with Container():
                with Vertical():
                    error = ErrorDisplay()
                    error.id = "error"
                    yield error
                    container_list = ContainerList()
                    container_list.id = "containers"
                    yield container_list
            yield Footer()
        except Exception as e:
            logger.error(f"Error during composition: {str(e)}", exc_info=True)
            raise

    def on_mount(self) -> None:
        """Set up the application after widgets are mounted.

        Initializes the container list, error display, and starts the auto-refresh timer.
        """
        try:
            self.title = "Docker Container Monitor"
            # Get references to our widgets after they're mounted using IDs
            self.container_list = self.query_one("#containers", ContainerList)
            self.error_display = self.query_one("#error", ErrorDisplay)
            # Start the auto-refresh timer with a longer interval
            self.refresh_timer = self.set_interval(5.0, self.action_refresh)
            # Trigger initial refresh immediately
            self.call_after_refresh(self.action_refresh)
        except Exception as e:
            logger.error(f"Error during mount: {str(e)}", exc_info=True)
            raise

    def action_quit(self) -> None:
        """Handle the quit action by stopping the refresh timer and exiting."""
        if self.refresh_timer:
            self.refresh_timer.stop()
        self.exit()

    def action_refresh(self) -> None:
        """Trigger an asynchronous refresh of the container list."""
        logger.info("=== REFRESH ACTION TRIGGERED ===")
        try:
            # Use call_after_refresh to ensure we're in the right context
            self.call_after_refresh(self.refresh_containers)
        except Exception as e:
            logger.error(f"Error scheduling refresh: {str(e)}", exc_info=True)

    async def refresh_containers(self) -> None:
        """Refresh the container list asynchronously.

        Fetches updated container and stack information in a background thread,
        then updates the UI with the new data.
        """
        global DEBUG_REFRESH_COMPLETED

        refresh_start = time.time()
        logger.info("[PERF] ====== REFRESH CYCLE STARTED ======")

        if not all([self.container_list, self.error_display]):
            logger.error("Error: Widgets not properly initialized")
            return

        try:
            # Show loading indicator in the title
            self.title = "Docker Container Monitor - Refreshing..."

            # Start the worker but don't block waiting for it
            # Textual's worker pattern will call the function and then process the results
            # when they're ready without blocking the UI
            self._refresh_containers_worker(self._handle_refresh_results)

        except Exception as e:
            logger.error(f"Error during refresh: {str(e)}", exc_info=True)
            self.error_display.update(f"Error refreshing: {str(e)}")

    @work(thread=True)
    def _refresh_containers_worker(self, callback) -> Tuple[Dict, List]:
        """Worker function to fetch container and stack data in a background thread.

        Args:
            callback: Function to call with the results when complete

        Returns:
            Tuple[Dict, List]: A tuple containing:
                - Dict: Mapping of stack names to stack information
                - List: List of container information dictionaries
        """
        start_time = time.time()
        logger.info("[PERF] Starting container data fetch in thread")
        try:
            # Get stacks and containers in the thread
            stacks_start = time.time()
            stacks = self.docker.get_compose_stacks()
            stacks_end = time.time()
            logger.info(f"[PERF] get_compose_stacks took {stacks_end - stacks_start:.3f}s")

            containers_start = time.time()
            containers = self.docker.get_containers()
            containers_end = time.time()
            logger.info(f"[PERF] get_containers took {containers_end - containers_start:.3f}s")

            end_time = time.time()
            logger.info(f"[PERF] Total worker time: {end_time - start_time:.3f}s - Found {len(stacks)} stacks and {len(containers)} containers")

            # Call the callback with the results
            # This will be executed in the main thread after the worker completes
            self.call_from_thread(callback, stacks, containers)

            return stacks, containers
        except Exception as e:
            logger.error(f"Error in refresh worker: {str(e)}", exc_info=True)
            self.call_from_thread(self.error_display.update, f"Error refreshing: {str(e)}")
            return {}, []

    def _handle_refresh_results(self, stacks, containers):
        """Handle the results from the refresh worker when they're ready.

        Args:
            stacks: Dictionary of stack information
            containers: List of container information
        """
        try:
            # Update UI with the results
            if hasattr(self.docker, 'last_error') and self.docker.last_error:
                self.error_display.update(f"Error: {self.docker.last_error}")
            else:
                self.error_display.update("")

            # Schedule the UI update to run asynchronously
            asyncio.create_task(self._update_ui_with_results(stacks, containers))

        except Exception as e:
            logger.error(f"Error handling refresh results: {str(e)}", exc_info=True)
            self.error_display.update(f"Error refreshing: {str(e)}")

    async def _update_ui_with_results(self, stacks, containers):
        """Update the UI with the results from the refresh worker.

        Args:
            stacks: Dictionary of stack information
            containers: List of container information
        """
        global DEBUG_REFRESH_COMPLETED

        ui_update_start = time.time()
        logger.info("[PERF] Starting UI update")

        try:
            # Begin a batch update to prevent UI flickering
            self.container_list.begin_update()

            try:
                # Process all stacks first
                stacks_update_start = time.time()
                for stack_name, stack_info in stacks.items():
                    self.container_list.add_stack(
                        stack_name,
                        stack_info['config_file'],
                        stack_info['running'],
                        stack_info['exited'],
                        stack_info['total']
                    )
                stacks_update_end = time.time()
                logger.info(f"[PERF] Adding {len(stacks)} stacks took {stacks_update_end - stacks_update_start:.3f}s")

                # Process all containers in a single batch
                containers_update_start = time.time()
                # Sort containers by stack to minimize UI updates
                sorted_containers = sorted(containers, key=lambda c: c["stack"])
                for container in sorted_containers:
                    self.container_list.add_container_to_stack(
                        container["stack"],
                        container
                    )
                containers_update_end = time.time()
                logger.info(f"[PERF] Adding {len(containers)} containers took {containers_update_end - containers_update_start:.3f}s")

            finally:
                # Always end the update, even if cancelled
                end_update_start = time.time()
                logger.info("[PERF] Calling end_update()")
                self.container_list.end_update()
                end_update_end = time.time()
                logger.info(f"[PERF] end_update() took {end_update_end - end_update_start:.3f}s")

            ui_update_end = time.time()
            logger.info(f"[PERF] Total UI update time: {ui_update_end - ui_update_start:.3f}s")

            # Update title with summary
            total_running = sum(s['running'] for s in stacks.values())
            total_exited = sum(s['exited'] for s in stacks.values())
            total_stacks = len(stacks)

            # Update the app title with stats
            self.title = f"Docker Container Monitor - {total_stacks} Stacks, {total_running} Running, {total_exited} Exited"

            refresh_end = time.time()
            logger.info(f"[PERF] ====== REFRESH CYCLE COMPLETED in {refresh_end - ui_update_start:.3f}s ======")

            # Increment refresh count
            self._refresh_count += 1

            # Exit after one refresh cycle if in debug mode
            if os.environ.get('DOCKERVIEW_DEBUG') == "1" and not DEBUG_REFRESH_COMPLETED:
                logger.info("Debug mode: Exiting after one refresh cycle")
                DEBUG_REFRESH_COMPLETED = True
                # Use call_later to allow the UI to update before exiting
                self.call_later(self.action_quit)

        except Exception as e:
            logger.error(f"Error during UI update: {str(e)}", exc_info=True)
            self.error_display.update(f"Error updating UI: {str(e)}")

def main():
    """Run the Docker container monitoring application."""
    try:
        app = DockerViewApp()
        app.run()
    except Exception as e:
        logger.error(f"Error running app: {str(e)}", exc_info=True)
        raise

__all__ = ['main', 'DockerViewApp']