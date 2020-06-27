from metrontagger.taggerlib.utils import cleanup_string, create_issue_query_dict


def test_dict(tmp_path):
    series = "Aquaman"
    number = "1"
    year = "1962"
    # Make the tmp file
    comic = tmp_path / f"{series} #{number} ({year}).cbz"

    result = create_issue_query_dict(comic)
    expected = {
        "series": f"{series}",
        "volume": "",
        "number": f"{number}",
        "year": f"{year}",
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
