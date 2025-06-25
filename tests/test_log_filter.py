"""Tests for the LogFilter class."""

import pytest

from dockerview.services.log_filter import LogFilter


class TestLogFilter:
    """Test cases for the LogFilter class."""

    @pytest.fixture
    def log_filter(self):
        """Create a LogFilter instance for testing."""
        return LogFilter(max_lines=10)

    def test_initialization(self):
        """Test LogFilter initialization with default and custom values."""
        # Test default initialization
        filter1 = LogFilter()
        assert filter1.max_lines == 2000
        assert len(filter1.all_log_lines) == 0
        assert filter1.search_filter == ""
        assert filter1.filtered_line_count == 0
        assert filter1.marker_pattern == "------ MARKED "
        assert filter1.pending_marker_context == 0

        # Test custom max_lines
        filter2 = LogFilter(max_lines=100)
        assert filter2.max_lines == 100

    def test_add_single_line(self, log_filter):
        """Test adding a single log line."""
        log_filter.add_line("Test log line")
        assert len(log_filter.all_log_lines) == 1
        assert log_filter.all_log_lines[0] == "Test log line"
        assert log_filter.get_line_count() == 1

    def test_add_multiple_lines(self, log_filter):
        """Test adding multiple log lines at once."""
        lines = ["Line 1", "Line 2", "Line 3"]
        log_filter.add_lines(lines)
        assert len(log_filter.all_log_lines) == 3
        assert list(log_filter.all_log_lines) == lines
        assert log_filter.get_line_count() == 3

    def test_clear(self, log_filter):
        """Test clearing all log lines and resetting state."""
        log_filter.add_lines(["Line 1", "Line 2", "Line 3"])
        log_filter.set_filter("test")
        log_filter.filtered_line_count = 5
        log_filter.pending_marker_context = 2

        log_filter.clear()

        assert len(log_filter.all_log_lines) == 0
        assert log_filter.get_line_count() == 0
        assert log_filter.filtered_line_count == 0
        assert log_filter.pending_marker_context == 0
        # Note: search_filter is not cleared
        assert log_filter.search_filter == "test"

    def test_buffer_max_lines_overflow(self):
        """Test that buffer respects max_lines limit."""
        log_filter = LogFilter(max_lines=5)
        
        # Add more lines than max_lines
        for i in range(10):
            log_filter.add_line(f"Line {i}")
        
        # Should only keep the last 5 lines
        assert len(log_filter.all_log_lines) == 5
        expected_lines = [f"Line {i}" for i in range(5, 10)]
        assert list(log_filter.all_log_lines) == expected_lines

    def test_set_filter(self, log_filter):
        """Test setting and updating the search filter."""
        # Test setting filter
        log_filter.set_filter("error")
        assert log_filter.search_filter == "error"

        # Test trimming whitespace
        log_filter.set_filter("  warning  ")
        assert log_filter.search_filter == "warning"

        # Test empty filter
        log_filter.set_filter("")
        assert log_filter.search_filter == ""

    def test_has_filter(self, log_filter):
        """Test checking if a filter is active."""
        assert not log_filter.has_filter()

        log_filter.set_filter("test")
        assert log_filter.has_filter()

        log_filter.set_filter("")
        assert not log_filter.has_filter()

        log_filter.set_filter("   ")  # Only whitespace
        assert not log_filter.has_filter()

    def test_matches_filter_no_filter(self, log_filter):
        """Test that all lines match when no filter is set."""
        assert log_filter.matches_filter("Any line")
        assert log_filter.matches_filter("")
        assert log_filter.matches_filter("Special characters !@#$%")

    def test_matches_filter_case_insensitive(self, log_filter):
        """Test case-insensitive filter matching."""
        log_filter.set_filter("ERROR")
        
        assert log_filter.matches_filter("Error in application")
        assert log_filter.matches_filter("error in application")
        assert log_filter.matches_filter("ERROR in application")
        assert log_filter.matches_filter("This is an eRrOr")
        assert not log_filter.matches_filter("This is a warning")

    def test_matches_filter_marker_always_shown(self, log_filter):
        """Test that marker lines always match regardless of filter."""
        log_filter.set_filter("error")
        
        # Marker line should always match
        assert log_filter.matches_filter("------ MARKED at 2024-01-01 ------")
        assert log_filter.matches_filter("Some text ------ MARKED timestamp")
        
        # Non-marker lines follow normal filter rules
        assert not log_filter.matches_filter("This is a warning")
        assert log_filter.matches_filter("This is an error")

    def test_get_filtered_lines_no_filter(self, log_filter):
        """Test getting all lines when no filter is set."""
        lines = ["Line 1", "Line 2", "Line 3"]
        log_filter.add_lines(lines)
        
        filtered = log_filter.get_filtered_lines()
        assert filtered == lines
        assert log_filter.get_filtered_line_count() == 3

    def test_get_filtered_lines_with_filter(self, log_filter):
        """Test filtering lines with a search filter."""
        log_filter.add_lines([
            "Error in module A",
            "Warning in module B",
            "Error in module C",
            "Info: All good",
            "Debug: Error count = 0"
        ])
        
        log_filter.set_filter("error")
        filtered = log_filter.get_filtered_lines()
        
        assert len(filtered) == 3
        assert "Error in module A" in filtered
        assert "Error in module C" in filtered
        assert "Debug: Error count = 0" in filtered
        assert log_filter.get_filtered_line_count() == 3

    def test_get_filtered_lines_marker_with_context(self, log_filter):
        """Test that marker lines include context lines."""
        log_filter.add_lines([
            "Line 0",
            "Line 1",
            "Line 2",
            "------ MARKED at timestamp ------",
            "Line 4",
            "Line 5",
            "Line 6"
        ])
        
        # Set filter that doesn't match any regular lines
        log_filter.set_filter("xyz")
        filtered = log_filter.get_filtered_lines()
        
        # Should include marker and 2 lines before/after
        assert len(filtered) == 5
        expected = [
            "Line 1",
            "Line 2", 
            "------ MARKED at timestamp ------",
            "Line 4",
            "Line 5"
        ]
        assert filtered == expected

    def test_get_filtered_lines_multiple_markers(self, log_filter):
        """Test filtering with multiple marker lines."""
        log_filter.add_lines([
            "Line 0",
            "------ MARKED 1 ------",
            "Line 2",
            "Line 3",
            "Line 4",
            "------ MARKED 2 ------",
            "Line 6"
        ])
        
        log_filter.set_filter("xyz")  # Filter that matches nothing
        filtered = log_filter.get_filtered_lines()
        
        # Should include both markers and their context
        # Marker 1: Line 0, marker, Line 2, Line 3
        # Marker 2: Line 4, marker, Line 6
        assert len(filtered) == 7  # All lines due to overlapping context

    def test_get_filtered_lines_marker_at_boundaries(self, log_filter):
        """Test marker context at buffer boundaries."""
        # Marker at start
        log_filter.clear()
        log_filter.add_lines([
            "------ MARKED start ------",
            "Line 1",
            "Line 2",
            "Line 3"
        ])
        
        log_filter.set_filter("xyz")
        filtered = log_filter.get_filtered_lines()
        # Should show marker + 2 after (no lines before)
        assert len(filtered) == 3
        assert filtered[0] == "------ MARKED start ------"
        
        # Marker at end
        log_filter.clear()
        log_filter.add_lines([
            "Line 0",
            "Line 1",
            "Line 2",
            "------ MARKED end ------"
        ])
        
        filtered = log_filter.get_filtered_lines()
        # Should show 2 before + marker (no lines after)
        assert len(filtered) == 3
        assert filtered[-1] == "------ MARKED end ------"

    def test_should_show_line_with_context_marker(self, log_filter):
        """Test real-time filtering with marker context."""
        # Test marker line starts context
        assert log_filter.should_show_line_with_context("------ MARKED test ------")
        assert log_filter.pending_marker_context == 2
        
        # Next 2 lines should be shown due to context
        assert log_filter.should_show_line_with_context("Line after marker 1")
        assert log_filter.pending_marker_context == 1
        
        assert log_filter.should_show_line_with_context("Line after marker 2")
        assert log_filter.pending_marker_context == 0
        
        # Context exhausted, should use normal filter
        log_filter.set_filter("error")
        assert not log_filter.should_show_line_with_context("Normal line")
        assert log_filter.should_show_line_with_context("Error line")

    def test_should_show_line_with_context_look_ahead(self, log_filter):
        """Test look-ahead functionality for upcoming markers."""
        # Add some lines including a marker
        log_filter.add_lines([
            "Line 1",
            "Line 2",
            "------ MARKED test ------"
        ])
        
        log_filter.set_filter("xyz")  # Filter that matches nothing
        
        # Should show line because marker is within 3 lines
        assert log_filter.should_show_line_with_context("New line")

    def test_complex_filtering_scenario(self, log_filter):
        """Test a complex scenario with mixed content."""
        log_filter.add_lines([
            "2024-01-01 INFO: Application started",
            "2024-01-01 ERROR: Connection failed",
            "2024-01-01 INFO: Retrying connection",
            "------ MARKED Important Section ------",
            "2024-01-01 DEBUG: Connection params: host=localhost",
            "2024-01-01 DEBUG: Connection params: port=5432",
            "2024-01-01 INFO: Connection successful",
            "2024-01-01 ERROR: Query failed",
            "2024-01-01 INFO: Application stopped"
        ])
        
        # Filter for ERROR
        log_filter.set_filter("ERROR")
        filtered = log_filter.get_filtered_lines()
        
        # Should include:
        # - Both ERROR lines
        # - Marker line and its context (2 before, 2 after)
        assert any("ERROR: Connection failed" in line for line in filtered)
        assert any("ERROR: Query failed" in line for line in filtered)
        assert "------ MARKED Important Section ------" in filtered
        assert any("INFO: Retrying connection" in line for line in filtered)  # Context before marker
        assert any("DEBUG: Connection params: host=localhost" in line for line in filtered)  # Context after marker

    def test_empty_log_operations(self, log_filter):
        """Test operations on empty log."""
        # No lines added
        assert log_filter.get_line_count() == 0
        assert log_filter.get_filtered_lines() == []
        assert log_filter.get_filtered_line_count() == 0
        assert log_filter.matches_filter("any line")
        assert log_filter.should_show_line_with_context("any line")

    def test_state_consistency(self, log_filter):
        """Test that state remains consistent across operations."""
        # Add lines and set filter
        log_filter.add_lines(["Error 1", "Info 1", "Error 2"])
        log_filter.set_filter("Error")
        
        # Get filtered lines multiple times
        filtered1 = log_filter.get_filtered_lines()
        filtered2 = log_filter.get_filtered_lines()
        
        # Results should be consistent
        assert filtered1 == filtered2
        assert log_filter.get_filtered_line_count() == 2
        
        # Add more lines
        log_filter.add_line("Error 3")
        filtered3 = log_filter.get_filtered_lines()
        
        assert len(filtered3) == 3
        assert log_filter.get_filtered_line_count() == 3