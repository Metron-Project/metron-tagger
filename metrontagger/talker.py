from __future__ import annotations

__all__ = ["Talker"]

import io
import warnings
from datetime import datetime
from enum import Enum, auto, unique
from functools import lru_cache
from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path

    from mokkari.schemas.generic import GenericItem
    from mokkari.schemas.issue import BaseIssue, Credit as MokkariCredit, Issue

import mokkari
import questionary
from comicfn2dict import comicfn2dict
from darkseid.comic import Comic, ComicArchiveError, MetadataFormat
from darkseid.issue_string import IssueString
from darkseid.metadata import (
    AgeRatings,
    Arc,
    Basic,
    Credit,
    InfoSources,
    Links,
    Metadata,
    Notes,
    Publisher,
    Role,
    Series,
    Universe,
)
from darkseid.utils import get_issue_id_from_note
from imagehash import ImageHash, hex_to_hash, phash
from mokkari.exceptions import ApiError, RateLimitError
from PIL import Image

from metrontagger import __version__
from metrontagger.styles import Styles
from metrontagger.utils import create_print_title, create_query_params

LOGGER = getLogger(__name__)

warnings.filterwarnings(
    "ignore", category=UserWarning
)  # Ignore 'UserWarning: Corrupt EXIF data' warnings

HAMMING_DISTANCE = 10


@unique
class InfoSource(Enum):
    """An enumeration of information sources.

    This class defines different sources of information, including Metron, Comic Vine, and Unknown.
    """

    METRON = auto()
    COMIC_VINE = auto()
    UNKNOWN = auto()


class MultipleMatch:
    """Class to store multiple matches for a filename.

    This class initializes with a filename and a list of BaseIssue matches.
    """

    def __init__(self, filename: Path, match_list: list[BaseIssue]) -> None:
        self.filename = filename
        self.matches = match_list


class OnlineMatchResults:
    """Class to store online match results.

    This class stores good matches, no matches, and multiple matches for online search results.
    """

    def __init__(self) -> None:
        """Initialize the OnlineMatchResults class.

        This method initializes lists to store good matches, no matches, and multiple matches.
        """
        self.good_matches: list[Path] = []
        self.no_matches: list[Path] = []
        self.multiple_matches: list[MultipleMatch] = []

    def add_good_match(self, file_name: Path) -> None:
        """Add a good match to the list."""
        self.good_matches.append(file_name)

    def add_no_match(self, file_name: Path) -> None:
        """Add a no match to the list."""
        self.no_matches.append(file_name)

    def add_multiple_match(self, multi_match: MultipleMatch) -> None:
        """Add a multiple match to the list."""
        self.multiple_matches.append(multi_match)


class MetadataExtractor:
    """Handles extraction of metadata from comic files."""

    @staticmethod
    def get_id_from_metron_info(md: Metadata) -> tuple[InfoSource, int] | None:
        """Extract ID from MetronInfo metadata."""
        online_sources = {"metron", "comic vine"}
        for src in md.info_source:
            lower_name = src.name.lower()
            if lower_name in online_sources:
                return (
                    InfoSource.METRON if lower_name == "metron" else InfoSource.COMIC_VINE,
                    src.id_,
                )
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
            LOGGER.exception("Comic has invalid id: %s #%s", md.series.name, md.issue)
            return None

        return src, id_


class CoverHashMatcher:
    """Handles cover hash matching for comics."""

    @staticmethod
    @lru_cache(maxsize=128)
    def get_comic_cover_hash_cached(comic: Comic) -> ImageHash | None:
        """Get the image hash of a comic cover.

        Args:
            comic: The Comic object representing the comic.

        Returns:
            The image hash of the comic cover, or None if unable to calculate.
        """
        try:
            with Image.open(io.BytesIO(comic.get_page(0))) as img:
                return phash(img)
        except OSError:
            questionary.print("Unable to get cover hash.", style=Styles.ERROR)
            return None

    @classmethod
    def is_within_hamming_distance(cls, comic: Comic, metron_hash: str | None = None) -> bool:
        """Check if the comic cover hash is within the specified Hamming distance."""
        if metron_hash is None:
            return False

        comic_hash = cls.get_comic_cover_hash_cached(comic)
        if comic_hash is None:
            return False
        try:
            hamming = comic_hash - hex_to_hash(metron_hash)
        except ValueError:
            LOGGER.exception("Failed to get Hamming distance for comic %s", comic.name)
            return False

        return hamming <= HAMMING_DISTANCE

    @classmethod
    def filter_by_hamming_distance(
        cls, comic: Comic, issue_list: list[BaseIssue]
    ) -> list[BaseIssue]:
        """Get the list of BaseIssue objects within the specified Hamming distance."""
        return [
            item
            for item in issue_list
            if cls.is_within_hamming_distance(comic, item.cover_hash)
        ]


