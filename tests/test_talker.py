"""Tests for the Talker class and its helper classes."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest
from comicfn2dict import comicfn2dict
from darkseid.comic import MetadataFormat
from darkseid.metadata import Metadata, Series
from imagehash import hex_to_hash
from mokkari.exceptions import ApiError
from mokkari.rate_limit import HeaderPacedRateLimiter
from mokkari.schemas.issue import CoverMatch
from mokkari.utils import hamming_distance

from metrontagger import __version__
from metrontagger.cover_match import (
    COVER_ACCEPT_DISTANCE,
    COVER_ACCEPT_MARGIN,
    COVER_SEARCH_MAX_DISTANCE,
    HALF_COVER_HAMMING_DISTANCE,
)
from metrontagger.talker import (
    CoverMatches,
    InfoSource,
    MetadataExtractor,
    MultipleMatch,
    OnlineMatchResults,
    ProcessingConfig,
    SearchResult,
    Talker,
    TalkerPresenter,
)
from tests.fakes import (
    SEARCH_HASH,
    create_mock_base_issue,
    create_mock_issue_response,
    hash_at_distance,
    tzinfo,
)


# Fixtures
@pytest.fixture
def mock_api():
    """Create a mock API object."""
    api = Mock()
    api.issue.return_value = create_mock_issue_response()
    api.issues_list.return_value = [create_mock_base_issue()]
    return api


@pytest.fixture
def talker(mock_api):
    """Create a Talker instance with mocked API."""
    with patch("metrontagger.metron_client.mokkari.api", return_value=mock_api):
        return Talker("my-token", [MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO])


@pytest.fixture
def sample_path():
    """Create a sample Path object."""
    return Path("test_comic.cbz")


def create_mock_metadata():
    """Create a mock Metadata object."""
    md = Mock(spec=Metadata, is_empty=False)
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


# Talker class tests
def test_talker_initialization():
    """Test Talker initialization."""
    with patch("metrontagger.metron_client.mokkari.api") as mock_api_func:
        talker = Talker("my-token", [MetadataFormat.METRON_INFO])
        assert talker.formats == (MetadataFormat.METRON_INFO,)
        assert isinstance(talker.match_results, OnlineMatchResults)
        mock_api_func.assert_called_once_with(
            user_agent=f"Metron-Tagger/{__version__}",
            api_token="my-token",  # noqa: S106
            rate_limiter=ANY,
        )
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )


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
    talker = Talker("my-token", [MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO])
    result = talker._handle_existing_id(InfoSource.METRON, 123)
    assert result == 123


def test_talker_handle_existing_id_comic_vine(talker):
    """Test handling existing Comic Vine ID."""
    talker.api.issues_list.return_value = [create_mock_base_issue()]
    result = talker._handle_existing_id(InfoSource.COMIC_VINE, 456)
    assert result == 123  # Should return the Metron ID


def test_talker_handle_existing_id_unknown():
    """Test handling unknown source ID."""
    talker = Talker("my-token", [MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO])
    result = talker._handle_existing_id(InfoSource.UNKNOWN, 123)
    assert result is None


@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.comics.Comic")
def test_talker_get_existing_metadata_id_no_metadata(mock_comic_class, talker):
    """Test extraction when no metadata exists."""
    mock_comic = Mock()
    mock_comic.has_metadata.return_value = False
    mock_comic_class.return_value = mock_comic

    result = talker._get_existing_metadata_id(mock_comic)
    assert result is None


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.comics.Comic")
def test_talker_should_skip_existing_metadata_true(mock_comic_class, talker):
    """Test skipping file with existing metadata."""
    mock_comic = Mock()
    mock_comic.has_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    result = talker._should_skip_existing_metadata(
        mock_comic, ProcessingConfig(ignore_existing=True)
    )
    assert result is True


@patch("metrontagger.comics.Comic")
def test_talker_should_skip_existing_metadata_false(mock_comic_class, talker):
    """Test not skipping file without ignore flag."""
    mock_comic = Mock()
    mock_comic.has_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    result = talker._should_skip_existing_metadata(
        mock_comic, ProcessingConfig(ignore_existing=False)
    )
    assert result is False


@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.ui.create_print_title")
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
@patch("metrontagger.ui.create_print_title")
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


@patch("metrontagger.ui.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.comics.Comic")
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

    config = ProcessingConfig(
        ignore_existing=False, accept_only=False, skip_multiple=True, series_id=None
    )

    file_list = [Path("test1.cbz"), Path("test2.cbz")]

    with (
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=None, has_multiple_matches=False),
        ) as mock_process,
        patch.object(talker, "_post_process_matches"),
    ):
        talker.identify_comics(file_list, config)

        # Verify _process_file was called with correct ProcessingConfig
        assert mock_process.call_count == 2
        for call in mock_process.call_args_list:
            config = call[0][1]  # ProcessingConfig is the second argument
            assert isinstance(config, ProcessingConfig)
            assert config.accept_only is False
            assert config.skip_multiple is True


@patch("metrontagger.ui.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.comics.Comic")
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

    config = ProcessingConfig(
        ignore_existing=False, accept_only=False, skip_multiple=False, series_id=None
    )

    file_list = [Path("test.cbz")]

    with (
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=None, has_multiple_matches=True),
        ) as mock_process,
        patch.object(talker, "_post_process_matches"),
    ):
        talker.identify_comics(file_list, config)

        # Verify _process_file was called with correct ProcessingConfig
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        config = call_args[0][1]  # ProcessingConfig is the second argument
        assert isinstance(config, ProcessingConfig)
        assert config.accept_only is False
        assert config.skip_multiple is False


@patch("metrontagger.ui.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.comics.Comic")
def test_identify_comics_with_ignore_modified_enabled(
    mock_comic_class,
    mock_print,  # noqa: ARG001
    mock_create_title,  # noqa: ARG001
    talker,
):
    """Test identify_comics passes ignore_modified through to each file."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True
    mock_comic.has_metadata.return_value = False
    mock_comic_class.return_value = mock_comic

    config = ProcessingConfig(
        ignore_existing=False,
        accept_only=False,
        skip_multiple=False,
        ignore_modified=True,
        series_id=None,
    )

    file_list = [Path("test.cbz")]

    with (
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=None, has_multiple_matches=True),
        ) as mock_process,
        patch.object(talker, "_post_process_matches"),
    ):
        talker.identify_comics(file_list, config)

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

    with patch.object(
        talker,
        "_get_existing_metadata_id",
        return_value=(InfoSource.METRON, 123, modified),
    ):
        config = ProcessingConfig(ignore_modified=True)
        result = talker._process_file(Path("test.cbz"), config, mock_comic)

    assert result.issue_id == 123
    assert result.modified is None


