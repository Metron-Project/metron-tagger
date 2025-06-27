"""Functions for renaming files based on metadata"""
# Copyright 2020 Brian Pepple

from __future__ import annotations

__all__ = ["FileRenamer"]

import contextlib
import datetime
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from darkseid.metadata import Metadata

import questionary
from darkseid.issue_string import IssueString
from darkseid.utils import unique_file

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string


class TokenType(Enum):
    """Enumeration of available template tokens."""

    SERIES = "%series%"
    VOLUME = "%volume%"
    ISSUE = "%issue%"
    ISSUE_COUNT = "%issue_count%"
    YEAR = "%year%"
    MONTH = "%month%"
    MONTH_NAME = "%month_name%"
    PUBLISHER = "%publisher%"
    IMPRINT = "%imprint%"
    ALTERNATE_SERIES = "%alternate_series%"
    ALTERNATE_NUMBER = "%alternate_number%"
    ALTERNATE_COUNT = "%alternate_count%"
    FORMAT = "%format%"
    MATURITY_RATING = "%maturity_rating%"
    SERIES_GROUP = "%series_group%"
    SCAN_INFO = "%scan_info%"


@dataclass(frozen=True)
class FormatMapping:
    """Immutable mapping for format conversions."""

    MAPPING: dict[str, str] = None

    def __post_init__(self):
        if self.MAPPING is None:
            object.__setattr__(
                self,
                "MAPPING",
                {
                    "Hard Cover": "HC",  # Old Metron Value
                    "Hardcover": "HC",
                    "Trade Paperback": "TPB",
                    "Digital Chapters": "Digital Chapter",  # Old Metron Value
                    "Digital Chapter": "Digital Chapter",
                },
            )

    def get(self, key: str, default: str = "") -> str:
        """Get format mapping with default value."""
        return self.MAPPING.get(key, default)