class MetadataMapper:
    """Handles mapping of API responses to metadata objects."""

    @staticmethod
    def create_resource_list(resource) -> list[Basic]:
        """Create a list of Basic objects from a given resource."""
        return [Basic(r.name, r.id) for r in resource]

    @staticmethod
    def create_arc_list(resource) -> list[Arc]:
        """Create a list of Arc objects from a given resource."""
        return [Arc(item.name, item.id) for item in resource]

    @staticmethod
    def create_notes(issue_id: int) -> Notes:
        """Create a note for an issue."""
        now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
        metron_info_note = (
            f"Tagged with MetronTagger-{__version__} using info from Metron on {now_date}."
        )
        comic_rack_note = f"{metron_info_note} [issue_id:{issue_id}]"
        return Notes(metron_info=metron_info_note, comic_rack=comic_rack_note)

    @staticmethod
    def create_role_list(roles: list[GenericItem]) -> list[Role]:
        """Create a list of Role objects from a list of GenericItem objects."""
        return [Role(r.name, r.id) for r in roles]

    @classmethod
    def add_credits_to_metadata(
        cls, meta_data: Metadata, credits_resp: list[MokkariCredit]
    ) -> Metadata:
        """Add credits to metadata."""
        for c in credits_resp:
            roles = cls.create_role_list(c.role) if c.role else []
            meta_data.add_credit(Credit(c.creator, roles, c.id))
        return meta_data

    @staticmethod
    def map_ratings(rating: str) -> AgeRatings:
        """Map a rating string to a standardized format."""
        age_rating = rating.lower()

        rating_map = {
            ("everyone", "cca"): ("Everyone", "Everyone"),
            "teen": ("Teen", "Teen"),
            "teen plus": ("Teen Plus", "Teen"),
            ("mature",): ("Mature", "Mature 17+"),
        }

        for rating_keys, (metron_rating, comic_rack_rating) in rating_map.items():
            if age_rating in rating_keys:
                return AgeRatings(metron_info=metron_rating, comic_rack=comic_rack_rating)

        return AgeRatings(metron_info="Unknown", comic_rack="Unknown")

    @classmethod
    def map_response_to_metadata(cls, resp: Issue) -> Metadata:  # noqa: PLR0912
        """Map response data to metadata."""
        md = Metadata()

        # Set info sources
        alt_info_sources = []
        if resp.cv_id:
            alt_info_sources.append(InfoSources("Comic Vine", resp.cv_id))
        if resp.gcd_id:
            alt_info_sources.append(InfoSources("Grand Comics Database", resp.gcd_id))

        # Should always have Metron as a primary source
        md.info_source = [InfoSources("Metron", resp.id, True), *alt_info_sources]

        # Set series information
        md.series = Series(
            name=resp.series.name,
            id_=resp.series.id,
            sort_name=resp.series.sort_name,
            volume=resp.series.volume,
            format=resp.series.series_type.name,
            start_year=resp.series.year_began,
        )

        # Set basic issue information
        md.issue = IssueString(resp.number).as_string() if resp.number else None
        md.cover_date = resp.cover_date
        md.store_date = resp.store_date
        md.comments = resp.desc
        md.notes = cls.create_notes(resp.id)
        md.modified = resp.modified

        # Set publisher information
        if resp.publisher:
            md.publisher = Publisher(resp.publisher.name, resp.publisher.id)
            if resp.imprint:
                md.publisher.imprint = Basic(resp.imprint.name, resp.imprint.id)

        # Set optional collections and lists
        if resp.story_titles:
            md.stories = [Basic(story) for story in resp.story_titles]
        if resp.collection_title:
            md.collection_title = resp.collection_title
        if resp.characters:
            md.characters = cls.create_resource_list(resp.characters)
        if resp.teams:
            md.teams = cls.create_resource_list(resp.teams)
        if resp.arcs:
            md.story_arcs = cls.create_arc_list(resp.arcs)
        if resp.series.genres:
            md.genres = cls.create_resource_list(resp.series.genres)
        if resp.reprints:
            md.reprints = [Basic(r.issue, r.id) for r in resp.reprints]
        if resp.universes:
            md.universes = [Universe(uni.name, uni.id) for uni in resp.universes]
        if resp.credits:
            md = cls.add_credits_to_metadata(md, resp.credits)
        if resp.rating:
            md.age_rating = cls.map_ratings(resp.rating.name)
        if resp.resource_url:
            md.web_link = [Links(str(resp.resource_url), True)]

        return md


