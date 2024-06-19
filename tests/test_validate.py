from pathlib import Path

import pytest

from metrontagger.validate_ci import SchemaVersion, ValidateComicInfo


@pytest.fixture()
def valid_comic_info_v1():
    # TODO: Add some ComicInfo v1 data.
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <ComicInfo>
        <!-- Valid XML content for v1 -->
    </ComicInfo>"""


@pytest.fixture()
def valid_comic_info_v2():
    return b"""<?xml version='1.0' encoding='utf-8'?> <ComicInfo
    xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="https://www.w3.org/2001/XMLSchema">
    <Title>"Fallen Grayson, Part Two"</Title> <Series>Nightwing</Series> <Number>115</Number> <Volume>4</Volume>
    <Summary>THE HEARTLESS SAGA BY TOM TAYLOR AND BRUNO REDONDO CONTINUES! When things go up in flames, Dick must put
    his feelings aside and help Shelton, a.k.a. Heartless, find his butler. After all, a superhero's job is to save
    everyone, even the very bad. But every noble sacrifice comes with a price, and Nightwing finds himself in a
    situation only someone as cunning as Heartless could've concocted. LEGACY #302</Summary> <Notes>Tagged with
    MetronTagger-2.3.0 using info from Metron on 2024-06-18 12:07:43. [issue_id:119742]</Notes> <Year>2024</Year>
    <Month>8</Month> <Day>1</Day> <Writer>Tom Taylor</Writer> <Penciller>Bruno Redondo</Penciller> <Inker>Bruno
    Redondo, Caio Filipe</Inker> <Colorist>Adriano Lucas</Colorist> <Letterer>Wes Abbott</Letterer>
    <CoverArtist>Bruka Jones, Bruno Redondo, Dan Mora, Marco Santucci, Vasco Georgiev</CoverArtist> <Editor>Jessica
    Berbey, Marie Javins, Rob Levin</Editor> <Publisher>DC Comics</Publisher> <Genre>Super-Hero</Genre>
    <Web>https://metron.cloud/issue/nightwing-2016-115/</Web> <PageCount>29</PageCount> <Format>Ongoing
    Series</Format> <Characters>Barbara Gordon, Dick Grayson</Characters> <StoryArc>Fallen Grayson</StoryArc>
    <AgeRating>Teen</AgeRating> <Pages> <Page Image="0" ImageHeight="3057" ImageSize="2046933" ImageWidth="1988"
    Type="FrontCover" /> <Page Image="1" ImageHeight="3056" ImageSize="1630556" ImageWidth="1989" /> <Page Image="2"
    ImageHeight="3057" ImageSize="3924933" ImageWidth="1988" /> <Page Image="3" ImageHeight="3057"
    ImageSize="3305072" ImageWidth="1988" /> <Page Image="4" ImageHeight="3057" ImageSize="3469700" ImageWidth="1988"
    /> <Page Image="5" ImageHeight="3057" ImageSize="3276728" ImageWidth="1988" /> <Page Image="6" ImageHeight="3057"
    ImageSize="2438857" ImageWidth="1988" /> <Page Image="7" ImageHeight="3057" ImageSize="3156648" ImageWidth="1988"
    /> <Page Image="8" ImageHeight="3057" ImageSize="2796989" ImageWidth="1988" /> <Page Image="9" ImageHeight="3057"
    ImageSize="5612305" ImageWidth="1988" /> <Page Image="10" ImageHeight="3057" ImageSize="6163202"
    ImageWidth="1988" /> <Page Image="11" ImageHeight="3057" ImageSize="3396077" ImageWidth="1988" /> <Page
    Image="12" ImageHeight="3057" ImageSize="2791071" ImageWidth="1988" /> <Page Image="13" ImageHeight="3057"
    ImageSize="3336552" ImageWidth="1988" /> <Page Image="14" ImageHeight="3057" ImageSize="3079797"
    ImageWidth="1988" /> <Page Image="15" ImageHeight="3057" ImageSize="2597035" ImageWidth="1988" /> <Page
    Image="16" ImageHeight="3057" ImageSize="2908071" ImageWidth="1988" /> <Page Image="17" ImageHeight="3057"
    ImageSize="3363714" ImageWidth="1988" /> <Page Image="18" ImageHeight="3057" ImageSize="3430998"
    ImageWidth="1988" /> <Page Image="19" ImageHeight="3057" ImageSize="3139254" ImageWidth="1988" /> <Page
    Image="20" ImageHeight="3057" ImageSize="3299736" ImageWidth="1988" /> <Page Image="21" ImageHeight="3057"
    ImageSize="2811842" ImageWidth="1988" /> <Page Image="22" ImageHeight="3057" ImageSize="3570565"
    ImageWidth="1988" /> <Page Image="23" ImageHeight="3057" ImageSize="3297615" ImageWidth="1988" /> <Page
    Image="24" ImageHeight="3056" ImageSize="3223048" ImageWidth="1989" /> <Page Image="25" ImageHeight="3057"
    ImageSize="3802328" ImageWidth="1988" /> <Page Image="26" ImageHeight="3057" ImageSize="3836401"
    ImageWidth="1988" /> <Page Image="27" ImageHeight="3057" ImageSize="4836062" ImageWidth="1988" /> <Page
    Image="28" ImageHeight="3056" ImageSize="4169094" ImageWidth="1989" /> </Pages> </ComicInfo>"""


@pytest.fixture()
def invalid_comic_info():
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <ComicFake>
        <!-- Invalid XML content -->
    </ComicFake>"""


