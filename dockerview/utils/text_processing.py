import re

# ANSI escape code pattern for stripping color codes
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_codes(text: str) -> str:
    """Strip ANSI escape codes from text.

    Args:
        text: The text containing ANSI codes

    Returns:
        The text with ANSI codes removed
    """
    return ANSI_ESCAPE_PATTERN.sub("", text)