@patch("metrontagger.talker.questionary.print")
def test_talker_process_file_keeps_modified_by_default(mock_print, talker):  # noqa: ARG001
    """Test that _process_file keeps the modified date when ignore_modified is unset."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True

    modified = datetime(2023, 6, 15, tzinfo=tzinfo)

    with patch.object(
        talker,
        "_get_existing_metadata_id",
        return_value=(InfoSource.METRON, 123, modified),
    ):
        config = ProcessingConfig()
        result = talker._process_file(Path("test.cbz"), config, mock_comic)

    assert result.issue_id == 123
    assert result.modified == modified


@patch("metrontagger.talker.comicfn2dict")
@patch("metrontagger.talker.create_query_params")
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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
@patch("metrontagger.comics.Comic")
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


@patch("metrontagger.ui.create_print_title")
@patch("metrontagger.talker.questionary.print")
@patch("metrontagger.comics.Comic")
def test_talker_identify_comics_success(mock_comic_class, _, mock_create_title, talker):  # noqa: PT019
    """Test successful comic identification."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = True
    mock_comic.seems_to_be_a_comic_archive.return_value = True
    mock_comic.has_metadata.return_value = False
    mock_comic.get_number_of_pages.return_value = 20
    mock_comic.write_metadata.return_value = True
    mock_comic_class.return_value = mock_comic

    config = ProcessingConfig(ignore_existing=False, accept_only=False, series_id=None)

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
        talker.identify_comics(file_list, config)
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
    config = ProcessingConfig(series_id=None)

    with (
        patch.object(talker, "_post_process_matches"),
        patch.object(talker, "_print_rate_limit_status") as mock_print_rate_limit,
    ):
        talker.identify_comics([], config)
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


