"""Remove all unused volumes confirmation modal."""

from ..confirm_modal_base import ConfirmModal


class RemoveUnusedVolumesModal(ConfirmModal):
    """Specialized modal for removing all unused volumes confirmation."""

    def __init__(self, unused_count: int):
        """Initialize the remove all unused volumes confirmation modal.

        Args:
            unused_count: Number of unused volumes that will be removed
        """
        super().__init__(
            title="Remove All Unused Volumes",
            message=f"This will remove {unused_count} unused volume{'s' if unused_count != 1 else ''}. "
            f"This action cannot be undone.\n\n"
            f"Note: Only volumes not mounted by any container will be removed.\n\n"
            f"Proceed?",
            checkbox_label=None,
            checkbox_default=False,
            confirm_label="Remove All",
            cancel_label="Cancel",
            dangerous=True,
        )
        self.unused_count = unused_count
