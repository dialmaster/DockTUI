"""Volume-specific functionality for the container list widget."""

import logging
from typing import Any, Dict, Optional, Set

from rich.text import Text
from textual.widgets import DataTable, Static
from textual.widgets.data_table import RowKey

from ..base.container_list_base import SelectionChanged
from ..widgets.headers import SectionHeader

logger = logging.getLogger("DockTUI.volume_manager")

# Constants for UI formatting
# Maximum length for container names display before truncation
MAX_CONTAINER_NAMES_LENGTH = 37
# Length at which to truncate container names
TRUNCATED_LENGTH = 34


class VolumeManager:
    """Manages volume-related UI components and operations."""

    def __init__(self, parent):
        """Initialize the volume manager.

        Args:
            parent: The parent ContainerList widget
        """
        self.parent = parent
        self.volume_table: Optional[DataTable] = None
        self.volume_rows: Dict[str, RowKey] = {}  # volume_name -> RowKey
        self._volumes_in_new_data: Set[str] = set()
        self.selected_volume_data: Optional[Dict[str, Any]] = None
        self.volume_section_header: Optional[SectionHeader] = None
        self._table_initialized = False
        self.loading_message: Optional[Static] = None
        self._pending_volumes: Dict[str, Dict[str, Any]] = (
            {}
        )  # Collect volumes before sorting
        self._volume_data: Dict[str, Dict[str, Any]] = {}  # Store volume data by name

    def add_volume(self, volume_data: Dict[str, Any]) -> None:
        """Add a volume to pending volumes for later sorting and display.

        Args:
            volume_data: Dictionary containing volume information
        """
        volume_name = volume_data["name"]

        # Track that this volume exists in the new data
        self._volumes_in_new_data.add(volume_name)

        # Store in pending volumes
        self._pending_volumes[volume_name] = volume_data

        # Update selected volume data if this is the selected volume
        if (
            self.parent.selected_item
            and self.parent.selected_item[0] == "volume"
            and self.parent.selected_item[1] == volume_name
        ):
            self.selected_volume_data = volume_data
            self.parent.selected_volume_data = volume_data

    def _initialize_table(self) -> None:
        """Initialize and mount the volume data table."""
        if self.parent.volumes_container and not self._table_initialized:
            # Hide loading message if it exists
            self.hide_loading_message()

            self.volume_table = DataTable(
                show_header=True,
                header_height=1,
                zebra_stripes=True,
                show_cursor=True,
                cursor_type="row",
                id="volume-table",
            )

            # Add columns
            self.volume_table.add_column("Name", key="name", width=30)
            self.volume_table.add_column(
                "Mount Point", key="mount"
            )  # No width limit for mount point
            self.volume_table.add_column("Stack", key="stack", width=20)
            self.volume_table.add_column("In Use", key="in_use", width=8)
            self.volume_table.add_column("Containers", key="containers", width=40)
            self.volume_table.add_column("Driver", key="driver", width=15)

            # Mount the table in the volumes container
            self.parent.volumes_container.mount(self.volume_table)
            self._table_initialized = True

            # Ensure table is visible
            self.volume_table.display = True
            self.volume_table.styles.width = "100%"

    def get_next_selection_after_removal(
        self, removed_volume_names: Set[str]
    ) -> Optional[str]:
        """Determine which volume should be selected after removal.

        Args:
            removed_volume_names: Set of volume names being removed

        Returns:
            The volume name that should be selected, or None if no volumes remain
        """
        if not self.volume_table or not removed_volume_names:
            return None

        try:
            current_selection = None
            if self.parent.selected_item and self.parent.selected_item[0] == "volume":
                current_selection = self.parent.selected_item[1]

            # If current selection is not being removed, keep it
            if current_selection and current_selection not in removed_volume_names:
                return current_selection

            # Get ordered list of all row keys
            all_row_keys = list(self.volume_table.rows)
            if not all_row_keys:
                return None

            # Find the first removed volume's position in the table
            min_removed_idx = None
            for volume_name in removed_volume_names:
                if volume_name in self.volume_rows:
                    row_key = self.volume_rows[volume_name]
                    try:
                        idx = all_row_keys.index(row_key)
                        if min_removed_idx is None or idx < min_removed_idx:
                            min_removed_idx = idx
                    except ValueError:
                        continue

            if min_removed_idx is None:
                return None

            # Build a list of remaining volumes in order
            remaining_volumes = []
            for row_key in all_row_keys:
                # Find volume name for this row key
                for vol_name, vol_key in self.volume_rows.items():
                    if vol_key == row_key and vol_name not in removed_volume_names:
                        remaining_volumes.append(vol_name)
                        break

            if not remaining_volumes:
                return None

            # Find the best candidate:
            # 1. Try the previous volume (before the first removed)
            for i in range(min_removed_idx - 1, -1, -1):
                row_key = all_row_keys[i]
                for vol_name, vol_key in self.volume_rows.items():
                    if vol_key == row_key and vol_name not in removed_volume_names:
                        return vol_name

            # 2. Try the next volume (after the removed ones)
            for i in range(min_removed_idx, len(all_row_keys)):
                row_key = all_row_keys[i]
                for vol_name, vol_key in self.volume_rows.items():
                    if vol_key == row_key and vol_name not in removed_volume_names:
                        return vol_name

            # 3. Fallback to first remaining volume
            return remaining_volumes[0] if remaining_volumes else None

        except Exception as e:
            logger.error(f"Error finding next selection: {e}")
            return None

    def remove_volume(self, volume_name: str) -> None:
        """Remove a volume from the table.

        Args:
            volume_name: Name of the volume to remove
        """
        if volume_name in self.volume_rows and self.volume_table:
            row_key = self.volume_rows[volume_name]
            try:
                self.volume_table.remove_row(row_key)
                del self.volume_rows[volume_name]
            except Exception as e:
                logger.error(f"Error removing volume {volume_name} from table: {e}")

        # Remove from volume data
        if volume_name in self._volume_data:
            del self._volume_data[volume_name]

        # Remove from pending volumes if present
        if volume_name in self._pending_volumes:
            del self._pending_volumes[volume_name]

        # Clear selection if this volume was selected
        if (
            self.parent.selected_item
            and self.parent.selected_item[0] == "volume"
            and self.parent.selected_item[1] == volume_name
        ):
            self.parent.selected_item = None
            self.selected_volume_data = None
            # Also clear the parent's reference
            self.parent.selected_volume_data = None

    def select_volume(self, volume_name: str) -> None:
        """Select a volume and update the footer.

        Args:
            volume_name: Name of the volume to select
        """
        if volume_name in self.volume_rows and self.volume_table:
            # Clear any previous selection
            self.parent.selected_item = ("volume", volume_name)
            self.parent.selected_container_data = None
            self.parent.selected_stack_data = None
            self.parent.selected_network_data = None

            # Get the volume data
            volume_data = self._volume_data.get(volume_name, {})
            self.selected_volume_data = volume_data
            self.parent.selected_volume_data = volume_data

            # Move cursor to the selected volume
            row_key = self.volume_rows[volume_name]

            # Verify the row key is still valid in the table
            try:
                if row_key in self.volume_table.rows:
                    self.volume_table.move_cursor(row=row_key)
            except Exception as e:
                logger.error(f"Error moving cursor to volume {volume_name}: {e}")

            # Update the footer and cursor visibility
            self.parent._update_footer_with_selection()
            self.parent._update_cursor_visibility()

            # Post selection change message
            self.parent.post_message(
                SelectionChanged("volume", volume_name, volume_data)
            )

    def reset_tracking(self) -> None:
        """Reset tracking for new data updates."""
        self._volumes_in_new_data = set()
        self._pending_volumes.clear()
        self._volume_data.clear()

    def cleanup_removed_volumes(self) -> None:
        """Remove volumes that no longer exist."""
        volumes_to_remove = []
        for volume_name in list(self.volume_rows.keys()):
            if volume_name not in self._volumes_in_new_data:
                volumes_to_remove.append(volume_name)

        for volume_name in volumes_to_remove:
            self.remove_volume(volume_name)

    def flush_pending_volumes(self) -> None:
        """Add all pending volumes to the table in sorted order."""
        if not self._pending_volumes:
            return

        # Initialize table if needed and container is mounted
        if (
            not self._table_initialized
            and self.parent.volumes_container
            and self.parent.volumes_container.parent
        ):
            self._initialize_table()

        if not self._table_initialized:
            return

        logger.debug(
            f"flush_pending_volumes: Processing {len(self._pending_volumes)} volumes"
        )

        # Sort volumes: in-use first, then by name descending
        sorted_volumes = sorted(
            self._pending_volumes.items(),
            key=lambda x: (
                0 if x[1].get("in_use", False) else 1,  # In-use volumes get 0
                x[0].lower(),  # Volume name for secondary sort
            ),
        )

        # Reverse name order within each group
        in_use_volumes = []
        not_in_use_volumes = []

        for volume_name, volume_data in sorted_volumes:
            if volume_data.get("in_use", False):
                in_use_volumes.append((volume_name, volume_data))
            else:
                not_in_use_volumes.append((volume_name, volume_data))

        # Reverse each group for descending name order
        in_use_volumes.reverse()
        not_in_use_volumes.reverse()

        # Combine groups
        sorted_volumes = in_use_volumes + not_in_use_volumes

        logger.debug(
            f"flush_pending_volumes: {len(in_use_volumes)} in-use, {len(not_in_use_volumes)} not in-use"
        )

        # Add volumes to table in sorted order
        for volume_name, volume_data in sorted_volumes:
            # Format the data for display
            stack_text = volume_data["stack"] if volume_data["stack"] else "None"
            in_use_text = "Yes" if volume_data.get("in_use", False) else "No"
            mount_display = volume_data["mountpoint"]

            # Format container names
            container_names = volume_data.get("container_names", [])
            if container_names:
                containers_text = ", ".join(container_names)
                # Truncate if too long
                if len(containers_text) > MAX_CONTAINER_NAMES_LENGTH:
                    containers_text = containers_text[:TRUNCATED_LENGTH] + "..."
            else:
                containers_text = "None"

            if volume_name not in self.volume_rows:
                # Add new row
                row_key = self.volume_table.add_row(
                    volume_name,
                    mount_display,
                    stack_text,
                    in_use_text,
                    containers_text,
                    volume_data["driver"],
                )
                # Store the row key
                self.volume_rows[volume_name] = row_key
                self._volume_data[volume_name] = volume_data  # Store volume data
            else:
                # Update existing row
                row_key = self.volume_rows[volume_name]
                self.volume_table.update_cell(row_key, "name", volume_name)
                self.volume_table.update_cell(row_key, "mount", mount_display)
                self.volume_table.update_cell(row_key, "stack", stack_text)
                self.volume_table.update_cell(row_key, "in_use", in_use_text)
                self.volume_table.update_cell(row_key, "containers", containers_text)
                self.volume_table.update_cell(row_key, "driver", volume_data["driver"])
                self._volume_data[volume_name] = (
                    volume_data  # Update stored volume data
                )

        # Clear pending volumes
        self._pending_volumes.clear()

    def sort_volume_table(self) -> None:
        """Sort the volume table with in-use volumes at top, then by name descending."""
        if not self.volume_table or self.volume_table.row_count == 0:
            logger.debug("sort_volume_table: No table or no rows to sort")
            return

        logger.debug(
            f"sort_volume_table: Starting sort with {self.volume_table.row_count} rows"
        )

        # Save the currently selected volume if any
        selected_volume_name = None
        if self.parent.selected_item and self.parent.selected_item[0] == "volume":
            selected_volume_name = self.parent.selected_item[1]

        # Get all rows with their data
        rows_data = []
        for row_key in self.volume_table.rows:
            row_cells = []
            for column in self.volume_table.columns:
                cell_value = self.volume_table.get_cell(row_key, column.key)
                row_cells.append(cell_value)

            # Extract the values we need for sorting
            name = row_cells[0]  # Name column
            in_use = row_cells[3]  # In Use column

            rows_data.append(
                {"key": row_key, "cells": row_cells, "name": name, "in_use": in_use}
            )

        logger.debug(f"sort_volume_table: Collected {len(rows_data)} rows")

        # Log first few rows before sorting
        for i, row in enumerate(rows_data[:5]):
            logger.debug(f"  Row {i}: name={row['name']}, in_use={row['in_use']}")

        # Sort: First by in_use (Yes before No), then by name descending
        # We use a custom sort key that returns a tuple:
        # - First element: 0 for "Yes" (in use), 1 for "No" (not in use)
        # - Second element: name (for reverse alphabetical within each group)
        sorted_rows = sorted(
            rows_data,
            key=lambda x: (
                0 if x["in_use"] == "Yes" else 1,  # In-use volumes get 0, others get 1
                x["name"].lower(),  # Case-insensitive name comparison
            ),
        )

        # Now we need to reverse the name order within each group
        # Split into groups
        in_use_volumes = []
        not_in_use_volumes = []

        for row in sorted_rows:
            if row["in_use"] == "Yes":
                in_use_volumes.append(row)
            else:
                not_in_use_volumes.append(row)

        logger.debug(
            f"sort_volume_table: {len(in_use_volumes)} in-use, {len(not_in_use_volumes)} not in-use"
        )

        # Reverse each group to get descending name order
        in_use_volumes.reverse()
        not_in_use_volumes.reverse()

        # Combine with in-use volumes first
        sorted_rows = in_use_volumes + not_in_use_volumes

        # Log first few rows after sorting
        logger.debug("sort_volume_table: After sorting:")
        for i, row in enumerate(sorted_rows[:5]):
            logger.debug(f"  Row {i}: name={row['name']}, in_use={row['in_use']}")

        # Clear the table
        self.volume_table.clear()
        self.volume_rows.clear()

        # Re-add rows in sorted order
        for row_data in sorted_rows:
            row_key = self.volume_table.add_row(*row_data["cells"])
            # Reconstruct the volume_rows mapping with row key
            volume_name = row_data["name"]
            self.volume_rows[volume_name] = row_key

        logger.debug(
            f"sort_volume_table: Sort completed, table now has {self.volume_table.row_count} rows"
        )

        # Restore selection if there was one
        if selected_volume_name and selected_volume_name in self.volume_rows:
            row_key = self.volume_rows[selected_volume_name]
            self.volume_table.move_cursor(row=row_key)

    def get_volume_table(self) -> Optional[DataTable]:
        """Get the volume table widget."""
        return self.volume_table

    def handle_table_selection(self, row_key: RowKey) -> None:
        """Handle volume selection from table row selection.

        Args:
            row_key: The key of the selected row
        """
        # Find the volume name for this row key
        for volume_name, stored_key in self.volume_rows.items():
            if stored_key == row_key:
                self.parent.selected_item = ("volume", volume_name)
                self.parent.selected_container_data = None
                self.parent.selected_stack_data = None
                self.parent.selected_network_data = None

                # Get the volume data
                volume_data = self._volume_data.get(volume_name, {})
                self.selected_volume_data = volume_data
                self.parent.selected_volume_data = volume_data

                # Update the footer
                self.parent._update_footer_with_selection()

                # Post selection change message with the actual volume data
                self.parent.post_message(
                    SelectionChanged("volume", volume_name, volume_data)
                )
                break

    def show_loading_message(self) -> None:
        """Show a loading message in the volumes container."""
        if self.parent.volumes_container and not self.loading_message:
            self.loading_message = Static(
                Text("Loading volume information...", style="dim italic"),
                classes="volume-loading-message",
            )
            self.parent.volumes_container.mount(self.loading_message)

    def hide_loading_message(self) -> None:
        """Hide the loading message if it exists."""
        if self.loading_message and self.loading_message.parent:
            self.loading_message.remove()
            self.loading_message = None