class FileRenamer:
    """A class for renaming comic book files based on metadata.

    This class provides methods for setting metadata, customizing file naming templates,
    and renaming files according to the specified rules.
    """

    # Class constants
    DEFAULT_TEMPLATE: str = "%series% %format% v%volume% #%issue% (%year%)"
    DEFAULT_ISSUE_PADDING: int = 3
    HALF_ISSUE_SYMBOL: str = "½"
    HALF_ISSUE_DECIMAL: str = "0.5"
    MINIMUM_TOKEN_LENGTH: int = 2
    MAXIMUM_MONTH_NUMBER: int = 12

    # Regex patterns (compiled once for performance)
    _EMPTY_SEPARATORS_PATTERN = re.compile(r"(\(\s*[-:]*\s*\)|\[\s*[-:]*\s*]|\{\s*[-:]*\s*})")
    _DUPLICATE_SPACES_PATTERN = re.compile(r"\s+")
    _DUPLICATE_HYPHEN_UNDERSCORE_PATTERN = re.compile(r"([-_]){2,}")
    _TRAILING_DASH_PATTERN = re.compile(r"-{1,2}\s*$")

    def __init__(self, metadata: Metadata | None = None) -> None:
        """Initialize the FileRenamer with optional metadata and default settings.

        Args:
            metadata: Optional metadata object for file renaming.
        """
        self._metadata = metadata
        self._template = self.DEFAULT_TEMPLATE
        self._smart_cleanup = True
        self._issue_zero_padding = self.DEFAULT_ISSUE_PADDING
        self._format_mapping = FormatMapping()

    @property
    def metadata(self) -> Metadata | None:
        """Get the current metadata."""
        return self._metadata

    @property
    def template(self) -> str:
        """Get the current template."""
        return self._template

    @property
    def smart_cleanup(self) -> bool:
        """Get the smart cleanup setting."""
        return self._smart_cleanup

    @property
    def issue_zero_padding(self) -> int:
        """Get the issue zero padding setting."""
        return self._issue_zero_padding

    def set_smart_cleanup(self, enabled: bool) -> None:
        """Set the smart cleanup option for file renaming.

        Args:
            enabled: Boolean to enable or disable smart cleanup.
        """
        self._smart_cleanup = enabled

    def set_metadata(self, metadata: Metadata) -> None:
        """Set the metadata for file renaming.

        Args:
            metadata: The Metadata object to be set for file renaming.
        """
        self._metadata = metadata

    def set_issue_zero_padding(self, count: int) -> None:
        """Set the padding for the issue number in file renaming.

        Args:
            count: The number of digits to pad the issue number with.

        Raises:
            ValueError: If count is negative.
        """
        if count < 0:
            msg = "Issue zero padding must be non-negative"
            raise ValueError(msg)
        self._issue_zero_padding = count

    def set_template(self, template: str) -> None:
        """Set a custom file naming template.

        Args:
            template: The custom file naming template to be used.

        Raises:
            ValueError: If template is empty.
        """
        if not template.strip():
            msg = "Template cannot be empty"
            raise ValueError(msg)
        self._template = template

    def _is_token(self, text: str) -> bool:
        """Check if a string is a token.

        Args:
            text: The string to check.

        Returns:
            True if the string is a token, False otherwise.
        """
        return (
            len(text) >= self.MINIMUM_TOKEN_LENGTH
            and text.startswith("%")
            and text.endswith("%")
        )

    def _replace_token(self, text: str, value: Any, token: TokenType) -> str:
        """Replace a token in the text with a value.

        Args:
            text: The text containing the token to be replaced.
            value: The value to replace the token with.
            token: The token to be replaced in the text.

        Returns:
            The text with the token replaced by the value.
        """
        token_str = token.value

        if value is not None:
            return text.replace(token_str, str(value))

        if not self._smart_cleanup:
            return text.replace(token_str, "")

        # Smart cleanup: remove associated text when token is empty
        text_parts = text.split()

        # Special case for issue_count: remove preceding non-token word
        if token == TokenType.ISSUE_COUNT:
            for idx, word in enumerate(text_parts):
                if token_str in word and idx > 0 and not self._is_token(text_parts[idx - 1]):
                    text_parts[idx - 1] = ""

        # Remove parts containing the token
        text_parts = [part for part in text_parts if token_str not in part]
        return " ".join(text_parts).strip()

    @classmethod
    def _remove_empty_separators(cls, value: str) -> str:
        """Remove empty separators from the provided value.

        Args:
            value: The input string containing separators to be removed.

        Returns:
            The string with empty separators removed.
        """
        return cls._EMPTY_SEPARATORS_PATTERN.sub("", value).strip()

    @classmethod
    def _remove_duplicate_hyphen_underscore(cls, value: str) -> str:
        """Remove duplicate hyphens and underscores from the provided value.

        Args:
            value: The string to clean up.

        Returns:
            The string with duplicate hyphens and underscores cleaned up.
        """
        return cls._DUPLICATE_HYPHEN_UNDERSCORE_PATTERN.sub(r"\1", value)

    def _smart_cleanup_string(self, text: str) -> str:
        """Perform smart cleanup on the provided text string.

        Args:
            text: The input string to be cleaned up.

        Returns:
            The cleaned up string after applying smart cleanup operations.
        """
        # Remove empty braces, brackets, parentheses
        text = self._remove_empty_separators(text)

        # Remove duplicate spaces
        text = self._DUPLICATE_SPACES_PATTERN.sub(" ", text)

        # Remove duplicate hyphens and underscores
        text = self._remove_duplicate_hyphen_underscore(text)

        # Remove trailing dashes
        text = self._TRAILING_DASH_PATTERN.sub("", text)

        return text.strip()

    def _format_issue_string(self, issue: str | None) -> str | None:
        """Format issue string with proper padding.

        Args:
            issue: The issue string to format.

        Returns:
            The formatted issue string or None if issue is None.
        """
        if issue is None:
            return None

        if issue == self.HALF_ISSUE_SYMBOL:
            return IssueString(self.HALF_ISSUE_DECIMAL).as_string(pad=self._issue_zero_padding)

        return IssueString(issue).as_string(pad=self._issue_zero_padding)

    def _get_month_name(self, month: int | str) -> str | None:
        """Get month name from month number.

        Args:
            month: Month number (1-12).

        Returns:
            Month name or None if invalid.
        """
        with contextlib.suppress(ValueError, TypeError):
            month_int = int(month)
            if 1 <= month_int <= self.MAXIMUM_MONTH_NUMBER:
                return datetime.datetime(
                    1970, month_int, 1, tzinfo=datetime.timezone.utc
                ).strftime("%B")
        return None

    def _extract_metadata_values(self) -> dict[TokenType, Any]:
        """Extract values from metadata for all tokens.

        Returns:
            Dictionary mapping tokens to their values.
        """
        if not self._metadata:
            return {}

        md = self._metadata
        values = {}

        # Series information
        if md.series:
            values[TokenType.SERIES] = md.series.name
            values[TokenType.VOLUME] = md.series.volume
            values[TokenType.ISSUE_COUNT] = md.series.issue_count
            values[TokenType.FORMAT] = self._format_mapping.get(md.series.format)
        else:
            values[TokenType.SERIES] = "Unknown"
            values[TokenType.VOLUME] = 0

        # Issue information
        values[TokenType.ISSUE] = self._format_issue_string(md.issue)

        # Date information
        if md.cover_date:
            values[TokenType.YEAR] = md.cover_date.year
            values[TokenType.MONTH] = md.cover_date.month
            values[TokenType.MONTH_NAME] = self._get_month_name(md.cover_date.month)
        else:
            values[TokenType.YEAR] = "Unknown"

        # Publisher information
        if md.publisher:
            values[TokenType.PUBLISHER] = md.publisher.name
            if md.publisher.imprint:
                values[TokenType.IMPRINT] = md.publisher.imprint.name
        else:
            values[TokenType.PUBLISHER] = "Unknown"

        # Additional metadata
        values[TokenType.ALTERNATE_SERIES] = md.alternate_series
        values[TokenType.ALTERNATE_NUMBER] = md.alternate_number
        values[TokenType.ALTERNATE_COUNT] = md.alternate_count
        values[TokenType.MATURITY_RATING] = md.age_rating
        values[TokenType.SERIES_GROUP] = md.series_group
        values[TokenType.SCAN_INFO] = md.scan_info

        return values

    def determine_name(self, filename: Path) -> str | None:
        """Determine the new filename based on metadata.

        Args:
            filename: The original filename path.

        Returns:
            The new filename generated based on the metadata, or None if metadata is not set.
        """
        if not self._metadata:
            return None

        new_name = self._template
        values = self._extract_metadata_values()

        # Replace all tokens with their values
        for token, value in values.items():
            new_name = self._replace_token(new_name, value, token)

        # Apply smart cleanup if enabled
        if self._smart_cleanup:
            new_name = self._smart_cleanup_string(new_name)

        # Add file extension
        new_name += filename.suffix

        return cleanup_string(new_name)

    def rename_file(self, comic: Path) -> Path | None:
        """Rename a comic file based on metadata.

        Args:
            comic: The path to the comic file to be renamed.

        Returns:
            The path to the renamed comic file, or None if the renaming process is skipped.
        """
        if self._metadata is None:
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

        try:
            unique_name = unique_file(comic.parent / new_name)
            comic.rename(unique_name)
        except OSError as e:
            questionary.print(
                f"Failed to rename '{comic.name}': {e}",
                style=Styles.WARNING,
            )
            return None
        else:
            return unique_name
