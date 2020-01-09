"""Main project file"""
import os
import sys
from base64 import standard_b64encode

from darkseid.comicarchive import ComicArchive, MetaDataStyle
from darkseid.genericmetadata import GenericMetadata
from darkseid.utils import get_recursive_filelist, unique_file

from .taggerlib.filerenamer import FileRenamer
from .taggerlib.filesorter import FileSorter
from .taggerlib.metrontalker import MetronTalker
from .taggerlib.options import make_parser
from .taggerlib.settings import MetronTaggerSettings
from .taggerlib.utils import create_issue_query_dict

# Load the settings
SETTINGS = MetronTaggerSettings()


# TODO: Consider making this a dict or tuple
class MultipleMatch:
    """Class to hold information on searches with multiple matches"""

    def __init__(self, filename, match_list):
        self.filename = filename
        self.matches = match_list


# TODO: Consider making this a dict or tuple
class OnlineMatchResults:
    """Class to track online match results"""

    def __init__(self):
        self.good_matches = []
        self.no_matches = []
        self.multiple_matches = []


def create_metron_talker():
    """Function that creates the metron talker"""
    auth = f"{SETTINGS.metron_user}:{SETTINGS.metron_pass}"
    base64string = standard_b64encode(auth.encode("utf-8"))
    talker = MetronTalker(base64string)

    return talker


def create_pagelist_metadata(comic_archive):
    """Function that returns the metadata for the total number of pages"""
    meta_data = GenericMetadata()
    meta_data.set_default_page_list(comic_archive.get_number_of_pages())

    return meta_data


def get_issue_metadata(filename, issue_id, talker):
    """
    Function to get an issue's metadata from Metron and the write that
    information to a tag in the comic archive
    """
    success = False

    metron_md = talker.fetch_issue_data_by_issue_id(issue_id)
    if metron_md:
        comic_archive = ComicArchive(filename)
        meta_data = create_pagelist_metadata(comic_archive)
        meta_data.overlay(metron_md)
        comic_archive.write_metadata(meta_data, MetaDataStyle.CIX)
        success = True

    return success


def select_choice_from_multiple_matches(filename, match_set):
    """
    Function to ask user to choice which issue metadata to write,
    when there are multiple choices
    """
    print(f"\n{os.path.basename(filename)} - Multiple results found")

    # sort match list by cover date
    match_set = sorted(match_set, key=lambda m: m["cover_date"])

    for (counter, match) in enumerate(match_set, start=1):
        print(f"{counter}. {match['__str__']} ({match['cover_date']})")

    while True:
        i = input("Choose a match #, or 's' to skip: ")
        if (i.isdigit() and int(i) in range(1, len(match_set) + 1)) or i == "s":
            break

    if i != "s":
        i = int(i) - 1
        issue_id = match_set[i]["id"]
    else:
        issue_id = None

    return issue_id


def process_file(filename, match_results, talker):
    """
    Main function to attempt query Metron and write a tag
    """
    comic_archive = ComicArchive(filename)

    if not comic_archive.seems_to_be_a_comic_archive():
        print(f"{os.path.basename(filename)} does not appear to be a comic archive.")
        return None, False

    if not comic_archive.is_writable():
        print(f"{os.path.basename(filename)} is not writable.")
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


def post_process_matches(match_results, talker):
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
                success = get_issue_metadata(match_set.filename, issue_id, talker)
                if not success:
                    print(
                        f"Unable to retrieve metadata for '{os.path.basename(match_set.filename)}'."
                    )


def main():
    """
    Main func
    """

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

    # Parse paths to get file list
    file_list = []
    file_list = get_recursive_filelist(opts.path)

    if not file_list:
        print("No files to process. Exiting.")
        sys.exit(0)

    if opts.missing:
        print("\nShowing files without metadata:\n-------------------------------")
        for comic in file_list:
            comic_archive = ComicArchive(comic)
            if comic_archive.has_metadata(MetaDataStyle.CIX):
                continue
            print(f"no metadata in '{os.path.basename(comic)}'")

    if opts.delete:
        print("\nRemoving metadata:\n-----------------")
        for comic in file_list:
            comic_archive = ComicArchive(comic)
            if comic_archive.has_metadata(MetaDataStyle.CIX):
                comic_archive.remove_metadata(MetaDataStyle.CIX)
                print(f"removed metadata from '{os.path.basename(comic)}'.")
            else:
                print(f"no metadata in '{os.path.basename(comic)}'.")

    if opts.id:
        if len(file_list) > 1:
            print("More than one file was passed for Id processing. Exiting...")
            sys.exit(0)

        filename = file_list[0]
        talker = create_metron_talker()
        success = get_issue_metadata(filename, opts.id, talker)
        if success:
            print(f"match found for '{os.path.basename(filename)}'.")

    if opts.online:
        print(
            "\nStarting online search and tagging:\n----------------------------------"
        )

        # Initialize class to handle results for files with multiple matches
        match_results = OnlineMatchResults()
        talker = create_metron_talker()

        # Let's look online to see if we can find any matches on Metron.
        for filename in file_list:
            if opts.ignore_existing:
                comic_archive = ComicArchive(filename)
                if comic_archive.check_for_cix():
                    print(f"{os.path.basename(filename)} has metadata. Skipping...")
                    continue

            issue_id, multiple_match = process_file(filename, match_results, talker)
            if issue_id:
                success = get_issue_metadata(filename, issue_id, talker)
                if success:
                    print(f"match found for '{os.path.basename(filename)}'.")
                else:
                    print(
                        f"there was a problem writing metadate for '{os.path.basename(filename)}'."
                    )
            else:
                if not multiple_match:
                    print(f"no match for '{os.path.basename(filename)}'.")
                    continue

        # Print match results & handle files with multiple matches
        post_process_matches(match_results, talker)

    if opts.rename:
        print("\nStarting comic archive renaming:\n-------------------------------")

        # Lists to track filename changes
        new_file_names = []
        original_files_changed = []
        for comic in file_list:
            comic_archive = ComicArchive(comic)
            if not comic_archive.check_for_cix():
                print(f"skipping '{os.path.basename(comic)}'. No metadata available.")
                continue

            meta_data = comic_archive.read_metadata(MetaDataStyle.CIX)
            renamer = FileRenamer(meta_data)
            new_name = renamer.determine_name(comic)

            if new_name == os.path.basename(comic):
                print("Filename is already good!", file=sys.stderr)
                continue

            folder = os.path.dirname(os.path.abspath(comic))
            new_abs_path = unique_file(os.path.join(folder, new_name))
            os.rename(comic, new_abs_path)
            # track what files are being renamed
            new_file_names.append(new_abs_path)
            original_files_changed.append(comic)

            print(f"renamed '{os.path.basename(comic)}' -> '{new_name}'")

        # Update file_list for renamed files
        for original_file in original_files_changed:
            file_list.remove(original_file)

        for new_file in new_file_names:
            file_list.append(new_file)

    if opts.sort:
        if not SETTINGS.sort_dir:
            print("Unable to sort files. No destination directory was provided.")
            return

        print(
            "\nStarting sorting of comic archives:\n----------------------------------"
        )
        file_sorter = FileSorter(SETTINGS.sort_dir)
        for comic in file_list:
            result = file_sorter.sort_comics(comic)
            if not result:
                print(f"unable to move {os.path.basename(comic)}.")


if __name__ == "__main__":
    sys.exit(main())
