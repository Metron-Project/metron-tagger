import sys
from typing import List
from zipfile import ZipFile

import pytest
from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GeneralResource
from mokkari.issue import IssueSchema, IssuesList
from mokkari.session import Session

from metrontagger.talker import Talker


@pytest.fixture()
def metron_response():
    i = {
        "id": 31047,
        "publisher": {"id": 1, "name": "Marvel"},
        "series": {
            "id": 2222,
            "name": "The Spectacular Spider-Man",
            "sort_name": "Spectacular Spider-Man",
            "volume": 1,
            "series_type": {"id": 2, "name": "Cancelled Series"},
            "genres": [{"id": 1, "name": "Super-Hero"}],
        },
        "number": "47",
        "title": "",
        "name": ["A Night on the Prowl!"],
        "cover_date": "1980-10-01",
        "store_date": None,
        "price": "0.50",
        "sku": "",
        "isbn": "",
        "upc": "",
        "page": 36,
        "desc": "Spider-Man goes on a wild goose chase to find out who is behind the Prowler impersonation.",
        "image": "https://static.metron.cloud/media/issue/2021/05/22/the-spectacular-spider-man-47.jpg",
        "arcs": [],
        "credits": [
            {"id": 233, "creator": "Al Milgrom", "role": [{"id": 7, "name": "Cover"}]},
            {
                "id": 1402,
                "creator": "Bruce Patterson",
                "role": [{"id": 4, "name": "Inker"}, {"id": 6, "name": "Letterer"}],
            },
            {"id": 128, "creator": "Dennis O'Neil", "role": [{"id": 8, "name": "Editor"}]},
            {"id": 1035, "creator": "Glynis Oliver", "role": [{"id": 5, "name": "Colorist"}]},
            {
                "id": 624,
                "creator": "Jim Shooter",
                "role": [{"id": 20, "name": "Editor In Chief"}],
            },
            {"id": 675, "creator": "Marie Severin", "role": [{"id": 3, "name": "Penciller"}]},
            {"id": 273, "creator": "Roger Stern", "role": [{"id": 1, "name": "Writer"}]},
        ],
        "characters": [
            {
                "id": 6784,
                "name": "Debra Whitman",
                "modified": "2021-05-22T22:47:25.294935-04:00",
            },
            {
                "id": 3067,
                "name": "Hobgoblin (Kingsley)",
                "modified": "2019-12-11T17:21:51.365470-05:00",
            },
            {"id": 2415, "name": "Prowler", "modified": "2019-08-24T16:37:06.997976-04:00"},
            {"id": 145, "name": "Spider-Man", "modified": "2022-05-16T09:22:42.644589-04:00"},
        ],
        "teams": [{"id": 1, "name": "Bar Foo"}],
        "reprints": [],
        "variants": [],
        "modified": "2022-05-29T08:22:38.584485-04:00",
    }
    return IssueSchema().load(i)


def create_resource_list(resource) -> List[GeneralResource]:
    return [GeneralResource(r.name, r.id) for r in resource]


def create_read_md_resource_list(resource) -> List[GeneralResource]:
    return [GeneralResource(r.name) for r in resource]


def create_read_md_story(resource) -> List[GeneralResource]:
    return [GeneralResource(story) for story in resource]


def test_map_resp_to_metadata(talker: Talker, metron_response) -> None:
    md = talker._map_resp_to_metadata(metron_response)
    assert md is not None
    assert md.stories == create_read_md_story(metron_response.story_titles)
    assert md.series.name == metron_response.series.name
    assert md.series.volume == metron_response.series.volume
    assert md.publisher.name == metron_response.publisher.name
    assert md.issue == metron_response.number
    assert md.story_arcs == create_resource_list(metron_response.arcs)
    assert md.teams == create_resource_list(metron_response.teams)
    assert md.cover_date.year == metron_response.cover_date.year
    assert md.characters == create_resource_list(metron_response.characters)
    assert md.credits is not None
    assert md.credits[0].person == "Al Milgrom"
    assert md.credits[0].role[0].name == "Cover"


