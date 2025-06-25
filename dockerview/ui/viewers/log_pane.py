import logging
import queue

import docker
from rich.text import Text
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from ...config import config
from ...services.log_filter import LogFilter
from ...services.log_streamer import LogStreamer
from ...utils.clipboard import copy_to_clipboard_async
from ..widgets.log_text_area import LogTextArea

logger = logging.getLogger("dockerview.log_pane")


class LogPane(Vertical):
    """A pane that displays real-time Docker logs for selected containers or stacks."""

    BINDINGS = [
        # Use different keybinding to avoid conflict with app's Ctrl+C (quit)
        Binding("ctrl+shift+c", "copy_selection", "Copy selected text", show=False),
        Binding("ctrl+a", "select_all", "Select all text", show=False),
    ]

    # Dropdown options configuration
    TAIL_OPTIONS = [
        ("50 lines", "50"),
        ("100 lines", "100"),
        ("200 lines", "200"),
        ("400 lines", "400"),
        ("800 lines", "800"),
        ("1600 lines", "1600"),
        ("3200 lines", "3200"),
        ("6400 lines", "6400"),
        ("12800 lines", "12800"),
    ]

    SINCE_OPTIONS = [
        ("5 minutes", "5m"),
        ("10 minutes", "10m"),
        ("15 minutes", "15m"),
        ("30 minutes", "30m"),
        ("1 hour", "1h"),
        ("2 hours", "2h"),
        ("4 hours", "4h"),
        ("8 hours", "8h"),
        ("24 hours", "24h"),
        ("48 hours", "48h"),
    ]

    DEFAULT_CSS = """
    LogPane {
        width: 50% !important;
        max-width: 50% !important;
        height: 100%;
        padding: 0;
        border-left: solid $primary-darken-1;
        background: $surface-darken-2;
        overflow-y: auto;
    }

    LogPane > Static.log-header {
        background: $primary-darken-1;
        color: white !important;
        text-align: center;
        height: 1;
        text-style: bold;
        padding: 0 1;
        border: none;
        dock: top;
    }

    .log-controls {
        height: 6;
        max-height: 6 !important;
        padding-top: 1;
        padding-bottom: 1;
        background: $surface;
        margin-top: 1;
        dock: top;
    }

    .log-controls-label {
        margin-top: 1;
        margin-left: 2;
    }

    .log-controls-search {
        height: 4;
        max-height: 4 !important;
        padding: 0 1;
        background: $surface;
        margin-top: 6;
        dock: top;
    }


    /* Container for the middle content, this contains the log display and the no selection display */
    .log-content-container {
        min-height: 1fr;  /* Fill remaining space */
        width: 100%;
        overflow: auto;
    }

    .no-selection {
        height: 100%;
        text-align: center;
        color: $text-muted;
        width: 100%;
        padding: 0 0;
        content-align: center middle;
        background: $surface-darken-2;
        border: none;
    }

    .log-display {
        height: 100%;  /* Fill parent container */
        background: $surface-darken-1;
        padding: 0 1;
        border: none;
        display: none;
    }

    .log-display:focus {
        border: none;
    }

    /* TextArea specific styling */
    .log-display .text-area--cursor {
        background: $primary;
        color: $text;
    }

    .log-display .text-area--selection {
        background: $primary-lighten-1;
    }

    #tail-select {
        width: 22;
        height: 3;
        margin: 0 1 0 0;
    }

    #since-select {
        width: 22;
        height: 3;
        margin: 0 1 0 0;
    }

    #search-input {
        width: 40%;
        max-width: 30;
        height: 3;
        margin-left: 1;
        margin-right: 0;
        margin-top: 0;
        margin-bottom: 0;
    }

    #auto-follow-checkbox {
        width: 20%;
        min-width: 15;
        max-width: 15;
        height: 3;
        padding: 0 1;
        margin-left: 1;
        margin-right: 0;
        margin-top: 0;
        margin-bottom: 0;
        content-align: center middle;
    }

    #mark-position-button {
        width: auto;
        min-width: 15;
        height: 3;
        margin-left: 1;
        margin-right: 0;
        margin-top: 0;
        margin-bottom: 0;
    }
    """

    def __init__(self):
        """Initialize the log pane."""
        super().__init__(id="log-pane")

        # State management
        self.current_item = None  # ("container", id) or ("stack", name)
        self.current_item_data = None
        self.auto_follow = True

        # Log filtering
        self.log_filter = LogFilter(max_lines=config.get("log.max_lines", 2000))

        # Log tail and since configuration
        self.LOG_TAIL = str(config.get("log.tail", 200))
        self.LOG_SINCE = config.get("log.since", "15m")

        # Track if we've received any logs yet
        self.initial_log_check_done = False
        self.waiting_for_logs = False
        self.showing_no_logs_message = (
            False  # Track when we're showing the "no logs found" message
        )
        self.showing_loading_message = (
            False  # Track when showing "Loading logs..." message
        )

        # Docker client for SDK streaming
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.docker_client = None

        # Log streaming
        self.log_streamer = (
            LogStreamer(self.docker_client) if self.docker_client else None
        )
        self.current_session_id = 0

        # UI components
        self.header = None
        self.log_display = None
        self.no_selection_display = None
        self.search_input = None
        self.auto_follow_checkbox = None
        self.mark_position_button = None
        self.content_container = None
        self.tail_select = None
        self.since_select = None

        # Timer for processing log queue
        self.queue_timer = None

    def compose(self):
        """Compose the log pane UI."""
        # Create the header
        self.header = Static("📋 Log Pane - No Selection", classes="log-header")

        # Create search and auto-follow controls
        self.search_input = Input(placeholder="Filter logs...", id="search-input")
        self.auto_follow_checkbox = Checkbox(
            "Follow", self.auto_follow, id="auto-follow-checkbox"
        )
        self.mark_position_button = Button(
            "Mark Log", id="mark-position-button", variant="primary"
        )

        # Create dropdowns with current values selected
        self.tail_select = self._create_tail_select()
        self.since_select = self._create_since_select()

        # Create the no-selection display
        self.no_selection_display = Static(
            Text.assemble(
                ("Select a container or stack to view logs\n\n", "dim"),
                "• Click on a container to see its logs\n",
                "• Click on a stack header to see logs for all containers in the stack\n",
                "• Use the search box to filter log entries\n",
                "• Toggle auto-follow to stop/start automatic scrolling\n",
                "• Adjust log settings to change time range and line count\n\n",
                ("Text Selection:\n", "bold"),
                "• Click and drag with mouse to select text\n",
                "• Right-click on selected text to copy",
            ),
            classes="no-selection",
        )
        self.no_selection_display.display = True

        # Create the log display with LogTextArea for proper text selection and right-click copy
        self.log_display = LogTextArea(
            read_only=True,
            classes="log-display",
            tab_behavior="focus",  # Don't insert tabs, just move focus
        )
        self.log_display.display = False
        # TextArea is focusable by default

        # Yield widgets in order: header, controls, content
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

    def on_mount(self):
        """Set up the log pane after mounting."""
        # Get reference to content container if needed
        self.content_container = self.query_one(".log-content-container")
        # Start the queue processing timer
        self.queue_timer = self.set_interval(0.1, self._process_log_queue)

    def on_unmount(self):
        """Clean up when unmounting."""
        if self.log_streamer:
            self.log_streamer.stop_streaming(wait=True)
        if self.queue_timer:
            self.queue_timer.stop()

    def update_selection(self, item_type: str, item_id: str, item_data: dict):
        """Update the log pane with a new selection.

        Args:
            item_type: Type of item ("container" or "stack")
            item_id: ID of the item
            item_data: Dictionary containing item information
        """

        # Check if this is the same item that's already selected
        if self.current_item == (item_type, item_id):
            # If it's the same container, check if status changed
            if item_type == "container" and self.current_item_data:
                old_status = self.current_item_data.get("status", "").lower()
                new_status = item_data.get("status", "").lower()

                # Check if container stopped
                if self._is_container_running(
                    old_status
                ) and self._is_container_stopped(new_status):
                    # Container was stopped, update the display
                    self._handle_status_change(item_data)
                    return

                # Check if container started
                elif self._is_container_stopped(
                    old_status
                ) and self._is_container_running(new_status):
                    # Container was started, resume logs
                    self._handle_status_change(item_data)
                    return

            # Update the stored data but don't restart logs for the same selection
            self.current_item_data = item_data
            return

        # Update state
        self.current_item = (item_type, item_id)
        self.current_item_data = item_data

        # Update header and check if item type has logs
        if not self._update_header_for_item(item_type, item_id, item_data):
            return  # Item type doesn't have logs

        # Show log display, hide no-selection display
        self._show_logs_ui()

        # Clear previous logs and stored lines
        self._clear_logs()

        # Check if this is a container and if it's not running - do this BEFORE stopping logs
        if item_type == "container" and item_data.get("status"):
            if self._is_container_stopped(item_data["status"]):
                # Container is not running, show appropriate message immediately
                self.log_display.text = f"Container '{item_data.get('name', item_id)}' is not running.\nStatus: {item_data['status']}"
                # Stop any existing log streaming (non-blocking)
                if self.log_streamer:
                    self.log_streamer.stop_streaming(wait=False)
                return

        # Show loading message immediately, but only if no filter is active
        # If a filter is active, we'll wait to see if any lines match before showing anything
        if not self.log_filter.has_filter():
            self.log_display.text = f"Loading logs for {item_type}: {item_id}...\n"
            self.showing_loading_message = True
        else:
            # Clear display but don't show loading message yet when filter is active
            self.log_display.clear()
            self.showing_loading_message = False

        # Stop any existing log streaming asynchronously to avoid blocking
        if self.log_streamer:
            self.log_streamer.stop_streaming(wait=False)

        # Start streaming logs without refresh to avoid blocking
        self._start_logs()

    def clear_selection(self):
        """Clear the current selection and show the no-selection state."""

        # Stop any existing log streaming
        if self.log_streamer:
            self.log_streamer.stop_streaming(wait=True)

        # Clear state
        self.current_item = None
        self.current_item_data = None

        # Update header
        self.header.update("📋 Log Pane - No Selection")

        # Hide log display, show no-selection display
        self._show_no_selection_ui()

        # Clear logs and stored lines
        self._clear_logs()

        # Refresh to ensure visibility changes take effect
        self.refresh()

    def _handle_status_change(self, item_data: dict):
        """Handle container status changes (started/stopped).

        Args:
            item_data: Updated container data with new status
        """
        # Stop any existing log streaming without blocking UI
        if self.log_streamer:
            self.log_streamer.stop_streaming(wait=False)

        # Update stored data
        self.current_item_data = item_data

        # Clear previous logs
        self._clear_logs()

        status = item_data.get("status", "")

        if self._is_container_stopped(status):
            # Container is not running, show message
            self.log_display.text = f"Container '{item_data.get('name', self.current_item[1])}' is not running.\nStatus: {item_data['status']}"
            self.refresh()
        elif self._is_container_running(status):
            # Container is running, start streaming logs
            self.log_display.clear()
            self.log_display.text = f"Container '{item_data.get('name', self.current_item[1])}' started. Loading logs...\n"
            self._start_logs()

    def _start_logs(self):
        """Start streaming logs for the current selection."""
        if not self.current_item:
            logger.warning("_start_logs called but no current_item")
            return

        if not self.log_streamer:
            logger.error("Log streamer not available")
            return

        item_type, item_id = self.current_item

        # Note: Loading message is already shown in update_selection()
        self.waiting_for_logs = True
        self.initial_log_check_done = False
        self.showing_no_logs_message = False  # Reset the flag when starting new logs

        # Start streaming logs
        self.current_session_id = self.log_streamer.start_streaming(
            item_type=item_type,
            item_id=item_id,
            item_data=self.current_item_data,
            tail=self.LOG_TAIL,
            since=self.LOG_SINCE,
        )

    def _process_log_queue(self):
        """Timer callback to process queued log lines."""
        if not self.log_streamer:
            return

        log_queue = self.log_streamer.get_queue()

        try:
            processed = 0
            matched_lines = 0  # Track lines that match the filter
            has_displayed_any = (
                len(self.log_display.text.strip()) > 0
            )  # Check if we've shown anything yet
            # Process up to 50 lines per tick to avoid blocking
            for _ in range(50):
                if log_queue.empty():
                    break

                try:
                    queue_item = log_queue.get_nowait()

                    # Handle both old format (msg_type, content) and new format (session_id, msg_type, content)
                    if len(queue_item) == 2:
                        # Old format - shouldn't happen but handle gracefully
                        msg_type, content = queue_item
                        session_id = 0
                    else:
                        # New format with session ID
                        session_id, msg_type, content = queue_item

                    # Skip if this is from an old session
                    if session_id != 0 and session_id != self.current_session_id:
                        continue

                    processed += 1

                    if msg_type == "log":
                        # Store all log lines
                        self.log_filter.add_line(content)

                        # Apply search filter with marker context awareness
                        if self.log_filter.should_show_line_with_context(content):
                            matched_lines += 1
                            # If we're showing the "no logs found" message or loading message, clear it
                            if (
                                self.showing_no_logs_message
                                or self.showing_loading_message
                            ):
                                self.log_display.clear()
                                self.showing_no_logs_message = False
                                self.showing_loading_message = False

                            # Append to the text area
                            self._append_log_line(content)

                            # First line processing handled elsewhere
                    elif msg_type == "error":
                        # Display errors (don't store these in all_log_lines)
                        error_msg = f"ERROR: {content}"
                        self._append_log_line(error_msg)
                        logger.error(f"Queue error message: {content}")
                    elif msg_type == "no_logs":
                        # Show informative message when no logs are found
                        if self.waiting_for_logs:
                            self.log_display.clear()
                            self.waiting_for_logs = False
                            self.log_display.text = self._get_no_logs_message()
                            self.showing_no_logs_message = (
                                True  # Mark that we're showing the no logs message
                            )

                except queue.Empty:
                    break

            if processed > 0:
                self.initial_log_check_done = True

                # If we have a filter, have processed some logs, but no lines matched, show message
                # Use our local matched_lines count instead of the filter's count
                # Only show the "no match" message if we haven't displayed anything yet
                if (
                    self.log_filter.has_filter()
                    and self.log_filter.get_line_count() > 0
                    and matched_lines == 0
                    and not has_displayed_any  # Only show if nothing displayed yet
                ):
                    self.log_display.text = "No log lines match filter"

        except Exception as e:
            logger.error(f"Error processing log queue: {e}", exc_info=True)

    def _get_no_logs_message(self):
        """Get the formatted 'No logs found' message."""
        item_type, item_id = self.current_item if self.current_item else ("", "")
        return (
            f"No logs found for {item_type}: {item_id}\n\n"
            "This could mean:\n"
            "  • The container/stack hasn't produced logs in the selected time range\n"
            "  • The container/stack was recently started\n"
            "  • Logs may have been cleared or rotated\n\n"
            "Try adjusting the log settings above to see more history.\n\n"
            "Waiting for new logs..."
        )

    def _refilter_logs(self):
        """Re-filter and display all stored log lines based on current search filter."""
        self.log_display.clear()

        # If we're showing the "no logs found" message and there are no logs,
        # preserve that message regardless of filter
        if self.showing_no_logs_message and self.log_filter.get_line_count() == 0:
            self.log_display.text = self._get_no_logs_message()
            return

        # Get filtered lines
        filtered_lines = self.log_filter.get_filtered_lines()

        # Set all filtered lines at once
        if filtered_lines:
            # Reconstruct the text exactly as it was originally displayed
            # Each line should end with a newline, including empty lines
            text_parts = []
            for line in filtered_lines:
                text_parts.append(line)
                text_parts.append("\n")
            self.log_display.text = "".join(text_parts)
        elif self.log_filter.has_filter() and self.log_filter.get_line_count() > 0:
            # If we have a filter and no lines match, show a message
            self.log_display.text = "No log lines match filter"
        else:
            self.log_display.text = ""

        # Handle scrolling based on auto-follow setting
        if self.auto_follow and filtered_lines:
            self._auto_scroll_to_bottom()

    def on_input_changed(self, event):
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.log_filter.set_filter(event.value)
            # Re-filter existing logs when search filter changes
            self._refilter_logs()

    def on_checkbox_changed(self, event):
        """Handle auto-follow checkbox changes."""
        if event.checkbox.id == "auto-follow-checkbox":
            self.auto_follow = event.value

            # If auto-follow is enabled, immediately scroll to the bottom
            self._auto_scroll_to_bottom()

    def on_select_changed(self, event):
        """Handle dropdown selection changes."""
        if event.select.id == "tail-select":
            # Update tail setting
            self.LOG_TAIL = event.value
            logger.info(f"Log tail setting changed to: {self.LOG_TAIL}")

            # If logs are currently displayed, restart them with new settings
            if self.current_item and self.log_display.display:
                self._restart_logs()

        elif event.select.id == "since-select":
            # Update since setting
            self.LOG_SINCE = event.value
            logger.info(f"Log since setting changed to: {self.LOG_SINCE}")

            # If logs are currently displayed, restart them with new settings
            if self.current_item and self.log_display.display:
                self._restart_logs()

    def _restart_logs(self):
        """Restart log streaming with new settings."""
        # Clear display and show loading message immediately
        self._clear_logs()

        # Show loading message
        item_type, item_id = self.current_item
        self.log_display.text = f"Reloading logs for {item_type}: {item_id}...\n"
        self.waiting_for_logs = True
        self.initial_log_check_done = False
        self.showing_loading_message = True

        # Stop current logs without waiting to avoid blocking the UI
        if self.log_streamer:
            self.log_streamer.stop_streaming(wait=False)

        # Start logs again
        self._start_logs()

    def _show_no_logs_message_for_item_type(self, item_type: str):
        """Show a message for item types that don't have logs and handle the UI state.

        Args:
            item_type: The type of item (e.g., 'Networks', 'Images', 'Volumes')
        """
        self._show_logs_ui()
        self._clear_logs()  # Clear the log buffer
        self.log_display.text = (
            f"{item_type} do not have logs. Select a container or stack to view logs."
        )
        # Stop any existing log streaming
        if self.log_streamer:
            self.log_streamer.stop_streaming(wait=False)
        self.refresh()

    def action_copy_selection(self):
        """Copy the selected text to the clipboard."""
        if self.log_display.display:
            selection = self.log_display.selected_text
            if selection:
                # Define callback to show notification from main thread
                def on_copy_complete(success):
                    if success:
                        logger.info(f"Copied {len(selection)} characters to clipboard")
                        # Show notification in the app, not in the log display to avoid disrupting logs
                        self.app.notify(
                            "Text copied to clipboard",
                            severity="information",
                            timeout=2,
                        )
                    else:
                        logger.error("Failed to copy to clipboard")
                        # Show error notification
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
            from datetime import datetime

            # Get current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            marker_text = f"------ MARKED {timestamp} ------"

            # Add to log filter for persistence through filtering
            # Add empty lines and marker as separate entries to preserve formatting
            self.log_filter.add_lines(["", "", marker_text, "", ""])

            # Always display the marker and its context lines
            # The filter will ensure these are always shown together
            self._append_log_line("")
            self._append_log_line("")
            self._append_log_line(marker_text)
            self._append_log_line("")
            self._append_log_line("")

            # Show notification
            self.app.notify(
                f"Position marked at {timestamp}",
                severity="information",
                timeout=2,
            )

    def _show_logs_ui(self):
        """Show the log display UI and hide the no-selection display."""
        self.log_display.display = True
        self.no_selection_display.display = False

    def _show_no_selection_ui(self):
        """Show the no-selection display and hide the log display."""
        self.log_display.display = False
        self.no_selection_display.display = True

    def _clear_logs(self):
        """Clear the log display and filter."""
        self.log_display.clear()
        # Preserve the search filter when clearing logs
        current_filter = self.log_filter.search_filter
        self.log_filter.clear()
        # Restore the search filter so new logs will be filtered correctly
        self.log_filter.set_filter(current_filter)
        self.showing_no_logs_message = False
        self.showing_loading_message = False

    def _auto_scroll_to_bottom(self):
        """Auto-scroll to the bottom of the log display if auto-follow is enabled."""
        if self.auto_follow:
            self.log_display.move_cursor(self.log_display.document.end)
            self.log_display.scroll_cursor_visible()

    def _append_log_line(self, line: str):
        """Append a line to the log display and handle auto-scrolling.

        Args:
            line: The log line to append
        """
        # Save scroll position if not following
        if not self.auto_follow:
            saved_scroll_y = self.log_display.scroll_y

        # Simply append the text
        current_text = self.log_display.text
        self.log_display.text = current_text + line + "\n"

        # Handle scrolling based on auto-follow setting
        if self.auto_follow:
            # Scroll to the bottom to follow new logs
            self.log_display.move_cursor(self.log_display.document.end)
            self.log_display.scroll_cursor_visible()
        else:
            # Restore the scroll position to prevent jumping
            self.log_display.scroll_y = saved_scroll_y

    def _is_container_stopped(self, status: str) -> bool:
        """Check if a container status indicates it's stopped.

        Args:
            status: The container status string

        Returns:
            True if the container is stopped, False otherwise
        """
        status_lower = status.lower()
        return any(state in status_lower for state in ["exited", "stopped", "created"])

    def _is_container_running(self, status: str) -> bool:
        """Check if a container status indicates it's running.

        Args:
            status: The container status string

        Returns:
            True if the container is running, False otherwise
        """
        status_lower = status.lower()
        return "running" in status_lower or "up" in status_lower

    def _update_header_for_item(
        self, item_type: str, item_id: str, item_data: dict
    ) -> bool:
        """Update the header based on the selected item type.

        Args:
            item_type: Type of item
            item_id: ID of the item
            item_data: Dictionary containing item information

        Returns:
            True if the item type has logs, False otherwise
        """
        item_name = item_data.get("name", item_id)

        if item_type == "container":
            self.header.update(f"📋 Log Pane - Container: {item_name}")
            return True
        elif item_type == "stack":
            self.header.update(f"📋 Log Pane - Stack: {item_name}")
            return True
        elif item_type == "network":
            self.header.update(f"📋 Log Pane - Network: {item_name}")
            self._show_no_logs_message_for_item_type("Networks")
            return False
        elif item_type == "image":
            self.header.update(f"📋 Log Pane - Image: {item_id[:12]}")
            self._show_no_logs_message_for_item_type("Images")
            return False
        elif item_type == "volume":
            self.header.update(f"📋 Log Pane - Volume: {item_name}")
            self._show_no_logs_message_for_item_type("Volumes")
            return False
        else:
            self.header.update("📋 Log Pane - Unknown Selection")
            return True

    def _create_tail_select(self) -> Select:
        """Create the tail select dropdown with current value."""
        tail_options = list(self.TAIL_OPTIONS)
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
        since_options = list(self.SINCE_OPTIONS)
        # If current value is not in options, add it
        if not any(opt[1] == self.LOG_SINCE for opt in since_options):
            since_options.insert(0, (f"{self.LOG_SINCE}", self.LOG_SINCE))

        return Select(
            options=since_options,
            value=self.LOG_SINCE,
            id="since-select",
            classes="log-setting",
        )
