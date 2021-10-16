import zipfile

import pytest
from darkseid.genericmetadata import GenericMetadata

from metrontagger.options import make_parser
from metrontagger.talker import Talker

CONTENT = "blah blah blah"


@pytest.fixture(scope="session")
def parser():
    return make_parser()


@pytest.fixture(scope="session")
def talker():
    username = "Foo"
    password = "Bar"
    return Talker(username, password)


@pytest.fixture(scope="function")
def fake_metadata():
    meta_data = GenericMetadata()
    meta_data.publisher = "DC Comics"
    meta_data.series = "Aquaman"
    meta_data.volume = "2"
    meta_data.issue = "1"
    meta_data.year = "2011"
    meta_data.add_credit("Peter David", "Writer")
    meta_data.add_credit("Martin Egeland", "Penciller")
    meta_data.add_credit("Martin Egeland", "Cover")

    return meta_data


@pytest.fixture(scope="function")
def fake_comic(tmp_path_factory):
    test_dir = tmp_path_factory.mktemp("data")
    img_1 = test_dir / "image-1.jpg"
    img_1.write_text(CONTENT)
    img_2 = test_dir / "image-2.jpg"
    img_2.write_text(CONTENT)
    img_3 = test_dir / "image-3.jpg"
    img_3.write_text(CONTENT)

    z_file = tmp_path_factory.mktemp("comic") / "Aquaman v1 #001 (of 08) (1994).cbz"
    zf = zipfile.ZipFile(z_file, "w")
    try:
        zf.write(img_1)
        zf.write(img_2)
        zf.write(img_3)
    finally:
        zf.close()

    return z_file
