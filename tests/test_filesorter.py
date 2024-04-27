import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from darkseid.comic import Comic
from darkseid.metadata import Metadata

from metrontagger.filesorter import FileSorter


# Skip test for windows, until some with a windows box can help debug this.
@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_sort_comic_with_missing_metadata(
    fake_comic: ZipFile,
    fake_metadata: Metadata,
    tmp_path: Path,
) -> None:
    test_dir = tmp_path / "sort10"

    fake_metadata.series.volume = None

    comic = Comic(str(fake_comic))
    if comic.has_metadata():
        comic.remove_metadata()
    comic.write_metadata(fake_metadata)
    file_sorter = FileSorter(str(test_dir))
    res = file_sorter.sort_comics(Path(str(fake_comic)))
    assert res is False


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_sort_comic_with_no_series_metadata(
    fake_comic: ZipFile, fake_metadata: Metadata, tmp_path: Path
) -> None:
    test_dir = tmp_path / "sort2"
    fake_metadata.series = None
    comic = Comic(str(fake_comic))
    if comic.has_metadata():
        comic.remove_metadata()
    comic.write_metadata(fake_metadata)
    assert comic.has_metadata()
    file_sorter = FileSorter(str(test_dir))
    res = file_sorter.sort_comics(Path(str(fake_comic)))
    assert res is False


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_sort_comic(fake_comic: ZipFile, fake_metadata: Metadata, tmp_path: Path) -> None:
    test_dir = tmp_path / "sort1"

    test_dir.mkdir()

    result_dir = (
        test_dir
        / fake_metadata.publisher.name
        / fake_metadata.series.name
        / f"v{fake_metadata.series.volume}"
    )

    # Write metadata to fake file
    comic = Comic(str(fake_comic))
    if comic.has_metadata():
        comic.remove_metadata()
    comic.write_metadata(fake_metadata)

    file_sorter = FileSorter(str(test_dir))
    res = file_sorter.sort_comics(Path(str(fake_comic)))
    assert result_dir.is_dir()
    assert res is True


@pytest.mark.skipif(sys.platform in ["win32"], reason="Skip Windows.")
def test_sort_tpb(fake_comic: ZipFile, fake_tpb_metadata: Metadata, tmp_path: Path) -> None:
    test_dir = tmp_path / "sort1"

    test_dir.mkdir()

    result_dir = (
        test_dir
        / fake_tpb_metadata.publisher.name
        / f"{fake_tpb_metadata.series.name} TPB"
        / f"v{fake_tpb_metadata.series.volume}"
    )

    # Write metadata to fake file
    comic = Comic(str(fake_comic))
    if comic.has_metadata():
        comic.remove_metadata()
    comic.write_metadata(fake_tpb_metadata)

    file_sorter = FileSorter(str(test_dir))
    res = file_sorter.sort_comics(Path(str(fake_comic)))
    assert result_dir.is_dir()
    assert res is True


def test_sort_files_without_metadata(fake_comic: ZipFile, tmp_path: Path) -> None:
    test_dir = tmp_path / "sort2"
    # If we add more tests we should probably create another tmpfile
    # since we are removing the metadata from the tmpfile
    comic = Comic(str(fake_comic))
    comic.remove_metadata()

    file_sorter = FileSorter(str(test_dir))
    res = file_sorter.sort_comics(Path(str(fake_comic)))
    assert res is False
