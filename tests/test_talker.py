"""Tests for the Talker class and its helper classes."""

import io
import random
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest
import redis
import requests
from comicfn2dict import comicfn2dict
from darkseid.comic import Comic
from darkseid.metadata import Basic, Metadata, MetronInfo, Notes
from imagehash import hex_to_hash, phash
from mokkari.exceptions import ApiError, RateLimitError
from mokkari.rate_limit import HeaderPacedRateLimiter
from PIL import ExifTags, Image

from metrontagger import __version__
from metrontagger.talker import (
    COVER_ACCEPT_DISTANCE,
    COVER_ACCEPT_MARGIN,
    COVER_SEARCH_MAX_DISTANCE,
    HALF_COVER_HAMMING_DISTANCE,
    HAMMING_DISTANCE,
    REDIS_SOCKET_TIMEOUT,
    CoverHashMatcher,
    CoverMatches,
    InfoSource,
    MetadataExtractor,
    MetadataMapper,
    MultipleMatch,
    OnlineMatchResults,
    ProcessingConfig,
    SearchResult,
    Talker,
    UIPresenter,
)

tzinfo = timezone(timedelta(hours=-5))


# Fixtures
@pytest.fixture
def mock_api():
    """Create a mock API object."""
    api = Mock()
    api.issue.return_value = create_mock_issue_response()
    api.issues_list.return_value = [create_mock_base_issue()]
    return api


@pytest.fixture
def mock_comic():
    """Create a mock Comic object."""
    comic = Mock(spec=Comic)
    comic.is_writable.return_value = True
    comic.seems_to_be_a_comic_archive.return_value = True
    comic.has_metadata.return_value = False
    comic.get_number_of_pages.return_value = 20
    comic.get_page.return_value = b"fake_image_data"
    comic.write_metadata.return_value = True
    return comic


@pytest.fixture
def talker(mock_api):
    """Create a Talker instance with mocked API."""
    with patch("metrontagger.talker.mokkari.api", return_value=mock_api):
        return Talker("my-token", metron_info=True, comic_info=True)


@pytest.fixture
def sample_path():
    """Create a sample Path object."""
    return Path("test_comic.cbz")


def create_http_api_error(status_code: int, message: str = "HTTP error") -> ApiError:
    """Create an ApiError chained to an HTTPError, mirroring what mokkari raises."""
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    http_error = requests.exceptions.HTTPError(response=response)
    api_error = ApiError(message)
    api_error.__cause__ = http_error
    return api_error


def create_mock_base_issue(issue_id=123, cover_hash="abcdef123456", series_name="Test Comic"):
    """Create a mock BaseIssue object."""
    issue = Mock()
    issue.id = issue_id
    issue.issue_name = f"{series_name} #1"
    issue.series.name = series_name
    issue.cover_date = datetime(2023, 1, 1, tzinfo=tzinfo).date()
    issue.cover_hash = cover_hash
    return issue


def create_mock_issue_response(
    isbn=None,
    upc=None,
    average_rating=Decimal("4.25"),
    rating_count=8,
    alt_number=None,
    alt_names=None,
    language="en",
):
    """Create a mock Issue response object."""

    issue = Mock()
    issue.id = 123
    issue.number = "1"
    issue.alt_number = alt_number
    issue.cover_date = datetime(2023, 1, 1, tzinfo=tzinfo).date()
    issue.store_date = datetime(2023, 1, 15, tzinfo=tzinfo).date()
    issue.desc = "Test description"
    issue.modified = datetime(2023, 1, 1, tzinfo=tzinfo)
    issue.cv_id = 456
    issue.gcd_id = None
    issue.collection_title = None
    issue.story_titles = ["Main Story"]
    issue.rating = Mock()
    issue.rating.name = "Teen"
    issue.resource_url = "https://example.com/issue/123"
    issue.price = Decimal("3.99")
    issue.price_currency = "USD"
    issue.isbn = isbn
    issue.upc = upc
    issue.average_rating = average_rating
    issue.rating_count = rating_count

    # Series mock
    issue.series = Mock()
    issue.series.name = "Test Series"
    issue.series.id = 1
    issue.series.sort_name = "Test Series"
    issue.series.alt_names = alt_names if alt_names is not None else []
    issue.series.volume = 1
    issue.series.series_type = Mock()
    issue.series.series_type.name = "Regular"
    issue.series.year_began = 2023
    issue.series.language = language
    issue.series.genres = [Mock(name="Action", id=1)]

    # Publisher mock
    issue.publisher = Mock()
    issue.publisher.name = "Test Publisher"
    issue.publisher.id = 1
    issue.imprint = None

    # Other collections
    issue.characters = [Mock(name="Hero", id=1)]
    issue.teams = [Mock(name="Team", id=1)]
    issue.arcs = [Mock(name="Arc", id=1)]
    issue.reprints = []
    issue.universes = [Mock(name="Universe", id=1)]
    issue.credits = [Mock(creator="Writer", role=[Mock(name="Writer", id=1)], id=1)]

    return issue


def create_mock_metadata():
    """Create a mock Metadata object."""
    md = Mock(spec=Metadata)
    md.info_source = [Mock(name="metron", id_=123)]
    md.notes = Mock()
    md.notes.comic_rack = "Tagged with MetronTagger [issue_id:123]"
    md.series = Mock()
    md.series.name = "Test Series"
    md.issue = "1"
    return md


# OnlineMatchResults tests
def test_online_match_results_initialization():
    """Test OnlineMatchResults initialization."""
    results = OnlineMatchResults()
    assert results.good_matches == []
    assert results.no_matches == []
    assert results.multiple_matches == []
    assert results.skipped_matches == []


def test_online_match_results_add_good_match():
    """Test adding a good match."""
    results = OnlineMatchResults()
    path = Path("test.cbz")
    results.add_good_match(path)
    assert path in results.good_matches


def test_online_match_results_add_no_match():
    """Test adding a no match."""
    results = OnlineMatchResults()
    path = Path("test.cbz")
    results.add_no_match(path)
    assert path in results.no_matches


def test_online_match_results_add_skipped_match():
    """Test adding a skipped match."""
    results = OnlineMatchResults()
    path = Path("test.cbz")
    results.add_skipped_match(path)
    assert path in results.skipped_matches
    assert len(results.skipped_matches) == 1


def test_online_match_results_add_multiple_skipped_matches():
    """Test adding multiple skipped matches."""
    results = OnlineMatchResults()
    paths = [Path("test1.cbz"), Path("test2.cbz"), Path("test3.cbz")]

    for path in paths:
        results.add_skipped_match(path)

    assert len(results.skipped_matches) == 3
    assert all(path in results.skipped_matches for path in paths)


def test_online_match_results_add_multiple_match():
    """Test adding a multiple match."""
    results = OnlineMatchResults()
    multi_match = MultipleMatch(Path("test.cbz"), [create_mock_base_issue()])
    results.add_multiple_match(multi_match)
    assert multi_match in results.multiple_matches


# MultipleMatch tests
def test_multiple_match_initialization():
    """Test MultipleMatch initialization."""
    filename = Path("test.cbz")
    matches = [create_mock_base_issue()]
    multi_match = MultipleMatch(filename, matches)
    assert multi_match.filename == filename
    assert multi_match.matches == matches


# MetadataExtractor tests
# TODO: Need to look into why this test is failing
# def test_metadata_extractor_get_id_from_metron_info_success():
#     """Test successful ID extraction from MetronInfo."""
#     md = create_mock_metadata()
#     result = MetadataExtractor.get_id_from_metron_info(md)
#     assert result == (InfoSource.METRON, 123)


def test_metadata_extractor_get_id_from_metron_info_no_sources():
    """Test ID extraction when no valid sources exist."""
    md = Mock(spec=Metadata)
    md.info_source = []
    result = MetadataExtractor.get_id_from_metron_info(md)
    assert result is None


def test_metadata_extractor_get_id_from_metron_info_none_sources():
    """Test ID extraction when info_source is None."""
    md = Mock(spec=Metadata)
    md.info_source = None
    result = MetadataExtractor.get_id_from_metron_info(md)
    assert result is None


def test_metadata_extractor_get_id_from_comic_info_success():
    """Test successful ID extraction from ComicInfo."""
    md = create_mock_metadata()

    with patch("metrontagger.talker.get_issue_id_from_note") as mock_get_id:
        mock_get_id.return_value = {"source": "Metron", "id": "123"}
        result = MetadataExtractor.get_id_from_comic_info(md)
        assert result == (InfoSource.METRON, 123)


def test_metadata_extractor_get_id_from_comic_info_no_notes():
    """Test ID extraction when no notes exist."""
    md = Mock(spec=Metadata)
    md.notes = None
    result = MetadataExtractor.get_id_from_comic_info(md)
    assert result is None


def test_metadata_extractor_get_id_from_comic_info_invalid_id():
    """Test ID extraction with invalid ID."""
    md = create_mock_metadata()

    with patch("metrontagger.talker.get_issue_id_from_note") as mock_get_id:
        mock_get_id.return_value = {"source": "Metron", "id": "invalid"}
        result = MetadataExtractor.get_id_from_comic_info(md)
        assert result is None


# CoverHashMatcher tests


def _make_image_bytes(size: tuple[int, int], seed: int = 0) -> bytes:
    """Create a PNG with a random noise pattern so phash values are distinctive."""
    rng = random.Random(seed)  # noqa: S311 - deterministic test data
    img = Image.new("L", size)
    img.putdata([rng.randint(0, 255) for _ in range(size[0] * size[1])])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_spread_bytes(left: bytes, right: bytes) -> bytes:
    """Join two page images side-by-side into a double-page spread."""
    with Image.open(io.BytesIO(left)) as left_img, Image.open(io.BytesIO(right)) as right_img:
        spread = Image.new("L", (left_img.width + right_img.width, left_img.height))
        spread.paste(left_img, (0, 0))
        spread.paste(right_img, (left_img.width, 0))
    buf = io.BytesIO()
    spread.save(buf, format="PNG")
    return buf.getvalue()


def _hash_hex(data: bytes) -> str:
    with Image.open(io.BytesIO(data)) as img:
        return str(phash(img))


@pytest.fixture
def _clear_cover_hash_cache():
    """Clear the cover-hash cache around tests that compute real cover hashes."""
    CoverHashMatcher.get_comic_cover_hashes_cached.cache_clear()
    yield
    CoverHashMatcher.get_comic_cover_hashes_cached.cache_clear()


