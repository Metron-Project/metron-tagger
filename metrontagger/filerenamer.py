"""Functions for renaming files based on metadata"""

# Copyright 2012-2014 Anthony Beville
# Copyright 2020 Brian Pepple
from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from darkseid.metadata import Metadata

import questionary
from darkseid.issue_string import IssueString
from darkseid.utils import unique_file

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string


class FileRenamer:
    """A class for renaming comic book files based on metadata.

    This class provides methods for setting metadata, customizing file naming templates, and renaming files according
    to the specified rules.

    Args:
        metadata: Metadata | None: Optional metadata object to be used for file renaming.

    Returns:
        None
    """

    def __init__(self: FileRenamer, metadata: Metadata | None = None) -> None:
        """Initialize the FileRenamer class with optional metadata and default settings.

        This method sets the metadata, file naming template, smart cleanup option, and issue number zero padding.

        Args:
            metadata: Metadata | None: Optional metadata object for file renaming.

        Returns:
            None
        """

        self.metadata: Metadata | None = metadata
        self.template: str = "%series% v%volume% #%issue% (of %issuecount%) (%year%)"
        self.smart_cleanup: bool = True
        self.issue_zero_padding: int = 3

    def set_smart_cleanup(self: FileRenamer, on: bool) -> None:
        """Set the smart cleanup option for file renaming.

        This method toggles the smart cleanup feature based on the provided boolean value.

        Args:
            on: bool: A boolean value to enable or disable smart cleanup.

        Returns:
            None
        """

        self.smart_cleanup = on

    def set_metadata(self: FileRenamer, metadata: Metadata) -> None:
        """Set the metadata for file renaming.

        This method updates the metadata used for file renaming to the provided Metadata object.

        Args:
            metadata: Metadata: The Metadata object to be set for file renaming.

        Returns:
            None
        """

        self.metadata = metadata

    def set_issue_zero_padding(self: FileRenamer, count: int) -> None:
        """Set the padding for the issue number in file renaming.

        This method updates the padding count used for formatting issue numbers in file names.

        Args:
            count: int: The number of digits to pad the issue number with.

        Returns:
            None
        """

        self.issue_zero_padding = count

    def set_template(self: FileRenamer, template: str) -> None:
        """Set a custom file naming template.

        This method updates the file naming template used for renaming files to the provided string.


        Args:
            template: str: The custom file naming template to be used.

        Returns:
            None
        """

        self.template = template

    def replace_token(
        self: FileRenamer, text: str, value: int | str | None, token: str
    ) -> str:
        """Replace a token in the text with a value.

        This method replaces a token in the text with the provided value, handling smart cleanup if enabled.

        Args:
            text: str: The text containing the token to be replaced.
            value: int | str | None: The value to replace the token with.
            token: str: The token to be replaced in the text.

        Returns:
            str: The text with the token replaced by the value.
        """

        # helper func
        def is_token(txt: str) -> bool:
            """Check if a string is a token.

            This function determines if a string is a token by checking if it starts and ends with '%'.

            Args:
                txt: str: The string to check if it is a token.

            Returns:
                bool: True if the string is a token, False otherwise.
            """

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
        """Remove empty separators from the provided value.

        This static method removes empty parentheses, brackets, and braces from the input string.

        Args:
            value: str: The input string containing separators to be removed.

        Returns:
            str: The string with empty separators removed.
        """
        pattern = r"(\(\s*[-:]*\s*\)|\[\s*[-:]*\s*]|\{\s*[-:]*\s*})"
        return re.sub(pattern, "", value).strip()

    @staticmethod
    def _remove_duplicate_hyphen_underscore(value: str) -> str:
        """Remove duplicate hyphens and underscores from the provided value.

        This static method cleans up the input string by replacing multiple hyphens and underscores with a single
        instance.

        Args:
            value: str: The string to remove duplicate hyphens and underscores from.

        Returns:
            str: The string with duplicate hyphens and underscores cleaned up.
        """
        return re.sub(r"([-_]){2,}", r"\1", value)

    def smart_cleanup_string(self: FileRenamer, new_name: str) -> str:
        """Perform smart cleanup on the provided new name string.

        This method applies various cleanup operations to the input string, including removing empty separators,
        duplicate spaces, duplicate hyphens and underscores, trailing dashes, and extra spaces.

        Args:
            new_name: str: The input string to be cleaned up.

        Returns:
            str: The cleaned up string after applying smart cleanup operations.
        """

        # remove empty braces, brackets, parentheses
        new_name = self._remove_empty_separators(new_name)

        # remove duplicate spaces, duplicate hyphens and underscores, and trailing dashes
        new_name = re.sub(r"\s+", " ", new_name)  # remove duplicate spaces
        new_name = self._remove_duplicate_hyphen_underscore(new_name)
        new_name = re.sub(
            r"-{1,2}\s*$", "", new_name
        )  # remove dash or double dash at end of line

        return new_name.strip()

    def determine_name(self: FileRenamer, filename: Path) -> str | None:
        """Determine the new filename based on metadata.

        This method constructs a new filename using the provided metadata and the file naming template,
        applying various replacements and cleanup operations.

        Args:
            filename: Path: The original filename path.

        Returns:
            str | None: The new filename generated based on the metadata, or None if metadata is not set.
        """

        if not self.metadata:
            return None
        md = self.metadata
        new_name = self.template

        series_name = md.series.name if md.series else "Unknown"
        series_volume = md.series.volume if md.series else 0
        new_name = self.replace_token(new_name, series_name, "%series%")
        new_name = self.replace_token(new_name, series_volume, "%volume%")

        if md.issue is None:
            issue_str = None
        elif md.issue == "½":
            issue_str = IssueString("0.5").as_string(pad=self.issue_zero_padding)
        else:
            issue_str = IssueString(md.issue).as_string(pad=self.issue_zero_padding)
        new_name = self.replace_token(new_name, issue_str, "%issue%")

        new_name = self.replace_token(new_name, md.issue_count, "%issuecount%")
        new_name = self.replace_token(
            new_name, md.cover_date.year if md.cover_date else "Unknown", "%year%"
        )
        new_name = self.replace_token(
            new_name, "Unknown" if md.publisher is None else md.publisher.name, "%publisher%"
        )

        if md.cover_date:
            new_name = self.replace_token(new_name, md.cover_date.month, "%month%")
            if (
                isinstance(md.cover_date.month, str | int)
                and 1 <= int(md.cover_date.month) <= 12  # noqa: PLR2004
            ):
                month_name = datetime.datetime(1970, int(md.cover_date.month), 1).strftime(  # noqa: DTZ001
                    "%B"
                )
            else:
                month_name = None
            new_name = self.replace_token(new_name, month_name, "%month_name%")

        new_name = self.replace_token(new_name, md.alternate_series, "%alternateseries%")
        new_name = self.replace_token(new_name, md.alternate_number, "%alternatenumber%")
        new_name = self.replace_token(new_name, md.alternate_count, "%alternatecount%")
        new_name = self.replace_token(new_name, md.imprint, "%imprint%")

        if md.series:
            format_mapping = {
                "Hard Cover": "HC",  # Old Metron Value
                "Hardcover": "HC",
                "Trade Paperback": "TPB",
                "Digital Chapters": "Digital Chapter",  # Old Metron Value
                "Digital Chapter": "Digital Chapter",
            }
            format_value = format_mapping.get(md.series.format, "")
            new_name = self.replace_token(new_name, format_value, "%format%")

        new_name = self.replace_token(new_name, md.age_rating, "%maturityrating%")
        new_name = self.replace_token(new_name, md.series_group, "%seriesgroup%")
        new_name = self.replace_token(new_name, md.scan_info, "%scaninfo%")

        if self.smart_cleanup:
            new_name = self.smart_cleanup_string(new_name)

        ext = filename.suffix
        new_name += ext

        return cleanup_string(new_name)

    def rename_file(self: FileRenamer, comic: Path) -> Path | None:
        """Rename a comic file based on metadata.

        This method renames the comic file using the metadata and file naming template, ensuring a unique filename.
        If metadata is not set, the function will skip the renaming process.

        Args:
            comic: Path: The path to the comic file to be renamed.

        Returns:
            Path | None: The path to the renamed comic file, or None if the renaming process is skipped.
        """

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
