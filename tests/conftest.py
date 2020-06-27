from base64 import standard_b64encode
from shutil import make_archive

import pytest
from darkseid.genericmetadata import GenericMetadata

from metrontagger.taggerlib.metrontalker import MetronTalker
from metrontagger.taggerlib.options import make_parser


@pytest.fixture(scope="module")
def parser():
    parser = make_parser()
    return parser


@pytest.fixture(scope="module")
def talker():
    auth = f"test_user:test_auth"
    base64string = standard_b64encode(auth.encode("utf-8"))
    talker = MetronTalker(base64string)
    return talker


@pytest.fixture(scope="session")
def fake_metadata():
    meta_data = GenericMetadata()
    meta_data.publisher = "DC Comics"
    meta_data.series = "Aquaman"
    meta_data.volume = "2"
    meta_data.issue = "1"
    meta_data.year = "2011"

    return meta_data


@pytest.fixture(scope="module")
def fake_comic(tmpdir_factory):
    image_dir = tmpdir_factory.mktemp("images")

    img_1 = image_dir.join("image-1.jpg")
    img_1.write(b"test data")

    img_2 = image_dir.join("image-2.jpg")
    img_2.write(b"more data")

    img_3 = image_dir.join("image-3.jpg")
    img_3.write(b"yet more data")

    comic_dir = tmpdir_factory.mktemp("comic")

    open(make_archive(comic_dir, "zip", image_dir))

    return comic_dir + ".zip"
