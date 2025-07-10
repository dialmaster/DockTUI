"""Tests for the main DockTUIApp class."""

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest
from textual.app import SystemCommand
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Header
from textual.worker import Worker

from DockTUI.app import DockTUIApp, main
from DockTUI.ui.base.container_list_base import SelectionChanged
from DockTUI.ui.containers import ContainerList
from DockTUI.ui.dialogs.confirm import (
    ComposeDownModal,
    RemoveContainerModal,
    RemoveImageModal,
    RemoveUnusedImagesModal,
    RemoveUnusedVolumesModal,
)
from DockTUI.ui.viewers.log_pane import LogPane
from DockTUI.ui.widgets.status import ErrorDisplay, StatusBar

if TYPE_CHECKING:
    from DockTUI.docker_mgmt.manager import DockerManager


class TestDockTUIApp:
    """Test cases for DockTUIApp class."""

    @patch("DockTUI.app.RefreshActions.__init__", return_value=None)
    @patch("DockTUI.app.DockerActions.__init__", return_value=None)
    @patch("DockTUI.app.App.__init__", return_value=None)
    @patch("DockTUI.app.DockerManager")
    def test_init(self, mock_docker_manager, mock_app_init, mock_docker_actions_init, mock_refresh_actions_init):
        """Test DockTUIApp initialization."""
        # Create app instance
        app = DockTUIApp()

        # Verify parent class initializations were called
        mock_app_init.assert_called_once()
        mock_docker_actions_init.assert_called_once()
        mock_refresh_actions_init.assert_called_once()

        # Verify DockerManager was instantiated
        mock_docker_manager.assert_called_once()

        # Verify initial state
        assert app.docker is not None
        assert app.container_list is None
        assert app.log_pane is None
        assert app.error_display is None
        assert app.refresh_timer is None
        assert app._current_worker is None
        assert app.footer is None
        assert app.status_bar is None
        assert app._current_selection_type == "none"
        assert app._current_selection_status == "none"

    @patch("DockTUI.app.RefreshActions.__init__", return_value=None)
    @patch("DockTUI.app.DockerActions.__init__", return_value=None)
    @patch("DockTUI.app.App.__init__")
    @patch("DockTUI.app.DockerManager")
    def test_init_error_handling(self, mock_docker_manager, mock_app_init, mock_docker_actions_init, mock_refresh_actions_init):
        """Test error handling during initialization."""
        # Make DockerManager raise an exception
        mock_docker_manager.side_effect = Exception("Docker connection failed")

        # Verify exception is propagated
        with pytest.raises(Exception, match="Docker connection failed"):
            DockTUIApp()

    def test_get_system_commands(self):
        """Test system command generation for command palette."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.action_start = Mock()
        app.action_stop = Mock()
        app.action_restart = Mock()
        app.action_recreate = Mock()
        app.action_remove_container = Mock()
        app.action_down = Mock()
        app.action_remove_image = Mock()
        app.action_remove_unused_images = Mock()

        # Mock super().get_system_commands to return some default commands
        with patch("DockTUI.app.App.get_system_commands") as mock_super:
            default_cmd = SystemCommand("Default", "Default command", Mock())
            mock_super.return_value = [default_cmd]

            # Get commands
            screen = Mock(spec=Screen)
            commands = list(app.get_system_commands(screen))

            # Verify default command is included
            assert commands[0] == default_cmd

            # Verify custom commands
            custom_titles = [cmd.title for cmd in commands[1:]]
            expected_titles = [
                "Start Selected",
                "Stop Selected",
                "Restart Selected",
                "Recreate Selected",
                "Remove Selected Container",
                "Down Selected Stack",
                "Remove Selected Image",
                "Remove All Unused Images",
                "Prune All Unused Volumes",
            ]
            assert custom_titles == expected_titles

            # Verify callbacks are correct
            assert commands[1].callback == app.action_start
            assert commands[2].callback == app.action_stop

    @patch("DockTUI.app.Header")
    @patch("DockTUI.app.Horizontal")
    @patch("DockTUI.app.Vertical")
    @patch("DockTUI.app.ErrorDisplay")
    @patch("DockTUI.app.ContainerList")
    @patch("DockTUI.app.LogPane")
    @patch("DockTUI.app.StatusBar")
    @patch("DockTUI.app.Footer")
    def test_compose(self, mock_footer, mock_status_bar, mock_log_pane,
                     mock_container_list, mock_error_display, mock_vertical,
                     mock_horizontal, mock_header):
        """Test widget composition."""
        app = DockTUIApp.__new__(DockTUIApp)

        # Mock the context managers
        mock_horizontal.return_value.__enter__ = Mock(return_value=mock_horizontal.return_value)
        mock_horizontal.return_value.__exit__ = Mock(return_value=None)
        mock_vertical.return_value.__enter__ = Mock(return_value=mock_vertical.return_value)
        mock_vertical.return_value.__exit__ = Mock(return_value=None)

        # Collect composed widgets
        widgets = list(app.compose())

        # Verify all expected widgets were created
        mock_header.assert_called_once()
        mock_error_display.assert_called_once()
        mock_container_list.assert_called_once()
        mock_log_pane.assert_called_once()
        mock_status_bar.assert_called_once()
        mock_footer.assert_called_once()

    @patch("DockTUI.app.metadata")
    @patch("DockTUI.app.config")
    def test_on_mount(self, mock_config, mock_metadata):
        """Test on_mount event handler."""
        # Mock the version to a fixed value for testing
        mock_metadata.version.return_value = "0.2.0"
        
        app = DockTUIApp.__new__(DockTUIApp)
        # Initialize attributes that would normally be set by __init__
        app.container_list = None
        app.log_pane = None
        app.error_display = None
        app.footer = None
        app.status_bar = None
        app.refresh_timer = None

        app.query_one = Mock()
        app.set_interval = Mock(return_value=Mock(spec=Timer))
        app.call_after_refresh = Mock()
        app.action_refresh = Mock()

        # Mock config
        mock_config.get.return_value = 2.5  # refresh interval

        # Mock query_one to return mock widgets
        mock_container_list = Mock(spec=ContainerList)
        mock_log_pane = Mock(spec=LogPane)
        mock_error_display = Mock(spec=ErrorDisplay)
        mock_footer = Mock(spec=Footer)
        mock_status_bar = Mock(spec=StatusBar)

        def query_one_side_effect(selector, widget_type):
            if selector == "#containers":
                return mock_container_list
            elif selector == "#log-pane":
                return mock_log_pane
            elif selector == "#error":
                return mock_error_display
            elif selector == "#footer":
                return mock_footer
            elif selector == "#status_bar":
                return mock_status_bar

        app.query_one.side_effect = query_one_side_effect

        # Mock the title property setter
        with patch.object(type(app), 'title', new_callable=PropertyMock) as mock_title:
            # Call on_mount
            app.on_mount()

            # Verify title was set (now includes version)
            mock_title.assert_called_with("DockTUI v0.2.0")

        # Verify widgets were queried and stored
        assert app.container_list == mock_container_list
        assert app.log_pane == mock_log_pane
        assert app.error_display == mock_error_display
        assert app.footer == mock_footer
        assert app.status_bar == mock_status_bar

        # Verify refresh timer was started
        mock_config.get.assert_called_with("app.refresh_interval", 5.0)
        app.set_interval.assert_called_with(2.5, app.action_refresh)

        # Verify initial refresh was scheduled
        app.call_after_refresh.assert_called_with(app.action_refresh)

    def test_action_quit(self):
        """Test quit action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.refresh_timer = Mock(spec=Timer)
        app.exit = Mock()

        app.action_quit()

        app.refresh_timer.stop.assert_called_once()
        app.exit.assert_called_once()

    def test_action_quit_no_timer(self):
        """Test quit action when no timer is set."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.refresh_timer = None
        app.exit = Mock()

        app.action_quit()

        app.exit.assert_called_once()

    def test_action_refresh(self):
        """Test refresh action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.call_after_refresh = Mock()
        app.refresh_containers = Mock()

        app.action_refresh()

        app.call_after_refresh.assert_called_with(app.refresh_containers)

    @patch("DockTUI.app.logger")
    def test_action_refresh_error(self, mock_logger):
        """Test refresh action error handling."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.call_after_refresh = Mock(side_effect=Exception("Refresh failed"))

        # Should not raise, just log
        app.action_refresh()

        mock_logger.error.assert_called()

    def test_action_start(self):
        """Test start action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.execute_docker_command = Mock()

        app.action_start()

        app.is_action_applicable.assert_called_with("start")
        app.execute_docker_command.assert_called_with("start")

    def test_action_start_not_applicable(self):
        """Test start action when not applicable."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=False)
        app.execute_docker_command = Mock()

        app.action_start()

        app.is_action_applicable.assert_called_with("start")
        app.execute_docker_command.assert_not_called()

    def test_action_stop(self):
        """Test stop action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.execute_docker_command = Mock()

        app.action_stop()

        app.is_action_applicable.assert_called_with("stop")
        app.execute_docker_command.assert_called_with("stop")

    def test_action_restart(self):
        """Test restart action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.execute_docker_command = Mock()

        app.action_restart()

        app.is_action_applicable.assert_called_with("restart")
        app.execute_docker_command.assert_called_with("restart")

    def test_action_recreate(self):
        """Test recreate action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.execute_docker_command = Mock()

        app.action_recreate()

        app.is_action_applicable.assert_called_with("recreate")
        app.execute_docker_command.assert_called_with("recreate")

    def test_action_remove_container(self):
        """Test remove container action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.container_list = Mock()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"name": "test-container"}
        app.error_display = Mock()
        app.push_screen = Mock()

        app.action_remove_container()

        # Verify modal was created and pushed
        app.push_screen.assert_called_once()
        modal = app.push_screen.call_args[0][0]
        assert isinstance(modal, RemoveContainerModal)
        assert modal.container_name == "test-container"

    def test_action_remove_container_not_container(self):
        """Test remove container action when selected item is not a container."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.container_list = Mock()
        app.container_list.selected_item = ("stack", "test-stack")
        app.error_display = Mock()

        app.action_remove_container()

        app.error_display.update.assert_called_with("Selected item is not a container")

    def test_action_down(self):
        """Test down action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.container_list = Mock()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {"name": "test-stack"}
        app.push_screen = Mock()

        app.action_down()

        # Verify modal was created and pushed
        app.push_screen.assert_called_once()
        modal = app.push_screen.call_args[0][0]
        assert isinstance(modal, ComposeDownModal)
        assert modal.stack_name == "test-stack"

    def test_action_down_with_volume_removal(self):
        """Test down action with volume removal option."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.is_action_applicable = Mock(return_value=True)
        app.container_list = Mock()
        app.container_list.selected_item = ("stack", "test-stack")
        app.container_list.selected_stack_data = {"name": "test-stack"}
        app.execute_docker_command = Mock()
        app.push_screen = Mock()

        app.action_down()

        # Get the callback function and modal
        modal = app.push_screen.call_args[0][0]
        callback = app.push_screen.call_args[0][1]

        # Mock the checkbox_checked property
        with patch.object(type(modal), 'checkbox_checked', new_callable=PropertyMock) as mock_checkbox:
            mock_checkbox.return_value = True

            # Call the callback with confirmation
            callback(True)

        # Verify command was executed with volume flag
        app.execute_docker_command.assert_called_with("down:remove_volumes")

    def test_action_remove_container_context(self):
        """Test context-aware remove action for containers."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.container_list = Mock()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"status": "exited"}
        app.error_display = Mock()
        app.action_remove_container = Mock()

        app.action_remove()

        app.action_remove_container.assert_called_once()

    def test_action_remove_container_running(self):
        """Test remove action for running container."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.container_list = Mock()
        app.container_list.selected_item = ("container", "test-container")
        app.container_list.selected_container_data = {"status": "running"}
        app.error_display = Mock()

        app.action_remove()

        app.error_display.update.assert_called_with(
            "Cannot remove running container (status: running)"
        )

    def test_action_remove_image_context(self):
        """Test context-aware remove action for images."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.container_list = Mock()
        app.container_list.selected_item = ("image", "test-image")
        app._remove_image = Mock()

        app.action_remove()

        app._remove_image.assert_called_once()

    def test_action_remove_no_selection(self):
        """Test remove action with no selection."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.container_list = None
        app.error_display = Mock()

        app.action_remove()

        app.error_display.update.assert_called_with("No item selected")

    def test_remove_image_internal(self):
        """Test internal _remove_image method."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.container_list = Mock()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = {
            "id": "test-image",
            "tags": ["test:latest"],
            "container_names": []
        }
        app.push_screen = Mock()

        app._remove_image()

        # Verify modal was created and pushed
        app.push_screen.assert_called_once()
        modal = app.push_screen.call_args[0][0]
        assert isinstance(modal, RemoveImageModal)

    def test_remove_image_in_use(self):
        """Test removing image that's in use."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.container_list = Mock()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = {
            "id": "test-image",
            "container_names": ["container1", "container2"]
        }
        app.error_display = Mock()

        app._remove_image()

        app.error_display.update.assert_called_with(
            "Cannot remove image: in use by 2 container(s)"
        )

    def test_action_remove_unused_images(self):
        """Test remove unused images action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.docker = Mock()
        app.docker.get_unused_images.return_value = [
            {"id": "image1"},
            {"id": "image2"},
        ]
        app.push_screen = Mock()

        app.action_remove_unused_images()

        # Verify modal was created with correct count
        app.push_screen.assert_called_once()
        modal = app.push_screen.call_args[0][0]
        assert isinstance(modal, RemoveUnusedImagesModal)
        assert modal.unused_count == 2

    def test_action_remove_unused_images_none_found(self):
        """Test remove unused images when none are found."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.docker = Mock()
        app.docker.get_unused_images.return_value = []
        app.error_display = Mock()

        app.action_remove_unused_images()

        app.error_display.update.assert_called_with("No unused images found")

    def test_action_prune_unused_volumes(self):
        """Test prune unused volumes action."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.docker = Mock()
        app.docker.get_unused_volumes.return_value = [
            {"name": "volume1", "in_use": False},
            {"name": "volume2", "in_use": False},
        ]
        app.push_screen = Mock()
        app.error_display = Mock()

        app.action_prune_unused_volumes()

        # Should get unused volumes
        app.docker.get_unused_volumes.assert_called_once()
        # Should push volume removal modal
        modal = app.push_screen.call_args[0][0]
        assert isinstance(modal, RemoveUnusedVolumesModal)
        assert modal.unused_count == 2

    def test_action_prune_unused_volumes_none_found(self):
        """Test prune unused volumes when none are found."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.docker = Mock()
        app.docker.get_unused_volumes.return_value = []
        app.error_display = Mock()

        app.action_prune_unused_volumes()

        app.error_display.update.assert_called_with("No unused volumes found")

    def test_check_action_system_actions(self):
        """Test check_action for system actions."""
        app = DockTUIApp.__new__(DockTUIApp)

        assert app.check_action("quit", ()) is True
        assert app.check_action("command_palette", ()) is True

    def test_check_action_container_actions(self):
        """Test check_action for container actions."""
        app = DockTUIApp.__new__(DockTUIApp)
        app._current_selection_type = "container"
        app._current_selection_status = "running"

        assert app.check_action("start", ()) is True
        assert app.check_action("stop", ()) is True
        assert app.check_action("restart", ()) is True
        assert app.check_action("recreate", ()) is True
        assert app.check_action("remove", ()) is None  # Disabled for running
        assert app.check_action("down", ()) is False  # Not available for containers

    def test_check_action_container_stopped(self):
        """Test check_action for stopped container."""
        app = DockTUIApp.__new__(DockTUIApp)
        app._current_selection_type = "container"
        app._current_selection_status = "exited"

        assert app.check_action("remove", ()) is True  # Enabled for exited

    def test_check_action_stack_actions(self):
        """Test check_action for stack actions."""
        app = DockTUIApp.__new__(DockTUIApp)
        app._current_selection_type = "stack"

        assert app.check_action("start", ()) is True
        assert app.check_action("stop", ()) is True
        assert app.check_action("restart", ()) is True
        assert app.check_action("recreate", ()) is True
        assert app.check_action("down", ()) is True
        assert app.check_action("remove", ()) is False

    def test_check_action_image_actions(self):
        """Test check_action for image actions."""
        app = DockTUIApp.__new__(DockTUIApp)
        app._current_selection_type = "image"
        app.container_list = Mock()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = {"container_names": []}

        assert app.check_action("remove", ()) is True
        assert app.check_action("remove_unused_images", ()) is True
        assert app.check_action("start", ()) is False

    def test_check_action_image_in_use(self):
        """Test check_action for image in use."""
        app = DockTUIApp.__new__(DockTUIApp)
        app._current_selection_type = "image"
        app.container_list = Mock()
        app.container_list.selected_item = ("image", "test-image")
        app.container_list.image_manager = Mock()
        app.container_list.image_manager.selected_image_data = {
            "container_names": ["container1"]
        }

        assert app.check_action("remove", ()) is None  # Disabled

    def test_on_selection_changed_with_selection(self):
        """Test selection changed event handler with a selection."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.log_pane = Mock()
        app.container_list = Mock()
        app.status_bar = Mock()
        app.refresh_bindings = Mock()
        app.footer = Mock()
        app._current_selection_type = "none"
        app._current_selection_status = "none"

        event = SelectionChanged(
            item_type="container",
            item_id="test-container",
            item_data={"name": "test-container", "status": "running"}
        )

        app.on_selection_changed(event)

        app.log_pane.update_selection.assert_called_with(
            "container", "test-container", {"name": "test-container", "status": "running"}
        )
        app.container_list._update_footer_with_selection.assert_called_once()
        app.status_bar.refresh.assert_called_once()
        assert app._current_selection_type == "container"
        assert app._current_selection_status == "running"
        app.refresh_bindings.assert_called_once()

    def test_on_selection_changed_no_selection(self):
        """Test selection changed event handler with no selection."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.log_pane = Mock()
        app.container_list = Mock()
        app.status_bar = Mock()
        app.refresh_bindings = Mock()
        app.footer = Mock()
        app._current_selection_type = "none"
        app._current_selection_status = "none"

        event = SelectionChanged(
            item_type="none",
            item_id=None,
            item_data=None
        )

        app.on_selection_changed(event)

        app.log_pane.clear_selection.assert_called_once()
        assert app._current_selection_type == "none"
        assert app._current_selection_status == "none"

    def test_on_selection_changed_no_log_pane(self):
        """Test selection changed when log pane is not ready."""
        app = DockTUIApp.__new__(DockTUIApp)
        app.log_pane = None
        app.refresh_bindings = Mock()
        # Initialize selection attributes
        app._current_selection_type = "none"
        app._current_selection_status = "none"

        event = SelectionChanged(
            item_type="container",
            item_id="test-container",
            item_data={"status": "running"}
        )

        # Should not raise
        app.on_selection_changed(event)

        # Selection state should NOT be updated when log_pane is None
        # because the method returns early
        assert app._current_selection_type == "none"
        assert app._current_selection_status == "none"

        # refresh_bindings should not be called
        app.refresh_bindings.assert_not_called()



