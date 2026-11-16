"""The notes Metron-Tagger leaves in the metadata it writes.

Each note names the Metron-Tagger version and when it ran. The ComicInfo tagging
note also carries the Metron issue ID, which later runs read back (see
`MetadataExtractor.get_id_from_comic_info`), so its `[issue_id:N]` form must not
change.
"""

from __future__ import annotations

__all__ = ["migration_note", "tagging_notes"]

from datetime import datetime

from darkseid.metadata import Notes

from metrontagger import __version__

TAGGER = f"MetronTagger-{__version__}"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _timestamp() -> str:
    """The current time for a note, in local time as notes have always used."""
    return datetime.now().strftime(TIMESTAMP_FORMAT)  # noqa: DTZ005


def tagging_notes(issue_id: int) -> Notes:
    """Notes for a comic tagged from Metron issue `issue_id`."""
    note = f"Tagged with {TAGGER} using info from Metron on {_timestamp()}."
    return Notes(metron_info=note, comic_rack=f"{note} [issue_id:{issue_id}]")


def migration_note() -> str:
    """The MetronInfo note for metadata migrated from ComicInfo.xml."""
    return f"Data migrated from 'ComicInfo.xml' using {TAGGER} on {_timestamp()}."
