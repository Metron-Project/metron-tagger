import os
import tempfile
from unittest import TestCase, main

from metrontagger.comicapi.filenameparser import FileNameParser as fn


class TestFileNameParser(TestCase):
    def setUp(self):
        self.comic = "Afterlife_With_Archie_V1_#002_(of_08)_(2013)"
        self.fnp = fn()

    def test_special_format(self):
        comic = "Aquaman TPB (1994)"
        _, issue_start, _ = self.fnp.getIssueNumber(comic)
        series, volume = self.fnp.getSeriesName(comic, issue_start)
        self.assertEqual(issue_start, 0)
        self.assertEqual(series, "Aquaman")
        self.assertEqual(volume, "1994")

    def test_get_issue_number(self):
        """Returns a tuple of issue number string, and start and end indexes in the filename"""
        issue, issue_start, issue_end = self.fnp.getIssueNumber(self.comic)
        self.assertEqual(issue, "002")
        self.assertEqual(issue_start, 25)
        self.assertEqual(issue_end, 29)

    def test_get_year(self):
        _, _, issue_end = self.fnp.getIssueNumber(self.comic)
        year = self.fnp.getYear(self.comic, issue_end)
        self.assertEqual(year, "2013")

    def test_get_series_name(self):
        _, issue_start, _ = self.fnp.getIssueNumber(self.comic)
        series, volume = self.fnp.getSeriesName(self.comic, issue_start)
        self.assertEqual(series, "Afterlife With Archie")
        self.assertEqual(volume, "1")

    def test_get_count(self):
        _, _, issue_end = self.fnp.getIssueNumber(self.comic)
        issue_count = self.fnp.getIssueCount(self.comic, issue_end)
        self.assertEqual(issue_count, "8")

    def test_fix_spaces(self):
        new_name = self.fnp.fixSpaces(self.comic)
        self.assertNotEqual(new_name, "Afterlife With Archie")

    def test_get_remainder(self):
        _, issue_start, issue_end = self.fnp.getIssueNumber(self.comic)
        year = self.fnp.getYear(self.comic, issue_end)
        _, volume = self.fnp.getSeriesName(self.comic, issue_start)
        count = self.fnp.getIssueCount(self.comic, issue_end)
        remainder = self.fnp.getRemainder(self.comic, year, count, volume, issue_end)
        self.assertEqual(remainder, "(of 08)")

    def test_parse_filename(self):
        tmp_file = tempfile.NamedTemporaryFile(prefix=self.comic, suffix=".cbz")
        tmp_path = tempfile.gettempdir()
        test_filename = tmp_path + os.path.pathsep + tmp_file.name
        tmp_file.close()

        self.fnp.parseFilename(test_filename)
        self.assertEqual(self.fnp.series, "Afterlife With Archie")
        self.assertEqual(self.fnp.volume, "1")
        self.assertEqual(self.fnp.issue, "2")
        self.assertEqual(self.fnp.issue_count, "8")
        self.assertEqual(self.fnp.year, "2013")


if __name__ == "__main__":
    main()
