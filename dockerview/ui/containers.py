import logging
from textual.widgets import DataTable, Static
from textual.binding import Binding
from textual.containers import VerticalScroll, Container
from textual.widget import Widget
from rich.text import Text
from rich.style import Style
from rich.console import RenderableType

logger = logging.getLogger('dockerview.containers')

class StackHeader(Static):
    """A header widget for Docker Compose stacks."""

    COMPONENT_CLASSES = {"header": "stack-header--header"}

    DEFAULT_CSS = """
    StackHeader {
        background: $panel;
        padding: 0 1;
        height: 3;
        border-bottom: solid $primary;
        margin: 0 0 0 0;
    }

    StackHeader:focus {
        background: $accent;
    }

    .stack-header--header {
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, stack_name: str, config_file: str, running: int, exited: int, total: int):
        super().__init__("")
        self.stack_name = stack_name
        self.expanded = False
        self.running = running
        self.exited = exited
        self.total = total
        self.config_file = config_file
        self.can_focus = True
        self._update_content()

    def _update_content(self) -> None:
        """Update the header content with current state."""
        icon = "▼" if self.expanded else "▶"
        running_text = Text(f"Running: {self.running}", style="green")
        exited_text = Text(f"Exited: {self.exited}", style="yellow")
        status = Text.assemble(
            running_text,
            ", ",
            exited_text,
            f", Total: {self.total}"
        )

        content = Text.assemble(
            Text(f"{icon} ", style="bold"),
            Text(self.stack_name, style="bold"),
            " ",
            Text(f"({self.config_file})", style="dim"),
            " - ",
            status
        )
        self.update(content)

    def on_focus(self) -> None:
        """Called when the header gets focus."""
        self.refresh()

    def on_blur(self) -> None:
        """Called when the header loses focus."""
        self.refresh()

    def toggle(self) -> None:
        """Toggle the expanded state."""
        self.expanded = not self.expanded
        self._update_content()

class ContainerList(VerticalScroll):
    """A widget for displaying Docker containers grouped by stack."""

    DEFAULT_CSS = """
    ContainerList {
        background: $surface;
        height: auto;
        border: round $primary;
        padding: 0 1;
    }

    StackHeader {
        layout: horizontal;
        width: 100%;
        height: 3;
    }

    .stack-container {
        layout: vertical;
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    DataTable {
        margin: 0 1 1 2;
        border: solid $primary;
        display: none;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "toggle_stack", "Expand/Collapse", show=True),
        Binding("space", "toggle_stack", "Expand/Collapse", show=False),
    ]

    def __init__(self):
        logger.info("Starting ContainerList initialization")
        try:
            super().__init__()
            logger.info("After ContainerList super().__init__()")
            self.stack_tables = {}  # Dictionary to store tables for each stack
            self.stack_headers = {}  # Dictionary to store headers for each stack
            self.container_rows = {}  # Dictionary to track container rows by ID
            self.current_focus = None
            self.expanded_stacks = set()  # Keep track of which stacks are expanded
            self._is_updating = False  # Track if we're in a batch update
            self._pending_clear = False  # Track if we need to clear during batch update
            logger.info("Finished ContainerList initialization")
        except Exception as e:
            logger.error(f"Error during ContainerList initialization: {str(e)}", exc_info=True)
            raise

    def create_stack_table(self, stack_name: str) -> DataTable:
        """Create a new DataTable for a stack."""
        table = DataTable()
        table.add_columns(
            "ID", "Name", "Status", "CPU %", "Memory", "PIDs"
        )
        table.cursor_type = "row"
        table.display = False  # Start collapsed
        table.can_focus = True
        return table

    def begin_update(self) -> None:
        """Begin a batch update to prevent UI flickering."""
        logger.info("Beginning batch update")
        self._is_updating = True
        # Only set pending_clear if this is the first update (no widgets mounted)
        self._pending_clear = len(self.children) == 0

        # Clear all tables but keep the table objects
        for table in self.stack_tables.values():
            table.clear()
        # Reset container tracking since all rows are now gone
        self.container_rows.clear()

    def end_update(self) -> None:
        """End a batch update and apply pending changes."""
        logger.info("Ending batch update")
        try:
            # Only do full clear and remount on first update
            if self._pending_clear:
                logger.debug("First update - doing full clear and remount")
                self.clear()

                # Create all containers first
                stack_containers = {}
                for stack_name in sorted(self.stack_headers.keys()):
                    header = self.stack_headers[stack_name]
                    table = self.stack_tables[stack_name]

                    # Create container
                    stack_container = Container(classes="stack-container")
                    stack_containers[stack_name] = (stack_container, header, table)

                # Now mount everything in order
                for stack_name, (container, header, table) in stack_containers.items():
                    # Mount the container to the main widget first
                    self.mount(container)
                    # Then mount the children to the container
                    container.mount(header)
                    container.mount(table)
                    # Set correct display state
                    table.styles.display = "block" if header.expanded else "none"

                self._pending_clear = False

                # Restore focus if needed
                if self.current_focus:
                    if self.current_focus in self.stack_headers:
                        self.stack_headers[self.current_focus].focus()
                    elif self.current_focus in self.stack_tables:
                        self.stack_tables[self.current_focus].focus()

            self._is_updating = False
        finally:
            # Only do a layout refresh if we did a full remount
            if len(self.children) > 0:
                self.refresh()

    def clear(self) -> None:
        """Clear all stacks and containers while preserving expansion states."""
        logger.info("Clearing ContainerList")
        # Save expanded states before clearing
        self.expanded_stacks = {
            name for name, header in self.stack_headers.items()
            if header.expanded
        }
        # Also save focused widget if any
        focused = self.screen.focused if self.screen else None
        if focused in self.stack_headers.values():
            self.current_focus = next(name for name, header in self.stack_headers.items() if header == focused)
        elif focused in self.stack_tables.values():
            self.current_focus = next(name for name, table in self.stack_tables.items() if table == focused)

        # Clear all widgets
        self.stack_tables.clear()
        self.stack_headers.clear()
        self.container_rows.clear()  # Clear container row tracking
        self.remove_children()

    def add_stack(self, name: str, config_file: str, running: int, exited: int, total: int) -> None:
        """Add or update a stack section."""
        logger.debug(f"Adding/updating stack: {name}")
        if name not in self.stack_tables:
            header = StackHeader(name, config_file, running, exited, total)
            table = self.create_stack_table(name)

            self.stack_headers[name] = header
            self.stack_tables[name] = table

            # Restore expanded state
            if name in self.expanded_stacks:
                header.expanded = True
                table.styles.display = "block"

            # Only mount if not in batch update
            if not self._is_updating:
                # Create and mount container first
                stack_container = Container(classes="stack-container")
                self.mount(stack_container)
                # Then mount children
                stack_container.mount(header)
                stack_container.mount(table)
        else:
            header = self.stack_headers[name]
            was_expanded = header.expanded  # Remember expansion state
            header.running = running
            header.exited = exited
            header.total = total
            header.config_file = config_file
            header.expanded = was_expanded  # Restore expansion state
            self.stack_tables[name].styles.display = "block" if was_expanded else "none"
            header._update_content()

    def add_container_to_stack(self, stack_name: str, container_data: dict) -> None:
        """Add or update a container in a specific stack's table."""
        logger.debug(f"Adding/updating container in stack {stack_name}: {container_data.get('name', 'unnamed')}")
        if stack_name not in self.stack_tables:
            self.add_stack(stack_name, "N/A", 0, 0, 0)

        table = self.stack_tables[stack_name]
        container_id = container_data["id"]

        # Prepare row data tuple
        row_data = (
            container_data["id"],
            container_data["name"],
            container_data["status"],
            container_data["cpu"],
            container_data["memory"],
            container_data["pids"]
        )

        try:
            # Always add as a new row since tables are cleared at the start of each update
            row_key = table.row_count
            table.add_row(*row_data)
            self.container_rows[container_id] = (stack_name, row_key)
            logger.debug(f"Added row {row_key} for container {container_id} with status {container_data['status']}")

        except Exception as e:
            logger.error(f"Error adding container {container_id}: {str(e)}", exc_info=True)
            return

        # If we're in a batch update and this is the last container,
        # mount all widgets at once
        if self._is_updating and self._pending_clear:
            try:
                for header in self.stack_headers.values():
                    self.mount(header)
                    if header.stack_name in self.expanded_stacks:
                        header.expanded = True
                for table in self.stack_tables.values():
                    self.mount(table)
                    if table in self.stack_tables.values():
                        stack_name = next(name for name, t in self.stack_tables.items() if t == table)
                        table.display = stack_name in self.expanded_stacks
                self._pending_clear = False

                # Restore focus if needed
                if self.current_focus:
                    if self.current_focus in self.stack_headers:
                        self.stack_headers[self.current_focus].focus()
                    elif self.current_focus in self.stack_tables:
                        self.stack_tables[self.current_focus].focus()
            except Exception as e:
                logger.error(f"Error mounting widgets: {str(e)}", exc_info=True)

    def action_toggle_stack(self) -> None:
        """Toggle the visibility of the selected stack's containers."""
        for stack_name, header in self.stack_headers.items():
            if header.has_focus:
                table = self.stack_tables[stack_name]
                header.toggle()
                table.styles.display = "block" if header.expanded else "none"
                break

    def on_mount(self) -> None:
        """Handle widget mount."""
        logger.info("Starting ContainerList mount")
        try:
            # Focus and expand the first header if available
            headers = list(self.stack_headers.values())
            if headers:
                first_header = headers[0]
                first_header.focus()
                first_header.expanded = True
                first_table = self.stack_tables[first_header.stack_name]
                first_table.display = True
                # If the first stack has containers, select the first one
                if first_table.row_count > 0:
                    first_table.focus()
                    first_table.move_cursor(row=0)
            logger.info("Finished ContainerList mount")
        except Exception as e:
            logger.error(f"Error during ContainerList mount: {str(e)}", exc_info=True)
            raise

    def action_cursor_up(self) -> None:
        """Handle up arrow key."""
        current = self.screen.focused
        if isinstance(current, DataTable):
            # If we're at the top of the table, focus the header
            if current.cursor_row == 0:
                stack_name = next(name for name, table in self.stack_tables.items() if table == current)
                self.stack_headers[stack_name].focus()
            else:
                current.action_cursor_up()
        elif isinstance(current, StackHeader):
            # Find previous visible widget
            current_idx = list(self.stack_headers.values()).index(current)
            if current_idx > 0:
                prev_header = list(self.stack_headers.values())[current_idx - 1]
                prev_table = self.stack_tables[prev_header.stack_name]
                if prev_header.expanded and prev_table.row_count > 0:
                    prev_table.focus()
                    prev_table.move_cursor(row=prev_table.row_count - 1)
                else:
                    prev_header.focus()

    def action_cursor_down(self) -> None:
        """Handle down arrow key."""
        current = self.screen.focused
        if isinstance(current, DataTable):
            # If we're at the bottom of the table, focus the next header
            if current.cursor_row >= current.row_count - 1:
                stack_name = next(name for name, table in self.stack_tables.items() if table == current)
                next_header_idx = list(self.stack_headers.keys()).index(stack_name) + 1
                if next_header_idx < len(self.stack_headers):
                    next_header = list(self.stack_headers.values())[next_header_idx]
                    next_header.focus()
            else:
                current.action_cursor_down()
        elif isinstance(current, StackHeader):
            # If expanded and has rows, focus the table
            table = self.stack_tables[current.stack_name]
            if current.expanded and table.row_count > 0:
                table.focus()
                table.move_cursor(row=0)
            else:
                # Focus next header
                current_idx = list(self.stack_headers.values()).index(current)
                if current_idx < len(self.stack_headers) - 1:
                    next_header = list(self.stack_headers.values())[current_idx + 1]
                    next_header.focus()