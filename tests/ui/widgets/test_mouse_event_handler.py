"""Unit tests for MouseEventHandler."""

import json
import time
from unittest.mock import Mock, call, patch

import pytest
from rich.segment import Segment
from textual.geometry import Offset

from DockTUI.models.log_line import LogLine
from DockTUI.ui.widgets.log_selection_manager import SelectionManager
from DockTUI.ui.widgets.mouse_event_handler import MouseEventHandler


def create_mouse_down(x, y, button=1):
    """Helper to create mock MouseDown event."""
    event = Mock()
    event.x = x
    event.y = y
    event.button = button
    return event


def create_mouse_move(x, y):
    """Helper to create mock MouseMove event."""
    event = Mock()
    event.x = x
    event.y = y
    return event


def create_mouse_up(x, y, button=1):
    """Helper to create mock MouseUp event."""
    event = Mock()
    event.x = x
    event.y = y
    event.button = button
    return event


class TestMouseEventHandler:
    """Test cases for MouseEventHandler."""

    @pytest.fixture
    def mock_selection_manager(self):
        """Create mock selection manager."""
        mock = Mock(spec=SelectionManager)
        mock.is_selecting = False
        return mock

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock callback functions."""
        return {
            "get_line_at_virtual_y": Mock(return_value=None),
            "count_json_lines": Mock(side_effect=lambda data: len(json.dumps(data, indent=2).split("\n"))),
            "count_xml_lines": Mock(return_value=3),
            "get_visible_lines": Mock(return_value=[]),
            "get_scroll_offset": Mock(return_value=Offset(0, 0)),
            "invalidate_virtual_size_immediate": Mock(),
            "clear_line_cache": Mock(),
            "refresh": Mock(),
            "action_copy_selection": Mock(),
        }

    @pytest.fixture
    def handler(self, mock_selection_manager, mock_dependencies):
        """Create MouseEventHandler instance."""
        return MouseEventHandler(
            selection_manager=mock_selection_manager,
            **mock_dependencies
        )

    @pytest.fixture
    def mock_log_line(self):
        """Create a mock LogLine."""
        line = Mock(spec=LogLine)
        line.raw_text = "Test log line with some content"
        line.is_expanded = False
        line.has_json = False
        line.has_xml = False
        line.json_data = None
        line.xml_data = None
        line.json_start_pos = None
        line.xml_start_pos = None
        line.ensure_parsed = Mock()
        line.invalidate_cache = Mock()
        return line

    def test_init(self, handler, mock_selection_manager, mock_dependencies):
        """Test MouseEventHandler initialization."""
        assert handler.selection_manager is mock_selection_manager
        assert handler._last_click_time == 0.0
        assert handler._last_click_pos is None
        # Verify all callbacks are stored
        for key, value in mock_dependencies.items():
            assert hasattr(handler, f"_{key}")

    def test_handle_mouse_down_left_click_simple(self, handler, mock_selection_manager, mock_log_line):
        """Test simple left mouse click."""
        # Setup
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        
        # Create mouse event
        event = create_mouse_down(x=10, y=5, button=1)
        
        # Execute
        handler.handle_mouse_down(event)
        
        # Verify
        mock_selection_manager.clear_selection.assert_called_once()
        mock_selection_manager.start_selection.assert_called_once_with(5, 9)  # x-1 for gutter
        handler._refresh.assert_called_once()
        
        # Check click tracking
        assert handler._last_click_time > 0
        assert handler._last_click_pos == (10, 5)

    def test_handle_mouse_down_right_click(self, handler, mock_selection_manager):
        """Test right mouse click for copy."""
        event = create_mouse_down(x=10, y=5, button=3)
        
        handler.handle_mouse_down(event)
        
        handler._action_copy_selection.assert_called_once()
        mock_selection_manager.clear_selection.assert_not_called()

    def test_handle_mouse_down_double_click(self, handler, mock_selection_manager, mock_log_line):
        """Test double-click detection and JSON/XML expansion."""
        # Setup for double click
        mock_log_line.has_json = True
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        # First click
        event1 = create_mouse_down(x=10, y=5, button=1)
        handler.handle_mouse_down(event1)
        
        # Simulate time passing (but within threshold)
        with patch("time.time", return_value=handler._last_click_time + 0.3):
            # Second click (double-click)
            event2 = create_mouse_down(x=11, y=5, button=1)  # Close to first position
            handler.handle_mouse_down(event2)
        
        # Verify double-click handling
        mock_log_line.ensure_parsed.assert_called_once()
        assert mock_log_line.is_expanded is True
        mock_log_line.invalidate_cache.assert_called_once()
        handler._clear_line_cache.assert_called_once()
        handler._invalidate_virtual_size_immediate.assert_called_once()
        
        # Should not start selection on double-click
        assert mock_selection_manager.start_selection.call_count == 1  # Only from first click

    def test_handle_mouse_down_double_click_timeout(self, handler, mock_selection_manager, mock_log_line):
        """Test that double-click doesn't trigger if too much time passes."""
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        # First click
        event1 = create_mouse_down(x=10, y=5, button=1)
        handler.handle_mouse_down(event1)
        
        # Simulate too much time passing
        with patch("time.time", return_value=handler._last_click_time + 0.6):
            # Second click (not a double-click)
            event2 = create_mouse_down(x=10, y=5, button=1)
            handler.handle_mouse_down(event2)
        
        # Should start new selection, not expand
        assert mock_selection_manager.start_selection.call_count == 2
        assert not mock_log_line.is_expanded

    def test_handle_mouse_down_with_json_emoji(self, handler, mock_selection_manager, mock_log_line):
        """Test mouse click adjustment for JSON emoji."""
        # Setup log line with JSON
        mock_log_line.has_json = True
        mock_log_line.json_start_pos = 10
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        # Mock display position conversion
        handler._char_index_to_display_x = Mock(return_value=10)
        handler._display_x_to_char_index = Mock(return_value=15)
        
        # Click after emoji position
        event = create_mouse_down(x=20, y=5, button=1)
        handler.handle_mouse_down(event)
        
        # Verify adjustment was applied
        # display_x should be adjusted: 20 + 0 - 1 - 1 = 18
        handler._display_x_to_char_index.assert_called_with(mock_log_line.raw_text, 18)

    def test_handle_mouse_down_with_xml_emoji(self, handler, mock_selection_manager, mock_log_line):
        """Test mouse click adjustment for XML emoji."""
        # Setup log line with XML
        mock_log_line.has_xml = True
        mock_log_line.xml_start_pos = 8
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        # Mock display position conversion
        handler._char_index_to_display_x = Mock(return_value=8)
        handler._display_x_to_char_index = Mock(return_value=12)
        
        # Click after emoji position
        event = create_mouse_down(x=15, y=5, button=1)
        handler.handle_mouse_down(event)
        
        # Verify adjustment was applied
        handler._display_x_to_char_index.assert_called_with(mock_log_line.raw_text, 13)

    def test_handle_mouse_down_expanded_json_line(self, handler, mock_selection_manager, mock_log_line):
        """Test mouse click on expanded JSON sub-line."""
        # Setup expanded JSON
        mock_log_line.is_expanded = True
        mock_log_line.json_data = {"key": "value", "number": 42}
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 2))  # Click on 3rd line of JSON
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        event = create_mouse_down(x=10, y=5, button=1)
        handler.handle_mouse_down(event)
        
        # Should handle JSON line selection
        mock_selection_manager.start_selection.assert_called_once()

    def test_handle_mouse_down_expanded_xml_line(self, handler, mock_selection_manager, mock_log_line):
        """Test mouse click on expanded XML sub-line."""
        # Setup expanded XML
        mock_log_line.is_expanded = True
        mock_log_line.xml_data = "<root><child>data</child></root>"
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 1))  # Click on 2nd line of XML
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        # Mock XML formatter
        with patch("DockTUI.services.log.xml_formatter.XMLFormatter") as mock_xml:
            mock_segments = [
                [Segment("<root>")],
                [Segment("  <child>data</child>")],
                [Segment("</root>")],
            ]
            mock_xml.format_xml_pretty.return_value = mock_segments
            
            event = create_mouse_down(x=10, y=5, button=1)
            handler.handle_mouse_down(event)
            
            mock_selection_manager.start_selection.assert_called_once()

    def test_handle_mouse_down_no_line_at_position(self, handler, mock_selection_manager):
        """Test mouse click where no line exists."""
        handler._get_line_at_virtual_y = Mock(return_value=None)
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        event = create_mouse_down(x=10, y=5, button=1)
        handler.handle_mouse_down(event)
        
        # Should use fallback calculation
        mock_selection_manager.start_selection.assert_called_once_with(5, 9)

    def test_handle_mouse_move_not_selecting(self, handler, mock_selection_manager):
        """Test mouse move when not selecting."""
        mock_selection_manager.is_selecting = False
        
        event = create_mouse_move(x=10, y=5)
        handler.handle_mouse_move(event)
        
        # Should not update selection
        mock_selection_manager.update_selection_end.assert_not_called()
        handler._refresh.assert_not_called()

    def test_handle_mouse_move_while_selecting(self, handler, mock_selection_manager, mock_log_line):
        """Test mouse move during selection (dragging)."""
        mock_selection_manager.is_selecting = True
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        handler._display_x_to_char_index = Mock(return_value=15)
        
        event = create_mouse_move(x=20, y=10)
        handler.handle_mouse_move(event)
        
        mock_selection_manager.update_selection_end.assert_called_once_with(10, 15)
        handler._refresh.assert_called_once()

    def test_handle_mouse_move_with_emoji_adjustment(self, handler, mock_selection_manager, mock_log_line):
        """Test mouse move with emoji position adjustment."""
        mock_selection_manager.is_selecting = True
        mock_log_line.has_json = True
        mock_log_line.json_start_pos = 5
        
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        handler._char_index_to_display_x = Mock(return_value=5)
        handler._display_x_to_char_index = Mock(return_value=10)
        
        event = create_mouse_move(x=15, y=5)
        handler.handle_mouse_move(event)
        
        # Verify emoji adjustment was applied
        handler._display_x_to_char_index.assert_called_with(mock_log_line.raw_text, 13)

    def test_handle_mouse_move_no_line_fallback(self, handler, mock_selection_manager):
        """Test mouse move fallback when no line found."""
        mock_selection_manager.is_selecting = True
        handler._get_line_at_virtual_y = Mock(return_value=None)
        handler._get_scroll_offset = Mock(return_value=Offset(5, 10))
        
        event = create_mouse_move(x=20, y=15)
        handler.handle_mouse_move(event)
        
        # Should use simple calculation: x + scroll_x - 1
        mock_selection_manager.update_selection_end.assert_called_once_with(25, 24)

    def test_handle_mouse_up(self, handler, mock_selection_manager):
        """Test mouse up event."""
        mock_selection_manager.is_selecting = True
        
        event = create_mouse_up(x=10, y=5, button=1)
        handler.handle_mouse_up(event)
        
        mock_selection_manager.finish_selection.assert_called_once()

    def test_handle_mouse_up_not_selecting(self, handler, mock_selection_manager):
        """Test mouse up when not selecting."""
        mock_selection_manager.is_selecting = False
        
        event = create_mouse_up(x=10, y=5, button=1)
        handler.handle_mouse_up(event)
        
        mock_selection_manager.finish_selection.assert_not_called()

    def test_handle_mouse_up_wrong_button(self, handler, mock_selection_manager):
        """Test mouse up with non-left button."""
        mock_selection_manager.is_selecting = True
        
        event = create_mouse_up(x=10, y=5, button=2)
        handler.handle_mouse_up(event)
        
        mock_selection_manager.finish_selection.assert_not_called()

    def test_handle_double_click_expand_json(self, handler, mock_log_line):
        """Test double-click expanding JSON."""
        mock_log_line.has_json = True
        mock_log_line.is_expanded = False
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        handler._handle_double_click(10, 5)
        
        mock_log_line.ensure_parsed.assert_called_once()
        assert mock_log_line.is_expanded is True
        mock_log_line.invalidate_cache.assert_called_once()
        handler._clear_line_cache.assert_called_once()
        handler._invalidate_virtual_size_immediate.assert_called_once()
        handler._refresh.assert_called_once()

    def test_handle_double_click_collapse_json(self, handler, mock_log_line):
        """Test double-click collapsing JSON."""
        mock_log_line.has_json = True
        mock_log_line.is_expanded = True
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 2))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        handler._handle_double_click(10, 5)
        
        assert mock_log_line.is_expanded is False

    def test_handle_double_click_no_json_or_xml(self, handler, mock_log_line):
        """Test double-click on line without JSON/XML."""
        mock_log_line.has_json = False
        mock_log_line.has_xml = False
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        handler._handle_double_click(10, 5)
        
        # Should not toggle expansion
        handler._clear_line_cache.assert_not_called()
        handler._invalidate_virtual_size_immediate.assert_not_called()

    def test_coords_to_position_simple(self, handler, mock_log_line):
        """Test coordinate to position conversion."""
        handler._get_scroll_offset = Mock(return_value=Offset(5, 10))
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_visible_lines = Mock(return_value=[mock_log_line])
        
        result = handler.coords_to_position(15, 20)
        
        assert result == (0, 20)  # line_idx=0, char_pos=min(virtual_x, text_length)

    def test_coords_to_position_expanded_json(self, handler, mock_log_line):
        """Test coordinate conversion for expanded JSON."""
        mock_log_line.is_expanded = True
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 2))  # Sub-line
        handler._get_visible_lines = Mock(return_value=[mock_log_line])
        
        result = handler.coords_to_position(10, 5)
        
        assert result == (0, 10)  # Maps to parent line

    def test_coords_to_position_not_found(self, handler):
        """Test coordinate conversion when line not found."""
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        handler._get_line_at_virtual_y = Mock(return_value=None)
        
        result = handler.coords_to_position(10, 5)
        
        assert result is None

    def test_coords_to_position_line_not_visible(self, handler, mock_log_line):
        """Test coordinate conversion when line not in visible list."""
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_visible_lines = Mock(return_value=[])  # Empty visible lines
        
        result = handler.coords_to_position(10, 5)
        
        assert result is None

    def test_display_x_to_char_index_simple(self, handler):
        """Test display position to character index conversion."""
        text = "Hello, World!"
        
        # Test various positions
        assert handler._display_x_to_char_index(text, 0) == 0
        assert handler._display_x_to_char_index(text, 5) == 5
        assert handler._display_x_to_char_index(text, 13) == 13  # End of string
        assert handler._display_x_to_char_index(text, 20) == 13  # Beyond string

    def test_display_x_to_char_index_unicode(self, handler):
        """Test display position conversion with unicode characters."""
        # Mock cell_len to return 2 for emoji, 1 for regular chars
        with patch("DockTUI.ui.widgets.mouse_event_handler.cell_len") as mock_cell_len:
            def cell_len_side_effect(char):
                return 2 if char == "😀" else 1
            
            mock_cell_len.side_effect = cell_len_side_effect
            
            text = "Hello😀World"
            
            # Before emoji
            assert handler._display_x_to_char_index(text, 5) == 5
            # At emoji start (click on first half of emoji)
            assert handler._display_x_to_char_index(text, 6) == 6  # Returns the emoji position
            # At emoji end (click on second half of emoji)
            assert handler._display_x_to_char_index(text, 7) == 6  # Still returns emoji position
            # After emoji
            assert handler._display_x_to_char_index(text, 8) == 7

    def test_display_x_to_char_index_negative(self, handler):
        """Test display position conversion with negative position."""
        text = "Test"
        assert handler._display_x_to_char_index(text, -5) == 0

    def test_char_index_to_display_x_simple(self, handler):
        """Test character index to display position conversion."""
        text = "Hello, World!"
        
        assert handler._char_index_to_display_x(text, 0) == 0
        assert handler._char_index_to_display_x(text, 5) == 5
        assert handler._char_index_to_display_x(text, 13) == 13

    def test_char_index_to_display_x_unicode(self, handler):
        """Test character index to display conversion with unicode."""
        with patch("DockTUI.ui.widgets.mouse_event_handler.cell_len") as mock_cell_len:
            def cell_len_side_effect(char):
                return 2 if char == "😀" else 1
            
            mock_cell_len.side_effect = cell_len_side_effect
            
            text = "Hello😀World"
            
            # Before emoji
            assert handler._char_index_to_display_x(text, 5) == 5
            # At emoji
            assert handler._char_index_to_display_x(text, 6) == 7  # 5 + 2 for emoji
            # After emoji
            assert handler._char_index_to_display_x(text, 7) == 8

    def test_char_index_to_display_x_negative(self, handler):
        """Test character index to display conversion with negative index."""
        text = "Test"
        assert handler._char_index_to_display_x(text, -1) == 0

    def test_triple_click_prevention(self, handler, mock_selection_manager, mock_log_line):
        """Test that triple-click doesn't trigger double-click."""
        mock_log_line.has_json = True
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        # First click
        event1 = create_mouse_down(x=10, y=5, button=1)
        handler.handle_mouse_down(event1)
        first_click_time = handler._last_click_time
        
        # Second click (double-click)
        with patch("time.time", return_value=first_click_time + 0.2):
            event2 = create_mouse_down(x=10, y=5, button=1)
            handler.handle_mouse_down(event2)
        
        # After double-click, click tracking should be reset
        assert handler._last_click_time == 0
        assert handler._last_click_pos is None
        
        # Third click should be treated as new single click
        with patch("time.time", return_value=first_click_time + 0.4):
            event3 = create_mouse_down(x=10, y=5, button=1)
            handler.handle_mouse_down(event3)
        
        # Should start new selection, not another double-click
        assert mock_selection_manager.start_selection.call_count == 2  # First and third click

    def test_double_click_position_tolerance(self, handler, mock_selection_manager, mock_log_line):
        """Test double-click position tolerance."""
        handler._get_line_at_virtual_y = Mock(return_value=(mock_log_line, 0))
        handler._get_scroll_offset = Mock(return_value=Offset(0, 0))
        
        # Test clicks at various distances from the original click at (10, 5)
        test_cases = [
            (10, 5, True),   # Same position
            (11, 5, True),   # 1 cell away horizontally
            (12, 5, True),   # 2 cells away horizontally  
            (13, 5, False),  # 3 cells away horizontally (too far)
            (10, 6, True),   # 1 cell away vertically
            (10, 7, False),  # 2 cells away vertically (too far)
            (11, 6, True),   # Diagonal within tolerance
        ]
        
        for x, y, should_double_click in test_cases:
            # Reset state completely for each test
            mock_log_line.has_json = True
            mock_log_line.is_expanded = False
            handler._last_click_time = 0
            handler._last_click_pos = None
            
            # First click at (10, 5)
            with patch("time.time", return_value=1000):
                event1 = create_mouse_down(x=10, y=5, button=1)
                handler.handle_mouse_down(event1)
            
            # Verify first click was registered
            assert handler._last_click_pos == (10, 5)
            assert handler._last_click_time == 1000
            
            # Second click at test position
            with patch("time.time", return_value=1000.3):
                event2 = create_mouse_down(x=x, y=y, button=1)
                handler.handle_mouse_down(event2)
                
                if should_double_click:
                    assert mock_log_line.is_expanded is True, f"Expected double-click at ({x}, {y}) from (10, 5)"
                else:
                    assert mock_log_line.is_expanded is False, f"Should not double-click at ({x}, {y}) from (10, 5)"

    def test_complex_selection_scenario(self, handler, mock_selection_manager):
        """Test complex selection scenario with scrolling."""
        # Setup scroll offset
        handler._get_scroll_offset = Mock(return_value=Offset(10, 20))
        
        # Create different log lines
        normal_line = Mock(spec=LogLine)
        normal_line.raw_text = "Normal log line"
        normal_line.is_expanded = False
        normal_line.has_json = False
        normal_line.has_xml = False
        
        json_line = Mock(spec=LogLine)
        json_line.raw_text = "JSON: {}"
        json_line.is_expanded = True
        json_line.has_json = True
        json_line.json_data = {"key": "value"}
        
        # Simulate selection across different line types
        handler._get_line_at_virtual_y = Mock(side_effect=[
            (normal_line, 0),  # Start selection
            (json_line, 2),    # Move to JSON sub-line
        ])
        
        # Start selection
        event1 = create_mouse_down(x=5, y=10, button=1)
        handler.handle_mouse_down(event1)
        
        # Verify scroll offset applied
        virtual_y = 10 + 20  # y + scroll_y
        handler._get_line_at_virtual_y.assert_called_with(30)
        
        # Continue selection
        mock_selection_manager.is_selecting = True
        event2 = create_mouse_move(x=15, y=20)
        handler.handle_mouse_move(event2)
        
        # Complete selection
        event3 = create_mouse_up(x=15, y=20, button=1)
        handler.handle_mouse_up(event3)
        
        mock_selection_manager.finish_selection.assert_called_once()