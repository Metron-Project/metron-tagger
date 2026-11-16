"""Tests for the duplicates module."""

import io
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from darkseid.comic import ComicArchiveError
from imagehash import average_hash, hex_to_hash
from PIL import Image, JpegImagePlugin

from metrontagger.duplicates import DuplicateIssue, Duplicates, DuplicatesPresenter


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
    comic.can_remove_pages.return_value = True
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
    assert duplicates._hash_cache is None


def test_duplicates_init_empty_list():
    """Test initialization with empty file list raises ValueError."""
    with pytest.raises(ValueError, match="File list cannot be empty"):
        Duplicates([])


def test_duplicates_context_manager(sample_files):
    """Test Duplicates as context manager."""
    with Duplicates(sample_files) as duplicates:
        assert duplicates._file_lst == sample_files
    # Cache should be cleared after exiting context
    assert duplicates._hash_cache is None


# Hash calculation tests
def test_calculate_image_hash_success(mock_image_data):
    """Test successful image hash calculation."""
    with patch("metrontagger.duplicates.average_hash") as mock_hash:
        mock_hash.return_value = "test_hash_value"
        result = Duplicates._calculate_image_hash(mock_image_data)
        assert result == "test_hash_value"


def _jpeg_bytes(size=(800, 1200)):
    """Create JPEG data for a smooth gradient page."""
    img = Image.linear_gradient("L").resize(size).convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_calculate_image_hash_jpeg_uses_draft_mode():
    """Test that JPEGs are decoded at reduced size and still hash like a full decode."""
    data = _jpeg_bytes()
    with patch.object(
        JpegImagePlugin.JpegImageFile,
        "draft",
        autospec=True,
        side_effect=JpegImagePlugin.JpegImageFile.draft,
    ) as draft:
        result = Duplicates._calculate_image_hash(data)

    draft.assert_called_once()
    with Image.open(io.BytesIO(data)) as img:
        full_hash = average_hash(img)
    assert result is not None
    assert abs(hex_to_hash(result) - full_hash) <= 2


def test_calculate_image_hash_png_unaffected_by_draft(mock_image_data):
    """Test that non-JPEG images hash exactly as they did without draft mode."""
    with Image.open(io.BytesIO(mock_image_data)) as img:
        expected = str(average_hash(img))
    assert Duplicates._calculate_image_hash(mock_image_data) == expected


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


def test_calculate_image_hash_runtime_error():
    """A decoder RuntimeError (e.g. from pillow-jxl-plugin) is treated as a failed hash."""
    with patch(
        "metrontagger.duplicates.Image.open", side_effect=RuntimeError("decode failed")
    ):
        assert Duplicates._calculate_image_hash(b"some_data") is None


def test_calculate_image_hash_corrupt_jxl():
    """A truncated JPEG XL page yields no hash instead of raising."""
    pytest.importorskip("pillow_jxl")
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color="red").save(buf, format="JXL", lossless=True)
    truncated = buf.getvalue()[: len(buf.getvalue()) // 2]

    assert Duplicates._calculate_image_hash(truncated) is None


def test_calculate_image_hash_none_page_data():
    """Test hash calculation when the page couldn't be read (e.g. exceeds the size limit)."""
    assert Duplicates._calculate_image_hash(None) is None


# Comic processing tests
@patch("metrontagger.comics.Comic")
def test_process_comic_pages_success(mock_comic_class, sample_files, mock_image_data):
    """Test successful comic page processing."""
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.get_number_of_pages.return_value = 3
    mock_comic.get_page.return_value = mock_image_data
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)

    with patch.object(duplicates, "_calculate_image_hash", return_value="hash123"):
        pages = list(duplicates._process_comic_pages(mock_comic))

        assert len(pages) == 2
        assert pages[0]["path"] == str(mock_comic.path)
        assert pages[0]["index"] == 1
        assert pages[0]["hash"] == "hash123"


@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.comics.Comic")
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


# Scanning and duplicate lookup tests
def _scan_returns(duplicates: Duplicates, pages: list[tuple[str, int, str]]):
    """Patch `duplicates` to scan the given (path, index, hash) pages instead of comics."""
    return patch.object(
        duplicates,
        "_generate_page_hashes",
        return_value=iter([{"path": p, "index": i, "hash": h} for p, i, h in pages]),
    )


# hash_b and hash_a each appear on two pages; "unique" on only one.
SCANNED_PAGES = [
    ("a.cbz", 1, "hash_b"),
    ("b.cbz", 2, "hash_b"),
    ("a.cbz", 3, "hash_a"),
    ("c.cbz", 1, "hash_a"),
    ("c.cbz", 2, "unique"),
]


