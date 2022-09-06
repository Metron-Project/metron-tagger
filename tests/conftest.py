import zipfile
from argparse import ArgumentParser
from datetime import date
from pathlib import Path

import pytest
from darkseid.metadata import Basic, Credit, Metadata, Role, Series

from metrontagger.options import make_parser
from metrontagger.talker import Talker

CONTENT = "blah blah blah"


@pytest.fixture(scope="session")
def parser() -> ArgumentParser:
    return make_parser()


@pytest.fixture(scope="session")
def talker() -> Talker:
    username = "Foo"
    password = "Bar"
    return Talker(username, password)


@pytest.fixture(scope="function")
def fake_tpb_metadata() -> Metadata:
    meta_data = Metadata()
    meta_data.publisher = Basic("DC Comics")
    meta_data.series = Series("Batman", volume=1, format="Trade Paperback")
    meta_data.issue = "1"
    meta_data.cover_date = date(2021, 9, 1)
    meta_data.add_credit(Credit("Grant Morrison", [Role("Writer")]))
    meta_data.add_credit(Credit("Chris Burham", [Role("Artist"), Role("Cover")]))

    return meta_data


@pytest.fixture(scope="function")
def fake_metadata() -> Metadata:
    meta_data = Metadata()
    meta_data.publisher = Basic("DC Comics")
    meta_data.series = Series("Aquaman", volume=2)
    meta_data.issue = "1"
    meta_data.cover_date = date(2011, 9, 1)
    meta_data.add_credit(Credit("Peter David", [Role("Writer")]))
    meta_data.add_credit(Credit("Martin Egeland", [Role("Penciller"), Role("Cover")]))

    return meta_data


@pytest.fixture(scope="function")
def fake_comic(tmp_path_factory: Path) -> zipfile.ZipFile:
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
