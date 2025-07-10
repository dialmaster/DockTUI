"""Smart log highlighting with automatic format detection."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.segment import Segment
from rich.style import Style

from ..json_formatter import JSONFormatter
from .patterns import LogPatterns
from .themes import PYGMENTS_TO_RICH, get_log_theme

logger = logging.getLogger("DockTUI.smart_highlighter")

# Optional imports
try:
    from pygments.lexers import guess_lexer

    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False

from .patterns import HAS_PYPARSING


class SmartLogFormatter:
    """Smart log formatter with pattern detection and syntax highlighting."""

    # Pre-compiled patterns for better performance
    _quoted_double_pattern = re.compile(r'"(?:[^"\\]|\\.)*"')
    _quoted_single_pattern = re.compile(r"'(?:[^'\\]|\\.)*'")
    _code_indicator_patterns = [
        re.compile(r"^\s*(?:def|class|function|const|let|var)\s+"),
        re.compile(r"^\s*(?:if|for|while|try|catch)\s*\("),
        re.compile(r"^\s*(?:import|from|require)\s+"),
        re.compile(r"^\s*(?:public|private|protected)\s+"),
        re.compile(r"[{};]\s*$"),
        re.compile(r"^\s*[}\]]\s*$"),
    ]

    def __init__(self):
        """Initialize the smart formatter."""
        self.theme = get_log_theme()
        self.patterns = LogPatterns()
        self.json_formatter = JSONFormatter()
        self._console = Console(theme=self.theme)

        # Cache for pattern performance
        self._pattern_cache: Dict[str, Any] = {}

    def format_json_pretty(self, json_data: Dict) -> List[List[Segment]]:
        """Format JSON using the shared formatter."""
        return self.json_formatter.format_json_pretty(json_data)

    def highlight_line(
        self,
        text: str,
        preserved_components: Optional[List[Tuple[str, str, int]]] = None,
        log_line=None,
    ) -> List[Segment]:
        """
        Apply smart highlighting to a log line.

        Args:
            text: The raw log line text
            preserved_components: Components that must keep their original styling

        Returns:
            List of styled segments
        """
        if not text:
            return [Segment(text, Style())]

        # Create a working copy of the text with placeholders for preserved components
        working_text = text
        placeholders = {}

        if preserved_components:
            # Sort by position to process in order
            sorted_components = sorted(preserved_components, key=lambda x: x[2])
            offset = 0

            for comp_type, comp_text, pos in sorted_components:
                placeholder = f"__PRESERVE_{len(placeholders)}__"
                placeholders[placeholder] = (comp_type, comp_text)

                # Replace in working text
                actual_pos = pos + offset
                working_text = (
                    working_text[:actual_pos]
                    + placeholder
                    + working_text[actual_pos + len(comp_text) :]
                )
                offset += len(placeholder) - len(comp_text)

        # Try to detect code patterns first
        if self._looks_like_code(working_text):
            segments = self._highlight_code(working_text)
        else:
            segments = self._highlight_log_patterns(working_text, log_line)

        # Restore preserved components
        if placeholders:
            segments = self._restore_preserved_components(segments, placeholders)

        return segments

    def _looks_like_code(self, text: str) -> bool:
        """Check if text looks like code rather than a log line."""
        for pattern in self._code_indicator_patterns:
            if pattern.search(text):
                return True

        return False

    def _get_style_name_for_pattern(self, pattern_type: str) -> Optional[str]:
        """Map pattern type to style name."""
        pattern_style_map = {
            "timestamp": "log.timestamp",
            "log_level_error": "log.level_error",
            "log_level_warn": "log.level_warn",
            "log_level_info": "log.level_info",
            "log_level_debug": "log.level_debug",
            "log_level_trace": "log.level_trace",
        }
        return pattern_style_map.get(pattern_type)

    def _highlight_code(self, text: str) -> List[Segment]:
        """Apply code syntax highlighting using Pygments if available."""
        if not HAS_PYGMENTS:
            return [Segment(text, Style())]

        try:
            # Try to guess the lexer
            lexer = guess_lexer(text)
            tokens = list(lexer.get_tokens(text))

            segments = []
            for token_type, token_text in tokens:
                # Map Pygments token to our style
                style_name = None
                for pygments_token, rich_style in PYGMENTS_TO_RICH.items():
                    if token_type.__name__.startswith(pygments_token):
                        style_name = rich_style
                        break

                if style_name and style_name in self.theme.styles:
                    style = self.theme.styles[style_name]
                else:
                    style = Style()

                segments.append(Segment(token_text, style))

            return segments

        except Exception as e:
            # Fallback to pattern-based highlighting
            logger.debug(
                f"Code highlighting failed, falling back to pattern-based: {e}"
            )
            return self._highlight_log_patterns(text)

    def _highlight_log_patterns(self, text: str, log_line=None) -> List[Segment]:
        """Apply pattern-based highlighting for log lines."""
        # Check if this is primarily JSON content
        if self._is_json_line(text):
            return self._highlight_json_content(text)

        # Check if this contains XML content
        if self._contains_xml(text):
            return self._highlight_xml_content(text)

        # Track which characters have been styled
        char_styles = [None] * len(text)

        # If we have pre-parsed pattern matches, apply them first
        if log_line and hasattr(log_line, "pattern_matches"):
            for pattern_type, start, end in log_line.pattern_matches:
                # Map pattern types to style names
                style_name = self._get_style_name_for_pattern(pattern_type)
                if style_name:
                    for i in range(start, min(end, len(char_styles))):
                        if char_styles[i] is None:
                            char_styles[i] = style_name

        # First, identify quoted strings to avoid highlighting inside them
        quoted_regions = self._find_quoted_regions(text)

        # Skip patterns we've already matched if we have pre-parsed data
        skip_patterns = set()
        if log_line and hasattr(log_line, "timestamp_pos") and log_line.timestamp_pos:
            skip_patterns.add("timestamp")
        if log_line and hasattr(log_line, "log_level_pos") and log_line.log_level_pos:
            skip_patterns.update(
                [
                    "level_error",
                    "level_warn",
                    "level_info",
                    "level_debug",
                    "level_trace",
                ]
            )

        # Apply patterns in priority order
        patterns_to_check = [
            # Strings first (highest priority to prevent other patterns inside)
            ("double_quoted", "log.quoted"),
            ("single_quoted", "log.single_quoted"),
            # High priority - these should override others
            ("timestamp", "log.timestamp"),
            ("level_error", "log.level_error"),
            ("level_warn", "log.level_warn"),
            ("level_info", "log.level_info"),
            ("level_debug", "log.level_debug"),
            ("level_trace", "log.level_trace"),
            # URLs and paths
            ("url", "log.url"),
            ("email", "log.email"),
            ("windows_path", "log.windows_path"),
            ("unix_path", "log.path"),
            # Network
            ("ipv6", "log.ipv6"),
            ("ipv4", "log.ip"),
            ("mac", "log.mac"),
            ("port", "log.port"),
            # Identifiers
            ("uuid", "log.uuid"),
            ("hex", "log.hex"),
            ("hash", "log.hash"),
            # Container/K8s
            ("k8s_resource", "log.k8s_resource"),
            ("docker_image", "log.docker_image"),
            # HTTP
            ("http_method", "log.http_method"),
            ("http_status", "log.http_status"),
            # Values
            ("null_value", "log.null"),
            ("bool_value", "log.bool"),
            ("size_value", "log.size"),
            ("duration_value", "log.duration"),
            ("number", "log.number"),
            # Process
            ("thread", "log.thread"),
            ("pid", "log.pid"),
        ]

        for pattern_name, style_name in patterns_to_check:
            # Skip patterns we've already matched during parsing
            if pattern_name in skip_patterns:
                continue

            # For string patterns, apply normally
            if pattern_name in ["double_quoted", "single_quoted"]:
                self._apply_pattern(text, pattern_name, style_name, char_styles)
            else:
                # For other patterns, skip quoted regions
                self._apply_pattern_with_exclusions(
                    text, pattern_name, style_name, char_styles, quoted_regions
                )

        # Convert char styles to segments
        return self._create_segments_from_char_styles(text, char_styles)

    def _apply_pattern(
        self,
        text: str,
        pattern_name: str,
        style_name: str,
        char_styles: List[Optional[str]],
    ) -> None:
        """Apply a pattern to the text, updating char_styles array."""
        pattern = self._get_cached_pattern(pattern_name)
        if not pattern:
            return

        if HAS_PYPARSING and hasattr(pattern, "scanString"):
            # pyparsing pattern
            try:
                for tokens, start, end in pattern.scanString(text):
                    for i in range(start, end):
                        if char_styles[i] is None:
                            char_styles[i] = style_name
            except Exception as e:
                logger.debug(f"Failed to apply pyparsing pattern {pattern_name}: {e}")
        else:
            # regex pattern
            for match in pattern.finditer(text):
                start, end = match.span()
                for i in range(start, end):
                    if char_styles[i] is None:
                        char_styles[i] = style_name

    def _get_cached_pattern(self, pattern_name: str) -> Any:
        """Get a pattern with caching."""
        if pattern_name not in self._pattern_cache:
            self._pattern_cache[pattern_name] = self.patterns.get_pattern(pattern_name)
        return self._pattern_cache[pattern_name]

    def _create_segments_from_char_styles(
        self, text: str, char_styles: List[Optional[str]]
    ) -> List[Segment]:
        """Create segments from character-level style information."""
        if not text:
            return []

        segments = []
        current_style = char_styles[0]
        current_text = text[0]

        for i in range(1, len(text)):
            if char_styles[i] == current_style:
                current_text += text[i]
            else:
                # Style changed, emit segment
                style = self._get_style(current_style)
                segments.append(Segment(current_text, style))
                current_style = char_styles[i]
                current_text = text[i]

        # Don't forget the last segment
        style = self._get_style(current_style)
        segments.append(Segment(current_text, style))

        return segments

    def _find_quoted_regions(self, text: str) -> List[Tuple[int, int]]:
        """Find all quoted string regions in the text."""
        regions = []

        # Find double-quoted strings using pre-compiled pattern
        for match in self._quoted_double_pattern.finditer(text):
            regions.append((match.start(), match.end()))

        # Find single-quoted strings using pre-compiled pattern
        for match in self._quoted_single_pattern.finditer(text):
            regions.append((match.start(), match.end()))

        # Sort by start position
        regions.sort(key=lambda x: x[0])

        return regions

    def _apply_pattern_with_exclusions(
        self,
        text: str,
        pattern_name: str,
        style_name: str,
        char_styles: List[Optional[str]],
        excluded_regions: List[Tuple[int, int]],
    ) -> None:
        """Apply a pattern to text, excluding certain regions."""
        pattern = self._get_cached_pattern(pattern_name)
        if not pattern:
            return

        def is_in_excluded_region(start: int, end: int) -> bool:
            """Check if a range overlaps with any excluded region."""
            for exc_start, exc_end in excluded_regions:
                if start < exc_end and end > exc_start:
                    return True
            return False

        if HAS_PYPARSING and hasattr(pattern, "scanString"):
            # pyparsing pattern
            try:
                for tokens, start, end in pattern.scanString(text):
                    if not is_in_excluded_region(start, end):
                        for i in range(start, end):
                            if char_styles[i] is None:
                                char_styles[i] = style_name
            except Exception as e:
                logger.debug(f"Failed to apply pyparsing pattern {pattern_name}: {e}")
        else:
            # regex pattern
            for match in pattern.finditer(text):
                start, end = match.span()
                if not is_in_excluded_region(start, end):
                    for i in range(start, end):
                        if char_styles[i] is None:
                            char_styles[i] = style_name

    def _get_style(self, style_name: Optional[str]) -> Style:
        """Get a Rich style by name."""
        if style_name and style_name in self.theme.styles:
            return self.theme.styles[style_name]
        return Style()

    def _restore_preserved_components(
        self, segments: List[Segment], placeholders: Dict[str, Tuple[str, str]]
    ) -> List[Segment]:
        """Restore preserved components in segments."""
        result = []

        for segment in segments:
            text = segment.text

            # Check if this segment contains any placeholders
            has_placeholder = False
            for placeholder in placeholders:
                if placeholder in text:
                    has_placeholder = True
                    break

            if not has_placeholder:
                result.append(segment)
                continue

            # Split and restore placeholders
            parts = []
            remaining = text

            while remaining:
                found_placeholder = None
                earliest_pos = len(remaining)

                # Find the earliest placeholder
                for placeholder in placeholders:
                    pos = remaining.find(placeholder)
                    if pos != -1 and pos < earliest_pos:
                        earliest_pos = pos
                        found_placeholder = placeholder

                if found_placeholder:
                    # Add text before placeholder
                    if earliest_pos > 0:
                        parts.append((remaining[:earliest_pos], segment.style))

                    # Add the preserved component
                    comp_type, comp_text = placeholders[found_placeholder]
                    style = self._get_preserved_style(comp_type)
                    parts.append((comp_text, style))

                    # Continue with remaining text
                    remaining = remaining[earliest_pos + len(found_placeholder) :]
                else:
                    # No more placeholders
                    parts.append((remaining, segment.style))
                    break

            # Convert parts to segments
            for text, style in parts:
                if text:
                    result.append(Segment(text, style))

        return result

    def _is_json_line(self, text: str) -> bool:
        """Check if a line appears to be primarily JSON content."""
        # Simple heuristic: if line contains a JSON object that takes up most of the line
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", text)
        if json_match:
            # If JSON takes up more than 50% of the line, treat it as JSON
            json_len = json_match.end() - json_match.start()
            return json_len > len(text) * 0.5
        return False

    def _highlight_json_content(self, text: str) -> List[Segment]:
        """Apply JSON-aware highlighting to text containing JSON."""
        segments = []

        # Find the JSON object
        json_match = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\})", text)
        if not json_match:
            # No JSON found, fall back to regular highlighting
            return self._highlight_regular_patterns(text)

        # Split into pre-JSON, JSON, and post-JSON
        pre_json = text[: json_match.start()]
        json_str = json_match.group(1)
        post_json = text[json_match.end() :]

        # Highlight pre-JSON part (container name, timestamp, etc.)
        if pre_json:
            segments.extend(self._highlight_regular_patterns(pre_json))

        # Highlight JSON content
        segments.extend(self._highlight_inline_json(json_str))

        # Highlight post-JSON part
        if post_json:
            segments.extend(self._highlight_regular_patterns(post_json))

        return segments

    def _highlight_inline_json(self, json_str: str) -> List[Segment]:
        """Apply inline JSON highlighting with proper key/value colors."""
        segments = []

        # Parse JSON to apply proper highlighting
        try:
            # Use a simple regex-based approach for inline JSON
            # This preserves the exact formatting while applying colors

            # Pattern to match key-value pairs
            kv_pattern = r'"([^"]+)"\s*:\s*([^,}]+)'
            last_end = 0

            for match in re.finditer(kv_pattern, json_str):
                # Add any text before this match
                if match.start() > last_end:
                    segments.append(
                        Segment(json_str[last_end : match.start()], Style())
                    )

                # Add the key (with quotes)
                key_with_quotes = f'"{match.group(1)}"'
                segments.append(Segment(key_with_quotes, Style(color="cyan")))

                # Add the colon and spacing
                colon_start = match.start() + len(key_with_quotes)
                colon_end = match.start(2)
                segments.append(Segment(json_str[colon_start:colon_end], Style()))

                # Add the value with appropriate styling
                value = match.group(2).strip()
                if value.startswith('"') and value.endswith('"'):
                    segments.append(Segment(value, Style(color="green")))
                elif value in ["true", "false"]:
                    segments.append(Segment(value, Style(color="magenta")))
                elif value == "null":
                    segments.append(
                        Segment(value, Style(color="bright_black", italic=True))
                    )
                elif self._is_number(value):
                    segments.append(Segment(value, Style(color="yellow")))
                else:
                    segments.append(Segment(value, Style()))

                last_end = match.end()

            # Add any remaining text
            if last_end < len(json_str):
                segments.append(Segment(json_str[last_end:], Style()))

        except Exception as e:
            # If parsing fails, return the whole JSON in a default style
            logger.debug(f"Failed to parse inline JSON for highlighting: {e}")
            segments.append(Segment(json_str, Style(color="blue")))

        return segments

    def _highlight_regular_patterns(self, text: str) -> List[Segment]:
        """Apply regular pattern highlighting without string exclusion."""
        # Similar to _highlight_log_patterns but simpler
        char_styles = [None] * len(text)

        patterns_to_check = [
            ("timestamp", "log.timestamp"),
            ("level_error", "log.level_error"),
            ("level_warn", "log.level_warn"),
            ("level_info", "log.level_info"),
            ("level_debug", "log.level_debug"),
            ("level_trace", "log.level_trace"),
            ("container_prefix", "log.container_id"),
        ]

        for pattern_name, style_name in patterns_to_check:
            self._apply_pattern(text, pattern_name, style_name, char_styles)

        return self._create_segments_from_char_styles(text, char_styles)

    def _is_number(self, value: str) -> bool:
        """Check if a string represents a number."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _get_preserved_style(self, comp_type: str) -> Style:
        """Get style for preserved component types."""
        style_map = {
            "container_prefix": "bright_magenta bold",
            "timestamp": "cyan",
            "level_error": "red bold",
            "level_warn": "yellow",
            "level_info": "green",
            "level_debug": "blue",
            "level_trace": "magenta",
        }

        if comp_type in style_map:
            return Style.parse(style_map[comp_type])
        return Style()

    def _contains_xml(self, text: str) -> bool:
        """Check if text contains XML content."""
        # Simple check for XML-like patterns
        xml_pattern = r"<[a-zA-Z][\w\-\.:]*(?:\s+[^>]*)?>.*?</[a-zA-Z][\w\-\.:]*>|<[a-zA-Z][\w\-\.:]*(?:\s+[^>]*)?/>"
        return bool(re.search(xml_pattern, text))

    def _highlight_xml_content(self, text: str) -> List[Segment]:
        """Apply XML-aware highlighting to text containing XML."""
        segments = []

        # Find quoted strings that might contain XML
        # Use separate patterns for double and single quotes to avoid backreference issues
        double_quoted_pattern = r'"([^"\\]|\\.)*"'
        single_quoted_pattern = r"'([^'\\]|\\.)*'"

        # Find all quoted strings
        quoted_matches = []
        for match in re.finditer(double_quoted_pattern, text):
            quoted_matches.append(
                (match.start(), match.end(), '"', match.group()[1:-1])
            )
        for match in re.finditer(single_quoted_pattern, text):
            quoted_matches.append(
                (match.start(), match.end(), "'", match.group()[1:-1])
            )

        # Sort by position
        quoted_matches.sort(key=lambda x: x[0])

        last_end = 0

        for start, end, quote_char, quoted_content in quoted_matches:
            # Add text before the quoted string
            if start > last_end:
                segments.extend(self._highlight_regular_patterns(text[last_end:start]))

            # Check if the quoted content contains XML
            if self._contains_xml(quoted_content):
                # Add the opening quote
                segments.append(Segment(quote_char, Style(color="green")))

                # Highlight the XML content
                segments.extend(self._highlight_inline_xml(quoted_content))

                # Add the closing quote
                segments.append(Segment(quote_char, Style(color="green")))
            else:
                # Regular quoted string
                segments.append(Segment(text[start:end], Style(color="green")))

            last_end = end

        # Add any remaining text
        if last_end < len(text):
            segments.extend(self._highlight_regular_patterns(text[last_end:]))

        return segments

    def _highlight_inline_xml(self, xml_str: str) -> List[Segment]:
        """Apply inline XML highlighting."""
        segments = []

        # Pattern to match XML tags and content
        pattern = r"(<[^>]+>)|([^<]+)"

        for match in re.finditer(pattern, xml_str):
            tag = match.group(1)
            content = match.group(2)

            if tag:
                # This is an XML tag
                if tag.startswith("</"):
                    # Closing tag
                    segments.append(
                        Segment("</", Style(color="bright_blue", bold=True))
                    )
                    tag_name = tag[2:-1]
                    segments.append(
                        Segment(tag_name, Style(color="bright_blue", bold=True))
                    )
                    segments.append(Segment(">", Style(color="bright_blue", bold=True)))
                elif tag.endswith("/>"):
                    # Self-closing tag
                    segments.append(Segment("<", Style(color="bright_blue", bold=True)))

                    # Extract tag name and attributes
                    tag_content = tag[1:-2].strip()
                    parts = tag_content.split(None, 1)
                    tag_name = parts[0]

                    segments.append(
                        Segment(tag_name, Style(color="bright_blue", bold=True))
                    )

                    if len(parts) > 1:
                        # Has attributes
                        segments.extend(self._highlight_xml_attributes(" " + parts[1]))

                    segments.append(
                        Segment("/>", Style(color="bright_blue", bold=True))
                    )
                else:
                    # Opening tag
                    segments.append(Segment("<", Style(color="bright_blue", bold=True)))

                    # Extract tag name and attributes
                    tag_content = tag[1:-1]
                    parts = tag_content.split(None, 1)
                    tag_name = parts[0]

                    segments.append(
                        Segment(tag_name, Style(color="bright_blue", bold=True))
                    )

                    if len(parts) > 1:
                        # Has attributes
                        segments.extend(self._highlight_xml_attributes(" " + parts[1]))

                    segments.append(Segment(">", Style(color="bright_blue", bold=True)))
            elif content:
                # This is text content
                segments.append(Segment(content, Style(color="white")))

        return segments

    def _highlight_xml_attributes(self, attrs_str: str) -> List[Segment]:
        """Highlight XML attributes."""
        segments = []

        # Pattern for attribute="value" pairs
        attr_pattern = r'(\s*)(\w+)(=)(["\'])([^\4]*?)\4'
        last_end = 0

        for match in re.finditer(attr_pattern, attrs_str):
            # Add any text before this attribute
            if match.start() > last_end:
                segments.append(Segment(attrs_str[last_end : match.start()], Style()))

            # Add the attribute components
            segments.append(Segment(match.group(1), Style()))  # whitespace
            segments.append(
                Segment(match.group(2), Style(color="bright_yellow"))
            )  # attribute name
            segments.append(Segment(match.group(3), Style()))  # equals sign
            segments.append(
                Segment(match.group(4), Style(color="bright_green"))
            )  # opening quote
            segments.append(
                Segment(match.group(5), Style(color="bright_green"))
            )  # value
            segments.append(
                Segment(match.group(4), Style(color="bright_green"))
            )  # closing quote

            last_end = match.end()

        # Add any remaining text
        if last_end < len(attrs_str):
            segments.append(Segment(attrs_str[last_end:], Style()))

        return segments
