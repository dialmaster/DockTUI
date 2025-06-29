"""Volume removal confirmation modal."""

from ..confirm_modal_base import ConfirmModal


class RemoveVolumeModal(ConfirmModal):
    """Specialized modal for volume removal confirmation."""

    def __init__(self, volume_info: dict):
        """Initialize the volume removal confirmation modal.

        Args:
            volume_info: Dictionary containing volume information
        """
        volume_name = volume_info.get("name", "unknown")
        container_count = volume_info.get("container_count", 0)
        stack_name = volume_info.get("stack", None)

        # Build the message
        message = f"Are you sure you want to remove the volume '{volume_name}'?"

        if stack_name:
            message += f"\n\nThis volume belongs to stack: {stack_name}"

        if container_count > 0:
            # This shouldn't happen as we check before showing dialog
            message += (
                f"\n\nWARNING: This volume is in use by {container_count} container(s)!"
            )

        message += "\n\nThis action cannot be undone."

        super().__init__(
            title="Confirm Volume Removal",
            message=message,
            checkbox_label=None,
            checkbox_default=False,
            confirm_label="Remove Volume",
            cancel_label="Cancel",
            dangerous=True,
        )
        self.volume_info = volume_info