@pytest.mark.parametrize(
    ("size", "expected"),
    [((650, 1000), False), ((1000, 1000), False), ((1150, 1000), False), ((1300, 1000), True)],
)
def test_cover_hash_matcher_is_double_spread(size, expected):
    """Only landscape images are treated as double-page spreads."""
    assert CoverHashMatcher.is_double_spread(Image.new("L", size)) is expected


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_single_cover():
    """A portrait cover yields a single hash."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = _make_image_bytes((65, 100))

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == 1


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_double_spread():
    """A landscape cover yields full, right-half, and left-half hashes."""
    left = _make_image_bytes((65, 100), seed=1)
    right = _make_image_bytes((65, 100), seed=2)
    mock_comic = Mock()
    mock_comic.get_page.return_value = _make_spread_bytes(left, right)

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == 3
    assert str(result[1]) == _hash_hex(right)
    assert str(result[2]) == _hash_hex(left)


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@pytest.mark.parametrize(("orientation", "expected_len"), [(1, 3), (6, 1), (8, 1)])
def test_cover_hash_matcher_get_comic_cover_hashes_exif_orientation(orientation, expected_len):
    """A landscape-stored cover that EXIF rotates to portrait isn't treated as a spread."""
    with Image.open(io.BytesIO(_make_image_bytes((130, 100)))) as img:
        exif = Image.Exif()
        exif[ExifTags.Base.Orientation] = orientation
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", exif=exif)
    mock_comic = Mock()
    mock_comic.get_page.return_value = buf.getvalue()

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == expected_len


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_jxl():
    """A JPEG XL cover is hashed when the optional `jxl` extra is installed."""
    pytest.importorskip("pillow_jxl")
    with Image.open(io.BytesIO(_make_image_bytes((65, 100)))) as img:
        buf = io.BytesIO()
        img.save(buf, format="JXL", lossless=True)
    mock_comic = Mock()
    mock_comic.get_page.return_value = buf.getvalue()

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == 1


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_corrupt_jxl():
    """A truncated JPEG XL cover yields no hashes instead of raising."""
    pytest.importorskip("pillow_jxl")
    with Image.open(io.BytesIO(_make_image_bytes((65, 100)))) as img:
        buf = io.BytesIO()
        img.save(buf, format="JXL", lossless=True)
    mock_comic = Mock()
    mock_comic.get_page.return_value = buf.getvalue()[: len(buf.getvalue()) // 2]

    with patch("metrontagger.talker.questionary.print"):
        assert CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic) == ()


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@patch("metrontagger.talker.Image.open", side_effect=RuntimeError("decode failed"))
def test_cover_hash_matcher_get_comic_cover_hash_runtime_error(_):  # noqa: PT019
    """A decoder RuntimeError (e.g. from pillow-jxl-plugin) yields no hashes."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = b"fake_image_data"

    with patch("metrontagger.talker.questionary.print"):
        assert CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic) == ()


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_no_page():
    """Missing cover page yields no hashes."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = None

    with patch("metrontagger.talker.questionary.print"):
        assert CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic) == ()


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@patch("metrontagger.talker.Image.open", side_effect=OSError("Invalid image"))
def test_cover_hash_matcher_get_comic_cover_hash_failure(_):  # noqa: PT019
    """Test cover hash calculation failure."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = b"fake_image_data"

    with patch("metrontagger.talker.questionary.print"):
        result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
        assert result == ()


def test_cover_hash_matcher_is_within_hamming_distance_success():
    """Test successful hamming distance check."""
    mock_comic = Mock()
    mock_hash = Mock()
    mock_hash.__sub__ = Mock(return_value=5)  # Within distance

    with (
        patch.object(
            CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=(mock_hash,)
        ),
        patch("metrontagger.talker.hex_to_hash", return_value=mock_hash),
    ):
        result = CoverHashMatcher.is_within_hamming_distance(mock_comic, "abcdef")
        assert result is True


def test_cover_hash_matcher_is_within_hamming_distance_failure():
    """Test failed hamming distance check."""
    mock_comic = Mock()
    mock_hash = Mock()
    mock_hash.__sub__ = Mock(return_value=15)  # Outside distance

    with (
        patch.object(
            CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=(mock_hash,)
        ),
        patch("metrontagger.talker.hex_to_hash", return_value=mock_hash),
    ):
        result = CoverHashMatcher.is_within_hamming_distance(mock_comic, "abcdef")
        assert result is False


def test_cover_hash_matcher_is_within_hamming_distance_no_hashes():
    """No cover hashes means no match."""
    with patch.object(CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=()):
        assert CoverHashMatcher.is_within_hamming_distance(Mock(), "abcdef") is False


@pytest.mark.parametrize(
    ("full_distance", "half_distance", "expected"),
    [
        (HAMMING_DISTANCE, 99, True),  # Full cover within its limit
        (HAMMING_DISTANCE + 1, 99, False),  # Full cover just over its limit
        (99, HALF_COVER_HAMMING_DISTANCE, True),  # Half within its limit
        (99, HALF_COVER_HAMMING_DISTANCE + 1, False),  # Half just over its limit
    ],
)
def test_cover_hash_matcher_half_cover_uses_own_distance(
    full_distance, half_distance, expected
):
    """The full cover and the half-cover crops are each checked against their own limit."""
    full_hash, half_hash = Mock(), Mock()
    full_hash.__sub__ = Mock(return_value=full_distance)
    half_hash.__sub__ = Mock(return_value=half_distance)

    with (
        patch.object(
            CoverHashMatcher,
            "get_comic_cover_hashes_cached",
            return_value=(full_hash, half_hash, half_hash),
        ),
        patch("metrontagger.talker.hex_to_hash"),
    ):
        assert CoverHashMatcher.is_within_hamming_distance(Mock(), "abcdef") is expected


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@pytest.mark.parametrize("front", ["right", "left"])
def test_cover_hash_matcher_double_spread_matches_single_cover(front):
    """A double-spread cover matches Metron's single front cover on either half."""
    back = _make_image_bytes((65, 100), seed=1)
    cover = _make_image_bytes((65, 100), seed=2)
    spread = (
        _make_spread_bytes(back, cover)
        if front == "right"
        else _make_spread_bytes(cover, back)
    )
    mock_comic = Mock()
    mock_comic.get_page.return_value = spread

    assert CoverHashMatcher.is_within_hamming_distance(mock_comic, _hash_hex(cover)) is True


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_double_spread_no_match():
    """A double-spread cover doesn't match an unrelated cover."""
    spread = _make_spread_bytes(
        _make_image_bytes((65, 100), seed=1), _make_image_bytes((65, 100), seed=2)
    )
    mock_comic = Mock()
    mock_comic.get_page.return_value = spread
    unrelated = _hash_hex(_make_image_bytes((65, 100), seed=3))

    assert CoverHashMatcher.is_within_hamming_distance(mock_comic, unrelated) is False


def test_cover_hash_matcher_filter_by_hamming_distance():
    """Test filtering issues by hamming distance."""
    mock_comic = Mock()
    issue1 = create_mock_base_issue()
    issue1.cover_hash = "hash1"
    issue2 = create_mock_base_issue()
    issue2.cover_hash = "hash2"

    with patch.object(
        CoverHashMatcher, "is_within_hamming_distance", side_effect=[True, False]
    ):
        result = CoverHashMatcher.filter_by_hamming_distance(mock_comic, [issue1, issue2])
        assert len(result) == 1
        assert result[0] == issue1


# MetadataMapper tests
def test_metadata_mapper_create_resource_list():
    """Test creating resource list."""
    resources = [Mock(name="Resource1", id=1), Mock(name="Resource2", id=2)]
    result = MetadataMapper.create_resource_list(resources)
    assert len(result) == 2
    assert all(isinstance(item, Basic) for item in result)


def test_metadata_mapper_create_notes():
    """Test creating notes."""
    issue_id = 123
    result = MetadataMapper.create_notes(issue_id)
    assert isinstance(result, Notes)
    assert "MetronTagger" in result.metron_info
    assert f"issue_id:{issue_id}" in result.comic_rack


def test_metadata_mapper_map_ratings():
    """Test rating mapping."""
    test_cases = [
        ("Everyone", ("Everyone", "Everyone")),
        ("Teen", ("Teen", "Teen")),
        ("Teen Plus", ("Teen Plus", "Teen")),
        ("Mature", ("Mature", "Mature 17+")),
        ("Unknown Rating", ("Unknown", "Unknown")),
    ]

    for input_rating, expected in test_cases:
        result = MetadataMapper.map_ratings(input_rating)
        assert result.metron_info == expected[0]
        assert result.comic_rack == expected[1]


def test_metadata_mapper_map_response_to_metadata():
    """Test mapping response to metadata."""

    resp = create_mock_issue_response()
    result = MetadataMapper.map_response_to_metadata(resp)

    assert isinstance(result, Metadata)
    assert result.series.name == "Test Series"
    assert result.issue == "1"
    assert len(result.info_source) >= 1
    assert result.info_source[0].name == "Metron"
    # Verify price is mapped
    assert result.prices is not None
    assert len(result.prices) == 1
    assert result.prices[0].amount == Decimal("3.99")
    assert result.prices[0].currency == "USD"
    # Verify community rating is mapped
    assert result.community_rating == Decimal("4.25")
    assert result.rating_count == 8


def test_metadata_mapper_map_response_to_metadata_without_average_rating():
    """Test mapping response to metadata when no average rating is present."""

    resp = create_mock_issue_response(average_rating=None, rating_count=0)
    result = MetadataMapper.map_response_to_metadata(resp)

    assert result.community_rating is None
    assert result.rating_count is None


def test_metadata_mapper_map_response_to_metadata_with_alternate_number():
    """Test mapping response to metadata when an alternate number is present."""

    resp = create_mock_issue_response(alt_number="1AU")
    result = MetadataMapper.map_response_to_metadata(resp)

    assert result.alternate_number == "1AU"


def test_metadata_mapper_map_response_to_metadata_without_alternate_number():
    """Test mapping response to metadata when no alternate number is present."""

    resp = create_mock_issue_response(alt_number=None)
    result = MetadataMapper.map_response_to_metadata(resp)

    assert result.alternate_number is None


def test_metadata_mapper_set_basic_issue_info_with_alternate_number():
    """Test setting basic issue info maps the alternate number."""
    resp = create_mock_issue_response(alt_number="25")
    md = Metadata()
    MetadataMapper._set_basic_issue_info(md, resp)

    assert md.alternate_number == "25"


def test_metadata_mapper_set_basic_issue_info_without_alternate_number():
    """Test setting basic issue info when no alternate number is present."""
    resp = create_mock_issue_response(alt_number=None)
    md = Metadata()
    MetadataMapper._set_basic_issue_info(md, resp)

    assert md.alternate_number is None


def test_metadata_mapper_set_series_info_with_alt_names():
    """Test setting series info maps alternate names."""
    resp = create_mock_issue_response(alt_names=["Alt Name One", "Alt Name Two"])
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert [n.name for n in md.series.alternative_names] == [
        "Alt Name One",
        "Alt Name Two",
    ]


def test_metadata_mapper_set_series_info_without_alt_names():
    """Test setting series info when no alternate names are present."""
    resp = create_mock_issue_response(alt_names=[])
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert md.series.alternative_names == []


def test_metadata_mapper_set_series_info_with_language():
    """Test setting series info maps the series language."""
    resp = create_mock_issue_response(language="en")
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert md.series.language == "en"


def test_metadata_mapper_set_series_info_without_language():
    """Test setting series info when no language is present."""
    resp = create_mock_issue_response(language=None)
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert md.series.language is None


def test_metadata_mapper_convert_gtin_to_int_valid():
    """Test converting valid GTIN string to int."""
    result = MetadataMapper._convert_gtin_to_int("9781234567890")
    assert result == 9781234567890
    assert isinstance(result, int)


def test_metadata_mapper_convert_gtin_to_int_invalid_string():
    """Test converting invalid GTIN string returns None."""
    result = MetadataMapper._convert_gtin_to_int("invalid")
    assert result is None


def test_metadata_mapper_convert_gtin_to_int_none():
    """Test converting None returns None."""
    result = MetadataMapper._convert_gtin_to_int(None)
    assert result is None


