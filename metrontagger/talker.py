import io
from datetime import datetime
from pathlib import Path
from typing import Optional

import mokkari
import questionary
from darkseid.comic import Comic
from darkseid.issue_string import IssueString
from darkseid.metadata import Basic, Credit, Metadata, Role, Series
from imagehash import ImageHash, hex_to_hash, phash
from mokkari.exceptions import ApiError
from mokkari.issue import CreditsSchema, IssueSchema, RolesSchema
from PIL import Image

from metrontagger import __version__
from metrontagger.settings import MetronTaggerSettings
from metrontagger.styles import Styles
from metrontagger.utils import create_query_params

HAMMING_DISTANCE = 10


class MultipleMatch:
    """Class to hold information on searches with multiple matches"""

    def __init__(self: "MultipleMatch", filename: Path, match_list: list[IssueSchema]) -> None:
        self.filename = filename
        self.matches = match_list


class OnlineMatchResults:
    """Class to track online match results"""

    def __init__(self: "OnlineMatchResults") -> None:
        self.good_matches: list[Path] = []
        self.no_matches: list[Path] = []
        self.multiple_matches: list[MultipleMatch] = []

    def add_good_match(self: "OnlineMatchResults", file_name: Path) -> None:
        self.good_matches.append(file_name)

    def add_no_match(self: "OnlineMatchResults", file_name: Path) -> None:
        self.no_matches.append(file_name)

    def add_multiple_match(self: "OnlineMatchResults", multi_match: MultipleMatch) -> None:
        self.multiple_matches.append(multi_match)


class Talker:
    def __init__(self: "Talker", username: str, password: str) -> None:
        self.api = mokkari.api(username, password, user_agent=f"Metron-Tagger/{__version__}")
        self.match_results = OnlineMatchResults()

    @staticmethod
    def _create_choice_list(match_set: list[IssueSchema]) -> list[questionary.Choice]:
        issue_lst = []
        for i in match_set:
            c = questionary.Choice(title=f"{i.issue_name} ({i.cover_date})", value=i.id)
            issue_lst.append(c)

        issue_lst.append(questionary.Choice(title="Skip", value=""))
        return issue_lst

    def _select_choice_from_matches(
        self: "Talker",
        fn: Path,
        match_set: list[IssueSchema],
    ) -> Optional[int]:
        """
        Function to ask user to choice which issue metadata to write,
        when there are multiple choices
        """
        questionary.print(f"\n{fn.name} - Results found:", style=Styles.TITLE)

        # sort match list by cover date
        match_set = sorted(match_set, key=lambda m: m.cover_date)
        choices = self._create_choice_list(match_set)

        return questionary.select("Select an issue to match", choices=choices).ask()

    @staticmethod
    def _get_comic_cover_hash(comic: Comic) -> Optional[ImageHash]:
        with Image.open(io.BytesIO(comic.get_page(0))) as img:
            try:
                ch = phash(img)
            except OSError:
                questionary.print("Unable to get cover hash.", style=Styles.ERROR)
                ch = None
        return ch

    @staticmethod
    def _get_cover_hamming_results(cover_hash: ImageHash, lst: list) -> list[any]:
        hamming_lst = []
        for item in lst:
            hamming = cover_hash - hex_to_hash(item.cover_hash)
            if hamming <= HAMMING_DISTANCE:
                hamming_lst.append(item)
        return hamming_lst

    def _process_file(
        self: "Talker",
        fn: Path,
        interactive: bool,
    ) -> tuple[Optional[int], bool]:
        ca = Comic(fn)

        if not ca.is_writable() and not ca.seems_to_be_a_comic_archive():
            questionary.print(
                f"{fn.name} appears not to be a comic or writable.",
                style=Styles.ERROR,
            )
            return None, False

        params = create_query_params(fn)
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
            if hamming_lst := self._get_cover_hamming_results(
                self._get_comic_cover_hash(ca),
                i_list,
            ):
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
            if not interactive:
                issue_id = i_list[0].id
                self.match_results.add_good_match(fn)
            else:
                issue_id = self._select_choice_from_matches(fn, i_list)
                if issue_id:
                    self.match_results.add_good_match(fn)
            multiple_match = False

        return issue_id, multiple_match

    def _post_process_matches(self: "Talker") -> None:
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

    def _write_issue_md(self: "Talker", filename: Path, issue_id: int) -> None:
        # sourcery skip: extract-method, inline-immediately-returned-variable
        success = False
        resp = None
        try:
            resp = self.api.issue(issue_id)
        except ApiError as e:
            questionary.print(f"Failed to retrieve data: {e!r}", style=Styles.ERROR)
        if resp is not None:
            ca = Comic(filename)
            meta_data = Metadata()
            meta_data.set_default_page_list(ca.get_number_of_pages())
            md = self._map_resp_to_metadata(resp)
            md.overlay(meta_data)
            success = ca.write_metadata(md)

        if success:
            questionary.print(
                f"Using '{md.series.name} #{md.issue} ({md.cover_date.year})' metadata for "
                f"'{filename.name}'.",
                style=Styles.SUCCESS,
            )
        else:
            questionary.print(
                f"There was a problem writing metadata for '{filename.name}'.",
                style=Styles.ERROR,
            )

    def identify_comics(
        self: "Talker",
        file_list: list[Path],
        config: MetronTaggerSettings,
    ) -> None:
        questionary.print(
            "\nStarting online search and tagging:\n----------------------------------",
            style=Styles.TITLE,
        )

        for fn in file_list:
            if config.ignore_existing:
                comic_archive = Comic(fn)
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

    def retrieve_single_issue(self: "Talker", fn: Path, id_: int) -> None:
        self._write_issue_md(fn, id_)

    @staticmethod
    def _map_resp_to_metadata(resp: IssueSchema) -> Metadata:  # C901
        # Helper functions
        def create_resource_list(resource: any) -> list[Basic]:
            return [Basic(r.name, r.id) for r in resource]

        def create_note(issue_id: int) -> str:
            now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
            return (
                f"Tagged with MetronTagger-{__version__} using info from Metron on "
                f"{now_date}. [issue_id:{issue_id}]"
            )

        def add_credits_to_metadata(
            md: Metadata,
            credits_resp: list[CreditsSchema],
        ) -> Metadata:
            def create_role_list(roles: list[RolesSchema]) -> list[Role]:
                return [Role(r.name, r.id) for r in roles]

            for c in credits_resp:
                if c.role:
                    md.add_credit(Credit(c.creator, create_role_list(c.role), c.id))
                else:
                    md.add_credit(Credit(c.creator, [], c.id))
            return md

        def map_ratings(rating: str) -> str:
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
            md.web_link = resp.resource_url

        return md
