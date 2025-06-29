"""Tests for filesorter.py module"""

from pathlib import Path
from shutil import Error as ShutilError
from unittest.mock import Mock, call, patch

import pytest
from darkseid.comic import MetadataFormat
from darkseid.metadata import Metadata

from metrontagger.filesorter import CleanedMetadata, FileSizeInfo, FileSorter, get_file_size_mb


# Fixtures
@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path / "test_sort"


@pytest.fixture
def file_sorter(temp_dir):
    """Create a FileSorter instance for testing."""
    return FileSorter(temp_dir)


@pytest.fixture
def mock_metadata():
    """Create a mock metadata object with all fields."""
    metadata = Mock(spec=Metadata)

    # Mock publisher
    metadata.publisher = Mock()
    metadata.publisher.name = "Marvel Comics"
    metadata.publisher.imprint = Mock()
    metadata.publisher.imprint.name = "Marvel"

    # Mock series
    metadata.series = Mock()
    metadata.series.name = "Amazing Spider-Man"
    metadata.series.volume = "1"
    metadata.series.format = "Ongoing"

    return metadata


@pytest.fixture
def mock_metadata_minimal():
    """Create a mock metadata object with minimal fields."""
    metadata = Mock(spec=Metadata)

    # Mock publisher without imprint
    metadata.publisher = Mock()
    metadata.publisher.name = "DC Comics"
    metadata.publisher.imprint = None

    # Mock series
    metadata.series = Mock()
    metadata.series.name = "Batman"
    metadata.series.volume = "2"
    metadata.series.format = "Ongoing"

    return metadata


@pytest.fixture
def mock_metadata_incomplete():
    """Create a mock metadata object with missing fields."""
    metadata = Mock(spec=Metadata)
    metadata.publisher = None
    metadata.series = None

    return metadata


@pytest.fixture
def mock_comic_file(tmp_path):
    """Create a mock comic file for testing."""
    comic_file = tmp_path / "test_comic.cbz"
    comic_file.write_bytes(b"fake comic data")
    return comic_file


