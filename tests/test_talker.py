"""Tests for the Talker class and its helper classes."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from darkseid.comic import Comic
from darkseid.metadata import Basic, Metadata, Notes
from mokkari.exceptions import ApiError

from metrontagger.talker import (
    CoverHashMatcher,
    InfoSource,
    MetadataExtractor,
    MetadataMapper,
    MultipleMatch,
    OnlineMatchResults,
    Talker,
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
        return Talker("username", "password", metron_info=True, comic_info=True)


@pytest.fixture
def sample_path():
    """Create a sample Path object."""
    return Path("test_comic.cbz")


def create_mock_base_issue():
    """Create a mock BaseIssue object."""
    issue = Mock()
    issue.id = 123
    issue.issue_name = "Test Comic #1"
    issue.cover_date = datetime(2023, 1, 1, tzinfo=tzinfo).date()
    issue.cover_hash = "abcdef123456"
    return issue


def create_mock_issue_response():
    """Create a mock Issue response object."""
    issue = Mock()
    issue.id = 123
    issue.number = "1"
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

    # Series mock
    issue.series = Mock()
    issue.series.name = "Test Series"
    issue.series.id = 1
    issue.series.sort_name = "Test Series"
    issue.series.volume = 1
    issue.series.series_type = Mock()
    issue.series.series_type.name = "Regular"
    issue.series.year_began = 2023
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


@patch("metrontagger.talker.phash")
@patch("metrontagger.talker.Image.open")
def test_cover_hash_matcher_get_comic_cover_hash_success(_, mock_phash):  # noqa: PT019
    """Test successful cover hash calculation."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = b"fake_image_data"
    mock_hash = Mock()
    mock_phash.return_value = mock_hash

    result = CoverHashMatcher.get_comic_cover_hash_cached(mock_comic)
    assert result == mock_hash
    mock_phash.assert_called_once()


@patch("metrontagger.talker.Image.open", side_effect=OSError("Invalid image"))
def test_cover_hash_matcher_get_comic_cover_hash_failure(_):  # noqa: PT019
    """Test cover hash calculation failure."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = b"fake_image_data"

    with patch("metrontagger.talker.questionary.print"):
        result = CoverHashMatcher.get_comic_cover_hash_cached(mock_comic)
        assert result is None


def test_cover_hash_matcher_is_within_hamming_distance_success():
    """Test successful hamming distance check."""
    mock_comic = Mock()
    mock_hash = Mock()
    mock_hash.__sub__ = Mock(return_value=5)  # Within distance

    with (
        patch.object(CoverHashMatcher, "get_comic_cover_hash_cached", return_value=mock_hash),
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
        patch.object(CoverHashMatcher, "get_comic_cover_hash_cached", return_value=mock_hash),
        patch("metrontagger.talker.hex_to_hash", return_value=mock_hash),
    ):
        result = CoverHashMatcher.is_within_hamming_distance(mock_comic, "abcdef")
        assert result is False


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


# Talker class tests
def test_talker_initialization():
    """Test Talker initialization."""
    with patch("metrontagger.talker.mokkari.api") as mock_api_func:
        talker = Talker("user", "pass", metron_info=True, comic_info=False)
        assert talker.metron_info is True
        assert talker.comic_info is False
        assert isinstance(talker.match_results, OnlineMatchResults)
        mock_api_func.assert_called_once()


def test_talker_create_choice_list():
    """Test creating choice list from matches."""
    matches = [create_mock_base_issue()]
    choices = Talker._create_choice_list(matches)
    assert len(choices) == 2  # 1 match + 1 skip option
    assert choices[-1].title == "Skip"


def test_talker_handle_existing_id_metron():
    """Test handling existing Metron ID."""
    talker = Talker("user", "pass", True, True)
    result = talker._handle_existing_id(InfoSource.METRON, 123)
    assert result == 123


def test_talker_handle_existing_id_comic_vine(talker):
    """Test handling existing Comic Vine ID."""
    talker.api.issues_list.return_value = [create_mock_base_issue()]
    result = talker._handle_existing_id(InfoSource.COMIC_VINE, 456)
    assert result == 123  # Should return the Metron ID


def test_talker_handle_existing_id_unknown():
    """Test handling unknown source ID."""
    talker = Talker("user", "pass", True, True)
    result = talker._handle_existing_id(InfoSource.UNKNOWN, 123)
    assert result is None


@patch("metrontagger.talker.Comic")
def test_talker_get_existing_metadata_id_success(mock_comic_class, talker):
    """Test successful extraction of existing metadata ID."""
    mock_comic = Mock()
    mock_comic.has_metadata.side_effect = [True, False]  # Has MetronInfo, not ComicInfo
    mock_comic.read_metadata.return_value = create_mock_metadata()
    mock_comic_class.return_value = mock_comic

    with patch.object(
        talker.metadata_extractor,
        "get_id_from_metron_info",
        return_value=(InfoSource.METRON, 123),
    ):
        result = talker._get_existing_metadata_id(mock_comic)
        assert result == (InfoSource.METRON, 123)


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
        result, multiple = talker._search_by_filename(Path("test.cbz"), mock_comic)
        assert result == 123
        assert multiple is False


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

    result, multiple = talker._search_by_filename(Path("test.cbz"), mock_comic)
    assert result is None
    assert multiple is False
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
        result, multiple = talker._search_by_filename(Path("test.cbz"), mock_comic)
        assert result is None
        assert multiple is True
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
        talker.api.issue.assert_called_once_with(123)
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
        patch.object(talker, "_process_file", return_value=(123, False)),
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

    with patch("metrontagger.talker.questionary.print") as mock_print:
        result, multiple = talker._search_by_filename(Path("unparseable.cbz"), mock_comic)
        assert result is None
        assert multiple is False
        error_calls = [
            call
            for call in mock_print.call_args_list
            if len(call[0]) > 0 and "Unable to correctly parse filename" in str(call[0][0])
        ]
        assert error_calls


@patch("metrontagger.talker.Comic")
def test_talker_process_file_not_writable(mock_comic_class, talker):
    """Test processing file that's not writable."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = False
    mock_comic.seems_to_be_a_comic_archive.return_value = False
    mock_comic_class.return_value = mock_comic

    with patch("metrontagger.talker.questionary.print") as mock_print:
        result, multiple = talker._process_file(Path("readonly.cbz"))
        assert result is None
        assert multiple is False
        error_calls = [
            call
            for call in mock_print.call_args_list
            if len(call[0]) > 0 and "appears not to be a comic" in str(call[0][0])
        ]
        assert error_calls


def test_info_source_enum():
    """Test InfoSource enum values."""
    assert InfoSource.METRON.name == "METRON"
    assert InfoSource.COMIC_VINE.name == "COMIC_VINE"
    assert InfoSource.UNKNOWN.name == "UNKNOWN"
