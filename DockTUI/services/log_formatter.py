"""Log formatting service for applying styles and formatting to log lines."""

import logging
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.segment import Segment
from rich.style import Style

from .log.json_formatter import JSONFormatter
from .log.xml_formatter import XMLFormatter

logger = logging.getLogger("DockTUI.log_formatter")

try:
    from .log.highlighter import SmartLogFormatter

    HAS_SMART_HIGHLIGHTER = True
except ImportError:
    HAS_SMART_HIGHLIGHTER = False


class LogFormatter:
    """Handles formatting of log lines with syntax highlighting."""

    STYLES = {
        "timestamp": Style(color="cyan"),
        "container_prefix": Style(color="bright_magenta", bold=True),
        "level_error": Style(color="red", bold=True),
        "level_fatal": Style(color="red", bold=True),
        "level_critical": Style(color="red", bold=True),
        "level_warn": Style(color="yellow"),
        "level_warning": Style(color="yellow"),
        "level_info": Style(color="green"),
        "level_debug": Style(color="blue"),
        "level_trace": Style(color="magenta"),
        "json": Style(color="blue"),
        "json_key": Style(color="cyan"),
        "json_string": Style(color="green"),
        "json_number": Style(color="yellow"),
        "marked": Style(color="white", bgcolor="purple", bold=True),
        "selection": Style(bgcolor="grey35"),
        "text": Style(),
    }

    def __init__(self):
        """Initialize the formatter."""
        self._console = Console(
            force_terminal=True, force_jupyter=False, width=1000, legacy_windows=False
        )
        self.json_formatter = JSONFormatter()
        self.xml_formatter = XMLFormatter()

        self.smart_formatter: Optional[SmartLogFormatter] = None
        if HAS_SMART_HIGHLIGHTER:
            try:
                self.smart_formatter = SmartLogFormatter()
            except (ImportError, AttributeError, ValueError) as e:
                logger.debug(f"Smart formatter initialization failed: {e}")
                self.smart_formatter = None

    def format_json_pretty(
        self, json_data: Dict, indent_level: int = 0
    ) -> List[List[Segment]]:
        """Format JSON data as pretty-printed segments, returning list of lines."""
        if self.smart_formatter:
            return self.smart_formatter.format_json_pretty(json_data)

        return self.json_formatter.format_json_pretty(json_data)

    def format_xml_pretty(self, xml_data: str) -> List[List[Segment]]:
        """Format XML data as pretty-printed segments, returning list of lines."""
        return self.xml_formatter.format_xml_pretty(xml_data)

    def apply_zebra_stripe(
        self, segments: List[Segment], line_number: int
    ) -> List[Segment]:
        """Apply zebra striping background to segments."""
        if line_number % 2 == 0:
            bg_style = Style(bgcolor="grey15")
            return [
                Segment(seg.text, seg.style + bg_style if seg.style else bg_style)
                for seg in segments
            ]
        return segments

    def apply_selection(
        self,
        segments: List[Segment],
        line_text: str,
        selection_start: int,
        selection_end: int,
    ) -> List[Segment]:
        """Apply selection highlighting to segments."""
        result = []
        current_pos = 0

        for segment in segments:
            seg_start = current_pos
            seg_end = current_pos + len(segment.text)

            result.extend(
                self._process_segment_selection(
                    segment, seg_start, seg_end, selection_start, selection_end
                )
            )

            current_pos = seg_end

        return result

    def _process_segment_selection(
        self,
        segment: Segment,
        seg_start: int,
        seg_end: int,
        sel_start: int,
        sel_end: int,
    ) -> List[Segment]:
        """Process a single segment for selection highlighting."""
        if seg_end <= sel_start or seg_start >= sel_end:
            return [segment]

        if seg_start >= sel_start and seg_end <= sel_end:
            return [self._apply_selection_style(segment)]

        if seg_start < sel_start < seg_end:
            return self._handle_selection_start_in_segment(
                segment, seg_start, seg_end, sel_start, sel_end
            )

        if seg_start < sel_end < seg_end:
            return self._handle_selection_end_in_segment(segment, seg_start, sel_end)

        return [segment]

    def _apply_selection_style(self, segment: Segment) -> Segment:
        """Apply selection style to a segment."""
        selection_style = self.STYLES["selection"]
        combined_style = (
            segment.style + selection_style if segment.style else selection_style
        )
        return Segment(segment.text, combined_style)

    def _handle_selection_start_in_segment(
        self,
        segment: Segment,
        seg_start: int,
        seg_end: int,
        sel_start: int,
        sel_end: int,
    ) -> List[Segment]:
        """Handle case where selection starts within segment."""
        result = []

        pre_sel = segment.text[: sel_start - seg_start]
        if pre_sel:
            result.append(Segment(pre_sel, segment.style))

        if sel_end < seg_end:
            in_sel = segment.text[sel_start - seg_start : sel_end - seg_start]
            post_sel = segment.text[sel_end - seg_start :]

            result.append(self._apply_selection_style(Segment(in_sel, segment.style)))
            if post_sel:
                result.append(Segment(post_sel, segment.style))
        else:
            in_sel = segment.text[sel_start - seg_start :]
            result.append(self._apply_selection_style(Segment(in_sel, segment.style)))

        return result

    def _handle_selection_end_in_segment(
        self, segment: Segment, seg_start: int, sel_end: int
    ) -> List[Segment]:
        """Handle case where selection ends within segment."""
        result = []

        in_sel = segment.text[: sel_end - seg_start]
        post_sel = segment.text[sel_end - seg_start :]

        result.append(self._apply_selection_style(Segment(in_sel, segment.style)))
        if post_sel:
            result.append(Segment(post_sel, segment.style))

        return result

    def create_segments_from_components(
        self,
        components: List[Tuple[str, str, int]],
        base_style: Optional[Style] = None,
        raw_text: Optional[str] = None,
        log_line=None,
    ) -> List[Segment]:
        """Create segments from parsed components with appropriate styling."""
        base_style = base_style or Style()

        if not self._should_use_smart_highlighting(components, raw_text):
            return self._create_basic_segments(components, base_style)

        return self._create_smart_segments(components, base_style, raw_text, log_line)

    def _should_use_smart_highlighting(
        self, components: List[Tuple[str, str, int]], raw_text: Optional[str]
    ) -> bool:
        """Determine if smart highlighting should be used."""
        if not self.smart_formatter or not raw_text:
            return False

        # Don't use smart highlighting for marked lines
        if any(comp_type == "marked" for comp_type, _, _ in components):
            return False

        return True

    def _create_basic_segments(
        self, components: List[Tuple[str, str, int]], base_style: Style
    ) -> List[Segment]:
        """Create segments using basic styling."""
        segments = []
        has_json = False
        has_xml = False

        # First pass: check if we have JSON or XML
        for comp_type, _, _ in components:
            if comp_type == "json":
                has_json = True
            elif comp_type == "xml":
                has_xml = True

        # Add emoji at the beginning if we have JSON or XML
        if has_json:
            segments.append(Segment("📋 ", Style(color="blue")))
        elif has_xml:
            segments.append(Segment("📄 ", Style(color="bright_blue")))

        # Now add all the components
        for comp_type, text, _ in components:
            style = self.STYLES.get(comp_type, self.STYLES["text"])
            combined_style = base_style + style

            if comp_type == "json_expanded":
                segments.append(Segment(" 📂", Style(color="blue", italic=True)))
            elif comp_type == "xml_expanded":
                segments.append(Segment(" 📂", Style(color="bright_blue", italic=True)))
            else:
                segments.append(Segment(text, combined_style))

        return segments

    def _create_smart_segments(
        self,
        components: List[Tuple[str, str, int]],
        base_style: Style,
        raw_text: str,
        log_line,
    ) -> List[Segment]:
        """Create segments using smart highlighting."""
        preserved_components = [
            (comp_type, text, pos)
            for comp_type, text, pos in components
            if comp_type not in ["text", "json"]
        ]

        highlighted_segments = self.smart_formatter.highlight_line(
            raw_text, preserved_components, log_line
        )

        # Check if we need to add JSON emoji
        if log_line and log_line.has_json and not log_line.is_expanded:
            return self._insert_json_emoji(
                highlighted_segments, log_line.json_start_pos
            )

        # Check if we need to add XML emoji
        if log_line and log_line.has_xml and not log_line.is_expanded:
            return self._insert_xml_emoji(highlighted_segments, log_line.xml_start_pos)

        return highlighted_segments

    def _insert_json_emoji(
        self, segments: List[Segment], json_pos: Optional[int]
    ) -> List[Segment]:
        """Insert JSON emoji at the beginning of the line."""
        if not segments:
            return segments

        # Always insert at the beginning
        return [Segment("📋 ", Style(color="blue"))] + segments

    def _insert_xml_emoji(
        self, segments: List[Segment], xml_pos: Optional[int]
    ) -> List[Segment]:
        """Insert XML emoji at the beginning of the line."""
        if not segments:
            return segments

        # Always insert at the beginning
        return [Segment("📄 ", Style(color="bright_blue"))] + segments