# Test get_file_size_mb function
def test_get_file_size_mb_success(tmp_path):
    """Test successful file size calculation."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"x" * 1048576)  # 1 MB

    size = get_file_size_mb(test_file)
    assert size == 1.0


def test_get_file_size_mb_nonexistent_file():
    """Test file size calculation for non-existent file."""
    nonexistent_file = Path("/nonexistent/file.txt")

    with pytest.raises(OSError):  # noqa: PT011
        get_file_size_mb(nonexistent_file)


# Test FileSorter initialization
def test_file_sorter_init_valid_directory(temp_dir):
    """Test FileSorter initialization with valid directory."""
    sorter = FileSorter(temp_dir)
    assert sorter.sort_directory == temp_dir


def test_file_sorter_init_string_directory(tmp_path):
    """Test FileSorter initialization with string directory path."""
    sorter = FileSorter(str(tmp_path))
    assert sorter.sort_directory == tmp_path


def test_file_sorter_init_empty_directory():
    """Test FileSorter initialization with empty directory."""
    with pytest.raises(ValueError, match="Directory path cannot be empty or None"):
        FileSorter("")


def test_file_sorter_init_none_directory():
    """Test FileSorter initialization with None directory."""
    with pytest.raises(ValueError, match="Directory path cannot be empty or None"):
        FileSorter(None)  # type: ignore


# Test _cleanup_metadata method
def test_cleanup_metadata_with_imprint(file_sorter, mock_metadata):
    """Test metadata cleanup when imprint is available."""
    with patch("metrontagger.filesorter.cleanup_string") as mock_cleanup:
        mock_cleanup.side_effect = lambda x: x.lower().replace(" ", "_")

        result = file_sorter._cleanup_metadata(mock_metadata)

        assert result.publisher == "marvel"
        assert result.series == "amazing_spider-man"
        assert result.volume == "1"


def test_cleanup_metadata_without_imprint(file_sorter, mock_metadata_minimal):
    """Test metadata cleanup when imprint is not available."""
    with patch("metrontagger.filesorter.cleanup_string") as mock_cleanup:
        mock_cleanup.side_effect = lambda x: x.lower().replace(" ", "_")

        result = file_sorter._cleanup_metadata(mock_metadata_minimal)

        assert result.publisher == "dc_comics"
        assert result.series == "batman"
        assert result.volume == "2"


def test_cleanup_metadata_no_publisher(file_sorter, mock_metadata_incomplete):
    """Test metadata cleanup when publisher is missing."""
    result = file_sorter._cleanup_metadata(mock_metadata_incomplete)

    assert result.publisher is None
    assert result.series is None
    assert result.volume is None


# Test _move_file_safely method
@patch("metrontagger.filesorter.move")
@patch("metrontagger.filesorter.questionary")
def test_move_file_safely_success(mock_questionary, mock_move, file_sorter, tmp_path):
    """Test successful file move."""
    source = tmp_path / "source.cbz"
    source.write_text("test")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    result = file_sorter._move_file_safely(source, dest_dir)

    assert result is True
    mock_move.assert_called_once_with(str(source), str(dest_dir / "source.cbz"))
    mock_questionary.print.assert_called_once()


@patch("metrontagger.filesorter.move")
@patch("metrontagger.filesorter.questionary")
def test_move_file_safely_shutil_error(mock_questionary, mock_move, file_sorter, tmp_path):
    """Test file move with shutil error."""
    mock_move.side_effect = ShutilError("Permission denied")

    source = tmp_path / "source.cbz"
    dest_dir = tmp_path / "dest"

    result = file_sorter._move_file_safely(source, dest_dir)

    assert result is False
    mock_questionary.print.assert_called_once()


@patch("metrontagger.filesorter.move")
@patch("metrontagger.filesorter.questionary")
def test_move_file_safely_unexpected_error(mock_questionary, mock_move, file_sorter, tmp_path):
    """Test file move with unexpected error."""
    mock_move.side_effect = Exception("Unexpected error")

    source = tmp_path / "source.cbz"
    dest_dir = tmp_path / "dest"

    result = file_sorter._move_file_safely(source, dest_dir)

    assert result is False
    mock_questionary.print.assert_called_once()


# Test _get_file_size_comparison method
def test_get_file_size_comparison_success(file_sorter, tmp_path):
    """Test successful file size comparison."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_bytes(b"x" * 1048576)  # 1 MB
    file2.write_bytes(b"x" * 2097152)  # 2 MB

    result = file_sorter._get_file_size_comparison(file1, file2)

    assert isinstance(result, FileSizeInfo)
    assert result.existing_mb == 1.0
    assert result.new_mb == 2.0


def test_get_file_size_comparison_error(file_sorter):
    """Test file size comparison with non-existent file."""
    file1 = Path("/nonexistent1.txt")
    file2 = Path("/nonexistent2.txt")

    with pytest.raises(OSError):  # noqa: PT011
        file_sorter._get_file_size_comparison(file1, file2)


# Test _handle_existing_file method
def test_handle_existing_file_no_conflict(file_sorter, tmp_path):
    """Test handling when no existing file conflict."""
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    source_file = tmp_path / "source.cbz"

    result = file_sorter._handle_existing_file(dest_dir, source_file)

    assert result is True


@patch("metrontagger.filesorter.questionary")
def test_handle_existing_file_overwrite_confirmed(mock_questionary, file_sorter, tmp_path):
    """Test handling existing file with overwrite confirmed."""
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    source_file = tmp_path / "source.cbz"
    source_file.write_bytes(b"source data")
    existing_file = dest_dir / "source.cbz"
    existing_file.write_bytes(b"existing data")

    mock_questionary.confirm.return_value.ask.return_value = True

    result = file_sorter._handle_existing_file(dest_dir, source_file)

    assert result is True
    assert not existing_file.exists()


