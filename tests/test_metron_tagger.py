"""Main metron_tagger tests"""

from metrontagger.talker import Talker


def test_create_metron_talker(settings) -> None:
    settings["metron.user"] = "test"
    settings["metron.password"] = "test_password"
    talker = Talker(settings["metron.user"], settings["metron.password"], True, True)
    assert isinstance(talker, Talker)
