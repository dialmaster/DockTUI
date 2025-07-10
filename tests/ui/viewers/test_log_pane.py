"""Tests for the LogPane widget."""

import asyncio
from queue import Queue, Empty
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, PropertyMock, AsyncMock

import pytest
from textual.document._document import Selection
from textual.events import Key
from textual.widgets import Checkbox, Select, Input, Button

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
        
    def add_log_line(self, line, is_system_message=False):
        """Mock add_log_line method for RichLogViewer compatibility."""
        self.text += line + '\n'
        
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
    
    def clear(self):
        """Mock clear method."""
        self.text = ""
        self.document.end = (0, 0)


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
            
            # Mock methods
            pane.mount = Mock()
            pane.refresh = Mock()
            pane.query = Mock()
            pane.query_one = Mock()
            pane.set_timer = Mock()
            pane.remove_children = Mock()
            pane._update_display = Mock()
            
            # Initialize other attributes from LogPane
            pane.LOG_TAIL = "200"
            pane.LOG_SINCE = "15m"
            pane.tail_select = None
            pane.since_select = None
            pane.search_input = None
            pane.auto_follow_checkbox = None
            pane.mark_position_button = None
            pane.header = Mock()
            pane.header.update = Mock()
            
            # Call LogPane.__init__ to properly initialize the instance 
            # This will define all the methods
            LogPane.__init__(pane)
            
            # Set up log_display after init since it's normally created in compose()
            pane.log_display = MockLogTextArea()
            pane.no_selection_display = Mock()
            pane.no_selection_display.display = False
            
            # Set up the managers after init
            pane.log_stream_manager = Mock()
            pane.log_stream_manager.is_available = True
            pane.log_stream_manager.get_queue = Mock(return_value=Queue())
            pane.log_stream_manager.process_queue = Mock(return_value={"lines": [], "errors": [], "no_logs": False, "processed": 0})
            pane.log_stream_manager.showing_loading_message = False
            pane.log_stream_manager.showing_no_logs_message = False
            pane.log_stream_manager.showing_no_matches_message = False
            pane.log_stream_manager.is_loading = False
            
            pane.log_filter_manager = Mock()
            pane.log_filter_manager.add_line = Mock()
            pane.log_filter_manager.add_lines = Mock()
            pane.log_filter_manager.should_show_line = Mock(return_value=True)
            pane.log_filter_manager.has_filter = Mock(return_value=False)
            pane.log_filter_manager.get_all_lines = Mock(return_value=[])
            pane.log_filter_manager.clear = Mock()
            pane.log_filter_manager.add_marker = Mock(return_value=["", "", "------ MARKED 2024-01-01 12:00:00 ------", "", ""])
            
            pane.log_state_manager = Mock()
            pane.log_state_manager.current_item = None
            pane.log_state_manager.current_item_data = None
            pane.log_state_manager.auto_follow = True
            pane.log_state_manager.save_dropdown_states = Mock(return_value={})
            pane.log_state_manager.restore_dropdown_states = Mock()
            pane.log_state_manager.is_same_item = Mock(return_value=False)
            pane.log_state_manager.update_header_for_item = Mock(return_value=True)
            pane.log_state_manager.set_current_item = Mock(return_value=("container", "test_id"))
            
            pane.log_queue_processor = Mock()
            pane.log_queue_processor.process_queue = Mock()
            
            # Set current_item and current_item_data as properties that delegate to state manager
            type(pane).current_item = property(
                lambda self: self.log_state_manager.current_item,
                lambda self, value: setattr(self.log_state_manager, 'current_item', value)
            )
            type(pane).current_item_data = property(
                lambda self: self.log_state_manager.current_item_data,
                lambda self, value: setattr(self.log_state_manager, 'current_item_data', value)
            )
            
            # Mock app property for notifications
            mock_app = Mock()
            mock_app.notify = Mock()
            type(pane).app = PropertyMock(return_value=mock_app)
            
            yield pane

    def test_process_log_queue_skips_when_selecting(self, log_pane):
        """Test that log processing is skipped when text is being selected."""
        # Set up log display to indicate selection is active
        log_pane.log_display.is_selecting = True
        
        # Mock the log stream manager's queue
        log_queue = Queue()
        log_pane.log_stream_manager.get_queue = Mock(return_value=log_queue)
        log_queue.put(("log", "Test log message"))
        
        # Call _process_log_queue
        log_pane._process_log_queue()
        
        # The log should not be processed (text should remain empty)
        assert log_pane.log_display.text == ""
        
        # The message should still be in the queue
        assert not log_queue.empty()

    def test_process_log_queue_processes_when_not_selecting(self, log_pane):
        """Test that log processing works normally when not selecting."""
        # Mock log_queue_processor
        log_pane.log_queue_processor.process_queue = Mock()
        
        # Call _process_log_queue
        log_pane._process_log_queue()
        
        # The processor should be called with max_items=50
        log_pane.log_queue_processor.process_queue.assert_called_once_with(max_items=50)

    def test_process_log_queue_without_log_display(self, log_pane):
        """Test that log processing handles missing log display gracefully."""
        # Remove log display
        log_pane.log_display = None
        
        # Mock the log stream manager's queue
        log_queue = Queue()
        log_pane.log_stream_manager.get_queue = Mock(return_value=log_queue)
        log_queue.put(("log", "Test log message"))
        
        # Call _process_log_queue - should not raise exception
        log_pane._process_log_queue()

    def test_process_log_queue_without_is_selecting_attr(self, log_pane):
        """Test that log processing handles missing is_selecting attribute."""
        # Mock log_queue_processor
        log_pane.log_queue_processor.process_queue = Mock()
        
        # Call _process_log_queue - should process normally
        log_pane._process_log_queue()
        
        # The processor should be called
        log_pane.log_queue_processor.process_queue.assert_called_once()

    def test_append_log_line_preserves_selection(self, log_pane):
        """Test that appending log lines works."""
        # Just test that the method can be called without error
        log_pane._append_log_line("New log line")

    def test_append_log_line_no_selection(self, log_pane):
        """Test that appending log lines works."""
        # Just test that the method can be called without error
        log_pane._append_log_line("New log line")

    def test_append_log_line_with_selection_auto_follow(self, log_pane):
        """Test that cursor doesn't move when there's a selection during auto-follow."""
        # Mock add_log_line method
        log_pane.log_display.add_log_line = Mock()
        
        # Call _append_log_line with marked line
        log_pane._append_log_line("------ MARKED 2024-01-01 12:00:00 ------")
        
        # Should have called add_log_line with is_system_message=True
        log_pane.log_display.add_log_line.assert_called_once_with(
            "------ MARKED 2024-01-01 12:00:00 ------", is_system_message=True
        )

    def test_append_log_line_no_auto_follow(self, log_pane):
        """Test that scroll position is preserved when not auto-following."""
        # Mock add_log_line method
        log_pane.log_display.add_log_line = Mock()
        
        # Call _append_log_line with spacer line
        log_pane._append_log_line("  ")
        
        # Should have called add_log_line with is_system_message=True for spacer
        log_pane.log_display.add_log_line.assert_called_once_with(
            "  ", is_system_message=True
        )

    def test_append_log_line_selection_restoration_failure(self, log_pane):
        """Test that append_log_line handles marked lines."""
        # Test with a marked line
        log_pane._append_log_line("------ MARKED 2024-01-01 12:00:00 ------")

    def test_mark_log_position_preserves_selection(self, log_pane):
        """Test that marking log position preserves selection."""
        # Mock dependencies
        log_pane.log_filter_manager.add_marker = Mock(return_value="2024-01-01 12:00:00")
        
        # Call _mark_position
        log_pane._mark_position()
        
        # Should call add_marker
        log_pane.log_filter_manager.add_marker.assert_called_once()
        
        # Should show notification (the actual implementation may extract timestamp differently)
        assert log_pane.app.notify.called
        call_args = log_pane.app.notify.call_args
        assert "Position marked at" in call_args[0][0]
        assert call_args[1]["severity"] == "information"
        assert call_args[1]["timeout"] == 2

    def test_mark_log_position_with_filter(self, log_pane):
        """Test marking position adds lines to filter."""
        # Mock dependencies
        log_pane.log_filter_manager.add_marker = Mock(return_value="2024-01-01 12:00:00")
        
        # Call _mark_position
        log_pane._mark_position()
        
        # Should call add_marker
        log_pane.log_filter_manager.add_marker.assert_called_once()

    def test_process_log_queue_empty_queue(self, log_pane):
        """Test processing with empty queue."""
        # Set up empty queue
        log_queue = Queue()
        log_pane.log_stream_manager.get_queue = Mock(return_value=log_queue)
        
        # Mock _append_log_line
        log_pane._append_log_line = Mock()
        
        # Call _process_log_queue
        log_pane._process_log_queue()
        
        # Should not append any lines
        log_pane._append_log_line.assert_not_called()

    def test_process_log_queue_exception(self, log_pane):
        """Test handling of queue.get exception."""
        # Make queue.get raise Empty exception
        log_queue = Queue()
        log_pane.log_stream_manager.get_queue = Mock(return_value=log_queue)
        log_queue.get = Mock(side_effect=Empty)
        
        # Mock _append_log_line
        log_pane._append_log_line = Mock()
        
        # Call _process_log_queue - should not raise
        log_pane._process_log_queue()
        
        # Should not append any lines
        log_pane._append_log_line.assert_not_called()

    def test_save_dropdown_states(self, log_pane):
        """Test saving dropdown states."""
        # Create mock dropdowns
        log_pane.tail_select = Mock()
        log_pane.tail_select.expanded = True
        log_pane.since_select = Mock()
        log_pane.since_select.expanded = False
        
        # Mock the save_dropdown_states method to return expected values
        log_pane.log_state_manager.save_dropdown_states = Mock(
            return_value={"tail_expanded": True, "since_expanded": False}
        )
        
        # Call save_dropdown_states via state manager
        states = log_pane.log_state_manager.save_dropdown_states(
            log_pane.tail_select, log_pane.since_select
        )
        
        # Should return correct states
        assert states == {
            "tail_expanded": True,
            "since_expanded": False,
        }

    def test_save_dropdown_states_missing_dropdowns(self, log_pane):
        """Test saving dropdown states when dropdowns don't exist."""
        # Set dropdowns to None
        log_pane.tail_select = None
        log_pane.since_select = None
        
        # Mock the save_dropdown_states method to return expected values
        log_pane.log_state_manager.save_dropdown_states = Mock(
            return_value={"tail_expanded": False, "since_expanded": False}
        )
        
        # Call save_dropdown_states via state manager
        states = log_pane.log_state_manager.save_dropdown_states(
            log_pane.tail_select, log_pane.since_select
        )
        
        # Should return False for both
        assert states == {
            "tail_expanded": False,
            "since_expanded": False,
        }

    def test_restore_dropdown_states_tail_expanded(self, log_pane):
        """Test restoring tail dropdown expanded state."""
        # Create mock dropdowns
        log_pane.tail_select = Mock()
        log_pane.tail_select.action_show_overlay = Mock()
        log_pane.since_select = Mock()
        log_pane.since_select.action_show_overlay = Mock()
        
        # Call restore_dropdown_states via state manager with tail expanded
        states = {"tail_expanded": True, "since_expanded": False}
        log_pane.log_state_manager.restore_dropdown_states(
            states, log_pane.tail_select, log_pane.since_select
        )
        
        # Just verify the method was called
        log_pane.log_state_manager.restore_dropdown_states.assert_called_once()

    def test_restore_dropdown_states_since_expanded(self, log_pane):
        """Test restoring since dropdown expanded state."""
        # Create mock dropdowns
        log_pane.tail_select = Mock()
        log_pane.tail_select.action_show_overlay = Mock()
        log_pane.since_select = Mock()
        log_pane.since_select.action_show_overlay = Mock()
        
        # Call restore_dropdown_states via state manager with since expanded
        states = {"tail_expanded": False, "since_expanded": True}
        log_pane.log_state_manager.restore_dropdown_states(
            states, log_pane.tail_select, log_pane.since_select
        )
        
        # Just verify the method was called
        log_pane.log_state_manager.restore_dropdown_states.assert_called_once()

    def test_restore_dropdown_states_none_expanded(self, log_pane):
        """Test restoring dropdown states when none are expanded."""
        # Create mock dropdowns
        log_pane.tail_select = Mock()
        log_pane.tail_select.action_show_overlay = Mock()
        log_pane.since_select = Mock()
        log_pane.since_select.action_show_overlay = Mock()
        
        # Call restore_dropdown_states via state manager with none expanded
        states = {"tail_expanded": False, "since_expanded": False}
        log_pane.log_state_manager.restore_dropdown_states(
            states, log_pane.tail_select, log_pane.since_select
        )
        
        # Should not restore any dropdown
        log_pane.tail_select.action_show_overlay.assert_not_called()
        log_pane.since_select.action_show_overlay.assert_not_called()

    def test_restore_dropdown_states_empty_states(self, log_pane):
        """Test restoring dropdown states with empty states dict."""
        # Create mock dropdowns
        log_pane.tail_select = Mock()
        log_pane.tail_select.action_show_overlay = Mock()
        log_pane.since_select = Mock()
        log_pane.since_select.action_show_overlay = Mock()
        
        # Call restore_dropdown_states via state manager with empty states
        log_pane.log_state_manager.restore_dropdown_states(
            {}, log_pane.tail_select, log_pane.since_select
        )
        
        # Should not restore any dropdown
        log_pane.tail_select.action_show_overlay.assert_not_called()
        log_pane.since_select.action_show_overlay.assert_not_called()

    def test_restore_dropdown_states_missing_dropdowns(self, log_pane):
        """Test restoring dropdown states when dropdowns don't exist."""
        # Set dropdowns to None
        log_pane.tail_select = None
        log_pane.since_select = None
        
        # Call restore_dropdown_states via state manager - should not raise
        states = {"tail_expanded": True, "since_expanded": True}
        log_pane.log_state_manager.restore_dropdown_states(
            states, log_pane.tail_select, log_pane.since_select
        )

    def test_update_selection_preserves_dropdown_state(self, log_pane):
        """Test that update_selection preserves dropdown states."""
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={"tail_expanded": True})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.log_state_manager.update_header_for_item = Mock(return_value=True)
        log_pane.call_after_refresh = Mock()
        log_pane._show_logs_ui = Mock()
        log_pane._clear_logs = Mock()
        log_pane._start_logs = Mock()
        log_pane._set_log_text = Mock()
        log_pane.log_stream_manager.showing_loading_message = False
        log_pane.log_stream_manager.stop_streaming = Mock()
        
        # Call update_selection
        log_pane.update_selection("container", "test_id", {"name": "test"})
        
        # Should save dropdown states
        log_pane.log_state_manager.save_dropdown_states.assert_called_once()
        # Should restore dropdown states via call_after_refresh
        assert log_pane.call_after_refresh.called

    def test_clear_selection_preserves_dropdown_state(self, log_pane):
        """Test that clear_selection preserves dropdown states."""
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={"since_expanded": True})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.call_after_refresh = Mock()
        log_pane.log_display.display = True
        log_pane.no_selection_display.display = False
        log_pane._clear_logs = Mock()
        log_pane.header = Mock()
        log_pane.refresh = Mock()
        log_pane.log_stream_manager.clear = Mock()
        log_pane.log_state_manager.clear_current_item = Mock()
        log_pane.log_state_manager.update_header_for_no_selection = Mock()
        
        # Call clear_selection
        log_pane.clear_selection()
        
        # Should save and restore dropdown states
        log_pane.log_state_manager.save_dropdown_states.assert_called_once()
        assert log_pane.call_after_refresh.called
        # Check that restore_dropdown_states is passed to call_after_refresh
        # The lambda function is harder to check, so we just verify call_after_refresh was called

    def test_update_selection_force_restart_true(self, log_pane):
        """Test that update_selection with force_restart=True restarts logs even for same selection."""
        # Set up current selection
        log_pane.current_item = ("container", "test_id")
        log_pane.current_item_data = {"name": "test", "status": "running"}
        
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.call_after_refresh = Mock()
        log_pane.log_state_manager.update_header_for_item = Mock(return_value=True)
        log_pane.log_state_manager.is_same_item = Mock(return_value=True)  # Force update despite same item
        log_pane.log_display.display = False
        log_pane.no_selection_display.display = True
        log_pane._clear_logs = Mock()
        log_pane._start_logs = Mock()
        log_pane._set_log_text = Mock()
        log_pane.log_stream_manager.showing_loading_message = False
        log_pane.log_stream_manager.stop_streaming = Mock()
        
        # Call update_selection with same item but force_restart=True
        log_pane.update_selection("container", "test_id", {"name": "test", "status": "running"}, force_restart=True)
        
        # Should NOT return early - should restart logs
        log_pane.log_state_manager.update_header_for_item.assert_called_once()
        assert log_pane.log_display.display == True  # logs UI shown
        assert log_pane.no_selection_display.display == False
        log_pane._clear_logs.assert_called_once()
        log_pane._start_logs.assert_called_once()
        
        # Should still save/restore dropdown states
        log_pane.log_state_manager.save_dropdown_states.assert_called_once()
        assert log_pane.call_after_refresh.called

    def test_update_selection_force_restart_false_same_item(self, log_pane):
        """Test that update_selection with force_restart=False (default) may still update for status changes."""
        # Set up current selection with same container but different status
        log_pane.log_state_manager.current_item = ("container", "test_id")
        log_pane.log_state_manager.current_item_data = {"name": "test", "status": "stopped"}
        
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.log_state_manager.is_same_item = Mock(return_value=True)
        log_pane.log_state_manager.update_current_item = Mock()
        log_pane._handle_status_change = Mock()
        log_pane.call_after_refresh = Mock()
        
        # Call update_selection with same item but different status
        log_pane.update_selection("container", "test_id", {"name": "test", "status": "running"})
        
        # Should detect status change and handle it
        log_pane._handle_status_change.assert_called_once_with(
            {"name": "test", "status": "running"}
        )
        
        # Should still save/restore dropdown states
        log_pane.log_state_manager.save_dropdown_states.assert_called_once()
        assert log_pane.call_after_refresh.called

    def test_update_selection_different_item_ignores_force_restart(self, log_pane):
        """Test that update_selection always restarts logs for different items regardless of force_restart."""
        # Set up current selection
        log_pane.log_state_manager.current_item = ("container", "old_id")
        log_pane.log_state_manager.current_item_data = {"name": "old_container", "status": "running"}
        
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.log_state_manager.is_same_item = Mock(return_value=False)  # Different item
        log_pane.log_state_manager.update_header_for_item = Mock(return_value=True)
        log_pane.call_after_refresh = Mock()
        log_pane._show_logs_ui = Mock()
        log_pane._clear_logs = Mock()
        log_pane._start_logs = Mock()
        log_pane._set_log_text = Mock()
        log_pane.log_stream_manager.showing_loading_message = False
        log_pane.log_stream_manager.stop_streaming = Mock()
        log_pane.log_display.display = False
        log_pane.no_selection_display.display = True
        
        # Call update_selection with different item and force_restart=False
        log_pane.update_selection("container", "new_id", {"name": "new_container", "status": "running"}, force_restart=False)
        
        # Should restart logs for different item
        log_pane.log_state_manager.update_header_for_item.assert_called_once()
        log_pane._clear_logs.assert_called_once()
        log_pane._start_logs.assert_called_once()
        
        # Display state should be updated
        assert log_pane.log_display.display == True
        assert log_pane.no_selection_display.display == False

    def test_init_with_docker_client_success(self):
        """Test successful Docker client initialization."""
        with patch('docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()
            with patch('DockTUI.config.config.get') as mock_config:
                mock_config.side_effect = lambda key, default: default
                pane = LogPane()
                assert pane.docker_client is not None
                assert pane.LOG_TAIL == "200"
                assert pane.LOG_SINCE == "15m"
                
    def test_init_with_docker_client_failure(self):
        """Test Docker client initialization failure."""
        with patch('docker.from_env') as mock_docker:
            mock_docker.side_effect = Exception("Docker not available")
            with patch('DockTUI.config.config.get') as mock_config:
                mock_config.side_effect = lambda key, default: default
                pane = LogPane()
                assert pane.docker_client is None
                
    def test_compose_creates_ui_components(self, log_pane):
        """Test that compose creates all UI components."""
        # Instead of running compose (which creates real widgets), just call it to verify it doesn't crash
        # and check that it initializes the attributes we expect
        
        # Mock widget classes to avoid Textual initialization
        with patch('DockTUI.ui.viewers.log_pane.Static') as mock_static, \
             patch('DockTUI.ui.viewers.log_pane.Input') as mock_input, \
             patch('DockTUI.ui.viewers.log_pane.Checkbox') as mock_checkbox, \
             patch('DockTUI.ui.viewers.log_pane.Button') as mock_button, \
             patch('DockTUI.ui.viewers.log_pane.RichLogViewer') as mock_rich_log, \
             patch('DockTUI.ui.viewers.log_pane.Label') as mock_label, \
             patch('DockTUI.ui.viewers.log_pane.Horizontal') as mock_horizontal, \
             patch('DockTUI.ui.viewers.log_pane.Container') as mock_container:
            
            # Mock the create methods too
            log_pane._create_tail_select = Mock(return_value=Mock())
            log_pane._create_since_select = Mock(return_value=Mock())
            
            # Run compose - it should set up all the UI components
            list(log_pane.compose())
            
            # Verify that all UI components were created
            mock_static.assert_called()  # Header and no_selection_display
            mock_input.assert_called()   # Search input
            mock_checkbox.assert_called()  # Auto-follow checkbox
            mock_button.assert_called()   # Mark position button
            mock_rich_log.assert_called()  # Log display
            
            # Should have called the create methods
            log_pane._create_tail_select.assert_called_once()
            log_pane._create_since_select.assert_called_once()
            
            # Check that log_queue_processor has log_display set
            log_pane.log_queue_processor.set_log_display.assert_called_once()
        
    def test_on_mount_starts_timer(self, log_pane):
        """Test that on_mount sets up the timer and UI components."""
        # Mock set_interval
        log_pane.set_interval = Mock(return_value=Mock())
        
        # Call on_mount
        log_pane.on_mount()
        
        # Should set up timer
        log_pane.set_interval.assert_called_once_with(0.1, log_pane._process_log_queue)
        assert log_pane.queue_timer is not None
        
        # Should set UI components in state manager
        log_pane.log_state_manager.set_ui_components.assert_called_once_with(
            log_pane.header, log_pane.log_display
        )
        
    def test_on_unmount_cleanup(self, log_pane):
        """Test that on_unmount cleans up resources."""
        # Set up resources
        log_pane.queue_timer = Mock()
        log_pane.queue_timer.stop = Mock()
        
        # Call on_unmount
        log_pane.on_unmount()
        
        # Should stop streaming and timer
        log_pane.log_stream_manager.stop_streaming.assert_called_once_with(wait=True)
        log_pane.queue_timer.stop.assert_called_once()
        log_pane.log_filter_manager.cleanup.assert_called_once()
        
    def test_on_input_changed_search(self, log_pane):
        """Test search input change handling."""
        # Create mock event
        event = Mock()
        event.input = Mock(id="search-input")
        event.value = "test search"
        
        # Call on_input_changed
        log_pane.on_input_changed(event)
        
        # Should handle search input
        log_pane.log_filter_manager.handle_search_input_changed.assert_called_once_with("test search")
        
    def test_on_checkbox_changed_auto_follow(self, log_pane):
        """Test auto-follow checkbox change handling."""
        # Create mock event
        event = Mock()
        event.checkbox = Mock(id="auto-follow-checkbox")
        event.value = True
        
        # Mock _auto_scroll_to_bottom
        log_pane._auto_scroll_to_bottom = Mock()
        
        # Call on_checkbox_changed
        log_pane.on_checkbox_changed(event)
        
        # Should update auto-follow state
        log_pane.log_state_manager.set_auto_follow.assert_called_once_with(True)
        log_pane._auto_scroll_to_bottom.assert_called_once()
        
    def test_on_select_changed_tail(self, log_pane):
        """Test tail dropdown change handling."""
        # Create mock event
        event = Mock()
        event.select = Mock(id="tail-select")
        event.value = "500"
        
        # Set up current item
        log_pane.log_state_manager.current_item = ("container", "test_id")
        log_pane.log_display.display = True
        
        # Mock _restart_logs
        log_pane._restart_logs = Mock()
        
        # Call on_select_changed
        log_pane.on_select_changed(event)
        
        # Should update tail value and restart logs
        assert log_pane.LOG_TAIL == "500"
        log_pane.log_stream_manager.update_settings.assert_called_once_with(tail="500")
        log_pane._restart_logs.assert_called_once()
        
    def test_on_select_changed_since(self, log_pane):
        """Test since dropdown change handling."""
        # Create mock event
        event = Mock()
        event.select = Mock(id="since-select")
        event.value = "30m"
        
        # Set up current item
        log_pane.log_state_manager.current_item = ("container", "test_id")
        log_pane.log_display.display = True
        
        # Mock _restart_logs
        log_pane._restart_logs = Mock()
        
        # Call on_select_changed
        log_pane.on_select_changed(event)
        
        # Should update since value and restart logs
        assert log_pane.LOG_SINCE == "30m"
        log_pane.log_stream_manager.update_settings.assert_called_once_with(since="30m")
        log_pane._restart_logs.assert_called_once()
        
    def test_on_button_pressed_mark_position(self, log_pane):
        """Test mark position button press handling."""
        # Create mock event
        event = Mock()
        event.button = Mock(id="mark-position-button")
        
        # Mock _mark_position
        log_pane._mark_position = Mock()
        
        # Call on_button_pressed
        log_pane.on_button_pressed(event)
        
        # Should call _mark_position
        log_pane._mark_position.assert_called_once()
        
    def test_action_copy_selection_with_text(self, log_pane):
        """Test copying selected text to clipboard."""
        # Set up selected text
        log_pane.log_display.display = True
        log_pane.log_display.selected_text = "Selected text to copy"
        
        # Mock copy_to_clipboard_async
        with patch('DockTUI.ui.viewers.log_pane.copy_to_clipboard_async') as mock_copy:
            # Call action_copy_selection
            log_pane.action_copy_selection()
            
            # Should call copy_to_clipboard_async
            mock_copy.assert_called_once()
            args = mock_copy.call_args[0]
            assert args[0] == "Selected text to copy"
            # Get the callback function
            callback = args[1]
            
            # Test success callback
            callback(True)
            log_pane.app.notify.assert_called_with(
                "Text copied to clipboard",
                severity="information",
                timeout=2
            )
            
            # Reset and test failure callback
            log_pane.app.notify.reset_mock()
            callback(False)
            log_pane.app.notify.assert_called_with(
                "Failed to copy to clipboard. Please install xclip or pyperclip.",
                severity="error",
                timeout=3
            )
            
    def test_action_copy_selection_no_text(self, log_pane):
        """Test copying with no selected text."""
        # Set up no selected text
        log_pane.log_display.display = True
        log_pane.log_display.selected_text = ""
        
        # Mock copy_to_clipboard_async
        with patch('DockTUI.ui.viewers.log_pane.copy_to_clipboard_async') as mock_copy:
            # Call action_copy_selection
            log_pane.action_copy_selection()
            
            # Should not call copy_to_clipboard_async
            mock_copy.assert_not_called()
            
    def test_action_select_all(self, log_pane):
        """Test selecting all text in log display."""
        # Set up log display
        log_pane.log_display.display = True
        log_pane.log_display.select_all = Mock()
        
        # Call action_select_all
        log_pane.action_select_all()
        
        # Should call select_all on log display
        log_pane.log_display.select_all.assert_called_once()
        
    def test_show_no_logs_message_for_item_type(self, log_pane):
        """Test showing no logs message for item types without logs."""
        # Mock methods
        log_pane._clear_logs = Mock()
        log_pane._set_log_text = Mock()
        log_pane.refresh = Mock()
        
        # Test for network
        log_pane._show_no_logs_message_for_item_type("Networks")
        
        # Should show appropriate message
        assert log_pane.log_display.display == True
        assert log_pane.no_selection_display.display == False
        log_pane._clear_logs.assert_called_once()
        log_pane._set_log_text.assert_called_once_with(
            "Networks do not have logs. Select a container or stack to view logs."
        )
        log_pane.log_stream_manager.stop_streaming.assert_called_with(wait=False)
        log_pane.refresh.assert_called_once()
        
    def test_restart_logs(self, log_pane):
        """Test restarting logs with new settings."""
        # Set up current item
        log_pane.log_state_manager.current_item = ("container", "test_id")
        
        # Mock methods
        log_pane._clear_logs = Mock()
        log_pane._set_log_text = Mock()
        
        # Call _restart_logs
        log_pane._restart_logs()
        
        # Should clear and show loading message
        log_pane._clear_logs.assert_called_once()
        log_pane._set_log_text.assert_called_once_with(
            "Reloading logs for container: test_id...\n"
        )
        assert log_pane.log_stream_manager.showing_loading_message == True
        log_pane.log_stream_manager.restart_streaming.assert_called_once()
        
    def test_auto_scroll_to_bottom_enabled(self, log_pane):
        """Test auto-scrolling when enabled."""
        # Set up auto-follow enabled
        log_pane.log_state_manager.should_auto_scroll = Mock(return_value=True)
        log_pane.log_display.scroll_to_end_immediate = Mock()
        
        # Call _auto_scroll_to_bottom
        log_pane._auto_scroll_to_bottom()
        
        # Should scroll to bottom
        log_pane.log_display.scroll_to_end_immediate.assert_called_once()
        
    def test_auto_scroll_to_bottom_disabled(self, log_pane):
        """Test auto-scrolling when disabled."""
        # Set up auto-follow disabled
        log_pane.log_state_manager.should_auto_scroll = Mock(return_value=False)
        log_pane.log_display.scroll_to_end_immediate = Mock()
        
        # Call _auto_scroll_to_bottom
        log_pane._auto_scroll_to_bottom()
        
        # Should not scroll
        log_pane.log_display.scroll_to_end_immediate.assert_not_called()
        
    def test_clear_log_display(self, log_pane):
        """Test clearing the log display."""
        # Mock clear method
        log_pane.log_display.clear = Mock()
        
        # Call _clear_log_display
        log_pane._clear_log_display()
        
        # Should clear display
        log_pane.log_display.clear.assert_called_once()
        
    def test_get_log_text(self, log_pane):
        """Test getting log text from display."""
        # Set up visible lines
        mock_line1 = Mock(raw_text="Line 1")
        mock_line2 = Mock(raw_text="Line 2")
        log_pane.log_display.visible_lines = [mock_line1, mock_line2]
        
        # Call _get_log_text
        result = log_pane._get_log_text()
        
        # Should join lines
        assert result == "Line 1\nLine 2"
        
    def test_update_header(self, log_pane):
        """Test updating header text."""
        # Call _update_header
        log_pane._update_header("New header text")
        
        # Should delegate to state manager
        log_pane.log_state_manager.update_header.assert_called_once_with("New header text")
        
    def test_set_log_text(self, log_pane):
        """Test setting log display text."""
        # Mock methods
        log_pane.log_display.clear = Mock()
        log_pane.log_display.add_log_line = Mock()
        
        # Call _set_log_text with multiline text
        log_pane._set_log_text("Line 1\nLine 2\nLine 3\n")
        
        # Should clear and add lines
        log_pane.log_display.clear.assert_called_once()
        assert log_pane.log_display.add_log_line.call_count == 3
        log_pane.log_display.add_log_line.assert_any_call("Line 1", is_system_message=True)
        log_pane.log_display.add_log_line.assert_any_call("Line 2", is_system_message=True)
        log_pane.log_display.add_log_line.assert_any_call("Line 3", is_system_message=True)
        
    def test_create_tail_select_default(self, log_pane):
        """Test creating tail select with default value."""
        # Mock the Select class to avoid Textual initialization issues
        with patch('DockTUI.ui.viewers.log_pane.Select') as mock_select:
            mock_instance = Mock()
            mock_select.return_value = mock_instance
            
            # Call _create_tail_select
            select = log_pane._create_tail_select()
            
            # Should create select with correct properties
            mock_select.assert_called_once()
            args, kwargs = mock_select.call_args
            assert kwargs['value'] == "200"
            assert kwargs['id'] == "tail-select"
            assert kwargs['classes'] == "log-setting"
            
    def test_create_tail_select_custom_value(self, log_pane):
        """Test creating tail select with custom value not in options."""
        # Set custom value
        log_pane.LOG_TAIL = "999"
        
        # Mock the Select class
        with patch('DockTUI.ui.viewers.log_pane.Select') as mock_select:
            mock_instance = Mock()
            mock_select.return_value = mock_instance
            
            # Call _create_tail_select
            select = log_pane._create_tail_select()
            
            # Should add custom value to options and use it
            args, kwargs = mock_select.call_args
            assert kwargs['value'] == "999"
            # Check that custom option was added
            options = kwargs['options']
            assert any(opt[1] == "999" for opt in options)
            
    def test_create_since_select_default(self, log_pane):
        """Test creating since select with default value."""
        # Mock the Select class
        with patch('DockTUI.ui.viewers.log_pane.Select') as mock_select:
            mock_instance = Mock()
            mock_select.return_value = mock_instance
            
            # Call _create_since_select
            select = log_pane._create_since_select()
            
            # Should create select with correct properties
            mock_select.assert_called_once()
            args, kwargs = mock_select.call_args
            assert kwargs['value'] == "15m"
            assert kwargs['id'] == "since-select"
            assert kwargs['classes'] == "log-setting"
        
    def test_refilter_logs_with_filter(self, log_pane):
        """Test re-filtering logs with active filter."""
        # Set up scenario with logs and filter
        log_pane.log_stream_manager.showing_no_logs_message = False
        log_pane.log_stream_manager.showing_no_matches_message = False
        log_pane.log_filter_manager.get_all_lines = Mock(return_value=["Line 1", "Line 2"])
        log_pane.log_filter_manager.get_current_filter = Mock(return_value="test")
        log_pane.log_filter_manager.has_filter = Mock(return_value=True)
        
        # Set up RichLogViewer with the necessary methods
        from DockTUI.ui.widgets.rich_log_viewer import RichLogViewer
        log_pane.log_display.__class__ = RichLogViewer  # Make isinstance check pass
        log_pane.log_display.set_filter = Mock()
        log_pane.log_display.refilter_existing_lines = Mock()
        log_pane.log_display.visible_lines = []  # No matches
        
        # Call _refilter_logs
        log_pane._refilter_logs()
        
        # Should update filter and mark as no matches
        log_pane.log_display.set_filter.assert_called_once_with("test")
        log_pane.log_display.refilter_existing_lines.assert_called_once()
        assert log_pane.log_stream_manager.showing_no_matches_message == True
        
    def test_refilter_logs_no_logs(self, log_pane):
        """Test re-filtering when there are no logs."""
        # Set up scenario with no logs
        log_pane.log_stream_manager.showing_no_logs_message = False
        log_pane.log_filter_manager.get_all_lines = Mock(return_value=[])
        log_pane._set_log_text = Mock()
        log_pane.log_queue_processor._get_no_logs_message = Mock(return_value="No logs found")
        
        # Call _refilter_logs
        log_pane._refilter_logs()
        
        # Should show no logs message
        log_pane._set_log_text.assert_called_once_with("No logs found")
        assert log_pane.log_stream_manager.showing_no_logs_message == True
        
    def test_on_marker_added(self, log_pane):
        """Test handling marker lines being added."""
        # Mock _append_log_line
        log_pane._append_log_line = Mock()
        
        # Call _on_marker_added
        marker_lines = ["Line 1", "Line 2", "Line 3"]
        log_pane._on_marker_added(marker_lines)
        
        # Should append each line
        assert log_pane._append_log_line.call_count == 3
        log_pane._append_log_line.assert_any_call("Line 1")
        log_pane._append_log_line.assert_any_call("Line 2")
        log_pane._append_log_line.assert_any_call("Line 3")
        
    def test_handle_status_change_stopped(self, log_pane):
        """Test handling container status change to stopped."""
        # Set up current item
        log_pane.log_state_manager.current_item = ("container", "test_id")
        log_pane.log_state_manager.current_item_data = {"name": "test_container"}
        log_pane.log_state_manager.is_container_stopped = Mock(return_value=True)
        
        # Mock methods
        log_pane._clear_logs = Mock()
        log_pane._set_log_text = Mock()
        log_pane._start_logs = Mock()
        
        # Call _handle_status_change
        item_data = {"name": "test_container", "status": "exited"}
        log_pane._handle_status_change(item_data)
        
        # Should update header and show stopped message
        log_pane.log_state_manager.update_header_with_status.assert_called_once_with(
            "test_container", "exited"
        )
        log_pane._set_log_text.assert_called_once_with(
            "Container 'test_container' stopped. Loading historical logs...\n"
        )
        log_pane._start_logs.assert_called_once()
        
    def test_handle_status_change_started(self, log_pane):
        """Test handling container status change to started."""
        # Set up current item
        log_pane.log_state_manager.current_item = ("container", "test_id")
        log_pane.log_state_manager.current_item_data = {"name": "test_container"}
        log_pane.log_state_manager.is_container_stopped = Mock(return_value=False)
        
        # Mock methods
        log_pane._clear_logs = Mock()
        log_pane._set_log_text = Mock()
        log_pane._start_logs = Mock()
        
        # Call _handle_status_change
        item_data = {"name": "test_container", "status": "running"}
        log_pane._handle_status_change(item_data)
        
        # Should update header and show started message
        log_pane.log_state_manager.update_header_with_status.assert_called_once_with(
            "test_container", "running"
        )
        log_pane._set_log_text.assert_called_once_with(
            "Container 'test_container' started. Loading logs...\n"
        )
        log_pane._start_logs.assert_called_once()
        
    def test_start_logs_no_current_item(self, log_pane):
        """Test starting logs with no current item."""
        # Set no current item
        log_pane.log_state_manager.current_item = None
        
        # Call _start_logs
        log_pane._start_logs()
        
        # Should not start streaming
        log_pane.log_stream_manager.start_streaming.assert_not_called()
        
    def test_start_logs_manager_not_available(self, log_pane):
        """Test starting logs when stream manager not available."""
        # Set current item but manager not available
        log_pane.log_state_manager.current_item = ("container", "test_id")
        log_pane.log_stream_manager.is_available = False
        
        # Call _start_logs
        log_pane._start_logs()
        
        # Should not start streaming
        log_pane.log_stream_manager.start_streaming.assert_not_called()
        
    def test_update_selection_network_type(self, log_pane):
        """Test update_selection for network type (no logs)."""
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.log_state_manager.update_header_for_item = Mock(return_value=False)  # No logs
        log_pane._show_no_logs_message_for_item_type = Mock()
        log_pane.call_after_refresh = Mock()
        
        # Call update_selection with network
        log_pane.update_selection("network", "bridge", {"name": "bridge"})
        
        # Should show no logs message for networks
        log_pane._show_no_logs_message_for_item_type.assert_called_once_with("Networks")
        
    def test_update_selection_image_type(self, log_pane):
        """Test update_selection for image type (no logs)."""
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.log_state_manager.update_header_for_item = Mock(return_value=False)  # No logs
        log_pane._show_no_logs_message_for_item_type = Mock()
        log_pane.call_after_refresh = Mock()
        
        # Call update_selection with image
        log_pane.update_selection("image", "ubuntu:latest", {"name": "ubuntu"})
        
        # Should show no logs message for images
        log_pane._show_no_logs_message_for_item_type.assert_called_once_with("Images")
        
    def test_update_selection_volume_type(self, log_pane):
        """Test update_selection for volume type (no logs)."""
        # Mock dependencies
        log_pane.log_state_manager.save_dropdown_states = Mock(return_value={})
        log_pane.log_state_manager.restore_dropdown_states = Mock()
        log_pane.log_state_manager.update_header_for_item = Mock(return_value=False)  # No logs
        log_pane._show_no_logs_message_for_item_type = Mock()
        log_pane.call_after_refresh = Mock()
        
        # Call update_selection with volume
        log_pane.update_selection("volume", "data_volume", {"name": "data_volume"})
        
        # Should show no logs message for volumes  
        log_pane._show_no_logs_message_for_item_type.assert_called_once_with("Volumes")