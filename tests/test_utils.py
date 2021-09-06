from metrontagger.utils import cleanup_string, create_query_params


def test_dict(tmp_path):
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


def test_query_dict_without_issue_number(tmp_path):
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


def test_cleanup_colon_space():
    test_str = "Hashtag: Danger (2019)"
    res = cleanup_string(test_str)
    assert res == "Hashtag - Danger (2019)"


def test_cleanup_space_colon():
    test_str = "Hashtag :Danger (2019)"
    res = cleanup_string(test_str)
    assert res == "Hashtag -Danger (2019)"


def test_cleanup_colon():
    test_str = "Hashtag:Danger (2019)"
    res = cleanup_string(test_str)
    assert res == "Hashtag-Danger (2019)"


def test_cleanup_backslash():
    test_str = "Hack/Slash (2019)"
    res = cleanup_string(test_str)
    assert res == "Hack-Slash (2019)"


def test_cleanup_questionmark():
    test_str = "What If? (2019)"
    res = cleanup_string(test_str)
    assert res == "What If (2019)"
