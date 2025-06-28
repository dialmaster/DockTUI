"""Refresh and UI update actions for DockTUI."""

import logging
from typing import TYPE_CHECKING, Dict, List, Tuple

from textual import work

if TYPE_CHECKING:
    from DockTUI.app import DockTUIApp

logger = logging.getLogger("DockTUI.actions.refresh")


class RefreshActions:
    """Mixin class that provides refresh and UI update functionality."""

    def __init__(self):
        """Initialize the refresh actions mixin."""
        self._refresh_count = 0

    async def refresh_containers(self: "DockTUIApp") -> None:
        """Refresh the container list asynchronously.

        Fetches updated container and stack information in a background thread,
        then updates the UI with the new data.
        """
        if not all([self.container_list, self.error_display]):
            logger.error("Error: Widgets not properly initialized")
            return

        try:
            # Add refreshing indicator to the existing title
            if "Refreshing..." not in self.title:
                self.title = self.title + "\nRefreshing..."

            # Start the worker but don't block waiting for it
            # Textual's worker pattern will call the function and then process the results
            # when they're ready without blocking the UI
            self._refresh_containers_worker(self._handle_refresh_results)

        except Exception as e:
            logger.error(f"Error during refresh: {str(e)}", exc_info=True)
            self.error_display.update(f"Error refreshing: {str(e)}")

    @work(thread=True)
    def _refresh_containers_worker(
        self: "DockTUIApp", callback
    ) -> Tuple[Dict, Dict, Dict, List]:
        """Worker function to fetch network, stack, volume and container data in a background thread.

        Args:
            callback: Function to call with the results when complete

        Returns:
            Tuple[Dict, Dict, Dict, Dict, List]: A tuple containing:
                - Dict: Mapping of network names to network information
                - Dict: Mapping of stack names to stack information
                - Dict: Mapping of image IDs to image information
                - Dict: Mapping of volume names to volume information
                - List: List of container information dictionaries
        """
        try:
            # Get networks, stacks, images, volumes and containers in the thread
            networks = self.docker.get_networks()
            stacks = self.docker.get_compose_stacks()
            images = self.docker.get_images()
            volumes = self.docker.get_volumes()
            containers = self.docker.get_containers()

            # Call the callback with the results
            # This will be executed in the main thread after the worker completes
            self.call_from_thread(
                callback, networks, stacks, images, volumes, containers
            )

            return networks, stacks, images, volumes, containers
        except Exception as e:
            logger.error(f"Error in refresh worker: {str(e)}", exc_info=True)
            self.call_from_thread(
                self.error_display.update, f"Error refreshing: {str(e)}"
            )
            return {}, {}, {}, {}, []

    def _handle_refresh_results(
        self: "DockTUIApp", networks, stacks, images, volumes, containers
    ):
        """Handle the results from the refresh worker when they're ready.

        Args:
            networks: Dictionary of network information
            stacks: Dictionary of stack information
            images: Dictionary of image information
            volumes: Dictionary of volume information
            containers: List of container information
        """
        try:
            # Update UI with the results
            if hasattr(self.docker, "last_error") and self.docker.last_error:
                self.error_display.update(f"Error: {self.docker.last_error}")
            else:
                self.error_display.update("")

            # Update UI directly without creating a new task
            # Since we're already in the main thread via call_from_thread,
            # we can safely update the UI synchronously
            self._sync_update_ui_with_results(
                networks, stacks, images, volumes, containers
            )

        except Exception as e:
            logger.error(f"Error handling refresh results: {str(e)}", exc_info=True)
            self.error_display.update(f"Error refreshing: {str(e)}")

    def _sync_update_ui_with_results(
        self: "DockTUIApp", networks, stacks, images, volumes, containers
    ):
        """Synchronously update the UI with the results from the refresh worker.

        Args:
            networks: Dictionary of network information
            stacks: Dictionary of stack information
            images: Dictionary of image information
            volumes: Dictionary of volume information
            containers: List of container information
        """

        try:
            # Begin a batch update to prevent UI flickering
            self.container_list.begin_update()

            try:
                # Process all stacks first
                for stack_name, stack_info in stacks.items():
                    self.container_list.add_stack(
                        stack_name,
                        stack_info["config_file"],
                        stack_info["running"],
                        stack_info["exited"],
                        stack_info["total"],
                        stack_info.get("can_recreate", True),
                        stack_info.get("has_compose_file", True),
                    )

                # Process all images next
                if images:
                    for image_id, image_info in images.items():
                        self.container_list.add_image(image_info)
                else:
                    # No images found, show message if section is expanded
                    if (
                        not self.container_list.images_section_collapsed
                        and self.container_list.images_container
                    ):
                        self.container_list.image_manager.show_no_images_message()

                if self.container_list.image_manager._preserve_selected_image_id:
                    preserved_id = (
                        self.container_list.image_manager._preserve_selected_image_id
                    )
                    if preserved_id in self.container_list.image_manager.image_rows:
                        self.container_list.image_manager.select_image(preserved_id)
                    self.container_list.image_manager._preserve_selected_image_id = None

                # Process all volumes after images
                for volume_name, volume_info in volumes.items():
                    self.container_list.add_volume(volume_info)

                # Process all networks after volumes
                for network_name, network_info in networks.items():
                    self.container_list.add_network(network_info)

                    # Add containers to the network
                    for container_info in network_info["connected_containers"]:
                        self.container_list.add_container_to_network(
                            network_name, container_info
                        )

                # Process all containers in a single batch
                # Sort containers by stack to minimize UI updates
                sorted_containers = sorted(containers, key=lambda c: c["stack"])
                for container in sorted_containers:
                    self.container_list.add_container_to_stack(
                        container["stack"], container
                    )

            finally:
                # Always end the update, even if cancelled
                self.container_list.end_update()

            # Handle container recreation - update log pane if needed
            if hasattr(self, "handle_post_recreate"):
                self.handle_post_recreate(containers)

            # Check if selected container's status changed - update log pane if needed
            if self.log_pane and self.container_list.selected_item:
                item_type, item_id = self.container_list.selected_item
                old_status = getattr(self, "_current_selection_status", "none")

                if item_type == "container":
                    # Find the container in the new data
                    for container in containers:
                        if container.get("id") == item_id:
                            # Always update the log pane with current status
                            # The log pane will check if status actually changed
                            self.log_pane.update_selection(
                                "container", item_id, container
                            )

                            # Check if status changed and refresh bindings if needed
                            new_status = container.get("status", "none")
                            if old_status != new_status and hasattr(
                                self, "_current_selection_status"
                            ):
                                self._current_selection_status = new_status
                                if hasattr(self, "refresh_bindings"):
                                    self.refresh_bindings()
                            break
                elif item_type == "image":
                    # Check if selected image's usage status changed
                    if self.container_list.image_manager.selected_image_data:
                        image_data = (
                            self.container_list.image_manager.selected_image_data
                        )
                        # For images, we track if they have containers
                        was_in_use = old_status == "Active"
                        is_in_use = bool(image_data.get("container_names", []))

                        if was_in_use != is_in_use and hasattr(
                            self, "_current_selection_status"
                        ):
                            self._current_selection_status = (
                                "Active" if is_in_use else "Unused"
                            )
                            if hasattr(self, "refresh_bindings"):
                                self.refresh_bindings()

            # Update title with summary
            total_running = sum(s["running"] for s in stacks.values())
            total_exited = sum(s["exited"] for s in stacks.values())
            total_networks = len(networks)
            total_stacks = len(stacks)

            # Update the app title with stats (removes any "Refreshing..." suffix)
            self.title = f"DockTUI - {total_networks} Networks, {total_stacks} Stacks, {total_running} Running, {total_exited} Exited"

            # Increment refresh count
            self._refresh_count += 1

        except Exception as e:
            logger.error(f"Error during UI update: {str(e)}", exc_info=True)
            self.error_display.update(f"Error updating UI: {str(e)}")
