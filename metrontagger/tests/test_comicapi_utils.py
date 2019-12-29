import os
import tempfile
import unittest

from metrontagger.comicapi import utils


class TestUtils(unittest.TestCase):
    def test_remove_articles(self):
        txt = "The Champions & Inhumans"
        new_txt = utils.removearticles(txt)
        self.assertEqual(new_txt, "champions inhumans")

    def test_list_to_string(self):
        thislist = ["apple", "banana", "cherry"]
        expected_result = "apple; banana; cherry"

        list_string = utils.listToString(thislist)
        self.assertEqual(list_string, expected_result)

    def test_unique_name(self):
        tmp_file = tempfile.NamedTemporaryFile(suffix=".cbz")
        new_file = tmp_file.name
        new_name = utils.unique_file(new_file)
        # Now let's create our expected result
        result_split = os.path.splitext(tmp_file.name)
        correct_result = result_split[0] + " (1)" + result_split[1]
        # Don't forget to close the tmpfile
        tmp_file.close()
        self.assertEqual(new_name, correct_result)


if __name__ == "__main__":
    unittest.main()
