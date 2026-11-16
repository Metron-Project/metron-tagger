"""Tests for the shared console output layer."""

from unittest.mock import patch

import pytest

from metrontagger.styles import Styles
from metrontagger.ui import UIPresenter


@pytest.mark.parametrize(
    ("method", "style"),
    [
        ("print_error", Styles.ERROR),
        ("print_warning", Styles.WARNING),
        ("print_info", Styles.INFO),
        ("print_success", Styles.SUCCESS),
        ("print_heading", Styles.TITLE),
    ],
)
def test_print_methods_use_their_style(method: str, style: str) -> None:
    with patch("metrontagger.ui.questionary.print") as mock_print:
        getattr(UIPresenter, method)("Some message")

    mock_print.assert_called_once_with("Some message", style=style)


def test_print_title_underlines_the_title() -> None:
    """print_title formats the title itself, so callers pass plain text."""
    with patch("metrontagger.ui.questionary.print") as mock_print:
        UIPresenter.print_title("Renaming Comic:")

    mock_print.assert_called_once_with(
        "\nRenaming Comic:\n---------------", style=Styles.TITLE
    )


def test_print_title_rejects_empty_title() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        UIPresenter.print_title("  ")
