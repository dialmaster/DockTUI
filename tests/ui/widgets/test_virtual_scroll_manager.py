"""Unit tests for VirtualScrollManager."""

import json
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest
from textual.geometry import Size

from DockTUI.models.log_line import LogLine
from DockTUI.ui.widgets.virtual_scroll_manager import VirtualScrollManager


class TestVirtualScrollManager:
    """Test cases for VirtualScrollManager."""

    @pytest.fixture
    def manager(self):
        """Create a VirtualScrollManager instance."""
        return VirtualScrollManager()

    @pytest.fixture
    def mock_log_lines(self):
        """Create mock log lines for testing."""
        lines = []
        for i in range(5):
            line = Mock(spec=LogLine)
            line.raw_text = f"Log line {i}"
            line.is_expanded = False
            line.is_parsed = False
            line.json_data = None
            line.xml_data = None
            line.ensure_parsed = Mock()
            lines.append(line)
        return lines

    @pytest.fixture
    def mock_count_json_lines_fn(self):
        """Mock function for counting JSON lines."""
        return Mock(side_effect=lambda data: len(json.dumps(data, indent=2).split("\n")))

    @pytest.fixture
    def mock_count_xml_lines_fn(self):
        """Mock function for counting XML lines."""
        return Mock(return_value=5)  # Default to 5 lines for XML

    def test_init(self, manager):
        """Test VirtualScrollManager initialization."""
        assert manager._virtual_size_cache is None
        assert manager._virtual_size_timer is None
        assert manager._virtual_size_pending is False
        assert isinstance(manager._lock, type(threading.RLock()))

    def test_cleanup_no_timer(self, manager):
        """Test cleanup when no timer is active."""
        manager.cleanup()
        # Should not raise any errors
        assert manager._virtual_size_timer is None

    def test_cleanup_with_active_timer(self, manager):
        """Test cleanup with an active timer."""
        # Create a mock timer
        mock_timer = Mock()
        manager._virtual_size_timer = mock_timer

        manager.cleanup()

        # Timer should be cancelled and cleared
        mock_timer.cancel.assert_called_once()
        assert manager._virtual_size_timer is None

    def test_get_virtual_size_initial_calculation(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test virtual size calculation when cache is empty."""
        widget_size = Size(80, 24)

        result = manager.get_virtual_size(
            mock_log_lines,
            widget_size,
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        # Should return calculated size
        assert result.width >= widget_size.width
        assert result.height >= len(mock_log_lines)
        assert manager._virtual_size_cache == result

    def test_get_virtual_size_cached(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test virtual size returns cached value."""
        cached_size = Size(100, 50)
        manager._virtual_size_cache = cached_size

        result = manager.get_virtual_size(
            mock_log_lines,
            widget_size=Size(80, 24),
            count_json_lines_fn=mock_count_json_lines_fn,
            count_xml_lines_fn=mock_count_xml_lines_fn,
        )

        # Should return cached value without recalculation
        assert result == cached_size
        # Log lines should not be parsed when using cache
        for line in mock_log_lines:
            line.ensure_parsed.assert_not_called()

    def test_get_virtual_size_with_expanded_json(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test virtual size calculation with expanded JSON lines."""
        # Make one line expanded with JSON data
        mock_log_lines[1].is_expanded = True
        mock_log_lines[1].json_data = {"key": "value", "nested": {"data": 123}}

        widget_size = Size(80, 24)

        result = manager.get_virtual_size(
            mock_log_lines,
            widget_size,
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        # Should parse expanded line
        mock_log_lines[1].ensure_parsed.assert_called_once()
        # Should count JSON lines
        mock_count_json_lines_fn.assert_called_once_with(mock_log_lines[1].json_data)
        # Height should be more than just line count due to expanded JSON
        assert result.height > len(mock_log_lines)

    def test_get_virtual_size_with_expanded_xml(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test virtual size calculation with expanded XML lines."""
        # Make one line expanded with XML data
        mock_log_lines[2].is_expanded = True
        mock_log_lines[2].xml_data = "<root><child>data</child></root>"

        # Mock XML formatter
        with patch(
            "DockTUI.services.log.xml_formatter.XMLFormatter"
        ) as mock_xml_formatter:
            mock_segments = [[Mock(text="  <root>")], [Mock(text="    <child>data</child>")], [Mock(text="  </root>")]]
            mock_xml_formatter.format_xml_pretty.return_value = mock_segments

            widget_size = Size(80, 24)

            result = manager.get_virtual_size(
                mock_log_lines,
                widget_size,
                mock_count_json_lines_fn,
                mock_count_xml_lines_fn,
            )

            # Should parse expanded line
            mock_log_lines[2].ensure_parsed.assert_called_once()
            # Should count XML lines
            mock_count_xml_lines_fn.assert_called_once_with(mock_log_lines[2].xml_data)
            # Height should include XML lines
            assert result.height > len(mock_log_lines)

    def test_get_virtual_size_no_widget_size(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test virtual size calculation with no widget size."""
        result = manager.get_virtual_size(
            mock_log_lines,
            None,  # No widget size
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        # Should use defaults
        assert result.width >= manager.DEFAULT_WIDTH
        assert result.height >= manager.MIN_VIRTUAL_HEIGHT

    def test_set_virtual_size(self, manager):
        """Test setting virtual size directly."""
        new_size = Size(120, 60)
        manager.set_virtual_size(new_size)

        assert manager._virtual_size_cache == new_size

    def test_invalidate_virtual_size_debounced(self, manager):
        """Test debounced virtual size invalidation."""
        callback = Mock()

        # First invalidation should start timer
        manager.invalidate_virtual_size(callback)

        assert manager._virtual_size_pending is True
        assert manager._virtual_size_timer is not None
        assert manager._virtual_size_timer.daemon is True

        # Second invalidation should not create new timer
        old_timer = manager._virtual_size_timer
        manager.invalidate_virtual_size(callback)

        assert manager._virtual_size_timer is old_timer

        # Cleanup
        manager.cleanup()

    def test_invalidate_virtual_size_immediate(self, manager):
        """Test immediate virtual size invalidation."""
        # Set up initial state
        manager._virtual_size_cache = Size(100, 50)
        manager._virtual_size_pending = True
        mock_timer = Mock()
        manager._virtual_size_timer = mock_timer

        manager.invalidate_virtual_size_immediate()

        # Should cancel timer and clear cache
        mock_timer.cancel.assert_called_once()
        assert manager._virtual_size_cache is None
        assert manager._virtual_size_pending is False
        assert manager._virtual_size_timer is None

    def test_perform_virtual_size_recalculation(self, manager):
        """Test the actual recalculation after debounce."""
        callback = Mock()
        manager._virtual_size_cache = Size(100, 50)
        manager._virtual_size_pending = True

        manager._perform_virtual_size_recalculation(callback)

        # Should clear cache and call callback
        assert manager._virtual_size_cache is None
        assert manager._virtual_size_pending is False
        assert manager._virtual_size_timer is None
        callback.assert_called_once()

    def test_perform_virtual_size_recalculation_not_pending(self, manager):
        """Test recalculation when not pending."""
        callback = Mock()
        manager._virtual_size_pending = False

        manager._perform_virtual_size_recalculation(callback)

        # Should not do anything
        callback.assert_not_called()

    def test_get_line_at_virtual_y_simple(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting line at virtual Y position with simple lines."""
        # All lines are 1 virtual line tall
        result = manager.get_line_at_virtual_y(
            2,  # Third line (0-indexed)
            mock_log_lines,
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        assert result is not None
        log_line, offset = result
        assert log_line == mock_log_lines[2]
        assert offset == 0

    def test_get_line_at_virtual_y_with_expanded(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting line at virtual Y with expanded lines."""
        # Make second line expanded with JSON (5 lines tall)
        mock_log_lines[1].is_expanded = True
        mock_log_lines[1].json_data = {"key": "value"}
        # Need to configure the mock properly to return 5 for this specific data
        mock_count_json_lines_fn.side_effect = lambda data: 5 if data == {"key": "value"} else 1

        # Virtual Y positions:
        # Line 0: position 0
        # Line 1: positions 1-5 (expanded, 5 lines)
        # Line 2: position 6
        # Line 3: position 7
        # Line 4: position 8

        # Test getting middle of expanded line
        result = manager.get_line_at_virtual_y(
            3,  # Middle of expanded line
            mock_log_lines,
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        assert result is not None
        log_line, offset = result
        assert log_line == mock_log_lines[1]
        assert offset == 2  # 3 - 1 = 2

        # Test getting line after expanded
        result = manager.get_line_at_virtual_y(
            6,  # Should be line 2
            mock_log_lines,
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        assert result is not None
        log_line, offset = result
        assert log_line == mock_log_lines[2]
        assert offset == 0

    def test_get_line_at_virtual_y_out_of_bounds(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test getting line at virtual Y position out of bounds."""
        result = manager.get_line_at_virtual_y(
            100,  # Way past the end
            mock_log_lines,
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        assert result is None

    def test_calculate_viewport_range_basic(self, manager):
        """Test basic viewport range calculation."""
        start, end = manager.calculate_viewport_range(
            scroll_offset_y=10.5,
            viewport_height=20,
            pre_parse_ahead=5,
            pre_parse_before=5,
        )

        # Start should be adjusted for pre-parse before
        assert start == 5  # max(0, 10 - 5)
        # End should include viewport + pre-parse ahead
        assert end == 35  # 10 + 20 + 5

    def test_calculate_viewport_range_near_top(self, manager):
        """Test viewport range calculation near top."""
        start, end = manager.calculate_viewport_range(
            scroll_offset_y=2.0,
            viewport_height=20,
            pre_parse_ahead=10,
            pre_parse_before=10,
        )

        # Start should be clamped to 0
        assert start == 0  # max(0, 2 - 10)
        assert end == 32  # 2 + 20 + 10

    def test_find_lines_in_viewport_simple(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test finding lines in viewport with simple lines."""
        lines_in_viewport = manager.find_lines_in_viewport(
            mock_log_lines,
            viewport_start=1,
            viewport_end=3,  # End at 3 to get lines 1, 2, 3
            count_json_lines_fn=mock_count_json_lines_fn,
            count_xml_lines_fn=mock_count_xml_lines_fn,
        )

        # Should return lines 1, 2, 3 with their positions
        assert len(lines_in_viewport) == 3
        assert lines_in_viewport[0] == (mock_log_lines[1], 1)
        assert lines_in_viewport[1] == (mock_log_lines[2], 2)
        assert lines_in_viewport[2] == (mock_log_lines[3], 3)

    def test_find_lines_in_viewport_with_expanded(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test finding lines in viewport with expanded lines."""
        # Make second line expanded and parsed
        mock_log_lines[1].is_expanded = True
        mock_log_lines[1].is_parsed = True
        mock_log_lines[1].json_data = {"key": "value"}
        # Configure mock to return 5 for this specific data
        mock_count_json_lines_fn.side_effect = lambda data: 5 if data == {"key": "value"} else 1

        # Virtual positions:
        # Line 0: 0
        # Line 1: 1-5 (expanded)
        # Line 2: 6
        # Line 3: 7
        # Line 4: 8

        lines_in_viewport = manager.find_lines_in_viewport(
            mock_log_lines,
            viewport_start=3,
            viewport_end=6,  # End at 6 to include line 2
            count_json_lines_fn=mock_count_json_lines_fn,
            count_xml_lines_fn=mock_count_xml_lines_fn,
        )

        # Should return expanded line and line 2
        assert len(lines_in_viewport) == 2
        assert lines_in_viewport[0] == (mock_log_lines[1], 1)  # Expanded line
        assert lines_in_viewport[1] == (mock_log_lines[2], 6)  # Next line

    def test_find_lines_in_viewport_past_end(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test finding lines when viewport extends past end."""
        lines_in_viewport = manager.find_lines_in_viewport(
            mock_log_lines,
            viewport_start=3,
            viewport_end=100,  # Way past end
            count_json_lines_fn=mock_count_json_lines_fn,
            count_xml_lines_fn=mock_count_xml_lines_fn,
        )

        # Should return lines 3 and 4
        assert len(lines_in_viewport) == 2
        assert lines_in_viewport[0] == (mock_log_lines[3], 3)
        assert lines_in_viewport[1] == (mock_log_lines[4], 4)

    def test_calculate_total_virtual_lines_simple(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test calculating total virtual lines with simple lines."""
        total = manager.calculate_total_virtual_lines(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        assert total == 5  # 5 simple lines

    def test_calculate_total_virtual_lines_with_expanded(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test calculating total virtual lines with expanded lines."""
        # Make one line expanded with JSON
        mock_log_lines[1].is_expanded = True
        mock_log_lines[1].json_data = {"key": "value"}
        # Configure mock to return specific values for specific data
        def count_json(data):
            if data == {"key": "value"}:
                return 5
            return 1
        mock_count_json_lines_fn.side_effect = count_json

        # Make another expanded with XML
        mock_log_lines[3].is_expanded = True
        mock_log_lines[3].xml_data = "<root/>"
        # Configure mock to return 3 for this XML
        def count_xml(data):
            if data == "<root/>":
                return 3
            return 1
        mock_count_xml_lines_fn.side_effect = count_xml

        total = manager.calculate_total_virtual_lines(
            mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )

        # Total: 1 + 5 + 1 + 3 + 1 = 11
        assert total == 11

    def test_thread_safety_get_virtual_size(
        self, manager, mock_log_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test thread safety of get_virtual_size."""
        widget_size = Size(80, 24)
        results = []

        def worker():
            result = manager.get_virtual_size(
                mock_log_lines,
                widget_size,
                mock_count_json_lines_fn,
                mock_count_xml_lines_fn,
            )
            results.append(result)

        # Run multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be the same
        assert len(results) == 5
        assert all(r == results[0] for r in results)

    def test_thread_safety_invalidation(self, manager):
        """Test thread safety of invalidation operations."""
        callback = Mock()
        
        def invalidate_worker():
            manager.invalidate_virtual_size(callback)
        
        def immediate_worker():
            manager.invalidate_virtual_size_immediate()

        # Run mixed operations in threads
        threads = []
        for i in range(10):
            if i % 2 == 0:
                t = threading.Thread(target=invalidate_worker)
            else:
                t = threading.Thread(target=immediate_worker)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()

        # Should not crash and manager should be in consistent state
        assert manager._lock is not None  # Lock should still exist
        
        # Cleanup
        manager.cleanup()

    def test_timer_callback_execution(self, manager):
        """Test that timer callback actually executes after delay."""
        callback = Mock()
        manager._virtual_size_cache = Size(100, 50)
        
        # Use a shorter delay for testing
        original_delay = manager.VIRTUAL_SIZE_THROTTLE_DELAY
        manager.VIRTUAL_SIZE_THROTTLE_DELAY = 0.1
        
        try:
            manager.invalidate_virtual_size(callback)
            
            # Wait for timer to fire
            time.sleep(0.2)
            
            # Callback should have been called
            callback.assert_called_once()
            assert manager._virtual_size_cache is None
            assert manager._virtual_size_timer is None
            
        finally:
            manager.VIRTUAL_SIZE_THROTTLE_DELAY = original_delay
            manager.cleanup()

    def test_edge_case_empty_lines(
        self, manager, mock_count_json_lines_fn, mock_count_xml_lines_fn
    ):
        """Test handling of empty lines list."""
        empty_lines = []
        widget_size = Size(80, 24)

        # Should not crash
        result = manager.get_virtual_size(
            empty_lines,
            widget_size,
            mock_count_json_lines_fn,
            mock_count_xml_lines_fn,
        )

        assert result.width >= widget_size.width
        assert result.height >= widget_size.height

        # Test other methods with empty lines
        line_result = manager.get_line_at_virtual_y(
            0, empty_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )
        assert line_result is None

        viewport_lines = manager.find_lines_in_viewport(
            empty_lines, 0, 10, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )
        assert viewport_lines == []

        total = manager.calculate_total_virtual_lines(
            empty_lines, mock_count_json_lines_fn, mock_count_xml_lines_fn
        )
        assert total == 0