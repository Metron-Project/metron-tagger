import zipfile
from argparse import ArgumentParser
from datetime import date
from io import BytesIO
from pathlib import Path
from random import randint

import pytest
from darkseid.metadata import Basic, Credit, Metadata, Role, Series
from PIL import Image

from metrontagger.options import make_parser
from metrontagger.talker import Talker

CONTENT = "blah blah blah"


def create_cover_page() -> bytes:
    """Create a small randomly colored square image."""
    r = randint(0, 255)  # noqa: S311
    g = randint(0, 255)  # noqa: S311
    b = randint(0, 255)  # noqa: S311
    img = Image.new("RGB", (250, 250), (r, g, b))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def parser() -> ArgumentParser:
    return make_parser()


@pytest.fixture(scope="session")
def talker() -> Talker:
    username = "Foo"
    password = "Bar"  # noqa: S105
    return Talker(username, password)


@pytest.fixture()
def fake_tpb_metadata() -> Metadata:
    meta_data = Metadata()
    meta_data.publisher = Basic("DC Comics")
    meta_data.series = Series("Batman", volume=1, format="Trade Paperback")
    meta_data.issue = "1"
    meta_data.cover_date = date(2021, 9, 1)
    meta_data.add_credit(Credit("Grant Morrison", [Role("Writer")]))
    meta_data.add_credit(Credit("Chris Burham", [Role("Artist"), Role("Cover")]))

    return meta_data


@pytest.fixture()
def fake_metadata() -> Metadata:
    meta_data = Metadata()
    meta_data.publisher = Basic("DC Comics")
    meta_data.series = Series("Aquaman", volume=2)
    meta_data.issue = "1"
    meta_data.cover_date = date(2011, 9, 1)
    meta_data.add_credit(Credit("Peter David", [Role("Writer")]))
    meta_data.add_credit(Credit("Martin Egeland", [Role("Penciller"), Role("Cover")]))

    return meta_data


@pytest.fixture()
def fake_comic(tmp_path_factory: Path) -> zipfile.ZipFile:
    z_file = tmp_path_factory.mktemp("comic") / "Aquaman v1 #001 (of 08) (1994).cbz"
    image_data = create_cover_page()
    with zipfile.ZipFile(z_file, mode="w") as zf:
        zf.writestr("cover.jpg", image_data)

    return z_file


@pytest.fixture()
def fake_tpb(tmp_path_factory: Path) -> zipfile.ZipFile:
    z_file = (
        tmp_path_factory.mktemp("comic")
        / "Batman - The Adventures Continue Season One (2021) "
        "(digital) (Son of Ultron-Empire).cbz"
    )
    image_data = create_cover_page()
    with zipfile.ZipFile(z_file, mode="w") as zf:
        zf.writestr("cover.jpg", image_data)

    return z_file
