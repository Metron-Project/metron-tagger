import zipfile
from argparse import ArgumentParser
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
from darkseid.comic import Comic, MetadataFormat
from darkseid.metadata import Credit, Metadata, Publisher, Role, Series

from metrontagger.options import make_parser
from metrontagger.settings import MetronTaggerSettings
from metrontagger.talker import Talker
from tests.fakes import create_cover_page

CONTENT = "blah blah blah"


@pytest.fixture(scope="session")
def parser() -> ArgumentParser:
    return make_parser()


@pytest.fixture
def settings(tmp_path: Path) -> MetronTaggerSettings:
    return MetronTaggerSettings(config_dir=str(tmp_path))


@pytest.fixture(scope="session")
def talker() -> Talker:
    return Talker("dummy-token", [MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO])


@pytest.fixture()
def fake_tpb_metadata() -> Metadata:
    meta_data = Metadata()
    meta_data.publisher = Publisher("DC Comics")
    meta_data.series = Series("Batman", volume=1, format="Trade Paperback")
    meta_data.issue = "1"
    meta_data.cover_date = date(2021, 9, 1)
    meta_data.add_credit(Credit("Grant Morrison", [Role("Writer")]))
    meta_data.add_credit(Credit("Chris Burham", [Role("Artist"), Role("Cover")]))

    return meta_data


@pytest.fixture()
def fake_metadata() -> Metadata:
    meta_data = Metadata()
    meta_data.publisher = Publisher("DC Comics")
    meta_data.series = Series("Aquaman", volume=2)
    meta_data.issue = "1"
    meta_data.cover_date = date(2011, 9, 1)
    meta_data.add_credit(Credit("Peter David", [Role("Writer")]))
    meta_data.add_credit(Credit("Martin Egeland", [Role("Penciller"), Role("Cover")]))

    return meta_data


@pytest.fixture()
def fake_comic(tmp_path_factory: pytest.TempPathFactory) -> Path:
    z_file = tmp_path_factory.mktemp("comic") / "Aquaman v1 #001 (of 08) (1994).cbz"
    image_data = create_cover_page()
    with zipfile.ZipFile(z_file, mode="w") as zf:
        zf.writestr("cover.jpg", image_data)

    return z_file


@pytest.fixture()
def fake_tpb(tmp_path_factory: pytest.TempPathFactory) -> Path:
    z_file = (
        tmp_path_factory.mktemp("comic")
        / "Batman - The Adventures Continue Season One (2021) "
        "(digital) (Son of Ultron-Empire).cbz"
    )
    image_data = create_cover_page()
    with zipfile.ZipFile(z_file, mode="w") as zf:
        zf.writestr("cover.jpg", image_data)

    return z_file


@pytest.fixture
def mock_comic():
    """Create a mock Comic object."""
    comic = Mock(spec=Comic)
    comic.is_writable.return_value = True
    comic.seems_to_be_a_comic_archive.return_value = True
    comic.has_metadata.return_value = False
    comic.get_number_of_pages.return_value = 20
    comic.get_page.return_value = b"fake_image_data"
    comic.write_metadata.return_value = True
    return comic
