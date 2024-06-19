"""Some miscellaneous functions"""

from urllib.parse import quote_plus


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


def create_query_params(metadata: dict[str, str | tuple[str, ...]]) -> dict[str, str]:
    """Create query parameters for searching based on metadata.

    This function prepares query parameters for searching based on the series name and issue number extracted from
    the metadata dictionary.

    Args:
        metadata: dict[str, str | tuple[str, ...]: A dictionary containing metadata information.

    Returns:
        dict[str, str]: The query parameters for searching.
    """

    # TODO: Should probably check if there is a 'series' key.
    # Remove hyphen when searching for series name
    series_string: str = (
        metadata["series"].replace(" - ", " ").replace(",", "").replace(" & ", " ").strip()
    )

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
