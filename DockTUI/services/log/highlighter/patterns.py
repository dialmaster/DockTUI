"""Pattern definitions for log highlighting."""

import re
from typing import Dict, Optional, Pattern, Union

try:
    from pyparsing import CaselessKeyword, CaselessLiteral, Combine, Literal
    from pyparsing import Optional as OptionalPP
    from pyparsing import ParserElement, Regex, Word, hexnums, nums
    from pyparsing import pyparsing_common as ppc

    HAS_PYPARSING = True
except ImportError:
    HAS_PYPARSING = False
    ParserElement = None


class LogPatterns:
    """Manages patterns for log parsing and highlighting."""

    _instance = None
    _patterns_initialized = False

    # Class-level pattern storage
    _pyparsing_patterns: Dict[str, ParserElement] = {}
    _regex_patterns: Dict[str, Pattern] = {}

    def __new__(cls):
        """Implement singleton pattern to avoid recreating patterns."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize pattern definitions once."""
        if not self._patterns_initialized:
            if HAS_PYPARSING:
                self._init_pyparsing_patterns()
            else:
                self._init_regex_patterns()
            self.__class__._patterns_initialized = True

    def _init_pyparsing_patterns(self):
        """Initialize pyparsing patterns for advanced parsing."""
        patterns = self._pyparsing_patterns

        # Log levels
        patterns["level_error"] = (
            CaselessKeyword("ERROR")
            | CaselessKeyword("FATAL")
            | CaselessKeyword("CRITICAL")
        )
        patterns["level_warn"] = CaselessKeyword("WARN") | CaselessKeyword("WARNING")
        patterns["level_info"] = CaselessKeyword("INFO")
        patterns["level_debug"] = CaselessKeyword("DEBUG")
        patterns["level_trace"] = CaselessKeyword("TRACE")

        # Timestamps - handle various ISO formats including timezone without colon
        iso_timestamp = Regex(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
        )
        syslog_timestamp = Regex(r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}")
        simple_timestamp = Regex(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}")
        patterns["timestamp"] = iso_timestamp | syslog_timestamp | simple_timestamp

        # Network patterns
        patterns["ipv4"] = ppc.ipv4_address.copy()
        patterns["ipv6"] = ppc.ipv6_address.copy()
        patterns["mac"] = ppc.mac_address.copy()
        patterns["port"] = Combine(
            (CaselessLiteral("port") | CaselessLiteral("Port"))
            + OptionalPP(Literal(":") | Literal("="))
            + Word(nums, max=5)
        )

        # URLs and paths
        patterns["url"] = Regex(r"https?://[^\s<>\"{}|\\^`\[\]]+")
        patterns["email"] = Regex(r"[\w\.-]+@[\w\.-]+\.\w+")
        patterns["unix_path"] = Regex(r"(?:/[\w\-\.]+)+/?")
        patterns["windows_path"] = Regex(r"[a-zA-Z]:\\(?:\\?[\w\-\.\\]+)+")

        # Identifiers
        patterns["uuid"] = ppc.uuid.copy()
        patterns["hex"] = Combine(Literal("0x") + Word(hexnums))
        patterns["hash"] = Regex(r"\b[a-fA-F0-9]{32,64}\b")
        patterns["container_id"] = Regex(r"\b[a-fA-F0-9]{12,64}\b")

        # Kubernetes/Docker
        patterns["k8s_resource"] = Regex(
            r"(?:pod|service|deployment|node|namespace)/[\w\-]+"
        )
        patterns["docker_image"] = Regex(r"[\w\-\.]+(?:/[\w\-\.]+)*:[^\s]+")

        # HTTP patterns
        patterns["http_method"] = (
            CaselessKeyword("GET")
            | CaselessKeyword("POST")
            | CaselessKeyword("PUT")
            | CaselessKeyword("DELETE")
            | CaselessKeyword("PATCH")
            | CaselessKeyword("HEAD")
            | CaselessKeyword("OPTIONS")
            | CaselessKeyword("CONNECT")
            | CaselessKeyword("TRACE")
        )
        patterns["http_status"] = Regex(r"\b[1-5]\d{2}\b")

        # Special values
        patterns["null_value"] = (
            CaselessKeyword("null")
            | CaselessKeyword("None")
            | CaselessKeyword("nil")
            | CaselessKeyword("NULL")
        )
        patterns["bool_value"] = (
            CaselessKeyword("true")
            | CaselessKeyword("false")
            | CaselessKeyword("True")
            | CaselessKeyword("False")
            | CaselessKeyword("yes")
            | CaselessKeyword("no")
        )

        # Numeric patterns with units
        patterns["size_value"] = Combine(
            Word(nums + ".") + Regex(r"\s*(?:B|KB|MB|GB|TB|b|kb|mb|gb|tb)")
        )
        patterns["duration_value"] = Combine(
            Word(nums + ".") + Regex(r"\s*(?:ms|s|m|h|d|ns|us|µs)")
        )
        patterns["number"] = ppc.real_number | ppc.signed_integer

        # Process patterns
        patterns["thread"] = Regex(r"Thread-\d+|\[Thread-\d+\]")
        patterns["pid"] = Regex(r"\bpid[=:\s]+\d+\b|\bPID[=:\s]+\d+\b")

        # Container patterns
        patterns["container_prefix"] = Regex(r"^\[[^\]]+\]")

        # Quoted strings
        patterns["double_quoted"] = Regex(r'"(?:[^"\\]|\\.)*"')
        patterns["single_quoted"] = Regex(r"'(?:[^'\\]|\\.)*'")

    def _init_regex_patterns(self):
        """Initialize regex patterns as fallback."""
        patterns = self._regex_patterns

        # Log level patterns
        patterns["level_error"] = re.compile(
            r"\b(ERROR|FATAL|CRITICAL)\b", re.IGNORECASE
        )
        patterns["level_warn"] = re.compile(r"\b(WARN|WARNING)\b", re.IGNORECASE)
        patterns["level_info"] = re.compile(r"\bINFO\b", re.IGNORECASE)
        patterns["level_debug"] = re.compile(r"\bDEBUG\b", re.IGNORECASE)
        patterns["level_trace"] = re.compile(r"\bTRACE\b", re.IGNORECASE)

        # Timestamp patterns - combine into one pattern with alternation
        patterns["timestamp"] = re.compile(
            r"(?:\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
        )

        # Network patterns
        patterns["ipv4"] = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        patterns["ipv6"] = re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\b")
        patterns["mac"] = re.compile(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b")
        patterns["port"] = re.compile(r"\b(?:port|Port)[:\s=]*(\d{1,5})\b")

        # URL and path patterns
        patterns["url"] = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]+")
        patterns["email"] = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
        patterns["unix_path"] = re.compile(r"(?:/[\w\-\.]+)+/?")
        patterns["windows_path"] = re.compile(r"[a-zA-Z]:\\(?:\\?[\w\-\.\\]+)+")

        # Identifier patterns
        patterns["uuid"] = re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        )
        patterns["hex"] = re.compile(r"\b0x[0-9a-fA-F]+\b")
        patterns["hash"] = re.compile(r"\b[a-fA-F0-9]{32,64}\b")

        # Container/K8s patterns
        patterns["k8s_resource"] = re.compile(
            r"\b(?:pod|service|deployment|node|namespace)/[\w\-]+"
        )
        patterns["docker_image"] = re.compile(r"[\w\-\.]+(?:/[\w\-\.]+)*:[^\s]+")

        # HTTP patterns
        patterns["http_method"] = re.compile(
            r"\b(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|CONNECT|TRACE)\b"
        )
        patterns["http_status"] = re.compile(r"\b[1-5]\d{2}\b")

        # Special value patterns
        patterns["null_value"] = re.compile(r"\b(null|None|nil|NULL)\b")
        patterns["bool_value"] = re.compile(r"\b(true|false|True|False|yes|no)\b")

        # Numeric patterns
        patterns["size_value"] = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|TB|b|kb|mb|gb|tb)\b"
        )
        patterns["duration_value"] = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:ms|s|m|h|d|ns|us|µs)\b"
        )
        patterns["number"] = re.compile(r"\b[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b")

        # Process patterns
        patterns["thread"] = re.compile(r"Thread-\d+|\[Thread-\d+\]")
        patterns["pid"] = re.compile(
            r"\bpid[=:\s]+\d+\b|\bPID[=:\s]+\d+\b", re.IGNORECASE
        )

        # Container patterns
        patterns["container_prefix"] = re.compile(r"^\[[^\]]+\]")

        # String patterns
        patterns["double_quoted"] = re.compile(r'"(?:[^"\\]|\\.)*"')
        patterns["single_quoted"] = re.compile(r"'(?:[^'\\]|\\.)*'")

    def get_pattern(self, pattern_name: str) -> Optional[Union[ParserElement, Pattern]]:
        """Get a pattern by name, handling both pyparsing and regex."""
        if HAS_PYPARSING:
            return self._pyparsing_patterns.get(pattern_name)
        else:
            return self._regex_patterns.get(pattern_name)
