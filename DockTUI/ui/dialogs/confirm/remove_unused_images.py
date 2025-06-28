"""Remove all unused images confirmation modal."""

from ..confirm_modal_base import ConfirmModal


class RemoveUnusedImagesModal(ConfirmModal):
    """Specialized modal for removing all unused images confirmation."""

    def __init__(self, unused_count: int):
        """Initialize the remove all unused images confirmation modal.

        Args:
            unused_count: Number of unused images that will be removed
        """
        super().__init__(
            title="Remove All Unused Images",
            message=f"This will remove {unused_count} unused image{'s' if unused_count != 1 else ''}. This action cannot be undone. Proceed?",
            checkbox_label=None,
            checkbox_default=False,
            confirm_label="Remove All",
            cancel_label="Cancel",
            dangerous=True,
        )
        self.unused_count = unused_count
