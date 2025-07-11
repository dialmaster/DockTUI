"""CSS styles for the LogPane component."""

LOG_PANE_CSS = """
LogPane {
    width: 50% !important;
    max-width: 50% !important;
    height: 100%;
    padding: 0;
    border-left: solid $primary-darken-1;
    background: $surface-darken-2;
    overflow-y: auto;
}

LogPane > Static.log-header {
    background: $primary-darken-1;
    color: white !important;
    text-align: center;
    height: 1;
    text-style: bold;
    padding: 0 1;
    border: none;
    dock: top;
}

.log-controls {
    height: 6;
    max-height: 6 !important;
    padding-top: 1;
    padding-bottom: 1;
    background: $surface;
    margin-top: 1;
    dock: top;
}

.log-controls-label {
    margin-top: 1;
    margin-left: 2;
}

.log-controls-search {
    height: 4;
    max-height: 4 !important;
    padding: 0 1;
    background: $surface;
    margin-top: 6;
    dock: top;
}


/* Container for the middle content, this contains the log display and the no selection display */
.log-content-container {
    min-height: 1fr;  /* Fill remaining space */
    width: 100%;
    overflow: auto;
}

.no-selection {
    height: 100%;
    text-align: center;
    color: $text-muted;
    width: 100%;
    padding: 0 0;
    content-align: center middle;
    background: $surface-darken-2;
    border: none;
}

.log-display {
    height: 100%;  /* Fill parent container */
    background: $surface-darken-1;
    padding: 0 1;
    border: none;
    display: none;
}

.log-display:focus {
    border: none;
}

#tail-select {
    width: 22;
    height: 3;
    margin: 0 1 0 0;
}

#since-select {
    width: 22;
    height: 3;
    margin: 0 1 0 0;
}

#search-input {
    width: 40%;
    max-width: 30;
    height: 3;
    margin-left: 1;
    margin-right: 0;
    margin-top: 0;
    margin-bottom: 0;
}

#auto-follow-checkbox {
    width: 20%;
    min-width: 15;
    max-width: 15;
    height: 3;
    padding: 0 1;
    margin-left: 1;
    margin-right: 0;
    margin-top: 0;
    margin-bottom: 0;
    content-align: center middle;
}

#mark-position-button {
    width: auto;
    min-width: 15;
    height: 3;
    margin-left: 1;
    margin-right: 0;
    margin-top: 0;
    margin-bottom: 0;
}

.log-footer {
    height: 2;
    padding: 0 1;
    background: $surface-darken-3;
    color: $text-muted;
    text-align: center;
    border-top: solid $primary-darken-3;
    dock: bottom;
}
"""

# Dropdown options configuration
TAIL_OPTIONS = [
    ("50 lines", "50"),
    ("100 lines", "100"),
    ("200 lines", "200"),
    ("400 lines", "400"),
    ("800 lines", "800"),
    ("1600 lines", "1600"),
    ("3200 lines", "3200"),
    ("6400 lines", "6400"),
    ("12800 lines", "12800"),
]

SINCE_OPTIONS = [
    ("5 minutes", "5m"),
    ("10 minutes", "10m"),
    ("15 minutes", "15m"),
    ("30 minutes", "30m"),
    ("1 hour", "1h"),
    ("2 hours", "2h"),
    ("4 hours", "4h"),
    ("8 hours", "8h"),
    ("24 hours", "24h"),
    ("48 hours", "48h"),
]

# No-selection display message
NO_SELECTION_MESSAGE = [
    ("Select a container or stack to view logs\n\n", "dim"),
    "• Click on a container to see its logs\n",
    "• Click on a stack header to see logs for all containers in the stack\n",
    "• Use the search box to filter log entries\n",
    "• Toggle auto-follow to stop/start automatic scrolling\n",
    "• Adjust log settings to change time range and line count\n\n",
    ("Text Selection:\n", "bold"),
    "• Click and drag with mouse to select text\n",
    "• Right-click on selected text to copy",
]