@patch("metrontagger.filesorter.questionary")
def test_handle_existing_file_overwrite_declined(mock_questionary, file_sorter, tmp_path):
    """Test handling existing file with overwrite declined."""
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    source_file = tmp_path / "source.cbz"
    source_file.write_bytes(b"source data")
    existing_file = dest_dir / "source.cbz"
    existing_file.write_bytes(b"existing data")

    mock_questionary.confirm.return_value.ask.return_value = False

    result = file_sorter._handle_existing_file(dest_dir, source_file)

    assert result is False
    assert existing_file.exists()


# Test _build_destination_path method
def test_build_destination_path_regular_series(file_sorter, mock_metadata):
    """Test building destination path for regular series."""
    cleaned = CleanedMetadata("marvel", "spider-man", "1")

    result = file_sorter._build_destination_path(mock_metadata, cleaned)
    expected = file_sorter.sort_directory / "marvel" / "spider-man" / "v1"

    assert result == expected


def test_build_destination_path_trade_paperback(file_sorter, mock_metadata):
    """Test building destination path for trade paperback."""
    mock_metadata.series.format = "Trade Paperback"
    cleaned = CleanedMetadata("dc", "batman", "2")

    result = file_sorter._build_destination_path(mock_metadata, cleaned)
    expected = file_sorter.sort_directory / "dc" / "batman TPB" / "v2"

    assert result == expected


# Test _create_directory_structure method
def test_create_directory_structure_success(file_sorter, tmp_path):
    """Test successful directory structure creation."""
    path = tmp_path / "publisher" / "series" / "volume"

    result = file_sorter._create_directory_structure(path)

    assert result is True
    assert path.exists()


def test_create_directory_structure_already_exists(file_sorter, tmp_path):
    """Test directory structure creation when path already exists."""
    path = tmp_path / "existing"
    path.mkdir()

    result = file_sorter._create_directory_structure(path)

    assert result is True


# TODO: Need to figure out how to patch Path's mkdir method
# @patch('metrontagger.filesorter.questionary')
# def test_create_directory_structure_permission_error(mock_questionary, file_sorter):
#     """Test directory structure creation with permission error."""
#     path = Path("/root/forbidden")
#
#     with patch.object(path, 'mkdir', side_effect=PermissionError):
#         result = file_sorter._create_directory_structure(path)
#
#     assert result is False
#     mock_questionary.print.assert_called_once()


# @patch('metrontagger.filesorter.questionary')
# def test_create_directory_structure_os_error(mock_questionary, file_sorter):
#     """Test directory structure creation with OS error."""
#     path = Path("/invalid/path")
#
#     with patch.object(path, 'mkdir', side_effect=OSError):
#         result = file_sorter._create_directory_structure(path)
#
#     assert result is False
#     mock_questionary.print.assert_called_once()


# Test _load_comic_metadata method
@patch("metrontagger.filesorter.Comic")
def test_load_comic_metadata_success_metron(mock_comic_class, file_sorter, mock_comic_file):
    """Test successful metadata loading with MetronInfo format."""
    mock_comic = Mock()
    mock_comic.has_metadata.side_effect = lambda fmt: fmt == MetadataFormat.METRON_INFO
    mock_comic.read_metadata.return_value = Mock(spec=Metadata)
    mock_comic_class.return_value = mock_comic

    result = file_sorter._load_comic_metadata(mock_comic_file)

    assert result is not None
    mock_comic.has_metadata.assert_called_with(MetadataFormat.METRON_INFO)
    mock_comic.read_metadata.assert_called_with(MetadataFormat.METRON_INFO)


