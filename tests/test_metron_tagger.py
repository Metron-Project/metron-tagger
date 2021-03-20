"""Main metron_tagger tests"""
import io
import sys
from pathlib import Path

import pytest
from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata

from metrontagger.main import (
    SETTINGS,
    MultipleMatch,
    OnlineMatchResults,
    create_metron_talker,
    delete_comics_metadata,
    list_comics_with_missing_metadata,
    post_process_matches,
    print_choices_to_user,
    retrieve_single_issue_from_id,
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


def test_retrieve_single_issue_from_id(fake_comic, mock_fetch):
    retrieve_single_issue_from_id([fake_comic], 1)

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


def test_retrieve_single_issue_from_id_multiple_files():
    with pytest.raises(SystemExit) as e:
        retrieve_single_issue_from_id(["blah_blah.cbz", "yeah_yeah.cbz"], 1)
    assert e.type == SystemExit
    assert e.value.code == 0


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
        + "moved 'Aquaman v1 #001 (of 08) (1994).cbz' to "
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


def test_print_multi_choices_to_user(capsys):
    fn = "Superman #1"
    data = [
        {"__str__": "Superman #1", "cover_date": "10/1/1939"},
        {"__str__": "Superman #1", "cover_date": "1/1/1986"},
    ]
    test_data = MultipleMatch(fn, data)
    expected_result = "1. Superman #1 (10/1/1939)\n2. Superman #1 (1/1/1986)\n"
    print_choices_to_user(test_data.matches)
    stdout, stderr = capsys.readouterr()
    assert stdout == expected_result


def test_post_process_matches(capsys, talker):
    results = OnlineMatchResults()
    results.good_matches.append("Inhumans #1.cbz")
    results.good_matches.append("Inhumans #2.cbz")
    results.no_matches.append("Outsiders #1.cbz")
    results.no_matches.append("Outsiders #2.cbz")

    expected_result = "\nSuccessful matches:\n------------------\nInhumans #1.cbz\nInhumans #2.cbz\n\n"
    expected_result += (
        "No matches:\n------------------\nOutsiders #1.cbz\nOutsiders #2.cbz\n"
    )

    post_process_matches(results, talker)
    stdout, _ = capsys.readouterr()

    assert stdout == expected_result
