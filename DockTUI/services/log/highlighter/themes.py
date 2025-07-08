"""Theme definitions for log highlighting."""

from rich.theme import Theme


def get_log_theme() -> Theme:
    """Get the theme for log highlighting."""
    return Theme(
        {
            # Timestamps and log levels
            "log.timestamp": "cyan",
            "log.level_error": "red bold",
            "log.level_warn": "yellow",
            "log.level_info": "green",
            "log.level_debug": "blue",
            "log.level_trace": "magenta",
            # Network
            "log.ip": "bright_cyan",
            "log.ipv6": "bright_cyan",
            "log.mac": "cyan",
            "log.port": "cyan bold",
            # URLs and paths
            "log.url": "blue underline",
            "log.email": "blue",
            "log.path": "green",
            "log.windows_path": "green",
            # Identifiers
            "log.uuid": "magenta",
            "log.hex": "bright_magenta",
            "log.hash": "magenta",
            # Kubernetes/Docker
            "log.k8s_resource": "bright_blue",
            "log.docker_image": "blue",
            "log.container_id": "dim cyan",
            # HTTP
            "log.http_method": "bold cyan",
            "log.http_status": "bold yellow",
            # Special values
            "log.null": "dim",
            "log.bool": "yellow",
            # Numeric
            "log.number": "bright_yellow",
            "log.size": "yellow italic",
            "log.duration": "yellow italic",
            # Process info
            "log.thread": "bright_magenta",
            "log.pid": "bright_magenta",
            # Strings
            "log.quoted": "green",
            "log.single_quoted": "green",
            # JSON
            "log.json": "blue",
            # Code
            "log.function": "blue",
            "log.class": "bright_blue",
            "log.module": "cyan",
            # Generic
            "log.keyword": "bold cyan",
            "log.comment": "dim",
            "log.error": "red bold",
        }
    )


# Pygments token to Rich style mapping
PYGMENTS_TO_RICH = {
    "Token.Keyword": "log.keyword",
    "Token.Keyword.Namespace": "log.module",
    "Token.Name.Function": "log.function",
    "Token.Name.Class": "log.class",
    "Token.Literal.String": "log.quoted",
    "Token.Literal.String.Double": "log.quoted",
    "Token.Literal.String.Single": "log.single_quoted",
    "Token.Literal.Number": "log.number",
    "Token.Comment": "log.comment",
    "Token.Error": "log.error",
    "Token.Name.Exception": "log.level_error",
}
