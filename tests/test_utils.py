from pathlib import Path

import pytest

from metrontagger.utils import cleanup_string, create_query_params


def test_dict(tmp_path: Path) -> None:
    series = "Aquaman"
    number = "9"
    volume = "1"
    year = "1999"
    # Make the tmp file
    comic = tmp_path / f"{series} v{volume} #{number} ({year}).cbz"

    result = create_query_params(comic)
    expected = {
        "series_name": f"{series}",
        "series_volume": f"{volume}",
        "number": f"{number}",
        "cover_year": f"{year}",
    }
    assert result == expected


def test_query_dict_without_issue_number(tmp_path: Path) -> None:
    series = "Batman"
    year = "1990"
    volume = "2"
    # Make the tmp file
    comic = tmp_path / f"{series} v{volume} ({year}).cbz"

    result = create_query_params(comic)
    expected = {
        "series_name": f"{series}",
        "series_volume": f"{volume}",
        "number": "1",
        "cover_year": f"{year}",
    }
    assert result == expected


test_strings = [
    pytest.param("Hashtag: Danger (2019)", "Cleanup colon space", "Hashtag - Danger (2019)"),
    pytest.param("Hashtag :Danger (2019)", "Cleanup space colon", "Hashtag -Danger (2019)"),
    pytest.param("Hashtag:Danger (2019)", "Cleanup colon", "Hashtag-Danger (2019)"),
    pytest.param("Hack/Slash (2019)", "Cleanup backslash", "Hack-Slash (2019)"),
    pytest.param("What If? (2019)", "Cleanup question mark", "What If (2019)"),
]


@pytest.mark.parametrize("string,reason,expected", test_strings)
def test_string_cleanup(string: str, reason: str, expected: str) -> None:
    assert cleanup_string(string) == expected
