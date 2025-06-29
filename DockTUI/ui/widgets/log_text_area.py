import logging

from textual.events import MouseDown, MouseUp
from textual.widgets import TextArea

from ...utils.clipboard import copy_to_clipboard_async

logger = logging.getLogger("DockTUI.log_text_area")


class LogTextArea(TextArea):
    """Custom TextArea that handles right-click to copy and tracks selection state."""

    def __init__(self, *args, **kwargs):
        """Initialize the LogTextArea with selection tracking."""
        super().__init__(*args, **kwargs)
        self._is_selecting = False

    def on_mouse_down(self, event: MouseDown) -> None:
        """Handle mouse down events for right-click copy and selection tracking."""
        # Track when left-click selection starts
        if event.button == 1:  # Left click
            self._is_selecting = True
            logger.debug("Started text selection")

        # Handle right-click copy
        if event.button == 3:
            # Check if there's selected text
            selection = self.selected_text
            if selection:
                # Define callback to show notification from main thread
                def on_copy_complete(success):
                    if success:
                        logger.info(
                            f"Copied {len(selection)} characters to clipboard via right-click"
                        )
                        # Use call_from_thread to ensure notification happens on main thread
                        self.app.call_from_thread(
                            self.app.notify,
                            "Text copied to clipboard",
                            severity="information",
                            timeout=1,
                        )
                    else:
                        logger.error("Failed to copy to clipboard")
                        # Show error notification from main thread
                        self.app.call_from_thread(
                            self.app.notify,
                            "Failed to copy to clipboard. Please install xclip or pyperclip.",
                            severity="error",
                            timeout=3,
                        )

                # Copy in background thread
                copy_to_clipboard_async(selection, on_copy_complete)
                # Prevent the right-click from starting a new selection
                return

        # For non-right-clicks, check if parent has the method before calling it
        if hasattr(super(), "on_mouse_down"):
            super().on_mouse_down(event)

    def on_mouse_up(self, event: MouseUp) -> None:
        """Handle mouse up events to track end of selection."""
        # End selection tracking
        if event.button == 1 and self._is_selecting:
            self._is_selecting = False
            logger.debug("Ended text selection")

        # Call parent handler
        if hasattr(super(), "on_mouse_up"):
            super().on_mouse_up(event)

    @property
    def is_selecting(self) -> bool:
        """Check if user is actively selecting text."""
        return self._is_selecting
