"""Tests for the notes Metron-Tagger writes into metadata."""

from datetime import datetime
from unittest.mock import patch

import pytest
from darkseid.utils import get_issue_id_from_note

from metrontagger import __version__
from metrontagger.notes import migration_note, tagging_notes

NOW = datetime(2026, 11, 16, 9, 30, 5)  # noqa: DTZ001 - notes use local time


@pytest.fixture
def frozen_now():
    with patch("metrontagger.notes.datetime") as mock_datetime:
        mock_datetime.now.return_value = NOW
        yield


@pytest.mark.usefixtures("frozen_now")
def test_tagging_notes() -> None:
    notes = tagging_notes(123)

    expected = f"Tagged with MetronTagger-{__version__} using info from Metron on 2026-11-16 09:30:05."
    assert notes.metron_info == expected
    assert notes.comic_rack == f"{expected} [issue_id:123]"


def test_tagging_notes_issue_id_can_be_read_back() -> None:
    """Later runs find the issue ID in the ComicInfo note, so its form must not change."""
    assert get_issue_id_from_note(tagging_notes(4567).comic_rack) == {
        "source": "Metron",
        "id": "4567",
    }


@pytest.mark.usefixtures("frozen_now")
def test_migration_note() -> None:
    assert migration_note() == (
        f"Data migrated from 'ComicInfo.xml' using MetronTagger-{__version__} "
        "on 2026-11-16 09:30:05."
    )
