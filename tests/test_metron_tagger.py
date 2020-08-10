"""Main metron_tagger tests"""
import io
import sys

import pytest
from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata

from metrontagger.main import (
    SETTINGS,
    create_metron_talker,
    get_issue_metadata,
    list_comics_with_missing_metadata,
    delete_comics_metadata
)
from metrontagger.taggerlib.metrontalker import MetronTalker


class MockFetchIssueResponse:
    @staticmethod
    def fetch_issue_data_by_issue_id():
        meta_data = GenericMetadata()
        meta_data.series = "Aquaman"
        meta_data.issue = "1"
        meta_data.year = "1993"
        meta_data.day = "15"
        meta_data.add_credit("Peter David", "Writer", primary=True)
        meta_data.add_credit("Martin Egeland", "Penciller")
        return meta_data


@pytest.fixture()
def mock_fetch(monkeypatch):
    def mock_get_issue(*args, **kwargs):
        return MockFetchIssueResponse().fetch_issue_data_by_issue_id()

    monkeypatch.setattr(MetronTalker, "fetch_issue_data_by_issue_id", mock_get_issue)


def test_get_issue_metadata(talker, fake_comic, mock_fetch):
    # expected = MockFetchIssueResponse.issue_response()
    res = get_issue_metadata(fake_comic, 1, talker)

    # Check to see the zipfile had metadata written
    comic = ComicArchive(fake_comic)
    file_md = comic.read_metadata()

    assert res is True
    assert file_md is not None
    assert file_md.series == "Aquaman"
    assert file_md.issue == "1"
    assert file_md.year == "1993"


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
    capturedOutput = io.StringIO()
    sys.stdout = capturedOutput

    list_comics_with_missing_metadata(fake_list)
    sys.stdout = sys.__stdout__

    assert expected_result == capturedOutput.getvalue()


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
    capturedOutput = io.StringIO()
    sys.stdout = capturedOutput

    delete_comics_metadata(fake_list)
    sys.stdout = sys.__stdout__

    assert expected_result == capturedOutput.getvalue()
