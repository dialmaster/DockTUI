"""Header widgets for different Docker resource types."""

import logging
import time
from typing import Optional

from rich.text import Text
from textual.message import Message
from textual.widgets import Static

logger = logging.getLogger("DockTUI.headers")


class SectionHeader(Static):
    """A section header widget for grouping related items (Networks, Stacks, etc.).

    Displays a prominent section title to organize the UI into logical groups.
    Now supports click-to-collapse functionality.
    """

    DEFAULT_CSS = """
    SectionHeader {
        background: $primary;
        color: $text;
        padding: 0 1;
        height: 1;
        margin: 2 0 0 0;
        text-style: bold;
        text-align: center;
    }

    SectionHeader:hover {
        background: $primary-lighten-1;
        color: $text;
    }
    """

    class Clicked(Message):
        """Event emitted when the header is clicked."""

        def __init__(self, section_header: "SectionHeader") -> None:
            self.section_header = section_header
            super().__init__()

    def __init__(self, title: str, collapsed: bool = False):
        """Initialize the section header.

        Args:
            title: The section title to display
            collapsed: Whether the section starts collapsed
        """
        self.base_title = title
        self.collapsed = collapsed
        super().__init__("")
        self._update_content()
        self.can_focus = False  # Section headers are not focusable

    def _update_content(self) -> None:
        """Update the header's displayed content based on current state."""
        icon = "▶" if self.collapsed else "▼"
        content = Text.assemble(Text(f"{icon} {self.base_title} {icon}", style="bold"))
        self.update(content)

    def toggle(self) -> None:
        """Toggle the collapsed/expanded state."""
        self.collapsed = not self.collapsed
        self._update_content()

    def on_click(self) -> None:
        """Handle click events."""
        self.toggle()
        self.post_message(self.Clicked(self))


