import zipfile
from pathlib import Path

import pytest
from darkseid.comicarchive import ComicArchive

from metrontagger.taggerlib.filesorter import FileSorter

CONTENT = "blah blah blah"


@pytest.fixture()
def fake_comic(tmp_path, fake_metadata):
    img_1 = tmp_path / "image-1.jpg"
    img_1.write_text(CONTENT)
    img_2 = tmp_path / "image-2.jpg"
    img_2.write_text(CONTENT)
    img_3 = tmp_path / "image-3.jpg"
    img_3.write_text(CONTENT)

    z_file = tmp_path / "Aquaman v1 #001 (of 08) (1994).cbz"
    zf = zipfile.ZipFile(z_file, "w")
    try:
        zf.write(img_1)
        zf.write(img_2)
        zf.write(img_3)
    finally:
        zf.close()

    comic = ComicArchive(z_file)
    comic.write_metadata(fake_metadata)

    return z_file


def test_sort_comic(fake_comic, fake_metadata, tmpdir):
    test_dir = tmpdir
    result_dir = Path(test_dir).joinpath(
        fake_metadata.publisher, fake_metadata.series, f"v{fake_metadata.volume}"
    )
    file_sorter = FileSorter(test_dir)
    res = file_sorter.sort_comics(fake_comic)
    assert result_dir.is_dir()
    assert res is True


def test_sort_files_without_metadata(fake_comic, tmpdir):
    # If we add more tests we should probably create another tmpfile
    # since we are removing the metadata from the tmpfile
    comic = ComicArchive(fake_comic)
    comic.remove_metadata()

    file_sorter = FileSorter(tmpdir)
    res = file_sorter.sort_comics(fake_comic)
    assert res is False
