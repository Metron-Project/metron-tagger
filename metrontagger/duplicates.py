"""Module to find and remove any duplicate pages from a directory of comics."""

# Copyright 2023 Brian Pepple
from __future__ import annotations

__all__ = ["DuplicateIssue", "Duplicates"]

import io
import warnings
from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import questionary
from darkseid.comic import Comic
from imagehash import average_hash
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

from metrontagger.styles import Styles

if TYPE_CHECKING:
    from collections.abc import Generator


LOGGER = getLogger(__name__)

warnings.filterwarnings(
    "ignore", category=UserWarning
)  # Ignore 'UserWarning: Corrupt EXIF data' warnings


@dataclass
class DuplicateIssue:
    """A data class representing a duplicate issue.

    This class stores information about a duplicate issue, including the path to the file and a list of page indices.

    Args:
        path_: str: The path to the file with the duplicate issue.
        pages_index: list[int]: A list of page indices where the duplicate issue occurs.

    Returns:
        str: A string representation of the DuplicateIssue object.
    """

    path_: str
    pages_index: list[int]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={Path(self.path_).name})"

    def add_page_index(self, index: int) -> None:
        """Add a page index to the list of duplicate pages."""
        if index not in self.pages_index:
            self.pages_index.append(index)


class DuplicateProcessingError(Exception):
    """Exception raised when duplicate processing fails."""