@patch("metrontagger.comics.Comic")
def test_scan_hashes_every_interior_page(mock_comic_class, sample_files):
    """A real scan (over mocked comics) hashes each interior page once."""
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.is_writable.return_value = True
    mock_comic.can_remove_pages.return_value = True
    mock_comic.get_number_of_pages.return_value = 2
    mock_comic.get_page.return_value = b"image_data"
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)

    with (
        patch.object(duplicates, "_calculate_image_hash", return_value="hash123"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        stats = duplicates.get_statistics()

    # One interior page per file (the cover is skipped), all with the same hash.
    assert stats["total_pages"] == len(sample_files)
    assert duplicates.get_distinct_hashes() == ["hash123"]


@patch("metrontagger.comics.Comic")
def test_scan_no_valid_hashes(mock_comic_class, sample_files, caplog):
    """Pages that can't be hashed are left out; with none left there are no duplicates."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.can_remove_pages.return_value = True
    mock_comic.get_number_of_pages.return_value = 2
    mock_comic.get_page.return_value = b"image_data"
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files)

    with (
        patch.object(duplicates, "_calculate_image_hash", return_value=None),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        assert duplicates.get_distinct_hashes() == []
        assert duplicates.get_statistics()["total_pages"] == 0

    assert "No valid page hashes found" in caplog.text


def test_get_distinct_hashes_only_repeated_hashes_sorted():
    duplicates = Duplicates([Path("test.cbz")])

    with _scan_returns(duplicates, SCANNED_PAGES):
        assert duplicates.get_distinct_hashes() == ["hash_a", "hash_b"]


def test_get_comic_list_from_hash_in_scan_order():
    duplicates = Duplicates([Path("test.cbz")])

    with _scan_returns(duplicates, SCANNED_PAGES):
        comics = duplicates.get_comic_list_from_hash("hash_b")

    assert [(c.path_, c.pages_index) for c in comics] == [("a.cbz", [1]), ("b.cbz", [2])]


def test_get_comic_list_from_hash_not_found():
    duplicates = Duplicates([Path("test.cbz")])

    with _scan_returns(duplicates, SCANNED_PAGES):
        assert duplicates.get_comic_list_from_hash("nonexistent_hash") == []


@pytest.mark.parametrize("pages", [SCANNED_PAGES, []], ids=["found", "nothing_found"])
def test_scan_runs_once(pages):
    """Every lookup shares one scan, even when the scan found nothing."""
    duplicates = Duplicates([Path("test.cbz")])

    with _scan_returns(duplicates, pages) as mock_generate:
        duplicates.get_distinct_hashes()
        duplicates.get_comic_list_from_hash("hash_a")
        duplicates.get_statistics()

    mock_generate.assert_called_once()


# Page deletion tests
@patch("metrontagger.comics.Comic")
def test_delete_comic_pages_success(mock_comic_class):
    """Test successful page deletion."""
    mock_comic = Mock()
    mock_comic.remove_pages.return_value = True
    mock_comic_class.return_value = mock_comic

    duplicates_list = [DuplicateIssue("comic1.cbz", [0, 2])]

    with patch("metrontagger.ui.questionary"):
        results = Duplicates.delete_comic_pages(duplicates_list)

    assert results["comic1.cbz"] is True
    mock_comic.remove_pages.assert_called_once_with([2, 0])  # Reversed order


@patch("metrontagger.comics.Comic")
def test_delete_comic_pages_failure(mock_comic_class):
    """Test page deletion failure."""
    mock_comic = Mock()
    mock_comic.remove_pages.return_value = False
    mock_comic_class.return_value = mock_comic

    duplicates_list = [DuplicateIssue("comic1.cbz", [0])]

    with patch("metrontagger.ui.questionary"):
        results = Duplicates.delete_comic_pages(duplicates_list)

    assert results["comic1.cbz"] is False


# @patch("metrontagger.comics.Comic")
# def test_delete_comic_pages_exception(mock_comic_class):
#     """Test page deletion with exception."""
#     mock_comic_class.side_effect = ComicArchiveError
#
#     duplicates_list = [DuplicateIssue("comic1.cbz", [0])]
#
#     with patch("metrontagger.ui.questionary"):
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


# @patch("metrontagger.comics.Comic")
# def test_show_image_exception(mock_comic_class):
#     """Test image display with exception."""
#     mock_comic = Mock()
#     mock_comic.get_page.side_effect = Exception("Page error")
#     mock_comic_class.return_value = mock_comic
#
#     duplicate_issue = DuplicateIssue("comic1.cbz", [0])
#
#     with patch("metrontagger.ui.questionary"):
#         result = Duplicates.show_image(duplicate_issue)
#         assert result is False


# Statistics tests
def test_get_statistics():
    """Test getting statistics about duplicate detection."""
    duplicates = Duplicates([Path("test1.cbz"), Path("test2.cbz")])

    with _scan_returns(duplicates, SCANNED_PAGES):
        stats = duplicates.get_statistics()

    assert stats == {
        "total_pages": 5,
        "duplicate_pages": 4,  # hash_a and hash_b pages, not "unique"
        "unique_duplicate_hashes": 2,
        "comics_processed": 2,
    }


def test_get_statistics_empty():
    """Test getting statistics with no data."""
    duplicates = Duplicates([Path("test.cbz")])

    with _scan_returns(duplicates, []):
        stats = duplicates.get_statistics()

    assert stats == {
        "total_pages": 0,
        "duplicate_pages": 0,
        "unique_duplicate_hashes": 0,
        "comics_processed": 1,
    }


# Cache management tests
def test_clear_cache_forces_rescan(sample_files):
    """After the cache is cleared, the next lookup scans the comics again."""
    duplicates = Duplicates(sample_files)

    with _scan_returns(duplicates, SCANNED_PAGES) as mock_generate:
        duplicates.get_distinct_hashes()
        duplicates._clear_cache()
        assert duplicates._hash_cache is None

        mock_generate.return_value = iter([])
        assert duplicates.get_distinct_hashes() == []

    assert mock_generate.call_count == 2


# Integration-style tests
@patch("metrontagger.comics.Comic")
def test_full_duplicate_detection_workflow(mock_comic_class, mock_image_data):
    """Test complete workflow from file list to duplicate detection."""
    sample_files = [Path("comic1.cbz"), Path("comic2.cbz")]

    # Mock two comics with identical pages
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.is_writable.return_value = True
    mock_comic.can_remove_pages.return_value = True
    mock_comic.get_number_of_pages.return_value = 2
    mock_comic.get_page.return_value = mock_image_data
    mock_comic_class.return_value = mock_comic

    with (
        Duplicates(sample_files) as duplicates,
        patch.object(duplicates, "_calculate_image_hash", return_value="identical_hash"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        # Get distinct hashes
        hashes = duplicates.get_distinct_hashes()
        assert len(hashes) == 1
        assert hashes[0] == "identical_hash"

        # Get the comics containing the duplicate image
        comics = duplicates.get_comic_list_from_hash("identical_hash")
        # One entry per comic; the cover (page 0) isn't scanned.
        assert [c.pages_index for c in comics] == [[1], [1]]

        # Get statistics
        stats = duplicates.get_statistics()
        assert stats["total_pages"] == 2
        assert stats["duplicate_pages"] == 2
        assert stats["unique_duplicate_hashes"] == 1


# Error handling tests
# @patch("metrontagger.comics.Comic")
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


# @patch("metrontagger.comics.Comic")
# def test_generate_page_hashes_with_comic_exception(mock_comic_class, sample_files):
#     """Test handling of exceptions during comic processing."""
#     mock_comic_class.side_effect = Exception("Comic creation failed")
#
#     duplicates = Duplicates(sample_files)
#
#     with patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x):
#         hashes = list(duplicates._generate_page_hashes())
#         assert not hashes


# Quick mode tests
def test_get_page_indices_normal_mode(sample_files):
    """Test that normal mode returns all page indices except the cover."""
    duplicates = Duplicates(sample_files)
    assert duplicates._get_page_indices(10) == list(range(1, 10))


def test_get_page_indices_quick_mode_many_pages(sample_files):
    """Test quick mode with a 10-page comic returns pages 1-3 and 7-9 (skip cover)."""
    duplicates = Duplicates(sample_files, quick=True)
    assert duplicates._get_page_indices(10) == [1, 2, 3, 7, 8, 9]


def test_get_page_indices_quick_mode_few_pages(sample_files):
    """Test quick mode with a 5-page comic returns pages 1-4 (deduplicated, skip cover)."""
    duplicates = Duplicates(sample_files, quick=True)
    assert duplicates._get_page_indices(5) == [1, 2, 3, 4]


def test_get_page_indices_quick_mode_six_pages(sample_files):
    """Test quick mode with a 6-page comic returns pages 1-5 (skip cover)."""
    duplicates = Duplicates(sample_files, quick=True)
    assert duplicates._get_page_indices(6) == [1, 2, 3, 4, 5]


def test_get_page_indices_quick_mode_seven_pages(sample_files):
    """Test quick mode with a 7-page comic returns pages 1-3 and 4-6."""
    duplicates = Duplicates(sample_files, quick=True)
    assert duplicates._get_page_indices(7) == [1, 2, 3, 4, 5, 6]


def test_get_page_indices_quick_mode_one_page(sample_files):
    """Test quick mode with a 1-page comic returns no pages (only cover)."""
    duplicates = Duplicates(sample_files, quick=True)
    assert duplicates._get_page_indices(1) == []


def test_get_page_indices_quick_mode_two_pages(sample_files):
    """Test quick mode with a 2-page comic returns only page 1."""
    duplicates = Duplicates(sample_files, quick=True)
    assert duplicates._get_page_indices(2) == [1]


@patch("metrontagger.comics.Comic")
def test_process_comic_pages_quick_mode(mock_comic_class, sample_files, mock_image_data):
    """Test that quick mode only processes expected pages."""
    mock_comic = Mock()
    mock_comic.path = Path("test.cbz")
    mock_comic.get_number_of_pages.return_value = 10
    mock_comic.get_page.return_value = mock_image_data
    mock_comic_class.return_value = mock_comic

    duplicates = Duplicates(sample_files, quick=True)

    with patch.object(duplicates, "_calculate_image_hash", return_value="hash123"):
        pages = list(duplicates._process_comic_pages(mock_comic))

        assert len(pages) == 6
        indices = [p["index"] for p in pages]
        assert indices == [1, 2, 3, 7, 8, 9]


def test_duplicates_init_quick_flag(sample_files):
    """Test that quick flag is stored correctly."""
    duplicates_normal = Duplicates(sample_files)
    assert duplicates_normal._quick is False

    duplicates_quick = Duplicates(sample_files, quick=True)
    assert duplicates_quick._quick is True


# Threaded scan tests
def _fake_comic(path, *, writable=True, pages=2):
    comic = Mock()
    comic.path = Path(path)
    comic.is_writable.return_value = writable
    comic.can_remove_pages.return_value = writable
    comic.get_number_of_pages.return_value = pages
    comic.get_page.return_value = b"image_data"
    return comic


def test_duplicates_init_invalid_max_workers(sample_files):
    """Test that a max_workers below 1 is rejected."""
    with pytest.raises(ValueError, match="max_workers"):
        Duplicates(sample_files, max_workers=0)


def test_duplicates_init_max_workers_capped(sample_files):
    """Test that the worker count never exceeds the number of files."""
    assert Duplicates(sample_files, max_workers=50)._max_workers == len(sample_files)
    assert Duplicates([Path("a.cbz")])._max_workers == 1


@patch("metrontagger.comics.Comic")
def test_generate_page_hashes_preserves_file_order(mock_comic_class, sample_files):
    """Test that results follow the file list order even if later comics finish first."""
    delays = {"comic1.cbz": 0.15, "comic2.cbz": 0.05, "comic3.cbz": 0.0}

    def make_comic(path):
        time.sleep(delays[Path(path).name])
        return _fake_comic(path)

    mock_comic_class.side_effect = make_comic
    duplicates = Duplicates(sample_files, max_workers=3)

    with (
        patch.object(duplicates, "_calculate_image_hash", return_value="hash123"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        rows = list(duplicates._generate_page_hashes())

    assert [Path(r["path"]).name for r in rows] == [f.name for f in sample_files]


@patch("metrontagger.comics.Comic")
def test_generate_page_hashes_skips_bad_comics(mock_comic_class):
    """Test that invalid and read-only comics are skipped without affecting the rest."""
    files = [Path("bad.cbz"), Path("readonly.cbz"), Path("good.cbz")]

    def make_comic(path):
        name = Path(path).name
        if name == "bad.cbz":
            raise ComicArchiveError
        return _fake_comic(path, writable=name != "readonly.cbz")

    mock_comic_class.side_effect = make_comic
    duplicates = Duplicates(files, max_workers=3)

    with (
        patch.object(duplicates, "_calculate_image_hash", return_value="hash123"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        rows = list(duplicates._generate_page_hashes())

    assert [Path(r["path"]).name for r in rows] == ["good.cbz"]


@pytest.mark.parametrize("name", ["issue.PDF", "issue.cbr"])
@patch("metrontagger.comics.Comic")
def test_generate_page_hashes_skips_unsupported_formats(mock_comic_class, name):
    """Test that comics whose pages can't be removed (e.g. PDFs and RARs) are skipped."""
    files = [Path(name), Path("issue.cbz")]

    def make_comic(path):
        return _fake_comic(path, writable=Path(path).name == "issue.cbz")

    mock_comic_class.side_effect = make_comic
    duplicates = Duplicates(files, max_workers=2)

    with (
        patch.object(duplicates, "_calculate_image_hash", return_value="hash123"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        rows = list(duplicates._generate_page_hashes())

    assert [Path(r["path"]).name for r in rows] == ["issue.cbz"]


@patch("metrontagger.comics.Comic")
def test_generate_page_hashes_single_worker_is_serial(mock_comic_class, sample_files):
    """Test that max_workers=1 scans without creating a thread pool."""
    mock_comic_class.side_effect = _fake_comic
    duplicates = Duplicates(sample_files, max_workers=1)

    with (
        patch("metrontagger.duplicates.ThreadPoolExecutor") as mock_executor,
        patch.object(duplicates, "_calculate_image_hash", return_value="hash123"),
        patch("metrontagger.duplicates.tqdm", side_effect=lambda x, **kwargs: x),
    ):
        rows = list(duplicates._generate_page_hashes())

    mock_executor.assert_not_called()
    assert len(rows) == len(sample_files)


# DuplicatesPresenter tests
@pytest.fixture
def printed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every message printed through the UI layer."""
    lines: list[str] = []
    monkeypatch.setattr(
        "metrontagger.ui.questionary.print", lambda msg, **_kw: lines.append(str(msg))
    )
    return lines


def _sized_dup(path: str, pages: list[int], start: int, end: int | None) -> DuplicateIssue:
    dup = DuplicateIssue(path, pages)
    dup.starting_size_bytes = start
    dup.ending_size_bytes = end
    return dup


def test_create_statistics_msg() -> None:
    msg = DuplicatesPresenter.create_statistics_msg(
        {
            "total_pages": 1234,
            "duplicate_pages": 5,
            "unique_duplicate_hashes": 2,
            "comics_processed": 3,
        }
    )

    assert "Total Pages Scanned: 1,234" in msg
    assert "Duplicate Pages Found: 5" in msg
    assert "Unique Duplicate Images: 2" in msg
    assert "Comics Processed: 3" in msg


def test_print_pre_processing_summary(printed: list[str]) -> None:
    dups = [
        _sized_dup("a.cbz", [1, 2], 2048, None),
        _sized_dup("b.cbz", [3], 1024, None),
    ]

    DuplicatesPresenter.print_pre_processing_summary(dups)

    out = "\n".join(printed)
    assert "Comics to process: 2" in out
    assert "Total duplicate pages to remove: 3" in out
    assert "Total starting size: 3.00 KB" in out


def test_print_summaries_skip_empty_list(printed: list[str]) -> None:
    DuplicatesPresenter.print_pre_processing_summary([])
    DuplicatesPresenter.print_post_processing_summary([], {})

    assert printed == []


def test_print_post_processing_summary(printed: list[str]) -> None:
    dups = [
        _sized_dup("/x/a.cbz", [1, 2], 4096, 2048),
        _sized_dup("/x/b.cbz", [3], 1024, 1024),
        _sized_dup("/x/c.cbz", [4], 1024, None),
    ]

    DuplicatesPresenter.print_post_processing_summary(
        dups, {"/x/a.cbz": True, "/x/b.cbz": True, "/x/c.cbz": False}
    )

    out = "\n".join(printed)
    assert "a.cbz - Removed 2 pages (Saved: 2.00 KB, 50.0%)" in out
    assert "b.cbz - Removed 1 page\n" in out + "\n"
    assert "Total pages removed: 3" in out
    assert "Total space saved: 2.00 KB" in out
    assert "Average space saved per comic: 1.00 KB" in out
    assert "FAILED TO PROCESS" in out
    assert "c.cbz - Failed to remove 1 page" in out


def test_print_post_processing_summary_all_failed(printed: list[str]) -> None:
    DuplicatesPresenter.print_post_processing_summary(
        [_sized_dup("a.cbz", [1], 1024, None)], {}
    )

    out = "\n".join(printed)
    assert "SUCCESSFULLY PROCESSED" not in out
    assert "a.cbz - Failed to remove 1 page" in out