def test_metadata_mapper_convert_gtin_to_int_empty_string():
    """Test converting empty string returns None."""
    result = MetadataMapper._convert_gtin_to_int("")
    assert result is None


def test_metadata_mapper_set_gtin_info_both_isbn_and_upc():
    """Test setting GTIN info with both ISBN and UPC."""
    resp = create_mock_issue_response(isbn="9781234567890", upc="12345678901")
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is not None
    assert md.gtin.isbn == 9781234567890
    assert md.gtin.upc == 12345678901


def test_metadata_mapper_set_gtin_info_isbn_only():
    """Test setting GTIN info with ISBN only."""
    resp = create_mock_issue_response(isbn="9781234567890", upc=None)
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is not None
    assert md.gtin.isbn == 9781234567890
    assert md.gtin.upc is None


def test_metadata_mapper_set_gtin_info_upc_only():
    """Test setting GTIN info with UPC only."""
    resp = create_mock_issue_response(isbn=None, upc="12345678901")
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is not None
    assert md.gtin.isbn is None
    assert md.gtin.upc == 12345678901


def test_metadata_mapper_set_gtin_info_neither():
    """Test setting GTIN info with neither ISBN nor UPC."""
    resp = create_mock_issue_response(isbn=None, upc=None)
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is None


def test_metadata_mapper_set_gtin_info_invalid_values():
    """Test setting GTIN info with invalid values."""
    resp = create_mock_issue_response(isbn="invalid", upc="also_invalid")
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    # Both values are invalid, so gtin should not be set
    assert md.gtin is None


def test_metadata_mapper_map_response_to_metadata_with_gtin():
    """Test mapping response to metadata includes GTIN data."""
    resp = create_mock_issue_response(isbn="9781234567890", upc="12345678901")
    result = MetadataMapper.map_response_to_metadata(resp)

    assert isinstance(result, Metadata)
    assert result.gtin is not None
    assert result.gtin.isbn == 9781234567890
    assert result.gtin.upc == 12345678901


def test_metadata_mapper_series_language_written_to_metron_info_xml():
    """Test that the series language mapped from a response ends up as the
    Series element's ``lang`` attribute when writing MetronInfo.xml."""
    resp = create_mock_issue_response(language="en")
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    xml_string = MetronInfo().string_from_metadata(md)
    root = ET.fromstring(xml_string)  # noqa: S314

    series_node = root.find("Series")
    assert series_node is not None
    assert series_node.get("lang") == "en"


def test_metadata_mapper_series_without_language_omits_lang_attribute():
    """Test that a missing series language leaves the ``lang`` attribute unset
    when writing MetronInfo.xml."""
    resp = create_mock_issue_response(language=None)
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    xml_string = MetronInfo().string_from_metadata(md)
    root = ET.fromstring(xml_string)  # noqa: S314

    series_node = root.find("Series")
    assert series_node is not None
    assert series_node.get("lang") is None


# Talker class tests
def test_talker_initialization():
    """Test Talker initialization."""
    with patch("metrontagger.talker.mokkari.api") as mock_api_func:
        talker = Talker("my-token", metron_info=True, comic_info=False)
        assert talker.metron_info is True
        assert talker.comic_info is False
        assert isinstance(talker.match_results, OnlineMatchResults)
        mock_api_func.assert_called_once_with(
            user_agent=f"Metron-Tagger/{__version__}",
            api_token="my-token",  # noqa: S106
            rate_limiter=ANY,
        )
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )


def test_talker_initialization_with_username_only_used_for_redis():
    """Test a username isn't passed to mokkari, since Basic Auth is no longer used."""
    token = "my-token"  # noqa: S105
    with patch("metrontagger.talker.mokkari.api") as mock_api_func:
        Talker(token, metron_info=True, comic_info=False, username="user")
        mock_api_func.assert_called_once_with(
            user_agent=f"Metron-Tagger/{__version__}",
            api_token=token,
            rate_limiter=ANY,
        )
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )


@patch("metrontagger.talker.UIPresenter.print_warning")
def test_talker_with_redis_url_without_username_falls_back(mock_warning):
    """Test Redis rate limiting is skipped without a username, even with an API token."""
    with (
        patch("redis.Redis.from_url") as mock_from_url,
        patch("metrontagger.talker.mokkari.api") as mock_api_func,
    ):
        Talker(
            "my-token",
            True,
            True,
            redis_url="redis://localhost:6379/0",
        )
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
        mock_from_url.assert_not_called()
    assert "Metron username" in mock_warning.call_args.args[0]


def test_talker_with_redis_url_uses_redis_rate_limiter():
    """Test a reachable Redis URL builds a RedisRateLimiter for the API session."""
    mock_client = Mock()
    with (
        patch("redis.Redis.from_url", return_value=mock_client) as mock_from_url,
        patch("mokkari.redis_rate_limit.RedisRateLimiter") as mock_limiter_cls,
        patch("metrontagger.talker.mokkari.api") as mock_api_func,
    ):
        talker = Talker(
            "my-token", True, True, username="user", redis_url="redis://localhost:6379/0"
        )
        mock_from_url.assert_called_once_with(
            "redis://localhost:6379/0",
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )
        mock_client.ping.assert_called_once_with()
        mock_limiter_cls.assert_called_once_with(mock_client, "user")
        assert mock_api_func.call_args.kwargs["rate_limiter"] is mock_limiter_cls.return_value

        talker.close()
        mock_client.close.assert_called_once_with()


def test_talker_with_redis_url_and_token_keys_by_username():
    """Test the Redis rate limiter is keyed by username, not the API token."""
    with (
        patch("redis.Redis.from_url", return_value=Mock()),
        patch("mokkari.redis_rate_limit.RedisRateLimiter") as mock_limiter_cls,
        patch("metrontagger.talker.mokkari.api"),
    ):
        Talker(
            "my-token",
            True,
            True,
            username="user",
            redis_url="redis://localhost:6379/0",
        )
        assert mock_limiter_cls.call_args.args[1] == "user"


@patch("metrontagger.talker.UIPresenter.print_warning")
def test_talker_with_unreachable_redis_falls_back(mock_warning):
    """Test an unreachable Redis server falls back to the local rate limiter."""
    import redis  # noqa: PLC0415

    mock_client = Mock()
    mock_client.ping.side_effect = redis.ConnectionError("refused")
    with (
        patch("redis.Redis.from_url", return_value=mock_client),
        patch("metrontagger.talker.mokkari.api") as mock_api_func,
    ):
        talker = Talker(
            "my-token", True, True, username="user", redis_url="redis://localhost:1"
        )
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
        mock_client.close.assert_called_once_with()
        assert talker._redis_client is None
    assert "Unable to connect to Redis" in mock_warning.call_args.args[0]


@patch("metrontagger.talker.UIPresenter.print_warning")
def test_talker_with_invalid_redis_url_falls_back(mock_warning):
    """Test an invalid Redis URL falls back to the local rate limiter."""
    with patch("metrontagger.talker.mokkari.api") as mock_api_func:
        Talker("my-token", True, True, username="user", redis_url="bogus://nowhere")
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
    assert "Invalid Redis URL" in mock_warning.call_args.args[0]


@patch("metrontagger.talker.UIPresenter.print_warning")
def test_talker_without_redis_installed_falls_back(mock_warning):
    """Test a missing redis package falls back to the local rate limiter."""
    with (
        patch.dict("sys.modules", {"redis": None}),
        patch("metrontagger.talker.mokkari.api") as mock_api_func,
    ):
        Talker("my-token", True, True, username="user", redis_url="redis://localhost:6379/0")
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
    assert "metron-tagger[redis]" in mock_warning.call_args.args[0]


def test_talker_close_closes_api_session(talker, mock_api):
    """Test close() releases the API session's pooled connections."""
    talker.close()
    mock_api.close.assert_called_once_with()


def test_talker_context_manager_closes_api_session(talker, mock_api):
    """Test using Talker as a context manager closes the API session on exit."""
    with talker as t:
        assert t is talker
        mock_api.close.assert_not_called()
    mock_api.close.assert_called_once_with()


def test_talker_context_manager_closes_api_session_on_error(talker, mock_api):
    """Test the API session is closed even when the body raises."""
    with pytest.raises(RuntimeError), talker:
        raise RuntimeError
    mock_api.close.assert_called_once_with()


def test_talker_create_choice_list():
    """Test creating choice list from matches."""
    matches = [create_mock_base_issue()]
    choices = Talker._create_choice_list(matches)
    assert len(choices) == 2  # 1 match + 1 skip option
    assert choices[-1].title == "Skip"


def test_talker_handle_existing_id_metron():
    """Test handling existing Metron ID."""
    talker = Talker("my-token", True, True)
    result = talker._handle_existing_id(InfoSource.METRON, 123)
    assert result == 123


def test_talker_handle_existing_id_comic_vine(talker):
    """Test handling existing Comic Vine ID."""
    talker.api.issues_list.return_value = [create_mock_base_issue()]
    result = talker._handle_existing_id(InfoSource.COMIC_VINE, 456)
    assert result == 123  # Should return the Metron ID


def test_talker_handle_existing_id_unknown():
    """Test handling unknown source ID."""
    talker = Talker("my-token", True, True)
    result = talker._handle_existing_id(InfoSource.UNKNOWN, 123)
    assert result is None


@patch("metrontagger.talker.Comic")
def test_talker_get_existing_metadata_id_success(mock_comic_class, talker):
    """Test successful extraction of existing metadata ID."""
    mock_comic = Mock()
    mock_comic.has_metadata.side_effect = [True, False]  # Has MetronInfo, not ComicInfo
    mock_md = create_mock_metadata()
    mock_md.modified = datetime(2023, 6, 15, tzinfo=tzinfo)
    mock_comic.read_metadata.return_value = mock_md
    mock_comic_class.return_value = mock_comic

    with patch.object(
        talker.metadata_extractor,
        "get_id_from_metron_info",
        return_value=(InfoSource.METRON, 123),
    ):
        result = talker._get_existing_metadata_id(mock_comic)
        assert result == (InfoSource.METRON, 123, datetime(2023, 6, 15, tzinfo=tzinfo))


@patch("metrontagger.talker.Comic")
def test_talker_get_existing_metadata_id_comic_vine_no_modified(mock_comic_class, talker):
    """Test that Comic Vine source returns None for modified."""
    mock_comic = Mock()
    mock_comic.has_metadata.side_effect = [True, False]
    mock_md = create_mock_metadata()
    mock_md.modified = datetime(2023, 6, 15, tzinfo=tzinfo)
    mock_comic.read_metadata.return_value = mock_md
    mock_comic_class.return_value = mock_comic

    with patch.object(
        talker.metadata_extractor,
        "get_id_from_metron_info",
        return_value=(InfoSource.COMIC_VINE, 456),
    ):
        result = talker._get_existing_metadata_id(mock_comic)
        assert result == (InfoSource.COMIC_VINE, 456, None)


