"""Main container list widget implementation."""

import logging

from rich.text import Text
from textual.widgets import DataTable, Static

from .base.container_list_base import ContainerListBase
from .components import FooterFormatter, NavigationHandler
from .managers.image_manager import ImageManager
from .managers.network_manager import NetworkManager
from .managers.stack_manager import StackManager
from .managers.volume_manager import VolumeManager
from .widgets.headers import NetworkHeader, StackHeader

logger = logging.getLogger("DockTUI.containers")


class ContainerList(ContainerListBase):
    """A scrollable widget that displays Docker containers grouped by their stacks.

    Provides collapsible stack sections with container details including resource usage
    and status information. Supports keyboard navigation and interaction.
    """

    def __init__(self):
        """Initialize the container list widget with resource managers."""
        super().__init__()
        # Initialize managers
        self.image_manager = ImageManager(self)
        self.volume_manager = VolumeManager(self)
        self.network_manager = NetworkManager(self)
        self.stack_manager = StackManager(self)

        # Loading message for initial data fetch
        self.loading_message = None
        self._initial_load_complete = False

        # Initialize helper components
        self.footer_formatter = FooterFormatter(self)
        self.navigation_handler = NavigationHandler(self)

        # Create references for backward compatibility
        self._setup_backward_compatibility()

    def begin_update(self) -> None:
        """Begin a batch update to prevent UI flickering during data updates."""
        self._is_updating = True
        # Only do a full clear if we have no children OR if the basic structure is missing
        self._pending_clear = (
            len(self.children) == 0
            or self.images_section_header is None
            or self.images_container is None
            or self.images_section_header not in self.children
            or self.images_container not in self.children
        )

        # Clear all tables to ensure fresh data
        self.network_manager.clear_tables()
        self.stack_manager.clear_tables()

        # Reset tracking for new data
        self.image_manager.reset_tracking()
        self.volume_manager.reset_tracking()
        self.network_manager.reset_tracking()
        self.stack_manager.reset_tracking()

        # Ensure section headers are created
        self._ensure_section_headers()

    def end_update(self) -> None:
        """End a batch update and apply pending changes to the UI."""
        try:
            # Remove loading message on first data load
            if not self._initial_load_complete and self.loading_message:
                if self.loading_message.parent:
                    self.loading_message.remove()
                self.loading_message = None
                self._initial_load_complete = True

            # First, clean up items that no longer exist in the Docker data
            self._cleanup_removed_items()

            # Then, determine what needs to be added or updated
            self._prepare_new_containers()

            # Apply changes to the UI
            if self._pending_clear:
                self._mount_all_sections()
            else:
                self._update_existing_sections()

            # Flush pending volumes to table in sorted order
            self.volume_manager.flush_pending_volumes()

            # Ensure images table is sorted after all updates
            self.image_manager.ensure_sorted()

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
        """Remove images, volumes, networks, and stacks that no longer exist."""
        # Delegate to managers
        self.image_manager.cleanup_removed_images()
        self.volume_manager.cleanup_removed_volumes()
        self.network_manager.cleanup_removed_networks()
        self.stack_manager.cleanup_removed_stacks()

    def _prepare_new_containers(self) -> None:
        """Prepare containers that need to be added to the UI."""
        # Get existing containers from managers
        if not self._pending_clear:
            self.existing_image_containers = (
                self.image_manager.get_existing_containers()
            )
            # Volumes now use a table, no individual containers
            self.existing_network_containers = (
                self.network_manager.get_existing_containers()
            )
            self.existing_stack_containers = (
                self.stack_manager.get_existing_containers()
            )
        else:
            self.existing_image_containers = {}
            self.existing_network_containers = {}
            self.existing_stack_containers = {}

        # Prepare new containers using managers
        self.new_image_containers = self.image_manager.prepare_new_containers()
        self.new_network_containers = self.network_manager.prepare_new_containers()
        self.new_stack_containers = self.stack_manager.prepare_new_containers()

    def _mount_all_sections(self) -> None:
        """Mount all sections when starting fresh."""
        self.remove_children()
        self._pending_clear = False

        # Ensure section headers and containers exist
        self._ensure_section_headers()

        # Mount all sections in order: STACKS, IMAGES, NETWORKS, VOLUMES
        self._mount_section(
            self.stacks_section_header,
            self.stacks_container,
            self.stacks_section_collapsed,
        )
        self._mount_new_containers(
            self.new_stack_containers, self.stacks_container, with_table=True
        )

        self._mount_section(
            self.images_section_header,
            self.images_container,
            self.images_section_collapsed,
        )

        self._mount_section(
            self.networks_section_header,
            self.networks_container,
            self.networks_section_collapsed,
        )
        self._mount_new_containers(
            self.new_network_containers, self.networks_container, with_table=True
        )

        self._mount_section(
            self.volumes_section_header,
            self.volumes_container,
            self.volumes_section_collapsed,
        )

    def _update_existing_sections(self) -> None:
        """Update existing sections and add new items."""
        # Images are handled by the table, no individual containers to update

        # Volumes are now handled by the table, will be mounted after ensuring container exists

        # Update existing networks
        for network_name, container in self.existing_network_containers.items():
            if network_name in self.network_headers:
                header = self.network_headers[network_name]
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
                for widget in container.children:
                    if isinstance(widget, StackHeader):
                        widget._update_content()
                    elif isinstance(widget, DataTable):
                        widget.styles.display = "block" if header.expanded else "none"
            else:
                container.remove()

        # Ensure section headers and containers exist
        self._ensure_section_headers()

        # Mount any missing sections in the correct order
        if self.stacks_section_header not in self.children:
            self.mount(self.stacks_section_header)
        if self.stacks_container not in self.children:
            self.mount(self.stacks_container)

        if self.images_section_header not in self.children:
            self.mount(self.images_section_header)
        if self.images_container not in self.children:
            self.mount(self.images_container)

        if self.networks_section_header not in self.children:
            self.mount(self.networks_section_header)
        if self.networks_container not in self.children:
            self.mount(self.networks_container)

        if self.volumes_section_header not in self.children:
            self.mount(self.volumes_section_header)
        if self.volumes_container not in self.children:
            self.mount(self.volumes_container)

        # Update visibility states
        self.stacks_container.styles.display = (
            "none" if self.stacks_section_collapsed else "block"
        )
        self.images_container.styles.display = (
            "none" if self.images_section_collapsed else "block"
        )
        self.networks_container.styles.display = (
            "none" if self.networks_section_collapsed else "block"
        )
        self.volumes_container.styles.display = (
            "none" if self.volumes_section_collapsed else "block"
        )

        # Add new items to each section
        self._mount_new_containers(
            self.new_stack_containers, self.stacks_container, with_table=True
        )
        self._mount_new_containers(
            self.new_network_containers, self.networks_container, with_table=True
        )

    def clear(self) -> None:
        """Clear all stacks and containers while preserving expansion states."""
        # Save expanded states before clearing
        # Volume manager doesn't have expanded state (uses table)
        self.network_manager.save_expanded_state()
        self.stack_manager.save_expanded_state()

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

    def add_image(self, image_data: dict) -> None:
        """Add or update an image section in the container list.

        Args:
            image_data: Dictionary containing image information
        """
        self.image_manager.add_image(image_data)
        # Update selected_image_data reference for backward compatibility
        self.selected_image_data = self.image_manager.selected_image_data

    def add_volume(self, volume_data: dict) -> None:
        """Add or update a volume section in the container list.

        Args:
            volume_data: Dictionary containing volume information
        """
        self.volume_manager.add_volume(volume_data)
        # Update selected_volume_data reference for backward compatibility
        self.selected_volume_data = self.volume_manager.selected_volume_data

    def add_network(self, network_data: dict) -> None:
        """Add or update a network section in the container list.

        Args:
            network_data: Dictionary containing network information
        """
        self.network_manager.add_network(network_data)
        # Update selected_network_data reference for backward compatibility
        self.selected_network_data = self.network_manager.selected_network_data

    def add_container_to_network(self, network_name: str, container_data: dict) -> None:
        """Add or update a container in its network's table.

        Args:
            network_name: Name of the network the container is connected to
            container_data: Dictionary containing container information
        """
        self.network_manager.add_container_to_network(network_name, container_data)

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
        self.stack_manager.add_stack(
            name, config_file, running, exited, total, can_recreate, has_compose_file
        )
        # Update selected_stack_data reference for backward compatibility
        self.selected_stack_data = self.stack_manager.selected_stack_data

    def add_container_to_stack(self, stack_name: str, container_data: dict) -> None:
        """Add or update a container in its stack's table.

        Args:
            stack_name: Name of the stack the container belongs to
            container_data: Dictionary containing container information
        """
        self.stack_manager.add_container_to_stack(stack_name, container_data)
        # Update selected_container_data reference for backward compatibility
        self.selected_container_data = self.stack_manager.selected_container_data

    def on_mount(self) -> None:
        """Handle initial widget mount by focusing and expanding the first stack."""
        try:
            # Show loading message if this is the initial load
            if not self._initial_load_complete and len(self.children) == 0:
                self.loading_message = Static(
                    Text("Please wait, loading data...", style="dim italic"),
                    classes="initial-loading-message",
                )
                self.loading_message.styles.width = "100%"
                self.loading_message.styles.height = "100%"
                self.loading_message.styles.content_align = ("center", "middle")
                self.loading_message.styles.padding = (2, 0)
                self.mount(self.loading_message)
                return  # Don't try to focus anything yet

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

                # Select the stack header only, not any container
                self.select_stack(first_header.stack_name)

                # Ensure no row is selected in any table initially
                for table in self.stack_tables.values():
                    if table.row_count > 0:
                        # Blur the table to remove cursor highlight
                        table.blur()
        except Exception as e:
            logger.error(f"Error during ContainerList mount: {str(e)}", exc_info=True)
            raise

    def select_image(self, image_id: str) -> None:
        """Select an image and update the footer.

        Args:
            image_id: ID of the image to select
        """
        self.image_manager.select_image(image_id)
        # Manager handles selection data updates

    def select_volume(self, volume_name: str) -> None:
        """Select a volume and update the footer.

        Args:
            volume_name: Name of the volume to select
        """
        self.volume_manager.select_volume(volume_name)
        # Manager handles selection data updates
        self.selected_volume_data = self.volume_manager.selected_volume_data

    def select_network(self, network_name: str) -> None:
        """Select a network and update the footer.

        Args:
            network_name: Name of the network to select
        """
        self.network_manager.select_network(network_name)
        # Manager handles selection data updates

    def select_stack(self, stack_name: str) -> None:
        """Select a stack and update the footer.

        Args:
            stack_name: Name of the stack to select
        """
        self.stack_manager.select_stack(stack_name)
        # Manager handles selection data updates

    def select_container(self, container_id: str) -> None:
        """Select a container and update the footer.

        Args:
            container_id: ID of the container to select
        """
        self.stack_manager.select_container(container_id)
        # Manager handles selection data updates

    def _update_footer_with_selection(self) -> None:
        """Update the footer with the current selection information."""
        self.footer_formatter.update_footer_with_selection()

    def _setup_backward_compatibility(self):
        """Set up references for backward compatibility."""
        # Image references
        self.image_headers = self.image_manager.image_headers
        self.expanded_images = self.image_manager.expanded_images
        self._images_in_new_data = self.image_manager._images_in_new_data

        # Volume references
        self.volume_rows = self.volume_manager.volume_rows
        self._volumes_in_new_data = self.volume_manager._volumes_in_new_data

        # Network references
        self.network_tables = self.network_manager.network_tables
        self.network_headers = self.network_manager.network_headers
        self.network_rows = self.network_manager.network_rows
        self.expanded_networks = self.network_manager.expanded_networks
        self._networks_in_new_data = self.network_manager._networks_in_new_data

        # Stack references
        self.stack_tables = self.stack_manager.stack_tables
        self.stack_headers = self.stack_manager.stack_headers
        self.container_rows = self.stack_manager.container_rows
        self.expanded_stacks = self.stack_manager.expanded_stacks
        self._stacks_in_new_data = self.stack_manager._stacks_in_new_data

    def _mount_section(self, header, container, collapsed):
        """Mount a section header and container."""
        self.mount(header)
        self.mount(container)
        container.styles.display = "none" if collapsed else "block"

    def _mount_new_containers(self, containers_dict, parent_container, with_table=True):
        """Mount new containers to their parent."""
        for name, (container, header, table) in containers_dict.items():
            parent_container.mount(container)
            container.mount(header)
            if with_table and table:
                container.mount(table)
                table.styles.display = "block" if header.expanded else "none"

    def clear_status_override(self, container_id: str) -> None:
        """Clear the status override for a container.

        Args:
            container_id: The short ID of the container
        """
        if (
            hasattr(self, "_status_overrides")
            and container_id in self._status_overrides
        ):
            del self._status_overrides[container_id]

    def update_container_status(self, container_id: str, status: str) -> None:
        """Set a status override for a container.

        Args:
            container_id: The short ID of the container
            status: The new status to display (e.g., "starting...", "stopping...")
        """
        # Store the override status - it will be used during the next refresh
        if not hasattr(self, "_status_overrides"):
            self._status_overrides = {}
        self._status_overrides[container_id] = status

    def _restore_selection(self) -> None:
        """Restore the previously selected item after a refresh."""
        self.navigation_handler.restore_selection()

    def _update_cursor_visibility(self) -> None:
        """Update cursor visibility and focus based on current selection."""
        self.navigation_handler.update_cursor_visibility()

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
                # Show loading message when expanding if table not initialized
                if not header.collapsed and not self.volume_manager._table_initialized:
                    self.volume_manager.show_loading_message()
        elif header == self.images_section_header:
            self.images_section_collapsed = header.collapsed
            # Toggle visibility of the images container
            if self.images_container:
                self.images_container.styles.display = (
                    "none" if header.collapsed else "block"
                )
                # Show loading message when expanding if table not initialized
                if not header.collapsed and not self.image_manager._table_initialized:
                    self.image_manager.show_loading_message()
        elif header == self.networks_section_header:
            self.networks_section_collapsed = header.collapsed
            # Toggle visibility of the networks container
            if self.networks_container:
                self.networks_container.styles.display = (
                    "none" if header.collapsed else "block"
                )

    def on_image_header_selected(self, event) -> None:
        """Handle ImageHeader selection events."""
        self.select_image(event.image_header.image_id)

    def on_image_header_clicked(self, event) -> None:
        """Handle ImageHeader click events."""
        self.select_image(event.image_header.image_id)

    def on_network_header_selected(self, event) -> None:
        """Handle NetworkHeader selection events."""
        self.select_network(event.network_header.network_name)

    def on_network_header_clicked(self, event) -> None:
        """Handle NetworkHeader click events."""
        self.select_network(event.network_header.network_name)

    def on_stack_header_selected(self, event) -> None:
        """Handle StackHeader selection events."""
        self.select_stack(event.stack_header.stack_name)

    def on_stack_header_clicked(self, event) -> None:
        """Handle StackHeader click events."""
        self.select_stack(event.stack_header.stack_name)

    def on_data_table_row_selected(self, event) -> None:
        """Handle DataTable row selection events."""
        table = event.data_table
        row_key = event.row_key

        # Check if it's the images table
        if self.image_manager.images_table and table == self.image_manager.images_table:
            self.image_manager.handle_selection(row_key)
            return

        # Check if it's the volumes table
        if (
            self.volume_manager.volume_table
            and table == self.volume_manager.volume_table
        ):
            self.volume_manager.handle_table_selection(row_key)
            return

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
        self.navigation_handler.handle_cursor_up()

    def action_cursor_down(self) -> None:
        """Handle down arrow key."""
        self.navigation_handler.handle_cursor_down()
