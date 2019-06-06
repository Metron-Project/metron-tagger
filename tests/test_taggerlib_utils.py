import unittest

from metrontagger.taggerlib.utils import cleanup_string


class TestTaggerlibUtils(unittest.TestCase):
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