class TestMain:
    """Test cases for the main function."""

    @patch("DockTUI.app.DockTUIApp")
    def test_main_success(self, mock_app_class):
        """Test successful main execution."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app

        main()

        mock_app_class.assert_called_once()
        mock_app.run.assert_called_once()

    @patch("DockTUI.app.DockTUIApp")
    @patch("DockTUI.app.logger")
    def test_main_error(self, mock_logger, mock_app_class):
        """Test main with error."""
        mock_app_class.side_effect = Exception("App failed")

        with pytest.raises(Exception, match="App failed"):
            main()

        mock_logger.error.assert_called()


class TestIntegration:
    """Integration tests for app components."""

    def test_css_constants(self):
        """Test that CSS is properly defined."""
        app = DockTUIApp.__new__(DockTUIApp)
        assert isinstance(app.CSS, str)
        assert "#left-pane" in app.CSS
        assert "ContainerList" in app.CSS

    def test_bindings(self):
        """Test that bindings are properly defined."""
        app = DockTUIApp.__new__(DockTUIApp)
        assert len(app.BINDINGS) > 0

        # Verify key bindings
        binding_keys = [b.key for b in app.BINDINGS]
        assert "q" in binding_keys
        assert "s" in binding_keys
        assert "t" in binding_keys
        assert "e" in binding_keys
        assert "u" in binding_keys
        assert "d" in binding_keys
        assert "r" in binding_keys
        assert "R" in binding_keys
        assert "p" in binding_keys

    def test_enable_command_palette(self):
        """Test that command palette is enabled."""
        assert DockTUIApp.ENABLE_COMMAND_PALETTE is True