from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import mokkari
import questionary
from darkseid.comicarchive import ComicArchive
from darkseid.genericmetadata import GenericMetadata
from darkseid.issuestring import IssueString
from darkseid.utils import list_to_string
from mokkari.issue import IssuesList

from metrontagger import __version__
from metrontagger.settings import MetronTaggerSettings
from metrontagger.styles import Styles
from metrontagger.utils import create_query_params


class MultipleMatch:
    """Class to hold information on searches with multiple matches"""

    def __init__(self, filename: Path, match_list: IssuesList) -> None:
        self.filename = filename
        self.matches = match_list


class OnlineMatchResults:
    """Class to track online match results"""

    def __init__(self) -> None:
        self.good_matches: List[Path] = []
        self.no_matches: List[Path] = []
        self.multiple_matches: List[MultipleMatch] = []

    def add_good_match(self, file_name: Path) -> None:
        self.good_matches.append(file_name)

    def add_no_match(self, file_name: Path) -> None:
        self.no_matches.append(file_name)

    def add_multiple_match(self, multi_match: MultipleMatch) -> None:
        self.multiple_matches.append(multi_match)


class Talker:
    def __init__(self, username: str, password: str) -> None:
        self.api = mokkari.api(username, password)
        self.match_results = OnlineMatchResults()

    @staticmethod
    def _create_choice_list(match_set) -> List[questionary.Choice]:
        issue_lst = []
        for i in match_set:
            c = questionary.Choice(title=f"{i.issue_name} ({i.cover_date})", value=i.id)
            issue_lst.append(c)

        issue_lst.append(questionary.Choice(title="Skip", value=""))
        return issue_lst

    def _select_choice_from_matches(self, fn: Path, match_set) -> Optional[int]:
        """
        Function to ask user to choice which issue metadata to write,
        when there are multiple choices
        """
        questionary.print(f"\n{fn.name} - Results found:", style=Styles.TITLE)

        # sort match list by cover date
        match_set = sorted(match_set, key=lambda m: m.cover_date)
        choices = self._create_choice_list(match_set)

        return questionary.select("Select an issue to match", choices=choices).ask()

    def _process_file(
        self, fn: Path, interactive: bool
    ) -> Tuple[Optional[int], Optional[bool]]:
        ca = ComicArchive(fn)

        if not ca.is_writable() and not ca.seems_to_be_a_comic_archive():
            questionary.print(
                f"{fn.name} appears not to be a comic or writable.", style=Styles.ERROR
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

    def _post_process_matches(self) -> None:
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
                    match_set.filename, match_set.matches
                ):
                    self._write_issue_md(match_set.filename, issue_id)

    def _write_issue_md(self, filename: Path, issue_id: int) -> None:
        success = False

        if resp := self.api.issue(issue_id):
            ca = ComicArchive(filename)
            meta_data = GenericMetadata()
            meta_data.set_default_page_list(ca.get_number_of_pages())
            md = self._map_resp_to_metadata(resp)
            md.overlay(meta_data)
            success = ca.write_metadata(md)

        if success:
            questionary.print(f"Match found for '{filename.name}'.", style=Styles.SUCCESS)
        else:
            questionary.print(
                f"There was a problem writing metadata for '{filename.name}'.",
                style=Styles.ERROR,
            )

    def identify_comics(self, file_list: List[Path], config: MetronTaggerSettings):
        questionary.print(
            "\nStarting online search and tagging:\n----------------------------------",
            style=Styles.TITLE,
        )

        for fn in file_list:
            if config.ignore_existing:
                comic_archive = ComicArchive(fn)
                if comic_archive.has_metadata():
                    questionary.print(
                        f"{fn.name} has metadata. Skipping...", style=Styles.WARNING
                    )
                    continue

            issue_id, multiple_match = self._process_file(fn, config.interactive)
            if issue_id:
                self._write_issue_md(fn, issue_id)
            elif not multiple_match:
                questionary.print(f"No Match for '{fn.name}'.", style=Styles.ERROR)

        # Print match results
        self._post_process_matches()

    def retrieve_single_issue(self, fn: Path, id: int) -> None:
        self._write_issue_md(fn, id)

    @staticmethod
    def _create_note(issue_id: int) -> str:
        now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"Tagged with MetronTagger-{__version__} using info from Metron on {now_date}. [issue_id:{issue_id}]"

    @staticmethod
    def _add_credits_to_metadata(md: GenericMetadata, credits_resp) -> GenericMetadata:
        for creator in credits_resp:
            if creator.role:
                for r in creator.role:
                    md.add_credit(creator.creator, r.name)
        return md

    def _map_resp_to_metadata(self, resp) -> GenericMetadata:
        md = GenericMetadata()

        if resp.credits:
            md = self._add_credits_to_metadata(md, resp.credits)

        md.series = resp.series.name
        md.volume = resp.volume
        md.issue = IssueString(resp.number).as_string()
        md.publisher = resp.publisher.name
        md.day = resp.cover_date.day
        md.month = resp.cover_date.month
        md.year = resp.cover_date.year
        md.comments = resp.desc
        md.notes = self._create_note(resp.id)

        if resp.story_titles:
            md.title = list_to_string(list(resp.story_titles))

        if resp.characters:
            md.characters = list_to_string([c.name for c in resp.characters])

        if resp.teams:
            md.teams = list_to_string([t.name for t in resp.teams])

        if resp.arcs:
            md.story_arc = list_to_string([a.name for a in resp.arcs])

        return md
