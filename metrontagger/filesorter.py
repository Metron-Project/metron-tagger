"""Class to sort comic file based on its metadata tags"""

from __future__ import annotations

__all__ = ["FileSorter"]

import logging
from pathlib import Path
from shutil import Error as ShutilError, move
from typing import TYPE_CHECKING, NamedTuple

import questionary
from darkseid.archivers import ArchiverReadError
from darkseid.comic import Comic, ComicArchiveError, MetadataFormat

if TYPE_CHECKING:
    from darkseid.metadata import Metadata

from metrontagger.styles import Styles
from metrontagger.utils import cleanup_string

logger = logging.getLogger(__name__)


class CleanedMetadata(NamedTuple):
    """Container for cleaned metadata components."""

    publisher: str | None
    series: str | None
    volume: str | None


class FileSizeInfo(NamedTuple):
    """Container for file size information."""

    existing_mb: float
    new_mb: float


def get_file_size_mb(file_path: Path) -> float:
    """
    Returns the size of the file in megabytes.

    Args:
        file_path: The path to the file.

    Returns:
        The size of the file in megabytes.

    Raises:
        OSError: If the file cannot be accessed or stat fails.
    """
    try:
        megabyte = 1_048_576  # Use underscore for better readability
        return file_path.stat().st_size / megabyte
    except OSError:
        logger.exception(f"Failed to get file size for {file_path}")
        raise


