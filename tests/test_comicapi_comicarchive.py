import os
import tempfile
from shutil import make_archive
from unittest import TestCase, main

from metrontagger.comicapi.comicarchive import ComicArchive, MetaDataStyle
from metrontagger.comicapi.genericmetadata import GenericMetadata


class TestComicArchive(TestCase):
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

        self.zipfile = os.path.join(self.tmp_archive_dir.name, "Aquaman #1 (1994)")

        # Create zipfile
        open(make_archive(self.zipfile, "zip", self.tmp_image_dir.name), "rb").read()

        self.ca = ComicArchive(self.zipfile + ".zip")

        # Setup test metadata
        self.md = GenericMetadata()
        self.md.series = "Aquaman"
        self.md.issue = "0"
        self.md.title = "A Crash of Symbols"
        self.md.notes = "Test comment"

    def tearDown(self):
        self.tmp_archive_dir.cleanup()
        self.tmp_image_dir.cleanup()

    def test_zip_file_exists(self):
        res = self.ca.isZip()
        self.assertTrue(res)

    def test_archive_number_of_pages(self):
        res = self.ca.getNumberOfPages()
        self.assertEqual(res, 3)

    def test_archive_is_writable(self):
        res = self.ca.isWritable()
        self.assertTrue(res)

    def test_archive_is_writable_for_style(self):
        res = self.ca.isWritableForStyle(MetaDataStyle.CIX)
        self.assertTrue(res)

    def test_archive_test_metadata(self):
        # verify archive has no metadata
        res = self.ca.hasMetadata(MetaDataStyle.CIX)
        self.assertFalse(res)

        # now let's test that we can write some
        self.ca.writeMetadata(self.md, MetaDataStyle.CIX)
        has_md = self.ca.hasMetadata(MetaDataStyle.CIX)
        self.assertTrue(has_md)

        # Verify what was written
        new_md = self.ca.readMetadata(MetaDataStyle.CIX)
        self.assertEqual(new_md.series, self.md.series)
        self.assertEqual(new_md.issue, self.md.issue)
        self.assertEqual(new_md.title, self.md.title)
        self.assertEqual(new_md.notes, self.md.notes)

        # now remove what was just written
        self.ca.removeMetadata(MetaDataStyle.CIX)
        remove_md = self.ca.hasMetadata(MetaDataStyle.CIX)
        self.assertFalse(remove_md)

    def test_archive_get_page(self):
        # Get page 2
        img = self.ca.getPage(1)
        self.assertIsNotNone(img)

    def test_archive_metadata_from_filename(self):
        test_md = self.ca.metadataFromFilename()
        self.assertEqual(test_md.series, "Aquaman")
        self.assertEqual(test_md.issue, "1")
        self.assertEqual(test_md.year, "1994")

    def test_archive_apply_file_info_to_metadata(self):
        test_md = GenericMetadata()
        self.ca.applyArchiveInfoToMetadata(test_md)
        # TODO: Need to test calculate page sizes
        self.assertEqual(test_md.pageCount, 3)


if __name__ == "__main__":
    main()
