"""Tests for the LogTextArea widget."""

from unittest.mock import Mock, PropertyMock, patch

import pytest
from textual.events import MouseDown, MouseUp

from DockTUI.ui.widgets.log_text_area import LogTextArea


class TestLogTextArea:
    """Test cases for the LogTextArea widget."""

    @pytest.fixture
    def log_text_area(self):
        """Create a LogTextArea instance with mocked dependencies."""
        # Mock the parent class initialization
        with patch('textual.widgets.TextArea.__init__', return_value=None):
            # Create instance without calling parent __init__
            area = object.__new__(LogTextArea)
            
            # Initialize attributes
            area._is_selecting = False
            
            # Mock selected_text as a property
            type(area).selected_text = PropertyMock(return_value="")
            
            # Mock methods
            area.refresh = Mock()
            area.post_message = Mock()
            
            # Mock app and its methods as a property
            mock_app = Mock()
            mock_app.notify = Mock()
            mock_app.call_from_thread = Mock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
            type(area).app = PropertyMock(return_value=mock_app)
            
            # Now call the actual LogTextArea __init__
            LogTextArea.__init__(area)
            
            yield area

    def test_init(self, log_text_area):
        """Test initialization of LogTextArea."""
        assert hasattr(log_text_area, '_is_selecting')
        assert log_text_area._is_selecting is False

    def test_is_selecting_property(self, log_text_area):
        """Test the is_selecting property."""
        # Initially should be False
        assert log_text_area.is_selecting is False
        
        # Set to True
        log_text_area._is_selecting = True
        assert log_text_area.is_selecting is True
        
        # Set back to False
        log_text_area._is_selecting = False
        assert log_text_area.is_selecting is False

    def test_on_mouse_down_left_click(self, log_text_area):
        """Test mouse down event for left click starts selection."""
        # Create left click event
        event = MouseDown(x=10, y=5, delta_x=0, delta_y=0, button=1, widget=None, shift=False, meta=False, ctrl=False)
        
        # Call handler
        log_text_area.on_mouse_down(event)
        
        # Should set selecting to True
        assert log_text_area._is_selecting is True

    def test_on_mouse_down_right_click_with_selection(self, log_text_area):
        """Test mouse down event for right click with selected text."""
        # Set up selected text
        type(log_text_area).selected_text = PropertyMock(return_value="Hello, World!")
        
        # Mock copy_to_clipboard_async
        with patch('DockTUI.ui.widgets.log_text_area.copy_to_clipboard_async') as mock_copy:
            # Create right click event
            event = MouseDown(x=10, y=5, delta_x=0, delta_y=0, button=3, widget=None, shift=False, meta=False, ctrl=False)
            
            # Call handler
            log_text_area.on_mouse_down(event)
            
            # Should not change selecting state
            assert log_text_area._is_selecting is False
            
            # Should call copy_to_clipboard_async with text and callback
            assert mock_copy.call_count == 1
            assert mock_copy.call_args[0][0] == "Hello, World!"
            assert callable(mock_copy.call_args[0][1])  # callback function
            
            # Simulate successful copy by calling the callback
            callback = mock_copy.call_args[0][1]
            callback(True)
            
            # Should show success notification
            log_text_area.app.notify.assert_called_once_with(
                "Text copied to clipboard",
                severity="information",
                timeout=1
            )

    def test_on_mouse_down_right_click_no_selection(self, log_text_area):
        """Test mouse down event for right click without selected text."""
        # No selected text (already set to "" in fixture)
        
        # Mock copy_to_clipboard_async to ensure it's not called
        with patch('DockTUI.ui.widgets.log_text_area.copy_to_clipboard_async') as mock_copy:
            # Create right click event
            event = MouseDown(x=10, y=5, delta_x=0, delta_y=0, button=3, widget=None, shift=False, meta=False, ctrl=False)
            
            # Call handler
            log_text_area.on_mouse_down(event)
            
            # Should not call copy_to_clipboard_async
            mock_copy.assert_not_called()
            
            # Should not show any notification (no text to copy)
            log_text_area.app.notify.assert_not_called()

    def test_on_mouse_down_right_click_copy_failure(self, log_text_area):
        """Test mouse down event for right click when copy fails."""
        # Set up selected text
        type(log_text_area).selected_text = PropertyMock(return_value="Hello, World!")
        
        # Mock copy_to_clipboard_async
        with patch('DockTUI.ui.widgets.log_text_area.copy_to_clipboard_async') as mock_copy:
            # Create right click event
            event = MouseDown(x=10, y=5, delta_x=0, delta_y=0, button=3, widget=None, shift=False, meta=False, ctrl=False)
            
            # Call handler
            log_text_area.on_mouse_down(event)
            
            # Get the callback and simulate failure
            callback = mock_copy.call_args[0][1]
            callback(False)
            
            # Should show error notification
            log_text_area.app.notify.assert_called_once_with(
                "Failed to copy to clipboard. Please install xclip or pyperclip.",
                severity="error",
                timeout=3
            )

    def test_on_mouse_down_middle_click(self, log_text_area):
        """Test mouse down event for middle click."""
        # Create middle click event
        event = MouseDown(x=10, y=5, delta_x=0, delta_y=0, button=2, widget=None, shift=False, meta=False, ctrl=False)
        
        # Call handler
        log_text_area.on_mouse_down(event)
        
        # Should not change selecting state
        assert log_text_area._is_selecting is False

    def test_on_mouse_up_left_click(self, log_text_area):
        """Test mouse up event for left click ends selection."""
        # Set selecting to True
        log_text_area._is_selecting = True
        
        # Create left click release event
        event = MouseUp(x=10, y=5, delta_x=0, delta_y=0, button=1, widget=None, shift=False, meta=False, ctrl=False)
        
        # Call handler
        log_text_area.on_mouse_up(event)
        
        # Should set selecting to False
        assert log_text_area._is_selecting is False

    def test_on_mouse_up_left_click_not_selecting(self, log_text_area):
        """Test mouse up event when not selecting."""
        # Not selecting
        log_text_area._is_selecting = False
        
        # Create left click release event
        event = MouseUp(x=10, y=5, delta_x=0, delta_y=0, button=1, widget=None, shift=False, meta=False, ctrl=False)
        
        # Call handler
        log_text_area.on_mouse_up(event)
        
        # Should remain False
        assert log_text_area._is_selecting is False

    def test_on_mouse_up_right_click(self, log_text_area):
        """Test mouse up event for right click."""
        # Create right click release event
        event = MouseUp(x=10, y=5, delta_x=0, delta_y=0, button=3, widget=None, shift=False, meta=False, ctrl=False)
        
        # Call handler
        log_text_area.on_mouse_up(event)
        
        # Should not affect selecting state
        assert log_text_area._is_selecting is False

    def test_on_mouse_down_calls_super(self, log_text_area):
        """Test that on_mouse_down handles super() call gracefully."""
        # Create left click event  
        event = MouseDown(x=10, y=5, delta_x=0, delta_y=0, button=1, widget=None, shift=False, meta=False, ctrl=False)
        
        # Call handler - should not raise even if super() method doesn't exist
        log_text_area.on_mouse_down(event)
        
        # Should still set selecting
        assert log_text_area._is_selecting is True

    def test_on_mouse_up_calls_super(self, log_text_area):
        """Test that on_mouse_up handles super() call gracefully."""
        # Set selecting to True
        log_text_area._is_selecting = True
        
        # Create left click release event
        event = MouseUp(x=10, y=5, delta_x=0, delta_y=0, button=1, widget=None, shift=False, meta=False, ctrl=False)
        
        # Call handler - should not raise even if super() method doesn't exist
        log_text_area.on_mouse_up(event)
        
        # Should still clear selecting
        assert log_text_area._is_selecting is False