@patch("metrontagger.filesorter.Comic")
def test_load_comic_metadata_success_comic_rack(
    mock_comic_class, file_sorter, mock_comic_file
):
    """Test successful metadata loading with ComicRack format."""
    mock_comic = Mock()
    mock_comic.has_metadata.side_effect = lambda fmt: fmt == MetadataFormat.COMIC_INFO
    mock_comic.read_metadata.return_value = Mock(spec=Metadata)
    mock_comic_class.return_value = mock_comic

    result = file_sorter._load_comic_metadata(mock_comic_file)

    assert result is not None
    mock_comic.has_metadata.assert_has_calls(
        [call(MetadataFormat.METRON_INFO), call(MetadataFormat.COMIC_INFO)]
    )
    mock_comic.read_metadata.assert_called_with(MetadataFormat.COMIC_INFO)


@patch("metrontagger.filesorter.Comic")
def test_load_comic_metadata_no_metadata(mock_comic_class, file_sorter, mock_comic_file):
    """Test metadata loading when no metadata is available."""
    mock_comic = Mock()
    mock_comic.has_metadata.return_value = False
    mock_comic_class.return_value = mock_comic

    result = file_sorter._load_comic_metadata(mock_comic_file)

    assert result is None


# @patch("metrontagger.filesorter.Comic")
# def test_load_comic_metadata_comic_open_error(mock_comic_class, file_sorter, mock_comic_file):
#     """Test metadata loading when comic file cannot be opened."""
#     mock_comic_class.side_effect = Exception("Cannot open comic")
#
#     result = file_sorter._load_comic_metadata(mock_comic_file)
#
#     assert result is None


# Test _validate_metadata_completeness method
@patch("metrontagger.filesorter.questionary")
def test_validate_metadata_completeness_complete(mock_questionary, file_sorter):
    """Test validation with complete metadata."""
    cleaned = CleanedMetadata("Marvel", "Spider-Man", "1")

    result = file_sorter._validate_metadata_completeness(cleaned, "test.cbz")

    assert result is True
    mock_questionary.print.assert_not_called()


@patch("metrontagger.filesorter.questionary")
def test_validate_metadata_completeness_incomplete(mock_questionary, file_sorter):
    """Test validation with incomplete metadata."""
    cleaned = CleanedMetadata(None, "Spider-Man", None)

    result = file_sorter._validate_metadata_completeness(cleaned, "test.cbz")

    assert result is False
    mock_questionary.print.assert_called_once()


# Test sort_comics method (integration tests)
def test_sort_comics_nonexistent_file(file_sorter):
    """Test sorting non-existent comic file."""
    nonexistent_file = Path("/nonexistent/comic.cbz")

    result = file_sorter.sort_comics(nonexistent_file)

    assert result is False


@patch("metrontagger.filesorter.FileSorter._load_comic_metadata")
def test_sort_comics_no_metadata(mock_load_metadata, file_sorter, mock_comic_file):
    """Test sorting comic with no metadata."""
    mock_load_metadata.return_value = None

    result = file_sorter.sort_comics(mock_comic_file)

    assert result is False


@patch("metrontagger.filesorter.FileSorter._load_comic_metadata")
@patch("metrontagger.filesorter.FileSorter._cleanup_metadata")
@patch("metrontagger.filesorter.FileSorter._validate_metadata_completeness")
def test_sort_comics_incomplete_metadata(
    mock_validate, mock_cleanup, mock_load_metadata, file_sorter, mock_comic_file
):
    """Test sorting comic with incomplete metadata."""
    mock_load_metadata.return_value = Mock()
    mock_cleanup.return_value = CleanedMetadata(None, None, None)
    mock_validate.return_value = False

    result = file_sorter.sort_comics(mock_comic_file)

    assert result is False


