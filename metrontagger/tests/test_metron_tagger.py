"""Main metron_tagger tests"""
from unittest import TestCase, main

from metrontagger.metron_tagger import create_metron_talker
from metrontagger.taggerlib.metrontalker import MetronTalker


class TestMetronTagger(TestCase):
    """Tests"""

    def test_create_metron_talker(self):
        """ Check for MetronTalker is created """
        talker = create_metron_talker()
        self.assertIsInstance(talker, MetronTalker)

    def test_get_issue_metadata(self):
        """ Test to get issues metadata """


if __name__ == "__main__":
    main()
