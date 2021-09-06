"""Main metron_tagger tests"""
import io
import sys
from pathlib import Path

import pytest
from darkseid.comicarchive import ComicArchive
from mokkari.issues_list import IssuesList

from metrontagger.main import (
    SETTINGS,
    delete_comics_metadata,
    list_comics_with_missing_metadata,
    sort_list_of_comics,
)
from metrontagger.talker import MultipleMatch, Talker


def test_create_metron_talker():
    SETTINGS.metron_user = "test"
    SETTINGS.metron_pass = "test_password"
    talker = Talker(SETTINGS.metron_user, SETTINGS.metron_pass)
    assert isinstance(talker, Talker)


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


@pytest.fixture()
def multi_choice_fixture():
    i = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"issue_name": "Superman #1", "cover_date": "1939-10-01"},
            {"issue_name": "Superman #1", "cover_date": "1986-01-01"},
        ],
    }
    return IssuesList(i)


def test_print_multi_choices_to_user(talker, multi_choice_fixture, capsys):
    fn = Path("/tmp/Superman #1")
    test_data = MultipleMatch(fn, multi_choice_fixture)
    expected_result = "1. Superman #1 (1939-10-01)\n2. Superman #1 (1986-01-01)\n"
    talker._print_choices_to_user(test_data.matches)
    stdout, _ = capsys.readouterr()
    assert stdout == expected_result


def test_post_process_matches(capsys, talker):
    talker.match_results.add_good_match("Inhumans #1.cbz")
    talker.match_results.good_matches.append("Inhumans #2.cbz")
    talker.match_results.no_matches.append("Outsiders #1.cbz")
    talker.match_results.no_matches.append("Outsiders #2.cbz")

    expected_result = (
        "\nSuccessful matches:\n------------------\nInhumans #1.cbz\nInhumans #2.cbz\n\n"
    )
    expected_result += "No matches:\n------------------\nOutsiders #1.cbz\nOutsiders #2.cbz\n"

    talker._post_process_matches()
    stdout, _ = capsys.readouterr()

    assert stdout == expected_result
