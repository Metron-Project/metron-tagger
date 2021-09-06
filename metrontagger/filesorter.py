"""Class to sort comic file based on it's metadata tags"""
import pathlib
from os import fspath
from pathlib import Path
from shutil import Error, move
from typing import Optional, Tuple

from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata

from .utils import cleanup_string


class FileSorter:
    """Class to move comic files based on it's metadata tags"""

    def __init__(self, directory: str) -> None:
        self.sort_directory = directory

    def _cleanup_metadata(
        self, meta_data: GenericMetadata
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Clean the metadata string."""
        publisher = cleanup_string(meta_data.publisher)
        series = cleanup_string(meta_data.series)
        volume = cleanup_string(meta_data.volume)
        return publisher, series, volume

    def _move_files(self, orig: Path, new: Path) -> bool:
        try:
            # Until python 3.9 is released, we need to force the Path
            # objects to strings so shutils.move will work correctly.
            move(fspath(orig), fspath(new))
            print(f"moved '{orig.name}' to '{new}'")
            return True
        except Error as e:
            print(f"Unable to move comic. Error: {e}")
            return False

    def sort_comics(self, comic: Path) -> bool:
        """Method to move the comic file based on it's metadata tag"""
        comic_archive = ComicArchive(comic)
        if comic_archive.has_metadata():
            meta_data = comic_archive.read_metadata()
        else:
            return False

        publisher, series, volume = self._cleanup_metadata(meta_data)

        if publisher and series and volume:
            new_path = pathlib.Path(self.sort_directory) / publisher / series / f"v{volume}"
        else:
            print(
                "Missing metadata from comic and will be unable to sort."
                + f"Publisher: {publisher}\nSeries: {series}\nVolume: {volume}"
            )
            return False

        if not new_path.is_dir():
            try:
                new_path.mkdir(parents=True)
            except PermissionError:
                print(f"due to permission error, failed to create directory: {new_path}")
                return False

        return self._move_files(pathlib.Path(comic), new_path)
