from base64 import standard_b64encode
from shutil import make_archive

import pytest

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
