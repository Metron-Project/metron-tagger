"""Opening comic archives and reading their metadata formats.

Every module opens comics and picks a metadata format through these helpers, so
invalid archives, unreadable metadata and format names are handled the same way
everywhere.
"""

from __future__ import annotations

__all__ = [
    "FORMAT_NAMES",
    "READ_PREFERENCE",
    "format_list",
    "iter_metadata",
    "open_comic",
    "read_preferred_metadata",
]

from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

from darkseid.comic import Comic, ComicArchiveError, ComicMetadataError, MetadataFormat

from metrontagger.ui import UIPresenter

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from darkseid.metadata import Metadata

LOGGER = getLogger(__name__)

FORMAT_NAMES = {
    MetadataFormat.COMIC_INFO: "ComicInfo.xml",
    MetadataFormat.METRON_INFO: "MetronInfo.xml",
}

# The order formats are read in when a comic has both: MetronInfo holds more
# information, so it's preferred.
READ_PREFERENCE = (MetadataFormat.METRON_INFO, MetadataFormat.COMIC_INFO)


def open_comic(path: Path | str, *, report: bool = True) -> Comic | None:
    """Open a comic archive, returning None if it isn't a valid comic.

    The failure is always logged. With `report`, a "not a valid comic" error is also
    printed; pass False where the caller reports problems itself, or runs where
    printing would interfere (e.g. worker threads under a progress bar).
    """
    path = Path(path)
    try:
        return Comic(path)
    except ComicArchiveError:
        LOGGER.exception("Comic not valid: %s", path)
        if report:
            UIPresenter.print_error(f"'{path.name}' is not a valid comic. Skipping...")
        return None


def format_list(formats: Iterable[MetadataFormat]) -> str:
    """Name formats for a message, e.g. "'ComicInfo.xml' and 'MetronInfo.xml'"."""
    return " and ".join(f"'{FORMAT_NAMES[fmt]}'" for fmt in formats)


def iter_metadata(
    comic: Comic, formats: Iterable[MetadataFormat] = READ_PREFERENCE
) -> Iterator[tuple[MetadataFormat, Metadata]]:
    """Yield each of `formats`, in order, that the comic has and can be read.

    A format whose XML can't be read or parsed, or that parses to empty metadata, is
    logged and skipped, so callers fall through to the next format.
    """
    for fmt in formats:
        if not comic.has_metadata(fmt):
            continue
        try:
            md = comic.read_metadata(fmt, strict=True)
        except ComicMetadataError as e:
            LOGGER.warning("Unable to read %s from %s: %s", FORMAT_NAMES[fmt], comic, e)
            continue
        if md.is_empty:
            LOGGER.warning(
                "Unable to read %s from %s: no metadata parsed", FORMAT_NAMES[fmt], comic
            )
            continue
        yield fmt, md


def read_preferred_metadata(comic: Comic) -> Metadata | None:
    """Read the comic's preferred metadata: MetronInfo if readable, else ComicInfo."""
    return next((md for _, md in iter_metadata(comic)), None)
