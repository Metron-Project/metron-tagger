"""Some miscellaneous functions"""

__all__ = [
    "ParsedFilename",
    "cleanup_string",
    "create_print_title",
    "create_query_params",
    "create_title_query_params",
    "get_settings_folder",
    "search_issue_number",
    "series_words",
]

import platform
import re
import unicodedata
from itertools import pairwise
from logging import getLogger
from os import environ
from pathlib import Path, PurePath
from typing import Any, TypeAlias

from darkseid.utils import remove_articles
from xdg.BaseDirectory import save_config_path

LOGGER = getLogger(__name__)

# A filename parsed by comicfn2dict: series, issue, year and so on, by name.
ParsedFilename: TypeAlias = dict[str, str | tuple[str, ...]]


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


# Dashes standing alone between words, as in "Star Wars - The Fall of Kylo Ren".
_STANDALONE_DASHES = frozenset({"-", "\u2013", "\u2014"})
# Format words dropped from a series name.
_FORMAT_WORDS = re.compile(r"\b(?:HC|TPB)\b")


def _clean_series_name(name: str) -> str:
    """Clean and normalize a series name for use in search queries.

    This function removes certain punctuation and keywords from the series name to improve search accuracy.
    Dashes standing alone between words are dropped too: Metron's series_q matches
    each word of the query separately, and Metron's name may not have the dash.

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
        ",": "",
        " & ": " ",
        "Digital Chapter": "",
    }

    cleaned = name
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    # Only as whole words, so a word like "TECHCORPS" isn't changed.
    cleaned = _FORMAT_WORDS.sub("", cleaned)

    return " ".join(w for w in cleaned.split() if w not in _STANDALONE_DASHES)


def _normalize_issue_number(number: Any) -> str:
    """Normalize an issue number so differently written forms compare equal.

    Converts the issue number to a string, strips leading zeros (keeping "0" if that's
    all there is), and writes a lone half issue as "½".

    Args:
        number: The issue number, which may be a string, tuple, or other type.

    Returns:
        The normalized issue number.
    """
    if isinstance(number, tuple):
        issue_str = " ".join(str(i) for i in number)
    elif isinstance(number, str):
        issue_str = number
    else:
        issue_str = str(number)

    issue_str = issue_str.lstrip("0") or "0"
    return "½" if issue_str == ".5" else issue_str


def search_issue_number(metadata: ParsedFilename) -> str:
    """Return the issue number to search Metron for, from a parsed filename.

    A filename without an issue number is searched as #1, since that's usually a
    one-shot or first issue. The number is sent as-is: the HTTP client URL-encodes
    query parameters itself.

    Args:
        metadata: The filename parsed by comicfn2dict.

    Returns:
        The normalized issue number, or "1".
    """
    issue = metadata.get("issue")
    return _normalize_issue_number(issue) if issue is not None else "1"


# Too common in series names to show that two names refer to the same series, on top
# of the articles and stop words darkseid's remove_articles() drops.
_SERIES_EXTRA_STOP_WORDS = frozenset({"vs"})
# A hyphen, slash, or apostrophe inside a word joins its parts, so "Spider-Man" is one
# word ("spiderman") and doesn't match "Iron Man" on "man".
_SERIES_WORD_JOINERS = re.compile(r"(?<=\w)[-/'\u2019](?=\w)")


def series_words(text: str) -> set[str]:
    """Return the distinctive words of a series name or title, for comparing names.

    Words are lowercased and stripped of accents. A hyphen, slash, or apostrophe
    inside a word joins it ("Spider-Man" is "spiderman"), other punctuation separates
    words, and very common words are dropped: darkseid's articles and stop words
    ("the", "of", "and", ...) plus "vs". Each pair of
    neighbouring words is also included joined together, so names written with a
    spaced slash on Metron ("Batman / Superman") still match filenames that write it
    as a hyphen ("Batman-Superman"): both give "batmansuperman".

    Args:
        text: A series name, title, or both.

    Returns:
        The set of distinctive words and joined word pairs.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    joined = _SERIES_WORD_JOINERS.sub("", folded)
    # remove_articles() splits on spaces, so it runs on the already separated words:
    # that way an article stuck to punctuation ("Wars:The") is still dropped.
    tokens = " ".join(re.findall(r"[^\W_]+", joined))
    words = [w for w in remove_articles(tokens).split() if w not in _SERIES_EXTRA_STOP_WORDS]
    return set(words) | {first + second for first, second in pairwise(words)}


def create_query_params(
    metadata: ParsedFilename,
) -> dict[str, str | int] | None:
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
            params["series_q"] = _clean_series_name(series_str)
        except ValueError:
            LOGGER.exception("Invalid series name in metadata")
            return None
    else:
        LOGGER.error("Bad filename parsing - missing series info: %s", metadata)
        return None

    # Handle issue number
    params["number"] = search_issue_number(metadata)
    return params


def create_title_query_params(
    metadata: ParsedFilename, params: dict[str, str | int], filename: str | PurePath
) -> dict[str, str | int] | None:
    """Build query parameters that search on the series name and title together.

    comicfn2dict splits a filename like "Star Wars - The Fall of Kylo Ren 004" into
    the series "Star Wars" and the title "The Fall of Kylo Ren", where Metron names
    the series "Star Wars: The Fall of Kylo Ren". Searching on the series alone then
    finds every Star Wars #4. Metron's series_q matches each word of the query
    separately, so the two are joined with a space.

    This only applies when the title comes before the issue number in the filename.
    A title after the number ("Batman 050 - The Wedding") is a story title, which
    would only narrow the search to the wrong series, if any.

    Args:
        metadata: The parsed filename.
        params: The create_query_params parameters for the filename.
        filename: The comic's filename.

    Returns:
        `params` with the title added to series_q, or None if there's a series ID
        (the series is already known), no title that adds anything to the search, or
        the title comes after the issue number.
    """
    title = metadata.get("title")
    if "series_q" not in params or not isinstance(title, str) or not title:
        return None
    cleaned_title = _clean_series_name(title)
    if not cleaned_title or not _title_before_issue(metadata, title, filename):
        return None
    return params | {"series_q": f"{params['series_q']} {cleaned_title}"}


def _title_before_issue(
    metadata: ParsedFilename, title: str, filename: str | PurePath
) -> bool:
    """Whether the parsed title comes before the issue number in the filename.

    That is, the issue number isn't between the series name and the title, as in
    "Batman 050 (2018) - The Wedding". The title is looked for after the series name,
    so a title that repeats it ("Batman 050 - Batman") is found in the right place,
    and the issue number only counts as a whole word, not inside a year.

    True too if the filename has no issue number, or the title can't be found in it
    as parsed: the title may then be part of the series name.
    """
    issue = metadata.get("issue")
    series = metadata.get("series")
    stem = PurePath(filename).stem
    after_series = 0
    if isinstance(series, str) and series and (series_at := stem.find(series)) >= 0:
        after_series = series_at + len(series)
    title_at = stem.find(title, after_series)
    if not isinstance(issue, str) or not issue or title_at < 0:
        return True
    between = stem[after_series:title_at]
    return re.search(rf"(?<!\w){re.escape(issue)}(?!\w)", between) is None
