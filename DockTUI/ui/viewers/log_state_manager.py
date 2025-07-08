"""Manages state tracking for the log pane.

This includes container state, header updates, auto-follow state management,
and dropdown state preservation.
"""

import logging
from typing import Optional, Tuple

from rich.text import Text

logger = logging.getLogger("DockTUI.log_state_manager")


class LogStateManager:
    """Manages state tracking for the log pane."""

    def __init__(self, parent):
        """Initialize the LogStateManager.

        Args:
            parent: The parent LogPane instance
        """
        self.parent = parent

        # State management
        self.current_item: Optional[Tuple[str, str]] = (
            None  # ("container", id) or ("stack", name)
        )
        self.current_item_data: Optional[dict] = None
        self.auto_follow: bool = True

        # UI component references (will be set by parent)
        self.header = None
        self.log_display = None

    def set_ui_components(self, header, log_display):
        """Set UI component references.

        Args:
            header: The header widget
            log_display: The log display widget
        """
        self.header = header
        self.log_display = log_display

    def set_current_item(
        self, item_type: str, item_id: str, item_data: dict
    ) -> Tuple[str, str]:
        """Set the current item and data.

        Args:
            item_type: Type of item ("container" or "stack")
            item_id: ID of the item
            item_data: Dictionary containing item information

        Returns:
            Tuple of (item_type, item_id)
        """
        self.current_item = (item_type, item_id)
        self.current_item_data = item_data
        return self.current_item

    def clear_current_item(self):
        """Clear the current item state."""
        self.current_item = None
        self.current_item_data = None

    def is_same_item(self, item_type: str, item_id: str) -> bool:
        """Check if the given item is the same as the current item.

        Args:
            item_type: Type of item to check
            item_id: ID of the item to check

        Returns:
            True if it's the same item, False otherwise
        """
        return self.current_item == (item_type, item_id)

    def is_container_running(self, status: str) -> bool:
        """Check if a container status indicates it's running.

        Args:
            status: Container status string

        Returns:
            True if container is running, False otherwise
        """
        if not status:
            return False
        status_lower = status.lower()
        return "running" in status_lower or "up" in status_lower

    def is_container_stopped(self, status: str) -> bool:
        """Check if a container status indicates it's stopped.

        Args:
            status: Container status string

        Returns:
            True if container is stopped, False otherwise
        """
        if not status:
            return True
        status_lower = status.lower()
        return any(
            state in status_lower
            for state in ["exited", "stopped", "dead", "removing", "created"]
        )

    def check_status_change(self, new_item_data: dict) -> Optional[str]:
        """Check if container status has changed.

        Args:
            new_item_data: New item data to compare

        Returns:
            "started" if container started, "stopped" if stopped, None if no change
        """
        if not self.current_item_data:
            return None

        old_status = self.current_item_data.get("status", "").lower()
        new_status = new_item_data.get("status", "").lower()

        # Check if container stopped
        if self.is_container_running(old_status) and self.is_container_stopped(
            new_status
        ):
            return "stopped"

        # Check if container started
        if self.is_container_stopped(old_status) and self.is_container_running(
            new_status
        ):
            return "started"

        return None

    def update_header(self, text: str):
        """Update the header text.

        Args:
            text: The header text to display
        """
        if self.header:
            self.header.update(text)

    def update_header_with_status(self, item_name: str, status: str):
        """Update header with container status indicator.

        Args:
            item_name: Name of the container
            status: Container status
        """
        if not self.header:
            return

        if self.is_container_stopped(status):
            # Create a rich Text object with red color for NOT RUNNING
            header_text = Text()
            header_text.append("📋 Log Pane - Container: ")
            header_text.append(item_name)
            header_text.append(" - ", style="")
            header_text.append("NOT RUNNING", style="red bold")
            self.header.update(header_text)
        else:
            self.header.update(f"📋 Log Pane - Container: {item_name}")

    def update_header_for_item(
        self, item_type: str, item_id: str, item_data: dict
    ) -> bool:
        """Update the header based on the selected item type.

        Args:
            item_type: Type of item
            item_id: ID of the item
            item_data: Dictionary containing item information

        Returns:
            True if the item type has logs, False otherwise
        """
        if not self.header:
            return True

        # Handle None item_data
        if item_data is None:
            item_data = {}
        item_name = item_data.get("name", item_id)

        if item_type == "container":
            # Check if container is stopped and add status indicator
            status = item_data.get("status", "")
            self.update_header_with_status(item_name, status)
            return True
        elif item_type == "stack":
            self.update_header(f"📋 Log Pane - Stack: {item_name}")
            return True
        elif item_type == "network":
            self.update_header(f"📋 Log Pane - Network: {item_name}")
            return False  # Networks don't have logs
        elif item_type == "image":
            self.update_header(f"📋 Log Pane - Image: {item_id[:12]}")
            return False  # Images don't have logs
        elif item_type == "volume":
            self.update_header(f"📋 Log Pane - Volume: {item_name}")
            return False  # Volumes don't have logs
        else:
            self.update_header("📋 Log Pane - Unknown Selection")
            return True

    def update_header_for_no_selection(self):
        """Update header to show no selection state."""
        self.update_header("📋 Log Pane - No Selection")

    def set_auto_follow(self, enabled: bool):
        """Set the auto-follow state.

        Args:
            enabled: Whether auto-follow should be enabled
        """
        self.auto_follow = enabled
        # Also update the log display's auto_follow property
        if self.log_display:
            self.log_display.auto_follow = enabled

    def should_auto_scroll(self) -> bool:
        """Check if auto-scrolling should be performed.

        Returns:
            True if auto-follow is enabled
        """
        return self.auto_follow

    def handle_container_status_change(
        self, status_change: str, item_name: str, status: str
    ):
        """Handle container status change by updating the header.

        Args:
            status_change: Type of change ("started" or "stopped")
            item_name: Name of the container
            status: Current container status
        """
        if status_change == "stopped":
            # Update header to show NOT RUNNING
            self.update_header_with_status(item_name, status)
        elif status_change == "started":
            # Update header for running container
            self.update_header(f"📋 Log Pane - Container: {item_name}")

    def save_dropdown_states(self, tail_select, since_select) -> dict:
        """Save the expanded state of dropdown widgets.

        Args:
            tail_select: The tail select dropdown widget
            since_select: The since select dropdown widget

        Returns:
            dict: Dictionary containing the expanded state of each dropdown
        """
        states = {
            "tail_expanded": False,
            "since_expanded": False,
        }

        # Check if dropdowns exist and save their expanded state
        if tail_select:
            states["tail_expanded"] = tail_select.expanded
        if since_select:
            states["since_expanded"] = since_select.expanded

        logger.debug(f"Saved dropdown states: {states}")
        return states

    def restore_dropdown_states(self, states: dict, tail_select, since_select) -> None:
        """Restore the expanded state of dropdown widgets.

        Args:
            states: Dictionary containing the saved dropdown states
            tail_select: The tail select dropdown widget
            since_select: The since select dropdown widget
        """
        if not states:
            return

        # Restore tail dropdown state
        if states.get("tail_expanded") and tail_select:
            logger.debug("Restoring tail dropdown expanded state")
            tail_select.action_show_overlay()

        # Restore since dropdown state
        elif states.get("since_expanded") and since_select:
            logger.debug("Restoring since dropdown expanded state")
            since_select.action_show_overlay()
