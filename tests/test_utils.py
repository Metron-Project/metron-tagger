import pytest
from comicfn2dict import comicfn2dict

from metrontagger.utils import (
    _clean_series_name,
    _normalize_issue_number,
    cleanup_string,
    create_query_params,
    create_title_query_params,
    search_issue_number,
    series_words,
)


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        # Happy path: series_id present, issue present
        ({"series_id": "123", "issue": "005"}, {"series_id": "123", "number": "5"}),
        # Happy path: series_id present, issue missing
        ({"series_id": "456"}, {"series_id": "456", "number": "1"}),
        # Happy path: series name with commas, ampersands, and keywords
        (
            {
                "series": "Batman Detective Comics, Vol. 1 & 2 HC TPB Digital Chapter",
                "issue": "001",
            },
            {"series_q": "Batman Detective Comics Vol. 1 2", "number": "1"},
        ),
        # Happy path: issue number is ".5" (should become "½")
        ({"series_id": "789", "issue": ".5"}, {"series_id": "789", "number": "½"}),
        # Happy path: issue number with leading zeros and special characters
        ({"series_id": "101", "issue": "0007"}, {"series_id": "101", "number": "7"}),
        # Happy path: issue number with unicode, sent as-is (the HTTP client encodes it)
        ({"series_id": "202", "issue": "é"}, {"series_id": "202", "number": "é"}),
        # Happy path: issue number with a space or slash isn't URL-encoded twice
        (
            {"series_id": "203", "issue": "101 / 102"},
            {"series_id": "203", "number": "101 / 102"},
        ),
        # Happy path: dashes standing alone are dropped, hyphenated words kept
        (
            {"series": "Star Wars - Darth Vader \u2013 X-Men", "issue": "1"},
            {"series_q": "Star Wars Darth Vader X-Men", "number": "1"},
        ),
        # Edge case: series name only, no issue
        ({"series": "X-Men"}, {"series_q": "X-Men", "number": "1"}),
        # Edge case: issue is "0" (should become "0")
        ({"series_id": "303", "issue": "0"}, {"series_id": "303", "number": "0"}),
        # Edge case: issue is "000" (should become "0")
        ({"series_id": "404", "issue": "000"}, {"series_id": "404", "number": "0"}),
        # Edge case: issue is "05" (should become "5")
        ({"series_id": "505", "issue": "05"}, {"series_id": "505", "number": "5"}),
        # Error case: missing both series_id and series
        (
            {"issue": "1"},
            None,
        ),
        # Error case: completely empty metadata
        ({}, None),
    ],
    ids=[
        "series_id_and_issue_present",
        "series_id_present_issue_missing",
        "series_name_cleanup",
        "half_issue_number",
        "issue_leading_zeros",
        "unicode_issue_number",
        "issue_number_with_space_and_slash",
        "standalone_dashes_dropped",
        "series_name_only",
        "issue_zero",
        "issue_all_zeros",
        "issue_single_leading_zero",
        "missing_series_id_and_series",
        "empty_metadata",
    ],
)
def test_create_query_params(metadata, expected, mocker):
    # Arrange
    if expected is None:
        # Patch LOGGER to avoid errors on logging
        mocker.patch("metrontagger.utils.LOGGER")

    # Act
    result = create_query_params(metadata)

    # Assert
    assert result == expected


test_strings = [
    pytest.param("Hashtag: Danger (2019)", "Cleanup colon space", "Hashtag - Danger (2019)"),
    pytest.param("Hashtag :Danger (2019)", "Cleanup space colon", "Hashtag -Danger (2019)"),
    pytest.param("Hashtag:Danger (2019)", "Cleanup colon", "Hashtag-Danger (2019)"),
    pytest.param("Hack/Slash (2019)", "Cleanup backslash", "Hack-Slash (2019)"),
    pytest.param("What If? (2019)", "Cleanup question mark", "What If (2019)"),
]