@patch("metrontagger.talker.Comic")
def test_talker_get_existing_metadata_id_no_metadata(mock_comic_class, talker):
    """Test extraction when no metadata exists."""
    mock_comic = Mock()
    mock_comic.has_metadata.return_value = False
    mock_comic_class.return_value = mock_comic

    result = talker._get_existing_metadata_id(mock_comic)
    assert result is None


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_search_by_filename_multiple_matches_skip_enabled(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test search by filename with multiple matches and skip_multiple=True."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    multiple_issues = [
        create_mock_base_issue(123, "hash1"),
        create_mock_base_issue(124, "hash2"),
    ]
    talker.api.issues_list.return_value = multiple_issues

    with patch.object(talker.cover_matcher, "filter_by_hamming_distance", return_value=[]):
        config = ProcessingConfig(skip_multiple=True)
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)

        assert search_result.issue_id is None
        assert search_result.has_multiple_matches is False
        assert len(talker.match_results.skipped_matches) == 1
        assert len(talker.match_results.multiple_matches) == 0


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_search_by_filename_multiple_matches_skip_disabled(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test search by filename with multiple matches and skip_multiple=False."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    multiple_issues = [
        create_mock_base_issue(123, "hash1"),
        create_mock_base_issue(124, "hash2"),
    ]
    talker.api.issues_list.return_value = multiple_issues

    with patch.object(talker.cover_matcher, "filter_by_hamming_distance", return_value=[]):
        config = ProcessingConfig(skip_multiple=False)
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)

        assert search_result.issue_id is None
        assert search_result.has_multiple_matches is True
        assert len(talker.match_results.skipped_matches) == 0
        assert len(talker.match_results.multiple_matches) == 1


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_search_by_filename_single_match_within_hamming_skip_enabled(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test search with single match within hamming distance when skip_multiple=True."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    single_issue = create_mock_base_issue()
    talker.api.issues_list.return_value = [single_issue]

    with patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=True):
        config = ProcessingConfig(skip_multiple=True)
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)

        assert search_result.issue_id == 123
        assert search_result.has_multiple_matches is False
        assert len(talker.match_results.good_matches) == 1
        assert len(talker.match_results.skipped_matches) == 0


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_search_by_filename_single_match_outside_hamming_skip_enabled(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test search with single match outside hamming distance when skip_multiple=True."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    single_issue = create_mock_base_issue()
    talker.api.issues_list.return_value = [single_issue]

    with patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=False):
        config = ProcessingConfig(skip_multiple=True)
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)

        assert search_result.issue_id is None
        assert search_result.has_multiple_matches is False
        assert len(talker.match_results.skipped_matches) == 1
        assert len(talker.match_results.multiple_matches) == 0


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_talker_search_by_filename_single_match(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test search by filename with single match."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    single_issue = create_mock_base_issue()
    talker.api.issues_list.return_value = [single_issue]

    with patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=True):
        config = ProcessingConfig()
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)
        assert search_result.issue_id == 123
        assert search_result.has_multiple_matches is False


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_talker_search_by_filename_no_matches(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test search by filename with no matches."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    talker.api.issues_list.return_value = []

    config = ProcessingConfig()
    search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)
    assert search_result.issue_id is None
    assert search_result.has_multiple_matches is False
    assert len(talker.match_results.no_matches) == 1


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_talker_search_by_filename_multiple_matches(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test search by filename with multiple matches."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    multiple_issues = [create_mock_base_issue(), create_mock_base_issue()]
    talker.api.issues_list.return_value = multiple_issues

    with patch.object(talker.cover_matcher, "filter_by_hamming_distance", return_value=[]):
        config = ProcessingConfig()
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)
        assert search_result.issue_id is None
        assert search_result.has_multiple_matches is True
        assert len(talker.match_results.multiple_matches) == 1


@patch("metrontagger.talker.Comic")
def test_talker_write_metadata_formats_success(mock_comic_class, talker):
    """Test successful metadata writing."""
    mock_comic = Mock()
    mock_comic.write_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    metadata = Metadata()
    result = talker._write_metadata_formats(mock_comic, metadata)

    assert "'ComicInfo.xml'" in result
    assert "'MetronInfo.xml'" in result
    assert len(result) == 2


@patch("metrontagger.talker.Comic")
def test_talker_write_issue_md_success(mock_comic_class, talker, sample_path):
    """Test successful issue metadata writing."""
    mock_comic = Mock()
    mock_comic.get_number_of_pages.return_value = 20
    mock_comic.write_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    with patch("metrontagger.talker.questionary.print") as mock_print:
        talker._write_issue_md(sample_path, 123)
        talker.api.issue.assert_called_once_with(123, if_modified_since=None)
        mock_print.assert_called()
        # Check that success message was printed
        success_calls = [
            call
            for call in mock_print.call_args_list
            if len(call[0]) > 0 and "Writing" in str(call[0][0])
        ]
        assert success_calls


def test_talker_write_issue_md_api_error(talker, sample_path):
    """Test issue metadata writing with API error."""
    talker.api.issue.side_effect = ApiError("API Error")

    with patch("metrontagger.talker.questionary.print") as mock_print:
        talker._write_issue_md(sample_path, 123)
        error_calls = [
            call
            for call in mock_print.call_args_list
            if len(call[0]) > 0 and "Failed to retrieve data" in str(call[0][0])
        ]
        assert error_calls


@patch("metrontagger.talker.Comic")
def test_talker_write_issue_md_with_if_modified_since(mock_comic_class, talker, sample_path):
    """Test issue metadata writing passes if_modified_since to API."""
    mock_comic = Mock()
    mock_comic.get_number_of_pages.return_value = 20
    mock_comic.write_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    modified_dt = datetime(2023, 6, 15, tzinfo=tzinfo)

    with patch("metrontagger.talker.questionary.print"):
        talker._write_issue_md(sample_path, 123, modified=modified_dt)
        talker.api.issue.assert_called_once_with(123, if_modified_since=modified_dt)


def test_talker_write_issue_md_not_modified(talker, sample_path):
    """Test issue metadata writing when API returns 304 Not Modified."""
    talker.api.issue.return_value = None
    modified_dt = datetime(2023, 6, 15, tzinfo=tzinfo)

    with patch("metrontagger.talker.questionary.print") as mock_print:
        talker._write_issue_md(sample_path, 123, modified=modified_dt)
        # Should print info message about not modified
        info_calls = [
            call
            for call in mock_print.call_args_list
            if len(call[0]) > 0 and "not been modified" in str(call[0][0])
        ]
        assert info_calls


def test_talker_write_issue_md_not_modified_no_message_without_modified(talker, sample_path):
    """Test that no info message is printed when modified is None and API returns None."""
    talker.api.issue.return_value = None

    with patch("metrontagger.talker.questionary.print") as mock_print:
        talker._write_issue_md(sample_path, 123)
        # Should NOT print the "not been modified" info message
        info_calls = [
            call
            for call in mock_print.call_args_list
            if len(call[0]) > 0 and "not been modified" in str(call[0][0])
        ]
        assert not info_calls


@patch("metrontagger.talker.Comic")
def test_talker_should_skip_existing_metadata_true(mock_comic_class, talker):
    """Test skipping file with existing metadata."""
    mock_comic = Mock()
    mock_comic.has_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    args = Mock()
    args.ignore_existing = True

    result = talker._should_skip_existing_metadata(args, mock_comic)
    assert result is True


@patch("metrontagger.talker.Comic")
def test_talker_should_skip_existing_metadata_false(mock_comic_class, talker):
    """Test not skipping file without ignore flag."""
    mock_comic = Mock()
    mock_comic.has_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    args = Mock()
    args.ignore_existing = False

    result = talker._should_skip_existing_metadata(args, mock_comic)
    assert result is False


@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.talker.create_print_title")
def test_post_process_matches_displays_skipped(mock_create_title, mock_print, talker):
    """Test that _post_process_matches displays skipped matches."""
    # Add some skipped matches
    talker.match_results.add_skipped_match(Path("skipped1.cbz"))
    talker.match_results.add_skipped_match(Path("skipped2.cbz"))

    mock_create_title.return_value = "Skipped Multiple Matches:"

    talker._post_process_matches()

    # Verify that the title for skipped matches was created
    title_calls = [
        call
        for call in mock_create_title.call_args_list
        if "Skipped Multiple Matches:" in str(call)
    ]
    assert len(title_calls) > 0

    # Verify that skipped files were printed
    print_calls = [str(call) for call in mock_print.call_args_list]
    assert any("skipped1.cbz" in call for call in print_calls)
    assert any("skipped2.cbz" in call for call in print_calls)


@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.talker.create_print_title")
def test_post_process_matches_no_skipped(mock_create_title, talker):
    """Test that _post_process_matches doesn't display skipped section when empty."""
    # Don't add any skipped matches
    talker._post_process_matches()

    # Verify that skipped matches title was not created
    title_calls = [
        call
        for call in mock_create_title.call_args_list
        if "Skipped Multiple Matches:" in str(call)
    ]
    assert len(title_calls) == 0


@patch("metrontagger.talker.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.talker.Comic")
def test_identify_comics_with_skip_multiple_enabled(
    mock_comic_class,
    mock_print,  # noqa: ARG001
    mock_create_title,  # noqa: ARG001
    talker,
):
    """Test identify_comics with skip_multiple flag enabled."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True
    mock_comic.has_metadata.return_value = False
    mock_comic_class.return_value = mock_comic

    args = Mock()
    args.ignore_existing = False
    args.accept_only = False
    args.skip_multiple = True
    args.id = None

    file_list = [Path("test1.cbz"), Path("test2.cbz")]

    with (
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=None, has_multiple_matches=False),
        ) as mock_process,
        patch.object(talker, "_post_process_matches"),
    ):
        talker.identify_comics(args, file_list)

        # Verify _process_file was called with correct ProcessingConfig
        assert mock_process.call_count == 2
        for call in mock_process.call_args_list:
            config = call[0][1]  # ProcessingConfig is the second argument
            assert isinstance(config, ProcessingConfig)
            assert config.accept_only is False
            assert config.skip_multiple is True


@patch("metrontagger.talker.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.talker.Comic")
def test_identify_comics_with_skip_multiple_disabled(
    mock_comic_class,
    mock_print,  # noqa: ARG001
    mock_create_title,  # noqa: ARG001
    talker,
):
    """Test identify_comics with skip_multiple flag disabled."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True
    mock_comic.has_metadata.return_value = False
    mock_comic_class.return_value = mock_comic

    args = Mock()
    args.ignore_existing = False
    args.accept_only = False
    args.skip_multiple = False
    args.id = None

    file_list = [Path("test.cbz")]

    with (
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=None, has_multiple_matches=True),
        ) as mock_process,
        patch.object(talker, "_post_process_matches"),
    ):
        talker.identify_comics(args, file_list)

        # Verify _process_file was called with correct ProcessingConfig
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        config = call_args[0][1]  # ProcessingConfig is the second argument
        assert isinstance(config, ProcessingConfig)
        assert config.accept_only is False
        assert config.skip_multiple is False


