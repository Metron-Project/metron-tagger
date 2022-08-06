import zipfile
from argparse import ArgumentParser
from datetime import date
from pathlib import Path

import pytest
from darkseid.genericmetadata import (
    CreditMetadata,
    GeneralResource,
    GenericMetadata,
    RoleMetadata,
    SeriesMetadata,
)

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
def fake_tpb_metadata() -> GenericMetadata:
    meta_data = GenericMetadata()
    meta_data.publisher = GeneralResource("DC Comics")
    meta_data.series = SeriesMetadata("Batman", volume=1, format="Trade Paperback")
    meta_data.issue = "1"
    meta_data.cover_date = date(2021, 9, 1)
    meta_data.add_credit(CreditMetadata("Grant Morrison", [RoleMetadata("Writer")]))
    meta_data.add_credit(
        CreditMetadata("Chris Burham", [RoleMetadata("Artist"), RoleMetadata("Cover")])
    )

    return meta_data


@pytest.fixture(scope="function")
def fake_metadata() -> GenericMetadata:
    meta_data = GenericMetadata()
    meta_data.publisher = GeneralResource("DC Comics")
    meta_data.series = SeriesMetadata("Aquaman", volume=2)
    meta_data.issue = "1"
    meta_data.cover_date = date(2011, 9, 1)
    meta_data.add_credit(CreditMetadata("Peter David", [RoleMetadata("Writer")]))
    meta_data.add_credit(
        CreditMetadata("Martin Egeland", [RoleMetadata("Penciller"), RoleMetadata("Cover")])
    )

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
