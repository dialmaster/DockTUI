"""Tests for the ContainerList widget."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest
from textual.widgets import DataTable, Static

from DockTUI.ui.containers import ContainerList
from DockTUI.ui.widgets.headers import NetworkHeader, SectionHeader, StackHeader, VolumeHeader

if TYPE_CHECKING:
    from DockTUI.app import DockTUIApp


class MockScreen:
    """Mock screen for testing."""
    def __init__(self, focused=None):
        self.focused = focused


@pytest.fixture(scope="module")
def event_loop():
    """Create an event loop for the tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


class TestContainerList:
    """Test cases for the ContainerList widget."""

    @pytest.fixture
    def container_list(self):
        """Create a ContainerList instance with mocked dependencies."""
        # Mock all the parent class initialization
        with patch('DockTUI.ui.base.container_list_base.ContainerListBase.__init__', return_value=None):
            # Create instance without calling parent __init__
            container_list = object.__new__(ContainerList)

            # Initialize base attributes that would be set by parent
            container_list._is_updating = False
            container_list._pending_clear = False
            container_list._initial_load_complete = False
            container_list.loading_message = None
            container_list._status_overrides = {}

            # Initialize collections from base class
            container_list.volume_headers = {}
            container_list.expanded_volumes = set()
            container_list.network_tables = {}
            container_list.network_headers = {}
            container_list.network_rows = {}
            container_list.expanded_networks = set()
            container_list.stack_tables = {}
            container_list.stack_headers = {}
            container_list.container_rows = {}
            container_list.expanded_stacks = set()

            # Section headers and containers
            container_list.images_section_header = None
            container_list.volumes_section_header = None
            container_list.networks_section_header = None
            container_list.stacks_section_header = None
            container_list.images_container = None
            container_list.volumes_container = None
            container_list.networks_container = None
            container_list.stacks_container = None

            # General state
            container_list.current_focus = None

            # Selection tracking
            container_list.selected_item = None
            container_list.selected_container_data = None
            container_list.selected_stack_data = None
            container_list.selected_network_data = None
            container_list.selected_volume_data = None
            container_list.selected_image_data = None

            # Tracking sets
            container_list._volumes_in_new_data = set()
            container_list._stacks_in_new_data = set()
            container_list._networks_in_new_data = set()

            # Section collapse states
            container_list.stacks_section_collapsed = False
            container_list.images_section_collapsed = True
            container_list.volumes_section_collapsed = True
            container_list.networks_section_collapsed = True

            # Initialize Textual-specific attributes
            container_list._nodes = []
            container_list._children = []
            container_list._parent = None
            container_list._closing = False
            container_list._closed = False
            container_list._name = None
            container_list._id = None
            container_list._classes = set()
            container_list._styles_cache = None

            # Now call the ContainerList __init__ to set up managers
            ContainerList.__init__(container_list)

            # Mock methods that might be called
            container_list.remove_children = Mock()
            container_list.mount = Mock()
            container_list.refresh = Mock()

            # Setup property mocks that persist for all tests
            self._mock_screen = MockScreen()
            self._screen_patch = patch.object(type(container_list), 'screen', new_callable=PropertyMock)
            self._mock_screen_prop = self._screen_patch.start()
            self._mock_screen_prop.return_value = self._mock_screen

            self._children_patch = patch.object(type(container_list), 'children', new_callable=PropertyMock)
            self._mock_children_prop = self._children_patch.start()
            self._mock_children_prop.return_value = []

            yield container_list

            # Clean up patches
            self._screen_patch.stop()
            self._children_patch.stop()

    def test_init(self, container_list):
        """Test initialization of ContainerList."""
        # Verify managers are initialized
        assert container_list.image_manager is not None
        assert container_list.volume_manager is not None
        assert container_list.network_manager is not None
        assert container_list.stack_manager is not None

        # Verify helper components
        assert container_list.footer_formatter is not None
        assert container_list.navigation_handler is not None

        # Verify initial state
        assert container_list.loading_message is None
        assert container_list._initial_load_complete is False

        # Verify backward compatibility references are set up
        assert hasattr(container_list, 'image_headers')
        assert hasattr(container_list, 'volume_headers')
        assert hasattr(container_list, 'network_tables')
        assert hasattr(container_list, 'stack_tables')

    def test_begin_update(self, container_list):
        """Test begin_update method."""
        # Mock managers
        container_list.network_manager.clear_tables = Mock()
        container_list.stack_manager.clear_tables = Mock()
        container_list.image_manager.reset_tracking = Mock()
        container_list.volume_manager.reset_tracking = Mock()
        container_list.network_manager.reset_tracking = Mock()
        container_list.stack_manager.reset_tracking = Mock()

        # Mock _ensure_section_headers
        container_list._ensure_section_headers = Mock()

        # Call begin_update
        container_list.begin_update()

        # Verify state
        assert container_list._is_updating is True
        assert container_list._pending_clear is True  # No children initially

        # Verify manager methods called
        container_list.network_manager.clear_tables.assert_called_once()
        container_list.stack_manager.clear_tables.assert_called_once()
        container_list.image_manager.reset_tracking.assert_called_once()
        container_list.volume_manager.reset_tracking.assert_called_once()
        container_list.network_manager.reset_tracking.assert_called_once()
        container_list.stack_manager.reset_tracking.assert_called_once()
        container_list._ensure_section_headers.assert_called_once()

    def test_end_update_initial_load(self, container_list):
        """Test end_update method on initial load."""
        # Set up initial load state
        container_list._initial_load_complete = False
        mock_parent = Mock()
        mock_loading_message = Mock()
        mock_loading_message.parent = mock_parent
        container_list.loading_message = mock_loading_message
        container_list._pending_clear = True

        # Mock methods
        container_list._cleanup_removed_items = Mock()
        container_list._prepare_new_containers = Mock()
        container_list._mount_all_sections = Mock()
        container_list._restore_selection = Mock()
        container_list._update_cursor_visibility = Mock()
        container_list.refresh = Mock()

        # Call end_update
        container_list.end_update()

        # Verify loading message removed and initial load marked complete
        mock_loading_message.remove.assert_called_once()
        assert container_list.loading_message is None
        assert container_list._initial_load_complete is True

        # Verify methods called in correct order
        container_list._cleanup_removed_items.assert_called_once()
        container_list._prepare_new_containers.assert_called_once()
        container_list._mount_all_sections.assert_called_once()
        container_list._restore_selection.assert_called_once()
        container_list._update_cursor_visibility.assert_called_once()

        # Verify state reset
        assert container_list._is_updating is False

    def test_end_update_existing_sections(self, container_list):
        """Test end_update method with existing sections."""
        # Set up state
        container_list._initial_load_complete = True
        container_list._pending_clear = False

        # Mock children property to return non-empty list
        with patch.object(type(container_list), 'children', new_callable=PropertyMock) as mock_children:
            mock_children.return_value = [Mock()]

            # Mock methods
            container_list._cleanup_removed_items = Mock()
            container_list._prepare_new_containers = Mock()
            container_list._update_existing_sections = Mock()
            container_list._restore_selection = Mock()
            container_list._update_cursor_visibility = Mock()
            container_list.refresh = Mock()

            # Call end_update
            container_list.end_update()

            # Verify update path taken
            container_list._update_existing_sections.assert_called_once()
            # Mock _mount_all_sections if not already mocked
            if not hasattr(container_list._mount_all_sections, 'assert_not_called'):
                container_list._mount_all_sections = Mock()
            container_list._mount_all_sections.assert_not_called()

            # Verify refresh called
            container_list.refresh.assert_called_once()

    def test_cleanup_removed_items(self, container_list):
        """Test _cleanup_removed_items method."""
        # Mock managers
        container_list.image_manager.cleanup_removed_images = Mock()
        container_list.volume_manager.cleanup_removed_volumes = Mock()
        container_list.network_manager.cleanup_removed_networks = Mock()
        container_list.stack_manager.cleanup_removed_stacks = Mock()

        # Call method
        container_list._cleanup_removed_items()

        # Verify all cleanup methods called
        container_list.image_manager.cleanup_removed_images.assert_called_once()
        container_list.volume_manager.cleanup_removed_volumes.assert_called_once()
        container_list.network_manager.cleanup_removed_networks.assert_called_once()
        container_list.stack_manager.cleanup_removed_stacks.assert_called_once()

    def test_prepare_new_containers(self, container_list):
        """Test _prepare_new_containers method."""
        # Create mock objects
        mock_img1 = Mock()
        mock_vol1 = Mock()
        mock_net1 = Mock()
        mock_stack1 = Mock()
        mock_img2 = Mock()
        mock_vol2 = Mock()
        mock_net2 = Mock()
        mock_stack2 = Mock()

        # Mock managers
        container_list.image_manager.get_existing_containers = Mock(return_value={"img1": mock_img1})
        container_list.volume_manager.get_existing_containers = Mock(return_value={"vol1": mock_vol1})
        container_list.network_manager.get_existing_containers = Mock(return_value={"net1": mock_net1})
        container_list.stack_manager.get_existing_containers = Mock(return_value={"stack1": mock_stack1})

        container_list.image_manager.prepare_new_containers = Mock(return_value={"img2": mock_img2})
        container_list.volume_manager.prepare_new_containers = Mock(return_value={"vol2": mock_vol2})
        container_list.network_manager.prepare_new_containers = Mock(return_value={"net2": mock_net2})
        container_list.stack_manager.prepare_new_containers = Mock(return_value={"stack2": mock_stack2})

        # Test with existing containers
        container_list._pending_clear = False
        container_list._prepare_new_containers()

        # Verify existing containers retrieved
        assert "img1" in container_list.existing_image_containers
        assert container_list.existing_image_containers["img1"] is mock_img1
        assert "vol1" in container_list.existing_volume_containers
        assert container_list.existing_volume_containers["vol1"] is mock_vol1
        assert "net1" in container_list.existing_network_containers
        assert container_list.existing_network_containers["net1"] is mock_net1
        assert "stack1" in container_list.existing_stack_containers
        assert container_list.existing_stack_containers["stack1"] is mock_stack1

        # Verify new containers prepared
        assert "img2" in container_list.new_image_containers
        assert container_list.new_image_containers["img2"] is mock_img2
        assert "vol2" in container_list.new_volume_containers
        assert container_list.new_volume_containers["vol2"] is mock_vol2
        assert "net2" in container_list.new_network_containers
        assert container_list.new_network_containers["net2"] is mock_net2
        assert "stack2" in container_list.new_stack_containers
        assert container_list.new_stack_containers["stack2"] is mock_stack2

        # Test with pending clear
        container_list._pending_clear = True
        container_list._prepare_new_containers()

        # Verify existing containers are empty
        assert container_list.existing_image_containers == {}
        assert container_list.existing_volume_containers == {}
        assert container_list.existing_network_containers == {}
        assert container_list.existing_stack_containers == {}

    def test_add_image(self, container_list):
        """Test add_image method."""
        # Mock image manager
        container_list.image_manager.add_image = Mock()
        container_list.image_manager.selected_image_data = {"id": "test-image"}

        # Add image
        image_data = {"id": "test-image", "tags": ["test:latest"]}
        container_list.add_image(image_data)

        # Verify manager called
        container_list.image_manager.add_image.assert_called_once_with(image_data)
        # Verify backward compatibility
        assert container_list.selected_image_data == {"id": "test-image"}

    def test_add_volume(self, container_list):
        """Test add_volume method."""
        # Mock volume manager
        container_list.volume_manager.add_volume = Mock()
        container_list.volume_manager.selected_volume_data = {"name": "test-volume"}

        # Add volume
        volume_data = {"name": "test-volume", "driver": "local"}
        container_list.add_volume(volume_data)

        # Verify manager called
        container_list.volume_manager.add_volume.assert_called_once_with(volume_data)
        # Verify backward compatibility
        assert container_list.selected_volume_data == {"name": "test-volume"}

    def test_add_network(self, container_list):
        """Test add_network method."""
        # Mock network manager
        container_list.network_manager.add_network = Mock()
        container_list.network_manager.selected_network_data = {"name": "test-network"}

        # Add network
        network_data = {"name": "test-network", "driver": "bridge"}
        container_list.add_network(network_data)

        # Verify manager called
        container_list.network_manager.add_network.assert_called_once_with(network_data)
        # Verify backward compatibility
        assert container_list.selected_network_data == {"name": "test-network"}

    def test_add_stack(self, container_list):
        """Test add_stack method."""
        # Mock stack manager
        container_list.stack_manager.add_stack = Mock()
        container_list.stack_manager.selected_stack_data = {"name": "test-stack"}

        # Add stack
        container_list.add_stack(
            name="test-stack",
            config_file="/path/to/compose.yml",
            running=2,
            exited=1,
            total=3,
            can_recreate=True,
            has_compose_file=True
        )

        # Verify manager called
        container_list.stack_manager.add_stack.assert_called_once_with(
            "test-stack", "/path/to/compose.yml", 2, 1, 3, True, True
        )
        # Verify backward compatibility
        assert container_list.selected_stack_data == {"name": "test-stack"}

    def test_add_container_to_stack(self, container_list):
        """Test add_container_to_stack method."""
        # Mock stack manager
        container_list.stack_manager.add_container_to_stack = Mock()
        container_list.stack_manager.selected_container_data = {"id": "test-container"}

        # Add container
        container_data = {"id": "test-container", "name": "test"}
        container_list.add_container_to_stack("test-stack", container_data)

        # Verify manager called
        container_list.stack_manager.add_container_to_stack.assert_called_once_with(
            "test-stack", container_data
        )
        # Verify backward compatibility
        assert container_list.selected_container_data == {"id": "test-container"}

    def test_add_container_to_network(self, container_list):
        """Test add_container_to_network method."""
        # Mock network manager
        container_list.network_manager.add_container_to_network = Mock()

        # Add container
        container_data = {"id": "test-container", "name": "test"}
        container_list.add_container_to_network("test-network", container_data)

        # Verify manager called
        container_list.network_manager.add_container_to_network.assert_called_once_with(
            "test-network", container_data
        )

    def test_select_image(self, container_list):
        """Test select_image method."""
        # Mock image manager
        container_list.image_manager.select_image = Mock()

        # Select image
        container_list.select_image("test-image-id")

        # Verify manager called
        container_list.image_manager.select_image.assert_called_once_with("test-image-id")

    def test_select_volume(self, container_list):
        """Test select_volume method."""
        # Mock volume manager
        container_list.volume_manager.select_volume = Mock()

        # Select volume
        container_list.select_volume("test-volume")

        # Verify manager called
        container_list.volume_manager.select_volume.assert_called_once_with("test-volume")

    def test_select_network(self, container_list):
        """Test select_network method."""
        # Mock network manager
        container_list.network_manager.select_network = Mock()

        # Select network
        container_list.select_network("test-network")

        # Verify manager called
        container_list.network_manager.select_network.assert_called_once_with("test-network")

    def test_select_stack(self, container_list):
        """Test select_stack method."""
        # Mock stack manager
        container_list.stack_manager.select_stack = Mock()

        # Select stack
        container_list.select_stack("test-stack")

        # Verify manager called
        container_list.stack_manager.select_stack.assert_called_once_with("test-stack")

    def test_select_container(self, container_list):
        """Test select_container method."""
        # Mock stack manager
        container_list.stack_manager.select_container = Mock()

        # Select container
        container_list.select_container("test-container-id")

        # Verify manager called
        container_list.stack_manager.select_container.assert_called_once_with("test-container-id")

    def test_clear(self, container_list):
        """Test clear method."""
        # Mock managers and state
        container_list.volume_manager.save_expanded_state = Mock()
        container_list.network_manager.save_expanded_state = Mock()
        container_list.stack_manager.save_expanded_state = Mock()

        # Set up some headers and tables
        container_list.volume_headers = {"vol1": Mock(), "vol2": Mock()}
        container_list.stack_headers = {"stack1": Mock()}
        container_list.stack_tables = {"stack1": Mock()}
        container_list.network_headers = {"net1": Mock()}
        container_list.network_tables = {"net1": Mock()}
        container_list.container_rows = {"cont1": ("stack1", 0)}
        container_list.network_rows = {"cont1": ("net1", 0)}

        # Mock remove_children
        container_list.remove_children = Mock()

        # Call clear
        container_list.clear()

        # Verify expanded states saved
        container_list.volume_manager.save_expanded_state.assert_called_once()
        container_list.network_manager.save_expanded_state.assert_called_once()
        container_list.stack_manager.save_expanded_state.assert_called_once()

        # Verify all collections cleared
        assert len(container_list.volume_headers) == 0
        assert len(container_list.stack_tables) == 0
        assert len(container_list.stack_headers) == 0
        assert len(container_list.network_tables) == 0
        assert len(container_list.network_headers) == 0
        assert len(container_list.container_rows) == 0
        assert len(container_list.network_rows) == 0

        # Verify children removed
        container_list.remove_children.assert_called_once()

    def test_on_mount_initial_load(self, container_list):
        """Test on_mount method during initial load."""
        # Set up initial load state
        container_list._initial_load_complete = False

        # Mock children property to return empty list
        with patch.object(type(container_list), 'children', new_callable=PropertyMock) as mock_children:
            mock_children.return_value = []

            # Mock mount method
            container_list.mount = Mock()

            # Mock Static class to avoid event loop requirement
            with patch('DockTUI.ui.containers.Static') as mock_static_cls:
                mock_static_instance = Mock()
                mock_static_cls.return_value = mock_static_instance

                # Call on_mount
                container_list.on_mount()

                # Verify loading message created
                mock_static_cls.assert_called_once()
                assert container_list.loading_message is mock_static_instance

                # Verify styles set
                assert mock_static_instance.styles.width == "100%"
                assert mock_static_instance.styles.height == "100%"
                assert mock_static_instance.styles.content_align == ("center", "middle")
                assert mock_static_instance.styles.padding == (2, 0)

                # Verify mounted
                container_list.mount.assert_called_once_with(mock_static_instance)

    def test_on_mount_with_stacks(self, container_list):
        """Test on_mount method with existing stacks."""
        # Set up state
        container_list._initial_load_complete = True

        # Mock children property to return non-empty list
        with patch.object(type(container_list), 'children', new_callable=PropertyMock) as mock_children:
            mock_children.return_value = [Mock()]

            # Create mock stack header and table
            mock_header = Mock()
            mock_header.stack_name = "test-stack"
            mock_header.expanded = False
            mock_table = Mock()
            mock_table.row_count = 5

            container_list.stack_headers = {"test-stack": mock_header}
            container_list.stack_tables = {"test-stack": mock_table}
            container_list.select_stack = Mock()

            # Call on_mount
            container_list.on_mount()

            # Verify first stack focused and expanded
            mock_header.focus.assert_called_once()
            assert mock_header.expanded is True
            assert mock_table.styles.display == "block"

            # Verify stack selected
            container_list.select_stack.assert_called_once_with("test-stack")

            # Verify table blurred
            mock_table.blur.assert_called_once()

    def test_on_mount_with_search_input_focused(self, container_list):
        """Test on_mount when search input is focused."""
        # Set up state
        container_list._initial_load_complete = True

        # Mock children property to return non-empty list
        with patch.object(type(container_list), 'children', new_callable=PropertyMock) as mock_children:
            mock_children.return_value = [Mock()]

            # Mock search input focused
            mock_search = Mock()
            mock_search.id = "search-input"

            # Update the screen's focused widget
            with patch.object(ContainerList, 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen = MockScreen(focused=mock_search)
                mock_screen_prop.return_value = mock_screen

                # Create mock stack header and table
                mock_header = Mock()
                mock_header.stack_name = "test-stack"
                mock_header.expanded = False
                mock_table = Mock()
                mock_table.row_count = 5
                mock_table.styles = Mock()
                mock_table.blur = Mock()

                container_list.stack_headers = {"test-stack": mock_header}
                container_list.stack_tables = {"test-stack": mock_table}
                container_list.select_stack = Mock()

                # Call on_mount
                container_list.on_mount()

                # Verify header not focused when search is active
                mock_header.focus.assert_not_called()

    def test_update_container_status(self, container_list):
        """Test update_container_status method."""
        # Call method
        container_list.update_container_status("cont123", "starting...")

        # Verify status override stored
        assert hasattr(container_list, "_status_overrides")
        assert container_list._status_overrides["cont123"] == "starting..."

        # Update again
        container_list.update_container_status("cont123", "stopping...")
        assert container_list._status_overrides["cont123"] == "stopping..."

    def test_clear_status_override(self, container_list):
        """Test clear_status_override method."""
        # Set up status override
        container_list._status_overrides = {"cont123": "starting...", "cont456": "stopping..."}

        # Clear one override
        container_list.clear_status_override("cont123")

        # Verify removed
        assert "cont123" not in container_list._status_overrides
        assert container_list._status_overrides["cont456"] == "stopping..."

        # Clear non-existent override (should not raise)
        container_list.clear_status_override("cont789")

    def test_update_footer_with_selection(self, container_list):
        """Test _update_footer_with_selection method."""
        # Mock footer formatter
        container_list.footer_formatter.update_footer_with_selection = Mock()

        # Call method
        container_list._update_footer_with_selection()

        # Verify formatter called
        container_list.footer_formatter.update_footer_with_selection.assert_called_once()

    def test_restore_selection(self, container_list):
        """Test _restore_selection method."""
        # Mock navigation handler
        container_list.navigation_handler.restore_selection = Mock()

        # Call method
        container_list._restore_selection()

        # Verify handler called
        container_list.navigation_handler.restore_selection.assert_called_once()

    def test_update_cursor_visibility(self, container_list):
        """Test _update_cursor_visibility method."""
        # Mock navigation handler
        container_list.navigation_handler.update_cursor_visibility = Mock()

        # Call method
        container_list._update_cursor_visibility()

        # Verify handler called
        container_list.navigation_handler.update_cursor_visibility.assert_called_once()

    def test_action_cursor_up(self, container_list):
        """Test action_cursor_up method."""
        # Mock navigation handler
        container_list.navigation_handler.handle_cursor_up = Mock()

        # Call action
        container_list.action_cursor_up()

        # Verify handler called
        container_list.navigation_handler.handle_cursor_up.assert_called_once()

    def test_action_cursor_down(self, container_list):
        """Test action_cursor_down method."""
        # Mock navigation handler
        container_list.navigation_handler.handle_cursor_down = Mock()

        # Call action
        container_list.action_cursor_down()

        # Verify handler called
        container_list.navigation_handler.handle_cursor_down.assert_called_once()

    def test_on_section_header_clicked_stacks(self, container_list):
        """Test on_section_header_clicked for stacks section."""
        # Create mock event
        mock_header = Mock()
        mock_header.collapsed = True
        mock_event = Mock()
        mock_event.section_header = mock_header

        # Set up section headers and containers
        container_list.stacks_section_header = mock_header
        container_list.stacks_container = Mock()

        # Call handler
        container_list.on_section_header_clicked(mock_event)

        # Verify state updated
        assert container_list.stacks_section_collapsed is True
        assert container_list.stacks_container.styles.display == "none"

    def test_on_section_header_clicked_images(self, container_list):
        """Test on_section_header_clicked for images section."""
        # Create mock event
        mock_header = Mock()
        mock_header.collapsed = False
        mock_event = Mock()
        mock_event.section_header = mock_header

        # Set up section headers and containers
        container_list.images_section_header = mock_header
        container_list.images_container = Mock()
        container_list.image_manager._table_initialized = False
        container_list.image_manager.show_loading_message = Mock()

        # Call handler
        container_list.on_section_header_clicked(mock_event)

        # Verify state updated
        assert container_list.images_section_collapsed is False
        assert container_list.images_container.styles.display == "block"
        # Verify loading message shown for uninitialized table
        container_list.image_manager.show_loading_message.assert_called_once()

    def test_on_image_header_selected(self, container_list):
        """Test on_image_header_selected event handler."""
        # Mock event
        mock_event = Mock()
        mock_event.image_header.image_id = "test-image-id"
        container_list.select_image = Mock()

        # Call handler
        container_list.on_image_header_selected(mock_event)

        # Verify selection
        container_list.select_image.assert_called_once_with("test-image-id")

    def test_on_volume_header_clicked(self, container_list):
        """Test on_volume_header_clicked event handler."""
        # Mock event
        mock_event = Mock()
        mock_event.volume_header.volume_name = "test-volume"
        container_list.select_volume = Mock()

        # Call handler
        container_list.on_volume_header_clicked(mock_event)

        # Verify selection
        container_list.select_volume.assert_called_once_with("test-volume")

    def test_on_network_header_selected(self, container_list):
        """Test on_network_header_selected event handler."""
        # Mock event
        mock_event = Mock()
        mock_event.network_header.network_name = "test-network"
        container_list.select_network = Mock()

        # Call handler
        container_list.on_network_header_selected(mock_event)

        # Verify selection
        container_list.select_network.assert_called_once_with("test-network")

    def test_on_stack_header_clicked(self, container_list):
        """Test on_stack_header_clicked event handler."""
        # Mock event
        mock_event = Mock()
        mock_event.stack_header.stack_name = "test-stack"
        container_list.select_stack = Mock()

        # Call handler
        container_list.on_stack_header_clicked(mock_event)

        # Verify selection
        container_list.select_stack.assert_called_once_with("test-stack")

    def test_on_data_table_row_selected_images(self, container_list):
        """Test on_data_table_row_selected for images table."""
        # Mock event and table
        mock_table = Mock()
        mock_event = Mock()
        mock_event.data_table = mock_table
        mock_event.row_key = "row1"

        # Set up image manager
        container_list.image_manager.images_table = mock_table
        container_list.image_manager.handle_selection = Mock()

        # Call handler
        container_list.on_data_table_row_selected(mock_event)

        # Verify image manager handles selection
        container_list.image_manager.handle_selection.assert_called_once_with("row1")

    def test_on_data_table_row_selected_stack_container(self, container_list):
        """Test on_data_table_row_selected for stack container table."""
        # Mock event and table
        mock_table = Mock()
        mock_table.get_row_index.return_value = 2
        mock_table.row_count = 5
        mock_table.get_cell_at.return_value = "container-123"

        mock_event = Mock()
        mock_event.data_table = mock_table
        mock_event.row_key = "row2"

        # Set up stack tables
        container_list.stack_tables = {"test-stack": mock_table}
        container_list.select_container = Mock()
        container_list.image_manager.images_table = None

        # Call handler
        container_list.on_data_table_row_selected(mock_event)

        # Verify container selected
        mock_table.get_row_index.assert_called_once_with("row2")
        mock_table.get_cell_at.assert_called_once_with((2, 0))
        container_list.select_container.assert_called_once_with("container-123")

    def test_mount_section(self, container_list):
        """Test _mount_section method."""
        # Mock widgets
        mock_header = Mock()
        mock_container = Mock()
        container_list.mount = Mock()

        # Call method with collapsed=True
        container_list._mount_section(mock_header, mock_container, collapsed=True)

        # Verify mounting
        assert container_list.mount.call_count == 2
        container_list.mount.assert_any_call(mock_header)
        container_list.mount.assert_any_call(mock_container)
        assert mock_container.styles.display == "none"

        # Call with collapsed=False
        container_list._mount_section(mock_header, mock_container, collapsed=False)
        assert mock_container.styles.display == "block"

    def test_mount_new_containers(self, container_list):
        """Test _mount_new_containers method."""
        # Mock containers
        mock_parent = Mock()
        mock_container1 = Mock()
        mock_header1 = Mock()
        mock_header1.expanded = True
        mock_table1 = Mock()

        mock_container2 = Mock()
        mock_header2 = Mock()
        mock_header2.expanded = False
        mock_table2 = Mock()

        containers_dict = {
            "item1": (mock_container1, mock_header1, mock_table1),
            "item2": (mock_container2, mock_header2, mock_table2),
        }

        # Call method with tables
        container_list._mount_new_containers(containers_dict, mock_parent, with_table=True)

        # Verify mounting
        mock_parent.mount.assert_any_call(mock_container1)
        mock_parent.mount.assert_any_call(mock_container2)
        mock_container1.mount.assert_any_call(mock_header1)
        mock_container1.mount.assert_any_call(mock_table1)
        mock_container2.mount.assert_any_call(mock_header2)
        mock_container2.mount.assert_any_call(mock_table2)

        # Verify table visibility
        assert mock_table1.styles.display == "block"
        assert mock_table2.styles.display == "none"

    def test_mount_all_sections(self, container_list):
        """Test _mount_all_sections method."""
        # Mock methods and attributes
        container_list.remove_children = Mock()
        container_list._ensure_section_headers = Mock()
        container_list._mount_section = Mock()
        container_list._mount_new_containers = Mock()

        # Create mock section headers and containers
        container_list.stacks_section_header = Mock()
        container_list.stacks_container = Mock()
        container_list.images_section_header = Mock()
        container_list.images_container = Mock()
        container_list.networks_section_header = Mock()
        container_list.networks_container = Mock()
        container_list.volumes_section_header = Mock()
        container_list.volumes_container = Mock()

        # Set collapse states
        container_list.stacks_section_collapsed = False
        container_list.images_section_collapsed = True
        container_list.networks_section_collapsed = True
        container_list.volumes_section_collapsed = False

        # Set new containers
        container_list.new_stack_containers = {"stack1": Mock()}
        container_list.new_network_containers = {"net1": Mock()}
        container_list.new_volume_containers = {"vol1": Mock()}

        # Call method
        container_list._mount_all_sections()

        # Verify children removed and headers ensured
        container_list.remove_children.assert_called_once()
        container_list._ensure_section_headers.assert_called_once()
        assert container_list._pending_clear is False

        # Verify sections mounted in correct order
        expected_mount_calls = [
            call(
                container_list.stacks_section_header,
                container_list.stacks_container,
                False
            ),
            call(
                container_list.images_section_header,
                container_list.images_container,
                True
            ),
            call(
                container_list.networks_section_header,
                container_list.networks_container,
                True
            ),
            call(
                container_list.volumes_section_header,
                container_list.volumes_container,
                False
            ),
        ]
        container_list._mount_section.assert_has_calls(expected_mount_calls)

        # Verify new containers mounted
        assert container_list._mount_new_containers.call_count == 3

    def test_update_existing_sections(self, container_list):
        """Test _update_existing_sections method."""
        # Mock existing containers
        mock_volume_container = Mock()
        mock_volume_header = Mock(spec=VolumeHeader)
        mock_volume_header._update_content = Mock()
        mock_volume_container.children = [mock_volume_header]
        mock_volume_container.remove = Mock()

        mock_network_container = Mock()
        mock_network_header = Mock(spec=NetworkHeader)
        mock_network_header._update_content = Mock()
        mock_network_table = Mock(spec=DataTable)
        mock_network_table.styles = Mock()
        mock_network_container.children = [mock_network_header, mock_network_table]
        mock_network_container.remove = Mock()

        container_list.existing_volume_containers = {"vol1": mock_volume_container}
        container_list.existing_network_containers = {"net1": mock_network_container}
        container_list.existing_stack_containers = {}

        # Set up headers
        container_list.volume_headers = {"vol1": Mock()}
        mock_net_header = Mock()
        mock_net_header.expanded = True
        container_list.network_headers = {"net1": mock_net_header}
        container_list.stack_headers = {}

        # Mock methods
        container_list._ensure_section_headers = Mock()
        container_list.mount = Mock()
        container_list._mount_new_containers = Mock()

        # Create section headers and containers
        container_list.stacks_section_header = Mock()
        container_list.stacks_container = Mock()
        container_list.images_section_header = Mock()
        container_list.images_container = Mock()
        container_list.networks_section_header = Mock()
        container_list.networks_container = Mock()
        container_list.volumes_section_header = Mock()
        container_list.volumes_container = Mock()

        # Mock children property
        with patch.object(type(container_list), 'children', new_callable=PropertyMock) as mock_children:
            # Set children to simulate some sections already mounted
            mock_children.return_value = [
                container_list.stacks_section_header,
                container_list.stacks_container
            ]

            # Set new containers
            container_list.new_stack_containers = {}
            container_list.new_network_containers = {}
            container_list.new_volume_containers = {}

            # Call method
            container_list._update_existing_sections()

            # Verify headers ensured
            container_list._ensure_section_headers.assert_called_once()

            # Verify missing sections mounted
            assert container_list.mount.call_count >= 4  # At least images and networks sections

            # Verify visibility states updated
            assert container_list.stacks_container.styles.display == "block"  # default not collapsed
            assert container_list.images_container.styles.display == "none"  # collapsed by default