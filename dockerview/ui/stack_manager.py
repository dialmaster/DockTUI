"""Stack-specific functionality for the container list widget."""

import logging
from typing import Dict, Optional, Tuple

from textual.containers import Container
from textual.widgets import DataTable

from .headers import StackHeader

logger = logging.getLogger("dockerview.stack_manager")


class StackManager:
    """Manages stack-related UI components and operations."""

    def __init__(self, parent):
        """Initialize the stack manager.

        Args:
            parent: The parent ContainerList widget
        """
        self.parent = parent
        self.stack_tables: Dict[str, DataTable] = {}
        self.stack_headers: Dict[str, StackHeader] = {}
        self.container_rows: Dict[str, Tuple[str, int]] = {}
        self.expanded_stacks = set()
        self._stacks_in_new_data = set()
        self.selected_stack_data: Optional[Dict] = None
        self.selected_container_data: Optional[Dict] = None

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
            table = self.parent.create_stack_table(name)

            self.stack_headers[name] = header
            self.stack_tables[name] = table

            if name in self.expanded_stacks:
                header.expanded = True
                table.styles.display = "block"

            # Update selected stack data if this is the selected stack
            if (
                self.parent.selected_item
                and self.parent.selected_item[0] == "stack"
                and self.parent.selected_item[1] == name
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
                self.parent.selected_item
                and self.parent.selected_item[0] == "stack"
                and self.parent.selected_item[1] == name
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

        # Check for status override
        status = container_data["status"]
        if (
            hasattr(self.parent, "_status_overrides")
            and container_id in self.parent._status_overrides
        ):
            status = self.parent._status_overrides[container_id]

        row_data = (
            container_data["id"],
            container_data["name"],
            status,
            container_data["cpu"],
            container_data["memory"],
            pids_display,
            container_data["ports"],
        )

        # Update selected container data if this is the selected container
        if (
            self.parent.selected_item
            and self.parent.selected_item[0] == "container"
            and self.parent.selected_item[1] == container_id
        ):
            self.selected_container_data = container_data

        try:
            # Since we clear container_rows at the beginning of each update cycle,
            # we'll always be adding new rows during a refresh
            if self.parent._is_updating:
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

    def remove_stack(self, stack_name: str) -> None:
        """Remove a stack and its associated UI elements.

        Args:
            stack_name: Name of the stack to remove
        """
        self.expanded_stacks.discard(stack_name)

        # Remove UI widgets
        if self.parent.stacks_container:
            for child in list(self.parent.stacks_container.children):
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
            self.parent.selected_item
            and self.parent.selected_item[0] == "stack"
            and self.parent.selected_item[1] == stack_name
        ):
            self.parent.selected_item = None
            self.selected_stack_data = None
        elif (
            self.parent.selected_item
            and self.parent.selected_item[0] == "container"
            and self.parent.selected_item[1] in containers_to_remove
        ):
            self.parent.selected_item = None
            self.selected_container_data = None

    def select_stack(self, stack_name: str) -> None:
        """Select a stack and update the footer.

        Args:
            stack_name: Name of the stack to select
        """
        if stack_name in self.stack_headers:
            # Clear any previous selection
            self.parent.selected_item = ("stack", stack_name)
            self.parent.selected_container_data = None
            self.parent.selected_volume_data = None
            self.parent.selected_network_data = None

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
            self.parent.selected_stack_data = self.selected_stack_data

            # Update the footer and cursor visibility
            self.parent._update_footer_with_selection()
            self.parent._update_cursor_visibility()

            # Import here to avoid circular import
            from .container_list_base import SelectionChanged

            # Post selection change message
            self.parent.post_message(
                SelectionChanged("stack", stack_name, self.selected_stack_data)
            )

    def select_container(self, container_id: str) -> None:
        """Select a container and update the footer.

        Args:
            container_id: ID of the container to select
        """
        if container_id in self.container_rows:
            # Clear any previous selection
            self.parent.selected_item = ("container", container_id)
            self.parent.selected_stack_data = None
            self.parent.selected_volume_data = None
            self.parent.selected_network_data = None

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
            self.parent.selected_container_data = container_data

            # Make sure the stack is expanded
            header = self.stack_headers[stack_name]
            if not header.expanded:
                header.expanded = True
                table.styles.display = "block"
                header._update_content()

            # Check if the search input is currently focused
            if self.parent.screen and self.parent.screen.focused:
                focused_widget = self.parent.screen.focused
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
            self.parent._update_footer_with_selection()

            # Import here to avoid circular import
            from .container_list_base import SelectionChanged

            # Post selection change message
            self.parent.post_message(
                SelectionChanged(
                    "container", container_id, self.selected_container_data
                )
            )
        else:
            logger.error(f"Container ID {container_id} not found in container_rows")

    def clear_tables(self) -> None:
        """Clear all stack tables."""
        for table in self.stack_tables.values():
            table.clear()
        self.container_rows.clear()

    def reset_tracking(self) -> None:
        """Reset tracking for new data updates."""
        self._stacks_in_new_data = set()

    def save_expanded_state(self) -> None:
        """Save the current expanded state of stacks."""
        self.expanded_stacks = {
            name for name, header in self.stack_headers.items() if header.expanded
        }

    def cleanup_removed_stacks(self) -> None:
        """Remove stacks that no longer exist."""
        stacks_to_remove = []
        for stack_name in list(self.stack_headers.keys()):
            if stack_name not in self._stacks_in_new_data:
                stacks_to_remove.append(stack_name)

        for stack_name in stacks_to_remove:
            self.remove_stack(stack_name)

    def get_existing_containers(self) -> dict:
        """Get existing stack containers for updates."""
        existing_stack_containers = {}
        if self.parent.stacks_container:
            for child in self.parent.stacks_container.children:
                if isinstance(child, Container) and "stack-container" in child.classes:
                    for widget in child.children:
                        if isinstance(widget, StackHeader):
                            existing_stack_containers[widget.stack_name] = child
                            break
        return existing_stack_containers

    def prepare_new_containers(self) -> dict:
        """Prepare new stack containers to be added."""
        new_stack_containers = {}
        existing_containers = self.get_existing_containers()

        for stack_name in sorted(self.stack_headers.keys()):
            if stack_name not in existing_containers:
                header = self.stack_headers[stack_name]
                table = self.stack_tables[stack_name]
                stack_container = Container(classes="stack-container")
                new_stack_containers[stack_name] = (stack_container, header, table)
        return new_stack_containers
