"""Rich log viewer widget with syntax highlighting and formatting support."""

import json
import logging
import threading
import time
from collections import OrderedDict
from typing import List, Optional, Tuple

from rich.cells import cell_len
from rich.segment import Segment
from textual.binding import Binding
from textual.events import Key, MouseDown, MouseMove, MouseUp
from textual.geometry import Size
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip

from ...models.log_line import LogLine
from ...services.log_formatter import LogFormatter
from ...services.log_parser import LogParser
from ...utils.clipboard import copy_to_clipboard_async
from .log_renderer import LogRenderer
from .log_selection_manager import SelectionManager
from .parsing_coordinator import ParsingCoordinator
from .virtual_scroll_manager import VirtualScrollManager

logger = logging.getLogger("DockTUI.rich_log_viewer")


class RichLogViewer(ScrollView):
    """
    Custom log viewer with rich formatting, syntax highlighting, and text selection.

    Features:
    - Syntax highlighting for timestamps, log levels, and JSON
    - Zebra striping for line demarcation
    - Text selection with mouse
    - JSON pretty-printing on demand
    - Efficient virtual scrolling
    """

    BINDINGS = [
        Binding("ctrl+shift+c", "copy_selection", "Copy", show=False),
        Binding("ctrl+a", "select_all", "Select All", show=False),
        Binding("p", "toggle_prettify", "Prettify", show=False),
    ]

    # Constants
    DOUBLE_CLICK_THRESHOLD = 0.5  # seconds
    DEFAULT_WIDTH = 80
    MIN_VIRTUAL_HEIGHT = 1
    MAX_CACHE_SIZE = 1000  # Maximum number of cached lines
    DEFAULT_MAX_LINES = 2000  # Default maximum number of log lines to keep
    VIRTUAL_SIZE_DEBOUNCE_DELAY = (
        1.0  # seconds to wait before recalculating virtual size
    )

    # Reactive properties
    auto_follow = reactive(True)
    syntax_highlight = reactive(True)
    zebra_stripe = reactive(True)

    def watch_auto_follow(self, value: bool) -> None:
        """React to auto_follow changes."""
        if value:
            # When auto-follow is enabled, immediately scroll to the end
            self.scroll_to_end_immediate()

    def on_mount(self) -> None:
        """Initialize when widget is mounted."""
        # Set app reference and start parsing coordinator
        self._parsing_coordinator.set_app(self.app)
        self._parsing_coordinator.start()

    def __init__(self, max_lines: int = None, *args, **kwargs):
        """Initialize the rich log viewer.

        Args:
            max_lines: Maximum number of log lines to keep in memory.
                      If None, defaults to DEFAULT_MAX_LINES.
        """
        super().__init__(*args, **kwargs)

        self.parser = LogParser()
        self.formatter = LogFormatter()

        self.max_lines = max_lines if max_lines is not None else self.DEFAULT_MAX_LINES
        self.log_lines: List[LogLine] = []
        self.visible_lines: List[LogLine] = []

        # Selection management
        self.selection_manager = SelectionManager()

        # Virtual scroll management
        self.virtual_scroll_manager = VirtualScrollManager()

        # Log rendering
        self.log_renderer = LogRenderer(
            self.parser, self.formatter, self.selection_manager
        )

        self.current_filter: str = ""
        self.line_height = 1

        self._line_cache: OrderedDict[int, List[Segment]] = OrderedDict()

        self._last_click_time = 0.0
        self._last_click_pos: Optional[Tuple[int, int]] = None

        # Thread safety lock for protecting shared state
        self._lock = threading.RLock()

        # Initialize with some height
        self.virtual_size = Size(self.DEFAULT_WIDTH, self.MIN_VIRTUAL_HEIGHT)

        # Background parsing setup
        self._parsing_coordinator = ParsingCoordinator(
            parse_complete_callback=self._on_parse_complete
        )

    def _get_cached_segments(self, cache_key: int) -> Optional[List[Segment]]:
        """Get segments from cache, updating LRU order."""
        if cache_key in self._line_cache:
            # Move to end (most recently used)
            self._line_cache.move_to_end(cache_key)
            return self._line_cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: int, segments: List[Segment]) -> None:
        """Add segments to cache with LRU eviction."""
        # Check if we need to evict
        if len(self._line_cache) >= self.MAX_CACHE_SIZE:
            # Remove least recently used (first item)
            self._line_cache.popitem(last=False)

        # Add new item
        self._line_cache[cache_key] = segments

    @property
    def virtual_size(self) -> Size:
        """Calculate the virtual size based on visible lines."""
        return self.virtual_scroll_manager.get_virtual_size(
            self.visible_lines, self.size, self._count_json_lines, self._count_xml_lines
        )

    @virtual_size.setter
    def virtual_size(self, size: Size) -> None:
        """Set the virtual size."""
        self.virtual_scroll_manager.set_virtual_size(size)

    def _invalidate_virtual_size(self):
        """Schedule a debounced virtual size recalculation."""

        def refresh_callback():
            # Trigger a refresh of the virtual size
            _ = self.virtual_size
            # Schedule UI refresh on the main thread
            self.app.call_from_thread(self.refresh)

        self.virtual_scroll_manager.invalidate_virtual_size(refresh_callback)

    def _invalidate_virtual_size_immediate(self):
        """Immediately invalidate virtual size cache without debouncing."""
        self.virtual_scroll_manager.invalidate_virtual_size_immediate()
        # Trigger immediate refresh
        _ = self.virtual_size

    def _schedule_parse(self, log_line: LogLine, priority: bool = False):
        """Schedule a log line for background parsing.

        Args:
            log_line: The log line to parse
            priority: If True, add to front of queue for immediate parsing
        """
        self._parsing_coordinator.schedule_parse(log_line, priority)

    def render_line(self, y: int) -> Strip:
        """Render a single line of the log viewer."""
        # Account for scroll position
        virtual_y = y + int(self.scroll_offset.y)

        # Find which log line corresponds to this virtual_y
        line_info = self._get_line_at_virtual_y(virtual_y)
        if not line_info:
            return Strip.blank(self.size.width)

        log_line, line_offset = line_info

        # Check cache first
        cache_key = (log_line.line_number, line_offset, log_line.is_expanded)
        cached_segments = self._get_cached_segments(cache_key)

        # Use the renderer to render the line
        strip, segments = self.log_renderer.render_line(
            virtual_y=virtual_y,
            log_line=log_line,
            line_offset=line_offset,
            cached_segments=cached_segments,
            widget_size=self.size,
            scroll_offset_x=self.scroll_offset.x,
            zebra_stripe=self.zebra_stripe,
            virtual_width=self.virtual_size.width,
        )

        # Cache the result if it wasn't cached
        if not (cached_segments and log_line.is_cache_valid()):
            self._add_to_cache(cache_key, segments)
            log_line._cache_valid = True

        return strip

    def _get_line_at_virtual_y(self, virtual_y: int) -> Optional[Tuple[LogLine, int]]:
        """
        Get the log line and offset within that line for a given virtual Y position.
        Returns (log_line, offset_within_line) or None.
        """
        return self.virtual_scroll_manager.get_line_at_virtual_y(
            virtual_y, self.visible_lines, self._count_json_lines, self._count_xml_lines
        )

    def _split_segments_into_lines(
        self, segments: List[Segment]
    ) -> List[List[Segment]]:
        """Split segments into separate lines."""
        lines = [[]]
        current_line = 0

        for segment in segments:
            text = segment.text
            style = segment.style

            # Handle newlines in segment text
            if "\n" in text:
                parts = text.split("\n")
                for i, part in enumerate(parts):
                    if i > 0:
                        lines.append([])
                        current_line += 1
                    if part:  # Don't add empty segments
                        lines[current_line].append(Segment(part, style))
            else:
                lines[current_line].append(segment)

        return lines

    def _count_json_lines(self, json_data: dict) -> int:
        """Count how many lines pretty-printed JSON will take."""
        return LogRenderer.count_json_lines(json_data)

    def _count_xml_lines(self, xml_data: str) -> int:
        """Count how many lines pretty-printed XML will take."""
        return LogRenderer.count_xml_lines(xml_data)

    # Public API methods
    def add_log_line(self, text: str, is_system_message: bool = False) -> None:
        """Add a new log line to the viewer."""
        with self._lock:
            # Create unparsed log line for lazy parsing
            line_number = len(self.log_lines)
            log_line = LogLine.create_unparsed(text, line_number, self.parser)

            # Mark as system message if specified (this doesn't require parsing)
            if is_system_message:
                log_line.is_system_message = True

            # Check if this is a marked line (quick check without full parsing)
            if "------ MARKED" in text and "------" in text:
                log_line.is_marked = True

            # Add to storage
            self.log_lines.append(log_line)

            # Schedule for background parsing
            self._schedule_parse(log_line)

            # Enforce memory limit - remove old lines if needed
            if len(self.log_lines) > self.max_lines:
                lines_to_remove = len(self.log_lines) - self.max_lines
                self.log_lines = self.log_lines[lines_to_remove:]

                # Update line numbers for remaining lines
                for i, line in enumerate(self.log_lines):
                    line.line_number = i

                # Need to refilter visible lines from scratch
                self.visible_lines = [
                    line for line in self.log_lines if self._should_show_line(line)
                ]
                self._invalidate_virtual_size()
            else:
                # Check if it passes filter
                if self._should_show_line(log_line):
                    self.visible_lines.append(log_line)
                    self._invalidate_virtual_size()

        # Force refresh to update virtual size before scrolling
        self.refresh()

        # Auto-scroll if enabled - use call_after_refresh to ensure size is updated
        if self.auto_follow:
            self.call_after_refresh(self.scroll_end)

    def add_log_lines(self, lines: List[str]) -> None:
        """Add multiple log lines efficiently."""
        if not lines:
            return

        with self._lock:
            # If adding these lines would exceed the limit, trim appropriately
            if len(self.log_lines) + len(lines) > self.max_lines:
                # Calculate how many existing lines to keep
                lines_to_keep = max(0, self.max_lines - len(lines))

                if lines_to_keep == 0:
                    # We're adding more lines than the limit, only keep the last max_lines
                    lines_to_add = lines[-self.max_lines :]
                    self.log_lines.clear()
                    start_line_number = 0
                else:
                    # Remove old lines to make room
                    self.log_lines = self.log_lines[-lines_to_keep:]
                    lines_to_add = lines
                    start_line_number = 0

                    # Update line numbers for kept lines
                    for i, line in enumerate(self.log_lines):
                        line.line_number = i
            else:
                lines_to_add = lines
                start_line_number = len(self.log_lines)

            # Process in smaller batches for better UI feedback
            BATCH_SIZE = 20  # Update UI every 20 lines for better scrollbar feedback

            for batch_start in range(0, len(lines_to_add), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(lines_to_add))
                batch_lines = lines_to_add[batch_start:batch_end]

                # Create unparsed log lines for lazy parsing
                new_log_lines = []
                for i, text in enumerate(batch_lines):
                    line_num = start_line_number + batch_start + i
                    log_line = LogLine.create_unparsed(text, line_num, self.parser)

                    # Quick check for marked lines without full parsing
                    if "------ MARKED" in text and "------" in text:
                        log_line.is_marked = True

                    new_log_lines.append(log_line)

                # Add to storage
                self.log_lines.extend(new_log_lines)

                # Schedule all new lines for background parsing
                for line in new_log_lines:
                    self._schedule_parse(line)

                # If we need to refilter (because old lines were removed), do it
                if start_line_number == 0:
                    # Refilter all visible lines
                    self.visible_lines = [
                        line for line in self.log_lines if self._should_show_line(line)
                    ]
                else:
                    # Just add new visible lines
                    new_visible = [
                        line for line in new_log_lines if self._should_show_line(line)
                    ]
                    if new_visible:
                        self.visible_lines.extend(new_visible)

                self._invalidate_virtual_size()

        # Force refresh to update scrollbar immediately
        self.refresh()

        # Final auto-scroll if enabled
        if self.auto_follow and lines_to_add:
            self.call_after_refresh(self.scroll_end)

    def clear(self) -> None:
        """Clear all log lines."""
        with self._lock:
            self.log_lines.clear()
            self.visible_lines.clear()
            self._line_cache.clear()
            self._invalidate_virtual_size_immediate()  # Use immediate for user action
            self.selection_manager.clear_selection()
        self.refresh()

    def on_unmount(self) -> None:
        """Clean up when widget is unmounted."""
        # Clean up virtual scroll manager
        self.virtual_scroll_manager.cleanup()

        # Stop parsing thread
        self._parsing_coordinator.stop()

    def set_filter(self, filter_text: str) -> None:
        """Apply a filter to log lines."""
        with self._lock:
            self.current_filter = filter_text.lower()

            # Refilter all lines
            if self.current_filter:
                self.visible_lines = [
                    line for line in self.log_lines if self._should_show_line(line)
                ]
            else:
                self.visible_lines = self.log_lines.copy()

            self._invalidate_virtual_size()
        self.refresh()

    def _should_show_line(self, log_line: LogLine) -> bool:
        """Check if a line should be shown based on current filter."""
        if not self.current_filter:
            return True

        # Always show marked lines
        if log_line.is_marked:
            return True

        # Always show system messages
        if log_line.is_system_message:
            return True

        # Check if filter text is in the line
        return self.current_filter in log_line.raw_text.lower()

    def get_selected_text(self) -> str:
        """Get the currently selected text."""
        return self.selection_manager.get_selected_text(
            self.visible_lines, self._count_json_lines, self._count_xml_lines
        )

    # Mouse handling for text selection
    def on_mouse_down(self, event: MouseDown) -> None:
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
                virtual_y = event.y + int(self.scroll_offset.y)

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
                    display_x = event.x + int(self.scroll_offset.x) - 1

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
                    virtual_x = event.x + int(self.scroll_offset.x) - 1
                    self.selection_manager.start_selection(virtual_y, virtual_x)

                self.refresh()

        elif event.button == 3:  # Right click
            # Copy selection
            self.action_copy_selection()

    def on_mouse_move(self, event: MouseMove) -> None:
        """Update selection during drag."""
        if self.selection_manager.is_selecting:
            virtual_y = event.y + int(self.scroll_offset.y)

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
                display_x = event.x + int(self.scroll_offset.x) - 1

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
                    event.x + int(self.scroll_offset.x) - 1
                )  # -1 to account for gutter width
                self.selection_manager.update_selection_end(virtual_y, virtual_x)

            self.refresh()

    def on_mouse_up(self, event: MouseUp) -> None:
        """Complete selection."""
        if event.button == 1 and self.selection_manager.is_selecting:
            self.selection_manager.finish_selection()
            # No need to normalize - we handle it in _apply_selection_to_segments

    def _coords_to_position(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        """Convert widget coordinates to line/character position."""
        # Account for scroll position
        virtual_y = y + int(self.scroll_offset.y)
        virtual_x = x + int(self.scroll_offset.x)

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
                line_idx = self.visible_lines.index(log_line)
                # For JSON lines, we'll treat them as part of the parent line
                # Character position is approximate based on virtual x coordinate
                return (line_idx, max(0, virtual_x))
            except ValueError:
                return None

        # Find the line index in visible_lines
        try:
            line_idx = self.visible_lines.index(log_line)
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

    def _handle_double_click(self, x: int, y: int) -> None:
        """Handle double-click to expand/collapse JSON/XML."""
        # The y coordinate from mouse event is already viewport-relative,
        # so we don't pass it through _coords_to_position which adds scroll offset
        virtual_y = y + int(self.scroll_offset.y)

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
            self._line_cache.clear()
            self._invalidate_virtual_size_immediate()  # Use immediate for user action
            self.refresh()

    def action_copy_selection(self) -> None:
        """Copy selected text to clipboard."""
        text = self.get_selected_text()
        if text:

            def on_copy_complete(success):
                if success:
                    self.app.notify("Copied to clipboard", severity="information")
                    # Clear selection after successful copy
                    self.selection_manager.clear_selection()
                    self.refresh()
                else:
                    self.app.notify(
                        "Failed to copy. Install xclip or pyperclip.", severity="error"
                    )

            copy_to_clipboard_async(text, on_copy_complete)

    def action_select_all(self) -> None:
        """Select all visible text."""
        if self.visible_lines:
            # Calculate total virtual lines
            total_virtual_lines = (
                self.virtual_scroll_manager.calculate_total_virtual_lines(
                    self.visible_lines, self._count_json_lines, self._count_xml_lines
                )
            )

            self.selection_manager.select_all(total_virtual_lines)
            self.refresh()

    def scroll_to_end_immediate(self) -> None:
        """Immediately scroll to the end of the logs."""
        # Force a refresh to ensure virtual size is up to date
        self.refresh()
        # Use call_after_refresh to ensure the scroll happens after size is updated
        self.call_after_refresh(self.scroll_end)

    def action_toggle_prettify(self) -> None:
        """Toggle pretty-printing for JSON/XML on line at cursor."""
        # Get the line under the mouse or use selection
        target_line = None

        # If we have a selection, use the start line
        if self.selection_manager.has_selection():
            start_y, _, _, _ = self.selection_manager.get_normalized_selection()
            line_info = self._get_line_at_virtual_y(start_y)
            if line_info:
                target_line = line_info[0]
        else:
            # Try to use the line at current scroll position
            # For now, use the first visible line with JSON or XML
            virtual_y = int(self.scroll_offset.y)
            line_info = self._get_line_at_virtual_y(virtual_y)
            if line_info:
                target_line = line_info[0]

        # If we found a line with JSON or XML, toggle it
        if target_line and (target_line.has_json or target_line.has_xml):
            target_line.is_expanded = not target_line.is_expanded
            target_line.invalidate_cache()
            self._invalidate_virtual_size_immediate()  # Use immediate for user action
            self.refresh()

    def on_key(self, event: Key) -> None:
        """Handle keyboard events for selection and navigation."""
        # Handle selection with shift+arrow keys
        if event.key in ["shift+up", "shift+down", "shift+left", "shift+right"]:
            # If no selection exists, start from current position
            if not self.selection_manager.has_selection():
                # Start from current scroll position
                virtual_y = int(self.scroll_offset.y)
                self.selection_manager.start_selection(virtual_y, 0)
                # Finish the selection start to allow extending
                self.selection_manager.is_selecting = False

            if event.key == "shift+up":
                self.selection_manager.extend_selection_up()
            elif event.key == "shift+down":
                # Calculate max virtual lines
                max_virtual = self.virtual_scroll_manager.calculate_total_virtual_lines(
                    self.visible_lines, self._count_json_lines, self._count_xml_lines
                )
                self.selection_manager.extend_selection_down(max_virtual)
            elif event.key == "shift+left":
                self.selection_manager.extend_selection_left()
            elif event.key == "shift+right":
                self.selection_manager.extend_selection_right()

            self.refresh()

    def on_scroll(self, event) -> None:
        """Handle scroll events to pre-parse upcoming lines."""
        super().on_scroll(event)

        # Pre-parse lines that are about to become visible
        if self.visible_lines and self.size:
            # Calculate which lines are in the viewport
            viewport_start, viewport_end = (
                self.virtual_scroll_manager.calculate_viewport_range(
                    self.scroll_offset.y, self.size.height
                )
            )

            # Find lines in viewport
            lines_in_viewport = self.virtual_scroll_manager.find_lines_in_viewport(
                self.visible_lines,
                viewport_start,
                viewport_end,
                self._count_json_lines,
                self._count_xml_lines,
            )

            # Pre-parse unparsed lines
            for line, _ in lines_in_viewport:
                if not line.is_parsed:
                    self._schedule_parse(line, priority=True)

    def _on_parse_complete(self, log_line: LogLine):
        """Called when a log line has been parsed in the background."""
        # Invalidate cache for this line to force re-render
        log_line.invalidate_cache()

        # Check if this line is currently visible
        if self.visible_lines and log_line in self.visible_lines:
            # Only refresh if the line might be in the viewport
            if self.size:
                viewport_start = int(self.scroll_offset.y)
                viewport_end = viewport_start + self.size.height

                # Find the virtual Y position of this line
                current_y = 0
                for line in self.visible_lines:
                    if line == log_line:
                        # This line is visible, check if it's in viewport
                        if viewport_start <= current_y <= viewport_end:
                            self.refresh()
                        break

                    # Update current_y
                    if line.is_expanded and line.is_parsed:
                        if line.json_data:
                            current_y += self._count_json_lines(line.json_data)
                        elif line.xml_data:
                            current_y += self._count_xml_lines(line.xml_data)
                        else:
                            current_y += 1
                    else:
                        current_y += 1
