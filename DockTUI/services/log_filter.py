from collections import deque
from typing import Deque, List


class LogFilter:
    """Handles log filtering and search functionality."""

    def __init__(self, max_lines: int = 2000):
        """Initialize the log filter.

        Args:
            max_lines: Maximum number of log lines to store
        """
        self.max_lines = max_lines
        self.all_log_lines: Deque[str] = deque(maxlen=max_lines)
        self.search_filter = ""
        self.filtered_line_count = 0
        self.marker_pattern = "------ MARKED "
        self.pending_marker_context = 0  # Track lines to show after a marker

    def clear(self):
        """Clear all stored log lines."""
        self.all_log_lines.clear()
        self.filtered_line_count = 0
        self.pending_marker_context = 0

    def add_line(self, line: str):
        """Add a log line to the buffer.

        Args:
            line: The log line to add
        """
        self.all_log_lines.append(line)

    def add_lines(self, lines: List[str]):
        """Add multiple log lines to the buffer.

        Args:
            lines: List of log lines to add
        """
        for line in lines:
            self.all_log_lines.append(line)

    def set_filter(self, search_filter: str):
        """Set the search filter.

        Args:
            search_filter: The search string to filter logs
        """
        self.search_filter = search_filter.strip()

    def get_filtered_lines(self) -> List[str]:
        """Get all log lines that match the current filter.

        Returns:
            List of filtered log lines
        """
        self.filtered_line_count = 0
        filtered_lines = []
        marker_indices = []

        # First pass: find all marker lines and lines that match the filter
        for i, line in enumerate(self.all_log_lines):
            if self.marker_pattern in line:
                marker_indices.append(i)

        # Second pass: build the filtered list
        for i, line in enumerate(self.all_log_lines):
            # Check if this line should be included
            should_include = False

            # Always include if no filter
            if not self.search_filter:
                should_include = True
            # Include if matches filter
            elif self.search_filter.lower() in line.lower():
                should_include = True
            # Include if it's a marker line
            elif self.marker_pattern in line:
                should_include = True
            # Include if it's within 2 lines of a marker
            else:
                for marker_idx in marker_indices:
                    if abs(i - marker_idx) <= 2:
                        should_include = True
                        break

            if should_include:
                filtered_lines.append(line)
                self.filtered_line_count += 1

        return filtered_lines

    def matches_filter(self, line: str) -> bool:
        """Check if a line matches the current filter.

        Args:
            line: The log line to check

        Returns:
            True if the line matches the filter, False otherwise
        """
        if not self.search_filter:
            return True
        # Always show marker lines
        if self.marker_pattern in line:
            return True
        return self.search_filter.lower() in line.lower()

    def should_show_line_with_context(self, line: str) -> bool:
        """Check if a line should be shown considering marker context.

        This method tracks marker context for real-time log processing.

        Args:
            line: The log line to check

        Returns:
            True if the line should be shown, False otherwise
        """
        # If it's a marker line, start showing context
        if self.marker_pattern in line:
            self.pending_marker_context = 2  # Show 2 lines after marker
            return True

        # If we're in marker context, always show
        if self.pending_marker_context > 0:
            self.pending_marker_context -= 1
            return True

        # Check if we need to show lines before a marker
        # Look ahead in the last few lines to see if a marker is coming
        recent_lines = list(self.all_log_lines)[-3:]  # Last 3 lines
        for recent_line in recent_lines:
            if self.marker_pattern in recent_line:
                return True

        # Otherwise use normal filter
        return self.matches_filter(line)

    def get_line_count(self) -> int:
        """Get the total number of stored log lines.

        Returns:
            The number of stored log lines
        """
        return len(self.all_log_lines)

    def get_filtered_line_count(self) -> int:
        """Get the number of lines matching the current filter.

        Returns:
            The number of filtered lines
        """
        return self.filtered_line_count

    def has_filter(self) -> bool:
        """Check if a filter is currently active.

        Returns:
            True if a filter is set, False otherwise
        """
        return bool(self.search_filter)

    def get_all_lines(self) -> List[str]:
        """Get all stored log lines.

        Returns:
            List of all stored log lines
        """
        return list(self.all_log_lines)
