"""Tests for FileRenamer class using pytest without classes."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from metrontagger.filerenamer import FileRenamer, FormatMapping, TokenType


# Fixtures
@pytest.fixture
def mock_metadata():
    """Create a mock metadata object with common attributes."""
    metadata = Mock()

    # Series information
    metadata.series = Mock()
    metadata.series.name = "Amazing Spider-Man"
    metadata.series.volume = 1
    metadata.series.issue_count = 700
    metadata.series.format = "Comic"

    # Issue information
    metadata.issue = "1"

    # Date information
    metadata.cover_date = Mock()
    metadata.cover_date.year = 2023
    metadata.cover_date.month = 6

    # Publisher information
    metadata.publisher = Mock()
    metadata.publisher.name = "Marvel Comics"
    metadata.publisher.imprint = Mock()
    metadata.publisher.imprint.name = "Marvel"

    # Additional metadata
    metadata.alternate_series = None
    metadata.alternate_number = None
    metadata.alternate_count = None
    metadata.age_rating = "T+"
    metadata.series_group = None
    metadata.scan_info = None

    return metadata


@pytest.fixture
def minimal_metadata():
    """Create a minimal mock metadata object."""
    metadata = Mock()
    metadata.series = None
    metadata.issue = None
    metadata.cover_date = None
    metadata.publisher = None
    metadata.alternate_series = None
    metadata.alternate_number = None
    metadata.alternate_count = None
    metadata.age_rating = None
    metadata.series_group = None
    metadata.scan_info = None
    return metadata


@pytest.fixture
def file_renamer():
    """Create a FileRenamer instance."""
    return FileRenamer()


@pytest.fixture
def file_renamer_with_metadata(mock_metadata):
    """Create a FileRenamer instance with metadata."""
    return FileRenamer(metadata=mock_metadata)


@pytest.fixture
def mock_path():
    """Create a mock Path object."""
    path = Mock(spec=Path)
    path.name = "test_comic.cbz"
    path.suffix = ".cbz"
    path.parent = Path("/test/dir")
    return path


# Test Initialization
def test_filerenamer_init_default():
    """Test FileRenamer initialization with default values."""
    renamer = FileRenamer()

    assert renamer.metadata is None
    assert renamer.template == FileRenamer.DEFAULT_TEMPLATE
    assert renamer.smart_cleanup is True
    assert renamer.issue_zero_padding == FileRenamer.DEFAULT_ISSUE_PADDING


def test_filerenamer_init_with_metadata(mock_metadata):
    """Test FileRenamer initialization with metadata."""
    renamer = FileRenamer(metadata=mock_metadata)

    assert renamer.metadata == mock_metadata
    assert renamer.template == FileRenamer.DEFAULT_TEMPLATE


# Test Property Setters
def test_set_smart_cleanup(file_renamer):
    """Test setting smart cleanup option."""
    file_renamer.set_smart_cleanup(False)
    assert file_renamer.smart_cleanup is False

    file_renamer.set_smart_cleanup(True)
    assert file_renamer.smart_cleanup is True


def test_set_metadata(file_renamer, mock_metadata):
    """Test setting metadata."""
    file_renamer.set_metadata(mock_metadata)
    assert file_renamer.metadata == mock_metadata


def test_set_issue_zero_padding(file_renamer):
    """Test setting issue zero padding."""
    file_renamer.set_issue_zero_padding(5)
    assert file_renamer.issue_zero_padding == 5


def test_set_issue_zero_padding_negative_raises_error(file_renamer):
    """Test that negative padding raises ValueError."""
    with pytest.raises(ValueError, match="Issue zero padding must be non-negative"):
        file_renamer.set_issue_zero_padding(-1)


def test_set_template(file_renamer):
    """Test setting template."""
    custom_template = "%series% #%issue%"
    file_renamer.set_template(custom_template)
    assert file_renamer.template == custom_template


def test_set_template_empty_raises_error(file_renamer):
    """Test that empty template raises ValueError."""
    with pytest.raises(ValueError, match="Template cannot be empty"):
        file_renamer.set_template("")

    with pytest.raises(ValueError, match="Template cannot be empty"):
        file_renamer.set_template("   ")


# Test Token Enum
def test_token_type_enum():
    """Test TokenType enum values."""
    assert TokenType.SERIES.value == "%series%"
    assert TokenType.VOLUME.value == "%volume%"
    assert TokenType.ISSUE.value == "%issue%"
    assert TokenType.YEAR.value == "%year%"


# Test FormatMapping
def test_format_mapping():
    """Test FormatMapping functionality."""
    mapping = FormatMapping()

    assert mapping.get("Hardcover") == "HC"
    assert mapping.get("Trade Paperback") == "TPB"
    assert mapping.get("Unknown Format") == ""
    assert mapping.get("Unknown Format", "N/A") == "N/A"


# Test Helper Methods
def test_is_token(file_renamer):
    """Test _is_token static method."""
    assert file_renamer._is_token("%series%") is True
    assert file_renamer._is_token("%issue%") is True
    assert file_renamer._is_token("series") is False
    assert file_renamer._is_token("%") is False
    assert file_renamer._is_token("") is False


def test_remove_empty_separators():
    """Test _remove_empty_separators method."""
    assert FileRenamer._remove_empty_separators("Test ()") == "Test"
    assert FileRenamer._remove_empty_separators("Test [] {}") == "Test"
    assert FileRenamer._remove_empty_separators("Test (2023)") == "Test (2023)"
    assert FileRenamer._remove_empty_separators("Test ( - )") == "Test"


def test_remove_duplicate_hyphen_underscore():
    """Test _remove_duplicate_hyphen_underscore method."""
    assert FileRenamer._remove_duplicate_hyphen_underscore("Test--Name") == "Test-Name"
    assert FileRenamer._remove_duplicate_hyphen_underscore("Test__Name") == "Test_Name"
    assert FileRenamer._remove_duplicate_hyphen_underscore("Test---Name") == "Test-Name"
    assert FileRenamer._remove_duplicate_hyphen_underscore("Test-Name") == "Test-Name"


def test_smart_cleanup_string(file_renamer):
    """Test smart cleanup string functionality."""
    test_cases = [
        ("Test  ()  Name", "Test Name"),
        # ("Test -- Name", "Test Name"),
        ("Test   Multiple   Spaces", "Test Multiple Spaces"),
        ("Test Name --", "Test Name"),
        ("Test [] {} ()", "Test"),
    ]

    for input_str, expected in test_cases:
        result = file_renamer._smart_cleanup_string(input_str)
        assert result == expected


def test_format_issue_string(file_renamer):
    """Test issue string formatting."""
    assert file_renamer._format_issue_string(None) is None

    # Mock IssueString to test formatting
    with patch("metrontagger.filerenamer.IssueString") as mock_issue_string:
        mock_instance = Mock()
        mock_instance.as_string.return_value = "001"
        mock_issue_string.return_value = mock_instance

        result = file_renamer._format_issue_string("1")
        mock_issue_string.assert_called_with("1")
        mock_instance.as_string.assert_called_with(pad=3)
        assert result == "001"


def test_format_issue_string_half_issue(file_renamer):
    """Test formatting of half issue symbol."""
    with patch("metrontagger.filerenamer.IssueString") as mock_issue_string:
        mock_instance = Mock()
        mock_instance.as_string.return_value = "000.5"
        mock_issue_string.return_value = mock_instance

        result = file_renamer._format_issue_string("½")
        mock_issue_string.assert_called_with("0.5")
        assert result == "000.5"


def test_get_month_name(file_renamer):
    """Test month name extraction."""
    assert file_renamer._get_month_name(1) == "January"
    assert file_renamer._get_month_name(6) == "June"
    assert file_renamer._get_month_name(12) == "December"
    assert file_renamer._get_month_name(13) is None
    assert file_renamer._get_month_name(0) is None
    assert file_renamer._get_month_name("invalid") is None


# Test Token Replacement
def test_replace_token_with_value(file_renamer):
    """Test token replacement with a value."""
    text = "Amazing %series% #%issue%"
    result = file_renamer._replace_token(text, "Spider-Man", TokenType.SERIES)
    assert result == "Amazing Spider-Man #%issue%"


def test_replace_token_none_value_no_smart_cleanup(file_renamer):
    """Test token replacement with None value and smart cleanup disabled."""
    file_renamer.set_smart_cleanup(False)
    text = "Amazing %series% #%issue%"
    result = file_renamer._replace_token(text, None, TokenType.SERIES)
    assert result == "Amazing  #%issue%"


def test_replace_token_none_value_with_smart_cleanup(file_renamer):
    """Test token replacement with None value and smart cleanup enabled."""
    text = "Amazing %series% #%issue%"
    result = file_renamer._replace_token(text, None, TokenType.SERIES)
    assert result == "Amazing #%issue%"


def test_replace_token_issue_count_special_case(file_renamer):
    """Test special case for issue_count token replacement."""
    text = "Issue #%issue% (of %issue_count%)"
    result = file_renamer._replace_token(text, None, TokenType.ISSUE_COUNT)
    assert result == "Issue #%issue%"


# Test Metadata Extraction
def test_extract_metadata_values_full(file_renamer_with_metadata):
    """Test metadata extraction with full metadata."""
    values = file_renamer_with_metadata._extract_metadata_values()

    assert values[TokenType.SERIES] == "Amazing Spider-Man"
    assert values[TokenType.VOLUME] == 1
    assert values[TokenType.ISSUE_COUNT] == 700
    assert values[TokenType.YEAR] == 2023
    assert values[TokenType.MONTH] == 6
    assert values[TokenType.MONTH_NAME] == "June"
    assert values[TokenType.PUBLISHER] == "Marvel Comics"
    assert values[TokenType.IMPRINT] == "Marvel"


def test_extract_metadata_values_minimal(file_renamer, minimal_metadata):
    """Test metadata extraction with minimal metadata."""
    file_renamer.set_metadata(minimal_metadata)
    values = file_renamer._extract_metadata_values()

    assert values[TokenType.SERIES] == "Unknown"
    assert values[TokenType.VOLUME] == 0
    assert values[TokenType.YEAR] == "Unknown"
    assert values[TokenType.PUBLISHER] == "Unknown"


def test_extract_metadata_values_no_metadata(file_renamer):
    """Test metadata extraction with no metadata."""
    values = file_renamer._extract_metadata_values()
    assert values == {}


# Test Filename Determination
@patch("metrontagger.filerenamer.cleanup_string")
def test_determine_name_success(mock_cleanup, file_renamer_with_metadata, mock_path):
    """Test successful filename determination."""
    mock_cleanup.return_value = "cleaned_name.cbz"

    result = file_renamer_with_metadata.determine_name(mock_path)

    assert result == "cleaned_name.cbz"
    mock_cleanup.assert_called_once()


def test_determine_name_no_metadata(file_renamer, mock_path):
    """Test filename determination without metadata."""
    result = file_renamer.determine_name(mock_path)
    assert result is None


@patch("metrontagger.filerenamer.cleanup_string")
def test_determine_name_with_custom_template(
    mock_cleanup, file_renamer_with_metadata, mock_path
):
    """Test filename determination with custom template."""
    mock_cleanup.return_value = "custom_name.cbz"
    file_renamer_with_metadata.set_template("%series% #%issue%")

    result = file_renamer_with_metadata.determine_name(mock_path)

    assert result == "custom_name.cbz"


# Test File Renaming
@patch("metrontagger.filerenamer.questionary")
def test_rename_file_no_metadata(mock_questionary, file_renamer, mock_path):
    """Test file renaming without metadata."""
    result = file_renamer.rename_file(mock_path)

    assert result is None
    mock_questionary.print.assert_called_once()


@patch("metrontagger.filerenamer.questionary")
@patch("metrontagger.filerenamer.unique_file")
def test_rename_file_same_name(
    mock_unique_file, mock_questionary, file_renamer_with_metadata, mock_path
):
    """Test file renaming when filename is already correct."""
    file_renamer_with_metadata.set_template("test_comic")

    with patch.object(
        file_renamer_with_metadata, "determine_name", return_value="test_comic.cbz"
    ):
        result = file_renamer_with_metadata.rename_file(mock_path)

    assert result is None
    mock_questionary.print.assert_called_once()
    mock_unique_file.assert_not_called()


@patch("metrontagger.filerenamer.unique_file")
def test_rename_file_success(mock_unique_file, file_renamer_with_metadata, mock_path):
    """Test successful file renaming."""
    new_path = Path("/test/dir/new_name.cbz")
    mock_unique_file.return_value = new_path

    with patch.object(
        file_renamer_with_metadata, "determine_name", return_value="new_name.cbz"
    ):
        result = file_renamer_with_metadata.rename_file(mock_path)

    assert result == new_path
    mock_path.rename.assert_called_once_with(new_path)


@patch("metrontagger.filerenamer.questionary")
@patch("metrontagger.filerenamer.unique_file")
def test_rename_file_os_error(
    mock_unique_file, mock_questionary, file_renamer_with_metadata, mock_path
):
    """Test file renaming with OS error."""
    new_path = Path("/test/dir/new_name.cbz")
    mock_unique_file.return_value = new_path
    mock_path.rename.side_effect = OSError("Permission denied")

    with patch.object(
        file_renamer_with_metadata, "determine_name", return_value="new_name.cbz"
    ):
        result = file_renamer_with_metadata.rename_file(mock_path)

    assert result is None
    mock_questionary.print.assert_called()


# Integration Tests
def test_full_workflow_integration(mock_metadata):
    """Test complete workflow from initialization to file renaming."""
    renamer = FileRenamer()
    renamer.set_metadata(mock_metadata)
    renamer.set_template("%series% v%volume% #%issue% (%year%)")
    renamer.set_issue_zero_padding(3)

    mock_path = Mock(spec=Path)
    mock_path.name = "old_name.cbz"
    mock_path.suffix = ".cbz"
    mock_path.parent = Path("/test")

    with (
        patch("metrontagger.filerenamer.IssueString") as mock_issue_string,
        patch("metrontagger.filerenamer.cleanup_string") as mock_cleanup,
        patch("metrontagger.filerenamer.unique_file") as mock_unique_file,
    ):
        # Setup mocks
        mock_issue_instance = Mock()
        mock_issue_instance.as_string.return_value = "001"
        mock_issue_string.return_value = mock_issue_instance
        mock_cleanup.return_value = "Amazing Spider-Man v1 #001 (2023).cbz"
        mock_unique_file.return_value = Path("/test/Amazing Spider-Man v1 #001 (2023).cbz")

        # Test filename determination
        new_name = renamer.determine_name(mock_path)
        assert new_name == "Amazing Spider-Man v1 #001 (2023).cbz"

        # Test file renaming
        result = renamer.rename_file(mock_path)
        assert result == Path("/test/Amazing Spider-Man v1 #001 (2023).cbz")


# Parametrized Tests
@pytest.mark.parametrize(
    ("template", "expected_tokens"),
    [
        ("%series% #%issue%", [TokenType.SERIES, TokenType.ISSUE]),
        (
            "%series% v%volume% #%issue% (%year%)",
            [TokenType.SERIES, TokenType.VOLUME, TokenType.ISSUE, TokenType.YEAR],
        ),
        ("Simple filename", []),
    ],
)
def test_template_token_detection(template, expected_tokens):
    """Test that templates contain expected tokens."""
    for token in expected_tokens:
        assert token.value in template


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("Test  Multiple  Spaces", "Test Multiple Spaces"),
        ("Test--Dashes", "Test-Dashes"),
        ("Test__Underscores", "Test_Underscores"),
        ("Test () [] {}", "Test"),
        ("Clean String", "Clean String"),
    ],
)
def test_smart_cleanup_parametrized(input_str, expected):
    """Test smart cleanup with various inputs."""
    renamer = FileRenamer()
    result = renamer._smart_cleanup_string(input_str)
    assert result == expected


@pytest.mark.parametrize(
    ("month", "expected"),
    [
        (1, "January"),
        (6, "June"),
        (12, "December"),
        (13, None),
        (0, None),
        ("invalid", None),
    ],
)
def test_get_month_name_parametrized(month, expected):
    """Test month name extraction with various inputs."""
    renamer = FileRenamer()
    result = renamer._get_month_name(month)
    assert result == expected


# Edge Cases
def test_edge_case_empty_series_name(file_renamer):
    """Test handling of empty series name."""
    metadata = Mock()
    metadata.series = Mock()
    metadata.series.name = ""
    metadata.series.volume = 1
    metadata.issue = "1"
    metadata.cover_date = None
    metadata.publisher = None

    file_renamer.set_metadata(metadata)
    values = file_renamer._extract_metadata_values()

    assert values[TokenType.SERIES] == ""


def test_edge_case_very_long_template():
    """Test handling of very long template."""
    long_template = " ".join(["%series%"] * 100)
    renamer = FileRenamer()
    renamer.set_template(long_template)

    assert renamer.template == long_template


def test_edge_case_unicode_characters(mock_metadata):
    """Test handling of Unicode characters in metadata."""
    mock_metadata.series.name = "Spider-Man: Niño Araña"
    mock_metadata.publisher.name = "Marvel Cómics"

    renamer = FileRenamer(metadata=mock_metadata)
    values = renamer._extract_metadata_values()

    assert values[TokenType.SERIES] == "Spider-Man: Niño Araña"
    assert values[TokenType.PUBLISHER] == "Marvel Cómics"
