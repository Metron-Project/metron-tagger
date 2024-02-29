"""Some miscellaneous functions"""
from pathlib import Path
from urllib.parse import quote_plus

from comicfn2dict import comicfn2dict


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


def create_query_params(filename: Path) -> dict[str, str]:
    """Function to create a diction of values based on the provided filename"""
    metadata: dict[str, str | tuple[str, ...]] = comicfn2dict(filename, verbose=0)

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

    params = {
        "series_name": series_string,
        "number": number,
    }
    # TODO: Probably want to remove these from the API call and use the info instead to find the issue
    #       from the return results.
    if "volume" in metadata:
        params["series_volume"] = metadata["volume"]
    if "year" in metadata:
        params["cover_year"] = metadata["year"]

    return params
