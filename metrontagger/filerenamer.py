"""Functions for renaming files based on metadata"""

# Copyright 2012-2014 Anthony Beville
# Copyright 2020 Brian Pepple

import datetime
import re
from pathlib import Path
from typing import Optional

import questionary
from darkseid.issue_string import IssueString
from darkseid.metadata import Metadata
from darkseid.utils import unique_file

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string


class FileRenamer:
    """Class to rename a comic archive based on it's metadata tag"""

    def __init__(self: "FileRenamer", metadata: Metadata) -> None:
        self.set_metadata(metadata)
        self.set_template("%series% v%volume% #%issue% (of %issuecount%) (%year%)")
        self.smart_cleanup = True
        self.issue_zero_padding = 3

    def set_smart_cleanup(self: "FileRenamer", on: bool) -> None:
        self.smart_cleanup = on

    def set_metadata(self: "FileRenamer", metadata: Metadata) -> None:
        """Method to set the metadata"""
        self.metdata = metadata

    def set_issue_zero_padding(self: "FileRenamer", count: int) -> None:
        """Method to set the padding for the issue's number"""
        self.issue_zero_padding = count

    def set_template(self: "FileRenamer", template: str) -> None:
        """
        Method to use a user's custom file naming template.
        Currently this hasn't been implemented
        """
        self.template = template

    def replace_token(self: "FileRenamer", text: str, value: Optional[str], token: str) -> str:
        """Method to replace a value with another value"""

        # helper func
        def is_token(word: str) -> bool:
            return word[0] == "%" and word.endswith("%")

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

    def determine_name(self: "FileRenamer", filename: Path) -> Optional[str]:
        """Method to create the new filename based on the files metadata"""
        meta_data = self.metdata
        new_name = self.template

        new_name = self.replace_token(new_name, meta_data.series.name, "%series%")
        new_name = self.replace_token(new_name, meta_data.series.volume, "%volume%")

        if meta_data.issue is None:
            issue_str = None
        elif meta_data.issue == "½":
            issue_str = IssueString("0.5").as_string(pad=self.issue_zero_padding)
        else:
            issue_str = "{}".format(
                IssueString(meta_data.issue).as_string(pad=self.issue_zero_padding),
            )
        new_name = self.replace_token(new_name, issue_str, "%issue%")

        new_name = self.replace_token(new_name, meta_data.issue_count, "%issuecount%")
        new_name = self.replace_token(new_name, meta_data.cover_date.year, "%year%")
        new_name = self.replace_token(new_name, meta_data.publisher, "%publisher%")
        new_name = self.replace_token(new_name, meta_data.stories, "%title%")
        new_name = self.replace_token(new_name, meta_data.cover_date.month, "%month%")
        month_name = None
        if (
            meta_data.cover_date.month is not None
            and (
                (
                    isinstance(meta_data.cover_date.month, str)
                    and meta_data.cover_date.month.isdigit()
                )
                or isinstance(meta_data.cover_date.month, int)
            )
            and int(meta_data.cover_date.month) in range(1, 13)
        ):
            date_time = datetime.datetime(  # noqa: DTZ001
                1970,
                int(meta_data.cover_date.month),
                1,
                0,
                0,
            )
            month_name = date_time.strftime("%B")
        new_name = self.replace_token(new_name, month_name, "%month_name%")

        new_name = self.replace_token(new_name, meta_data.genres, "%genre%")
        new_name = self.replace_token(new_name, meta_data.series.language, "%language_code%")
        new_name = self.replace_token(new_name, meta_data.critical_rating, "%criticalrating%")
        new_name = self.replace_token(
            new_name,
            meta_data.alternate_series,
            "%alternateseries%",
        )
        new_name = self.replace_token(
            new_name,
            meta_data.alternate_number,
            "%alternatenumber%",
        )
        new_name = self.replace_token(new_name, meta_data.alternate_count, "%alternatecount%")
        new_name = self.replace_token(new_name, meta_data.imprint, "%imprint%")
        new_name = self.replace_token(new_name, meta_data.series.format, "%format%")
        new_name = self.replace_token(new_name, meta_data.age_rating, "%maturityrating%")
        new_name = self.replace_token(new_name, meta_data.stories, "%storyarc%")
        new_name = self.replace_token(new_name, meta_data.series_group, "%seriesgroup%")
        new_name = self.replace_token(new_name, meta_data.scan_info, "%scaninfo%")

        if self.smart_cleanup:
            new_name = self.smart_cleanup_string(new_name)

        ext = filename.suffix
        new_name += ext

        return cleanup_string(new_name)

    def rename_file(self: "FileRenamer", comic: Path) -> Optional[Path]:
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
