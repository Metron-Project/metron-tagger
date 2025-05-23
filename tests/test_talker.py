import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest
from darkseid.comic import Comic, MetadataFormat
from darkseid.metadata import AgeRatings, Basic, InfoSources, Links, Metadata, Notes, Series
from mokkari.schemas.base import BaseResource
from mokkari.schemas.generic import GenericItem
from mokkari.schemas.issue import BaseIssue, BasicSeries, Credit, Issue, IssueSeries
from mokkari.schemas.reprint import Reprint
from mokkari.session import Session
from pydantic import HttpUrl, TypeAdapter

from metrontagger.talker import InfoSource, Talker

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
            year_began=1978,
        ),
        number="47",
        alt_number="",
        title="",
        name=["A Night on the Prowl!"],
        cover_date=date(1980, 10, 1),
        store_date=None,
        price=Decimal(".5"),
        rating=GenericItem(id=6, name="CCA"),
        upc="",
        isbn="",
        sku="",
        page=36,
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
    assert md.age_rating == AgeRatings("Everyone", "Everyone")
    assert md.web_link == [
        Links("https://metron.cloud/issue/the-spectacular-spider-man-1976-47/", True)
    ]


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
    assert meta_data.series.start_year == test_issue.series.year_began
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
            issue="Aquaman (1962) #1",
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
            issue="Aquaman (1986) #1",
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
            issue="Aquaman (1989) #1",
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
    if ca.has_metadata(MetadataFormat.COMIC_RACK):
        ca.remove_metadata(MetadataFormat.COMIC_RACK)

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


def test_process_file_with_accept_only(
    talker: Talker,
    fake_comic: ZipFile,
    test_issue_list: list[BaseIssue],
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(str(fake_comic))
    if ca.has_metadata(MetadataFormat.COMIC_RACK):
        ca.remove_metadata(MetadataFormat.COMIC_RACK)

    # Mock the call to Metron with a single result
    mocker.patch.object(Session, "issues_list", return_value=[test_issue_list[0]])

    # Test with a single match
    id_, multiple = talker._process_file(Path(str(fake_comic)), True)
    assert id_ is not None
    assert id_ == test_issue_list[0].id
    assert not multiple
    assert fake_comic in talker.match_results.good_matches


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_write_issue_md(
    talker: Talker,
    fake_comic: ZipFile,
    test_issue: Issue,
    mocker: any,
) -> None:
    # Remove any existing metadata from comic fixture
    ca = Comic(str(fake_comic))
    if ca.has_metadata(MetadataFormat.COMIC_RACK):
        ca.remove_metadata(MetadataFormat.COMIC_RACK)

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=test_issue)
    talker.retrieve_single_issue(5, Path(str(fake_comic)))

    # Now let's test writing the metadata to file
    talker._write_issue_md(Path(str(fake_comic)), 1)
    ca = Comic(str(fake_comic))
    assert ca.has_metadata(MetadataFormat.COMIC_RACK)
    ca_md = ca.read_metadata(MetadataFormat.COMIC_RACK)
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
    if ca.has_metadata(MetadataFormat.COMIC_RACK):
        ca.remove_metadata(MetadataFormat.COMIC_RACK)

    # Mock the call to Metron
    mocker.patch.object(Session, "issue", return_value=test_issue)
    talker.retrieve_single_issue(10, Path(str(fake_comic)))

    # Now let's test the metadata
    ca = Comic(str(fake_comic))
    assert ca.has_metadata(MetadataFormat.COMIC_RACK)
    ca_md = ca.read_metadata(MetadataFormat.COMIC_RACK)
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


@pytest.mark.parametrize(
    ("primary_name", "primary_id", "alternatives", "expected"),
    [
        # Happy path tests
        ("metron", 123, [], (InfoSource.metron, 123)),
        ("comic vine", 456, [], (InfoSource.comic_vine, 456)),
        ("anilist", 789, [InfoSources("metron", 321)], (InfoSource.metron, 321)),
        # Edge case
        ("anilist", 789, [], None),
    ],
    ids=[
        "happy_path_metron_primary",
        "happy_path_comic_vine_primary",
        "happy_path_metron_alternative",
        "edge_case_no_metron_or_comic_vine",
    ],
)
def test_get_id_from_metron_info(primary_name, primary_id, alternatives, expected):
    # Arrange
    md = Metadata(info_source=[InfoSources(primary_name, primary_id, True), *alternatives])

    # Act
    result = Talker._get_id_from_metron_info(md)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("notes", "expected"),
    [
        # Happy path tests
        (
            "Tagged with MetronTagger-2.6.0 using info from Metron on 2024-10-16 16:07:08. [issue_id:12345]",
            (InfoSource.metron, 12345),
        ),
        (
            "Tagged with ComicTagger 1.3.2a5 using info from Comic Vine on 2022-04-16 15:52:26. [Issue ID 67890]",
            (InfoSource.comic_vine, 67890),
        ),
        # Edge cases
        (
            "Tagged with MetronTagger-2.6.0 using info from Metron on 2024-10-16 16:07:08. [issue_id:00001]",
            (InfoSource.metron, 1),
        ),
        (
            "Tagged with ComicTagger 1.3.2a5 using info from Comic Vine on 2022-04-16 15:52:26. [Issue ID 00000]",
            (InfoSource.comic_vine, 0),
        ),
        # Error cases
        (
            "Tagged with MetronTagger-2.6.0 using info from Metron on 2024-10-16 16:07:08. [issue_id:abcde]",
            None,
        ),
        (
            "Tagged with ComicTagger 1.3.2a5 using info from Comic Vine on 2022-04-16 15:52:26. [Issue ID abcde]",
            None,
        ),
        ("[unknown] Issue ID: 12345", None),
        (None, None),
    ],
    ids=[
        "metrontagger_valid_id",
        "comictagger_valid_id",
        "metrontagger_leading_zeros",
        "comictagger_zero_id",
        "metrontagger_invalid_id",
        "comictagger_invalid_id",
        "unknown_source",
        "no_notes",
    ],
)
def test_get_id_from_comic_info(notes, expected):
    # Arrange
    md = Metadata(
        notes=Notes(comic_rack=notes) if notes else None, series=Series("Foo"), issue="2"
    )

    # Act
    result = Talker._get_id_from_comic_info(md)

    # Assert
    assert result == expected
