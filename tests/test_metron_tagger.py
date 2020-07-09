"""Main metron_tagger tests"""

import zipfile

import pytest
from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata

from metrontagger.main import SETTINGS, create_metron_talker, get_issue_metadata
from metrontagger.taggerlib.metrontalker import MetronTalker

CONTENT = "blah blah blah"


@pytest.fixture()
def fake_comic(tmp_path):
    img_1 = tmp_path / "image-1.jpg"
    img_1.write_text(CONTENT)
    img_2 = tmp_path / "image-2.jpg"
    img_2.write_text(CONTENT)
    img_3 = tmp_path / "image-3.jpg"
    img_3.write_text(CONTENT)

    z_file = tmp_path / "Aquaman v1 #001 (of 08) (1994).cbz"
    zf = zipfile.ZipFile(z_file, "w")
    try:
        zf.write(img_1)
        zf.write(img_2)
        zf.write(img_3)
    finally:
        zf.close()

    return z_file


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
