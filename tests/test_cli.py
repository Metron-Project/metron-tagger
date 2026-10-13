from unittest.mock import MagicMock, patch

import pytest

from metrontagger.cli import _metron_credentials, _set_sort_directory
from metrontagger.settings import MetronTaggerSettings


@patch("questionary.print")
@patch("questionary.text")
def test__metron_credentials_existing_token_skips_prompts(
    mock_text: MagicMock, mock_print: MagicMock, settings: MetronTaggerSettings
) -> None:
    """An existing API token means no prompts are shown at all."""
    settings["metron.auth_token"] = "existing-token"  # noqa: S105

    _metron_credentials(settings)

    mock_text.assert_not_called()
    mock_print.assert_not_called()
    assert settings["metron.auth_token"] == "existing-token"  # noqa: S105


@patch("questionary.print")
@patch("questionary.text")
def test__metron_credentials_no_token_prompts_for_token(
    mock_text: MagicMock, mock_print: MagicMock, settings: MetronTaggerSettings
) -> None:
    """Without an API token configured, the user is prompted for one."""
    mock_text.return_value.ask.return_value = "brand-new-token"

    _metron_credentials(settings)

    mock_text.assert_called_once_with("What is your Metron API token?")
    mock_print.assert_called_once()
    assert settings["metron.auth_token"] == "brand-new-token"  # noqa: S105


@pytest.mark.parametrize(
    ("initial_sort_dir", "input_sort_dir", "expected_sort_dir"),
    [
        ("", "/test/sort/dir", "/test/sort/dir"),
        (
            "/existing/sort/dir",
            "/test/sort/dir",
            "/existing/sort/dir",
        ),  # input_sort_dir is unused
    ],
    ids=["happy_path_none", "happy_path_set"],
)
@patch("questionary.text")
def test__set_sort_directory(
    mock_questionary,
    initial_sort_dir,
    input_sort_dir,
    expected_sort_dir,
    settings,
):
    """Test the _set_sort_directory function."""

    # Arrange
    settings["sort.directory"] = initial_sort_dir
    mock_questionary.return_value.ask.return_value = input_sort_dir  # Mock the user input

    # Act
    _set_sort_directory(settings)

    # Assert
    assert settings["sort.directory"] == expected_sort_dir
