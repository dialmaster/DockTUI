import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Tuple

from rich.console import RenderableType
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Footer, Header, Static
from textual.worker import Worker

from dockerview.config import config
from dockerview.docker_mgmt.manager import DockerManager
from dockerview.ui.containers import ContainerList, SelectionChanged
from dockerview.ui.dialogs.confirm_modal import ComposeDownModal
from dockerview.ui.viewers.log_pane import LogPane


def setup_logging():
    """Configure logging to write to file in the user's home directory.

    Creates a .dockerview/logs directory in the user's home directory and sets up
    file-based logging with detailed formatting. Only enables logging if DEBUG mode
    is active.

    Returns:
        Path: Path to the log file, or None if logging is disabled
    """
    # Check if debug mode is enabled (env var must be "1")
    if os.environ.get("DOCKERVIEW_DEBUG") != "1":
        # Disable all logging
        logging.getLogger().setLevel(logging.CRITICAL)
        return None

    log_dir = Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "dockerview.log"

    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s"
    )

    # Use RotatingFileHandler to limit log file size to 20MB with 2 backup files
    file_handler = RotatingFileHandler(
        log_file, maxBytes=20 * 1024 * 1024, backupCount=2  # 20MB
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    return log_file


# Initialize logging
log_file = setup_logging()
logger = logging.getLogger("dockerview")
if log_file:  # Only log if debug mode is enabled
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


class StatusBar(Static):
    """A widget that displays the current selection status at the bottom of the screen."""

    DEFAULT_CSS = """
    StatusBar {
        background: $panel;
        color: $text-primary;
        height: 3;
        dock: bottom;
        padding-top: 0;
        margin-top: 0;
        text-align: center;
        text-style: bold;
    }
    """

    def __init__(self):
        """Initialize the status bar with an empty message."""
        from rich.style import Style
        from rich.text import Text

        no_selection_text = Text("No selection", Style(color="white", bold=True))
        super().__init__(no_selection_text)

    def update(self, message: str) -> None:
        """Update the status bar with a new message.

        Args:
            message: The message to display in the status bar (string or Rich Text object)
        """

        super().update(message)


class DockerViewApp(App):
    """A Textual TUI application for monitoring Docker containers and stacks."""

    CSS = """
    Screen {
        background: $surface-darken-1;
    }

    Container {
        height: auto;
    }

    Horizontal {
        height: 100%;
        width: 100%;
        overflow: hidden;
    }

    #left-pane {
        width: 50%;
        height: 100%;
        padding: 0 1;
    }

    /* Only apply to Vertical containers inside left-pane */
    #left-pane Vertical {
        height: auto;
        width: 100%;
        padding: 0 1;
    }

    /* Ensure ContainerList fills available space and scrolls independently */
    ContainerList {
        height: 100%;
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
        Binding("s", "start", "Start Selected"),
        Binding("t", "stop", "Stop Selected"),
        Binding("e", "restart", "Restart Selected"),
        Binding("u", "recreate", "Recreate Selected (Up)"),
        Binding("d", "down", "Down Selected Stack"),
    ]

    def __init__(self):
        """Initialize the application and Docker manager."""
        try:
            super().__init__(driver_class=None)
            self.docker = DockerManager()
            self.container_list: ContainerList | None = None
            self.log_pane: LogPane | None = None
            self.error_display: ErrorDisplay | None = None
            self.refresh_timer: Timer | None = None
            self._current_worker: Worker | None = None
            self._refresh_count = 0
            self.footer: Footer | None = None
            self.status_bar: StatusBar | None = None
            # Track recreate operations to update log pane after refresh
            self._recreating_container_name = None
            self._recreating_item_type = None
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
            with Horizontal():
                with Vertical(id="left-pane"):
                    error = ErrorDisplay()
                    error.id = "error"
                    yield error
                    container_list = ContainerList()
                    container_list.id = "containers"
                    yield container_list
                log_pane = LogPane()
                yield log_pane
            status_bar = StatusBar()
            status_bar.id = "status_bar"
            yield status_bar
            footer = Footer()
            footer.id = "footer"
            yield footer
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
            self.log_pane = self.query_one("#log-pane", LogPane)
            self.error_display = self.query_one("#error", ErrorDisplay)
            self.footer = self.query_one("#footer", Footer)
            self.status_bar = self.query_one("#status_bar", StatusBar)

            # Start the auto-refresh timer with interval from config
            refresh_interval = config.get("app.refresh_interval", 5.0)
            self.refresh_timer = self.set_interval(
                refresh_interval, self.action_refresh
            )
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
        try:
            # Use call_after_refresh to ensure we're in the right context
            self.call_after_refresh(self.refresh_containers)
        except Exception as e:
            logger.error(f"Error scheduling refresh: {str(e)}", exc_info=True)

    def action_start(self) -> None:
        """Start the selected container or stack."""
        self._execute_docker_command("start")

    def action_stop(self) -> None:
        """Stop the selected container or stack."""
        self._execute_docker_command("stop")

    def action_restart(self) -> None:
        """Restart the selected container or stack."""
        self._execute_docker_command("restart")

    def action_recreate(self) -> None:
        """Recreate the selected container or stack using docker compose up -d."""
        self._execute_docker_command("recreate")

    def action_down(self) -> None:
        """Take down the selected stack with confirmation dialog."""
        if not self.container_list or not self.container_list.selected_item:
            self.error_display.update("No item selected to take down")
            return

        item_type, item_id = self.container_list.selected_item

        # Only allow down command on stacks, not individual containers
        if item_type != "stack":
            self.error_display.update(
                "Down command only works on stacks, not individual containers"
            )
            return

        # Get stack name for the modal
        stack_name = "unknown"
        if self.container_list.selected_stack_data:
            stack_name = self.container_list.selected_stack_data.get("name", "unknown")

        # Create the modal
        modal = ComposeDownModal(stack_name)

        # Push the confirmation modal
        def handle_down_confirmation(confirmed: bool) -> None:
            """Handle the result from the confirmation modal."""
            if confirmed:
                # Get checkbox state from the modal instance
                remove_volumes = modal.checkbox_checked

                # Build command with volume flag if needed
                command = "down"
                if remove_volumes:
                    command = "down:remove_volumes"

                self._execute_docker_command(command)

        self.push_screen(modal, handle_down_confirmation)

    def _execute_docker_command(self, command: str) -> None:
        """Execute a Docker command on the selected item.

        Args:
            command: The command to execute (start, stop, restart, recreate)
        """
        if not self.container_list or not self.container_list.selected_item:
            self.error_display.update(f"No item selected to {command}")
            return

        item_type, item_id = self.container_list.selected_item
        success = False

        # Track recreate operations so we can update log pane after refresh
        if command == "recreate":
            self._recreating_item_type = item_type
            if item_type == "container" and self.container_list.selected_container_data:
                self._recreating_container_name = (
                    self.container_list.selected_container_data.get("name")
                )
            elif item_type == "stack" and self.container_list.selected_stack_data:
                self._recreating_container_name = (
                    self.container_list.selected_stack_data.get("name")
                )
        else:
            self._recreating_container_name = None
            self._recreating_item_type = None

        try:
            if item_type == "container":
                item_name = (
                    self.container_list.selected_container_data.get("name", item_id)
                    if self.container_list.selected_container_data
                    else item_id
                )
                action_verb = (
                    "Recreating"
                    if command == "recreate"
                    else f"{command.capitalize()}ing"
                )
                message = f"{action_verb} container: {item_name}"

                # Update UI immediately for container operations
                status_map = {
                    "start": "starting...",
                    "stop": "stopping...",
                    "restart": "restarting...",
                    "recreate": "recreating...",
                }

                if command in status_map:
                    self.container_list.update_container_status(
                        item_id, status_map[command]
                    )
                    self.refresh()

                # Execute command in background thread
                def execute_and_clear():
                    success, _ = self.docker.execute_container_command(item_id, command)
                    if success:
                        # Clear status override after a delay
                        self.call_from_thread(
                            self.set_timer,
                            3,
                            lambda: (
                                self.container_list.clear_status_override(item_id),
                                self.action_refresh(),
                            ),
                        )

                import threading

                thread = threading.Thread(target=execute_and_clear)
                thread.daemon = True
                thread.start()

                success = True
            elif item_type == "stack":
                # Execute command on stack
                if self.container_list.selected_stack_data:
                    stack_name = self.container_list.selected_stack_data.get(
                        "name", item_id
                    )
                    config_file = self.container_list.selected_stack_data.get(
                        "config_file", ""
                    )

                    # Check if recreate is allowed
                    if command == "recreate":
                        can_recreate = self.container_list.selected_stack_data.get(
                            "can_recreate", True
                        )
                        if not can_recreate:
                            self.error_display.update(
                                f"Cannot recreate stack '{stack_name}': compose file not accessible"
                            )
                            return

                    success = self.docker.execute_stack_command(
                        stack_name, config_file, command
                    )
                    if command.startswith("down"):
                        action_verb = "Taking down"
                        message = f"{action_verb} stack: {stack_name}"
                        if "remove_volumes" in command:
                            message += " (including volumes)"
                    else:
                        action_verb = (
                            "Recreating"
                            if command == "recreate"
                            else f"{command.capitalize()}ing"
                        )
                        message = f"{action_verb} stack: {stack_name}"
                else:
                    self.error_display.update(f"Missing stack data for {item_id}")
                    return
            else:
                self.error_display.update(f"Unknown item type: {item_type}")
                return

            if success:
                # For container operations, the status is shown in the container list
                # For stack operations, we still show the message
                if item_type == "stack":
                    # Show a temporary message in the error display
                    self.error_display.update(message)
                    # Schedule clearing the message after a few seconds
                    self.set_timer(3, lambda: self.error_display.update(""))
                # Schedule a refresh after a short delay to update the UI
                self.set_timer(2, self.action_refresh)
            else:
                self.error_display.update(
                    f"Error {command}ing {item_type}: {self.docker.last_error}"
                )
        except Exception as e:
            logger.error(f"Error executing {command} command: {str(e)}", exc_info=True)
            self.error_display.update(f"Error executing {command}: {str(e)}")

    async def refresh_containers(self) -> None:
        """Refresh the container list asynchronously.

        Fetches updated container and stack information in a background thread,
        then updates the UI with the new data.
        """
        if not all([self.container_list, self.error_display]):
            logger.error("Error: Widgets not properly initialized")
            return

        try:
            # Add refreshing indicator to the existing title
            if " - Refreshing..." not in self.title:
                self.title = self.title + " - Refreshing..."

            # Start the worker but don't block waiting for it
            # Textual's worker pattern will call the function and then process the results
            # when they're ready without blocking the UI
            self._refresh_containers_worker(self._handle_refresh_results)

        except Exception as e:
            logger.error(f"Error during refresh: {str(e)}", exc_info=True)
            self.error_display.update(f"Error refreshing: {str(e)}")

    @work(thread=True)
    def _refresh_containers_worker(self, callback) -> Tuple[Dict, Dict, Dict, List]:
        """Worker function to fetch network, stack, volume and container data in a background thread.

        Args:
            callback: Function to call with the results when complete

        Returns:
            Tuple[Dict, Dict, Dict, List]: A tuple containing:
                - Dict: Mapping of network names to network information
                - Dict: Mapping of stack names to stack information
                - Dict: Mapping of volume names to volume information
                - List: List of container information dictionaries
        """
        try:
            # Get networks, stacks, volumes and containers in the thread
            networks = self.docker.get_networks()
            stacks = self.docker.get_compose_stacks()
            volumes = self.docker.get_volumes()
            containers = self.docker.get_containers()

            # Call the callback with the results
            # This will be executed in the main thread after the worker completes
            self.call_from_thread(callback, networks, stacks, volumes, containers)

            return networks, stacks, volumes, containers
        except Exception as e:
            logger.error(f"Error in refresh worker: {str(e)}", exc_info=True)
            self.call_from_thread(
                self.error_display.update, f"Error refreshing: {str(e)}"
            )
            return {}, {}, {}, []

    def _handle_refresh_results(self, networks, stacks, volumes, containers):
        """Handle the results from the refresh worker when they're ready.

        Args:
            networks: Dictionary of network information
            stacks: Dictionary of stack information
            volumes: Dictionary of volume information
            containers: List of container information
        """
        try:
            # Update UI with the results
            if hasattr(self.docker, "last_error") and self.docker.last_error:
                self.error_display.update(f"Error: {self.docker.last_error}")
            else:
                self.error_display.update("")

            # Schedule the UI update to run asynchronously
            asyncio.create_task(
                self._update_ui_with_results(networks, stacks, volumes, containers)
            )

        except Exception as e:
            logger.error(f"Error handling refresh results: {str(e)}", exc_info=True)
            self.error_display.update(f"Error refreshing: {str(e)}")

    async def _update_ui_with_results(self, networks, stacks, volumes, containers):
        """Update the UI with the results from the refresh worker.

        Args:
            networks: Dictionary of network information
            stacks: Dictionary of stack information
            volumes: Dictionary of volume information
            containers: List of container information
        """

        try:
            # Begin a batch update to prevent UI flickering
            self.container_list.begin_update()

            try:
                # Process all stacks first
                for stack_name, stack_info in stacks.items():
                    self.container_list.add_stack(
                        stack_name,
                        stack_info["config_file"],
                        stack_info["running"],
                        stack_info["exited"],
                        stack_info["total"],
                        stack_info.get("can_recreate", True),
                        stack_info.get("has_compose_file", True),
                    )

                # Process all volumes next
                for volume_name, volume_info in volumes.items():
                    self.container_list.add_volume(volume_info)

                # Process all networks after volumes
                for network_name, network_info in networks.items():
                    self.container_list.add_network(network_info)

                    # Add containers to the network
                    for container_info in network_info["connected_containers"]:
                        self.container_list.add_container_to_network(
                            network_name, container_info
                        )

                # Process all containers in a single batch
                # Sort containers by stack to minimize UI updates
                sorted_containers = sorted(containers, key=lambda c: c["stack"])
                for container in sorted_containers:
                    self.container_list.add_container_to_stack(
                        container["stack"], container
                    )

            finally:
                # Always end the update, even if cancelled
                self.container_list.end_update()

            # Handle container recreation - update log pane if needed
            if self._recreating_container_name and self.log_pane:
                # Find the new container with the same name
                new_container_id = None
                new_container_data = None

                if self._recreating_item_type == "container":
                    # Look for a container with the same name
                    for container in containers:
                        if container.get("name") == self._recreating_container_name:
                            new_container_id = container.get("id")
                            new_container_data = container
                            break

                    if new_container_id and new_container_data:
                        # Use select_container to properly update the UI and trigger all necessary events
                        self.container_list.select_container(new_container_id)
                        # Explicitly update the log pane with the new container data
                        # This ensures the log pane gets the updated container info immediately
                        self.log_pane.update_selection(
                            "container", new_container_id, new_container_data
                        )

                elif self._recreating_item_type == "stack":
                    # For stacks, just trigger a re-selection of the stack
                    stack_name = self._recreating_container_name
                    if stack_name in stacks:
                        self.container_list.select_stack(stack_name)

                # Clear the tracking variables
                self._recreating_container_name = None
                self._recreating_item_type = None

            # Check if selected container's status changed - update log pane if needed
            if self.log_pane and self.container_list.selected_item:
                item_type, item_id = self.container_list.selected_item
                if item_type == "container":
                    # Find the container in the new data
                    for container in containers:
                        if container.get("id") == item_id:
                            # Always update the log pane with current status
                            # The log pane will check if status actually changed
                            self.log_pane.update_selection(
                                "container", item_id, container
                            )
                            break

            # Update title with summary
            total_running = sum(s["running"] for s in stacks.values())
            total_exited = sum(s["exited"] for s in stacks.values())
            total_networks = len(networks)
            total_stacks = len(stacks)

            # Update the app title with stats (removes any "- Refreshing..." suffix)
            self.title = f"Docker Monitor - {total_networks} Networks, {total_stacks} Stacks, {total_running} Running, {total_exited} Exited"

            # Increment refresh count
            self._refresh_count += 1

        except Exception as e:
            logger.error(f"Error during UI update: {str(e)}", exc_info=True)
            self.error_display.update(f"Error updating UI: {str(e)}")

    def on_selection_changed(self, event: SelectionChanged) -> None:
        """Handle selection changes from the container list.

        Args:
            event: The SelectionChanged event containing selection information
        """
        if not self.log_pane:
            return

        if event.item_type == "none":
            # Clear selection
            self.log_pane.clear_selection()
        else:
            # Update log pane with new selection
            self.log_pane.update_selection(
                event.item_type, event.item_id, event.item_data
            )


def main():
    """Run the Docker container monitoring application."""
    try:
        app = DockerViewApp()
        app.run()
    except Exception as e:
        logger.error(f"Error running app: {str(e)}", exc_info=True)
        raise


__all__ = ["main", "DockerViewApp"]