def test_talker_presenter_print_rate_limit_status():
    """Test that the rate limit message is printed when limit data is known."""
    reset = datetime(2026, 7, 21, tzinfo=UTC)
    with patch("metrontagger.talker.questionary.print") as mock_print:
        TalkerPresenter.print_rate_limit_status(4823, 5000, reset)
        mock_print.assert_called_once()
        assert "4,823/5,000 daily requests remaining" in mock_print.call_args[0][0]


def test_talker_presenter_print_rate_limit_status_without_reset():
    """Test that the message omits the reset time when it isn't known."""
    with patch("metrontagger.talker.questionary.print") as mock_print:
        TalkerPresenter.print_rate_limit_status(4823, 5000, None)
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
def test_talker_presenter_print_rate_limit_status_unknown(remaining, limit):
    """Test that nothing is printed when the sustained limit isn't known yet."""
    with patch("metrontagger.talker.questionary.print") as mock_print:
        TalkerPresenter.print_rate_limit_status(remaining, limit, None)
        mock_print.assert_not_called()


# Edge cases and error handling
@patch("metrontagger.talker.comicfn2dict", return_value={})
@patch("metrontagger.talker.create_query_params", return_value=None)
@patch("metrontagger.comics.Comic")
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


def test_talker_process_file_not_writable(talker):
    """Test processing file that's not writable."""
    mock_comic = Mock()
    mock_comic.is_writable.return_value = False
    mock_comic.seems_to_be_a_comic_archive.return_value = False

    config = ProcessingConfig()
    search_result = talker._process_file(Path("readonly.cbz"), config, mock_comic)
    assert search_result.issue_id is None
    assert search_result.has_multiple_matches is False


def test_info_source_enum():
    """Test InfoSource enum values."""
    assert InfoSource.METRON.name == "METRON"
    assert InfoSource.COMIC_VINE.name == "COMIC_VINE"
    assert InfoSource.UNKNOWN.name == "UNKNOWN"


# Cover-first search
BOBA_FETT = Path("Star Wars - The Book of Boba Fett 005 (2027) (Digital).cbz")
BOBA_FETT_SERIES = "Star Wars: The Book of Boba Fett"


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
    }


@pytest.mark.parametrize("metadata", [{"issue": "150", "year": "2016"}, {"issue": "150"}])
def test_cover_search_params_series_id(metadata):
    """A given series id replaces the year range, which may be the series' start year."""
    assert Talker._cover_search_params(metadata, 42) == {"number": "150", "series_id": 42}


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


def cover_issue(issue_id: int, bits: int, series_name: str = BOBA_FETT_SERIES):
    """A search result whose cover is `bits` from SEARCH_HASH, in the filename's series."""
    return create_mock_base_issue(issue_id, hash_at_distance(bits), series_name)


