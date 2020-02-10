"""Class to sort comic file based on it's metadata tags"""
import pathlib
from os import fspath
from shutil import Error, move

from darkseid.comicarchive import ComicArchive

from .utils import cleanup_string


class FileSorter:
    """Class to move comic files based on it's metadata tags"""

    def __init__(self, directory):
        self.sort_directory = directory

    def sort_comics(self, comic):
        """Method to move the comic file based on it's metadata tag"""
        comic_archive = ComicArchive(comic)
        if comic_archive.has_metadata():
            meta_data = comic_archive.read_metadata()
        else:
            return False

        publisher = cleanup_string(meta_data.publisher)
        series = cleanup_string(meta_data.series)
        volume = "v" + cleanup_string(meta_data.volume)
        new_path = pathlib.Path(self.sort_directory) / publisher / series / volume

        if not new_path.is_dir():
            new_path.mkdir(parents=True)

        original_path = pathlib.Path(comic)
        try:
            # Until python 3.9 is released, we need to force the Path
            # objects to strings so shutils.move will work correctly.
            move(fspath(original_path), fspath(new_path))
            print(f"moved '{original_path.name}' to '{new_path}'")
        except Error:
            return False

        return True
