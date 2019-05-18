#!/usr/bin/env python3

from base64 import standard_b64encode
import os
import sys
import urllib.parse

from comicapi.comicarchive import ComicArchive
from comicapi.filenameparser import FileNameParser
from taggerlib.metrontalker import MetronTalker
from taggerlib.options import make_parser
from taggerlib.settings import MetronTaggerSettings


# Load the settings
SETTINGS = MetronTaggerSettings()


def select_choice_from_multiple_matches(filename, match_set):
    print(f"{filename} - Multiple results found")

    for (counter, m) in enumerate(match_set["results"]):
        counter += 1
        print(f"{counter}. {m['__str__']} ({m['cover_date']})")

    while True:
        i = input("Choose a match #, or 's' to skip: ")
        if (i.isdigit() and int(i) in range(1, len(match_set) + 1)) or i == 's':
            break

    if i != 's':
        i = int(i) - 1
        issue_id = match_set['results'][i]['id']
    else:
        issue_id = None

    return issue_id


def process_file(filename, talker):

    fnp = FileNameParser()
    fnp.parseFilename(filename)

    series_word_list = fnp.series.split()
    series_string = " ".join(series_word_list).strip()
    series_string = urllib.parse.quote_plus(series_string.encode("utf-8"))

    search_results = talker.searchForIssue(series_string, fnp.issue, fnp.year)

    search_results_count = search_results["count"]

    if not search_results_count > 0:
        print(f"No issues results were found for {filename}.")
        return
    elif search_results_count > 1:
        issue_id = select_choice_from_multiple_matches(
            filename, search_results)
    elif search_results_count == 1:
        issue_id = search_results['results'][0]['id']

    if (issue_id):
        md = talker.fetchIssueDataByIssueID(issue_id)
        if md:
            ca = ComicArchive(filename)
            if ca.isWritable():
                ca.writeCIX(md)
                print(f"Wrote metadata to {filename}.")


def main():

    parser = make_parser()
    opts = parser.parse_args()

    if opts.user:
        SETTINGS.metron_user = opts.user

    if opts.password:
        SETTINGS.metron_pass = opts.password

    if opts.set_metron_user:
        SETTINGS.save()

    # Parse paths to get file list
    full_paths = [os.path.join(os.getcwd(), path) for path in opts.path]
    file_list = []

    for path in full_paths:
        if os.path.isfile(path):
            fileName, fileExt = os.path.splitext(path)
            # TODO: Use ZipFile to determine file type
            if fileExt == '.cbz':
                file_list.append(path)
        else:
            if opts.recursive:
                if os.path.isdir(path):
                    for root, dirs, files in os.walk(path):
                        for f in files:
                            fileName, fileExt = os.path.splitext(f)
                            if fileExt == '.cbz':
                                file_list.append(os.path.join(root, f))

    if not file_list:
        print('No files to process. Exiting.')
        sys.exit(0)
    else:
        auth = f'{SETTINGS.metron_user}:{SETTINGS.metron_pass}'
        base64string = standard_b64encode(auth.encode('utf-8'))

        talker = MetronTalker(base64string)
        for f in file_list:
            process_file(f, talker)


if __name__ == '__main__':
    sys.exit(main())