class Talker:
    """Class for handling online search and tagging of comic files.

    This class provides methods for identifying comics, retrieving single issues, and processing match results.
    """

    def __init__(
        self, username: str, password: str, metron_info: bool, comic_info: bool
    ) -> None:
        """Initialize the Talker class with API credentials."""
        self.api = mokkari.api(username, password, user_agent=f"Metron-Tagger/{__version__}")
        self.metron_info = metron_info
        self.comic_info = comic_info
        self.match_results = OnlineMatchResults()
        self.metadata_extractor = MetadataExtractor()
        self.cover_matcher = CoverHashMatcher()
        self.metadata_mapper = MetadataMapper()

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
        """Select an issue from a list of matches."""
        questionary.print(f"\n{fn.name} - Results found:", style=Styles.TITLE)

        # sort match list by cover date
        match_set = sorted(match_set, key=lambda m: m.cover_date)
        choices = self._create_choice_list(match_set)

        return questionary.select("Select an issue to match", choices=choices).ask()

    def _get_existing_metadata_id(self, comic: Comic) -> tuple[InfoSource, int] | None:
        """Get existing metadata ID from comic if available."""
        metadata_formats = [
            (MetadataFormat.METRON_INFO, self.metadata_extractor.get_id_from_metron_info),
            (MetadataFormat.COMIC_INFO, self.metadata_extractor.get_id_from_comic_info),
        ]

        for format_type, extractor_func in metadata_formats:
            if not comic.has_metadata(format_type):
                continue

            try:
                md = comic.read_metadata(format_type)
                if md is not None and (result := extractor_func(md)):
                    return result
            except KeyError:
                format_name = (
                    "MetronInfo.xml"
                    if format_type == MetadataFormat.METRON_INFO
                    else "ComicInfo.xml"
                )
                LOGGER.warning("Unable to find %s. File: %s", format_name, comic)

        return None

    @staticmethod
    def _print_metadata_message(source: InfoSource, comic: Comic) -> None:
        """Print appropriate message based on metadata source."""
        source_messages = {
            InfoSource.METRON: ("Metron ID", Styles.INFO),
            InfoSource.COMIC_VINE: ("ComicVine", Styles.INFO),
            InfoSource.UNKNOWN: ("Unknown Source", Styles.WARNING),
        }

        if source in source_messages:
            message_text, style = source_messages[source]
            if source != InfoSource.UNKNOWN:
                questionary.print(
                    f"Found {message_text} in '{comic}' metadata and using that to get the metadata...",
                    style=style,
                )
            else:
                questionary.print(
                    f"Found {message_text} in '{comic}' metadata. Skipping...",
                    style=style,
                )

    def _handle_existing_id(self, source: InfoSource, id_: int) -> int | None:
        """Handle cases where we have an existing ID from metadata."""
        if source == InfoSource.METRON:
            return id_
        if source == InfoSource.COMIC_VINE:
            try:
                issues = self.api.issues_list(params={"cv_id": id_})
            except RateLimitError as e:
                LOGGER.debug("Rate limit exceeded: %s", e)
                questionary.print(f"{e!s}", style=Styles.WARNING)
                return None
            except ApiError as e:
                LOGGER.exception("Failed to retrieve data")
                questionary.print(f"Failed to retrieve data: {e!r}", style=Styles.ERROR)
                return None

            # This should always be 1 otherwise let's do a regular search.
            if len(issues) == 1:
                return issues[0].id
        return None

    def _search_by_filename(  # noqa: PLR0911
        self,
        filename: Path,
        comic: Comic,
        series_id: int | None = None,
        accept_only: bool = False,
    ) -> tuple[int | None, bool]:
        """Search for comic by filename parsing."""
        metadata: dict[str, str | tuple[str, ...]] = comicfn2dict(filename, verbose=0)
        if series_id is not None:
            metadata["series_id"] = str(series_id)

        params = create_query_params(metadata)
        if params is None:
            questionary.print(
                f"Unable to correctly parse filename: {filename.name}", style=Styles.ERROR
            )
            return None, False

        try:
            i_list = self.api.issues_list(params=params)
        except RateLimitError as e:
            LOGGER.debug("Rate limit exceeded: %s", e)
            questionary.print(f"{e!s}", style=Styles.WARNING)
            return None, False
        except ApiError as e:
            LOGGER.exception("Failed to retrieve data")
            questionary.print(f"Failed to retrieve data: {e!r}", style=Styles.ERROR)
            return None, False

        result_count = len(i_list)

        # No matches
        if result_count <= 0:
            self.match_results.add_no_match(filename)
            return None, False

        # Multiple matches - check hamming distance
        if result_count > 1:
            LOGGER.debug("Check Hamming for '%s'", comic)
            hamming_lst = self.cover_matcher.filter_by_hamming_distance(comic, i_list)

            # Matched single cover within hamming distance from multiple results
            if hamming_lst and len(hamming_lst) == 1:
                self.match_results.add_good_match(filename)
                return hamming_lst[0].id, False

            # No hamming match, let's ask the user later.
            self.match_results.add_multiple_match(MultipleMatch(filename, i_list))
            return None, True

        # Single match - check hamming distance or accept if auto-accept is enabled
        single_match = i_list[0]
        return self._handle_single_match(filename, comic, single_match, accept_only)

    def _handle_single_match(
        self, filename: Path, comic: Comic, match: BaseIssue, accept_only: bool = False
    ) -> tuple[int | None, bool]:
        """Handle single match results."""
        if self.cover_matcher.is_within_hamming_distance(comic, match.cover_hash):
            self.match_results.add_good_match(filename)
            return match.id, False

        # If --accept-only flag is set, automatically accept the single match
        if accept_only:
            self.match_results.add_good_match(filename)
            return match.id, False

        # Otherwise, add to multiple matches to ask the user later
        self.match_results.add_multiple_match(MultipleMatch(filename, [match]))
        return None, True

    def _process_file(
        self, fn: Path, accept_only: bool = False, series_id: int | None = None
    ) -> tuple[int | None, bool]:
        """Process a comic file for metadata."""
        try:
            comic = Comic(fn)
        except ComicArchiveError:
            LOGGER.exception("Comic not valid: %s", str(fn))
            return None, False

        if not comic.is_writable() or not comic.seems_to_be_a_comic_archive():
            LOGGER.exception("Comic appears not to be a comic or writable: %s", str(fn))
            questionary.print(
                f"{fn.name} appears not to be a comic or writable.",
                style=Styles.ERROR,
            )
            return None, False

        # Check if comic has existing metadata with ID
        if existing_id_info := self._get_existing_metadata_id(comic):
            source, id_ = existing_id_info
            self._print_metadata_message(source, comic)

            if result_id := self._handle_existing_id(source, id_):
                self.match_results.add_good_match(fn)
                return result_id, False

        # Search by filename if no existing metadata or ID handling failed
        return self._search_by_filename(fn, comic, series_id, accept_only)

    def _post_process_matches(self) -> None:
        """Post-process the match results."""
        # Print successful matches
        if self.match_results.good_matches:
            msg = create_print_title("Successful Matches:")
            questionary.print(msg, style=Styles.TITLE)
            for comic in self.match_results.good_matches:
                questionary.print(f"{comic}", style=Styles.SUCCESS)

        # Print no matches
        if self.match_results.no_matches:
            msg = create_print_title("No Matches:")
            questionary.print(msg, style=Styles.TITLE)
            for comic in self.match_results.no_matches:
                questionary.print(f"{comic}", style=Styles.WARNING)

        # Handle files with multiple matches
        if self.match_results.multiple_matches:
            for match_set in self.match_results.multiple_matches:
                if issue_id := self._select_choice_from_matches(
                    match_set.filename, match_set.matches
                ):
                    self._write_issue_md(match_set.filename, issue_id)

    def _write_metadata_formats(self, comic: Comic, metadata: Metadata) -> list[str]:
        """Write metadata in the requested formats."""
        written_formats = []

        format_configs = [
            (MetadataFormat.COMIC_INFO, "'ComicInfo.xml'", self.comic_info),
            (MetadataFormat.METRON_INFO, "'MetronInfo.xml'", self.metron_info),
        ]

        for meta_format, file_name, should_write in format_configs:
            if should_write:
                try:
                    if comic.write_metadata(metadata, meta_format):
                        written_formats.append(file_name)
                except KeyError:
                    LOGGER.warning("Failed to write metadata %s for '%s'.", file_name, comic)

        return written_formats

    def _write_issue_md(self, filename: Path, issue_id: int) -> None:
        """Write metadata for a comic issue."""
        try:
            resp = self.api.issue(issue_id)
        except RateLimitError as e:
            LOGGER.debug("Rate limit exceeded: %s", e)
            questionary.print(f"{e!s}", style=Styles.WARNING)
            return
        except ApiError as e:
            LOGGER.exception("Failed to retrieve data")
            questionary.print(f"Failed to retrieve data: {e!r}", style=Styles.ERROR)
            return

        try:
            comic = Comic(filename)
        except ComicArchiveError:
            LOGGER.exception("Comic not valid: %s", str(filename))
            questionary.print(
                f"{filename.name} appears not to be a comic. Skipping...", style=Styles.ERROR
            )
            return

        meta_data = Metadata()
        meta_data.set_default_page_list(comic.get_number_of_pages())

        md = self.metadata_mapper.map_response_to_metadata(resp)
        md.overlay(meta_data)

        if written_formats := self._write_metadata_formats(comic, md):
            collection = md.series.format.lower() in ["trade paperback", "hard cover"]
            collection_text = " (Collection)" if collection else ""
            fmt = " and ".join(written_formats)
            msg = (
                f"Writing {fmt} metadata using "
                f"'{md.series.name} #{md.issue} ({md.cover_date.year}){collection_text}' "
                f"for '{filename.name}'."
            )
            questionary.print(msg, style=Styles.SUCCESS)
        else:
            questionary.print(
                f"There was a problem writing metadata for '{filename.name}'. Check logs for details.",
                style=Styles.ERROR,
            )

    def _should_skip_existing_metadata(self, args: Namespace, comic: Comic) -> bool:
        """Check if file should be skipped due to existing metadata."""
        if not args.ignore_existing:
            return False

        has_comic_rack = comic.has_metadata(MetadataFormat.COMIC_INFO)
        has_metron_info = comic.has_metadata(MetadataFormat.METRON_INFO)

        return (has_comic_rack and self.comic_info) or (has_metron_info and self.metron_info)

    def identify_comics(self, args: Namespace, file_list: list[Path]) -> None:
        """Identify and tag comics from a list of files."""
        title_suffix = f" (Series ID: {args.id})" if args.id is not None else ""
        msg = create_print_title(f"Starting Online Search and Tagging{title_suffix}:")
        questionary.print(msg, style=Styles.TITLE)

        for fn in file_list:
            try:
                comic = Comic(fn)
            except ComicArchiveError:
                LOGGER.exception("Comic not valid: %s", str(fn))
                questionary.print(
                    f"{fn.name} appears not to be a comic. Skipping...", style=Styles.ERROR
                )
                continue

            if self._should_skip_existing_metadata(args, comic):
                questionary.print(
                    f"{fn.name} has metadata. Skipping...",
                    style=Styles.WARNING,
                )
                continue

            issue_id, multiple_match = self._process_file(
                fn, args.accept_only, series_id=args.id
            )

            if issue_id:
                self._write_issue_md(fn, issue_id)
            elif not multiple_match:
                questionary.print(f"No Match for '{fn.name}'.", style=Styles.ERROR)

        # Print match results
        self._post_process_matches()

    def retrieve_single_issue(self, id_: int, fn: Path) -> None:
        """Retrieve and write metadata for a single issue."""
        self._write_issue_md(fn, id_)
