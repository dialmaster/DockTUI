"""Keyboard navigation, focus and selection restoration for the container list."""

import logging
from typing import TYPE_CHECKING, List, Optional

from textual.coordinate import Coordinate
from textual.widget import Widget
from textual.widgets import DataTable

from ..base.container_list_base import focus_is_inside
from ..widgets.headers import NetworkHeader, StackHeader

if TYPE_CHECKING:
    from ..containers import ContainerList

logger = logging.getLogger("DockTUI.navigation_handler")


class NavigationHandler:
    """Moves focus and selection through the left pane with the keyboard.

    The left pane is treated as one linear list of focusable widgets (section
    headers, stack/network headers and the rows of every table), in display
    order. Up/Down walk that list; tables are entered row by row.
    """

    def __init__(self, container_list: "ContainerList"):
        """Initialize the navigation handler.

        Args:
            container_list: The parent ContainerList widget
        """
        self.container_list = container_list

    # ------------------------------------------------------------------
    # Focus helpers
    # ------------------------------------------------------------------

    def _focused(self) -> Optional[Widget]:
        screen = self.container_list.screen
        return screen.focused if screen else None

    def focus_is_in_list(self) -> bool:
        """True when nothing is focused or focus is inside the container list."""
        return focus_is_inside(self.container_list, self._focused())

    def _focusables(self) -> List[Widget]:
        """Left-pane widgets that can currently take focus, in display order."""
        screen = self.container_list.screen
        if screen is None:
            return []
        return [
            widget
            for widget in screen.focus_chain
            if self.container_list in widget.ancestors
        ]

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def handle_cursor_up(self) -> None:
        """Handle up arrow key navigation."""
        self._move(-1)

    def handle_cursor_down(self) -> None:
        """Handle down arrow key navigation."""
        self._move(1)

    def _move(self, step: int) -> None:
        current = self._focused()
        if isinstance(current, DataTable) and current.row_count:
            target_row = current.cursor_row + step
            if 0 <= target_row < current.row_count:
                current.move_cursor(row=target_row)
                self.select_row_at_cursor(current)
                return
        self._focus_neighbor(current, step)

    def _focus_neighbor(self, current: Optional[Widget], step: int) -> None:
        chain = self._focusables()
        if not chain:
            return
        if current in chain:
            index = chain.index(current) + step
        else:
            index = 0 if step > 0 else len(chain) - 1
        while 0 <= index < len(chain):
            if self.focus_widget(chain[index], enter_from_end=step < 0):
                return
            index += step

    def focus_widget(self, widget: Widget, enter_from_end: bool = False) -> bool:
        """Focus a left-pane widget and select what it represents.

        Returns:
            bool: False if the widget should be skipped (an empty table)
        """
        container_list = self.container_list
        if isinstance(widget, DataTable):
            if widget.row_count == 0:
                return False
            widget.focus()
            widget.move_cursor(row=widget.row_count - 1 if enter_from_end else 0)
            self.select_row_at_cursor(widget)
            return True

        widget.focus()
        if isinstance(widget, StackHeader):
            container_list.select_stack(widget.stack_name)
        elif isinstance(widget, NetworkHeader):
            container_list.select_network(widget.network_name)
        return True

    def focus_selected(self) -> None:
        """Focus the widget showing the current selection, or the first item."""
        widget = self._widget_for_selection()
        if widget is not None and widget in self._focusables():
            widget.focus()
            return
        self._focus_neighbor(None, 1)

    def _widget_for_selection(self) -> Optional[Widget]:
        container_list = self.container_list
        if not container_list.selected_item:
            return None
        item_type, item_id = container_list.selected_item
        if item_type == "container" and item_id in container_list.container_rows:
            stack_name, _ = container_list.container_rows[item_id]
            return container_list.stack_tables.get(stack_name)
        if item_type == "stack":
            return container_list.stack_headers.get(item_id)
        if item_type == "network":
            return container_list.network_headers.get(item_id)
        if item_type == "image":
            return container_list.image_manager.images_table
        if item_type == "volume":
            return container_list.volume_manager.volume_table
        return None

    # ------------------------------------------------------------------
    # Selection from table cursors
    # ------------------------------------------------------------------

    def select_row_at_cursor(self, table: DataTable) -> None:
        """Select the item under a table's cursor, if it changed."""
        container_list = self.container_list
        row = table.cursor_row
        if row is None or row < 0 or row >= table.row_count:
            return

        if table in container_list.stack_tables.values():
            container_id = str(table.get_cell_at((row, 0)))
            if container_list.selected_item != ("container", container_id):
                container_list.select_container(container_id)
        elif table is container_list.image_manager.images_table:
            row_key = self._row_key_at(table, row)
            if row_key is not None and container_list.selected_item != (
                "image",
                row_key.value,
            ):
                container_list.select_image(row_key.value)
        elif table is container_list.volume_manager.volume_table:
            row_key = self._row_key_at(table, row)
            volume_name = next(
                (
                    name
                    for name, key in container_list.volume_rows.items()
                    if key == row_key
                ),
                None,
            )
            if volume_name and container_list.selected_item != ("volume", volume_name):
                container_list.select_volume(volume_name)
        # Network tables keep the network selected; Enter jumps to the container.

    @staticmethod
    def _row_key_at(table: DataTable, row: int):
        try:
            return table.coordinate_to_cell_key(Coordinate(row, 0)).row_key
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Refresh support
    # ------------------------------------------------------------------

    def restore_selection(self) -> None:
        """Re-apply selection styling and cursor position after a refresh.

        Tables are rebuilt on every refresh, so the highlighted row and the
        cursor have to be put back. Focus is deliberately left alone: the
        user may be working in the log pane.
        """
        container_list = self.container_list
        try:
            if container_list.selected_item is None:
                return

            container_list.clear_all_selections()
            item_type, item_id = container_list.selected_item

            if (
                item_type == "image"
                and item_id in container_list.image_manager.image_rows
            ):
                table = container_list.image_manager.images_table
                if table:
                    row_index = container_list.image_manager.image_rows[item_id]
                    if 0 <= row_index < table.row_count:
                        table.add_class("has-selection")
                        table.move_cursor(row=row_index)

            elif item_type == "volume" and item_id in container_list.volume_rows:
                table = container_list.volume_manager.volume_table
                if table:
                    row_index = self._volume_row_index(item_id)
                    if row_index is not None:
                        table.add_class("has-selection")
                        table.move_cursor(row=row_index)

            elif item_type == "stack" and item_id in container_list.stack_headers:
                container_list.stack_headers[item_id].add_class("selected")

            elif item_type == "network" and item_id in container_list.network_headers:
                container_list.network_headers[item_id].add_class("selected")

            elif item_type == "container" and item_id in container_list.container_rows:
                stack_name, row_idx = container_list.container_rows[item_id]
                if stack_name in container_list.stack_tables:
                    table = container_list.stack_tables[stack_name]
                    header = container_list.stack_headers[stack_name]
                    if not header.expanded:
                        header.expanded = True
                        table.styles.display = "block"
                        header._update_content()
                    container_list.stack_manager._set_row_selection(table, item_id)
                    table.add_class("has-selection")
                    if 0 <= row_idx < table.row_count:
                        table.move_cursor(row=row_idx)

            container_list.footer_formatter.update_footer_with_selection()
        except Exception as e:
            logger.error(f"Error restoring selection: {str(e)}", exc_info=True)

    def _volume_row_index(self, volume_name: str) -> Optional[int]:
        table = self.container_list.volume_manager.volume_table
        row_key = self.container_list.volume_rows.get(volume_name)
        if table is None or row_key is None:
            return None
        try:
            return table.get_row_index(row_key)
        except Exception:
            return None

    def update_cursor_visibility(self) -> None:
        """Give focus to the selected item, but only when nothing has focus.

        This happens after the focused widget was removed (for example a stack
        that disappeared). While the user has focus somewhere, whether in the
        list or in the log pane, it must not be moved by a refresh.
        """
        try:
            if self._focused() is not None:
                return
            widget = self._widget_for_selection()
            if widget is not None and widget in self._focusables():
                widget.focus()
        except Exception as e:
            logger.error(
                f"Error updating cursor visibility and focus: {str(e)}", exc_info=True
            )
