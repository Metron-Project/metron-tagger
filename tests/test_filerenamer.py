from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from metrontagger.filerenamer import FileRenamer


@pytest.fixture()
def metadata():
    mock_metadata = Mock()
    mock_metadata.series.name = "Test Series"
    mock_metadata.series.volume = 1
    mock_metadata.issue = "1"
    mock_metadata.issue_count = 5
    mock_metadata.cover_date.year = 2021
    mock_metadata.cover_date.month = 5
    mock_metadata.publisher.name = "Test Publisher"
    mock_metadata.alternate_series = "Alt Series"
    mock_metadata.alternate_number = "Alt Number"
    mock_metadata.alternate_count = "Alt Count"
    mock_metadata.imprint = "Test Imprint"
    mock_metadata.series.format = "Hardcover"
    mock_metadata.age_rating = "PG-13"
    mock_metadata.series_group = "Group A"
    mock_metadata.scan_info = "Scan Info"
    return mock_metadata


@pytest.mark.parametrize(
    ("template", "expected_name"),
    [
        ("%series% v%volume% #%issue% (%year%)", "Test Series v1 #001 (2021).cbz"),
        ("%series% #%issue% (%year%)", "Test Series #001 (2021).cbz"),
        ("%series% #%issue% (%month_name%)", "Test Series #001 (May).cbz"),
    ],
    ids=["default_template", "no_volume", "month_name"],
)
def test_determine_name_happy_path(template, expected_name, metadata):
    # Arrange
    renamer = FileRenamer(metadata)
    renamer.set_template(template)
    filename = Path("test.cbz")

    # Act
    new_name = renamer.determine_name(filename)

    # Assert
    assert new_name == expected_name


@pytest.mark.parametrize(
    ("issue", "expected_issue_str"),
    [
        ("1", "001"),
        ("½", "000.5"),
        (None, None),
    ],
    ids=["normal_issue", "half_issue", "no_issue"],
)
def test_replace_token_issue(issue, expected_issue_str, metadata):
    # Arrange
    renamer = FileRenamer(metadata)
    renamer.set_issue_zero_padding(3)
    metadata.issue = issue
    text = "%issue%"

    # Act
    result = renamer.replace_token(text, expected_issue_str, "%issue%")

    # Assert
    assert result == (expected_issue_str or "")


@pytest.mark.parametrize(
    ("text", "value", "token", "expected"),
    [
        ("Test %token%", "value", "%token%", "Test value"),
        ("Test %token%", None, "%token%", "Test"),
    ],
    ids=["replace_with_value", "replace_with_none"],
)
def test_replace_token(text, value, token, expected):
    # Arrange
    renamer = FileRenamer()
    renamer.set_smart_cleanup(True)

    # Act
    result = renamer.replace_token(text, value, token)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("new_name", "expected"),
    [
        ("Test ()", "Test"),
        ("Test []", "Test"),
        ("Test {}", "Test"),
    ],
    ids=["empty_parentheses", "empty_brackets", "empty_braces"],
)
def test_remove_empty_separators(new_name, expected):
    # Act
    result = FileRenamer._remove_empty_separators(new_name)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("new_name", "expected"),
    [
        ("Test--Name", "Test-Name"),
        ("Test__Name", "Test_Name"),
    ],
    ids=["duplicate_hyphens", "duplicate_underscores"],
)
def test_remove_duplicate_hyphen_underscore(new_name, expected):
    # Act
    result = FileRenamer._remove_duplicate_hyphen_underscore(new_name)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("new_name", "expected"),
    [
        ("Test ()", "Test"),
        ("Test--Name", "Test-Name"),
        ("Test__Name", "Test_Name"),
        ("Test  Name", "Test Name"),
        ("Test-", "Test"),
    ],
    ids=[
        "empty_separators",
        "duplicate_hyphens",
        "duplicate_underscores",
        "duplicate_spaces",
        "trailing_dash",
    ],
)
def test_smart_cleanup_string(new_name, expected):
    # Arrange
    renamer = FileRenamer()

    # Act
    result = renamer.smart_cleanup_string(new_name)

    # Assert
    assert result == expected


# TODO: Need to add tests for mocking of questionary print results.
@pytest.mark.parametrize(
    (
        "metadata",
        "comic_name",
        "new_name",
        "expected_result",
        "print_called",
        "print_message",
        "print_style",
    ),
    [
        # Happy path
        ({"title": "Comic1"}, "comic1.cbz", "Comic1.cbz", "Comic1.cbz", False, None, None),
        # Edge case: new_name is None
        ({"title": "Comic3"}, "comic3.cbz", None, None, False, None, None),
    ],
    ids=["happy_path", "new_name_none"],
)
def test_rename_file(  # noqa: PLR0913
    metadata, comic_name, new_name, expected_result, print_called, print_message, print_style
):
    # Arrange
    comic_path = Path(comic_name)
    file_renamer = FileRenamer()
    file_renamer.metadata = metadata
    file_renamer.determine_name = MagicMock(return_value=new_name)

    # Act
    with (
        patch("questionary.print") as mock_print,
        patch(
            "darkseid.utils.unique_file",
            return_value=Path(expected_result) if expected_result else None,
        ),
        patch(
            "pathlib.Path.rename",
            return_value=Path(expected_result) if expected_result else None,
        ),
    ):
        result = file_renamer.rename_file(comic_path)

    # Assert
    if print_called:
        mock_print.assert_called_once_with(print_message, style=print_style)
    else:
        mock_print.assert_not_called()
    if expected_result:
        assert result == Path(expected_result)
    else:
        assert result is None
