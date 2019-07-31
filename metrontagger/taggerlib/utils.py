import urllib.parse

from metrontagger.comicapi.filenameparser import FileNameParser


def cleanup_string(path_name):
    path_name = path_name.replace("/", "-")
    path_name = path_name.replace(" :", " -")
    path_name = path_name.replace(": ", " - ")
    path_name = path_name.replace(":", "-")
    path_name = path_name.replace("?", "")

    return path_name


def create_issue_query_dict(filename):
    fnp = FileNameParser()
    fnp.parseFilename(filename)

    # Substitute colon for hyphen when searching for series name
    fixed_txt = fnp.series.replace(" - ", ": ")
    series_word_list = fixed_txt.split()
    series_string = " ".join(series_word_list).strip()
    series_string = urllib.parse.quote_plus(series_string.encode("utf-8"))
    number = urllib.parse.quote_plus(fnp.issue.encode("utf-8"))
    query_dict = {
        "series": series_string,
        "volume": fnp.volume,
        "number": number,
        "year": fnp.year,
    }

    return query_dict
