import os
from shutil import Error, move

from metrontagger.comicapi.comicarchive import ComicArchive, MetaDataStyle
from metrontagger.taggerlib.utils import cleanup_string


class FileSorter:
    def __init__(self, directory):
        self.set_directory(directory)

    def set_directory(self, directory):
        self.sort_directory = directory

    def set_template(self, template):
        self.template = template

    def sort_comics(self, comic):
        ca = ComicArchive(comic)
        if ca.hasMetadata(MetaDataStyle.CIX):
            md = ca.readMetadata(MetaDataStyle.CIX)
        else:
            return False

        if md is not None:
            # Cleanup the publisher & series metadata so they play nicely with filesystems.
            publisher = cleanup_string(md.publisher)
            series = cleanup_string(md.series)
            if md.volume:
                volume = "v" + cleanup_string(md.volume)
                new_path = (
                    self.sort_directory
                    + os.sep
                    + publisher
                    + os.sep
                    + series
                    + os.sep
                    + volume
                    + os.sep
                )
            else:
                new_path = (
                    self.sort_directory + os.sep + publisher + os.sep + series + os.sep
                )
        else:
            return False

        if not os.path.isdir(new_path):
            os.makedirs(new_path)

        try:
            move(comic, new_path)
            print(f"moved {os.path.basename(comic)} to {new_path}.")
        except Error:
            return False

        return True
