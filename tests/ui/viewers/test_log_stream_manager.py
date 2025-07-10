"""Tests for the LogStreamManager class."""

import queue
import threading
from unittest.mock import Mock, MagicMock, patch, call

import docker
import pytest

from DockTUI.ui.viewers.log_stream_manager import LogStreamManager


class TestLogStreamManager:
    """Test cases for LogStreamManager."""

    @pytest.fixture
    def mock_docker_client(self):
        """Create a mock Docker client."""
        return Mock(spec=docker.DockerClient)

    @pytest.fixture
    def mock_log_streamer(self):
        """Create a mock LogStreamer."""
        streamer = Mock()
        streamer.get_queue.return_value = queue.Queue()
        streamer.start_streaming.return_value = 1  # Default session ID
        return streamer

    @pytest.fixture
    def manager_with_docker(self, mock_docker_client, mock_log_streamer):
        """Create a LogStreamManager instance with mocked Docker client."""
        with patch("DockTUI.ui.viewers.log_stream_manager.LogStreamer", return_value=mock_log_streamer):
            with patch("DockTUI.ui.viewers.log_stream_manager.config.get") as mock_config:
                mock_config.side_effect = lambda key, default: {
                    "log.tail": 200,
                    "log.since": "15m"
                }.get(key, default)
                manager = LogStreamManager(mock_docker_client)
                return manager

    @pytest.fixture
    def manager_without_docker(self):
        """Create a LogStreamManager instance without Docker client."""
        with patch("DockTUI.ui.viewers.log_stream_manager.config.get") as mock_config:
            mock_config.side_effect = lambda key, default: {
                "log.tail": 200,
                "log.since": "15m"
            }.get(key, default)
            return LogStreamManager(None)

    def test_init_with_docker_client(self, mock_docker_client):
        """Test initialization with Docker client."""
        with patch("DockTUI.ui.viewers.log_stream_manager.LogStreamer") as MockLogStreamer:
            mock_streamer = Mock()
            MockLogStreamer.return_value = mock_streamer
            
            with patch("DockTUI.ui.viewers.log_stream_manager.config.get") as mock_config:
                mock_config.side_effect = lambda key, default: {
                    "log.tail": 300,
                    "log.since": "30m"
                }.get(key, default)
                
                manager = LogStreamManager(mock_docker_client)
                
                assert manager.docker_client == mock_docker_client
                assert manager.log_streamer == mock_streamer
                MockLogStreamer.assert_called_once_with(mock_docker_client)
                
                # Check initial state
                assert manager.current_session_id == 0
                assert manager.current_item is None
                assert manager.current_item_data is None
                assert manager.waiting_for_logs is False
                assert manager.initial_log_check_done is False
                assert manager.showing_no_logs_message is False
                assert manager.showing_loading_message is False
                assert manager.showing_no_matches_message is False
                assert manager.logs_loading is False
                
                # Check log settings from config
                assert manager.log_tail == "300"
                assert manager.log_since == "30m"

    def test_init_without_docker_client(self, manager_without_docker):
        """Test initialization without Docker client."""
        assert manager_without_docker.docker_client is None
        assert manager_without_docker.log_streamer is None
        assert manager_without_docker.current_session_id == 0

    def test_is_available(self, manager_with_docker, manager_without_docker):
        """Test is_available property."""
        assert manager_with_docker.is_available is True
        assert manager_without_docker.is_available is False

    def test_is_loading(self, manager_with_docker):
        """Test is_loading property."""
        assert manager_with_docker.is_loading is False
        manager_with_docker.logs_loading = True
        assert manager_with_docker.is_loading is True

    def test_has_no_logs_message(self, manager_with_docker):
        """Test has_no_logs_message property."""
        assert manager_with_docker.has_no_logs_message is False
        manager_with_docker.showing_no_logs_message = True
        assert manager_with_docker.has_no_logs_message is True

    def test_start_streaming_success(self, manager_with_docker):
        """Test successful start of streaming."""
        mock_streamer = manager_with_docker.log_streamer
        mock_streamer.start_streaming.return_value = 42
        
        result = manager_with_docker.start_streaming(
            "container",
            "test_container_id",
            {"name": "test_container"},
            tail="100",
            since="5m"
        )
        
        assert result is True
        assert manager_with_docker.current_session_id == 42
        assert manager_with_docker.current_item == ("container", "test_container_id")
        assert manager_with_docker.current_item_data == {"name": "test_container"}
        assert manager_with_docker.waiting_for_logs is True
        assert manager_with_docker.initial_log_check_done is False
        assert manager_with_docker.showing_no_logs_message is False
        assert manager_with_docker.showing_no_matches_message is False
        assert manager_with_docker.logs_loading is True
        
        mock_streamer.start_streaming.assert_called_once_with(
            item_type="container",
            item_id="test_container_id",
            item_data={"name": "test_container"},
            tail="100",
            since="5m"
        )

    def test_start_streaming_default_settings(self, manager_with_docker):
        """Test start streaming with default settings."""
        mock_streamer = manager_with_docker.log_streamer
        
        manager_with_docker.start_streaming("container", "test_id", None)
        
        mock_streamer.start_streaming.assert_called_once_with(
            item_type="container",
            item_id="test_id",
            item_data={},
            tail="200",  # Default from config
            since="15m"  # Default from config
        )

    def test_start_streaming_no_streamer(self, manager_without_docker):
        """Test start streaming without log streamer."""
        result = manager_without_docker.start_streaming("container", "test_id", None)
        assert result is False

    def test_stop_streaming_with_wait(self, manager_with_docker):
        """Test stop streaming with wait."""
        mock_streamer = manager_with_docker.log_streamer
        
        manager_with_docker.stop_streaming(wait=True)
        
        mock_streamer.stop_streaming.assert_called_once_with(wait=True)

    def test_stop_streaming_without_wait(self, manager_with_docker):
        """Test stop streaming without wait."""
        mock_streamer = manager_with_docker.log_streamer
        
        manager_with_docker.stop_streaming(wait=False)
        
        mock_streamer.stop_streaming.assert_called_once_with(wait=False)

    def test_stop_streaming_no_streamer(self, manager_without_docker):
        """Test stop streaming without log streamer."""
        # Should not raise exception
        manager_without_docker.stop_streaming()

    def test_restart_streaming_success(self, manager_with_docker):
        """Test successful restart of streaming."""
        # Set up current item
        manager_with_docker.current_item = ("container", "test_id")
        manager_with_docker.current_item_data = {"name": "test"}
        manager_with_docker.log_tail = "50"
        manager_with_docker.log_since = "10m"
        
        mock_streamer = manager_with_docker.log_streamer
        mock_streamer.start_streaming.return_value = 2
        
        result = manager_with_docker.restart_streaming()
        
        assert result is True
        assert manager_with_docker.waiting_for_logs is True
        assert manager_with_docker.initial_log_check_done is False
        assert manager_with_docker.showing_loading_message is True
        assert manager_with_docker.logs_loading is True
        
        # Verify stop was called without wait
        mock_streamer.stop_streaming.assert_called_once_with(wait=False)
        
        # Verify start was called with correct parameters
        mock_streamer.start_streaming.assert_called_once_with(
            item_type="container",
            item_id="test_id",
            item_data={"name": "test"},
            tail="50",
            since="10m"
        )

    def test_restart_streaming_no_current_item(self, manager_with_docker):
        """Test restart streaming with no current item."""
        result = manager_with_docker.restart_streaming()
        assert result is False

    def test_process_queue_empty(self, manager_with_docker):
        """Test process queue when empty."""
        result = manager_with_docker.process_queue()
        
        assert result == {
            "processed": 0,
            "matched": 0,
            "lines": [],
            "errors": [],
            "no_logs": False
        }

    def test_process_queue_no_streamer(self, manager_without_docker):
        """Test process queue without streamer."""
        result = manager_without_docker.process_queue()
        
        assert result == {
            "processed": 0,
            "matched": 0,
            "lines": [],
            "errors": [],
            "no_logs": False
        }

    def test_process_queue_log_messages(self, manager_with_docker):
        """Test processing log messages from queue."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        manager_with_docker.current_session_id = 1
        manager_with_docker.logs_loading = True
        
        # Add items to queue
        log_queue.put((1, "log", "Log line 1"))
        log_queue.put((1, "log", "Log line 2"))
        log_queue.put((1, "log", "Log line 3"))
        
        result = manager_with_docker.process_queue(max_items=2)
        
        assert result["processed"] == 2
        assert result["matched"] == 2
        assert result["lines"] == ["Log line 1", "Log line 2"]
        assert result["errors"] == []
        assert result["no_logs"] is False
        assert manager_with_docker.initial_log_check_done is True
        assert manager_with_docker.logs_loading is False

    def test_process_queue_error_messages(self, manager_with_docker):
        """Test processing error messages from queue."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        manager_with_docker.current_session_id = 1
        
        # Add error messages
        log_queue.put((1, "error", "Error message 1"))
        log_queue.put((1, "error", "Error message 2"))
        
        result = manager_with_docker.process_queue()
        
        assert result["processed"] == 2
        assert result["matched"] == 0
        assert result["lines"] == []
        assert result["errors"] == ["Error message 1", "Error message 2"]
        assert result["no_logs"] is False

    def test_process_queue_no_logs_message(self, manager_with_docker):
        """Test processing no_logs message from queue."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        manager_with_docker.current_session_id = 1
        manager_with_docker.waiting_for_logs = True
        
        # Add no_logs message
        log_queue.put((1, "no_logs", ""))
        
        result = manager_with_docker.process_queue()
        
        assert result["processed"] == 1
        assert result["no_logs"] is True
        assert manager_with_docker.waiting_for_logs is False
        assert manager_with_docker.showing_no_logs_message is True

    def test_process_queue_skip_old_session(self, manager_with_docker):
        """Test that messages from old sessions are skipped."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        manager_with_docker.current_session_id = 2
        
        # Add messages from different sessions
        log_queue.put((1, "log", "Old session log"))  # Old session
        log_queue.put((2, "log", "Current session log"))  # Current session
        log_queue.put((0, "log", "Legacy format log"))  # Legacy format (always processed)
        
        result = manager_with_docker.process_queue()
        
        assert result["processed"] == 2
        assert result["matched"] == 2
        assert result["lines"] == ["Current session log", "Legacy format log"]

    def test_process_queue_legacy_format(self, manager_with_docker):
        """Test processing legacy format messages (without session ID)."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        
        # Add legacy format message
        log_queue.put(("log", "Legacy log line"))
        
        result = manager_with_docker.process_queue()
        
        assert result["processed"] == 1
        assert result["matched"] == 1
        assert result["lines"] == ["Legacy log line"]

    def test_process_queue_exception_handling(self, manager_with_docker):
        """Test exception handling in process queue."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        manager_with_docker.current_session_id = 1
        
        # Add a corrupted item that will cause an exception when unpacking
        log_queue.put("corrupted_item")  # This can't be unpacked into 3 values
        
        with patch("DockTUI.ui.viewers.log_stream_manager.logger") as mock_logger:
            result = manager_with_docker.process_queue(max_items=5)
            
            # Should handle the exception gracefully
            assert result["processed"] == 0
            assert result["matched"] == 0
            assert result["lines"] == []
            
            # Should log the error
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args
            assert "Error processing log queue item" in error_call[0][0]

    def test_update_settings(self, manager_with_docker):
        """Test updating log settings."""
        manager_with_docker.update_settings(tail="500", since="1h")
        
        assert manager_with_docker.log_tail == "500"
        assert manager_with_docker.log_since == "1h"

    def test_update_settings_partial(self, manager_with_docker):
        """Test updating partial settings."""
        original_tail = manager_with_docker.log_tail
        original_since = manager_with_docker.log_since
        
        # Update only tail
        manager_with_docker.update_settings(tail="300")
        assert manager_with_docker.log_tail == "300"
        assert manager_with_docker.log_since == original_since
        
        # Update only since
        manager_with_docker.update_settings(since="30m")
        assert manager_with_docker.log_tail == "300"
        assert manager_with_docker.log_since == "30m"

    def test_is_container_stopped(self, manager_with_docker):
        """Test container stopped status detection."""
        assert manager_with_docker.is_container_stopped("Exited (0) 2 hours ago")
        assert manager_with_docker.is_container_stopped("Stopped")
        assert manager_with_docker.is_container_stopped("Created")
        assert manager_with_docker.is_container_stopped("EXITED (1)")
        
        assert not manager_with_docker.is_container_stopped("Up 2 hours")
        assert not manager_with_docker.is_container_stopped("Running")
        assert not manager_with_docker.is_container_stopped("Restarting")

    def test_is_container_running(self, manager_with_docker):
        """Test container running status detection."""
        assert manager_with_docker.is_container_running("Up 2 hours")
        assert manager_with_docker.is_container_running("Running")
        assert manager_with_docker.is_container_running("Up 10 seconds")
        assert manager_with_docker.is_container_running("RUNNING")
        
        assert not manager_with_docker.is_container_running("Exited (0)")
        assert not manager_with_docker.is_container_running("Stopped")
        assert not manager_with_docker.is_container_running("Restarting")

    def test_get_current_item(self, manager_with_docker):
        """Test getting current item."""
        assert manager_with_docker.get_current_item() is None
        
        manager_with_docker.current_item = ("container", "test_id")
        assert manager_with_docker.get_current_item() == ("container", "test_id")

    def test_clear(self, manager_with_docker):
        """Test clearing the manager state."""
        # Set up some state
        manager_with_docker.current_item = ("container", "test_id")
        manager_with_docker.current_item_data = {"name": "test"}
        manager_with_docker.waiting_for_logs = True
        manager_with_docker.initial_log_check_done = True
        manager_with_docker.showing_no_logs_message = True
        manager_with_docker.showing_loading_message = True
        manager_with_docker.showing_no_matches_message = True
        manager_with_docker.logs_loading = True
        
        mock_streamer = manager_with_docker.log_streamer
        
        # Clear the state
        manager_with_docker.clear()
        
        # Verify stop_streaming was called
        mock_streamer.stop_streaming.assert_called_once_with(wait=True)
        
        # Verify all state was reset
        assert manager_with_docker.current_item is None
        assert manager_with_docker.current_item_data is None
        assert manager_with_docker.waiting_for_logs is False
        assert manager_with_docker.initial_log_check_done is False
        assert manager_with_docker.showing_no_logs_message is False
        assert manager_with_docker.showing_loading_message is False
        assert manager_with_docker.showing_no_matches_message is False
        assert manager_with_docker.logs_loading is False

    def test_clear_no_streamer(self, manager_without_docker):
        """Test clearing when no streamer is available."""
        # Should not raise exception
        manager_without_docker.clear()

    def test_process_queue_max_items_limit(self, manager_with_docker):
        """Test that process_queue respects max_items limit."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        manager_with_docker.current_session_id = 1
        
        # Add more items than max_items
        for i in range(10):
            log_queue.put((1, "log", f"Log line {i}"))
        
        # Process with max_items=5
        result = manager_with_docker.process_queue(max_items=5)
        
        assert result["processed"] == 5
        assert result["matched"] == 5
        assert len(result["lines"]) == 5
        assert result["lines"] == ["Log line 0", "Log line 1", "Log line 2", "Log line 3", "Log line 4"]
        
        # Queue should still have remaining items
        assert not log_queue.empty()

    def test_mixed_message_types(self, manager_with_docker):
        """Test processing mixed message types in queue."""
        log_queue = manager_with_docker.log_streamer.get_queue()
        manager_with_docker.current_session_id = 1
        
        # Add mixed messages
        log_queue.put((1, "log", "Log line 1"))
        log_queue.put((1, "error", "Error occurred"))
        log_queue.put((1, "log", "Log line 2"))
        log_queue.put((1, "no_logs", ""))
        
        result = manager_with_docker.process_queue()
        
        assert result["processed"] == 4
        assert result["matched"] == 2
        assert result["lines"] == ["Log line 1", "Log line 2"]
        assert result["errors"] == ["Error occurred"]
        assert result["no_logs"] is True