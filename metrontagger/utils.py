"""Some miscellaneous functions"""
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from darkseid.filename import FileNameParser


def cleanup_string(path_name: Optional[str]) -> Optional[str]:
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
    fnp = FileNameParser()
    fnp.parse_filename(filename)

    # Remove hyphen when searching for series name
    fixed_txt: str = fnp.series.replace(" - ", " ")
    series_word_list: list[str] = fixed_txt.split()
    series_string: str = " ".join(series_word_list).strip()

    # If there isn't an issue number, let's assume it's "1".
    number: str = quote_plus(fnp.issue.encode("utf-8")) if fnp.issue else "1"
    # Handle issues with #½
    if number == "0.5":
        number = "½"

    params = {
        "series_name": series_string,
        "number": number,
    }
    if fnp.volume:
        params["series_volume"] = fnp.volume
    if fnp.year:
        params["cover_year"] = fnp.year

    return params
