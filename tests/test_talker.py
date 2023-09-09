import sys
from typing import Union
from zipfile import ZipFile

import pytest
from darkseid.comic import Comic
from darkseid.metadata import Basic
from mokkari.issue import IssueSchema, IssuesList
from mokkari.session import Session

from metrontagger.talker import Talker


@pytest.fixture()
def metron_response() -> dict[str, any]:
    i = {
        "id": 31047,
        "publisher": {"id": 1, "name": "Marvel"},
        "series": {
            "id": 2222,
            "name": "The Spectacular Spider-Man",
            "sort_name": "Spectacular Spider-Man",
            "volume": 1,
            "series_type": {"id": 2, "name": "Cancelled Series"},
            "genres": [],
        },
        "number": "47",
        "title": "",
        "name": ["A Night on the Prowl!"],
        "cover_date": "1980-10-01",
        "store_date": None,
        "price": "0.50",
        "rating": {"id": 6, "name": "CCA"},
        "sku": "",
        "isbn": "",
        "upc": "",
        "page": 36,
        "desc": "Spider-Man goes on a wild goose chase to find out who is behind the Prowler impersonation.",  # noqa: E501
        "image": "https://static.metron.cloud/media/issue/2021/05/22/the-spectacular-spider-man-47.jpg",
        "cover_hash": "c0f83fe438876c1b",
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
            {"id": 2415, "name": "Prowler", "modified": "2023-03-04T10:29:02.743798-05:00"},
            {"id": 145, "name": "Spider-Man", "modified": "2023-08-31T08:53:14.183600-04:00"},
        ],
        "teams": [],
        "reprints": [],
        "variants": [],
        "cv_id": 20745,
        "resource_url": "https://metron.cloud/issue/the-spectacular-spider-man-1976-47/",
        "modified": "2023-05-21T16:09:03.709255-04:00",
    }
    return IssueSchema().load(i)


def create_reprint_list(resource: dict[str, Union[int, str]]) -> list[Basic]:
    return [Basic(r.issue, r.id) for r in resource]


def create_resource_list(resource: dict[str, Union[int, str]]) -> list[Basic]:
    return [Basic(r.name, r.id) for r in resource]


def create_read_md_resource_list(resource: dict[str, Union[int, str]]) -> list[Basic]:
    return [Basic(r.name) for r in resource]


def create_read_md_story(resource: dict[str, Union[int, str]]) -> list[Basic]:
    return [Basic(story) for story in resource]


def test_map_resp_to_metadata(talker: Talker, metron_response: dict[str, any]) -> None:
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
    assert md.reprints == create_reprint_list(metron_response.reprints)
    assert md.age_rating == "Everyone"
    assert md.web_link == metron_response.resource_url


