"""Main metron_tagger tests"""

from metrontagger.talker import Talker


def test_create_metron_talker(settings) -> None:
    settings["metron.auth_token"] = "test-token"  # noqa: S105
    talker = Talker(settings["metron.auth_token"], True, True)
    assert isinstance(talker, Talker)
