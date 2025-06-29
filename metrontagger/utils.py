"""Some miscellaneous functions"""

__all__ = [
    "cleanup_string",
    "create_print_title",
    "create_query_params",
    "get_settings_folder",
]

import platform
from logging import getLogger
from os import environ
from pathlib import Path, PurePath
from typing import Any
from urllib.parse import quote_plus

from xdg.BaseDirectory import save_config_path

LOGGER = getLogger(__name__)


def get_settings_folder() -> Path:
    """Method to determine where the users configs should be saved.

    Returns:
        Path: The configuration directory path for the current platform.
    """
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
        txt: The text to be used as the title.

    Returns:
        The formatted title string, including newlines and dashes.

    Raises:
        ValueError: If txt is empty or contains only whitespace.
    """
    if not txt or not txt.strip():
        msg = "Title text cannot be empty or whitespace only"
        raise ValueError(msg)

    return f"\n{txt}\n{'-' * len(txt)}"


def cleanup_string(path_name: float | str | None) -> str | None:
    """Clean up and sanitize a string for use as a path name.

    This function takes an input string, converts integers & floats to strings, and removes or replaces
    characters to ensure the string is suitable for use as a path name.

    Args:
        path_name: The input value to clean up. Can be int, float, str, or None.

    Returns:
        The cleaned up string or None if the input was None.
    """
    if path_name is None:
        return None

    if isinstance(path_name, int | float):
        path_name = str(path_name)

    return (
        path_name.replace("/", "-")
        .replace(" :", " -")
        .replace(": ", " - ")
        .replace(":", "-")
        .replace("?", "")
    )


def _clean_series_name(name: str) -> str:
    """Clean and normalize a series name for use in search queries.

    This function removes certain punctuation and keywords from the series name to improve search accuracy.

    Args:
        name: The original series name string.

    Returns:
        The cleaned series name.

    Raises:
        ValueError: If name is empty or None.
    """
    if not name:
        msg = "Series name cannot be empty or None"
        raise ValueError(msg)

    # Define replacements for better maintainability
    replacements = {
        " - ": " ",
        ",": "",
        " & ": " ",
        "HC": "",
        "TPB": "",
        "Digital Chapter": "",
    }

    cleaned = name
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)

    return cleaned.strip()


def _clean_issue_number(number: Any) -> str:
    """Format and encode an issue number for search queries.

    This function converts the issue number to a string, strips leading zeros, handles special cases,
    and URL-encodes the result.

    Args:
        number: The issue number, which may be a string, tuple, or other type.

    Returns:
        The URL-encoded issue number as a string.
    """
    if isinstance(number, tuple):
        issue_str = " ".join(str(i) for i in number)
    elif isinstance(number, str):
        issue_str = number
    else:
        issue_str = str(number)

    # Remove leading zeros but preserve "0" if that's all there is
    issue_str = issue_str.lstrip("0") or "0"

    # Handle special case for half issues
    return "½" if issue_str == ".5" else quote_plus(issue_str.encode("utf-8"))


def create_query_params(metadata: dict[str, str | tuple[str, ...]]) -> dict[str, str] | None:
    """Generate query parameters for searching based on provided metadata.

    This function creates a dictionary of query parameters using series and issue information from the metadata.
    It returns None if neither a series ID nor a series name is present.

    Args:
        metadata: A dictionary containing metadata information, such as series ID, series name, and issue number.

    Returns:
        The query parameters for searching, or None if required fields are missing.

    Raises:
        TypeError: If metadata is not a dictionary.
    """
    if not isinstance(metadata, dict):
        msg = "metadata must be a dictionary"
        raise TypeError(msg)

    params = {}

    # Handle series identification
    series_id = metadata.get("series_id")
    series = metadata.get("series")

    if series_id:
        params["series_id"] = str(series_id)
    elif series:
        series_str = series if isinstance(series, str) else str(series)
        try:
            params["series_name"] = _clean_series_name(series_str)
        except ValueError:
            LOGGER.exception("Invalid series name in metadata")
            return None
    else:
        LOGGER.error("Bad filename parsing - missing series info: %s", metadata)
        return None

    # Handle issue number
    issue = metadata.get("issue")
    params["number"] = _clean_issue_number(issue) if issue is not None else "1"
    return params
