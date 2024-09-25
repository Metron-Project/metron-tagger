"""Class to handle project settings"""

from __future__ import annotations

import configparser
import platform
from os import environ
from pathlib import Path, PurePath

import questionary
from xdg.BaseDirectory import save_config_path

from metrontagger.styles import Styles


class MetronTaggerSettings:
    """Class for managing Metron Tagger settings.

    This class handles the loading and saving of user settings for Metron Tagger, including Metron credentials,
    file paths, sorting options, renaming settings, and more.

    Args:
        config_dir: str | None: The directory path for the configuration files.

    Returns:
        None
    """

    def __init__(self: MetronTaggerSettings, config_dir: str | None = None) -> None:
        """Initialize MetronTaggerSettings with default values or load from configuration file.

        This method sets up the MetronTaggerSettings object with default values or loads settings from a
        configuration file.
        """
        self.config = configparser.RawConfigParser()

        # Metron credentials
        self.metron_user: str = ""
        self.metron_pass: str = ""
        self.path: str = ""
        self.sort_dir: str = ""
        self.id: bool = False
        self.online: bool = False
        self.missing: bool = False
        self.delete: bool = False
        self.rename: bool = False
        self.sort: bool = False
        self.interactive: bool = False
        self.ignore_existing: bool = False
        self.export_to_cbz: bool = False
        self.delete_original: bool = False
        self.validate: bool = False
        self.remove_non_valid: bool = False
        self.duplicates: bool = False

        # Rename settings
        self.rename_template = "%series% v%volume% #%issue% (%year%)"
        self.rename_issue_number_padding = 3
        self.rename_use_smart_string_cleanup: bool = True

        # Metadata format: setting the defaults to True for new users.
        self.use_metron_info: bool = True
        self.use_comic_info: bool = True

        folder = Path(config_dir) if config_dir else MetronTaggerSettings.get_settings_folder()
        self.settings_file = folder / "settings.ini"

        if not self.settings_file.parent.exists():
            self.settings_file.parent.mkdir()

        # Write the config file if it doesn't exist
        if not self.settings_file.exists():
            self.save()
        else:
            self.load()

    def _ask_user_default_metadata(self: MetronTaggerSettings) -> None:
        msg = (
            "Multiple metadata formats support has been added, we need you to set the default format(s) "
            "you wish to use. If you wish to change this in the future, you'll need to modify your settings.ini."
        )
        questionary.print(msg, style=Styles.TITLE)
        answers = questionary.form(
            ci=questionary.confirm(
                "Do you wish to write `ComicInfo.xml` metadata to your comics?"
            ),
            mi=questionary.confirm(
                "Do you wish to write `MetronInfo.xml` metadata to your comics?"
            ),
        ).ask()
        self.use_comic_info = answers["ci"]
        self.use_metron_info = answers["mi"]
        self.save()

    @staticmethod
    def get_settings_folder() -> Path:
        """Get the folder path for saving user settings.

        This static method determines the appropriate folder path for saving user settings based on the operating
        system.

        Returns:
            Path: The folder path for saving user settings.
        """

        if platform.system() != "Windows":
            return Path(save_config_path("metron-tagger"))

        windows_path = PurePath(environ["APPDATA"]).joinpath("MetronTagger")
        return Path(windows_path)

    def load(self: MetronTaggerSettings) -> None:
        """Load user settings from the configuration file.

        This method reads and loads user settings from the specified configuration file, updating the settings
        attributes accordingly.
        """

        self.config.read(self.settings_file)

        if self.config.has_option("metron", "user"):
            self.metron_user = self.config["metron"]["user"]

        if self.config.has_option("metron", "password"):
            self.metron_pass = self.config["metron"]["password"]

        if self.config.has_option("DEFAULT", "sort_dir"):
            self.sort_dir = self.config["DEFAULT"]["sort_dir"]

        if self.config.has_option("rename", "rename_template"):
            self.rename_template = self.config.get("rename", "rename_template")

        if self.config.has_option("rename", "rename_issue_number_padding"):
            self.rename_issue_number_padding = self.config.getint(
                "rename",
                "rename_issue_number_padding",
            )

        if self.config.has_option("rename", "rename_use_smart_string_cleanup"):
            self.rename_use_smart_string_cleanup = self.config.getboolean(
                "rename",
                "rename_use_smart_string_cleanup",
            )

        if not self.config.has_section("metadata"):
            # Ask user what metadata format to use for defaults.
            self._ask_user_default_metadata()

        if self.config.has_option("metadata", "use_metron_info"):
            self.use_metron_info = self.config.getboolean("metadata", "use_metron_info")

        if self.config.has_option("metadata", "use_comic_info"):
            self.use_comic_info = self.config.getboolean("metadata", "use_comic_info")

    def save(self: MetronTaggerSettings) -> None:
        """Save user settings to the configuration file.

        This method updates the configuration file with the current user settings, including Metron credentials,
        sorting directory, and renaming settings.
        """

        if not self.config.has_section("metron"):
            self.config.add_section("metron")

        self.config["DEFAULT"]["sort_dir"] = self.sort_dir
        self.config["metron"]["user"] = self.metron_user
        self.config["metron"]["password"] = self.metron_pass

        if not self.config.has_section("rename"):
            self.config.add_section("rename")

        self.config.set("rename", "rename_template", self.rename_template)
        self.config.set(
            "rename",
            "rename_issue_number_padding",
            str(self.rename_issue_number_padding),
        )
        self.config.set(
            "rename",
            "rename_use_smart_string_cleanup",
            str(self.rename_use_smart_string_cleanup),
        )

        if not self.config.has_section("metadata"):
            self.config.add_section("metadata")

        self.config.set("metadata", "use_metron_info", str(self.use_metron_info))
        self.config.set("metadata", "use_comic_info", str(self.use_comic_info))

        with self.settings_file.open("w") as configfile:
            self.config.write(configfile)
