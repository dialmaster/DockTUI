"""Image-specific functionality for the container list widget."""

import logging
from datetime import datetime
from typing import Dict, Optional, Set, Tuple

from rich.text import Text
from textual.containers import Container
from textual.widgets import DataTable, Static

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
        self.loading_message: Optional[Static] = None
        self.image_rows: Dict[str, int] = {}  # Map image ID to row index
        self._images_in_new_data = set()
        self.selected_image_data: Optional[Dict] = None
        self._table_initialized = False
        self._removed_images: Set[str] = set()  # Track removed images for strikethrough
        self._preserve_selected_image_id: Optional[str] = (
            None  # Image ID to preserve during refresh
        )

        # For compatibility with existing structure
        self.image_headers = {}  # Empty dict for compatibility
        self.expanded_images = set()  # Empty set since images don't expand

    def reset_tracking(self) -> None:
        """Reset tracking for new data update."""
        self._images_in_new_data.clear()

    def show_loading_message(self) -> None:
        """Show a loading message in the images container."""
        if self.parent.images_container and not self.loading_message:
            self.loading_message = Static(
                Text("Loading images, please wait...", style="dim italic"),
                classes="loading-message",
            )
            self.loading_message.styles.width = "100%"
            self.loading_message.styles.text_align = "center"
            self.loading_message.styles.padding = (2, 0)
            self.parent.images_container.mount(self.loading_message)

    def hide_loading_message(self) -> None:
        """Hide the loading message if it exists."""
        if self.loading_message and self.loading_message.parent:
            self.loading_message.remove()
            self.loading_message = None

    def show_no_images_message(self) -> None:
        """Show a message when no images are found."""
        if self.parent.images_container and not self.loading_message:
            self.loading_message = Static(
                Text("No images found", style="dim italic"), classes="no-images-message"
            )
            self.loading_message.styles.width = "100%"
            self.loading_message.styles.text_align = "center"
            self.loading_message.styles.padding = (2, 0)
            self.parent.images_container.mount(self.loading_message)

    def prepare_new_containers(self) -> Dict[str, Tuple]:
        """Prepare new containers for mounting.

        Returns an empty dict since we use a single table for all images.
        """
        # Don't initialize table here - it will be done when adding first image
        return {}

    def _initialize_table(self) -> None:
        """Initialize the images table within the images container."""
        if self.parent.images_container and not self._table_initialized:
            # Hide loading message if it exists
            self.hide_loading_message()
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

        # Format repository name - truncate beginning if > 20 chars
        display_repository = repository
        if len(repository) > 25:
            display_repository = (
                "..." + repository[-25:]
            )  # Keep last 17 chars plus ellipsis

        # Format tag - truncate end if > 10 chars
        display_tag = tag
        if len(tag) > 10:
            display_tag = tag[:10] + "..."

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

        # Create row data - apply strikethrough if image is marked as removed
        if image_id in self._removed_images:
            row_data = (
                Text(display_repository, style="strike dim"),
                Text(display_tag, style="strike dim"),
                Text(image_id[:12], style="strike dim"),  # Short ID
                Text(containers_text, style="strike dim"),
                Text(created, style="strike dim"),
                Text(image_data.get("size", "N/A"), style="strike dim"),
                Text(status, style="strike dim"),
            )
        else:
            row_data = (
                display_repository,
                display_tag,
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

    def mark_image_as_removed(self, image_id: str) -> None:
        """Mark an image as removed by applying strikethrough style.

        Args:
            image_id: The ID of the image to mark as removed
        """
        if not self.images_table or image_id not in self.image_rows:
            return

        # Add to removed images set
        self._removed_images.add(image_id)

        # Get row index
        row_index = self.image_rows[image_id]

        # Update all cells in the row with strikethrough style
        for col_index in range(len(self.images_table.columns)):
            cell_value = self.images_table.get_cell_at((row_index, col_index))
            self.images_table.update_cell_at(
                (row_index, col_index), Text(str(cell_value), style="strike dim")
            )

    def remove_image(self, image_id: str) -> None:
        """Remove an image from the table.

        Args:
            image_id: The ID of the image to remove
        """
        if not self.images_table or image_id not in self.image_rows:
            return

        # We stored the image_id as the row key when adding rows
        # So we can remove directly by the image_id
        try:
            self.images_table.remove_row(image_id)

            # Update row indices for remaining images
            del self.image_rows[image_id]

            # Remove from removed images set if present
            self._removed_images.discard(image_id)

            # Rebuild the index mapping
            self.image_rows.clear()
            for idx, row in enumerate(self.images_table.rows):
                # The row key is the image_id we set when adding the row
                if row.key:
                    self.image_rows[row.key] = idx
        except Exception as e:
            logger.error(f"Error removing image {image_id} from table: {e}")

    def cleanup_removed_images(self) -> None:
        """Remove images that are no longer present."""
        images_to_remove = []
        for image_id in self.image_rows:
            if image_id not in self._images_in_new_data:
                images_to_remove.append(image_id)

        logger.debug(f"Cleaning up {len(images_to_remove)} removed images")
        for image_id in images_to_remove:
            self.remove_image(image_id)

        # Clear the removed images tracking after cleanup
        self._removed_images.clear()

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

            # Store basic image data from the table
            if image_id in self.image_rows and self.images_table:
                row_index = self.image_rows[image_id]
                # Extract data from the table row
                self.selected_image_data = {
                    "id": image_id,
                    "repository": str(self.images_table.get_cell_at((row_index, 0))),
                    "tag": str(self.images_table.get_cell_at((row_index, 1))),
                    "containers": str(self.images_table.get_cell_at((row_index, 3))),
                    "created": str(self.images_table.get_cell_at((row_index, 4))),
                    "size": str(self.images_table.get_cell_at((row_index, 5))),
                    "status": str(self.images_table.get_cell_at((row_index, 6))),
                    "tags": [],  # Will be populated from repository:tag
                }
                # Build tags list from repository and tag
                repo = self.selected_image_data["repository"]
                tag = self.selected_image_data["tag"]
                if repo != "<none>" and tag != "<none>":
                    self.selected_image_data["tags"] = [f"{repo}:{tag}"]
                # Also update parent's reference
                self.parent.selected_image_data = self.selected_image_data

            # Focus the table row
            if self.images_table:
                row_index = self.image_rows[image_id]
                self.images_table.move_cursor(row=row_index)

            # Post selection changed event
            if self.selected_image_data:
                self.parent.post_message(
                    SelectionChanged("image", image_id, self.selected_image_data)
                )

    def handle_selection(self, row_key) -> bool:
        """Handle selection of an image row.

        Args:
            row_key: The key of the selected row

        Returns:
            True if the selection was handled, False otherwise
        """
        if not row_key or not self.images_table:
            return False

        try:
            # Get the row index from the row key
            row_index = self.images_table.get_row_index(row_key)
            if row_index is None:
                return False

            # Find the image_id from our mapping
            image_id = None
            for img_id, idx in self.image_rows.items():
                if idx == row_index:
                    image_id = img_id
                    break

            if not image_id:
                return False

            # Use the parent's select_image method which handles everything properly
            self.parent.select_image(image_id)
            return True
        except Exception as e:
            logger.error(f"Error handling image selection: {e}")
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

    def get_next_selection_after_removal(
        self, removed_image_ids: Set[str]
    ) -> Optional[str]:
        """Determine which image should be selected after removal.

        Args:
            removed_image_ids: Set of image IDs being removed

        Returns:
            The image ID that should be selected, or None if no images remain
        """
        if not self.images_table or not removed_image_ids:
            return None

        current_selection = None
        if self.parent.selected_item and self.parent.selected_item[0] == "image":
            current_selection = self.parent.selected_item[1]

        if current_selection and current_selection not in removed_image_ids:
            return current_selection

        min_removed_row_idx = float("inf")
        for image_id in removed_image_ids:
            if image_id in self.image_rows:
                min_removed_row_idx = min(
                    min_removed_row_idx, self.image_rows[image_id]
                )

        if min_removed_row_idx == float("inf"):
            return None

        for row_idx in range(min_removed_row_idx - 1, -1, -1):
            for image_id, idx in self.image_rows.items():
                if (
                    idx == row_idx
                    and image_id not in removed_image_ids
                    and image_id not in self._removed_images
                ):
                    return image_id

        for row_idx in range(min_removed_row_idx + 1, self.images_table.row_count):
            for image_id, idx in self.image_rows.items():
                if (
                    idx == row_idx
                    and image_id not in removed_image_ids
                    and image_id not in self._removed_images
                ):
                    return image_id

        return None

    def sort_images_table(self) -> None:
        """Sort the images table:
        1) Status (Active, Stopped, Unused)
        2) Created (newest → oldest)
        3) Image ID (lexicographic)
        """
        if not self.images_table or self.images_table.row_count == 0:
            return

        rows_data = []
        for row_idx in range(self.images_table.row_count):
            try:
                cells = [
                    str(self.images_table.get_cell_at((row_idx, col_idx)))
                    for col_idx in range(len(self.images_table.columns))
                ]

                # Find the image_id mapped to this row index
                image_id = next(
                    (iid for iid, idx in self.image_rows.items() if idx == row_idx),
                    None,
                )
                if image_id and len(cells) >= 7:
                    rows_data.append((image_id, tuple(cells)))
            except Exception as e:
                logger.debug(f"Error getting row data at index {row_idx}: {e}")

        def _created_ts(created: str) -> float:
            """Convert 'YYYY-MM-DD' or ISO-8601 string to POSIX seconds.
            Return 0 for unparsable or 'N/A' (treat as oldest)."""
            if not created or created == "N/A":
                return 0
            try:
                # Accept either full ISO or simple date
                if "T" in created:
                    return datetime.fromisoformat(created).timestamp()
                return datetime.strptime(created, "%Y-%m-%d").timestamp()
            except Exception:
                return 0

        def sort_key(item):
            image_id, cells = item
            status = cells[6]
            created = cells[4]

            status_order = (
                0 if status == "Active" else 1 if status == "Stopped" else 2  # Unused
            )

            # Negative timestamp → newest first
            return (status_order, -_created_ts(created), image_id)

        rows_data.sort(key=sort_key)

        # Rebuild table
        self.images_table.clear(columns=False)
        self.image_rows.clear()
        for idx, (image_id, cells) in enumerate(rows_data):
            self.images_table.add_row(*cells, key=image_id)
            self.image_rows[image_id] = idx
