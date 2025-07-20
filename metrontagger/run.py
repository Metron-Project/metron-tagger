from __future__ import annotations

import sys
from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from darkseid.comic import Comic, ComicArchiveError, MetadataFormat
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
from darkseid.validate import SchemaVersion

from metrontagger import __version__
from metrontagger.styles import Styles
from metrontagger.talker import Talker

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
            try:
                comic = Comic(item)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(item))
                questionary.print(f"'{item.name}' is not a valid comic.'", style=Styles.ERROR)
                return

            if comic.has_metadata(MetadataFormat.COMIC_INFO) and not comic.has_metadata(
                MetadataFormat.METRON_INFO
            ):
                md = comic.read_metadata(MetadataFormat.COMIC_INFO)
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

    def _create_file_renamer(self) -> FileRenamer:
        """Set options for file renaming."""
        renamer = FileRenamer()
        if rename_template := self.config["rename.rename_template"]:
            try:
                renamer.set_template(rename_template)
            except ValueError:
                LOGGER.exception("Failed to set rename template.")
        if number_padding := self.config["rename.rename_issue_number_padding"]:
            try:
                renamer.set_issue_zero_padding(number_padding)
            except ValueError:
                LOGGER.exception("Failed to set issue number padding.")
        renamer.set_smart_cleanup(self.config["rename.rename_use_smart_string_cleanup"])
        return renamer

    @staticmethod
    def _get_comic_metadata(comic: Comic) -> Metadata | None:
        # Prefer MetronInfo and if not present use ComicRack
        if comic.has_metadata(MetadataFormat.METRON_INFO):
            return comic.read_metadata(MetadataFormat.METRON_INFO)
        if comic.has_metadata(MetadataFormat.COMIC_INFO):
            return comic.read_metadata(MetadataFormat.COMIC_INFO)
        return None

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
        # Create & set the FileRenamer options
        renamer = self._create_file_renamer()

        for comic in file_list:
            try:
                comic_archive = Comic(comic)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(comic))
                continue

            # Retrieve the metadata from the comic
            md = self._get_comic_metadata(comic_archive)
            if md is None:
                questionary.print(
                    f"skipping '{comic.name}'. no metadata available.",
                    style=Styles.WARNING,
                )
                continue

            renamer.set_metadata(md)

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
            if comic.suffix.lower() in {".cbz"}:
                questionary.print(
                    f"'{comic.name}' is already a cbz archive. Skipping...",
                    style=Styles.WARNING,
                )
                continue

            try:
                ca = Comic(comic)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(comic))
                questionary.print(
                    f"'{comic.name}' is not a valid comic. Skipping...", style=Styles.ERROR
                )
                continue

            new_fn = Path(comic).with_suffix(".cbz")
            if ca.export_as_zip(new_fn):
                questionary.print(
                    f"Exported '{comic.name}' to a cbz archive.",
                    style=Styles.SUCCESS,
                )
                if self.args.delete_original:
                    questionary.print(f"Removing '{comic.name}'.", style=Styles.SUCCESS)
                    try:
                        comic.unlink()
                    except OSError as e:
                        LOGGER.warning("Failed to remove file %s: %s", comic.name, e)
                        questionary.print(
                            f"Failed to remove file: {comic.name}.", style=Styles.ERROR
                        )
            else:
                questionary.print(f"Failed to export '{comic.name}'", style=Styles.ERROR)

    def _validate_comic_info(
        self: Runner, file_list: list[Path], remove_ci: bool = False
    ) -> None:
        """Validate metadata in comic archives."""
        msg = create_print_title("Validating Metadata:")
        questionary.print(msg, style=Styles.TITLE)
        for comic in file_list:
            try:
                ca = Comic(comic)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(comic))
                questionary.print(
                    f"'{comic.name}' is not a valid comic. Skipping...", style=Styles.ERROR
                )
                continue

            has_comic_rack = ca.has_metadata(MetadataFormat.COMIC_INFO)
            has_metron_info = ca.has_metadata(MetadataFormat.METRON_INFO)

            if not has_comic_rack and not has_metron_info:
                questionary.print(
                    f"'{ca.path.name}' doesn't have any metadata files.",
                    style=Styles.WARNING,
                )
                continue

            if self.args.comicinfo and has_comic_rack:
                self._check_if_xml_is_valid(ca, MetadataFormat.COMIC_INFO, remove_ci)

            if self.args.metroninfo and has_metron_info:
                self._check_if_xml_is_valid(ca, MetadataFormat.METRON_INFO, remove_ci)

    @staticmethod
    def _check_if_xml_is_valid(
        comic: Comic, fmt: MetadataFormat, remove_metadata: bool
    ) -> None:
        result = comic.validate_metadata(fmt)
        messages = {
            SchemaVersion.COMIC_INFO_V2: (
                f"'{comic.path.name}' has a valid ComicInfo Version 2",
                Styles.SUCCESS,
            ),
            SchemaVersion.COMIC_INFO_V1: (
                f"'{comic.path.name}' has a valid ComicInfo Version 1",
                Styles.SUCCESS,
            ),
            SchemaVersion.METRON_INFO_V1: (
                f"'{comic.path.name}' has a valid MetronInfo Version 1",
                Styles.SUCCESS,
            ),
        }

        message, style = messages.get(
            result, (f"'{comic.path.name}' is not valid", Styles.ERROR)
        )
        questionary.print(message, style=style)

        if result not in messages and remove_metadata and comic.remove_metadata([fmt]):
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

        if sort_dir := self.config["sort.directory"]:
            msg = create_print_title("Starting Sorting of Comic Archives:")
            questionary.print(msg, style=Styles.TITLE)
            file_sorter = FileSorter(sort_dir)
            for comic in file_list:
                result = file_sorter.sort_comics(comic)
                if not result:
                    questionary.print(f"Unable to move '{comic.name}'.", style=Styles.ERROR)
            return
        # Sort directory not set.
        questionary.print(
            "\nUnable to sort files. No destination directory was provided.",
            style=Styles.ERROR,
        )

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
            try:
                comic_archive = Comic(comic)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(comic))
                questionary.print(
                    f"'{comic.name}' is not a valid comic. Skipping...", style=Styles.ERROR
                )
                continue

            if (
                self.args.comicinfo
                and not comic_archive.has_metadata(MetadataFormat.COMIC_INFO)
            ) or (
                self.args.metroninfo
                and not comic_archive.has_metadata(MetadataFormat.METRON_INFO)
            ):
                questionary.print(f"{comic}", style=Styles.SUCCESS)

    def _delete_metadata(self: Runner, file_list: list[Path]) -> None:  # noqa: PLR0912
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
            try:
                comic_archive = Comic(item)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(item))
                questionary.print(
                    f"'{item.name}' is not a valid comic. Skipping...", style=Styles.ERROR
                )
                continue
            formats_removed = []

            if (
                self.args.comicinfo
                and self.args.metroninfo
                and comic_archive.has_metadata(MetadataFormat.COMIC_INFO)
                and comic_archive.has_metadata(MetadataFormat.METRON_INFO)
            ):
                if not comic_archive.remove_metadata(
                    [MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO]
                ):
                    LOGGER.error("Failed to remove Metadata from %s", str(comic_archive))
                    questionary.print(
                        f"Failed to remove Metadata from '{item.name}'", style=Styles.ERROR
                    )
                else:
                    formats_removed.extend(["'ComicInfo.xml'", "'MetronInfo.xml'"])
            elif self.args.comicinfo and comic_archive.has_metadata(MetadataFormat.COMIC_INFO):
                if not comic_archive.remove_metadata([MetadataFormat.COMIC_INFO]):
                    LOGGER.error("Failed to remove ComicInfo.xml from: %s", str(item))
                    questionary.print(
                        f"Failed to remove ComicInfo.xml from '{item.name}'",
                        style=Styles.ERROR,
                    )
                else:
                    formats_removed.append("'ComicInfo.xml'")
            elif self.args.metroninfo and comic_archive.has_metadata(
                MetadataFormat.METRON_INFO
            ):
                if not comic_archive.remove_metadata([MetadataFormat.METRON_INFO]):
                    LOGGER.error("Failed to remove MetronInfo.xml from: %s", str(item))
                    questionary.print(
                        f"Failed to remove MetronInfo.xml from '{item.name}'",
                        style=Styles.ERROR,
                    )
                else:
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
            try:
                comic = Comic(item.path_)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(item))
                questionary.print(
                    f"'{item.path_}' is not a valid comic. Skipping...", style=Styles.ERROR
                )
                continue

            if comic.has_metadata(MetadataFormat.COMIC_INFO):
                md = comic.read_metadata(MetadataFormat.COMIC_INFO)
                new_md = Metadata()
                new_md.set_default_page_list(comic.get_number_of_pages())
                md.overlay(new_md)
                if not comic.write_metadata(md, MetadataFormat.COMIC_INFO):
                    LOGGER.error("Could not write metadata to %s", comic)

    def _remove_duplicates(self: Runner, file_list: list[Path]) -> None:  # noqa: PLR0912
        """Remove duplicate images from comic archives with size tracking.

        This method identifies and allows the user to review and remove duplicate images from the provided list of
        comic archives, with options to delete pages per book and update the ComicInfo metadata. It now tracks
        and displays file size savings after duplicate removal.

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
                                di.add_page_index(comic.pages_index[0])
                            else:
                                # Create new DuplicateIssue with automatic size tracking
                                new_dup = DuplicateIssue(comic.path_, [comic.pages_index[0]])
                                duplicates_lst.append(new_dup)
                        else:
                            # Create new DuplicateIssue with automatic size tracking
                            new_dup = DuplicateIssue(comic.path_, [comic.pages_index[0]])
                            duplicates_lst.append(new_dup)

            # After building the list let's ask the user if they want to write the changes.
            if (
                duplicates_lst
                and questionary.confirm("Do want to write your changes to the comics?").ask()
            ):
                # Display before processing summary
                self._display_pre_processing_summary(duplicates_lst)

                # Process the duplicates and get results
                results = dup_objs.delete_comic_pages(duplicates_lst)

                # Update ending sizes for all processed files
                for duplicate_issue in duplicates_lst:
                    if results.get(
                        duplicate_issue.path_, False
                    ):  # Only update if processing was successful
                        duplicate_issue.update_ending_size()

                # Display post-processing summary with size savings
                self._display_post_processing_summary(duplicates_lst, results)

                # Display overall statistics
                stats_msg = self._create_duplicate_statistics_msg(dup_objs.get_statistics())
                questionary.print(stats_msg, style=Styles.INFO)
            else:
                questionary.print("No duplicate page changes to write.", style=Styles.SUCCESS)

        # Ask user if they want to update ComicInfo.xml pages for changes. Not necessary for MetronInfo.xml
        if (
            self.args.comicinfo
            and duplicates_lst
            and questionary.confirm(
                "Do you want to update the comic's 'comicinfo.xml' for the changes?",
            ).ask()
        ):
            self._update_ci_xml(duplicates_lst)

    @staticmethod
    def _display_pre_processing_summary(duplicates_lst: list[DuplicateIssue]) -> None:
        """Display a summary before processing duplicate removal.

        Args:
            duplicates_lst: list[DuplicateIssue]: List of duplicate issues to be processed.
        """
        if not duplicates_lst:
            return

        total_pages_to_remove = sum(len(dup.pages_index) for dup in duplicates_lst)
        total_starting_size = sum(
            dup.starting_size_bytes
            for dup in duplicates_lst
            if dup.starting_size_bytes is not None
        )

        questionary.print("\n" + "=" * 60, style=Styles.INFO)
        questionary.print("DUPLICATE REMOVAL SUMMARY", style=Styles.TITLE)
        questionary.print("=" * 60, style=Styles.INFO)
        questionary.print(f"Comics to process: {len(duplicates_lst)}", style=Styles.INFO)
        questionary.print(
            f"Total duplicate pages to remove: {total_pages_to_remove}", style=Styles.INFO
        )
        questionary.print(
            f"Total starting size: {DuplicateIssue.format_file_size(total_starting_size)}",
            style=Styles.INFO,
        )
        questionary.print("=" * 60 + "\n", style=Styles.INFO)

    @staticmethod
    def _display_post_processing_summary(
        duplicates_lst: list[DuplicateIssue], results: dict[str, bool]
    ) -> None:
        """Display a summary after processing duplicate removal with size savings.

        Args:
            duplicates_lst: list[DuplicateIssue]: List of processed duplicate issues.
            results: dict[str, bool]: Results of the duplicate removal process.
        """
        if not duplicates_lst:
            return

        successful_removals = []
        failed_removals = []

        for duplicate_issue in duplicates_lst:
            if results.get(duplicate_issue.path_, False):
                successful_removals.append(duplicate_issue)
            else:
                failed_removals.append(duplicate_issue)

        questionary.print("\n" + "=" * 60, style=Styles.INFO)
        questionary.print("DUPLICATE REMOVAL RESULTS", style=Styles.TITLE)
        questionary.print("=" * 60, style=Styles.INFO)

        if successful_removals:
            questionary.print("✅ SUCCESSFULLY PROCESSED:", style=Styles.SUCCESS)
            questionary.print("-" * 40, style=Styles.INFO)

            total_pages_removed = 0
            total_size_saved = 0

            for dup in successful_removals:
                pages_removed = len(dup.pages_index)
                total_pages_removed += pages_removed

                size_info = ""
                if dup.starting_size_bytes is not None and dup.ending_size_bytes is not None:
                    size_reduction = dup.get_size_reduction()
                    if size_reduction and size_reduction > 0:
                        total_size_saved += size_reduction
                        percentage = dup.get_size_reduction_percentage()
                        size_info = f" (Saved: {dup.size_reduction_formatted}"
                        size_info += f", {percentage:.1f}%)" if percentage else ")"
                questionary.print(
                    f"  📁 {Path(dup.path_).name} - Removed {pages_removed} page{'s' if pages_removed != 1 else ''}{size_info}",
                    style=Styles.SUCCESS,
                )

            questionary.print("-" * 40, style=Styles.INFO)
            questionary.print(
                f"📊 Total pages removed: {total_pages_removed}", style=Styles.SUCCESS
            )
            questionary.print(
                f"💾 Total space saved: {DuplicateIssue.format_file_size(total_size_saved)}",
                style=Styles.SUCCESS,
            )

            if total_size_saved > 0:
                # Calculate average space saved per comic
                avg_saved = total_size_saved / len(successful_removals)
                questionary.print(
                    f"📈 Average space saved per comic: {DuplicateIssue.format_file_size(int(avg_saved))}",
                    style=Styles.SUCCESS,
                )

        if failed_removals:
            questionary.print("\n❌ FAILED TO PROCESS:", style=Styles.ERROR)
            questionary.print("-" * 40, style=Styles.INFO)
            for dup in failed_removals:
                pages_attempted = len(dup.pages_index)
                questionary.print(
                    f"  📁 {Path(dup.path_).name} - Failed to remove {pages_attempted} page{'s' if pages_attempted != 1 else ''}",
                    style=Styles.ERROR,
                )

        questionary.print("=" * 60 + "\n", style=Styles.INFO)

    @staticmethod
    def _create_duplicate_statistics_msg(stats: dict[str, int]) -> str:
        """Create a formatted statistics message for duplicate processing.

        Args:
            stats: dict[str, int]: Statistics dictionary from duplicate processing.

        Returns:
            str: Formatted statistics message.
        """
        return (
            f"📈 PROCESSING STATISTICS:\n"
            f"  • Total Pages Scanned: {stats['total_pages']:,}\n"
            f"  • Duplicate Pages Found: {stats['duplicate_pages']:,}\n"
            f"  • Unique Duplicate Images: {stats['unique_duplicate_hashes']:,}\n"
            f"  • Comics Processed: {stats['comics_processed']:,}"
        )

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
