import tempfile
from unittest import TestCase, main

from metrontagger.comicapi.comicinfoxml import ComicInfoXml
from metrontagger.comicapi.genericmetadata import GenericMetadata


class TestComicInfoXml(TestCase):
    def setUp(self):
        self.md = GenericMetadata()
        self.md.series = "Aquaman"
        self.md.issue = "1"
        self.md.year = "1993"
        self.md.day = "15"
        self.md.addCredit("Peter David", "Writer", primary=True)
        self.md.addCredit("Martin Egeland", "Penciller")
        self.md.addCredit("Martin Egeland", "Cover")
        self.md.addCredit("Kevin Dooley", "Editor")
        self.md.addCredit("Howard Shum", "Inker")
        self.md.addCredit("Tom McCraw", "Colorist")
        self.md.addCredit("Dan Nakrosis", "Letterer")

    def test_metadata_from_xml(self):
        res = ComicInfoXml().stringFromMetadata(self.md)
        # TODO: add more asserts to verify data.
        self.assertIsNotNone(res)

    def test_meta_write_to_file(self):
        tmp_file = tempfile.NamedTemporaryFile(suffix=".xml")
        ComicInfoXml().writeToExternalFile(tmp_file.name, self.md)
        # Read the contents of the file just written.
        # TODO: Verify the data.
        res = open(tmp_file.name).read()
        tmp_file.close()
        self.assertIsNotNone(res)

    def test_read_from_file(self):
        tmp_file = tempfile.NamedTemporaryFile(suffix=".xml")
        # Write metadata to file
        ComicInfoXml().writeToExternalFile(tmp_file.name, self.md)
        # Read the metadat from the file
        new_md = ComicInfoXml().readFromExternalFile(tmp_file.name)
        tmp_file.close()

        self.assertIsNotNone(new_md)
        self.assertEqual(new_md.series, self.md.series)
        self.assertEqual(new_md.issue, self.md.issue)
        self.assertEqual(new_md.year, self.md.year)
        self.assertEqual(new_md.month, self.md.month)
        self.assertEqual(new_md.day, self.md.day)


if __name__ == "__main__":
    main()
