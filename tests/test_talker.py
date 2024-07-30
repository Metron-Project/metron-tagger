import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest
from darkseid.comic import Comic
from darkseid.metadata import Basic
from mokkari.schemas.base import BaseResource
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.issue import BaseIssue, BasicSeries, Credit, Issue, IssueSeries
from mokkari.schemas.reprint import Reprint
from mokkari.session import Session
from pydantic import HttpUrl, TypeAdapter

from metrontagger.talker import Talker

tzinfo = timezone(timedelta(hours=-5))


@pytest.fixture()
def test_issue() -> Issue:
    issue = Issue(
        id=31047,
        publisher=GenericItem(id=1, name="Marvel"),
        series=IssueSeries(
            id=2222,
            name="The Spectacular Spider-Man",
            sort_name="Spectacular Spider-Man",
            volume=1,
            series_type=GenericItem(id=2, name="Single Issue"),
        ),
        number="47",
        collection_title="",
        story_titles=["A Night on the Prowl!"],
        cover_date=date(1980, 10, 1),
        store_date=None,
        price=Decimal(".5"),
        rating=GenericItem(id=6, name="CCA"),
        upc="",
        isbn="",
        sku="",
        page_count=36,
        desc="Spider-Man goes on a wild goose chase to find out who is behind the Prowler impersonation.",
        image=HttpUrl(
            "https://static.metron.cloud/media/issue/2021/05/22/the-spectacular-spider-man-47.jpg"
        ),
        cover_hash="c0f83fe438876c1b",
        credits=[
            Credit(id=2335, creator="Al Milgrom", role=[GenericItem(id=7, name="Cover")]),
            Credit(
                id=1402,
                creator="Bruce Patterson",
                role=[GenericItem(id=4, name="Inker"), GenericItem(id=6, name="Letterer")],
            ),
            Credit(id=128, creator="Dennis O'Neil", role=[GenericItem(id=8, name="Editor")]),
            Credit(id=624, creator="Glynis Oliver", role=[GenericItem(id=5, name="Colorist")]),
            Credit(
                id=624,
                creator="Jim Shooter",
                role=[GenericItem(id=20, name="Editor In Chief")],
            ),
            Credit(
                id=675, creator="Marie Severin", role=[GenericItem(id=3, name="Penciller")]
            ),
            Credit(id=675, creator="Roger Stern", role=[GenericItem(id=1, name="Writer")]),
        ],
        characters=[
            BaseResource(id=6784, name="Debra Whitman", modified=datetime.now(tzinfo)),
            BaseResource(id=3067, name="Hobgoblin (Kingsley)", modified=datetime.now(tzinfo)),
            BaseResource(id=2415, name="Prowler", modified=datetime.now(tzinfo)),
            BaseResource(id=145, name="Spider-Man", modified=datetime.now(tzinfo)),
        ],
        cv_id=20745,
        resource_url=HttpUrl("https://metron.cloud/issue/the-spectacular-spider-man-1976-47/"),
        modified=datetime.now(tzinfo),
    )
    adapter = TypeAdapter(Issue)
    return adapter.validate_python(issue)


def create_reprint_list(resource: list[Reprint]) -> list[Basic]:
    return [Basic(r.issue, r.id) for r in resource]


def create_resource_list(resource: any) -> list[Basic]:
    return [Basic(r.name, r.id) for r in resource]


def create_read_md_resource_list(resource: any) -> list[Basic]:
    return [Basic(r.name) for r in resource]


def create_read_md_story(resource: list[str]) -> list[Basic]:
    return [Basic(story) for story in resource]


def test_map_resp_to_metadata(talker: Talker, test_issue: Issue) -> None:
    md = talker._map_resp_to_metadata(test_issue)
    assert md is not None
    assert md.stories == create_read_md_story(test_issue.story_titles)
    assert md.series.name == test_issue.series.name
    assert md.series.volume == test_issue.series.volume
    assert md.publisher.name == test_issue.publisher.name
    assert md.issue == test_issue.number
    assert md.story_arcs == create_resource_list(test_issue.arcs)
    assert md.teams == create_resource_list(test_issue.teams)
    assert md.cover_date.year == test_issue.cover_date.year
    assert md.characters == create_resource_list(test_issue.characters)
    assert md.credits is not None
    assert md.credits[0].person == "Al Milgrom"
    assert md.credits[0].role[0].name == "Cover"
    assert md.reprints == create_reprint_list(test_issue.reprints)
    assert md.age_rating == "Everyone"
    assert md.web_link == "https://metron.cloud/issue/the-spectacular-spider-man-1976-47/"