def search_by_cover(talker, results, config=None, hashes=(SEARCH_HASH,), filename=BOBA_FETT):
    """Run _search_by_cover with the API returning `results` (a list per request).

    Each of `hashes` is a hash (searched as a whole cover) or a (hash, limit) pair.
    Like mokkari, each result's distance is worked out from the hash searched.
    """
    responses = iter(results)

    def issues_by_cover_hash(cover_hash, **_kwargs):
        return [
            CoverMatch.model_construct(
                issue=issue, distance=hamming_distance(cover_hash, issue.cover_hash)
            )
            for issue in next(responses)
        ]

    talker.api.issues_by_cover_hash.side_effect = issues_by_cover_hash
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
    results = talker.match_results
    assert results.good_matches == []
    assert results.no_matches == []
    assert results.multiple_matches == []
    assert results.skipped_matches == []
    talker.api.issues_by_cover_hash.assert_called_once_with(
        str(SEARCH_HASH),
        max_distance=COVER_SEARCH_MAX_DISTANCE,
        params={
            "number": "5",
            "cover_date_range_after": "2026-01-01",
            "cover_date_range_before": "2028-12-31",
        },
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
    assert talker.api.issues_by_cover_hash.call_count == 2


def test_search_by_cover_no_results(talker):
    """No cover match gives nothing to accept and no candidates."""
    assert search_by_cover(talker, [[]]) == CoverMatches()


def test_search_by_cover_api_error_keeps_earlier_candidates(talker):
    """An API error ends the search but keeps what earlier hashes found."""
    far = cover_issue(1, COVER_ACCEPT_DISTANCE + 2)
    left = hex_to_hash(hash_at_distance(1))
    far_match = CoverMatch.model_construct(issue=far, distance=COVER_ACCEPT_DISTANCE + 2)
    with patch.object(talker.client, "call", side_effect=[[far_match], None]):
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
    talker.api.issues_by_cover_hash.assert_not_called()


def make_writable_comic():
    comic = Mock()
    comic.is_writable.return_value = True
    comic.seems_to_be_a_comic_archive.return_value = True
    return comic


def process_file(talker, cover, config=None):
    """Run _process_file with the cover search returning `cover`."""
    with (
        patch.object(talker, "_get_existing_metadata_id", return_value=None),
        patch.object(talker, "_search_by_cover", return_value=cover),
        patch.object(talker, "_search_by_filename") as by_filename,
    ):
        result = talker._process_file(
            BOBA_FETT, config or ProcessingConfig(), make_writable_comic()
        )
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
    talker.client.stop_processing = True
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
        patch.object(talker, "_get_existing_metadata_id", return_value=None),
        patch("metrontagger.talker.comicfn2dict", return_value=parsed) as parse,
        patch.object(talker, "_search_by_cover", return_value=CoverMatches()) as by_cover,
        patch.object(talker, "_search_by_filename") as by_filename,
    ):
        talker._process_file(BOBA_FETT, ProcessingConfig(), make_writable_comic())

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
    assert talker.api.issues_by_cover_hash.call_count == 2


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
        patch.object(talker.client, "call", return_value=None),
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
    talker.client.stop_processing = True
    assert search_by_cover(talker, [[cover_issue(1, 0)]]) == CoverMatches()
    talker.api.issues_by_cover_hash.assert_not_called()


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


@pytest.mark.parametrize(
    ("formats", "existing", "expected"),
    [
        ([MetadataFormat.METRON_INFO], {MetadataFormat.COMIC_INFO}, False),
        ([MetadataFormat.METRON_INFO], {MetadataFormat.METRON_INFO}, True),
        ([MetadataFormat.COMIC_INFO], {MetadataFormat.METRON_INFO}, False),
        (
            [MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO],
            {MetadataFormat.COMIC_INFO},
            True,
        ),
        ([MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO], set(), False),
    ],
    ids=[
        "mi_writer_ci_only",
        "mi_writer_has_mi",
        "ci_writer_mi_only",
        "both_has_ci",
        "untagged",
    ],
)
def test_should_skip_existing_metadata_checks_only_written_formats(
    formats, existing, expected
):
    """--ignore-existing skips a comic only if it has a format this Talker writes."""
    with patch("metrontagger.metron_client.mokkari.api"):
        talker = Talker("my-token", formats)
    comic = Mock()
    comic.has_metadata.side_effect = lambda fmt: fmt in existing

    result = talker._should_skip_existing_metadata(
        comic, ProcessingConfig(ignore_existing=True)
    )

    assert result is expected


def test_metadata_extractor_invalid_id_without_series():
    """An invalid ID on metadata with no series is logged without crashing."""
    md = create_mock_metadata()
    md.series = None

    with patch("metrontagger.talker.get_issue_id_from_note") as mock_get_id:
        mock_get_id.return_value = {"source": "Metron", "id": "invalid"}
        assert MetadataExtractor.get_id_from_comic_info(md) is None


@pytest.mark.parametrize(
    ("series_format", "expected_collection"),
    [
        ("Trade Paperback", True),
        ("Hardcover", True),
        ("Hard Cover", True),
        ("Single Issue", False),
        (None, False),
    ],
)
@patch("metrontagger.comics.Comic")
def test_write_issue_md_collection_flag(
    mock_comic_class, talker, sample_path, series_format, expected_collection
):
    """A series with no format is written as a non-collection, not a crash."""
    mock_comic_class.return_value.get_number_of_pages.return_value = 20
    mock_comic_class.return_value.write_metadata.return_value = True
    md = Metadata()
    md.series = Series("Aquaman", format=series_format)

    with (
        patch.object(talker.metadata_mapper, "map_response_to_metadata", return_value=md),
        patch.object(talker.ui, "print_metadata_write_success") as mock_success,
    ):
        talker._write_issue_md(sample_path, 123)

    assert mock_success.call_args.kwargs["is_collection"] is expected_collection


