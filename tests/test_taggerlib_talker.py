import pytest
from darkseid.comicarchive import ComicArchive
from darkseid.utils import list_to_string
from mokkari.issue import IssueSchema
from mokkari.sesssion import Session


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
        "arcs": [{"id": 1, "name": "Foo Bar"}],
        "credits": [
            {"id": 233, "creator": "Al Milgrom", "role": [{"id": 7, "name": "Cover"}]},
        ],
        "characters": [
            {"id": 6784, "name": "Debra Whitman"},
            {"id": 3067, "name": "Hobgoblin (Kingsley)"},
        ],
        "teams": [{"id": 1, "name": "Bar Foo"}],
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
    assert md.story_arc == list_to_string(a.name for a in metron_response.arcs)
    assert md.teams == list_to_string(t.name for t in metron_response.teams)
    assert md.year == metron_response.cover_date.year
    assert md.characters == list_to_string([c.name for c in metron_response.characters])
    assert md.credits is not None
    assert md.credits[0]["person"] == "Al Milgrom"
    assert md.credits[0]["role"] == "Cover"


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


def test_write_issue_md(talker, fake_comic, metron_response, mocker):
    # Remove any existing metadata from comic fixture
    ComicArchive(fake_comic).remove_metadata()
    assert not ComicArchive(fake_comic).has_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=metron_response)
    talker.retrieve_single_issue(fake_comic, 5)

    # Now let's test writing the metadata to file
    talker._write_issue_md(fake_comic, 1)
    ca = ComicArchive(fake_comic)
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.title == list_to_string([title for title in metron_response.name])
    assert ca_md.series == metron_response.series.name
    assert ca_md.volume == str(metron_response.volume)
    assert ca_md.publisher == metron_response.publisher.name
    assert ca_md.issue == metron_response.number
    assert ca_md.story_arc == list_to_string(a.name for a in metron_response.arcs)
    assert ca_md.teams == list_to_string(t.name for t in metron_response.teams)
    assert ca_md.year == str(metron_response.cover_date.year)
    assert ca_md.characters == list_to_string(
        [c.name for c in metron_response.characters]
    )
    assert ca_md.credits is not None
    assert ca_md.credits[0]["person"] == "Al Milgrom"
    assert ca_md.credits[0]["role"] == "Cover"


def test_retrieve_single_issue(talker, fake_comic, metron_response, mocker):
    # Remove any existing metadata from comic fixture
    ComicArchive(fake_comic).remove_metadata()
    assert not ComicArchive(fake_comic).has_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=metron_response)
    talker.retrieve_single_issue(fake_comic, 10)

    # Now let's test the metadata
    ca = ComicArchive(fake_comic)
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.title == list_to_string([title for title in metron_response.name])
    assert ca_md.series == metron_response.series.name
    assert ca_md.volume == str(metron_response.volume)
    assert ca_md.publisher == metron_response.publisher.name
    assert ca_md.issue == metron_response.number
    assert ca_md.story_arc == list_to_string(a.name for a in metron_response.arcs)
    assert ca_md.teams == list_to_string(t.name for t in metron_response.teams)
    assert ca_md.year == str(metron_response.cover_date.year)
    assert ca_md.characters == list_to_string(
        [c.name for c in metron_response.characters]
    )
    assert ca_md.credits is not None
    assert ca_md.credits[0]["person"] == "Al Milgrom"
    assert ca_md.credits[0]["role"] == "Cover"