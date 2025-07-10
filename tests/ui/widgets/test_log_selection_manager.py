"""Unit tests for SelectionManager."""

import json
from unittest.mock import Mock, patch

import pytest

from DockTUI.models.log_line import LogLine
from DockTUI.ui.widgets.log_selection_manager import SelectionManager


class TestSelectionManager:
    """Test cases for SelectionManager."""

    @pytest.fixture
    def manager(self):
        """Create a SelectionManager instance."""
        return SelectionManager()

    @pytest.fixture
    def mock_log_lines(self):
        """Create mock log lines for testing."""
        lines = []
        for i in range(5):
            line = Mock(spec=LogLine)
            line.raw_text = f"Log line {i} with some text content"
            line.is_expanded = False
            line.has_json = False
            line.has_xml = False
            line.json_data = None
            line.xml_data = None
            line.json_start_pos = None
            line.xml_start_pos = None
            lines.append(line)
        return lines

    @pytest.fixture
    def mock_count_json_lines_fn(self):
        """Mock function for counting JSON lines."""
        return Mock(side_effect=lambda data: len(json.dumps(data, indent=2).split("\n")))

    @pytest.fixture
    def mock_count_xml_lines_fn(self):
        """Mock function for counting XML lines."""
        return Mock(return_value=3)  # Default to 3 lines for XML

    def test_init(self, manager):
        """Test SelectionManager initialization."""
        assert manager.selection_start_virtual is None
        assert manager.selection_end_virtual is None
        assert manager.selection_start_x is None
        assert manager.selection_end_x is None
        assert manager.is_selecting is False

    def test_clear_selection(self, manager):
        """Test clearing selection state."""
        # Set some selection state
        manager.selection_start_virtual = 0
        manager.selection_end_virtual = 10
        manager.selection_start_x = 5
        manager.selection_end_x = 20
        manager.is_selecting = True

        # Clear selection
        manager.clear_selection()

        # All state should be reset
        assert manager.selection_start_virtual is None
        assert manager.selection_end_virtual is None
        assert manager.selection_start_x is None
        assert manager.selection_end_x is None
        assert manager.is_selecting is False

    def test_start_selection(self, manager):
        """Test starting a new selection."""
        manager.start_selection(virtual_y=5, virtual_x=10)

        assert manager.selection_start_virtual == 5
        assert manager.selection_end_virtual == 5
        assert manager.selection_start_x == 10
        assert manager.selection_end_x == 11  # Start + 1 for initial character
        assert manager.is_selecting is True

    def test_update_selection_end(self, manager):
        """Test updating selection end position."""
        # Start a selection
        manager.start_selection(virtual_y=5, virtual_x=10)
        
        # Update end position
        manager.update_selection_end(virtual_y=8, virtual_x=25)

        assert manager.selection_end_virtual == 8
        assert manager.selection_end_x == 25
        # Start position should remain unchanged
        assert manager.selection_start_virtual == 5
        assert manager.selection_start_x == 10

    def test_finish_selection(self, manager):
        """Test finishing a selection."""
        manager.start_selection(virtual_y=5, virtual_x=10)
        manager.finish_selection()

        assert manager.is_selecting is False
        # Selection coordinates should remain intact
        assert manager.selection_start_virtual == 5
        assert manager.selection_end_virtual == 5

    def test_select_all(self, manager):
        """Test select all functionality."""
        manager.select_all(total_virtual_lines=20, max_line_length=100)

        assert manager.selection_start_virtual == 0
        assert manager.selection_start_x == 0
        assert manager.selection_end_virtual == 19  # total_lines - 1
        assert manager.selection_end_x == 100

    def test_select_all_default_max_length(self, manager):
        """Test select all with default max line length."""
        manager.select_all(total_virtual_lines=10)

        assert manager.selection_end_x == 999  # Default value

    def test_has_selection_no_selection(self, manager):
        """Test has_selection when no selection exists."""
        assert manager.has_selection() is False

    def test_has_selection_partial_selection(self, manager):
        """Test has_selection with partial selection state."""
        manager.selection_start_virtual = 5
        # End is None
        assert manager.has_selection() is False

        manager.selection_end_virtual = 10
        assert manager.has_selection() is True

    def test_get_normalized_selection_no_selection(self, manager):
        """Test normalized selection when no selection exists."""
        result = manager.get_normalized_selection()
        assert result == (0, 0, 0, 0)

    def test_get_normalized_selection_forward(self, manager):
        """Test normalized selection with forward selection."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 15
        manager.selection_end_x = 30

        start_y, start_x, end_y, end_x = manager.get_normalized_selection()

        assert start_y == 5
        assert end_y == 10
        assert start_x == 15
        assert end_x == 30

    def test_get_normalized_selection_backward(self, manager):
        """Test normalized selection with backward selection."""
        # Selection from bottom to top
        manager.selection_start_virtual = 10
        manager.selection_end_virtual = 5
        manager.selection_start_x = 30
        manager.selection_end_x = 15

        start_y, start_x, end_y, end_x = manager.get_normalized_selection()

        # Y coordinates should be swapped
        assert start_y == 5
        assert end_y == 10
        # X coordinates should also be swapped
        assert start_x == 15
        assert end_x == 30

    def test_get_normalized_selection_none_values(self, manager):
        """Test normalized selection with None X values."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = None
        manager.selection_end_x = None

        start_y, start_x, end_y, end_x = manager.get_normalized_selection()

        assert start_x == 0
        assert end_x == 0

    def test_is_line_in_selection_no_selection(self, manager):
        """Test line in selection check with no selection."""
        assert manager.is_line_in_selection(5) is False

    def test_is_line_in_selection_within_range(self, manager):
        """Test line in selection check within range."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 0
        manager.selection_end_x = 100

        assert manager.is_line_in_selection(4) is False
        assert manager.is_line_in_selection(5) is True
        assert manager.is_line_in_selection(7) is True
        assert manager.is_line_in_selection(10) is True
        assert manager.is_line_in_selection(11) is False

    def test_get_line_selection_range_not_in_selection(self, manager):
        """Test line selection range when line is not in selection."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 0
        manager.selection_end_x = 100

        # Line outside selection
        start, end = manager.get_line_selection_range(3, "Some text")
        assert start == 0
        assert end == 0

    def test_get_line_selection_range_single_line(self, manager):
        """Test line selection range for single-line selection."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 5
        manager.selection_start_x = 10
        manager.selection_end_x = 20

        line_text = "This is a test line with some content"
        start, end = manager.get_line_selection_range(5, line_text)

        assert start == 10
        assert end == 20

    def test_get_line_selection_range_first_line(self, manager):
        """Test line selection range for first line of multi-line selection."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 15
        manager.selection_end_x = 30

        line_text = "First line of the selection"
        start, end = manager.get_line_selection_range(5, line_text)

        assert start == 15
        assert end == len(line_text)

    def test_get_line_selection_range_middle_line(self, manager):
        """Test line selection range for middle line of multi-line selection."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 15
        manager.selection_end_x = 30

        line_text = "Middle line of the selection"
        start, end = manager.get_line_selection_range(7, line_text)

        assert start == 0
        assert end == len(line_text)

    def test_get_line_selection_range_last_line(self, manager):
        """Test line selection range for last line of multi-line selection."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 15
        manager.selection_end_x = 30

        line_text = "Last line of the selection"
        start, end = manager.get_line_selection_range(10, line_text)

        assert start == 0
        assert end == 30

    def test_get_selected_text_no_selection(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting selected text with no selection."""
        result = manager.get_selected_text(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )
        assert result == ""

    def test_get_selected_text_single_line(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting selected text from single line."""
        # Select part of line 1
        manager.selection_start_virtual = 1
        manager.selection_end_virtual = 1
        manager.selection_start_x = 4
        manager.selection_end_x = 10

        result = manager.get_selected_text(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        # Should get "line 1" from "Log line 1 with some text content"
        assert result == "line 1"

    def test_get_selected_text_multiple_lines(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting selected text from multiple lines."""
        # Select from middle of line 1 to middle of line 3
        manager.selection_start_virtual = 1
        manager.selection_end_virtual = 3
        manager.selection_start_x = 10
        manager.selection_end_x = 15

        result = manager.get_selected_text(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == " with some text content"  # From line 1 (includes space at position 10)
        assert lines[1] == mock_log_lines[2].raw_text  # Full line 2
        assert lines[2] == "Log line 3 with"  # Beginning of line 3

    def test_get_selected_text_with_expanded_json(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting selected text with expanded JSON."""
        # Configure line 1 to have expanded JSON
        mock_log_lines[1].is_expanded = True
        mock_log_lines[1].json_data = {"key": "value", "number": 42}

        # Select across the expanded JSON (which will be 4 lines when pretty printed)
        manager.selection_start_virtual = 1
        manager.selection_end_virtual = 4
        manager.selection_start_x = 0
        manager.selection_end_x = 5

        result = manager.get_selected_text(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        lines = result.split("\n")
        assert len(lines) == 4
        # First line is the original log line
        assert lines[0] == mock_log_lines[1].raw_text
        # Next lines are JSON content
        assert "{" in lines[1]
        assert "key" in result or "number" in result

    def test_get_selected_text_with_expanded_xml(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting selected text with expanded XML."""
        # Configure line 2 to have expanded XML
        mock_log_lines[2].is_expanded = True
        mock_log_lines[2].xml_data = "<root><child>data</child></root>"

        # Mock XML formatter
        with patch(
            "DockTUI.services.log.xml_formatter.XMLFormatter"
        ) as mock_xml_formatter:
            mock_segments = [
                [Mock(text="<root>")],
                [Mock(text="  <child>data</child>")],
                [Mock(text="</root>")],
            ]
            mock_xml_formatter.format_xml_pretty.return_value = mock_segments

            # Select the expanded XML lines only (not including next line)
            # Line 2 is expanded with 3 XML lines:
            # Virtual 2: original log line (offset 0)
            # Virtual 3: "<root>" (offset 1)
            # Virtual 4: "  <child>data</child>" (offset 2)
            # Virtual 5: "</root>" (offset 3 - but current_y would be 5)
            # Line 3 starts at virtual 5 after the loop completes
            # So we need to select exactly to the end of the XML
            manager.selection_start_virtual = 2
            manager.selection_end_virtual = 4
            manager.selection_start_x = 0
            manager.selection_end_x = 100  # Large enough to get full line

            result = manager.get_selected_text(
                mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
            )

            lines = result.split("\n")
            # When a line has 3 lines from XML formatter, the iteration goes:
            # current_y=2, offset=0: raw text
            # current_y=3, offset=1: first XML line  
            # current_y=4, offset=2: second XML line
            # current_y=5 (but loop exits as offset would be 3 and line_count is 3)
            assert len(lines) == 3
            assert lines[0] == mock_log_lines[2].raw_text
            assert lines[1] == "<root>"
            assert lines[2] == "  <child>data</child>"

    def test_get_selected_text_with_json_emoji_adjustment(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test selected text with JSON emoji position adjustment."""
        # Configure line with JSON but not expanded
        mock_log_lines[1].has_json = True
        mock_log_lines[1].json_start_pos = 10
        mock_log_lines[1].is_expanded = False

        # Select after the emoji position
        manager.selection_start_virtual = 1
        manager.selection_end_virtual = 1
        manager.selection_start_x = 15  # After emoji at position 10
        manager.selection_end_x = 25

        result = manager.get_selected_text(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        # The selection should be adjusted by -2 for the emoji
        # So actual selection is from 13 to 23
        expected = mock_log_lines[1].raw_text[13:23]
        assert result == expected

    def test_get_selected_text_with_xml_emoji_adjustment(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test selected text with XML emoji position adjustment."""
        # Configure line with XML but not expanded
        mock_log_lines[2].has_xml = True
        mock_log_lines[2].xml_start_pos = 5
        mock_log_lines[2].is_expanded = False

        # Select before and after the emoji
        manager.selection_start_virtual = 2
        manager.selection_end_virtual = 2
        manager.selection_start_x = 3  # Before emoji
        manager.selection_end_x = 20  # After emoji

        result = manager.get_selected_text(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        # Start is before emoji, so no adjustment
        # End is after emoji at pos 5, so adjust by -2
        expected = mock_log_lines[2].raw_text[3:18]
        assert result == expected

    def test_get_line_text_at_offset_main_line(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting line text at offset 0 (main line)."""
        result = manager._get_line_text_at_offset(
            mock_log_lines[0], 0, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )
        assert result == mock_log_lines[0].raw_text

    def test_get_line_text_at_offset_json(
        self, manager, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting line text from JSON offset."""
        log_line = Mock(spec=LogLine)
        log_line.raw_text = "Original line"
        log_line.json_data = {"key": "value", "nested": {"data": 123}}

        # Get second line of JSON (offset 1 means second line)
        result = manager._get_line_text_at_offset(
            log_line, 2, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        # Should get a line from the JSON
        assert "key" in result or "nested" in result or "}" in result

    def test_get_line_text_at_offset_xml(
        self, manager, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting line text from XML offset."""
        log_line = Mock(spec=LogLine)
        log_line.raw_text = "Original line"
        log_line.json_data = None
        log_line.xml_data = "<root><child>data</child></root>"

        with patch(
            "DockTUI.services.log.xml_formatter.XMLFormatter"
        ) as mock_xml_formatter:
            mock_segments = [
                [Mock(text="<root>")],
                [Mock(text="  <child>data</child>")],
                [Mock(text="</root>")],
            ]
            mock_xml_formatter.format_xml_pretty.return_value = mock_segments

            # Get second line of XML
            result = manager._get_line_text_at_offset(
                log_line, 1, mock_count_json_lines_fn, mock_count_xml_lines_fn
            )

            assert result == "<root>"

    def test_get_line_text_at_offset_out_of_bounds(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting line text with out of bounds offset."""
        log_line = Mock(spec=LogLine)
        log_line.raw_text = "Original line"
        log_line.json_data = {"key": "value"}

        # Request offset way beyond JSON lines
        result = manager._get_line_text_at_offset(
            log_line, 100, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        assert result == ""

    def test_extend_selection_up(self, manager):
        """Test extending selection upward."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 0
        manager.selection_end_x = 20

        manager.extend_selection_up()

        assert manager.selection_end_virtual == 9
        assert manager.selection_end_x == 0

    def test_extend_selection_up_at_boundary(self, manager):
        """Test extending selection up at top boundary."""
        manager.selection_end_virtual = 0
        manager.selection_end_x = 10

        manager.extend_selection_up()

        # Should not go below 0
        assert manager.selection_end_virtual == 0
        assert manager.selection_end_x == 10

    def test_extend_selection_up_none_value(self, manager):
        """Test extending selection up with None value."""
        manager.selection_end_virtual = None

        manager.extend_selection_up()

        # Should remain None
        assert manager.selection_end_virtual is None

    def test_extend_selection_down(self, manager):
        """Test extending selection downward."""
        manager.selection_start_virtual = 5
        manager.selection_end_virtual = 10
        manager.selection_start_x = 0
        manager.selection_end_x = 20

        manager.extend_selection_down(max_virtual_lines=20)

        assert manager.selection_end_virtual == 11
        assert manager.selection_end_x == 0

    def test_extend_selection_down_at_boundary(self, manager):
        """Test extending selection down at bottom boundary."""
        manager.selection_end_virtual = 19

        manager.extend_selection_down(max_virtual_lines=20)

        # Should not go beyond max
        assert manager.selection_end_virtual == 19

    def test_extend_selection_down_none_value(self, manager):
        """Test extending selection down with None value."""
        manager.selection_end_virtual = None

        manager.extend_selection_down(max_virtual_lines=20)

        # Should remain None
        assert manager.selection_end_virtual is None

    def test_extend_selection_left(self, manager):
        """Test extending selection left."""
        manager.selection_end_x = 10

        manager.extend_selection_left()

        assert manager.selection_end_x == 9

    def test_extend_selection_left_at_boundary(self, manager):
        """Test extending selection left at boundary."""
        manager.selection_end_x = 0

        manager.extend_selection_left()

        assert manager.selection_end_x == 0

    def test_extend_selection_left_none_value(self, manager):
        """Test extending selection left with None value."""
        manager.selection_end_x = None

        manager.extend_selection_left()

        assert manager.selection_end_x is None

    def test_extend_selection_right(self, manager):
        """Test extending selection right."""
        manager.selection_end_x = 10

        manager.extend_selection_right()

        assert manager.selection_end_x == 11

    def test_extend_selection_right_none_value(self, manager):
        """Test extending selection right with None value."""
        manager.selection_end_x = None

        manager.extend_selection_right()

        assert manager.selection_end_x == 1

    def test_complex_selection_scenario(
        self, manager, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test a complex selection scenario with mixed content."""
        # Create complex log lines
        lines = []
        
        # Regular line
        line1 = Mock(spec=LogLine)
        line1.raw_text = "First regular line"
        line1.is_expanded = False
        line1.has_json = False
        line1.has_xml = False
        line1.json_data = None
        line1.xml_data = None
        lines.append(line1)

        # JSON line (expanded)
        line2 = Mock(spec=LogLine)
        line2.raw_text = "Line with JSON: {\"key\": \"value\"}"
        line2.is_expanded = True
        line2.has_json = True
        line2.json_data = {"key": "value", "number": 42}
        line2.xml_data = None
        line2.json_start_pos = None
        line2.xml_start_pos = None
        lines.append(line2)

        # Regular line
        line3 = Mock(spec=LogLine)
        line3.raw_text = "Another regular line"
        line3.is_expanded = False
        line3.has_json = False
        line3.has_xml = False
        line3.json_data = None
        line3.xml_data = None
        lines.append(line3)

        # Select from middle of first line through JSON to middle of last line
        manager.selection_start_virtual = 0
        manager.selection_end_virtual = 6  # Through expanded JSON
        manager.selection_start_x = 6
        manager.selection_end_x = 7

        result = manager.get_selected_text(
            lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        lines_result = result.split("\n")
        assert len(lines_result) > 3  # Should have multiple lines due to JSON
        assert lines_result[0] == "regular line"  # End of first line
        assert "Another" in lines_result[-1]  # Part of last line

    def test_edge_cases(self, manager):
        """Test various edge cases."""
        # Test empty selection coordinates
        manager.selection_start_virtual = 0
        manager.selection_end_virtual = 0
        manager.selection_start_x = 0
        manager.selection_end_x = 0

        assert manager.has_selection() is True
        start_y, start_x, end_y, end_x = manager.get_normalized_selection()
        assert (start_y, start_x, end_y, end_x) == (0, 0, 0, 0)

        # Test very large selection
        manager.select_all(total_virtual_lines=10000, max_line_length=5000)
        assert manager.selection_end_virtual == 9999
        assert manager.selection_end_x == 5000

        # Test selection state consistency
        manager.start_selection(10, 20)
        manager.update_selection_end(5, 15)
        manager.finish_selection()
        
        # Selection should be preserved after finishing
        assert manager.has_selection() is True
        assert manager.is_selecting is False