"""Coordinates background parsing of log lines."""

import logging
import queue
import threading
from typing import Callable, Optional

from ...models.log_line import LogLine

logger = logging.getLogger("DockTUI.parsing_coordinator")


class ParsingCoordinator:
    """
    Manages background parsing of log lines.

    This class handles:
    - Background parsing thread management
    - Parse queue management
    - Scheduling lines for parsing
    - Notifying when parsing is complete
    """

    def __init__(
        self, parse_complete_callback: Optional[Callable[[LogLine], None]] = None
    ):
        """Initialize the parsing coordinator.

        Args:
            parse_complete_callback: Callback to invoke when a log line is parsed.
                                   Will be called on the main thread.
        """
        self._parse_queue: queue.Queue[LogLine] = queue.Queue(maxsize=1000)
        self._parsing_thread: Optional[threading.Thread] = None
        self._stop_parsing = threading.Event()
        self._parse_complete_callback = parse_complete_callback
        self._app = None  # Will be set when we need to call back to main thread

    def set_app(self, app):
        """Set the app reference for thread callbacks."""
        self._app = app

    def start(self):
        """Start the background parsing thread."""
        if self._parsing_thread is None or not self._parsing_thread.is_alive():
            self._stop_parsing.clear()
            self._parsing_thread = threading.Thread(
                target=self._parsing_worker, daemon=True, name="LogParsingWorker"
            )
            self._parsing_thread.start()

    def stop(self):
        """Stop the background parsing thread."""
        if self._parsing_thread and self._parsing_thread.is_alive():
            self._stop_parsing.set()
            # Add sentinel to wake up the thread
            try:
                self._parse_queue.put(None, block=False)
            except queue.Full:
                pass
            self._parsing_thread.join(timeout=1.0)

    def schedule_parse(self, log_line: LogLine, priority: bool = False):
        """Schedule a log line for background parsing.

        Args:
            log_line: The log line to parse
            priority: If True, parse synchronously instead of queuing
        """
        if not log_line.is_parsed:
            try:
                if priority:
                    # For priority items, parse synchronously
                    log_line.ensure_parsed()
                    # Still notify callback if set
                    if self._parse_complete_callback and self._app:
                        self._app.call_from_thread(
                            self._parse_complete_callback, log_line
                        )
                else:
                    self._parse_queue.put_nowait(log_line)
            except queue.Full:
                # Queue is full, parse synchronously as fallback
                log_line.ensure_parsed()
                # Still notify callback if set
                if self._parse_complete_callback and self._app:
                    self._app.call_from_thread(self._parse_complete_callback, log_line)

    def _parsing_worker(self):
        """Background worker thread for parsing log lines."""
        while not self._stop_parsing.is_set():
            try:
                # Get log line from queue with timeout
                log_line = self._parse_queue.get(timeout=0.1)

                if log_line is None:  # Sentinel value to stop
                    break

                # Parse the log line
                if not log_line.is_parsed and log_line._parser is not None:
                    log_line._parser.parse_into_line(log_line)
                    log_line._is_parsed = True
                    log_line._parser = None

                    # Notify main thread if this line affects visible content
                    if self._parse_complete_callback and self._app:
                        self._app.call_from_thread(
                            self._parse_complete_callback, log_line
                        )

                # Mark task as done
                self._parse_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in parsing worker: {e}", exc_info=True)
