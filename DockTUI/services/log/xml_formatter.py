"""XML formatting utilities for log viewers."""

import logging
import re
from typing import List

try:
    import defusedxml.minidom as minidom
except ImportError:
    # Fall back to standard library with security warning
    import xml.dom.minidom as minidom

    logging.getLogger("DockTUI.xml_formatter").warning(
        "defusedxml not available. XML parsing may be vulnerable to XXE attacks. "
        "Run 'poetry install' to install security dependencies."
    )

from rich.segment import Segment
from rich.style import Style

logger = logging.getLogger("DockTUI.xml_formatter")


class XMLFormatter:
    """Handles XML formatting and pretty-printing for logs."""

    # XML-specific styles with distinct colors
    XML_STYLES = {
        "tag": Style(color="bright_blue", bold=True),  # Bright blue for XML tags
        "attribute": Style(color="bright_yellow"),  # Bright yellow for attributes
        "value": Style(color="bright_green"),  # Bright green for attribute values
        "text": Style(color="white"),  # White for text content
        "comment": Style(color="bright_black", italic=True),  # Dimmed for comments
        "brace": Style(
            color="bright_blue", bold=True
        ),  # Match tag color for < > brackets
        "default": Style(),
    }

    @classmethod
    def format_xml_pretty(cls, xml_data: str) -> List[List[Segment]]:
        """
        Format XML data as pretty-printed segments, returning list of lines.

        Args:
            xml_data: The XML string to format

        Returns:
            List of lines, where each line is a list of segments
        """
        try:
            # Parse and pretty-print the XML
            dom = minidom.parseString(xml_data)
            pretty_xml = dom.toprettyxml(indent="  ")

            # Remove empty lines
            lines = [line for line in pretty_xml.split("\n") if line.strip()]

            # Skip the XML declaration if present
            if lines and lines[0].startswith("<?xml"):
                lines = lines[1:]

            # Format each line
            formatted_lines = []
            for line in lines:
                segments = cls._format_xml_line(line)
                formatted_lines.append(segments)

            return formatted_lines

        except Exception as e:
            # If parsing fails, return the original XML split by lines
            logger.debug(f"Failed to parse XML for formatting: {e}")
            lines = xml_data.split("\n") if "\n" in xml_data else [xml_data]
            return [[Segment(line, cls.XML_STYLES["default"])] for line in lines]

    @classmethod
    def _format_xml_line(cls, line: str) -> List[Segment]:
        """Format a single line of XML with syntax highlighting."""
        segments = []

        # Handle indentation
        indent_match = re.match(r"^(\s*)", line)
        if indent_match:
            segments.append(Segment(indent_match.group(1), Style()))
            line = line[len(indent_match.group(1)) :]

        # Handle comments
        if line.strip().startswith("<!--"):
            segments.append(Segment(line, cls.XML_STYLES["comment"]))
            return segments

        # Pattern to match XML elements
        # This pattern handles: tags, attributes, text content
        pattern = r"(<[^>]+>)|([^<]+)"

        for match in re.finditer(pattern, line):
            tag_match = match.group(1)
            text_match = match.group(2)

            if tag_match:
                # This is a tag
                segments.extend(cls._format_xml_tag(tag_match))
            elif text_match and text_match.strip():
                # This is text content
                segments.append(Segment(text_match, cls.XML_STYLES["text"]))

        return segments

    @classmethod
    def _format_xml_tag(cls, tag: str) -> List[Segment]:
        """Format an XML tag with attributes."""
        segments = []

        # Extract tag name and attributes
        if tag.startswith("</"):
            # Closing tag
            segments.append(Segment("<", cls.XML_STYLES["brace"]))
            segments.append(Segment("/", cls.XML_STYLES["brace"]))
            tag_name = tag[2:-1]
            segments.append(Segment(tag_name, cls.XML_STYLES["tag"]))
            segments.append(Segment(">", cls.XML_STYLES["brace"]))
        else:
            # Opening tag or self-closing tag
            segments.append(Segment("<", cls.XML_STYLES["brace"]))

            # Parse tag content
            tag_content = tag[1:-1]  # Remove < and >

            # Check if self-closing
            if tag_content.endswith("/"):
                tag_content = tag_content[:-1].strip()
                is_self_closing = True
            else:
                is_self_closing = False

            # Extract tag name and attributes
            parts = tag_content.split(None, 1)
            tag_name = parts[0]
            segments.append(Segment(tag_name, cls.XML_STYLES["tag"]))

            if len(parts) > 1:
                # Has attributes
                attributes_str = parts[1]
                segments.extend(cls._format_xml_attributes(attributes_str))

            if is_self_closing:
                segments.append(Segment("/", cls.XML_STYLES["brace"]))
            segments.append(Segment(">", cls.XML_STYLES["brace"]))

        return segments

    @classmethod
    def _format_xml_attributes(cls, attributes_str: str) -> List[Segment]:
        """Format XML attributes."""
        segments = []

        # Add space before attributes
        segments.append(Segment(" ", Style()))

        # Pattern to match attribute="value" pairs
        attr_pattern = r'(\w+)=("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'

        last_end = 0
        for match in re.finditer(attr_pattern, attributes_str):
            # Add any text between attributes
            if match.start() > last_end:
                segments.append(
                    Segment(attributes_str[last_end : match.start()], Style())
                )

            attr_name = match.group(1)
            attr_value = match.group(2)

            segments.append(Segment(attr_name, cls.XML_STYLES["attribute"]))
            segments.append(Segment("=", cls.XML_STYLES["default"]))
            segments.append(Segment(attr_value, cls.XML_STYLES["value"]))

            last_end = match.end()

        # Add any remaining text
        if last_end < len(attributes_str):
            segments.append(Segment(attributes_str[last_end:], Style()))

        return segments
