"""Time-related utility functions."""

from datetime import datetime, timezone
from typing import Optional


def format_uptime(start_time: Optional[str]) -> str:
    """Format container uptime as a human-readable string.

    Formats time showing a maximum of 2 units (e.g., "2h 15m", "3d 4h", "1m 45s").

    Args:
        start_time: ISO 8601 timestamp string of when container started

    Returns:
        str: Formatted uptime string, or "N/A" if not available
    """
    if not start_time:
        return "N/A"

    try:
        # Parse ISO 8601 timestamp
        # Handle both formats: with Z suffix and with microseconds
        if start_time.endswith("Z"):
            # Replace Z with +00:00 for timezone
            clean_time = start_time[:-1] + "+00:00"
        else:
            clean_time = start_time

        # Python 3.8's fromisoformat doesn't handle more than 6 decimal places
        # in microseconds, so we need to truncate if necessary
        if "." in clean_time:
            parts = clean_time.split(".")
            if len(parts) == 2:
                microseconds_and_tz = parts[1]
                # Find where timezone starts (+ or -)
                tz_start = max(
                    microseconds_and_tz.find("+"), microseconds_and_tz.find("-")
                )
                if tz_start > 6:
                    # Truncate microseconds to 6 digits
                    microseconds = microseconds_and_tz[:6]
                    tz = microseconds_and_tz[tz_start:] if tz_start > -1 else ""
                    clean_time = f"{parts[0]}.{microseconds}{tz}"

        start_dt = datetime.fromisoformat(clean_time)

        # Get current time in UTC
        now = datetime.now(timezone.utc)

        # Calculate duration
        duration = now - start_dt
        total_seconds = int(duration.total_seconds())

        if total_seconds < 0:
            return "N/A"

        # Calculate time components
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        # Format based on magnitude, showing max 2 units
        if days > 0:
            if hours > 0:
                return f"{days}d {hours}h"
            else:
                return f"{days}d"
        elif hours > 0:
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
        elif minutes > 0:
            if seconds > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{minutes}m"
        else:
            return f"{seconds}s"

    except Exception:
        return "N/A"
