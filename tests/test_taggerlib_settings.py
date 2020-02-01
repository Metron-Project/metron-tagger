from metrontagger.taggerlib.settings import MetronTaggerSettings


def test_read_settings(tmpdir):
    user = "test"
    dummy = "dummy_value"

    config = MetronTaggerSettings(config_dir=tmpdir)
    config.metron_user = user
    config.metron_pass = dummy
    config.save()

    # Now load that file and verify the contents
    new_config = MetronTaggerSettings(config_dir=tmpdir)
    assert new_config.metron_user == user
    assert new_config.metron_pass == dummy
