from __future__ import annotations

import sys
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from darkseid.comic import Comic
from darkseid.metadata import Metadata
from darkseid.utils import get_recursive_filelist
from tqdm import tqdm

from metrontagger.duplicates import DuplicateIssue, Duplicates
from metrontagger.filerenamer import FileRenamer
from metrontagger.filesorter import FileSorter
from metrontagger.logging import init_logging

if TYPE_CHECKING:
    from metrontagger.settings import MetronTaggerSettings
from metrontagger.styles import Styles
from metrontagger.talker import Talker
from metrontagger.validate_ci import SchemaVersion, ValidateComicInfo

LOGGER = getLogger(__name__)


class Runner:
    """Class for running Metron Tagger operations.

    This class handles the execution of various operations such as renaming comics, exporting to cbz,
    removing duplicates, validating ComicInfo, and more based on the provided settings.
    """

    def __init__(self: Runner, config: MetronTaggerSettings) -> None:
        """Initialize the Runner with MetronTaggerSettings.

        This method sets up the Runner object with the provided MetronTaggerSettings configuration.
        """

        self.config = config

    def rename_comics(self: Runner, file_list: list[Path]) -> list[Path]:
        """Rename comic archives based on metadata.

        This method renames comic archives in the provided file list according to the metadata information,
        using the specified renaming template and settings.

        Args:
            file_list: list[Path]: The list of comic archive file paths to rename.

        Returns:
            list[Path]: The updated list of file paths after renaming.
        """

        questionary.print(
            "\nStarting comic archive renaming:\n-------------------------------",
            style=Styles.TITLE,
        )

        # Lists to track filename changes
        new_file_names: list[Path] = []
        original_files_changed: list[Path] = []
        renamer = FileRenamer()
        for comic in file_list:
            comic_archive = Comic(str(comic))
            if not comic_archive.has_metadata():
                questionary.print(
                    f"skipping '{comic.name}'. no metadata available.",
                    style=Styles.WARNING,
                )
                continue

            meta_data = comic_archive.read_metadata()
            renamer.set_metadata(meta_data)
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
                f"renamed '{comic.name}' -> '{unique_name.name}'",
                style=Styles.SUCCESS,
            )

        # Update file_list for renamed files
        for original_file in original_files_changed:
            file_list.remove(original_file)

        # Add new file names to file list.
        file_list.extend(iter(new_file_names))
        return file_list

    def _export_to_zip(self: Runner, file_list: list[Path]) -> None:
        """Export comic archives to cbz format.

        This method exports the comic archives in the provided file list to cbz format, and optionally deletes the
        original archives based on the configuration settings.

        Args:
            file_list: list[Path]: The list of comic archive file paths to export.

        Returns:
            None
        """

        questionary.print("\nExporting to cbz:\n-----------------", style=Styles.TITLE)
        for comic in file_list:
            ca = Comic(str(comic))
            if ca.is_rar():
                new_fn = Path(comic).with_suffix(".cbz")
                if ca.export_as_zip(new_fn):
                    questionary.print(
                        f"Exported '{comic.name}' to a cbz archive.",
                        style=Styles.SUCCESS,
                    )
                    if self.config.delete_original:
                        questionary.print(f"Removing '{comic.name}'.", style=Styles.SUCCESS)
                        comic.unlink()
                else:
                    questionary.print(f"Failed to export '{comic.name}'", style=Styles.ERROR)
            else:
                questionary.print(
                    f"'{comic.name}' is not a cbr archive. skipping...",
                    style=Styles.WARNING,
                )

    @staticmethod
    def _validate_comic_info(file_list: list[Path], remove_ci: bool = False) -> None:
        """Validate ComicInfo metadata in comic archives.

        This static method validates the ComicInfo metadata in the provided list of comic archives, displaying the
        validation results and optionally removing non-valid metadata based on the 'remove_ci' flag.

        Args:
            file_list: list[Path]: The list of comic archive file paths to validate.
            remove_ci: bool, optional: A flag indicating whether to remove non-valid metadata. Defaults to False.

        Returns:
            None
        """

        questionary.print("\nValidating ComicInfo:\n---------------------", style=Styles.TITLE)
        for comic in file_list:
            ca = Comic(str(comic))
            if not ca.has_metadata():
                questionary.print(
                    f"'{ca.path.name}' doesn't have a ComicInfo.xml file.",
                    style=Styles.WARNING,
                )
                continue
            xml = ca.archiver.read_file("ComicInfo.xml")
            result = ValidateComicInfo(xml).validate()
            if result == SchemaVersion.v2:
                questionary.print(
                    f"'{ca.path.name}' is a valid ComicInfo Version 2",
                    style=Styles.SUCCESS,
                )
            elif result == SchemaVersion.v1:
                questionary.print(
                    f"'{ca.path.name}' is a valid ComicInfo Version 1",
                    style=Styles.SUCCESS,
                )
            else:
                questionary.print(f"'{ca.path.name}' is not valid", style=Styles.ERROR)
                if remove_ci and ca.remove_metadata():
                    questionary.print(
                        f"Removed non-valid metadata from '{ca.path.name}'.",
                        style=Styles.WARNING,
                    )

    def _sort_comic_list(self: Runner, file_list: list[Path]) -> None:
        """Sort comic archives in the provided list.

        This method sorts the comic archives in the file list based on the specified destination directory,
        using the configured sorting settings.

        Args:
            file_list: list[Path]: The list of comic archive file paths to sort.

        Returns:
            None
        """

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
                questionary.print(f"Unable to move '{comic.name}'.", style=Styles.ERROR)

    @staticmethod
    def _comics_with_no_metadata(file_list: list[Path]) -> None:
        """Display files without metadata.

        This static method prints out the files in the provided list that do not have associated metadata.

        Args:
            file_list: list[Path]: The list of comic archive file paths to check for metadata.

        Returns:
            None
        """

        questionary.print(
            "\nShowing files without metadata:\n-------------------------------",
            style=Styles.TITLE,
        )
        for comic in file_list:
            comic_archive = Comic(str(comic))
            if comic_archive.has_metadata():
                continue
            questionary.print(f"{comic}", style=Styles.SUCCESS)

    @staticmethod
    def _delete_metadata(file_list: list[Path]) -> None:
        """Remove metadata from comic archives.

        This static method removes metadata from the comic archives in the provided list, if metadata exists.

        Args:
            file_list: list[Path]: The list of comic archive file paths to remove metadata from.

        Returns:
            None
        """

        questionary.print("\nRemoving metadata:\n-----------------", style=Styles.TITLE)
        for comic in file_list:
            comic_archive = Comic(str(comic))
            if comic_archive.has_metadata():
                comic_archive.remove_metadata()
                questionary.print(
                    f"removed metadata from '{comic.name}'",
                    style=Styles.SUCCESS,
                )
            else:
                questionary.print(f"no metadata in '{comic.name}'", style=Styles.WARNING)

    def _has_credentials(self: Runner) -> bool:
        """Check if Metron credentials are present.

        This method returns True if Metron credentials are provided in the configuration settings, otherwise False.

        Returns:
            bool: True if Metron credentials are present, False otherwise.
        """

        return bool(self.config.metron_user and self.config.metron_pass)

    def _get_credentials(self: Runner) -> bool:
        """Prompt the user to enter Metron credentials.

        This method asks the user to input their Metron username and password, and provides an option to save the
        credentials based on the user's choice.

        Returns:
            bool: True if the user entered both username and password, False otherwise.
        """

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

    def _get_sort_dir(self: Runner) -> bool:
        """Prompt the user to specify the directory for sorting comics.

        This method asks the user to input the directory path where the comics should be sorted to, and provides an
        option to save this location for future use.

        Returns:
            bool: True if a directory path is provided, False otherwise.
        """

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

    @staticmethod
    def _get_duplicate_entry_index(
        comic_path: str,
        dups_list: list[DuplicateIssue],
    ) -> int | None:
        """Get the index of a duplicate entry in the list.

        This static method searches for the index of a duplicate entry in the list of DuplicateIssue objects based on
        the provided comic path.

        Args:
            comic_path: str: The path of the comic to search for.
            dups_list: list[DuplicateIssue]: The list of DuplicateIssue objects to search within.

        Returns:
            int | None: The index of the duplicate entry if found, otherwise None.
        """

        return next(
            (idx for idx, item in enumerate(dups_list) if comic_path in item.path_),
            None,
        )

    @staticmethod
    def _update_ci_xml(file_list: list[DuplicateIssue]) -> None:
        """Update ComicInfo metadata in comic archives.

        This static method updates the ComicInfo metadata in the provided list of comic archives with default page
        list information, if metadata exists.

        Args:
            file_list: list[DuplicateIssue]: The list of DuplicateIssue objects representing comic archives.

        Returns:
            None
        """

        for item in tqdm(file_list):
            comic = Comic(item.path_)
            if comic.has_metadata():
                md = comic.read_metadata()
                new_md = Metadata()
                new_md.set_default_page_list(comic.get_number_of_pages())
                md.overlay(new_md)
                if not comic.write_metadata(md):
                    LOGGER.error("Could not write metadata to %s", comic)

    def _remove_duplicates(self: Runner, file_list: list[Path]) -> None:
        """Remove duplicate images from comic archives.

        This method identifies and allows the user to review and remove duplicate images from the provided list of
        comic archives, with options to delete pages per book and update the ComicInfo metadata.

        Args:
            file_list: list[Path]: The list of comic archive file paths to check for duplicates.

        Returns:
            None
        """

        dups_obj = Duplicates(file_list)
        distinct_hashes = dups_obj.get_distinct_hashes()
        if not questionary.confirm(
            f"Found {len(distinct_hashes)} duplicate images. Do you want to review them?",
        ).ask():
            return

        # List of page indexes to delete for each comic.
        duplicates_lst: list[DuplicateIssue] = []
        # This Loop runs for each *distinct* hash.
        for count, img_hash in enumerate(distinct_hashes, 1):
            comics_lst = dups_obj.get_comic_list_from_hash(img_hash)
            # Simple info message to show the user
            comics_lst_str = "\n\t".join(
                map(str, [Path(i.path_).name for i in comics_lst]),
            )
            questionary.print(
                f"Showing image #{count} which is in:\n\t{comics_lst_str}",
                style=Styles.SUCCESS,
            )
            # Get image from the first comic in the comics list for the hash to display
            # to the user.
            first_comic = dups_obj.get_comic_info_for_distinct_hash(img_hash)
            dups_obj.show_image(first_comic)

            # TODO: Give user the option to delete page per book.
            if questionary.confirm("Do you want to remove this image from all comics?").ask():
                for comic in comics_lst:
                    if duplicates_lst:
                        dup_entry_idx = self._get_duplicate_entry_index(
                            comic.path_,
                            duplicates_lst,
                        )
                        if dup_entry_idx is not None:
                            di: DuplicateIssue = duplicates_lst[dup_entry_idx]
                            di.pages_index.append(comic.pages_index[0])
                        else:
                            duplicates_lst.append(
                                DuplicateIssue(comic.path_, [comic.pages_index[0]]),
                            )
                    else:
                        duplicates_lst.append(
                            DuplicateIssue(comic.path_, [comic.pages_index[0]]),
                        )

        # After building the list let's ask the user if they want to write the changes.
        if (
            duplicates_lst
            and questionary.confirm("Do want to write your changes to the comics?").ask()
        ):
            dups_obj.delete_comic_pages(duplicates_lst)
        else:
            questionary.print("No duplicate page changes to write.", style=Styles.SUCCESS)

        # Ask user if they want to update ComicInfo.xml for changes.
        if questionary.confirm(
            "Do you want to update the comic's 'comicinfo.xml' for the changes?",
        ).ask():
            self._update_ci_xml(duplicates_lst)

    def run(self: Runner) -> None:  # noqa: PLR0912
        """Run Metron Tagger operations based on the provided settings.

        This method orchestrates various operations such as handling missing metadata, exporting to cbz,
        deleting metadata, removing duplicates, processing Ids or online, renaming comics, sorting, and validating
        comic information.

        Returns:
            None
        """

        if not (file_list := get_recursive_filelist(self.config.path)):
            questionary.print("No files to process. Exiting.", style=Styles.WARNING)
            sys.exit(0)

        # Start logging
        init_logging(self.config)

        if self.config.missing:
            self._comics_with_no_metadata(file_list)

        if self.config.export_to_cbz:
            self._export_to_zip(file_list)

        if self.config.delete:
            self._delete_metadata(file_list)

        if self.config.duplicates:
            self._remove_duplicates(file_list)

        if self.config.id or self.config.online:
            if not self._has_credentials() and not self._get_credentials():
                questionary.print("No credentials provided. Exiting...", style=Styles.ERROR)
                sys.exit(0)

            t = Talker(self.config.metron_user, self.config.metron_pass)
            if self.config.id:
                if len(file_list) == 1:
                    t.retrieve_single_issue(file_list[0], self.config.id)
                else:
                    questionary.print(
                        "More than one file was passed for Id processing. Exiting...",
                        style=Styles.WARNING,
                    )
                    sys.exit(0)
            else:
                t.identify_comics(file_list, self.config)

        if self.config.rename:
            file_list = self.rename_comics(file_list)

        if self.config.sort:
            if not self.config.sort_dir and not self._get_sort_dir():
                questionary.print("No sort directory given. Exiting...")
                sys.exit(0)
            self._sort_comic_list(file_list)

        if self.config.validate:
            self._validate_comic_info(file_list, self.config.remove_non_valid)
