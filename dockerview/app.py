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
from pathlib import Path

from dockerview.ui.containers import ContainerList
from dockerview.docker_mgmt.manager import DockerManager

def setup_logging():
    """Configure logging to write to file in the user's home directory.

    Creates a .dockerview/logs directory in the user's home directory and sets up
    file-based logging with detailed formatting.

    Returns:
        Path: Path to the log file
    """
    log_dir = Path.home() / '.dockerview' / 'logs'
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
logger.info(f"Logging initialized. Log file: {log_file}")

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
        padding: 0 2;
    }

    Footer {
        background: $primary-darken-2;
        color: $primary-lighten-2;
        border-top: solid $primary-darken-3;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Manual Refresh"),
    ]

    def __init__(self):
        """Initialize the application and Docker manager."""
        logger.info("Starting DockerViewApp initialization")
        try:
            super().__init__(driver_class=None)
            logger.info("After super().__init__()")
            self.docker = DockerManager()
            logger.info("Created DockerManager")
            self.container_list: ContainerList | None = None
            self.error_display: ErrorDisplay | None = None
            self.refresh_timer: Timer | None = None
            self._current_worker: Worker | None = None
            logger.info("Finished DockerViewApp initialization")
        except Exception as e:
            logger.error(f"Error during initialization: {str(e)}", exc_info=True)
            raise

    def compose(self) -> ComposeResult:
        """Create the application's widget hierarchy.

        Returns:
            ComposeResult: The composed widget tree
        """
        logger.info("Starting composition")
        try:
            yield Header()
            logger.info("Added header")
            with Container():
                with Vertical():
                    error = ErrorDisplay()
                    error.id = "error"
                    yield error
                    logger.info("Added error display")
                    logger.info("About to create ContainerList")
                    container_list = ContainerList()
                    logger.info("Created ContainerList")
                    container_list.id = "containers"
                    yield container_list
                    logger.info("Added container list")
            yield Footer()
            logger.info("Added footer")
            logger.info("Finished composition")
        except Exception as e:
            logger.error(f"Error during composition: {str(e)}", exc_info=True)
            raise

    def on_mount(self) -> None:
        """Set up the application after widgets are mounted.

        Initializes the container list, error display, and starts the auto-refresh timer.
        """
        logger.info("Starting mount")
        try:
            self.title = "Docker Container Monitor"
            # Get references to our widgets after they're mounted using IDs
            self.container_list = self.query_one("#containers", ContainerList)
            self.error_display = self.query_one("#error", ErrorDisplay)
            # Start the auto-refresh timer with a longer interval
            self.refresh_timer = self.set_interval(5.0, self.action_refresh)
            # Trigger initial refresh immediately
            self.call_after_refresh(self.action_refresh)
            logger.info("Finished mount")
        except Exception as e:
            logger.error(f"Error during mount: {str(e)}", exc_info=True)
            raise

    async def on_load(self) -> None:
        """Called when the app is first loaded."""
        logger.info("App load event triggered")

    async def on_show(self) -> None:
        """Called when the app screen is shown."""
        logger.info("App screen is now visible")

    async def on_ready(self) -> None:
        """Called when the app is ready to start processing events."""
        logger.info("App is ready to process events")
        try:
            # Force a screen update
            self.refresh(layout=True)
            logger.info("Forced initial screen refresh")
        except Exception as e:
            logger.error(f"Error in on_ready: {str(e)}", exc_info=True)
            raise

    def watch_app_state(self, old_state: str, new_state: str) -> None:
        """Watch for app state changes."""
        logger.info(f"App state changed from {old_state} to {new_state}")

    def action_quit(self) -> None:
        """Handle the quit action by stopping the refresh timer and exiting."""
        if self.refresh_timer:
            self.refresh_timer.stop()
        self.exit()

    def action_refresh(self) -> None:
        """Trigger an asynchronous refresh of the container list."""
        logger.info("Refresh action triggered")
        try:
            # Use call_after_refresh to ensure we're in the right context
            self.call_after_refresh(self.refresh_containers)
            logger.info("Scheduled refresh_containers call")
        except Exception as e:
            logger.error(f"Error scheduling refresh: {str(e)}", exc_info=True)

    @work(thread=True)
    def _refresh_containers_worker(self) -> Tuple[Dict, List]:
        """Worker function to fetch container and stack data in a background thread.

        Returns:
            Tuple[Dict, List]: A tuple containing:
                - Dict: Mapping of stack names to stack information
                - List: List of container information dictionaries
        """
        logger.info("Starting container refresh in thread")
        try:
            # Get stacks and containers in the thread
            logger.debug("About to fetch compose stacks")
            stacks = self.docker.get_compose_stacks()
            logger.debug(f"Got stacks: {stacks}")

            logger.debug("About to fetch containers")
            containers = self.docker.get_containers()
            logger.debug(f"Got containers: {containers}")

            logger.info(f"Worker completed successfully - Found {len(stacks)} stacks and {len(containers)} containers")
            return stacks, containers
        except Exception as e:
            logger.error(f"Error in refresh worker: {str(e)}", exc_info=True)
            return {}, []

    async def refresh_containers(self) -> None:
        """Refresh the container list asynchronously.

        Fetches updated container and stack information in a background thread,
        then updates the UI with the new data.
        """
        logger.info("Starting container refresh")
        if not all([self.container_list, self.error_display]):
            logger.error("[REFRESH] Error: Widgets not properly initialized")
            return

        try:
            # Run the refresh in a thread worker
            logger.info("[REFRESH] Creating new worker")
            worker = self._refresh_containers_worker()
            logger.info("[REFRESH] Worker created, waiting for results")

            try:
                stacks, containers = await worker.wait()
                logger.info(f"[REFRESH] Got results from worker - Stacks: {len(stacks)}, Containers: {len(containers)}")
            except Exception as worker_error:
                logger.error(f"[REFRESH] Worker failed: {str(worker_error)}", exc_info=True)
                raise

            # Update UI with the results
            if hasattr(self.docker, 'last_error') and self.docker.last_error:
                logger.error(f"[REFRESH] Docker error: {self.docker.last_error}")
                self.error_display.update(f"Error: {self.docker.last_error}")
            else:
                self.error_display.update("")

            # Start batch update
            logger.info("[REFRESH] Beginning container list update")
            self.container_list.begin_update()

            try:
                # Add stacks first
                for stack_name, stack_info in stacks.items():
                    logger.info(f"[REFRESH] Adding stack: {stack_name}")
                    self.container_list.add_stack(
                        stack_name,
                        stack_info['config_file'],
                        stack_info['running'],
                        stack_info['exited'],
                        stack_info['total']
                    )
                    # Small yield to keep UI responsive
                    await asyncio.sleep(0)

                # Add containers to their respective stacks
                logger.info(f"[REFRESH] Adding {len(containers)} containers to stacks")
                for container in containers:
                    logger.info(f"[REFRESH] Adding container to stack {container['stack']}: {container.get('name', 'unnamed')}")
                    self.container_list.add_container_to_stack(
                        container["stack"],
                        container
                    )
                    # Small yield to keep UI responsive
                    await asyncio.sleep(0)

            finally:
                # Always end the update, even if cancelled
                logger.info("[REFRESH] Ending container list update")
                self.container_list.end_update()

            # Update title with summary
            total_running = sum(s['running'] for s in stacks.values())
            total_exited = sum(s['exited'] for s in stacks.values())
            total_stacks = len(stacks)

            logger.info(f"[REFRESH] Updating title - Stacks: {total_stacks}, Running: {total_running}, Exited: {total_exited}")
            # Update the app title with stats
            self.title = f"Docker Container Monitor - {total_stacks} Stacks, {total_running} Running, {total_exited} Exited"

        except Exception as e:
            logger.error(f"[REFRESH] Error during refresh: {str(e)}", exc_info=True)
            self.error_display.update(f"Error refreshing: {str(e)}")

def main():
    """Run the Docker container monitoring application."""
    logger.info("Starting application")
    try:
        app = DockerViewApp()
        logger.info("Created DockerViewApp instance")
        logger.info("About to run app")
        app.run()
        logger.info("App.run() completed")
    except Exception as e:
        logger.error(f"Error running app: {str(e)}", exc_info=True)
        raise

__all__ = ['main', 'DockerViewApp']