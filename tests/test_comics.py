"""Tests for the comic-opening and metadata-format helpers."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from darkseid.archivers import ArchiverReadError
from darkseid.comic import Comic, ComicArchiveError, MetadataFormat
from darkseid.metadata import Metadata, Series

from metrontagger.comics import (
    FORMAT_NAMES,
    format_list,
    iter_metadata,
    open_comic,
    read_preferred_metadata,
)

CI = MetadataFormat.COMIC_INFO
MI = MetadataFormat.METRON_INFO


@pytest.fixture
def printed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every message printed through the UI layer."""
    lines: list[str] = []
    monkeypatch.setattr(
        "metrontagger.ui.questionary.print", lambda msg, **_kw: lines.append(str(msg))
    )
    return lines


def _metadata(series: str) -> Metadata:
    md = Metadata()
    md.series = Series(series)
    md.issue = "1"
    return md


# Mock comics by path, so reopening one (see iter_metadata) returns the same mock.
_MOCK_COMICS: dict[Path, Mock] = {}


@pytest.fixture(autouse=True)
def _reopen_mock_comics():
    """Make Comic(path) return the mock comic for a mock's path, else a real Comic."""
    real_comic = Comic
    with patch(
        "metrontagger.comics.Comic",
        side_effect=lambda path: _MOCK_COMICS.get(path) or real_comic(path),
    ):
        yield
    _MOCK_COMICS.clear()


def _mock_comic(readable: dict[MetadataFormat, Metadata | Exception | None]) -> Mock:
    """A comic that has the given formats; an Exception value is raised on read."""
    comic = Mock(spec=Comic)
    comic.path = Path(f"/mock/{len(_MOCK_COMICS)}.cbz")
    _MOCK_COMICS[comic.path] = comic
    comic.has_metadata.side_effect = lambda fmt: fmt in readable

    def read(fmt: MetadataFormat) -> Metadata | None:
        value = readable[fmt]
        if isinstance(value, Exception):
            raise value
        return value

    comic.read_metadata.side_effect = read
    return comic


# open_comic
def test_open_comic_valid(fake_comic: Path, printed: list[str]) -> None:
    comic = open_comic(fake_comic)

    assert isinstance(comic, Comic)
    assert printed == []


@pytest.mark.parametrize("report", [True, False])
def test_open_comic_invalid(
    report: bool, printed: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    with patch("metrontagger.comics.Comic", side_effect=ComicArchiveError):
        assert open_comic(Path("/x/bad.cbz"), report=report) is None

    assert "Comic not valid" in caplog.text
    assert printed == (["'bad.cbz' is not a valid comic. Skipping..."] if report else [])


def test_open_comic_accepts_str(fake_comic: Path) -> None:
    assert isinstance(open_comic(str(fake_comic)), Comic)


# format_list
@pytest.mark.parametrize(
    ("formats", "expected"),
    [
        ([CI], "'ComicInfo.xml'"),
        ([MI], "'MetronInfo.xml'"),
        ([CI, MI], "'ComicInfo.xml' and 'MetronInfo.xml'"),
        ([], ""),
    ],
)
def test_format_list(formats: list[MetadataFormat], expected: str) -> None:
    assert format_list(formats) == expected


def test_format_names_cover_every_format() -> None:
    assert set(FORMAT_NAMES) == set(MetadataFormat) - {MetadataFormat.UNKNOWN}


# iter_metadata / read_preferred_metadata
def test_iter_metadata_yields_metron_info_first() -> None:
    mi, ci = _metadata("MI"), _metadata("CI")
    comic = _mock_comic({CI: ci, MI: mi})

    assert list(iter_metadata(comic)) == [(MI, mi), (CI, ci)]


def test_iter_metadata_respects_given_formats() -> None:
    mi, ci = _metadata("MI"), _metadata("CI")
    comic = _mock_comic({CI: ci, MI: mi})

    assert list(iter_metadata(comic, [CI])) == [(CI, ci)]


@pytest.mark.parametrize(
    "error", [ArchiverReadError("bad xml"), KeyError("MetronInfo.xml")], ids=type
)
def test_iter_metadata_skips_unreadable_format(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    ci = _metadata("CI")
    comic = _mock_comic({MI: error, CI: ci})

    assert list(iter_metadata(comic)) == [(CI, ci)]
    assert "Unable to read MetronInfo.xml" in caplog.text


def test_iter_metadata_skips_format_read_as_none() -> None:
    ci = _metadata("CI")
    comic = _mock_comic({MI: None, CI: ci})

    assert list(iter_metadata(comic)) == [(CI, ci)]


def test_iter_metadata_no_metadata() -> None:
    assert list(iter_metadata(_mock_comic({}))) == []


@pytest.mark.parametrize(
    ("readable", "expected_series"),
    [
        ({CI: "CI", MI: "MI"}, "MI"),
        ({CI: "CI"}, "CI"),
        ({MI: "MI"}, "MI"),
        ({}, None),
    ],
    ids=["both", "comicinfo_only", "metroninfo_only", "none"],
)
def test_read_preferred_metadata(
    readable: dict[MetadataFormat, str], expected_series: str | None
) -> None:
    comic = _mock_comic({fmt: _metadata(series) for fmt, series in readable.items()})

    md = read_preferred_metadata(comic)

    assert (md.series.name if md else None) == expected_series


def test_read_preferred_metadata_real_archive(
    fake_comic: Path, fake_metadata: Metadata, fake_tpb_metadata: Metadata
) -> None:
    """With both formats in a real archive, MetronInfo's data is read."""
    comic = Comic(fake_comic)
    assert comic.write_metadata(fake_tpb_metadata, CI)
    assert comic.write_metadata(fake_metadata, MI)

    md = read_preferred_metadata(Comic(fake_comic))

    assert md is not None
    assert md.series.name == fake_metadata.series.name


def test_iter_metadata_reads_each_format_fresh(fake_comic: Path) -> None:
    """Each format's own data is returned, despite darkseid caching the first read.

    darkseid's Comic keeps one metadata cache for every format, so without reopening
    the archive the second format read would return the first format's data.
    """
    comic = Comic(fake_comic)
    mi = _metadata("From MetronInfo")
    ci = _metadata("From ComicInfo")
    assert comic.write_metadata(mi, MI)
    assert comic.write_metadata(ci, CI)
    # Writing ComicInfo also updates MetronInfo, so put MetronInfo's own data back.
    assert Comic(fake_comic).write_metadata(mi, MI)

    read = {fmt: md.series.name for fmt, md in iter_metadata(Comic(fake_comic))}

    assert read == {MI: "From MetronInfo", CI: "From ComicInfo"}