def test_post_process_matches_skips_prompts_after_stop(talker):
    """Once processing has stopped, multiple matches aren't offered for a choice."""
    talker.match_results.add_multiple_match(
        MultipleMatch(Path("a.cbz"), [create_mock_base_issue()])
    )
    talker.client.stop_processing = True

    with (
        patch.object(talker, "_select_choice_from_matches") as mock_select,
        patch.object(talker.ui, "print_match_results"),
        patch.object(talker.ui, "print_info") as mock_info,
    ):
        talker._post_process_matches()

    mock_select.assert_not_called()
    mock_info.assert_called_once_with("Skipping the remaining multiple matches.")


def test_post_process_matches_stops_after_a_choice_hits_a_fatal_error(talker):
    """A fatal error while writing one choice stops the prompts for the rest."""
    for name in ("a.cbz", "b.cbz"):
        talker.match_results.add_multiple_match(
            MultipleMatch(Path(name), [create_mock_base_issue()])
        )

    def fail_fatally(*_args):
        talker.client.stop_processing = True

    with (
        patch.object(talker, "_select_choice_from_matches", return_value=123) as mock_select,
        patch.object(talker, "_write_issue_md", side_effect=fail_fatally),
        patch.object(talker.ui, "print_match_results"),
        patch.object(talker.ui, "print_info"),
    ):
        talker._post_process_matches()

    assert mock_select.call_count == 1


def test_write_issue_md_failed_call_is_not_reported_as_not_modified(talker, sample_path):
    """An API error isn't also reported as the comic being up to date."""
    talker.api.issue.side_effect = ApiError("Server error")

    with (
        patch.object(talker.ui, "print_info") as mock_info,
        patch.object(talker.ui, "print_error"),
    ):
        talker._write_issue_md(sample_path, 123, modified=datetime(2024, 1, 1, tzinfo=UTC))

    assert not any("not been modified" in str(c.args[0]) for c in mock_info.call_args_list)


def test_identify_comics_opens_each_file_once(talker):
    """The comic opened by identify_comics is reused for the search and the write."""
    comic = make_writable_comic()
    comic.has_metadata.return_value = False

    with (
        patch("metrontagger.talker.open_comic", return_value=comic) as mock_open,
        patch.object(
            talker,
            "_process_file",
            return_value=SearchResult(issue_id=123, has_multiple_matches=False),
        ) as mock_process,
        patch.object(talker, "_write_issue_md") as mock_write,
        patch.object(talker, "_post_process_matches"),
        patch.object(talker, "_print_rate_limit_status"),
    ):
        talker.identify_comics([BOBA_FETT], ProcessingConfig())

    mock_open.assert_called_once_with(BOBA_FETT)
    assert mock_process.call_args.args[2] is comic
    mock_write.assert_called_once_with(BOBA_FETT, 123, None, comic)


def test_write_issue_md_uses_given_comic(talker, sample_path):
    """An already-open comic is written to without opening the file again."""
    comic = Mock()
    comic.get_number_of_pages.return_value = 20
    comic.write_metadata.return_value = True

    with (
        patch.object(talker.client, "call", return_value=Mock()),
        patch.object(
            talker.metadata_mapper, "map_response_to_metadata", return_value=Metadata()
        ),
        patch.object(talker.ui, "print_metadata_write_success"),
        patch("metrontagger.talker.open_comic") as mock_open,
    ):
        talker._write_issue_md(sample_path, 123, comic=comic)

    mock_open.assert_not_called()
    comic.write_metadata.assert_called()


KYLO_REN = Path("Star Wars - The Fall of Kylo Ren 004 (2026) (Digital) (Kileko-Empire).cbz")
SERIES_ONLY_PARAMS = {"series_q": "Star Wars", "number": "4"}
SERIES_AND_TITLE_PARAMS = {"series_q": "Star Wars The Fall of Kylo Ren", "number": "4"}


