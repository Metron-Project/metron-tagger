from unittest import TestCase, main

from metrontagger.comicapi.issuestring import IssueString


class TestIssueString(TestCase):
    def test_issue_string_pad(self):
        val = IssueString(int(1)).asString(pad=3)
        self.assertEqual(val, "001")

    def test_issue_float(self):
        val = IssueString("1½").asFloat()
        self.assertEqual(val, 1.5)

    def test_issue_float_half(self):
        val = IssueString("½").asFloat()
        self.assertEqual(val, 0.5)

    def test_issue_verify_float(self):
        val = IssueString("1.5").asFloat()
        self.assertEqual(val, 1.5)

    def test_issue_string_no_value_as_int(self):
        val = IssueString("").asInt()
        self.assertIsNone(val)

    def test_issue_int(self):
        val = IssueString("1").asInt()
        self.assertEqual(val, 1)

    def test_issue_float_as_int(self):
        val = IssueString("1.5").asInt()
        self.assertEqual(val, 1)

    def test_issue_string_monsters_unleashed(self):
        val = IssueString("1.MU").asString(3)
        self.assertEqual(val, "001.MU")

    def test_issue_string_minus_one(self):
        val = IssueString("-1").asString(3)
        self.assertEqual(val, "-001")

    def test_issue_string_none_value(self):
        val = IssueString("Test").asString()
        self.assertEqual(val, "Test")


if __name__ == "__main__":
    main()