@patch("metrontagger.talker.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.talker.Comic")
def test_identify_comics_with_ignore_modified_enabled(
    mock_comic_class,
    mock_print,  # noqa: ARG001
    mock_create_title,  # noqa: ARG001
    talker,
):
    """Test identify_comics wires args.ignore_modified into ProcessingConfig."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True
    mock_comic.has_metadata.return_value = False
    mock_comic_class.return_value = mock_comic

    args = Mock()
    args.ignore_existing = False
    args.accept_only = False
    args.skip_multiple = False
    args.ignore_modified = True
    args.id = None

    file_list = [Path("test.cbz")]

    with (
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=None, has_multiple_matches=True),
        ) as mock_process,
        patch.object(talker, "_post_process_matches"),
    ):
        talker.identify_comics(args, file_list)

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        config = call_args[0][1]  # ProcessingConfig is the second argument
        assert isinstance(config, ProcessingConfig)
        assert config.ignore_modified is True


@patch("metrontagger.talker.questionary.print")
def test_talker_process_file_ignore_modified_drops_date(mock_print, talker):  # noqa: ARG001
    """Test that _process_file drops the modified date when ignore_modified is set."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True

    modified = datetime(2023, 6, 15, tzinfo=tzinfo)

    with (
        patch.object(talker, "_create_comic", return_value=mock_comic),
        patch.object(
            talker,
            "_get_existing_metadata_id",
            return_value=(InfoSource.METRON, 123, modified),
        ),
    ):
        config = ProcessingConfig(ignore_modified=True)
        result = talker._process_file(Path("test.cbz"), config)

    assert result.issue_id == 123
    assert result.modified is None


@patch("metrontagger.talker.questionary.print")
def test_talker_process_file_keeps_modified_by_default(mock_print, talker):  # noqa: ARG001
    """Test that _process_file keeps the modified date when ignore_modified is unset."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True

    modified = datetime(2023, 6, 15, tzinfo=tzinfo)

    with (
        patch.object(talker, "_create_comic", return_value=mock_comic),
        patch.object(
            talker,
            "_get_existing_metadata_id",
            return_value=(InfoSource.METRON, 123, modified),
        ),
    ):
        config = ProcessingConfig()
        result = talker._process_file(Path("test.cbz"), config)

    assert result.issue_id == 123
    assert result.modified == modified


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_skip_multiple_with_accept_only_both_enabled(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test behavior when both skip_multiple and accept_only are enabled."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    single_issue = create_mock_base_issue()
    talker.api.issues_list.return_value = [single_issue]

    with patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=False):
        config = ProcessingConfig(accept_only=True, skip_multiple=True)
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)

        # accept_only should take precedence
        assert search_result.issue_id == 123
        assert search_result.has_multiple_matches is False
        assert len(talker.match_results.good_matches) == 1
        assert len(talker.match_results.skipped_matches) == 0


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_skip_multiple_with_series_id_filter(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test skip_multiple works correctly with series_id filtering."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test", "series_id": "42"}

    multiple_issues = [create_mock_base_issue(123), create_mock_base_issue(124)]
    talker.api.issues_list.return_value = multiple_issues

    with patch.object(talker.cover_matcher, "filter_by_hamming_distance", return_value=[]):
        config = ProcessingConfig(series_id=42, skip_multiple=True)
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)

        assert search_result.issue_id is None
        assert search_result.has_multiple_matches is False
        assert len(talker.match_results.skipped_matches) == 1


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.talker.Comic")
def test_skip_multiple_with_hamming_filter_reduces_to_single(
    mock_comic_class, mock_create_params, mock_comicfn2dict, talker
):
    """Test that hamming distance filtering can reduce multiple matches to single match."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series": "Test"}

    multiple_issues = [
        create_mock_base_issue(123, "hash1"),
        create_mock_base_issue(124, "hash2"),
    ]
    talker.api.issues_list.return_value = multiple_issues

    # Hamming filter returns only one match
    with patch.object(
        talker.cover_matcher, "filter_by_hamming_distance", return_value=[multiple_issues[0]]
    ):
        config = ProcessingConfig(skip_multiple=True)
        search_result = talker._search_by_filename(Path("test.cbz"), mock_comic, config)

        # Should accept the single hamming match even with skip_multiple=True
        assert search_result.issue_id == 123
        assert search_result.has_multiple_matches is False
        assert len(talker.match_results.good_matches) == 1
        assert len(talker.match_results.skipped_matches) == 0


@patch("metrontagger.talker.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.talker.Comic")
def test_talker_identify_comics_success(mock_comic_class, _, mock_create_title, talker):  # noqa: PT019
    """Test successful comic identification."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True
    mock_comic.has_metadata.return_value = False
    mock_comic.get_number_of_pages.return_value = 20
    mock_comic.write_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    args = Mock()
    args.ignore_existing = False
    args.accept_only = False
    args.id = None

    file_list = [Path("test.cbz")]

    with (
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=123, has_multiple_matches=False),
        ),
        patch.object(talker, "_write_issue_md"),
        patch.object(talker, "_post_process_matches"),
    ):
        talker.identify_comics(args, file_list)
        mock_create_title.assert_called()


def test_talker_retrieve_single_issue(talker, sample_path):
    """Test retrieving single issue."""
    with patch.object(talker, "_write_issue_md") as mock_write:
        talker.retrieve_single_issue(123, sample_path)
        mock_write.assert_called_once_with(sample_path, 123)


def test_talker_retrieve_single_issue_prints_rate_limit_status(talker, sample_path):
    """Test that retrieving a single issue also reports the rate limit status."""
    with (
        patch.object(talker, "_write_issue_md"),
        patch.object(talker, "_print_rate_limit_status") as mock_print_rate_limit,
    ):
        talker.retrieve_single_issue(123, sample_path)
        mock_print_rate_limit.assert_called_once()


def test_talker_identify_comics_prints_rate_limit_status(talker):
    """Test that identify_comics reports the rate limit status after processing."""
    args = Mock()
    args.id = None

    with (
        patch.object(talker, "_post_process_matches"),
        patch.object(talker, "_print_rate_limit_status") as mock_print_rate_limit,
    ):
        talker.identify_comics(args, [])
        mock_print_rate_limit.assert_called_once()


def test_talker_print_rate_limit_status(talker):
    """Test that Talker._print_rate_limit_status reads the sustained window from the API."""
    reset = datetime(2026, 7, 21, tzinfo=UTC)
    talker.api.rate_limit_status.sustained.remaining = 4823
    talker.api.rate_limit_status.sustained.limit = 5000
    talker.api.rate_limit_status.sustained.reset = reset

    with patch.object(talker.ui, "print_rate_limit_status") as mock_print:
        talker._print_rate_limit_status()
        mock_print.assert_called_once_with(4823, 5000, reset)


def test_ui_presenter_print_rate_limit_status():
    """Test that the rate limit message is printed when limit data is known."""
    reset = datetime(2026, 7, 21, tzinfo=UTC)
    with patch("metrontagger.talker.questionary.print") as mock_print:
        UIPresenter.print_rate_limit_status(4823, 5000, reset)
        mock_print.assert_called_once()
        assert "4,823/5,000 daily requests remaining" in mock_print.call_args[0][0]


def test_ui_presenter_print_rate_limit_status_without_reset():
    """Test that the message omits the reset time when it isn't known."""
    with patch("metrontagger.talker.questionary.print") as mock_print:
        UIPresenter.print_rate_limit_status(4823, 5000, None)
        mock_print.assert_called_once()
        msg = mock_print.call_args[0][0]
        assert "4,823/5,000 daily requests remaining" in msg
        assert "resets" not in msg


@pytest.mark.parametrize(
    ("remaining", "limit"),
    [
        (None, 5000),
        (4823, None),
        (None, None),
    ],
)
def test_ui_presenter_print_rate_limit_status_unknown(remaining, limit):
    """Test that nothing is printed when the sustained limit isn't known yet."""
    with patch("metrontagger.talker.questionary.print") as mock_print:
        UIPresenter.print_rate_limit_status(remaining, limit, None)
        mock_print.assert_not_called()


# Edge cases and error handling
@patch("metrontagger.talker.comicfn2dict", return_value={})
@patch("metrontagger.talker.create_query_params", return_value=None)
@patch("metrontagger.talker.Comic")
def test_talker_search_by_filename_parse_error(
    mock_comic_class,
    mock_create_params,  # noqa: ARG001
    mock_comicfn2dict,  # noqa: ARG001
    talker,
):
    """Test search by filename with parse error."""
    mock_comic = Mock()
    mock_comic_class.return_value = mock_comic

    config = ProcessingConfig()
    search_result = talker._search_by_filename(Path("unparseable.cbz"), mock_comic, config)
    assert search_result.issue_id is None
    assert search_result.has_multiple_matches is False


@patch("metrontagger.talker.Comic")
def test_talker_process_file_not_writable(mock_comic_class, talker):
    """Test processing file that's not writable."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = False
    mock_comic.seems_to_be_a_comic_archive.return_value = False
    mock_comic_class.return_value = mock_comic

    config = ProcessingConfig()
    search_result = talker._process_file(Path("readonly.cbz"), config)
    assert search_result.issue_id is None
    assert search_result.has_multiple_matches is False


def test_info_source_enum():
    """Test InfoSource enum values."""
    assert InfoSource.METRON.name == "METRON"
    assert InfoSource.COMIC_VINE.name == "COMIC_VINE"
    assert InfoSource.UNKNOWN.name == "UNKNOWN"


# Tests for _handle_api_call method
def test_handle_api_call_success(talker):
    """Test successful API call."""
    mock_call = Mock(return_value="success")
    result = talker._handle_api_call(mock_call)
    assert result == "success"
    mock_call.assert_called_once()


def test_handle_api_call_rate_limit_no_retry_after(talker):
    """Test rate limit error with no retry_after attribute."""
    error = RateLimitError("Rate limit exceeded")
    mock_call = Mock(side_effect=error)

    result = talker._handle_api_call(mock_call)
    assert result is None
    mock_call.assert_called_once()


def test_handle_api_call_rate_limit_zero_retry_after(talker):
    """Test rate limit error with retry_after = 0."""
    error = RateLimitError("Rate limit exceeded", retry_after=0)
    mock_call = Mock(side_effect=error)

    result = talker._handle_api_call(mock_call)
    assert result is None
    mock_call.assert_called_once()


@patch("metrontagger.talker.UIPresenter.print_error")
def test_handle_api_call_redis_error_stops_processing(mock_error, talker):
    """Test a Redis rate limiter error stops further processing."""
    talker._redis_errors = (redis.RedisError,)
    mock_call = Mock(side_effect=redis.ConnectionError("refused"))

    result = talker._handle_api_call(mock_call, "Failed to retrieve data")

    assert result is None
    assert talker._stop_processing is True
    assert "Redis rate limiter error" in mock_error.call_args.args[0]


def test_handle_api_call_redis_error_not_caught_without_redis(talker):
    """Test Redis errors aren't swallowed when no Redis rate limiter is in use."""
    mock_call = Mock(side_effect=redis.ConnectionError("refused"))

    with pytest.raises(redis.ConnectionError):
        talker._handle_api_call(mock_call)


@patch("metrontagger.talker.UIPresenter.print_error")
@patch("metrontagger.talker.time.sleep")
def test_handle_api_call_redis_error_on_retry_stops_processing(mock_sleep, mock_error, talker):
    """Test a Redis error raised while retrying after a rate limit stops processing."""
    talker._redis_errors = (redis.RedisError,)
    error = RateLimitError("Rate limit exceeded", retry_after=30)
    mock_call = Mock(side_effect=[error, redis.ConnectionError("refused")])

    result = talker._handle_api_call(mock_call)

    assert result is None
    assert talker._stop_processing is True
    mock_sleep.assert_called_once_with(32)
    assert "Redis rate limiter error" in mock_error.call_args.args[0]


