from darkseid.comicarchive import ComicArchive

from metrontagger.filesorter import FileSorter


def test_sort_comic_with_missing_metadata(fake_comic, fake_metadata, tmp_path):
    test_dir = tmp_path / "sort10"

    fake_metadata.volume = None

    comic = ComicArchive(fake_comic)
    if comic.has_metadata():
        comic.remove_metadata()
    comic.write_metadata(fake_metadata)
    file_sorter = FileSorter(test_dir)
    res = file_sorter.sort_comics(fake_comic)
    assert res is False


def test_sort_comic(fake_comic, fake_metadata, tmp_path):
    test_dir = tmp_path / "sort1"

    test_dir.mkdir()

    result_dir = (
        test_dir / fake_metadata.publisher / fake_metadata.series / f"v{fake_metadata.volume}"
    )

    # Write metadata to fake file
    comic = ComicArchive(fake_comic)
    if comic.has_metadata():
        comic.remove_metadata()
    comic.write_metadata(fake_metadata)

    file_sorter = FileSorter(test_dir)
    res = file_sorter.sort_comics(fake_comic)
    assert result_dir.is_dir()
    assert res is True


def test_sort_files_without_metadata(fake_comic, tmp_path):
    test_dir = tmp_path / "sort2"
    # If we add more tests we should probably create another tmpfile
    # since we are removing the metadata from the tmpfile
    comic = ComicArchive(fake_comic)
    comic.remove_metadata()

    file_sorter = FileSorter(test_dir)
    res = file_sorter.sort_comics(fake_comic)
    assert res is False
