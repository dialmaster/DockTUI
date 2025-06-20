"""Image removal confirmation modal."""

from ..confirm_modal_base import ConfirmModal


class RemoveImageModal(ConfirmModal):
    """Specialized modal for image removal confirmation."""

    def __init__(self, image_info: dict):
        """Initialize the image removal confirmation modal.

        Args:
            image_info: Dictionary containing image information
        """
        image_id = image_info.get("id", "unknown")[:12]
        tags = image_info.get("tags", [])
        tag_display = tags[0] if tags else f"<none>:{image_id}"

        super().__init__(
            title="Confirm Image Removal",
            message=f"Are you sure you want to remove the image '{tag_display}'? This action cannot be undone.",
            checkbox_label=None,
            checkbox_default=False,
            confirm_label="Remove Image",
            cancel_label="Cancel",
            dangerous=True,
        )
        self.image_info = image_info