class Duplicates:
    """A class for handling duplicate comic book pages.

    This class provides methods for identifying duplicate pages in a list of comic book files and performing actions
    on them.

    Args:
        file_lst: list[Path]: A list of file paths to the comic book files.

    Returns:
        None
    """

    def __init__(self, file_lst: list[Path]) -> None:
        """Initialize the Duplicates class with a list of file paths.

        This method sets the list of file paths and initializes the data frame to None.

        Args:
            file_lst: list[Path]: A list of file paths to be processed.

        Returns:
            None
        """
        if not file_lst:
            msg = "File list cannot be empty"
            raise ValueError(msg)

        self._file_lst = file_lst
        self._data_frame: pd.DataFrame | None = None
        self._hash_cache: dict[str, list[dict[str, str | int]]] = defaultdict(list)

    def __enter__(self):
        return self

    def __exit__(self, *_) -> None:
        self._clear_cache()

    def _clear_cache(self) -> None:
        """Clear internal caches to free memory."""
        self._data_frame = None
        self._hash_cache.clear()

    def _generate_page_hashes(self) -> Generator[dict[str, str | int], None, None]:
        """Generator to yield page hash information for each comic page.

        Yields:
            dict[str, str | int]: Dictionary containing file path, page index, and page hash.
        """
        questionary.print("Getting page hashes.", style=Styles.INFO)
        for item in tqdm(self._file_lst, desc="Processing comics"):
            try:
                comic = Comic(item)
                if not comic.is_writable():
                    LOGGER.warning("Comic %s is not writable, skipping", comic)
                    continue

                yield from self._process_comic_pages(comic)

            except Exception as e:
                LOGGER.error("Failed to process comic %s: %s", item, e)  # noqa: TRY400
                continue

    def _process_comic_pages(
        self, comic: Comic
    ) -> Generator[dict[str, str | int], None, None]:
        """Process all pages in a comic and yield hash information.

        Args:
            comic: Comic object to process

        Yields:
            dict[str, str | int]: Dictionary containing file path, page index, and page hash.
        """
        num_pages = comic.get_number_of_pages()
        for page_idx in range(num_pages):
            try:
                page_data = comic.get_page(page_idx)
                if img_hash := self._calculate_image_hash(page_data):
                    yield {
                        "path": str(comic.path),
                        "index": page_idx,
                        "hash": img_hash,
                    }
            except Exception:
                LOGGER.exception("Failed to process page %d of '%s'", page_idx, comic)

    @staticmethod
    def _calculate_image_hash(page_data: bytes) -> str | None:
        """Calculate the hash for a single image page.

        Args:
            page_data: Raw image data as bytes

        Returns:
            str | None: Hash string or None if calculation failed
        """
        try:
            with Image.open(io.BytesIO(page_data)) as img:
                return str(average_hash(img))
        except (UnidentifiedImageError, OSError) as e:
            LOGGER.debug("Unable to calculate hash for image: %s", e)
            return None

    def _build_dataframe(self) -> pd.DataFrame:
        """Build a DataFrame from page hashes and cache duplicates.

        Returns:
            pd.DataFrame: DataFrame containing comics with duplicate pages.
        """
        if self._data_frame is not None:
            return self._data_frame

        # Convert generator to list for DataFrame creation
        hash_data = list(self._generate_page_hashes())

        if not hash_data:
            LOGGER.warning("No valid page hashes found")
            return pd.DataFrame()

        self._data_frame = pd.DataFrame(hash_data)

        # Build hash cache for faster lookups
        self._build_hash_cache()

        return self._data_frame

    def _build_hash_cache(self) -> None:
        """Build a cache of hash values for faster duplicate lookups."""
        if self._data_frame is None or self._data_frame.empty:
            return

        for _, row in self._data_frame.iterrows():
            hash_value = row["hash"]
            self._hash_cache[hash_value].append({"path": row["path"], "index": row["index"]})

    def get_duplicate_pages_dataframe(self) -> pd.DataFrame:
        """Get a DataFrame containing only duplicate pages.

        Returns:
            pd.DataFrame: DataFrame containing comics with duplicate pages.
        """
        df = self._build_dataframe()
        if df.empty:
            return df

        return df[df["hash"].duplicated(keep=False)].sort_values("hash")

    def get_distinct_hashes(self) -> list[str]:
        """Get distinct hash values for duplicate pages.

        Returns:
            list[str]: A list of distinct hash values that appear in multiple pages.
        """
        duplicate_df = self.get_duplicate_pages_dataframe()
        return [] if duplicate_df.empty else list(duplicate_df["hash"].unique())

    def get_comic_info_for_hash(self, img_hash: str) -> DuplicateIssue | None:
        """Retrieve comic information for a specific hash value.

        Args:
            img_hash: str: The hash value to search for.

        Returns:
            DuplicateIssue | None: A DuplicateIssue object or None if hash not found.
        """
        if img_hash not in self._hash_cache:
            return None

        first_entry = self._hash_cache[img_hash][0]
        return DuplicateIssue(first_entry["path"], [first_entry["index"]])

    def get_comic_list_from_hash(self, img_hash: str) -> list[DuplicateIssue]:
        """Get a list of DuplicateIssue objects from a hash value.

        Args:
            img_hash: str: The hash value to search for.

        Returns:
            list[DuplicateIssue]: A list of DuplicateIssue objects representing comics with the specified hash value.
        """
        if img_hash not in self._hash_cache:
            return []

        return [
            DuplicateIssue(entry["path"], [entry["index"]])
            for entry in self._hash_cache[img_hash]
        ]

    @staticmethod
    def delete_comic_pages(duplicates_list: list[DuplicateIssue]) -> dict[str, bool]:
        """Delete pages from comics and return results.

        Args:
            duplicates_list: list[DuplicateIssue]: List of DuplicateIssue objects representing duplicate pages.

        Returns:
            dict[str, bool]: Dictionary mapping comic paths to success status.
        """
        if not duplicates_list:
            LOGGER.info("No duplicate pages to delete")
            return {}

        results = {}
        for item in duplicates_list:
            try:
                comic = Comic(item.path_)
                # Sort pages in descending order to avoid index shifting issues
                sorted_pages = sorted(item.pages_index, reverse=True)
                success = comic.remove_pages(sorted_pages)
                results[item.path_] = success

                status_msg = "Removed" if success else "Failed to remove"
                style = Styles.SUCCESS if success else Styles.WARNING
                questionary.print(
                    f"{status_msg} duplicate pages from {comic}",
                    style=style,
                )
            except Exception as e:
                LOGGER.error("Error deleting pages from %s: %s", item.path_, e)  # noqa: TRY400
                results[item.path_] = False
                questionary.print(
                    f"Error removing duplicate pages from {Path(item.path_).name}: {e}",
                    style=Styles.ERROR,
                )

        return results

    @staticmethod
    def show_image(duplicate_issue: DuplicateIssue) -> bool:
        """Show an image from a comic to the user.

        Args:
            duplicate_issue: DuplicateIssue: The DuplicateIssue object representing the comic to display.

        Returns:
            bool: True if image was successfully shown, False otherwise.
        """
        if not duplicate_issue.pages_index:
            LOGGER.warning("No page indices available for %s", duplicate_issue.path_)
            return False

        try:
            comic = Comic(duplicate_issue.path_)
            # Use first page index if multiple are available
            page_index = duplicate_issue.pages_index[0]
            img_data = comic.get_page(page_index)

            with io.BytesIO(img_data) as img_io:
                image = Image.open(img_io)
                image.show()
                return True

        except (UnidentifiedImageError, OSError, IndexError) as e:
            LOGGER.warning("Unable to show image from %s: %s", duplicate_issue.path_, e)
            questionary.print(
                f"Unable to show image from {Path(duplicate_issue.path_).name}.",
                style=Styles.WARNING,
            )
            return False
        except Exception as e:
            LOGGER.error(  # noqa: TRY400
                "Unexpected error showing image from %s: %s", duplicate_issue.path_, e
            )
            return False

    def get_statistics(self) -> dict[str, int]:
        """Get statistics about the duplicate detection process.

        Returns:
            dict[str, int]: Dictionary containing various statistics.
        """
        df = self._build_dataframe()
        duplicate_df = self.get_duplicate_pages_dataframe()

        return {
            "total_pages": len(df),
            "duplicate_pages": len(duplicate_df),
            "unique_duplicate_hashes": len(self.get_distinct_hashes()),
            "comics_processed": len(self._file_lst),
        }
