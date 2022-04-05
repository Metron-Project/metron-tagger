"""Main project file"""
import signal
import sys
from argparse import Namespace
from pathlib import Path
from typing import List

from darkseid.comicarchive import ComicArchive
from darkseid.utils import get_recursive_filelist

from .filerenamer import FileRenamer
from .filesorter import FileSorter
from .options import make_parser
from .settings import MetronTaggerSettings
from .talker import Talker


def sigint_handler(signal, frame):
    print("KeyboardInterrupt. Exiting...")
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_handler)


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


def sort_list_of_comics(sort_dir: str, file_list: List[Path]) -> None:
    if not sort_dir:
        print("\nUnable to sort files. No destination directory was provided.")
        return

    print("\nStarting sorting of comic archives:\n----------------------------------")
    file_sorter = FileSorter(sort_dir)
    for comic in file_list:
        result = file_sorter.sort_comics(comic)
        if not result:
            print(f"unable to move {comic.name}.")


def export_to_cb7(file_list: List[Path]) -> None:
    print("\nExporting to cb7:\n-----------------")
    for comic in file_list:
        ca = ComicArchive(comic)
        if ca.is_zip():
            new_fn = Path(comic).with_suffix(".cb7")
            if ca.export_as_cb7(new_fn):
                print(f"Exported '{comic.name}' to a cb7 archive.")
            else:
                print(f"Failed to export '{comic.name}'")
        else:
            print(f"'{comic.name}' is not a cbz archive. skipping...")


def get_options() -> Namespace:
    parser = make_parser()
    return parser.parse_args()


def update_settings(settings: MetronTaggerSettings, opts: Namespace) -> None:
    if opts.user:
        settings.metron_user = opts.user

    if opts.password:
        settings.metron_pass = opts.password

    if opts.sort_dir:
        settings.sort_dir = opts.sort_dir

    if opts.set_metron_user or opts.set_sort_dir:
        settings.save()


def rename_comics(file_list: List[Path], settings: MetronTaggerSettings) -> List[Path]:
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
        renamer.set_template(settings.rename_template)
        renamer.set_issue_zero_padding(settings.rename_issue_number_padding)
        renamer.set_smart_cleanup(settings.rename_use_smart_string_cleanup)

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

    # Add new file names to file list.
    file_list.extend(iter(new_file_names))
    return file_list


def main() -> None:
    """
    Main func
    """
    opts = get_options()
    settings = MetronTaggerSettings()
    update_settings(settings, opts)

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
        t = Talker(settings.metron_user, settings.metron_pass)
        if len(file_list) == 1:
            t.retrieve_single_issue(file_list[0], opts.id)
        else:
            print("More than one file was passed for Id processing. Exiting...")
            exit(0)

    if opts.online:
        t = Talker(settings.metron_user, settings.metron_pass)
        t.identify_comics(file_list, opts.interactive, opts.ignore_existing)

    if opts.rename:
        file_list = rename_comics(file_list, settings)

    if opts.sort:
        sort_list_of_comics(settings.sort_dir, file_list)

    if opts.export_to_cb7:
        export_to_cb7(file_list)


if __name__ == "__main__":
    main()
