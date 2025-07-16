"""Log renderer for rich log viewer."""

import json
import logging
from typing import List, Optional, Tuple

from rich.segment import Segment
from rich.style import Style
from textual.geometry import Size
from textual.strip import Strip

from ...models.log_line import LogLine
from ...services.log_formatter import LogFormatter
from ...services.log_parser import LogParser
from .log_selection_manager import SelectionManager

logger = logging.getLogger("DockTUI.log_renderer")


class LogRenderer:
    """
    Handles rendering of log lines with syntax highlighting and formatting.

    This class is responsible for:
    - Rendering individual log lines with proper formatting
    - Handling expanded JSON/XML rendering
    - Applying selection highlighting
    - Managing zebra striping
    - Horizontal scrolling support
    """

    def __init__(
        self,
        parser: LogParser,
        formatter: LogFormatter,
        selection_manager: SelectionManager,
    ):
        """Initialize the log renderer.

        Args:
            parser: Log parser instance
            formatter: Log formatter instance
            selection_manager: Selection manager instance
        """
        self.parser = parser
        self.formatter = formatter
        self.selection_manager = selection_manager

    def render_line(
        self,
        virtual_y: int,
        log_line: LogLine,
        line_offset: int,
        cached_segments: Optional[List[Segment]],
        widget_size: Optional[Size],
        scroll_offset_x: float,
        zebra_stripe: bool,
        virtual_width: int,
    ) -> Tuple[Strip, List[Segment]]:
        """Render a single line of the log viewer.

        Args:
            virtual_y: Virtual Y position of the line
            log_line: The log line to render
            line_offset: Offset within the log line (for expanded content)
            cached_segments: Cached segments if available
            widget_size: Current widget size
            scroll_offset_x: Horizontal scroll offset
            zebra_stripe: Whether to apply zebra striping
            virtual_width: Virtual width for the strip

        Returns:
            Tuple of (rendered strip, segments for caching)
        """
        # Ensure the line is parsed before checking its properties
        log_line.ensure_parsed()

        # Use cached segments if available and valid
        if cached_segments and log_line.is_cache_valid():
            segments = cached_segments
        else:
            # Generate segments based on line type
            segments = self._generate_segments(log_line, line_offset, zebra_stripe)

        if hasattr(log_line, "search_matches") and log_line.search_matches:
            adjusted_matches = log_line.search_matches
            if line_offset == 0 and not log_line.is_expanded:
                has_emoji = False
                if log_line.has_json and log_line.json_start_pos is not None:
                    has_emoji = True
                elif log_line.has_xml and log_line.xml_start_pos is not None:
                    has_emoji = True

                if has_emoji:
                    adjusted_matches = [
                        (start + 2, end + 2) for start, end in log_line.search_matches
                    ]

            segments = self._apply_search_highlighting(segments, adjusted_matches)

        if self.selection_manager.has_selection():
            segments = self._apply_selection_to_segments(
                segments, virtual_y, log_line, line_offset
            )

        # Create strip from segments
        strip = Strip(segments)

        # Always extend to at least widget width to ensure full clearing
        width = widget_size.width if widget_size else 80
        min_width = max(virtual_width, width)

        if strip.cell_length < min_width:
            bg_style = self._get_background_style(log_line, zebra_stripe)
            strip = strip.extend_cell_length(min_width, bg_style)

        # Crop for horizontal scrolling
        scroll_x = int(scroll_offset_x)
        cropped_strip = strip.crop(scroll_x, scroll_x + width)

        return cropped_strip, segments

    def _generate_segments(
        self, log_line: LogLine, line_offset: int, zebra_stripe: bool
    ) -> List[Segment]:
        """Generate segments for a log line.

        Args:
            log_line: The log line to render
            line_offset: Offset within the line
            zebra_stripe: Whether to apply zebra striping

        Returns:
            List of segments
        """
        if log_line.is_expanded and log_line.json_data and line_offset > 0:
            # This is a JSON line within an expanded log entry
            return self._render_json_line(log_line, line_offset - 1, zebra_stripe)
        elif log_line.is_expanded and log_line.xml_data and line_offset > 0:
            # This is an XML line within an expanded log entry
            return self._render_xml_line(log_line, line_offset - 1, zebra_stripe)
        else:
            # This is the main log line (whether expanded or not)
            return self._render_log_line(log_line, zebra_stripe)

    def _render_log_line(self, log_line: LogLine, zebra_stripe: bool) -> List[Segment]:
        """Render a normal log line with syntax highlighting.

        Args:
            log_line: The log line to render
            zebra_stripe: Whether to apply zebra striping

        Returns:
            List of segments
        """
        # Get components - parser handles expanded vs collapsed state
        components = self.parser.get_line_components(log_line)
        segments = self.formatter.create_segments_from_components(
            components, Style(), log_line.raw_text, log_line
        )

        # Apply zebra striping if enabled (but not for system messages or marked lines)
        if zebra_stripe and not log_line.is_system_message and not log_line.is_marked:
            segments = self.formatter.apply_zebra_stripe(segments, log_line.line_number)

        return segments

    def _render_json_line(
        self, log_line: LogLine, line_offset: int, zebra_stripe: bool
    ) -> List[Segment]:
        """Render a line from pretty-printed JSON.

        Args:
            log_line: The log line containing JSON
            line_offset: Offset within the JSON lines
            zebra_stripe: Whether to apply zebra striping

        Returns:
            List of segments
        """
        # Check if we have multiple JSON objects
        if hasattr(log_line, "json_objects") and log_line.json_objects:
            return self._render_multiple_json_line(log_line, line_offset, zebra_stripe)

        # Single JSON object (backward compatibility)
        # Get pretty-printed JSON segments (already split into lines)
        json_lines = self.formatter.format_json_pretty(log_line.json_data)

        if 0 <= line_offset < len(json_lines):
            segments = json_lines[line_offset]
            if zebra_stripe:
                # Use the parent log line's number for consistent background
                segments = self.formatter.apply_zebra_stripe(
                    segments, log_line.line_number
                )
            return segments

        return []

    def _render_multiple_json_line(
        self, log_line: LogLine, line_offset: int, zebra_stripe: bool
    ) -> List[Segment]:
        """Render a line from multiple pretty-printed JSON objects.

        Args:
            log_line: The log line containing multiple JSON objects
            line_offset: Offset within all the JSON lines
            zebra_stripe: Whether to apply zebra striping

        Returns:
            List of segments
        """
        current_offset = 0

        for i, (json_data, _, _) in enumerate(log_line.json_objects):
            # Add separator line between JSON objects
            if i > 0:
                if line_offset == current_offset:
                    # Return a line filled with spaces as separator
                    # This ensures proper background rendering
                    bg_style = self._get_background_style(log_line, zebra_stripe)
                    segments = [
                        Segment(" " * 80, bg_style)
                    ]  # Use a reasonable default width
                    return segments
                current_offset += 1

            # Get pretty-printed JSON segments for this object
            json_lines = self.formatter.format_json_pretty(json_data)

            # Check if the requested line is within this JSON object
            if current_offset <= line_offset < current_offset + len(json_lines):
                segments = json_lines[line_offset - current_offset]
                if zebra_stripe:
                    segments = self.formatter.apply_zebra_stripe(
                        segments, log_line.line_number
                    )
                return segments

            current_offset += len(json_lines)

        return []

    def _render_xml_line(
        self, log_line: LogLine, line_offset: int, zebra_stripe: bool
    ) -> List[Segment]:
        """Render a line from pretty-printed XML.

        Args:
            log_line: The log line containing XML
            line_offset: Offset within the XML lines
            zebra_stripe: Whether to apply zebra striping

        Returns:
            List of segments
        """
        # Get pretty-printed XML segments (already split into lines)
        xml_lines = self.formatter.format_xml_pretty(log_line.xml_data)

        if 0 <= line_offset < len(xml_lines):
            segments = xml_lines[line_offset]
            if zebra_stripe:
                # Use the parent log line's number for consistent background
                segments = self.formatter.apply_zebra_stripe(
                    segments, log_line.line_number
                )
            return segments

        return []

    def _apply_selection_to_segments(
        self,
        segments: List[Segment],
        virtual_y: int,
        log_line: LogLine,
        line_offset: int,
    ) -> List[Segment]:
        """Apply selection highlighting to segments if this line is selected.

        Args:
            segments: The segments to apply selection to
            virtual_y: Virtual Y position
            log_line: The log line being rendered
            line_offset: Offset within the line

        Returns:
            Segments with selection applied
        """
        if not self.selection_manager.is_line_in_selection(virtual_y):
            return segments

        # Get the text for this specific line (could be JSON/XML sub-line)
        if log_line.is_expanded and line_offset > 0:
            # This is a JSON/XML sub-line, get its text from the segments
            line_text = "".join(seg.text for seg in segments)
        else:
            # This is the main log line
            line_text = log_line.raw_text

        # Get selection range for this line
        sel_start, sel_end = self.selection_manager.get_line_selection_range(
            virtual_y, line_text
        )

        # Apply selection formatting
        return self.formatter.apply_selection(segments, line_text, sel_start, sel_end)

    def _apply_search_highlighting(
        self, segments: List[Segment], search_matches: List[Tuple[int, int]]
    ) -> List[Segment]:
        """Apply search match highlighting to segments.

        Args:
            segments: The segments to apply highlighting to
            search_matches: List of (start, end) positions for matches

        Returns:
            Segments with search highlighting applied
        """
        if not search_matches:
            return segments

        result = []
        current_pos = 0

        for segment in segments:
            seg_start = current_pos
            seg_end = current_pos + len(segment.text)

            segment_pieces = []
            piece_start = 0

            for match_start, match_end in search_matches:
                if match_end <= seg_start or match_start >= seg_end:
                    continue

                overlap_start = max(0, match_start - seg_start)
                overlap_end = min(len(segment.text), match_end - seg_start)

                if overlap_start > piece_start:
                    segment_pieces.append((piece_start, overlap_start, False))

                segment_pieces.append((overlap_start, overlap_end, True))
                piece_start = overlap_end

            if piece_start < len(segment.text):
                segment_pieces.append((piece_start, len(segment.text), False))

            for start, end, is_match in segment_pieces:
                text = segment.text[start:end]
                if is_match:
                    search_style = self.formatter.STYLES["search_match"]
                    combined_style = (
                        segment.style + search_style if segment.style else search_style
                    )
                    result.append(Segment(text, combined_style))
                else:
                    result.append(Segment(text, segment.style))

            current_pos = seg_end

        return result

    def _get_background_style(self, log_line: LogLine, zebra_stripe: bool) -> Style:
        """Get the background style for a log line.

        Args:
            log_line: The log line
            zebra_stripe: Whether zebra striping is enabled

        Returns:
            Style object with appropriate background
        """
        if (
            zebra_stripe
            and log_line
            and log_line.line_number % 2 == 0
            and not log_line.is_system_message
            and not log_line.is_marked
        ):
            return Style(bgcolor="grey15")
        return Style()

    @staticmethod
    def count_json_lines(json_data: dict) -> int:
        """Count how many lines pretty-printed JSON will take.

        Args:
            json_data: The JSON data

        Returns:
            Number of lines including the original log line
        """
        json_str = json.dumps(json_data, indent=2)
        # Add 1 for the original log line
        return len(json_str.split("\n")) + 1

    @staticmethod
    def count_all_json_lines(json_objects: List[Tuple[dict, int, int]]) -> int:
        """Count total lines for all JSON objects when expanded.

        Args:
            json_objects: List of (json_data, start_pos, end_pos) tuples

        Returns:
            Total number of lines including separators and original log line
        """
        if not json_objects:
            return 1  # Just the original line

        total = 1  # Start with 1 for the original log line
        for i, (json_data, _, _) in enumerate(json_objects):
            if i > 0:
                total += 1  # Add a blank line between JSON objects
            json_str = json.dumps(json_data, indent=2)
            total += len(json_str.split("\n"))
        return total

    @staticmethod
    def count_xml_lines(xml_data: str) -> int:
        """Count how many lines pretty-printed XML will take.

        Args:
            xml_data: The XML data

        Returns:
            Number of lines including the original log line
        """
        from ...services.log.xml_formatter import XMLFormatter

        formatted_lines = XMLFormatter.format_xml_pretty(xml_data)
        # Add 1 for the original log line
        return len(formatted_lines) + 1