@patch("metrontagger.filesorter.FileSorter._load_comic_metadata")
@patch("metrontagger.filesorter.FileSorter._cleanup_metadata")
@patch("metrontagger.filesorter.FileSorter._validate_metadata_completeness")
@patch("metrontagger.filesorter.FileSorter._build_destination_path")
@patch("metrontagger.filesorter.FileSorter._create_directory_structure")
def test_sort_comics_directory_creation_fails(  # noqa: PLR0913
    mock_create_dir,
    mock_build_path,
    mock_validate,
    mock_cleanup,
    mock_load_metadata,
    file_sorter,
    mock_comic_file,
):
    """Test sorting comic when directory creation fails."""
    mock_load_metadata.return_value = Mock()
    mock_cleanup.return_value = CleanedMetadata("Marvel", "Spider-Man", "1")
    mock_validate.return_value = True
    mock_build_path.return_value = Path("/some/path")
    mock_create_dir.return_value = False

    result = file_sorter.sort_comics(mock_comic_file)

    assert result is False


@patch("metrontagger.filesorter.FileSorter._load_comic_metadata")
@patch("metrontagger.filesorter.FileSorter._cleanup_metadata")
@patch("metrontagger.filesorter.FileSorter._validate_metadata_completeness")
@patch("metrontagger.filesorter.FileSorter._build_destination_path")
@patch("metrontagger.filesorter.FileSorter._create_directory_structure")
@patch("metrontagger.filesorter.FileSorter._handle_existing_file")
def test_sort_comics_existing_file_conflict(  # noqa: PLR0913
    mock_handle_existing,
    mock_create_dir,
    mock_build_path,
    mock_validate,
    mock_cleanup,
    mock_load_metadata,
    file_sorter,
    mock_comic_file,
):
    """Test sorting comic with existing file conflict."""
    mock_load_metadata.return_value = Mock()
    mock_cleanup.return_value = CleanedMetadata("Marvel", "Spider-Man", "1")
    mock_validate.return_value = True
    mock_build_path.return_value = Path("/some/path")
    mock_create_dir.return_value = True
    mock_handle_existing.return_value = False

    result = file_sorter.sort_comics(mock_comic_file)

    assert result is False


@patch("metrontagger.filesorter.FileSorter._load_comic_metadata")
@patch("metrontagger.filesorter.FileSorter._cleanup_metadata")
@patch("metrontagger.filesorter.FileSorter._validate_metadata_completeness")
@patch("metrontagger.filesorter.FileSorter._build_destination_path")
@patch("metrontagger.filesorter.FileSorter._create_directory_structure")
@patch("metrontagger.filesorter.FileSorter._handle_existing_file")
@patch("metrontagger.filesorter.FileSorter._move_file_safely")
def test_sort_comics_success(  # noqa: PLR0913
    mock_move_file,
    mock_handle_existing,
    mock_create_dir,
    mock_build_path,
    mock_validate,
    mock_cleanup,
    mock_load_metadata,
    file_sorter,
    mock_comic_file,
):
    """Test successful comic sorting."""
    mock_load_metadata.return_value = Mock()
    mock_cleanup.return_value = CleanedMetadata("Marvel", "Spider-Man", "1")
    mock_validate.return_value = True
    mock_build_path.return_value = Path("/some/path")
    mock_create_dir.return_value = True
    mock_handle_existing.return_value = True
    mock_move_file.return_value = True

    result = file_sorter.sort_comics(mock_comic_file)

    assert result is True


# Test CleanedMetadata NamedTuple
def test_cleaned_metadata_creation():
    """Test CleanedMetadata creation and access."""
    cleaned = CleanedMetadata("Marvel", "Spider-Man", "1")

    assert cleaned.publisher == "Marvel"
    assert cleaned.series == "Spider-Man"
    assert cleaned.volume == "1"


# Test FileSizeInfo NamedTuple
def test_file_size_info_creation():
    """Test FileSizeInfo creation and access."""
    size_info = FileSizeInfo(1.5, 2.0)

    assert size_info.existing_mb == 1.5
    assert size_info.new_mb == 2.0
