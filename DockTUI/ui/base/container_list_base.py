"""Base container list widget with core functionality."""

import logging
from typing import Dict, List, Optional, Set, Tuple

from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable

from ..widgets.headers import NetworkHeader, SectionHeader, StackHeader, VolumeHeader

logger = logging.getLogger("DockTUI.container_list")


class SelectionChanged(Message):
    """Message sent when the selection changes in the container list."""

    def __init__(self, item_type: str, item_id: str, item_data: dict):
        self.item_type = item_type
        self.item_id = item_id
        self.item_data = item_data
        super().__init__()


class DockerOperationCompleted(Message):
    """Message sent when a Docker operation completes."""

    def __init__(
        self,
        operation: str,
        success: bool,
        message: str,
        item_id: Optional[str] = None,
        item_ids: Optional[List[str]] = None,
    ):
        self.operation = operation
        self.success = success
        self.message = message
        self.item_id = item_id  # Single item for backward compatibility
        self.item_ids = item_ids or ([item_id] if item_id else [])  # List of items
        super().__init__()


class ContainerListBase(VerticalScroll):
    """Base class for container list widget with shared functionality."""

    DEFAULT_CSS = """
    ContainerListBase {
        background: transparent;
        height: auto;
        border: none;
        padding: 0;
    }

    .initial-loading-message {
        background: transparent;
        color: $text-muted;
        text-style: italic;
    }

    StackHeader {
        layout: horizontal;
        width: 100%;
        height: 3;
    }

    .images-group {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0 0 2 0;
        background: transparent;
    }

    .volumes-group {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0 0 2 0;
        background: transparent;
    }

    .stacks-group {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0 0 2 0;
        background: transparent;
    }

    .networks-group {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0;
        background: transparent;
    }

    .volume-container {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0 0 0 0;
        background: transparent;
        border: none;
    }

    .volume-container VolumeHeader {
        background: $surface;
        border: solid $secondary-darken-3;
        margin: 0 0 1 0;
        padding: 0 1;
    }

    .network-container {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        background: $surface;
        border: solid $accent-darken-3;
    }

    .stack-container {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        background: $surface;
        border: solid $primary-darken-3;
    }

    .stack-container:first-of-type {
        margin-bottom: 1;
    }

    .stack-container StackHeader {
        background: $surface-darken-2;
        border-bottom: solid $primary-darken-3;
    }

    DataTable {
        margin: 0;
        padding: 0 1;
        border: none;
        display: none;
        background: transparent;
    }

    .stack-container DataTable {
        border: none;
        background: $surface;
    }

    .images-group DataTable {
        display: block;
        height: auto;
        max-height: 100%;
    }

    /* Force cursor to be invisible when table is not focused */
    DataTable > .datatable--cursor {
        background: transparent !important;
        color: $text !important;
        text-style: none !important;
    }

    /* Show cursor only when table is focused */
    DataTable:focus > .datatable--cursor {
        background: $primary !important;
        color: $text !important;
    }

    /* Style for row hover */
    DataTable > .datatable--row:hover {
        background: $primary-darken-2;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "toggle_item", "Expand/Collapse", show=True),
        Binding("space", "toggle_item", "Expand/Collapse", show=False),
    ]

    def __init__(self):
        """Initialize the container list widget."""
        super().__init__()

        # Volume components
        self.volume_headers: Dict[str, VolumeHeader] = {}
        self.expanded_volumes: Set[str] = set()

        # Network components
        self.network_tables: Dict[str, DataTable] = {}
        self.network_headers: Dict[str, NetworkHeader] = {}
        self.network_rows: Dict[str, Tuple[str, int]] = {}
        self.expanded_networks: Set[str] = set()

        # Stack components
        self.stack_tables: Dict[str, DataTable] = {}
        self.stack_headers: Dict[str, StackHeader] = {}
        self.container_rows: Dict[str, Tuple[str, int]] = {}
        self.expanded_stacks: Set[str] = set()

        # Section headers and containers
        self.images_section_header: Optional[SectionHeader] = None
        self.volumes_section_header: Optional[SectionHeader] = None
        self.networks_section_header: Optional[SectionHeader] = None
        self.stacks_section_header: Optional[SectionHeader] = None
        self.images_container: Optional[Container] = None
        self.volumes_container: Optional[Container] = None
        self.networks_container: Optional[Container] = None
        self.stacks_container: Optional[Container] = None

        # General state
        self.current_focus: Optional[str] = None
        self._is_updating = False
        self._pending_clear = False

        # Selection tracking
        self.selected_item: Optional[Tuple[str, str]] = None
        self.selected_container_data: Optional[Dict] = None
        self.selected_stack_data: Optional[Dict] = None
        self.selected_network_data: Optional[Dict] = None
        self.selected_volume_data: Optional[Dict] = None
        self.selected_image_data: Optional[Dict] = None

        # Track which items exist in current update cycle
        self._volumes_in_new_data: Set[str] = set()
        self._stacks_in_new_data: Set[str] = set()
        self._networks_in_new_data: Set[str] = set()

        # Track section collapse states
        self.stacks_section_collapsed = False  # Stacks start expanded
        self.images_section_collapsed = True  # Images start collapsed
        self.volumes_section_collapsed = True  # Volumes start collapsed
        self.networks_section_collapsed = True  # Networks start collapsed

    def _ensure_section_headers(self) -> None:
        """Ensure section headers and containers exist."""
        if self.stacks_section_header is None:
            self.stacks_section_header = SectionHeader(
                "📦 DOCKER COMPOSE STACKS", collapsed=self.stacks_section_collapsed
            )
            self.stacks_section_header.styles.margin = (0, 0, 0, 0)

        if self.images_section_header is None:
            self.images_section_header = SectionHeader(
                "📷 DOCKER IMAGES", collapsed=self.images_section_collapsed
            )

        if self.volumes_section_header is None:
            self.volumes_section_header = SectionHeader(
                "💾 DOCKER VOLUMES", collapsed=self.volumes_section_collapsed
            )

        if self.networks_section_header is None:
            self.networks_section_header = SectionHeader(
                "🌐 DOCKER NETWORKS", collapsed=self.networks_section_collapsed
            )

        if self.stacks_container is None:
            self.stacks_container = Container(classes="stacks-group")

        if self.images_container is None:
            self.images_container = Container(classes="images-group")
            self.images_container.show_vertical_scrollbar = False

        if self.volumes_container is None:
            self.volumes_container = Container(classes="volumes-group")

        if self.networks_container is None:
            self.networks_container = Container(classes="networks-group")

    def create_network_table(self, network_name: str) -> DataTable:
        """Create a new DataTable for displaying network container information.

        Args:
            network_name: Name of the network this table will display

        Returns:
            DataTable: A configured table for displaying network container information
        """
        table = DataTable()
        table.add_columns("Container ID", "Container Name", "Stack", "IP Address")

        # Configure cursor behavior
        table.cursor_type = "row"
        table.display = False  # Start collapsed
        table.can_focus = True
        table.show_cursor = True
        table.watch_cursor = True

        return table

    def create_stack_table(self, stack_name: str) -> DataTable:
        """Create a new DataTable for displaying container information.

        Args:
            stack_name: Name of the stack this table will display

        Returns:
            DataTable: A configured table for displaying container information
        """
        table = DataTable()
        table.add_columns(
            "ID", "Name", "Status", "Uptime", "CPU %", "Memory", "PIDs", "Ports"
        )

        # Configure cursor behavior
        table.cursor_type = "row"
        table.display = False  # Start collapsed
        table.can_focus = True
        table.show_cursor = True
        table.watch_cursor = True

        return table

    def begin_update(self) -> None:
        """Begin a batch update to prevent UI flickering during data updates."""
        self._is_updating = True
        self._pending_clear = len(self.children) == 0

        # Clear all tables to ensure fresh data
        for table in self.network_tables.values():
            table.clear()
        for table in self.stack_tables.values():
            table.clear()

        # Clear the tracking dictionaries
        self.container_rows.clear()
        self.network_rows.clear()

        # Track which items should exist after this update
        self._volumes_in_new_data = set()
        self._networks_in_new_data = set()
        self._stacks_in_new_data = set()

        # Ensure section headers are created
        self._ensure_section_headers()

    def action_toggle_item(self) -> None:
        """Toggle the visibility of the selected item."""
        # Check if a network header has focus
        for network_name, header in self.network_headers.items():
            if header.has_focus:
                table = self.network_tables[network_name]
                header.toggle()
                table.styles.display = "block" if header.expanded else "none"
                return

        # Check if a stack header has focus
        for stack_name, header in self.stack_headers.items():
            if header.has_focus:
                table = self.stack_tables[stack_name]
                header.toggle()
                table.styles.display = "block" if header.expanded else "none"
                return

    def action_toggle_network(self) -> None:
        """Toggle the visibility of the selected network's container table."""
        for network_name, header in self.network_headers.items():
            if header.has_focus:
                table = self.network_tables[network_name]
                header.toggle()
                table.styles.display = "block" if header.expanded else "none"
                break

    def action_toggle_stack(self) -> None:
        """Toggle the visibility of the selected stack's container table."""
        for stack_name, header in self.stack_headers.items():
            if header.has_focus:
                table = self.stack_tables[stack_name]
                header.toggle()
                table.styles.display = "block" if header.expanded else "none"
                break
