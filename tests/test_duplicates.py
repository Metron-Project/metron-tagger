from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from PIL import UnidentifiedImageError

from metrontagger.duplicates import DuplicateIssue, Duplicates


@pytest.fixture()
def mock_comic():
    with patch("metrontagger.duplicates.Comic") as mockcomic:
        yield mockcomic


@pytest.fixture()
def sample_file_list():
    return [Path(f"comic_{i}.cbz") for i in range(3)]


@pytest.fixture()
def duplicates_instance(sample_file_list):
    return Duplicates(sample_file_list)


@pytest.mark.parametrize(
    ("file_lst", "expected_length"),
    [([Path("comic_1.cbz"), Path("comic_2.cbz")], 2), ([Path("comic_1.cbz")], 1), ([], 0)],
    ids=["two_files", "one_file", "no_files"],
)
def test_init(file_lst, expected_length):
    # Act
    duplicates = Duplicates(file_lst)

    # Assert
    assert len(duplicates._file_lst) == expected_length
    assert duplicates._data_frame is None


@pytest.mark.parametrize(
    ("comic_pages", "expected_hashes"),
    [
        # ([b"page1", b"page2"], 2),
        # ([b"page1"], 1),
        ([], 0)
    ],
    ids=["no_pages"],
)
def test_image_hashes(mock_comic, duplicates_instance, comic_pages, expected_hashes):
    # Arrange
    mock_comic.return_value.get_number_of_pages.return_value = len(comic_pages)
    mock_comic.return_value.get_page.side_effect = comic_pages

    # Act
    hashes = duplicates_instance._image_hashes()

    # Assert
    assert len(hashes) == expected_hashes


@pytest.mark.parametrize(
    ("comic_hashes", "expected_duplicates"),
    [
        (
            [
                {"path": "comic_1", "index": 0, "hash": "hash1"},
                {"path": "comic_1", "index": 1, "hash": "hash1"},
            ],
            2,
        ),
        (
            [
                {"path": "comic_1", "index": 0, "hash": "hash1"},
                {"path": "comic_1", "index": 1, "hash": "hash2"},
            ],
            0,
        ),
    ],
    ids=["two_duplicates", "no_duplicates"],
)
def test_get_page_hashes(duplicates_instance, comic_hashes, expected_duplicates):
    # Arrange
    with patch.object(duplicates_instance, "_image_hashes", return_value=comic_hashes):
        # Act
        df = duplicates_instance._get_page_hashes()

        # Assert
        assert len(df) == expected_duplicates


@pytest.mark.parametrize(
    ("page_hashes", "expected", "description"),
    [
        ({"hash": ["abc", "def", "ghi"]}, ["abc", "def", "ghi"], "unique hashes"),
        ({"hash": ["abc", "abc", "def"]}, ["abc", "def"], "duplicate hashes"),
        ({"hash": []}, [], "empty hash list"),
        ({"hash": ["abc"]}, ["abc"], "single hash"),
        ({"hash": ["abc", "ABC"]}, ["abc", "ABC"], "case-sensitive hashes"),
    ],
    ids=[
        "unique_hashes",
        "duplicate_hashes",
        "empty_hash_list",
        "single_hash",
        "case_sensitive_hashes",
    ],
)
def test_get_distinct_hashes(page_hashes, expected, description):
    # Arrange
    duplicates = Duplicates([Path("tmp")])
    duplicates._get_page_hashes = MagicMock(return_value=page_hashes)

    # Act
    result = duplicates.get_distinct_hashes()

    # Assert
    assert set(result) == set(expected), f"Failed on {description}"


@pytest.mark.parametrize(
    ("page_hashes", "expected_exception", "description"),
    [
        (None, TypeError, "None as page_hashes"),
        ({"hash": None}, TypeError, "None as hash list"),
    ],
    ids=["none_page_hashes", "none_hash_list"],
)
def test_get_distinct_hashes_errors(page_hashes, expected_exception, description):  # noqa: ARG001
    # Arrange
    duplicates = Duplicates([Path("tmp")])
    duplicates._get_page_hashes = MagicMock(return_value=page_hashes)

    # Act & Assert
    with pytest.raises(expected_exception):
        duplicates.get_distinct_hashes()


@pytest.mark.parametrize(
    ("comic_hashes", "img_hash", "expected_path", "expected_index"),
    [
        (
            [
                {"path": "comic_1", "index": 0, "hash": "hash1"},
                {"path": "comic_1", "index": 1, "hash": "hash1"},
            ],
            "hash1",
            "comic_1",
            0,
        ),
        (
            [
                {"path": "comic_1", "index": 0, "hash": "hash1"},
                {"path": "comic_1", "index": 1, "hash": "hash2"},
            ],
            "hash2",
            "comic_1",
            1,
        ),
    ],
    ids=["first_duplicate", "second_duplicate"],
)
def test_get_comic_info_for_distinct_hash(
    duplicates_instance, comic_hashes, img_hash, expected_path, expected_index
):
    # Arrange
    duplicates_instance._data_frame = pd.DataFrame(comic_hashes)

    # Act
    comic_info = duplicates_instance.get_comic_info_for_distinct_hash(img_hash)

    # Assert
    assert comic_info.path_ == expected_path
    assert comic_info.pages_index == expected_index


@pytest.mark.parametrize(
    ("comic_hashes", "img_hash", "expected_comics"),
    [
        (
            [
                {"path": "comic_1", "index": 0, "hash": "hash1"},
                {"path": "comic_1", "index": 1, "hash": "hash1"},
            ],
            "hash1",
            [DuplicateIssue("comic_1", [0]), DuplicateIssue("comic_1", [1])],
        ),
        (
            [
                {"path": "comic_1", "index": 0, "hash": "hash1"},
                {"path": "comic_1", "index": 1, "hash": "hash2"},
            ],
            "hash2",
            [DuplicateIssue("comic_1", [1])],
        ),
    ],
    ids=["multiple_duplicates", "single_duplicate"],
)
def test_get_comic_list_from_hash(
    duplicates_instance, comic_hashes, img_hash, expected_comics
):
    # Arrange
    duplicates_instance._data_frame = pd.DataFrame(comic_hashes)

    # Act
    comic_list = duplicates_instance.get_comic_list_from_hash(img_hash)

    # Assert
    assert comic_list == expected_comics


@pytest.mark.parametrize(
    ("dups_lst", "remove_success"),
    [([DuplicateIssue("comic_1", [0])], True), ([DuplicateIssue("comic_1", [0])], False)],
    ids=["remove_success", "remove_failure"],
)
def test_delete_comic_pages(mock_comic, dups_lst, remove_success):
    # Arrange
    mock_comic.return_value.remove_pages.return_value = remove_success

    # Act
    Duplicates.delete_comic_pages(dups_lst)

    mock_comic.return_value.remove_pages.assert_called_once()


@pytest.mark.parametrize(
    ("img_data", "should_raise"),
    [
        (b"valid_image_data", False),
        # (b"invalid_image_data", True)
    ],
    ids=["valid_image"],
)
def test_show_image(mock_comic, img_data, should_raise):
    # Arrange
    mock_comic.return_value.get_page.return_value = img_data
    duplicate_issue = DuplicateIssue("comic_1", [0])

    # Act
    if should_raise:
        with pytest.raises(UnidentifiedImageError):
            Duplicates.show_image(duplicate_issue)
    else:
        Duplicates.show_image(duplicate_issue)

    # Assert
    if not should_raise:
        mock_comic.return_value.get_page.assert_called_once()