def test_map_resp_to_metadata_with_no_story_name(
    talker: Talker,
    metron_response: dict[str, any],
) -> None:
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
            {
                "id": 3634,
                "series": {"name": "Aquaman", "volume": 1, "year_began": 1962},
                "number": "1",
                "issue": "Aquaman (1962) #1",
                "cover_date": "1962-02-01",
                "image": "https://static.metron.cloud/media/issue/2019/07/12/aquaman-v1-1.jpg",
                "cover_hash": "ccb2097c5b273c1b",
                "modified": "2023-05-27T07:33:05.220213-04:00",
            },
            {
                "id": 2471,
                "series": {"name": "Aquaman", "volume": 2, "year_began": 1986},
                "number": "1",
                "issue": "Aquaman (1986) #1",
                "cover_date": "1986-02-01",
                "image": "https://static.metron.cloud/media/issue/2019/05/19/aquaman-v2-1.jpg",
                "cover_hash": "ea97c11cb3660c79",
                "modified": "2023-05-30T11:16:46.832919-04:00",
            },
            {
                "id": 2541,
                "series": {"name": "Aquaman", "volume": 3, "year_began": 1989},
                "number": "1",
                "issue": "Aquaman (1989) #1",
                "cover_date": "1989-06-01",
                "image": "https://static.metron.cloud/media/issue/2019/05/25/aquaman-v3-1.jpg",
                "cover_hash": "d50df6181876276d",
                "modified": "2023-05-30T11:16:59.837088-04:00",
            },
            {
                "id": 2510,
                "series": {"name": "Aquaman", "volume": 4, "year_began": 1991},
                "number": "1",
                "issue": "Aquaman (1991) #1",
                "cover_date": "1991-12-01",
                "image": "https://static.metron.cloud/media/issue/2019/05/20/aquaman-v4-1.jpg",
                "cover_hash": "b45b17f5214a1cbc",
                "modified": "2023-05-27T07:45:16.756751-04:00",
            },
            {
                "id": 1776,
                "series": {"name": "Aquaman", "volume": 5, "year_began": 1994},
                "number": "1",
                "issue": "Aquaman (1994) #1",
                "cover_date": "1994-08-01",
                "image": "https://static.metron.cloud/media/issue/2019/04/01/aquaman-1.jpg",
                "cover_hash": "abf0cf94916ab126",
                "modified": "2023-05-27T07:49:39.853440-04:00",
            },
            {
                "id": 2429,
                "series": {"name": "Aquaman", "volume": 6, "year_began": 2003},
                "number": "1",
                "issue": "Aquaman (2003) #1",
                "cover_date": "2003-02-01",
                "image": "https://static.metron.cloud/media/issue/2019/05/15/aquaman-v6-1.jpg",
                "cover_hash": "904aaee7e6d0d88d",
                "modified": "2023-05-27T07:54:56.676104-04:00",
            },
            {
                "id": 2523,
                "series": {"name": "Aquaman", "volume": 7, "year_began": 2011},
                "number": "1",
                "issue": "Aquaman (2011) #1",
                "cover_date": "2011-11-01",
                "image": "https://static.metron.cloud/media/issue/2019/05/21/aquaman-v7-1.jpg",
                "cover_hash": "91f1c7f28b346b30",
                "modified": "2023-05-27T07:58:16.239841-04:00",
            },
            {
                "id": 2896,
                "series": {"name": "Aquaman", "volume": 8, "year_began": 2016},
                "number": "1",
                "issue": "Aquaman (2016) #1",
                "cover_date": "2016-08-01",
                "image": "https://static.metron.cloud/media/issue/2019/06/19/aquaman-v8-1.jpg",
                "cover_hash": "8c4bf0234b3c3ae7",
                "modified": "2023-05-29T15:53:16.887401-04:00",
            },
        ],
    }
    return IssuesList(i)


def test_process_file(
    talker: Talker,
    fake_comic: ZipFile,
    issue_list_response: IssuesList,
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(fake_comic)
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
def test_write_issue_md(
    talker: Talker,
    fake_comic: ZipFile,
    metron_response: dict[str, any],
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(fake_comic)
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=metron_response)
    talker.retrieve_single_issue(fake_comic, 5)

    # Now let's test writing the metadata to file
    talker._write_issue_md(fake_comic, 1)
    ca = Comic(fake_comic)
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.stories == create_read_md_story(metron_response.story_titles)
    assert ca_md.series.name == metron_response.series.name
    assert ca_md.series.volume == metron_response.series.volume
    assert ca_md.publisher.name == metron_response.publisher.name
    assert ca_md.issue == metron_response.number
    assert ca_md.teams is None
    assert ca_md.cover_date.year == metron_response.cover_date.year
    assert ca_md.characters == create_read_md_resource_list(metron_response.characters)
    assert ca_md.credits is not None
    assert ca_md.credits[0].person == "Roger Stern"
    assert ca_md.credits[0].role[0].name == "Writer"


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_retrieve_single_issue(
    talker: Talker,
    fake_comic: ZipFile,
    metron_response: dict[str, any],
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(fake_comic)
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=metron_response)
    talker.retrieve_single_issue(fake_comic, 10)

    # Now let's test the metadata
    ca = Comic(fake_comic)
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.stories == create_read_md_story(metron_response.story_titles)
    assert ca_md.series.name == metron_response.series.name
    assert ca_md.series.volume == metron_response.series.volume
    assert ca_md.publisher.name == metron_response.publisher.name
    assert ca_md.issue == metron_response.number
    assert ca_md.teams is None
    assert ca_md.cover_date.year == metron_response.cover_date.year
    assert ca_md.characters == create_read_md_resource_list(metron_response.characters)
    assert ca_md.credits is not None
    assert ca_md.credits[0].person == "Roger Stern"
    assert ca_md.credits[0].role[0].name == "Writer"
