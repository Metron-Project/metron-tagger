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


def test_map_resp_to_metadata_with_no_story_name(talker, metron_response):
    test_data = metron_response
    test_data.name = None
    meta_data = talker._map_resp_to_metadata(test_data)
    assert meta_data is not None
    assert meta_data.title is None
    assert meta_data.series == metron_response.series.name
    assert meta_data.volume == metron_response.volume
    assert meta_data.publisher == metron_response.publisher.name
    assert meta_data.issue == metron_response.number
    assert meta_data.year == metron_response.cover_date.year
