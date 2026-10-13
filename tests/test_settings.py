def test_settings(settings) -> None:
    user = "test"
    dummy = "dummy_value"
    padding = 4
    cleanup = False
    file_template = "%series% v%volume% #%issue% (of %issuecount%) (%year%)"

    config = settings
    # Make sure initial values are correct
    assert not config["metron.user"]
    assert not config["metron.auth_token"]
    assert not config["sort.directory"]
    assert config["rename.rename_issue_number_padding"] == 3
    assert config["rename.rename_use_smart_string_cleanup"] is True
    assert config["rename.rename_template"] == ""

    # Save the new values
    config["metron.user"] = user
    config["metron.auth_token"] = dummy
    config["rename.rename_issue_number_padding"] = padding
    config["rename.rename_use_smart_string_cleanup"] = str(cleanup)
    config["rename.rename_template"] = file_template
    config["sort.directory"] = "/tmp/foo"  # NOQA: S108
    # Now load that file and verify the contents
    new_config = settings
    assert new_config["metron.user"] == user
    assert new_config["metron.auth_token"] == dummy
    assert new_config["sort.directory"] == "/tmp/foo"  # NOQA: S108
    assert new_config["rename.rename_issue_number_padding"] == padding
    assert new_config["rename.rename_use_smart_string_cleanup"] == cleanup
    assert new_config["rename.rename_template"] == file_template


def test_settings_removes_obsolete_options(tmp_path) -> None:
    """Basic Auth options left over from older versions are removed on load."""
    from metrontagger.settings import MetronTaggerSettings  # noqa: PLC0415

    settings_file = tmp_path / "settings.ini"
    settings_file.write_text(
        "[metron]\nuser = test\npassword = secret\ntoken_migration_prompted = true\n",
        encoding="utf-8",
    )

    config = MetronTaggerSettings(config_dir=tmp_path)

    assert config["metron.user"] == "test"
    assert not config.has_option("metron.password")
    assert not config.has_option("metron.token_migration_prompted")
    assert "password" not in settings_file.read_text(encoding="utf-8")
