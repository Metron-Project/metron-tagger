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


def cleanup_string(path_name: float | str | None) -> str | None:
    """Clean up and sanitize a string for use as a path name.

    This function takes an input string, converts integers & floats to strings, and removes or replaces characters to
    ensure the string is suitable for use as a path name.


    Args:
        path_name: int | str | None: The input string to clean up.

    Returns:
        str | None: The cleaned up string or None if the input was None.
    """

    if path_name is None:
        return None

    if isinstance(path_name, int | float):
        path_name = str(path_name)

    path_name = path_name.replace("/", "-")
    path_name = path_name.replace(" :", " -")
    path_name = path_name.replace(": ", " - ")
    path_name = path_name.replace(":", "-")
    return path_name.replace("?", "")


def _clean_series_name(name: str) -> str:
    """Clean and normalize a series name for use in search queries.

    This function removes certain punctuation and keywords from the series name to improve search accuracy.

    Args:
        name: The original series name string.

    Returns:
        str: The cleaned series name.
    """
    return (
        name.replace(" - ", " ")
        .replace(",", "")
        .replace(" & ", " ")
        .replace("HC", "")
        .replace("TPB", "")
        .replace("Digital Chapter", "")
        .strip()
    )


def _clean_issue_number(number: any) -> str:
    """Format and encode an issue number for search queries.

    This function converts the issue number to a string, strips leading zeros, handles special cases, and URL-encodes
    the result.

    Args:
        number: The issue number, which may be a string, tuple, or other type.

    Returns:
        str: The URL-encoded issue number as a string.
    """
    issue_str = (
        " ".join(str(i) for i in number)
        if isinstance(number, tuple)
        else number
        if isinstance(number, str)
        else str(number)
    )
    issue_str = issue_str.lstrip("0") or "0"
    return "½" if issue_str == ".5" else quote_plus(issue_str.encode("utf-8"))


def create_query_params(metadata: dict[str, str | tuple[str, ...]]) -> dict[str, str] | None:
    """Generate query parameters for searching based on provided metadata.

    This function creates a dictionary of query parameters using series and issue information from the metadata. It
    returns None if neither a series ID nor a series name is present.

    Args:
        metadata: A dictionary containing metadata information, such as series ID, series name, and issue number.

    Returns:
        dict[str, str] | None: The query parameters for searching, or None if required fields are missing.
    """
    params = {}

    if series_id := metadata.get("series_id"):
        params["series_id"] = str(series_id)
    elif series := metadata.get("series"):
        params["series_name"] = _clean_series_name(
            series if isinstance(series, str) else str(series)
        )
    else:
        LOGGER.error("Bad filename parsing: %s", metadata)
        return None

    # Handle issue number
    if issue := metadata.get("issue"):
        params["number"] = _clean_issue_number(issue)
    else:
        params["number"] = "1"

    return params
