from base64 import standard_b64encode

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
