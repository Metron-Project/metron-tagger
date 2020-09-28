"""Main metron_tagger tests"""
import io
import sys
from pathlib import Path

import pytest
from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata

from metrontagger.main import (
    SETTINGS,
    create_metron_talker,
    delete_comics_metadata,
    write_issue_metadata,
    list_comics_with_missing_metadata,
    sort_list_of_comics,
)
from metrontagger.taggerlib.metrontalker import MetronTalker

MARTY = "Martin Egeland"


class MockFetchIssueResponse:
    @staticmethod
    def fetch_issue_data_by_issue_id():
        meta_data = GenericMetadata()
        meta_data.series = "Aquaman"
        meta_data.issue = "1"
        meta_data.year = "1993"
        meta_data.day = "15"
        meta_data.add_credit("Peter David", "Writer")
        meta_data.add_credit(MARTY, "Penciller")
        meta_data.add_credit(MARTY, "Cover")
        return meta_data


@pytest.fixture()
def mock_fetch(monkeypatch):
    def mock_get_issue(*args, **kwargs):
        return MockFetchIssueResponse().fetch_issue_data_by_issue_id()

    monkeypatch.setattr(MetronTalker, "fetch_issue_data_by_issue_id", mock_get_issue)


def test_get_issue_metadata(talker, fake_comic, mock_fetch):
    write_issue_metadata(fake_comic, 1, talker)

    # Check to see the zipfile had metadata written
    comic = ComicArchive(fake_comic)
    file_md = comic.read_metadata()

    credits_result = [
        {"person": "Peter David", "role": "Writer"},
        {"person": MARTY, "role": "Penciller"},
        {"person": MARTY, "role": "Cover"},
    ]

    assert file_md is not None
    assert file_md.series == "Aquaman"
    assert file_md.issue == "1"
    assert file_md.year == "1993"
    assert file_md.credits == credits_result


def test_create_metron_talker():
    SETTINGS.metron_user = "test"
    SETTINGS.metron_pass = "test_password"
    talker = create_metron_talker()
    assert isinstance(talker, MetronTalker)


def test_list_comics_with_missing_metadata(fake_comic):
    expected_result = (
        "\nShowing files without metadata:"
        + "\n-------------------------------"
        + "\nno metadata in 'Aquaman v1 #001 (of 08) (1994).cbz'"
        + "\n"
    )
    # Make sure fake comic archive doesn't have any metadata
    if ComicArchive(fake_comic).has_metadata():
        ComicArchive(fake_comic).remove_metadata()

    fake_list = [fake_comic]

    # Capture the output so we can verify the print output
    captured_output = io.StringIO()
    sys.stdout = captured_output

    list_comics_with_missing_metadata(fake_list)
    sys.stdout = sys.__stdout__

    assert expected_result == captured_output.getvalue()


def test_delete_comics_with_metadata(fake_comic, fake_metadata):
    expected_result = (
        "\nRemoving metadata:\n-----------------"
        + "\nremoved metadata from 'Aquaman v1 #001 (of 08) (1994).cbz'"
        + "\n"
    )

    # If comic doesn't already have metadata let's add it
    if not ComicArchive(fake_comic).has_metadata():
        ComicArchive(fake_comic).write_metadata(fake_metadata)

    fake_list = [fake_comic]

    # Capture the output so we can verify the print output
    captured_output = io.StringIO()
    sys.stdout = captured_output

    delete_comics_metadata(fake_list)
    sys.stdout = sys.__stdout__

    assert expected_result == captured_output.getvalue()


def test_delete_comics_without_metadata(fake_comic, fake_metadata):
    expected_result = (
        "\nRemoving metadata:\n-----------------"
        + "\nno metadata in 'Aquaman v1 #001 (of 08) (1994).cbz'"
        + "\n"
    )

    # If comic has metadata let's remove it
    if ComicArchive(fake_comic).has_metadata():
        ComicArchive(fake_comic).remove_metadata()

    fake_list = [fake_comic]

    # Capture the output so we can verify the print output
    captured_output = io.StringIO()
    sys.stdout = captured_output

    delete_comics_metadata(fake_list)
    sys.stdout = sys.__stdout__

    assert expected_result == captured_output.getvalue()


def test_sort_comics_without_sort_dir(fake_comic, tmpdir):
    expected_result = "\nUnable to sort files. No destination directory was provided.\n"

    # Create fake settings.
    SETTINGS.sort_dir = ""

    fake_list = [fake_comic]

    # Capture the output so we can verify the print output
    captured_output = io.StringIO()
    sys.stdout = captured_output

    sort_list_of_comics(fake_list)
    sys.stdout = sys.__stdout__

    assert expected_result == captured_output.getvalue()


def test_sort_comics_with_dir(fake_comic, fake_metadata, tmpdir):
    SETTINGS.sort_dir = tmpdir

    expected_result = (
        "\nStarting sorting of comic archives:\n----------------------------------\n"
        + f"moved 'Aquaman v1 #001 (of 08) (1994).cbz' to "
        + f"'{SETTINGS.sort_dir}/{fake_metadata.publisher}/{fake_metadata.series}/v{fake_metadata.volume}'\n"
    )

    comic = ComicArchive(fake_comic)

    if not comic.has_metadata():
        comic.write_metadata(fake_metadata)

    fake_list = [fake_comic]

    # Capture the output so we can verify the print output
    captured_output = io.StringIO()
    sys.stdout = captured_output

    sort_list_of_comics(fake_list)
    sys.stdout = sys.__stdout__

    # Path for moved file
    moved_comic = (
        Path(f"{SETTINGS.sort_dir}")
        / f"{fake_metadata.publisher}"
        / f"{fake_metadata.series}"
        / f"v{fake_metadata.volume}"
        / fake_comic.name
    )

    assert moved_comic.parent.is_dir()
    assert moved_comic.is_file()
    assert expected_result == captured_output.getvalue()
