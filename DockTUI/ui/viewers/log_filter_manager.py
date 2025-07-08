import logging
from datetime import datetime
from typing import Callable, List, Optional

from textual.timer import Timer

from ...config import config
from ...services.log_filter import LogFilter

logger = logging.getLogger("DockTUI.log_filter_manager")


class LogFilterManager:
    """Manages log filtering, search, and marker functionality."""

    def __init__(self, parent):
        """Initialize the LogFilterManager.

        Args:
            parent: The parent widget (LogPane) for timer management
        """
        self.parent = parent

        # Initialize the log filter
        self.log_filter = LogFilter(max_lines=config.get("log.max_lines", 2000))

        # Filter state
        self.filter_timer: Optional[Timer] = None
        self.pending_filter_value: Optional[str] = None

        # Callbacks
        self.on_filter_changed: Optional[Callable[[], None]] = None
        self.on_marker_added: Optional[Callable[[List[str]], None]] = None

    def clear(self):
        """Clear the filter state while preserving the search filter."""
        current_filter = self.log_filter.search_filter
        self.log_filter.clear()
        # Restore the search filter so new logs will be filtered correctly
        self.log_filter.set_filter(current_filter)

    def add_line(self, line: str):
        """Add a log line to the filter buffer.

        Args:
            line: The log line to add
        """
        self.log_filter.add_line(line)

    def add_lines(self, lines: List[str]):
        """Add multiple log lines to the filter buffer.

        Args:
            lines: List of log lines to add
        """
        self.log_filter.add_lines(lines)

    def should_show_line(self, line: str) -> bool:
        """Check if a line should be shown based on current filter.

        Args:
            line: The log line to check

        Returns:
            True if the line should be shown
        """
        return self.log_filter.should_show_line_with_context(line)

    def has_filter(self) -> bool:
        """Check if a filter is currently active.

        Returns:
            True if a filter is set
        """
        return self.log_filter.has_filter()

    def get_all_lines(self) -> List[str]:
        """Get all stored log lines.

        Returns:
            List of all stored log lines
        """
        return self.log_filter.get_all_lines()

    def get_current_filter(self) -> str:
        """Get the current search filter.

        Returns:
            The current search filter string
        """
        return self.log_filter.search_filter

    def handle_search_input_changed(self, value: str):
        """Handle search input changes with debouncing.

        Args:
            value: The new search input value
        """
        # Cancel any existing timer
        if self.filter_timer:
            self.filter_timer.stop()

        # Store the pending filter value
        self.pending_filter_value = value

        # Start a new timer to apply the filter after a delay
        self.filter_timer = self.parent.set_timer(0.3, self._apply_filter_debounced)

    def _apply_filter_debounced(self):
        """Apply the filter after debounce delay."""
        if self.pending_filter_value is not None:
            self.log_filter.set_filter(self.pending_filter_value)
            # Always notify parent that filter has changed, even if no logs
            # This ensures UI updates properly when viewing containers with no logs
            if self.on_filter_changed:
                self.on_filter_changed()
            self.pending_filter_value = None

    def add_marker(self) -> List[str]:
        """Add a timestamp marker to the logs.

        Returns:
            The marker lines that were added
        """
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        marker_text = f"------ MARKED {timestamp} ------"

        # Create marker lines with empty lines for spacing
        marker_lines = ["", "", marker_text, "", ""]

        # Add to log filter for persistence through filtering
        self.log_filter.add_lines(marker_lines)

        # Notify parent if callback is set
        if self.on_marker_added:
            self.on_marker_added(marker_lines)

        return marker_lines

    def get_filtered_lines_for_display(self) -> List[str]:
        """Get all lines that should be displayed based on current filter.

        This is used when re-filtering the entire log display.

        Returns:
            List of lines that match the current filter
        """
        all_lines = self.log_filter.get_all_lines()

        # If no filter, return all lines
        if not self.has_filter():
            return all_lines

        # Otherwise filter lines with context awareness
        filtered_lines = []
        for line in all_lines:
            if self.log_filter.should_show_line_with_context(line):
                filtered_lines.append(line)

        return filtered_lines

    def cleanup(self):
        """Clean up resources."""
        if self.filter_timer:
            self.filter_timer.stop()
            self.filter_timer = None
