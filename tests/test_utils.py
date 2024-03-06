from pathlib import Path

import pytest
from comicfn2dict import comicfn2dict

from metrontagger.utils import cleanup_string, create_query_params


def test_dict(tmp_path: Path) -> None:
    series = "Aquaman"
    number = "9"
    volume = "1"
    year = "1999"
    # Make the tmp file
    comic = tmp_path / f"{series} v{volume} #{number} ({year}).cbz"
    md = comicfn2dict(comic)

    result = create_query_params(md)
    expected = {
        "series_name": f"{series}",
        "number": f"{number}",
    }
    assert result == expected


def test_dict_with_title_hyphon(tmp_path: Path) -> None:
    series = "Batman - Superman"
    number = "5"
    volume = "1"
    year = "2013"
    # Make the tmp file
    comic = tmp_path / f"{series} v{volume} #{number} ({year}).cbz"
    md = comicfn2dict(comic)

    result = create_query_params(md)
    expected = {
        "series_name": "Batman Superman",
        "number": f"{number}",
    }
    assert result == expected


def test_query_dict_without_issue_number(tmp_path: Path) -> None:
    series = "Batman"
    year = "1990"
    # Make the tmp file
    comic = tmp_path / f"{series} ({year}).cbz"
    md = comicfn2dict(comic)

    result = create_query_params(md)
    expected = {
        "series_name": f"{series}",
        "number": "1",
    }
    assert result == expected


def test_query_dict_with_issue_number(tmp_path: Path) -> None:
    fn = "Moon Knight - Black, White, & Blood #1.cbz"
    comic = tmp_path / fn
    md = comicfn2dict(comic)
    result = create_query_params(md)
    expected = {"series_name": "Moon Knight Black White Blood", "number": "1"}
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
