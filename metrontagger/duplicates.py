"""Module to find and remove any duplicate pages from a directory of comics."""

# Copyright 2023 Brian Pepple
from __future__ import annotations

__all__ = ["DuplicateIssue", "Duplicates", "DuplicatesPresenter"]

import io
import os
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Self, TypedDict

from imagehash import average_hash
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

from metrontagger.comics import open_comic
from metrontagger.ui import UIPresenter

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from darkseid.comic import Comic


LOGGER = getLogger(__name__)

warnings.filterwarnings(
    "ignore", category=UserWarning
)  # Ignore 'UserWarning: Corrupt EXIF data' warnings

# Constants
KB_SIZE = 1024
ROUND_TO_TENTH_PLACE = 10
ROUND_TO_HUNDREDTH_PLACE = 100
DEFAULT_MAX_WORKERS = 8
# average_hash shrinks pages to 8x8, so JPEGs can be decoded at a much smaller scale.
HASH_DRAFT_SIZE = (64, 64)


class PageLocation(TypedDict):
    """Where a hashed page is: the comic's path and the page's index in it."""

    path: str
    index: int


class PageHash(PageLocation):
    """A hashed page: where it is, and its image hash."""

    hash: str


@dataclass
class DuplicateIssue:
    """A data class representing a duplicate issue with file size tracking.

    This class stores information about a duplicate issue, including the path to the file,
    a list of page indices, and file sizes before and after processing.

    Args:
        path_: str: The path to the file with the duplicate issue.
        pages_index: list[int]: A list of page indices where the duplicate issue occurs.
        starting_size_bytes: Optional[int]: The original file size in bytes (auto-calculated if None).
        ending_size_bytes: Optional[int]: The file size after processing in bytes.

    Returns:
        str: A string representation of the DuplicateIssue object.
    """

    path_: str
    pages_index: list[int] = field(default_factory=list)
    starting_size_bytes: int | None = field(default=None, init=False)
    ending_size_bytes: int | None = field(default=None)

    def __post_init__(self) -> None:
        """Initialize starting file size after object creation."""
        if self.starting_size_bytes is None:
            self.starting_size_bytes = self._get_current_file_size()

    def __repr__(self) -> str:
        size_info = ""
        if self.starting_size_bytes is not None:
            size_info = f", size={self.format_file_size(self.starting_size_bytes)}"
        return f"{self.__class__.__name__}(name={Path(self.path_).name}{size_info})"

    def __str__(self) -> str:
        """Provide a detailed string representation with size information."""
        file_name = Path(self.path_).name
        pages_count = len(self.pages_index)

        size_info = ""
        if self.starting_size_bytes is not None:
            start_size = self.format_file_size(self.starting_size_bytes)
            if self.ending_size_bytes is not None:
                end_size = self.format_file_size(self.ending_size_bytes)
                saved_bytes = self.starting_size_bytes - self.ending_size_bytes
                saved_size = self.format_file_size(saved_bytes)
                size_info = f" (Size: {start_size} → {end_size}, Saved: {saved_size})"
            else:
                size_info = f" (Size: {start_size})"

        return f"{file_name} - {pages_count} duplicate page(s){size_info}"

    def _get_current_file_size(self) -> int | None:
        """Get the current file size in bytes."""
        try:
            return Path(self.path_).stat().st_size
        except OSError:
            return None

    def add_page_index(self, index: int) -> None:
        """Add a page index to the list of duplicate pages."""
        if index not in self.pages_index:
            self.pages_index.append(index)

    def update_ending_size(self) -> None:
        """Update the ending file size after processing."""
        self.ending_size_bytes = self._get_current_file_size()

    def get_size_reduction(self) -> int | None:
        """Get the size reduction in bytes.

        Returns:
            Optional[int]: Size reduction in bytes, or None if sizes unavailable.
        """
        if self.starting_size_bytes is not None and self.ending_size_bytes is not None:
            return self.starting_size_bytes - self.ending_size_bytes
        return None

    def get_size_reduction_percentage(self) -> float | None:
        """Get the size reduction as a percentage.

        Returns:
            Optional[float]: Size reduction percentage, or None if sizes unavailable.
        """
        reduction = self.get_size_reduction()
        if reduction is not None and self.starting_size_bytes and self.starting_size_bytes > 0:
            return (reduction / self.starting_size_bytes) * 100
        return None

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format.

        Args:
            size_bytes: int: Size in bytes.

        Returns:
            str: Formatted size string (e.g., "1.5 MB", "234 KB").
        """
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0

        while size >= KB_SIZE and unit_index < len(units) - 1:
            size /= KB_SIZE
            unit_index += 1

        # Format with appropriate decimal places
        if unit_index == 0:  # Bytes
            return f"{int(size)} {units[unit_index]}"
        if size >= ROUND_TO_HUNDREDTH_PLACE:
            return f"{size:.0f} {units[unit_index]}"
        if size >= ROUND_TO_TENTH_PLACE:
            return f"{size:.1f} {units[unit_index]}"
        return f"{size:.2f} {units[unit_index]}"

    @property
    def size_reduction_formatted(self) -> str:
        """Get formatted size reduction."""
        reduction = self.get_size_reduction()
        return self.format_file_size(reduction) if reduction is not None else "Unknown"


class Duplicates:
    """A class for handling duplicate comic book pages.

    This class provides methods for identifying duplicate pages in a list of comic book files and performing actions
    on them.
    """

    def __init__(
        self,
        file_lst: list[Path],
        *,
        quick: bool = False,
        max_workers: int | None = None,
    ) -> None:
        """Initialize the Duplicates class with a list of file paths.

        The pages aren't hashed until a duplicate lookup first needs them.

        Args:
            file_lst: list[Path]: A list of file paths to be processed.
            quick: bool: If True, only scan the first 3 interior pages and last 3 pages
                of each comic (skipping the cover at page 0).
            max_workers: int | None: Maximum number of comics to scan concurrently. Defaults
                to the CPU count (capped at 8). A value of 1 scans serially.

        Raises:
            ValueError: If `file_lst` is empty or `max_workers` is less than 1.
        """
        if not file_lst:
            msg = "File list cannot be empty"
            raise ValueError(msg)
        if max_workers is not None and max_workers < 1:
            msg = "max_workers must be at least 1"
            raise ValueError(msg)

        if max_workers is None:
            max_workers = min(DEFAULT_MAX_WORKERS, os.cpu_count() or 1)

        self._file_lst = file_lst
        self._quick = quick
        self._max_workers = min(max_workers, len(file_lst))
        # Page locations grouped by image hash, filled in by the first scan.
        self._hash_cache: dict[str, list[PageLocation]] | None = None
        self._total_pages = 0

    def __enter__(self) -> Self:
        """Enter the context manager, returning this Duplicates."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Exit the context manager, freeing the cached page hashes."""
        self._clear_cache()

    def _clear_cache(self) -> None:
        """Clear internal caches to free memory."""
        self._hash_cache = None
        self._total_pages = 0

    def _generate_page_hashes(self) -> Generator[PageHash, None, None]:
        """Generator to yield page hash information for each comic page.

        Comics are scanned concurrently, one comic per worker thread, with results yielded in
        the same order as the file list.

        Yields:
            PageHash: The page's comic path, index and hash.
        """
        UIPresenter.print_info("Getting page hashes.")
        if self._max_workers == 1:
            yield from self._collect_hashes(map(self._hash_comic, self._file_lst))
            return

        executor = ThreadPoolExecutor(max_workers=self._max_workers)
        try:
            yield from self._collect_hashes(executor.map(self._hash_comic, self._file_lst))
        finally:
            # Drop queued comics if we're interrupted (e.g. Ctrl-C) or the consumer stops early.
            executor.shutdown(wait=False, cancel_futures=True)

    def _collect_hashes(
        self, results: Iterable[list[PageHash]]
    ) -> Generator[PageHash, None, None]:
        """Yield page hashes from per-comic results, showing scan progress."""
        for page_hashes in tqdm(results, total=len(self._file_lst), desc="Processing comics"):
            yield from page_hashes

    def _hash_comic(self, item: Path) -> list[PageHash]:
        """Hash the pages of a single comic.

        Each call opens its own Comic, so it is safe to run from multiple threads.

        Args:
            item: Path: The comic archive to scan.

        Returns:
            list[PageHash]: The comic's page hashes, empty if the comic was skipped.
        """
        # Runs in worker threads under a progress bar, so only log invalid comics.
        if (comic := open_comic(item, report=False)) is None:
            return []

        if not comic.can_remove_pages():
            LOGGER.info("Skipping %s, pages can't be removed", comic)
            return []

        return list(self._process_comic_pages(comic))

    def _get_page_indices(self, num_pages: int) -> list[int]:
        """Get page indices to process based on the scanning mode.

        In quick mode, returns the first 3 interior pages (skipping the cover at
        page 0) and the last 3 pages. In normal mode, returns all page indices
        except the cover (page 0).

        Args:
            num_pages: Total number of pages in the comic.

        Returns:
            list[int]: Sorted list of page indices to process.
        """
        if not self._quick:
            return list(range(1, num_pages))

        indices: set[int] = set()
        # First 3 interior pages (skip cover at index 0)
        for i in range(1, min(4, num_pages)):
            indices.add(i)
        # Last 3 pages
        for i in range(max(num_pages - 3, 1), num_pages):
            indices.add(i)
        return sorted(indices)

    def _process_comic_pages(self, comic: Comic) -> Generator[PageHash, None, None]:
        """Process pages in a comic and yield hash information.

        In quick mode, only the first 3 interior pages and last 3 pages are
        processed. Otherwise, all pages except the cover are processed.

        Args:
            comic: Comic object to process

        Yields:
            PageHash: The page's comic path, index and hash.
        """
        num_pages = comic.get_number_of_pages()
        for page_idx in self._get_page_indices(num_pages):
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
    def _calculate_image_hash(page_data: bytes | None) -> str | None:
        """Calculate the hash for a single image page.

        Args:
            page_data: Raw image data as bytes, or None if the page couldn't be read

        Returns:
            str | None: Hash string or None if calculation failed
        """
        if page_data is None:
            return None
        try:
            with Image.open(io.BytesIO(page_data)) as img:
                # Ask the JPEG decoder for a reduced-size grayscale image; a no-op for other
                # formats. pillow-jxl-plugin decodes the full image inside Image.open(), so
                # JXL pages always arrive at full resolution.
                img.draft("L", HASH_DRAFT_SIZE)
                return str(average_hash(img))
        # pillow-jxl-plugin raises RuntimeError on corrupt/truncated JXL data.
        except (UnidentifiedImageError, OSError, RuntimeError) as e:
            LOGGER.debug("Unable to calculate hash for image: %s", e)
            return None

    def _scan(self) -> dict[str, list[PageLocation]]:
        """Hash every page once, grouping page locations by image hash.

        The result is cached, so later calls don't rescan the comics.
        """
        if self._hash_cache is not None:
            return self._hash_cache

        hash_cache: dict[str, list[PageLocation]] = defaultdict(list)
        total_pages = 0
        for page in self._generate_page_hashes():
            hash_cache[page["hash"]].append({"path": page["path"], "index": page["index"]})
            total_pages += 1

        if not total_pages:
            LOGGER.warning("No valid page hashes found")
        self._hash_cache = dict(hash_cache)
        self._total_pages = total_pages
        return self._hash_cache

    def _duplicate_groups(self) -> dict[str, list[PageLocation]]:
        """Return the hashes found on more than one page, in hash order."""
        return {
            img_hash: locations
            for img_hash, locations in sorted(self._scan().items())
            if len(locations) > 1
        }

    def get_distinct_hashes(self) -> list[str]:
        """Get the distinct hashes of images that appear on more than one page.

        Returns:
            list[str]: The hashes, in sorted order.
        """
        return list(self._duplicate_groups())

    def get_comic_list_from_hash(self, img_hash: str) -> list[DuplicateIssue]:
        """Get a list of DuplicateIssue objects from a hash value.

        Args:
            img_hash: str: The hash value to search for.

        Returns:
            list[DuplicateIssue]: A list of DuplicateIssue objects representing comics with the specified hash value.
        """
        return [
            DuplicateIssue(entry["path"], [entry["index"]])
            for entry in self._scan().get(img_hash, [])
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
            if (comic := open_comic(item.path_, report=False)) is None:
                continue

            # Sort pages in descending order to avoid index shifting issues
            sorted_pages = sorted(item.pages_index, reverse=True)

            try:
                success = comic.remove_pages(sorted_pages)
            except (ValueError, OSError) as e:
                LOGGER.error("Error deleting pages from %s: %s", item.path_, e)  # noqa: TRY400
                results[item.path_] = False
                UIPresenter.print_error(
                    f"Error removing duplicate pages from {Path(item.path_).name}: {e}"
                )
                continue

            if success:
                item.update_ending_size()

            results[item.path_] = success

            if success:
                UIPresenter.print_success(f"Removed duplicate pages from {comic}")
            else:
                UIPresenter.print_warning(f"Failed to remove duplicate pages from {comic}")

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

        if (comic := open_comic(duplicate_issue.path_, report=False)) is None:
            return False

        # Use first page index if multiple are available
        page_index = duplicate_issue.pages_index[0]
        try:
            img_data = comic.get_page(page_index)
        except (ValueError, OSError):
            LOGGER.exception("Unable to retrieve page")
            img_data = None
        if img_data is None:
            LOGGER.warning(
                "No image data for page %d of %s", page_index, duplicate_issue.path_
            )
            return False

        try:
            with io.BytesIO(img_data) as img_io:
                image = Image.open(img_io)
                image.show()
                return True
        except (UnidentifiedImageError, ValueError, TypeError) as e:
            LOGGER.warning("Unable to show image from %s: %s", duplicate_issue.path_, e)
            UIPresenter.print_warning(
                f"Unable to show image from {Path(duplicate_issue.path_).name}."
            )
            return False
        except Exception as e:  # noqa: BLE001
            LOGGER.error(  # noqa: TRY400
                "Unexpected error showing image from %s: %s", duplicate_issue.path_, e
            )
            return False

    def get_statistics(self) -> dict[str, int]:
        """Get statistics about the duplicate detection process.

        Returns:
            dict[str, int]: Dictionary containing various statistics.
        """
        duplicate_groups = self._duplicate_groups()
        return {
            "total_pages": self._total_pages,
            "duplicate_pages": sum(len(locations) for locations in duplicate_groups.values()),
            "unique_duplicate_hashes": len(duplicate_groups),
            "comics_processed": len(self._file_lst),
        }


def _pages(count: int) -> str:
    return f"{count} page{'s' if count != 1 else ''}"


class DuplicatesPresenter(UIPresenter):
    """Console output for duplicate page removal."""

    RULE = "=" * 60
    SUB_RULE = "-" * 40

    @classmethod
    def print_pre_processing_summary(cls, duplicates_lst: list[DuplicateIssue]) -> None:
        """Print a summary of the pages about to be removed."""
        if not duplicates_lst:
            return

        total_pages_to_remove = sum(len(dup.pages_index) for dup in duplicates_lst)
        total_starting_size = sum(
            dup.starting_size_bytes
            for dup in duplicates_lst
            if dup.starting_size_bytes is not None
        )

        cls.print_info("\n" + cls.RULE)
        cls.print_heading("DUPLICATE REMOVAL SUMMARY")
        cls.print_info(cls.RULE)
        cls.print_info(f"Comics to process: {len(duplicates_lst)}")
        cls.print_info(f"Total duplicate pages to remove: {total_pages_to_remove}")
        cls.print_info(
            f"Total starting size: {DuplicateIssue.format_file_size(total_starting_size)}"
        )
        cls.print_info(cls.RULE + "\n")

    @classmethod
    def _print_successful(cls, successful: list[DuplicateIssue]) -> None:
        cls.print_success("✅ SUCCESSFULLY PROCESSED:")
        cls.print_info(cls.SUB_RULE)

        total_pages_removed = 0
        total_size_saved = 0
        for dup in successful:
            pages_removed = len(dup.pages_index)
            total_pages_removed += pages_removed

            size_info = ""
            if dup.starting_size_bytes is not None and dup.ending_size_bytes is not None:
                size_reduction = dup.get_size_reduction()
                if size_reduction and size_reduction > 0:
                    total_size_saved += size_reduction
                    percentage = dup.get_size_reduction_percentage()
                    size_info = f" (Saved: {dup.size_reduction_formatted}"
                    size_info += f", {percentage:.1f}%)" if percentage else ")"
            cls.print_success(
                f"  📁 {Path(dup.path_).name} - Removed {_pages(pages_removed)}{size_info}"
            )

        cls.print_info(cls.SUB_RULE)
        cls.print_success(f"📊 Total pages removed: {total_pages_removed}")
        cls.print_success(
            f"💾 Total space saved: {DuplicateIssue.format_file_size(total_size_saved)}"
        )
        if total_size_saved > 0:
            avg_saved = total_size_saved / len(successful)
            cls.print_success(
                f"📈 Average space saved per comic: {DuplicateIssue.format_file_size(int(avg_saved))}"
            )

    @classmethod
    def _print_failed(cls, failed: list[DuplicateIssue]) -> None:
        cls.print_error("\n❌ FAILED TO PROCESS:")
        cls.print_info(cls.SUB_RULE)
        for dup in failed:
            cls.print_error(
                f"  📁 {Path(dup.path_).name} - Failed to remove {_pages(len(dup.pages_index))}"
            )

    @classmethod
    def print_post_processing_summary(
        cls, duplicates_lst: list[DuplicateIssue], results: dict[str, bool]
    ) -> None:
        """Print which comics had pages removed, with size savings, and which failed."""
        if not duplicates_lst:
            return

        successful = [dup for dup in duplicates_lst if results.get(dup.path_, False)]
        failed = [dup for dup in duplicates_lst if not results.get(dup.path_, False)]

        cls.print_info("\n" + cls.RULE)
        cls.print_heading("DUPLICATE REMOVAL RESULTS")
        cls.print_info(cls.RULE)
        if successful:
            cls._print_successful(successful)
        if failed:
            cls._print_failed(failed)
        cls.print_info(cls.RULE + "\n")

    @staticmethod
    def create_statistics_msg(stats: dict[str, int]) -> str:
        """Create a formatted statistics message for duplicate processing.

        Args:
            stats: Statistics dictionary from `Duplicates.get_statistics`.
        """
        return (
            f"📈 PROCESSING STATISTICS:\n"
            f"  • Total Pages Scanned: {stats['total_pages']:,}\n"
            f"  • Duplicate Pages Found: {stats['duplicate_pages']:,}\n"
            f"  • Unique Duplicate Images: {stats['unique_duplicate_hashes']:,}\n"
            f"  • Comics Processed: {stats['comics_processed']:,}"
        )

    @classmethod
    def print_statistics(cls, stats: dict[str, int]) -> None:
        """Print the statistics from `Duplicates.get_statistics`."""
        cls.print_info(cls.create_statistics_msg(stats))
