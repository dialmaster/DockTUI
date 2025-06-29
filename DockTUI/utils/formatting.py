"""Formatting utilities for Docker TUI."""


def format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string with appropriate unit (B, KB, MB, GB)
    """
    if size_bytes >= 1073741824:  # >= 1 GB
        return f"{size_bytes / 1073741824:.1f} GB"
    elif size_bytes >= 1048576:  # >= 1 MB
        return f"{size_bytes / 1048576:.1f} MB"
    elif size_bytes >= 1024:  # >= 1 KB
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"
