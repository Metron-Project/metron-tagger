import os
import tempfile
from shutil import make_archive
from unittest import TestCase, main

from metrontagger.comicapi.genericmetadata import GenericMetadata
from metrontagger.taggerlib.filerenamer import FileRenamer


class TestFileRenamer(TestCase):
    def setUp(self):
        self.tmp_archive_dir = tempfile.TemporaryDirectory()
        self.tmp_image_dir = tempfile.TemporaryDirectory()
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

        self.zipfile = os.path.join(self.tmp_archive_dir.name, "comic")

        # Create zipfile
        open(make_archive(self.zipfile, "zip", self.tmp_image_dir.name), "rb").read()

        # Create test metadata
        self.md = GenericMetadata()
        self.md.series = "Aquaman"
        self.md.issue = "1"
        self.md.year = "2011"

    def tearDown(self):
        self.tmp_archive_dir.cleanup()
        self.tmp_image_dir.cleanup()

    def test_determine_name(self):
        renamer = FileRenamer(self.md)
        new_name = renamer.determineName(self.zipfile + ".zip")
        self.assertEqual(new_name, "Aquaman #001 (2011).zip")


if __name__ == "__main__":
    main()
