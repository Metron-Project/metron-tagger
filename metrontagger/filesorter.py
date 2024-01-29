"""Class to sort comic file based on its metadata tags"""
from pathlib import Path
from shutil import Error, move

import questionary
from darkseid.comic import Comic
from darkseid.metadata import Metadata

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string


def get_file_size(fn: Path) -> float:
    megabyte = 1048576
    return fn.stat().st_size / megabyte


class FileSorter:
    """Class to move comic files based on its metadata tags"""

    def __init__(self: "FileSorter", directory: str) -> None:
        self.sort_directory = directory

    @staticmethod
    def _cleanup_metadata(
        meta_data: Metadata,
    ) -> tuple[str | None, str | None, str | None]:
        """Clean the metadata string."""
        publisher = cleanup_string(meta_data.publisher.name)
        series = cleanup_string(meta_data.series.name)
        volume = cleanup_string(meta_data.series.volume)
        return publisher, series, volume

    @staticmethod
    def _move_files(orig: Path, new: Path) -> bool:
        try:
            move(orig, new)
            questionary.print(f"moved '{orig.name}' to '{new}'", style=Styles.SUCCESS)
            return True
        except Error:
            return False

    @staticmethod
    def _overwrite_existing(new_path: Path, old_comic: Path) -> None:
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
        self: "FileSorter",
        meta_data: Metadata,
        publisher: str,
        series: str,
        volume: str,
    ) -> Path:
        tpb = meta_data.series.format == "Trade Paperback"
        return (
            Path(self.sort_directory)
            / publisher
            / f"{f'{series} TPB' if tpb else f'{series}'}"
            / f"v{volume}"
        )

    @staticmethod
    def _create_new_path(new_sort_path: Path) -> bool:
        try:
            new_sort_path.mkdir(parents=True)
        except PermissionError:
            questionary.print(
                f"Due to permission error, failed to create directory: {new_sort_path}",
                style=Styles.ERROR,
            )
            return False
        return True

    def sort_comics(self: "FileSorter", comic: Path) -> bool:
        """Method to move the comic file based on its metadata tag"""
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
