"""Mouse event handler for RichLogViewer widget."""

import json
import logging
import time
from typing import Callable, Optional, Tuple

from rich.cells import cell_len
from textual.events import MouseDown, MouseMove, MouseUp

from .log_selection_manager import SelectionManager

logger = logging.getLogger("DockTUI.mouse_event_handler")


class MouseEventHandler:
    """
    Handles mouse events for RichLogViewer.

    This class encapsulates all mouse interaction logic including:
    - Click and drag selection
    - Double-click to expand/collapse JSON/XML
    - Right-click to copy
    - Coordinate conversion utilities
    """

    # Constants
    DOUBLE_CLICK_THRESHOLD = 0.5  # seconds

    def __init__(
        self,
        selection_manager: SelectionManager,
        get_line_at_virtual_y: Callable,
        count_json_lines: Callable,
        count_xml_lines: Callable,
        get_visible_lines: Callable,
        get_scroll_offset: Callable,
        invalidate_virtual_size_immediate: Callable,
        clear_line_cache: Callable,
        refresh: Callable,
        action_copy_selection: Callable,
    ):
        """Initialize mouse event handler.

        Args:
            selection_manager: Selection manager instance
            get_line_at_virtual_y: Function to get line at virtual Y position
            count_json_lines: Function to count JSON lines
            count_xml_lines: Function to count XML lines
            get_visible_lines: Function to get visible lines list
            get_scroll_offset: Function to get current scroll offset
            invalidate_virtual_size_immediate: Function to invalidate virtual size
            clear_line_cache: Function to clear line cache
            refresh: Function to refresh display
            action_copy_selection: Function to copy selection to clipboard
        """
        self.selection_manager = selection_manager
        self._get_line_at_virtual_y = get_line_at_virtual_y
        self._count_json_lines = count_json_lines
        self._count_xml_lines = count_xml_lines
        self._get_visible_lines = get_visible_lines
        self._get_scroll_offset = get_scroll_offset
        self._invalidate_virtual_size_immediate = invalidate_virtual_size_immediate
        self._clear_line_cache = clear_line_cache
        self._refresh = refresh
        self._action_copy_selection = action_copy_selection

        # Track double-click state
        self._last_click_time = 0.0
        self._last_click_pos: Optional[Tuple[int, int]] = None

    def handle_mouse_down(self, event: MouseDown) -> None:
        """Start text selection on left click, copy on right click, double-click for JSON."""
        if event.button == 1:  # Left click
            # Check for double-click
            current_time = time.time()
            current_pos = (event.x, event.y)

            is_double_click = False
            if self._last_click_pos:
                # Check if click is in roughly the same position (within 2 cells)
                last_x, last_y = self._last_click_pos
                if abs(event.x - last_x) <= 2 and abs(event.y - last_y) <= 1:
                    time_diff = current_time - self._last_click_time
                    if time_diff <= self.DOUBLE_CLICK_THRESHOLD:
                        is_double_click = True

            if is_double_click:
                # Handle double-click to expand/collapse JSON
                self._handle_double_click(event.x, event.y)
                # Reset to prevent triple-click from being detected as double-click
                self._last_click_time = 0
                self._last_click_pos = None
            else:
                # Update last click info for next time
                self._last_click_time = current_time
                self._last_click_pos = current_pos

                # Normal click - start selection
                self.selection_manager.clear_selection()

                # Calculate virtual Y position
                scroll_offset = self._get_scroll_offset()
                virtual_y = event.y + int(scroll_offset.y)

                # Get the line at this position to calculate proper character index
                line_info = self._get_line_at_virtual_y(virtual_y)
                if line_info:
                    log_line, line_offset = line_info

                    # Get the actual text for this line
                    if line_offset == 0:
                        line_text = log_line.raw_text
                    elif log_line.json_data:
                        json_lines = json.dumps(log_line.json_data, indent=2).split(
                            "\n"
                        )
                        line_text = (
                            json_lines[line_offset - 1]
                            if line_offset - 1 < len(json_lines)
                            else ""
                        )
                    elif log_line.xml_data:
                        from ...services.log.xml_formatter import XMLFormatter

                        xml_lines = XMLFormatter.format_xml_pretty(log_line.xml_data)
                        line_text = (
                            "".join(seg.text for seg in xml_lines[line_offset - 1])
                            if line_offset - 1 < len(xml_lines)
                            else ""
                        )
                    else:
                        line_text = ""

                    # Convert display position to character index
                    # Account for horizontal scroll offset and gutter
                    # Note: event.x is already relative to the content area in ScrollView
                    # There seems to be a 1-character offset (possibly a gutter or padding)
                    display_x = event.x + int(scroll_offset.x) - 1

                    # Account for emojis that are inserted at specific positions
                    # The formatter inserts "📋 " (emoji + space = 3 units) or "📄 " at json/xml start positions
                    if (
                        line_offset == 0 and not log_line.is_expanded
                    ):  # Only on the main line when not expanded
                        if log_line.has_json and log_line.json_start_pos is not None:
                            # Convert json_start_pos to display position to see if we're after it
                            json_display_pos = self._char_index_to_display_x(
                                line_text, log_line.json_start_pos
                            )
                            if display_x > json_display_pos:
                                # Click is after the emoji insertion point, adjust by emoji width
                                display_x -= 1  # emoji width is 1
                        elif log_line.has_xml and log_line.xml_start_pos is not None:
                            # Convert xml_start_pos to display position to see if we're after it
                            xml_display_pos = self._char_index_to_display_x(
                                line_text, log_line.xml_start_pos
                            )
                            if display_x > xml_display_pos:
                                # Click is after the emoji insertion point, adjust by emoji width
                                display_x -= 1  # emoji width is 1

                    char_index = self._display_x_to_char_index(line_text, display_x)

                    # Debug: log the conversion
                    # logger.debug(f"Mouse click: display_x={display_x}, char_index={char_index}, text_len={len(line_text)}")
                    # if char_index < len(line_text):
                    #     logger.debug(f"Char at index: '{line_text[char_index]}'")

                    self.selection_manager.start_selection(virtual_y, char_index)
                else:
                    # Fallback to simple calculation
                    virtual_x = event.x + int(scroll_offset.x) - 1
                    self.selection_manager.start_selection(virtual_y, virtual_x)

                self._refresh()

        elif event.button == 3:  # Right click
            # Copy selection
            self._action_copy_selection()

    def handle_mouse_move(self, event: MouseMove) -> None:
        """Update selection during drag."""
        if self.selection_manager.is_selecting:
            scroll_offset = self._get_scroll_offset()
            virtual_y = event.y + int(scroll_offset.y)

            # Get the line at this position to calculate proper character index
            line_info = self._get_line_at_virtual_y(virtual_y)
            if line_info:
                log_line, line_offset = line_info

                # Get the actual text for this line
                if line_offset == 0:
                    line_text = log_line.raw_text
                elif log_line.json_data:
                    json_lines = json.dumps(log_line.json_data, indent=2).split("\n")
                    line_text = (
                        json_lines[line_offset - 1]
                        if line_offset - 1 < len(json_lines)
                        else ""
                    )
                elif log_line.xml_data:
                    from ...services.log.xml_formatter import XMLFormatter

                    xml_lines = XMLFormatter.format_xml_pretty(log_line.xml_data)
                    line_text = (
                        "".join(seg.text for seg in xml_lines[line_offset - 1])
                        if line_offset - 1 < len(xml_lines)
                        else ""
                    )
                else:
                    line_text = ""

                # Convert display position to character index
                # Account for horizontal scroll offset and gutter
                display_x = event.x + int(scroll_offset.x) - 1

                # Account for emojis that are inserted at specific positions
                if (
                    line_offset == 0 and not log_line.is_expanded
                ):  # Only on the main line when not expanded
                    # Check for either JSON or XML emoji insertion
                    emoji_pos = None
                    if log_line.has_json and log_line.json_start_pos is not None:
                        emoji_pos = log_line.json_start_pos
                    elif log_line.has_xml and log_line.xml_start_pos is not None:
                        emoji_pos = log_line.xml_start_pos

                    if emoji_pos is not None:
                        # Convert emoji position to display position to see if we're after it
                        emoji_display_pos = self._char_index_to_display_x(
                            line_text, emoji_pos
                        )
                        if display_x > emoji_display_pos:
                            # Drag is after the emoji insertion point, adjust by emoji width
                            display_x -= 1

                char_index = self._display_x_to_char_index(line_text, display_x)

                self.selection_manager.update_selection_end(virtual_y, char_index)
            else:
                # Fallback to simple calculation
                virtual_x = (
                    event.x + int(scroll_offset.x) - 1
                )  # -1 to account for gutter width
                self.selection_manager.update_selection_end(virtual_y, virtual_x)

            self._refresh()

    def handle_mouse_up(self, event: MouseUp) -> None:
        """Complete selection."""
        if event.button == 1 and self.selection_manager.is_selecting:
            self.selection_manager.finish_selection()
            # No need to normalize - we handle it in _apply_selection_to_segments

    def _handle_double_click(self, x: int, y: int) -> None:
        """Handle double-click to expand/collapse JSON/XML."""
        # The y coordinate from mouse event is already viewport-relative,
        # so we don't pass it through _coords_to_position which adds scroll offset
        scroll_offset = self._get_scroll_offset()
        virtual_y = y + int(scroll_offset.y)

        # Find which log line corresponds to this virtual_y directly
        line_info = self._get_line_at_virtual_y(virtual_y)
        if not line_info:
            return

        log_line, line_offset = line_info

        # Ensure the line is parsed to check for JSON/XML
        log_line.ensure_parsed()

        # Allow expanding/collapsing if the line has JSON or XML
        # If clicking on any part of an expanded content (offset > 0), collapse it
        # If clicking on a collapsed line (offset == 0), expand it
        if log_line.has_json or log_line.has_xml:
            # Toggle expansion
            log_line.is_expanded = not log_line.is_expanded
            log_line.invalidate_cache()
            # Clear the entire line cache to force re-render
            self._clear_line_cache()
            self._invalidate_virtual_size_immediate()  # Use immediate for user action
            self._refresh()

    def coords_to_position(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        """Convert widget coordinates to line/character position."""
        # Account for scroll position
        scroll_offset = self._get_scroll_offset()
        virtual_y = y + int(scroll_offset.y)
        virtual_x = x + int(scroll_offset.x)

        # Find which log line corresponds to this virtual_y
        line_info = self._get_line_at_virtual_y(virtual_y)
        if not line_info:
            return None

        log_line, line_offset = line_info

        # For expanded JSON, we need to handle the offset
        if log_line.is_expanded and line_offset > 0:
            # This is a sub-line of expanded JSON
            # Map to the parent log line but track that it's in the JSON
            try:
                visible_lines = self._get_visible_lines()
                line_idx = visible_lines.index(log_line)
                # For JSON lines, we'll treat them as part of the parent line
                # Character position is approximate based on virtual x coordinate
                return (line_idx, max(0, virtual_x))
            except ValueError:
                return None

        # Find the line index in visible_lines
        try:
            visible_lines = self._get_visible_lines()
            line_idx = visible_lines.index(log_line)
        except ValueError:
            return None

        # Calculate character position based on virtual x coordinate
        # This is simplified - in reality we'd need to account for character widths
        char_pos = max(0, min(virtual_x, len(log_line.raw_text)))

        return (line_idx, char_pos)

    def _display_x_to_char_index(self, text: str, display_x: int) -> int:
        """Convert display position to character index accounting for Unicode widths.

        Args:
            text: The text string
            display_x: The display position (accounting for character widths)

        Returns:
            Character index in the string
        """
        if display_x <= 0:
            return 0

        current_display_pos = 0
        for i, char in enumerate(text):
            char_width = cell_len(char)
            # Check if we've reached or passed the target display position
            if current_display_pos + char_width > display_x:
                # The click is within this character's display area
                # For multi-width chars, decide based on which half was clicked
                if display_x - current_display_pos < char_width / 2:
                    return i
                else:
                    return i + 1
            current_display_pos += char_width

        # If we've gone through all characters, return the length
        return len(text)

    def _char_index_to_display_x(self, text: str, char_index: int) -> int:
        """Convert character index to display position accounting for Unicode widths.

        Args:
            text: The text string
            char_index: Character index in the string

        Returns:
            Display position (accounting for character widths)
        """
        if char_index <= 0:
            return 0

        display_pos = 0
        for i, char in enumerate(text[:char_index]):
            display_pos += cell_len(char)

        return display_pos
