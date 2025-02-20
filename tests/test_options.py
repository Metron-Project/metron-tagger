import pytest

from metrontagger.options import make_parser


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
                "--interactive",
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
                "id": "12345",
                "delete": True,
                "ignore_existing": True,
                "interactive": True,
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
