"""Tests for volume-related Docker actions."""

import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from DockTUI.ui.actions.docker_actions import DockerActions
from DockTUI.ui.base.container_list_base import DockerOperationCompleted


class MockDockTUIApp(DockerActions):
    """Mock DockTUIApp for testing DockerActions mixin."""

    def __init__(self):
        super().__init__()
        self.container_list = Mock()
        self.error_display = Mock()
        self.docker = Mock()
        self.log_pane = Mock()
        self._timers = []
        self.refresh = Mock()
        self.action_refresh = Mock()
        self.app = self  # DockerActions expects self.app for post_message
        self._posted_messages = []  # Track posted messages

    def set_timer(self, delay, callback):
        """Mock set_timer method."""
        self._timers.append((delay, callback))

    def call_from_thread(self, func, *args, **kwargs):
        """Mock call_from_thread method."""
        func(*args, **kwargs)

    def post_message(self, message):
        """Mock post_message method."""
        self._posted_messages.append(message)

    def _is_volume_removable(self, volume_data):
        """Mock _is_volume_removable method."""
        if not volume_data:
            return False, "No volume data available"
        if volume_data.get("in_use", False):
            container_count = volume_data.get("container_count", 0)
            return False, f"Cannot remove volume: in use by {container_count} container(s)"
        return True, ""


