"""Clipboard utilities for DockTUI."""

import logging
import os
import subprocess
import threading

logger = logging.getLogger("DockTUI.clipboard")


def copy_to_clipboard_sync(text):
    """Copy text to clipboard synchronously with container support."""
    # Check if we're in container mode
    in_container = os.environ.get("DOCKTUI_IN_CONTAINER", "").lower() in [
        "1",
        "true",
        "yes",
    ]

    # Check for clipboard file mount FIRST (container preferred method)
    clipboard_file = os.environ.get("DOCKTUI_CLIPBOARD_FILE")
    if clipboard_file and in_container:
        try:
            with open(clipboard_file, "w") as f:
                f.write(text)
            logger.info(f"Wrote to clipboard file: {clipboard_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to write to clipboard file {clipboard_file}: {e}")

    # If not in container, try pyperclip first (local environments)
    if not in_container:
        try:
            import pyperclip

            pyperclip.copy(text)
            return True
        except Exception as e:
            logger.debug(f"pyperclip failed: {e}")

    # Try xclip (works in containers with X11 forwarding and on Linux)
    try:
        process = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            text=True,
        )
        process.communicate(input=text, timeout=1.0)
        return process.returncode == 0
    except subprocess.TimeoutExpired:
        logger.debug("xclip timed out")
        return False
    except FileNotFoundError:
        logger.debug("xclip not found")
    except Exception as e:
        logger.debug(f"xclip failed: {e}")

    # Try clipboard file as fallback even if not in container
    if clipboard_file and not in_container:
        try:
            with open(clipboard_file, "w") as f:
                f.write(text)
            logger.debug(f"Wrote to clipboard file: {clipboard_file}")
            return True
        except Exception as e:
            logger.debug(f"Failed to write to clipboard file: {e}")

    # All methods failed
    return False


def copy_to_clipboard_async(text, callback=None):
    """Copy text to clipboard in a background thread.

    Args:
        text: Text to copy
        callback: Optional callback function that receives (success: bool)
    """

    def _copy_thread():
        success = copy_to_clipboard_sync(text)
        if callback:
            callback(success)

    thread = threading.Thread(target=_copy_thread, daemon=True)
    thread.start()
