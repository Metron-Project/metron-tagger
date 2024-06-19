"""Class to sort comic file based on its metadata tags"""

from __future__ import annotations

from pathlib import Path
from shutil import Error, move
from typing import TYPE_CHECKING

import questionary
from darkseid.comic import Comic

if TYPE_CHECKING:
    from darkseid.metadata import Metadata

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string


def get_file_size(fn: Path) -> float:
    """
    Returns the size of the file in megabytes.

    Args:
        fn (Path): The path to the file.

    Returns:
        float: The size of the file in megabytes.
    """

    megabyte = 1048576
    return fn.stat().st_size / megabyte


class FileSorter:
    """
    Method to move the comic file based on its metadata tag.
    """

    def __init__(self: FileSorter, directory: str) -> None:
        """
        Initializes the FileSorter object with the specified directory.

        Args:
            directory (str): The directory path for sorting files.
        """

        self.sort_directory = directory

    @staticmethod
    def _cleanup_metadata(
        meta_data: Metadata,
    ) -> tuple[str | None, str | None, str | None]:
        """
        Clean the metadata string.

        Args:
            meta_data (Metadata): The metadata to clean.

        Returns:
            tuple[str | None, str | None, str | None]: Cleaned publisher, series, and volume strings.
        """

        publisher = cleanup_string(meta_data.publisher.name) if meta_data.publisher else None
        if meta_data.series:
            series = cleanup_string(meta_data.series.name)
            volume = cleanup_string(meta_data.series.volume)
        else:
            series = volume = None
        return publisher, series, volume

    @staticmethod
    def _move_files(orig: Path, new: Path) -> bool:
        """
        Move files from the original path to the new path.

        Args:
            orig (Path): The original path of the file.
            new (Path): The new path to move the file to.

        Returns:
            bool: True if the file is successfully moved, False otherwise.
        """

        try:
            move(orig, new)
        except Error:
            return False
        questionary.print(f"moved '{orig.name}' to '{new}'", style=Styles.SUCCESS)
        return True

    @staticmethod
    def _overwrite_existing(new_path: Path, old_comic: Path) -> None:
        """
        Check and overwrite an existing comic if needed.

        Args:
            new_path (Path): The path to the new comic location.
            old_comic (Path): The path to the old comic file.

        Returns:
            None
        """

        existing_comic = new_path / old_comic.name
        if existing_comic.exists():
            existing_size = get_file_size(existing_comic)
            new_size = get_file_size(old_comic)
            msg = (
                f"{existing_comic.name} exists at {existing_comic.parent}.\nOld file: "
                f"{existing_size:.2f} MB -> New file: {new_size:.2f} MB"
            )
            questionary.print(msg, Styles.WARNING)
            if questionary.confirm(
                "Would you like to overwrite existing file?",
                default=False,
            ).ask():
                existing_comic.unlink()

    def _get_new_path(
        self: FileSorter,
        meta_data: Metadata,
        publisher: str,
        series: str,
        volume: str,
    ) -> Path:
        """
        Generate the new path for sorting the comic file based on metadata.

        Args:
            meta_data (Metadata): The metadata of the comic.
            publisher (str): The publisher of the comic.
            series (str): The series of the comic.
            volume (str): The volume of the comic.

        Returns:
            Path: The new path for sorting the comic file.
        """

        tpb = (
            False if meta_data.series is None else meta_data.series.format == "Trade Paperback"
        )
        return (
            Path(self.sort_directory)
            / publisher
            / f"{f'{series} TPB' if tpb else f'{series}'}"
            / f"v{volume}"
        )

    @staticmethod
    def _create_new_path(new_sort_path: Path) -> bool:
        """
        Create a new directory path.

        Args:
            new_sort_path (Path): The path to create the new directory.

        Returns:
            bool: True if the directory is successfully created, False otherwise.
        """

        try:
            new_sort_path.mkdir(parents=True)
        except PermissionError:
            questionary.print(
                f"Due to permission error, failed to create directory: {new_sort_path}",
                style=Styles.ERROR,
            )
            return False
        return True

    def sort_comics(self: FileSorter, comic: Path) -> bool:
        """
        Method to sort the comic file based on its metadata tag.

        Args:
            comic (Path): The path to the comic file.

        Returns:
            bool: True if the comic file is successfully sorted, False otherwise.
        """

        try:
            comic_archive = Comic(str(comic))
        except FileNotFoundError:
            return False

        if not comic_archive.has_metadata():
            return False

        meta_data = comic_archive.read_metadata()
        publisher, series, volume = self._cleanup_metadata(meta_data)

        if not publisher or not series or not volume:
            questionary.print(
                "Missing metadata from comic and will be unable to sort."
                f"Publisher: {publisher}\nSeries: {series}\nVolume: {volume}",
                style=Styles.WARNING,
            )
            return False

        new_path = self._get_new_path(meta_data, publisher, series, volume)
        self._overwrite_existing(new_path, comic)

        if not new_path.is_dir() and not self._create_new_path(new_path):
            return False

        return self._move_files(comic, new_path)
