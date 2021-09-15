"""Main project file"""
from argparse import Namespace
from pathlib import Path
from sys import exit
from typing import List

from darkseid.comicarchive import ComicArchive
from darkseid.utils import get_recursive_filelist

from .filerenamer import FileRenamer
from .filesorter import FileSorter
from .options import make_parser
from .settings import MetronTaggerSettings
from .talker import Talker

# Load the settings
SETTINGS = MetronTaggerSettings()


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
        renamer.set_template(SETTINGS.rename_template)
        renamer.set_issue_zero_padding(SETTINGS.rename_issue_number_padding)
        renamer.set_smart_cleanup(SETTINGS.rename_use_smart_string_cleanup)

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
        t = Talker(SETTINGS.metron_user, SETTINGS.metron_pass)
        if len(file_list) == 1:
            t.retrieve_single_issue(file_list[0], opts.id)
        else:
            print("More than one file was passed for Id processing. Exiting...")
            exit(0)

    if opts.online:
        t = Talker(SETTINGS.metron_user, SETTINGS.metron_pass)
        t.identify_comics(file_list, opts.interactive, opts.ignore_existing)

    if opts.rename:
        file_list = rename_comics(file_list)

    if opts.sort:
        sort_list_of_comics(file_list)


if __name__ == "__main__":
    exit(main())
