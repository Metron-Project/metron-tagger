from __future__ import annotations

import io
from datetime import datetime
from enum import Enum, auto, unique
from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from mokkari.schemas.generic import GenericItem
    from mokkari.schemas.issue import BaseIssue, Credit as MokkariCredit, Issue

    from metrontagger.settings import MetronTaggerSettings

import mokkari
import questionary
from comicfn2dict import comicfn2dict
from darkseid.comic import Comic
from darkseid.issue_string import IssueString
from darkseid.metadata import Basic, Credit, Metadata, Role, Series
from imagehash import ImageHash, hex_to_hash, phash
from mokkari.exceptions import ApiError
from PIL import Image

from metrontagger import __version__
from metrontagger.styles import Styles
from metrontagger.utils import create_query_params

LOGGER = getLogger(__name__)
HAMMING_DISTANCE = 10


@unique
class InfoSource(Enum):
    """An enumeration of information sources.

    This class defines different sources of information, including Metron, Comic Vine, and Unknown.
    """

    metron = auto()
    comic_vine = auto()
    unknown = auto()


class MultipleMatch:
    """Class to store multiple matches for a filename.

    This class initializes with a filename and a list of BaseIssue matches.
    """

    def __init__(self: MultipleMatch, filename: Path, match_list: list[BaseIssue]) -> None:
        self.filename = filename
        self.matches = match_list


class OnlineMatchResults:
    """Class to store online match results.

    This class stores good matches, no matches, and multiple matches for online search results.
    """

    def __init__(self: OnlineMatchResults) -> None:
        """Initialize the OnlineMatchResults class.

        This method initializes lists to store good matches, no matches, and multiple matches.
        """
        self.good_matches: list[Path] = []
        self.no_matches: list[Path] = []
        self.multiple_matches: list[MultipleMatch] = []

    def add_good_match(self: OnlineMatchResults, file_name: Path) -> None:
        """Add a good match to the list.

        This method appends a file name to the list of good matches.
        """
        self.good_matches.append(file_name)

    def add_no_match(self: OnlineMatchResults, file_name: Path) -> None:
        """Add a no match to the list.

        This method appends a file name to the list of no matches.
        """
        self.no_matches.append(file_name)

    def add_multiple_match(self: OnlineMatchResults, multi_match: MultipleMatch) -> None:
        """Add a multiple match to the list.

        This method appends a MultipleMatch object to the list of multiple matches.
        """
        self.multiple_matches.append(multi_match)