def search_kylo_ren(talker, responses, *, cover_matches=True, config=None):
    """Run _search_by_filename on KYLO_REN, the API returning each of `responses` in turn.

    Every cover matches if `cover_matches`, otherwise none does.
    Returns the search result and the params of each API call.
    """
    talker.api.issues_list.side_effect = responses
    with (
        patch.object(
            talker.cover_matcher, "is_within_hamming_distance", return_value=cover_matches
        ),
        patch.object(
            talker.cover_matcher,
            "filter_by_hamming_distance",
            side_effect=lambda _comic, issues: issues if cover_matches else [],
        ),
    ):
        result = talker._search_by_filename(
            KYLO_REN,
            Mock(),
            config or ProcessingConfig(),
            comicfn2dict(KYLO_REN, verbose=0),
        )
    calls = [c.kwargs["params"] for c in talker.api.issues_list.call_args_list]
    return result, calls


def test_search_by_filename_uses_series_and_title(talker):
    """A filename split into series and title is searched on both together."""
    result, calls = search_kylo_ren(talker, [[create_mock_base_issue(185517)]])

    assert result == SearchResult(issue_id=185517, has_multiple_matches=False)
    assert calls == [SERIES_AND_TITLE_PARAMS]


def test_search_by_filename_falls_back_to_series_only(talker):
    """If the series and title together find nothing, the series alone is searched."""
    result, calls = search_kylo_ren(talker, [[], [create_mock_base_issue(1)]])

    assert result == SearchResult(issue_id=1, has_multiple_matches=False)
    assert calls == [SERIES_AND_TITLE_PARAMS, SERIES_ONLY_PARAMS]


def test_search_by_filename_series_only_after_title_search_api_error(talker):
    """An API error on the series and title search still runs the series-only search."""
    result, calls = search_kylo_ren(talker, [None, [create_mock_base_issue(1)]])

    assert result == SearchResult(issue_id=1, has_multiple_matches=False)
    assert calls == [SERIES_AND_TITLE_PARAMS, SERIES_ONLY_PARAMS]


def test_search_by_filename_api_errors_not_no_match(talker):
    """API errors on both searches aren't recorded as no match."""
    with patch.object(talker.client, "call", return_value=None) as call:
        result = talker._search_by_filename(
            KYLO_REN, Mock(), ProcessingConfig(), comicfn2dict(KYLO_REN, verbose=0)
        )

    assert result == SearchResult(issue_id=None, has_multiple_matches=False)
    assert call.call_count == 2
    assert not talker.match_results.no_matches


def test_search_by_filename_no_series_search_after_stop(talker):
    """A fatal API error on the series and title search stops the series-only search."""

    def stop(*_args):
        talker.client.stop_processing = True

    with patch.object(talker.client, "call", side_effect=stop) as call:
        result = talker._search_by_filename(
            KYLO_REN, Mock(), ProcessingConfig(), comicfn2dict(KYLO_REN, verbose=0)
        )

    assert result == SearchResult(issue_id=None, has_multiple_matches=False)
    call.assert_called_once()
    assert not talker.match_results.no_matches


def test_search_by_filename_offers_title_matches_after_series_api_error(talker):
    """An API error on the series-only search still offers the series and title matches."""
    match = create_mock_base_issue(9)
    result, _ = search_kylo_ren(talker, [[match], None], cover_matches=False)

    assert result == SearchResult(issue_id=None, has_multiple_matches=True)
    assert talker.match_results.multiple_matches == [MultipleMatch(KYLO_REN, [match])]


def test_search_by_filename_with_series_id_ignores_title(talker):
    """With --id the series is known, so the title isn't added to the search."""
    talker.api.issues_list.return_value = [create_mock_base_issue(185517)]
    with patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=True):
        talker._search_by_filename(
            KYLO_REN,
            Mock(),
            ProcessingConfig(series_id=16447),
            comicfn2dict(KYLO_REN, verbose=0),
        )

    talker.api.issues_list.assert_called_once_with(
        params={"series_id": "16447", "number": "4"}
    )


def test_search_by_filename_title_match_needs_cover_with_accept_only(talker):
    """--accept-only doesn't accept a lone series and title match: the series is searched."""
    result, calls = search_kylo_ren(
        talker,
        [[create_mock_base_issue(9)], [create_mock_base_issue(1)]],
        cover_matches=False,
        config=ProcessingConfig(accept_only=True),
    )

    assert result == SearchResult(issue_id=1, has_multiple_matches=False)
    assert calls == [SERIES_AND_TITLE_PARAMS, SERIES_ONLY_PARAMS]


