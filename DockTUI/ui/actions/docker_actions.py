"""Docker command execution actions for DockTUI."""

import logging
import threading
from typing import TYPE_CHECKING, Optional, Tuple

from ..base.container_list_base import DockerOperationCompleted

if TYPE_CHECKING:
    from DockTUI.app import DockTUIApp

logger = logging.getLogger("DockTUI.actions.docker")


class DockerActions:
    """Mixin class that provides Docker command execution functionality."""

    def __init__(self):
        """Initialize the Docker actions mixin."""
        # Track recreate operations to update log pane after refresh
        self._recreating_container_name = None
        self._recreating_item_type = None
        # Prevent concurrent volume operations
        self._volume_operation_in_progress = False
        self._volume_operation_lock = threading.Lock()

    def is_action_applicable(self: "DockTUIApp", action: str) -> bool:
        """Check if an action is applicable to the current selection.

        Args:
            action: The action to check (start, stop, restart, recreate, down, remove)

        Returns:
            bool: True if the action is applicable, False otherwise
        """
        # Check if there's a selection
        if not self.container_list or not self.container_list.selected_item:
            self.error_display.update(f"No item selected to {action}")
            return False

        item_type, item_id = self.container_list.selected_item

        # Check if action is applicable to the selected item type
        if action == "down":
            if item_type != "stack":
                self.error_display.update(
                    "Down command only works on stacks, not individual containers"
                )
                return False

        if action == "remove":
            if item_type != "container":
                self.error_display.update(
                    "Remove command only works on containers, not stacks"
                )
                return False

        # Check if recreate is allowed for stacks
        if action == "recreate" and item_type == "stack":
            if self.container_list.selected_stack_data:
                can_recreate = self.container_list.selected_stack_data.get(
                    "can_recreate", True
                )
                if not can_recreate:
                    stack_name = self.container_list.selected_stack_data.get(
                        "name", item_id
                    )
                    self.error_display.update(
                        f"Cannot recreate stack '{stack_name}': compose file not accessible"
                    )
                    return False

        return True

    def execute_docker_command(self: "DockTUIApp", command: str) -> None:
        """Execute a Docker command on the selected item.

        Args:
            command: The command to execute (start, stop, restart, recreate, remove)
        """
        # Note: Validation is now done in is_action_applicable before calling this method
        item_type, item_id = self.container_list.selected_item
        success = False

        # Track recreate operations so we can update log pane after refresh
        if command == "recreate":
            self._recreating_item_type = item_type
            if item_type == "container" and self.container_list.selected_container_data:
                self._recreating_container_name = (
                    self.container_list.selected_container_data.get("name")
                )
            elif item_type == "stack" and self.container_list.selected_stack_data:
                self._recreating_container_name = (
                    self.container_list.selected_stack_data.get("name")
                )
        else:
            self._recreating_container_name = None
            self._recreating_item_type = None

        try:
            if item_type == "container":
                item_name = (
                    self.container_list.selected_container_data.get("name", item_id)
                    if self.container_list.selected_container_data
                    else item_id
                )
                action_verb = (
                    "Recreating"
                    if command == "recreate"
                    else (
                        "Removing"
                        if command == "remove"
                        else f"{command.capitalize()}ing"
                    )
                )
                message = f"{action_verb} container: {item_name}"

                # Update UI immediately for container operations
                status_map = {
                    "start": "starting...",
                    "stop": "stopping...",
                    "restart": "restarting...",
                    "recreate": "recreating...",
                    "remove": "removing...",
                }

                if command in status_map:
                    self.container_list.update_container_status(
                        item_id, status_map[command]
                    )
                    self.refresh()

                # Execute command in background thread
                def execute_and_clear():
                    success, _ = self.docker.execute_container_command(item_id, command)
                    if success:
                        # Clear status override after a delay
                        self.call_from_thread(
                            self.set_timer,
                            3,
                            lambda: (
                                self.container_list.clear_status_override(item_id),
                                self.action_refresh(),
                            ),
                        )

                thread = threading.Thread(target=execute_and_clear)
                thread.daemon = True
                thread.start()

                success = True
            elif item_type == "stack":
                # Execute command on stack
                if self.container_list.selected_stack_data:
                    stack_name = self.container_list.selected_stack_data.get(
                        "name", item_id
                    )
                    config_file = self.container_list.selected_stack_data.get(
                        "config_file", ""
                    )

                    success = self.docker.execute_stack_command(
                        stack_name, config_file, command
                    )
                    if command.startswith("down"):
                        action_verb = "Taking down"
                        message = f"{action_verb} stack: {stack_name}"
                        if "remove_volumes" in command:
                            message += " (including volumes)"
                    else:
                        action_verb = (
                            "Recreating"
                            if command == "recreate"
                            else f"{command.capitalize()}ing"
                        )
                        message = f"{action_verb} stack: {stack_name}"
                else:
                    self.error_display.update(f"Missing stack data for {item_id}")
                    return
            else:
                self.error_display.update(f"Unknown item type: {item_type}")
                return

            if success:
                # For container operations, the status is shown in the container list
                # For stack operations, we still show the message
                if item_type == "stack":
                    # Show a temporary message in the error display
                    self.error_display.update(message)
                    # Schedule clearing the message after a few seconds
                    self.set_timer(3, lambda: self.error_display.update(""))
                # Schedule a refresh after a short delay to update the UI
                self.set_timer(2, self.action_refresh)
            else:
                self.error_display.update(
                    f"Error {command}ing {item_type}: {self.docker.last_error}"
                )
        except Exception as e:
            logger.error(f"Error executing {command} command: {str(e)}", exc_info=True)
            self.error_display.update(f"Error executing {command}: {str(e)}")

    def handle_post_recreate(
        self: "DockTUIApp", containers: list
    ) -> Tuple[Optional[str], Optional[dict]]:
        """Handle container selection after a recreate operation.

        Args:
            containers: List of container information

        Returns:
            Tuple of (new_container_id, new_container_data) if found, (None, None) otherwise
        """
        if not self._recreating_container_name or not self.log_pane:
            return None, None

        new_container_id = None
        new_container_data = None

        if self._recreating_item_type == "container":
            # Look for a container with the same name
            for container in containers:
                if container.get("name") == self._recreating_container_name:
                    new_container_id = container.get("id")
                    new_container_data = container
                    break

            if new_container_id and new_container_data:
                # Use select_container to properly update the UI and trigger all necessary events
                self.container_list.select_container(new_container_id)
                # Explicitly update the log pane with the new container data
                # This ensures the log pane gets the updated container info immediately
                self.log_pane.update_selection(
                    "container", new_container_id, new_container_data
                )

        elif self._recreating_item_type == "stack":
            # For stacks, just trigger a re-selection of the stack
            stack_name = self._recreating_container_name
            self.container_list.select_stack(stack_name)

        # Clear the tracking variables
        self._recreating_container_name = None
        self._recreating_item_type = None

        return new_container_id, new_container_data

    def execute_image_command(self: "DockTUIApp", command: str) -> None:
        """Execute a Docker command on the selected image.

        Args:
            command: The command to execute (remove_image, remove_unused_images)
        """
        if command == "remove_image":
            if not self.container_list or not self.container_list.selected_item:
                self.error_display.update("No image selected")
                return

            item_type, item_id = self.container_list.selected_item
            if item_type != "image":
                self.error_display.update("Selected item is not an image")
                return

            image_data = self.container_list.image_manager.selected_image_data
            if not image_data:
                self.error_display.update("No image data available")
                return

            container_names = image_data.get("container_names", [])
            if container_names:
                self.error_display.update(
                    f"Cannot remove image: in use by {len(container_names)} container(s)"
                )
                return

            next_selection = (
                self.container_list.image_manager.get_next_selection_after_removal(
                    {item_id}
                )
            )

            success, message = self.docker.remove_image(item_id)
            if success:
                self.error_display.update(message)
                self.container_list.image_manager.mark_image_as_removed(item_id)

                if next_selection:
                    self.container_list.image_manager.select_image(next_selection)
                    self.container_list.image_manager._preserve_selected_image_id = (
                        next_selection
                    )

                self.set_timer(2.0, self.action_refresh)
            else:
                self.error_display.update(f"Error: {message}")

        elif command == "remove_unused_images":
            unused_images = self.docker.get_unused_images()
            unused_count = len(unused_images)

            if unused_count == 0:
                self.error_display.update("No unused images found")
                return

            unused_image_ids = {img["id"] for img in unused_images}

            next_selection = (
                self.container_list.image_manager.get_next_selection_after_removal(
                    unused_image_ids
                )
            )

            success, message, removed_count = self.docker.remove_unused_images()
            if success:
                self.error_display.update(message)

                for img in unused_images:
                    self.container_list.image_manager.mark_image_as_removed(img["id"])

                if next_selection:
                    self.container_list.image_manager.select_image(next_selection)
                    self.container_list.image_manager._preserve_selected_image_id = (
                        next_selection
                    )

                self.set_timer(2.0, self.action_refresh)
            else:
                self.error_display.update(f"Error: {message}")

    def execute_volume_command(self: "DockTUIApp", command: str) -> None:
        """Execute a Docker command on volumes.

        Args:
            command: The command to execute (remove_volume, remove_unused_volumes)
        """
        # Check if a volume operation is already in progress
        with self._volume_operation_lock:
            if self._volume_operation_in_progress:
                self.error_display.update("A volume operation is already in progress")
                return
            self._volume_operation_in_progress = True

        try:
            if command == "remove_volume":
                if not self.container_list or not self.container_list.selected_item:
                    self.error_display.update("No volume selected")
                    with self._volume_operation_lock:
                        self._volume_operation_in_progress = False
                    return

                item_type, item_id = self.container_list.selected_item
                if item_type != "volume":
                    self.error_display.update("Selected item is not a volume")
                    with self._volume_operation_lock:
                        self._volume_operation_in_progress = False
                    return

                volume_data = self.container_list.volume_manager.selected_volume_data
                can_remove, error_msg = self._is_volume_removable(volume_data)

                if not can_remove:
                    self.error_display.update(error_msg)
                    with self._volume_operation_lock:
                        self._volume_operation_in_progress = False
                    return

                def remove_volume_thread():
                    """Execute volume removal in background thread."""
                    try:
                        success, message = self.docker.remove_volume(item_id)

                        # Post completion message from the thread
                        self.app.post_message(
                            DockerOperationCompleted(
                                operation="remove_volume",
                                success=success,
                                message=message,
                                item_id=item_id,
                            )
                        )
                    finally:
                        # Always clear the operation flag
                        with self._volume_operation_lock:
                            self._volume_operation_in_progress = False

                # Start the operation in a background thread
                thread = threading.Thread(target=remove_volume_thread, daemon=True)
                thread.start()

                # Show immediate feedback
                self.error_display.update(f"Removing volume '{item_id}'...")

            elif command == "remove_unused_volumes":
                unused_volumes = self.docker.get_unused_volumes()
                unused_count = len(unused_volumes)

                if unused_count == 0:
                    self.error_display.update("No unused volumes found")
                    with self._volume_operation_lock:
                        self._volume_operation_in_progress = False
                    return

                def remove_unused_volumes_thread():
                    """Execute unused volume removal in background thread."""
                    try:
                        # Store volume names before removal
                        volume_names = [v["name"] for v in unused_volumes]
                        success, message, removed_count = (
                            self.docker.remove_unused_volumes()
                        )

                        # Post completion message from the thread
                        self.app.post_message(
                            DockerOperationCompleted(
                                operation="remove_unused_volumes",
                                success=success,
                                message=message,
                                item_ids=volume_names,  # Pass volume names as list
                            )
                        )
                    finally:
                        # Always clear the operation flag
                        with self._volume_operation_lock:
                            self._volume_operation_in_progress = False

                # Start the operation in a background thread
                thread = threading.Thread(
                    target=remove_unused_volumes_thread, daemon=True
                )
                thread.start()

                # Show immediate feedback
                self.error_display.update(f"Removing {unused_count} unused volumes...")
        except Exception as e:
            logger.error(f"Error in execute_volume_command: {e}")
            self.error_display.update(f"Error: {str(e)}")
            with self._volume_operation_lock:
                self._volume_operation_in_progress = False
