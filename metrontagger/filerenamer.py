"""Functions for renaming files based on metadata"""

# Copyright 2012-2014 Anthony Beville
# Copyright 2020 Brian Pepple

import datetime
import re
from pathlib import Path

import questionary
from darkseid.issue_string import IssueString
from darkseid.metadata import Metadata
from darkseid.utils import unique_file

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string


class FileRenamer:
    """Class to rename a comic archive based on it's metadata tag"""

    def __init__(self: "FileRenamer", metadata: Metadata | None = None) -> None:
        self.metadata: Metadata | None = metadata
        self.template: str = "%series% v%volume% #%issue% (of %issuecount%) (%year%)"
        self.smart_cleanup: bool = True
        self.issue_zero_padding: int = 3

    def set_smart_cleanup(self: "FileRenamer", on: bool) -> None:
        self.smart_cleanup = on

    def set_metadata(self: "FileRenamer", metadata: Metadata) -> None:
        """Method to set the metadata"""
        self.metadata = metadata

    def set_issue_zero_padding(self: "FileRenamer", count: int) -> None:
        """Method to set the padding for the issue's number"""
        self.issue_zero_padding = count

    def set_template(self: "FileRenamer", template: str) -> None:
        """
        Method to use a user's custom file naming template.
        """
        self.template = template

    def replace_token(self: "FileRenamer", text: str, value: str | None, token: str) -> str:
        """Method to replace a value with another value"""

        # helper func
        def is_token(txt: str) -> bool:
            return txt[0] == "%" and txt.endswith("%")

        if value is not None:
            return text.replace(token, str(value))

        if self.smart_cleanup:
            # smart cleanup means we want to remove anything appended to token if it's empty
            # (e.g "#%issue%"  or "v%volume%")
            text_list = text.split()

            # special case for issuecount, remove preceding non-token word,
            # as in "...(of %issuecount%)..."
            if token == "%issuecount%":  # noqa: S105
                for idx, word in enumerate(text_list):
                    if token in word and not is_token(text_list[idx - 1]):
                        text_list[idx - 1] = ""

            text_list = [x for x in text_list if token not in x]
            return " ".join(text_list)

        return text.replace(token, "")

    @staticmethod
    def _remove_empty_separators(value: str) -> str:
        value = re.sub(r"\(\s*[-:]*\s*\)", "", value)
        value = re.sub(r"\[\s*[-:]*\s*\]", "", value)
        return re.sub(r"\{\s*[-:]*\s*\}", "", value)

    @staticmethod
    def _remove_duplicate_hyphen_underscore(value: str) -> str:
        value = re.sub(r"[-_]{2,}\s+", "-- ", value)
        value = re.sub(r"(\s--)+", " --", value)
        return re.sub(r"(\s-)+", " -", value)

    def smart_cleanup_string(self: "FileRenamer", new_name: str) -> str:
        # remove empty braces,brackets, parentheses
        new_name = self._remove_empty_separators(new_name)

        # remove duplicate spaces
        new_name = " ".join(new_name.split())

        # remove remove duplicate -, _,
        new_name = self._remove_duplicate_hyphen_underscore(new_name)

        # remove dash or double dash at end of line
        new_name = re.sub(r"[-]{1,2}\s*$", "", new_name)

        # remove duplicate spaces (again!)
        return " ".join(new_name.split())

    def determine_name(self: "FileRenamer", filename: Path) -> str | None:
        """Method to create the new filename based on the files metadata"""
        md = self.metadata
        new_name = self.template

        new_name = self.replace_token(new_name, md.series.name, "%series%")
        new_name = self.replace_token(new_name, md.series.volume, "%volume%")

        if md.issue is None:
            issue_str = None
        elif md.issue == "½":
            issue_str = IssueString("0.5").as_string(pad=self.issue_zero_padding)
        else:
            issue_str = IssueString(md.issue).as_string(pad=self.issue_zero_padding)
        new_name = self.replace_token(new_name, issue_str, "%issue%")

        new_name = self.replace_token(new_name, md.issue_count, "%issuecount%")
        new_name = self.replace_token(new_name, md.cover_date.year, "%year%")
        new_name = self.replace_token(new_name, md.publisher, "%publisher%")
        new_name = self.replace_token(new_name, md.stories, "%title%")
        new_name = self.replace_token(new_name, md.cover_date.month, "%month%")
        month_name = None
        if (
            md.cover_date.month is not None
            and (
                (isinstance(md.cover_date.month, str) and md.cover_date.month.isdigit())
                or isinstance(md.cover_date.month, int)
            )
            and int(md.cover_date.month) in range(1, 13)
        ):
            date_time = datetime.datetime(  # noqa: DTZ001
                1970,
                int(md.cover_date.month),
                1,
                0,
                0,
            )
            month_name = date_time.strftime("%B")
        new_name = self.replace_token(new_name, month_name, "%month_name%")

        new_name = self.replace_token(new_name, md.genres, "%genre%")
        new_name = self.replace_token(new_name, md.series.language, "%language_code%")
        new_name = self.replace_token(new_name, md.critical_rating, "%criticalrating%")
        new_name = self.replace_token(
            new_name,
            md.alternate_series,
            "%alternateseries%",
        )
        new_name = self.replace_token(
            new_name,
            md.alternate_number,
            "%alternatenumber%",
        )
        new_name = self.replace_token(new_name, md.alternate_count, "%alternatecount%")
        new_name = self.replace_token(new_name, md.imprint, "%imprint%")
        if md.series.format == "Hard Cover":
            new_name = self.replace_token(new_name, "HC", "%format%")
        elif md.series.format == "Trade Paperback":
            new_name = self.replace_token(new_name, "TPB", "%format%")
        else:
            new_name = self.replace_token(new_name, "", "%format%")
        new_name = self.replace_token(new_name, md.age_rating, "%maturityrating%")
        new_name = self.replace_token(new_name, md.stories, "%storyarc%")
        new_name = self.replace_token(new_name, md.series_group, "%seriesgroup%")
        new_name = self.replace_token(new_name, md.scan_info, "%scaninfo%")

        if self.smart_cleanup:
            new_name = self.smart_cleanup_string(new_name)

        ext = filename.suffix
        new_name += ext

        return cleanup_string(new_name)

    def rename_file(self: "FileRenamer", comic: Path) -> Path | None:
        # This shouldn't happen, but just in case let's make sure there is metadata.
        if self.metadata is None:
            questionary.print(
                f"Metadata hasn't been set for {comic}. Skipping...",
                style=Styles.WARNING,
            )
            return None

        new_name = self.determine_name(comic)
        if not new_name:
            return None

        if new_name == comic.name:
            questionary.print(
                f"Filename for '{comic.name}' is already good!",
                style=Styles.SUCCESS,
            )
            return None

        unique_name = unique_file(comic.parent / new_name)
        comic.rename(unique_name)

        return unique_name
