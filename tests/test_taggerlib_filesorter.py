import os
import tempfile
from shutil import make_archive
from unittest import TestCase, main

from darkseid.comicarchive import ComicArchive, MetaDataStyle
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
        meta_data = GenericMetadata()
        meta_data.series = "Aquaman"
        meta_data.issue = "1"
        meta_data.year = "2011"
        meta_data.publisher = "DC Comics"

        # Now write it to the zipfile
        comic_archive = ComicArchive(self.zfile + ".zip")
        comic_archive.write_metadata(meta_data, MetaDataStyle.CIX)

    def tearDown(self):
        self.tmp_archive_dir.cleanup()
        self.tmp_sort_dir.cleanup()
        self.tmp_image_dir.cleanup()

    def test_sort_file(self):
        file_sorter = FileSorter(self.tmp_sort_dir.name)
        res = file_sorter.sort_comics(self.zfile + ".zip")
        self.assertTrue(res)


if __name__ == "__main__":
    main()
