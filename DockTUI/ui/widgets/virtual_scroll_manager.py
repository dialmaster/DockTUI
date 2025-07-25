"""Virtual scrolling manager for log viewer."""

import json
import logging
import threading
import time
from typing import List, Optional, Tuple

from textual.geometry import Size

from ...models.log_line import LogLine

logger = logging.getLogger("DockTUI.virtual_scroll_manager")


class VirtualScrollManager:
    """
    Manages virtual scrolling, viewport calculations, and visible line tracking.

    This class handles:
    - Virtual size calculations with caching
    - Viewport management and line tracking
    - Scroll position calculations
    - Debounced virtual size invalidation
    """

    # Constants
    DEFAULT_WIDTH = 80
    MIN_VIRTUAL_HEIGHT = 1
    # Seconds to wait before recalculating virtual size
    # This prevents the UI from becoming unresponsive when very large amounts of logs are being added
    # At the expense of the scrollbar/UI only being updated every X seconds
    VIRTUAL_SIZE_THROTTLE_DELAY = 0.3

    def __init__(self):
        """Initialize the virtual scroll manager."""
        self._virtual_size_cache: Optional[Size] = None
        self._virtual_size_timer: Optional[threading.Timer] = None
        self._virtual_size_pending = False
        self._lock = threading.RLock()
        self._last_update_time: float = (
            0.0  # Track last update time for smart throttling
        )

    def cleanup(self):
        """Clean up resources (timers, etc)."""
        with self._lock:
            if self._virtual_size_timer is not None:
                self._virtual_size_timer.cancel()
                self._virtual_size_timer = None

    def get_virtual_size(
        self,
        visible_lines: List[LogLine],
        widget_size: Optional[Size],
        count_json_lines_fn,
        count_xml_lines_fn,
    ) -> Size:
        """Calculate the virtual size based on visible lines.

        Args:
            visible_lines: List of visible log lines
            widget_size: Current widget size
            count_json_lines_fn: Function to count JSON lines
            count_xml_lines_fn: Function to count XML lines

        Returns:
            Virtual size as (width, height)
        """
        if self._virtual_size_cache is None:
            with self._lock:
                total_height = 0
                max_width = self.DEFAULT_WIDTH

                for line in visible_lines:
                    if line.is_expanded:
                        # Only parse if the line is expanded (user interaction)
                        # For virtual size calculation, we need synchronous parsing
                        line.ensure_parsed()

                        if line.json_data:
                            # Calculate height of pretty-printed JSON
                            if hasattr(line, "json_objects") and line.json_objects:
                                # Multiple JSON objects
                                from .log_renderer import LogRenderer

                                json_lines = LogRenderer.count_all_json_lines(
                                    line.json_objects
                                )
                                total_height += (
                                    json_lines - 1
                                )  # -1 because total_height already includes the line
                                # Check width of all JSON objects
                                for json_obj, _, _ in line.json_objects:
                                    json_str = json.dumps(json_obj, indent=2)
                                    for json_line in json_str.split("\n"):
                                        max_width = max(max_width, len(json_line))
                            else:
                                # Single JSON object (backward compatibility)
                                json_lines = count_json_lines_fn(line.json_data)
                                total_height += json_lines
                                # Check width of JSON lines
                                json_str = json.dumps(line.json_data, indent=2)
                                for json_line in json_str.split("\n"):
                                    max_width = max(max_width, len(json_line))
                        elif line.xml_data:
                            # Calculate height of pretty-printed XML
                            xml_lines = count_xml_lines_fn(line.xml_data)
                            total_height += xml_lines
                            # Check width of XML lines
                            from ...services.log.xml_formatter import XMLFormatter

                            formatted_lines = XMLFormatter.format_xml_pretty(
                                line.xml_data
                            )
                            for xml_line_segments in formatted_lines:
                                line_text = "".join(
                                    seg.text for seg in xml_line_segments
                                )
                                max_width = max(max_width, len(line_text))
                        else:
                            # Shouldn't happen if expanded, but handle gracefully
                            total_height += 1
                            max_width = max(max_width, len(line.raw_text))
                    else:
                        total_height += 1
                        # Check width of this line (no parsing needed for raw_text)
                        max_width = max(max_width, len(line.raw_text))

                # Ensure we have at least the widget height/width
                total_height = max(
                    total_height, widget_size.height if widget_size else 1
                )
                # Add some padding to the width for comfortable viewing
                max_width = max(max_width + 5, widget_size.width if widget_size else 80)
                self._virtual_size_cache = Size(max_width, total_height)

        return self._virtual_size_cache

    def set_virtual_size(self, size: Size):
        """Set the virtual size directly."""
        self._virtual_size_cache = size

    def invalidate_virtual_size(self, callback_fn):
        """Schedule a smart throttled virtual size recalculation.

        Uses smart throttling:
        - If enough time has passed since last update, update immediately
        - Otherwise, schedule a throttled update

        Args:
            callback_fn: Function to call when recalculation is complete
        """
        with self._lock:
            current_time = time.time()
            time_since_last_update = current_time - self._last_update_time

            # Check if we should update immediately (first update after quiet period)
            if time_since_last_update >= self.VIRTUAL_SIZE_THROTTLE_DELAY:
                # Immediate update - enough time has passed
                logger.debug(
                    f"Smart throttle: Immediate update (last update {time_since_last_update:.3f}s ago)"
                )

                # Cancel any pending timer
                if self._virtual_size_timer is not None:
                    self._virtual_size_timer.cancel()
                    self._virtual_size_timer = None

                # Perform update immediately
                self._virtual_size_cache = None
                self._virtual_size_pending = False
                self._last_update_time = current_time

                # Call callback immediately - but still use timer with 0 delay to ensure proper threading
                if callback_fn:
                    self._virtual_size_timer = threading.Timer(
                        0, callback_fn  # Immediate execution
                    )
                    self._virtual_size_timer.daemon = True
                    self._virtual_size_timer.start()
            else:
                # Throttled update - too soon since last update
                self._virtual_size_pending = True

                if self._virtual_size_timer is None:
                    # Calculate remaining time to wait
                    remaining_delay = (
                        self.VIRTUAL_SIZE_THROTTLE_DELAY - time_since_last_update
                    )
                    logger.debug(
                        f"Smart throttle: Scheduling update in {remaining_delay:.3f}s"
                    )

                    # Schedule new recalculation
                    self._virtual_size_timer = threading.Timer(
                        remaining_delay,
                        self._perform_virtual_size_recalculation,
                        args=(callback_fn,),
                    )
                    self._virtual_size_timer.daemon = True
                    self._virtual_size_timer.start()

    def invalidate_virtual_size_immediate(self):
        """Immediately invalidate virtual size cache with no throttling."""
        with self._lock:
            # Cancel any pending timer
            if self._virtual_size_timer is not None:
                self._virtual_size_timer.cancel()
                self._virtual_size_timer = None

            self._virtual_size_pending = False
            self._virtual_size_cache = None

    def _perform_virtual_size_recalculation(self, callback_fn):
        """Actually perform the virtual size recalculation after debounce delay.

        Args:
            callback_fn: Function to call when complete
        """
        with self._lock:
            if not self._virtual_size_pending:
                return

            self._virtual_size_cache = None
            self._virtual_size_pending = False
            self._virtual_size_timer = None
            self._last_update_time = time.time()  # Record update time

        # Call the callback to trigger refresh
        if callback_fn:
            callback_fn()

    def get_line_at_virtual_y(
        self,
        virtual_y: int,
        visible_lines: List[LogLine],
        count_json_lines_fn,
        count_xml_lines_fn,
    ) -> Optional[Tuple[LogLine, int]]:
        """
        Get the log line and offset within that line for a given virtual Y position.

        Args:
            virtual_y: Virtual Y position
            visible_lines: List of visible log lines
            count_json_lines_fn: Function to count JSON lines
            count_xml_lines_fn: Function to count XML lines

        Returns:
            (log_line, offset_within_line) or None.
        """
        with self._lock:
            current_y = 0

            for line in visible_lines:
                if line.is_expanded:
                    # Ensure parsed to check for JSON/XML
                    line.ensure_parsed()
                    if line.json_data:
                        if hasattr(line, "json_objects") and line.json_objects:
                            from .log_renderer import LogRenderer

                            line_height = LogRenderer.count_all_json_lines(
                                line.json_objects
                            )
                        else:
                            line_height = count_json_lines_fn(line.json_data)
                    elif line.xml_data:
                        line_height = count_xml_lines_fn(line.xml_data)
                    else:
                        line_height = 1
                else:
                    line_height = 1

                if current_y <= virtual_y < current_y + line_height:
                    return (line, virtual_y - current_y)

                current_y += line_height

            return None

    def calculate_viewport_range(
        self,
        scroll_offset_y: float,
        viewport_height: int,
        pre_parse_ahead: int = 10,
        pre_parse_before: int = 10,
    ) -> Tuple[int, int]:
        """Calculate the range of lines that should be visible/pre-parsed.

        Args:
            scroll_offset_y: Current scroll Y offset
            viewport_height: Height of the viewport
            pre_parse_ahead: Number of lines to pre-parse ahead
            pre_parse_before: Number of lines to pre-parse before

        Returns:
            (viewport_start, viewport_end) virtual Y positions
        """
        viewport_start = int(scroll_offset_y)
        viewport_end = viewport_start + viewport_height + pre_parse_ahead

        # Adjust start for pre-parsing before
        viewport_start = max(0, viewport_start - pre_parse_before)

        return viewport_start, viewport_end

    def find_lines_in_viewport(
        self,
        visible_lines: List[LogLine],
        viewport_start: int,
        viewport_end: int,
        count_json_lines_fn,
        count_xml_lines_fn,
    ) -> List[Tuple[LogLine, int]]:
        """Find all lines that are within the viewport range.

        Args:
            visible_lines: List of visible log lines
            viewport_start: Start of viewport (virtual Y)
            viewport_end: End of viewport (virtual Y)
            count_json_lines_fn: Function to count JSON lines
            count_xml_lines_fn: Function to count XML lines

        Returns:
            List of (log_line, virtual_y_position) tuples
        """
        lines_in_viewport = []
        current_y = 0

        for line in visible_lines:
            if current_y > viewport_end:
                break

            # Calculate line height
            if line.is_expanded and line.is_parsed:
                if line.json_data:
                    if hasattr(line, "json_objects") and line.json_objects:
                        from .log_renderer import LogRenderer

                        line_height = LogRenderer.count_all_json_lines(
                            line.json_objects
                        )
                    else:
                        line_height = count_json_lines_fn(line.json_data)
                elif line.xml_data:
                    line_height = count_xml_lines_fn(line.xml_data)
                else:
                    line_height = 1
            else:
                line_height = 1

            # Check if line is in viewport
            if current_y + line_height > viewport_start:
                lines_in_viewport.append((line, current_y))

            current_y += line_height

        return lines_in_viewport

    def calculate_total_virtual_lines(
        self, visible_lines: List[LogLine], count_json_lines_fn, count_xml_lines_fn
    ) -> int:
        """Calculate total number of virtual lines.

        Args:
            visible_lines: List of visible log lines
            count_json_lines_fn: Function to count JSON lines
            count_xml_lines_fn: Function to count XML lines

        Returns:
            Total number of virtual lines
        """
        total_virtual_lines = 0

        for line in visible_lines:
            if line.is_expanded:
                line.ensure_parsed()
                if line.json_data:
                    if hasattr(line, "json_objects") and line.json_objects:
                        from .log_renderer import LogRenderer

                        total_virtual_lines += LogRenderer.count_all_json_lines(
                            line.json_objects
                        )
                    else:
                        total_virtual_lines += count_json_lines_fn(line.json_data)
                elif line.xml_data:
                    total_virtual_lines += count_xml_lines_fn(line.xml_data)
                else:
                    total_virtual_lines += 1
            else:
                total_virtual_lines += 1

        return total_virtual_lines