@patch("metrontagger.talker.UIPresenter.print_error")
@patch("metrontagger.talker.time.sleep")
def test_handle_api_call_redis_error_on_second_retry_stops_processing(
    mock_sleep, mock_error, talker
):
    """Test a Redis error raised on the second short rate-limit retry stops processing."""
    talker._redis_errors = (redis.RedisError,)
    mock_call = Mock(
        side_effect=[
            RateLimitError("Rate limit exceeded", retry_after=30),
            RateLimitError("Rate limit exceeded", retry_after=10),
            redis.ConnectionError("refused"),
        ]
    )

    result = talker._handle_api_call(mock_call)

    assert result is None
    assert talker._stop_processing is True
    assert mock_call.call_count == 3
    assert mock_sleep.call_count == 2
    assert "Redis rate limiter error" in mock_error.call_args.args[0]


@patch("metrontagger.talker.time.sleep")
def test_handle_api_call_rate_limit_short_delay_success(mock_sleep, talker):
    """Test rate limit with short delay (< 60s) that succeeds on retry."""
    error = RateLimitError("Rate limit exceeded", retry_after=30)
    mock_call = Mock(side_effect=[error, "success"])

    result = talker._handle_api_call(mock_call)

    assert result == "success"
    mock_sleep.assert_called_once_with(32)
    assert mock_call.call_count == 2


@patch("metrontagger.talker.time.sleep")
def test_handle_api_call_rate_limit_short_delay_retry_fails(mock_sleep, talker):
    """Test rate limit with short delay (< 60s) that fails on retry."""
    error = RateLimitError("Rate limit exceeded", retry_after=45)
    retry_error = ApiError("API error on retry")
    mock_call = Mock(side_effect=[error, retry_error])

    result = talker._handle_api_call(mock_call)

    assert result is None
    mock_sleep.assert_called_once_with(47)
    assert mock_call.call_count == 2


@patch("metrontagger.talker.questionary.confirm")
@patch("metrontagger.talker.time.sleep")
@patch("metrontagger.talker.time.monotonic")
def test_handle_api_call_rate_limit_long_delay_user_confirms_success(
    mock_monotonic, mock_sleep, mock_confirm, talker
):
    """Test rate limit with long delay (>= 60s) where user confirms and retry succeeds."""
    mock_monotonic.side_effect = [1000.0, 1000.0]  # no time spent answering the prompt
    error = RateLimitError("Rate limit exceeded", retry_after=120)
    mock_call = Mock(side_effect=[error, "success"])
    mock_confirm.return_value.ask.return_value = True

    result = talker._handle_api_call(mock_call)

    assert result == "success"
    mock_sleep.assert_called_once_with(122)
    mock_confirm.assert_called_once()
    assert mock_call.call_count == 2
    assert talker._stop_processing is False


@patch("metrontagger.talker.questionary.confirm")
@patch("metrontagger.talker.time.sleep")
@patch("metrontagger.talker.time.monotonic")
def test_handle_api_call_rate_limit_long_delay_user_confirms_retry_fails(
    mock_monotonic, mock_sleep, mock_confirm, talker
):
    """Test rate limit with long delay (>= 60s) where user confirms but retry fails."""
    mock_monotonic.side_effect = [1000.0, 1000.0]  # no time spent answering the prompt
    error = RateLimitError("Rate limit exceeded", retry_after=90)
    retry_error = RateLimitError("Still rate limited")
    mock_call = Mock(side_effect=[error, retry_error])
    mock_confirm.return_value.ask.return_value = True

    result = talker._handle_api_call(mock_call)

    assert result is None
    mock_sleep.assert_called_once_with(92)
    mock_confirm.assert_called_once()
    assert mock_call.call_count == 2
    assert talker._stop_processing is False


@patch("metrontagger.talker.questionary.confirm")
@patch("metrontagger.talker.time.sleep")
@patch("metrontagger.talker.time.monotonic")
def test_handle_api_call_rate_limit_long_delay_deducts_time_spent_answering(
    mock_monotonic, mock_sleep, mock_confirm, talker
):
    """Time spent waiting for the user's answer is deducted from the retry sleep."""
    # 35 seconds pass between when retry_after is known and when the user answers.
    mock_monotonic.side_effect = [1000.0, 1035.0]
    error = RateLimitError("Rate limit exceeded", retry_after=120)
    mock_call = Mock(side_effect=[error, "success"])
    mock_confirm.return_value.ask.return_value = True

    result = talker._handle_api_call(mock_call)

    assert result == "success"
    # 120 - 35 elapsed + 2s buffer = 87
    mock_sleep.assert_called_once_with(87)


@patch("metrontagger.talker.questionary.confirm")
@patch("metrontagger.talker.time.sleep")
@patch("metrontagger.talker.time.monotonic")
def test_handle_api_call_rate_limit_long_delay_answer_exceeds_retry_after(
    mock_monotonic, mock_sleep, mock_confirm, talker
):
    """If the user takes longer than retry_after to answer, don't sleep a negative amount."""
    # 150 seconds pass, more than the 120s retry_after.
    mock_monotonic.side_effect = [1000.0, 1150.0]
    error = RateLimitError("Rate limit exceeded", retry_after=120)
    mock_call = Mock(side_effect=[error, "success"])
    mock_confirm.return_value.ask.return_value = True

    result = talker._handle_api_call(mock_call)

    assert result == "success"
    # elapsed already exceeds retry_after, so only the buffer remains
    mock_sleep.assert_called_once_with(2)


@patch("metrontagger.talker.questionary.confirm")
def test_handle_api_call_rate_limit_long_delay_user_declines(mock_confirm, talker):
    """Test rate limit with long delay (>= 60s) where user declines to wait."""
    error = RateLimitError("Rate limit exceeded", retry_after=300)
    mock_call = Mock(side_effect=error)
    mock_confirm.return_value.ask.return_value = False

    result = talker._handle_api_call(mock_call)

    assert result is None
    mock_confirm.assert_called_once()
    assert mock_call.call_count == 1
    assert talker._stop_processing is True


def test_handle_api_call_api_error(talker):
    """Test handling of ApiError."""
    error = ApiError("API error occurred")
    mock_call = Mock(side_effect=error)

    result = talker._handle_api_call(mock_call, error_context="Test API call")

    assert result is None
    mock_call.assert_called_once()
    assert talker._stop_processing is False


@pytest.mark.parametrize("status_code", [400, 401])
def test_handle_api_call_fatal_http_error_stops_processing(talker, status_code):
    """A 400 or 401 response should stop further tagging, not just this call."""
    error = create_http_api_error(status_code)
    mock_call = Mock(side_effect=error)

    result = talker._handle_api_call(mock_call, error_context="Test API call")

    assert result is None
    assert talker._stop_processing is True


@pytest.mark.parametrize("status_code", [403, 404, 500, 503])
def test_handle_api_call_non_fatal_http_error_does_not_stop_processing(talker, status_code):
    """Other HTTP errors are logged but shouldn't halt processing of remaining files."""
    error = create_http_api_error(status_code)
    mock_call = Mock(side_effect=error)

    result = talker._handle_api_call(mock_call, error_context="Test API call")

    assert result is None
    assert talker._stop_processing is False


def test_get_http_status_code_from_chained_http_error(talker):
    """Status code is recovered from the HTTPError that ApiError was raised from."""
    error = create_http_api_error(401)
    assert talker._get_http_status_code(error) == 401


def test_get_http_status_code_without_cause_returns_none(talker):
    """An ApiError with no chained HTTPError (e.g. JSON decode failure) has no status code."""
    error = ApiError("Invalid JSON response")
    assert talker._get_http_status_code(error) is None


# Tests for _retry_api_call method
def test_retry_api_call_success(talker):
    """Test successful retry."""
    mock_call = Mock(return_value="retry success")
    result = talker._retry_api_call(mock_call)
    assert result == "retry success"
    mock_call.assert_called_once()


def test_retry_api_call_rate_limit_error(talker):
    """Test retry that fails with RateLimitError."""
    error = RateLimitError("Still rate limited")
    mock_call = Mock(side_effect=error)

    result = talker._retry_api_call(mock_call)
    assert result is None
    mock_call.assert_called_once()


def test_retry_api_call_api_error(talker):
    """Test retry that fails with ApiError."""
    error = ApiError("API error")
    mock_call = Mock(side_effect=error)

    result = talker._retry_api_call(mock_call)
    assert result is None
    mock_call.assert_called_once()
    assert talker._stop_processing is False


def test_retry_api_call_fatal_http_error_stops_processing(talker):
    """A 401 hit during a retry should also stop further processing."""
    error = create_http_api_error(401)
    mock_call = Mock(side_effect=error)

    result = talker._retry_api_call(mock_call)
    assert result is None
    assert talker._stop_processing is True


@patch("metrontagger.talker.time.sleep")
def test_retry_api_call_fatal_http_error_after_short_rate_limit_wait(mock_sleep, talker):
    """A fatal error hit on the second attempt (after a short rate-limit wait) also stops."""
    rate_limit_error = RateLimitError("Rate limit exceeded", retry_after=10)
    fatal_error = create_http_api_error(400)
    mock_call = Mock(side_effect=[rate_limit_error, fatal_error])

    result = talker._retry_api_call(mock_call)

    assert result is None
    assert talker._stop_processing is True
    assert mock_call.call_count == 2
    mock_sleep.assert_called_once_with(12)


# Cover-first search
BOBA_FETT = Path("Star Wars - The Book of Boba Fett 005 (2027) (Digital).cbz")
BOBA_FETT_SERIES = "Star Wars: The Book of Boba Fett"
SEARCH_HASH = hex_to_hash("0000000000000000")


def hash_at_distance(bits: int) -> str:
    """A cover hash exactly `bits` bits from SEARCH_HASH."""
    return f"{(1 << bits) - 1:016x}"


def test_get_search_hashes_single_cover():
    """A single cover is searched by its full-cover hash, at the cover-search limit."""
    with patch.object(
        CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=("full",)
    ):
        assert CoverHashMatcher.get_search_hashes(Mock()) == (("full", COVER_ACCEPT_DISTANCE),)


def test_get_search_hashes_double_spread():
    """A spread is searched by its right then left half, then as a whole.

    The halves are held to the half-cover limit, since one of them is the back
    cover. The whole cover comes last in case it's a genuinely landscape single cover.
    """
    with patch.object(
        CoverHashMatcher,
        "get_comic_cover_hashes_cached",
        return_value=("full", "right", "left"),
    ):
        assert CoverHashMatcher.get_search_hashes(Mock()) == (
            ("right", HALF_COVER_HAMMING_DISTANCE),
            ("left", HALF_COVER_HAMMING_DISTANCE),
            ("full", COVER_ACCEPT_DISTANCE),
        )


def test_get_search_hashes_no_cover():
    """No hashes when the cover can't be hashed."""
    with patch.object(CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=()):
        assert CoverHashMatcher.get_search_hashes(Mock()) == ()


def test_cover_search_params_defaults_issue_to_one():
    """A filename without an issue number is searched as #1, like the filename search."""
    params = Talker._cover_search_params({"year": "2026"}, None)
    assert params is not None
    assert params["number"] == "1"


def test_cover_search_params():
    """The filename's number and a year either side of its year narrow the search."""
    params = Talker._cover_search_params({"issue": "005", "year": "2027"}, None)
    assert params == {
        "number": "5",
        "cover_date_range_after": "2026-01-01",
        "cover_date_range_before": "2028-12-31",
        "cover_hash_max_distance": COVER_SEARCH_MAX_DISTANCE,
    }


