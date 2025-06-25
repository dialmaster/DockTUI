import queue
import threading
import time
from unittest.mock import MagicMock, Mock, call, patch

import docker
import pytest

from dockerview.services.log_streamer import LogStreamer


class TestLogStreamer:
    @pytest.fixture
    def mock_docker_client(self):
        """Create a mock Docker client."""
        return Mock(spec=docker.DockerClient)

    @pytest.fixture
    def log_streamer(self, mock_docker_client):
        """Create a LogStreamer instance with mock client."""
        return LogStreamer(mock_docker_client)

    def test_init(self, mock_docker_client):
        """Test LogStreamer initialization."""
        streamer = LogStreamer(mock_docker_client)
        assert streamer.docker_client == mock_docker_client
        assert streamer.log_thread is None
        assert isinstance(streamer.stop_event, threading.Event)
        assert isinstance(streamer.log_queue, queue.Queue)
        assert streamer.log_session_id == 0

    def test_get_queue(self, log_streamer):
        """Test getting the log queue."""
        assert log_streamer.get_queue() is log_streamer.log_queue

    def test_start_streaming_container(self, log_streamer):
        """Test starting a container log stream."""
        with patch.object(threading, "Thread") as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread

            session_id = log_streamer.start_streaming(
                "container", "test_container_id", {}, tail="100", since="10m"
            )

            assert session_id == 1
            assert log_streamer.log_session_id == 1
            mock_thread_class.assert_called_once()
            mock_thread.start.assert_called_once()
            assert not log_streamer.stop_event.is_set()

    def test_start_streaming_stack(self, log_streamer):
        """Test starting a stack log stream."""
        with patch.object(threading, "Thread") as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread

            session_id = log_streamer.start_streaming(
                "stack", "test_stack", {"name": "test_stack"}
            )

            assert session_id == 1
            mock_thread.start.assert_called_once()

    def test_stop_streaming(self, log_streamer):
        """Test stopping log streaming."""
        # Setup a mock thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        log_streamer.log_thread = mock_thread

        # Add some items to the queue
        log_streamer.log_queue.put("item1")
        log_streamer.log_queue.put("item2")

        log_streamer.stop_streaming(wait=True)

        assert log_streamer.stop_event.is_set()
        mock_thread.join.assert_called_once_with(timeout=2)
        assert log_streamer.log_queue.empty()

    def test_stop_streaming_no_wait(self, log_streamer):
        """Test stopping log streaming without waiting."""
        mock_thread = Mock()
        log_streamer.log_thread = mock_thread

        log_streamer.stop_streaming(wait=False)

        assert log_streamer.stop_event.is_set()
        mock_thread.join.assert_not_called()

    def test_convert_since_to_timestamp(self, log_streamer):
        """Test converting time strings to timestamps."""
        current_time = int(time.time())

        # Test minutes
        with patch("time.time", return_value=current_time):
            result = log_streamer._convert_since_to_timestamp("5m")
            assert result == current_time - (5 * 60)

        # Test hours
        with patch("time.time", return_value=current_time):
            result = log_streamer._convert_since_to_timestamp("2h")
            assert result == current_time - (2 * 3600)

        # Test days
        with patch("time.time", return_value=current_time):
            result = log_streamer._convert_since_to_timestamp("1d")
            assert result == current_time - (1 * 86400)

        # Test invalid format (defaults to 15 minutes)
        with patch("time.time", return_value=current_time):
            result = log_streamer._convert_since_to_timestamp("invalid")
            assert result == current_time - (15 * 60)

    def test_log_worker_container(self, log_streamer):
        """Test log worker for container type."""
        with patch.object(log_streamer, "_stream_container_logs") as mock_stream:
            log_streamer._log_worker(
                "container", "test_id", {}, "100", "10m", 1
            )
            mock_stream.assert_called_once_with("test_id", "100", "10m", 1)

    def test_log_worker_stack(self, log_streamer):
        """Test log worker for stack type."""
        with patch.object(log_streamer, "_stream_stack_logs") as mock_stream:
            item_data = {"name": "test_stack"}
            log_streamer._log_worker(
                "stack", "test_id", item_data, "100", "10m", 1
            )
            mock_stream.assert_called_once_with(item_data, "100", "10m", 1)

    def test_log_worker_unknown_type(self, log_streamer):
        """Test log worker with unknown item type."""
        log_streamer._log_worker("unknown", "test_id", {}, "100", "10m", 1)
        
        # Check that error was queued
        assert not log_streamer.log_queue.empty()
        session_id, msg_type, msg = log_streamer.log_queue.get()
        assert session_id == 1
        assert msg_type == "error"
        assert "Unknown item type: unknown" in msg

    def test_log_worker_exception(self, log_streamer):
        """Test log worker exception handling."""
        with patch.object(log_streamer, "_stream_container_logs") as mock_stream:
            mock_stream.side_effect = Exception("Test error")
            
            log_streamer._log_worker(
                "container", "test_id", {}, "100", "10m", 1
            )
            
            # Check that error was queued
            assert not log_streamer.log_queue.empty()
            session_id, msg_type, msg = log_streamer.log_queue.get()
            assert session_id == 1
            assert msg_type == "error"
            assert "Error streaming logs: Test error" in msg

    @patch("dockerview.services.log_streamer.strip_ansi_codes")
    def test_stream_container_logs_success(self, mock_strip_ansi, log_streamer, mock_docker_client):
        """Test successful container log streaming."""
        # Setup mocks
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        # Mock initial log check
        mock_container.logs.side_effect = [
            b"Initial log\n",  # First call for checking
            [b"Log line 1\n", b"Log line 2\n"]  # Second call for streaming
        ]
        
        mock_strip_ansi.side_effect = lambda x: x  # Return input unchanged
        
        # Start streaming in a thread
        log_streamer.stop_event.clear()
        
        # Run the method
        threading.Thread(
            target=log_streamer._stream_container_logs,
            args=("test_container", "100", "10m", 1),
            daemon=True
        ).start()
        
        # Give thread time to process
        time.sleep(0.1)
        log_streamer.stop_event.set()
        
        # Verify Docker API calls
        mock_docker_client.containers.get.assert_called_once_with("test_container")
        assert mock_container.logs.call_count == 2

    def test_stream_container_logs_not_found(self, log_streamer, mock_docker_client):
        """Test container not found error."""
        mock_docker_client.containers.get.side_effect = docker.errors.NotFound("Not found")
        
        log_streamer._stream_container_logs("test_container", "100", "10m", 1)
        
        # Check error was queued
        assert not log_streamer.log_queue.empty()
        session_id, msg_type, msg = log_streamer.log_queue.get()
        assert session_id == 1
        assert msg_type == "error"
        assert "Container test_container not found" in msg

    def test_stream_container_logs_no_logs(self, log_streamer, mock_docker_client):
        """Test handling when container has no logs."""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        # Mock no initial logs
        mock_container.logs.side_effect = [
            b"",  # Empty initial check
            []  # Empty stream
        ]
        
        with patch.object(log_streamer, "_check_no_logs_found") as mock_check:
            log_streamer._stream_container_logs("test_container", "100", "10m", 1)
            mock_check.assert_called_once_with(1)

    def test_stream_stack_logs_success(self, log_streamer, mock_docker_client):
        """Test successful stack log streaming."""
        # Setup mock containers
        mock_container1 = Mock()
        mock_container1.id = "container1"
        mock_container1.name = "app1"
        mock_container1.logs.return_value = [b"App1 log\n"]
        
        mock_container2 = Mock()
        mock_container2.id = "container2"
        mock_container2.name = "app2"
        mock_container2.logs.return_value = [b"App2 log\n"]
        
        mock_docker_client.containers.list.return_value = [mock_container1, mock_container2]
        
        # Start streaming
        threading.Thread(
            target=log_streamer._stream_stack_logs,
            args=({"name": "test_stack"}, "100", "10m", 1),
            daemon=True
        ).start()
        
        # Give thread time to start
        time.sleep(0.1)
        log_streamer.stop_event.set()
        
        # Verify Docker API calls
        mock_docker_client.containers.list.assert_called_once_with(
            all=True, filters={"label": "com.docker.compose.project=test_stack"}
        )

    def test_stream_stack_logs_no_containers(self, log_streamer, mock_docker_client):
        """Test stack with no containers."""
        mock_docker_client.containers.list.return_value = []
        
        log_streamer._stream_stack_logs({"name": "test_stack"}, "100", "10m", 1)
        
        # Check error was queued
        assert not log_streamer.log_queue.empty()
        session_id, msg_type, msg = log_streamer.log_queue.get()
        assert session_id == 1
        assert msg_type == "error"
        assert "No containers found for stack test_stack" in msg

    def test_stream_stack_logs_duplicate_containers(self, log_streamer, mock_docker_client):
        """Test handling duplicate containers in stack."""
        # Create containers with same ID
        mock_container1 = Mock()
        mock_container1.id = "container1"
        mock_container1.name = "app1"
        
        mock_container2 = Mock()
        mock_container2.id = "container1"  # Same ID as container1
        mock_container2.name = "app1_duplicate"
        
        mock_docker_client.containers.list.return_value = [
            mock_container1, mock_container2, mock_container1
        ]
        
        with patch.object(log_streamer, "_check_no_logs_found"):
            # Mock logs method to prevent actual streaming
            mock_container1.logs.return_value = []
            
            log_streamer._stream_stack_logs({"name": "test_stack"}, "100", "10m", 1)
            
            # Should only try to get logs from unique container
            assert mock_container1.logs.called

    def test_check_no_logs_found(self, log_streamer):
        """Test the no logs found notification."""
        log_streamer._check_no_logs_found(42)
        
        assert not log_streamer.log_queue.empty()
        session_id, msg_type, msg = log_streamer.log_queue.get()
        assert session_id == 42
        assert msg_type == "no_logs"
        assert msg == ""

    def test_multiple_sessions(self, log_streamer):
        """Test multiple streaming sessions with incrementing IDs."""
        with patch.object(threading, "Thread"):
            session1 = log_streamer.start_streaming("container", "c1", {})
            assert session1 == 1
            
            session2 = log_streamer.start_streaming("container", "c2", {})
            assert session2 == 2
            
            session3 = log_streamer.start_streaming("stack", "s1", {"name": "stack1"})
            assert session3 == 3

    @patch("dockerview.services.log_streamer.strip_ansi_codes")
    def test_ansi_code_stripping(self, mock_strip_ansi, log_streamer, mock_docker_client):
        """Test ANSI code stripping in logs."""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        # Mock logs with ANSI codes
        ansi_log = b"\x1b[31mRed text\x1b[0m\n"
        mock_container.logs.side_effect = [
            ansi_log,  # Initial check
            [ansi_log]  # Stream
        ]
        
        # Mock strip_ansi_codes to remove ANSI
        mock_strip_ansi.return_value = "Red text"
        
        log_streamer._stream_container_logs("test_container", "100", "10m", 1)
        
        # Verify strip_ansi_codes was called
        assert mock_strip_ansi.called

    def test_empty_line_handling(self, log_streamer, mock_docker_client):
        """Test handling of empty lines in logs."""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        # Mock logs with empty lines
        mock_container.logs.side_effect = [
            b"Not empty\n",  # Initial check
            [b"\n", b"  \n", b"Text\n", b"\n"]  # Stream with empty lines
        ]
        
        with patch("dockerview.services.log_streamer.strip_ansi_codes") as mock_strip:
            mock_strip.side_effect = lambda x: x.strip()
            
            log_streamer._stream_container_logs("test_container", "100", "10m", 1)
            
            # Should have queued lines including empty ones
            messages = []
            while not log_streamer.log_queue.empty():
                messages.append(log_streamer.log_queue.get())
            
            # Should include empty lines that were empty before ANSI stripping
            log_messages = [msg for _, msg_type, msg in messages if msg_type == "log"]
            assert len(log_messages) >= 3  # At least the non-empty lines