def test_map_resp_to_metadata_with_no_story_name(
    talker: Talker,
    test_issue: Issue,
) -> None:
    test_data = test_issue
    test_data.story_titles = []
    meta_data = talker._map_resp_to_metadata(test_data)
    assert meta_data is not None
    assert len(meta_data.stories) == 0
    assert meta_data.series.name == test_issue.series.name
    assert meta_data.series.volume == test_issue.series.volume
    assert meta_data.publisher.name == test_issue.publisher.name
    assert meta_data.issue == test_issue.number
    assert meta_data.cover_date.year == test_issue.cover_date.year


@pytest.fixture()
def test_issue_list() -> list[BaseIssue]:
    i_list = [
        BaseIssue(
            id=3634,
            series=BasicSeries(name="Aquaman", volume=1, year_began=1962),
            number="1",
            issue_name="Aquaman (1962) #1",
            cover_date=date(1962, 2, 1),
            image=HttpUrl(
                "https://static.metron.cloud/media/issue/2019/07/12/aquaman-v1-1.jpg"
            ),
            cover_hash="ccb2097c5b273c1b",
            modified=datetime.now(tzinfo),
        ),
        BaseIssue(
            id=2471,
            series=BasicSeries(name="Aquaman", volume=2, year_began=1986),
            number="1",
            issue_name="Aquaman (1986) #1",
            cover_date=date(1986, 2, 1),
            image=HttpUrl(
                "https://static.metron.cloud/media/issue/2019/05/19/aquaman-v2-1.jpg"
            ),
            cover_hash="ea97c11cb3660c79",
            modified=datetime.now(tzinfo),
        ),
        BaseIssue(
            id=2541,
            series=BasicSeries(name="Aquaman", volume=3, year_began=1989),
            number="1",
            issue_name="Aquaman (1989) #1",
            cover_date=date(1989, 6, 1),
            image=HttpUrl(
                "https://static.metron.cloud/media/issue/2019/05/25/aquaman-v3-1.jpg"
            ),
            cover_hash="d50df6181876276d",
            modified=datetime.now(tzinfo),
        ),
    ]
    adapter = TypeAdapter(list[BaseIssue])
    return adapter.validate_python(i_list)


def test_process_file(
    talker: Talker,
    fake_comic: ZipFile,
    test_issue_list: list[BaseIssue],
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(str(fake_comic))
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issues_list", return_value=test_issue_list)
    talker._process_file(Path(str(fake_comic)), False)

    id_, multiple = talker._process_file(Path(str(fake_comic)), False)
    assert id_ is None
    assert multiple
    assert fake_comic in [c.filename for c in talker.match_results.multiple_matches]

    id_list = []
    for c in talker.match_results.multiple_matches:
        id_list.extend(i.id for i in c.matches)
    assert 2471 in id_list  # noqa: PLR2004


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_write_issue_md(
    talker: Talker,
    fake_comic: ZipFile,
    test_issue: Issue,
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(str(fake_comic))
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=test_issue)
    talker.retrieve_single_issue(Path(str(fake_comic)), 5)

    # Now let's test writing the metadata to file
    talker._write_issue_md(Path(str(fake_comic)), 1)
    ca = Comic(str(fake_comic))
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.stories == create_read_md_story(test_issue.story_titles)
    assert ca_md.series.name == test_issue.series.name
    assert ca_md.series.volume == test_issue.series.volume
    assert ca_md.publisher.name == test_issue.publisher.name
    assert ca_md.issue == test_issue.number
    assert ca_md.teams is None
    assert ca_md.cover_date.year == test_issue.cover_date.year
    assert ca_md.characters == create_read_md_resource_list(test_issue.characters)
    assert ca_md.credits is not None
    assert ca_md.credits[0].person == "Roger Stern"
    assert ca_md.credits[0].role[0].name == "Writer"


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_retrieve_single_issue(
    talker: Talker,
    fake_comic: ZipFile,
    test_issue: Issue,
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(str(fake_comic))
    if ca.has_metadata():
        ca.remove_metadata()

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=test_issue)
    talker.retrieve_single_issue(Path(str(fake_comic)), 10)

    # Now let's test the metadata
    ca = Comic(str(fake_comic))
    assert ca.has_metadata()
    ca_md = ca.read_metadata()
    assert ca_md.stories == create_read_md_story(test_issue.story_titles)
    assert ca_md.series.name == test_issue.series.name
    assert ca_md.series.volume == test_issue.series.volume
    assert ca_md.publisher.name == test_issue.publisher.name
    assert ca_md.issue == test_issue.number
    assert ca_md.teams is None
    assert ca_md.cover_date.year == test_issue.cover_date.year
    assert ca_md.characters == create_read_md_resource_list(test_issue.characters)
    assert ca_md.credits is not None
    assert ca_md.credits[0].person == "Roger Stern"
    assert ca_md.credits[0].role[0].name == "Writer"
