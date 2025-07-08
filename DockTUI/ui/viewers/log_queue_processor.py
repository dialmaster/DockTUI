"""Log Queue Processor for handling log queue processing in LogPane."""

import logging
from typing import TYPE_CHECKING, List, Tuple

from DockTUI.ui.widgets.rich_log_viewer import RichLogViewer

if TYPE_CHECKING:
    from DockTUI.ui.viewers.log_filter_manager import LogFilterManager
    from DockTUI.ui.viewers.log_stream_manager import LogStreamManager

logger = logging.getLogger(__name__)


class LogQueueProcessor:
    """Handles log queue processing for LogPane."""

    def __init__(
        self,
        log_stream_manager: "LogStreamManager",
        log_filter_manager: "LogFilterManager",
        parent=None,
    ):
        """Initialize the log queue processor.

        Args:
            log_stream_manager: Manager for log streaming
            log_filter_manager: Manager for log filtering
            parent: Parent LogPane instance
        """
        self.log_stream_manager = log_stream_manager
        self.log_filter_manager = log_filter_manager
        self.parent = parent
        self.log_display = None
        self.current_item = None
        self.current_item_data = None

    def set_log_display(self, log_display: RichLogViewer) -> None:
        """Set the log display widget."""
        self.log_display = log_display

    def set_current_item(self, item_type: str, item_id: str, item_data: dict) -> None:
        """Set the current item being logged."""
        self.current_item = (item_type, item_id)
        self.current_item_data = item_data

    def should_skip_processing(self) -> bool:
        """Check if log processing should be skipped."""
        if not self.log_stream_manager.is_available:
            return True

        # Skip processing if user is actively selecting text
        if (
            self.log_display
            and hasattr(self.log_display, "is_selecting")
            and self.log_display.is_selecting
        ):
            logger.debug("Skipping log processing during active text selection")
            return True

        # Don't skip if showing "no matches" - we want to process new logs that might match
        return False

    def process_queue(self, max_items: int = 50) -> dict:
        """Process queued log lines.

        Args:
            max_items: Maximum number of items to process

        Returns:
            Dictionary with processing results
        """
        if self.should_skip_processing():
            return {"processed": 0, "matched": 0, "has_displayed_any": False}

        try:
            has_displayed_any = self._check_has_displayed_logs()
            result = self.log_stream_manager.process_queue(max_items=max_items)

            # Process log lines
            batch_lines, matched_lines = self._process_log_lines(result["lines"])

            # Process errors
            self._process_errors(result["errors"])

            # Handle no logs scenario
            self._handle_no_logs(result["no_logs"])

            # Add batch lines to display
            self._add_batch_lines_to_display(batch_lines)

            # Update loading state
            self._update_loading_state(result["processed"])

            # Handle filter with no matches only if we processed something or don't have the message
            if (
                result["processed"] > 0
                or not self.log_stream_manager.showing_no_matches_message
            ):
                self._handle_no_matches(
                    result["processed"], matched_lines, has_displayed_any
                )

            return {
                "processed": result["processed"],
                "matched": matched_lines,
                "has_displayed_any": has_displayed_any,
            }

        except Exception as e:
            logger.error(f"Error processing log queue: {e}", exc_info=True)
            return {"processed": 0, "matched": 0, "has_displayed_any": False}

    def _check_has_displayed_logs(self) -> bool:
        """Check if any logs have been displayed."""
        if not self.log_display:
            return False
        log_text = self._get_log_text()
        return len(log_text.strip()) > 0

    def _process_log_lines(self, lines: List[str]) -> Tuple[List[str], int]:
        """Process log lines and return batch lines and match count."""
        batch_lines = []
        matched_lines = 0

        for content in lines:
            # Store all log lines
            self.log_filter_manager.add_line(content)

            # Apply search filter with marker context awareness
            if self.log_filter_manager.should_show_line(content):
                matched_lines += 1
                self._clear_status_messages_if_needed()

                # If we have a matching line and were showing "no matches", clear it
                if self.log_stream_manager.showing_no_matches_message:
                    self.log_stream_manager.showing_no_matches_message = False
                    # Clear the "no matches" message
                    self._clear_log_display()

                # Collect lines for batch processing
                if isinstance(self.log_display, RichLogViewer):
                    batch_lines.append(content)
                else:
                    # Append immediately for LogTextArea
                    self._append_log_line(content)

        return batch_lines, matched_lines

    def _clear_status_messages_if_needed(self) -> None:
        """Clear loading or no-logs messages if needed."""
        if (
            self.log_stream_manager.showing_no_logs_message
            or self.log_stream_manager.showing_loading_message
        ):
            self._clear_log_display()
            self.log_stream_manager.showing_no_logs_message = False
            self.log_stream_manager.showing_loading_message = False

    def _process_errors(self, errors: List[str]) -> None:
        """Process error messages."""
        for error in errors:
            error_msg = f"ERROR: {error}"
            self._append_log_line(error_msg)

    def _handle_no_logs(self, no_logs: bool) -> None:
        """Handle the case when no logs are available."""
        if no_logs:
            # Clear any filter to ensure the no logs message is shown
            self._clear_log_display()
            # Clear the filter lines but keep the filter itself
            self.log_filter_manager.clear()
            self._set_log_text(self._get_no_logs_message())
            self._clear_loading_state_if_needed()
            self.log_stream_manager.showing_no_logs_message = True

    def _clear_loading_state_if_needed(self) -> None:
        """Clear loading state and update header if needed."""
        if self.log_stream_manager.is_loading and self.current_item:
            item_type, item_id = self.current_item
            header_text = self._get_header_text(item_type, item_id)
            self._update_header(header_text)

    def _add_batch_lines_to_display(self, batch_lines: List[str]) -> None:
        """Add batch lines to RichLogViewer if any were collected."""
        if batch_lines and isinstance(self.log_display, RichLogViewer):
            self.log_display.add_log_lines(batch_lines)

    def _update_loading_state(self, processed_count: int) -> None:
        """Update loading state when first logs arrive."""
        if processed_count > 0 and self.log_stream_manager.is_loading:
            self._clear_loading_state_if_needed()

    def _handle_no_matches(
        self, processed: int, matched_lines: int, has_displayed_any: bool
    ) -> None:
        """Handle case when filter matches no lines."""
        # Don't show "no matches" if we already showed "no logs"
        if self.log_stream_manager.showing_no_logs_message:
            return

        # Check if we have logs but no matches with active filter
        if (
            self.log_filter_manager.has_filter()
            and len(self.log_filter_manager.get_all_lines()) > 0
        ):
            # Calculate total matches across all stored lines
            total_matches = sum(
                1
                for line in self.log_filter_manager.get_all_lines()
                if self.log_filter_manager.should_show_line(line)
            )

            # If no lines match the filter, show the message
            if total_matches == 0:
                self._clear_log_display()
                self._set_log_text("No log lines match filter")
                self.log_stream_manager.showing_no_matches_message = True
            else:
                # We have matches, clear the flag
                self.log_stream_manager.showing_no_matches_message = False

    def _get_header_text(self, item_type: str, item_id: str) -> str:
        """Get header text for current item."""
        if item_type == "container":
            item_name = (
                self.current_item_data.name if self.current_item_data else item_id
            )
            return f"📋 Log Pane - Container: {item_name}"
        elif item_type == "stack":
            return f"📋 Log Pane - Stack: {item_id}"
        return "📋 Log Pane"

    def _get_no_logs_message(self) -> str:
        """Get the formatted 'No logs found' message."""
        item_type, item_id = self.current_item if self.current_item else ("", "")
        return (
            f"No logs found for {item_type}: {item_id}\n\n"
            "This could mean:\n"
            "  • The container/stack hasn't produced logs in the selected time range\n"
            "  • The container/stack was recently started\n"
            "  • Logs may have been cleared or rotated\n\n"
            "Try adjusting the log settings above to see more history.\n\n"
            "Waiting for new logs..."
        )

    # Delegate methods to parent LogPane
    def _get_log_text(self) -> str:
        """Get current log text from parent."""
        if self.parent:
            return self.parent._get_log_text()
        return ""

    def _clear_log_display(self) -> None:
        """Clear log display through parent."""
        if self.parent:
            self.parent._clear_log_display()

    def _append_log_line(self, line: str) -> None:
        """Append a log line through parent."""
        if self.parent:
            self.parent._append_log_line(line)

    def _set_log_text(self, text: str) -> None:
        """Set log text through parent."""
        if self.parent:
            self.parent._set_log_text(text)

    def _update_header(self, text: str) -> None:
        """Update header text through parent."""
        if self.parent:
            self.parent._update_header(text)
