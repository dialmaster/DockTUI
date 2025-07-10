"""Mixin for objects with cached rendering."""

from typing import Any, Optional


class CacheableMixin:
    """Mixin for objects that need cache management for rendering."""

    def __init__(self, *args, **kwargs):
        """Initialize cache attributes."""
        super().__init__(*args, **kwargs)
        self._cached_segments: Optional[Any] = None
        self._cache_valid: bool = False

    def invalidate_cache(self) -> None:
        """Invalidate the cached rendering."""
        self._cache_valid = False
        self._cached_segments = None

    def is_cache_valid(self) -> bool:
        """Check if cache is valid."""
        return self._cache_valid

    def get_cached_segments(self) -> Optional[Any]:
        """Get cached segments if valid."""
        return self._cached_segments if self._cache_valid else None

    def set_cached_segments(self, segments: Any) -> None:
        """Set cached segments and mark cache as valid."""
        self._cached_segments = segments
        self._cache_valid = True
