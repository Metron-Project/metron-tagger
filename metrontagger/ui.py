"""Console output shared by every command.

All user-facing output goes through `UIPresenter` (or a subclass of it for output
specific to one feature), so styles and formatting stay consistent.
"""

__all__ = ["UIPresenter"]

import questionary

from metrontagger.styles import Styles
from metrontagger.utils import create_print_title


class UIPresenter:
    """Print styled messages to the console."""

    @staticmethod
    def print_error(message: str) -> None:
        """Print an error message."""
        questionary.print(message, style=Styles.ERROR)

    @staticmethod
    def print_warning(message: str) -> None:
        """Print a warning message."""
        questionary.print(message, style=Styles.WARNING)

    @staticmethod
    def print_info(message: str) -> None:
        """Print an info message."""
        questionary.print(message, style=Styles.INFO)

    @staticmethod
    def print_success(message: str) -> None:
        """Print a success message."""
        questionary.print(message, style=Styles.SUCCESS)

    @staticmethod
    def print_heading(message: str) -> None:
        """Print a message in the title style, without an underline."""
        questionary.print(message, style=Styles.TITLE)

    @staticmethod
    def print_title(title: str) -> None:
        """Print a section title, underlined and preceded by a blank line."""
        questionary.print(create_print_title(title), style=Styles.TITLE)
