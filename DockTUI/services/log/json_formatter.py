"""Shared JSON formatting utilities for log viewers."""

import json
import re
from typing import Any, Dict, List

from rich.segment import Segment
from rich.style import Style


class JSONFormatter:
    """Handles JSON formatting and pretty-printing for logs."""

    # JSON-specific styles with improved contrast
    JSON_STYLES = {
        "key": Style(color="cyan"),  # Cyan for JSON keys
        "string": Style(color="green"),  # Green for string values
        "number": Style(color="yellow"),  # Yellow for numbers
        "bool": Style(color="magenta"),  # Magenta for booleans (was yellow)
        "null": Style(color="bright_black", italic=True),  # Dimmed italic for null
        "brace": Style(color="white", bold=True),  # White bold for braces
        "default": Style(),
    }

    @classmethod
    def format_json_pretty(cls, json_data: Dict[str, Any]) -> List[List[Segment]]:
        """
        Format JSON data as pretty-printed segments, returning list of lines.

        Args:
            json_data: The JSON data to format

        Returns:
            List of lines, where each line is a list of segments
        """
        json_str = json.dumps(json_data, indent=2)
        lines = []

        for line in json_str.split("\n"):
            segments = cls._format_json_line(line)
            lines.append(segments)

        return lines

    @classmethod
    def _format_json_line(cls, line: str) -> List[Segment]:
        """Format a single line of JSON."""
        segments = []

        # Handle key-value pairs
        if ":" in line:
            parts = line.split(":", 1)
            key_part = parts[0]
            value_part = parts[1] if len(parts) > 1 else ""

            # Add indentation
            indent_match = re.match(r"^(\s*)", key_part)
            if indent_match:
                segments.append(Segment(indent_match.group(1), Style()))
                key_part = key_part[len(indent_match.group(1)) :]

            # Add key
            if '"' in key_part:
                segments.append(Segment(key_part, cls.JSON_STYLES["key"]))
            else:
                segments.append(Segment(key_part, cls.JSON_STYLES["default"]))

            # Add colon
            segments.append(Segment(":", cls.JSON_STYLES["default"]))

            # Add value segments
            segments.extend(cls._format_json_value_segments(value_part))
        else:
            # Handle braces, brackets, or plain values
            if any(c in line for c in "{}[]"):
                segments.append(Segment(line, cls.JSON_STYLES["brace"]))
            else:
                segments.append(Segment(line, cls.JSON_STYLES["default"]))

        return segments

    @classmethod
    def _format_json_value_segments(cls, value: str) -> List[Segment]:
        """Format a JSON value as multiple segments with appropriate styling."""
        segments = []

        # First, find the actual value part (skip leading spaces)
        value_match = re.match(r"^(\s*)(.*?)(\s*,?\s*)$", value)
        if not value_match:
            return [Segment(value, cls.JSON_STYLES["default"])]

        lead_space, actual_value, trail = value_match.groups()

        # Add leading space if any
        if lead_space:
            segments.append(Segment(lead_space, Style()))

        # Style the actual value
        if actual_value.startswith('"') and actual_value.endswith('"'):
            segments.append(Segment(actual_value, cls.JSON_STYLES["string"]))
        elif actual_value in ["true", "false"]:
            segments.append(Segment(actual_value, cls.JSON_STYLES["bool"]))
        elif actual_value == "null":
            segments.append(Segment(actual_value, cls.JSON_STYLES["null"]))
        elif cls._is_number(actual_value):
            segments.append(Segment(actual_value, cls.JSON_STYLES["number"]))
        else:
            segments.append(Segment(actual_value, cls.JSON_STYLES["default"]))

        # Add trailing characters (comma, spaces)
        if trail:
            segments.append(Segment(trail, Style()))

        return segments

    @staticmethod
    def _is_number(value: str) -> bool:
        """Check if a value is a number."""
        try:
            float(value)
            return True
        except ValueError:
            return False