def test_map_resp_to_metadata_with_no_story_name(talker: Talker, metron_response) -> None:
    test_data = metron_response
    test_data.story_titles = None
    meta_data = talker._map_resp_to_metadata(test_data)
    assert meta_data is not None
    assert len(meta_data.stories) == 0
    assert meta_data.series.name == metron_response.series.name
    assert meta_data.series.volume == metron_response.series.volume
    assert meta_data.publisher.name == metron_response.publisher.name
    assert meta_data.issue == metron_response.number
    assert meta_data.cover_date.year == metron_response.cover_date.year


@pytest.fixture()
def issue_list_response() -> IssuesList:
    i = {
        "count": 8,
        "next": None,
        "previous": None,
        "results": [
            {"id": 3634, "__str__": "Aquaman #1", "cover_date": "1962-02-01"},
            {"id": 2471, "__str__": "Aquaman #1", "cover_date": "1986-02-01"},
            {"id": 2541, "__str__": "Aquaman #1", "cover_date": "1989-06-01"},
            {"id": 2510, "__str__": "Aquaman #1", "cover_date": "1991-12-01"},
            {"id": 1776, "__str__": "Aquaman #1", "cover_date": "1994-08-01"},
            {"id": 2429, "__str__": "Aquaman #1", "cover_date": "2003-02-01"},
            {"id": 2523, "__str__": "Aquaman #1", "cover_date": "2011-11-01"},
            {"id": 2896, "__str__": "Aquaman #1", "cover_date": "2016-08-01"},
        ],
    }
    return IssuesList(i)


def test_process_file(
    talker: Talker, fake_comic: ZipFile, issue_list_response: IssuesList, mocker
) -> None:
    # Remove any existing metadata from comic fixture
    ca = ComicArchive(fake_comic)
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issues_list", return_value=issue_list_response)
    talker._process_file(fake_comic, False)

    id, multiple = talker._process_file(fake_comic, False)
    assert id is None
    assert multiple
    assert fake_comic in [c.filename for c in talker.match_results.multiple_matches]

    id_list = []
    for c in talker.match_results.multiple_matches:
        id_list.extend(i.id for i in c.matches)
    assert 2471 in id_list


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_write_issue_md(talker: Talker, fake_comic: ZipFile, metron_response, mocker) -> None:
    # Remove any existing metadata from comic fixture
    ca = ComicArchive(fake_comic)
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=metron_response)
    talker.retrieve_single_issue(fake_comic, 5)

    # Now let's test writing the metadata to file
    talker._write_issue_md(fake_comic, 1)
    ca = ComicArchive(fake_comic)
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.stories == create_read_md_story(metron_response.story_titles)
    assert ca_md.series.name == metron_response.series.name
    assert ca_md.series.volume == metron_response.series.volume
    assert ca_md.publisher.name == metron_response.publisher.name
    assert ca_md.issue == metron_response.number
    assert ca_md.teams == create_read_md_resource_list(metron_response.teams)
    assert ca_md.cover_date.year == metron_response.cover_date.year
    assert ca_md.characters == create_read_md_resource_list(metron_response.characters)
    assert ca_md.credits is not None
    assert ca_md.credits[0].person == "Roger Stern"
    assert ca_md.credits[0].role[0].name == "Writer"


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_retrieve_single_issue(
    talker: Talker, fake_comic: ZipFile, metron_response, mocker
) -> None:
    # Remove any existing metadata from comic fixture
    ca = ComicArchive(fake_comic)
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=metron_response)
    talker.retrieve_single_issue(fake_comic, 10)

    # Now let's test the metadata
    ca = ComicArchive(fake_comic)
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.stories == create_read_md_story(metron_response.story_titles)
    assert ca_md.series.name == metron_response.series.name
    assert ca_md.series.volume == metron_response.series.volume
    assert ca_md.publisher.name == metron_response.publisher.name
    assert ca_md.issue == metron_response.number
    assert ca_md.teams == create_read_md_resource_list(metron_response.teams)
    assert ca_md.cover_date.year == metron_response.cover_date.year
    assert ca_md.characters == create_read_md_resource_list(metron_response.characters)
    assert ca_md.credits is not None
    assert ca_md.credits[0].person == "Roger Stern"
    assert ca_md.credits[0].role[0].name == "Writer"
