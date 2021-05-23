import pytest
from darkseid.utils import list_to_string
from mokkari.issue import IssueSchema


@pytest.fixture()
def metron_response():
    i = {
        "id": 1,
        "publisher": {"id": 1, "name": "Marvel"},
        "series": {"id": 1, "name": "Death of the Inhumans"},
        "volume": 1,
        "number": "1",
        "name": ["Chapter One: Vox"],
        "cover_date": "2018-09-01",
        "store_date": "2018-07-04",
        "desc": "THE TITLE SAYS IT ALL - HERE LIE THE INHUMANS.\r\n\r\nThe Kree have gone murdering, leaving behind a message: Join or die. Thousands of Inhumans have already made their choice - the evidence floats bleeding in space. Black Bolt and his family are next. Rising star Donny Cates and PUNISHER: WAR JOURNAL artist Ariel Olivetti bring their brutal talents to the Inhumans!",
        "image": "https://static.metron.cloud/media/issue/2018/11/11/6497376-01.jpg",
        "arcs": [],
        "credits": [
            {
                "id": 6,
                "creator": "Ariel Olivetti",
                "role": [{"id": 2, "name": "Artist"}, {"id": 7, "name": "Cover"}],
            },
            {
                "id": 5,
                "creator": "Clayton Cowles",
                "role": [{"id": 6, "name": "Letterer"}],
            },
            {"id": 1, "creator": "Donny Cates", "role": [{"id": 1, "name": "Writer"}]},
            {
                "id": 9,
                "creator": "Greg Hildebrandt",
                "role": [{"id": 7, "name": "Cover"}],
            },
            {
                "id": 11,
                "creator": "Javier Garrón",
                "role": [{"id": 7, "name": "Cover"}],
            },
            {"id": 7, "creator": "Kaare Andrews", "role": [{"id": 7, "name": "Cover"}]},
            {
                "id": 10,
                "creator": "Matthew Wilson",
                "role": [{"id": 7, "name": "Cover"}],
            },
            {
                "id": 2,
                "creator": "Russell Dauterman",
                "role": [{"id": 7, "name": "Cover"}],
            },
            {"id": 8, "creator": "Wil Moss", "role": [{"id": 8, "name": "Editor"}]},
        ],
        "characters": [
            {"id": 1, "name": "Black Bolt"},
            {"id": 5, "name": "Crystal"},
            {"id": 3, "name": "Gorgon"},
            {"id": 4, "name": "Karnak"},
            {"id": 8, "name": "Lockjaw"},
            {"id": 6, "name": "Maximus"},
            {"id": 2, "name": "Medusa"},
            {"id": 7, "name": "Triton"},
            {"id": 9, "name": "Vox"},
        ],
        "teams": [{"id": 1, "name": "Inhumans"}],
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
    assert md.teams == list_to_string([t.name for t in metron_response.teams])
    assert md.year == metron_response.cover_date.year
    assert md.characters == list_to_string([c.name for c in metron_response.characters])


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
