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
    assert not config["sort.directory"]
    assert config["rename.rename_issue_number_padding"] == 3
    assert config["rename.rename_use_smart_string_cleanup"] is True
    assert config["rename.rename_template"] == ""

    # Save the new values
    config["metron.user"] = user
    config["metron.password"] = dummy
    config["rename.rename_issue_number_padding"] = padding
    config["rename.rename_use_smart_string_cleanup"] = str(cleanup)
    config["rename.rename_template"] = file_template
    config["sort.directory"] = "/tmp/foo"  # NOQA: S108
    # Now load that file and verify the contents
    new_config = settings
    assert new_config["metron.user"] == user
    assert new_config["metron.password"] == dummy
    assert new_config["sort.directory"] == "/tmp/foo"  # NOQA: S108
    assert new_config["rename.rename_issue_number_padding"] == padding
    assert new_config["rename.rename_use_smart_string_cleanup"] == cleanup
    assert new_config["rename.rename_template"] == file_template
