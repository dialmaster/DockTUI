"""Manages text selection state and operations for the log viewer."""

import json
from typing import List, Optional, Tuple

from ...models.log_line import LogLine


class SelectionManager:
    """
    Manages text selection for the rich log viewer.

    This class handles all selection state and operations including:
    - Tracking selection start/end positions
    - Converting between screen coordinates and text positions
    - Extracting selected text from log lines
    - Managing selection during mouse/keyboard interactions
    """

    def __init__(self):
        """Initialize the selection manager."""
        # Selection state in virtual coordinates
        self.selection_start_virtual: Optional[int] = None
        self.selection_end_virtual: Optional[int] = None
        self.selection_start_x: Optional[int] = None
        self.selection_end_x: Optional[int] = None
        self.is_selecting: bool = False

    def clear_selection(self) -> None:
        """Clear all selection state."""
        self.selection_start_virtual = None
        self.selection_end_virtual = None
        self.selection_start_x = None
        self.selection_end_x = None
        self.is_selecting = False

    def start_selection(self, virtual_y: int, virtual_x: int) -> None:
        """Start a new selection at the given position.

        Args:
            virtual_y: Virtual Y coordinate (accounting for scroll)
            virtual_x: Virtual X coordinate (accounting for scroll)
        """
        self.selection_start_virtual = virtual_y
        self.selection_end_virtual = virtual_y
        self.selection_start_x = virtual_x
        # For initial click, end should be start + 1 to select the clicked character
        self.selection_end_x = virtual_x + 1
        self.is_selecting = True

    def update_selection_end(self, virtual_y: int, virtual_x: int) -> None:
        """Update the end position of the current selection.

        Args:
            virtual_y: Virtual Y coordinate (accounting for scroll)
            virtual_x: Virtual X coordinate (accounting for scroll)
        """
        self.selection_end_virtual = virtual_y
        self.selection_end_x = virtual_x

    def finish_selection(self) -> None:
        """Mark the current selection as finished."""
        self.is_selecting = False

    def select_all(self, total_virtual_lines: int, max_line_length: int = 999) -> None:
        """Select all visible text.

        Args:
            total_virtual_lines: Total number of virtual lines
            max_line_length: Maximum expected line length (default: 999)
        """
        self.selection_start_virtual = 0
        self.selection_start_x = 0
        self.selection_end_virtual = total_virtual_lines - 1
        self.selection_end_x = max_line_length

    def has_selection(self) -> bool:
        """Check if there is an active selection."""
        return (
            self.selection_start_virtual is not None
            and self.selection_end_virtual is not None
        )

    def get_normalized_selection(self) -> Tuple[int, int, int, int]:
        """Get normalized selection coordinates (start before end).

        Returns:
            Tuple of (start_y, start_x, end_y, end_x)
        """
        if not self.has_selection():
            return (0, 0, 0, 0)

        # Normalize selection range
        start_y = min(self.selection_start_virtual, self.selection_end_virtual)
        end_y = max(self.selection_start_virtual, self.selection_end_virtual)

        # Swap X coordinates if needed
        if self.selection_start_virtual > self.selection_end_virtual:
            start_x = self.selection_end_x or 0
            end_x = self.selection_start_x or 0
        else:
            start_x = self.selection_start_x or 0
            end_x = self.selection_end_x or 0

        return (start_y, start_x, end_y, end_x)

    def is_line_in_selection(self, virtual_y: int) -> bool:
        """Check if a virtual line is within the selection range.

        Args:
            virtual_y: Virtual Y coordinate to check

        Returns:
            True if the line is in the selection range
        """
        if not self.has_selection():
            return False

        start_y, _, end_y, _ = self.get_normalized_selection()
        return start_y <= virtual_y <= end_y

    def get_line_selection_range(
        self, virtual_y: int, line_text: str
    ) -> Tuple[int, int]:
        """Get the selection range for a specific line.

        Args:
            virtual_y: Virtual Y coordinate of the line
            line_text: Text content of the line

        Returns:
            Tuple of (start_pos, end_pos) for this line's selection
        """
        if not self.is_line_in_selection(virtual_y):
            return (0, 0)

        start_y, start_x, end_y, end_x = self.get_normalized_selection()

        # Determine selection range for this line
        sel_start = 0
        sel_end = len(line_text)

        if virtual_y == start_y == end_y:
            # Selection within single line
            sel_start = start_x
            sel_end = end_x
        elif virtual_y == start_y:
            # First line of multi-line selection
            sel_start = start_x
        elif virtual_y == end_y:
            # Last line of multi-line selection
            sel_end = end_x

        return (sel_start, sel_end)

    def get_selected_text(
        self, visible_lines: List[LogLine], count_json_lines_func, count_xml_lines_func
    ) -> str:
        """Get the currently selected text from visible lines.

        Args:
            visible_lines: List of visible log lines
            count_json_lines_func: Function to count JSON lines
            count_xml_lines_func: Function to count XML lines

        Returns:
            Selected text as a string
        """
        if not self.has_selection():
            return ""

        start_y, start_x, end_y, end_x = self.get_normalized_selection()

        selected_lines = []
        current_y = 0

        for log_line in visible_lines:
            # Calculate lines for this log entry
            if log_line.is_expanded and log_line.json_data:
                line_count = count_json_lines_func(log_line.json_data)
            elif log_line.is_expanded and log_line.xml_data:
                line_count = count_xml_lines_func(log_line.xml_data)
            else:
                line_count = 1

            # Check each virtual line in this log entry
            for offset in range(line_count):
                if current_y < start_y:
                    current_y += 1
                    continue
                if current_y > end_y:
                    break

                # This line is in the selection
                line_text = self._get_line_text_at_offset(
                    log_line, offset, count_json_lines_func, count_xml_lines_func
                )

                # Apply selection boundaries
                # Adjust for emoji insertion if needed
                adjusted_start_x = start_x
                adjusted_end_x = end_x

                # If this is the main line (offset 0) with JSON/XML emoji
                if offset == 0 and not log_line.is_expanded:
                    emoji_inserted = False
                    emoji_pos = None

                    if log_line.has_json and log_line.json_start_pos is not None:
                        emoji_pos = log_line.json_start_pos
                        emoji_inserted = True
                    elif log_line.has_xml and log_line.xml_start_pos is not None:
                        emoji_pos = log_line.xml_start_pos
                        emoji_inserted = True

                    # If emoji was inserted and selection is after it, adjust positions
                    if emoji_inserted and emoji_pos is not None:
                        if current_y == start_y and start_x > emoji_pos:
                            adjusted_start_x = max(
                                0, start_x - 2
                            )  # Emoji takes 2 positions in display
                        if current_y == end_y and end_x > emoji_pos:
                            adjusted_end_x = max(0, end_x - 2)

                if current_y == start_y == end_y:
                    # Selection within single line
                    selected_lines.append(line_text[adjusted_start_x:adjusted_end_x])
                elif current_y == start_y:
                    # First line of selection
                    selected_lines.append(line_text[adjusted_start_x:])
                elif current_y == end_y:
                    # Last line of selection
                    selected_lines.append(line_text[:adjusted_end_x])
                else:
                    # Middle line - select entire line
                    selected_lines.append(line_text)

                current_y += 1

            if current_y > end_y:
                break

        return "\n".join(selected_lines)

    def _get_line_text_at_offset(
        self,
        log_line: LogLine,
        offset: int,
        count_json_lines_func,
        count_xml_lines_func,
    ) -> str:
        """Get the text for a specific line offset within a log entry.

        Args:
            log_line: The log line
            offset: Offset within the log entry (0 for main line)
            count_json_lines_func: Function to count JSON lines
            count_xml_lines_func: Function to count XML lines

        Returns:
            Text content at the specified offset
        """
        if offset == 0:
            # Main log line
            return log_line.raw_text
        elif log_line.json_data:
            # JSON sub-line
            json_lines = json.dumps(log_line.json_data, indent=2).split("\n")
            if offset - 1 < len(json_lines):
                return json_lines[offset - 1]
            else:
                return ""
        elif log_line.xml_data:
            # XML sub-line
            # Import here to avoid circular dependency
            from ...services.log.xml_formatter import XMLFormatter

            xml_lines = XMLFormatter.format_xml_pretty(log_line.xml_data)
            if offset - 1 < len(xml_lines):
                return "".join(seg.text for seg in xml_lines[offset - 1])
            else:
                return ""
        else:
            return ""

    def extend_selection_up(self) -> None:
        """Extend selection up by one line."""
        if self.selection_end_virtual is not None and self.selection_end_virtual > 0:
            self.selection_end_virtual -= 1
            self.selection_end_x = 0

    def extend_selection_down(self, max_virtual_lines: int) -> None:
        """Extend selection down by one line.

        Args:
            max_virtual_lines: Maximum number of virtual lines
        """
        if (
            self.selection_end_virtual is not None
            and self.selection_end_virtual < max_virtual_lines - 1
        ):
            self.selection_end_virtual += 1
            self.selection_end_x = 0

    def extend_selection_left(self) -> None:
        """Extend selection left by one character."""
        if self.selection_end_x is not None and self.selection_end_x > 0:
            self.selection_end_x -= 1

    def extend_selection_right(self) -> None:
        """Extend selection right by one character."""
        self.selection_end_x = (self.selection_end_x or 0) + 1
