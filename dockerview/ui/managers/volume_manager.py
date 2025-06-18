"""Volume-specific functionality for the container list widget."""

import logging
from typing import Dict, Optional

from textual.containers import Container

from ..base.container_list_base import SelectionChanged
from ..widgets.headers import VolumeHeader

logger = logging.getLogger("dockerview.volume_manager")


class VolumeManager:
    """Manages volume-related UI components and operations."""

    def __init__(self, parent):
        """Initialize the volume manager.

        Args:
            parent: The parent ContainerList widget
        """
        self.parent = parent
        self.volume_headers: Dict[str, VolumeHeader] = {}
        self.expanded_volumes = set()
        self._volumes_in_new_data = set()
        self.selected_volume_data: Optional[Dict] = None

    def add_volume(self, volume_data: dict) -> None:
        """Add or update a volume section in the container list.

        Args:
            volume_data: Dictionary containing volume information
        """
        volume_name = volume_data["name"]

        # Track that this volume exists in the new data
        self._volumes_in_new_data.add(volume_name)

        if volume_name not in self.volume_headers:
            header = VolumeHeader(
                volume_name,
                volume_data["driver"],
                volume_data["mountpoint"],
                volume_data["created"],
                volume_data["stack"],
                volume_data["scope"],
            )

            self.volume_headers[volume_name] = header
            # No table needed for volumes since they don't expand

            # Update selected volume data if this is the selected volume
            if (
                self.parent.selected_item
                and self.parent.selected_item[0] == "volume"
                and self.parent.selected_item[1] == volume_name
            ):
                self.selected_volume_data = volume_data
        else:
            # Update existing volume
            header = self.volume_headers[volume_name]
            header.driver = volume_data["driver"]
            header.mountpoint = volume_data["mountpoint"]
            header.created = volume_data["created"]
            header.stack = volume_data["stack"]
            header.scope = volume_data["scope"]
            header._update_content()

            # Update selected volume data if this is the selected volume
            if (
                self.parent.selected_item
                and self.parent.selected_item[0] == "volume"
                and self.parent.selected_item[1] == volume_name
            ):
                self.selected_volume_data = volume_data

    def remove_volume(self, volume_name: str) -> None:
        """Remove a volume and its associated UI elements.

        Args:
            volume_name: Name of the volume to remove
        """
        self.expanded_volumes.discard(volume_name)

        if self.parent.volumes_container:
            for child in list(self.parent.volumes_container.children):
                if isinstance(child, Container) and "volume-container" in child.classes:
                    for widget in child.children:
                        if (
                            isinstance(widget, VolumeHeader)
                            and widget.volume_name == volume_name
                        ):
                            child.remove()
                            break

        if volume_name in self.volume_headers:
            del self.volume_headers[volume_name]

        if (
            self.parent.selected_item
            and self.parent.selected_item[0] == "volume"
            and self.parent.selected_item[1] == volume_name
        ):
            self.parent.selected_item = None
            self.selected_volume_data = None

    def select_volume(self, volume_name: str) -> None:
        """Select a volume and update the footer.

        Args:
            volume_name: Name of the volume to select
        """
        if volume_name in self.volume_headers:
            # Clear any previous selection
            self.parent.selected_item = ("volume", volume_name)
            self.parent.selected_container_data = None
            self.parent.selected_stack_data = None
            self.parent.selected_network_data = None

            # Store volume data for footer display
            header = self.volume_headers[volume_name]
            self.selected_volume_data = {
                "name": volume_name,
                "driver": header.driver,
                "mountpoint": header.mountpoint,
                "created": header.created,
                "stack": header.stack,
                "scope": header.scope,
            }
            self.parent.selected_volume_data = self.selected_volume_data

            # Update the footer and cursor visibility
            self.parent._update_footer_with_selection()
            self.parent._update_cursor_visibility()

            # Post selection change message
            self.parent.post_message(
                SelectionChanged("volume", volume_name, self.selected_volume_data)
            )

    def reset_tracking(self) -> None:
        """Reset tracking for new data updates."""
        self._volumes_in_new_data = set()

    def save_expanded_state(self) -> None:
        """Save the current expanded state of volumes."""
        self.expanded_volumes = {
            name for name, header in self.volume_headers.items() if header.expanded
        }

    def cleanup_removed_volumes(self) -> None:
        """Remove volumes that no longer exist."""
        volumes_to_remove = []
        for volume_name in list(self.volume_headers.keys()):
            if volume_name not in self._volumes_in_new_data:
                volumes_to_remove.append(volume_name)

        for volume_name in volumes_to_remove:
            self.remove_volume(volume_name)

    def get_existing_containers(self) -> dict:
        """Get existing volume containers for updates."""
        existing_volume_containers = {}
        if self.parent.volumes_container:
            for child in self.parent.volumes_container.children:
                if isinstance(child, Container) and "volume-container" in child.classes:
                    for widget in child.children:
                        if isinstance(widget, VolumeHeader):
                            existing_volume_containers[widget.volume_name] = child
                            break
        return existing_volume_containers

    def prepare_new_containers(self) -> dict:
        """Prepare new volume containers to be added."""
        new_volume_containers = {}
        existing_containers = self.get_existing_containers()

        for volume_name in sorted(self.volume_headers.keys()):
            if volume_name not in existing_containers:
                header = self.volume_headers[volume_name]
                volume_container = Container(classes="volume-container")
                new_volume_containers[volume_name] = (
                    volume_container,
                    header,
                    None,  # No table for volumes
                )
        return new_volume_containers
