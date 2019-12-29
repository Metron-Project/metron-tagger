from unittest import TestCase, main

from ..comicapi.genericmetadata import GenericMetadata


class TestGenericMetadata(TestCase):
    def setUp(self):
        self.meta_data = GenericMetadata()
        self.meta_data.series = "Aquaman"
        self.meta_data.issue = "0"
        self.meta_data.title = "A Crash of Symbols"
        self.meta_data.isEmpty = False

        self.new_md = GenericMetadata()
        self.new_md.year = "1994"
        self.new_md.month = "10"
        self.new_md.day = "1"
        self.meta_data.isEmpty = False

    def test_metadata_overlay(self):
        self.meta_data.overlay(self.new_md)

        self.assertEqual(self.meta_data.series, "Aquaman")
        self.assertEqual(self.meta_data.issue, "0")
        self.assertEqual(self.meta_data.title, "A Crash of Symbols")
        self.assertEqual(self.meta_data.year, "1994")
        self.assertEqual(self.meta_data.month, "10")
        self.assertEqual(self.meta_data.day, "1")

    def test_metadata_credits(self):
        result = [
            {"person": "Peter David", "primary": True, "role": "Writer"},
            {"person": "Martin Egeland", "role": "Penciller"},
            {"person": "Martin Egeland", "role": "Cover"},
        ]

        self.meta_data.addCredit("Peter David", "Writer", primary=True)
        self.meta_data.addCredit("Martin Egeland", "Penciller")
        self.meta_data.addCredit("Martin Egeland", "Cover")

        self.assertEqual(self.meta_data.credits, result)

    def test_metadata_credits_overlay(self):
        new_credit = [{"person": "Tom McCray", "role": "Colorist"}]
        result = [
            {"person": "Peter David", "role": "Writer"},
            {"person": "Tom McCray", "role": "Colorist"},
        ]

        self.meta_data.addCredit("Peter David", "Writer")
        self.meta_data.overlayCredits(new_credit)

        self.assertEqual(self.meta_data.credits, result)

    def test_metadata_print_str(self):
        self.assertEqual(
            str(self.meta_data), "series: Aquaman\nissue:  0\ntitle:  A Crash of Symbols\n"
        )

    def test_no_metadata_print_str(self):
        m_data = GenericMetadata()
        self.assertEqual(str(m_data), "No metadata")


if __name__ == "__main__":
    main()
