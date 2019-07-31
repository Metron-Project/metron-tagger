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
            "id": 1778,
            "publisher": {"id": 2, "name": "DC Comics"},
            "series": {"id": 204, "name": "Aquaman"},
            "volume": 4,
            "number": "0",
            "name": ["A Crash of Symbols"],
            "cover_date": "1994-10-01",
            "store_date": None,
            "desc": "A ZERO HOUR tie-in! Aquaman battles against his father and the outcome leads to his discovery of a hidden heritage. When the water subsides, the Sea King's relationship with the surface world and his life as a hero will be forever affected!",
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
                {
                    "id": 739,
                    "creator": "Eddie Berganza",
                    "role": [{"id": 12, "name": "Assistant Editor"}],
                },
                {
                    "id": 1579,
                    "creator": "Howard Shum",
                    "role": [{"id": 4, "name": "Inker"}],
                },
                {
                    "id": 1560,
                    "creator": "Kevin Dooley",
                    "role": [{"id": 8, "name": "Editor"}],
                },
                {
                    "id": 1577,
                    "creator": "Martin Egeland",
                    "role": [
                        {"id": 3, "name": "Penciller"},
                        {"id": 7, "name": "Cover"},
                    ],
                },
                {
                    "id": 166,
                    "creator": "Peter David",
                    "role": [{"id": 1, "name": "Writer"}],
                },
                {
                    "id": 1268,
                    "creator": "Tom McCraw",
                    "role": [{"id": 5, "name": "Colorist"}],
                },
            ],
            "characters": [
                {"id": 86, "name": "Aquaman"},
                {"id": 1499, "name": "Dolphin"},
                {"id": 416, "name": "Garth"},
                {"id": 1500, "name": "Vulko"},
            ],
            "teams": [],
        }

    def test_map_resp_to_metadata(self):
        md = self.talker.mapMetronDataToMetadata(self.resp)
        self.assertIsNotNone(md)
        self.assertEqual(md.series, self.resp["series"]["name"])
        self.assertEqual(md.volume, self.resp["volume"])
        self.assertEqual(md.publisher, self.resp["publisher"]["name"])
        self.assertEqual(md.issue, self.resp["number"])
        self.assertEqual(md.year, "1994")

    @patch("metrontagger.taggerlib.metrontalker.MetronTalker.fetchResponse")
    def test_fetch_issue_by_id(self, MockFetch):
        MockFetch.return_value = self.resp
        talker = MetronTalker(self.base64string)
        md = talker.fetchIssueDataByIssueId("1")
        self.assertIsNotNone(md)
        self.assertIsInstance(md, GenericMetadata)
        self.assertEqual(md.series, self.resp["series"]["name"])
        self.assertEqual(md.issue, self.resp["number"])

    @patch("metrontagger.taggerlib.metrontalker.MetronTalker.fetchResponse")
    def test_search_for_issue(self, MockFetch):
        query_dict = {"series": "aquaman", "volume": "", "number": "10", "year": ""}
        res = {
            "count": 7,
            "next": None,
            "previous": None,
            "results": [
                {"id": 3643, "__str__": "Aquaman #10", "cover_date": "1963-08-01"},
                {"id": 2519, "__str__": "Aquaman #10", "cover_date": "1992-09-01"},
                {"id": 1786, "__str__": "Aquaman #10", "cover_date": "1995-07-01"},
                {"id": 2439, "__str__": "Aquaman #10", "cover_date": "2003-11-01"},
                {"id": 2534, "__str__": "Aquaman #10", "cover_date": "2012-08-01"},
                {"id": 2908, "__str__": "Aquaman #10", "cover_date": "2017-01-01"},
                {
                    "id": 3631,
                    "__str__": "Aquaman and the Others #10",
                    "cover_date": "2014-04-01",
                },
            ],
        }
        MockFetch.return_value = res
        talker = MetronTalker(self.base64string)
        response = talker.searchForIssue(query_dict)
        self.assertIsNotNone(response)
        self.assertEqual(response, res)


if __name__ == "__main__":
    main()
