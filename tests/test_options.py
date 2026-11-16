import pytest

from metrontagger.options import check_args, make_parser


@pytest.mark.parametrize(
    ("cli_args", "expected_values"),
    [
        (
            ["/path/to/comic.cbz"],
            {"path": ["/path/to/comic.cbz"]},
        ),
        (
            ["/path/to/comic1.cbz", "/path/to/comic2.cbr"],
            {"path": ["/path/to/comic1.cbz", "/path/to/comic2.cbr"]},
        ),
        (
            ["--rename", "/path/to/comic.cbz"],
            {"rename": True, "path": ["/path/to/comic.cbz"]},
        ),
        (
            ["--online", "/path/to/comic.cbz"],
            {"online": True, "path": ["/path/to/comic.cbz"]},
        ),
        (
            ["--ignore-modified", "/path/to/comic.cbz"],
            {"ignore_modified": True, "path": ["/path/to/comic.cbz"]},
        ),
        (
            ["--metroninfo", "/path/to/comic.cbz"],
            {"metroninfo": True, "path": ["/path/to/comic.cbz"]},
        ),
        # ... (Test cases for all other arguments)
        (
            [
                "/path/to/comic.cbz",
                "--rename",
                "--online",
                "--metroninfo",
                "--comicinfo",
                "--id",
                "12345",
                "--delete",
                "--ignore-existing",
                "--skip-multiple",
                "--ignore-modified",
                "--missing",
                "--sort",
                "--export-to-cbz",
                "--validate",
                "--remove-non-valid",
                "--delete-original",
                "--duplicates",
                "--migrate",
            ],
            {
                "path": ["/path/to/comic.cbz"],
                "rename": True,
                "online": True,
                "metroninfo": True,
                "comicinfo": True,
                "id": 12345,
                "delete": True,
                "ignore_existing": True,
                "skip_multiple": True,
                "ignore_modified": True,
                "missing": True,
                "sort": True,
                "export_to_cbz": True,
                "validate": True,
                "remove_non_valid": True,
                "delete_original": True,
                "duplicates": True,
                "migrate": True,
            },
        ),
    ],
    ids=[
        "happy_path_single_file",
        "happy_path_multiple_files",
        "happy_path_rename",
        "happy_path_online",
        "happy_path_ignore_modified",
        "happy_path_metroninfo",
        "happy_path_all_options",
    ],
)
def test_make_parser(cli_args, expected_values):
    """Test the make_parser function."""

    # Act
    parser = make_parser()

    # Assert
    if isinstance(expected_values, dict):
        args = parser.parse_args(cli_args)
        for key, value in expected_values.items():
            assert getattr(args, key) == value


@pytest.mark.parametrize(
    "flags",
    [["--missing"], ["--delete"], ["--online"], ["--id", "42"], ["--validate"]],
    ids=["missing", "delete", "online", "id", "validate"],
)
def test_check_args_requires_metadata_format(
    flags: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    parser = make_parser()
    args = parser.parse_args(["comic.cbz", *flags])

    with pytest.raises(SystemExit) as exc:
        check_args(parser, args)

    assert exc.value.code == 2
    assert f"{flags[0]} requires --comicinfo and/or --metroninfo" in capsys.readouterr().err


def test_check_args_lists_every_offending_option(capsys: pytest.CaptureFixture[str]) -> None:
    parser = make_parser()
    args = parser.parse_args(["comic.cbz", "--delete", "--validate"])

    with pytest.raises(SystemExit):
        check_args(parser, args)

    assert "--delete, --validate requires" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["comic.cbz", "--delete", "-c"],
        ["comic.cbz", "--online", "-m"],
        ["comic.cbz", "--validate", "-c", "-m"],
        ["comic.cbz", "-r", "-s", "-z", "--migrate", "--duplicates"],
    ],
    ids=["delete_ci", "online_mi", "validate_both", "no_format_needed"],
)
def test_check_args_accepts_valid_combinations(argv: list[str]) -> None:
    parser = make_parser()

    check_args(parser, parser.parse_args(argv))
