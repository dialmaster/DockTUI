"""Manager for handling log streaming operations.

This module extracts log streaming logic from LogPane to improve maintainability
and separation of concerns.
"""

import logging
import queue
from typing import Any, Dict, Optional, Tuple

import docker

from ...config import config
from ...services.log_streamer import LogStreamer

logger = logging.getLogger("DockTUI.log_stream_manager")


class LogStreamManager:
    """Manages log streaming operations for the LogPane."""

    def __init__(self, docker_client: Optional[docker.DockerClient]):
        """Initialize the log stream manager.

        Args:
            docker_client: Docker client instance, or None if not available
        """
        self.docker_client = docker_client
        self.log_streamer = LogStreamer(docker_client) if docker_client else None

        # Session management
        self.current_session_id = 0
        self.current_item: Optional[Tuple[str, str]] = None
        self.current_item_data: Optional[dict] = None

        # State tracking
        self.waiting_for_logs = False
        self.initial_log_check_done = False
        self.showing_no_logs_message = False
        self.showing_loading_message = False
        self.showing_no_matches_message = False
        self.logs_loading = False

        # Log settings
        self.log_tail = str(config.get("log.tail", 200))
        self.log_since = config.get("log.since", "15m")

    def start_streaming(
        self,
        item_type: str,
        item_id: str,
        item_data: Optional[dict],
        tail: Optional[str] = None,
        since: Optional[str] = None,
    ) -> bool:
        """Start streaming logs for the specified item.

        Args:
            item_type: Type of item ("container" or "stack")
            item_id: ID of the item
            item_data: Dictionary containing item information
            tail: Number of lines to tail (uses default if None)
            since: Time range for logs (uses default if None)

        Returns:
            True if streaming started successfully, False otherwise
        """
        if not self.log_streamer:
            logger.error("Log streamer not available")
            return False

        # Update current item
        self.current_item = (item_type, item_id)
        self.current_item_data = item_data

        # Set state flags
        self.waiting_for_logs = True
        self.initial_log_check_done = False
        self.showing_no_logs_message = False
        self.showing_no_matches_message = False
        self.logs_loading = True

        # Use provided settings or defaults
        tail = tail or self.log_tail
        since = since or self.log_since

        # Start streaming
        self.current_session_id = self.log_streamer.start_streaming(
            item_type=item_type,
            item_id=item_id,
            item_data=item_data or {},
            tail=tail,
            since=since,
        )

        logger.info(
            f"Started log streaming for {item_type}: {item_id} "
            f"(session {self.current_session_id})"
        )
        return True

    def stop_streaming(self, wait: bool = True) -> None:
        """Stop the current log streaming.

        Args:
            wait: Whether to wait for the streaming thread to finish
        """
        if self.log_streamer:
            self.log_streamer.stop_streaming(wait=wait)
            logger.debug(f"Stopped log streaming (wait={wait})")

    def restart_streaming(self) -> bool:
        """Restart log streaming with current settings.

        Returns:
            True if streaming restarted successfully, False otherwise
        """
        if not self.current_item:
            logger.warning("Cannot restart streaming: no current item")
            return False

        item_type, item_id = self.current_item

        # Reset state
        self.waiting_for_logs = True
        self.initial_log_check_done = False
        self.showing_loading_message = True
        self.logs_loading = True

        # Stop current streaming without waiting
        self.stop_streaming(wait=False)

        # Start streaming again
        return self.start_streaming(
            item_type, item_id, self.current_item_data, self.log_tail, self.log_since
        )

    def process_queue(self, max_items: int = 50) -> Dict[str, Any]:
        """Process items from the log queue.

        Args:
            max_items: Maximum number of items to process in one call

        Returns:
            Dictionary containing:
                - processed: Number of items processed
                - matched: Number of lines that matched filters
                - lines: List of log lines to display
                - errors: List of error messages
                - no_logs: True if "no_logs" message was received
        """
        if not self.log_streamer:
            return {
                "processed": 0,
                "matched": 0,
                "lines": [],
                "errors": [],
                "no_logs": False,
            }

        log_queue = self.log_streamer.get_queue()
        result = {
            "processed": 0,
            "matched": 0,
            "lines": [],
            "errors": [],
            "no_logs": False,
        }

        # Process up to max_items from the queue
        for _ in range(max_items):
            if log_queue.empty():
                break

            try:
                queue_item = log_queue.get_nowait()

                # Handle both old format (msg_type, content) and new format
                if len(queue_item) == 2:
                    # Old format - shouldn't happen but handle gracefully
                    msg_type, content = queue_item
                    session_id = 0
                else:
                    # New format with session ID
                    session_id, msg_type, content = queue_item

                # Skip if this is from an old session
                if session_id != 0 and session_id != self.current_session_id:
                    continue

                result["processed"] += 1

                if msg_type == "log":
                    result["lines"].append(content)
                    result["matched"] += 1
                elif msg_type == "error":
                    result["errors"].append(content)
                    logger.error(f"Log stream error: {content}")
                elif msg_type == "no_logs":
                    result["no_logs"] = True
                    self.waiting_for_logs = False
                    self.showing_no_logs_message = True

            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error processing log queue item: {e}", exc_info=True)

        # Update state based on processing
        if result["processed"] > 0:
            self.initial_log_check_done = True
            if self.logs_loading:
                self.logs_loading = False

        return result

    def update_settings(
        self, tail: Optional[str] = None, since: Optional[str] = None
    ) -> None:
        """Update log streaming settings.

        Args:
            tail: New tail setting (number of lines)
            since: New since setting (time range)
        """
        if tail is not None:
            self.log_tail = tail
            logger.info(f"Updated log tail setting to: {tail}")

        if since is not None:
            self.log_since = since
            logger.info(f"Updated log since setting to: {since}")

    def is_container_stopped(self, status: str) -> bool:
        """Check if a container status indicates it's stopped.

        Args:
            status: The container status string

        Returns:
            True if the container is stopped, False otherwise
        """
        status_lower = status.lower()
        return any(state in status_lower for state in ["exited", "stopped", "created"])

    def is_container_running(self, status: str) -> bool:
        """Check if a container status indicates it's running.

        Args:
            status: The container status string

        Returns:
            True if the container is running, False otherwise
        """
        status_lower = status.lower()
        return "running" in status_lower or "up" in status_lower

    def get_current_item(self) -> Optional[Tuple[str, str]]:
        """Get the current item being streamed.

        Returns:
            Tuple of (item_type, item_id) or None if no item is selected
        """
        return self.current_item

    def clear(self) -> None:
        """Clear the current streaming state."""
        self.stop_streaming(wait=True)
        self.current_item = None
        self.current_item_data = None
        self.waiting_for_logs = False
        self.initial_log_check_done = False
        self.showing_no_logs_message = False
        self.showing_loading_message = False
        self.showing_no_matches_message = False
        self.logs_loading = False

    @property
    def is_available(self) -> bool:
        """Check if log streaming is available.

        Returns:
            True if log streamer is available, False otherwise
        """
        return self.log_streamer is not None

    @property
    def is_loading(self) -> bool:
        """Check if logs are currently loading.

        Returns:
            True if logs are loading, False otherwise
        """
        return self.logs_loading

    @property
    def has_no_logs_message(self) -> bool:
        """Check if the "no logs" message was shown.

        Returns:
            True if no logs message was shown, False otherwise
        """
        return self.showing_no_logs_message
