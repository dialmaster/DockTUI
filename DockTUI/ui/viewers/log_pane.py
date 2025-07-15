import logging

import docker
from rich.text import Text
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from ...config import config
from ...utils.clipboard import copy_to_clipboard_async
from ..widgets.rich_log_viewer import RichLogViewer
from .log_filter_manager import LogFilterManager
from .log_pane_styles import (
    LOG_PANE_CSS,
    NO_SELECTION_MESSAGE,
    SINCE_OPTIONS,
    TAIL_OPTIONS,
)
from .log_queue_processor import LogQueueProcessor
from .log_state_manager import LogStateManager
from .log_stream_manager import LogStreamManager

logger = logging.getLogger("DockTUI.log_pane")


class LogPane(Vertical):
    """A pane that displays real-time Docker logs for selected containers or stacks."""

    BINDINGS = [
        Binding("ctrl+shift+c", "copy_selection", "Copy selected text", show=False),
        Binding("ctrl+a", "select_all", "Select all text", show=False),
    ]

    DEFAULT_CSS = LOG_PANE_CSS

    def __init__(self):
        """Initialize the log pane."""
        super().__init__(id="log-pane")

        # Log configuration
        self.LOG_TAIL = str(config.get("log.tail", 200))
        self.LOG_SINCE = config.get("log.since", "15m")

        # Docker client for SDK streaming
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.docker_client = None

        # Initialize managers
        self.log_state_manager = LogStateManager(self)
        self.log_filter_manager = LogFilterManager(self)
        self.log_stream_manager = LogStreamManager(self.docker_client)
        self.log_queue_processor = LogQueueProcessor(
            self.log_stream_manager, self.log_filter_manager, parent=self
        )

        # UI components (initialized in compose)
        self.header = None
        self.log_display = None
        self.no_selection_display = None
        self.search_input = None
        self.auto_follow_checkbox = None
        self.mark_position_button = None
        self.tail_select = None
        self.since_select = None

        # Timer for processing log queue
        self.queue_timer = None

        # Set up manager callbacks
        self.log_filter_manager.on_filter_changed = self._refilter_logs
        self.log_filter_manager.on_marker_added = self._on_marker_added

    def compose(self):
        """Compose the log pane UI."""
        # Create the header
        self.header = Static("📋 Log Pane - No Selection", classes="log-header")

        # Create controls
        self.search_input = Input(placeholder="Filter logs...", id="search-input")
        self.auto_follow_checkbox = Checkbox(
            "Follow", self.log_state_manager.auto_follow, id="auto-follow-checkbox"
        )
        self.mark_position_button = Button(
            "Mark Log", id="mark-position-button", variant="primary"
        )

        # Create dropdowns
        self.tail_select = self._create_tail_select()
        self.since_select = self._create_since_select()

        # Create the no-selection display
        self.no_selection_display = Static(
            Text.assemble(*NO_SELECTION_MESSAGE),
            classes="no-selection",
        )
        self.no_selection_display.display = True

        # Create the log display
        self.log_display = RichLogViewer(
            max_lines=config.get("log.max_lines", 2000),
            classes="log-display",
        )
        self.log_display.display = False

        # Set log display in processor
        self.log_queue_processor.set_log_display(self.log_display)

        # Yield widgets in order
        yield self.header

        # First control row - log settings
        yield Horizontal(
            Label("Show last:", classes="log-controls-label"),
            self.tail_select,
            Label("From past:", classes="log-controls-label"),
            self.since_select,
            classes="log-controls",
        )

        # Second control row - search, auto-follow, and mark position
        yield Horizontal(
            self.search_input,
            self.auto_follow_checkbox,
            self.mark_position_button,
            classes="log-controls-search",
        )

        # Content container that will expand to fill space
        yield Container(
            self.no_selection_display, self.log_display, classes="log-content-container"
        )

        # Footer with instructions
        yield Static(
            "📋 Double-click to expand JSON/XML • Click+drag to select • Right-click to copy",
            classes="log-footer",
        )

    def on_mount(self):
        """Set up the log pane after mounting."""
        # Start the queue processing timer
        self.queue_timer = self.set_interval(0.1, self._process_log_queue)
        # Set UI components in state manager
        self.log_state_manager.set_ui_components(self.header, self.log_display)

    def on_unmount(self):
        """Clean up when unmounting."""
        if self.log_stream_manager:
            self.log_stream_manager.stop_streaming(wait=True)
        if self.queue_timer:
            self.queue_timer.stop()
        if self.log_filter_manager:
            self.log_filter_manager.cleanup()

    def update_selection(
        self, item_type: str, item_id: str, item_data: dict, force_restart: bool = False
    ):
        """Update the log pane with a new selection."""
        # Save dropdown states before any UI updates
        dropdown_states = self.log_state_manager.save_dropdown_states(
            self.tail_select, self.since_select
        )

        # Check if this is the same item that's already selected
        if (
            self.log_state_manager.is_same_item(item_type, item_id)
            and not force_restart
        ):
            # If it's the same container, check if status changed
            if item_type == "container":
                status_change = self.log_state_manager.check_status_change(item_data)
                if status_change:
                    # Container status changed, update the display
                    self._handle_status_change(item_data, status_change)
                    # Restore dropdown states after UI updates
                    self.call_after_refresh(
                        lambda: self.log_state_manager.restore_dropdown_states(
                            dropdown_states, self.tail_select, self.since_select
                        )
                    )
                    return
            elif item_type == "stack":
                # For stacks, check if container statuses have changed
                stack_status_changed = self._check_stack_containers_status_changed(
                    item_data
                )
                if stack_status_changed:
                    logger.info(
                        f"Stack '{item_id}' containers status changed, refreshing logs"
                    )
                    # Force restart logs to pick up new container states
                    self._clear_logs()
                    self._set_log_text(
                        f"Stack container status changed. Refreshing logs...\n"
                    )
                    self._start_logs()
                    # Restore dropdown states after UI updates
                    self.call_after_refresh(
                        lambda: self.log_state_manager.restore_dropdown_states(
                            dropdown_states, self.tail_select, self.since_select
                        )
                    )
                    return

            # Update the stored data but don't restart logs for the same selection
            self.log_state_manager.current_item_data = item_data

            # Update header to reflect current status (e.g., NOT RUNNING)
            if item_type == "container":
                status = item_data.get("status", "")
                item_name = item_data.get("name", item_id)
                logger.debug(
                    f"Updating header for container {item_name} with status: {status}"
                )
                self.log_state_manager.update_header_with_status(item_name, status)

            # Restore dropdown states even when returning early
            self.call_after_refresh(
                lambda: self.log_state_manager.restore_dropdown_states(
                    dropdown_states, self.tail_select, self.since_select
                )
            )
            return

        # Update state via state manager
        current_item = self.log_state_manager.set_current_item(
            item_type, item_id, item_data
        )

        # Sync with other managers
        self.log_stream_manager.current_item = current_item
        self.log_stream_manager.current_item_data = item_data
        self.log_queue_processor.set_current_item(item_type, item_id, item_data)

        # Update header and check if item type has logs
        has_logs = self.log_state_manager.update_header_for_item(
            item_type, item_id, item_data
        )
        if not has_logs:
            # Show appropriate message for item types without logs
            if item_type == "network":
                self._show_no_logs_message_for_item_type("Networks")
            elif item_type == "image":
                self._show_no_logs_message_for_item_type("Images")
            elif item_type == "volume":
                self._show_no_logs_message_for_item_type("Volumes")
            # Restore dropdown states even when returning early
            self.call_after_refresh(
                lambda: self.log_state_manager.restore_dropdown_states(
                    dropdown_states, self.tail_select, self.since_select
                )
            )
            return

        # Show log display UI
        self.log_display.display = True
        self.no_selection_display.display = False

        # Clear previous logs and stored lines
        self._clear_logs()

        # Show loading message
        self._set_log_text(f"Loading logs for {item_type}: {item_id}...\n")
        self.log_stream_manager.showing_loading_message = True

        # Stop any existing log streaming asynchronously to avoid blocking
        self.log_stream_manager.stop_streaming(wait=False)

        # Start streaming logs
        self._start_logs()

        # Restore dropdown states after all UI updates
        self.call_after_refresh(
            lambda: self.log_state_manager.restore_dropdown_states(
                dropdown_states, self.tail_select, self.since_select
            )
        )

    def clear_selection(self):
        """Clear the current selection and show the no-selection state."""
        # Save dropdown states before any UI updates
        dropdown_states = self.log_state_manager.save_dropdown_states(
            self.tail_select, self.since_select
        )

        # Stop any existing log streaming and clear state
        if self.log_stream_manager:
            self.log_stream_manager.clear()

        # Clear state via state manager
        self.log_state_manager.clear_current_item()
        self.log_state_manager.update_header_for_no_selection()

        # Update UI state
        self.log_display.display = False
        self.no_selection_display.display = True
        self._clear_logs()
        self.refresh()

        # Restore dropdown states after refresh
        self.call_after_refresh(
            lambda: self.log_state_manager.restore_dropdown_states(
                dropdown_states, self.tail_select, self.since_select
            )
        )

    def _handle_status_change(self, item_data: dict, status_change: str = None):
        """Handle container status changes (started/stopped/restarted).

        Args:
            item_data: Container data
            status_change: Type of status change ("started", "stopped", "restarted")
        """
        # Stop any existing log streaming without blocking UI
        if self.log_stream_manager:
            self.log_stream_manager.stop_streaming(wait=False)

        # Update stored data
        self.log_state_manager.current_item_data = item_data
        self._clear_logs()

        status = item_data.get("status", "")
        current_item = self.log_state_manager.current_item
        item_name = item_data.get("name", current_item[1] if current_item else "")

        # Update header based on status
        self.log_state_manager.update_header_with_status(item_name, status)

        # Load logs with appropriate message
        if status_change == "restarted":
            self._set_log_text(
                f"Container '{item_name}' restarted. Loading fresh logs...\n"
            )
        elif self.log_state_manager.is_container_stopped(status):
            self._set_log_text(
                f"Container '{item_name}' stopped. Loading historical logs...\n"
            )
        else:
            self._set_log_text(f"Container '{item_name}' started. Loading logs...\n")

        self._start_logs()

    def _start_logs(self):
        """Start streaming logs for the current selection."""
        current_item = self.log_state_manager.current_item
        if not current_item:
            logger.warning("_start_logs called but no current_item")
            return

        if not self.log_stream_manager.is_available:
            logger.error("Log stream manager not available")
            return

        item_type, item_id = current_item

        # Start streaming logs
        self.log_stream_manager.start_streaming(
            item_type=item_type,
            item_id=item_id,
            item_data=self.log_state_manager.current_item_data,
            tail=self.LOG_TAIL,
            since=self.LOG_SINCE,
        )

    def _process_log_queue(self):
        """Timer callback to process queued log lines."""
        self.log_queue_processor.process_queue(max_items=50)

    def _refilter_logs(self):
        """Re-filter and display all stored log lines based on current search filter."""
        # Clear the "no matches" flag as we're re-evaluating
        self.log_stream_manager.showing_no_matches_message = False

        # First check if we're in a "no logs" state
        if self.log_stream_manager.showing_no_logs_message:
            # Container has no logs - always show this message regardless of filter
            self._set_log_text(self.log_queue_processor._get_no_logs_message())
            return

        # Check if we have any logs at all
        all_lines = self.log_filter_manager.get_all_lines()

        if not all_lines:
            # No logs at all - show "No logs found"
            self._set_log_text(self.log_queue_processor._get_no_logs_message())
            self.log_stream_manager.showing_no_logs_message = True
            return

        # Update the filter text in RichLogViewer
        current_filter = self.log_filter_manager.get_current_filter()
        if isinstance(self.log_display, RichLogViewer):
            self.log_display.set_filter(current_filter)
            self.log_display.set_log_filter(self.log_filter_manager.log_filter)
            self.log_display.refilter_existing_lines()
            self._auto_scroll_to_bottom()

            # Check if we have any visible lines after filtering
            if (
                not self.log_display.visible_lines
                and self.log_filter_manager.has_filter()
            ):
                # We have a filter but no matches
                self.log_stream_manager.showing_no_matches_message = True
                # Don't clear logs! The logs are still there, just filtered out
                # The RichLogViewer will show an empty view, which is what we want

    def _on_marker_added(self, marker_lines: list):
        """Handle marker lines being added by the filter manager."""
        # Display the marker lines
        for line in marker_lines:
            self._append_log_line(line)

    def on_input_changed(self, event):
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.log_filter_manager.handle_search_input_changed(event.value)

    def on_checkbox_changed(self, event):
        """Handle auto-follow checkbox changes."""
        if event.checkbox.id == "auto-follow-checkbox":
            self.log_state_manager.set_auto_follow(event.value)
            self._auto_scroll_to_bottom()

    def on_select_changed(self, event):
        """Handle dropdown selection changes."""
        if event.select.id == "tail-select":
            self.LOG_TAIL = event.value
            self.log_stream_manager.update_settings(tail=self.LOG_TAIL)

            # If logs are currently displayed, restart them with new settings
            if self.log_state_manager.current_item and self.log_display.display:
                self._restart_logs()

        elif event.select.id == "since-select":
            self.LOG_SINCE = event.value
            self.log_stream_manager.update_settings(since=self.LOG_SINCE)

            # If logs are currently displayed, restart them with new settings
            if self.log_state_manager.current_item and self.log_display.display:
                self._restart_logs()

    def _restart_logs(self):
        """Restart log streaming with new settings."""
        # Clear display and show loading message
        self._clear_logs()

        # Show loading message
        current_item = self.log_state_manager.current_item
        if current_item:
            item_type, item_id = current_item
            self._set_log_text(f"Reloading logs for {item_type}: {item_id}...\n")
            self.log_stream_manager.showing_loading_message = True

        # Restart streaming with new settings
        self.log_stream_manager.restart_streaming()

    def _show_no_logs_message_for_item_type(self, item_type: str):
        """Show a message for item types that don't have logs."""
        self.log_display.display = True
        self.no_selection_display.display = False
        self._clear_logs()
        self._set_log_text(
            f"{item_type} do not have logs. Select a container or stack to view logs."
        )
        # Stop any existing log streaming
        self.log_stream_manager.stop_streaming(wait=False)
        self.refresh()

    def action_copy_selection(self):
        """Copy the selected text to the clipboard."""
        if self.log_display.display:
            selection = self.log_display.selected_text
            if selection:

                def on_copy_complete(success):
                    if success:
                        logger.info(f"Copied {len(selection)} characters to clipboard")
                        self.app.notify(
                            "Text copied to clipboard",
                            severity="information",
                            timeout=2,
                        )
                    else:
                        logger.error("Failed to copy to clipboard")
                        self.app.notify(
                            "Failed to copy to clipboard. Please install xclip or pyperclip.",
                            severity="error",
                            timeout=3,
                        )

                # Copy in background thread
                copy_to_clipboard_async(selection, on_copy_complete)

    def action_select_all(self):
        """Select all text in the log display."""
        if self.log_display.display:
            self.log_display.select_all()

    def on_button_pressed(self, event):
        """Handle button presses."""
        if event.button.id == "mark-position-button":
            self._mark_position()

    def _mark_position(self):
        """Add a timestamp marker to the log display."""
        if self.log_display.display:
            # Let the filter manager handle marker creation
            marker_lines = self.log_filter_manager.add_marker()

            # Show notification
            if marker_lines:
                # Extract timestamp from marker line
                marker_text = marker_lines[2]  # The actual marker line
                timestamp = marker_text.replace("------ MARKED ", "").replace(
                    " ------", ""
                )

                self.app.notify(
                    f"Position marked at {timestamp}",
                    severity="information",
                    timeout=2,
                )

    def _clear_logs(self):
        """Clear the log display and filter."""
        self.log_display.clear()
        self.log_filter_manager.clear()
        self.log_stream_manager.showing_no_logs_message = False
        self.log_stream_manager.showing_loading_message = False

    def _auto_scroll_to_bottom(self):
        """Auto-scroll to the bottom of the log display if auto-follow is enabled."""
        if self.log_state_manager.should_auto_scroll():
            self.log_display.scroll_to_end_immediate()

    def _clear_log_display(self):
        """Clear the log display widget."""
        self.log_display.clear()

    def _get_log_text(self) -> str:
        """Get the text content of the log display."""
        # For RichLogViewer, reconstruct text from visible lines
        return "\n".join(line.raw_text for line in self.log_display.visible_lines)

    def _update_header(self, text: str):
        """Update the header text."""
        self.log_state_manager.update_header(text)

    def _append_log_line(self, line: str):
        """Append a line to the log display."""
        is_marked_line = "------ MARKED" in line and "------" in line
        is_spacer = line.strip() == ""
        self.log_display.add_log_line(
            line, is_system_message=(is_marked_line or is_spacer)
        )

    def _set_log_text(self, text: str, is_system_message: bool = True):
        """Set the entire text content of the log display."""
        self.log_display.clear()
        if text:
            for line in text.rstrip("\n").split("\n"):
                self.log_display.add_log_line(line, is_system_message=is_system_message)

    def _create_tail_select(self) -> Select:
        """Create the tail select dropdown with current value."""
        tail_options = list(TAIL_OPTIONS)
        # If current value is not in options, add it
        if not any(opt[1] == self.LOG_TAIL for opt in tail_options):
            tail_options.insert(0, (f"{self.LOG_TAIL} lines", self.LOG_TAIL))

        return Select(
            options=tail_options,
            value=self.LOG_TAIL,
            id="tail-select",
            classes="log-setting",
        )

    def _create_since_select(self) -> Select:
        """Create the since select dropdown with current value."""
        since_options = list(SINCE_OPTIONS)
        # If current value is not in options, add it
        if not any(opt[1] == self.LOG_SINCE for opt in since_options):
            since_options.insert(0, (f"{self.LOG_SINCE}", self.LOG_SINCE))

        return Select(
            options=since_options,
            value=self.LOG_SINCE,
            id="since-select",
            classes="log-setting",
        )

    def _check_stack_containers_status_changed(self, new_stack_data: dict) -> bool:
        """Check if any container statuses in a stack have changed.

        Args:
            new_stack_data: New stack data to compare

        Returns:
            True if any container status changed, False otherwise
        """
        # Get the stored stack data
        old_stack_data = self.log_state_manager.current_item_data
        if not old_stack_data:
            return False

        # Extract container status counts
        old_running = old_stack_data.get("running", 0)
        old_exited = old_stack_data.get("exited", 0)
        new_running = new_stack_data.get("running", 0)
        new_exited = new_stack_data.get("exited", 0)

        # Check if the counts have changed
        if old_running != new_running or old_exited != new_exited:
            logger.debug(
                f"Stack container counts changed: running {old_running}->{new_running}, "
                f"exited {old_exited}->{new_exited}"
            )
            return True

        return False
