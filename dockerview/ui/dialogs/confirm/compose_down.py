"""Compose down confirmation modal."""

from ..confirm_modal_base import ConfirmModal


class ComposeDownModal(ConfirmModal):
    """Specialized modal for docker-compose down confirmation."""

    def __init__(self, stack_name: str):
        """Initialize the compose down confirmation modal.

        Args:
            stack_name: Name of the stack to be taken down
        """
        super().__init__(
            title="Confirm Stack Down",
            message=f"Are you sure you want to take down the stack '{stack_name}'? This will stop and remove all containers in the stack.",
            checkbox_label="Also remove volumes",
            checkbox_default=False,
            confirm_label="Take Down",
            cancel_label="Cancel",
            dangerous=True,
        )
        self.stack_name = stack_name
