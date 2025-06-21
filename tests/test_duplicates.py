"""Tests for the duplicates module."""

import io
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from PIL import Image

from metrontagger.duplicates import DuplicateIssue, Duplicates


# Fixtures for test data
@pytest.fixture
def sample_files():
    """Create sample file paths for testing."""
    return [Path("comic1.cbz"), Path("comic2.cbz"), Path("comic3.cbz")]


@pytest.fixture
def empty_file_list():
    """Return empty file list for testing."""
    return []


@pytest.fixture
def sample_duplicate_issue():
    """Create a sample DuplicateIssue for testing."""
    return DuplicateIssue("test_comic.cbz", [0, 1, 2])


@pytest.fixture
def mock_comic():
    """Create a mock Comic object."""
    comic = Mock()
    comic.path = Path("test_comic.cbz")
    comic.is_writable.return_value = True
    comic.get_number_of_pages.return_value = 3
    return comic


@pytest.fixture
def mock_image_data():
    """Create mock image data."""
    # Create a simple test image
    img = Image.new("RGB", (100, 100), color="red")
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    return img_buffer.getvalue()


# TODO: Need to mock PIL's Image.show(), so we can test that.


# DuplicateIssue tests
def test_duplicate_issue_creation():
    """Test DuplicateIssue creation and basic properties."""
    duplicate = DuplicateIssue("test.cbz", [0, 1])
    assert duplicate.path_ == "test.cbz"
    assert duplicate.pages_index == [0, 1]


def test_duplicate_issue_repr():
    """Test DuplicateIssue string representation."""
    duplicate = DuplicateIssue("/path/to/comic.cbz", [0])
    repr_str = repr(duplicate)
    assert "DuplicateIssue" in repr_str
    assert "comic.cbz" in repr_str


def test_duplicate_issue_add_page_index():
    """Test adding page indices to DuplicateIssue."""
    duplicate = DuplicateIssue("test.cbz", [0])

    # Add new index
    duplicate.add_page_index(1)
    assert 1 in duplicate.pages_index
    assert len(duplicate.pages_index) == 2

    # Try to add duplicate index
    duplicate.add_page_index(1)
    assert len(duplicate.pages_index) == 2  # Should not add duplicate


# Duplicates class initialization tests
def test_duplicates_init_success(sample_files):
    """Test successful initialization of Duplicates class."""
    duplicates = Duplicates(sample_files)
    assert duplicates._file_lst == sample_files
    assert duplicates._data_frame is None
    assert len(duplicates._hash_cache) == 0


def test_duplicates_init_empty_list():
    """Test initialization with empty file list raises ValueError."""
    with pytest.raises(ValueError, match="File list cannot be empty"):
        Duplicates([])


def test_duplicates_context_manager(sample_files):
    """Test Duplicates as context manager."""
    with Duplicates(sample_files) as duplicates:
        assert duplicates._file_lst == sample_files
    # Cache should be cleared after exiting context
    assert duplicates._data_frame is None
    assert len(duplicates._hash_cache) == 0


# Hash calculation tests
def test_calculate_image_hash_success(mock_image_data):
    """Test successful image hash calculation."""
    with patch("metrontagger.duplicates.average_hash") as mock_hash:
        mock_hash.return_value = "test_hash_value"
        result = Duplicates._calculate_image_hash(mock_image_data)
        assert result == "test_hash_value"


def test_calculate_image_hash_invalid_image():
    """Test hash calculation with invalid image data."""
    invalid_data = b"not_an_image"
    result = Duplicates._calculate_image_hash(invalid_data)
    assert result is None


def test_calculate_image_hash_os_error():
    """Test hash calculation with OS error."""
    with patch("metrontagger.duplicates.Image.open", side_effect=OSError("File error")):
        result = Duplicates._calculate_image_hash(b"some_data")
        assert result is None


# Comic processing tests
@patch("metrontagger.duplicates.Comic")
def test_process_comic_pages_success(mock_comic_class, sample_files, mock_image_data):
    """Test successful comic page processing."""
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.get_number_of_pages.return_value = 2
    mock_comic.get_page.return_value = mock_image_data
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)

    with patch.object(duplicates, "_calculate_image_hash", return_value="hash123"):
        pages = list(duplicates._process_comic_pages(mock_comic))

        assert len(pages) == 2
        assert pages[0]["path"] == str(mock_comic.path)
        assert pages[0]["index"] == 0
        assert pages[0]["hash"] == "hash123"


