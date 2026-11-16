"""Main metron_tagger tests"""

from darkseid.comic import MetadataFormat

from metrontagger.talker import Talker


def test_create_metron_talker(settings) -> None:
    settings["metron.auth_token"] = "test-token"  # noqa: S105
    talker = Talker(
        settings["metron.auth_token"], [MetadataFormat.COMIC_INFO, MetadataFormat.METRON_INFO]
    )
    assert isinstance(talker, Talker)
