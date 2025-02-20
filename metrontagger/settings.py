"""Class to handle project settings"""

__all__ = ["MetronTaggerSettings"]

import configparser
from pathlib import Path

from metrontagger.utils import get_settings_folder


class MetronTaggerSettings:
    """Manages Metron Tagger settings.

    Handles loading and saving user settings, including credentials, file paths,
    and various application options.
    """

    def __init__(self, config_dir: str | None = None) -> None:
        """Initialize MetronTaggerSettings.

        Sets up the settings object, creating necessary sections. Creates an empty
        settings file if one doesn't exist.
        """
        self.config = configparser.RawConfigParser()
        folder = Path(config_dir) if config_dir else get_settings_folder()
        self.settings_file = folder / "settings.ini"

        self.config.read(self.settings_file)

        if not self.config.has_section("metron"):
            self.config.add_section("metron")

        if not self.config.has_section("rename"):
            self.config.add_section("rename")

        if not self.settings_file.parent.exists():
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)

        # Template default values
        if not self.config.has_option("rename", "rename_issue_number_padding"):
            self.config.set("rename", "rename_issue_number_padding", "3")

        if not self.config.has_option("rename", "rename_use_smart_string_cleanup"):
            self.config.set("rename", "rename_use_smart_string_cleanup", "True")

        if not self.config.has_option("rename", "rename_template"):
            rename_template = "%series% %format% v%volume% #%issue% (%year%)"
            self.config.set("rename", "rename_template", rename_template)

        if not self.settings_file.exists():
            with self.settings_file.open("w") as f:
                self.config.write(f)

    def __getitem__(self, key: str) -> str | int | bool | None:
        """Retrieve a setting value.

        Retrieves the value associated with the given key, which should be in the
        format "section.option".

        Args:
            key: The setting key in "section.option" format.

        Returns:
            The setting value if found, otherwise None.
        """
        section, option = key.split(".")
        if self.config.has_option(section, option):
            # Handle some non-string values
            if section == "rename":
                if option == "rename_issue_number_padding":
                    return self.config.getint(section, option)
                if option == "rename_use_smart_string_cleanup":
                    return self.config.getboolean(section, option)
                return self.config.get(section, option)
            return self.config.get(section, option)
        return None

    def __setitem__(self, key: str, value: str | int | bool) -> None:
        """Set a setting value.

        Sets the value associated with the given key, which should be in the
        format "section.option". The settings file is updated immediately.

        Args:
            key: The setting key in "section.option" format.
            value: The value to set for the setting.
        """
        section, option = key.split(".")
        self.config.set(section, option, value)
        with self.settings_file.open("w") as f:
            self.config.write(f)