@pytest.mark.parametrize("metadata", [{"issue": "150", "year": "2016"}, {"issue": "150"}])
def test_cover_search_params_series_id(metadata):
    """A given series id replaces the year range, which may be the series' start year."""
    assert Talker._cover_search_params(metadata, 42) == {
        "number": "150",
        "series_id": 42,
        "cover_hash_max_distance": COVER_SEARCH_MAX_DISTANCE,
    }


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param({"issue": "5"}, id="no-year"),
        pytest.param({"issue": "5", "year": "20xx"}, id="bad-year"),
        pytest.param({"issue": "5", "year": "0000"}, id="implausible-year"),
        pytest.param({"issue": "5", "year": "3020"}, id="future-year"),
        pytest.param({"issue": "5", "year": "20\u00b2\u00b2"}, id="non-ascii-digits"),
    ],
)
def test_cover_search_params_missing_fields(metadata):
    """Without a plausible four-digit year, the cover search isn't used."""
    assert Talker._cover_search_params(metadata, None) is None


def test_rank_by_distance():
    """Issues are ranked closest first; ones without a valid hash are dropped."""
    far = create_mock_base_issue(1, hash_at_distance(12))
    near = create_mock_base_issue(2, hash_at_distance(2))
    invalid = [
        create_mock_base_issue(3, ""),
        create_mock_base_issue(4, "zzzzzzzzzzzzzzzz"),
        # Valid hex of another size raises TypeError rather than ValueError.
        create_mock_base_issue(5, "abcd"),
        create_mock_base_issue(6, "0" * 64),
    ]
    ranked = CoverHashMatcher.rank_by_distance(SEARCH_HASH, [far, *invalid, near])
    assert [(d, i.id) for d, i in ranked] == [(2, 2), (12, 1)]


def cover_issue(issue_id: int, bits: int, series_name: str = BOBA_FETT_SERIES):
    """A search result whose cover is `bits` from SEARCH_HASH, in the filename's series."""
    return create_mock_base_issue(issue_id, hash_at_distance(bits), series_name)


def search_by_cover(talker, results, config=None, hashes=(SEARCH_HASH,), filename=BOBA_FETT):
    """Run _search_by_cover with the API returning `results` (a list per request).

    Each of `hashes` is a hash (searched as a whole cover) or a (hash, limit) pair.
    """
    talker.api.issues_list.side_effect = results
    parsed = comicfn2dict(filename, verbose=0)
    search_hashes = tuple(
        h if isinstance(h, tuple) else (h, COVER_ACCEPT_DISTANCE) for h in hashes
    )
    with patch.object(talker.cover_matcher, "get_search_hashes", return_value=search_hashes):
        return talker._search_by_cover(filename, Mock(), config or ProcessingConfig(), parsed)


def test_search_by_cover_accepts_clear_closest_match(talker):
    """The Boba Fett case: the closest issue is 16 bits off but clear of the next."""
    issue = cover_issue(185209, 16)
    other = cover_issue(171897, 16 + COVER_ACCEPT_MARGIN)
    result = search_by_cover(talker, [[other, issue]])

    assert result == CoverMatches(accepted=issue)
    # The cover search only reports; _process_file records the outcome.
    assert not talker.match_results.has_results
    talker.api.issues_list.assert_called_once_with(
        params={
            "number": "5",
            "cover_date_range_after": "2026-01-01",
            "cover_date_range_before": "2028-12-31",
            "cover_hash_max_distance": COVER_SEARCH_MAX_DISTANCE,
            "cover_hash_near": str(SEARCH_HASH),
        }
    )


@pytest.mark.parametrize(
    ("distances", "reason"),
    [
        ((4, 4 + COVER_ACCEPT_MARGIN - 1), "runner-up too close"),
        ((COVER_ACCEPT_DISTANCE + 1,), "too far"),
    ],
)
def test_search_by_cover_candidates_when_not_clear(talker, distances, reason):
    """Results that are too far or too close together are candidates, closest first."""
    issues = [cover_issue(i, d) for i, d in enumerate(distances)]
    result = search_by_cover(talker, [list(reversed(issues))])

    assert result == CoverMatches(candidates=issues), reason


def test_search_by_cover_accept_only_keeps_distance_limit(talker):
    """--accept-only doesn't accept a lone cover result beyond COVER_ACCEPT_DISTANCE.

    The filename search applies --accept-only to its own series and number match.
    """
    issue = cover_issue(7, COVER_ACCEPT_DISTANCE + 2)
    result = search_by_cover(talker, [[issue]], ProcessingConfig(accept_only=True))

    assert result == CoverMatches(candidates=[issue])


def test_search_by_cover_accept_only_needs_series_agreement(talker):
    """--accept-only doesn't accept a lone result from an unrelated series."""
    wrong = cover_issue(161431, 16, "Monster High: Boomuda Triangle")
    filename = Path("Punisher - Red Band 003 (2026) (c2c).cbz")
    config = ProcessingConfig(accept_only=True)
    result = search_by_cover(talker, [[wrong]], config, filename=filename)

    # Not accepted, and not offered either: its series disagrees.
    assert result == CoverMatches()


def test_search_by_cover_tries_left_half_of_spread(talker):
    """For a spread, the left half is searched when the right half finds nothing."""
    left = hex_to_hash(hash_at_distance(8))
    issue = cover_issue(9, 8)
    result = search_by_cover(talker, [[], [issue]], hashes=(SEARCH_HASH, left))

    assert result == CoverMatches(accepted=issue)
    assert talker.api.issues_list.call_count == 2


def test_search_by_cover_no_results(talker):
    """No cover match gives nothing to accept and no candidates."""
    assert search_by_cover(talker, [[]]) == CoverMatches()


def test_search_by_cover_api_error_keeps_earlier_candidates(talker):
    """An API error ends the search but keeps what earlier hashes found."""
    far = cover_issue(1, COVER_ACCEPT_DISTANCE + 2)
    left = hex_to_hash(hash_at_distance(1))
    with patch.object(talker, "_handle_api_call", side_effect=[[far], None]):
        result = search_by_cover(talker, [], hashes=(SEARCH_HASH, left))
    assert result == CoverMatches(candidates=[far])


@pytest.mark.parametrize(
    ("filename", "hashes"),
    [
        pytest.param(Path("Star Wars 005.cbz"), (SEARCH_HASH,), id="no-year"),
        pytest.param(BOBA_FETT, (), id="no-cover-hash"),
    ],
)
def test_search_by_cover_skipped(talker, filename, hashes):
    """Without a year or a cover hash, no cover search request is made."""
    assert search_by_cover(talker, [], hashes=hashes, filename=filename) == CoverMatches()
    talker.api.issues_list.assert_not_called()


def make_writable_comic():
    comic = Mock()
    comic.is_writable.return_value = True
    comic.seems_to_be_a_comic_archive.return_value = True
    return comic


def process_file(talker, cover, config=None):
    """Run _process_file with the cover search returning `cover`."""
    with (
        patch.object(talker, "_create_comic", return_value=make_writable_comic()),
        patch.object(talker, "_get_existing_metadata_id", return_value=None),
        patch.object(talker, "_search_by_cover", return_value=cover),
        patch.object(talker, "_search_by_filename") as by_filename,
    ):
        result = talker._process_file(BOBA_FETT, config or ProcessingConfig())
    return result, by_filename


def test_process_file_uses_cover_search_first(talker):
    """An accepted cover match is recorded without running the filename search."""
    issue = cover_issue(1, 0)
    result, by_filename = process_file(talker, CoverMatches(accepted=issue))

    assert result == SearchResult(issue_id=1, has_multiple_matches=False)
    assert talker.match_results.good_matches == [BOBA_FETT]
    by_filename.assert_not_called()


def test_process_file_falls_back_with_cover_candidates(talker):
    """Without an accepted cover match, the filename search runs with the candidates."""
    candidate = cover_issue(1, COVER_ACCEPT_DISTANCE + 2)
    result, by_filename = process_file(talker, CoverMatches(candidates=[candidate]))

    assert result is by_filename.return_value
    assert by_filename.call_args.args[4] == [candidate]


def test_process_file_stops_after_fatal_cover_error(talker):
    """A fatal API error in the cover search doesn't go on to the filename search."""
    talker._stop_processing = True
    result, by_filename = process_file(talker, CoverMatches())

    assert result == SearchResult(issue_id=None, has_multiple_matches=False)
    by_filename.assert_not_called()


def test_search_by_cover_prompts_when_series_disagrees(talker):
    """A close, clear cover from an unrelated series isn't accepted.

    A CGC-slab photo of Punisher: Red Band #3 was closest to Monster High #3's cover.
    """
    wrong = cover_issue(161431, 16, "Monster High: Boomuda Triangle")
    right = cover_issue(156898, 20, "Punisher: Red Band")
    filename = Path("Punisher - Red Band 003 (2026) (c2c).cbz")
    result = search_by_cover(talker, [[right, wrong]], filename=filename)

    # Only the candidate whose series agrees is offered.
    assert result == CoverMatches(candidates=[right])


@pytest.mark.parametrize(
    ("metadata", "series_name", "expected"),
    [
        pytest.param(
            {"series": "Star Wars", "title": "The Book of Boba Fett"},
            BOBA_FETT_SERIES,
            True,
            id="series-split-from-title",
        ),
        pytest.param(
            {"series": "Ghost Rider"}, "Ghost Rider: Kushala", True, id="shared-word"
        ),
        pytest.param({"series": "Pokémon"}, "Pokemon Adventures", True, id="accents"),
        pytest.param({"series": "Punisher - Red Band"}, "Monster High", False, id="unrelated"),
        pytest.param({"series": "The Flash"}, "The Boys", False, id="stop-words-only"),
        pytest.param({}, BOBA_FETT_SERIES, False, id="no-series"),
    ],
)
def test_series_agrees(metadata, series_name, expected):
    """The issue's series must share a distinctive word with the filename's series/title."""
    issue = create_mock_base_issue(series_name=series_name)
    assert Talker._series_agrees(metadata, issue) is expected


@pytest.mark.parametrize(
    ("filename_series", "series_name"),
    [("Iron Man", "The Amazing Spider-Man"), ("X-Factor", "X-Men")],
)
def test_series_agrees_ignores_parts_of_hyphenated_names(filename_series, series_name):
    """Sharing "man" or "x" from a hyphenated name doesn't make two series agree."""
    issue = create_mock_base_issue(series_name=series_name)
    assert Talker._series_agrees({"series": filename_series}, issue) is False


def test_process_file_parses_filename_once(talker):
    """The filename is parsed once and shared by the cover and filename searches."""
    parsed = {"series": "Test", "issue": "1", "year": "2026"}
    with (
        patch.object(talker, "_create_comic", return_value=make_writable_comic()),
        patch.object(talker, "_get_existing_metadata_id", return_value=None),
        patch("metrontagger.talker.comicfn2dict", return_value=parsed) as parse,
        patch.object(talker, "_search_by_cover", return_value=CoverMatches()) as by_cover,
        patch.object(talker, "_search_by_filename") as by_filename,
    ):
        talker._process_file(BOBA_FETT, ProcessingConfig())

    parse.assert_called_once()
    assert by_cover.call_args.args[3] is parsed
    assert by_filename.call_args.args[3] is parsed


