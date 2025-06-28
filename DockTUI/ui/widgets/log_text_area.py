import logging

from textual.events import MouseDown
from textual.widgets import TextArea

from ...utils.clipboard import copy_to_clipboard_async

logger = logging.getLogger("DockTUI.log_text_area")


class LogTextArea(TextArea):
    """Custom TextArea that handles right-click to copy."""

    def on_mouse_down(self, event: MouseDown) -> None:
        """Handle mouse down events for right-click copy."""
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
