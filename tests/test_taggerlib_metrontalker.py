import pytest
from darkseid.utils import list_to_string
from mokkari.issue import IssueSchema


@pytest.fixture()
def metron_response():
    i = {
        "id": 31047,
        "publisher": {"id": 1, "name": "Marvel"},
        "series": {"id": 2222, "name": "The Spectacular Spider-Man"},
        "volume": 1,
        "number": "47",
        "name": ["A Night on the Prowl!"],
        "cover_date": "1980-10-01",
        "store_date": None,
        "desc": "Spider-Man goes on a wild goose chase to find out who is behind the Prowler impersonation.",
        "image": "https://static.metron.cloud/media/issue/2021/05/22/the-spectacular-spider-man-47.jpg",
        "arcs": [],
        "credits": [
            {"id": 233, "creator": "Al Milgrom", "role": [{"id": 7, "name": "Cover"}]},
        ],
        "characters": [
            {"id": 6784, "name": "Debra Whitman"},
            {"id": 3067, "name": "Hobgoblin (Kingsley)"},
        ],
        "teams": [],
    }
    return IssueSchema().load(i)


def test_map_resp_to_metadata(talker, metron_response):
    md = talker._map_resp_to_metadata(metron_response)
    assert md is not None
    assert md.title == list_to_string([title for title in metron_response.name])
    assert md.series == metron_response.series.name
    assert md.volume == metron_response.volume
    assert md.publisher == metron_response.publisher.name
    assert md.issue == metron_response.number
    assert md.teams is None
    assert md.year == metron_response.cover_date.year
    assert md.characters == list_to_string([c.name for c in metron_response.characters])
    assert md.credits is not None


# def test_map_resp_to_metadata_with_no_story_name(talker, metron_response):
#     test_data = metron_response
#     test_data["name"] = None
#     meta_data = talker.map_metron_data_to_metadata(test_data)
#     assert meta_data is not None
#     assert meta_data.title is None
#     assert meta_data.series == metron_response["series"]["name"]
#     assert meta_data.volume == metron_response["volume"]
#     assert meta_data.publisher == metron_response["publisher"]["name"]
#     assert meta_data.issue == metron_response["number"]
#     assert meta_data.year == "1994"


# class MockFetchIssueResponse:
#     @staticmethod
#     def fetch_issue_data_by_issue_id():
#         meta_data = GenericMetadata()
#         meta_data.series = "Aquaman"
#         meta_data.issue = "1"
#         meta_data.year = "1993"
#         meta_data.day = "15"
#         meta_data.add_credit("Peter David", "Writer")
#         meta_data.add_credit("Martin Egeland", "Penciller")
#         return meta_data

#     @staticmethod
#     def search_for_issue():
#         return {
#             "count": 7,
#             "next": None,
#             "previous": None,
#             "results": [
#                 {"id": 3643, "__str__": ISSUE, "cover_date": "1963-08-01"},
#                 {"id": 2519, "__str__": ISSUE, "cover_date": "1992-09-01"},
#                 {"id": 1786, "__str__": ISSUE, "cover_date": "1995-07-01"},
#                 {"id": 2439, "__str__": ISSUE, "cover_date": "2003-11-01"},
#                 {"id": 2534, "__str__": ISSUE, "cover_date": "2012-08-01"},
#                 {"id": 2908, "__str__": ISSUE, "cover_date": "2017-01-01"},
#                 {
#                     "id": 3631,
#                     "__str__": "Aquaman and the Others #10",
#                     "cover_date": "2014-04-01",
#                 },
#             ],
#         }


# @pytest.fixture()
# def mock_fetch(monkeypatch):
#     def mock_get_issue(*args, **kwargs):
#         return MockFetchIssueResponse().fetch_issue_data_by_issue_id()

#     def mock_get_search(*args, **kwargs):
#         return MockFetchIssueResponse().search_for_issue()

#     monkeypatch.setattr(MetronTalker, "fetch_issue_data_by_issue_id", mock_get_issue)
#     monkeypatch.setattr(MetronTalker, "fetch_response", mock_get_search)


# def test_fetch_issue_by_id(talker, mock_fetch):
#     expected = MockFetchIssueResponse.fetch_issue_data_by_issue_id()
#     meta_data = talker.fetch_issue_data_by_issue_id("1")
#     assert meta_data is not None
#     assert isinstance(meta_data, GenericMetadata)
#     assert meta_data.series == expected.series
#     assert meta_data.issue == expected.issue
#     assert meta_data.year == expected.year
#     assert meta_data.day == expected.day
#     assert meta_data.credits[0] == expected.credits[0]


# def test_search_for_issue(talker, mock_fetch):
#     query_dict = {"series": "aquaman", "volume": "1", "number": "10", "year": "1963"}
#     response = talker.search_for_issue(query_dict)
#     assert response is not None
#     assert response == MockFetchIssueResponse().search_for_issue()


# def test_fetch_response_with_no_host(talker):
#     with pytest.raises(Exception):
#         fake_url = "https://"
#         assert talker.fetch_response(fake_url)
