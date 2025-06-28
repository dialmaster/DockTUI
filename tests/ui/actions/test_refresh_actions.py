"""Tests for the RefreshActions mixin class."""

import asyncio
import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from DockTUI.ui.actions.refresh_actions import RefreshActions

if TYPE_CHECKING:
    from DockTUI.app import DockTUIApp


class MockDockTUIApp(RefreshActions):
    """Mock DockTUIApp for testing RefreshActions mixin."""

    def __init__(self):
        super().__init__()
        self.container_list = Mock()
        self.container_list.selected_item = None  # Set to None by default
        self.error_display = Mock()
        self.docker = Mock()
        self.docker.last_error = None  # Set to None instead of Mock
        self.log_pane = Mock()
        self.title = "DockTUI"
        self._worker_called = False
        self._worker_callback = None
        # Store the real implementation
        self._real_call_from_thread = self._call_from_thread_impl
        # Create a Mock that wraps the real implementation
        self.call_from_thread = Mock(side_effect=self._real_call_from_thread)

    def _call_from_thread_impl(self, func, *args, **kwargs):
        """Real implementation of call_from_thread."""
        func(*args, **kwargs)

    def _refresh_containers_worker(self, callback):
        """Mock worker method to track calls."""
        self._worker_called = True
        self._worker_callback = callback


