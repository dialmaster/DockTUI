"""Status display widgets for DockTUI."""

from typing import Union

from rich.console import RenderableType
from rich.style import Style
from rich.text import Text
from textual.widgets import Static


class ErrorDisplay(Static):
    """A widget that displays error messages with error styling.

    The widget is hidden when there is no error message to display.
    """

    DEFAULT_CSS = """
    ErrorDisplay {
        background: $error;
        color: $text;
        padding: 0 2;
        height: auto;
        display: none;
    }
    """

    def update(self, renderable: RenderableType) -> None:
        """Update the error message and visibility state.

        Args:
            renderable: The error message to display
        """
        super().update(renderable)
        self.styles.display = "block" if renderable else "none"


class StatusBar(Static):
    """A widget that displays the current selection status at the bottom of the screen."""

    # Note that the bottom 2 rows of the StatusBar are hidden by the Footer widget
    DEFAULT_CSS = """
    StatusBar {
        background: $panel;
        color: $text-primary;
        height: 4;
        dock: bottom;
        padding-top: 0;
        margin-top: 0;
        text-align: center;
        text-style: bold;
    }
    """

    def __init__(self):
        """Initialize the status bar with an empty message."""
        no_selection_text = Text("No selection", Style(color="white", bold=True))
        super().__init__(no_selection_text)

    def update(self, message: Union[str, Text]) -> None:
        """Update the status bar with a new message.

        Args:
            message: The message to display in the status bar (string or Rich Text object)
        """
        super().update(message)
