"""Some miscellaneous functions"""

__all__ = [
    "get_settings_folder",
    "create_print_title",
    "cleanup_string",
    "create_query_params",
]

import platform
from logging import getLogger
from os import environ
from pathlib import Path, PurePath
from urllib.parse import quote_plus

from xdg.BaseDirectory import save_config_path

LOGGER = getLogger(__name__)


def get_settings_folder() -> Path:
    """Method to determine where the users configs should be saved."""

    if platform.system() != "Windows":
        return Path(save_config_path("metron-tagger"))

    windows_path = PurePath(environ["APPDATA"]).joinpath("MetronTagger")
    return Path(windows_path)


def create_print_title(txt: str) -> str:
    """Create a formatted title string for printing.

    This function generates a title string that includes the provided text, formatted with newlines
    and a line of dashes beneath it for visual separation. It is useful for enhancing the readability
    of printed output by clearly delineating sections.

    Args:
        txt (str): The text to be used as the title.

    Returns:
        str: The formatted title string, including newlines and dashes.
    """
    return f"\n{txt}\n{txt.replace(txt, '-' * len(txt))}"


def cleanup_string(path_name: int | str | None) -> str | None:
    """Clean up and sanitize a string for use as a path name.

    This function takes an input string, converts integers to strings, and removes or replaces characters to ensure
    the string is suitable for use as a path name.


    Args:
        path_name: int | str | None: The input string to clean up.

    Returns:
        str | None: The cleaned up string or None if the input was None.
    """

    if path_name is None:
        return None

    if isinstance(path_name, int):
        path_name = str(path_name)

    path_name = path_name.replace("/", "-")
    path_name = path_name.replace(" :", " -")
    path_name = path_name.replace(": ", " - ")
    path_name = path_name.replace(":", "-")
    return path_name.replace("?", "")


def create_query_params(metadata: dict[str, str | tuple[str, ...]]) -> dict[str, str] | None:
    """Create query parameters for searching based on metadata.

    This function prepares query parameters for searching based on the series name and issue number extracted from
    the metadata dictionary.

    Args:
        metadata: dict[str, str | tuple[str, ...]: A dictionary containing metadata information.

    Returns:
        dict[str, str]: The query parameters for searching.
    """
    # Remove hyphen when searching for series name
    try:
        series_string: str = (
            metadata["series"].replace(" - ", " ").replace(",", "").replace(" & ", " ").strip()
        )
    except KeyError:
        LOGGER.error("Bad filename parsing: %s", metadata)  # NOQA: TRY400
        return None

    # If there isn't an issue number, let's assume it's "1".
    number: str = quote_plus(metadata["issue"].encode("utf-8")) if "issue" in metadata else "1"

    # Strip any leading zeros from the issue number for the API to correctly match.
    number = number.lstrip("0")

    # Handle issues with #½
    if number == ".5":
        number = "½"

    return {
        "series_name": series_string,
        "number": number,
    }