class FileSorter:
    """
    A class to move comic files based on their metadata tags.

    This class provides functionality to sort comic files into a directory structure
    based on publisher, series, and volume information extracted from metadata.
    """

    def __init__(self, directory: str | Path) -> None:
        """
        Initialize the FileSorter with a target directory.

        Args:
            directory: The directory path for sorting files.

        Raises:
            ValueError: If the directory path is empty or None.
        """
        if not directory:
            msg = "Directory path cannot be empty or None"
            raise ValueError(msg)

        self.sort_directory = Path(directory)
        logger.info(f"FileSorter initialized with directory: {self.sort_directory}")

    @staticmethod
    def _cleanup_metadata(meta_data: Metadata) -> CleanedMetadata:
        """
        Clean and extract metadata components.

        Args:
            meta_data: The metadata to clean.

        Returns:
            A CleanedMetadata object containing cleaned publisher, series, and volume strings.
        """
        # Prefer imprint over publisher if available
        if meta_data.publisher and meta_data.publisher.imprint:
            publisher = cleanup_string(meta_data.publisher.imprint.name)
        elif meta_data.publisher:
            publisher = cleanup_string(meta_data.publisher.name)
        else:
            publisher = None

        if meta_data.series:
            series = cleanup_string(meta_data.series.name)
            volume = cleanup_string(meta_data.series.volume)
        else:
            series = volume = None

        return CleanedMetadata(publisher, series, volume)

    @staticmethod
    def _move_file_safely(source: Path, destination_dir: Path) -> bool:
        """
        Safely move a file from source to destination directory.

        Args:
            source: The source file path.
            destination_dir: The target directory path.

        Returns:
            True if the file was successfully moved, False otherwise.
        """
        destination = destination_dir / source.name

        try:
            move(str(source), str(destination))
            questionary.print(
                f"Moved '{source.name}' to '{destination_dir}'", style=Styles.SUCCESS
            )
            logger.info(f"Successfully moved {source} to {destination}")
        except ShutilError as e:
            error_msg = f"Failed to move '{source.name}' to '{destination_dir}': {e}"
            questionary.print(error_msg, style=Styles.ERROR)
            logger.exception(error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected error moving '{source.name}': {e}"
            questionary.print(error_msg, style=Styles.ERROR)
            logger.exception(error_msg)
            return False
        else:
            return True

    @staticmethod
    def _get_file_size_comparison(existing_file: Path, new_file: Path) -> FileSizeInfo:
        """
        Compare file sizes between existing and new files.

        Args:
            existing_file: Path to the existing file.
            new_file: Path to the new file.

        Returns:
            FileSizeInfo containing size information for both files.

        Raises:
            OSError: If file size cannot be determined.
        """
        return FileSizeInfo(
            existing_mb=get_file_size_mb(existing_file), new_mb=get_file_size_mb(new_file)
        )

    def _handle_existing_file(self, destination_dir: Path, source_file: Path) -> bool:
        """
        Handle the case where a file with the same name already exists.

        Args:
            destination_dir: The destination directory.
            source_file: The source file being moved.

        Returns:
            True if the existing file was handled (removed or kept), False if user cancelled.
        """
        existing_file = destination_dir / source_file.name

        if not existing_file.exists():
            return True

        try:
            size_info = self._get_file_size_comparison(existing_file, source_file)

            message = (
                f"{existing_file.name} already exists at {existing_file.parent}.\n"
                f"Existing file: {size_info.existing_mb:.2f} MB -> "
                f"New file: {size_info.new_mb:.2f} MB"
            )
            questionary.print(message, style=Styles.WARNING)

            if questionary.confirm(
                "Would you like to overwrite the existing file?",
                default=False,
            ).ask():
                try:
                    existing_file.unlink()
                    logger.info(f"Removed existing file: {existing_file}")
                except OSError as e:
                    error_msg = f"Failed to remove existing file {existing_file}: {e}"
                    questionary.print(error_msg, style=Styles.ERROR)
                    logger.exception(error_msg)
                    return False
                else:
                    return True
            else:
                logger.info(f"User chose not to overwrite {existing_file}")
                return False

        except OSError as e:
            error_msg = f"Failed to compare file sizes: {e}"
            questionary.print(error_msg, style=Styles.ERROR)
            logger.exception(error_msg)
            return False

    def _build_destination_path(self, metadata: Metadata, cleaned: CleanedMetadata) -> Path:
        """
        Build the destination path based on metadata.

        Args:
            metadata: The comic metadata.
            cleaned: The cleaned metadata components.

        Returns:
            The constructed destination path.
        """
        is_trade_paperback = (
            metadata.series is not None and metadata.series.format == "Trade Paperback"
        )

        series_folder = f"{cleaned.series} TPB" if is_trade_paperback else cleaned.series

        return self.sort_directory / cleaned.publisher / series_folder / f"v{cleaned.volume}"

    @staticmethod
    def _create_directory_structure(path: Path) -> bool:
        """
        Create the directory structure if it doesn't exist.

        Args:
            path: The directory path to create.

        Returns:
            True if the directory was created or already exists, False on failure.
        """
        if path.exists():
            return True

        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory structure: {path}")
        except PermissionError:
            error_msg = f"Permission denied creating directory: {path}"
            questionary.print(error_msg, style=Styles.ERROR)
            logger.exception(f"{error_msg}")
            return False
        except OSError:
            error_msg = f"Failed to create directory: {path}"
            questionary.print(error_msg, style=Styles.ERROR)
            logger.exception(f"{error_msg}")
            return False
        else:
            return True

    @staticmethod
    def _load_comic_metadata(comic_path: Path) -> Metadata | None:
        """
        Load metadata from a comic file.

        Args:
            comic_path: Path to the comic file.

        Returns:
            The loaded metadata, or None if no suitable metadata is found.
        """
        try:
            comic_archive = Comic(comic_path)
        except ComicArchiveError:
            logger.exception("Failed to open comic: %s", str(comic_path))
            return None

        # Try MetronInfo first, then ComicRack
        for format_type in [MetadataFormat.METRON_INFO, MetadataFormat.COMIC_INFO]:
            if comic_archive.has_metadata(format_type):
                try:
                    return comic_archive.read_metadata(format_type)
                except ArchiverReadError as e:
                    logger.warning(
                        f"Failed to read {format_type} metadata from {comic_path}: {e}"
                    )
                    continue

        logger.warning(f"No readable metadata found in {comic_path}")
        return None

    @staticmethod
    def _validate_metadata_completeness(cleaned: CleanedMetadata, comic_name: str) -> bool:
        """
        Validate that all required metadata components are present.

        Args:
            cleaned: The cleaned metadata components.
            comic_name: Name of the comic file for error reporting.

        Returns:
            True if all required metadata is present, False otherwise.
        """
        missing_fields = []
        if not cleaned.publisher:
            missing_fields.append("Publisher")
        if not cleaned.series:
            missing_fields.append("Series")
        if not cleaned.volume:
            missing_fields.append("Volume")

        if missing_fields:
            message = (
                f"Missing required metadata from '{comic_name}' - cannot sort.\n"
                f"Missing: {', '.join(missing_fields)}\n"
                f"Present: Publisher={cleaned.publisher}, Series={cleaned.series}, Volume={cleaned.volume}"
            )
            questionary.print(message, style=Styles.WARNING)
            logger.warning(f"Incomplete metadata for {comic_name}: missing {missing_fields}")
            return False

        return True

    def sort_comics(self, comic_path: Path) -> bool:
        """
        Sort a comic file based on its metadata tags.

        This method reads the comic's metadata, extracts publisher, series, and volume
        information, creates the appropriate directory structure, and moves the file.

        Args:
            comic_path: The path to the comic file to sort.

        Returns:
            True if the comic file was successfully sorted, False otherwise.
        """
        if not comic_path.exists():
            logger.error(f"Comic file does not exist: {comic_path}")
            return False

        # Load metadata
        metadata = self._load_comic_metadata(comic_path)
        if not metadata:
            return False

        # Clean and validate metadata
        cleaned = self._cleanup_metadata(metadata)
        if not self._validate_metadata_completeness(cleaned, comic_path.name):
            return False

        # Build destination path
        destination_path = self._build_destination_path(metadata, cleaned)

        # Create directory structure
        if not self._create_directory_structure(destination_path):
            return False

        # Handle existing files
        if not self._handle_existing_file(destination_path, comic_path):
            logger.info(f"Skipping sort for {comic_path.name} due to existing file conflict")
            return False

        # Move the file
        return self._move_file_safely(comic_path, destination_path)
