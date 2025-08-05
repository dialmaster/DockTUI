"""Tests for the StackManager class."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from textual.containers import Container
from textual.widgets import DataTable

from DockTUI.ui.base.container_list_base import SelectionChanged
from DockTUI.ui.managers.stack_manager import StackManager
from DockTUI.ui.widgets.headers import StackHeader


class TestStackManager(unittest.TestCase):
    """Test cases for StackManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.parent = Mock()
        self.parent.selected_item = None
        self.parent.selected_container_data = None
        self.parent.selected_stack_data = None
        self.parent.selected_network_data = None
        self.parent.selected_volume_data = None
        self.parent.post_message = Mock()
        self.parent._update_footer_with_selection = Mock()
        self.parent._update_cursor_visibility = Mock()
        self.parent.create_stack_table = Mock()
        self.parent.stacks_container = Mock()
        self.parent.stacks_container.children = []
        self.parent._is_updating = False
        self.parent._status_overrides = {}
        # Stack status overrides no longer exist
        self.parent.screen = None

        self.manager = StackManager(self.parent)

    def test_init(self):
        """Test StackManager initialization."""
        self.assertEqual(self.manager.parent, self.parent)
        self.assertEqual(self.manager.stack_tables, {})
        self.assertEqual(self.manager.stack_headers, {})
        self.assertEqual(self.manager.container_rows, {})
        self.assertEqual(self.manager.expanded_stacks, set())
        self.assertEqual(self.manager._stacks_in_new_data, set())
        self.assertIsNone(self.manager.selected_stack_data)
        self.assertIsNone(self.manager.selected_container_data)

    @patch('DockTUI.ui.managers.stack_manager.StackHeader')
    def test_add_stack_new(self, mock_header_class):
        """Test adding a new stack."""
        mock_header = Mock()
        mock_header_class.return_value = mock_header
        mock_table = Mock()
        self.parent.create_stack_table.return_value = mock_table

        self.manager.add_stack(
            "test-stack",
            "/path/to/compose.yml",
            running=2,
            exited=1,
            total=3,
            can_recreate=True,
            has_compose_file=True
        )

        # Check stack was tracked
        self.assertIn("test-stack", self.manager._stacks_in_new_data)

        # Check header was created
        mock_header_class.assert_called_once_with(
            "test-stack",
            "/path/to/compose.yml",
            2, 1, 3,
            True, True
        )

        # Check table was created
        self.parent.create_stack_table.assert_called_once_with("test-stack")

        # Check they were stored
        self.assertEqual(self.manager.stack_headers["test-stack"], mock_header)
        self.assertEqual(self.manager.stack_tables["test-stack"], mock_table)

    @patch('DockTUI.ui.managers.stack_manager.StackHeader')
    def test_add_stack_expanded(self, mock_header_class):
        """Test adding a stack that should be expanded."""
        mock_header = Mock()
        mock_header_class.return_value = mock_header
        mock_table = Mock()
        self.parent.create_stack_table.return_value = mock_table

        # Mark stack as expanded
        self.manager.expanded_stacks.add("test-stack")

        self.manager.add_stack("test-stack", "/path/to/compose.yml", 1, 0, 1)

        # Check expanded state was set
        self.assertEqual(mock_header.expanded, True)
        self.assertEqual(mock_table.styles.display, "block")

    def test_add_stack_update_existing(self):
        """Test updating an existing stack."""
        # Set up existing stack
        mock_header = Mock()
        mock_header.expanded = True
        mock_table = Mock()
        self.manager.stack_headers["test-stack"] = mock_header
        self.manager.stack_tables["test-stack"] = mock_table

        self.manager.add_stack(
            "test-stack",
            "/new/path/compose.yml",
            running=3,
            exited=2,
            total=5,
            can_recreate=False,
            has_compose_file=True
        )

        # Check header was updated
        self.assertEqual(mock_header.running, 3)
        self.assertEqual(mock_header.exited, 2)
        self.assertEqual(mock_header.total, 5)
        self.assertEqual(mock_header.config_file, "/new/path/compose.yml")
        self.assertEqual(mock_header.can_recreate, False)
        self.assertEqual(mock_header.has_compose_file, True)
        mock_header._update_content.assert_called_once()

    def test_add_stack_updates_selected_stack_data(self):
        """Test that adding selected stack updates selected_stack_data."""
        mock_header = Mock()
        mock_table = Mock()
        self.manager.stack_headers["test-stack"] = mock_header
        self.manager.stack_tables["test-stack"] = mock_table
        self.parent.selected_item = ("stack", "test-stack")

        self.manager.add_stack("test-stack", "/path/compose.yml", 2, 1, 3)

        # Check selected_stack_data was updated
        self.assertIsNotNone(self.manager.selected_stack_data)
        self.assertEqual(self.manager.selected_stack_data["name"], "test-stack")
        self.assertEqual(self.manager.selected_stack_data["running"], 2)

    def test_add_container_to_stack_new_container(self):
        """Test adding a new container to a stack."""
        mock_table = Mock()
        mock_table.row_count = 0
        self.manager.stack_tables["test-stack"] = mock_table
        self.parent._is_updating = True

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "running",
            "uptime": "2 hours",
            "cpu": "5%",
            "memory": "100MB",
            "pids": "10",
            "ports": "80:80"
        }

        self.manager.add_container_to_stack("test-stack", container_data)

        # Check row was added
        mock_table.add_row.assert_called_once()
        args = mock_table.add_row.call_args[0]
        self.assertEqual(args[0], "abc123")
        self.assertEqual(args[1], "test-container")
        self.assertEqual(args[2], "running")
        self.assertEqual(args[6], "10")  # PIDs

        # Check container was tracked
        self.assertEqual(self.manager.container_rows["abc123"], ("test-stack", 0))

    def test_add_container_to_stack_pids_zero(self):
        """Test adding container with 0 PIDs shows N/A."""
        mock_table = Mock()
        mock_table.row_count = 0
        self.manager.stack_tables["test-stack"] = mock_table
        self.parent._is_updating = True

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "exited",
            "uptime": "N/A",
            "cpu": "0%",
            "memory": "0MB",
            "pids": "0",
            "ports": ""
        }

        self.manager.add_container_to_stack("test-stack", container_data)

        # Check PIDs shows as N/A and status
        args = mock_table.add_row.call_args[0]
        
        # With the new approach, ContainerText objects are used for all containers
        # Since we're using ContainerText, we need to convert to string for comparison
        self.assertEqual(str(args[6]), "N/A")  # PIDs column
        self.assertEqual(str(args[2]), "exited")  # Status column

    def test_add_container_to_stack_status_override(self):
        """Test adding container with status override."""
        mock_table = Mock()
        mock_table.row_count = 0
        self.manager.stack_tables["test-stack"] = mock_table
        self.parent._is_updating = True
        self.parent._status_overrides = {"abc123": "starting..."}

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "created",
            "uptime": "N/A",
            "cpu": "0%",
            "memory": "0MB",
            "pids": "0",
            "ports": ""
        }

        self.manager.add_container_to_stack("test-stack", container_data)

        # Check status override was applied
        args = mock_table.add_row.call_args[0]
        self.assertEqual(args[2], "starting...")

    def test_add_container_to_stack_creates_stack_if_missing(self):
        """Test adding container creates stack if it doesn't exist."""
        # Mock the add_stack method to just set up the table
        def mock_add_stack_side_effect(name, *args, **kwargs):
            # Set up a mock table for the new stack
            mock_table = Mock()
            mock_table.row_count = 0
            self.manager.stack_tables[name] = mock_table

        with patch.object(self.manager, 'add_stack', side_effect=mock_add_stack_side_effect) as mock_add_stack:
            self.parent._is_updating = True
            container_data = {
                "id": "abc123",
                "name": "test-container",
                "status": "running",
                "uptime": "1 hour",
                "cpu": "2%",
                "memory": "50MB",
                "pids": "5",
                "ports": ""
            }

            self.manager.add_container_to_stack("new-stack", container_data)

            # Check stack was created
            mock_add_stack.assert_called_once_with("new-stack", "N/A", 0, 0, 0)

    def test_add_container_to_stack_update_existing(self):
        """Test updating an existing container."""
        mock_table = Mock()
        mock_table.row_count = 2
        mock_table.rows = {"abc123": 1}  # Mock the rows attribute
        mock_table.get_row = Mock(return_value=["abc123", "old-name", "stopped", "1 hour", "5%", "50MB", "5", ""])
        self.manager.stack_tables["test-stack"] = mock_table
        self.manager.container_rows["abc123"] = ("test-stack", 1)
        self.parent._is_updating = False

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "running",
            "uptime": "3 hours",
            "cpu": "10%",
            "memory": "150MB",
            "pids": "15",
            "ports": "80:80"
        }

        self.manager.add_container_to_stack("test-stack", container_data)

        # Check table was cleared and rebuilt
        mock_table.clear.assert_called_once()
        # Check row was added with new data
        mock_table.add_row.assert_called()

    def test_add_container_to_stack_move_between_stacks(self):
        """Test moving container between stacks."""
        old_table = Mock()
        new_table = Mock()
        new_table.row_count = 1
        self.manager.stack_tables = {
            "old-stack": old_table,
            "new-stack": new_table
        }
        self.manager.container_rows = {
            "abc123": ("old-stack", 1),
            "def456": ("old-stack", 2)
        }
        self.parent._is_updating = False

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "running",
            "uptime": "1 hour",
            "cpu": "5%",
            "memory": "100MB",
            "pids": "10",
            "ports": ""
        }

        self.manager.add_container_to_stack("new-stack", container_data)

        # Check container was removed from old stack
        old_table.remove_row.assert_called_once_with(1)

        # Check container was added to new stack
        new_table.add_row.assert_called_once()

        # Check container rows were updated
        self.assertEqual(self.manager.container_rows["abc123"], ("new-stack", 1))
        self.assertEqual(self.manager.container_rows["def456"], ("old-stack", 1))  # Updated index

    def test_add_container_updates_selected_container_data(self):
        """Test that adding selected container updates selected_container_data."""
        mock_table = Mock()
        self.manager.stack_tables["test-stack"] = mock_table
        self.manager.container_rows["abc123"] = ("test-stack", 0)
        self.parent.selected_item = ("container", "abc123")
        self.parent._is_updating = False

        container_data = {
            "id": "abc123",
            "name": "updated-name",
            "status": "running",
            "uptime": "5 hours",
            "cpu": "20%",
            "memory": "200MB",
            "pids": "25",
            "ports": "443:443"
        }

        self.manager.add_container_to_stack("test-stack", container_data)

        # Check selected_container_data was updated
        self.assertEqual(self.manager.selected_container_data, container_data)

    def test_remove_stack(self):
        """Test removing a stack."""
        # Set up stack with containers
        mock_header = Mock(spec=StackHeader)
        mock_header.stack_name = "test-stack"
        mock_table = Mock()
        mock_container = Mock(spec=Container)
        mock_container.classes = ["stack-container"]
        mock_container.children = [mock_header]

        self.manager.stack_headers["test-stack"] = mock_header
        self.manager.stack_tables["test-stack"] = mock_table
        self.manager.container_rows = {
            "abc123": ("test-stack", 0),
            "def456": ("test-stack", 1),
            "ghi789": ("other-stack", 0)
        }
        self.manager.expanded_stacks.add("test-stack")
        self.parent.stacks_container.children = [mock_container]

        self.manager.remove_stack("test-stack")

        # Check stack was removed from tracking
        self.assertNotIn("test-stack", self.manager.stack_headers)
        self.assertNotIn("test-stack", self.manager.stack_tables)
        self.assertNotIn("test-stack", self.manager.expanded_stacks)

        # Check containers were removed
        self.assertNotIn("abc123", self.manager.container_rows)
        self.assertNotIn("def456", self.manager.container_rows)
        self.assertIn("ghi789", self.manager.container_rows)

        # Check UI was removed
        mock_container.remove.assert_called_once()

    def test_remove_stack_clears_selection(self):
        """Test removing selected stack clears selection."""
        self.manager.stack_headers["test-stack"] = Mock()
        self.manager.stack_tables["test-stack"] = Mock()
        self.parent.selected_item = ("stack", "test-stack")
        self.manager.selected_stack_data = {"name": "test-stack"}

        self.manager.remove_stack("test-stack")

        self.assertIsNone(self.parent.selected_item)
        self.assertIsNone(self.manager.selected_stack_data)

    def test_remove_stack_clears_container_selection(self):
        """Test removing stack clears selected container."""
        self.manager.stack_headers["test-stack"] = Mock()
        self.manager.stack_tables["test-stack"] = Mock()
        self.manager.container_rows["abc123"] = ("test-stack", 0)
        self.parent.selected_item = ("container", "abc123")
        self.manager.selected_container_data = {"id": "abc123"}

        self.manager.remove_stack("test-stack")

        self.assertIsNone(self.parent.selected_item)
        self.assertIsNone(self.manager.selected_container_data)

    def test_select_stack(self):
        """Test selecting a stack."""
        mock_header = Mock()
        mock_header.config_file = "/path/compose.yml"
        mock_header.running = 2
        mock_header.exited = 1
        mock_header.total = 3
        mock_header.can_recreate = True
        mock_header.has_compose_file = True
        self.manager.stack_headers["test-stack"] = mock_header

        self.manager.select_stack("test-stack")

        # Check selection was set
        self.assertEqual(self.parent.selected_item, ("stack", "test-stack"))
        self.assertIsNone(self.parent.selected_container_data)
        self.assertIsNone(self.parent.selected_volume_data)
        self.assertIsNone(self.parent.selected_network_data)

        # Check stack data was stored
        self.assertIsNotNone(self.manager.selected_stack_data)
        self.assertEqual(self.manager.selected_stack_data["name"], "test-stack")
        self.assertEqual(self.manager.selected_stack_data["running"], 2)
        self.assertEqual(self.parent.selected_stack_data, self.manager.selected_stack_data)

        # Check UI updates were called
        self.parent._update_footer_with_selection.assert_called_once()
        self.parent._update_cursor_visibility.assert_called_once()

        # Check selection message was posted
        self.parent.post_message.assert_called_once()
        event = self.parent.post_message.call_args[0][0]
        self.assertIsInstance(event, SelectionChanged)
        self.assertEqual(event.item_type, "stack")
        self.assertEqual(event.item_id, "test-stack")

    def test_select_stack_not_found(self):
        """Test selecting non-existent stack."""
        self.manager.select_stack("nonexistent")

        # Should not set selection or post message
        self.assertIsNone(self.parent.selected_item)
        self.parent.post_message.assert_not_called()

    def test_select_container(self):
        """Test selecting a container."""
        mock_table = Mock()
        mock_table.get_cell_at.side_effect = [
            "abc123",  # id
            "test-container",  # name
            "running",  # status
            "2 hours",  # uptime
            "5%",  # cpu
            "100MB",  # memory
            "10",  # pids
            "80:80"  # ports
        ]
        mock_table.cursor_row = 0
        mock_table.row_count = 2  # Set row_count to avoid Mock comparison
        
        # Make move_cursor update cursor_row to simulate real behavior
        def move_cursor_side_effect(row):
            mock_table.cursor_row = row
        mock_table.move_cursor.side_effect = move_cursor_side_effect

        mock_header = Mock()
        mock_header.expanded = True

        self.manager.stack_tables["test-stack"] = mock_table
        self.manager.stack_headers["test-stack"] = mock_header
        self.manager.container_rows["abc123"] = ("test-stack", 1)

        self.manager.select_container("abc123")

        # Check selection was set
        self.assertEqual(self.parent.selected_item, ("container", "abc123"))
        self.assertIsNone(self.parent.selected_stack_data)
        self.assertIsNone(self.parent.selected_volume_data)
        self.assertIsNone(self.parent.selected_network_data)

        # Check container data was stored
        self.assertIsNotNone(self.manager.selected_container_data)
        self.assertEqual(self.manager.selected_container_data["id"], "abc123")
        self.assertEqual(self.manager.selected_container_data["stack"], "test-stack")

        # Check table was focused and cursor moved
        mock_table.focus.assert_called_once()
        mock_table.move_cursor.assert_called_once_with(row=1)
        mock_table.refresh.assert_called_once()

        # Check UI updates
        self.parent._update_footer_with_selection.assert_called_once()

        # Check selection message was posted
        self.parent.post_message.assert_called_once()

    def test_select_container_expands_stack(self):
        """Test selecting container in collapsed stack expands it."""
        mock_table = Mock()
        mock_table.get_cell_at.return_value = "value"
        mock_table.row_count = 1  # Set row_count to avoid Mock comparison
        mock_header = Mock()
        mock_header.expanded = False

        self.manager.stack_tables["test-stack"] = mock_table
        self.manager.stack_headers["test-stack"] = mock_header
        self.manager.container_rows["abc123"] = ("test-stack", 0)

        self.manager.select_container("abc123")

        # Check stack was expanded
        self.assertEqual(mock_header.expanded, True)
        self.assertEqual(mock_table.styles.display, "block")
        mock_header._update_content.assert_called_once()

    def test_select_container_search_focused(self):
        """Test selecting container when search is focused."""
        mock_table = Mock()
        mock_table.get_cell_at.return_value = "value"
        mock_table.cursor_row = 0
        mock_table.row_count = 2  # Set row_count to avoid Mock comparison
        
        # Make move_cursor update cursor_row to simulate real behavior
        def move_cursor_side_effect(row):
            mock_table.cursor_row = row
        mock_table.move_cursor.side_effect = move_cursor_side_effect
        
        mock_header = Mock()
        mock_header.expanded = True

        # Set up focused search widget
        mock_focused = Mock()
        mock_focused.id = "search-input"
        mock_screen = Mock()
        mock_screen.focused = mock_focused
        self.parent.screen = mock_screen

        self.manager.stack_tables["test-stack"] = mock_table
        self.manager.stack_headers["test-stack"] = mock_header
        self.manager.container_rows["abc123"] = ("test-stack", 1)

        self.manager.select_container("abc123")

        # Table should not be focused, only cursor moved
        mock_table.focus.assert_not_called()
        mock_table.move_cursor.assert_called_once_with(row=1)

    def test_select_container_not_found(self):
        """Test selecting non-existent container."""
        self.manager.select_container("nonexistent")

        # Should not set selection or post message
        self.assertIsNone(self.parent.selected_item)
        self.parent.post_message.assert_not_called()

    def test_clear_tables(self):
        """Test clearing all tables."""
        mock_table1 = Mock()
        mock_table2 = Mock()
        self.manager.stack_tables = {
            "stack1": mock_table1,
            "stack2": mock_table2
        }
        self.manager.container_rows = {
            "abc123": ("stack1", 0),
            "def456": ("stack2", 0)
        }

        self.manager.clear_tables()

        # Check tables were cleared
        mock_table1.clear.assert_called_once()
        mock_table2.clear.assert_called_once()

        # Check container rows were cleared
        self.assertEqual(self.manager.container_rows, {})

    def test_reset_tracking(self):
        """Test resetting tracking."""
        self.manager._stacks_in_new_data = {"stack1", "stack2"}

        self.manager.reset_tracking()

        self.assertEqual(self.manager._stacks_in_new_data, set())

    def test_save_expanded_state(self):
        """Test saving expanded state."""
        mock_header1 = Mock()
        mock_header1.expanded = True
        mock_header2 = Mock()
        mock_header2.expanded = False
        mock_header3 = Mock()
        mock_header3.expanded = True

        self.manager.stack_headers = {
            "stack1": mock_header1,
            "stack2": mock_header2,
            "stack3": mock_header3
        }

        self.manager.save_expanded_state()

        self.assertEqual(self.manager.expanded_stacks, {"stack1", "stack3"})

    def test_cleanup_removed_stacks(self):
        """Test cleanup of removed stacks."""
        self.manager.stack_headers = {
            "keep1": Mock(),
            "keep2": Mock(),
            "remove1": Mock(),
            "remove2": Mock()
        }
        self.manager._stacks_in_new_data = {"keep1", "keep2"}

        with patch.object(self.manager, 'remove_stack') as mock_remove:
            self.manager.cleanup_removed_stacks()

        # Check correct stacks were removed
        mock_remove.assert_any_call("remove1")
        mock_remove.assert_any_call("remove2")
        self.assertEqual(mock_remove.call_count, 2)

    def test_get_existing_containers(self):
        """Test getting existing stack containers."""
        mock_header1 = Mock(spec=StackHeader)
        mock_header1.stack_name = "stack1"
        mock_header2 = Mock(spec=StackHeader)
        mock_header2.stack_name = "stack2"

        mock_container1 = Mock(spec=Container)
        mock_container1.classes = ["stack-container"]
        mock_container1.children = [mock_header1]

        mock_container2 = Mock(spec=Container)
        mock_container2.classes = ["stack-container"]
        mock_container2.children = [mock_header2]

        mock_other = Mock(spec=Container)
        mock_other.classes = ["other-class"]

        self.parent.stacks_container.children = [mock_container1, mock_other, mock_container2]

        result = self.manager.get_existing_containers()

        self.assertEqual(result, {
            "stack1": mock_container1,
            "stack2": mock_container2
        })

    def test_get_existing_containers_no_stacks_container(self):
        """Test getting existing containers when stacks_container is None."""
        self.parent.stacks_container = None

        result = self.manager.get_existing_containers()

        self.assertEqual(result, {})

    @patch('DockTUI.ui.managers.stack_manager.Container')
    def test_prepare_new_containers(self, mock_container_class):
        """Test preparing new containers."""
        mock_header1 = Mock()
        mock_table1 = Mock()
        mock_header2 = Mock()
        mock_table2 = Mock()

        # Mock Container class to avoid event loop issues
        mock_container_instance = Mock()
        mock_container_class.return_value = mock_container_instance

        self.manager.stack_headers = {
            "new-stack1": mock_header1,
            "existing-stack": Mock(),
            "new-stack2": mock_header2
        }
        self.manager.stack_tables = {
            "new-stack1": mock_table1,
            "existing-stack": Mock(),
            "new-stack2": mock_table2
        }

        with patch.object(self.manager, 'get_existing_containers') as mock_get:
            mock_get.return_value = {"existing-stack": Mock()}

            result = self.manager.prepare_new_containers()

        # Check only new stacks are in result
        self.assertEqual(len(result), 2)
        self.assertIn("new-stack1", result)
        self.assertIn("new-stack2", result)

        # Check container was created with proper classes
        mock_container_class.assert_called_with(classes="stack-container")

        # Check container structure
        container1, header1, table1 = result["new-stack1"]
        self.assertEqual(container1, mock_container_instance)
        self.assertEqual(header1, mock_header1)
        self.assertEqual(table1, mock_table1)

    def test_add_container_exception_handling(self):
        """Test exception handling when adding container."""
        mock_table = Mock()
        mock_table.add_row.side_effect = Exception("Test error")
        self.manager.stack_tables["test-stack"] = mock_table
        self.parent._is_updating = True

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "running",
            "uptime": "1 hour",
            "cpu": "5%",
            "memory": "100MB",
            "pids": "10",
            "ports": ""
        }

        # Should not raise exception
        self.manager.add_container_to_stack("test-stack", container_data)

    def test_add_container_move_exception_handling(self):
        """Test exception handling when moving container between stacks."""
        old_table = Mock()
        old_table.remove_row.side_effect = Exception("Remove error")
        new_table = Mock()

        self.manager.stack_tables = {
            "old-stack": old_table,
            "new-stack": new_table
        }
        self.manager.container_rows = {"abc123": ("old-stack", 0)}
        self.parent._is_updating = False

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "running",
            "uptime": "1 hour",
            "cpu": "5%",
            "memory": "100MB",
            "pids": "10",
            "ports": ""
        }

        # Should not raise exception
        self.manager.add_container_to_stack("new-stack", container_data)

    def test_add_container_update_exception_handling(self):
        """Test exception handling when updating container."""
        mock_table = Mock()
        mock_table.update_cell.side_effect = Exception("Update error")
        self.manager.stack_tables["test-stack"] = mock_table
        self.manager.container_rows["abc123"] = ("test-stack", 0)
        self.parent._is_updating = False

        container_data = {
            "id": "abc123",
            "name": "test-container",
            "status": "running",
            "uptime": "1 hour",
            "cpu": "5%",
            "memory": "100MB",
            "pids": "10",
            "ports": ""
        }

        # Should not raise exception
        self.manager.add_container_to_stack("test-stack", container_data)


if __name__ == "__main__":
    unittest.main()