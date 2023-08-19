"""Class to sort comic file based on it's metadata tags"""
from pathlib import Path
from shutil import Error, move
from typing import Optional

import questionary
from darkseid.comic import Comic
from darkseid.metadata import Metadata

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string

MEGABYTE = 1048576


class FileSorter:
    """Class to move comic files based on it's metadata tags"""

    def __init__(self: "FileSorter", directory: str) -> None:
        self.sort_directory = directory

    @staticmethod
    def _cleanup_metadata(
        meta_data: Metadata,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
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
            existing_size = existing_comic.stat().st_size / MEGABYTE
            new_size = old_comic.stat().st_size / MEGABYTE
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

    def sort_comics(self: "FileSorter", comic: Path) -> bool:
        """Method to move the comic file based on it's metadata tag"""
        comic_archive = Comic(comic)
        if comic_archive.has_metadata():
            meta_data = comic_archive.read_metadata()
        else:
            return False

        publisher, series, volume = self._cleanup_metadata(meta_data)

        if publisher and series and volume:
            tpb = meta_data.series.format == "Trade Paperback"
            new_path = (
                Path(self.sort_directory)
                / publisher
                / f"{f'{series} TPB' if tpb else f'{series}'}"
                / f"v{volume}"
            )
        else:
            questionary.print(
                "Missing metadata from comic and will be unable to sort."
                f"Publisher: {publisher}\nSeries: {series}\nVolume: {volume}",
                style=Styles.WARNING,
            )
            return False

        self._overwrite_existing(new_path, comic)

        if not new_path.is_dir():
            try:
                new_path.mkdir(parents=True)
            except PermissionError:
                questionary.print(
                    f"due to permission error, failed to create directory: {new_path}",
                    style=Styles.ERROR,
                )
                return False

        return self._move_files(comic, new_path)
