import zipfile

import pytest

from metrontagger.taggerlib.filerenamer import FileRenamer

CONTENT = "blah blah blah"


@pytest.fixture()
def fake_comic(tmp_path):
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

    return z_file


def test_determine_name(fake_comic, fake_metadata):
    expected_result = "Aquaman v2 #001 (2011).cbz"

    renamer = FileRenamer(fake_metadata)
    new_file_name = renamer.determine_name(fake_comic)
    assert new_file_name == expected_result
