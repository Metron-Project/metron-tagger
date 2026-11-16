from __future__ import annotations

from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import questionary
from darkseid.comic import Comic, ComicArchiveError, MetadataFormat
from darkseid.metadata import Metadata, Notes
from darkseid.utils import get_recursive_filelist
from darkseid.validate import SchemaVersion
from tqdm import tqdm

from metrontagger import __version__
from metrontagger.duplicates import DuplicateIssue, Duplicates, DuplicatesPresenter
from metrontagger.filerenamer import FileRenamer
from metrontagger.filesorter import FileSorter
from metrontagger.talker import Talker
from metrontagger.ui import UIPresenter

if TYPE_CHECKING:
    from argparse import Namespace

    from metrontagger.settings import MetronTaggerSettings

LOGGER = getLogger(__name__)

FORMAT_NAMES = {
    MetadataFormat.COMIC_INFO: "ComicInfo.xml",
    MetadataFormat.METRON_INFO: "MetronInfo.xml",
}

VALID_SCHEMA_NAMES = {
    SchemaVersion.COMIC_INFO_V2: "ComicInfo Version 2",
    SchemaVersion.COMIC_INFO_V1: "ComicInfo Version 1",
    SchemaVersion.METRON_INFO_V1_1: "MetronInfo Version 1.1",
    SchemaVersion.METRON_INFO_V1_2: "MetronInfo Version 1.2",
}


def _open_comic(path: Path | str) -> Comic | None:
    """Open a comic archive, printing an error and returning None if it isn't valid."""
    path = Path(path)
    try:
        return Comic(path)
    except ComicArchiveError:
        LOGGER.exception("Comic not valid: %s", path)
        UIPresenter.print_error(f"'{path.name}' is not a valid comic. Skipping...")
        return None


