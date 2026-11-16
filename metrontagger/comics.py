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

from darkseid.archivers import ArchiverReadError
from darkseid.comic import Comic, ComicArchiveError, MetadataFormat

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

    A format whose XML can't be read is logged and skipped, so callers fall through
    to the next format. darkseid doesn't raise for malformed XML: it logs the parse
    error and returns an empty Metadata, so an empty result counts as unreadable.
    """
    current = comic
    has_read = False
    for fmt in formats:
        if not current.has_metadata(fmt):
            continue
        if has_read:
            # darkseid's Comic caches the first metadata it reads in one slot shared
            # by every format, so reading another format from the same object would
            # return the earlier one again. Reopen the archive to read this one fresh.
            # Remove once https://github.com/Metron-Project/darkseid/issues/267 is fixed.
            reopened = open_comic(comic.path, report=False)
            if reopened is None:
                return
            current = reopened
        has_read = True
        try:
            md = current.read_metadata(fmt)
        except (ArchiverReadError, KeyError) as e:
            LOGGER.warning("Unable to read %s from %s: %s", FORMAT_NAMES[fmt], comic, e)
            continue
        if md is None or md.is_empty:
            LOGGER.warning(
                "Unable to read %s from %s: no metadata parsed", FORMAT_NAMES[fmt], comic
            )
            continue
        yield fmt, md


def read_preferred_metadata(comic: Comic) -> Metadata | None:
    """Read the comic's preferred metadata: MetronInfo if readable, else ComicInfo."""
    return next((md for _, md in iter_metadata(comic)), None)
