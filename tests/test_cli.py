from unittest.mock import MagicMock, patch

import pytest

from metrontagger.cli import _metron_credentials, _set_sort_directory
from metrontagger.settings import MetronTaggerSettings


class MockQuestionary:
    def __init__(self, question: any, answers: any) -> None:
        self.question = question
        self.answers = answers

    def ask(self) -> any:
        return self.answers[self.question]


@patch("questionary.text")
def test__metron_credentials_existing_token_skips_prompts(
    mock_text: MagicMock, settings: MetronTaggerSettings
) -> None:
    """An existing API token means no prompts are shown at all."""
    settings["metron.auth_token"] = "existing-token"  # noqa: S105

    _metron_credentials(settings)

    mock_text.assert_not_called()
    assert settings["metron.auth_token"] == "existing-token"  # noqa: S105


@patch("questionary.confirm")
@patch("questionary.print")
def test__metron_credentials_offers_migration_for_existing_user_pass(
    mock_print: MagicMock,
    mock_confirm: MagicMock,
    settings: MetronTaggerSettings,
) -> None:
    """Existing username/password users are offered a one-time token migration."""
    settings["metron.user"] = "existing_username"
    settings["metron.password"] = "existing_password"

    mock_confirm.return_value.ask.return_value = True
    with patch("questionary.text") as mock_text:
        mock_text.return_value.ask.return_value = "new-token"
        _metron_credentials(settings)

    assert settings["metron.auth_token"] == "new-token"  # noqa: S105
    assert not settings["metron.user"]
    assert not settings["metron.password"]
    assert settings["metron.token_migration_prompted"] is True
    mock_print.assert_called_once()


@patch("questionary.confirm")
@patch("questionary.print")
def test__metron_credentials_migration_declined_keeps_user_pass(
    mock_print: MagicMock,
    mock_confirm: MagicMock,
    settings: MetronTaggerSettings,
) -> None:
    """Declining the migration offer keeps the existing username/password."""
    settings["metron.user"] = "existing_username"
    settings["metron.password"] = "existing_password"

    mock_confirm.return_value.ask.return_value = False

    _metron_credentials(settings)

    assert settings["metron.user"] == "existing_username"
    assert settings["metron.password"] == "existing_password"
    assert not settings["metron.auth_token"]
    # Should not be asked again on subsequent runs.
    assert settings["metron.token_migration_prompted"] is True
    mock_print.assert_called_once()


@patch("questionary.confirm")
@patch("questionary.print")
def test__metron_credentials_migration_not_offered_twice(
    mock_print: MagicMock,
    mock_confirm: MagicMock,
    settings: MetronTaggerSettings,
) -> None:
    """Once the migration has been offered, it isn't offered again."""
    settings["metron.user"] = "existing_username"
    settings["metron.password"] = "existing_password"
    settings["metron.token_migration_prompted"] = True

    _metron_credentials(settings)

    mock_confirm.assert_not_called()
    mock_print.assert_not_called()


@patch("questionary.confirm")
def test__metron_credentials_no_creds_chooses_token(
    mock_confirm: MagicMock, settings: MetronTaggerSettings
) -> None:
    """With no credentials configured, choosing token auth prompts for a token."""
    mock_confirm.return_value.ask.return_value = True

    with patch("questionary.text") as mock_text:
        mock_text.return_value.ask.return_value = "brand-new-token"
        _metron_credentials(settings)

    assert settings["metron.auth_token"] == "brand-new-token"  # noqa: S105
    assert not settings["metron.user"]
    assert not settings["metron.password"]


@patch("questionary.confirm")
def test__metron_credentials_no_creds_chooses_user_pass(
    mock_confirm: MagicMock, settings: MetronTaggerSettings
) -> None:
    """With no credentials configured, declining token auth prompts for username/password."""
    mock_confirm.return_value.ask.return_value = False

    mock_questionary = lambda question: MockQuestionary(  # noqa: E731
        question,
        {
            "What is your Metron username?": "test_username",
            "What is your Metron password?": "test_password",
        },
    )
    with patch("questionary.text", side_effect=mock_questionary):
        _metron_credentials(settings)

    assert settings["metron.user"] == "test_username"
    assert settings["metron.password"] == "test_password"
    assert not settings["metron.auth_token"]


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
