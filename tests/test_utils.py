from pathlib import Path

import pytest
from comicfn2dict import comicfn2dict

from metrontagger.utils import cleanup_string, create_query_params


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        # Happy path: series_id present, issue present
        ({"series_id": "123", "issue": "005"}, {"series_id": "123", "number": "5"}),
        # Happy path: series_id present, issue missing
        ({"series_id": "456"}, {"series_id": "456", "number": "1"}),
        # Happy path: series name with hyphens, commas, ampersands, and keywords
        (
            {
                "series": "Batman - Detective Comics, Vol. 1 & 2 HC TPB Digital Chapter",
                "issue": "001",
            },
            {"series_name": "Batman Detective Comics Vol. 1 2", "number": "1"},
        ),
        # Happy path: issue number is ".5" (should become "½")
        ({"series_id": "789", "issue": ".5"}, {"series_id": "789", "number": "½"}),
        # Happy path: issue number with leading zeros and special characters
        ({"series_id": "101", "issue": "0007"}, {"series_id": "101", "number": "7"}),
        # Happy path: issue number with unicode, should be quoted
        ({"series_id": "202", "issue": "é"}, {"series_id": "202", "number": "%C3%A9"}),
        # Edge case: series name only, no issue
        ({"series": "X-Men"}, {"series_name": "X-Men", "number": "1"}),
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


def test_heavy_metal() -> None:
    # Heavy Metal is a special case where the metadata doesn't have a series name.
    fn = Path("Heavy Metal #319 (2022).cbz")
    md = comicfn2dict(fn)
    result = create_query_params(md)
    assert result is None


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
