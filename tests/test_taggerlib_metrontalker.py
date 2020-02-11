import pytest
from darkseid.genericmetadata import GenericMetadata

from metrontagger.taggerlib.metrontalker import MetronTalker

resp = {
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
        {"id": 1576, "creator": "Brad Vancata", "role": [{"id": 4, "name": "Inker"}]},
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
        {"id": 1579, "creator": "Howard Shum", "role": [{"id": 4, "name": "Inker"}]},
        {"id": 1560, "creator": "Kevin Dooley", "role": [{"id": 8, "name": "Editor"}]},
        {
            "id": 1577,
            "creator": "Martin Egeland",
            "role": [{"id": 3, "name": "Penciller"}, {"id": 7, "name": "Cover"}],
        },
        {"id": 166, "creator": "Peter David", "role": [{"id": 1, "name": "Writer"}]},
        {"id": 1268, "creator": "Tom McCraw", "role": [{"id": 5, "name": "Colorist"}]},
    ],
    "characters": [
        {"id": 86, "name": "Aquaman"},
        {"id": 1499, "name": "Dolphin"},
        {"id": 416, "name": "Garth"},
        {"id": 1500, "name": "Vulko"},
    ],
    "teams": [],
}


def test_map_resp_to_metadata(talker):
    meta_data = talker.map_metron_data_to_metadata(resp)
    assert meta_data is not None
    assert meta_data.title == resp["name"][0]
    assert meta_data.story_arc == resp["arcs"][0]["name"]
    assert meta_data.series == resp["series"]["name"]
    assert meta_data.volume == resp["volume"]
    assert meta_data.publisher == resp["publisher"]["name"]
    assert meta_data.issue == resp["number"]
    assert meta_data.year == "1994"


def test_map_resp_to_metadata_with_no_story_name(talker):
    test_data = resp
    test_data["name"] = None
    meta_data = talker.map_metron_data_to_metadata(test_data)
    assert meta_data is not None
    assert meta_data.title is None
    assert meta_data.series == resp["series"]["name"]
    assert meta_data.volume == resp["volume"]
    assert meta_data.publisher == resp["publisher"]["name"]
    assert meta_data.issue == resp["number"]
    assert meta_data.year == "1994"


class MockFetchIssueResponse:
    @staticmethod
    def fetch_issue_data_by_issue_id():
        meta_data = GenericMetadata()
        meta_data.series = "Aquaman"
        meta_data.issue = "1"
        meta_data.year = "1993"
        meta_data.day = "15"
        meta_data.add_credit("Peter David", "Writer", primary=True)
        meta_data.add_credit("Martin Egeland", "Penciller")
        meta_data.add_credit("Martin Egeland", "Cover")
        meta_data.add_credit("Kevin Dooley", "Editor")
        meta_data.add_credit("Howard Shum", "Inker")
        meta_data.add_credit("Tom McCraw", "Colorist")
        meta_data.add_credit("Dan Nakrosis", "Letterer")
        return meta_data


@pytest.fixture()
def mock_fetch_issue_by_id_response(monkeypatch):
    def mock_get(*args, **kwargs):
        return MockFetchIssueResponse().fetch_issue_data_by_issue_id()

    monkeypatch.setattr(MetronTalker, "fetch_issue_data_by_issue_id", mock_get)


def test_fetch_issue_by_id(talker, mock_fetch_issue_by_id_response):
    meta_data = talker.fetch_issue_data_by_issue_id("1")
    assert meta_data is not None
    assert isinstance(meta_data, GenericMetadata)
    assert meta_data.series == "Aquaman"
    assert meta_data.issue == "1"
    assert meta_data.year == "1993"
    assert meta_data.day == "15"


# @patch("metrontagger.taggerlib.metrontalker.MetronTalker.fetch_response")
# def test_search_for_issue(, mock_fetch):
#     query_dict = {"series": "aquaman", "volume": "", "number": "10", "year": ""}
#     res = {
#         "count": 7,
#         "next": None,
#         "previous": None,
#         "results": [
#             {"id": 3643, "__str__": "Aquaman #10", "cover_date": "1963-08-01"},
#             {"id": 2519, "__str__": "Aquaman #10", "cover_date": "1992-09-01"},
#             {"id": 1786, "__str__": "Aquaman #10", "cover_date": "1995-07-01"},
#             {"id": 2439, "__str__": "Aquaman #10", "cover_date": "2003-11-01"},
#             {"id": 2534, "__str__": "Aquaman #10", "cover_date": "2012-08-01"},
#             {"id": 2908, "__str__": "Aquaman #10", "cover_date": "2017-01-01"},
#             {
#                 "id": 3631,
#                 "__str__": "Aquaman and the Others #10",
#                 "cover_date": "2014-04-01",
#             },
#         ],
#     }
#     mock_fetch.return_value = res
#     talker = MetronTalker(.base64string)
#     response = talker.search_for_issue(query_dict)
#     .assertIsNotNone(response)
#     .assertEqual(response, res)