@pytest.mark.parametrize(
    ("comic_info_xml", "schema_version", "expected_result"),
    [
        # ("valid_comic_info_v1", SchemaVersion.v1, True),
        ("valid_comic_info_v2", SchemaVersion.v2, True),
        # ("invalid_comic_info", SchemaVersion.v1, False),
        ("invalid_comic_info", SchemaVersion.v2, False),
    ],
    ids=[
        # "valid_v1",
        "valid_v2",
        # "invalid_v1",
        "invalid_v2",
    ],
)
def test_is_valid(comic_info_xml, schema_version, expected_result, request):
    # Arrange
    comic_info_xml = request.getfixturevalue(comic_info_xml)
    validator = ValidateComicInfo(comic_info_xml)

    # Act
    result = validator._is_valid(schema_version)

    # Assert
    assert result == expected_result


@pytest.mark.parametrize(
    ("comic_info_xml", "expected_version"),
    [
        # ("valid_comic_info_v1", SchemaVersion.v1),
        ("valid_comic_info_v2", SchemaVersion.v2),
        ("invalid_comic_info", SchemaVersion.Unknown),
    ],
    ids=[
        # "valid_v1",
        "valid_v2",
        "invalid",
    ],
)
def test_validate(comic_info_xml, expected_version, request):
    # Arrange
    comic_info_xml = request.getfixturevalue(comic_info_xml)
    validator = ValidateComicInfo(comic_info_xml)

    # Act
    result = validator.validate()

    # Assert
    assert result == expected_version


@pytest.mark.parametrize(
    ("schema_version", "expected_path"),
    [
        (SchemaVersion.v1, Path("/path/to/metrontagger.schema.v1/ComicInfo.xsd")),
        (SchemaVersion.v2, Path("/path/to/metrontagger.schema.v2/ComicInfo.xsd")),
        (SchemaVersion.Unknown, None),
    ],
    ids=[
        "schema_v1",
        "schema_v2",
        "schema_unknown",
    ],
)
def test_get_xsd(mocker, schema_version, expected_path):
    # Arrange
    mocker.patch("metrontagger.validate_ci.files", side_effect=lambda x: Path(f"/path/to/{x}"))
    validator = ValidateComicInfo(b"")

    # Act
    result = validator._get_xsd(schema_version)

    # Assert
    assert result == expected_path
