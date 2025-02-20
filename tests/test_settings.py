def test_settings(settings) -> None:
    user = "test"
    dummy = "dummy_value"
    padding = 4
    cleanup = False
    file_template = "%series% v%volume% #%issue% (of %issuecount%) (%year%)"

    config = settings
    # Make sure initial values are correct
    assert not config["metron.user"]
    assert not config["metron.password"]
    assert not config["DEFAULT.sort_dir"]
    assert config["rename.rename_issue_number_padding"] == 3  # noqa: PLR2004
    assert config["rename.rename_use_smart_string_cleanup"] is True
    assert config["rename.rename_template"] == "%series% %format% v%volume% #%issue% (%year%)"

    # Save the new values
    config["metron.user"] = user
    config["metron.password"] = dummy
    config["rename.rename_issue_number_padding"] = padding
    config["rename.rename_use_smart_string_cleanup"] = str(cleanup)
    config["rename.rename_template"] = file_template
    config["DEFAULT.sort_dir"] = "/tmp/foo"  # NOQA: S108
    # Now load that file and verify the contents
    new_config = settings
    assert new_config["metron.user"] == user
    assert new_config["metron.password"] == dummy
    assert new_config["DEFAULT.sort_dir"] == "/tmp/foo"  # NOQA: S108
    assert new_config["rename.rename_issue_number_padding"] == padding
    assert new_config["rename.rename_use_smart_string_cleanup"] == cleanup
    assert new_config["rename.rename_template"] == file_template
