"""Some miscellaneous functions"""
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from darkseid.filenameparser import FileNameParser


def cleanup_string(path_name: Optional[str]) -> Optional[str]:
    """Function to remove some characters that don't play nicely on Windows machines filesystem"""
    if path_name is None:
        return None

    path_name = path_name.replace("/", "-")
    path_name = path_name.replace(" :", " -")
    path_name = path_name.replace(": ", " - ")
    path_name = path_name.replace(":", "-")
    path_name = path_name.replace("?", "")
    return path_name


def create_query_params(filename: Path) -> Dict[str, str]:
    """Function to create a diction of values based on the provided filename"""
    fnp = FileNameParser()
    fnp.parse_filename(filename)

    # Substitute colon for hyphen when searching for series name
    fixed_txt: str = fnp.series.replace(" - ", ": ")
    series_word_list: List[str] = fixed_txt.split()
    series_string: str = " ".join(series_word_list).strip()

    # If there isn't an issue number, let's assume it's "1".
    number: str = quote_plus(fnp.issue.encode("utf-8")) if fnp.issue else "1"

    params = {
        "series_name": series_string,
        "number": number,
    }
    if fnp.volume:
        params["series_volume"] = fnp.volume
    if fnp.year:
        params["cover_year"] = fnp.year

    return params
