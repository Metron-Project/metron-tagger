import pytest
from darkseid.genericmetadata import GenericMetadata

from metrontagger.taggerlib.metrontalker import MetronTalker


@pytest.fixture()
def metron_response():
    return {
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
        "characters": [
            {"id": 86, "name": "Aquaman"},
            {"id": 1499, "name": "Dolphin"},
            {"id": 416, "name": "Garth"},
            {"id": 1500, "name": "Vulko"},
        ],
        "teams": [{"id": 1, "name": "Justice League"}],
    }


def test_map_resp_to_metadata(talker, metron_response):
    meta_data = talker.map_metron_data_to_metadata(metron_response)
    assert meta_data is not None
    assert meta_data.title == metron_response["name"][0]
    assert meta_data.story_arc == metron_response["arcs"][0]["name"]
    assert meta_data.series == metron_response["series"]["name"]
    assert meta_data.volume == metron_response["volume"]
    assert meta_data.publisher == metron_response["publisher"]["name"]
    assert meta_data.issue == metron_response["number"]
    assert meta_data.teams == metron_response["teams"][0]["name"]
    assert meta_data.year == "1994"


def test_map_resp_to_metadata_with_no_story_name(talker, metron_response):
    test_data = metron_response
    test_data["name"] = None
    meta_data = talker.map_metron_data_to_metadata(test_data)
    assert meta_data is not None
    assert meta_data.title is None
    assert meta_data.series == metron_response["series"]["name"]
    assert meta_data.volume == metron_response["volume"]
    assert meta_data.publisher == metron_response["publisher"]["name"]
    assert meta_data.issue == metron_response["number"]
    assert meta_data.year == "1994"


class MockFetchIssueResponse:
    @staticmethod
    def fetch_issue_data_by_issue_id():
        meta_data = GenericMetadata()
        meta_data.series = "Aquaman"
        meta_data.issue = "1"
        meta_data.year = "1993"
        meta_data.day = "15"
        meta_data.add_credit("Peter David", "Writer")
        meta_data.add_credit("Martin Egeland", "Penciller")
        return meta_data

    @staticmethod
    def search_for_issue():
        return {
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


@pytest.fixture()
def mock_fetch(monkeypatch):
    def mock_get_issue(*args, **kwargs):
        return MockFetchIssueResponse().fetch_issue_data_by_issue_id()

    def mock_get_search(*args, **kwargs):
        return MockFetchIssueResponse().search_for_issue()

    monkeypatch.setattr(MetronTalker, "fetch_issue_data_by_issue_id", mock_get_issue)
    monkeypatch.setattr(MetronTalker, "fetch_response", mock_get_search)


def test_fetch_issue_by_id(talker, mock_fetch):
    expected = MockFetchIssueResponse.fetch_issue_data_by_issue_id()
    meta_data = talker.fetch_issue_data_by_issue_id("1")
    assert meta_data is not None
    assert isinstance(meta_data, GenericMetadata)
    assert meta_data.series == expected.series
    assert meta_data.issue == expected.issue
    assert meta_data.year == expected.year
    assert meta_data.day == expected.day
    assert meta_data.credits[0] == expected.credits[0]


def test_search_for_issue(talker, mock_fetch):
    query_dict = {"series": "aquaman", "volume": "1", "number": "10", "year": "1963"}
    response = talker.search_for_issue(query_dict)
    assert response is not None
    assert response == MockFetchIssueResponse().search_for_issue()