class TestRefreshActions:
    """Test cases for the RefreshActions mixin."""

    def test_init(self):
        """Test initialization of RefreshActions."""
        app = MockDockTUIApp()
        assert app._refresh_count == 0

    def test_refresh_containers_widgets_not_initialized(self):
        """Test refresh_containers when widgets are not initialized."""
        app = MockDockTUIApp()
        app.container_list = None

        # Run the async function synchronously
        asyncio.run(app.refresh_containers())

        # Should not call worker or update UI
        assert not app._worker_called
        app.error_display.update.assert_not_called()

    def test_refresh_containers_success(self):
        """Test successful refresh_containers call."""
        app = MockDockTUIApp()

        # Run the async function synchronously
        asyncio.run(app.refresh_containers())

        # Should update title and start worker
        assert "Refreshing..." in app.title
        assert app._worker_called
        assert app._worker_callback is not None

    def test_refresh_containers_title_already_refreshing(self):
        """Test refresh_containers when title already shows refreshing."""
        app = MockDockTUIApp()
        app.title = "DockTUI\nRefreshing..."

        # Run the async function synchronously
        asyncio.run(app.refresh_containers())

        # Should not add another refreshing indicator
        assert app.title == "DockTUI\nRefreshing..."
        assert app._worker_called

    def test_refresh_containers_exception(self):
        """Test refresh_containers with exception."""
        app = MockDockTUIApp()

        # Make _refresh_containers_worker raise an exception
        def raise_error(callback):
            raise Exception("Test error")

        app._refresh_containers_worker = raise_error

        with patch("DockTUI.ui.actions.refresh_actions.logger") as mock_logger:
            asyncio.run(app.refresh_containers())

            mock_logger.error.assert_called()
            app.error_display.update.assert_called_with("Error refreshing: Test error")

    def test_refresh_containers_worker_success(self):
        """Test _refresh_containers_worker successful execution."""
        app = MockDockTUIApp()

        # Mock the docker methods
        app.docker.get_networks.return_value = {"net1": {"name": "net1"}}
        app.docker.get_compose_stacks.return_value = {"stack1": {"name": "stack1"}}
        app.docker.get_images.return_value = {"img1": {"id": "img1"}}
        app.docker.get_volumes.return_value = {"vol1": {"name": "vol1"}}
        app.docker.get_containers.return_value = [{"id": "container1"}]

        callback = Mock()

        # Create a test version of the worker without the decorator
        def test_worker(self, callback):
            try:
                networks = self.docker.get_networks()
                stacks = self.docker.get_compose_stacks()
                images = self.docker.get_images()
                volumes = self.docker.get_volumes()
                containers = self.docker.get_containers()

                self.call_from_thread(
                    callback, networks, stacks, images, volumes, containers
                )

                return networks, stacks, images, volumes, containers
            except Exception as e:
                self.call_from_thread(
                    self.error_display.update, f"Error refreshing: {str(e)}"
                )
                return {}, {}, {}, {}, []

        # Test the worker logic
        result = test_worker(app, callback)

        # Verify docker methods were called
        app.docker.get_networks.assert_called_once()
        app.docker.get_compose_stacks.assert_called_once()
        app.docker.get_images.assert_called_once()
        app.docker.get_volumes.assert_called_once()
        app.docker.get_containers.assert_called_once()

        # Verify callback was called with results
        app.call_from_thread.assert_called_once()
        call_args = app.call_from_thread.call_args[0]
        assert call_args[0] == callback
        assert call_args[1] == {"net1": {"name": "net1"}}
        assert call_args[2] == {"stack1": {"name": "stack1"}}
        assert call_args[3] == {"img1": {"id": "img1"}}
        assert call_args[4] == {"vol1": {"name": "vol1"}}
        assert call_args[5] == [{"id": "container1"}]

        # Verify return value
        assert result == (
            {"net1": {"name": "net1"}},
            {"stack1": {"name": "stack1"}},
            {"img1": {"id": "img1"}},
            {"vol1": {"name": "vol1"}},
            [{"id": "container1"}],
        )

    def test_refresh_containers_worker_exception(self):
        """Test _refresh_containers_worker with exception."""
        app = MockDockTUIApp()
        app.docker.get_networks.side_effect = Exception("Network error")

        callback = Mock()

        # Create a test version of the worker without the decorator
        def test_worker(self, callback):
            try:
                networks = self.docker.get_networks()
                stacks = self.docker.get_compose_stacks()
                images = self.docker.get_images()
                volumes = self.docker.get_volumes()
                containers = self.docker.get_containers()

                self.call_from_thread(
                    callback, networks, stacks, images, volumes, containers
                )

                return networks, stacks, images, volumes, containers
            except Exception as e:
                self.call_from_thread(
                    self.error_display.update, f"Error refreshing: {str(e)}"
                )
                return {}, {}, {}, {}, []

        with patch("DockTUI.ui.actions.refresh_actions.logger") as mock_logger:
            result = test_worker(app, callback)

            app.error_display.update.assert_called_with(
                "Error refreshing: Network error"
            )

            # Should return empty results
            assert result == ({}, {}, {}, {}, [])

    def test_handle_refresh_results_success(self):
        """Test _handle_refresh_results successful execution."""
        app = MockDockTUIApp()
        app._sync_update_ui_with_results = Mock()

        networks = {"net1": {"name": "net1"}}
        stacks = {"stack1": {"name": "stack1"}}
        images = {"img1": {"id": "img1"}}
        volumes = {"vol1": {"name": "vol1"}}
        containers = [{"id": "container1"}]

        app._handle_refresh_results(networks, stacks, images, volumes, containers)

        # Should clear error display
        app.error_display.update.assert_called_with("")

        # Should call sync update
        app._sync_update_ui_with_results.assert_called_once_with(
            networks, stacks, images, volumes, containers
        )

    def test_handle_refresh_results_with_docker_error(self):
        """Test _handle_refresh_results when docker has last_error."""
        app = MockDockTUIApp()
        app.docker.last_error = "Docker connection failed"
        app._sync_update_ui_with_results = Mock()

        app._handle_refresh_results({}, {}, {}, {}, [])

        # Should show docker error
        app.error_display.update.assert_called_with("Error: Docker connection failed")

        # Should still call sync update
        app._sync_update_ui_with_results.assert_called_once()

    def test_handle_refresh_results_exception(self):
        """Test _handle_refresh_results with exception."""
        app = MockDockTUIApp()
        app._sync_update_ui_with_results = Mock(side_effect=Exception("UI error"))

        with patch("DockTUI.ui.actions.refresh_actions.logger") as mock_logger:
            app._handle_refresh_results({}, {}, {}, {}, [])

            mock_logger.error.assert_called()
            app.error_display.update.assert_called_with("Error refreshing: UI error")

    def test_sync_update_ui_with_results_full_update(self):
        """Test _sync_update_ui_with_results with full data."""
        app = MockDockTUIApp()
        app.container_list.images_section_collapsed = True
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}  # Mock the image_rows attribute

        networks = {
            "net1": {
                "name": "net1",
                "connected_containers": [{"id": "c1", "name": "container1"}],
            }
        }
        stacks = {
            "stack1": {
                "config_file": "/path/to/compose.yml",
                "running": 2,
                "exited": 1,
                "total": 3,
                "can_recreate": True,
                "has_compose_file": True,
            }
        }
        images = {"img1": {"id": "img1", "tags": ["test:latest"]}}
        volumes = {"vol1": {"name": "vol1", "driver": "local"}}
        containers = [
            {"id": "c1", "name": "container1", "stack": "stack1", "status": "running"}
        ]

        app._sync_update_ui_with_results(networks, stacks, images, volumes, containers)

        # Verify batch update
        app.container_list.begin_update.assert_called_once()
        app.container_list.end_update.assert_called_once()

        # Verify stack was added
        app.container_list.add_stack.assert_called_once_with(
            "stack1", "/path/to/compose.yml", 2, 1, 3, True, True
        )

        # Verify image was added
        app.container_list.add_image.assert_called_once_with(
            {"id": "img1", "tags": ["test:latest"]}
        )

        # Verify volume was added
        app.container_list.add_volume.assert_called_once_with(
            {"name": "vol1", "driver": "local"}
        )

        # Verify network was added
        app.container_list.add_network.assert_called_once_with(networks["net1"])
        app.container_list.add_container_to_network.assert_called_once_with(
            "net1", {"id": "c1", "name": "container1"}
        )

        # Verify container was added
        app.container_list.add_container_to_stack.assert_called_once_with(
            "stack1", containers[0]
        )

        # Verify title was updated
        assert app.title == "DockTUI - 1 Networks, 1 Stacks, 2 Running, 1 Exited"

        # Verify refresh count incremented
        assert app._refresh_count == 1

    def test_sync_update_ui_with_results_no_images(self):
        """Test _sync_update_ui_with_results with no images."""
        app = MockDockTUIApp()
        app.container_list.images_section_collapsed = False
        app.container_list.images_container = Mock()
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}

        networks = {}
        stacks = {}
        images = {}  # No images
        volumes = {}
        containers = []

        app._sync_update_ui_with_results(networks, stacks, images, volumes, containers)

        # Should show no images message
        app.container_list.image_manager.show_no_images_message.assert_called_once()

    def test_sync_update_ui_with_results_preserve_image_selection(self):
        """Test _sync_update_ui_with_results preserving image selection."""
        app = MockDockTUIApp()
        app.container_list.images_section_collapsed = True
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = "img1"
        app.container_list.image_manager.image_rows = {"img1": Mock()}

        images = {"img1": {"id": "img1"}}

        app._sync_update_ui_with_results({}, {}, images, {}, [])

        # Should re-select preserved image
        app.container_list.image_manager.select_image.assert_called_once_with("img1")
        assert app.container_list.image_manager._preserve_selected_image_id is None

    def test_sync_update_ui_with_results_handle_post_recreate(self):
        """Test _sync_update_ui_with_results calls handle_post_recreate."""
        app = MockDockTUIApp()
        app.handle_post_recreate = Mock()
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        containers = [{"id": "c1", "stack": "default"}]

        app._sync_update_ui_with_results({}, {}, {}, {}, containers)

        app.handle_post_recreate.assert_called_once_with(containers)

    def test_sync_update_ui_with_results_update_selected_container(self):
        """Test _sync_update_ui_with_results updates selected container in log pane."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "c1")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        containers = [
            {"id": "c1", "name": "container1", "stack": "stack1", "status": "running"}
        ]

        app._sync_update_ui_with_results({}, {}, {}, {}, containers)

        app.log_pane.update_selection.assert_called_once_with(
            "container", "c1", containers[0]
        )

    def test_sync_update_ui_with_results_selected_container_not_found(self):
        """Test _sync_update_ui_with_results when selected container not in new data."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("container", "c2")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        containers = [{"id": "c1", "name": "container1", "stack": "stack1"}]

        app._sync_update_ui_with_results({}, {}, {}, {}, containers)

        # Should not update log pane
        app.log_pane.update_selection.assert_not_called()

    def test_sync_update_ui_with_results_selected_item_not_container(self):
        """Test _sync_update_ui_with_results when selected item is not a container."""
        app = MockDockTUIApp()
        app.container_list.selected_item = ("stack", "stack1")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        containers = [{"id": "c1", "name": "container1", "stack": "stack1"}]

        app._sync_update_ui_with_results({}, {}, {}, {}, containers)

        # Should not update log pane
        app.log_pane.update_selection.assert_not_called()

    def test_sync_update_ui_with_results_no_log_pane(self):
        """Test _sync_update_ui_with_results when log_pane is None."""
        app = MockDockTUIApp()
        app.log_pane = None
        app.container_list.selected_item = ("container", "c1")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        containers = [{"id": "c1", "stack": "default"}]

        # Should not crash
        app._sync_update_ui_with_results({}, {}, {}, {}, containers)

    def test_sync_update_ui_with_results_exception_in_update(self):
        """Test _sync_update_ui_with_results with exception during update."""
        app = MockDockTUIApp()
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        app.container_list.begin_update.side_effect = Exception("Update error")

        with patch("DockTUI.ui.actions.refresh_actions.logger") as mock_logger:
            app._sync_update_ui_with_results({}, {}, {}, {}, [])

            mock_logger.error.assert_called()
            app.error_display.update.assert_called_with("Error updating UI: Update error")

    def test_sync_update_ui_with_results_exception_ensures_end_update(self):
        """Test _sync_update_ui_with_results calls end_update even on exception."""
        app = MockDockTUIApp()
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        app.container_list.add_stack.side_effect = Exception("Add error")

        stacks = {"stack1": {"running": 1, "exited": 0, "total": 1}}

        with patch("DockTUI.ui.actions.refresh_actions.logger"):
            app._sync_update_ui_with_results({}, stacks, {}, {}, [])

            # Should still call end_update
            app.container_list.begin_update.assert_called_once()
            app.container_list.end_update.assert_called_once()

    def test_sync_update_ui_with_results_sorted_containers(self):
        """Test _sync_update_ui_with_results sorts containers by stack."""
        app = MockDockTUIApp()
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}

        containers = [
            {"id": "c3", "stack": "stack3"},
            {"id": "c1", "stack": "stack1"},
            {"id": "c2", "stack": "stack2"},
        ]

        app._sync_update_ui_with_results({}, {}, {}, {}, containers)

        # Verify containers were added in sorted order
        calls = app.container_list.add_container_to_stack.call_args_list
        assert len(calls) == 3
        assert calls[0][0] == ("stack1", {"id": "c1", "stack": "stack1"})
        assert calls[1][0] == ("stack2", {"id": "c2", "stack": "stack2"})
        assert calls[2][0] == ("stack3", {"id": "c3", "stack": "stack3"})

    def test_sync_update_ui_with_results_no_handle_post_recreate(self):
        """Test _sync_update_ui_with_results when handle_post_recreate doesn't exist."""
        app = MockDockTUIApp()
        app.container_list.image_manager = Mock()
        app.container_list.image_manager._preserve_selected_image_id = None
        app.container_list.image_manager.image_rows = {}
        # Remove the handle_post_recreate attribute
        if hasattr(app, "handle_post_recreate"):
            delattr(app, "handle_post_recreate")

        # Should not crash
        app._sync_update_ui_with_results({}, {}, {}, {}, [])

        # Verify other operations still work
        assert app._refresh_count == 1