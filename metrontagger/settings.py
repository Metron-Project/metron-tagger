"""Class to handle project settings"""

import configparser
import platform
from os import environ
from pathlib import Path, PurePath

from xdg.BaseDirectory import save_config_path


class MetronTaggerSettings:
    """Class to handle project settings"""

    def __init__(self: "MetronTaggerSettings", config_dir: str | None = None) -> None:
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
        self.duplicates: bool = False

        # Rename settings
        self.rename_template = "%series% v%volume% #%issue% (%year%)"
        self.rename_issue_number_padding = 3
        self.rename_use_smart_string_cleanup = True

        self.config = configparser.RawConfigParser()

        folder = Path(config_dir) if config_dir else MetronTaggerSettings.get_settings_folder()
        self.settings_file = folder / "settings.ini"

        if not self.settings_file.parent.exists():
            self.settings_file.parent.mkdir()

        # Write the config file if it doesn't exist
        if not self.settings_file.exists():
            self.save()
        else:
            self.load()

    @staticmethod
    def get_settings_folder() -> Path:
        """Method to determine where the users settings should be saved"""
        if platform.system() != "Windows":
            return Path(save_config_path("metron-tagger"))

        windows_path = PurePath(environ["APPDATA"]).joinpath("MetronTagger")
        return Path(windows_path)

    def load(self: "MetronTaggerSettings") -> None:
        """Method to retrieve a users settings"""
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

    def save(self: "MetronTaggerSettings") -> None:
        """Method to save a users settings"""
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

        with self.settings_file.open("w") as configfile:
            self.config.write(configfile)
