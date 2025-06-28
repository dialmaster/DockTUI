"""Tests for the ImageManager class."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from rich.text import Text
from textual.containers import Container
from textual.widgets import DataTable, Static

from dockerview.ui.base.container_list_base import SelectionChanged
from dockerview.ui.managers.image_manager import ImageManager


class TestImageManager(unittest.TestCase):
    """Test cases for ImageManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.parent = Mock()
        self.parent.images_container = Mock(spec=Container)
        self.parent.images_container.parent = Mock()
        self.parent.selected_item = None
        self.parent.selected_container_data = None
        self.parent.selected_stack_data = None
        self.parent.selected_network_data = None
        self.parent.selected_volume_data = None
        self.parent.selected_image_data = None
        self.parent.post_message = Mock()
        self.parent.select_image = Mock()
        
        self.manager = ImageManager(self.parent)

    def test_init(self):
        """Test ImageManager initialization."""
        self.assertEqual(self.manager.parent, self.parent)
        self.assertIsNone(self.manager.images_table)
        self.assertIsNone(self.manager.images_container)
        self.assertIsNone(self.manager.loading_message)
        self.assertEqual(self.manager.image_rows, {})
        self.assertEqual(self.manager._images_in_new_data, set())
        self.assertIsNone(self.manager.selected_image_data)
        self.assertFalse(self.manager._table_initialized)
        self.assertEqual(self.manager._removed_images, set())
        self.assertIsNone(self.manager._preserve_selected_image_id)
        # Check compatibility attributes
        self.assertEqual(self.manager.image_headers, {})
        self.assertEqual(self.manager.expanded_images, set())

    def test_reset_tracking(self):
        """Test reset_tracking clears the images set."""
        self.manager._images_in_new_data.add("image1")
        self.manager._images_in_new_data.add("image2")
        self.manager.reset_tracking()
        self.assertEqual(self.manager._images_in_new_data, set())

    @patch('dockerview.ui.managers.image_manager.Static')
    def test_show_loading_message(self, mock_static):
        """Test showing loading message."""
        mock_static_instance = Mock()
        mock_static.return_value = mock_static_instance
        
        self.manager.show_loading_message()
        
        mock_static.assert_called_once()
        self.parent.images_container.mount.assert_called_once_with(mock_static_instance)
        self.assertEqual(self.manager.loading_message, mock_static_instance)

    def test_show_loading_message_already_shown(self):
        """Test showing loading message when already shown."""
        self.manager.loading_message = Mock()
        
        self.manager.show_loading_message()
        
        # Should not mount again
        self.parent.images_container.mount.assert_not_called()

    def test_hide_loading_message(self):
        """Test hiding loading message."""
        mock_message = Mock()
        mock_message.parent = Mock()
        self.manager.loading_message = mock_message
        
        self.manager.hide_loading_message()
        
        mock_message.remove.assert_called_once()
        self.assertIsNone(self.manager.loading_message)

    def test_hide_loading_message_no_parent(self):
        """Test hiding loading message when it has no parent."""
        mock_message = Mock()
        mock_message.parent = None
        self.manager.loading_message = mock_message
        
        self.manager.hide_loading_message()
        
        mock_message.remove.assert_not_called()
        # Loading message is NOT set to None when it has no parent
        self.assertEqual(self.manager.loading_message, mock_message)

    @patch('dockerview.ui.managers.image_manager.Static')
    def test_show_no_images_message(self, mock_static):
        """Test showing no images message."""
        mock_static_instance = Mock()
        mock_static.return_value = mock_static_instance
        
        self.manager.show_no_images_message()
        
        mock_static.assert_called_once()
        self.parent.images_container.mount.assert_called_once_with(mock_static_instance)
        self.assertEqual(self.manager.loading_message, mock_static_instance)

    def test_prepare_new_containers(self):
        """Test prepare_new_containers returns empty dict."""
        result = self.manager.prepare_new_containers()
        self.assertEqual(result, {})

    @patch('dockerview.ui.managers.image_manager.DataTable')
    def test_initialize_table(self, mock_datatable):
        """Test table initialization."""
        mock_table = Mock()
        mock_datatable.return_value = mock_table
        
        self.manager._initialize_table()
        
        # Check table was created and configured
        mock_datatable.assert_called_once_with(
            show_cursor=True,
            cursor_foreground_priority=True,
            zebra_stripes=True,
            fixed_rows=0,
        )
        self.assertTrue(mock_table.can_focus)
        self.assertFalse(mock_table.show_vertical_scrollbar)
        
        # Check columns were added
        mock_table.add_columns.assert_called_once_with(
            "Repository",
            "Tag",
            "Image ID",
            "Containers",
            "Created",
            "Size",
            "Status",
        )
        
        # Check table was mounted
        self.parent.images_container.mount.assert_called_once_with(mock_table)
        self.assertTrue(self.manager._table_initialized)
        self.assertEqual(self.manager.images_table, mock_table)

    @patch('dockerview.ui.managers.image_manager.DataTable')
    def test_add_image_new(self, mock_datatable):
        """Test adding a new image."""
        mock_table = Mock()
        mock_table.row_count = 0
        
        # Mock add_row to increment row_count
        def add_row_side_effect(*args, **kwargs):
            mock_table.row_count += 1
        
        mock_table.add_row.side_effect = add_row_side_effect
        mock_datatable.return_value = mock_table
        self.manager._table_initialized = True
        self.manager.images_table = mock_table
        
        image_data = {
            "id": "abc123def456",
            "tags": ["myrepo/myimage:v1.0"],
            "created": "2024-01-15T10:30:00Z",
            "size": "150MB",
            "container_names": ["container1", "container2"],
            "has_running": True,
        }
        
        self.manager.add_image(image_data)
        
        # Check that image was tracked
        self.assertIn("abc123def456", self.manager._images_in_new_data)
        
        # Check that row was added
        mock_table.add_row.assert_called_once()
        args = mock_table.add_row.call_args[0]
        self.assertEqual(args[0], "myrepo/myimage")  # repository
        self.assertEqual(args[1], "v1.0")  # tag
        self.assertEqual(args[2], "abc123def456")  # short id
        self.assertIn("container1", args[3])  # containers
        self.assertEqual(args[4], "2024-01-15")  # created date
        self.assertEqual(args[5], "150MB")  # size
        self.assertEqual(args[6], "Active")  # status
        
        # Check row index was stored
        self.assertEqual(self.manager.image_rows["abc123def456"], 0)

    def test_add_image_no_tags(self):
        """Test adding an image with no tags."""
        self.manager._table_initialized = True
        self.manager.images_table = Mock()
        self.manager.images_table.row_count = 0
        
        image_data = {
            "id": "abc123",
            "tags": [],
            "created": "N/A",
            "size": "50MB",
            "container_names": [],
            "has_running": False,
        }
        
        self.manager.add_image(image_data)
        
        args = self.manager.images_table.add_row.call_args[0]
        self.assertEqual(args[0], "<none>")  # repository
        self.assertEqual(args[1], "<none>")  # tag
        self.assertEqual(args[3], "None")  # containers
        self.assertEqual(args[6], "Unused")  # status

    def test_add_image_update_existing(self):
        """Test updating an existing image."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_table.row_count = 1
        self.manager.images_table = mock_table
        self.manager.image_rows["abc123"] = 0
        
        image_data = {
            "id": "abc123",
            "tags": ["updated:latest"],
            "created": "2024-01-16",
            "size": "200MB",
            "container_names": ["new_container"],
            "has_running": False,
        }
        
        self.manager.add_image(image_data)
        
        # Should update cells, not add row
        mock_table.add_row.assert_not_called()
        self.assertEqual(mock_table.update_cell_at.call_count, 7)  # 7 columns

    def test_add_image_truncate_long_names(self):
        """Test truncation of long repository and tag names."""
        self.manager._table_initialized = True
        self.manager.images_table = Mock()
        self.manager.images_table.row_count = 0
        
        image_data = {
            "id": "abc123",
            "tags": ["very-long-repository-name-that-should-be-truncated:very-long-tag-name"],
            "created": "2024-01-15",
            "size": "100MB",
            "container_names": ["container-with-a-very-long-name-that-should-be-truncated"],
            "has_running": True,
        }
        
        self.manager.add_image(image_data)
        
        args = self.manager.images_table.add_row.call_args[0]
        # Repository should be truncated at beginning
        self.assertTrue(args[0].startswith("..."))
        self.assertLessEqual(len(args[0]), 28)  # 25 + 3 for "..."
        # Tag should be truncated at end
        self.assertTrue(args[1].endswith("..."))
        self.assertLessEqual(len(args[1]), 13)  # 10 + 3 for "..."
        # Containers text should be truncated
        self.assertTrue(args[3].endswith("..."))
        self.assertLessEqual(len(args[3]), 30)

    def test_mark_image_as_removed(self):
        """Test marking an image as removed."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_table.columns = ["col1", "col2", "col3", "col4", "col5", "col6", "col7"]
        mock_table.get_cell_at.return_value = "cell_value"
        self.manager.images_table = mock_table
        self.manager.image_rows["abc123"] = 0
        
        self.manager.mark_image_as_removed("abc123")
        
        # Check image was added to removed set
        self.assertIn("abc123", self.manager._removed_images)
        
        # Check all cells were updated with strikethrough
        self.assertEqual(mock_table.update_cell_at.call_count, 7)
        for call in mock_table.update_cell_at.call_args_list:
            text_arg = call[0][1]
            self.assertIsInstance(text_arg, Text)
            self.assertEqual(text_arg.style, "strike dim")

    def test_mark_image_as_removed_not_found(self):
        """Test marking non-existent image as removed."""
        self.manager._table_initialized = True
        self.manager.images_table = Mock()
        
        # Should not raise error
        self.manager.mark_image_as_removed("nonexistent")
        
        self.manager.images_table.update_cell_at.assert_not_called()

    def test_remove_image(self):
        """Test removing an image from the table."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_row1 = Mock(key="abc123")
        mock_row2 = Mock(key="def456")
        
        # Initial state
        mock_table.rows = [mock_row1, mock_row2]
        
        # Mock remove_row to simulate removing the row
        def remove_row_side_effect(key):
            # Simulate removing the row by updating mock_table.rows
            mock_table.rows = [mock_row2]  # Only def456 remains
        
        mock_table.remove_row.side_effect = remove_row_side_effect
        
        self.manager.images_table = mock_table
        self.manager.image_rows = {"abc123": 0, "def456": 1}
        self.manager._removed_images.add("abc123")
        
        self.manager.remove_image("abc123")
        
        # Check row was removed
        mock_table.remove_row.assert_called_once_with("abc123")
        
        # Check image was removed from tracking
        self.assertNotIn("abc123", self.manager.image_rows)
        self.assertNotIn("abc123", self.manager._removed_images)
        
        # Check that remaining image has correct index
        self.assertEqual(self.manager.image_rows["def456"], 0)

    def test_remove_image_exception(self):
        """Test removing image handles exceptions."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_table.remove_row.side_effect = Exception("Test error")
        self.manager.images_table = mock_table
        self.manager.image_rows = {"abc123": 0}
        
        # Should not raise error
        self.manager.remove_image("abc123")

    def test_cleanup_removed_images(self):
        """Test cleanup of removed images."""
        self.manager._table_initialized = True
        self.manager.images_table = Mock()
        self.manager.image_rows = {
            "keep1": 0,
            "keep2": 1,
            "remove1": 2,
            "remove2": 3,
        }
        self.manager._images_in_new_data = {"keep1", "keep2"}
        
        with patch.object(self.manager, 'remove_image') as mock_remove:
            with patch.object(self.manager, 'sort_images_table') as mock_sort:
                self.manager.cleanup_removed_images()
        
        # Check correct images were removed
        mock_remove.assert_any_call("remove1")
        mock_remove.assert_any_call("remove2")
        self.assertEqual(mock_remove.call_count, 2)
        
        # Check table was sorted
        mock_sort.assert_called_once()
        
        # Check removed images tracking was cleared
        self.assertEqual(self.manager._removed_images, set())

    def test_select_image(self):
        """Test selecting an image."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_table.get_cell_at.side_effect = [
            "myrepo/myimage",  # repository
            "latest",  # tag
            "container1",  # containers
            "2024-01-15",  # created
            "100MB",  # size
            "Active",  # status
        ]
        self.manager.images_table = mock_table
        self.manager.image_rows["abc123"] = 0
        
        self.manager.select_image("abc123")
        
        # Check selection was set
        self.assertEqual(self.parent.selected_item, ("image", "abc123"))
        self.assertIsNone(self.parent.selected_container_data)
        self.assertIsNone(self.parent.selected_stack_data)
        self.assertIsNone(self.parent.selected_network_data)
        self.assertIsNone(self.parent.selected_volume_data)
        
        # Check image data was stored
        self.assertIsNotNone(self.manager.selected_image_data)
        self.assertEqual(self.manager.selected_image_data["id"], "abc123")
        self.assertEqual(self.manager.selected_image_data["repository"], "myrepo/myimage")
        self.assertEqual(self.manager.selected_image_data["tags"], ["myrepo/myimage:latest"])
        
        # Check table cursor was moved
        mock_table.move_cursor.assert_called_once_with(row=0)
        
        # Check selection changed event was posted
        self.parent.post_message.assert_called_once()
        event = self.parent.post_message.call_args[0][0]
        self.assertIsInstance(event, SelectionChanged)
        self.assertEqual(event.item_type, "image")
        self.assertEqual(event.item_id, "abc123")

    def test_select_image_not_found(self):
        """Test selecting non-existent image."""
        self.manager.select_image("nonexistent")
        
        # Should not set selection or post message
        self.assertIsNone(self.parent.selected_item)
        self.parent.post_message.assert_not_called()

    def test_handle_selection(self):
        """Test handling row selection."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_table.get_row_index.return_value = 0
        self.manager.images_table = mock_table
        self.manager.image_rows = {"abc123": 0}
        
        result = self.manager.handle_selection("row_key")
        
        self.assertTrue(result)
        self.parent.select_image.assert_called_once_with("abc123")

    def test_handle_selection_no_row_key(self):
        """Test handling selection with no row key."""
        result = self.manager.handle_selection(None)
        self.assertFalse(result)

    def test_handle_selection_row_not_found(self):
        """Test handling selection when row not found."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_table.get_row_index.return_value = None
        self.manager.images_table = mock_table
        
        result = self.manager.handle_selection("row_key")
        
        self.assertFalse(result)

    def test_toggle_images_section(self):
        """Test toggling images section visibility."""
        mock_table = Mock()
        mock_table.display = True
        self.manager.images_table = mock_table
        
        self.manager.toggle_images_section()
        
        self.assertFalse(mock_table.display)
        
        self.manager.toggle_images_section()
        
        self.assertTrue(mock_table.display)

    def test_get_existing_containers(self):
        """Test get_existing_containers returns empty dict."""
        result = self.manager.get_existing_containers()
        self.assertEqual(result, {})

    def test_get_next_selection_after_removal_current_not_removed(self):
        """Test getting next selection when current is not being removed."""
        self.manager.images_table = Mock()
        self.parent.selected_item = ("image", "keep")
        
        result = self.manager.get_next_selection_after_removal({"remove1", "remove2"})
        
        self.assertEqual(result, "keep")

    def test_get_next_selection_after_removal_select_previous(self):
        """Test selecting previous image after removal."""
        mock_table = Mock()
        mock_table.row_count = 4
        self.manager.images_table = mock_table
        self.manager.image_rows = {
            "img0": 0,
            "img1": 1,
            "img2": 2,  # Will be removed
            "img3": 3,
        }
        self.parent.selected_item = ("image", "img2")
        
        result = self.manager.get_next_selection_after_removal({"img2"})
        
        self.assertEqual(result, "img1")

    def test_get_next_selection_after_removal_select_next(self):
        """Test selecting next image when no previous available."""
        mock_table = Mock()
        mock_table.row_count = 3
        self.manager.images_table = mock_table
        self.manager.image_rows = {
            "img0": 0,  # Will be removed
            "img1": 1,
            "img2": 2,
        }
        self.parent.selected_item = ("image", "img0")
        
        result = self.manager.get_next_selection_after_removal({"img0"})
        
        self.assertEqual(result, "img1")

    def test_get_next_selection_after_removal_none_remain(self):
        """Test when no images remain after removal."""
        mock_table = Mock()
        mock_table.row_count = 2
        self.manager.images_table = mock_table
        self.manager.image_rows = {
            "img0": 0,
            "img1": 1,
        }
        
        result = self.manager.get_next_selection_after_removal({"img0", "img1"})
        
        self.assertIsNone(result)

    def test_sort_images_table(self):
        """Test sorting images table."""
        mock_table = Mock()
        mock_table.row_count = 3
        mock_table.columns = ["col1", "col2", "col3", "col4", "col5", "col6", "col7"]
        
        # Set up cells for 3 rows
        cells = [
            ["repo1", "tag1", "id1", "container1", "2024-01-15", "100MB", "Unused"],
            ["repo2", "tag2", "id2", "container2", "2024-01-16", "200MB", "Active"],
            ["repo3", "tag3", "id3", "container3", "2024-01-14", "300MB", "Stopped"],
        ]
        
        def get_cell_at(pos):
            row, col = pos
            return cells[row][col]
        
        mock_table.get_cell_at.side_effect = get_cell_at
        mock_table.rows = [
            Mock(key="id1"),
            Mock(key="id2"),
            Mock(key="id3"),
        ]
        
        self.manager.images_table = mock_table
        self.manager.image_rows = {"id1": 0, "id2": 1, "id3": 2}
        
        self.manager.sort_images_table()
        
        # Table should be cleared and rebuilt
        mock_table.clear.assert_called_once_with(columns=False)
        
        # Rows should be added in sorted order:
        # 1. Active (newest first)
        # 2. Stopped
        # 3. Unused
        self.assertEqual(mock_table.add_row.call_count, 3)
        
        # Check the order of rows added
        first_row = mock_table.add_row.call_args_list[0][0]
        self.assertEqual(first_row[6], "Active")  # Status
        
        second_row = mock_table.add_row.call_args_list[1][0]
        self.assertEqual(second_row[6], "Stopped")  # Status
        
        third_row = mock_table.add_row.call_args_list[2][0]
        self.assertEqual(third_row[6], "Unused")  # Status

    def test_sort_images_table_empty(self):
        """Test sorting empty images table."""
        mock_table = Mock()
        mock_table.row_count = 0
        self.manager.images_table = mock_table
        
        # Should not raise error
        self.manager.sort_images_table()
        
        mock_table.clear.assert_not_called()

    def test_sort_images_table_date_parsing(self):
        """Test date parsing in sort function."""
        mock_table = Mock()
        mock_table.row_count = 4
        mock_table.columns = ["col1", "col2", "col3", "col4", "col5", "col6", "col7"]
        
        # Test various date formats
        cells = [
            ["repo1", "tag1", "id1", "c1", "2024-01-15T10:30:00Z", "100MB", "Active"],
            ["repo2", "tag2", "id2", "c2", "2024-01-16", "200MB", "Active"],
            ["repo3", "tag3", "id3", "c3", "N/A", "300MB", "Active"],
            ["repo4", "tag4", "id4", "c4", "invalid-date", "400MB", "Active"],
        ]
        
        def get_cell_at(pos):
            row, col = pos
            return cells[row][col]
        
        mock_table.get_cell_at.side_effect = get_cell_at
        mock_table.rows = [
            Mock(key=f"id{i+1}") for i in range(4)
        ]
        
        self.manager.images_table = mock_table
        self.manager.image_rows = {f"id{i+1}": i for i in range(4)}
        
        self.manager.sort_images_table()
        
        # Should handle all date formats without error
        mock_table.clear.assert_called_once()
        self.assertEqual(mock_table.add_row.call_count, 4)

    def test_add_image_with_strikethrough(self):
        """Test adding an image that's marked as removed."""
        self.manager._table_initialized = True
        self.manager.images_table = Mock()
        self.manager.images_table.row_count = 0
        self.manager._removed_images.add("abc123")
        
        image_data = {
            "id": "abc123",
            "tags": ["test:latest"],
            "created": "2024-01-15",
            "size": "100MB",
            "container_names": [],
            "has_running": False,
        }
        
        self.manager.add_image(image_data)
        
        # Check that row was added with strikethrough style
        args = self.manager.images_table.add_row.call_args[0]
        for arg in args[:7]:  # All 7 columns
            self.assertIsInstance(arg, Text)
            self.assertEqual(arg.style, "strike dim")

    def test_add_image_updates_selected_image_data(self):
        """Test that adding selected image updates selected_image_data."""
        self.manager._table_initialized = True
        self.manager.images_table = Mock()
        self.manager.image_rows["abc123"] = 0
        self.parent.selected_item = ("image", "abc123")
        
        image_data = {
            "id": "abc123",
            "tags": ["updated:v2"],
            "created": "2024-01-16",
            "size": "150MB",
            "container_names": ["new_container"],
            "has_running": True,
        }
        
        self.manager.add_image(image_data)
        
        # Check that selected_image_data was updated
        self.assertEqual(self.manager.selected_image_data, image_data)

    def test_handle_selection_exception(self):
        """Test handle_selection with exception."""
        self.manager._table_initialized = True
        mock_table = Mock()
        mock_table.get_row_index.side_effect = Exception("Test error")
        self.manager.images_table = mock_table
        
        result = self.manager.handle_selection("row_key")
        
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()