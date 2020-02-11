import pytest

from metrontagger.taggerlib.options import make_parser


@pytest.fixture(scope="module")
def parser():
    parser = make_parser()
    return parser
