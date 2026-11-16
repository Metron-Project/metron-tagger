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
    assert config["metron.password"] is None
    assert config["metron.token_migration_prompted"] is None
    assert "password" not in settings_file.read_text(encoding="utf-8")


def test_settings_values_read_back_from_file_have_default_types(tmp_path) -> None:
    """Values reloaded from settings.ini come back as their default's type."""
    from metrontagger.settings import MetronTaggerSettings  # noqa: PLC0415

    config = MetronTaggerSettings(config_dir=tmp_path)
    config["rename.rename_issue_number_padding"] = 5
    config["rename.rename_use_smart_string_cleanup"] = False
    config["sort.directory"] = "/comics"

    reloaded = MetronTaggerSettings(config_dir=tmp_path)

    assert reloaded["rename.rename_issue_number_padding"] == 5
    assert type(reloaded["rename.rename_issue_number_padding"]) is int
    assert reloaded["rename.rename_use_smart_string_cleanup"] is False
    assert reloaded["sort.directory"] == "/comics"


def test_settings_every_default_round_trips_with_its_type(tmp_path) -> None:
    """Each default, written to the file and read back, keeps its value and type."""
    from metrontagger.settings import MetronTaggerSettings  # noqa: PLC0415

    MetronTaggerSettings(config_dir=tmp_path)  # writes the defaults
    reloaded = MetronTaggerSettings(config_dir=tmp_path)

    for section, options in MetronTaggerSettings.DEFAULT_CONFIG.items():
        for option, default in options.items():
            value = reloaded[f"{section}.{option}"]
            assert value == default
            assert type(value) is type(default)


def test_settings_option_without_default_is_a_string(tmp_path) -> None:
    from metrontagger.settings import MetronTaggerSettings  # noqa: PLC0415

    (tmp_path / "settings.ini").write_text("[extra]\ncount = 7\n", encoding="utf-8")

    assert MetronTaggerSettings(config_dir=tmp_path)["extra.count"] == "7"


def test_settings_invalid_typed_value_reads_as_none(tmp_path) -> None:
    """A value that can't be converted to its option's type reads as None."""
    from metrontagger.settings import MetronTaggerSettings  # noqa: PLC0415

    (tmp_path / "settings.ini").write_text(
        "[rename]\nrename_issue_number_padding = lots\n", encoding="utf-8"
    )

    assert (
        MetronTaggerSettings(config_dir=tmp_path)["rename.rename_issue_number_padding"] is None
    )
