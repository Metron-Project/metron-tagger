"""Main project file"""
from argparse import Namespace
from base64 import standard_b64encode
from pathlib import Path
from sys import exit
from typing import List, Optional, Tuple

from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata
from darkseid.utils import get_recursive_filelist

from .taggerlib.filerenamer import FileRenamer
from .taggerlib.filesorter import FileSorter
from .taggerlib.metrontalker import MetronTalker
from .taggerlib.options import make_parser
from .taggerlib.settings import MetronTaggerSettings
from .taggerlib.utils import create_issue_query_dict

# Load the settings
SETTINGS = MetronTaggerSettings()


class MultipleMatch:
    """Class to hold information on searches with multiple matches"""

    def __init__(self, filename, match_list) -> None:
        self.filename = filename
        self.matches = match_list


class OnlineMatchResults:
    """Class to track online match results"""

    def __init__(self) -> None:
        self.good_matches: List[str] = []
        self.no_matches: List[str] = []
        self.multiple_matches: List[str] = []


def create_metron_talker() -> MetronTalker:
    """Function that creates the metron talker"""
    auth = f"{SETTINGS.metron_user}:{SETTINGS.metron_pass}"
    base64string = standard_b64encode(auth.encode("utf-8"))
    return MetronTalker(base64string)


def create_pagelist_metadata(comic_archive: ComicArchive) -> GenericMetadata:
    """Function that returns the metadata for the total number of pages"""
    meta_data = GenericMetadata()
    meta_data.set_default_page_list(comic_archive.get_number_of_pages())

    return meta_data


def write_issue_metadata(filename: Path, issue_id: int, talker: MetronTalker) -> None:
    """
    Function to get an issue's metadata from Metron and the write that
    information to a tag in the comic archive
    """
    success = False

    metron_md = talker.fetch_issue_data_by_issue_id(issue_id)
    if metron_md:
        comic_archive = ComicArchive(filename)
        meta_data = create_pagelist_metadata(comic_archive)
        metron_md.overlay(meta_data)
        success = comic_archive.write_metadata(metron_md)

    if success:
        print(f"match found for '{filename.name}'")
    else:
        print(f"there was a problem writing metadate for '{filename.name}'")


def print_choices_to_user(match_set) -> None:
    for (counter, match) in enumerate(match_set, start=1):
        print(f"{counter}. {match['__str__']} ({match['cover_date']})")


def select_choice_from_multiple_matches(filename: Path, match_set) -> Optional[int]:
    """
    Function to ask user to choice which issue metadata to write,
    when there are multiple choices
    """
    print(f"\n{filename.name} - Multiple results found:")

    # sort match list by cover date
    match_set = sorted(match_set, key=lambda m: m["cover_date"])
    print_choices_to_user(match_set)

    while True:
        i = input("Choose a match #, or 's' to skip: ")
        if (i.isdigit() and int(i) in range(1, len(match_set) + 1)) or i == "s":
            break

    if i != "s":
        i = int(i) - 1
        return match_set[i]["id"]
    else:
        return None


def workable_comic(comic: ComicArchive) -> bool:
    return comic.is_writable() and comic.seems_to_be_a_comic_archive()


def process_file(
    filename: Path, match_results, talker: MetronTalker
) -> Tuple[Optional[int], Optional[bool]]:
    """
    Main function to attempt query Metron and write a tag
    """
    comic_archive = ComicArchive(filename)

    if not workable_comic(comic_archive):
        print(f"{filename.name} may not be a comic or writable")
        return None, False

    query_dict = create_issue_query_dict(filename)
    res = talker.search_for_issue(query_dict)
    res_count = res["count"]

    issue_id = None
    multiple_match = False
    if not res_count > 0:
        issue_id = None
        match_results.no_matches.append(filename)
        multiple_match = False
    elif res_count > 1:
        issue_id = None
        match_results.multiple_matches.append(MultipleMatch(filename, res["results"]))
        multiple_match = True
    elif res_count == 1:
        issue_id = res["results"][0]["id"]
        match_results.good_matches.append(filename)
        multiple_match = False

    return issue_id, multiple_match


def post_process_matches(match_results, talker: MetronTalker) -> None:
    """
    Function to print match results and if there are
    multiple matches, prompt the user
    """
    # Print file matching results.
    if match_results.good_matches:
        print("\nSuccessful matches:\n------------------")
        for comic in match_results.good_matches:
            print(comic)

    if match_results.no_matches:
        print("\nNo matches:\n------------------")
        for comic in match_results.no_matches:
            print(comic)

    # Handle files with multiple matches.
    if match_results.multiple_matches:
        for match_set in match_results.multiple_matches:
            issue_id = select_choice_from_multiple_matches(
                match_set.filename, match_set.matches
            )
            if issue_id:
                write_issue_metadata(match_set.filename, issue_id, talker)


