"""Some miscellaneous functions"""
from urllib.parse import quote_plus


def cleanup_string(path_name: str | None) -> str | None:
    """
    Function to remove some characters that don't play nicely on Windows machines filesystem
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
    # TODO: Should probably check if there is a 'series' key.
    # Remove hyphen when searching for series name
    series_string: str = metadata["series"].replace(" - ", " ").strip()

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
