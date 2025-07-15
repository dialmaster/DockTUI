import logging
import queue
import re
import threading
import time
from typing import Optional

import docker

from ..utils.text_processing import strip_ansi_codes

logger = logging.getLogger("DockTUI.log_streamer")


class LogStreamer:
    """Handles streaming logs from Docker containers and stacks."""

    def __init__(self, docker_client: docker.DockerClient):
        """Initialize the log streamer.

        Args:
            docker_client: Docker client instance
        """
        self.docker_client = docker_client
        self.log_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()
        self.log_session_id = 0

    def start_streaming(
        self,
        item_type: str,
        item_id: str,
        item_data: dict,
        tail: str = "200",
        since: str = "15m",
    ) -> int:
        """Start streaming logs for a container or stack.

        Args:
            item_type: Type of item ("container" or "stack")
            item_id: ID of the item
            item_data: Dictionary containing item information
            tail: Number of lines to tail
            since: Time range for logs

        Returns:
            The session ID for this log stream
        """
        # Increment session ID to distinguish this log stream from previous ones
        self.log_session_id += 1
        current_session_id = self.log_session_id

        # Clear stop event for the new thread
        self.stop_event.clear()
        self.log_thread = threading.Thread(
            target=self._log_worker,
            args=(item_type, item_id, item_data, tail, since, current_session_id),
            daemon=True,
        )
        self.log_thread.start()

        return current_session_id

    def stop_streaming(self, wait: bool = True):
        """Stop the current log streaming.

        Args:
            wait: Whether to wait for the thread to finish
        """
        # Signal the thread to stop
        self.stop_event.set()

        # Wait for the thread to finish if requested
        if wait and self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=2)

        # Clear the queue
        while not self.log_queue.empty():
            try:
                self.log_queue.get_nowait()
            except queue.Empty:
                break

    def get_queue(self) -> queue.Queue:
        """Get the log queue.

        Returns:
            The queue containing log messages
        """
        return self.log_queue

    def _log_worker(
        self,
        item_type: str,
        item_id: str,
        item_data: dict,
        tail: str,
        since: str,
        session_id: int,
    ):
        """Worker thread that reads Docker logs and puts them in the queue.

        Args:
            item_type: Type of item ("container" or "stack")
            item_id: ID of the item
            item_data: Dictionary containing item information
            tail: Number of lines to tail
            since: Time range for logs
            session_id: The session ID for this log stream
        """
        try:
            if item_type == "container":
                # Stream logs for a single container
                self._stream_container_logs(item_id, tail, since, session_id)
            elif item_type == "stack":
                # Stream logs for all containers in a stack
                self._stream_stack_logs(item_data, tail, since, session_id)
            else:
                self.log_queue.put(
                    (session_id, "error", f"Unknown item type: {item_type}")
                )
        except Exception as e:
            logger.error(f"Error in log worker: {e}", exc_info=True)
            self.log_queue.put((session_id, "error", f"Error streaming logs: {str(e)}"))

    def _stream_container_logs(
        self, container_id: str, tail: str, since: str, session_id: int
    ):
        """Stream logs for a single container using Docker SDK.

        Args:
            container_id: The container ID
            tail: Number of lines to tail
            since: Time range for logs
            session_id: The session ID for this log stream
        """
        try:
            container = self.docker_client.containers.get(container_id)

            # Convert tail and since parameters
            tail_int = int(tail)

            # Convert since parameter to proper format
            since_timestamp = self._convert_since_to_timestamp(since)

            # Check if container is running
            is_running = container.status.lower() == "running"

            # First, quickly check if there are any logs without following
            initial_logs = container.logs(
                stream=False,
                follow=False,
                tail=1,  # Just check for one line
                since=since_timestamp,
                stdout=True,
                stderr=True,
                timestamps=False,
            )

            # If no logs found initially, show message quickly
            if not initial_logs or not initial_logs.strip():
                self._check_no_logs_found(session_id)
                # For exited containers, return early if no logs
                if not is_running:
                    return
                # Still continue to stream for running containers in case new logs appear

            # Now stream logs - only follow if container is running
            log_stream = container.logs(
                stream=True,
                follow=is_running,  # Only follow logs for running containers
                tail=tail_int,
                since=since_timestamp,
                stdout=True,
                stderr=True,
                timestamps=False,
            )

            line_count = 0

            for line in log_stream:
                if self.stop_event.is_set():
                    break

                # Decode the line
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")

                # Strip only trailing newlines, preserve internal \r for splitting
                line = line.rstrip("\n")

                # Split on carriage returns to handle progress updates
                # Each segment becomes a separate log line
                segments = line.split("\r")

                for segment in segments:
                    # Expand tabs to spaces (use 4 spaces per tab)
                    segment = segment.expandtabs(4)

                    # Check if segment was empty before ANSI stripping
                    was_empty_before_ansi = not segment

                    # Strip ANSI escape codes to prevent text selection issues
                    cleaned_segment = strip_ansi_codes(segment)

                    # Include the segment if it was originally not empty OR if it was empty before ANSI stripping
                    if cleaned_segment or was_empty_before_ansi:
                        line_count += 1
                        self.log_queue.put((session_id, "log", cleaned_segment))

        except docker.errors.NotFound:
            self.log_queue.put(
                (session_id, "error", f"Container {container_id} not found")
            )
        except Exception as e:
            logger.error(f"Error streaming container logs: {e}", exc_info=True)
            raise

    def _stream_stack_logs(
        self, item_data: dict, tail: str, since: str, session_id: int
    ):
        """Stream logs for all containers in a stack using Docker SDK.

        Args:
            item_data: Dictionary containing stack information
            tail: Number of lines to tail
            since: Time range for logs
            session_id: The session ID for this log stream
        """
        try:
            stack_name = item_data.get("name", "")

            # Get all containers for this stack
            containers = self.docker_client.containers.list(
                all=True, filters={"label": f"com.docker.compose.project={stack_name}"}
            )

            # Remove any duplicate containers (shouldn't happen, but just in case)
            seen_ids = set()
            unique_containers = []
            for container in containers:
                if container.id not in seen_ids:
                    seen_ids.add(container.id)
                    unique_containers.append(container)
            containers = unique_containers

            if not containers:
                self.log_queue.put(
                    (session_id, "error", f"No containers found for stack {stack_name}")
                )
                return

            # Create log streams for all containers
            log_streams = []
            for container in containers:
                try:
                    # Convert tail and since parameters
                    tail_int = int(tail)
                    since_timestamp = self._convert_since_to_timestamp(since)

                    log_stream = container.logs(
                        stream=True,
                        follow=True,
                        tail=tail_int,
                        since=since_timestamp,
                        stdout=True,
                        stderr=True,
                        timestamps=False,
                    )

                    # Store container name with the stream for prefixing
                    log_streams.append((container.name, log_stream))
                except Exception as e:
                    logger.warning(
                        f"Failed to get logs for container {container.name}: {e}"
                    )

            if not log_streams:
                self.log_queue.put(
                    (
                        session_id,
                        "error",
                        f"Could not stream logs for any containers in stack {stack_name}",
                    )
                )
                return

            # Stream logs from all containers
            has_any_logs = False

            # Set a shorter timer to check if we've received any logs
            check_timer = threading.Timer(
                0.5,
                lambda: (
                    self._check_no_logs_found(session_id) if not has_any_logs else None
                ),
            )
            check_timer.start()

            # Create threads to read from each stream
            combined_queue = queue.Queue()

            def read_container_logs(name, stream):
                """Read logs from a single container stream."""
                try:
                    for line in stream:
                        if self.stop_event.is_set():
                            break

                        # Decode the line
                        if isinstance(line, bytes):
                            line = line.decode("utf-8", errors="replace")

                        # Strip only trailing newlines, preserve internal \r for splitting
                        line = line.rstrip("\n")

                        # Split on carriage returns to handle progress updates
                        # Each segment becomes a separate log line
                        segments = line.split("\r")

                        for segment in segments:
                            # Expand tabs to spaces (use 4 spaces per tab)
                            segment = segment.expandtabs(4)

                            # Check if segment was empty before ANSI stripping
                            was_empty_before_ansi = not segment

                            # Strip ANSI escape codes to prevent text selection issues
                            cleaned_segment = strip_ansi_codes(segment)

                            # Include the segment if it was originally not empty OR if it was empty before ANSI stripping
                            if cleaned_segment or was_empty_before_ansi:
                                # Prefix with container name for stack logs
                                prefixed_line = f"[{name}] {cleaned_segment}"
                                combined_queue.put(prefixed_line)
                except Exception as e:
                    logger.error(f"Error reading logs from {name}: {e}")

            # Start threads for each container
            threads = []
            for name, stream in log_streams:
                thread = threading.Thread(
                    target=read_container_logs, args=(name, stream), daemon=True
                )
                thread.start()
                threads.append(thread)

            # Read from combined queue and forward to main log queue
            while not self.stop_event.is_set():
                try:
                    # Use timeout to periodically check stop_event
                    line = combined_queue.get(timeout=0.1)
                    has_any_logs = True
                    self.log_queue.put((session_id, "log", line))
                except:
                    # Check if all threads have finished
                    if all(not t.is_alive() for t in threads):
                        break

            # Cancel timer if still running
            check_timer.cancel()

        except Exception as e:
            logger.error(f"Error streaming stack logs: {e}", exc_info=True)
            raise

    def _check_no_logs_found(self, session_id: int):
        """Check if no logs were found and show an informative message.

        Args:
            session_id: The session ID for this log stream
        """
        self.log_queue.put((session_id, "no_logs", ""))

    def _convert_since_to_timestamp(self, since_str: str) -> int:
        """Convert a time string like '5m' or '1h' to a Unix timestamp.

        Args:
            since_str: Time string (e.g., '5m', '1h', '24h')

        Returns:
            Unix timestamp for the 'since' parameter
        """
        # Parse the time unit and value
        match = re.match(r"^(\d+)([mhd])$", since_str)
        if not match:
            # If format is invalid, default to 15 minutes
            logger.warning(f"Invalid since format: {since_str}, defaulting to 15m")
            return int(time.time() - 15 * 60)

        value = int(match.group(1))
        unit = match.group(2)

        # Convert to seconds
        if unit == "m":
            seconds = value * 60
        elif unit == "h":
            seconds = value * 3600
        elif unit == "d":
            seconds = value * 86400
        else:
            seconds = 15 * 60  # Default to 15 minutes

        # Return Unix timestamp for 'since' time
        return int(time.time() - seconds)
