"""Network-specific functionality for the container list widget."""

import logging
from typing import Dict, Optional

from textual.containers import Container
from textual.widgets import DataTable

from .headers import NetworkHeader

logger = logging.getLogger("dockerview.network_manager")


class NetworkManager:
    """Manages network-related UI components and operations."""

    def __init__(self, parent):
        """Initialize the network manager.

        Args:
            parent: The parent ContainerList widget
        """
        self.parent = parent
        self.network_tables: Dict[str, DataTable] = {}
        self.network_headers: Dict[str, NetworkHeader] = {}
        self.network_rows: Dict[str, tuple] = {}
        self.expanded_networks = set()
        self._networks_in_new_data = set()
        self.selected_network_data: Optional[Dict] = None

    def add_network(self, network_data: dict) -> None:
        """Add or update a network section in the container list.

        Args:
            network_data: Dictionary containing network information
        """
        network_name = network_data["name"]

        # Track that this network exists in the new data
        self._networks_in_new_data.add(network_name)

        if network_name not in self.network_tables:
            header = NetworkHeader(
                network_name,
                network_data["driver"],
                network_data["scope"],
                network_data["subnet"],
                network_data["total_containers"],
                network_data["connected_stacks"],
            )
            table = self.parent.create_network_table(network_name)

            self.network_headers[network_name] = header
            self.network_tables[network_name] = table

            if network_name in self.expanded_networks:
                header.expanded = True
                table.styles.display = "block"

            # Update selected network data if this is the selected network
            if (
                self.parent.selected_item
                and self.parent.selected_item[0] == "network"
                and self.parent.selected_item[1] == network_name
            ):
                self.selected_network_data = network_data
        else:
            header = self.network_headers[network_name]
            was_expanded = header.expanded
            header.driver = network_data["driver"]
            header.scope = network_data["scope"]
            header.subnet = network_data["subnet"]
            header.total_containers = network_data["total_containers"]
            header.connected_stacks = network_data["connected_stacks"]
            header.expanded = was_expanded
            self.network_tables[network_name].styles.display = (
                "block" if was_expanded else "none"
            )
            header._update_content()

            # Update selected network data if this is the selected network
            if (
                self.parent.selected_item
                and self.parent.selected_item[0] == "network"
                and self.parent.selected_item[1] == network_name
            ):
                self.selected_network_data = network_data

    def add_container_to_network(self, network_name: str, container_data: dict) -> None:
        """Add or update a container in its network's table.

        Args:
            network_name: Name of the network the container is connected to
            container_data: Dictionary containing container information
        """
        if network_name not in self.network_tables:
            logger.warning(
                f"Network {network_name} not found when trying to add container"
            )
            return

        table = self.network_tables[network_name]
        container_id = container_data["id"]

        row_data = (
            container_data["id"],
            container_data["name"],
            container_data["stack"],
            container_data["ip"],
        )

        try:
            # Add as a new row
            row_key = table.row_count
            table.add_row(*row_data)
            self.network_rows[f"{network_name}:{container_id}"] = (
                network_name,
                row_key,
            )
        except Exception as e:
            logger.error(
                f"Error adding container {container_id} to network {network_name}: {str(e)}",
                exc_info=True,
            )

    def remove_network(self, network_name: str) -> None:
        """Remove a network and its associated UI elements.

        Args:
            network_name: Name of the network to remove
        """
        self.expanded_networks.discard(network_name)

        if self.parent.networks_container:
            for child in list(self.parent.networks_container.children):
                if (
                    isinstance(child, Container)
                    and "network-container" in child.classes
                ):
                    for widget in child.children:
                        if (
                            isinstance(widget, NetworkHeader)
                            and widget.network_name == network_name
                        ):
                            child.remove()
                            break

        if network_name in self.network_headers:
            del self.network_headers[network_name]
        if network_name in self.network_tables:
            del self.network_tables[network_name]

        if (
            self.parent.selected_item
            and self.parent.selected_item[0] == "network"
            and self.parent.selected_item[1] == network_name
        ):
            self.parent.selected_item = None
            self.selected_network_data = None

    def select_network(self, network_name: str) -> None:
        """Select a network and update the footer.

        Args:
            network_name: Name of the network to select
        """
        if network_name in self.network_headers:
            # Clear any previous selection
            self.parent.selected_item = ("network", network_name)
            self.parent.selected_container_data = None
            self.parent.selected_stack_data = None
            self.parent.selected_volume_data = None

            # Store network data for footer display
            header = self.network_headers[network_name]
            self.selected_network_data = {
                "name": network_name,
                "driver": header.driver,
                "scope": header.scope,
                "subnet": header.subnet,
                "total_containers": header.total_containers,
                "connected_stacks": header.connected_stacks,
            }
            self.parent.selected_network_data = self.selected_network_data

            # Update the footer and cursor visibility
            self.parent._update_footer_with_selection()
            self.parent._update_cursor_visibility()

            # Import here to avoid circular import
            from .container_list_base import SelectionChanged

            # Post selection change message
            self.parent.post_message(
                SelectionChanged("network", network_name, self.selected_network_data)
            )

    def clear_tables(self) -> None:
        """Clear all network tables."""
        for table in self.network_tables.values():
            table.clear()
        self.network_rows.clear()

    def reset_tracking(self) -> None:
        """Reset tracking for new data updates."""
        self._networks_in_new_data = set()

    def save_expanded_state(self) -> None:
        """Save the current expanded state of networks."""
        self.expanded_networks = {
            name for name, header in self.network_headers.items() if header.expanded
        }

    def cleanup_removed_networks(self) -> None:
        """Remove networks that no longer exist."""
        networks_to_remove = []
        for network_name in list(self.network_headers.keys()):
            if network_name not in self._networks_in_new_data:
                networks_to_remove.append(network_name)

        for network_name in networks_to_remove:
            self.remove_network(network_name)

    def get_existing_containers(self) -> dict:
        """Get existing network containers for updates."""
        existing_network_containers = {}
        if self.parent.networks_container:
            for child in self.parent.networks_container.children:
                if (
                    isinstance(child, Container)
                    and "network-container" in child.classes
                ):
                    for widget in child.children:
                        if isinstance(widget, NetworkHeader):
                            existing_network_containers[widget.network_name] = child
                            break
        return existing_network_containers

    def prepare_new_containers(self) -> dict:
        """Prepare new network containers to be added."""
        new_network_containers = {}
        existing_containers = self.get_existing_containers()

        for network_name in sorted(self.network_headers.keys()):
            if network_name not in existing_containers:
                header = self.network_headers[network_name]
                table = self.network_tables[network_name]
                network_container = Container(classes="network-container")
                new_network_containers[network_name] = (
                    network_container,
                    header,
                    table,
                )
        return new_network_containers