def test_search_by_filename_offers_both_searches_without_cover_match(talker):
    """Without a cover match, both searches' results are offered, each issue once.

    The series and title matches come first, then the series-only ones, each in
    cover-date order.
    """
    a, b, c, d = (create_mock_base_issue(i) for i in (1, 2, 3, 4))
    a.cover_date = datetime(2020, 1, 1, tzinfo=UTC).date()
    b.cover_date = datetime(2022, 1, 1, tzinfo=UTC).date()
    c.cover_date = datetime(2021, 1, 1, tzinfo=UTC).date()
    d.cover_date = datetime(2019, 1, 1, tzinfo=UTC).date()
    result, calls = search_kylo_ren(talker, [[b, a], [c, b, d]], cover_matches=False)

    assert result == SearchResult(issue_id=None, has_multiple_matches=True)
    assert calls == [SERIES_AND_TITLE_PARAMS, SERIES_ONLY_PARAMS]
    assert talker.match_results.multiple_matches == [MultipleMatch(KYLO_REN, [a, b, d, c])]


def test_search_by_filename_offers_title_matches_if_series_finds_nothing(talker):
    """Series and title matches without a cover match are still offered."""
    match = create_mock_base_issue(9)
    result, _ = search_kylo_ren(talker, [[match], []], cover_matches=False)

    assert result == SearchResult(issue_id=None, has_multiple_matches=True)
    assert talker.match_results.multiple_matches == [MultipleMatch(KYLO_REN, [match])]


def test_search_by_filename_accepts_unique_title_cover_match(talker):
    """Of several series and title matches, the only cover match is accepted."""
    match = create_mock_base_issue(7)
    talker.api.issues_list.return_value = [create_mock_base_issue(6), match]
    with patch.object(
        talker.cover_matcher, "filter_by_hamming_distance", return_value=[match]
    ):
        result = talker._search_by_filename(
            KYLO_REN, Mock(), ProcessingConfig(), comicfn2dict(KYLO_REN, verbose=0)
        )

    assert result == SearchResult(issue_id=7, has_multiple_matches=False)
    talker.api.issues_list.assert_called_once_with(params=SERIES_AND_TITLE_PARAMS)


def test_search_by_filename_story_title_searches_series_only(talker):
    """A title after the issue number is a story title: only the series is searched."""
    filename = Path("Batman v3 050 - The Wedding.cbz")
    talker.api.issues_list.return_value = [create_mock_base_issue(50)]
    with patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=True):
        result = talker._search_by_filename(
            filename, Mock(), ProcessingConfig(), comicfn2dict(filename, verbose=0)
        )

    assert result == SearchResult(issue_id=50, has_multiple_matches=False)
    talker.api.issues_list.assert_called_once_with(
        params={"series_q": "Batman", "number": "50"}
    )


def test_search_by_filename_no_prompt_after_fatal_series_error(talker):
    """A fatal API error on the series-only search doesn't offer the title matches."""
    responses = iter([[create_mock_base_issue(9)], None])

    def call(*_args):
        result = next(responses)
        if result is None:
            talker.client.stop_processing = True
        return result

    with (
        patch.object(talker.client, "call", side_effect=call),
        patch.object(talker.cover_matcher, "is_within_hamming_distance", return_value=False),
    ):
        result = talker._search_by_filename(
            KYLO_REN, Mock(), ProcessingConfig(), comicfn2dict(KYLO_REN, verbose=0)
        )

    assert result == SearchResult(issue_id=None, has_multiple_matches=False)
    assert not talker.match_results.multiple_matches
    assert not talker.match_results.no_matches


def test_search_by_filename_title_search_error_not_no_match(talker):
    """After an API error on the series and title search, an empty series-only search
    isn't recorded as no match: the issue may just not have been found."""
    result, calls = search_kylo_ren(talker, [None, []])

    assert result == SearchResult(issue_id=None, has_multiple_matches=False)
    assert calls == [SERIES_AND_TITLE_PARAMS, SERIES_ONLY_PARAMS]
    assert not talker.match_results.no_matches
