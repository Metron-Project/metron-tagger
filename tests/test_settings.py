from metrontagger.settings import MetronTaggerSettings


def test_settings(tmpdir):
    user = "test"
    dummy = "dummy_value"
    padding = 4
    cleanup = False
    file_template = "%series% v%volume% #%issue% (of %issuecount%) (%year%)"

    config = MetronTaggerSettings(config_dir=tmpdir)
    # Make sure initial values are correct
    assert not config.metron_user
    assert not config.metron_pass
    assert not config.sort_dir
    assert config.rename_issue_number_padding == 3
    assert config.rename_use_smart_string_cleanup is True
    assert config.rename_template == "%series% v%volume% #%issue% (%year%)"
    # Save the new values
    config.metron_user = user
    config.metron_pass = dummy
    config.rename_issue_number_padding = padding
    config.rename_use_smart_string_cleanup = cleanup
    config.rename_template = file_template
    config.save()
    # Now load that file and verify the contents
    new_config = MetronTaggerSettings(config_dir=tmpdir)
    assert new_config.metron_user == user
    assert new_config.metron_pass == dummy
    assert not new_config.sort_dir
    assert new_config.rename_issue_number_padding == padding
    assert new_config.rename_use_smart_string_cleanup == cleanup
    assert new_config.rename_template == file_template
