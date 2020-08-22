"""Class to handle project settings"""
import configparser
from pathlib import Path
from typing import Optional


class MetronTaggerSettings:
    """Class to handle project settings"""

    @staticmethod
    def get_settings_folder() -> Path:
        """Method to determine where the users settings should be saved"""
        # TODO: Removed the old windows directory code. Someone that has a windows
        #       machine should probably write the code since I don't have one
        return Path.home() / ".MetronTagger"

    def __init__(self, config_dir: Optional[str] = None) -> None:
        # Metron creditials
        self.metron_user: str = ""
        self.metron_pass: str = ""
        self.sort_dir: str = ""

        self.config = configparser.ConfigParser()

        if not config_dir:
            self.folder = MetronTaggerSettings.get_settings_folder()
        else:
            self.folder = Path(config_dir)

        self.settings_file = self.folder / "settings.ini"

        if not self.settings_file.parent.exists():
            self.settings_file.parent.mkdir()

        # Write the config file if it doesn't exist
        if not self.settings_file.exists():
            self.save()
        else:
            self.load()

    def load(self) -> None:
        """Method to retrieve a users settings"""
        self.config.read(self.settings_file)

        if self.config.has_option("metron", "user"):
            self.metron_user = self.config["metron"]["user"]

        if self.config.has_option("metron", "password"):
            self.metron_pass = self.config["metron"]["password"]

        if self.config.has_option("DEFAULT", "sort_dir"):
            self.sort_dir = self.config["DEFAULT"]["sort_dir"]

    def save(self) -> None:
        """Method to save a users settings"""
        if not self.config.has_section("metron"):
            self.config.add_section("metron")

        self.config["DEFAULT"]["sort_dir"] = self.sort_dir
        self.config["metron"]["user"] = self.metron_user
        self.config["metron"]["password"] = self.metron_pass

        with self.settings_file.open("w") as configfile:
            self.config.write(configfile)
