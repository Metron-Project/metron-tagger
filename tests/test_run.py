from pathlib import Path
from unittest.mock import Mock

import pytest
from darkseid.comic import Comic
from darkseid.metadata import Metadata

from metrontagger.duplicates import DuplicateIssue
from metrontagger.run import Runner


@pytest.mark.parametrize(
    ("has_metadata", "write_success", "expected_log_message"),
    [
        (
            True,
            True,
            None,
        ),
        (
            False,
            False,  # Value doesn't matter when has_metadata is False
            None,
        ),
        # TODO: Need to mock the comic name, so the return message is correct.
        # (
        #     True,
        #     False,
        #     "Could not write metadata to test_comic.cbz",
        # ),
    ],
    ids=[
        "happy_path_metadata_exists_write_success",
        "edge_case_no_metadata",
        # "error_case_write_fails",
    ],
)
def test__update_ci_xml(  # NOQA: PLR0913
    has_metadata: bool,
    write_success: bool,
    expected_log_message: str | None,
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    # Arrange
    comic_path = str(tmp_path / "test_comic.cbz")
    file_list = [DuplicateIssue(comic_path, [1])]

    mock_comic = Mock(spec=Comic)
    mock_comic.path = comic_path  # Set path for accurate logging
    mock_comic.has_metadata.return_value = has_metadata
    mock_comic.write_metadata.return_value = write_success
    if has_metadata:
        mock_comic.read_metadata.return_value = Metadata()
        mock_comic.get_number_of_pages.return_value = 10
    monkeypatch.setattr("metrontagger.run.Comic", lambda _: mock_comic)

    # Act
    with caplog.at_level("ERROR"):  # Capture log messages at ERROR level
        Runner._update_ci_xml(file_list)

    # Assert
    if expected_log_message:
        assert expected_log_message in caplog.text
    else:
        assert "Could not write metadata" not in caplog.text  # Ensure no unexpected error logs
