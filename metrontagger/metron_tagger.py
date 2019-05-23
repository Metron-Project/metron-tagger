import os
import sys
import urllib.parse
from base64 import standard_b64encode

# Append sys.path so imports work.
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from metrontagger.comicapi.comicarchive import ComicArchive, MetaDataStyle
from metrontagger.comicapi.filenameparser import FileNameParser
from metrontagger.comicapi.utils import get_recursive_filelist, unique_file
from metrontagger.taggerlib.filerenamer import FileRenamer
from metrontagger.taggerlib.metrontalker import MetronTalker
from metrontagger.taggerlib.options import make_parser
from metrontagger.taggerlib.settings import MetronTaggerSettings

# Load the settings
SETTINGS = MetronTaggerSettings()


def select_choice_from_multiple_matches(filename, match_set):
    print(f"{os.path.basename(filename)} - Multiple results found")

    for (counter, m) in enumerate(match_set["results"]):
        counter += 1
        print(f"{counter}. {m['__str__']} ({m['cover_date']})")

    while True:
        i = input("Choose a match #, or 's' to skip: ")
        if (i.isdigit() and int(i) in range(1, len(match_set) + 1)) or i == "s":
            break

    if i != "s":
        i = int(i) - 1
        issue_id = match_set["results"][i]["id"]
    else:
        issue_id = None

    return issue_id


def get_issue_id(filename, talker):

    fnp = FileNameParser()
    fnp.parseFilename(filename)

    series_word_list = fnp.series.split()
    series_string = " ".join(series_word_list).strip()
    series_string = urllib.parse.quote_plus(series_string.encode("utf-8"))

    search_results = talker.searchForIssue(series_string, fnp.issue, fnp.year)

    search_results_count = search_results["count"]

    if not search_results_count > 0:
        print(f"no match for '{os.path.basename(filename)}'.")
        issue_id = None
    elif search_results_count > 1:
        issue_id = select_choice_from_multiple_matches(filename, search_results)
    elif search_results_count == 1:
        issue_id = search_results["results"][0]["id"]

    return issue_id


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
    file_list = []
    file_list = get_recursive_filelist(opts.path)

    if not file_list:
        print("No files to process. Exiting.")
        sys.exit(0)

    if opts.online:
        print("** Starting online search and tagging **")

        auth = f"{SETTINGS.metron_user}:{SETTINGS.metron_pass}"
        base64string = standard_b64encode(auth.encode("utf-8"))
        talker = MetronTalker(base64string)

        for f in file_list:
            ca = ComicArchive(f)
            if opts.ignore_existing:
                if ca.hasMetadata(MetaDataStyle.CIX):
                    continue

            id = get_issue_id(f, talker)
            if not id:
                continue
            md = talker.fetchIssueDataByIssueID(id)
            if md:
                if ca.isWritable():
                    ca.writeMetadata(md, MetaDataStyle.CIX)
                    print(f"match found for '{os.path.basename(f)}'.")

    if opts.rename:
        print("** Starting comic archive renaming **")
        for f in file_list:
            ca = ComicArchive(f)
            if not ca.hasCIX():
                print(f"skipping '{os.path.basename(f)}'. No metadata available.")
                continue

            md = ca.readMetadata(MetaDataStyle.CIX)
            renamer = FileRenamer(md)
            new_name = renamer.determineName(f)

            if new_name == os.path.basename(f):
                print("Filename is already good!", file=sys.stderr)
                continue

            folder = os.path.dirname(os.path.abspath(f))
            new_abs_path = unique_file(os.path.join(folder, new_name))
            os.rename(f, new_abs_path)
            print(f"renamed '{os.path.basename(f)}' -> '{new_name}'")


if __name__ == "__main__":
    sys.exit(main())