class TestVolumeActions:
    """Test cases for volume-related Docker actions."""

    def test_execute_volume_command_remove_volume_no_selection(self):
        """Test execute_volume_command remove_volume with no selection."""
        app = MockDockTUIApp()
        app.container_list = None

        app.execute_volume_command("remove_volume")

        app.error_display.update.assert_called_once_with("No volume selected")
        app.docker.remove_volume.assert_not_called()

    def test_execute_volume_command_remove_volume_wrong_selection_type(self):
        """Test execute_volume_command remove_volume with non-volume selection."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")

        app.execute_volume_command("remove_volume")

        app.error_display.update.assert_called_once_with("Selected item is not a volume")
        app.docker.remove_volume.assert_not_called()

    def test_execute_volume_command_remove_volume_in_use(self):
        """Test execute_volume_command remove_volume when volume is in use."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("volume", "test-volume")
        app.container_list.volume_manager.selected_volume_data = {
            "name": "test-volume",
            "in_use": True,
            "container_count": 2,
        }

        app.execute_volume_command("remove_volume")

        app.error_display.update.assert_called_once_with(
            "Cannot remove volume: in use by 2 container(s)"
        )
        app.docker.remove_volume.assert_not_called()

    @patch("DockTUI.ui.actions.docker_actions.threading.Thread")
    def test_execute_volume_command_remove_volume_success(self, mock_thread):
        """Test execute_volume_command remove_volume successful execution."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("volume", "test-volume")
        app.container_list.volume_manager.selected_volume_data = {
            "name": "test-volume",
            "in_use": False,
        }

        # Capture the thread target function
        target_func = None

        def capture_thread(*args, **kwargs):
            nonlocal target_func
            target_func = kwargs.get("target")
            thread_instance = MagicMock()
            thread_instance.daemon = False
            return thread_instance

        mock_thread.side_effect = capture_thread
        app.docker.remove_volume.return_value = (
            True,
            "Volume 'test-volume' removed successfully",
        )

        app.execute_volume_command("remove_volume")

        # Execute the captured thread function
        assert target_func is not None
        target_func()

        # Verify docker command was called
        app.docker.remove_volume.assert_called_once_with("test-volume")

        # Verify completion message was posted
        assert len(app._posted_messages) == 1
        msg = app._posted_messages[0]
        assert isinstance(msg, DockerOperationCompleted)
        assert msg.operation == "remove_volume"
        assert msg.success is True
        assert msg.message == "Volume 'test-volume' removed successfully"
        assert msg.item_id == "test-volume"

        # Verify immediate feedback
        app.error_display.update.assert_called_with("Removing volume 'test-volume'...")

    def test_execute_volume_command_remove_unused_volumes_none_found(self):
        """Test execute_volume_command remove_unused_volumes when no unused volumes."""
        app = MockDockTUIApp()
        app.docker.get_unused_volumes.return_value = []

        app.execute_volume_command("remove_unused_volumes")

        app.error_display.update.assert_called_once_with("No unused volumes found")
        app.docker.remove_unused_volumes.assert_not_called()

    @patch("DockTUI.ui.actions.docker_actions.threading.Thread")
    def test_execute_volume_command_remove_unused_volumes_success(self, mock_thread):
        """Test execute_volume_command remove_unused_volumes successful execution."""
        app = MockDockTUIApp()
        unused_volumes = [
            {"name": "volume1"},
            {"name": "volume2"},
            {"name": "volume3"},
        ]
        app.docker.get_unused_volumes.return_value = unused_volumes

        # Capture the thread target function
        target_func = None

        def capture_thread(*args, **kwargs):
            nonlocal target_func
            target_func = kwargs.get("target")
            thread_instance = MagicMock()
            thread_instance.daemon = False
            return thread_instance

        mock_thread.side_effect = capture_thread
        app.docker.remove_unused_volumes.return_value = (
            True,
            "Successfully removed 3 unused volumes, freed 100 MB",
            3,
        )

        app.execute_volume_command("remove_unused_volumes")

        # Execute the captured thread function
        assert target_func is not None
        target_func()

        # Verify docker command was called
        app.docker.remove_unused_volumes.assert_called_once()

        # Verify completion message was posted
        assert len(app._posted_messages) == 1
        msg = app._posted_messages[0]
        assert isinstance(msg, DockerOperationCompleted)
        assert msg.operation == "remove_unused_volumes"
        assert msg.success is True
        assert msg.message == "Successfully removed 3 unused volumes, freed 100 MB"
        assert msg.item_ids == ["volume1", "volume2", "volume3"]

        # Verify immediate feedback
        app.error_display.update.assert_called_with("Removing 3 unused volumes...")

    def test_execute_volume_command_concurrent_operations_blocked(self):
        """Test that concurrent volume operations are blocked."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("volume", "test-volume")
        app.container_list.volume_manager.selected_volume_data = {
            "name": "test-volume",
            "in_use": False,
        }

        # Simulate an operation already in progress
        app._volume_operation_in_progress = True

        app.execute_volume_command("remove_volume")

        app.error_display.update.assert_called_once_with(
            "A volume operation is already in progress"
        )
        app.docker.remove_volume.assert_not_called()

    @patch("DockTUI.ui.actions.docker_actions.threading.Thread")
    def test_execute_volume_command_error_clears_flag(self, mock_thread):
        """Test that errors in thread properly clear the operation flag."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("volume", "test-volume")
        app.container_list.volume_manager.selected_volume_data = {
            "name": "test-volume",
            "in_use": False,
        }

        # Capture the thread target function
        target_func = None

        def capture_thread(*args, **kwargs):
            nonlocal target_func
            target_func = kwargs.get("target")
            thread_instance = MagicMock()
            thread_instance.daemon = False
            return thread_instance

        mock_thread.side_effect = capture_thread
        app.docker.remove_volume.side_effect = Exception("Docker API error")

        app.execute_volume_command("remove_volume")

        # Verify flag was set
        assert app._volume_operation_in_progress is True

        # Execute the captured thread function with exception
        with pytest.raises(Exception):
            target_func()

        # Verify flag was cleared even with exception
        assert app._volume_operation_in_progress is False

    def test_is_volume_removable(self):
        """Test _is_volume_removable method logic."""
        app = MockDockTUIApp()

        # Test with None data
        can_remove, msg = app._is_volume_removable(None)
        assert can_remove is False
        assert msg == "No volume data available"

        # Test with in-use volume
        volume_data = {"in_use": True, "container_count": 3}
        can_remove, msg = app._is_volume_removable(volume_data)
        assert can_remove is False
        assert msg == "Cannot remove volume: in use by 3 container(s)"

        # Test with removable volume
        volume_data = {"in_use": False}
        can_remove, msg = app._is_volume_removable(volume_data)
        assert can_remove is True
        assert msg == ""