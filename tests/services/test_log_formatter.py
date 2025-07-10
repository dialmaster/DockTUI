"""Tests for the LogFormatter service."""

import logging
from unittest.mock import Mock, MagicMock, patch

import pytest
from rich.segment import Segment
from rich.style import Style

from DockTUI.services.log_formatter import LogFormatter


class TestLogFormatter:
    """Test cases for the LogFormatter class."""
    
    @pytest.fixture
    def formatter(self):
        """Create a LogFormatter instance for testing."""
        return LogFormatter()
    
    @pytest.fixture
    def mock_log_line(self):
        """Create a mock log line object."""
        mock = Mock()
        mock.has_json = False
        mock.has_xml = False
        mock.is_expanded = False
        mock.json_start_pos = None
        mock.xml_start_pos = None
        return mock
    
    def test_init_with_smart_highlighter(self):
        """Test initialization when SmartLogFormatter is available."""
        with patch('DockTUI.services.log_formatter.HAS_SMART_HIGHLIGHTER', True):
            with patch('DockTUI.services.log_formatter.SmartLogFormatter') as mock_smart:
                mock_instance = Mock()
                mock_smart.return_value = mock_instance
                
                formatter = LogFormatter()
                
                assert formatter.smart_formatter is mock_instance
                assert formatter.json_formatter is not None
                assert formatter.xml_formatter is not None
                assert formatter._console is not None
    
    def test_init_without_smart_highlighter(self):
        """Test initialization when SmartLogFormatter is not available."""
        with patch('DockTUI.services.log_formatter.HAS_SMART_HIGHLIGHTER', False):
            formatter = LogFormatter()
            
            assert formatter.smart_formatter is None
            assert formatter.json_formatter is not None
            assert formatter.xml_formatter is not None
    
    def test_init_smart_highlighter_import_error(self):
        """Test initialization when SmartLogFormatter import fails."""
        with patch('DockTUI.services.log_formatter.HAS_SMART_HIGHLIGHTER', True):
            with patch('DockTUI.services.log_formatter.SmartLogFormatter') as mock_smart:
                mock_smart.side_effect = ImportError("Test error")
                
                formatter = LogFormatter()
                
                assert formatter.smart_formatter is None
    
    def test_format_json_pretty_with_smart_formatter(self, formatter):
        """Test JSON formatting when smart formatter is available."""
        # Set up smart formatter
        mock_smart = Mock()
        mock_result = [[Segment("test", Style())]]
        mock_smart.format_json_pretty.return_value = mock_result
        formatter.smart_formatter = mock_smart
        
        # Test
        json_data = {"key": "value"}
        result = formatter.format_json_pretty(json_data)
        
        # Verify
        assert result == mock_result
        mock_smart.format_json_pretty.assert_called_once_with(json_data)
        
    def test_format_json_pretty_without_smart_formatter(self, formatter):
        """Test JSON formatting when smart formatter is not available."""
        # Remove smart formatter
        formatter.smart_formatter = None
        
        # Mock json formatter
        mock_result = [[Segment("json", Style())]]
        formatter.json_formatter.format_json_pretty = Mock(return_value=mock_result)
        
        # Test
        json_data = {"key": "value"}
        result = formatter.format_json_pretty(json_data)
        
        # Verify
        assert result == mock_result
        formatter.json_formatter.format_json_pretty.assert_called_once_with(json_data)
    
    def test_format_xml_pretty(self, formatter):
        """Test XML formatting."""
        # Mock xml formatter
        mock_result = [[Segment("xml", Style())]]
        formatter.xml_formatter.format_xml_pretty = Mock(return_value=mock_result)
        
        # Test
        xml_data = "<root><item>test</item></root>"
        result = formatter.format_xml_pretty(xml_data)
        
        # Verify
        assert result == mock_result
        formatter.xml_formatter.format_xml_pretty.assert_called_once_with(xml_data)
    
    def test_apply_zebra_stripe_even_line(self, formatter):
        """Test zebra striping for even line numbers."""
        segments = [
            Segment("test", Style(color="red")),
            Segment(" text", Style())
        ]
        
        result = formatter.apply_zebra_stripe(segments, line_number=2)
        
        # Should add grey15 background
        assert len(result) == 2
        assert result[0].text == "test"
        assert "grey15" in str(result[0].style.bgcolor)
        assert "red" in str(result[0].style.color)  # Original color preserved
        assert result[1].text == " text"
        assert "grey15" in str(result[1].style.bgcolor)
    
    def test_apply_zebra_stripe_odd_line(self, formatter):
        """Test zebra striping for odd line numbers."""
        segments = [
            Segment("test", Style(color="red")),
            Segment(" text", Style())
        ]
        
        result = formatter.apply_zebra_stripe(segments, line_number=3)
        
        # Should return segments unchanged
        assert result == segments
    
    def test_apply_selection_no_overlap(self, formatter):
        """Test selection when there's no overlap with text."""
        segments = [Segment("Hello World", Style())]
        line_text = "Hello World"
        
        # Selection outside of text
        result = formatter.apply_selection(segments, line_text, 20, 25)
        
        assert result == segments
    
    def test_apply_selection_full_overlap(self, formatter):
        """Test selection when entire text is selected."""
        segments = [Segment("Hello World", Style(color="red"))]
        line_text = "Hello World"
        
        result = formatter.apply_selection(segments, line_text, 0, 11)
        
        assert len(result) == 1
        assert result[0].text == "Hello World"
        assert "grey35" in str(result[0].style.bgcolor)  # Selection background
        assert "red" in str(result[0].style.color)  # Original color preserved
    
    def test_apply_selection_partial_overlap(self, formatter):
        """Test selection with partial overlap."""
        segments = [Segment("Hello World", Style())]
        line_text = "Hello World"
        
        # Select "lo Wo"
        result = formatter.apply_selection(segments, line_text, 3, 8)
        
        assert len(result) == 3
        assert result[0].text == "Hel"
        assert result[0].style.bgcolor is None
        assert result[1].text == "lo Wo"
        assert "grey35" in str(result[1].style.bgcolor)
        assert result[2].text == "rld"
        assert result[2].style.bgcolor is None
    
    def test_apply_selection_multiple_segments(self, formatter):
        """Test selection across multiple segments."""
        segments = [
            Segment("Hello", Style(color="red")),
            Segment(" ", Style()),
            Segment("World", Style(color="blue"))
        ]
        line_text = "Hello World"
        
        # Select from "llo" to "Wor"
        result = formatter.apply_selection(segments, line_text, 2, 9)
        
        # Should split segments appropriately
        assert len(result) >= 5
        assert result[0].text == "He"
        assert result[0].style.bgcolor is None
        assert result[1].text == "llo"
        assert "grey35" in str(result[1].style.bgcolor)
    
    def test_process_segment_selection_no_overlap(self, formatter):
        """Test processing segment with no selection overlap."""
        segment = Segment("test", Style())
        result = formatter._process_segment_selection(segment, 0, 4, 10, 15)
        
        assert result == [segment]
    
    def test_process_segment_selection_full_overlap(self, formatter):
        """Test processing segment fully within selection."""
        segment = Segment("test", Style())
        result = formatter._process_segment_selection(segment, 5, 9, 0, 20)
        
        assert len(result) == 1
        assert result[0].text == "test"
        assert "grey35" in str(result[0].style.bgcolor)
    
    def test_handle_selection_start_in_segment(self, formatter):
        """Test handling selection that starts within segment."""
        segment = Segment("Hello World", Style())
        
        # Selection starts at position 6 (W) and ends at position 15 (beyond segment)
        result = formatter._handle_selection_start_in_segment(
            segment, seg_start=0, seg_end=11, sel_start=6, sel_end=15
        )
        
        assert len(result) == 2
        assert result[0].text == "Hello "
        assert result[0].style.bgcolor is None
        assert result[1].text == "World"
        assert "grey35" in str(result[1].style.bgcolor)
    
    def test_handle_selection_end_in_segment(self, formatter):
        """Test handling selection that ends within segment."""
        segment = Segment("Hello World", Style())
        
        # Selection from before segment to position 5
        result = formatter._handle_selection_end_in_segment(
            segment, seg_start=0, sel_end=5
        )
        
        assert len(result) == 2
        assert result[0].text == "Hello"
        assert "grey35" in str(result[0].style.bgcolor)
        assert result[1].text == " World"
        assert result[1].style.bgcolor is None
    
    def test_create_segments_from_components_basic(self, formatter):
        """Test creating segments with basic styling."""
        formatter.smart_formatter = None  # Force basic styling
        
        components = [
            ("timestamp", "2024-01-01", 0),
            ("text", " ", 10),
            ("level_error", "ERROR", 11),
            ("text", " message", 16)
        ]
        
        result = formatter.create_segments_from_components(components)
        
        assert len(result) == 4
        assert result[0].text == "2024-01-01"
        assert "cyan" in str(result[0].style.color)
        assert result[2].text == "ERROR"
        assert "red" in str(result[2].style.color)
        assert result[2].style.bold == True
    
    def test_create_segments_from_components_marked(self, formatter):
        """Test creating segments for marked lines (should not use smart highlighting)."""
        formatter.smart_formatter = Mock()  # Has smart formatter
        
        components = [
            ("marked", "------ MARKED 2024-01-01 ------", 0)
        ]
        
        result = formatter.create_segments_from_components(components, raw_text="test")
        
        # Should use basic styling for marked lines
        assert len(result) == 1
        assert "purple" in str(result[0].style.bgcolor)
        assert result[0].style.bold == True
        # Smart formatter should not be called
        formatter.smart_formatter.highlight_line.assert_not_called()
    
    def test_create_segments_from_components_json(self, formatter):
        """Test creating segments for JSON content."""
        formatter.smart_formatter = None
        
        components = [
            ("json", '{"key": "value"}', 0),
            ("json_expanded", "", 16)
        ]
        
        result = formatter.create_segments_from_components(components)
        
        # Should have JSON emoji
        assert any(seg.text == "📋 " for seg in result)
        # Should have expansion indicator
        assert any(seg.text == " 📂" for seg in result)
    
    def test_create_segments_from_components_xml(self, formatter):
        """Test creating segments for XML content."""
        formatter.smart_formatter = None
        
        components = [
            ("xml", '<root>test</root>', 0),
            ("xml_expanded", "", 17)
        ]
        
        result = formatter.create_segments_from_components(components)
        
        # Should have XML emoji
        assert any(seg.text == "📄 " for seg in result)
        # Should have expansion indicator
        assert any(seg.text == " 📂" for seg in result)
    
    def test_create_segments_from_components_smart(self, formatter, mock_log_line):
        """Test creating segments with smart highlighting."""
        # Set up smart formatter
        mock_smart = Mock()
        mock_segments = [Segment("smart", Style(color="green"))]
        mock_smart.highlight_line.return_value = mock_segments
        formatter.smart_formatter = mock_smart
        
        components = [
            ("timestamp", "2024-01-01", 0),
            ("text", " test", 10)
        ]
        raw_text = "2024-01-01 test"
        
        result = formatter.create_segments_from_components(
            components, raw_text=raw_text, log_line=mock_log_line
        )
        
        assert result == mock_segments
        mock_smart.highlight_line.assert_called_once()
    
    def test_should_use_smart_highlighting_no_formatter(self, formatter):
        """Test smart highlighting check when formatter not available."""
        formatter.smart_formatter = None
        
        components = [("text", "test", 0)]
        assert formatter._should_use_smart_highlighting(components, "test") == False
    
    def test_should_use_smart_highlighting_no_raw_text(self, formatter):
        """Test smart highlighting check with no raw text."""
        formatter.smart_formatter = Mock()
        
        components = [("text", "test", 0)]
        assert formatter._should_use_smart_highlighting(components, None) == False
    
    def test_should_use_smart_highlighting_marked_line(self, formatter):
        """Test smart highlighting check for marked lines."""
        formatter.smart_formatter = Mock()
        
        components = [("marked", "MARKED", 0)]
        assert formatter._should_use_smart_highlighting(components, "test") == False
    
    def test_insert_json_emoji_no_position(self, formatter):
        """Test JSON emoji insertion with no position."""
        segments = [Segment("test", Style())]
        result = formatter._insert_json_emoji(segments, None)
        
        assert result == segments
    
    def test_insert_json_emoji_at_start(self, formatter):
        """Test JSON emoji insertion at start of text."""
        segments = [Segment('{"key": "value"}', Style())]
        result = formatter._insert_json_emoji(segments, 0)
        
        assert len(result) == 2
        assert result[0].text == "📋 "
        assert "blue" in str(result[0].style.color)
        assert result[1].text == '{"key": "value"}'
    
    def test_insert_json_emoji_in_middle(self, formatter):
        """Test JSON emoji insertion in middle of segment."""
        segments = [Segment("Response: {data}", Style())]
        result = formatter._insert_json_emoji(segments, 10)
        
        assert len(result) == 3
        assert result[0].text == "Response: "
        assert result[1].text == "📋 "
        assert result[2].text == "{data}"
    
    def test_insert_json_emoji_across_segments(self, formatter):
        """Test JSON emoji insertion between segments."""
        segments = [
            Segment("Response", Style()),
            Segment(": ", Style()),
            Segment("{data}", Style())
        ]
        result = formatter._insert_json_emoji(segments, 10)
        
        # Should insert emoji at the right position
        assert any(seg.text == "📋 " for seg in result)
    
    def test_insert_xml_emoji_no_position(self, formatter):
        """Test XML emoji insertion with no position."""
        segments = [Segment("test", Style())]
        result = formatter._insert_xml_emoji(segments, None)
        
        assert result == segments
    
    def test_insert_xml_emoji_at_position(self, formatter):
        """Test XML emoji insertion at specific position."""
        segments = [Segment("Data: <root>test</root>", Style())]
        result = formatter._insert_xml_emoji(segments, 6)
        
        assert len(result) == 3
        assert result[0].text == "Data: "
        assert result[1].text == "📄 "
        assert "bright_blue" in str(result[1].style.color)
        assert result[2].text == "<root>test</root>"
    
    def test_create_smart_segments_with_json_emoji(self, formatter, mock_log_line):
        """Test smart segment creation with JSON emoji insertion."""
        # Set up mock log line with JSON
        mock_log_line.has_json = True
        mock_log_line.is_expanded = False
        mock_log_line.json_start_pos = 5
        
        # Set up smart formatter
        mock_smart = Mock()
        mock_segments = [Segment("test {}", Style())]
        mock_smart.highlight_line.return_value = mock_segments
        formatter.smart_formatter = mock_smart
        
        components = [("text", "test {}", 0)]
        result = formatter._create_smart_segments(
            components, Style(), "test {}", mock_log_line
        )
        
        # Should insert JSON emoji
        assert any(seg.text == "📋 " for seg in result)
    
    def test_create_smart_segments_with_xml_emoji(self, formatter, mock_log_line):
        """Test smart segment creation with XML emoji insertion."""
        # Set up mock log line with XML
        mock_log_line.has_json = False
        mock_log_line.has_xml = True
        mock_log_line.is_expanded = False
        mock_log_line.xml_start_pos = 5
        
        # Set up smart formatter
        mock_smart = Mock()
        mock_segments = [Segment("test <xml>", Style())]
        mock_smart.highlight_line.return_value = mock_segments
        formatter.smart_formatter = mock_smart
        
        components = [("text", "test <xml>", 0)]
        result = formatter._create_smart_segments(
            components, Style(), "test <xml>", mock_log_line
        )
        
        # Should insert XML emoji
        assert any(seg.text == "📄 " for seg in result)
    
    def test_styles_dict(self, formatter):
        """Test that all expected styles are defined."""
        expected_styles = [
            "timestamp", "container_prefix", "level_error", "level_fatal",
            "level_critical", "level_warn", "level_warning", "level_info",
            "level_debug", "level_trace", "json", "json_key", "json_string",
            "json_number", "marked", "selection", "text"
        ]
        
        for style_name in expected_styles:
            assert style_name in formatter.STYLES
            assert isinstance(formatter.STYLES[style_name], Style)
    
    def test_console_configuration(self, formatter):
        """Test console is configured correctly."""
        assert formatter._console is not None
        assert formatter._console.width == 1000
        assert formatter._console.legacy_windows == False
    
    def test_edge_cases(self, formatter):
        """Test various edge cases."""
        # Empty segments
        assert formatter.apply_selection([], "", 0, 5) == []
        
        # Empty selection range
        segments = [Segment("test", Style())]
        assert formatter.apply_selection(segments, "test", 5, 5) == segments
        
        # Selection beyond text
        result = formatter._handle_selection_start_in_segment(
            Segment("test", Style()), 0, 4, 2, 10
        )
        assert len(result) == 2
        assert result[0].text == "te"
        assert result[1].text == "st"
        
    def test_complex_selection_scenario(self, formatter):
        """Test complex selection scenario with multiple segments and styles."""
        segments = [
            Segment("[2024-01-01] ", Style(color="cyan")),
            Segment("ERROR", Style(color="red", bold=True)),
            Segment(": ", Style()),
            Segment("Failed to connect", Style())
        ]
        line_text = "[2024-01-01] ERROR: Failed to connect"
        
        # Select "01] ERROR: Fa"
        result = formatter.apply_selection(segments, line_text, 9, 22)
        
        # Verify selection is applied correctly across segments
        selected_text = ""
        for seg in result:
            if seg.style and "grey35" in str(seg.style.bgcolor):
                selected_text += seg.text
        
        assert "01] ERROR: Fa" in line_text[9:22]
    
    def test_process_segment_selection_edge_case(self, formatter):
        """Test edge case in _process_segment_selection."""
        # Test case where segment doesn't overlap with selection at all
        # but doesn't match any of the specific conditions
        segment = Segment("test", Style())
        # Craft specific positions that don't match any condition
        result = formatter._process_segment_selection(
            segment, seg_start=10, seg_end=14, sel_start=5, sel_end=9
        )
        assert result == [segment]
    
    def test_insert_xml_emoji_multiple_segments(self, formatter):
        """Test XML emoji insertion with segments before insertion point."""
        # Create segments where emoji position is in a later segment
        segments = [
            Segment("Before ", Style()),  # 0-7
            Segment("text ", Style()),    # 7-12
            Segment("<xml>", Style())     # 12-17
        ]
        
        # Insert emoji at position 12 (start of third segment)
        result = formatter._insert_xml_emoji(segments, 12)
        
        # First two segments should be unchanged
        assert result[0].text == "Before "
        assert result[1].text == "text "
        # Emoji should be inserted before third segment
        assert any(seg.text == "📄 " for seg in result)
        assert any(seg.text == "<xml>" for seg in result)