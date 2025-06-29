"""Tests for the DockerActions mixin class."""

import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from DockTUI.ui.actions.docker_actions import DockerActions

if TYPE_CHECKING:
    from DockTUI.app import DockTUIApp


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

    def set_timer(self, delay, callback):
        """Mock set_timer method."""
        self._timers.append((delay, callback))

    def call_from_thread(self, func, *args, **kwargs):
        """Mock call_from_thread method."""
        func(*args, **kwargs)
    
    def post_message(self, message):
        """Mock post_message method."""
        pass
    
    def _is_volume_removable(self, volume_data):
        """Mock _is_volume_removable method."""
        if not volume_data:
            return False, "No volume data available"
        if volume_data.get("in_use", False):
            container_count = volume_data.get("container_count", 0)
            return False, f"Cannot remove volume: in use by {container_count} container(s)"
        return True, ""


class TestDockerActions:
    """Test cases for the DockerActions mixin."""

    def test_init(self):
        """Test initialization of DockerActions."""
        app = MockDockTUIApp()
        assert app._recreating_container_name is None
        assert app._recreating_item_type is None

    def test_is_action_applicable_no_selection(self):
        """Test is_action_applicable with no selection."""
        app = MockDockTUIApp()
        app.container_list.selected_item = None

        result = app.is_action_applicable("start")

        assert result is False
        app.error_display.update.assert_called_once_with("No item selected to start")

    def test_is_action_applicable_down_on_container(self):
        """Test is_action_applicable for down command on container."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")

        result = app.is_action_applicable("down")

        assert result is False
        app.error_display.update.assert_called_once_with(
            "Down command only works on stacks, not individual containers"
        )

    def test_is_action_applicable_down_on_stack(self):
        """Test is_action_applicable for down command on stack."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")

        result = app.is_action_applicable("down")

        assert result is True

    def test_is_action_applicable_recreate_stack_no_compose_file(self):
        """Test is_action_applicable for recreate on stack without compose file."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {
            "name": "test-stack",
            "can_recreate": False,
        }

        result = app.is_action_applicable("recreate")

        assert result is False
        app.error_display.update.assert_called_once_with(
            "Cannot recreate stack 'test-stack': compose file not accessible"
        )

    def test_is_action_applicable_recreate_stack_with_compose_file(self):
        """Test is_action_applicable for recreate on stack with compose file."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {
            "name": "test-stack",
            "can_recreate": True,
        }

        result = app.is_action_applicable("recreate")

        assert result is True

    def test_is_action_applicable_container_actions(self):
        """Test is_action_applicable for container actions."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")

        for action in ["start", "stop", "restart", "recreate"]:
            result = app.is_action_applicable(action)
            assert result is True

    @patch("DockTUI.ui.actions.docker_actions.threading.Thread")
    def test_execute_docker_command_container_start(self, mock_thread):
        """Test execute_docker_command for container start."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"name": "my-container"}
        app.docker.execute_container_command.return_value = (True, "")

        # Mock the thread
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app.execute_docker_command("start")

        # Verify UI updates
        app.container_list.update_container_status.assert_called_once_with(
            "test-container", "starting..."
        )
        app.refresh.assert_called_once()

        # Verify thread was started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        assert mock_thread_instance.daemon is True

    @patch("DockTUI.ui.actions.docker_actions.threading.Thread")
    def test_execute_docker_command_container_stop(self, mock_thread):
        """Test execute_docker_command for container stop."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"name": "my-container"}
        app.docker.execute_container_command.return_value = (True, "")

        # Mock the thread
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app.execute_docker_command("stop")

        # Verify UI updates
        app.container_list.update_container_status.assert_called_once_with(
            "test-container", "stopping..."
        )
        app.refresh.assert_called_once()

        # Verify thread was started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    @patch("DockTUI.ui.actions.docker_actions.threading.Thread")
    def test_execute_docker_command_container_recreate(self, mock_thread):
        """Test execute_docker_command for container recreate."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"name": "my-container"}
        app.docker.execute_container_command.return_value = (True, "")

        # Mock the thread
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        app.execute_docker_command("recreate")

        # Verify recreate tracking
        assert app._recreating_item_type == "container"
        assert app._recreating_container_name == "my-container"

        # Verify UI updates
        app.container_list.update_container_status.assert_called_once_with(
            "test-container", "recreating..."
        )

    def test_execute_docker_command_stack_start(self):
        """Test execute_docker_command for stack start."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {
            "name": "my-stack",
            "config_file": "/path/to/compose.yml",
        }
        app.docker.execute_stack_command.return_value = True

        app.execute_docker_command("start")

        app.docker.execute_stack_command.assert_called_once_with(
            "my-stack", "/path/to/compose.yml", "start"
        )
        app.error_display.update.assert_called_with("Starting stack: my-stack")

        # Check that timer was set
        assert len(app._timers) == 2  # One for message clear, one for refresh

    def test_execute_docker_command_stack_down(self):
        """Test execute_docker_command for stack down."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {
            "name": "my-stack",
            "config_file": "/path/to/compose.yml",
        }
        app.docker.execute_stack_command.return_value = True

        app.execute_docker_command("down")

        app.docker.execute_stack_command.assert_called_once_with(
            "my-stack", "/path/to/compose.yml", "down"
        )
        app.error_display.update.assert_called_with("Taking down stack: my-stack")

    def test_execute_docker_command_stack_down_with_volumes(self):
        """Test execute_docker_command for stack down with volumes."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {
            "name": "my-stack",
            "config_file": "/path/to/compose.yml",
        }
        app.docker.execute_stack_command.return_value = True

        app.execute_docker_command("down_remove_volumes")

    def test_execute_volume_command_remove_success(self):
        """Test successful volume removal command."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("volume", "test-volume")
        app.container_list.volume_manager = Mock()
        app.container_list.volume_manager.selected_volume_data = {
            "name": "test-volume",
            "in_use": False
        }
        app.container_list.volume_manager.remove_volume = Mock()
        app.docker.remove_volume.return_value = (True, "Volume removed successfully")

        app.execute_volume_command("remove_volume")

        # The remove_volume operation will be called in a thread, so we need to wait
        # Since we can't easily wait for threads in tests, just check the immediate feedback
        app.error_display.update.assert_called_with("Removing volume 'test-volume'...")

    def test_execute_volume_command_remove_in_use(self):
        """Test volume removal when volume is in use."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("volume", "test-volume")
        app.container_list.volume_manager = Mock()
        app.container_list.volume_manager.selected_volume_data = {
            "name": "test-volume",
            "in_use": True,
            "container_names": ["container1", "container2"],
            "container_count": 2
        }

        app.execute_volume_command("remove_volume")

        app.docker.remove_volume.assert_not_called()
        app.error_display.update.assert_called_with(
            "Cannot remove volume: in use by 2 container(s)"
        )

    def test_execute_volume_command_no_selection(self):
        """Test volume removal with no selection."""
        app = MockDockTUIApp()
        app.container_list.selected_item = None

        app.execute_volume_command("remove_volume")

        app.error_display.update.assert_called_with("No volume selected")

    def test_execute_volume_command_wrong_type(self):
        """Test volume removal when non-volume is selected."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")

        app.execute_volume_command("remove_volume")

        app.error_display.update.assert_called_with("Selected item is not a volume")

    def test_execute_volume_command_remove_unused_success(self):
        """Test successful removal of unused volumes."""
        app = MockDockTUIApp()
        unused_volumes = [
            {"name": "vol1", "in_use": False},
            {"name": "vol2", "in_use": False}
        ]
        app.docker.get_unused_volumes.return_value = unused_volumes
        app.docker.remove_unused_volumes.return_value = (
            True, "Removed 2 volumes, freed 100 MB", 2
        )
        app.container_list.volume_manager = Mock()

        app.execute_volume_command("remove_unused_volumes")

        # The operation will be called in a thread, so check immediate feedback
        app.error_display.update.assert_called_with("Removing 2 unused volumes...")

    def test_execute_volume_command_remove_unused_none(self):
        """Test remove unused volumes when none exist."""
        app = MockDockTUIApp()
        app.docker.get_unused_volumes.return_value = []

        app.execute_volume_command("remove_unused_volumes")

        app.docker.remove_unused_volumes.assert_not_called()
        app.error_display.update.assert_called_with("No unused volumes found")

    def test_execute_docker_command_stack_recreate(self):
        """Test execute_docker_command for stack recreate."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {
            "name": "my-stack",
            "config_file": "/path/to/compose.yml",
        }
        app.docker.execute_stack_command.return_value = True

        app.execute_docker_command("recreate")

        # Verify recreate tracking
        assert app._recreating_item_type == "stack"
        assert app._recreating_container_name == "my-stack"

        app.docker.execute_stack_command.assert_called_once_with(
            "my-stack", "/path/to/compose.yml", "recreate"
        )

    def test_execute_docker_command_no_stack_data(self):
        """Test execute_docker_command with missing stack data."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = None

        app.execute_docker_command("start")

        app.error_display.update.assert_called_once_with(
            "Missing stack data for test-stack"
        )
        app.docker.execute_stack_command.assert_not_called()

    def test_execute_docker_command_unknown_type(self):
        """Test execute_docker_command with unknown item type."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("unknown", "test-item")

        app.execute_docker_command("start")

        app.error_display.update.assert_called_once_with("Unknown item type: unknown")

    def test_execute_docker_command_failure(self):
        """Test execute_docker_command when docker command fails."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {
            "name": "my-stack",
            "config_file": "/path/to/compose.yml",
        }
        app.docker.execute_stack_command.return_value = False
        app.docker.last_error = "Permission denied"

        app.execute_docker_command("start")

        app.error_display.update.assert_called_with(
            "Error starting stack: Permission denied"
        )

    def test_execute_docker_command_exception(self):
        """Test execute_docker_command with exception."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"name": "my-container"}
        app.container_list.update_container_status.side_effect = Exception(
            "Test error"
        )

        app.execute_docker_command("start")

        app.error_display.update.assert_called_with("Error executing start: Test error")

    def test_handle_post_recreate_container(self):
        """Test handle_post_recreate for container."""
        app = MockDockTUIApp()
        app._recreating_container_name = "my-container"
        app._recreating_item_type = "container"

        containers = [
            {"id": "new-id-123", "name": "my-container"},
            {"id": "other-id", "name": "other-container"},
        ]

        new_id, new_data = app.handle_post_recreate(containers)

        assert new_id == "new-id-123"
        assert new_data == {"id": "new-id-123", "name": "my-container"}

        # Verify UI updates
        app.container_list.select_container.assert_called_once_with("new-id-123")
        app.log_pane.update_selection.assert_called_once_with(
            "container", "new-id-123", {"id": "new-id-123", "name": "my-container"}
        )

        # Verify tracking variables cleared
        assert app._recreating_container_name is None
        assert app._recreating_item_type is None

    def test_handle_post_recreate_stack(self):
        """Test handle_post_recreate for stack."""
        app = MockDockTUIApp()
        app._recreating_container_name = "my-stack"
        app._recreating_item_type = "stack"

        containers = []
        new_id, new_data = app.handle_post_recreate(containers)

        assert new_id is None
        assert new_data is None

        # Verify stack selection
        app.container_list.select_stack.assert_called_once_with("my-stack")

        # Verify tracking variables cleared
        assert app._recreating_container_name is None
        assert app._recreating_item_type is None

    def test_handle_post_recreate_no_tracking(self):
        """Test handle_post_recreate with no tracking variables."""
        app = MockDockTUIApp()
        app._recreating_container_name = None
        app._recreating_item_type = None

        containers = []
        new_id, new_data = app.handle_post_recreate(containers)

        assert new_id is None
        assert new_data is None

        # Verify no UI updates
        app.container_list.select_container.assert_not_called()
        app.container_list.select_stack.assert_not_called()

    def test_handle_post_recreate_no_log_pane(self):
        """Test handle_post_recreate when log_pane is None."""
        app = MockDockTUIApp()
        app._recreating_container_name = "my-container"
        app._recreating_item_type = "container"
        app.log_pane = None

        containers = []
        new_id, new_data = app.handle_post_recreate(containers)

        assert new_id is None
        assert new_data is None

    def test_handle_post_recreate_container_not_found(self):
        """Test handle_post_recreate when container not found."""
        app = MockDockTUIApp()
        app._recreating_container_name = "my-container"
        app._recreating_item_type = "container"

        containers = [
            {"id": "other-id", "name": "other-container"},
        ]

        new_id, new_data = app.handle_post_recreate(containers)

        assert new_id is None
        assert new_data is None

        # Verify no UI updates for container
        app.container_list.select_container.assert_not_called()

    def test_execute_image_command_remove_image_no_selection(self):
        """Test execute_image_command remove_image with no selection."""
        app = MockDockTUIApp()
        app.container_list.selected_item = None

        app.execute_image_command("remove_image")

        app.error_display.update.assert_called_once_with("No image selected")

    def test_execute_image_command_remove_image_wrong_type(self):
        """Test execute_image_command remove_image with wrong item type."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")

        app.execute_image_command("remove_image")

        app.error_display.update.assert_called_once_with(
            "Selected item is not an image"
        )

    def test_execute_image_command_remove_image_no_data(self):
        """Test execute_image_command remove_image with no image data."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = None

        app.execute_image_command("remove_image")

        app.error_display.update.assert_called_once_with("No image data available")

    def test_execute_image_command_remove_image_in_use(self):
        """Test execute_image_command remove_image when image is in use."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = {
            "container_names": ["container1", "container2"]
        }

        app.execute_image_command("remove_image")

        app.error_display.update.assert_called_once_with(
            "Cannot remove image: in use by 2 container(s)"
        )

    def test_execute_image_command_remove_image_success(self):
        """Test execute_image_command remove_image successful removal."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = {"container_names": []}
        app.container_list.image_manager.get_next_selection_after_removal.return_value = (
            "next-image"
        )
        app.docker.remove_image.return_value = (True, "Image removed successfully")

        app.execute_image_command("remove_image")

        app.docker.remove_image.assert_called_once_with("test-image")
        app.error_display.update.assert_called_once_with("Image removed successfully")
        app.container_list.image_manager.mark_image_as_removed.assert_called_once_with(
            "test-image"
        )
        app.container_list.image_manager.select_image.assert_called_once_with(
            "next-image"
        )
        assert (
            app.container_list.image_manager._preserve_selected_image_id == "next-image"
        )

        # Check timer was set
        assert len(app._timers) == 1
        assert app._timers[0][0] == 2.0

    def test_execute_image_command_remove_image_failure(self):
        """Test execute_image_command remove_image failed removal."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = {"container_names": []}
        app.docker.remove_image.return_value = (False, "Permission denied")

        app.execute_image_command("remove_image")

        app.error_display.update.assert_called_once_with("Error: Permission denied")
        app.container_list.image_manager.mark_image_as_removed.assert_not_called()

    def test_execute_image_command_remove_unused_images_none_found(self):
        """Test execute_image_command remove_unused_images when none found."""
        app = MockDockTUIApp()
        app.docker.get_unused_images.return_value = []

        app.execute_image_command("remove_unused_images")

        app.error_display.update.assert_called_once_with("No unused images found")

    def test_execute_image_command_remove_unused_images_success(self):
        """Test execute_image_command remove_unused_images successful removal."""
        app = MockDockTUIApp()
        app.container_list.image_manager = Mock()
        unused_images = [
            {"id": "image1"},
            {"id": "image2"},
            {"id": "image3"},
        ]
        app.docker.get_unused_images.return_value = unused_images
        app.container_list.image_manager.get_next_selection_after_removal.return_value = (
            "next-image"
        )
        app.docker.remove_unused_images.return_value = (
            True,
            "Removed 3 unused images",
            3,
        )

        app.execute_image_command("remove_unused_images")

        app.docker.remove_unused_images.assert_called_once()
        app.error_display.update.assert_called_once_with("Removed 3 unused images")

        # Verify all images marked as removed
        expected_calls = [call("image1"), call("image2"), call("image3")]
        app.container_list.image_manager.mark_image_as_removed.assert_has_calls(
            expected_calls
        )

        # Verify selection update
        app.container_list.image_manager.select_image.assert_called_once_with(
            "next-image"
        )
        assert (
            app.container_list.image_manager._preserve_selected_image_id == "next-image"
        )

    def test_execute_image_command_remove_unused_images_failure(self):
        """Test execute_image_command remove_unused_images failed removal."""
        app = MockDockTUIApp()
        app.container_list.image_manager = Mock()
        unused_images = [{"id": "image1"}]
        app.docker.get_unused_images.return_value = unused_images
        app.docker.remove_unused_images.return_value = (
            False,
            "Permission denied",
            0,
        )

        app.execute_image_command("remove_unused_images")

        app.error_display.update.assert_called_once_with("Error: Permission denied")
        app.container_list.image_manager.mark_image_as_removed.assert_not_called()

    def test_execute_image_command_remove_unused_images_no_next_selection(self):
        """Test execute_image_command remove_unused_images with no next selection."""
        app = MockDockTUIApp()
        app.container_list.image_manager = Mock()
        unused_images = [{"id": "image1"}]
        app.docker.get_unused_images.return_value = unused_images
        app.container_list.image_manager.get_next_selection_after_removal.return_value = (
            None
        )
        app.docker.remove_unused_images.return_value = (
            True,
            "Removed 1 unused image",
            1,
        )

        app.execute_image_command("remove_unused_images")

        # Verify no selection update when next_selection is None
        app.container_list.image_manager.select_image.assert_not_called()

    @patch("DockTUI.ui.actions.docker_actions.threading.Thread")
    def test_execute_docker_command_thread_execution(self, mock_thread):
        """Test that container commands execute in background thread properly."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"name": "my-container"}

        # Capture the target function when Thread is created
        target_func = None

        def capture_thread(*args, **kwargs):
            nonlocal target_func
            target_func = kwargs.get("target")
            thread_instance = MagicMock()
            thread_instance.daemon = False
            return thread_instance

        mock_thread.side_effect = capture_thread

        # Set up the docker command to return success
        app.docker.execute_container_command.return_value = (True, "")

        app.execute_docker_command("start")

        # Now execute the captured thread function
        assert target_func is not None
        target_func()

        # Verify docker command was called
        app.docker.execute_container_command.assert_called_once_with(
            "test-container", "start"
        )

        # Verify timer was set to clear status (there are 2 timers: one from thread, one from line 176)
        assert len(app._timers) == 2
        # Find the timer with 3 second delay (from the thread)
        timer_3s = [t for t in app._timers if t[0] == 3]
        assert len(timer_3s) == 1

        # Execute the 3 second timer callback
        timer_callback = timer_3s[0][1]
        timer_callback()

        # Verify status was cleared and refresh was called
        app.container_list.clear_status_override.assert_called_once_with(
            "test-container"
        )
        app.action_refresh.assert_called_once()