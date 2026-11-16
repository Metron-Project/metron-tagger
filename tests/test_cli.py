from unittest.mock import MagicMock, patch

import pytest

from metrontagger.cli import _metron_credentials, _set_sort_directory, main
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


@pytest.mark.parametrize("answer", [None, "", "   "], ids=["ctrl_c", "empty", "blank"])
@patch("questionary.print")
@patch("questionary.text")
def test__metron_credentials_no_answer_exits_without_saving(
    mock_text: MagicMock, mock_print: MagicMock, settings: MetronTaggerSettings, answer
) -> None:
    """Ctrl-C (ask() returns None) or an empty answer exits, and nothing is saved."""
    mock_text.return_value.ask.return_value = answer

    with pytest.raises(SystemExit) as exc:
        _metron_credentials(settings)

    assert exc.value.code == 1
    assert settings["metron.auth_token"] == ""
    assert "None" not in settings.settings_file.read_text(encoding="utf-8")
    # An empty answer is explained; on Ctrl-C questionary already said "Cancelled".
    printed = " ".join(str(c.args[0]) for c in mock_print.call_args_list)
    assert ("token is needed" in printed) is (answer is not None)


@patch("questionary.print", new=MagicMock())
@patch("questionary.text")
def test__metron_credentials_strips_token(
    mock_text: MagicMock, settings: MetronTaggerSettings
) -> None:
    """A pasted token's surrounding whitespace isn't saved."""
    mock_text.return_value.ask.return_value = "  brand-new-token\n"

    _metron_credentials(settings)

    assert settings["metron.auth_token"] == "brand-new-token"  # noqa: S105


@patch("questionary.text")
def test__set_sort_directory_ctrl_c_exits_without_saving(
    mock_text: MagicMock, settings: MetronTaggerSettings
) -> None:
    mock_text.return_value.ask.return_value = None

    with pytest.raises(SystemExit):
        _set_sort_directory(settings)

    assert settings["sort.directory"] == ""


@pytest.mark.parametrize("answer", ["", "   "], ids=["empty", "blank"])
@patch("questionary.text")
def test__set_sort_directory_empty_answer_not_saved(
    mock_text: MagicMock, settings: MetronTaggerSettings, answer: str
) -> None:
    """An empty answer isn't saved, and doesn't exit: the sort step reports it."""
    mock_text.return_value.ask.return_value = answer

    _set_sort_directory(settings)

    assert settings["sort.directory"] == ""


@pytest.mark.parametrize(
    ("flags", "expect_token_prompt", "expect_sort_prompt"),
    [
        (["-r"], False, False),
        (["-o", "-c"], True, False),
        (["--id", "5", "-m"], True, False),
        (["-s"], False, True),
        (["-o", "-s", "-m"], True, True),
    ],
    ids=["rename_only", "online", "id", "sort", "online_and_sort"],
)
def test_main_prompts_then_runs(
    monkeypatch: pytest.MonkeyPatch,
    settings: MetronTaggerSettings,
    flags: list[str],
    expect_token_prompt: bool,
    expect_sort_prompt: bool,
) -> None:
    """main() asks only for the settings the requested operations need, then runs them."""
    monkeypatch.setattr("sys.argv", ["metron-tagger", "comic.cbz", *flags])
    monkeypatch.setattr("metrontagger.cli.init_logging", MagicMock())
    monkeypatch.setattr("metrontagger.cli.MetronTaggerSettings", lambda: settings)
    token_prompt = MagicMock()
    sort_prompt = MagicMock()
    runner_cls = MagicMock()
    monkeypatch.setattr("metrontagger.cli._metron_credentials", token_prompt)
    monkeypatch.setattr("metrontagger.cli._set_sort_directory", sort_prompt)
    monkeypatch.setattr("metrontagger.cli.Runner", runner_cls)

    main()

    assert token_prompt.called is expect_token_prompt
    assert sort_prompt.called is expect_sort_prompt
    args, runner_settings = runner_cls.call_args.args
    assert args.path == ["comic.cbz"]
    assert runner_settings is settings
    runner_cls.return_value.run.assert_called_once_with()


def test_main_rejects_invalid_args_before_prompting(
    monkeypatch: pytest.MonkeyPatch, settings: MetronTaggerSettings
) -> None:
    """Invalid options exit with a usage error before any prompt or operation."""
    monkeypatch.setattr("sys.argv", ["metron-tagger", "comic.cbz", "--online"])
    monkeypatch.setattr("metrontagger.cli.init_logging", MagicMock())
    monkeypatch.setattr("metrontagger.cli.MetronTaggerSettings", lambda: settings)
    token_prompt = MagicMock()
    runner_cls = MagicMock()
    monkeypatch.setattr("metrontagger.cli._metron_credentials", token_prompt)
    monkeypatch.setattr("metrontagger.cli.Runner", runner_cls)

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    token_prompt.assert_not_called()
    runner_cls.assert_not_called()
