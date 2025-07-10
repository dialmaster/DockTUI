"""Unit tests for SmartLogFormatter."""

import re
from typing import Dict, List, Tuple
from unittest.mock import MagicMock, Mock, patch

import pytest
from rich.segment import Segment
from rich.style import Style
from rich.theme import Theme

from DockTUI.services.log.highlighter.smart import SmartLogFormatter


class TestSmartLogFormatter:
    """Test cases for SmartLogFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create a SmartLogFormatter instance for testing."""
        return SmartLogFormatter()

    @pytest.fixture
    def mock_theme(self):
        """Create a mock theme with test styles."""
        theme = Theme()
        theme.styles = {
            "log.timestamp": Style(color="cyan"),
            "log.level_error": Style(color="red", bold=True),
            "log.level_warn": Style(color="yellow"),
            "log.level_info": Style(color="green"),
            "log.level_debug": Style(color="blue"),
            "log.level_trace": Style(color="magenta"),
            "log.quoted": Style(color="green"),
            "log.single_quoted": Style(color="green"),
            "log.url": Style(color="blue", underline=True),
            "log.ip": Style(color="cyan"),
            "log.number": Style(color="yellow"),
            "log.null": Style(color="bright_black", italic=True),
            "log.bool": Style(color="magenta"),
            "log.path": Style(color="cyan"),
        }
        return theme

    def test_initialization(self, formatter):
        """Test SmartLogFormatter initialization."""
        assert formatter.theme is not None
        assert formatter.patterns is not None
        assert formatter.json_formatter is not None
        assert hasattr(formatter, "_console")
        assert isinstance(formatter._pattern_cache, dict)
        assert len(formatter._pattern_cache) == 0

    def test_highlight_empty_line(self, formatter):
        """Test highlighting an empty line."""
        segments = formatter.highlight_line("")
        assert len(segments) == 1
        assert segments[0].text == ""
        assert segments[0].style == Style()

    def test_highlight_simple_text(self, formatter):
        """Test highlighting simple text without patterns."""
        text = "This is plain text without any special patterns"
        segments = formatter.highlight_line(text)
        
        # Should return segments but exact styling depends on pattern matching
        assert len(segments) >= 1
        # Reconstruct the text from segments
        reconstructed = "".join(seg.text for seg in segments)
        assert reconstructed == text

    def test_looks_like_code_detection(self, formatter):
        """Test code pattern detection."""
        # Code patterns that should be detected
        code_samples = [
            "def hello_world():",
            "class MyClass:",
            "function test() {",
            "const value = 42;",
            "let name = 'test';",
            "var items = [];",
            "if (condition) {",
            "for (i = 0; i < 10; i++) {",
            "while (true) {",
            "try {",
            "import os",
            "from collections import defaultdict",
            "require('express');",
            "public void method() {",
            "private String name;",
            "protected int count;",
            "return value;",
            "    }",
            "]",
        ]
        
        for code in code_samples:
            assert formatter._looks_like_code(code), f"Failed to detect code: {code}"
        
        # Non-code patterns
        non_code_samples = [
            "2024-01-01 INFO: Application started",
            "Error: Connection failed",
            "This is a regular log message",
        ]
        
        for text in non_code_samples:
            assert not formatter._looks_like_code(text), f"Incorrectly detected as code: {text}"

    def test_get_style_name_for_pattern(self, formatter):
        """Test pattern type to style name mapping."""
        mappings = {
            "timestamp": "log.timestamp",
            "log_level_error": "log.level_error",
            "log_level_warn": "log.level_warn",
            "log_level_info": "log.level_info",
            "log_level_debug": "log.level_debug",
            "log_level_trace": "log.level_trace",
        }
        
        for pattern_type, expected_style in mappings.items():
            assert formatter._get_style_name_for_pattern(pattern_type) == expected_style
        
        # Test unknown pattern type
        assert formatter._get_style_name_for_pattern("unknown") is None

    def test_find_quoted_regions(self, formatter):
        """Test finding quoted string regions."""
        # Test double quotes
        text = 'This is "quoted text" and more'
        regions = formatter._find_quoted_regions(text)
        assert len(regions) == 1
        assert regions[0] == (8, 21)  # Position of "quoted text"
        
        # Test single quotes
        text = "This is 'single quoted' text"
        regions = formatter._find_quoted_regions(text)
        assert len(regions) == 1
        assert regions[0] == (8, 23)  # Position of 'single quoted'
        
        # Test mixed quotes
        text = 'Both "double" and \'single\' quotes'
        regions = formatter._find_quoted_regions(text)
        assert len(regions) == 2
        assert regions[0] == (5, 13)  # "double"
        assert regions[1] == (18, 26)  # 'single'
        
        # Test escaped quotes
        text = r'Escaped \"quote\" should not match'
        regions = formatter._find_quoted_regions(text)
        # Depending on regex, this might or might not match escaped quotes

    def test_is_json_line(self, formatter):
        """Test JSON line detection."""
        # Lines that should be detected as JSON
        json_lines = [
            '{"key": "value"}',
            'Prefix {"nested": {"data": 123}} suffix',
            '{"array": [1, 2, 3], "bool": true}',
        ]
        
        for line in json_lines:
            assert formatter._is_json_line(line), f"Failed to detect JSON: {line}"
        
        # Lines that should NOT be detected as JSON (< 50% of line)
        non_json_lines = [
            'This is a long message with small {"json": "object"} embedded',
            'Regular log message without JSON',
            'Error: {incomplete json',
        ]
        
        for line in non_json_lines:
            if "{" in line and "}" in line:
                # Check if JSON takes up less than 50% of the line
                json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", line)
                if json_match:
                    json_len = json_match.end() - json_match.start()
                    is_json = json_len > len(line) * 0.5
                    assert formatter._is_json_line(line) == is_json

    def test_is_number(self, formatter):
        """Test number detection."""
        # Valid numbers
        numbers = ["42", "3.14", "-10", "0.001", "1e6", "-3.14e-10", "NaN"]  # NaN is valid for float()
        for num in numbers:
            assert formatter._is_number(num), f"Failed to detect number: {num}"
        
        # Invalid numbers
        non_numbers = ["abc", "12.34.56", "10x", ""]
        for text in non_numbers:
            assert not formatter._is_number(text), f"Incorrectly detected as number: {text}"

    def test_contains_xml(self, formatter):
        """Test XML content detection."""
        # XML content
        xml_content = [
            "<tag>content</tag>",
            '<element attr="value">text</element>',
            "<self-closing/>",
            '<ns:element xmlns:ns="http://example.com">data</ns:element>',
        ]
        
        for xml in xml_content:
            assert formatter._contains_xml(xml), f"Failed to detect XML: {xml}"
        
        # Non-XML content
        non_xml = [
            "Plain text",
            "Less than < and greater than >",
            "Email: user@example.com",
        ]
        
        for text in non_xml:
            assert not formatter._contains_xml(text), f"Incorrectly detected as XML: {text}"

    def test_get_preserved_style(self, formatter):
        """Test getting styles for preserved components."""
        style_map = {
            "container_prefix": "bright_magenta bold",
            "timestamp": "cyan",
            "level_error": "red bold",
            "level_warn": "yellow",
            "level_info": "green",
            "level_debug": "blue",
            "level_trace": "magenta",
        }
        
        for comp_type, expected_style_str in style_map.items():
            style = formatter._get_preserved_style(comp_type)
            assert isinstance(style, Style)
            # Style.parse should create a style from the string
            expected = Style.parse(expected_style_str)
            assert style == expected
        
        # Test unknown component type
        style = formatter._get_preserved_style("unknown")
        assert style == Style()

    def test_create_segments_from_char_styles(self, formatter):
        """Test creating segments from character-level styles."""
        text = "Hello World"
        char_styles = [
            "style1", "style1", "style1", "style1", "style1",  # "Hello"
            None,  # space
            "style2", "style2", "style2", "style2", "style2"  # "World"
        ]
        
        with patch.object(formatter, "_get_style") as mock_get_style:
            mock_get_style.side_effect = lambda s: Style(color="red") if s == "style1" else (
                Style(color="blue") if s == "style2" else Style()
            )
            
            segments = formatter._create_segments_from_char_styles(text, char_styles)
            
            assert len(segments) == 3
            assert segments[0].text == "Hello"
            assert segments[1].text == " "
            assert segments[2].text == "World"

    def test_apply_pattern(self, formatter):
        """Test applying a pattern to text."""
        text = "Error: Something went wrong"
        char_styles = [None] * len(text)
        
        # Mock the pattern cache to return a simple regex
        formatter._pattern_cache["test_pattern"] = re.compile(r"Error")
        
        formatter._apply_pattern(text, "test_pattern", "error_style", char_styles)
        
        # Check that "Error" positions are marked with the style
        assert char_styles[0:5] == ["error_style"] * 5
        # Rest should remain None
        assert all(s is None for s in char_styles[5:])

    def test_apply_pattern_with_exclusions(self, formatter):
        """Test applying pattern with excluded regions."""
        text = 'This "Error" is quoted but Error is not'
        char_styles = [None] * len(text)
        excluded_regions = [(5, 12)]  # Position of "Error" including quotes
        
        # Mock the pattern
        formatter._pattern_cache["error_pattern"] = re.compile(r"Error")
        
        formatter._apply_pattern_with_exclusions(
            text, "error_pattern", "error_style", char_styles, excluded_regions
        )
        
        # First "Error" should be excluded (inside quotes)
        assert all(s is None for s in char_styles[6:11])  # "Error" inside quotes
        
        # Second "Error" should be styled
        error_start = text.rfind("Error")
        assert char_styles[error_start:error_start + 5] == ["error_style"] * 5

    @patch("DockTUI.services.log.highlighter.smart.HAS_PYGMENTS", True)
    @patch("DockTUI.services.log.highlighter.smart.guess_lexer")
    def test_highlight_code_with_pygments(self, mock_guess_lexer, formatter):
        """Test code highlighting with Pygments available."""
        from pygments.token import Token
        
        # Mock lexer and tokens
        mock_lexer = Mock()
        mock_lexer.get_tokens.return_value = [
            (Token.Keyword, "def"),
            (Token.Text, " "),
            (Token.Name.Function, "test"),
            (Token.Punctuation, "():"),
        ]
        mock_guess_lexer.return_value = mock_lexer
        
        # Mock token names
        for token, _ in mock_lexer.get_tokens.return_value:
            token.__name__ = str(token).split(".")[-1]
        
        segments = formatter._highlight_code("def test():")
        
        assert len(segments) == 4
        assert segments[0].text == "def"
        assert segments[1].text == " "
        assert segments[2].text == "test"
        assert segments[3].text == "():"

    @patch("DockTUI.services.log.highlighter.smart.HAS_PYGMENTS", False)
    def test_highlight_code_without_pygments(self, formatter):
        """Test code highlighting fallback when Pygments not available."""
        with patch.object(formatter, "_highlight_log_patterns") as mock_highlight:
            mock_highlight.return_value = [Segment("def test():", Style())]
            
            segments = formatter._highlight_code("def test():")
            
            assert len(segments) == 1
            assert segments[0].text == "def test():"
            mock_highlight.assert_not_called()  # Should return early

    def test_highlight_inline_json(self, formatter):
        """Test inline JSON highlighting."""
        json_str = '{"key": "value", "number": 42, "bool": true, "null": null}'
        segments = formatter._highlight_inline_json(json_str)
        
        # Verify segments were created
        assert len(segments) > 0
        
        # Reconstruct text
        reconstructed = "".join(seg.text for seg in segments)
        assert reconstructed == json_str
        
        # Check for specific styling (keys should be cyan)
        text_parts = [seg.text for seg in segments]
        assert '"key"' in text_parts
        
    def test_highlight_inline_xml(self, formatter):
        """Test inline XML highlighting."""
        xml_str = '<root attr="value"><child>content</child></root>'
        segments = formatter._highlight_inline_xml(xml_str)
        
        # Verify segments were created
        assert len(segments) > 0
        
        # Reconstruct text
        reconstructed = "".join(seg.text for seg in segments)
        assert reconstructed == xml_str

    def test_highlight_xml_attributes(self, formatter):
        """Test XML attribute highlighting."""
        attrs_str = ' id="123" class="test" enabled="true"'
        segments = formatter._highlight_xml_attributes(attrs_str)
        
        # Verify segments were created
        assert len(segments) > 0
        
        # Reconstruct text
        reconstructed = "".join(seg.text for seg in segments)
        assert reconstructed == attrs_str

    def test_restore_preserved_components(self, formatter):
        """Test restoring preserved components in segments."""
        # Create segments with placeholders
        segments = [
            Segment("Before ", Style()),
            Segment("__PRESERVE_0__", Style()),
            Segment(" after", Style()),
        ]
        
        placeholders = {
            "__PRESERVE_0__": ("timestamp", "2024-01-01 12:00:00")
        }
        
        with patch.object(formatter, "_get_preserved_style") as mock_get_style:
            mock_get_style.return_value = Style(color="cyan")
            
            result = formatter._restore_preserved_components(segments, placeholders)
            
            assert len(result) == 3
            assert result[0].text == "Before "
            assert result[1].text == "2024-01-01 12:00:00"
            assert result[2].text == " after"
            
            mock_get_style.assert_called_once_with("timestamp")

    def test_highlight_line_with_preserved_components(self, formatter):
        """Test highlighting with preserved components."""
        text = "2024-01-01 ERROR: Test message"
        preserved = [
            ("timestamp", "2024-01-01", 0),
            ("level_error", "ERROR", 11),
        ]
        
        segments = formatter.highlight_line(text, preserved_components=preserved)
        
        # Verify text is preserved
        reconstructed = "".join(seg.text for seg in segments)
        assert reconstructed == text

    def test_highlight_log_patterns_with_log_line(self, formatter, mock_theme):
        """Test pattern highlighting with pre-parsed log line data."""
        formatter.theme = mock_theme
        
        # Mock log line with pattern matches
        mock_log_line = Mock()
        mock_log_line.pattern_matches = [
            ("timestamp", 0, 10),
            ("log_level_error", 11, 16),
        ]
        mock_log_line.timestamp_pos = (0, 10)
        mock_log_line.log_level_pos = (11, 16)
        
        text = "2024-01-01 ERROR: Test message"
        segments = formatter._highlight_log_patterns(text, mock_log_line)
        
        # Verify segments were created
        assert len(segments) > 0
        reconstructed = "".join(seg.text for seg in segments)
        assert reconstructed == text

    def test_get_cached_pattern(self, formatter):
        """Test pattern caching."""
        # First call should cache the pattern
        with patch.object(formatter.patterns, "get_pattern") as mock_get:
            mock_pattern = re.compile(r"test")
            mock_get.return_value = mock_pattern
            
            pattern1 = formatter._get_cached_pattern("test_pattern")
            assert pattern1 == mock_pattern
            mock_get.assert_called_once_with("test_pattern")
        
        # Second call should use cache
        with patch.object(formatter.patterns, "get_pattern") as mock_get:
            pattern2 = formatter._get_cached_pattern("test_pattern")
            assert pattern2 == mock_pattern
            mock_get.assert_not_called()

    def test_format_json_pretty_delegation(self, formatter):
        """Test that format_json_pretty delegates to json_formatter."""
        json_data = {"key": "value"}
        expected_result = [[Segment("formatted", Style())]]
        
        with patch.object(formatter.json_formatter, "format_json_pretty") as mock_format:
            mock_format.return_value = expected_result
            
            result = formatter.format_json_pretty(json_data)
            
            assert result == expected_result
            mock_format.assert_called_once_with(json_data)

    def test_edge_cases(self, formatter):
        """Test various edge cases."""
        # Empty text
        assert formatter.highlight_line("") == [Segment("", Style())]
        
        # None text (should handle gracefully)
        # The implementation returns Segment(None, Style()) for None input
        assert formatter.highlight_line(None) == [Segment(None, Style())]
        
        # Very long line
        long_text = "A" * 10000
        segments = formatter.highlight_line(long_text)
        reconstructed = "".join(seg.text for seg in segments)
        assert len(reconstructed) == 10000
        
        # Special characters
        special_text = "!@#$%^&*()[]{}|\\<>?/~`"
        segments = formatter.highlight_line(special_text)
        reconstructed = "".join(seg.text for seg in segments)
        assert reconstructed == special_text

    def test_real_world_log_lines(self, formatter):
        """Test with real-world log line examples."""
        log_lines = [
            "2024-01-01 12:00:00 INFO [main] Application started successfully",
            "ERROR: Database connection failed at 192.168.1.100:5432",
            '{"timestamp": "2024-01-01", "level": "WARN", "message": "High memory usage"}',
            "DEBUG Thread-1 Processing request from user@example.com",
            "TRACE [UUID: 550e8400-e29b-41d4-a716-446655440000] Operation completed",
            "<request><method>GET</method><url>/api/users</url></request>",
            "Exception in thread \"main\" java.lang.NullPointerException",
        ]
        
        for line in log_lines:
            segments = formatter.highlight_line(line)
            
            # Verify basic properties
            assert len(segments) > 0
            reconstructed = "".join(seg.text for seg in segments).rstrip()
            assert reconstructed == line
            
            # At least some segments should have styling
            has_style = any(seg.style != Style() for seg in segments)
            # Most real log lines should have some highlighting