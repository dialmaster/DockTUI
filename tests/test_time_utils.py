"""Unit tests for time utility functions."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from dockerview.utils.time_utils import format_uptime


class TestFormatUptime:
    """Test cases for the format_uptime function."""

    def test_none_input(self):
        """Test that None input returns 'N/A'."""
        assert format_uptime(None) == "N/A"

    def test_empty_string_input(self):
        """Test that empty string input returns 'N/A'."""
        assert format_uptime("") == "N/A"

    def test_invalid_timestamp(self):
        """Test that invalid timestamp returns 'N/A'."""
        assert format_uptime("not-a-timestamp") == "N/A"
        assert format_uptime("2025-13-45T25:99:99Z") == "N/A"

    @patch('dockerview.utils.time_utils.datetime')
    def test_seconds_only(self, mock_datetime):
        """Test formatting when uptime is less than a minute."""
        # Mock current time
        now = datetime(2025, 6, 17, 12, 0, 30, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started 45 seconds ago
        start_time = datetime(2025, 6, 17, 11, 59, 45, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "45s"

    @patch('dockerview.utils.time_utils.datetime')
    def test_minutes_and_seconds(self, mock_datetime):
        """Test formatting when uptime is minutes and seconds."""
        now = datetime(2025, 6, 17, 12, 5, 30, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started 2 minutes 15 seconds ago
        start_time = datetime(2025, 6, 17, 12, 3, 15, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "2m 15s"

    @patch('dockerview.utils.time_utils.datetime')
    def test_minutes_only(self, mock_datetime):
        """Test formatting when uptime is exact minutes."""
        now = datetime(2025, 6, 17, 12, 10, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started exactly 10 minutes ago
        start_time = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "10m"

    @patch('dockerview.utils.time_utils.datetime')
    def test_hours_and_minutes(self, mock_datetime):
        """Test formatting when uptime is hours and minutes."""
        now = datetime(2025, 6, 17, 14, 35, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started 2 hours 15 minutes ago
        start_time = datetime(2025, 6, 17, 12, 20, 0, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "2h 15m"

    @patch('dockerview.utils.time_utils.datetime')
    def test_hours_only(self, mock_datetime):
        """Test formatting when uptime is exact hours."""
        now = datetime(2025, 6, 17, 15, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started exactly 3 hours ago
        start_time = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "3h"

    @patch('dockerview.utils.time_utils.datetime')
    def test_days_and_hours(self, mock_datetime):
        """Test formatting when uptime is days and hours."""
        now = datetime(2025, 6, 19, 15, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started 2 days 3 hours ago
        start_time = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "2d 3h"

    @patch('dockerview.utils.time_utils.datetime')
    def test_days_only(self, mock_datetime):
        """Test formatting when uptime is exact days."""
        now = datetime(2025, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started exactly 3 days ago
        start_time = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "3d"

    @patch('dockerview.utils.time_utils.datetime')
    def test_future_timestamp(self, mock_datetime):
        """Test that future timestamps return 'N/A'."""
        now = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container "started" 1 hour in the future
        start_time = datetime(2025, 6, 17, 13, 0, 0, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "N/A"

    def test_docker_timestamp_with_z_suffix(self):
        """Test parsing Docker timestamps with Z suffix."""
        # This test uses a relative time calculation
        with patch('dockerview.utils.time_utils.datetime') as mock_datetime:
            now = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = now
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Docker format with Z suffix
            start_time = "2025-06-17T10:00:00Z"
            assert format_uptime(start_time) == "2h"

    def test_docker_timestamp_with_nanoseconds(self):
        """Test parsing Docker timestamps with nanosecond precision."""
        with patch('dockerview.utils.time_utils.datetime') as mock_datetime:
            now = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = now
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Docker format with nanoseconds (9 decimal places)
            # The nanoseconds will be truncated to microseconds, causing a slight difference
            start_time = "2025-06-17T11:30:00.123456789Z"
            result = format_uptime(start_time)
            # Should be approximately 30 minutes (might be 29m 59s due to microsecond truncation)
            assert result in ["30m", "29m 59s"]

    def test_timestamp_with_timezone_offset(self):
        """Test parsing timestamps with timezone offset."""
        with patch('dockerview.utils.time_utils.datetime') as mock_datetime:
            now = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = now
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Timestamp with +00:00 timezone
            start_time = "2025-06-17T09:00:00+00:00"
            assert format_uptime(start_time) == "3h"

    @patch('dockerview.utils.time_utils.datetime')
    def test_zero_seconds(self, mock_datetime):
        """Test formatting when container just started."""
        now = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started at the same time as now
        start_time = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        assert format_uptime(start_time.isoformat()) == "0s"

    @patch('dockerview.utils.time_utils.datetime')
    def test_large_uptime(self, mock_datetime):
        """Test formatting for containers running for many days."""
        now = datetime(2025, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Container started 100 days 5 hours ago
        start_time = now - timedelta(days=100, hours=5)
        assert format_uptime(start_time.isoformat()) == "100d 5h"

    def test_exception_handling(self):
        """Test that exceptions during parsing return 'N/A'."""
        # Test with a malformed timestamp that will cause parsing to fail
        assert format_uptime("2025-06-17T12:00:00.INVALIDZ") == "N/A"
        
        # Test with a timestamp that has invalid structure
        assert format_uptime("not-a-valid-iso-format") == "N/A"