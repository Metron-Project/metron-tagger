from base64 import standard_b64encode

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