def list_comics_with_missing_metadata(file_list: List[Path]) -> None:
    print("\nShowing files without metadata:\n-------------------------------")
    for comic in file_list:
        comic_archive = ComicArchive(comic)
        if comic_archive.has_metadata():
            continue
        print(f"no metadata in '{comic.name}'")


def delete_comics_metadata(file_list: List[Path]) -> None:
    print("\nRemoving metadata:\n-----------------")
    for comic in file_list:
        comic_archive = ComicArchive(comic)
        if comic_archive.has_metadata():
            comic_archive.remove_metadata()
            print(f"removed metadata from '{comic.name}'")
        else:
            print(f"no metadata in '{comic.name}'")


def sort_list_of_comics(file_list: List[Path]) -> None:
    if not SETTINGS.sort_dir:
        print("\nUnable to sort files. No destination directory was provided.")
        return

    print("\nStarting sorting of comic archives:\n----------------------------------")
    file_sorter = FileSorter(SETTINGS.sort_dir)
    for comic in file_list:
        result = file_sorter.sort_comics(comic)
        if not result:
            print(f"unable to move {comic.name}.")


def retrieve_single_issue_from_id(file_list: List[Path], id: int) -> None:
    if len(file_list) > 1:
        print("More than one file was passed for Id processing. Exiting...")
        exit(0)

    filename = file_list[0]
    talker = create_metron_talker()
    write_issue_metadata(filename, id, talker)


def get_options() -> Namespace:
    parser = make_parser()
    opts = parser.parse_args()

    if opts.user:
        SETTINGS.metron_user = opts.user

    if opts.password:
        SETTINGS.metron_pass = opts.password

    if opts.sort_dir:
        SETTINGS.sort_dir = opts.sort_dir

    if opts.set_metron_user or opts.set_sort_dir:
        SETTINGS.save()

    return opts


def identify_comics(file_list: List[Path], ignore: bool) -> None:
    print("\nStarting online search and tagging:\n----------------------------------")

    # Initialize class to handle results for files with multiple matches
    match_results = OnlineMatchResults()
    talker = create_metron_talker()

    # Let's look online to see if we can find any matches on Metron.
    for filename in file_list:
        if ignore:
            comic_archive = ComicArchive(filename)
            if comic_archive.has_metadata():
                print(f"{filename.name} has metadata. Skipping...")
                continue

        issue_id, multiple_match = process_file(filename, match_results, talker)
        if issue_id:
            write_issue_metadata(filename, issue_id, talker)
        else:
            if not multiple_match:
                print(f"no match for '{filename.name}'")

    # Print match results & handle files with multiple matches
    post_process_matches(match_results, talker)


def rename_comics(file_list: List[Path]) -> List[Path]:
    print("\nStarting comic archive renaming:\n-------------------------------")

    # Lists to track filename changes
    new_file_names: List[Path] = []
    original_files_changed: List[Path] = []
    for comic in file_list:
        comic_archive = ComicArchive(comic)
        if not comic_archive.has_metadata():
            print(f"skipping '{comic.name}'. no metadata available.")
            continue

        meta_data = comic_archive.read_metadata()
        renamer = FileRenamer(meta_data)
        unique_name = renamer.rename_file(comic)
        if unique_name is None:
            continue

        # track what files are being renamed
        new_file_names.append(unique_name)
        original_files_changed.append(comic)

        print(f"renamed '{comic.name}' -> '{unique_name.name}'")

    # Update file_list for renamed files
    for original_file in original_files_changed:
        file_list.remove(original_file)

    for new_file in new_file_names:
        file_list.append(new_file)

    return file_list


def main() -> None:
    """
    Main func
    """
    opts = get_options()

    # Parse paths to get file list
    file_list = []
    file_list = get_recursive_filelist(opts.path)

    if not file_list:
        print("No files to process. Exiting.")
        exit(0)

    if opts.missing:
        list_comics_with_missing_metadata(file_list)

    if opts.delete:
        delete_comics_metadata(file_list)

    if opts.id:
        retrieve_single_issue_from_id(file_list, opts.id)

    if opts.online:
        identify_comics(file_list, opts.ignore_existing)

    if opts.rename:
        file_list = rename_comics(file_list)

    if opts.sort:
        sort_list_of_comics(file_list)


if __name__ == "__main__":
    exit(main())
