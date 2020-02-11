"""Main metron_tagger tests"""
import tempfile
from base64 import standard_b64encode
from pathlib import Path
from shutil import make_archive
from unittest import TestCase, main
from unittest.mock import patch

from darkseid.comicarchive import ComicArchive

from metrontagger.main import get_issue_metadata
from metrontagger.taggerlib.metrontalker import MetronTalker


def test_create_metron_talker(talker):
    assert isinstance(talker, MetronTalker)


class TestMetronTagger(TestCase):
    """Tests"""

    def setUp(self):
        # Create a zipfile
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
        self.zipfile = Path(self.tmp_archive_dir.name) / "comic"
        open(make_archive(self.zipfile, "zip", self.tmp_image_dir.name), "rb").read()

        # response for MetronTalker
        auth = f"test_user:test_auth"
        self.base64string = standard_b64encode(auth.encode("utf-8"))
        self.talker = MetronTalker(self.base64string)
        self.resp = {
            "id": 1778,
            "publisher": {"id": 2, "name": "DC Comics"},
            "series": {"id": 204, "name": "Aquaman"},
            "volume": 4,
            "number": "0",
            "name": ["A Crash of Symbols"],
            "cover_date": "1994-10-01",
            "store_date": None,
            "desc": "A ZERO HOUR tie-in!",
            "image": "http://127.0.0.1:8000/media/issue/2019/04/01/aquaman-0.jpg",
            "arcs": [{"id": 69, "name": "Zero Hour"}],
            "credits": [
                {
                    "id": 1576,
                    "creator": "Brad Vancata",
                    "role": [{"id": 4, "name": "Inker"}],
                },
                {
                    "id": 1575,
                    "creator": "Dan Nakrosis",
                    "role": [{"id": 6, "name": "Letterer"}],
                },
            ],
            "characters": [{"id": 86, "name": "Aquaman"}],
            "teams": [],
        }

    def tearDown(self):
        self.tmp_archive_dir.cleanup()
        self.tmp_image_dir.cleanup()

    @patch("metrontagger.taggerlib.metrontalker.MetronTalker.fetch_response")
    def test_get_issue_metadata(self, mock_fetch):
        """ Test to get issues metadata """
        # Mock the fetch response
        mock_fetch.return_value = self.resp
        talker = MetronTalker(self.base64string)
        res = get_issue_metadata(self.zipfile.with_suffix(".zip"), 1, talker)

        # Check to see the zipfile had metadata written
        comic_archive = ComicArchive(self.zipfile.with_suffix(".zip"))
        file_md = comic_archive.read_metadata()

        self.assertTrue(res)
        self.assertIsNotNone(file_md)
        self.assertEqual(file_md.series, "Aquaman")


if __name__ == "__main__":
    main()
