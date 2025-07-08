"""Stack-specific functionality for the container list widget."""

import logging
from typing import Dict, Optional, Tuple

from textual.containers import Container
from textual.widgets import DataTable

from ..base.container_list_base import SelectionChanged
from ..widgets.headers import StackHeader

logger = logging.getLogger("DockTUI.stack_manager")


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
        # Cache full container data for each container ID
        self._container_data_cache: Dict[str, Dict] = {}
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

        # Get operation status from parent if available
        operation_status = None
        if hasattr(self.parent, "get_stack_status"):
            operation_status = self.parent.get_stack_status(name)

        if name not in self.stack_tables:
            header = StackHeader(
                name,
                config_file,
                running,
                exited,
                total,
                can_recreate,
                has_compose_file,
                operation_status,
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
            # Only preserve existing operation status if:
            # 1. New status is None
            # 2. Header has an existing status
            # 3. The status is still in the parent's overrides (not cleared)
            if operation_status is None and header.operation_status:
                # Check if the status is still valid in the parent's overrides
                if (
                    hasattr(self.parent, "_stack_status_overrides")
                    and isinstance(self.parent._stack_status_overrides, dict)
                    and name in self.parent._stack_status_overrides
                ):
                    operation_status = header.operation_status
                else:
                    # Status was cleared, so don't preserve it
                    operation_status = None
            header.running = running
            header.exited = exited
            header.total = total
            header.config_file = config_file
            header.can_recreate = can_recreate
            header.has_compose_file = has_compose_file
            header.expanded = was_expanded
            header.operation_status = operation_status
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
        actual_status = status.lower()

        if (
            hasattr(self.parent, "_status_overrides")
            and container_id in self.parent._status_overrides
        ):
            override = self.parent._status_overrides[container_id]

            # Get the time when this override was set
            override_time = None
            if hasattr(self.parent, "_status_override_times"):
                override_time = self.parent._status_override_times.get(container_id)

            # Only apply the override if it makes sense given the actual status
            # For example, don't show "stopping..." if container is already exited
            should_apply_override = False

            if override == "stopping...":
                # Only show "stopping..." if container is still running
                should_apply_override = actual_status in ["running", "restarting"]
            elif override == "starting...":
                # Only show "starting..." if container is not yet running
                should_apply_override = actual_status in [
                    "exited",
                    "stopped",
                    "created",
                    "paused",
                ]
            elif override in ["restarting...", "recreating..."]:
                # For these operations, show the status for up to 10 seconds
                # After that, assume the operation has completed
                if override_time:
                    import time

                    elapsed = time.time() - override_time
                    should_apply_override = elapsed < 10.0  # 10 second timeout
                else:
                    # If no timestamp, show for backwards compatibility
                    should_apply_override = True

            if should_apply_override:
                status = override
            else:
                # Clear the override since it's no longer relevant
                del self.parent._status_overrides[container_id]
                if (
                    hasattr(self.parent, "_status_override_times")
                    and container_id in self.parent._status_override_times
                ):
                    del self.parent._status_override_times[container_id]

        row_data = (
            container_data["id"],
            container_data["name"],
            status,
            container_data.get("uptime", "N/A"),
            container_data["cpu"],
            container_data["memory"],
            pids_display,
            container_data["ports"],
        )

        # Cache the full container data
        self._container_data_cache[container_id] = container_data

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
                table.add_row(*row_data, key=container_id)
                self.container_rows[container_id] = (stack_name, row_key)

                # Check if this was the previously selected row
                if hasattr(self, "_pending_selection") and self._pending_selection:
                    pending_stack, pending_container_id = self._pending_selection
                    if (
                        pending_stack == stack_name
                        and pending_container_id == container_id
                    ):
                        # Restore the selection
                        table.add_class("has-selection")
                        table._selected_row_key = container_id
                        table.move_cursor(row=row_key)
                        delattr(self, "_pending_selection")
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
                        table.add_row(*row_data, key=container_id)
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
            # Clear all selections using the shared method
            self.parent.clear_all_selections()

            # Add 'selected' class to the selected stack header
            self.stack_headers[stack_name].add_class("selected")

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

            # Post selection change message
            self.parent.post_message(
                SelectionChanged("stack", stack_name, self.selected_stack_data)
            )

    def select_container(self, container_id: str) -> None:
        """Select a container and update the footer.

        Args:
            container_id: ID of the container to select
        """
        logger.debug(f"select_container called with container_id: {container_id}")
        if container_id in self.container_rows:
            # Clear all selections using the shared method
            self.parent.clear_all_selections()

            # Clear any previous selection
            self.parent.selected_item = ("container", container_id)
            self.parent.selected_stack_data = None
            self.parent.selected_volume_data = None
            self.parent.selected_network_data = None

            # Find the container data
            stack_name, row_idx = self.container_rows[container_id]
            table = self.stack_tables[stack_name]

            # Store the selected row for custom rendering
            self._set_row_selection(table, container_id)

            # Add has-selection class and move cursor for visual feedback
            table.add_class("has-selection")
            if row_idx < table.row_count:
                table.move_cursor(row=row_idx)

            # Use cached full container data if available
            if container_id in self._container_data_cache:
                container_data = self._container_data_cache[container_id].copy()
                # Ensure stack name is included
                container_data["stack"] = stack_name
            else:
                # Fallback to getting data from the table
                container_data = {
                    "id": table.get_cell_at((row_idx, 0)),
                    "name": table.get_cell_at((row_idx, 1)),
                    "status": table.get_cell_at((row_idx, 2)),
                    "uptime": table.get_cell_at((row_idx, 3)),
                    "cpu": table.get_cell_at((row_idx, 4)),
                    "memory": table.get_cell_at((row_idx, 5)),
                    "pids": table.get_cell_at((row_idx, 6)),
                    "ports": table.get_cell_at((row_idx, 7)),
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

            # Post selection change message
            self.parent.post_message(
                SelectionChanged(
                    "container", container_id, self.selected_container_data
                )
            )
        else:
            logger.error(f"Container ID {container_id} not found in container_rows")

    def _clear_row_selection(self, table: DataTable) -> None:
        """Clear row selection by removing stored selection state."""
        if hasattr(table, "_selected_row_key"):
            delattr(table, "_selected_row_key")

    def _set_row_selection(self, table: DataTable, container_id: str) -> None:
        """Store the selected row key for custom rendering."""
        logger.debug(f"_set_row_selection called for container_id: {container_id}")
        # Store the selected row key on the table
        table._selected_row_key = container_id

    def clear_tables(self) -> None:
        """Clear all stack tables."""
        # Save which table has selection and which row before clearing
        selected_table_and_row = None
        for stack_name, table in self.stack_tables.items():
            if table.has_class("has-selection") and hasattr(table, "_selected_row_key"):
                selected_table_and_row = (stack_name, table._selected_row_key)
                break

        for table in self.stack_tables.values():
            table.clear()
            # Remove has-selection class when clearing
            table.remove_class("has-selection")
        self.container_rows.clear()

        # Store the selection info for restoration later
        if selected_table_and_row:
            self._pending_selection = selected_table_and_row

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
