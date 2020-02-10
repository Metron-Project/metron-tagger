import os
import tempfile
from pathlib import Path
from shutil import make_archive
from unittest import TestCase, main

from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata

from metrontagger.taggerlib.filesorter import FileSorter


class TestFileSorter(TestCase):
    def setUp(self):
        self.tmp_archive_dir = tempfile.TemporaryDirectory()
        self.tmp_image_dir = tempfile.TemporaryDirectory()
        self.tmp_sort_dir = tempfile.TemporaryDirectory()
        # Create 3 fake jpgs
        img_1 = tempfile.NamedTemporaryFile(
            suffix=".jpg", dir=self.tmp_image_dir.name, mode="wb"
        )
        img_1.write(b"test data")
        img_2 = tempfile.NamedTemporaryFile(
            suffix=".jpg", dir=self.tmp_image_dir.name, mode="wb"
        )
        img_2.write(b"more data")
        img_3 = tempfile.NamedTemporaryFile(
            suffix=".jpg", dir=self.tmp_image_dir.name, mode="wb"
        )
        img_3.write(b"yet more data")

        self.zfile = os.path.join(self.tmp_archive_dir.name, "comic")

        # Create zipfile
        open(make_archive(self.zfile, "zip", self.tmp_image_dir.name), "rb").read()

        # Create test metadata
        self.meta_data = GenericMetadata()
        self.meta_data.series = "Aquaman"
        self.meta_data.volume = "1"
        self.meta_data.issue = "1"
        self.meta_data.year = "2011"
        self.meta_data.publisher = "DC Comics"

        # Now write it to the zipfile
        comic_archive = ComicArchive(self.zfile + ".zip")
        comic_archive.write_metadata(self.meta_data)

    def tearDown(self):
        self.tmp_archive_dir.cleanup()
        self.tmp_sort_dir.cleanup()
        self.tmp_image_dir.cleanup()

    def test_sort_file(self):
        result_dir = Path(self.tmp_sort_dir.name).joinpath(
            self.meta_data.publisher, self.meta_data.series, f"v{self.meta_data.volume}"
        )
        file_sorter = FileSorter(self.tmp_sort_dir.name)
        res = file_sorter.sort_comics(self.zfile + ".zip")
        self.assertTrue(result_dir.is_dir())
        self.assertTrue(res)

    def test_sort_files_without_metadata(self):
        # If we add more tests we should probably create another tmpfile
        # since we are removing the metadata from the tmpfile
        comic = ComicArchive(self.zfile + ".zip")
        comic.remove_metadata()

        file_sorter = FileSorter(self.tmp_sort_dir.name)
        res = file_sorter.sort_comics(self.zfile + ".zip")
        self.assertFalse(res)


if __name__ == "__main__":
    main()
