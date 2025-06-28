"""Remove container confirmation modal."""

from ..confirm_modal_base import ConfirmModal


class RemoveContainerModal(ConfirmModal):
    """Specialized modal for container removal confirmation."""

    def __init__(self, container_name: str):
        """Initialize the container removal confirmation modal.

        Args:
            container_name: Name of the container to be removed
        """
        super().__init__(
            title="Confirm Container Removal",
            message=f"Are you sure you want to remove the container '{container_name}'? This action cannot be undone.",
            checkbox_label=None,  # No checkbox needed for container removal
            checkbox_default=False,
            confirm_label="Remove",
            cancel_label="Cancel",
            dangerous=True,
        )
        self.container_name = container_name