@pytest.mark.parametrize(("string", "reason", "expected"), test_strings)
def test_string_cleanup(string: str, reason: str, expected: str) -> None:  # noqa: ARG001
    assert cleanup_string(string) == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("simple_string", "simple_string"),  # ID: happy_path_simple
        ("string with spaces", "string with spaces"),  # ID: happy_path_spaces
        ("string/with/slashes", "string-with-slashes"),  # ID: happy_path_slashes
        ("string:with:colons", "string-with-colons"),  # ID: happy_path_colons
        ("string :", "string -"),  # ID: happy_path_colon_space_start
        ("string?", "string"),  # ID: happy_path_question_mark
        (123, "123"),  # ID: happy_path_integer
        (123.45, "123.45"),  # ID: happy_path_float
    ],
)
def test_cleanup_string_happy_path(test_input, expected):
    # Act
    result = cleanup_string(test_input)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("", ""),  # ID: edge_case_empty
        (None, None),  # ID: edge_case_none
        ("   ", "   "),  # ID: edge_case_whitespace
        ("string\nwith\nnewlines", "string\nwith\nnewlines"),  # ID: edge_case_newlines
        ("string\twith\ttabs", "string\twith\ttabs"),  # ID: edge_case_tabs
    ],
)
def test_cleanup_string_edge_cases(test_input, expected):
    # Act
    result = cleanup_string(test_input)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("007", "7"),
        ("000", "0"),
        (".5", "½"),
        ("16.NOW", "16.NOW"),
        (("1", "A"), "1 A"),
        (12, "12"),
    ],
)
def test_normalize_issue_number(number, expected):
    """Leading zeros are stripped, and a lone half issue becomes "½"."""
    assert _normalize_issue_number(number) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The Amazing Spider-Man", {"amazing", "spiderman", "amazingspiderman"}),
        ("Batman / Superman", {"batman", "superman", "batmansuperman"}),
        ("World\u2019s Finest", {"worlds", "finest", "worldsfinest"}),
        ("Pokémon", {"pokemon"}),
        ("X-Men_Annual", {"xmen", "annual", "xmenannual"}),
        ("The", set()),
    ],
)
def test_series_words(text, expected):
    """Words are folded, joined within a word, paired, and common words dropped."""
    assert series_words(text) == expected


@pytest.mark.parametrize(
    ("filename_name", "metron_name", "agrees"),
    [
        # Metron spaces the slash; filenames often turn it into a hyphen.
        ("Batman-Superman", "Batman / Superman", True),
        ("Batman-Superman - World's Finest", "Batman / Superman: World's Finest", True),
        ("Spider Man", "The Amazing Spider-Man", True),
        ("Iron Man", "The Amazing Spider-Man", False),
        ("X-Factor", "X-Men", False),
    ],
)
def test_series_words_agreement(filename_name, metron_name, agrees):
    """Filename and Metron names agree when they share a word or joined pair."""
    assert bool(series_words(filename_name) & series_words(metron_name)) is agrees


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # darkseid's remove_articles() list, including words beyond "the"/"of".
        ("Who Is Jake Ellis?", {"who", "jake", "ellis", "whojake", "jakeellis"}),
        (
            "Star Wars:The Clone Wars",
            {"star", "wars", "clone", "starwars", "warsclone", "clonewars"},
        ),
        ("It", set()),
        # "vs" isn't in darkseid's list but is dropped too.
        ("Alien vs. Predator", {"alien", "predator", "alienpredator"}),
    ],
)
def test_series_words_stop_words(text, expected):
    """Articles and stop words are dropped, even when stuck to punctuation."""
    assert series_words(text) == expected


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [({"issue": "007"}, "7"), ({"issue": ".5"}, "½"), ({}, "1")],
)
def test_search_issue_number(metadata, expected):
    """The searched number is normalized, or "1" when the filename has none."""
    assert search_issue_number(metadata) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        pytest.param(
            "Star Wars - The Fall of Kylo Ren 004 (2026) (Digital).cbz",
            {"series_q": "Star Wars The Fall of Kylo Ren", "number": "4"},
            id="series-and-title",
        ),
        pytest.param(
            "Star Wars - Boba Fett \u2013 Black, White & Red 001.cbz",
            {"series_q": "Star Wars Boba Fett Black White Red", "number": "1"},
            id="title-cleaned-like-series",
        ),
        pytest.param(
            "Spider-Man - Blue 001.cbz",
            {"series_q": "Spider-Man Blue", "number": "1"},
            id="hyphenated-word-kept",
        ),
        pytest.param(
            "Star Wars - The Fall of Kylo Ren (2026).cbz",
            {"series_q": "Star Wars The Fall of Kylo Ren", "number": "1"},
            id="no-issue-number",
        ),
        pytest.param("Batman v3 050 - The Wedding.cbz", None, id="story-title"),
        pytest.param("Amazing Spider-Man 001 (2018) - Venom.cbz", None, id="title-after-year"),
        pytest.param("Batman 050 (2018) - Batman.cbz", None, id="title-repeats-series"),
        pytest.param("Batman #001 - Superman.cbz", None, id="hash-issue-number"),
        pytest.param(
            "Star Wars (2001) - Tales 001.cbz",
            {"series_q": "Star Wars Tales", "number": "1"},
            id="issue-digits-in-year",
        ),
        pytest.param("Star Wars 004.cbz", None, id="no-title"),
    ],
)
def test_create_title_query_params(filename, expected):
    """The title is added to the search only when it comes before the issue number."""
    metadata = comicfn2dict(filename, verbose=0)
    params = create_query_params(metadata)
    assert params is not None
    assert create_title_query_params(metadata, params, filename) == expected


