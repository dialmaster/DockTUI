"""Tests for the LogPane widget."""

import asyncio
from queue import Queue, Empty
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, PropertyMock

import pytest
from textual.document._document import Selection

from DockTUI.ui.viewers.log_pane import LogPane


class MockLogTextArea:
    """Mock LogTextArea for testing."""
    def __init__(self):
        self.text = ""
        self.scroll_y = 0
        self.is_selecting = False
        self.selection = Mock()
        self.selection.is_empty = True
        self.selection.start = (0, 0)
        self.selection.end = (0, 0)
        self.document = Mock()
        self.document.end = (0, 0)
        self.display = True  # Add display attribute
        
    def insert(self, text, location=None, maintain_selection_offset=False):
        """Mock insert method."""
        self.text += text
        # Update document end location
        lines = self.text.count('\n')
        last_line_len = len(self.text.split('\n')[-1]) if self.text else 0
        self.document.end = (lines, last_line_len)
        
    def move_cursor(self, location):
        """Mock move cursor method."""
        pass
        
    def scroll_cursor_visible(self):
        """Mock scroll cursor visible method."""
        pass


class TestLogPane:
    """Test cases for the LogPane widget."""

    @pytest.fixture
    def log_pane(self):
        """Create a LogPane instance with mocked dependencies."""
        # Mock the parent class initialization
        with patch('textual.containers.Vertical.__init__', return_value=None):
            # Create instance without calling parent __init__
            pane = object.__new__(LogPane)
            
            # Initialize attributes before calling LogPane.__init__
            pane.auto_follow = True
            pane.log_streamer = Mock()
            pane.log_streamer.get_queue.return_value = Queue()
            
            # Mock methods
            pane.mount = Mock()
            pane.refresh = Mock()
            pane.query = Mock()
            pane.query_one = Mock()
            pane.set_timer = Mock()
            pane.remove_children = Mock()
            pane._update_display = Mock()
            
            # Initialize other attributes from LogPane
            pane._log_lines = []
            pane._filtered_lines = []
            pane._search_pattern = None
            pane._mark_positions = []
            pane._is_processing = False
            pane._container_id = None
            pane._container_name = None
            pane._container_status = None
            
            # Call LogPane.__init__ to properly initialize the instance 
            # This will define all the methods
            LogPane.__init__(pane)
            
            # Set up log_display after init since it's normally created in compose()
            pane.log_display = MockLogTextArea()
            
            # Replace log_filter with a mock after init
            pane.log_filter = Mock()
            pane.log_filter.add_lines = Mock()
            pane.log_filter.update_mark_positions = Mock()
            
            # Mock app property for notifications
            mock_app = Mock()
            mock_app.notify = Mock()
            type(pane).app = PropertyMock(return_value=mock_app)
            
            yield pane

    def test_process_log_queue_skips_when_selecting(self, log_pane):
        """Test that log processing is skipped when text is being selected."""
        # Set up log display to indicate selection is active
        log_pane.log_display.is_selecting = True
        
        # Add a log message to the queue (in the expected format)
        log_queue = log_pane.log_streamer.get_queue()
        log_queue.put(("log", "Test log message"))
        
        # Call _process_log_queue
        log_pane._process_log_queue()
        
        # The log should not be processed (text should remain empty)
        assert log_pane.log_display.text == ""
        
        # The message should still be in the queue
        assert not log_queue.empty()

    def test_process_log_queue_processes_when_not_selecting(self, log_pane):
        """Test that log processing works normally when not selecting."""
        # Mock _append_log_line
        log_pane._append_log_line = Mock()
        
        # Set up log display to indicate no selection
        log_pane.log_display.is_selecting = False
        
        # Add log messages to the queue (in the expected format)
        log_queue = log_pane.log_streamer.get_queue()
        log_queue.put(("log", "Test log message 1"))  # Old format
        log_queue.put((0, "log", "Test log message 2"))  # New format with session_id
        
        # Call _process_log_queue
        log_pane._process_log_queue()
        
        # The logs should be processed
        assert log_pane._append_log_line.call_count == 2
        log_pane._append_log_line.assert_any_call("Test log message 1")
        log_pane._append_log_line.assert_any_call("Test log message 2")

    def test_process_log_queue_without_log_display(self, log_pane):
        """Test that log processing handles missing log display gracefully."""
        # Remove log display
        log_pane.log_display = None
        
        # Add a log message to the queue (in the expected format)
        log_queue = log_pane.log_streamer.get_queue()
        log_queue.put(("log", "Test log message"))
        
        # Call _process_log_queue - should not raise exception
        log_pane._process_log_queue()

    def test_process_log_queue_without_is_selecting_attr(self, log_pane):
        """Test that log processing handles missing is_selecting attribute."""
        # Mock _append_log_line
        log_pane._append_log_line = Mock()
        
        # Remove is_selecting attribute
        delattr(log_pane.log_display, 'is_selecting')
        
        # Add a log message to the queue (in the expected format)
        log_queue = log_pane.log_streamer.get_queue()
        log_queue.put(("log", "Test log message"))
        
        # Call _process_log_queue - should process normally
        log_pane._process_log_queue()
        
        # The log should be processed
        log_pane._append_log_line.assert_called_once_with("Test log message")

    def test_append_log_line_preserves_selection(self, log_pane):
        """Test that appending log lines preserves text selection."""
        # Set up initial text and selection
        log_pane.log_display.text = "Initial text\n"
        log_pane.log_display.selection.is_empty = False
        log_pane.log_display.selection.start = (0, 0)
        log_pane.log_display.selection.end = (0, 7)  # Select "Initial"
        
        # Mock Selection class
        with patch('textual.document._document.Selection') as MockSelection:
            # Configure mock to return a new Selection instance
            mock_selection = Mock()
            MockSelection.return_value = mock_selection
            
            # Call _append_log_line
            log_pane._append_log_line("New log line")
            
            # Should have created a new selection with saved coordinates
            MockSelection.assert_called_once_with(start=(0, 0), end=(0, 7))
            
            # Should have restored the selection
            assert log_pane.log_display.selection == mock_selection

    def test_append_log_line_no_selection(self, log_pane):
        """Test that appending log lines works without selection."""
        # Set up with no selection
        log_pane.log_display.selection.is_empty = True
        log_pane.auto_follow = True
        
        # Mock move_cursor and scroll_cursor_visible
        log_pane.log_display.move_cursor = Mock()
        log_pane.log_display.scroll_cursor_visible = Mock()
        
        # Call _append_log_line
        log_pane._append_log_line("New log line")
        
        # Should append the text
        assert "New log line\n" in log_pane.log_display.text
        
        # Should move cursor and scroll when auto-following
        log_pane.log_display.move_cursor.assert_called_once()
        log_pane.log_display.scroll_cursor_visible.assert_called_once()

    def test_append_log_line_with_selection_auto_follow(self, log_pane):
        """Test that cursor doesn't move when there's a selection during auto-follow."""
        # Set up with selection and auto-follow
        log_pane.log_display.selection.is_empty = False
        log_pane.auto_follow = True
        
        # Mock move_cursor and scroll_cursor_visible
        log_pane.log_display.move_cursor = Mock()
        log_pane.log_display.scroll_cursor_visible = Mock()
        
        # Call _append_log_line
        log_pane._append_log_line("New log line")
        
        # Should NOT move cursor when there's a selection
        log_pane.log_display.move_cursor.assert_not_called()
        log_pane.log_display.scroll_cursor_visible.assert_not_called()

    def test_append_log_line_no_auto_follow(self, log_pane):
        """Test that scroll position is preserved when not auto-following."""
        # Set up without auto-follow
        log_pane.auto_follow = False
        log_pane.log_display.scroll_y = 50
        
        # Call _append_log_line
        log_pane._append_log_line("New log line")
        
        # Should preserve scroll position
        assert log_pane.log_display.scroll_y == 50

    def test_append_log_line_selection_restoration_failure(self, log_pane):
        """Test graceful handling of selection restoration failure."""
        # Set up with selection
        log_pane.log_display.selection.is_empty = False
        log_pane.log_display.selection.start = (0, 0)
        log_pane.log_display.selection.end = (0, 7)
        
        # Save the original class to restore later
        original_class = log_pane.log_display.__class__
        
        # Create a temporary subclass that raises on selection assignment
        class TempLogDisplay(MockLogTextArea):
            _selection = None
            
            @property
            def selection(self):
                return self._selection or Mock(is_empty=False, start=(0, 0), end=(0, 7))
            
            @selection.setter
            def selection(self, value):
                if hasattr(self, '_selection') and self._selection is not None:
                    # Raise when trying to restore selection
                    raise Exception("Selection error")
                self._selection = value
        
        # Temporarily change the instance's class
        log_pane.log_display.__class__ = TempLogDisplay
        
        try:
            # Call _append_log_line - should not raise despite the error
            log_pane._append_log_line("New log line")
            
            # Should still append the text
            assert "New log line\n" in log_pane.log_display.text
        finally:
            # Restore the original class
            log_pane.log_display.__class__ = original_class

    def test_mark_log_position_preserves_selection(self, log_pane):
        """Test that marking log position preserves selection."""
        # Mock dependencies
        log_pane._append_log_line = Mock()
        
        # Ensure log_display.display is True
        assert log_pane.log_display.display == True
        
        # Debug - check log_filter
        assert hasattr(log_pane, 'log_filter')
        assert log_pane.log_filter is not None
        
        # Mock datetime
        from unittest.mock import patch
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2024-01-01 12:00:00"
            
            # Call _mark_position
            log_pane._mark_position()
            
            # Should append empty lines and marker
            assert log_pane._append_log_line.call_count == 5
            calls = log_pane._append_log_line.call_args_list
            assert calls[0][0][0] == ""
            assert calls[1][0][0] == ""
            assert "MARKED 2024-01-01 12:00:00" in calls[2][0][0]
            assert calls[3][0][0] == ""
            assert calls[4][0][0] == ""
            
            # Should add lines to log filter
            log_pane.log_filter.add_lines.assert_called_once_with(
                ["", "", "------ MARKED 2024-01-01 12:00:00 ------", "", ""]
            )
            
            # Should show notification
            log_pane.app.notify.assert_called_once_with(
                "Position marked at 2024-01-01 12:00:00",
                severity="information",
                timeout=2
            )

    def test_mark_log_position_with_filter(self, log_pane):
        """Test marking position adds lines to filter."""
        # Set up with filter
        log_pane._append_log_line = Mock()
        
        # Ensure log_display.display is True 
        assert log_pane.log_display.display == True
        
        # Mock datetime
        from unittest.mock import patch
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2024-01-01 12:00:00"
            
            # Call _mark_position
            log_pane._mark_position()
            
            # Should add lines to log filter
            log_pane.log_filter.add_lines.assert_called_once_with(
                ["", "", "------ MARKED 2024-01-01 12:00:00 ------", "", ""]
            )
            
            # Should append the marker lines
            assert log_pane._append_log_line.call_count == 5

    def test_process_log_queue_empty_queue(self, log_pane):
        """Test processing with empty queue."""
        # Set up empty queue
        log_queue = log_pane.log_streamer.get_queue()
        
        # Mock _append_log_line
        log_pane._append_log_line = Mock()
        
        # Call _process_log_queue
        log_pane._process_log_queue()
        
        # Should not append any lines
        log_pane._append_log_line.assert_not_called()

    def test_process_log_queue_exception(self, log_pane):
        """Test handling of queue.get exception."""
        # Make queue.get raise Empty exception
        log_queue = log_pane.log_streamer.get_queue()
        log_queue.get = Mock(side_effect=Empty)
        
        # Mock _append_log_line
        log_pane._append_log_line = Mock()
        
        # Call _process_log_queue - should not raise
        log_pane._process_log_queue()
        
        # Should not append any lines
        log_pane._append_log_line.assert_not_called()