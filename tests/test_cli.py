from unittest.mock import patch

import pytest

from metrontagger.cli import _metron_credentials, _set_sort_directory
from metrontagger.settings import MetronTaggerSettings


@pytest.mark.parametrize(
    ("username", "password", "expected_username", "expected_password"),
    [("existing_username", "existing_password", "existing_username", "existing_password")],
    ids=["happy_path_both_set"],
)
@patch("questionary.text")
@patch("metrontagger.cli.LOGGER")
def test__metron_credentials_happy_path(  # NOQA: PLR0913
    mock_logger: any,
    mock_questionary: any,
    username: str,
    password: str,
    expected_username: str,
    expected_password: str,
    settings: MetronTaggerSettings,
) -> None:
    # Arrange

    if username:
        settings["metron.username"] = username
    if password:
        settings["metron.password"] = password

    mock_questionary.side_effect = lambda question: MockQuestionary(
        question,
        {
            "What is your Metron username?": "test_username",
            "What is your Metron password?": "test_password",
        },
    )

    # Act
    _metron_credentials(settings)

    # Assert
    assert settings["metron.username"] == expected_username
    assert settings["metron.password"] == expected_password
    if username is None:
        mock_logger.info.assert_any_call("Added Metron username")
    if password is None:
        mock_logger.info.assert_any_call("Added Metron password")


@pytest.mark.parametrize(
    ("initial_sort_dir", "input_sort_dir", "expected_sort_dir"),
    [
        (None, "/test/sort/dir", "/test/sort/dir"),
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
    settings["DEFAULT.sort_dir"] = initial_sort_dir
    mock_questionary.return_value.ask.return_value = input_sort_dir  # Mock the user input

    # Act
    _set_sort_directory(settings)

    # Assert
    assert settings["DEFAULT.sort_dir"] == expected_sort_dir


class MockQuestionary:
    def __init__(self, question: any, answers: any) -> None:
        self.question = question
        self.answers = answers

    def ask(self) -> any:
        return self.answers[self.question]