def test_select_choice_keeps_given_order(talker):
    """The prompt shows matches in the order given (closest cover first)."""
    later = create_mock_base_issue(1)
    later.cover_date = datetime(2026, 5, 1, tzinfo=tzinfo).date()
    earlier = create_mock_base_issue(2)
    earlier.cover_date = datetime(2025, 1, 1, tzinfo=tzinfo).date()
    with (
        patch.object(talker.ui, "print_multiple_match_prompt"),
        patch("metrontagger.talker.questionary.select") as select,
    ):
        talker._select_choice_from_matches(BOBA_FETT, [later, earlier])

    values = [choice.value for choice in select.call_args.kwargs["choices"]]
    assert values == [1, 2, ""]


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
def test_search_by_filename_multiple_matches_sorted_by_cover_date(
    mock_create_params, mock_comicfn2dict, talker
):
    """Filename search matches are still offered in cover-date order."""
    mock_comicfn2dict.return_value = {"series": "Test", "issue": "1"}
    mock_create_params.return_value = {"series_q": "Test", "number": "1"}
    later = create_mock_base_issue(1)
    later.cover_date = datetime(2026, 5, 1, tzinfo=tzinfo).date()
    earlier = create_mock_base_issue(2)
    earlier.cover_date = datetime(2025, 1, 1, tzinfo=tzinfo).date()
    talker.api.issues_list.return_value = [later, earlier]

    with patch.object(talker.cover_matcher, "filter_by_hamming_distance", return_value=[]):
        talker._search_by_filename(Path("test.cbz"), Mock(), ProcessingConfig())

    assert talker.match_results.multiple_matches[0].matches == [earlier, later]


@pytest.mark.parametrize(
    ("accepted_id", "skip_multiple", "expected", "outcome"),
    [
        (2, False, SearchResult(issue_id=2, has_multiple_matches=False), "good"),
        (2, True, SearchResult(issue_id=2, has_multiple_matches=False), "good"),
        (None, True, SearchResult(issue_id=None, has_multiple_matches=False), "skipped"),
        (None, False, SearchResult(issue_id=None, has_multiple_matches=True), "multiple"),
    ],
)
def test_resolve_search(talker, accepted_id, skip_multiple, expected, outcome):
    """An accepted issue wins; otherwise the comic is skipped or its candidates kept."""
    candidates = [create_mock_base_issue(1), create_mock_base_issue(2)]
    accepted = candidates[1] if accepted_id else None
    config = ProcessingConfig(skip_multiple=skip_multiple)

    assert talker._resolve_search(BOBA_FETT, accepted, candidates, config) == expected
    results = talker.match_results
    assert results.good_matches == ([BOBA_FETT] if outcome == "good" else [])
    assert results.skipped_matches == ([BOBA_FETT] if outcome == "skipped" else [])
    expected_multiple = [MultipleMatch(BOBA_FETT, candidates)] if outcome == "multiple" else []
    assert results.multiple_matches == expected_multiple


def test_search_by_cover_tries_left_half_after_unaccepted_right_half(talker):
    """A spread's left half is still searched when the right half's results are rejected.

    For a right-to-left book, the right half is the back cover and can pull in
    unrelated covers; the left half is the front cover.
    """
    left = hex_to_hash(hash_at_distance(8))
    unrelated = cover_issue(1, 4, "Some Other Series")
    issue = cover_issue(9, 8)
    result = search_by_cover(talker, [[unrelated], [issue]], hashes=(SEARCH_HASH, left))

    assert result == CoverMatches(accepted=issue)
    assert talker.api.issues_list.call_count == 2


def test_search_by_cover_candidates_from_every_hash(talker):
    """If no hash gives an accepted match, all results are candidates, closest first."""
    left = hex_to_hash(hash_at_distance(1))
    far = cover_issue(1, COVER_ACCEPT_DISTANCE + 2)
    near = cover_issue(2, COVER_ACCEPT_DISTANCE + 1)
    # The left half sees `far` again (now 1 bit closer); it's listed once.
    result = search_by_cover(talker, [[far], [near, far]], hashes=(SEARCH_HASH, left))

    assert result == CoverMatches(candidates=[near, far])


def test_search_by_cover_series_id_skips_series_check(talker):
    """With --id, a match isn't rejected because the filename's series name differs."""
    issue = cover_issue(300, 0, "The Amazing Spider-Man")
    config = ProcessingConfig(series_id=42)
    result = search_by_cover(talker, [[issue]], config, filename=Path("ASM 300 (1988).cbz"))

    assert result == CoverMatches(accepted=issue)


def test_search_by_cover_only_invalid_hashes_falls_back(talker):
    """If no result has a usable cover hash, there are no candidates to offer."""
    invalid = create_mock_base_issue(2, "abcd", BOBA_FETT_SERIES)
    assert search_by_cover(talker, [[invalid]]) == CoverMatches()


def search_by_filename(talker, results, cover_candidates, config=None, params=None):
    """Run _search_by_filename with the API returning `results` and cover candidates."""
    if params is None:
        params = {"series_q": "Test", "number": "1"}
    talker.api.issues_list.return_value = results
    with (
        patch("metrontagger.talker.create_query_params", return_value=params),
        patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=False),
        patch.object(talker.cover_matcher, "filter_by_hamming_distance", return_value=[]),
    ):
        return talker._search_by_filename(
            BOBA_FETT, Mock(), config or ProcessingConfig(), {}, cover_candidates
        )


def test_search_by_filename_accept_only_after_rejected_cover(talker):
    """--accept-only still takes a lone filename match the cover search couldn't accept.

    For example, "ASM 300" shares no words with "The Amazing Spider-Man".
    """
    cover_candidate = cover_issue(1, 2, "The Amazing Spider-Man")
    match = create_mock_base_issue(1)
    config = ProcessingConfig(accept_only=True)
    result = search_by_filename(talker, [match], [cover_candidate], config)

    assert result == SearchResult(issue_id=1, has_multiple_matches=False)
    assert talker.match_results.good_matches == [BOBA_FETT]


def test_search_by_filename_offers_cover_candidates_first(talker):
    """Without a filename match, cover candidates come first, then new filename results."""
    cover_a, cover_b = cover_issue(1, 4), cover_issue(2, 6)
    later = create_mock_base_issue(3)
    later.cover_date = datetime(2026, 5, 1, tzinfo=tzinfo).date()
    earlier = create_mock_base_issue(4)
    earlier.cover_date = datetime(2025, 1, 1, tzinfo=tzinfo).date()
    # The filename search also finds cover_b; it's listed once.
    result = search_by_filename(talker, [later, cover_b, earlier], [cover_a, cover_b])

    assert result == SearchResult(issue_id=None, has_multiple_matches=True)
    expected = [cover_a, cover_b, earlier, later]
    assert talker.match_results.multiple_matches == [MultipleMatch(BOBA_FETT, expected)]


@pytest.mark.parametrize(
    ("results", "params"),
    [
        pytest.param([], {"series_q": "Test", "number": "1"}, id="no-filename-results"),
        pytest.param(None, None, id="unparsable-filename"),
    ],
)
def test_search_by_filename_falls_back_to_cover_candidates(talker, results, params):
    """If the filename search finds nothing, the cover candidates are still offered."""
    candidate = cover_issue(1, COVER_ACCEPT_DISTANCE + 2)
    with patch("metrontagger.talker.create_query_params", return_value=params):
        talker.api.issues_list.return_value = results
        result = talker._search_by_filename(
            BOBA_FETT, Mock(), ProcessingConfig(), {}, [candidate]
        )

    assert result == SearchResult(issue_id=None, has_multiple_matches=True)
    assert talker.match_results.multiple_matches == [MultipleMatch(BOBA_FETT, [candidate])]
    assert not talker.match_results.no_matches


def test_search_by_filename_api_error_offers_cover_candidates(talker):
    """A non-fatal API error in the filename search still offers the cover candidates."""
    candidate = cover_issue(1, COVER_ACCEPT_DISTANCE + 2)
    with (
        patch("metrontagger.talker.create_query_params", return_value={"number": "1"}),
        patch.object(talker, "_handle_api_call", return_value=None),
    ):
        result = talker._search_by_filename(
            BOBA_FETT, Mock(), ProcessingConfig(), {}, [candidate]
        )

    assert result == SearchResult(issue_id=None, has_multiple_matches=True)


def test_search_by_filename_skips_only_after_both_searches(talker):
    """With --skip-multiple, a comic is skipped only once neither search accepts a match."""
    candidate = cover_issue(1, 4)
    config = ProcessingConfig(skip_multiple=True)
    result = search_by_filename(talker, [create_mock_base_issue(2)], [candidate], config)

    assert result == SearchResult(issue_id=None, has_multiple_matches=False)
    assert talker.match_results.skipped_matches == [BOBA_FETT]


@pytest.mark.parametrize(
    ("metron_hash", "expected"),
    [
        (hash_at_distance(5), 5),
        (None, None),
        ("", None),
        ("zzzzzzzzzzzzzzzz", None),
        ("abcd", None),  # a different size raises TypeError
    ],
)
def test_cover_hash_distance(metron_hash, expected):
    """The distance is None when the Metron hash can't be compared."""
    assert CoverHashMatcher.distance(SEARCH_HASH, metron_hash) == expected


def test_is_within_hamming_distance_wrong_size_hash():
    """A Metron hash of another size doesn't match, rather than raising TypeError."""
    with patch.object(
        CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=(SEARCH_HASH,)
    ):
        assert CoverHashMatcher.is_within_hamming_distance(Mock(), "abcd") is False


def test_search_by_cover_drops_unrelated_candidates(talker):
    """Same-number covers from unrelated series aren't offered for a comic not on Metron."""
    unrelated = [cover_issue(1, 19, "Hit Comics"), cover_issue(2, 20, "Conan & Dragonero")]
    assert search_by_cover(talker, [unrelated]) == CoverMatches()


def test_search_by_cover_series_id_keeps_all_candidates(talker):
    """With --id every candidate is offered, since the search is limited to that series."""
    far = cover_issue(1, COVER_ACCEPT_DISTANCE + 2, "The Amazing Spider-Man")
    config = ProcessingConfig(series_id=42)
    result = search_by_cover(talker, [[far]], config, filename=Path("ASM 300 (1988).cbz"))
    assert result == CoverMatches(candidates=[far])


def test_search_by_cover_after_fatal_error(talker):
    """No cover search request is made after a fatal error for this comic."""
    talker._stop_processing = True
    assert search_by_cover(talker, [[cover_issue(1, 0)]]) == CoverMatches()
    talker.api.issues_list.assert_not_called()


@pytest.mark.parametrize(
    ("bits", "accepted"),
    [(HALF_COVER_HAMMING_DISTANCE, True), (HALF_COVER_HAMMING_DISTANCE + 2, False)],
)
def test_search_by_cover_half_cover_limit(talker, bits, accepted):
    """A match on a spread's half is only accepted within the half-cover limit."""
    issue = cover_issue(1, bits)
    half = (SEARCH_HASH, HALF_COVER_HAMMING_DISTANCE)
    result = search_by_cover(talker, [[issue]], hashes=(half,))

    expected = CoverMatches(accepted=issue) if accepted else CoverMatches(candidates=[issue])
    assert result == expected
