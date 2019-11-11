"""Class to handle project settings"""
import configparser
import os
import platform


class MetronTaggerSettings:
    """Class to handle project settings"""
    @staticmethod
    def get_settings_folder():
        """Method to determine where the users settings should be saved"""
        if platform.system() == "Windows":
            folder = os.path.join(os.environ["APPDATA"], "MetronTagger")
        else:
            folder = os.path.join(os.path.expanduser("~"), ".MetronTagger")
        if folder is not None:
            folder = folder
        return folder

    def set_default_values(self):
        """Method to set default values as empty"""
        # Metron creditials
        self.metron_user = ""
        self.metron_pass = ""
        self.sort_dir = ""

    def __init__(self, config_dir=None):
        self.settings_file = ""
        self.folder = ""
        self.set_default_values()

        self.config = configparser.ConfigParser()
        self.folder = config_dir or MetronTaggerSettings.get_settings_folder()

        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

        self.settings_file = os.path.join(self.folder, "settings.ini")

        # Write the config file if it doesn't exist
        if not os.path.exists(self.settings_file):
            self.save()
        else:
            self.load()

    def load(self):
        """Method to retrieve a users settings"""
        self.config.read(self.settings_file)

        if self.config.has_option("metron", "user"):
            self.metron_user = self.config["metron"]["user"]

        if self.config.has_option("metron", "password"):
            self.metron_pass = self.config["metron"]["password"]

        if self.config.has_option("DEFAULT", "sort_dir"):
            self.sort_dir = self.config["DEFAULT"]["sort_dir"]

    def save(self):
        """Method to save a users settings"""
        if not self.config.has_section("metron"):
            self.config.add_section("metron")

        self.config["DEFAULT"]["sort_dir"] = self.sort_dir
        self.config["metron"]["user"] = self.metron_user
        self.config["metron"]["password"] = self.metron_pass

        with open(self.settings_file, "w") as configfile:
            self.config.write(configfile)
