import os
import sys
import urllib.parse
from base64 import standard_b64encode
from shutil import Error, move

# Append sys.path so imports work.
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from metrontagger.comicapi.comicarchive import ComicArchive, MetaDataStyle
from metrontagger.comicapi.filenameparser import FileNameParser
from metrontagger.comicapi.genericmetadata import GenericMetadata
from metrontagger.comicapi.utils import get_recursive_filelist, unique_file
from metrontagger.taggerlib.filerenamer import FileRenamer
from metrontagger.taggerlib.metrontalker import MetronTalker
from metrontagger.taggerlib.options import make_parser
from metrontagger.taggerlib.settings import MetronTaggerSettings
from metrontagger.taggerlib.utils import cleanup_string


# Load the settings
SETTINGS = MetronTaggerSettings()


def sort_file(comic, sort_dir):
    ca = ComicArchive(comic)
    if ca.hasMetadata(MetaDataStyle.CIX):
        md = ca.readMetadata(MetaDataStyle.CIX)
    else:
        print(f"{os.path.basename(comic)} has no metadata. skipping...")
        return

    if md is not None:
        # Cleanup the publisher & series metadata so they play nicely with filesystems.
        publisher = cleanup_string(md.publisher)
        series = cleanup_string(md.series)
        new_path = sort_dir + os.sep + publisher + os.sep + series + os.sep
    else:
        return

    if not os.path.isdir(new_path):
        os.makedirs(new_path)

    try:
        move(comic, new_path)
        print(f"moved {os.path.basename(comic)} to {new_path}")
    except Error:
        print(
            f"{os.path.basename(comic)} already exists in sort directory... not moving."
        )


def create_metron_talker():
    auth = f"{SETTINGS.metron_user}:{SETTINGS.metron_pass}"
    base64string = standard_b64encode(auth.encode("utf-8"))
    talker = MetronTalker(base64string)

    return talker


def createPagelistMetadata(ca):

    md = GenericMetadata()
    md.setDefaultPageList(ca.getNumberOfPages())

    return md


def selectChoiceFromMultipleMatches(filename, match_set):
    print(f"{os.path.basename(filename)} - Multiple results found")

    # sort match list by cover date
    match_set = sorted(match_set, key=lambda m: m["cover_date"])

    for (counter, m) in enumerate(match_set):
        counter += 1
        print(f"{counter}. {m['__str__']} ({m['cover_date']})")

    while True:
        i = input("Choose a match #, or 's' to skip: ")
        if (i.isdigit() and int(i) in range(1, len(match_set) + 1)) or i == "s":
            break

    if i != "s":
        i = int(i) - 1
        issue_id = match_set[i]["id"]
    else:
        issue_id = None

    return issue_id


def getIssueId(filename, talker):

    fnp = FileNameParser()
    fnp.parseFilename(filename)

    series_word_list = fnp.series.split()
    series_string = " ".join(series_word_list).strip()
    series_string = urllib.parse.quote_plus(series_string.encode("utf-8"))

    search_results = talker.searchForIssue(series_string, fnp.issue, fnp.year)
    search_results_count = search_results["count"]

    if not search_results_count > 0:
        issue_id = None
    elif search_results_count > 1:
        issue_id = selectChoiceFromMultipleMatches(filename, search_results["results"])
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

    if opts.sort_dir:
        SETTINGS.sort_dir = opts.sort_dir

    if opts.set_metron_user or opts.set_sort_dir:
        SETTINGS.save()

    # Parse paths to get file list
    file_list = []
    file_list = get_recursive_filelist(opts.path)

    if not file_list:
        print("No files to process. Exiting.")
        sys.exit(0)

    if opts.missing:
        print("** Showing files without metadata **")
        for f in file_list:
            ca = ComicArchive(f)
            if ca.hasMetadata(MetaDataStyle.CIX):
                continue
            print(f"no metadata in '{os.path.basename(f)}'")

    if opts.delete:
        print("** Removing metadata **")
        for f in file_list:
            ca = ComicArchive(f)
            if ca.hasMetadata(MetaDataStyle.CIX):
                ca.removeMetadata(MetaDataStyle.CIX)
                print(f"removed metadata from '{os.path.basename(f)}'.")
            else:
                print(f"no metadata in '{os.path.basename(f)}'.")

    if opts.id:
        if len(file_list) > 1:
            print("More than one file was passed for Id processing. Exiting...")
            sys.exit(0)

        f = file_list[0]
        ca = ComicArchive(f)
        if ca.isWritable():
            md = createPagelistMetadata(ca)
            talker = create_metron_talker()
            metron_md = talker.fetchIssueDataByIssueId(opts.id)
            if metron_md:
                md.overlay(metron_md)
                ca.writeMetadata(md, MetaDataStyle.CIX)
                print(f"match found for '{os.path.basename(f)}'.")

    if opts.online:
        print("** Starting online search and tagging **")

        talker = create_metron_talker()

        for f in file_list:
            ca = ComicArchive(f)
            if opts.ignore_existing:
                if ca.hasMetadata(MetaDataStyle.CIX):
                    continue

            if ca.isWritable():
                md = createPagelistMetadata(ca)
                issue_id = getIssueId(f, talker)
                if not issue_id:
                    print(f"no match for '{os.path.basename(f)}'.")
                    continue

                metron_md = talker.fetchIssueDataByIssueId(issue_id)
                if metron_md:
                    md.overlay(metron_md)
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

    if opts.sort:
        if not SETTINGS.sort_dir:
            print("Unable to sort files. No destination directory was provided.")
            return

        print("** Starting sorting of comic archives **")
        for comic in file_list:
            sort_file(comic, SETTINGS.sort_dir)


if __name__ == "__main__":
    sys.exit(main())
