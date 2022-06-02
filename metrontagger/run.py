from pathlib import Path
from typing import List

import questionary
from darkseid.comicarchive import ComicArchive
from darkseid.utils import get_recursive_filelist

from metrontagger.filerenamer import FileRenamer
from metrontagger.filesorter import FileSorter
from metrontagger.settings import MetronTaggerSettings
from metrontagger.styles import Styles
from metrontagger.talker import Talker


class Runner:
    """Main runner"""

    def __init__(self, config: MetronTaggerSettings) -> None:
        self.config = config

    def rename_comics(self, file_list: List[Path]) -> List[Path]:
        questionary.print(
            "\nStarting comic archive renaming:\n-------------------------------",
            style=Styles.TITLE,
        )

        # Lists to track filename changes
        new_file_names: List[Path] = []
        original_files_changed: List[Path] = []
        for comic in file_list:
            comic_archive = ComicArchive(comic)
            if not comic_archive.has_metadata():
                questionary.print(
                    f"skipping '{comic.name}'. no metadata available.", style=Styles.WARNING
                )
                continue

            meta_data = comic_archive.read_metadata()
            renamer = FileRenamer(meta_data)
            renamer.set_template(self.config.rename_template)
            renamer.set_issue_zero_padding(self.config.rename_issue_number_padding)
            renamer.set_smart_cleanup(self.config.rename_use_smart_string_cleanup)

            unique_name = renamer.rename_file(comic)
            if unique_name is None:
                continue

            # track what files are being renamed
            new_file_names.append(unique_name)
            original_files_changed.append(comic)

            questionary.print(
                f"renamed '{comic.name}' -> '{unique_name.name}'", style=Styles.SUCCESS
            )

        # Update file_list for renamed files
        for original_file in original_files_changed:
            file_list.remove(original_file)

        # Add new file names to file list.
        file_list.extend(iter(new_file_names))
        return file_list

    @staticmethod
    def _export_to_cb7(file_list: List[Path]) -> None:
        questionary.print("\nExporting to cb7:\n-----------------", style=Styles.TITLE)
        for comic in file_list:
            ca = ComicArchive(comic)
            if ca.is_zip():
                new_fn = Path(comic).with_suffix(".cb7")
                if ca.export_as_cb7(new_fn):
                    questionary.print(
                        f"Exported '{comic.name}' to a cb7 archive.", style=Styles.SUCCESS
                    )
                else:
                    questionary.print(f"Failed to export '{comic.name}'", style=Styles.ERROR)
            else:
                questionary.print(
                    f"'{comic.name}' is not a cbz archive. skipping...", style=Styles.WARNING
                )

    def _sort_list_of_comics(self, file_list: List[Path]) -> None:
        if not self.config.sort_dir:
            questionary.print(
                "\nUnable to sort files. No destination directory was provided.",
                style=Styles.ERROR,
            )
            return

        questionary.print(
            "\nStarting sorting of comic archives:\n----------------------------------",
            style=Styles.TITLE,
        )
        file_sorter = FileSorter(self.config.sort_dir)
        for comic in file_list:
            result = file_sorter.sort_comics(comic)
            if not result:
                questionary.print(f"unable to move {comic.name}.", style=Styles.ERROR)

    @staticmethod
    def _list_comics_with_missing_metadata(file_list: List[Path]) -> None:
        questionary.print(
            "\nShowing files without metadata:\n-------------------------------",
            style=Styles.TITLE,
        )
        for comic in file_list:
            comic_archive = ComicArchive(comic)
            if comic_archive.has_metadata():
                continue
            questionary.print(f"no metadata in '{comic.name}'", style=Styles.SUCCESS)

    @staticmethod
    def _delete_comics_metadata(file_list: List[Path]) -> None:
        questionary.print("\nRemoving metadata:\n-----------------", style=Styles.TITLE)
        for comic in file_list:
            comic_archive = ComicArchive(comic)
            if comic_archive.has_metadata():
                comic_archive.remove_metadata()
                questionary.print(
                    f"removed metadata from '{comic.name}'", style=Styles.SUCCESS
                )
            else:
                questionary.print(f"no metadata in '{comic.name}'", style=Styles.WARNING)

    def run(self) -> None:

        if not (file_list := get_recursive_filelist(self.config.path)):
            print("No files to process. Exiting.")
            exit(0)

        if self.config.missing:
            self._list_comics_with_missing_metadata(file_list)

        if self.config.delete:
            self._delete_comics_metadata(file_list)

        if self.config.id:
            if len(file_list) == 1:
                t = Talker(self.config.metron_user, self.config.metron_pass)
                t.retrieve_single_issue(file_list[0], self.config.id)
            else:
                questionary.print(
                    "More than one file was passed for Id processing. Exiting...",
                    style=Styles.WARNING,
                )
                exit(0)

        if self.config.online:
            t = Talker(self.config.metron_user, self.config.metron_pass)
            t.identify_comics(file_list, self.config)

        if self.config.rename:
            file_list = self.rename_comics(file_list)

        if self.config.sort:
            self._sort_list_of_comics(file_list)

        if self.config.export_to_cb7:
            self._export_to_cb7(file_list)
