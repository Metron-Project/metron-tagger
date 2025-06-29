"""Class to handle project settings"""

__all__ = ["MetronTaggerSettings"]

import configparser
from logging import getLogger
from pathlib import Path
from typing import Any, ClassVar

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
        "metron": {"user": "", "password": ""},
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
        "metron": {"user": str, "password": str},
        "rename": {
            "rename_issue_number_padding": int,
            "rename_use_smart_string_cleanup": bool,
            "rename_template": str,
        },
        "sort": {"directory": str},
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

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with a default fallback.

        Args:
            key: The setting key in "section.option" format.
            default: Default value to return if key is not found.

        Returns:
            The configuration value or default if not found.
        """
        try:
            value = self[key]
        except ValueError:
            return default
        else:
            return value if value is not None else default

    def has_option(self, key: str) -> bool:
        """Check if a configuration option exists.

        Args:
            key: The setting key in "section.option" format.

        Returns:
            True if the option exists, False otherwise.
        """
        try:
            section, option = self._parse_key(key)
            return self.config.has_option(section, option)
        except ValueError:
            return False

    def remove_option(self, key: str) -> bool:
        """Remove a configuration option.

        Args:
            key: The setting key in "section.option" format.

        Returns:
            True if the option was removed, False if it didn't exist.

        Raises:
            ValueError: If key format is invalid.
            OSError: If unable to save configuration file.
        """
        try:
            section, option = self._parse_key(key)
        except ValueError:
            LOGGER.exception("Invalid configuration key")
            raise

        if self.config.has_option(section, option):
            self.config.remove_option(section, option)
            self._save_config()
            LOGGER.debug("Removed configuration option: %s", key)
            return True

        return False

    def get_section(self, section_name: str) -> dict[str, Any]:
        """Get all options from a configuration section.

        Args:
            section_name: Name of the configuration section.

        Returns:
            Dictionary of option names to values.
        """
        if not self.config.has_section(section_name):
            return {}

        result = {}
        for option in self.config.options(section_name):
            key = f"{section_name}.{option}"
            result[option] = self[key]

        return result

    def reset_to_defaults(self) -> None:
        """Reset all configuration to default values.

        Raises:
            OSError: If unable to save configuration file.
        """
        # Clear existing configuration
        for section in self.config.sections():
            self.config.remove_section(section)

        # Reinitialize with defaults
        self._ensure_sections()
        self._apply_defaults()
        self._save_config()

        LOGGER.info("Configuration reset to defaults")

    @property
    def config_file_path(self) -> Path:
        """Get the path to the configuration file.

        Returns:
            Path to the configuration file.
        """
        return self.settings_file

    def is_default_value(self, key: str) -> bool:
        """Check if a configuration option is using its default value.

        Args:
            key: The setting key in "section.option" format.

        Returns:
            True if the option is using the default value, False otherwise.
        """
        try:
            section, option = self._parse_key(key)
        except ValueError:
            return False

        # Check if we have a default value for this key
        if section not in self.DEFAULT_CONFIG or option not in self.DEFAULT_CONFIG[section]:
            return False

        # Get current value and default value
        current_value = self[key]
        default_value = self.DEFAULT_CONFIG[section][option]

        return current_value == default_value

    def reset_option_to_default(self, key: str) -> bool:
        """Reset a configuration option to its default value.

        Args:
            key: The setting key in "section.option" format.

        Returns:
            True if the option was reset, False if no default exists.

        Raises:
            ValueError: If key format is invalid.
            OSError: If unable to save configuration file.
        """
        try:
            section, option = self._parse_key(key)
        except ValueError:
            LOGGER.exception("Invalid configuration key")
            raise

        # Check if there's a default value for this option
        if section in self.DEFAULT_CONFIG and option in self.DEFAULT_CONFIG[section]:
            default_value = self.DEFAULT_CONFIG[section][option]
            self[key] = default_value
            LOGGER.debug("Reset %s to default value: %s", key, default_value)
            return True

        return False

    def list_all_options(self) -> dict[str, dict[str, Any]]:
        """List all configuration options grouped by section.

        Returns:
            Dictionary of section names to their options and values.
        """
        return {
            section_name: self.get_section(section_name)
            for section_name in self.config.sections()
        }
