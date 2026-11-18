from __future__ import annotations

__all__ = ["Talker"]

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto, unique
from logging import getLogger
from typing import TYPE_CHECKING, Self

import questionary
from comicfn2dict import comicfn2dict
from darkseid.comic import MetadataFormat
from darkseid.metadata import Metadata
from darkseid.utils import get_issue_id_from_note

from metrontagger.comics import format_list, iter_metadata, open_comic
from metrontagger.cover_match import (
    COVER_ACCEPT_MARGIN,
    COVER_SEARCH_MAX_DISTANCE,
    COVER_YEAR_RANGE,
    COVER_YEAR_TOLERANCE,
    CoverHashMatcher,
)
from metrontagger.mapper import MetadataMapper
from metrontagger.metron_client import MetronClient
from metrontagger.ui import UIPresenter
from metrontagger.utils import (
    ParsedFilename,
    create_query_params,
    create_title_query_params,
    search_issue_number,
    series_words,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from darkseid.comic import Comic
    from mokkari.schemas.issue import BaseIssue
    from mokkari.session import Session

LOGGER = getLogger(__name__)

# Series formats shown as a "(Collection)" when tagged, lowercased. "hard cover" is
# Metron's old name for "Hardcover" (see FormatMapping in filerenamer.py).
COLLECTION_FORMATS = frozenset({"trade paperback", "hardcover", "hard cover"})


@unique
class InfoSource(Enum):
    """An enumeration of information sources.

    This class defines different sources of information, including Metron, Comic Vine, and Unknown.
    """

    METRON = auto()
    COMIC_VINE = auto()
    UNKNOWN = auto()


# Source messages for metadata printing
SOURCE_MESSAGES = {
    InfoSource.METRON: ("Metron ID", UIPresenter.print_info),
    InfoSource.COMIC_VINE: ("ComicVine", UIPresenter.print_info),
    InfoSource.UNKNOWN: ("Unknown Source", UIPresenter.print_warning),
}


@dataclass
class SearchResult:
    """Result of a comic search operation."""

    issue_id: int | None
    has_multiple_matches: bool
    modified: datetime | None = None


@dataclass
class ProcessingConfig:
    """Configuration for comic processing."""

    accept_only: bool = False
    skip_multiple: bool = False
    series_id: int | None = None
    ignore_existing: bool = False
    ignore_modified: bool = False


@dataclass
class CoverMatches:
    """What a cover search found: an accepted issue, or candidates for the user."""

    accepted: BaseIssue | None = None
    candidates: list[BaseIssue] = field(default_factory=list)


@dataclass
class MultipleMatch:
    """Class to store multiple matches for a filename."""

    filename: Path
    matches: list[BaseIssue]


class OnlineMatchResults:
    """Class to store online match results.

    This class stores good matches, no matches, multiple matches, and skipped matches for online search results.
    """

    def __init__(self) -> None:
        """Initialize the OnlineMatchResults class.

        This method initializes lists to store good matches, no matches, multiple matches, and skipped matches.
        """
        self._good_matches: list[Path] = []
        self._no_matches: list[Path] = []
        self._multiple_matches: list[MultipleMatch] = []
        self._skipped_matches: list[Path] = []

    @property
    def good_matches(self) -> list[Path]:
        """Get the list of good matches."""
        return self._good_matches

    @property
    def no_matches(self) -> list[Path]:
        """Get the list of no matches."""
        return self._no_matches

    @property
    def multiple_matches(self) -> list[MultipleMatch]:
        """Get the list of multiple matches."""
        return self._multiple_matches

    @property
    def skipped_matches(self) -> list[Path]:
        """Get the list of skipped matches."""
        return self._skipped_matches

    def add_good_match(self, file_name: Path) -> None:
        """Add a good match to the list."""
        self._good_matches.append(file_name)

    def add_no_match(self, file_name: Path) -> None:
        """Add a no match to the list."""
        self._no_matches.append(file_name)

    def add_multiple_match(self, multi_match: MultipleMatch) -> None:
        """Add a multiple match to the list."""
        self._multiple_matches.append(multi_match)

    def add_skipped_match(self, file_name: Path) -> None:
        """Add a skipped match to the list."""
        self._skipped_matches.append(file_name)


class TalkerPresenter(UIPresenter):
    """Console output for online search and tagging."""

    @staticmethod
    def print_metadata_source_message(source: InfoSource, comic: Comic) -> None:
        """Print appropriate message based on metadata source."""
        if source not in SOURCE_MESSAGES:
            return

        message_text, print_func = SOURCE_MESSAGES[source]
        if source != InfoSource.UNKNOWN:
            print_func(
                f"Found {message_text} in '{comic}' metadata and using that to get the metadata..."
            )
        else:
            print_func(f"Found {message_text} in '{comic}' metadata. Skipping...")

    @classmethod
    def print_match_results(cls, results: OnlineMatchResults) -> None:
        """Print all match results."""
        sections = (
            ("Successful Matches:", results.good_matches, cls.print_success),
            ("No Matches:", results.no_matches, cls.print_warning),
            ("Skipped Multiple Matches:", results.skipped_matches, cls.print_warning),
        )
        for title, comics, print_func in sections:
            if comics:
                cls.print_title(title)
                for comic in comics:
                    print_func(f"{comic}")

    @classmethod
    def print_multiple_match_prompt(cls, fn: Path) -> None:
        """Print prompt for multiple matches."""
        cls.print_heading(f"\n{fn.name} - Results found:")

    @classmethod
    def print_rate_limit_status(
        cls, remaining: int | None, limit: int | None, reset: datetime | None
    ) -> None:
        """Print the sustained (daily) Metron API quota remaining, if known."""
        if not isinstance(remaining, int) or not isinstance(limit, int):
            return

        msg = f"Metron API: {remaining:,}/{limit:,} daily requests remaining"
        if isinstance(reset, datetime):
            msg += f" (resets {reset.astimezone().strftime('%H:%M %Z')})"
        cls.print_info(msg)

    @classmethod
    def print_metadata_write_success(  # noqa: PLR0913, PLR0917
        cls,
        formats: list[str],
        series_name: str,
        issue: str,
        year: int,
        filename: str,
        is_collection: bool,
    ) -> None:
        """Print success message for metadata writing."""
        collection_text = " (Collection)" if is_collection else ""
        fmt = " and ".join(formats)
        cls.print_success(
            f"Writing {fmt} metadata using "
            f"'{series_name} #{issue} ({year}){collection_text}' "
            f"for '{filename}'."
        )


class MetadataExtractor:
    """Handles extraction of metadata from comic files."""

    @staticmethod
    def get_id_from_metron_info(md: Metadata) -> tuple[InfoSource, int] | None:
        """Extract ID from MetronInfo metadata."""
        if not md.info_source:
            return None

        online_sources = {"metron", "comic vine"}

        for src in md.info_source:
            lower_name = src.name.lower()
            if lower_name in online_sources:
                return (
                    InfoSource.METRON if lower_name == "metron" else InfoSource.COMIC_VINE,
                    src.id_,
                )  # type: ignore
        return None

    @staticmethod
    def get_id_from_comic_info(md: Metadata) -> tuple[InfoSource, int] | None:
        """Extract ID from ComicInfo metadata."""
        if md.notes is None or not md.notes.comic_rack:
            return None

        res = get_issue_id_from_note(md.notes.comic_rack)
        if res is None:
            return None

        source_map = {"Metron": InfoSource.METRON, "Comic Vine": InfoSource.COMIC_VINE}
        src = source_map.get(res["source"])
        if src is None:
            return None

        try:
            id_ = int(res["id"])
        except ValueError:
            series_name = md.series.name if md.series else "Unknown series"
            LOGGER.exception("Comic has invalid id: %s #%s", series_name, md.issue)
            return None

        return src, id_


class Talker:
    """Class for handling online search and tagging of comic files.

    This class provides methods for identifying comics, retrieving single issues, and processing match results.
    """

    def __init__(
        self,
        api_token: str,
        formats: Iterable[MetadataFormat],
        *,
        username: str | None = None,
        redis_url: str | None = None,
    ) -> None:
        """Initialize the Talker with a Metron API token.

        Args:
            api_token: The Metron API token.
            formats: The metadata formats to write, in the order to write them.
            username: The Metron username; with `redis_url`, configures the shared
                rate limiter (see `MetronClient`).
            redis_url: The Redis server for the shared rate limiter, if any.
        """
        self.ui = TalkerPresenter()
        self.client = MetronClient(
            api_token, username=username, redis_url=redis_url, ui=self.ui
        )
        self.formats = tuple(formats)
        self.match_results = OnlineMatchResults()
        self.metadata_extractor = MetadataExtractor()
        self.cover_matcher = CoverHashMatcher()
        self.metadata_mapper = MetadataMapper()

    @property
    def api(self) -> Session:
        """The underlying mokkari API session."""
        return self.client.api

    def close(self) -> None:
        """Close the Metron API session's pooled connections and any Redis client."""
        self.client.close()

    def __enter__(self) -> Self:
        """Enter the context manager, returning this Talker."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Exit the context manager, closing pooled connections."""
        self.close()

    @staticmethod
    def _create_choice_list(match_set: list[BaseIssue]) -> list[questionary.Choice]:
        """Create a list of choices for selecting issues."""
        issue_lst = [
            questionary.Choice(title=f"{i.issue_name} ({i.cover_date})", value=i.id)
            for i in match_set
        ]
        issue_lst.append(questionary.Choice(title="Skip", value=""))
        return issue_lst

    def _select_choice_from_matches(self, fn: Path, match_set: list[BaseIssue]) -> int | None:
        """Select an issue from a list of matches, shown in the order given.

        Cover search matches come closest cover first; filename search matches come
        in cover-date order.
        """
        self.ui.print_multiple_match_prompt(fn)
        choices = self._create_choice_list(match_set)

        return questionary.select("Select an issue to match", choices=choices).ask()

    def _get_existing_metadata_id(
        self, comic: Comic
    ) -> tuple[InfoSource, int, datetime | None] | None:
        """Get existing metadata ID from comic if available."""
        extractors = {
            MetadataFormat.METRON_INFO: self.metadata_extractor.get_id_from_metron_info,
            MetadataFormat.COMIC_INFO: self.metadata_extractor.get_id_from_comic_info,
        }
        # A format without an ID falls through to the next one.
        for fmt, md in iter_metadata(comic):
            if result := extractors[fmt](md):
                source, id_ = result
                modified = (
                    md.modified
                    if source == InfoSource.METRON and fmt == MetadataFormat.METRON_INFO
                    else None
                )
                return source, id_, modified

        return None

    def _handle_existing_id(self, source: InfoSource, id_: int) -> int | None:
        """Handle cases where we have an existing ID from metadata."""
        if source == InfoSource.METRON:
            return id_
        if source == InfoSource.COMIC_VINE:
            issues = self.client.call(
                lambda: self.api.issues_list(params={"cv_id": id_}), "Failed to retrieve data"
            )
            if issues is None:
                return None

            # This should always be 1 otherwise let's do a regular search.
            if len(issues) == 1:
                return issues[0].id
        return None

    def _search_by_filename(
        self,
        filename: Path,
        comic: Comic,
        config: ProcessingConfig,
        parsed: ParsedFilename | None = None,
        cover_candidates: list[BaseIssue] | None = None,
    ) -> SearchResult:
        """Search for comic by filename parsing.

        Args:
            filename: The comic's path.
            comic: The comic.
            config: The processing options.
            parsed: The filename already parsed by comicfn2dict, if the caller has it.
            cover_candidates: Issues a cover search found but didn't accept. If this
                search doesn't accept a match either, they're offered first.
        """
        cover_candidates = cover_candidates or []
        metadata = dict(parsed) if parsed is not None else comicfn2dict(filename, verbose=0)
        if config.series_id is not None:
            metadata["series_id"] = str(config.series_id)

        params = create_query_params(metadata)
        if params is None:
            if cover_candidates:
                return self._resolve_search(filename, None, cover_candidates, config)
            self.ui.print_error(f"Unable to correctly parse filename: {filename.name}")
            return SearchResult(issue_id=None, has_multiple_matches=False)

        i_list = self._search_issues(metadata, params)
        if not i_list:
            # Nothing found, or an API error (already reported by MetronClient.call).
            if cover_candidates and not self.client.stop_processing:
                return self._resolve_search(filename, None, cover_candidates, config)
            if i_list is not None:
                self.match_results.add_no_match(filename)
            return SearchResult(issue_id=None, has_multiple_matches=False)

        accepted: BaseIssue | None = None
        if len(i_list) == 1:
            # A single match is accepted if its cover matches, or with --accept-only.
            match = i_list[0]
            if config.accept_only or self.cover_matcher.is_within_hamming_distance(
                comic, match.cover_hash
            ):
                accepted = match
        else:
            # Of several matches, accept the only one whose cover matches, if any.
            LOGGER.debug("Check Hamming for '%s'", comic)
            hamming_lst = self.cover_matcher.filter_by_hamming_distance(comic, i_list)
            if len(hamming_lst) == 1:
                accepted = hamming_lst[0]

        if accepted is not None:
            return self._resolve_search(filename, accepted, [], config)
        # For the prompt: the cover search's candidates (closest cover first), then
        # this search's results in cover-date order.
        listed = {issue.id for issue in cover_candidates}
        by_date = sorted(i_list, key=lambda m: m.cover_date)
        candidates = cover_candidates + [i for i in by_date if i.id not in listed]
        return self._resolve_search(filename, None, candidates, config)

    def _search_issues(
        self, metadata: ParsedFilename, params: dict[str, str | int]
    ) -> list[BaseIssue] | None:
        """Search Metron for the filename's issue, on its series name and title first.

        The series and title together (see create_title_query_params) narrow the
        search when the filename parser split the series name in two. If that finds
        nothing, the title is probably a story title rather than part of the series
        name, so the search is run again with `params`, on the series alone.

        Returns:
            The issues found, or None after an API error (already reported by
            MetronClient.call).
        """
        title_params = create_title_query_params(metadata)
        if title_params is not None:
            i_list = self.client.call(
                lambda: self.api.issues_list(params=title_params), "Failed to retrieve data"
            )
            if i_list is None or i_list:
                return i_list
        return self.client.call(
            lambda: self.api.issues_list(params=params), "Failed to retrieve data"
        )

    @staticmethod
    def _cover_search_params(
        metadata: ParsedFilename, series_id: int | None
    ) -> dict[str, str | int] | None:
        """Build the cover search filters from the filename, or None if it lacks them.

        The issue number and year do most of the narrowing: a cover hash on its own
        can't tell apart unrelated covers that are only a few bits apart. A given
        series ID narrows the search more than a year can, so the year isn't needed
        then; it's left out, since a filename year is often the series' start year.
        A filename without an issue number is searched as #1, as the filename search
        does, since that's usually a one-shot or first issue.
        """
        params: dict[str, str | int] = {
            "number": search_issue_number(metadata),
            "cover_hash_max_distance": COVER_SEARCH_MAX_DISTANCE,
        }
        if series_id is not None:
            params["series_id"] = series_id
            return params
        year_text = metadata.get("year")
        if not isinstance(year_text, str) or not (year_text.isascii() and year_text.isdigit()):
            return None
        year = int(year_text)
        if year not in COVER_YEAR_RANGE:
            return None
        params["cover_date_range_after"] = f"{year - COVER_YEAR_TOLERANCE}-01-01"
        params["cover_date_range_before"] = f"{year + COVER_YEAR_TOLERANCE}-12-31"
        return params

    def _search_by_cover(
        self,
        filename: Path,
        comic: Comic,
        config: ProcessingConfig,
        metadata: ParsedFilename,
    ) -> CoverMatches:
        """Search Metron for the comic by its cover hash, issue number, and year.

        Each cover hash is tried in turn (see get_search_hashes) until one gives a
        match _choose_cover_match accepts. Nothing is recorded in the match results:
        the caller decides what to do with what was found.

        Returns:
            The accepted issue, if any. Otherwise the results from every hash tried
            whose series agrees with the filename, closest cover first, for the
            filename search to fall back on: empty if
            the filename lacks a usable year, the cover can't be hashed,
            or nothing matched. An API error ends the search early, keeping what
            was found so far.
        """
        base_params = self._cover_search_params(metadata, config.series_id)
        if base_params is None or self.client.stop_processing:
            # No usable year, or a fatal API error already happened for this comic
            # (for example in the existing-ID lookup).
            return CoverMatches()

        # Results from every hash tried, for the prompt if none is accepted, at each
        # issue's closest distance. (Metron only returns issues with a valid cover
        # hash for cover_hash_near, so every result can be ranked.)
        closest: dict[int, tuple[int, BaseIssue]] = {}
        for search_hash, accept_distance in self.cover_matcher.get_search_hashes(comic):
            params = base_params | {"cover_hash_near": str(search_hash)}
            i_list = self.client.call(
                lambda p=params: self.api.issues_list(params=p), "Failed to retrieve data"
            )
            if i_list is None:
                # API error, already reported by MetronClient.call.
                break

            ranked = self.cover_matcher.rank_by_distance(search_hash, i_list)
            LOGGER.debug(
                "Cover search for '%s': distances %s",
                filename,
                [distance for distance, _ in ranked[:3]],
            )
            accepted = self._choose_cover_match(ranked, accept_distance, config, metadata)
            if accepted is not None:
                return CoverMatches(accepted=accepted)

            for distance, issue in ranked:
                if issue.id not in closest or distance < closest[issue.id][0]:
                    closest[issue.id] = (distance, issue)

        # Only candidates whose series agrees with the filename (or all, with --id) are
        # offered: the others are mostly same-number covers from unrelated series,
        # which would turn a comic that isn't on Metron into a prompt of wrong issues.
        candidates = [
            issue
            for _, issue in sorted(closest.values(), key=lambda p: p[0])
            if config.series_id is not None or self._series_agrees(metadata, issue)
        ]
        return CoverMatches(candidates=candidates)

    def _choose_cover_match(
        self,
        ranked: list[tuple[int, BaseIssue]],
        accept_distance: int,
        config: ProcessingConfig,
        metadata: ParsedFilename,
    ) -> BaseIssue | None:
        """Return the closest cover match if it can be accepted, else None.

        It's accepted if it's within accept_distance, leads the next one by
        COVER_ACCEPT_MARGIN, and its series agrees with the filename. --accept-only
        doesn't loosen this: if the cover match isn't accepted, the filename search
        runs and applies --accept-only to its own single series and number match.

        Args:
            ranked: The results, closest cover first.
            accept_distance: The furthest the closest cover may be: see
                CoverHashMatcher.get_search_hashes.
            config: The processing options.
            metadata: The parsed filename.
        """
        if not ranked:
            return None
        best_distance, best = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else None
        is_close = best_distance <= accept_distance
        is_clear = runner_up is None or runner_up - best_distance >= COVER_ACCEPT_MARGIN
        # With --id the search is already limited to the series, so the filename's
        # series name (which may not match Metron's) isn't checked.
        is_same_series = config.series_id is not None or self._series_agrees(metadata, best)
        if is_close and is_clear and is_same_series:
            return best
        return None

    @staticmethod
    def _series_agrees(metadata: ParsedFilename, issue: BaseIssue) -> bool:
        """Return True if the issue's series name shares a word with the filename's.

        Both the parsed series and title are used, since the filename parser often
        splits a name like "Star Wars - The Book of Boba Fett" into the two.
        """
        filename_text = " ".join(
            str(metadata[key])
            for key in ("series", "title")
            if isinstance(metadata.get(key), str)
        )
        return bool(series_words(filename_text) & series_words(issue.series.name))

    def _resolve_search(
        self,
        filename: Path,
        accepted: BaseIssue | None,
        candidates: list[BaseIssue],
        config: ProcessingConfig,
    ) -> SearchResult:
        """Record how a search for a comic ended, once its search has picked a match.

        The accepted issue, if any, is a good match. Otherwise the comic is skipped
        with --skip-multiple, or its candidates are kept, in the order given, for the
        user to choose from.
        """
        if accepted is not None:
            self.match_results.add_good_match(filename)
            return SearchResult(issue_id=accepted.id, has_multiple_matches=False)

        if config.skip_multiple:
            self.match_results.add_skipped_match(filename)
            return SearchResult(issue_id=None, has_multiple_matches=False)

        self.match_results.add_multiple_match(MultipleMatch(filename, candidates))
        return SearchResult(issue_id=None, has_multiple_matches=True)

    def _process_file(
        self,
        fn: Path,
        config: ProcessingConfig,
        comic: Comic,
    ) -> SearchResult:
        """Find the Metron issue for an opened comic file."""
        if not comic.is_writable() or not comic.seems_to_be_a_comic_archive():
            LOGGER.warning("Comic appears not to be a comic or writable: %s", fn)
            self.ui.print_error(f"{fn.name} appears not to be a comic or writable.")
            return SearchResult(issue_id=None, has_multiple_matches=False)

        # Check if comic has existing metadata with ID
        if existing_id_info := self._get_existing_metadata_id(comic):
            source, id_, modified = existing_id_info
            self.ui.print_metadata_source_message(source, comic)

            if result_id := self._handle_existing_id(source, id_):
                self.match_results.add_good_match(fn)
                return SearchResult(
                    issue_id=result_id,
                    has_multiple_matches=False,
                    modified=None if config.ignore_modified else modified,
                )

        # Search by cover first. If no cover match is accepted, the filename search
        # runs, and its prompt also offers the cover search's candidates.
        parsed: ParsedFilename = comicfn2dict(fn, verbose=0)
        cover = self._search_by_cover(fn, comic, config, parsed)
        if cover.accepted is not None:
            return self._resolve_search(fn, cover.accepted, [], config)
        if self.client.stop_processing:
            return SearchResult(issue_id=None, has_multiple_matches=False)
        return self._search_by_filename(fn, comic, config, parsed, cover.candidates)

    def _print_rate_limit_status(self) -> None:
        """Show the user's remaining daily (sustained) Metron API quota, if known."""
        sustained = self.api.rate_limit_status.sustained
        self.ui.print_rate_limit_status(sustained.remaining, sustained.limit, sustained.reset)

    def _post_process_matches(self) -> None:
        """Post-process the match results."""
        # Print match results summary
        self.ui.print_match_results(self.match_results)

        # Ask about files with multiple matches, unless processing was stopped (a
        # fatal API error, or the user declining to wait out a rate limit): every
        # choice would need another API call.
        for match_set in self.match_results.multiple_matches:
            if self.client.stop_processing:
                self.ui.print_info("Skipping the remaining multiple matches.")
                break
            if issue_id := self._select_choice_from_matches(
                match_set.filename, match_set.matches
            ):
                self._write_issue_md(match_set.filename, issue_id)

    def _write_metadata_formats(self, comic: Comic, metadata: Metadata) -> list[str]:
        """Write metadata in the requested formats."""
        written_formats = []

        for meta_format in self.formats:
            file_name = format_list([meta_format])
            try:
                if comic.write_metadata(metadata, meta_format):
                    written_formats.append(file_name)
            except KeyError:
                LOGGER.warning("Failed to write metadata %s for '%s'.", file_name, comic)

        return written_formats

    def _write_issue_md(
        self,
        filename: Path,
        issue_id: int,
        modified: datetime | None = None,
        comic: Comic | None = None,
    ) -> None:
        """Write metadata for a comic issue.

        Pass `comic` if the file is already open, so it isn't opened again: opening
        is slow for formats like CBR, CB7 and PDF.
        """
        resp = self.client.call(
            lambda: self.api.issue(issue_id, if_modified_since=modified),
            "Failed to retrieve data",
        )
        if resp is None:
            # None is a 304 Not Modified only if the call didn't fail; a failure
            # has already been reported by MetronClient.call.
            if modified is not None and not self.client.last_call_failed:
                self.ui.print_info(
                    f"{filename.name} has not been modified since last tagging."
                )
            return

        if comic is None and (comic := open_comic(filename)) is None:
            return

        meta_data = Metadata()
        meta_data.set_default_page_list(comic.get_number_of_pages())

        md = self.metadata_mapper.map_response_to_metadata(resp)
        md.overlay(meta_data)

        if written_formats := self._write_metadata_formats(comic, md):
            series_format = md.series.format if md.series else None
            collection = bool(series_format) and series_format.lower() in COLLECTION_FORMATS
            self.ui.print_metadata_write_success(
                formats=written_formats,
                series_name=(md.series.name if md.series else None) or "Unknown",
                issue=md.issue or "Unknown",
                year=md.cover_date.year if md.cover_date else 0,
                filename=filename.name,
                is_collection=collection,
            )
        else:
            self.ui.print_error(
                f"There was a problem writing metadata for '{filename.name}'. Check logs for details."
            )

    def _should_skip_existing_metadata(self, comic: Comic, config: ProcessingConfig) -> bool:
        """Check if file should be skipped because it already has a format to be written."""
        if not config.ignore_existing:
            return False
        return any(comic.has_metadata(fmt) for fmt in self.formats)

    def identify_comics(
        self, file_list: list[Path], config: ProcessingConfig | None = None
    ) -> None:
        """Identify and tag comics from a list of files.

        Args:
            file_list: The comics to tag.
            config: How to search and when to skip a comic; the defaults if not given.
        """
        config = config or ProcessingConfig()
        # Reset stop flag at start of processing
        self.client.stop_processing = False

        title_suffix = (
            f" (Series ID: {config.series_id})" if config.series_id is not None else ""
        )
        self.ui.print_title(f"Starting Online Search and Tagging{title_suffix}:")

        for fn in file_list:
            # Check if processing should stop (e.g., rate limit declined)
            if self.client.stop_processing:
                self.ui.print_info("Stopping processing of remaining files.")
                break

            comic = open_comic(fn)
            if comic is None:
                continue

            if self._should_skip_existing_metadata(comic, config):
                self.ui.print_warning(f"{fn.name} has metadata. Skipping...")
                continue

            result = self._process_file(fn, config, comic)

            if result.issue_id:
                self._write_issue_md(fn, result.issue_id, result.modified, comic)
            elif not result.has_multiple_matches:
                self.ui.print_error(f"No Match for '{fn.name}'.")

        # Print match results
        self._post_process_matches()
        self._print_rate_limit_status()

    def retrieve_single_issue(self, id_: int, fn: Path) -> None:
        """Retrieve and write metadata for a single issue."""
        self._write_issue_md(fn, id_)
        self._print_rate_limit_status()
