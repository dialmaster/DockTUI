"""Main container list widget implementation."""

import logging
from typing import Dict, Optional

from rich.style import Style
from rich.text import Text
from textual.containers import Container
from textual.widgets import DataTable

from .container_list_base import ContainerListBase, SelectionChanged
from .headers import NetworkHeader, StackHeader, VolumeHeader

logger = logging.getLogger("dockerview.containers")


class ContainerList(ContainerListBase):
    """A scrollable widget that displays Docker containers grouped by their stacks.

    Provides collapsible stack sections with container details including resource usage
    and status information. Supports keyboard navigation and interaction.
    """

    def end_update(self) -> None:
        """End a batch update and apply pending changes to the UI."""
        try:
            # First, clean up items that no longer exist in the Docker data
            self._cleanup_removed_items()

            # Then, determine what needs to be added or updated
            self._prepare_new_containers()

            # Apply changes to the UI
            if self._pending_clear:
                self._mount_all_sections()
            else:
                self._update_existing_sections()

            # Restore selection and focus
            self._restore_selection()

            # Update cursor visibility based on the restored selection
            self._update_cursor_visibility()

            self._is_updating = False
        finally:
            if len(self.children) > 0:
                self.refresh()
            self._is_updating = False

    def _cleanup_removed_items(self) -> None:
        """Remove volumes, networks, and stacks that no longer exist."""
        # Volumes cleanup
        volumes_to_remove = []
        for volume_name in list(self.volume_headers.keys()):
            if volume_name not in self._volumes_in_new_data:
                volumes_to_remove.append(volume_name)

        # Networks cleanup
        networks_to_remove = []
        for network_name in list(self.network_headers.keys()):
            if network_name not in self._networks_in_new_data:
                networks_to_remove.append(network_name)

        # Stacks cleanup
        stacks_to_remove = []
        for stack_name in list(self.stack_headers.keys()):
            if stack_name not in self._stacks_in_new_data:
                stacks_to_remove.append(stack_name)

        # Remove obsolete volumes
        for volume_name in volumes_to_remove:
            self._remove_volume(volume_name)

        # Remove obsolete networks
        for network_name in networks_to_remove:
            self._remove_network(network_name)

        # Remove obsolete stacks
        for stack_name in stacks_to_remove:
            self._remove_stack(stack_name)

    def _remove_volume(self, volume_name: str) -> None:
        """Remove a volume and its associated UI elements."""
        self.expanded_volumes.discard(volume_name)

        if self.volumes_container:
            for child in list(self.volumes_container.children):
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
            self.selected_item
            and self.selected_item[0] == "volume"
            and self.selected_item[1] == volume_name
        ):
            self.selected_item = None
            self.selected_volume_data = None

    def _remove_network(self, network_name: str) -> None:
        """Remove a network and its associated UI elements."""
        self.expanded_networks.discard(network_name)

        if self.networks_container:
            for child in list(self.networks_container.children):
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
            self.selected_item
            and self.selected_item[0] == "network"
            and self.selected_item[1] == network_name
        ):
            self.selected_item = None
            self.selected_network_data = None

    def _remove_stack(self, stack_name: str) -> None:
        """Remove a stack and its associated UI elements."""
        self.expanded_stacks.discard(stack_name)

        # Remove UI widgets
        if self.stacks_container:
            for child in list(self.stacks_container.children):
                if isinstance(child, Container) and "stack-container" in child.classes:
                    for widget in child.children:
                        if (
                            isinstance(widget, StackHeader)
                            and widget.stack_name == stack_name
                        ):
                            child.remove()
                            break

        # Remove from tracking dictionaries
        if stack_name in self.stack_headers:
            del self.stack_headers[stack_name]
        if stack_name in self.stack_tables:
            del self.stack_tables[stack_name]

        # Remove container rows that belonged to this stack
        containers_to_remove = [
            cid
            for cid, (cstack, _) in self.container_rows.items()
            if cstack == stack_name
        ]
        for cid in containers_to_remove:
            del self.container_rows[cid]

        # Clear selection if needed
        if (
            self.selected_item
            and self.selected_item[0] == "stack"
            and self.selected_item[1] == stack_name
        ):
            self.selected_item = None
            self.selected_stack_data = None
        elif (
            self.selected_item
            and self.selected_item[0] == "container"
            and self.selected_item[1] in containers_to_remove
        ):
            self.selected_item = None
            self.selected_container_data = None

    def _prepare_new_containers(self) -> None:
        """Prepare containers that need to be added to the UI."""
        self.new_volume_containers = {}
        self.new_network_containers = {}
        self.new_stack_containers = {}

        # Find existing containers
        self.existing_volume_containers = {}
        self.existing_network_containers = {}
        self.existing_stack_containers = {}

        if not self._pending_clear:
            # Find existing volumes
            if self.volumes_container:
                for child in self.volumes_container.children:
                    if (
                        isinstance(child, Container)
                        and "volume-container" in child.classes
                    ):
                        for widget in child.children:
                            if isinstance(widget, VolumeHeader):
                                self.existing_volume_containers[widget.volume_name] = (
                                    child
                                )
                                break

            # Find existing networks
            if self.networks_container:
                for child in self.networks_container.children:
                    if (
                        isinstance(child, Container)
                        and "network-container" in child.classes
                    ):
                        for widget in child.children:
                            if isinstance(widget, NetworkHeader):
                                self.existing_network_containers[
                                    widget.network_name
                                ] = child
                                break

            # Find existing stacks
            if self.stacks_container:
                for child in self.stacks_container.children:
                    if (
                        isinstance(child, Container)
                        and "stack-container" in child.classes
                    ):
                        for widget in child.children:
                            if isinstance(widget, StackHeader):
                                self.existing_stack_containers[widget.stack_name] = (
                                    child
                                )
                                break

        # Prepare new volumes
        for volume_name in sorted(self.volume_headers.keys()):
            if volume_name not in self.existing_volume_containers:
                header = self.volume_headers[volume_name]
                volume_container = Container(classes="volume-container")
                self.new_volume_containers[volume_name] = (
                    volume_container,
                    header,
                    None,  # No table for volumes
                )

        # Prepare new networks
        for network_name in sorted(self.network_headers.keys()):
            if network_name not in self.existing_network_containers:
                header = self.network_headers[network_name]
                table = self.network_tables[network_name]
                network_container = Container(classes="network-container")
                self.new_network_containers[network_name] = (
                    network_container,
                    header,
                    table,
                )

        # Prepare new stacks
        for stack_name in sorted(self.stack_headers.keys()):
            if stack_name not in self.existing_stack_containers:
                header = self.stack_headers[stack_name]
                table = self.stack_tables[stack_name]
                stack_container = Container(classes="stack-container")
                self.new_stack_containers[stack_name] = (stack_container, header, table)

    def _mount_all_sections(self) -> None:
        """Mount all sections when starting fresh."""
        self.remove_children()
        self._pending_clear = False

        # Ensure section headers and containers exist
        self._ensure_section_headers()

        # Mount stacks section
        if self.new_stack_containers or self.stack_headers:
            self.mount(self.stacks_section_header)
            self.mount(self.stacks_container)
            # Set container visibility based on section collapsed state
            self.stacks_container.styles.display = (
                "none" if self.stacks_section_collapsed else "block"
            )
            for stack_name, (
                stack_container,
                header,
                table,
            ) in self.new_stack_containers.items():
                self.stacks_container.mount(stack_container)
                stack_container.mount(header)
                stack_container.mount(table)
                table.styles.display = "block" if header.expanded else "none"

        # Mount volumes section
        if self.new_volume_containers or self.volume_headers:
            self.mount(self.volumes_section_header)
            self.mount(self.volumes_container)
            # Set container visibility based on section collapsed state
            self.volumes_container.styles.display = (
                "none" if self.volumes_section_collapsed else "block"
            )
            for volume_name, (
                volume_container,
                header,
                table,
            ) in self.new_volume_containers.items():
                self.volumes_container.mount(volume_container)
                volume_container.mount(header)
                # No table to mount for volumes

        # Mount networks section
        if self.new_network_containers or self.network_headers:
            self.mount(self.networks_section_header)
            self.mount(self.networks_container)
            # Set container visibility based on section collapsed state
            self.networks_container.styles.display = (
                "none" if self.networks_section_collapsed else "block"
            )
            for network_name, (
                network_container,
                header,
                table,
            ) in self.new_network_containers.items():
                self.networks_container.mount(network_container)
                network_container.mount(header)
                network_container.mount(table)
                table.styles.display = "block" if header.expanded else "none"

    def _update_existing_sections(self) -> None:
        """Update existing sections and add new items."""
        # Update existing volumes
        for volume_name, container in self.existing_volume_containers.items():
            if volume_name in self.volume_headers:
                for widget in container.children:
                    if isinstance(widget, VolumeHeader):
                        widget._update_content()
            else:
                container.remove()

        # Update existing networks
        for network_name, container in self.existing_network_containers.items():
            if network_name in self.network_headers:
                header = self.network_headers[network_name]
                table = self.network_tables[network_name]
                for widget in container.children:
                    if isinstance(widget, NetworkHeader):
                        widget._update_content()
                    elif isinstance(widget, DataTable):
                        widget.styles.display = "block" if header.expanded else "none"
            else:
                container.remove()

        # Update existing stacks
        for stack_name, container in self.existing_stack_containers.items():
            if stack_name in self.stack_headers:
                header = self.stack_headers[stack_name]
                table = self.stack_tables[stack_name]
                for widget in container.children:
                    if isinstance(widget, StackHeader):
                        widget._update_content()
                    elif isinstance(widget, DataTable):
                        widget.styles.display = "block" if header.expanded else "none"
            else:
                container.remove()

        # Ensure section headers and containers exist
        self._ensure_section_headers()

        # Check what sections need to be mounted
        volumes_header_exists = self.volumes_section_header in self.children
        networks_header_exists = self.networks_section_header in self.children
        stacks_header_exists = self.stacks_section_header in self.children
        volumes_container_exists = self.volumes_container in self.children
        networks_container_exists = self.networks_container in self.children
        stacks_container_exists = self.stacks_container in self.children

        # Mount stacks section if needed
        if self.new_stack_containers or self.stack_headers:
            if not stacks_header_exists:
                self.mount(self.stacks_section_header, after=0)
            if not stacks_container_exists:
                self.mount(self.stacks_container, after=self.stacks_section_header)

            # Update container visibility based on section collapsed state
            if self.stacks_container:
                self.stacks_container.styles.display = (
                    "none" if self.stacks_section_collapsed else "block"
                )

            for stack_name, (
                stack_container,
                header,
                table,
            ) in self.new_stack_containers.items():
                self.stacks_container.mount(stack_container)
                stack_container.mount(header)
                stack_container.mount(table)
                table.styles.display = "block" if header.expanded else "none"

        # Mount volumes section if needed
        if self.new_volume_containers or self.volume_headers:
            if not volumes_header_exists:
                insert_after = (
                    self.stacks_container
                    if stacks_container_exists
                    else self.stacks_section_header if stacks_header_exists else 0
                )
                self.mount(self.volumes_section_header, after=insert_after)
            if not volumes_container_exists:
                self.mount(self.volumes_container, after=self.volumes_section_header)

            # Update container visibility based on section collapsed state
            if self.volumes_container:
                self.volumes_container.styles.display = (
                    "none" if self.volumes_section_collapsed else "block"
                )

            for volume_name, (
                volume_container,
                header,
                table,
            ) in self.new_volume_containers.items():
                self.volumes_container.mount(volume_container)
                volume_container.mount(header)
                # No table to mount for volumes

        # Mount networks section if needed
        if self.new_network_containers or self.network_headers:
            if not networks_header_exists:
                # Recalculate existence after volumes might have been mounted
                volumes_container_exists = self.volumes_container in self.children
                volumes_header_exists = self.volumes_section_header in self.children

                insert_after = (
                    self.volumes_container
                    if volumes_container_exists
                    else (
                        self.volumes_section_header
                        if volumes_header_exists
                        else (
                            self.stacks_container
                            if stacks_container_exists
                            else (
                                self.stacks_section_header
                                if stacks_header_exists
                                else 0
                            )
                        )
                    )
                )
                self.mount(self.networks_section_header, after=insert_after)
            if not networks_container_exists:
                self.mount(self.networks_container, after=self.networks_section_header)

            # Update container visibility based on section collapsed state
            if self.networks_container:
                self.networks_container.styles.display = (
                    "none" if self.networks_section_collapsed else "block"
                )

            for network_name, (
                network_container,
                header,
                table,
            ) in self.new_network_containers.items():
                self.networks_container.mount(network_container)
                network_container.mount(header)
                network_container.mount(table)
                table.styles.display = "block" if header.expanded else "none"

    def clear(self) -> None:
        """Clear all stacks and containers while preserving expansion states."""
        # Save expanded states before clearing
        self.expanded_volumes = {
            name for name, header in self.volume_headers.items() if header.expanded
        }
        self.expanded_stacks = {
            name for name, header in self.stack_headers.items() if header.expanded
        }
        self.expanded_networks = {
            name for name, header in self.network_headers.items() if header.expanded
        }

        # Save focused widget if any
        focused = self.screen.focused if self.screen else None
        if focused in self.volume_headers.values():
            self.current_focus = next(
                name
                for name, header in self.volume_headers.items()
                if header == focused
            )
        elif focused in self.stack_headers.values():
            self.current_focus = next(
                name for name, header in self.stack_headers.items() if header == focused
            )
        elif focused in self.stack_tables.values():
            self.current_focus = next(
                name for name, table in self.stack_tables.items() if table == focused
            )
        elif focused in self.network_headers.values():
            self.current_focus = next(
                name
                for name, header in self.network_headers.items()
                if header == focused
            )
        elif focused in self.network_tables.values():
            self.current_focus = next(
                name for name, table in self.network_tables.items() if table == focused
            )

        # Clear all widgets
        self.volume_headers.clear()
        self.stack_tables.clear()
        self.stack_headers.clear()
        self.network_tables.clear()
        self.network_headers.clear()
        self.container_rows.clear()
        self.network_rows.clear()
        self.remove_children()

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
                self.selected_item
                and self.selected_item[0] == "volume"
                and self.selected_item[1] == volume_name
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
                self.selected_item
                and self.selected_item[0] == "volume"
                and self.selected_item[1] == volume_name
            ):
                self.selected_volume_data = volume_data

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
            table = self.create_network_table(network_name)

            self.network_headers[network_name] = header
            self.network_tables[network_name] = table

            if network_name in self.expanded_networks:
                header.expanded = True
                table.styles.display = "block"

            # Update selected network data if this is the selected network
            if (
                self.selected_item
                and self.selected_item[0] == "network"
                and self.selected_item[1] == network_name
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
                self.selected_item
                and self.selected_item[0] == "network"
                and self.selected_item[1] == network_name
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

    def add_stack(
        self,
        name: str,
        config_file: str,
        running: int,
        exited: int,
        total: int,
        can_recreate: bool = True,
        has_compose_file: bool = True,
    ) -> None:
        """Add or update a stack section in the container list.

        Args:
            name: Name of the stack
            config_file: Path to the compose configuration file
            running: Number of running containers
            exited: Number of exited containers
            total: Total number of containers
            can_recreate: Whether the stack can be recreated (compose file accessible)
            has_compose_file: Whether a compose file path is defined
        """
        # Track that this stack exists in the new data
        self._stacks_in_new_data.add(name)

        if name not in self.stack_tables:
            header = StackHeader(
                name,
                config_file,
                running,
                exited,
                total,
                can_recreate,
                has_compose_file,
            )
            table = self.create_stack_table(name)

            self.stack_headers[name] = header
            self.stack_tables[name] = table

            if name in self.expanded_stacks:
                header.expanded = True
                table.styles.display = "block"

            # Update selected stack data if this is the selected stack
            if (
                self.selected_item
                and self.selected_item[0] == "stack"
                and self.selected_item[1] == name
            ):
                self.selected_stack_data = {
                    "name": name,
                    "config_file": config_file,
                    "running": running,
                    "exited": exited,
                    "total": total,
                    "can_recreate": can_recreate,
                    "has_compose_file": has_compose_file,
                }
        else:
            header = self.stack_headers[name]
            was_expanded = header.expanded
            header.running = running
            header.exited = exited
            header.total = total
            header.config_file = config_file
            header.can_recreate = can_recreate
            header.has_compose_file = has_compose_file
            header.expanded = was_expanded
            self.stack_tables[name].styles.display = "block" if was_expanded else "none"
            header._update_content()

            # Update selected stack data if this is the selected stack
            if (
                self.selected_item
                and self.selected_item[0] == "stack"
                and self.selected_item[1] == name
            ):
                self.selected_stack_data = {
                    "name": name,
                    "config_file": config_file,
                    "running": running,
                    "exited": exited,
                    "total": total,
                    "can_recreate": can_recreate,
                    "has_compose_file": has_compose_file,
                }

    def add_container_to_stack(self, stack_name: str, container_data: dict) -> None:
        """Add or update a container in its stack's table.

        Args:
            stack_name: Name of the stack the container belongs to
            container_data: Dictionary containing container information
        """
        if stack_name not in self.stack_tables:
            self.add_stack(stack_name, "N/A", 0, 0, 0)

        table = self.stack_tables[stack_name]
        container_id = container_data["id"]

        # Format PIDs to show "N/A" when 0
        pids_display = (
            "N/A" if container_data["pids"] == "0" else container_data["pids"]
        )

        row_data = (
            container_data["id"],
            container_data["name"],
            container_data["status"],
            container_data["cpu"],
            container_data["memory"],
            pids_display,
            container_data["ports"],
        )

        # Update selected container data if this is the selected container
        if (
            self.selected_item
            and self.selected_item[0] == "container"
            and self.selected_item[1] == container_id
        ):
            self.selected_container_data = container_data

        try:
            # Since we clear container_rows at the beginning of each update cycle,
            # we'll always be adding new rows during a refresh
            if self._is_updating:
                # Add as a new row
                row_key = table.row_count
                table.add_row(*row_data)
                self.container_rows[container_id] = (stack_name, row_key)
            else:
                # For individual updates outside of a batch update cycle,
                # check if this container already exists in the table
                if container_id in self.container_rows:
                    existing_stack, existing_row = self.container_rows[container_id]

                    # If the container moved to a different stack, remove it from the old one
                    if (
                        existing_stack != stack_name
                        and existing_stack in self.stack_tables
                    ):
                        old_table = self.stack_tables[existing_stack]
                        try:
                            old_table.remove_row(existing_row)
                            # Update row indices for containers after this one
                            for cid, (cstack, crow) in list(
                                self.container_rows.items()
                            ):
                                if cstack == existing_stack and crow > existing_row:
                                    self.container_rows[cid] = (cstack, crow - 1)
                        except Exception as e:
                            logger.error(
                                f"Error removing container {container_id} from old stack: {str(e)}",
                                exc_info=True,
                            )

                        # Add to the new stack
                        row_key = table.row_count
                        table.add_row(*row_data)
                        self.container_rows[container_id] = (stack_name, row_key)
                    else:
                        # Update the existing row in the same stack
                        try:
                            for col_idx, value in enumerate(row_data):
                                table.update_cell(existing_row, col_idx, value)
                        except Exception as e:
                            logger.error(
                                f"Error updating container {container_id}: {str(e)}",
                                exc_info=True,
                            )
                else:
                    # Add as a new row
                    row_key = table.row_count
                    table.add_row(*row_data)
                    self.container_rows[container_id] = (stack_name, row_key)

        except Exception as e:
            logger.error(
                f"Error adding container {container_id}: {str(e)}", exc_info=True
            )

    def on_mount(self) -> None:
        """Handle initial widget mount by focusing and expanding the first stack."""
        try:
            # Check if the search input is currently focused
            should_focus = True
            if self.screen and self.screen.focused:
                focused_widget = self.screen.focused
                if (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    should_focus = False

            headers = list(self.stack_headers.values())
            if headers:
                first_header = headers[0]
                if should_focus:
                    first_header.focus()
                first_header.expanded = True
                first_table = self.stack_tables[first_header.stack_name]
                first_table.styles.display = "block"

                # If there are rows in the first table, select the first container
                if first_table.row_count > 0:
                    if should_focus:
                        first_table.focus()
                    first_table.move_cursor(row=0)

                    # Get the container ID from the first row
                    container_id = first_table.get_cell_at((0, 0))
                    if container_id:
                        self.select_container(container_id)
                else:
                    # If no containers, select the stack
                    self.select_stack(first_header.stack_name)
        except Exception as e:
            logger.error(f"Error during ContainerList mount: {str(e)}", exc_info=True)
            raise

    def select_volume(self, volume_name: str) -> None:
        """Select a volume and update the footer.

        Args:
            volume_name: Name of the volume to select
        """
        if volume_name in self.volume_headers:
            # Clear any previous selection
            self.selected_item = ("volume", volume_name)
            self.selected_container_data = None
            self.selected_stack_data = None
            self.selected_network_data = None

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

            # Update the footer and cursor visibility
            self._update_footer_with_selection()
            self._update_cursor_visibility()

            # Post selection change message
            self.post_message(
                SelectionChanged("volume", volume_name, self.selected_volume_data)
            )

    def select_network(self, network_name: str) -> None:
        """Select a network and update the footer.

        Args:
            network_name: Name of the network to select
        """
        if network_name in self.network_headers:
            # Clear any previous selection
            self.selected_item = ("network", network_name)
            self.selected_container_data = None
            self.selected_stack_data = None
            self.selected_volume_data = None

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

            # Update the footer and cursor visibility
            self._update_footer_with_selection()
            self._update_cursor_visibility()

            # Post selection change message
            self.post_message(
                SelectionChanged("network", network_name, self.selected_network_data)
            )

    def select_stack(self, stack_name: str) -> None:
        """Select a stack and update the footer.

        Args:
            stack_name: Name of the stack to select
        """
        if stack_name in self.stack_headers:
            # Clear any previous selection
            self.selected_item = ("stack", stack_name)
            self.selected_container_data = None
            self.selected_volume_data = None
            self.selected_network_data = None

            # Store stack data for footer display
            header = self.stack_headers[stack_name]
            self.selected_stack_data = {
                "name": stack_name,
                "config_file": header.config_file,
                "running": header.running,
                "exited": header.exited,
                "total": header.total,
                "can_recreate": header.can_recreate,
                "has_compose_file": header.has_compose_file,
            }

            # Update the footer and cursor visibility
            self._update_footer_with_selection()
            self._update_cursor_visibility()

            # Post selection change message
            self.post_message(
                SelectionChanged("stack", stack_name, self.selected_stack_data)
            )

    def select_container(self, container_id: str) -> None:
        """Select a container and update the footer.

        Args:
            container_id: ID of the container to select
        """
        if container_id in self.container_rows:
            # Clear any previous selection
            self.selected_item = ("container", container_id)
            self.selected_stack_data = None
            self.selected_volume_data = None
            self.selected_network_data = None

            # Find the container data
            stack_name, row_idx = self.container_rows[container_id]
            table = self.stack_tables[stack_name]

            # Get container data from the table
            container_data = {
                "id": table.get_cell_at((row_idx, 0)),
                "name": table.get_cell_at((row_idx, 1)),
                "status": table.get_cell_at((row_idx, 2)),
                "cpu": table.get_cell_at((row_idx, 3)),
                "memory": table.get_cell_at((row_idx, 4)),
                "pids": table.get_cell_at((row_idx, 5)),
                "ports": table.get_cell_at((row_idx, 6)),
                "stack": stack_name,
            }

            self.selected_container_data = container_data

            # Make sure the stack is expanded
            header = self.stack_headers[stack_name]
            if not header.expanded:
                header.expanded = True
                table.styles.display = "block"
                header._update_content()

            # Check if the search input is currently focused
            if self.screen and self.screen.focused:
                focused_widget = self.screen.focused
                if (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    # Still position the cursor on the selected row without focusing
                    if table.cursor_row != row_idx:
                        table.move_cursor(row=row_idx)
                else:
                    # Focus the table and position the cursor
                    table.focus()
                    if table.cursor_row != row_idx:
                        table.move_cursor(row=row_idx)
            else:
                # Focus the table and position the cursor
                table.focus()
                if table.cursor_row != row_idx:
                    table.move_cursor(row=row_idx)

            # Force a refresh of the table to ensure the cursor is visible
            table.refresh()

            # Update the footer with selection
            self._update_footer_with_selection()

            # Post selection change message
            self.post_message(
                SelectionChanged(
                    "container", container_id, self.selected_container_data
                )
            )
        else:
            logger.error(f"Container ID {container_id} not found in container_rows")

    def _update_footer_with_selection(self) -> None:
        """Update the footer with the current selection information."""
        if self.screen is None:
            logger.warning("Cannot update footer: screen is None")
            return

        try:
            status_bar = self.screen.query_one("#status_bar")

            if self.selected_item is None:
                no_selection_text = Text(
                    "No selection", Style(color="white", bold=True)
                )
                status_bar.update(no_selection_text)
                self.post_message(SelectionChanged("none", "", {}))
                return

            item_type, item_id = self.selected_item

            if item_type == "volume" and self.selected_volume_data:
                volume_data = self.selected_volume_data
                selection_text = Text()
                selection_text.append(
                    "Current Selection:", Style(color="black", bgcolor="yellow")
                )
                selection_text.append("  Volume: ", Style(color="white"))
                selection_text.append(
                    f"{volume_data['name']}", Style(color="magenta", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Driver: ", Style(color="white"))
                selection_text.append(
                    f"{volume_data['driver']}", Style(color="blue", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Stack: ", Style(color="white"))
                if volume_data["stack"]:
                    selection_text.append(
                        f"{volume_data['stack']}", Style(color="green", bold=True)
                    )
                else:
                    selection_text.append("None", Style(color="dim", bold=True))
                status_bar.update(selection_text)

            elif item_type == "network" and self.selected_network_data:
                network_data = self.selected_network_data
                selection_text = Text()
                selection_text.append(
                    "Current Selection:", Style(color="black", bgcolor="yellow")
                )
                selection_text.append("  Network: ", Style(color="white"))
                selection_text.append(
                    f"{network_data['name']}", Style(color="cyan", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Driver: ", Style(color="white"))
                selection_text.append(
                    f"{network_data['driver']}", Style(color="blue", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Scope: ", Style(color="white"))
                selection_text.append(
                    f"{network_data['scope']}", Style(color="magenta", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Containers: ", Style(color="white"))
                selection_text.append(
                    f"{network_data['total_containers']}",
                    Style(color="green", bold=True),
                )
                status_bar.update(selection_text)

            elif item_type == "stack" and self.selected_stack_data:
                stack_data = self.selected_stack_data
                selection_text = Text()
                selection_text.append(
                    "Current Selection:", Style(color="black", bgcolor="yellow")
                )
                selection_text.append("  Stack: ", Style(color="white"))
                selection_text.append(
                    f"{stack_data['name']}", Style(color="white", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Running: ", Style(color="white"))
                selection_text.append(
                    f"{stack_data['running']}", Style(color="green", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Exited: ", Style(color="white"))
                selection_text.append(
                    f"{stack_data['exited']}", Style(color="yellow", bold=True)
                )
                selection_text.append(" | ", Style(color="white"))
                selection_text.append(f"Total: ", Style(color="white"))
                selection_text.append(
                    f"{stack_data['total']}", Style(color="cyan", bold=True)
                )
                status_bar.update(selection_text)

            elif item_type == "container" and self.selected_container_data:
                container_data = self.selected_container_data
                selection_text = Text()
                selection_text.append(
                    "Current Selection:", Style(color="black", bgcolor="yellow")
                )
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

            else:
                # Clear the status bar if no valid selection
                logger.warning(f"Invalid selection: {item_type} - {item_id}")
                invalid_selection_text = Text(
                    f"Invalid selection: {item_type} - {item_id}",
                    Style(color="red", bold=True),
                )
                status_bar.update(invalid_selection_text)

        except Exception as e:
            logger.error(f"Error updating status bar: {str(e)}", exc_info=True)

    def _restore_selection(self) -> None:
        """Restore the previously selected item after a refresh."""
        try:
            if self.selected_item is None:
                return

            # Check if the search input is currently focused
            if self.screen and self.screen.focused:
                focused_widget = self.screen.focused
                if (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    self._update_footer_with_selection()
                    return

            item_type, item_id = self.selected_item

            if item_type == "volume" and item_id in self.volume_headers:
                header = self.volume_headers[item_id]
                header.focus()
                self._update_footer_with_selection()

            elif item_type == "stack" and item_id in self.stack_headers:
                header = self.stack_headers[item_id]
                header.focus()
                self._update_footer_with_selection()

            elif item_type == "container" and item_id in self.container_rows:
                stack_name, row_idx = self.container_rows[item_id]
                if stack_name in self.stack_tables:
                    table = self.stack_tables[stack_name]
                    header = self.stack_headers[stack_name]

                    if not header.expanded:
                        header.expanded = True
                        table.styles.display = "block"
                        header._update_content()

                    table.focus()
                    table.move_cursor(row=row_idx)
                    self._update_footer_with_selection()
        except Exception as e:
            logger.error(f"Error restoring selection: {str(e)}", exc_info=True)

    def _update_cursor_visibility(self) -> None:
        """Update cursor visibility and focus based on current selection."""
        try:
            # Check if the search input is currently focused
            if self.screen and self.screen.focused:
                focused_widget = self.screen.focused
                if (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    return

            # If a container is selected, focus its table and position the cursor
            if self.selected_item and self.selected_item[0] == "container":
                container_id = self.selected_item[1]
                if container_id in self.container_rows:
                    stack_name, row_idx = self.container_rows[container_id]
                    if stack_name in self.stack_tables:
                        table = self.stack_tables[stack_name]
                        table.focus()
                        if table.cursor_row != row_idx:
                            table.move_cursor(row=row_idx)

            # If a stack is selected, focus its header
            elif self.selected_item and self.selected_item[0] == "stack":
                stack_name = self.selected_item[1]
                if stack_name in self.stack_headers:
                    header = self.stack_headers[stack_name]
                    header.focus()

            # If a volume is selected, focus its header
            elif self.selected_item and self.selected_item[0] == "volume":
                volume_name = self.selected_item[1]
                if volume_name in self.volume_headers:
                    header = self.volume_headers[volume_name]
                    header.focus()

        except Exception as e:
            logger.error(
                f"Error updating cursor visibility and focus: {str(e)}", exc_info=True
            )

    # Event handlers
    def on_section_header_clicked(self, event) -> None:
        """Handle SectionHeader click events to toggle section visibility."""
        header = event.section_header

        # Update the collapsed state based on which section was clicked
        if header == self.stacks_section_header:
            self.stacks_section_collapsed = header.collapsed
            # Toggle visibility of the stacks container
            if self.stacks_container:
                self.stacks_container.styles.display = (
                    "none" if header.collapsed else "block"
                )
        elif header == self.volumes_section_header:
            self.volumes_section_collapsed = header.collapsed
            # Toggle visibility of the volumes container
            if self.volumes_container:
                self.volumes_container.styles.display = (
                    "none" if header.collapsed else "block"
                )
        elif header == self.networks_section_header:
            self.networks_section_collapsed = header.collapsed
            # Toggle visibility of the networks container
            if self.networks_container:
                self.networks_container.styles.display = (
                    "none" if header.collapsed else "block"
                )

    def on_volume_header_selected(self, event) -> None:
        """Handle VolumeHeader selection events."""
        header = event.volume_header
        self.select_volume(header.volume_name)

    def on_volume_header_clicked(self, event) -> None:
        """Handle VolumeHeader click events."""
        header = event.volume_header
        self.select_volume(header.volume_name)

    def on_network_header_selected(self, event) -> None:
        """Handle NetworkHeader selection events."""
        header = event.network_header
        self.select_network(header.network_name)

    def on_network_header_clicked(self, event) -> None:
        """Handle NetworkHeader click events."""
        header = event.network_header
        self.select_network(header.network_name)

    def on_stack_header_selected(self, event) -> None:
        """Handle StackHeader selection events."""
        header = event.stack_header
        self.select_stack(header.stack_name)

    def on_stack_header_clicked(self, event) -> None:
        """Handle StackHeader click events."""
        header = event.stack_header
        self.select_stack(header.stack_name)

    def on_data_table_row_selected(self, event) -> None:
        """Handle DataTable row selection events."""
        table = event.data_table
        row_key = event.row_key

        # Find which stack this table belongs to
        for stack_name, stack_table in self.stack_tables.items():
            if stack_table == table:
                try:
                    row = table.get_row_index(row_key)
                    if row is not None and row < table.row_count:
                        container_id = table.get_cell_at((row, 0))
                        self.select_container(container_id)
                except Exception as e:
                    logger.error(
                        f"Error handling row selection: {str(e)}", exc_info=True
                    )
                break

    def action_cursor_up(self) -> None:
        """Handle up arrow key."""
        current = self.screen.focused

        # Check if the search input is currently focused
        if hasattr(current, "id") and current.id == "search-input":
            return

        if isinstance(current, DataTable):
            # If we're at the top of the table, focus the header
            if current.cursor_row == 0:
                stack_name = next(
                    name
                    for name, table in self.stack_tables.items()
                    if table == current
                )
                header = self.stack_headers[stack_name]
                header.focus()
                self.select_stack(stack_name)
            else:
                current.action_cursor_up()
                # Update selection based on new cursor position
                row = current.cursor_row
                stack_name = next(
                    name
                    for name, table in self.stack_tables.items()
                    if table == current
                )
                container_id = current.get_cell_at((row, 0))
                self.select_container(container_id)
        elif isinstance(current, StackHeader):
            # Find previous visible widget
            current_idx = list(self.stack_headers.values()).index(current)
            if current_idx > 0:
                prev_header = list(self.stack_headers.values())[current_idx - 1]
                prev_table = self.stack_tables[prev_header.stack_name]
                if prev_header.expanded and prev_table.row_count > 0:
                    prev_table.focus()
                    prev_table.move_cursor(row=prev_table.row_count - 1)
                    # Update selection to the container
                    container_id = prev_table.get_cell_at((prev_table.row_count - 1, 0))
                    self.select_container(container_id)
                else:
                    prev_header.focus()
                    self.select_stack(prev_header.stack_name)

    def action_cursor_down(self) -> None:
        """Handle down arrow key."""
        current = self.screen.focused

        # Check if the search input is currently focused
        if hasattr(current, "id") and current.id == "search-input":
            return

        if isinstance(current, DataTable):
            # If we're at the bottom of the table, focus the next header
            if current.cursor_row >= current.row_count - 1:
                stack_name = next(
                    name
                    for name, table in self.stack_tables.items()
                    if table == current
                )
                next_header_idx = list(self.stack_headers.keys()).index(stack_name) + 1
                if next_header_idx < len(self.stack_headers):
                    next_header = list(self.stack_headers.values())[next_header_idx]
                    next_header.focus()
                    self.select_stack(list(self.stack_headers.keys())[next_header_idx])
            else:
                current.action_cursor_down()
                # Update selection based on new cursor position
                row = current.cursor_row
                stack_name = next(
                    name
                    for name, table in self.stack_tables.items()
                    if table == current
                )
                container_id = current.get_cell_at((row, 0))
                self.select_container(container_id)
        elif isinstance(current, StackHeader):
            # If expanded and has rows, focus the table
            stack_name = current.stack_name
            table = self.stack_tables[stack_name]
            if current.expanded and table.row_count > 0:
                table.focus()
                table.move_cursor(row=0)
                # Update selection to the first container
                container_id = table.get_cell_at((0, 0))
                self.select_container(container_id)
            else:
                # Focus next header
                current_idx = list(self.stack_headers.values()).index(current)
                if current_idx < len(self.stack_headers) - 1:
                    next_header = list(self.stack_headers.values())[current_idx + 1]
                    next_header.focus()
                    self.select_stack(next_header.stack_name)