class Runner:
    """Class for running Metron Tagger operations.

    This class handles the execution of various operations such as renaming comics, exporting to cbz,
    removing duplicates, validating ComicInfo, and more based on the provided settings.
    """

    def __init__(self: Runner, args: Namespace, config: MetronTaggerSettings) -> None:
        """Initialize the Runner with the parsed arguments and MetronTaggerSettings."""
        self.args = args
        self.config = config

    def _selected_formats(self) -> list[MetadataFormat]:
        """Return the metadata formats requested with --comicinfo and --metroninfo."""
        return [
            fmt
            for fmt, selected in (
                (MetadataFormat.COMIC_INFO, self.args.comicinfo),
                (MetadataFormat.METRON_INFO, self.args.metroninfo),
            )
            if selected
        ]

    @staticmethod
    def migrate_ci_to_mi(file_list: list[Path]) -> None:
        """Migrate ComicInfo.xml metadata to MetronInfo.xml format.

        Comics that have ComicInfo.xml but no MetronInfo.xml get a MetronInfo.xml built from
        it, with a note recording the migration.

        Args:
            file_list: The comic files to process.
        """

        def create_mi_note(md: Metadata) -> Metadata:
            now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
            note_txt = f"Data migrated from 'ComicInfo.xml' using MetronTagger-{__version__} on {now_date}."
            if md.notes is None:
                md.notes = Notes(metron_info=note_txt)
            elif not md.notes.metron_info:
                md.notes.metron_info = note_txt
            return md

        UIPresenter.print_title("Migrating ComicInfo.xml to MetronInfo.xml:")

        for item in file_list:
            if (comic := _open_comic(item)) is None:
                continue

            if comic.has_metadata(MetadataFormat.COMIC_INFO) and not comic.has_metadata(
                MetadataFormat.METRON_INFO
            ):
                md = comic.read_metadata(MetadataFormat.COMIC_INFO)
                md = create_mi_note(md)
                if comic.write_metadata(md, MetadataFormat.METRON_INFO):
                    UIPresenter.print_success(
                        f"Migrated information to new MetronInfo.xml for '{comic}'"
                    )
                else:
                    UIPresenter.print_error(
                        f"There was an error writing MetronInfo.xml for '{comic}'"
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

    def _rename_comic(self, renamer: FileRenamer, path: Path) -> Path | None:
        """Rename a single comic from its metadata, returning its new path if renamed."""
        if (comic := _open_comic(path)) is None:
            return None

        if (md := self._get_comic_metadata(comic)) is None:
            UIPresenter.print_warning(f"skipping '{path.name}'. no metadata available.")
            return None

        renamer.set_metadata(md)
        if (new_path := renamer.rename_file(path)) is None:
            return None

        UIPresenter.print_success(f"renamed '{path.name}' -> '{new_path.name}'")
        return new_path

    def rename_comics(self: Runner, file_list: list[Path]) -> list[Path]:
        """Rename comic archives based on metadata.

        Args:
            file_list: The comic archive file paths to rename.

        Returns:
            The file list with each renamed comic's path replaced by its new path.
        """
        UIPresenter.print_title("Renaming Comic:")
        renamer = self._create_file_renamer()
        return [self._rename_comic(renamer, path) or path for path in file_list]

    def _export_to_zip(self: Runner, file_list: list[Path]) -> None:
        """Export comic archives to cbz format.

        Optionally deletes the original archives when --delete-original is given.

        Args:
            file_list: The comic archive file paths to export.
        """
        UIPresenter.print_title("Exporting to CBZ:")
        for path in file_list:
            if path.suffix.lower() == ".cbz":
                UIPresenter.print_warning(
                    f"'{path.name}' is already a cbz archive. Skipping..."
                )
                continue

            if (comic := _open_comic(path)) is None:
                continue

            if not comic.export_as_zip(path.with_suffix(".cbz")):
                UIPresenter.print_error(f"Failed to export '{path.name}'")
                continue

            UIPresenter.print_success(f"Exported '{path.name}' to a cbz archive.")
            if self.args.delete_original:
                UIPresenter.print_success(f"Removing '{path.name}'.")
                try:
                    path.unlink()
                except OSError as e:
                    LOGGER.warning("Failed to remove file %s: %s", path.name, e)
                    UIPresenter.print_error(f"Failed to remove file: {path.name}.")

    def _validate_comic_info(
        self: Runner, file_list: list[Path], remove_ci: bool = False
    ) -> None:
        """Validate metadata in comic archives."""
        UIPresenter.print_title("Validating Metadata:")
        for path in file_list:
            if (comic := _open_comic(path)) is None:
                continue

            present = [fmt for fmt in FORMAT_NAMES if comic.has_metadata(fmt)]
            if not present:
                UIPresenter.print_warning(
                    f"'{comic.path.name}' doesn't have any metadata files."
                )
                continue

            for fmt in self._selected_formats():
                if fmt in present:
                    self._check_if_xml_is_valid(comic, fmt, remove_ci)

    @staticmethod
    def _check_if_xml_is_valid(
        comic: Comic, fmt: MetadataFormat, remove_metadata: bool
    ) -> None:
        result = comic.validate_metadata(fmt)
        if schema_name := VALID_SCHEMA_NAMES.get(result):
            UIPresenter.print_success(f"'{comic.path.name}' has a valid {schema_name}")
            return

        UIPresenter.print_error(f"'{comic.path.name}' is not valid")
        if remove_metadata and comic.remove_metadata([fmt]):
            UIPresenter.print_warning(f"Removed non-valid metadata from '{comic.path.name}'.")

    def _sort_comic_list(self: Runner, file_list: list[Path]) -> None:
        """Move comic archives into the configured sort directory.

        Args:
            file_list: The comic archive file paths to sort.
        """
        if not (sort_dir := self.config["sort.directory"]):
            UIPresenter.print_error(
                "\nUnable to sort files. No destination directory was provided."
            )
            return

        UIPresenter.print_title("Starting Sorting of Comic Archives:")
        file_sorter = FileSorter(sort_dir)
        for path in file_list:
            if not file_sorter.sort_comics(path):
                UIPresenter.print_error(f"Unable to move '{path.name}'.")

    def _comics_with_no_metadata(self: Runner, file_list: list[Path]) -> None:
        """Print the files missing any of the requested metadata formats.

        Args:
            file_list: The comic archive file paths to check.
        """
        UIPresenter.print_title("Showing Files Without Metadata:")
        if not (formats := self._selected_formats()):
            return

        for path in file_list:
            if (comic := _open_comic(path)) is None:
                continue
            if not all(comic.has_metadata(fmt) for fmt in formats):
                UIPresenter.print_success(f"{path}")

    def _delete_metadata(self: Runner, file_list: list[Path]) -> None:
        """Remove the requested metadata formats from comic archives.

        Args:
            file_list: The comic archive file paths to remove metadata from.
        """
        UIPresenter.print_title("Removing Metadata:")
        selected = self._selected_formats()
        for path in file_list:
            if (comic := _open_comic(path)) is None:
                continue

            formats = [fmt for fmt in selected if comic.has_metadata(fmt)]
            if not formats:
                UIPresenter.print_warning(f"no metadata in '{path.name}'")
                continue

            names = " and ".join(f"'{FORMAT_NAMES[fmt]}'" for fmt in formats)
            if comic.remove_metadata(formats):
                UIPresenter.print_success(f"Removed {names} metadata from '{path.name}'.")
            else:
                LOGGER.error("Failed to remove %s from %s", names, path)
                UIPresenter.print_error(f"Failed to remove {names} from '{path.name}'")

    @staticmethod
    def _update_ci_xml(file_list: list[DuplicateIssue]) -> None:
        """Reset the ComicInfo page list of comics that had duplicate pages removed.

        Args:
            file_list: The DuplicateIssue objects for the processed comics.
        """
        for item in tqdm(file_list):
            if (comic := _open_comic(item.path_)) is None:
                continue

            if comic.has_metadata(MetadataFormat.COMIC_INFO):
                md = comic.read_metadata(MetadataFormat.COMIC_INFO)
                new_md = Metadata()
                new_md.set_default_page_list(comic.get_number_of_pages())
                md.overlay(new_md)
                if not comic.write_metadata(md, MetadataFormat.COMIC_INFO):
                    LOGGER.error("Could not write metadata to %s", comic)

    @staticmethod
    def _review_duplicate_images(
        dup_objs: Duplicates, distinct_hashes: list[str]
    ) -> list[DuplicateIssue]:
        """Show each duplicate image and collect the pages the user chooses to remove.

        Returns:
            One DuplicateIssue per comic, holding every page selected for removal from it.
        """
        selected: dict[str, DuplicateIssue] = {}
        for count, img_hash in enumerate(distinct_hashes, 1):
            comics_lst = dup_objs.get_comic_list_from_hash(img_hash)
            comics_lst_str = "\n\t".join(Path(i.path_).name for i in comics_lst)
            UIPresenter.print_success(
                f"Showing image #{count} which is in:\n\t{comics_lst_str}"
            )
            dup_objs.show_image(comics_lst[0])

            # TODO: Give user the option to delete page per book.
            if not questionary.confirm(
                "Do you want to remove this image from all comics?"
            ).ask():
                continue

            for comic in comics_lst:
                page = comic.pages_index[0]
                if (existing := selected.get(comic.path_)) is not None:
                    existing.add_page_index(page)
                else:
                    selected[comic.path_] = DuplicateIssue(comic.path_, [page])

        return list(selected.values())

    def _write_duplicate_changes(
        self: Runner, dup_objs: Duplicates, duplicates_lst: list[DuplicateIssue]
    ) -> None:
        """Delete the selected pages and print before/after summaries."""
        DuplicatesPresenter.print_pre_processing_summary(duplicates_lst)
        results = dup_objs.delete_comic_pages(duplicates_lst)

        # Only update sizes of files that were processed successfully.
        for duplicate_issue in duplicates_lst:
            if results.get(duplicate_issue.path_, False):
                duplicate_issue.update_ending_size()

        DuplicatesPresenter.print_post_processing_summary(duplicates_lst, results)
        DuplicatesPresenter.print_statistics(dup_objs.get_statistics())

    def _remove_duplicates(
        self: Runner, file_list: list[Path], *, quick: bool = False
    ) -> None:
        """Find duplicate images across comics and let the user remove them.

        Args:
            file_list: The comic archive file paths to check for duplicates.
            quick: If True, only scan the first 3 interior pages and last 3 pages of each comic.
        """
        with Duplicates(file_list, quick=quick) as dup_objs:
            distinct_hashes = dup_objs.get_distinct_hashes()
            if not questionary.confirm(
                f"Found {len(distinct_hashes)} duplicate images. Do you want to review them?",
            ).ask():
                return

            duplicates_lst = self._review_duplicate_images(dup_objs, distinct_hashes)
            if (
                duplicates_lst
                and questionary.confirm("Do want to write your changes to the comics?").ask()
            ):
                self._write_duplicate_changes(dup_objs, duplicates_lst)
            else:
                UIPresenter.print_success("No duplicate page changes to write.")

        # Ask user if they want to update ComicInfo.xml pages for changes. Not necessary for MetronInfo.xml
        if (
            self.args.comicinfo
            and duplicates_lst
            and questionary.confirm(
                "Do you want to update the comic's 'comicinfo.xml' for the changes?",
            ).ask()
        ):
            self._update_ci_xml(duplicates_lst)

    def _tag_online(self: Runner, file_list: list[Path]) -> None:
        """Tag comics from Metron, by issue ID for a single file or by searching otherwise."""
        with Talker(
            self.config["metron.auth_token"],
            self.args.metroninfo,
            self.args.comicinfo,
            username=self.config["metron.user"] or None,
            redis_url=self.config["metron.redis_url"] or None,
        ) as t:
            if self.args.id and len(file_list) == 1:
                # Single file with --id: interpret as issue ID
                t.retrieve_single_issue(self.args.id, file_list[0])
            else:
                t.identify_comics(self.args, file_list)

    def run(self: Runner) -> None:
        """Run the requested operations, in a fixed order, on every file under the given paths.

        Commands that need --comicinfo and/or --metroninfo are checked when the arguments are
        parsed (see `options.check_args`), so they aren't checked again here.
        """
        if not (file_list := get_recursive_filelist(self.args.path)):
            UIPresenter.print_warning("No files to process. Exiting.")
            raise SystemExit(0)

        if self.args.missing:
            self._comics_with_no_metadata(file_list)
        if self.args.export_to_cbz:
            self._export_to_zip(file_list)
        if self.args.delete:
            self._delete_metadata(file_list)
        if self.args.duplicates:
            self._remove_duplicates(file_list)
        if self.args.quick_duplicates:
            self._remove_duplicates(file_list, quick=True)
        if self.args.id or self.args.online:
            self._tag_online(file_list)
        if self.args.migrate:
            self.migrate_ci_to_mi(file_list)
        if self.args.rename:
            file_list = self.rename_comics(file_list)
        if self.args.sort:
            self._sort_comic_list(file_list)
        if self.args.validate:
            self._validate_comic_info(file_list, self.args.remove_non_valid)
