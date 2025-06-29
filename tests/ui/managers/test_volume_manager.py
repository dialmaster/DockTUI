"""Tests for the VolumeManager class."""

import logging
from unittest.mock import MagicMock, Mock, patch

import pytest
from textual.widgets.data_table import RowKey

from DockTUI.ui.managers.volume_manager import VolumeManager


class TestVolumeManager:
    """Test cases for the VolumeManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parent = Mock()
        self.parent.selected_item = None
        self.parent.selected_volume_data = None
        self.parent.volumes_container = Mock()
        self.parent.volumes_container.parent = Mock()
        self.parent.post_message = Mock()
        self.parent._update_footer_with_selection = Mock()
        self.parent._update_cursor_visibility = Mock()

        self.manager = VolumeManager(self.parent)

    def test_init(self):
        """Test VolumeManager initialization."""
        assert self.manager.parent == self.parent
        assert self.manager.volume_table is None
        assert self.manager.volume_rows == {}
        assert self.manager._volumes_in_new_data == set()
        assert self.manager.selected_volume_data is None

    def test_add_volume(self):
        """Test adding a volume to pending volumes."""
        volume_data = {
            "name": "test-volume",
            "mountpoint": "/var/lib/docker/volumes/test-volume/_data",
            "driver": "local",
            "stack": "mystack",
            "in_use": True,
            "container_count": 2,
            "container_names": ["container1", "container2"],
        }

        self.manager.add_volume(volume_data)

        assert "test-volume" in self.manager._pending_volumes
        assert "test-volume" in self.manager._volumes_in_new_data
        assert self.manager._pending_volumes["test-volume"] == volume_data

    def test_add_volume_updates_selected_data(self):
        """Test that adding a volume updates selected data if it's selected."""
        self.parent.selected_item = ("volume", "test-volume")
        volume_data = {"name": "test-volume", "in_use": False}

        self.manager.add_volume(volume_data)

        assert self.manager.selected_volume_data == volume_data
        assert self.parent.selected_volume_data == volume_data

    @patch("DockTUI.ui.managers.volume_manager.DataTable")
    def test_initialize_table(self, mock_datatable_class):
        """Test table initialization."""
        mock_table = Mock()
        mock_datatable_class.return_value = mock_table

        self.manager._initialize_table()

        assert self.manager.volume_table == mock_table
        assert self.manager._table_initialized is True
        mock_table.add_column.assert_any_call("Name", key="name", width=30)
        mock_table.add_column.assert_any_call("Mount Point", key="mount")
        mock_table.add_column.assert_any_call("Stack", key="stack", width=20)
        mock_table.add_column.assert_any_call("In Use", key="in_use", width=8)
        mock_table.add_column.assert_any_call("Containers", key="containers", width=40)
        mock_table.add_column.assert_any_call("Driver", key="driver", width=15)
        self.parent.volumes_container.mount.assert_called_once_with(mock_table)

    def test_remove_volume(self):
        """Test removing a volume from the table."""
        # Set up mock table and row
        mock_table = Mock()
        mock_row_key = RowKey("row1")
        self.manager.volume_table = mock_table
        self.manager.volume_rows = {"test-volume": mock_row_key}
        self.manager._volume_data = {"test-volume": {"name": "test-volume"}}

        self.manager.remove_volume("test-volume")

        mock_table.remove_row.assert_called_once_with(mock_row_key)
        assert "test-volume" not in self.manager.volume_rows
        assert "test-volume" not in self.manager._volume_data

    def test_remove_volume_clears_selection(self):
        """Test that removing a selected volume clears selection."""
        self.parent.selected_item = ("volume", "test-volume")
        self.manager.selected_volume_data = {"name": "test-volume"}
        self.parent.selected_volume_data = {"name": "test-volume"}

        mock_table = Mock()
        mock_row_key = RowKey("row1")
        self.manager.volume_table = mock_table
        self.manager.volume_rows = {"test-volume": mock_row_key}

        self.manager.remove_volume("test-volume")

        assert self.parent.selected_item is None
        assert self.manager.selected_volume_data is None
        assert self.parent.selected_volume_data is None

    def test_select_volume(self):
        """Test selecting a volume."""
        mock_table = Mock()
        mock_row_key = RowKey("row1")
        # Mock the table.rows to contain the row key
        mock_table.rows = [mock_row_key]
        self.manager.volume_table = mock_table
        self.manager.volume_rows = {"test-volume": mock_row_key}
        self.manager._volume_data = {"test-volume": {"name": "test-volume", "in_use": True}}

        self.manager.select_volume("test-volume")

        assert self.parent.selected_item == ("volume", "test-volume")
        assert self.parent.selected_container_data is None
        assert self.parent.selected_stack_data is None
        assert self.parent.selected_network_data is None
        assert self.manager.selected_volume_data == {"name": "test-volume", "in_use": True}
        assert self.parent.selected_volume_data == {"name": "test-volume", "in_use": True}

        mock_table.move_cursor.assert_called_once_with(row=mock_row_key)
        self.parent._update_footer_with_selection.assert_called_once()
        self.parent._update_cursor_visibility.assert_called_once()
        self.parent.post_message.assert_called_once()

    def test_get_next_selection_after_removal_no_table(self):
        """Test get_next_selection_after_removal with no table."""
        result = self.manager.get_next_selection_after_removal({"volume1"})
        assert result is None

    def test_get_next_selection_after_removal_keep_current(self):
        """Test get_next_selection_after_removal keeps current if not removed."""
        self.parent.selected_item = ("volume", "current-volume")
        mock_table = Mock()
        self.manager.volume_table = mock_table

        result = self.manager.get_next_selection_after_removal({"other-volume"})
        assert result == "current-volume"

    def test_get_next_selection_after_removal_find_previous(self):
        """Test get_next_selection_after_removal finds previous volume."""
        mock_table = Mock()
        row_key1 = RowKey("row1")
        row_key2 = RowKey("row2")
        row_key3 = RowKey("row3")
        
        mock_table.rows = [row_key1, row_key2, row_key3]
        self.manager.volume_table = mock_table
        self.manager.volume_rows = {
            "volume1": row_key1,
            "volume2": row_key2,  # Will be removed
            "volume3": row_key3,
        }

        result = self.manager.get_next_selection_after_removal({"volume2"})
        assert result == "volume1"

    def test_get_next_selection_after_removal_find_next(self):
        """Test get_next_selection_after_removal finds next volume when no previous."""
        mock_table = Mock()
        row_key1 = RowKey("row1")
        row_key2 = RowKey("row2")
        row_key3 = RowKey("row3")
        
        mock_table.rows = [row_key1, row_key2, row_key3]
        self.manager.volume_table = mock_table
        self.manager.volume_rows = {
            "volume1": row_key1,  # Will be removed
            "volume2": row_key2,
            "volume3": row_key3,
        }

        result = self.manager.get_next_selection_after_removal({"volume1"})
        assert result == "volume2"

    def test_get_next_selection_after_removal_all_removed(self):
        """Test get_next_selection_after_removal when all volumes removed."""
        mock_table = Mock()
        row_key1 = RowKey("row1")
        
        mock_table.rows = [row_key1]
        self.manager.volume_table = mock_table
        self.manager.volume_rows = {"volume1": row_key1}

        result = self.manager.get_next_selection_after_removal({"volume1"})
        assert result is None

    def test_cleanup_removed_volumes(self):
        """Test cleanup_removed_volumes removes volumes not in new data."""
        mock_table = Mock()
        row_key1 = RowKey("row1")
        row_key2 = RowKey("row2")
        
        self.manager.volume_table = mock_table
        self.manager.volume_rows = {"volume1": row_key1, "volume2": row_key2}
        self.manager._volumes_in_new_data = {"volume1"}  # volume2 is not in new data

        # Mock remove_volume to track calls
        with patch.object(self.manager, "remove_volume") as mock_remove:
            self.manager.cleanup_removed_volumes()
            mock_remove.assert_called_once_with("volume2")

    def test_flush_pending_volumes_adds_new_rows(self):
        """Test flush_pending_volumes adds new volume rows."""
        # Initialize table first
        mock_table = Mock()
        mock_table.row_count = 0
        self.manager.volume_table = mock_table
        self.manager._table_initialized = True

        # Add pending volumes
        self.manager._pending_volumes = {
            "volume1": {
                "name": "volume1",
                "mountpoint": "/mnt/volume1",
                "driver": "local",
                "stack": "stack1",
                "in_use": True,
                "container_names": ["container1"],
            },
            "volume2": {
                "name": "volume2",
                "mountpoint": "/mnt/volume2",
                "driver": "local",
                "stack": None,
                "in_use": False,
                "container_names": [],
            },
        }

        # Mock add_row to return row keys
        row_key1 = RowKey("row1")
        row_key2 = RowKey("row2")
        mock_table.add_row.side_effect = [row_key1, row_key2]
        mock_table.row_count = 2

        self.manager.flush_pending_volumes()

        # Verify rows were added
        assert mock_table.add_row.call_count == 2
        assert self.manager.volume_rows["volume1"] == row_key1
        assert self.manager.volume_rows["volume2"] == row_key2
        assert len(self.manager._volume_data) == 2
        assert self.manager._pending_volumes == {}

    def test_handle_table_selection(self):
        """Test handling table row selection."""
        row_key = RowKey("row1")
        self.manager.volume_rows = {"test-volume": row_key}
        self.manager._volume_data = {"test-volume": {"name": "test-volume", "in_use": False}}
        self.manager.volume_table = Mock()

        self.manager.handle_table_selection(row_key)

        assert self.parent.selected_item == ("volume", "test-volume")
        assert self.manager.selected_volume_data == {"name": "test-volume", "in_use": False}
        self.parent._update_footer_with_selection.assert_called_once()
        self.parent.post_message.assert_called_once()

    def test_container_names_truncation(self):
        """Test that long container names are truncated properly."""
        # Initialize table
        mock_table = Mock()
        mock_table.row_count = 0
        self.manager.volume_table = mock_table
        self.manager._table_initialized = True

        # Create volume with long container names
        long_names = ["very-long-container-name-" + str(i) for i in range(10)]
        self.manager._pending_volumes = {
            "volume1": {
                "name": "volume1",
                "mountpoint": "/mnt/volume1",
                "driver": "local",
                "stack": None,
                "in_use": True,
                "container_names": long_names,
            }
        }

        row_key = RowKey("row1")
        mock_table.add_row.return_value = row_key
        mock_table.row_count = 1

        self.manager.flush_pending_volumes()

        # Get the call arguments for add_row
        call_args = mock_table.add_row.call_args[0]
        containers_text = call_args[4]  # 5th argument is containers

        # Verify truncation
        assert len(containers_text) <= 37  # MAX_CONTAINER_NAMES_LENGTH
        assert containers_text.endswith("...")

    def test_reset_tracking(self):
        """Test reset_tracking clears all tracking data."""
        self.manager._volumes_in_new_data = {"volume1", "volume2"}
        self.manager._pending_volumes = {"volume1": {}}
        self.manager._volume_data = {"volume1": {}}

        self.manager.reset_tracking()

        assert self.manager._volumes_in_new_data == set()
        assert self.manager._pending_volumes == {}
        assert self.manager._volume_data == {}