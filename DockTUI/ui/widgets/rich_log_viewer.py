"""Rich log viewer widget with syntax highlighting and formatting support."""

import logging
import threading
from collections import OrderedDict
from typing import List, Optional, Tuple

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
from .mouse_event_handler import MouseEventHandler
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

        # Mouse event handling
        self.mouse_handler = MouseEventHandler(
            selection_manager=self.selection_manager,
            get_line_at_virtual_y=self._get_line_at_virtual_y,
            count_json_lines=self._count_json_lines,
            count_xml_lines=self._count_xml_lines,
            get_visible_lines=lambda: self.visible_lines,
            get_scroll_offset=lambda: self.scroll_offset,
            invalidate_virtual_size_immediate=self._invalidate_virtual_size_immediate,
            clear_line_cache=lambda: self._line_cache.clear(),
            refresh=self.refresh,
            action_copy_selection=self.action_copy_selection,
        )

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
        # Multiple approaches to force scrollbar update (Textual issue)
        # 1. Force scroll position update
        current_y = self.scroll_offset.y
        self.scroll_to(y=current_y, animate=False, force=True)
        # 2. Refresh with layout flag
        self.refresh(layout=True)

    def _schedule_parse(self, log_line: LogLine, priority: bool = False):
        """Schedule a log line for background parsing.

        Args:
            log_line: The log line to parse
            priority: If True, add to front of queue for immediate parsing
        """
        self._parsing_coordinator.schedule_parse(log_line, priority)

    def render_line(self, y: int) -> Strip:
        """Render a single line of the log viewer."""
        # Show "no matches" message if we have a filter but no visible lines
        if self.current_filter and not self.visible_lines:
            if y == 0:
                from rich.style import Style
                from rich.text import Text

                message = Text(
                    "No log lines match filter",
                    style=Style(color="yellow", italic=True),
                )
                # Pad the message to fill the entire width
                message_str = message.plain
                if len(message_str) < self.size.width:
                    message = Text(
                        message_str.ljust(self.size.width),
                        style=Style(color="yellow", italic=True),
                    )
                segments = list(message.render(self.app.console))
                return Strip(segments, self.size.width)
            else:
                # Return blank lines for all other positions
                return Strip.blank(self.size.width)

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
        self.refresh(layout=True)

        # Auto-scroll if enabled - use call_after_refresh to ensure size is updated
        if self.auto_follow:
            self.call_after_refresh(self.scroll_end)

    def add_log_lines(self, lines: List[str], unfiltered: bool = False) -> None:
        """Add multiple log lines efficiently.

        Args:
            lines: List of log line strings to add
            unfiltered: If True, lines are already filtered and should all be added to visible_lines
        """
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
            # Use larger batches for filtered operations to reduce overhead
            BATCH_SIZE = 100 if unfiltered else 20

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

                # Handle visibility based on whether lines are pre-filtered
                if unfiltered:
                    # Lines are already filtered, add all of them to visible_lines
                    if start_line_number == 0:
                        # Replace all visible lines with new ones
                        self.visible_lines = new_log_lines.copy()
                    else:
                        # Just add new lines
                        self.visible_lines.extend(new_log_lines)
                else:
                    # Need to filter lines
                    if start_line_number == 0:
                        # Refilter all visible lines
                        self.visible_lines = [
                            line
                            for line in self.log_lines
                            if self._should_show_line(line)
                        ]
                    else:
                        # Just add new visible lines
                        new_visible = [
                            line
                            for line in new_log_lines
                            if self._should_show_line(line)
                        ]
                        if new_visible:
                            self.visible_lines.extend(new_visible)

                # Use immediate invalidation for filter operations
                if unfiltered:
                    self._invalidate_virtual_size_immediate()
                else:
                    self._invalidate_virtual_size()

        # Force refresh to update scrollbar immediately
        self.refresh(layout=True)

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
        self.refresh(layout=True)

    def on_unmount(self) -> None:
        """Clean up when widget is unmounted."""
        # Clean up virtual scroll manager
        self.virtual_scroll_manager.cleanup()

        # Stop parsing thread
        self._parsing_coordinator.stop()

    def set_filter(self, filter_text: str) -> None:
        """Update the current filter text without re-filtering.

        Note: This method now only updates the filter text. Actual filtering
        should be done before calling add_log_lines() with unfiltered=True.
        """
        with self._lock:
            self.current_filter = filter_text.lower()

    def refilter_existing_lines(self) -> None:
        """Refilter the existing log lines based on current filter."""
        with self._lock:
            # Refilter all existing lines
            if self.current_filter:
                # Find all marker positions first
                marker_positions = []
                for i, line in enumerate(self.log_lines):
                    if line.is_marked:
                        marker_positions.append(i)

                # Filter lines with marker context
                self.visible_lines = []
                for i, line in enumerate(self.log_lines):
                    should_show = False

                    # Always show marked lines
                    if line.is_marked:
                        should_show = True
                    # Always show system messages
                    elif line.is_system_message:
                        should_show = True
                    # Check if matches filter
                    elif self.current_filter in line.raw_text.lower():
                        should_show = True
                    else:
                        # Check if within 2 lines of a marker
                        for marker_idx in marker_positions:
                            if abs(i - marker_idx) <= 2:
                                should_show = True
                                break

                    if should_show:
                        self.visible_lines.append(line)
            else:
                # No filter - show all lines
                self.visible_lines = self.log_lines.copy()

            self._invalidate_virtual_size_immediate()

        # Workaround for Textual scrollbar update delay (GitHub issues #5631, #5632)
        # Force scrollbar to update immediately using multiple techniques

        # First, do an immediate refresh with layout
        self.refresh(layout=True)

        # Then schedule additional updates after refresh
        def force_scrollbar_update():
            # Access virtual size to ensure it's calculated
            _ = self.virtual_size
            # Slightly modify scroll position to force full recalculation
            current_y = self.scroll_offset.y
            # Move by 1 pixel then back - forces scrollbar update
            self.scroll_to(x=0, y=current_y + 1, animate=False, force=True)
            self.scroll_to(x=0, y=current_y, animate=False, force=True)
            # Final refresh
            self.refresh()

        # Use multiple call_after_refresh for aggressive update
        self.call_after_refresh(force_scrollbar_update)
        # Second call to ensure it happens
        self.call_after_refresh(lambda: self.refresh(layout=True))

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
        self.mouse_handler.handle_mouse_down(event)

    def on_mouse_move(self, event: MouseMove) -> None:
        """Update selection during drag."""
        self.mouse_handler.handle_mouse_move(event)

    def on_mouse_up(self, event: MouseUp) -> None:
        """Complete selection."""
        self.mouse_handler.handle_mouse_up(event)

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
