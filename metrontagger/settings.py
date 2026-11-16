"""Class to handle project settings"""

__all__ = ["MetronTaggerSettings"]

import configparser
from logging import getLogger
from pathlib import Path
from typing import ClassVar

from metrontagger.utils import get_settings_folder

LOGGER = getLogger(__name__)

# Constant
KEY_PARTS = 2


class MetronTaggerSettings:
    """Manages Metron Tagger settings.

    Handles loading and saving user settings, including credentials, file paths,
    and various application options with type safety and error handling.
    """

    # Default configuration values
    DEFAULT_CONFIG: ClassVar[dict[str, dict[str, str] | dict[str, int | bool | str]]] = {
        "metron": {
            "user": "",
            "auth_token": "",
            "redis_url": "",
        },
        "rename": {
            "rename_issue_number_padding": 3,
            "rename_use_smart_string_cleanup": True,
            "rename_template": "",
        },
        "sort": {"directory": ""},
    }

    # Type mapping for configuration options
    TYPE_MAPPING: ClassVar[
        dict[str, dict[str, type[str]] | dict[str, type[int | bool | str]]]
    ] = {
        "metron": {
            "user": str,
            "auth_token": str,
            "redis_url": str,
        },
        "rename": {
            "rename_issue_number_padding": int,
            "rename_use_smart_string_cleanup": bool,
            "rename_template": str,
        },
        "sort": {"directory": str},
    }

    # Options from older versions that are no longer used and are removed on load
    OBSOLETE_OPTIONS: ClassVar[dict[str, tuple[str, ...]]] = {
        "metron": ("password", "token_migration_prompted"),
    }

    def __init__(self, config_dir: str | Path | None = None) -> None:
        """Initialize MetronTaggerSettings.

        Args:
            config_dir: Custom configuration directory path. If None, uses default.

        Raises:
            OSError: If unable to create configuration directory or file.
            configparser.Error: If configuration file is corrupted.
        """
        self.config = configparser.RawConfigParser()

        # Determine settings file location
        folder = Path(config_dir) if config_dir else get_settings_folder()
        self.settings_file = folder / "settings.ini"

        try:
            self._initialize_config()
        except Exception:
            LOGGER.exception("Failed to initialize configuration")
            raise

    def _initialize_config(self) -> None:
        """Initialize configuration file and default sections."""
        # Read existing configuration
        if self.settings_file.exists():
            try:
                self.config.read(self.settings_file)
                LOGGER.debug("Loaded existing configuration from %s", self.settings_file)
            except configparser.Error as e:
                LOGGER.warning("Configuration file corrupt, recreating: %s", e)
                self.config = configparser.RawConfigParser()

        # Ensure required sections exist
        self._ensure_sections()

        # Apply default values
        self._apply_defaults()

        # Create directory and file if needed
        self._ensure_file_exists()

        # Drop options no longer used, e.g. the Basic Auth password
        self._remove_obsolete_options()

    def _ensure_sections(self) -> None:
        """Ensure all required configuration sections exist."""
        required_sections = list(self.DEFAULT_CONFIG.keys())

        for section in required_sections:
            if not self.config.has_section(section):
                self.config.add_section(section)
                LOGGER.debug("Added missing section: %s", section)

    def _apply_defaults(self) -> None:
        """Apply default values for missing configuration options."""
        for section_name, section_defaults in self.DEFAULT_CONFIG.items():
            for option, default_value in section_defaults.items():
                if not self.config.has_option(section_name, option):
                    # Convert value to string for configparser
                    str_value = (
                        str(default_value).lower()
                        if isinstance(default_value, bool)
                        else str(default_value)
                    )
                    self.config.set(section_name, option, str_value)
                    LOGGER.debug(
                        "Set default value for %s.%s: %s", section_name, option, default_value
                    )

    def _remove_obsolete_options(self) -> None:
        """Remove options no longer used by Metron-Tagger and save if any were found."""
        removed = False
        for section_name, options in self.OBSOLETE_OPTIONS.items():
            for option in options:
                if self.config.remove_option(section_name, option):
                    LOGGER.info("Removed obsolete setting: %s.%s", section_name, option)
                    removed = True
        if removed:
            self._save_config()

    def _ensure_file_exists(self) -> None:
        """Create configuration directory and file if they don't exist."""
        try:
            # Create parent directory if needed
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)

            # Create configuration file if it doesn't exist
            if not self.settings_file.exists():
                self._save_config()
                LOGGER.info("Created new configuration file: %s", self.settings_file)

        except OSError:
            LOGGER.exception("Failed to create configuration file")
            raise

    def _save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with self.settings_file.open("w", encoding="utf-8") as f:
                self.config.write(f)
        except OSError:
            LOGGER.exception("Failed to save configuration")
            raise

    @staticmethod
    def _parse_key(key: str) -> tuple[str, str]:
        """Parse a configuration key into section and option.

        Args:
            key: Configuration key in "section.option" format.

        Returns:
            Tuple of (section, option).

        Raises:
            ValueError: If key format is invalid.
        """
        parts = key.split(".", 1)
        if len(parts) != KEY_PARTS:
            msg = f"Invalid key format '{key}'. Expected 'section.option'"
            raise ValueError(msg)
        return parts[0], parts[1]

    def _convert_value(self, section: str, option: str, value: str) -> str | int | bool:
        """Convert string value to appropriate type based on configuration schema.

        Args:
            section: Configuration section name.
            option: Configuration option name.
            value: String value from configuration file.

        Returns:
            Converted value with appropriate type.
        """
        if section in self.TYPE_MAPPING and option in self.TYPE_MAPPING[section]:
            expected_type = self.TYPE_MAPPING[section][option]

            if expected_type is bool:
                return self.config.getboolean(section, option)
            if expected_type is int:
                return self.config.getint(section, option)

        return value

    def __getitem__(self, key: str) -> str | int | bool | None:
        """Retrieve a setting value with type conversion.

        Args:
            key: The setting key in "section.option" format.

        Returns:
            The setting value with appropriate type, or None if not found.

        Raises:
            ValueError: If key format is invalid.
        """
        try:
            section, option = self._parse_key(key)
        except ValueError:
            LOGGER.exception("Invalid configuration key")
            raise

        if not self.config.has_option(section, option):
            LOGGER.debug("Configuration option not found: %s", key)
            return None

        try:
            return self._convert_value(section, option, self.config.get(section, option))
        except (ValueError, TypeError):
            LOGGER.exception("Failed to convert configuration value")
            return None

    def __setitem__(self, key: str, value: str | int | bool) -> None:
        """Set a setting value with immediate persistence.

        Args:
            key: The setting key in "section.option" format.
            value: The value to set for the setting.

        Raises:
            ValueError: If key format is invalid.
            OSError: If unable to save configuration file.
        """
        try:
            section, option = self._parse_key(key)
        except ValueError:
            LOGGER.exception("Invalid configuration key")
            raise

        # Ensure section exists
        if not self.config.has_section(section):
            self.config.add_section(section)
            LOGGER.debug("Added new section: %s", section)

        # Convert value to string for configparser
        str_value = str(value).lower() if isinstance(value, bool) else str(value)

        try:
            self.config.set(section, option, str_value)
            self._save_config()
            LOGGER.debug("Set configuration %s = %s", key, value)
        except Exception:
            LOGGER.exception("Failed to set configuration")
            raise
