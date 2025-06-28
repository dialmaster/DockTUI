"""Tests for the header widgets."""

import time
from unittest.mock import Mock, MagicMock, patch, PropertyMock

import pytest
from rich.text import Text

from DockTUI.ui.widgets.headers import (
    ImageHeader,
    NetworkHeader,
    SectionHeader,
    StackHeader,
    VolumeHeader,
)


class TestSectionHeader:
    """Test cases for SectionHeader class."""

    def test_init(self):
        """Test SectionHeader initialization."""
        # Create instance without calling parent __init__
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(SectionHeader)
            header.update = Mock()
            header.can_focus = None

            # Call the actual init
            SectionHeader.__init__(header, "Test Section")

            assert header.base_title == "Test Section"
            assert not header.collapsed
            assert header.can_focus is False
            # Check that update was called during init
            header.update.assert_called()

    def test_init_collapsed(self):
        """Test SectionHeader initialization with collapsed state."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(SectionHeader)
            header.update = Mock()
            header.can_focus = None

            SectionHeader.__init__(header, "Collapsed Section", collapsed=True)

            assert header.base_title == "Collapsed Section"
            assert header.collapsed

    def test_update_content_expanded(self):
        """Test content update when expanded."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(SectionHeader)
            header.update = Mock()
            header.can_focus = None

            SectionHeader.__init__(header, "Test Section")
            header.collapsed = False
            header.update.reset_mock()

            header._update_content()

            # Check that update was called with expanded icon
            header.update.assert_called_once()
            content = header.update.call_args[0][0]
            assert "▼" in content.plain
            assert "Test Section" in content.plain

    def test_update_content_collapsed(self):
        """Test content update when collapsed."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(SectionHeader)
            header.update = Mock()
            header.can_focus = None

            SectionHeader.__init__(header, "Test Section")
            header.collapsed = True
            header.update.reset_mock()

            header._update_content()

            # Check that update was called with collapsed icon
            header.update.assert_called_once()
            content = header.update.call_args[0][0]
            assert "▶" in content.plain
            assert "Test Section" in content.plain

    def test_toggle(self):
        """Test toggling expanded/collapsed state."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(SectionHeader)
            header.update = Mock()
            header.can_focus = None

            SectionHeader.__init__(header, "Test Section")
            header.collapsed = False

            initial_state = header.collapsed
            header.toggle()
            assert header.collapsed == (not initial_state)

            header.toggle()
            assert header.collapsed == initial_state

    def test_on_click(self):
        """Test click event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(SectionHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.can_focus = None

            SectionHeader.__init__(header, "Test Section")
            header.collapsed = False

            header.on_click()

            # Check that toggle was called
            assert header.collapsed

            # Check that Clicked message was posted
            header.post_message.assert_called()
            message = header.post_message.call_args[0][0]
            assert isinstance(message, SectionHeader.Clicked)
            assert message.section_header == header


class TestNetworkHeader:
    """Test cases for NetworkHeader class."""

    def test_init(self):
        """Test NetworkHeader initialization."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks={"stack1", "stack2"}
            )

            assert header.network_name == "test-network"
            assert header.driver == "bridge"
            assert header.scope == "local"
            assert header.subnet == "172.17.0.0/16"
            assert header.total_containers == 3
            assert header.connected_stacks == {"stack1", "stack2"}
            assert not header.expanded
            assert header._last_click_time == 0
            assert header.can_focus is True

    def test_update_content_with_containers(self):
        """Test content update with containers."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks={"stack1", "stack2"}
            )
            header.expanded = False
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check content includes expected elements
            assert "▶" in content.plain  # Collapsed icon
            assert "test-network" in content.plain
            assert "bridge/local" in content.plain
            assert "172.17.0.0/16" in content.plain
            assert "Containers: 3" in content.plain
            assert "stack1" in content.plain
            assert "stack2" in content.plain

    def test_update_content_expanded(self):
        """Test content update when expanded."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks={"stack1", "stack2"}
            )
            header.expanded = True
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check expanded icon
            assert "▼" in content.plain

    def test_update_content_no_containers(self):
        """Test content update with no containers."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="empty-network",
                driver="bridge",
                scope="local",
                subnet="172.18.0.0/16",
                total_containers=0,
                connected_stacks=set()
            )
            header.expanded = False
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Should not have expand/collapse icon
            assert "▶" not in content.plain
            assert "▼" not in content.plain
            assert "No stacks" in content.plain

    def test_update_content_long_stacks_list(self):
        """Test content truncation for long stacks list."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="busy-network",
                driver="bridge",
                scope="local",
                subnet="172.19.0.0/16",
                total_containers=10,
                connected_stacks={f"very-long-stack-name-{i}" for i in range(10)}
            )
            header.expanded = False
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check that stacks text was truncated
            assert "..." in content.plain

    def test_on_focus(self):
        """Test focus event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.post_message = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks=set()
            )

            header.on_focus()

            header.refresh.assert_called_once()
            header.post_message.assert_called_once()
            message = header.post_message.call_args[0][0]
            assert isinstance(message, NetworkHeader.Selected)
            assert message.network_header == header

    def test_on_blur(self):
        """Test blur event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks=set()
            )

            header.on_blur()
            header.refresh.assert_called_once()

    def test_toggle_with_containers(self):
        """Test toggling with containers."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks=set()
            )
            header.expanded = False

            initial_state = header.expanded
            header.toggle()
            assert header.expanded == (not initial_state)

    def test_toggle_without_containers(self):
        """Test toggling without containers does nothing."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=0,
                connected_stacks=set()
            )
            header.expanded = False

            initial_state = header.expanded
            header.toggle()
            assert header.expanded == initial_state

    def test_on_click_single(self):
        """Test single click event."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks=set()
            )
            header._last_click_time = 0

            header.on_click()

            header.post_message.assert_called_once()
            message = header.post_message.call_args[0][0]
            assert isinstance(message, NetworkHeader.Clicked)

    @patch('DockTUI.ui.widgets.headers.time.time')
    def test_on_click_double(self, mock_time):
        """Test double click event."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks=set()
            )
            header._last_click_time = 0

            # Mock screen for query_one
            mock_screen = Mock()
            mock_screen.focused = None
            mock_container_list = Mock()
            mock_screen.query_one.return_value = mock_container_list

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                # Set up double click timing
                mock_time.side_effect = [1.0, 1.3]  # 0.3 seconds apart

                # First click
                header.on_click()
                # Second click (double click)
                header.on_click()

                # Should focus the header
                header.focus.assert_called_once()

                # Should call container list action
                mock_container_list.action_toggle_network.assert_called_once()

    @patch('DockTUI.ui.widgets.headers.time.time')
    def test_on_click_double_search_focused(self, mock_time):
        """Test double click when search is focused."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(NetworkHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            NetworkHeader.__init__(
                header,
                network_name="test-network",
                driver="bridge",
                scope="local",
                subnet="172.17.0.0/16",
                total_containers=3,
                connected_stacks=set()
            )
            header._last_click_time = 0

            # Mock screen with focused search widget
            mock_screen = Mock()
            mock_search = Mock()
            mock_search.id = "search-input"
            mock_screen.focused = mock_search

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                # Set up double click timing
                mock_time.side_effect = [1.0, 1.3]

                # First click
                header.on_click()
                # Second click (double click)
                header.on_click()

                # Should NOT focus the header when search is focused
                header.focus.assert_not_called()


class TestVolumeHeader:
    """Test cases for VolumeHeader class."""

    def test_init(self):
        """Test VolumeHeader initialization."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="test-volume",
                driver="local",
                mountpoint="/var/lib/docker/volumes/test-volume/_data",
                created="2024-01-15T10:30:00Z",
                stack="test-stack",
                scope="local"
            )

            assert header.volume_name == "test-volume"
            assert header.driver == "local"
            assert header.mountpoint == "/var/lib/docker/volumes/test-volume/_data"
            assert header.created == "2024-01-15T10:30:00Z"
            assert header.stack == "test-stack"
            assert header.scope == "local"
            assert header.can_focus is True

    def test_update_content_with_stack(self):
        """Test content update with stack association."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="test-volume",
                driver="local",
                mountpoint="/var/lib/docker/volumes/test-volume/_data",
                created="2024-01-15T10:30:00Z",
                stack="test-stack",
                scope="local"
            )
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check content includes expected elements
            assert "test-volume" in content.plain
            assert "local/local" in content.plain
            assert "test-stack" in content.plain
            assert "/var/lib/docker/volumes/test-volume/_data" in content.plain

    def test_update_content_no_stack(self):
        """Test content update without stack association."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="orphan-volume",
                driver="local",
                mountpoint="/var/lib/docker/volumes/orphan-volume/_data",
                created="2024-01-15T10:30:00Z",
                stack=None,
                scope="local"
            )
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            assert "No stack association" in content.plain

    def test_update_content_long_mountpoint(self):
        """Test mountpoint truncation for long paths."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="test-volume",
                driver="local",
                mountpoint="/very/long/path/that/should/be/truncated/because/it/is/too/long/to/display/fully",
                created="2024-01-15T10:30:00Z",
                stack="test-stack",
                scope="local"
            )
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check that mountpoint was truncated
            assert "..." in content.plain
            # Extract mount part and check length
            mount_line = [line for line in content.plain.split('\n') if 'Mount:' in line][0]
            mount_text = mount_line.split('Mount: ')[1]
            assert len(mount_text) <= 50

    def test_on_focus(self):
        """Test focus event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.post_message = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="test-volume",
                driver="local",
                mountpoint="/var/lib/docker/volumes/test-volume/_data",
                created="2024-01-15T10:30:00Z",
                stack="test-stack",
                scope="local"
            )

            header.on_focus()

            header.refresh.assert_called_once()
            header.post_message.assert_called_once()
            message = header.post_message.call_args[0][0]
            assert isinstance(message, VolumeHeader.Selected)
            assert message.volume_header == header

    def test_on_blur(self):
        """Test blur event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="test-volume",
                driver="local",
                mountpoint="/var/lib/docker/volumes/test-volume/_data",
                created="2024-01-15T10:30:00Z",
                stack="test-stack",
                scope="local"
            )

            header.on_blur()
            header.refresh.assert_called_once()

    def test_on_click(self):
        """Test click event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="test-volume",
                driver="local",
                mountpoint="/var/lib/docker/volumes/test-volume/_data",
                created="2024-01-15T10:30:00Z",
                stack="test-stack",
                scope="local"
            )

            # Mock screen
            mock_screen = Mock()
            mock_screen.focused = None

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                header.on_click()

                header.post_message.assert_called_once()
                message = header.post_message.call_args[0][0]
                assert isinstance(message, VolumeHeader.Clicked)

                header.focus.assert_called_once()

    def test_on_click_search_focused(self):
        """Test click when search is focused."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(VolumeHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            VolumeHeader.__init__(
                header,
                volume_name="test-volume",
                driver="local",
                mountpoint="/var/lib/docker/volumes/test-volume/_data",
                created="2024-01-15T10:30:00Z",
                stack="test-stack",
                scope="local"
            )

            # Mock screen with focused search
            mock_screen = Mock()
            mock_search = Mock()
            mock_search.id = "search-input"
            mock_screen.focused = mock_search

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                header.on_click()

                # Should NOT focus when search is focused
                header.focus.assert_not_called()


class TestStackHeader:
    """Test cases for StackHeader class."""

    def test_init(self):
        """Test StackHeader initialization."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3,
                can_recreate=True,
                has_compose_file=True
            )

            assert header.stack_name == "test-stack"
            assert header.config_file == "/path/to/docker-compose.yml"
            assert header.running == 2
            assert header.exited == 1
            assert header.total == 3
            assert header.can_recreate
            assert header.has_compose_file
            assert header.expanded  # Starts expanded
            assert header._last_click_time == 0
            assert header.can_focus is True

    def test_update_content_expanded(self):
        """Test content update when expanded."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3,
                can_recreate=True,
                has_compose_file=True
            )
            header.expanded = True
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check content includes expected elements
            assert "▼" in content.plain  # Expanded icon
            assert "test-stack" in content.plain
            assert "/path/to/docker-compose.yml" in content.plain
            assert "Running: 2" in content.plain
            assert "Exited: 1" in content.plain
            assert "Total: 3" in content.plain

    def test_update_content_collapsed(self):
        """Test content update when collapsed."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3,
                can_recreate=True,
                has_compose_file=True
            )
            header.expanded = False
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check collapsed icon
            assert "▶" in content.plain

    def test_update_content_no_compose_file(self):
        """Test content update when compose file not accessible."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="broken-stack",
                config_file="/missing/docker-compose.yml",
                running=0,
                exited=2,
                total=2,
                can_recreate=False,
                has_compose_file=True
            )
            header.expanded = True
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            assert "[compose file not accessible]" in content.plain

    def test_on_focus(self):
        """Test focus event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.post_message = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3
            )

            header.on_focus()

            header.refresh.assert_called_once()
            header.post_message.assert_called_once()
            message = header.post_message.call_args[0][0]
            assert isinstance(message, StackHeader.Selected)
            assert message.stack_header == header

    def test_on_blur(self):
        """Test blur event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3
            )

            header.on_blur()
            header.refresh.assert_called_once()

    def test_toggle(self):
        """Test toggling expanded/collapsed state."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3
            )
            header.expanded = True

            initial_state = header.expanded
            header.toggle()
            assert header.expanded == (not initial_state)

    def test_on_click_single(self):
        """Test single click event."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3
            )
            header._last_click_time = 0

            header.on_click()

            header.post_message.assert_called_once()
            message = header.post_message.call_args[0][0]
            assert isinstance(message, StackHeader.Clicked)

    @patch('DockTUI.ui.widgets.headers.time.time')
    def test_on_click_double(self, mock_time):
        """Test double click event."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3
            )
            header._last_click_time = 0

            # Mock screen
            mock_screen = Mock()
            mock_screen.focused = None
            mock_container_list = Mock()
            mock_screen.query_one.return_value = mock_container_list

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                # Set up double click timing
                mock_time.side_effect = [1.0, 1.3]  # 0.3 seconds apart

                # First click
                header.on_click()
                # Second click (double click)
                header.on_click()

                # Should focus the header
                header.focus.assert_called_once()

                # Should call container list action
                mock_container_list.action_toggle_stack.assert_called_once()

    @patch('DockTUI.ui.widgets.headers.time.time')
    def test_on_click_double_search_focused(self, mock_time):
        """Test double click when search is focused."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(StackHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            StackHeader.__init__(
                header,
                stack_name="test-stack",
                config_file="/path/to/docker-compose.yml",
                running=2,
                exited=1,
                total=3
            )
            header._last_click_time = 0

            # Mock screen with focused search
            mock_screen = Mock()
            mock_search = Mock()
            mock_search.id = "search-input"
            mock_screen.focused = mock_search

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                # Set up double click timing
                mock_time.side_effect = [1.0, 1.3]

                # First click
                header.on_click()
                # Second click (double click)
                header.on_click()

                # Should NOT focus the header when search is focused
                header.focus.assert_not_called()


class TestImageHeader:
    """Test cases for ImageHeader class."""

    def test_init(self):
        """Test ImageHeader initialization."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="abc123def456",
                tags=["myapp:latest", "myapp:v1.0"],
                created="2024-01-15T10:30:00Z",
                size="500MB",
                containers=2,
                architecture="amd64",
                os="linux"
            )

            assert header.image_id == "abc123def456"
            assert header.tags == ["myapp:latest", "myapp:v1.0"]
            assert header.created == "2024-01-15T10:30:00Z"
            assert header.image_size == "500MB"
            assert header.containers == 2
            assert header.architecture == "amd64"
            assert header.os == "linux"
            assert header.can_focus is True

    def test_update_content_with_tags(self):
        """Test content update with tags."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="abc123def456",
                tags=["myapp:latest", "myapp:v1.0"],
                created="2024-01-15T10:30:00Z",
                size="500MB",
                containers=2,
                architecture="amd64",
                os="linux"
            )
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check content includes expected elements
            assert "abc123def456"[:12] in content.plain  # Short ID
            assert "myapp:latest" in content.plain
            assert "myapp:v1.0" in content.plain
            assert "500MB" in content.plain
            assert "2 containers" in content.plain
            assert "linux/amd64" in content.plain

    def test_update_content_no_tags(self):
        """Test content update without tags."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="def789ghi012",
                tags=[],
                created="2024-01-15T10:30:00Z",
                size="100MB",
                containers=0,
                architecture="arm64",
                os="linux"
            )
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            assert "<none>" in content.plain
            assert "0 container" in content.plain  # Singular

    def test_update_content_long_tags(self):
        """Test tag truncation for long tag lists."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="xyz789abc123",
                tags=[f"very-long-tag-name-{i}:version-{i}" for i in range(10)],
                created="2024-01-15T10:30:00Z",
                size="1GB",
                containers=5,
                architecture="amd64",
                os="linux"
            )
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            # Check that tags were truncated
            assert "..." in content.plain

    def test_update_content_single_container(self):
        """Test content with single container."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="single123",
                tags=["app:latest"],
                created="2024-01-15T10:30:00Z",
                size="200MB",
                containers=1,
                architecture="amd64",
                os="linux"
            )
            header.update.reset_mock()

            header._update_content()

            # Check that update was called
            header.update.assert_called_once()
            content = header.update.call_args[0][0]

            assert "1 container" in content.plain  # Singular, not "1 containers"

    def test_on_focus(self):
        """Test focus event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.post_message = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="abc123def456",
                tags=["myapp:latest"],
                created="2024-01-15T10:30:00Z",
                size="500MB",
                containers=2,
                architecture="amd64",
                os="linux"
            )

            header.on_focus()

            header.refresh.assert_called_once()
            header.post_message.assert_called_once()
            message = header.post_message.call_args[0][0]
            assert isinstance(message, ImageHeader.Selected)
            assert message.image_header == header

    def test_on_blur(self):
        """Test blur event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.refresh = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="abc123def456",
                tags=["myapp:latest"],
                created="2024-01-15T10:30:00Z",
                size="500MB",
                containers=2,
                architecture="amd64",
                os="linux"
            )

            header.on_blur()
            header.refresh.assert_called_once()

    def test_on_click(self):
        """Test click event handling."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="abc123def456",
                tags=["myapp:latest"],
                created="2024-01-15T10:30:00Z",
                size="500MB",
                containers=2,
                architecture="amd64",
                os="linux"
            )

            # Mock screen
            mock_screen = Mock()
            mock_screen.focused = None

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                header.on_click()

                header.post_message.assert_called_once()
                message = header.post_message.call_args[0][0]
                assert isinstance(message, ImageHeader.Clicked)

                header.focus.assert_called_once()

    def test_on_click_search_focused(self):
        """Test click when search is focused."""
        with patch('DockTUI.ui.widgets.headers.Static.__init__', return_value=None):
            header = object.__new__(ImageHeader)
            header.update = Mock()
            header.post_message = Mock()
            header.focus = Mock()
            header.can_focus = None

            ImageHeader.__init__(
                header,
                image_id="abc123def456",
                tags=["myapp:latest"],
                created="2024-01-15T10:30:00Z",
                size="500MB",
                containers=2,
                architecture="amd64",
                os="linux"
            )

            # Mock screen with focused search
            mock_screen = Mock()
            mock_search = Mock()
            mock_search.id = "search-input"
            mock_screen.focused = mock_search

            with patch.object(type(header), 'screen', new_callable=PropertyMock) as mock_screen_prop:
                mock_screen_prop.return_value = mock_screen

                header.on_click()

                # Should NOT focus when search is focused
                header.focus.assert_not_called()


class TestMessages:
    """Test cases for message classes."""

    def test_section_header_clicked_message(self):
        """Test SectionHeader.Clicked message."""
        header = Mock()
        message = SectionHeader.Clicked(header)
        assert message.section_header == header

    def test_network_header_selected_message(self):
        """Test NetworkHeader.Selected message."""
        header = Mock()
        message = NetworkHeader.Selected(header)
        assert message.network_header == header

    def test_network_header_clicked_message(self):
        """Test NetworkHeader.Clicked message."""
        header = Mock()
        message = NetworkHeader.Clicked(header)
        assert message.network_header == header

    def test_volume_header_selected_message(self):
        """Test VolumeHeader.Selected message."""
        header = Mock()
        message = VolumeHeader.Selected(header)
        assert message.volume_header == header

    def test_volume_header_clicked_message(self):
        """Test VolumeHeader.Clicked message."""
        header = Mock()
        message = VolumeHeader.Clicked(header)
        assert message.volume_header == header

    def test_stack_header_selected_message(self):
        """Test StackHeader.Selected message."""
        header = Mock()
        message = StackHeader.Selected(header)
        assert message.stack_header == header

    def test_stack_header_clicked_message(self):
        """Test StackHeader.Clicked message."""
        header = Mock()
        message = StackHeader.Clicked(header)
        assert message.stack_header == header

    def test_image_header_selected_message(self):
        """Test ImageHeader.Selected message."""
        header = Mock()
        message = ImageHeader.Selected(header)
        assert message.image_header == header

    def test_image_header_clicked_message(self):
        """Test ImageHeader.Clicked message."""
        header = Mock()
        message = ImageHeader.Clicked(header)
        assert message.image_header == header