class NetworkHeader(Static):
    """A header widget for displaying Docker network information.

    Displays network name, driver, scope, and connected container/stack counts with
    collapsible/expandable functionality.
    """

    COMPONENT_CLASSES = {"header": "network-header--header"}

    DEFAULT_CSS = """
    NetworkHeader {
        background: $surface-darken-1;
        padding: 0 0;
        height: 3;
        border-bottom: solid $accent-darken-3;
        margin: 0 0 0 0;
        color: $text;
    }

    NetworkHeader:hover {
        background: $surface-lighten-1;
        color: $accent-lighten-1;
        text-style: bold;
    }

    NetworkHeader:focus {
        background: $surface-lighten-2;
        color: $accent-lighten-2;
        text-style: bold;
    }

    NetworkHeader.selected:blur {
        background: $surface-lighten-1;
        color: $accent;
        text-style: bold;
        opacity: 0.8;
    }

    .network-header--header {
        color: $text;
        text-style: bold;
    }
    """

    class Selected(Message):
        """Event emitted when the header is selected."""

        def __init__(self, network_header: "NetworkHeader") -> None:
            self.network_header = network_header
            super().__init__()

    class Clicked(Message):
        """Event emitted when the header is clicked."""

        def __init__(self, network_header: "NetworkHeader") -> None:
            self.network_header = network_header
            super().__init__()

    def __init__(
        self,
        network_name: str,
        driver: str,
        scope: str,
        subnet: str,
        total_containers: int,
        connected_stacks: set,
    ):
        """Initialize the network header.

        Args:
            network_name: Name of the Docker network
            driver: Network driver (bridge, overlay, host, etc.)
            scope: Network scope (local, swarm)
            subnet: Network subnet/IP range
            total_containers: Total number of connected containers
            connected_stacks: Set of stack names using this network
        """
        super().__init__("")
        self.network_name = network_name
        self.driver = driver
        self.scope = scope
        self.subnet = subnet
        self.total_containers = total_containers
        self.connected_stacks = connected_stacks
        self.expanded = False  # Start collapsed by default
        self.can_focus = True
        self._last_click_time = 0
        self._update_content()

    def _update_content(self) -> None:
        """Update the header's displayed content based on current state."""
        # Only show expand/collapse icon if there are containers
        if self.total_containers > 0:
            icon = "▼" if self.expanded else "▶"
            icon_text = f"{icon} "
        else:
            icon_text = "  "  # Indent for alignment

        # Format connected stacks list
        if self.connected_stacks:
            stacks_text = ", ".join(sorted(self.connected_stacks))
            if len(stacks_text) > 40:
                stacks_text = stacks_text[:37] + "..."
        else:
            stacks_text = "No stacks"

        content = Text.assemble(
            Text(icon_text, style="bold"),
            Text(self.network_name, style="bold cyan"),
            " ",
            Text(f"({self.driver}/{self.scope})", style="dim"),
            " ",
            Text(f"Subnet: {self.subnet}", style="blue"),
            "\n",
            Text(
                f"Containers: {self.total_containers}, Stacks: {stacks_text}",
                style="yellow",
            ),
        )
        self.update(content)

    def on_focus(self) -> None:
        """Called when the header gets focus."""
        self.refresh()
        self.post_message(self.Selected(self))

    def on_blur(self) -> None:
        """Called when the header loses focus."""
        self.refresh()

    def toggle(self) -> None:
        """Toggle the expanded/collapsed state of the network."""
        # Only allow toggle if there are containers to show
        if self.total_containers > 0:
            self.expanded = not self.expanded
            self._update_content()

    def on_click(self) -> None:
        """Handle click events for double-click detection."""
        current_time = time.time()

        self.post_message(self.Clicked(self))

        if current_time - self._last_click_time < 0.5:
            # Check if the search input is currently focused
            # If it is, don't steal focus from it
            if self.screen and self.screen.focused:
                focused_widget = self.screen.focused
                if not (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    # Focus the header only if search input is not focused
                    self.focus()
            else:
                self.focus()

            # Only toggle if there are containers
            if self.screen and self.total_containers > 0:
                container_list = self.screen.query_one("ContainerList")
                container_list.action_toggle_network()

        self._last_click_time = current_time


class VolumeHeader(Static):
    """A header widget for displaying Docker volume information.

    Displays volume name, driver, mount point, and stack association with
    collapsible/expandable functionality.
    """

    COMPONENT_CLASSES = {"header": "volume-header--header"}

    DEFAULT_CSS = """
    VolumeHeader {
        background: $surface-darken-1;
        padding: 0 0;
        height: 3;
        border-bottom: solid $secondary-darken-3;
        margin: 0 0 0 0;
        color: $text;
    }

    VolumeHeader:hover {
        background: $surface-lighten-1;
        color: $secondary-lighten-1;
        text-style: bold;
    }

    VolumeHeader:focus {
        background: $surface-lighten-2;
        color: $secondary-lighten-2;
        text-style: bold;
    }

    VolumeHeader.selected:blur {
        background: $surface-lighten-1;
        color: $secondary;
        text-style: bold;
        opacity: 0.8;
    }

    .volume-header--header {
        color: $text;
        text-style: bold;
    }
    """

    class Selected(Message):
        """Event emitted when the header is selected."""

        def __init__(self, volume_header: "VolumeHeader") -> None:
            self.volume_header = volume_header
            super().__init__()

    class Clicked(Message):
        """Event emitted when the header is clicked."""

        def __init__(self, volume_header: "VolumeHeader") -> None:
            self.volume_header = volume_header
            super().__init__()

    def __init__(
        self,
        volume_name: str,
        driver: str,
        mountpoint: str,
        created: str,
        stack: Optional[str],
        scope: str,
    ):
        """Initialize the volume header.

        Args:
            volume_name: Name of the Docker volume
            driver: Volume driver
            mountpoint: Volume mount point on the host
            created: Creation timestamp
            stack: Associated Docker Compose stack name (if any)
            scope: Volume scope
        """
        super().__init__("")
        self.volume_name = volume_name
        self.driver = driver
        self.mountpoint = mountpoint
        self.created = created
        self.stack = stack
        self.scope = scope
        self.can_focus = True
        self._update_content()

    def _update_content(self) -> None:
        """Update the header's displayed content based on current state."""
        # Format stack association
        stack_text = self.stack if self.stack else "No stack association"
        stack_style = "green" if self.stack else "dim"

        # Truncate mount point if too long
        mount_display = self.mountpoint
        if len(mount_display) > 50:
            mount_display = "..." + mount_display[-47:]

        content = Text.assemble(
            Text("  ", style="bold"),  # Indent for visual alignment
            Text(self.volume_name, style="bold magenta"),
            " ",
            Text(f"({self.driver}/{self.scope})", style="dim"),
            "\n",
            Text("  Stack: ", style="white"),  # Indent for visual alignment
            Text(stack_text, style=stack_style),
            " | ",
            Text(f"Mount: {mount_display}", style="blue dim"),
        )
        self.update(content)

    def on_focus(self) -> None:
        """Called when the header gets focus."""
        self.refresh()
        self.post_message(self.Selected(self))

    def on_blur(self) -> None:
        """Called when the header loses focus."""
        self.refresh()

    def on_click(self) -> None:
        """Handle click events."""
        self.post_message(self.Clicked(self))
        # Focus the header on click
        if self.screen and self.screen.focused:
            focused_widget = self.screen.focused
            if not (
                hasattr(focused_widget, "id") and focused_widget.id == "search-input"
            ):
                self.focus()
        else:
            self.focus()


class StackHeader(Static):
    """A header widget for displaying Docker Compose stack information.

    Displays stack name, configuration file path, and container counts with
    collapsible/expandable functionality.
    """

    COMPONENT_CLASSES = {"header": "stack-header--header"}

    DEFAULT_CSS = """
    StackHeader {
        background: $surface-darken-2;
        padding: 0 0;
        height: 3;
        border-bottom: solid $primary-darken-3;
        margin: 0 0 0 0;
        color: $text;
    }

    StackHeader:hover {
        background: $surface-lighten-1;
        color: $primary-lighten-1;
        text-style: bold;
    }

    StackHeader:focus {
        background: $surface-lighten-2;
        color: $primary-lighten-2;
        text-style: bold;
    }

    StackHeader.selected:blur {
        background: $surface-lighten-1;
        color: $primary;
        text-style: bold;
        opacity: 0.8;
    }

    .stack-header--header {
        color: $text;
        text-style: bold;
    }
    """

    class Selected(Message):
        """Event emitted when the header is selected."""

        def __init__(self, stack_header: "StackHeader") -> None:
            self.stack_header = stack_header
            super().__init__()

    class Clicked(Message):
        """Event emitted when the header is clicked."""

        def __init__(self, stack_header: "StackHeader") -> None:
            self.stack_header = stack_header
            super().__init__()

    def __init__(
        self,
        stack_name: str,
        config_file: str,
        running: int,
        exited: int,
        total: int,
        can_recreate: bool = True,
        has_compose_file: bool = True,
    ):
        """Initialize the stack header.

        Args:
            stack_name: Name of the Docker Compose stack
            config_file: Path to the compose configuration file
            running: Number of running containers
            exited: Number of exited containers
            total: Total number of containers
            can_recreate: Whether the stack can be recreated (compose file accessible)
            has_compose_file: Whether a compose file path is defined
        """
        super().__init__("")
        self.stack_name = stack_name
        self.expanded = True
        self.running = running
        self.exited = exited
        self.total = total
        self.config_file = config_file
        self.can_recreate = can_recreate
        self.has_compose_file = has_compose_file
        self.can_focus = True
        self._last_click_time = 0
        self._update_content()

    def _update_content(self) -> None:
        """Update the header's displayed content based on current state."""
        icon = "▼" if self.expanded else "▶"
        running_text = Text(f"Running: {self.running}", style="green")
        exited_text = Text(f"Exited: {self.exited}", style="yellow")
        status = Text.assemble(
            running_text, ", ", exited_text, f", Total: {self.total}"
        )

        # Add indicator if recreate is not available
        recreate_indicator = ""
        if not self.can_recreate:
            recreate_indicator = Text(" [compose file not accessible]", style="red dim")

        content = Text.assemble(
            Text(f"{icon} ", style="bold"),
            Text(self.stack_name, style="bold"),
            " ",
            Text(f"({self.config_file})", style="dim"),
            recreate_indicator,
            "\n",
            status,
        )
        self.update(content)

    def on_focus(self) -> None:
        """Called when the header gets focus."""
        self.refresh()
        # Emit a selected event when focused
        self.post_message(self.Selected(self))

    def on_blur(self) -> None:
        """Called when the header loses focus."""
        self.refresh()

    def toggle(self) -> None:
        """Toggle the expanded/collapsed state of the stack."""
        self.expanded = not self.expanded
        self._update_content()

    def on_click(self) -> None:
        """Handle click events for double-click detection."""
        current_time = time.time()

        # Emit a clicked event
        self.post_message(self.Clicked(self))

        if current_time - self._last_click_time < 0.5:
            # Check if the search input is currently focused
            # If it is, don't steal focus from it
            if self.screen and self.screen.focused:
                focused_widget = self.screen.focused
                if not (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    # Focus the header only if search input is not focused
                    self.focus()
            else:
                self.focus()

            if self.screen:
                container_list = self.screen.query_one("ContainerList")
                container_list.action_toggle_stack()

        self._last_click_time = current_time


class ImageHeader(Static):
    """A header widget for displaying Docker image information.

    Displays image ID, tags, creation date, size, and container count.
    """

    COMPONENT_CLASSES = {"header": "image-header--header"}

    DEFAULT_CSS = """
    ImageHeader {
        background: $surface-darken-1;
        padding: 0 0;
        height: 3;
        border-bottom: solid $warning-darken-3;
        margin: 0 0 0 0;
        color: $text;
    }

    ImageHeader:hover {
        background: $surface-lighten-1;
        color: $warning-lighten-1;
        text-style: bold;
    }

    ImageHeader:focus {
        background: $surface-lighten-2;
        color: $warning-lighten-2;
        text-style: bold;
    }

    .image-header--header {
        color: $text;
        text-style: bold;
    }
    """

    class Selected(Message):
        """Event emitted when the header is selected."""

        def __init__(self, image_header: "ImageHeader") -> None:
            self.image_header = image_header
            super().__init__()

    class Clicked(Message):
        """Event emitted when the header is clicked."""

        def __init__(self, image_header: "ImageHeader") -> None:
            self.image_header = image_header
            super().__init__()

    def __init__(
        self,
        image_id: str,
        tags: list,
        created: str,
        size: str,
        containers: int,
        architecture: str,
        os: str,
    ):
        """Initialize the image header.

        Args:
            image_id: Docker image ID (short form)
            tags: List of tags for this image
            created: Creation timestamp
            size: Image size (human-readable)
            containers: Number of containers using this image
            architecture: Image architecture (e.g., amd64)
            os: Operating system (e.g., linux)
        """
        super().__init__("")
        self.image_id = image_id
        self.tags = tags
        self.created = created
        self.image_size = size
        self.containers = containers
        self.architecture = architecture
        self.os = os
        self.can_focus = True
        self._update_content()

    def _update_content(self) -> None:
        """Update the header's displayed content based on current state."""
        # Format tags display
        if self.tags:
            # Join tags and truncate if too long
            tags_text = ", ".join(self.tags)
            if len(tags_text) > 50:
                tags_text = tags_text[:47] + "..."
        else:
            tags_text = "<none>"

        # Format container count
        container_text = (
            f"{self.containers} container{'s' if self.containers != 1 else ''}"
        )
        container_style = "green" if self.containers > 0 else "dim"

        content = Text.assemble(
            Text("  ", style="bold"),  # Indent for visual alignment
            Text(self.image_id[:12], style="bold yellow"),  # Show first 12 chars of ID
            " ",
            Text(tags_text, style="cyan"),
            "\n",
            Text("  ", style="white"),  # Indent for visual alignment
            Text(f"Size: {self.image_size}", style="blue"),
            " | ",
            Text(container_text, style=container_style),
            " | ",
            Text(f"{self.os}/{self.architecture}", style="dim"),
        )
        self.update(content)

    def on_focus(self) -> None:
        """Called when the header gets focus."""
        self.refresh()
        self.post_message(self.Selected(self))

    def on_blur(self) -> None:
        """Called when the header loses focus."""
        self.refresh()

    def on_click(self) -> None:
        """Handle click events."""
        self.post_message(self.Clicked(self))
        # Focus the header on click
        if self.screen and self.screen.focused:
            focused_widget = self.screen.focused
            if not (
                hasattr(focused_widget, "id") and focused_widget.id == "search-input"
            ):
                self.focus()
        else:
            self.focus()