@pytest.mark.parametrize(
    ("metadata", "params"),
    [
        pytest.param(
            {"series": "Star Wars", "title": "  ", "issue": "4"},
            {"series_q": "Star Wars", "number": "4"},
            id="blank-title",
        ),
        pytest.param(
            {"series": "Star Wars", "title": "TPB", "issue": "4"},
            {"series_q": "Star Wars", "number": "4"},
            id="title-cleans-away",
        ),
        pytest.param(
            {"series": "Star Wars", "title": " - ", "issue": "4"},
            {"series_q": "Star Wars", "number": "4"},
            id="title-only-dash",
        ),
        pytest.param(
            {"series_id": "16447", "series": "Star Wars", "title": "The Fall of Kylo Ren"},
            {"series_id": "16447", "number": "4"},
            id="series-id",
        ),
        pytest.param(
            {"series": "Star Wars", "title": "The Fall Of Kylo Ren", "issue": "004"},
            {"series_q": "Star Wars", "number": "4"},
            id="title-not-in-filename",
        ),
    ],
)
def test_create_title_query_params_nothing_to_add(metadata, params):
    """No title search without a title to add, with the series known, or with a title
    that can't be found in the filename."""
    filename = "Star Wars - The Fall of Kylo Ren 004.cbz"
    assert create_title_query_params(metadata, params, filename) is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("Batman HC", "Batman", id="hc-word"),
        pytest.param("Batman TPB", "Batman", id="tpb-word"),
        pytest.param("TECHCORPS", "TECHCORPS", id="inside-word-kept"),
        pytest.param("TPBS Tales", "TPBS Tales", id="word-start-kept"),
        pytest.param("X-HC", "X-HC", id="hyphenated-end-kept"),
        pytest.param("TPB-Force", "TPB-Force", id="hyphenated-start-kept"),
    ],
)
def test_clean_series_name_format_words(name, expected):
    """HC and TPB are dropped only as whole words."""
    assert _clean_series_name(name) == expected


@pytest.mark.parametrize(
    "series",
    [pytest.param("TPB", id="format-word"), pytest.param(" - ", id="dash")],
)
def test_create_query_params_empty_series_after_cleanup(series, mocker):
    """A series name with nothing left after cleanup is a bad parse, not a search."""
    mocker.patch("metrontagger.utils.LOGGER")
    assert create_query_params({"series": series, "issue": "1"}) is None
