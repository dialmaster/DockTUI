import re
from collections import deque
from typing import Deque, List, Optional, Pattern, Tuple


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
        self._search_filter_lower = ""  # Cached lowercase version
        self.filtered_line_count = 0
        self.marker_pattern = "------ MARKED "
        self.pending_marker_context = 0
        self._is_regex = False
        self._regex_pattern: Optional[Pattern[str]] = None
        self._regex_valid = True

    def clear(self):
        """Clear all stored log lines."""
        self.all_log_lines.clear()
        self.filtered_line_count = 0
        self.pending_marker_context = 0
        self._regex_pattern = None
        self._is_regex = False
        self._regex_valid = True

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
            search_filter: The search string to filter logs.
                         If enclosed in '/', it will be treated as a regex pattern.
        """
        self.search_filter = search_filter.strip()

        if (
            len(self.search_filter) >= 2
            and self.search_filter.startswith("/")
            and self.search_filter.endswith("/")
        ):
            pattern = self.search_filter[1:-1]
            self._is_regex = True

            try:
                self._regex_pattern = re.compile(pattern, re.IGNORECASE)
                self._regex_valid = True
            except re.error:
                self._regex_pattern = None
                self._regex_valid = False
        else:
            self._is_regex = False
            self._regex_pattern = None
            self._regex_valid = True
            self._search_filter_lower = self.search_filter.lower()

    def get_filtered_lines(self) -> List[str]:
        """Get all log lines that match the current filter.

        Returns:
            List of filtered log lines
        """
        self.filtered_line_count = 0
        filtered_lines = []

        if not self.search_filter or not self._regex_valid:
            self.filtered_line_count = len(self.all_log_lines)
            return list(self.all_log_lines)

        # Single pass: find markers and filter lines
        marker_positions = []

        for i, line in enumerate(self.all_log_lines):
            # Check if it's a marker line
            is_marker = self.marker_pattern in line
            if is_marker:
                marker_positions.append(i)

            # Check if this line should be included
            should_include = False

            if is_marker:
                should_include = True
            elif self.matches_filter(line):
                should_include = True
            else:
                for marker_idx in marker_positions:
                    if abs(i - marker_idx) <= 2:
                        should_include = True
                        break

            if should_include:
                filtered_lines.append(line)
                self.filtered_line_count += 1

        # Second pass for lines that come before markers (look ahead)
        # This is more efficient than the previous implementation
        if marker_positions:
            # Check lines that come right before the first few markers
            for marker_idx in marker_positions:
                for offset in range(1, 3):  # Check 2 lines before each marker
                    line_idx = marker_idx - offset
                    if line_idx >= 0 and line_idx < len(self.all_log_lines):
                        line = self.all_log_lines[line_idx]
                        # Only add if not already included
                        if line not in filtered_lines:
                            # Insert at the correct position
                            insert_pos = 0
                            for j, existing_line in enumerate(filtered_lines):
                                if self.all_log_lines.index(existing_line) > line_idx:
                                    insert_pos = j
                                    break
                                insert_pos = j + 1
                            filtered_lines.insert(insert_pos, line)
                            self.filtered_line_count += 1

        return filtered_lines

    def matches_filter(self, line: str) -> bool:
        """Check if a line matches the current filter.

        Args:
            line: The log line to check

        Returns:
            True if the line matches the filter, False otherwise
        """
        if not self.search_filter or not self._regex_valid:
            return True
        if self.marker_pattern in line:
            return True

        if self._is_regex and self._regex_pattern:
            return bool(self._regex_pattern.search(line))
        else:
            return self._search_filter_lower in line.lower()

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
        # More efficient: check last 3 lines without creating new list
        line_count = len(self.all_log_lines)
        if line_count >= 1:
            start_idx = max(0, line_count - 3)
            for i in range(start_idx, line_count):
                if self.marker_pattern in self.all_log_lines[i]:
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

    def find_match_positions(self, line: str) -> List[Tuple[int, int]]:
        """Find all match positions in a line.

        Args:
            line: The line to search in

        Returns:
            List of (start, end) tuples for each match
        """
        if not self.search_filter or not self._regex_valid:
            return []

        matches = []

        if self._is_regex and self._regex_pattern:
            for match in self._regex_pattern.finditer(line):
                matches.append((match.start(), match.end()))
        else:
            line_lower = line.lower()
            search_len = len(self._search_filter_lower)
            start = 0

            while True:
                pos = line_lower.find(self._search_filter_lower, start)
                if pos == -1:
                    break
                matches.append((pos, pos + search_len))
                start = pos + 1

        return matches
