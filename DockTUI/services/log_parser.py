"""Log parsing service for extracting structured information from log lines."""

import json
import re
from datetime import datetime
from typing import List, Pattern, Tuple

try:
    import defusedxml.ElementTree as ET
except ImportError:
    # Fall back to standard library with security warning
    import logging
    import xml.etree.ElementTree as ET

    logging.getLogger("DockTUI.log_parser").warning(
        "defusedxml not available. XML parsing may be vulnerable to XXE attacks. "
        "Run 'poetry install' to install security dependencies."
    )

from ..models.log_line import LogLine
from .log.highlighter.patterns import LogPatterns


class LogParser:
    """Parses log lines to extract structured information."""

    # Singleton instance of LogPatterns for shared compiled patterns
    _patterns = None

    # Pre-compiled patterns specific to LogParser
    _timestamp_patterns: List[Tuple[Pattern, str]] = None
    _json_pattern: Pattern = None
    _xml_pattern: Pattern = None
    _container_prefix_pattern: Pattern = None

    def __init__(self):
        """Initialize the parser with pre-compiled patterns."""
        # Get singleton LogPatterns instance
        if LogParser._patterns is None:
            LogParser._patterns = LogPatterns()

        # Initialize parser-specific compiled patterns if not already done
        if LogParser._timestamp_patterns is None:
            LogParser._init_compiled_patterns()

    @classmethod
    def _init_compiled_patterns(cls):
        """Initialize all compiled patterns once at class level."""
        # Timestamp patterns with their format strings
        cls._timestamp_patterns = [
            # ISO 8601
            (
                re.compile(
                    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)"
                ),
                "%Y-%m-%dT%H:%M:%S",
            ),
            # Common log format
            (re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"), "%Y-%m-%d %H:%M:%S"),
            # Syslog format
            (re.compile(r"(\w{3} +\d{1,2} \d{2}:\d{2}:\d{2})"), "%b %d %H:%M:%S"),
        ]

        # JSON pattern
        cls._json_pattern = re.compile(r"(\{[^{}]*\}|\{[^{}]*\{[^{}]*\}[^{}]*\})")

        # XML pattern - improved to match nested structures
        cls._xml_pattern = re.compile(
            r"(<([^>/\s]+)(?:\s[^>]*)?>(?:(?!<\2[>\s])(?:<[^>]+>.*?</[^>]+>|[^<]))*?</\2>|<[^>]+/>)"
        )

        # Container prefix pattern
        cls._container_prefix_pattern = re.compile(r"^\[([^\]]+)\]")

    def parse_line(self, text: str, line_number: int) -> LogLine:
        """Parse a log line and extract metadata."""
        log_line = LogLine(raw_text=text, line_number=line_number)
        self.parse_into_line(log_line)
        return log_line

    def parse_into_line(self, log_line: LogLine) -> None:
        """Parse metadata into an existing LogLine object (for lazy parsing).

        Args:
            log_line: The LogLine object to parse into
        """
        text = log_line.raw_text

        # Check for container prefix first using pre-compiled pattern
        container_match = self._container_prefix_pattern.match(text)
        if container_match:
            log_line.container_name = container_match.group(1)
            log_line.container_prefix_end = container_match.end()

        # Extract timestamp using pre-compiled patterns
        for pattern, date_format in self._timestamp_patterns:
            match = pattern.search(text)
            if match:
                try:
                    # Handle different timestamp formats
                    timestamp_str = match.group(1)
                    # Store match position for rendering
                    log_line.timestamp_pos = (match.start(1), match.end(1))
                    log_line.add_pattern_match(
                        "timestamp", match.start(1), match.end(1)
                    )

                    # Remove timezone info if present for simpler parsing
                    timestamp_str = re.sub(r"[+-]\d{2}:\d{2}$", "", timestamp_str)
                    timestamp_str = timestamp_str.rstrip("Z")
                    # Handle milliseconds
                    if "." in timestamp_str:
                        # Try with milliseconds first
                        try:
                            log_line.timestamp = datetime.strptime(
                                timestamp_str, date_format + ".%f"
                            )
                        except ValueError:
                            # Fall back to without milliseconds
                            timestamp_str = timestamp_str.split(".")[0]
                            log_line.timestamp = datetime.strptime(
                                timestamp_str, date_format
                            )
                    else:
                        log_line.timestamp = datetime.strptime(
                            timestamp_str, date_format
                        )
                    break
                except ValueError:
                    continue

        # Extract log level using pre-compiled pattern from LogPatterns
        # Check each log level pattern
        for level_type in [
            "level_error",
            "level_warn",
            "level_info",
            "level_debug",
            "level_trace",
        ]:
            pattern = self._patterns.get_pattern(level_type)
            if pattern:
                if hasattr(pattern, "searchString"):  # pyparsing
                    try:
                        for tokens, start, end in pattern.scanString(text):
                            if tokens:
                                log_line.log_level = str(tokens[0]).upper()
                                # Store match position
                                log_line.log_level_pos = (start, end)
                                log_line.add_pattern_match(
                                    f"log_{level_type}", start, end
                                )
                                break
                    except:
                        pass
                else:  # regex
                    match = pattern.search(text)
                    if match:
                        log_line.log_level = match.group(0).upper()
                        # Store match position
                        log_line.log_level_pos = (match.start(), match.end())
                        log_line.add_pattern_match(
                            f"log_{level_type}", match.start(), match.end()
                        )
                        break

        # Detect JSON using pre-compiled pattern
        json_matches = list(self._json_pattern.finditer(text))
        for json_match in json_matches:
            try:
                # Try to parse the JSON to validate it
                json_str = json_match.group(1)
                log_line.json_data = json.loads(json_str)
                log_line.has_json = True
                log_line.json_start_pos = json_match.start(1)
                log_line.json_end_pos = json_match.end(1)
                break  # Use the first valid JSON found
            except json.JSONDecodeError:
                # Not valid JSON, continue looking
                continue

        # Detect XML (only if we didn't find JSON)
        if not log_line.has_json:
            xml_fragments = self._find_xml_fragments(text)
            if xml_fragments:
                # Use the first (and potentially largest) valid XML fragment
                xml_str, start_pos, end_pos = xml_fragments[0]
                log_line.xml_data = xml_str
                log_line.has_xml = True
                log_line.xml_start_pos = start_pos
                log_line.xml_end_pos = end_pos

        # Check if this is a marked line
        if "------ MARKED" in text and "------" in text:
            log_line.is_marked = True

        # Mark as parsed when using parse_into_line
        log_line._is_parsed = True

    def get_line_components(self, log_line: LogLine) -> List[Tuple[str, str, int]]:
        """
        Break down a log line into components for formatting.
        Returns list of (component_type, text, start_position).
        """
        components = []
        text = log_line.raw_text

        # Track what we've already added to avoid duplicates
        added_ranges = []

        def add_component(comp_type: str, start: int, end: int):
            """Add a component if it doesn't overlap with already added ones."""
            for added_start, added_end in added_ranges:
                if start < added_end and end > added_start:
                    # Overlapping, skip
                    return
            components.append((comp_type, text[start:end], start))
            added_ranges.append((start, end))

        # Special handling for marked lines
        if log_line.is_marked:
            add_component("marked", 0, len(text))
            return components

        # Extract components in order of priority
        # 1. Container prefix (if present)
        if log_line.container_name and log_line.container_prefix_end:
            add_component("container_prefix", 0, log_line.container_prefix_end)

        # Skip timestamp and log level components - let smart highlighter handle them

        # 4. JSON (if expanded)
        if log_line.has_json and log_line.is_expanded:
            # For expanded JSON, mark everything before JSON as regular text
            if log_line.json_start_pos and log_line.json_start_pos > 0:
                add_component("text", 0, log_line.json_start_pos)
            # Add an expanded JSON marker
            if log_line.json_start_pos:
                add_component(
                    "json_expanded",
                    log_line.json_start_pos,
                    log_line.json_start_pos + 1,
                )

        # 5. XML (if expanded)
        elif log_line.has_xml and log_line.is_expanded:
            # For expanded XML, mark everything before XML as regular text
            if log_line.xml_start_pos and log_line.xml_start_pos > 0:
                add_component("text", 0, log_line.xml_start_pos)
            # Add an expanded XML marker
            if log_line.xml_start_pos:
                add_component(
                    "xml_expanded",
                    log_line.xml_start_pos,
                    log_line.xml_start_pos + 1,
                )

        # 4. Fill in the gaps with plain text
        # Sort components by start position
        components.sort(key=lambda x: x[2])

        # Add text components for gaps
        final_components = []
        last_end = 0

        for comp_type, comp_text, start_pos in components:
            # Add gap text if any
            if start_pos > last_end:
                final_components.append(("text", text[last_end:start_pos], last_end))
            final_components.append((comp_type, comp_text, start_pos))
            last_end = start_pos + len(comp_text)

        # Add remaining text
        if last_end < len(text):
            final_components.append(("text", text[last_end:], last_end))

        # If no components were found, return the entire line as text
        if not final_components:
            final_components.append(("text", text, 0))

        return final_components

    def _is_valid_xml(self, xml_str: str) -> bool:
        """Validate XML using proper parser."""
        if not xml_str.strip():
            return False

        try:
            # Try to parse as complete XML
            ET.fromstring(xml_str)
            return True
        except ET.ParseError:
            # If it fails, try wrapping in a root element
            try:
                ET.fromstring(f"<root>{xml_str}</root>")
                return True
            except ET.ParseError:
                return False

    def _find_xml_fragments(self, text: str) -> List[Tuple[str, int, int]]:
        """Find all potential XML fragments in text."""
        fragments = []

        # More comprehensive patterns to find XML
        patterns = [
            # Complete element with matching opening/closing tags (handles nested)
            re.compile(r"<([a-zA-Z][\w\-\.:]*)(?:\s+[^>]*)?>(?:(?!<\1[\s>]).)*?<\/\1>"),
            # Self-closing tags
            re.compile(r"<[a-zA-Z][\w\-\.:]*(?:\s+[^>]*)?/>"),
        ]

        # First, try to find the largest possible XML structures
        # This pattern attempts to match balanced tags
        def find_balanced_xml(text, start=0):
            """Find balanced XML tags using a stack-based approach."""
            stack = []
            i = start
            xml_start = None

            while i < len(text):
                # Look for tag start
                if text[i] == "<":
                    tag_end = text.find(">", i)
                    if tag_end == -1:
                        i += 1
                        continue

                    tag = text[i : tag_end + 1]

                    # Skip comments and declarations
                    if tag.startswith("<!--") or tag.startswith("<?"):
                        i = tag_end + 1
                        continue

                    # Self-closing tag
                    if tag.endswith("/>"):
                        if not stack and xml_start is None:
                            # This is a standalone self-closing tag
                            yield (tag, i, tag_end + 1)
                        i = tag_end + 1
                        continue

                    # Closing tag
                    if tag.startswith("</"):
                        tag_name = re.match(r"</([a-zA-Z][\w\-\.:]*)", tag)
                        if tag_name and stack and stack[-1] == tag_name.group(1):
                            stack.pop()
                            if not stack and xml_start is not None:
                                # Found complete XML
                                yield (
                                    text[xml_start : tag_end + 1],
                                    xml_start,
                                    tag_end + 1,
                                )
                                xml_start = None
                    else:
                        # Opening tag
                        tag_name = re.match(r"<([a-zA-Z][\w\-\.:]*)", tag)
                        if tag_name:
                            if xml_start is None:
                                xml_start = i
                            stack.append(tag_name.group(1))

                    i = tag_end + 1
                else:
                    i += 1

        # Try the balanced approach first
        for xml_str, start, end in find_balanced_xml(text):
            if self._is_valid_xml(xml_str):
                fragments.append((xml_str, start, end))

        for pattern in patterns:
            for match in pattern.finditer(text):
                xml_str = match.group(0)
                if self._is_valid_xml(xml_str):
                    fragments.append((xml_str, match.start(), match.end()))

        # If we have overlapping fragments, keep the longest ones
        if fragments:
            # Sort by length (descending) to prefer longer matches
            fragments.sort(key=lambda x: x[2] - x[1], reverse=True)

            # Remove overlapping fragments
            non_overlapping = []
            for frag in fragments:
                overlaps = False
                for existing in non_overlapping:
                    # Check if this fragment overlaps with an existing one
                    if frag[1] < existing[2] and frag[2] > existing[1]:
                        overlaps = True
                        break
                if not overlaps:
                    non_overlapping.append(frag)

            # Sort by position for processing
            non_overlapping.sort(key=lambda x: x[1])
            return non_overlapping

        return []
