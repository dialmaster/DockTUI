"""Log line data model for rich log viewer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..utils.mixins import CacheableMixin


@dataclass
class LogLine(CacheableMixin):
    """Represents a single log line with metadata."""

    raw_text: str
    line_number: int
    timestamp: Optional[datetime] = None
    log_level: Optional[str] = None
    container_name: Optional[str] = None
    container_prefix_end: Optional[int] = None
    has_json: bool = False
    json_data: Optional[Dict] = None  # First JSON object (for backward compatibility)
    json_start_pos: Optional[int] = None  # Position of first JSON
    json_end_pos: Optional[int] = None
    # Support for multiple JSON objects
    json_objects: List[Tuple[Dict, int, int]] = field(
        default_factory=list
    )  # List of (json_data, start_pos, end_pos)
    has_xml: bool = False
    xml_data: Optional[str] = None  # Store as string, not parsed
    xml_start_pos: Optional[int] = None
    xml_end_pos: Optional[int] = None
    is_marked: bool = False
    is_expanded: bool = False
    is_system_message: bool = False

    # Store pattern match positions to avoid re-matching during rendering
    # Each entry is (pattern_type, start_pos, end_pos)
    pattern_matches: List[Tuple[str, int, int]] = field(default_factory=list)

    # Store specific match positions for commonly used patterns
    timestamp_pos: Optional[Tuple[int, int]] = None  # (start, end) positions
    log_level_pos: Optional[Tuple[int, int]] = None  # (start, end) positions

    # Lazy parsing support
    _is_parsed: bool = field(default=False, init=False)
    _parser: Optional[object] = field(
        default=None, init=False, repr=False
    )  # Will store LogParser reference

    def __post_init__(self):
        """Post-initialization processing."""
        super().__init__()
        self.invalidate_cache()

    def add_pattern_match(self, pattern_type: str, start: int, end: int) -> None:
        """Add a pattern match position.

        Args:
            pattern_type: Type of pattern (e.g., 'timestamp', 'log_level', 'url', etc.)
            start: Start position in the raw text
            end: End position in the raw text
        """
        self.pattern_matches.append((pattern_type, start, end))

    def ensure_parsed(self) -> None:
        """Ensure this log line has been parsed. Called on-demand during rendering."""
        if not self._is_parsed and self._parser is not None:
            # Parse the line using the stored parser
            self._parser.parse_into_line(self)

            # Mark as parsed and clear parser reference to free memory
            self._is_parsed = True
            self._parser = None

    @property
    def is_parsed(self) -> bool:
        """Check if this line has been parsed."""
        return self._is_parsed

    @classmethod
    def create_unparsed(
        cls, raw_text: str, line_number: int, parser: object = None
    ) -> "LogLine":
        """Create an unparsed LogLine for lazy parsing.

        Args:
            raw_text: The raw log text
            line_number: The line number
            parser: Optional parser instance for lazy parsing

        Returns:
            An unparsed LogLine instance
        """
        line = cls(raw_text=raw_text, line_number=line_number)
        line._parser = parser
        line._is_parsed = False
        return line
