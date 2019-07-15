import tempfile
from unittest import TestCase, main

from metrontagger.taggerlib.utils import cleanup_string, create_issue_query_dict


class TestTaggerlibUtils(TestCase):
    def setUp(self):
        self.series = "Aquaman"
        self.number = "1"
        self.year = "1962"
        self.tmp_file = tempfile.NamedTemporaryFile(
            prefix=f"{self.series} #{self.number} ({self.year})", suffix=".cbz"
        )

    def test_cleanup_colon_space(self):
        test_str = "Hashtag: Danger (2019)"
        res = cleanup_string(test_str)
        self.assertEqual(res, "Hashtag - Danger (2019)")

    def test_cleanup_space_colon(self):
        test_str = "Hashtag :Danger (2019)"
        res = cleanup_string(test_str)
        self.assertEqual(res, "Hashtag -Danger (2019)")

    def test_cleanup_colon(self):
        test_str = "Hashtag:Danger (2019)"
        res = cleanup_string(test_str)
        self.assertEqual(res, "Hashtag-Danger (2019)")

    def test_cleanup_backslash(self):
        test_str = "Hack/Slash (2019)"
        res = cleanup_string(test_str)
        self.assertEqual(res, "Hack-Slash (2019)")

    def test_cleanup_questionmark(self):
        test_str = "What If? (2019)"
        res = cleanup_string(test_str)
        self.assertEqual(res, "What If (2019)")

    def test_create_issue_query_dict(self):
        i = create_issue_query_dict(self.tmp_file.name)
        results = {
            "series": f"{self.series}",
            "volume": "",
            "number": f"{self.number}",
            "year": f"{self.year}",
        }
        self.assertEqual(i, results)


if __name__ == "__main__":
    main()
