"""Navigation and cursor handling for the container list widget."""

import logging
from typing import TYPE_CHECKING, Optional

from textual.widgets import DataTable

from ..widgets.headers import StackHeader

if TYPE_CHECKING:
    from ..containers import ContainerList

logger = logging.getLogger("DockTUI.navigation_handler")


class NavigationHandler:
    """Handles keyboard navigation and cursor movement."""

    def __init__(self, container_list: "ContainerList"):
        """Initialize the navigation handler.

        Args:
            container_list: The parent ContainerList widget
        """
        self.container_list = container_list

    def handle_cursor_up(self) -> None:
        """Handle up arrow key navigation."""
        current = self.container_list.screen.focused

        # Check if the search input is currently focused
        if hasattr(current, "id") and current.id == "search-input":
            return

        if isinstance(current, DataTable):
            self._handle_table_up(current)
        elif isinstance(current, StackHeader):
            self._handle_header_up(current)

    def handle_cursor_down(self) -> None:
        """Handle down arrow key navigation."""
        current = self.container_list.screen.focused

        # Check if the search input is currently focused
        if hasattr(current, "id") and current.id == "search-input":
            return

        if isinstance(current, DataTable):
            self._handle_table_down(current)
        elif isinstance(current, StackHeader):
            self._handle_header_down(current)

    def _handle_table_up(self, table: DataTable) -> None:
        """Handle up navigation within a table."""
        # If we're at the top of the table, focus the header
        if table.cursor_row == 0:
            stack_name = self._find_table_stack(table)
            if stack_name:
                header = self.container_list.stack_headers[stack_name]
                header.focus()
                self.container_list.select_stack(stack_name)
        else:
            table.action_cursor_up()
            # Update selection based on new cursor position
            row = table.cursor_row
            stack_name = self._find_table_stack(table)
            if stack_name:
                container_id = table.get_cell_at((row, 0))
                self.container_list.select_container(container_id)

    def _handle_table_down(self, table: DataTable) -> None:
        """Handle down navigation within a table."""
        # If we're at the bottom of the table, focus the next header
        if table.cursor_row >= table.row_count - 1:
            stack_name = self._find_table_stack(table)
            if stack_name:
                next_header_idx = (
                    list(self.container_list.stack_headers.keys()).index(stack_name) + 1
                )
                if next_header_idx < len(self.container_list.stack_headers):
                    next_header = list(self.container_list.stack_headers.values())[
                        next_header_idx
                    ]
                    next_header.focus()
                    self.container_list.select_stack(
                        list(self.container_list.stack_headers.keys())[next_header_idx]
                    )
        else:
            table.action_cursor_down()
            # Update selection based on new cursor position
            row = table.cursor_row
            stack_name = self._find_table_stack(table)
            if stack_name:
                container_id = table.get_cell_at((row, 0))
                self.container_list.select_container(container_id)

    def _handle_header_up(self, current: StackHeader) -> None:
        """Handle up navigation from a header."""
        # Find previous visible widget
        current_idx = list(self.container_list.stack_headers.values()).index(current)
        if current_idx > 0:
            prev_header = list(self.container_list.stack_headers.values())[
                current_idx - 1
            ]
            prev_table = self.container_list.stack_tables[prev_header.stack_name]
            if prev_header.expanded and prev_table.row_count > 0:
                prev_table.focus()
                prev_table.move_cursor(row=prev_table.row_count - 1)
                # Update selection to the container
                container_id = prev_table.get_cell_at((prev_table.row_count - 1, 0))
                self.container_list.select_container(container_id)
            else:
                prev_header.focus()
                self.container_list.select_stack(prev_header.stack_name)

    def _handle_header_down(self, current: StackHeader) -> None:
        """Handle down navigation from a header."""
        # If expanded and has rows, focus the table
        stack_name = current.stack_name
        table = self.container_list.stack_tables[stack_name]
        if current.expanded and table.row_count > 0:
            table.focus()
            table.move_cursor(row=0)
            # Update selection to the first container
            container_id = table.get_cell_at((0, 0))
            self.container_list.select_container(container_id)
        else:
            # Focus next header
            current_idx = list(self.container_list.stack_headers.values()).index(
                current
            )
            if current_idx < len(self.container_list.stack_headers) - 1:
                next_header = list(self.container_list.stack_headers.values())[
                    current_idx + 1
                ]
                next_header.focus()
                self.container_list.select_stack(next_header.stack_name)

    def _find_table_stack(self, table: DataTable) -> Optional[str]:
        """Find which stack a table belongs to."""
        for stack_name, stack_table in self.container_list.stack_tables.items():
            if stack_table == table:
                return stack_name
        return None

    def restore_selection(self) -> None:
        """Restore the previously selected item after a refresh."""
        try:
            if self.container_list.selected_item is None:
                return

            # Check if the search input is currently focused
            if self.container_list.screen and self.container_list.screen.focused:
                focused_widget = self.container_list.screen.focused
                if (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    self.container_list.footer_formatter.update_footer_with_selection()
                    return

            item_type, item_id = self.container_list.selected_item

            if (
                item_type == "image"
                and item_id in self.container_list.image_manager.image_rows
            ):
                if self.container_list.image_manager.images_table:
                    self.container_list.image_manager.images_table.focus()
                    row_index = self.container_list.image_manager.image_rows[item_id]
                    self.container_list.image_manager.images_table.move_cursor(
                        row=row_index
                    )
                self.container_list.footer_formatter.update_footer_with_selection()

            elif (
                item_type == "volume" and item_id in self.container_list.volume_headers
            ):
                header = self.container_list.volume_headers[item_id]
                header.focus()
                self.container_list.footer_formatter.update_footer_with_selection()

            elif item_type == "stack" and item_id in self.container_list.stack_headers:
                header = self.container_list.stack_headers[item_id]
                header.focus()
                self.container_list.footer_formatter.update_footer_with_selection()

            elif (
                item_type == "container"
                and item_id in self.container_list.container_rows
            ):
                stack_name, row_idx = self.container_list.container_rows[item_id]
                if stack_name in self.container_list.stack_tables:
                    table = self.container_list.stack_tables[stack_name]
                    header = self.container_list.stack_headers[stack_name]

                    if not header.expanded:
                        header.expanded = True
                        table.styles.display = "block"
                        header._update_content()

                    table.focus()
                    table.move_cursor(row=row_idx)
                    self.container_list.footer_formatter.update_footer_with_selection()
        except Exception as e:
            logger.error(f"Error restoring selection: {str(e)}", exc_info=True)

    def update_cursor_visibility(self) -> None:
        """Update cursor visibility and focus based on current selection."""
        try:
            # Check if the search input is currently focused
            if self.container_list.screen and self.container_list.screen.focused:
                focused_widget = self.container_list.screen.focused
                if (
                    hasattr(focused_widget, "id")
                    and focused_widget.id == "search-input"
                ):
                    return

            # If a container is selected, focus its table and position the cursor
            if (
                self.container_list.selected_item
                and self.container_list.selected_item[0] == "container"
            ):
                container_id = self.container_list.selected_item[1]
                if container_id in self.container_list.container_rows:
                    stack_name, row_idx = self.container_list.container_rows[
                        container_id
                    ]
                    if stack_name in self.container_list.stack_tables:
                        table = self.container_list.stack_tables[stack_name]
                        table.focus()
                        if table.cursor_row != row_idx:
                            table.move_cursor(row=row_idx)

            # If a stack is selected, focus its header
            elif (
                self.container_list.selected_item
                and self.container_list.selected_item[0] == "stack"
            ):
                stack_name = self.container_list.selected_item[1]
                if stack_name in self.container_list.stack_headers:
                    header = self.container_list.stack_headers[stack_name]
                    header.focus()

            # If an image is selected, focus its header
            elif (
                self.container_list.selected_item
                and self.container_list.selected_item[0] == "image"
            ):
                image_id = self.container_list.selected_item[1]
                if image_id in self.container_list.image_headers:
                    header = self.container_list.image_headers[image_id]
                    header.focus()

            # If a volume is selected, focus its header
            elif (
                self.container_list.selected_item
                and self.container_list.selected_item[0] == "volume"
            ):
                volume_name = self.container_list.selected_item[1]
                if volume_name in self.container_list.volume_headers:
                    header = self.container_list.volume_headers[volume_name]
                    header.focus()

        except Exception as e:
            logger.error(
                f"Error updating cursor visibility and focus: {str(e)}", exc_info=True
            )
