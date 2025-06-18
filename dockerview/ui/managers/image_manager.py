"""Image-specific functionality for the container list widget."""

import logging
from typing import Dict, Optional, Tuple

from textual.containers import Container
from textual.widgets import DataTable

from ..base.container_list_base import SelectionChanged

logger = logging.getLogger("dockerview.image_manager")


class ImageManager:
    """Manages image-related UI components and operations."""

    def __init__(self, parent):
        """Initialize the image manager.

        Args:
            parent: The parent ContainerList widget
        """
        self.parent = parent
        self.images_table: Optional[DataTable] = None
        self.images_container: Optional[Container] = None
        self.image_rows: Dict[str, int] = {}  # Map image ID to row index
        self._images_in_new_data = set()
        self.selected_image_data: Optional[Dict] = None
        self._table_initialized = False

        # For compatibility with existing structure
        self.image_headers = {}  # Empty dict for compatibility
        self.expanded_images = set()  # Empty set since images don't expand

    def reset_tracking(self) -> None:
        """Reset tracking for new data update."""
        self._images_in_new_data.clear()

    def prepare_new_containers(self) -> Dict[str, Tuple]:
        """Prepare new containers for mounting.

        Returns an empty dict since we use a single table for all images.
        """
        # Don't initialize table here - it will be done when adding first image
        return {}

    def _initialize_table(self) -> None:
        """Initialize the images table within the images container."""
        if self.parent.images_container and not self._table_initialized:
            # Create the images table with fixed rows to prevent scrolling
            self.images_table = DataTable(
                show_cursor=True,
                cursor_foreground_priority=True,
                zebra_stripes=True,
                fixed_rows=0,  # This might help with scrolling behavior
            )
            self.images_table.can_focus = True
            self.images_table.show_vertical_scrollbar = False

            # Add column headers
            self.images_table.add_columns(
                "Repository",
                "Tag",
                "Image ID",
                "Containers",
                "Created",
                "Size",
                "Status",
            )

            # Mount the table in the images container
            self.parent.images_container.mount(self.images_table)
            self._table_initialized = True

            # Connect the table selection event
            self.images_table.cursor_type = "row"

            # Ensure table is visible
            self.images_table.display = True
            self.images_table.styles.width = "100%"
            # Let the table handle its own height based on content

            logger.debug(
                f"Images table initialized with {self.images_table.row_count} rows"
            )

    def add_image(self, image_data: dict) -> None:
        """Add or update an image in the table.

        Args:
            image_data: Dictionary containing image information including:
                - id: Image ID (short form)
                - tags: List of image tags
                - created: Creation timestamp
                - size: Image size (human-readable)
                - container_names: List of container names using this image
                - has_running: Boolean indicating if any container is running
                - architecture: Image architecture
                - os: Operating system
        """
        # Initialize table if needed and container is mounted
        if (
            not self._table_initialized
            and self.parent.images_container
            and self.parent.images_container.parent
        ):
            self._initialize_table()

        if not self._table_initialized:
            return

        image_id = image_data["id"]

        # Track that this image exists in the new data
        self._images_in_new_data.add(image_id)

        # Parse repository and tag from tags list
        repository = "<none>"
        tag = "<none>"
        if image_data.get("tags"):
            # Take the first tag
            first_tag = image_data["tags"][0]
            if ":" in first_tag:
                repository, tag = first_tag.rsplit(":", 1)
            else:
                repository = first_tag
                tag = "latest"

        # Format container info
        container_names = image_data.get("container_names", [])
        if container_names:
            # Show container names, truncate if too long
            containers_text = ", ".join(container_names)
            if len(containers_text) > 30:
                containers_text = containers_text[:27] + "..."
        else:
            containers_text = "None"

        # Determine status based on container usage
        if container_names:
            # Check if any containers are running
            status = "Active" if image_data.get("has_running", False) else "Stopped"
        else:
            status = "Unused"

        # Format created time (just show date part if it's a timestamp)
        created = image_data.get("created", "N/A")
        if created != "N/A" and "T" in created:
            created = created.split("T")[0]  # Just the date part

        # Create row data
        row_data = (
            repository,
            tag,
            image_id[:12],  # Short ID
            containers_text,
            created,
            image_data.get("size", "N/A"),
            status,
        )

        if image_id in self.image_rows:
            # Update existing row
            row_index = self.image_rows[image_id]
            for col_index, value in enumerate(row_data):
                self.images_table.update_cell_at((row_index, col_index), value)
        else:
            # Add new row
            self.images_table.add_row(*row_data, key=image_id)
            # Store the row index (it's the last row added)
            self.image_rows[image_id] = self.images_table.row_count - 1
            logger.debug(
                f"Added image {image_id} - total rows: {self.images_table.row_count}"
            )

        # Update selected image data if this is the selected image
        if (
            self.parent.selected_item
            and self.parent.selected_item[0] == "image"
            and self.parent.selected_item[1] == image_id
        ):
            self.selected_image_data = image_data

    def remove_image(self, image_id: str) -> None:
        """Remove an image from the table.

        Args:
            image_id: The ID of the image to remove
        """
        if not self.images_table or image_id not in self.image_rows:
            return

        row_index = self.image_rows[image_id]

        # Get the row key before removing
        row_key = None
        for row in self.images_table.rows:
            if row.index == row_index:
                row_key = row.key
                break

        if row_key:
            self.images_table.remove_row(row_key)

            # Update row indices for remaining images
            del self.image_rows[image_id]
            # Rebuild the index mapping
            self.image_rows.clear()
            for idx, row in enumerate(self.images_table.rows):
                if row.key and hasattr(row.key, "value"):
                    self.image_rows[row.key.value] = idx

    def cleanup_removed_images(self) -> None:
        """Remove images that are no longer present."""
        images_to_remove = []
        for image_id in self.image_rows:
            if image_id not in self._images_in_new_data:
                images_to_remove.append(image_id)

        logger.debug(f"Cleaning up {len(images_to_remove)} removed images")
        for image_id in images_to_remove:
            self.remove_image(image_id)

        # Sort the table after cleanup
        logger.debug(
            f"Sorting table with {self.images_table.row_count if self.images_table else 0} rows"
        )
        self.sort_images_table()

    def select_image(self, image_id: str) -> None:
        """Select an image and update the footer.

        Args:
            image_id: ID of the image to select
        """
        if image_id in self.image_rows:
            # Clear any previous selection
            self.parent.selected_item = ("image", image_id)
            self.parent.selected_container_data = None
            self.parent.selected_stack_data = None
            self.parent.selected_network_data = None
            self.parent.selected_volume_data = None

            # Find and store the image data
            if hasattr(self.parent, "_last_images_data"):
                for img_data in self.parent._last_images_data.values():
                    if img_data["id"] == image_id:
                        self.selected_image_data = img_data
                        break

            # Focus the table row
            if self.images_table:
                row_index = self.image_rows[image_id]
                self.images_table.move_cursor(row=row_index)

    def handle_selection(self, row_key) -> bool:
        """Handle selection of an image row.

        Args:
            row_key: The key of the selected row

        Returns:
            True if the selection was handled, False otherwise
        """
        if row_key and hasattr(row_key, "value") and row_key.value in self.image_rows:
            image_id = row_key.value
            self.parent.selected_item = ("image", image_id)

            # Find the image data from parent's data
            if hasattr(self.parent, "_last_images_data"):
                for img_data in self.parent._last_images_data.values():
                    if img_data["id"] == image_id:
                        self.selected_image_data = img_data
                        break

            # Notify about selection change
            self.parent.post_message(
                SelectionChanged("image", image_id, self.selected_image_data or {})
            )
            return True
        return False

    def toggle_images_section(self) -> None:
        """Toggle the images section visibility."""
        if self.images_table:
            self.images_table.display = not self.images_table.display

    def get_existing_containers(self) -> dict:
        """Get existing containers for updates.

        For images, we don't have individual containers, just the table.
        Returns an empty dict since images use a different UI pattern.
        """
        return {}

    def sort_images_table(self) -> None:
        """Sort the images table with unused images at the bottom."""
        if not self.images_table or self.images_table.row_count == 0:
            return

        # Get all rows with their data
        rows_data = []

        # Iterate through rows using their indices
        for row_idx in range(self.images_table.row_count):
            try:
                # Get the row data directly by index
                row_cells = []
                for col_idx in range(len(self.images_table.columns)):
                    cell_value = self.images_table.get_cell_at((row_idx, col_idx))
                    row_cells.append(str(cell_value))

                # Find the image_id for this row
                image_id = None
                for img_id, stored_idx in self.image_rows.items():
                    if stored_idx == row_idx:
                        image_id = img_id
                        break

                if image_id and len(row_cells) >= 7:
                    rows_data.append((image_id, tuple(row_cells)))
            except Exception as e:
                logger.debug(f"Error getting row data at index {row_idx}: {e}")
                continue

        # Sort by status first (Active, Stopped, Unused), then by repository name
        def sort_key(item):
            image_id, row_data = item
            repository = row_data[0]  # Repository is first column
            status = row_data[6]  # Status is last column

            # Primary sort by status: Active (0), Stopped (1), Unused (2)
            if status == "Active":
                status_order = 0
            elif status == "Stopped":
                status_order = 1
            else:  # Unused
                status_order = 2

            # Secondary sort by repository name (alphabetical)
            return (status_order, repository.lower())

        rows_data.sort(key=sort_key)

        # Clear all rows - use clear() which preserves columns
        self.images_table.clear(columns=False)
        self.image_rows.clear()

        # Re-add all rows in sorted order
        for idx, (image_id, row_data) in enumerate(rows_data):
            self.images_table.add_row(*row_data, key=image_id)
            self.image_rows[image_id] = idx
