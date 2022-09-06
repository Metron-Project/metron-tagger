from pathlib import Path
from typing import List

import questionary
from darkseid.comic import Comic
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
            comic_archive = Comic(comic)
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

    def _export_to_cb7(self, file_list: List[Path]) -> None:
        questionary.print("\nExporting to cb7:\n-----------------", style=Styles.TITLE)
        for comic in file_list:
            ca = Comic(comic)
            if ca.is_zip() or ca.is_rar():
                new_fn = Path(comic).with_suffix(".cb7")
                if ca.export_as_cb7(new_fn):
                    questionary.print(
                        f"Exported '{comic.name}' to a cb7 archive.", style=Styles.SUCCESS
                    )
                    if self.config.delete_original:
                        questionary.print(f"Removing '{comic.name}'.", style=Styles.SUCCESS)
                        comic.unlink()
                else:
                    questionary.print(f"Failed to export '{comic.name}'", style=Styles.ERROR)
            else:
                questionary.print(
                    f"'{comic.name}' is not a cbr or cbz archive. skipping...",
                    style=Styles.WARNING,
                )

    def _export_to_zip(self, file_list: List[Path]) -> None:
        questionary.print("\nExporting to cbz:\n-----------------", style=Styles.TITLE)
        for comic in file_list:
            ca = Comic(comic)
            if ca.is_rar() or ca.is_sevenzip():
                new_fn = Path(comic).with_suffix(".cbz")
                if ca.export_as_zip(new_fn):
                    questionary.print(
                        f"Exported '{comic.name}' to a cbz archive.", style=Styles.SUCCESS
                    )
                    if self.config.delete_original:
                        questionary.print(f"Removing '{comic.name}'.", style=Styles.SUCCESS)
                        comic.unlink()
                else:
                    questionary.print(f"Failed to export '{comic.name}'", style=Styles.ERROR)
            else:
                questionary.print(
                    f"'{comic.name}' is not a cbr or cb7 archive. skipping...",
                    style=Styles.WARNING,
                )

    def _sort_comic_list(self, file_list: List[Path]) -> None:
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
    def _comics_with_no_metadata(file_list: List[Path]) -> None:
        questionary.print(
            "\nShowing files without metadata:\n-------------------------------",
            style=Styles.TITLE,
        )
        for comic in file_list:
            comic_archive = Comic(comic)
            if comic_archive.has_metadata():
                continue
            questionary.print(f"no metadata in '{comic.name}'", style=Styles.SUCCESS)

    @staticmethod
    def _delete_metadata(file_list: List[Path]) -> None:
        questionary.print("\nRemoving metadata:\n-----------------", style=Styles.TITLE)
        for comic in file_list:
            comic_archive = Comic(comic)
            if comic_archive.has_metadata():
                comic_archive.remove_metadata()
                questionary.print(
                    f"removed metadata from '{comic.name}'", style=Styles.SUCCESS
                )
            else:
                questionary.print(f"no metadata in '{comic.name}'", style=Styles.WARNING)

    def _has_credentials(self) -> bool:
        return bool(self.config.metron_user and self.config.metron_pass)

    def _get_credentials(self) -> bool:
        answers = questionary.form(
            user=questionary.text("What is your Metron username?"),
            passwd=questionary.text("What is your Metron password?"),
            save=questionary.confirm("Would you like to save your credentials?"),
        ).ask()
        if answers["user"] and answers["passwd"]:
            self.config.metron_user = answers["user"]
            self.config.metron_pass = answers["passwd"]
            if answers["save"]:
                self.config.save()
            return True
        return False

    def _get_sort_dir(self) -> bool:
        answers = questionary.form(
            dir=questionary.path("What directory should comics be sorted to?"),
            save=questionary.confirm("Would you like to save this location for future use?"),
        ).ask()
        if answers["dir"]:
            self.config.sort_dir = answers["dir"]
            if answers["save"]:
                self.config.save()
            return True
        return False

    def run(self) -> None:

        if not (file_list := get_recursive_filelist(self.config.path)):
            print("No files to process. Exiting.")
            exit(0)

        if self.config.missing:
            self._comics_with_no_metadata(file_list)

        if self.config.delete:
            self._delete_metadata(file_list)

        if self.config.id or self.config.online:
            if not self._has_credentials() and not self._get_credentials():
                questionary.print("No credentials provided. Exiting...")
                exit(0)

            t = Talker(self.config.metron_user, self.config.metron_pass)
            if self.config.id:
                if len(file_list) == 1:
                    t.retrieve_single_issue(file_list[0], self.config.id)
                else:
                    questionary.print(
                        "More than one file was passed for Id processing. Exiting...",
                        style=Styles.WARNING,
                    )
                    exit(0)
            else:
                t.identify_comics(file_list, self.config)

        if self.config.rename:
            file_list = self.rename_comics(file_list)

        if self.config.sort:
            if not self.config.sort_dir and not self._get_sort_dir():
                questionary.print("No sort directory given. Exiting...")
                exit(0)
            self._sort_comic_list(file_list)

        if self.config.export_to_cb7:
            self._export_to_cb7(file_list)

        if self.config.export_to_cbz:
            self._export_to_zip(file_list)