@patch("metrontagger.duplicates.Comic")
def test_process_comic_pages_hash_failure(mock_comic_class, sample_files):
    """Test comic page processing when hash calculation fails."""
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.get_number_of_pages.return_value = 1
    mock_comic.get_page.return_value = b"invalid_image"
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)

    with patch.object(duplicates, "_calculate_image_hash", return_value=None):
        pages = list(duplicates._process_comic_pages(mock_comic))
        assert not pages


@patch("metrontagger.duplicates.Comic")
def test_process_comic_pages_exception(mock_comic_class, sample_files):
    """Test comic page processing with exception during page retrieval."""
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.get_number_of_pages.return_value = 1
    mock_comic.get_page.side_effect = Exception("Page read error")
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)
    pages = list(duplicates._process_comic_pages(mock_comic))
    assert not pages


# DataFrame building tests
@patch("metrontagger.duplicates.Comic")
def test_build_dataframe_success(mock_comic_class, sample_files):
    """Test successful DataFrame building."""
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.is_writable.return_value = True
    mock_comic.get_number_of_pages.return_value = 1
    mock_comic.get_page.return_value = b"image_data"
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)

    with (
        patch.object(duplicates, "_calculate_image_hash", return_value="hash123"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        df = duplicates._build_dataframe()

        assert not df.empty
        assert len(df) == len(sample_files)  # One page per file
        assert "path" in df.columns
        assert "index" in df.columns
        assert "hash" in df.columns


@patch("metrontagger.duplicates.Comic")
def test_build_dataframe_no_valid_hashes(mock_comic_class, sample_files):
    """Test DataFrame building when no valid hashes are found."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.get_number_of_pages.return_value = 1
    mock_comic.get_page.return_value = b"image_data"
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)

    with (
        patch.object(duplicates, "_calculate_image_hash", return_value=None),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        df = duplicates._build_dataframe()
        assert df.empty


def test_build_dataframe_caching(sample_files):
    """Test that DataFrame is cached after first build."""
    duplicates = Duplicates(sample_files)
    mock_df = pd.DataFrame({"test": [1, 2, 3]})
    duplicates._data_frame = mock_df

    # Should return cached DataFrame without processing
    result = duplicates._build_dataframe()
    assert result is mock_df


# Duplicate detection tests
def test_get_duplicate_pages_dataframe():
    """Test getting DataFrame with only duplicate pages."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)

    # Mock DataFrame with duplicates
    test_data = pd.DataFrame(
        {
            "path": ["comic1.cbz", "comic2.cbz", "comic3.cbz"],
            "index": [0, 1, 0],
            "hash": ["hash1", "hash1", "hash2"],
        }
    )
    duplicates._data_frame = test_data

    duplicate_df = duplicates.get_duplicate_pages_dataframe()

    # Should only contain rows with hash1 (the duplicate)
    assert len(duplicate_df) == 2
    assert all(duplicate_df["hash"] == "hash1")


def test_get_duplicate_pages_dataframe_empty():
    """Test getting duplicate pages when no data exists."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)
    duplicates._data_frame = pd.DataFrame()

    result = duplicates.get_duplicate_pages_dataframe()
    assert result.empty


def test_get_distinct_hashes():
    """Test getting distinct hash values."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)

    with patch.object(duplicates, "get_duplicate_pages_dataframe") as mock_get_dupes:
        mock_df = pd.DataFrame({"hash": ["hash1", "hash1", "hash2", "hash2"]})
        mock_get_dupes.return_value = mock_df

        hashes = duplicates.get_distinct_hashes()
        assert len(hashes) == 2
        assert "hash1" in hashes
        assert "hash2" in hashes


def test_get_distinct_hashes_empty():
    """Test getting distinct hashes when no duplicates exist."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)

    with patch.object(duplicates, "get_duplicate_pages_dataframe") as mock_get_dupes:
        mock_get_dupes.return_value = pd.DataFrame()

        hashes = duplicates.get_distinct_hashes()
        assert hashes == []


# Comic info retrieval tests
def test_get_comic_info_for_hash_found():
    """Test retrieving comic info for existing hash."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)
    duplicates._hash_cache["hash1"] = [{"path": "comic1.cbz", "index": 0}]

    result = duplicates.get_comic_info_for_hash("hash1")

    assert result is not None
    assert result.path_ == "comic1.cbz"
    assert result.pages_index == [0]


def test_get_comic_info_for_hash_not_found():
    """Test retrieving comic info for non-existing hash."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)

    result = duplicates.get_comic_info_for_hash("nonexistent_hash")
    assert result is None


def test_get_comic_list_from_hash():
    """Test getting list of comics from hash."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)
    duplicates._hash_cache["hash1"] = [
        {"path": "comic1.cbz", "index": 0},
        {"path": "comic2.cbz", "index": 1},
    ]

    result = duplicates.get_comic_list_from_hash("hash1")

    assert len(result) == 2
    assert result[0].path_ == "comic1.cbz"
    assert result[1].path_ == "comic2.cbz"


def test_get_comic_list_from_hash_not_found():
    """Test getting comic list for non-existing hash."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)

    result = duplicates.get_comic_list_from_hash("nonexistent_hash")
    assert result == []


# Page deletion tests
@patch("metrontagger.duplicates.Comic")
def test_delete_comic_pages_success(mock_comic_class):
    """Test successful page deletion."""
    mock_comic = Mock()
    mock_comic.remove_pages.return_value = True
    mock_comic_class.return_value = mock_comic

    duplicates_list = [DuplicateIssue("comic1.cbz", [0, 2])]

    with patch("metrontagger.duplicates.questionary"):
        results = Duplicates.delete_comic_pages(duplicates_list)

    assert results["comic1.cbz"] is True
    mock_comic.remove_pages.assert_called_once_with([2, 0])  # Reversed order


@patch("metrontagger.duplicates.Comic")
def test_delete_comic_pages_failure(mock_comic_class):
    """Test page deletion failure."""
    mock_comic = Mock()
    mock_comic.remove_pages.return_value = False
    mock_comic_class.return_value = mock_comic

    duplicates_list = [DuplicateIssue("comic1.cbz", [0])]

    with patch("metrontagger.duplicates.questionary"):
        results = Duplicates.delete_comic_pages(duplicates_list)

    assert results["comic1.cbz"] is False


# @patch("metrontagger.duplicates.Comic")
# def test_delete_comic_pages_exception(mock_comic_class):
#     """Test page deletion with exception."""
#     mock_comic_class.side_effect = ComicArchiveError
#
#     duplicates_list = [DuplicateIssue("comic1.cbz", [0])]
#
#     with patch("metrontagger.duplicates.questionary"):
#         results = Duplicates.delete_comic_pages(duplicates_list)
#
#     assert results["comic1.cbz"] is False


def test_delete_comic_pages_empty_list():
    """Test page deletion with empty list."""
    results = Duplicates.delete_comic_pages([])
    assert results == {}


def test_show_image_no_pages():
    """Test image display with no page indices."""
    duplicate_issue = DuplicateIssue("comic1.cbz", [])

    result = Duplicates.show_image(duplicate_issue)
    assert result is False


# @patch("metrontagger.duplicates.Comic")
# def test_show_image_exception(mock_comic_class):
#     """Test image display with exception."""
#     mock_comic = Mock()
#     mock_comic.get_page.side_effect = Exception("Page error")
#     mock_comic_class.return_value = mock_comic
#
#     duplicate_issue = DuplicateIssue("comic1.cbz", [0])
#
#     with patch("metrontagger.duplicates.questionary"):
#         result = Duplicates.show_image(duplicate_issue)
#         assert result is False


# Statistics tests
def test_get_statistics():
    """Test getting statistics about duplicate detection."""
    sample_files = [Path("test1.cbz"), Path("test2.cbz")]
    duplicates = Duplicates(sample_files)

    # Mock the data
    test_data = pd.DataFrame(
        {
            "path": ["comic1.cbz", "comic2.cbz", "comic3.cbz", "comic4.cbz"],
            "index": [0, 1, 0, 1],
            "hash": ["hash1", "hash1", "hash2", "hash3"],
        }
    )
    duplicates._data_frame = test_data

    with patch.object(duplicates, "get_distinct_hashes", return_value=["hash1"]):
        stats = duplicates.get_statistics()

    assert stats["total_pages"] == 4
    assert stats["duplicate_pages"] == 2  # Only hash1 pages
    assert stats["unique_duplicate_hashes"] == 1
    assert stats["comics_processed"] == 2


def test_get_statistics_empty():
    """Test getting statistics with no data."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)
    duplicates._data_frame = pd.DataFrame()

    with patch.object(duplicates, "get_distinct_hashes", return_value=[]):
        stats = duplicates.get_statistics()

    assert stats["total_pages"] == 0
    assert stats["duplicate_pages"] == 0
    assert stats["unique_duplicate_hashes"] == 0
    assert stats["comics_processed"] == 1


# Cache management tests
def test_clear_cache(sample_files):
    """Test cache clearing functionality."""
    duplicates = Duplicates(sample_files)

    # Set some cached data
    duplicates._data_frame = pd.DataFrame({"test": [1, 2, 3]})
    duplicates._hash_cache["test"] = [{"path": "test.cbz", "index": 0}]

    duplicates._clear_cache()

    assert duplicates._data_frame is None
    assert len(duplicates._hash_cache) == 0


def test_build_hash_cache():
    """Test hash cache building."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)

    test_data = pd.DataFrame(
        {"path": ["comic1.cbz", "comic2.cbz"], "index": [0, 1], "hash": ["hash1", "hash2"]}
    )
    duplicates._data_frame = test_data

    duplicates._build_hash_cache()

    assert "hash1" in duplicates._hash_cache
    assert "hash2" in duplicates._hash_cache
    assert duplicates._hash_cache["hash1"][0]["path"] == "comic1.cbz"
    assert duplicates._hash_cache["hash1"][0]["index"] == 0


def test_build_hash_cache_empty():
    """Test hash cache building with empty DataFrame."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)
    duplicates._data_frame = pd.DataFrame()

    duplicates._build_hash_cache()

    assert len(duplicates._hash_cache) == 0


def test_build_hash_cache_none():
    """Test hash cache building with None DataFrame."""
    sample_files = [Path("test.cbz")]
    duplicates = Duplicates(sample_files)
    duplicates._data_frame = None

    duplicates._build_hash_cache()

    assert len(duplicates._hash_cache) == 0


# Integration-style tests
@patch("metrontagger.duplicates.Comic")
def test_full_duplicate_detection_workflow(mock_comic_class, mock_image_data):
    """Test complete workflow from file list to duplicate detection."""
    sample_files = [Path("comic1.cbz"), Path("comic2.cbz")]

    # Mock two comics with identical pages
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.is_writable.return_value = True
    mock_comic.get_number_of_pages.return_value = 1
    mock_comic.get_page.return_value = mock_image_data
    mock_comic_class.return_value = mock_comic

    with (
        Duplicates(sample_files) as duplicates,
        patch.object(duplicates, "_calculate_image_hash", return_value="identical_hash"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        # Build the dataframe
        df = duplicates._build_dataframe()
        assert len(df) == 2

        # Get duplicates
        duplicate_df = duplicates.get_duplicate_pages_dataframe()
        assert len(duplicate_df) == 2  # Both pages are duplicates of each other

        # Get distinct hashes
        hashes = duplicates.get_distinct_hashes()
        assert len(hashes) == 1
        assert hashes[0] == "identical_hash"

        # Get comic info
        comic_info = duplicates.get_comic_info_for_hash("identical_hash")
        assert comic_info is not None

        # Get statistics
        stats = duplicates.get_statistics()
        assert stats["total_pages"] == 2
        assert stats["duplicate_pages"] == 2
        assert stats["unique_duplicate_hashes"] == 1


# Error handling tests
# @patch("metrontagger.duplicates.Comic")
# def test_generate_page_hashes_with_unwritable_comic(mock_comic_class, sample_files):
#     """Test handling of unwritable comics."""
#     mock_comic = Mock()
#     mock_comic.is_writable.return_value = False
#     mock_comic_class.return_value = mock_comic
#
#     duplicates = Duplicates(sample_files)
#
#     with patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x):
#         hashes = list(duplicates._generate_page_hashes())
#         assert not hashes


# @patch("metrontagger.duplicates.Comic")
# def test_generate_page_hashes_with_comic_exception(mock_comic_class, sample_files):
#     """Test handling of exceptions during comic processing."""
#     mock_comic_class.side_effect = Exception("Comic creation failed")
#
#     duplicates = Duplicates(sample_files)
#
#     with patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x):
#         hashes = list(duplicates._generate_page_hashes())
#         assert not hashes