class Talker:
    """Class for handling online search and tagging of comic files.

    This class provides methods for identifying comics, retrieving single issues, and processing match results.
    """

    def __init__(self: Talker, username: str, password: str) -> None:
        """Initialize the Talker class with API credentials.

        This method sets up the API connection using the provided username and password, and initializes match
        results storage.
        """
        self.api = mokkari.api(username, password, user_agent=f"Metron-Tagger/{__version__}")
        self.match_results = OnlineMatchResults()

    @staticmethod
    def _create_choice_list(match_set: list[BaseIssue]) -> list[questionary.Choice]:
        """Create a list of choices for selecting issues.

        This static method generates a list of choices based on the provided list of BaseIssue objects, including
        issue names and cover dates.

        Args:
            match_set: list[BaseIssue]: The list of BaseIssue objects to create choices from.

        Returns:
            list[questionary.Choice]: A list of choices for selecting issues, including a 'Skip' option.
        """
        issue_lst = []
        for i in match_set:
            c = questionary.Choice(title=f"{i.issue_name} ({i.cover_date})", value=i.id)
            issue_lst.append(c)

        issue_lst.append(questionary.Choice(title="Skip", value=""))
        return issue_lst

    def _select_choice_from_matches(
        self: Talker,
        fn: Path,
        match_set: list[BaseIssue],
    ) -> int | None:
        """Select an issue from a list of matches.

        This method displays the results found for a file, sorts the match list by cover date, and prompts the user
        to select an issue to match.

        Args:
            fn: Path: The file path for which matches are being selected.
            match_set: list[BaseIssue]: The list of BaseIssue objects to choose from.

        Returns:
            int | None: The selected issue ID or None if no selection is made.
        """
        questionary.print(f"\n{fn.name} - Results found:", style=Styles.TITLE)

        # sort match list by cover date
        match_set = sorted(match_set, key=lambda m: m.cover_date)
        choices = self._create_choice_list(match_set)

        return questionary.select("Select an issue to match", choices=choices).ask()

    @staticmethod
    def _get_comic_cover_hash(comic: Comic) -> ImageHash | None:
        """Get the image hash of a comic cover.

        This static method calculates the image hash of the comic cover image using pHash algorithm.

        Args:
            comic: Comic: The Comic object representing the comic.

        Returns:
            ImageHash | None: The image hash of the comic cover, or None if unable to calculate.
        """
        with Image.open(io.BytesIO(comic.get_page(0))) as img:
            try:
                ch = phash(img)
            except OSError:
                questionary.print("Unable to get cover hash.", style=Styles.ERROR)
                ch = None
        return ch

    def _within_hamming_distance(
        self: Talker, comic: Comic, metron_hash: str | None = None
    ) -> bool:
        """Check if the comic cover hash is within the specified Hamming distance.

        This method compares the comic cover hash with a provided hash to determine if they are within the specified
        Hamming distance.
        """
        if metron_hash is None:
            return False
        comic_hash = self._get_comic_cover_hash(comic)
        if comic_hash is None:
            return False
        hamming = comic_hash - hex_to_hash(metron_hash)
        return hamming <= HAMMING_DISTANCE

    def _get_hamming_results(self: Talker, comic: Comic, lst: list[BaseIssue]) -> list[any]:
        """Get the list of BaseIssue objects within the specified Hamming distance.

        This method filters the list of BaseIssue objects based on the Hamming distance between the comic cover hash
        and the cover hash of each item.
        """
        return [item for item in lst if self._within_hamming_distance(comic, item.cover_hash)]

    @staticmethod
    def _get_source_id(md: Metadata) -> tuple[InfoSource, int | None]:
        """Get the information source and ID from metadata.

        This static method extracts the information source and ID from the metadata notes field, returning a tuple of
        InfoSource and ID.
        """

        def _extract_id_str(notes: str, keyword: str) -> str:
            """
            Extracts and returns a specific string segment from the given notes based on the provided keyword.

            Args:
                notes (str): The notes string from which to extract the segment.
                keyword (str): The keyword used to identify the segment to extract.

            Returns:
                str: The extracted string segment.
            """

            return notes.split(keyword)[1].split("]")[0].strip()

        source: InfoSource = InfoSource.unknown
        id_: int | None = None

        # If `Notes` element doesn't exist let's bail.
        if md.notes is None:
            return source, id_

        lower_notes = md.notes.lower()

        id_str = ""
        if "metrontagger" in lower_notes:
            source = InfoSource.metron
            id_str = _extract_id_str(md.notes, "issue_id:")
        elif "comictagger" in lower_notes:
            if "metron" in lower_notes:
                source = InfoSource.metron
            elif "comic vine" in lower_notes:
                source = InfoSource.comic_vine
            else:
                source = InfoSource.unknown
                id_str = _extract_id_str(md.notes, "Issue ID")
        else:
            return source, id_

        try:
            id_ = int(id_str)
        except ValueError:
            LOGGER.exception("Comic has invalid id: %s #%s", md.series.name, md.issue)

        return source, id_

    def _process_file(self: Talker, fn: Path, interactive: bool) -> tuple[int | None, bool]:  # noqa: PLR0912 PLR0915
        """Process a comic file for metadata.

        This method processes a comic file to extract metadata, including checking for existing metadata, extracting
        source and ID information, and handling multiple matches.

        Args:
            fn: Path: The file path of the comic to process.
            interactive: bool: A flag indicating if the process should be interactive.

        Returns: tuple[int | None, bool]: A tuple containing the issue ID and a flag indicating if multiple matches
        were found.
        """
        ca = Comic(fn)

        if not ca.is_writable() and not ca.seems_to_be_a_comic_archive():
            questionary.print(
                f"{fn.name} appears not to be a comic or writable.",
                style=Styles.ERROR,
            )
            return None, False

        # Check if comic has a comicinfo.xml that contains either a cvid or metron id.
        if ca.has_metadata():
            md = ca.read_metadata()
            source, id_ = self._get_source_id(md)
            if source is not InfoSource.unknown and id_ is not None:

                def _print_metadata_message(src: InfoSource, comic: Comic) -> None:
                    source_messages = {
                        InfoSource.metron: "Metron ID",
                        InfoSource.comic_vine: "ComicVine",
                    }
                    if src in source_messages:
                        questionary.print(
                            f"Found {source_messages[src]} in '{comic}' metadata and using that to get the metadata...",
                            style=Styles.INFO,
                        )

                _print_metadata_message(source, ca)

                match source:
                    case InfoSource.metron:
                        self.match_results.add_good_match(fn)
                        return id_, False
                    case InfoSource.comic_vine:
                        issues = self.api.issues_list(params={"cv_id": id_})
                        # This should always be 1 otherwise let's do a regular search.
                        if len(issues) == 1:
                            return issues[0].id, False
                    case _:
                        pass

        # Alright, if the comic doesn't have an let's do a search based on the filename.
        # TODO: Determine if we want to use some of the other keys beyond 'series' and 'issue number'
        metadata: dict[str, str | tuple[str, ...]] = comicfn2dict(fn, verbose=0)

        params = create_query_params(metadata)
        i_list = self.api.issues_list(params=params)
        result_count = len(i_list)

        issue_id = None
        multiple_match = False
        if result_count <= 0:
            issue_id = None
            self.match_results.add_no_match(fn)
            multiple_match = False
        elif result_count > 1:
            # Let's use the cover hash to try to narrow down the results
            LOGGER.debug("Check Hamming for '%s'", ca)
            if hamming_lst := self._get_hamming_results(ca, i_list):
                if len(hamming_lst) == 1:
                    issue_id = hamming_lst[0].id
                    self.match_results.add_good_match(fn)
                # TODO: Need to handle situation where *None* of the choices match.
                elif issue_id := self._select_choice_from_matches(fn, hamming_lst):
                    self.match_results.add_good_match(fn)
            else:
                issue_id = None
                self.match_results.add_multiple_match(MultipleMatch(fn, i_list))
                multiple_match = True
        elif result_count == 1:
            # Let's see if the cover is correct otherwise ask for user to select issue.
            if not interactive and self._within_hamming_distance(ca, i_list[0].cover_hash):
                issue_id = i_list[0].id
                self.match_results.add_good_match(fn)
            else:
                issue_id = self._select_choice_from_matches(fn, i_list)
                if issue_id:
                    self.match_results.add_good_match(fn)
            multiple_match = False

        return issue_id, multiple_match

    def _post_process_matches(self: Talker) -> None:
        """Post-process the match results.

        This method prints the successful matches and no matches, and handles files with multiple matches by
        selecting an issue to write metadata for.
        """
        # Print file matching results.
        if self.match_results.good_matches:
            questionary.print("\nSuccessful matches:\n------------------", style=Styles.TITLE)
            for comic in self.match_results.good_matches:
                questionary.print(f"{comic}", style=Styles.SUCCESS)

        if self.match_results.no_matches:
            questionary.print("\nNo matches:\n------------------", style=Styles.TITLE)
            for comic in self.match_results.no_matches:
                questionary.print(f"{comic}", style=Styles.WARNING)

        # Handle files with multiple matches
        if self.match_results.multiple_matches:
            for match_set in self.match_results.multiple_matches:
                if issue_id := self._select_choice_from_matches(
                    match_set.filename,
                    match_set.matches,
                ):
                    self._write_issue_md(match_set.filename, issue_id)

    def _write_issue_md(self: Talker, filename: Path, issue_id: int) -> None:
        """Write metadata for an issue.

        This method retrieves issue data, overlays it with existing metadata, and writes the metadata to the comic file.
        """
        # sourcery skip: extract-method, inline-immediately-returned-variable
        success = False
        resp = None
        md = None
        try:
            resp = self.api.issue(issue_id)
        except ApiError as e:
            questionary.print(f"Failed to retrieve data: {e!r}", style=Styles.ERROR)
        if resp is not None:
            ca = Comic(str(filename))
            meta_data = Metadata()
            meta_data.set_default_page_list(ca.get_number_of_pages())
            md = self._map_resp_to_metadata(resp)
            md.overlay(meta_data)
            success = ca.write_metadata(md)

        if success and md is not None:
            collection = md.series.format.lower() in ["trade paperback", "hard cover"]
            collection_text = " (Collection)" if collection else ""
            msg = (
                f"Using '{md.series.name} #{md.issue} ({md.cover_date.year}){collection_text}' "
                f"metadata for '{filename.name}'."
            )
            questionary.print(msg, style=Styles.SUCCESS)
        else:
            questionary.print(
                f"There was a problem writing metadata for '{filename.name}'.",
                style=Styles.ERROR,
            )

    def identify_comics(
        self: Talker,
        file_list: list[Path],
        config: MetronTaggerSettings,
    ) -> None:
        """Identify and tag comics from a list of files.

        This method initiates an online search and tagging process for each file in the provided list, skipping files
        with existing metadata and handling multiple matches.

        Args:
            file_list: list[Path]: A list of file paths to process.
            config: MetronTaggerSettings: The configuration settings for the tagging process.

        Returns:
            None
        """
        questionary.print(
            "\nStarting online search and tagging:\n----------------------------------",
            style=Styles.TITLE,
        )

        for fn in file_list:
            if config.ignore_existing:
                comic_archive = Comic(str(fn))
                if comic_archive.has_metadata():
                    questionary.print(
                        f"{fn.name} has metadata. Skipping...",
                        style=Styles.WARNING,
                    )
                    continue

            issue_id, multiple_match = self._process_file(fn, config.interactive)
            if issue_id:
                self._write_issue_md(fn, issue_id)
            elif not multiple_match:
                questionary.print(f"No Match for '{fn.name}'.", style=Styles.ERROR)

        # Print match results
        self._post_process_matches()

    def retrieve_single_issue(self: Talker, fn: Path, id_: int) -> None:
        """Retrieve and write metadata for a single issue.

        This method retrieves metadata for a single issue using the provided ID and writes the metadata to the
        corresponding file.
        """
        self._write_issue_md(fn, id_)

    @staticmethod
    def _map_resp_to_metadata(resp: Issue) -> Metadata:
        """Map response data to metadata.

        This static method maps the response data from an Issue object to a Metadata object, including information
        such as series, issue number, publisher, cover date, and additional metadata details.
        """

        # Helper functions
        def create_resource_list(resource: any) -> list[Basic]:
            """Create a list of Basic objects from a given resource.

            This function takes a resource and generates a list of Basic objects with name and ID attributes.
            """
            return [Basic(r.name, r.id) for r in resource]

        def create_note(issue_id: int) -> str:
            """Create a note for an issue.

            This function generates a note string including tagging information from MetronTagger and the issue ID.
            """
            now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
            return (
                f"Tagged with MetronTagger-{__version__} using info from Metron on "
                f"{now_date}. [issue_id:{issue_id}]"
            )

        def add_credits_to_metadata(
            meta_data: Metadata,
            credits_resp: list[MokkariCredit],
        ) -> Metadata:
            """Add credits to metadata.

            This function adds credits information to the metadata object based on the provided credits response.

            Args:
                meta_data: Metadata: The metadata object to add credits to.
                credits_resp: list[MokkariCredit]: The list of credits information to add.

            Returns:
                Metadata: The updated metadata object with added credits.
            """

            def create_role_list(roles: list[GenericItem]) -> list[Role]:
                """Create a list of Role objects from a list of GenericItem objects.

                This function converts a list of GenericItem objects representing roles into a list of Role objects
                with name and ID attributes.
                """
                return [Role(r.name, r.id) for r in roles]

            for c in credits_resp:
                if c.role:
                    meta_data.add_credit(Credit(c.creator, create_role_list(c.role), c.id))
                else:
                    meta_data.add_credit(Credit(c.creator, [], c.id))
            return meta_data

        def map_ratings(rating: str) -> str:
            """Map a rating string to a standardized format.

            This function maps a given rating string to a standardized format ('Everyone', 'Teen', 'Mature 17+',
            or 'Unknown').

            Args:
                rating: str: The rating string to map.

            Returns:
                str: The standardized rating.
            """
            age_rating = rating.lower()
            if age_rating in {"everyone", "cca"}:
                return "Everyone"
            if age_rating in {"teen", "teen plus"}:
                return "Teen"
            return "Mature 17+" if age_rating == "mature" else "Unknown"

        md = Metadata()
        md.info_source = Basic("Metron", resp.id)
        md.series = Series(
            resp.series.name,
            resp.series.id,
            resp.series.sort_name,
            resp.series.volume,
            resp.series.series_type.name,
        )
        md.issue = IssueString(resp.number).as_string()
        md.publisher = Basic(resp.publisher.name, resp.publisher.id)
        md.cover_date = resp.cover_date
        md.comments = resp.desc
        md.notes = create_note(md.info_source.id_)
        if resp.story_titles:
            md.stories = [Basic(story) for story in resp.story_titles]
        if resp.characters:
            md.characters = create_resource_list(resp.characters)
        if resp.teams:
            md.teams = create_resource_list(resp.teams)
        if resp.arcs:
            md.story_arcs = create_resource_list(resp.arcs)
        if resp.series.genres:
            md.genres = create_resource_list(resp.series.genres)
        if resp.reprints:
            md.reprints = [Basic(r.issue, r.id) for r in resp.reprints]
        if resp.credits:
            md = add_credits_to_metadata(md, resp.credits)
        if resp.rating:
            md.age_rating = map_ratings(resp.rating.name)
        if resp.resource_url:
            md.web_link = str(resp.resource_url)

        return md
