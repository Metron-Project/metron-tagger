"""Main metron_tagger tests"""

# import io
# import sys
from pathlib import Path

from metrontagger.settings import MetronTaggerSettings
from metrontagger.talker import Talker

# from darkseid.metadata import Metadata
# from mokkari.issue import IssuesList


def test_create_metron_talker(tmp_path: Path) -> None:
    s = MetronTaggerSettings(tmp_path)
    s.metron_user = "test"
    s.metron_pass = "test_password"  # noqa: S105
    talker = Talker(s.metron_user, s.metron_pass)
    assert isinstance(talker, Talker)


# def test_list_comics_with_missing_metadata(fake_comic: ZipFile) -> None:
#     expected_result = (
#         "\nShowing files without metadata:"
#         + "\n-------------------------------"
#         + "\nno metadata in 'Aquaman v1 #001 (of 08) (1994).cbz'"
#         + "\n"
#     )
#     # Make sure fake comic archive doesn't have any metadata
#     if Comic(fake_comic).has_metadata():
#         Comic(fake_comic).remove_metadata()

#     fake_list = [fake_comic]

#     # Capture the output so we can verify the print output
#     captured_output = io.StringIO()
#     sys.stdout = captured_output

#     list_comics_with_missing_metadata(fake_list)
#     sys.stdout = sys.__stdout__

#     assert expected_result == captured_output.getvalue()


# def test_delete_comics_with_metadata(
#     fake_comic: ZipFile, fake_metadata: Metadata
# ) -> None:
#     expected_result = (
#         "\nRemoving metadata:\n-----------------"
#         + "\nremoved metadata from 'Aquaman v1 #001 (of 08) (1994).cbz'"
#         + "\n"
#     )

#     # If comic doesn't already have metadata let's add it
#     if not Comic(fake_comic).has_metadata():
#         Comic(fake_comic).write_metadata(fake_metadata)

#     fake_list = [fake_comic]

#     # Capture the output so we can verify the print output
#     captured_output = io.StringIO()
#     sys.stdout = captured_output

#     delete_comics_metadata(fake_list)
#     sys.stdout = sys.__stdout__

#     assert expected_result == captured_output.getvalue()


# def test_delete_comics_without_metadata(fake_comic: ZipFile) -> None:
#     expected_result = (
#         "\nRemoving metadata:\n-----------------"
#         + "\nno metadata in 'Aquaman v1 #001 (of 08) (1994).cbz'"
#         + "\n"
#     )

#     # If comic has metadata let's remove it
#     if Comic(fake_comic).has_metadata():
#         Comic(fake_comic).remove_metadata()

#     fake_list = [fake_comic]

#     # Capture the output so we can verify the print output
#     captured_output = io.StringIO()
#     sys.stdout = captured_output

#     delete_comics_metadata(fake_list)
#     sys.stdout = sys.__stdout__

#     assert expected_result == captured_output.getvalue()


# def test_sort_comics_without_sort_dir(fake_comic: ZipFile, tmp_path: Path) -> None:
#     expected_result = "\nUnable to sort files. No destination directory was provided.\n"

#     # Create fake settings.
#     s = MetronTaggerSettings(tmp_path)
#     s.sort_dir = ""

#     fake_list = [fake_comic]

#     # Capture the output so we can verify the print output
#     captured_output = io.StringIO()
#     sys.stdout = captured_output

#     sort_list_of_comics(s.sort_dir, fake_list)
#     sys.stdout = sys.__stdout__

#     assert expected_result == captured_output.getvalue()


# def test_sort_comics_with_dir(
#     fake_comic: ZipFile, fake_metadata: Metadata, tmp_path: Path
# ) -> None:
#     s = MetronTaggerSettings(tmp_path)
#     s.sort_dir = tmp_path

#     res_path = (
#         Path(f"{s.sort_dir}")
#         / f"{fake_metadata.publisher}"
#         / f"{fake_metadata.series}"
#         / f"v{fake_metadata.volume}"
#     )

#     expected_result = (
#         "\nStarting sorting of comic archives:\n----------------------------------\n"
#         + "moved 'Aquaman v1 #001 (of 08) (1994).cbz' to "
#         + "'"
#         + str(res_path)
#         + "'\n"
#     )

#     comic = Comic(fake_comic)

#     if not comic.has_metadata():
#         comic.write_metadata(fake_metadata)

#     fake_list = [fake_comic]

#     # Capture the output so we can verify the print output
#     captured_output = io.StringIO()
#     sys.stdout = captured_output

#     sort_list_of_comics(s.sort_dir, fake_list)
#     sys.stdout = sys.__stdout__

#     # Path for moved file
#     moved_comic = (
#         Path(f"{s.sort_dir}")
#         / f"{fake_metadata.publisher}"
#         / f"{fake_metadata.series}"
#         / f"v{fake_metadata.volume}"
#         / fake_comic.name
#     )

#     assert moved_comic.parent.is_dir()
#     assert moved_comic.is_file()
#     assert expected_result == captured_output.getvalue()


# @pytest.fixture()
# def multi_choice_fixture() -> IssuesList:
#     i = {
#         "count": 2,
#         "next": None,
#         "previous": None,
#         "results": [
#             {"issue": "Superman #1", "cover_date": "1939-10-01"},
#             {"issue": "Superman #1", "cover_date": "1986-01-01"},
#         ],
#     }
#     return IssuesList(i)


# def test_print_multi_choices_to_user(
#     talker: Talker, multi_choice_fixture: IssuesList, capsys
# ) -> None:
#     fn = Path("/tmp/Superman #1")
#     test_data = MultipleMatch(fn, multi_choice_fixture)
#     expected_result = "1. Superman #1 (1939-10-01)\n2. Superman #1 (1986-01-01)\n"
#     talker._print_choices_to_user(test_data.matches)
#     stdout, _ = capsys.readouterr()
#     assert stdout == expected_result


# def test_post_process_matches(capsys, talker: Talker) -> None:
#     talker.match_results.add_good_match("Inhumans #1.cbz")
#     talker.match_results.good_matches.append("Inhumans #2.cbz")
#     talker.match_results.no_matches.append("Outsiders #1.cbz")
#     talker.match_results.no_matches.append("Outsiders #2.cbz")

#     expected_result = (
#         "\nSuccessful matches:\n------------------\nInhumans #1.cbz\nInhumans #2.cbz\n\n"
#         + "No matches:\n------------------\nOutsiders #1.cbz\nOutsiders #2.cbz\n"
#     )

#     talker._post_process_matches()
#     stdout, _ = capsys.readouterr()

#     assert stdout == expected_result
