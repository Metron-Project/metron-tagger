from __future__ import annotations

import sys
from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from darkseid.comic import Comic, MetadataFormat
from darkseid.metadata import Metadata, Notes
from darkseid.utils import get_recursive_filelist
from tqdm import tqdm

from metrontagger.duplicates import DuplicateIssue, Duplicates
from metrontagger.filerenamer import FileRenamer
from metrontagger.filesorter import FileSorter
from metrontagger.utils import create_print_title

if TYPE_CHECKING:
    from argparse import Namespace

    from metrontagger.settings import MetronTaggerSettings
from metrontagger import __version__
from metrontagger.styles import Styles
from metrontagger.talker import Talker
from metrontagger.validate import SchemaVersion, ValidateMetadata

LOGGER = getLogger(__name__)


class Runner:
    """Class for running Metron Tagger operations.

    This class handles the execution of various operations such as renaming comics, exporting to cbz,
    removing duplicates, validating ComicInfo, and more based on the provided settings.
    """

    def __init__(self: Runner, args: Namespace, config: MetronTaggerSettings) -> None:
        """Initialize the Runner with MetronTaggerSettings.

        This method sets up the Runner object with the provided MetronTaggerSettings configuration.
        """
        self.args = args
        self.config = config

    @staticmethod
    def migrate_ci_to_mi(file_list: list[Path]) -> None:
        """
        Migrate ComicInfo.xml metadata to MetronInfo.xml format.

        This static method processes a list of comic files, checking for existing ComicInfo.xml metadata and
        migrating it to the MetronInfo.xml format if applicable. It provides feedback on the migration process
        through printed messages.

        Args:
            file_list (list[Path]): A list of Path objects representing the comic files to be processed.

        Returns:
            None
        """

        def create_mi_note(md: Metadata) -> Metadata:
            now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
            note_txt = f"Data migrated from 'ComicInfo.xml' using MetronTagger-{__version__} on {now_date}."
            if md.notes is None:
                md.notes = Notes(metron_info=note_txt)
            elif not md.notes.metron_info:
                md.notes.metron_info = note_txt
            return md

        msg = create_print_title("Migrating ComicInfo.xml to MetronInfo.xml:")
        questionary.print(msg, style=Styles.TITLE)

        for item in file_list:
            comic = Comic(item)
            if comic.has_metadata(MetadataFormat.COMIC_RACK) and not comic.has_metadata(
                MetadataFormat.METRON_INFO
            ):
                md = comic.read_metadata(MetadataFormat.COMIC_RACK)
                md = create_mi_note(md)
                if comic.write_metadata(md, MetadataFormat.METRON_INFO):
                    questionary.print(
                        f"Migrated information to new MetronInfo.xml for '{comic}'",
                        style=Styles.SUCCESS,
                    )
                else:
                    questionary.print(
                        f"There was an error writing MetronInfo.xml for '{comic}'",
                        style=Styles.ERROR,
                    )

    def rename_comics(self: Runner, file_list: list[Path]) -> list[Path]:
        """Rename comic archives based on metadata.

        This method renames comic archives in the provided file list according to the metadata information,
        using the specified renaming template and settings.

        Args:
            file_list: list[Path]: The list of comic archive file paths to rename.

        Returns:
            list[Path]: The updated list of file paths after renaming.
        """
        msg = create_print_title("Renaming ComicInfo.xml to MetronInfo.xml:")
        questionary.print(msg, style=Styles.TITLE)

        # Lists to track filename changes
        new_file_names: list[Path] = []
        original_files_changed: list[Path] = []
        renamer = FileRenamer()
        for comic in file_list:
            comic_archive = Comic(comic)
            if comic_archive.has_metadata(MetadataFormat.METRON_INFO):
                md = comic_archive.read_metadata(MetadataFormat.METRON_INFO)
            elif comic_archive.has_metadata(MetadataFormat.COMIC_RACK):
                md = comic_archive.read_metadata(MetadataFormat.COMIC_RACK)
            else:
                questionary.print(
                    f"skipping '{comic.name}'. no metadata available.",
                    style=Styles.WARNING,
                )
                continue

            renamer.set_metadata(md)
            renamer.set_template(self.config["rename.rename_template"])
            renamer.set_issue_zero_padding(self.config["rename.rename_issue_number_padding"])
            renamer.set_smart_cleanup(self.config["rename.rename_use_smart_string_cleanup"])

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
        msg = create_print_title("Exporting to CBZ:")
        questionary.print(msg, style=Styles.TITLE)
        for comic in file_list:
            ca = Comic(str(comic))
            if ca.is_rar():
                new_fn = Path(comic).with_suffix(".cbz")
                if ca.export_as_zip(new_fn):
                    questionary.print(
                        f"Exported '{comic.name}' to a cbz archive.",
                        style=Styles.SUCCESS,
                    )
                    if self.args.delete_original:
                        questionary.print(f"Removing '{comic.name}'.", style=Styles.SUCCESS)
                        comic.unlink()
                else:
                    questionary.print(f"Failed to export '{comic.name}'", style=Styles.ERROR)
            else:
                questionary.print(
                    f"'{comic.name}' is not a cbr archive. skipping...",
                    style=Styles.WARNING,
                )

    def _validate_comic_info(
        self: Runner, file_list: list[Path], remove_ci: bool = False
    ) -> None:
        """Validate ComicInfo metadata in comic archives."""
        msg = create_print_title("Validating ComicInfo:")
        questionary.print(msg, style=Styles.TITLE)
        for comic in file_list:
            ca = Comic(comic)
            has_comic_rack = ca.has_metadata(MetadataFormat.COMIC_RACK)
            has_metron_info = ca.has_metadata(MetadataFormat.METRON_INFO)

            if not has_comic_rack and not has_metron_info:
                questionary.print(
                    f"'{ca.path.name}' doesn't have any metadata files.",
                    style=Styles.WARNING,
                )
                continue

            if self.args.comicinfo and has_comic_rack:
                xml = ca.archiver.read_file("ComicInfo.xml")
                self._check_if_xml_is_valid(ca, xml, MetadataFormat.COMIC_RACK, remove_ci)

            if self.args.metroninfo and has_metron_info:
                xml = ca.archiver.read_file("MetronInfo.xml")
                self._check_if_xml_is_valid(ca, xml, MetadataFormat.METRON_INFO, remove_ci)

    @staticmethod
    def _check_if_xml_is_valid(
        comic: Comic, xml: bytes, fmt: MetadataFormat, remove_metadata: bool
    ) -> None:
        result = ValidateMetadata(xml).validate()
        messages = {
            SchemaVersion.ci_v2: (
                f"'{comic.path.name}' has a valid ComicInfo Version 2",
                Styles.SUCCESS,
            ),
            SchemaVersion.ci_v1: (
                f"'{comic.path.name}' has a valid ComicInfo Version 1",
                Styles.SUCCESS,
            ),
            SchemaVersion.mi_v1: (
                f"'{comic.path.name}' has a valid MetronInfo Version 1",
                Styles.SUCCESS,
            ),
        }

        message, style = messages.get(
            result, (f"'{comic.path.name}' is not valid", Styles.ERROR)
        )
        questionary.print(message, style=style)

        if result not in messages and remove_metadata and comic.remove_metadata(fmt):
            questionary.print(
                f"Removed non-valid metadata from '{comic.path.name}'.",
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

        if not self.config["DEFAULT.sort_dir"]:
            questionary.print(
                "\nUnable to sort files. No destination directory was provided.",
                style=Styles.ERROR,
            )
            return

        msg = create_print_title("Starting Sorting of Comic Archives:")
        questionary.print(msg, style=Styles.TITLE)
        file_sorter = FileSorter(self.config["DEFAULT.sort_dir"])
        for comic in file_list:
            result = file_sorter.sort_comics(comic)
            if not result:
                questionary.print(f"Unable to move '{comic.name}'.", style=Styles.ERROR)

    def _comics_with_no_metadata(self: Runner, file_list: list[Path]) -> None:
        """Display files without metadata.

        This static method prints out the files in the provided list that do not have associated metadata.

        Args:
            file_list: list[Path]: The list of comic archive file paths to check for metadata.

        Returns:
            None
        """
        msg = create_print_title("Showing Files Without Metadata:")
        questionary.print(msg, style=Styles.TITLE)

        if not (self.args.comicinfo or self.args.metroninfo):
            return

        for comic in file_list:
            comic_archive = Comic(str(comic))
            if (
                self.args.comicinfo
                and not comic_archive.has_metadata(MetadataFormat.COMIC_RACK)
            ) or (
                self.args.metroninfo
                and not comic_archive.has_metadata(MetadataFormat.METRON_INFO)
            ):
                questionary.print(f"{comic}", style=Styles.SUCCESS)

    def _delete_metadata(self: Runner, file_list: list[Path]) -> None:
        """Remove metadata from comic archives.

        This static method removes metadata from the comic archives in the provided list, if metadata exists.

        Args:
            file_list: list[Path]: The list of comic archive file paths to remove metadata from.

        Returns:
            None
        """
        msg = create_print_title("Removing Metadata:")
        questionary.print(msg, style=Styles.TITLE)
        for item in file_list:
            comic_archive = Comic(item)
            formats_removed = []

            if self.args.comicinfo and comic_archive.has_metadata(MetadataFormat.COMIC_RACK):
                comic_archive.remove_metadata(MetadataFormat.COMIC_RACK)
                formats_removed.append("'ComicInfo.xml'")

            if self.args.metroninfo and comic_archive.has_metadata(MetadataFormat.METRON_INFO):
                comic_archive.remove_metadata(MetadataFormat.METRON_INFO)
                formats_removed.append("'MetronInfo.xml'")

            if formats_removed:
                fmt = " and ".join(formats_removed)
                msg = f"Removed {fmt} metadata from '{item.name}'."
                questionary.print(msg, style=Styles.SUCCESS)
            else:
                questionary.print(f"no metadata in '{item.name}'", style=Styles.WARNING)

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
            if comic.has_metadata(MetadataFormat.COMIC_RACK):
                md = comic.read_metadata(MetadataFormat.COMIC_RACK)
                new_md = Metadata()
                new_md.set_default_page_list(comic.get_number_of_pages())
                md.overlay(new_md)
                if not comic.write_metadata(md, MetadataFormat.COMIC_RACK):
                    LOGGER.error("Could not write metadata to %s", comic)

    @staticmethod
    def _create_duplicate_statistics_msg(stats: dict[str, int]) -> str:
        return (
            f"Total Pages: {stats['total_pages']}\n"
            f"Duplicate Pages: {stats['duplicate_pages']}\n"
            f"Unique Hashes: {stats['unique_duplicate_hashes']}\n"
            f"Comics Processed: {stats['comics_processed']}"
        )

    def _remove_duplicates(self: Runner, file_list: list[Path]) -> None:
        """Remove duplicate images from comic archives.

        This method identifies and allows the user to review and remove duplicate images from the provided list of
        comic archives, with options to delete pages per book and update the ComicInfo metadata.

        Args:
            file_list: list[Path]: The list of comic archive file paths to check for duplicates.

        Returns:
            None
        """

        with Duplicates(file_list) as dup_objs:
            distinct_hashes = dup_objs.get_distinct_hashes()
            if not questionary.confirm(
                f"Found {len(distinct_hashes)} duplicate images. Do you want to review them?",
            ).ask():
                return

            # List of page indexes to delete for each comic.
            duplicates_lst: list[DuplicateIssue] = []
            # This Loop runs for each *distinct* hash.
            for count, img_hash in enumerate(distinct_hashes, 1):
                comics_lst = dup_objs.get_comic_list_from_hash(img_hash)
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
                dup_objs.show_image(comics_lst[0])

                # TODO: Give user the option to delete page per book.
                if questionary.confirm(
                    "Do you want to remove this image from all comics?"
                ).ask():
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
                dup_objs.delete_comic_pages(duplicates_lst)
                msg = self._create_duplicate_statistics_msg(dup_objs.get_statistics())
                questionary.print(msg, style=Styles.INFO)
            else:
                questionary.print("No duplicate page changes to write.", style=Styles.SUCCESS)

        # Ask user if they want to update ComicInfo.xml pages for changes. Not necessary for MetronInfo.xml
        if (
            self.args.comicinfo
            and questionary.confirm(
                "Do you want to update the comic's 'comicinfo.xml' for the changes?",
            ).ask()
        ):
            self._update_ci_xml(duplicates_lst)

    def _no_md_fmt_set(self: Runner) -> bool:
        if not self.args.metroninfo and not self.args.comicinfo:
            questionary.print("No metadata format was given. Exiting...", style=Styles.ERROR)
            return True
        return False

    def run(self: Runner) -> None:  # noqa: PLR0912
        """Run Metron Tagger operations based on the provided settings.

        This method orchestrates various operations such as handling missing metadata, exporting to cbz,
        deleting metadata, removing duplicates, processing Ids or online, renaming comics, sorting, and validating
        comic information.

        Returns:
            None
        """

        if not (file_list := get_recursive_filelist(self.args.path)):
            questionary.print("No files to process. Exiting.", style=Styles.WARNING)
            sys.exit(0)

        if self.args.missing:
            if self._no_md_fmt_set():
                sys.exit(0)
            self._comics_with_no_metadata(file_list)

        if self.args.export_to_cbz:
            self._export_to_zip(file_list)

        if self.args.delete:
            if self._no_md_fmt_set():
                sys.exit(0)
            self._delete_metadata(file_list)

        if self.args.duplicates:
            self._remove_duplicates(file_list)

        if self.args.id or self.args.online:
            if self._no_md_fmt_set():
                sys.exit(0)

            t = Talker(
                self.config["metron.user"],
                self.config["metron.password"],
                self.args.metroninfo,
                self.args.comicinfo,
            )
            if self.args.id and len(file_list) == 1:
                # Single file with --id: interpret as issue ID
                t.retrieve_single_issue(self.args.id, file_list[0])
            else:
                t.identify_comics(self.args, file_list)

        if self.args.migrate:
            self.migrate_ci_to_mi(file_list)

        if self.args.rename:
            file_list = self.rename_comics(file_list)

        if self.args.sort:
            self._sort_comic_list(file_list)

        if self.args.validate:
            if self._no_md_fmt_set():
                sys.exit(0)
            self._validate_comic_info(file_list, self.args.remove_non_valid)
