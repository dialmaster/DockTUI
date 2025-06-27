"""Footer formatting functionality for the container list widget."""

import logging

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

logger = logging.getLogger("dockerview.footer_formatter")


class FooterFormatter:
    """Handles formatting and updating the footer status bar."""

    def __init__(self, container_list):
        """Initialize the footer formatter.

        Args:
            container_list: The parent ContainerList widget
        """
        self.container_list = container_list

    def update_footer_with_selection(self) -> None:
        """Update the footer with the current selection information."""
        if self.container_list.screen is None:
            logger.warning("Cannot update footer: screen is None")
            return

        try:
            status_bar = self.container_list.screen.query_one("#status_bar")

            if self.container_list.selected_item is None:
                self._update_no_selection(status_bar)
                return

            item_type, item_id = self.container_list.selected_item

            # Route to appropriate handler based on item type
            if item_type == "volume":
                self._update_volume(status_bar, item_id)
            elif item_type == "image":
                self._update_image(status_bar, item_id)
            elif item_type == "network":
                self._update_network(status_bar, item_id)
            elif item_type == "stack":
                self._update_stack(status_bar, item_id)
            elif item_type == "container":
                self._update_container(status_bar, item_id)
            else:
                self._update_invalid_selection(status_bar, item_type, item_id)

        except Exception as e:
            logger.error(f"Error updating status bar: {str(e)}", exc_info=True)

    def _update_no_selection(self, status_bar: Static) -> None:
        """Update footer when there's no selection."""
        no_selection_text = Text("No selection", Style(color="white", bold=True))
        status_bar.update(no_selection_text)
        # Don't post SelectionChanged here - it's already handled by managers

    def _update_volume(self, status_bar: Static, item_id: str) -> None:
        """Update footer for volume selection."""
        if not self.container_list.selected_volume_data:
            return

        volume_data = self.container_list.selected_volume_data
        selection_text = self._create_selection_header()
        selection_text.append("  Volume: ", Style(color="white"))
        selection_text.append(
            f"{volume_data['name']}", Style(color="magenta", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Driver: ", Style(color="white"))
        selection_text.append(
            f"{volume_data['driver']}", Style(color="blue", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Stack: ", Style(color="white"))
        if volume_data["stack"]:
            selection_text.append(
                f"{volume_data['stack']}", Style(color="green", bold=True)
            )
        else:
            selection_text.append("None", Style(color="dim", bold=True))
        status_bar.update(selection_text)
        # SelectionChanged is posted by the volume manager

    def _update_image(self, status_bar: Static, item_id: str) -> None:
        """Update footer for image selection."""
        if not self.container_list.selected_image_data:
            return

        image_data = self.container_list.selected_image_data
        selection_text = self._create_selection_header()
        selection_text.append("  Image: ", Style(color="white"))
        # Show first 12 chars of ID
        selection_text.append(
            f"{image_data['id'][:12]}", Style(color="yellow", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        if image_data["tags"]:
            tags_text = ", ".join(image_data["tags"])
            selection_text.append(f"{tags_text}", Style(color="cyan", bold=True))
        else:
            selection_text.append("<none>", Style(color="blue", bold=True))
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Containers: ", Style(color="white"))
        selection_text.append(
            f"{image_data['containers']}", Style(color="green", bold=True)
        )
        status_bar.update(selection_text)
        # SelectionChanged is posted by the image manager

    def _update_network(self, status_bar: Static, item_id: str) -> None:
        """Update footer for network selection."""
        if not self.container_list.selected_network_data:
            return

        network_data = self.container_list.selected_network_data
        selection_text = self._create_selection_header()
        selection_text.append("  Network: ", Style(color="white"))
        selection_text.append(f"{network_data['name']}", Style(color="cyan", bold=True))
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Driver: ", Style(color="white"))
        selection_text.append(
            f"{network_data['driver']}", Style(color="blue", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Scope: ", Style(color="white"))
        selection_text.append(
            f"{network_data['scope']}", Style(color="magenta", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Containers: ", Style(color="white"))
        selection_text.append(
            f"{network_data['total_containers']}",
            Style(color="green", bold=True),
        )
        status_bar.update(selection_text)
        # SelectionChanged is posted by the network manager

    def _update_stack(self, status_bar: Static, item_id: str) -> None:
        """Update footer for stack selection."""
        if not self.container_list.selected_stack_data:
            return

        stack_data = self.container_list.selected_stack_data
        selection_text = self._create_selection_header()
        selection_text.append("  Stack: ", Style(color="white"))
        selection_text.append(f"{stack_data['name']}", Style(color="white", bold=True))
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Running: ", Style(color="white"))
        selection_text.append(
            f"{stack_data['running']}", Style(color="green", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Exited: ", Style(color="white"))
        selection_text.append(
            f"{stack_data['exited']}", Style(color="yellow", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Total: ", Style(color="white"))
        selection_text.append(f"{stack_data['total']}", Style(color="cyan", bold=True))
        status_bar.update(selection_text)
        # SelectionChanged is posted by the stack manager

    def _update_container(self, status_bar: Static, item_id: str) -> None:
        """Update footer for container selection."""
        if not self.container_list.selected_container_data:
            return

        container_data = self.container_list.selected_container_data
        selection_text = self._create_selection_header()
        selection_text.append("  Container: ", Style(color="white"))
        selection_text.append(
            f"{container_data['name']}", Style(color="white", bold=True)
        )
        selection_text.append(" | ", Style(color="white"))
        selection_text.append("Status: ", Style(color="white"))

        # Style status based on value
        status = container_data["status"]
        if "running" in status.lower():
            status_style = Style(color="green", bold=True)
        elif "exited" in status.lower():
            status_style = Style(color="yellow", bold=True)
        else:
            status_style = Style(color="red", bold=True)

        selection_text.append(status, status_style)

        # Add CPU and memory if available
        if "cpu" in container_data and container_data["cpu"]:
            selection_text.append(" | ", Style(color="white"))
            selection_text.append("CPU: ", Style(color="white"))
            selection_text.append(
                f"{container_data['cpu']}", Style(color="cyan", bold=True)
            )

        if "memory" in container_data and container_data["memory"]:
            selection_text.append(" | ", Style(color="white"))
            selection_text.append("Memory: ", Style(color="white"))
            selection_text.append(
                f"{container_data['memory']}", Style(color="magenta", bold=True)
            )

        status_bar.update(selection_text)
        # SelectionChanged is posted by the stack manager

    def _update_invalid_selection(
        self, status_bar: Static, item_type: str, item_id: str
    ) -> None:
        """Update footer for invalid selection."""
        logger.warning(f"Invalid selection: {item_type} - {item_id}")
        invalid_selection_text = Text(
            f"Invalid selection: {item_type} - {item_id}",
            Style(color="red", bold=True),
        )
        status_bar.update(invalid_selection_text)
        # Don't post SelectionChanged for invalid selections

    def _create_selection_header(self) -> Text:
        """Create the selection header text."""
        selection_text = Text()
        selection_text.append("Selection:", Style(color="black", bgcolor="yellow"))
        return selection_text
