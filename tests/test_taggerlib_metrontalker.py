from base64 import standard_b64encode
from unittest import TestCase, main
from unittest.mock import patch

from metrontagger.comicapi.genericmetadata import GenericMetadata
from metrontagger.taggerlib.metrontalker import MetronTalker


class TestMetronTalker(TestCase):
    def setUp(self):
        auth = f"test_user:test_auth"
        self.base64string = standard_b64encode(auth.encode("utf-8"))
        self.talker = MetronTalker(self.base64string)
        self.resp = {
            "id": 2471,
            "publisher": "DC Comics",
            "series": "Aquaman",
            "volume": "2",
            "number": "1",
            "name": [],
            "cover_date": "1986-02-01",
            "store_date": None,
            "desc": "Aquaman settles back in New Venice until it is suddenly and totally destroyed by Ocean Master. The tragedy catapults Aquaman back to Atlantis, where he discovers that ancient talismans dating back to Arion's time are missing!",
            "image": "https://metron.cloud/media/issue/2019/05/19/aquaman-v2-1.jpg",
            "arcs": [],
            "credits": [
                {
                    "id": 1566,
                    "creator": "Bob Lappan",
                    "role": [{"id": 6, "name": "Letterer"}],
                },
                {
                    "id": 1614,
                    "creator": "Craig Hamilton",
                    "role": [{"id": 2, "name": "Artist"}, {"id": 7, "name": "Cover"}],
                },
                {
                    "id": 399,
                    "creator": "Dick Giordano",
                    "role": [{"id": 8, "name": "Editor"}],
                },
                {
                    "id": 1977,
                    "creator": "Joe Orlando",
                    "role": [{"id": 5, "name": "Colorist"}],
                },
                {
                    "id": 1975,
                    "creator": "Neal Pozner",
                    "role": [{"id": 30, "name": "Story"}, {"id": 8, "name": "Editor"}],
                },
                {
                    "id": 1976,
                    "creator": "Steve Montano",
                    "role": [{"id": 4, "name": "Inker"}],
                },
            ],
            "characters": [
                {"id": 86, "name": "Aquaman"},
                {"id": 530, "name": "Mera"},
                {"id": 1773, "name": "Nuada Silver-Hand"},
                {"id": 1520, "name": "Ocean Master"},
                {"id": 1500, "name": "Vulko"},
            ],
            "teams": [],
        }

    def test_map_resp_to_metadata(self):
        md = self.talker.mapMetronDataToMetadata(self.resp)
        self.assertIsNotNone(md)
        self.assertEqual(md.series, "Aquaman")
        self.assertEqual(md.volume, "2")
        self.assertEqual(md.publisher, "DC Comics")
        self.assertEqual(md.issue, "1")
        self.assertEqual(md.year, "1986")

    @patch("metrontagger.taggerlib.metrontalker.MetronTalker.fetchResponse")
    def test_fetch_issue_by_id(self, MockFetch):
        MockFetch.return_value.fetchResponse.return_value = self.resp
        talker = MetronTalker(self.base64string)
        md = talker.fetchIssueDataByIssueId(1)
        self.assertIsNotNone(md)
        self.assertIsInstance(md, GenericMetadata)


if __name__ == "__main__":
    main()
