import unittest

from comicapi.genericmetadata import GenericMetadata
from taggerlib.filerenamer import FileRenamer


class TestFileRenamer(unittest.TestCase):
    def setUp(self):
        self.md = GenericMetadata()
        self.md.series = "Aquaman"
        self.md.issue = "1"
        self.md.year = "2011"

    def test_determineName(self):
        renamer = FileRenamer(self.md)
        new_name = renamer.determineName("/tmp/test.cbz")
        self.assertEqual(new_name, "Aquaman #001 (2011).cbz")


if __name__ == "__main__":
    unittest.main()
