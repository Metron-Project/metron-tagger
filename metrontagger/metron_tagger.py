import os
import sys
from base64 import standard_b64encode

# Append sys.path so imports work.
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from metrontagger.comicapi.comicarchive import ComicArchive, MetaDataStyle
from metrontagger.comicapi.genericmetadata import GenericMetadata
from metrontagger.comicapi.utils import get_recursive_filelist, unique_file
from metrontagger.taggerlib.filerenamer import FileRenamer
from metrontagger.taggerlib.filesorter import FileSorter
from metrontagger.taggerlib.metrontalker import MetronTalker
from metrontagger.taggerlib.options import make_parser
from metrontagger.taggerlib.settings import MetronTaggerSettings
from metrontagger.taggerlib.utils import create_issue_query_dict


# Load the settings
SETTINGS = MetronTaggerSettings()


class MultipleMatch:
    def __init__(self, filename, match_list):
        self.filename = filename
        self.matches = match_list


class OnlineMatchResults:
    def __init__(self):
        self.multipleMatches = []


def create_metron_talker():
    auth = f"{SETTINGS.metron_user}:{SETTINGS.metron_pass}"
    base64string = standard_b64encode(auth.encode("utf-8"))
    talker = MetronTalker(base64string)

    return talker


def createPagelistMetadata(ca):
    md = GenericMetadata()
    md.setDefaultPageList(ca.getNumberOfPages())

    return md


def getIssueMetadata(filename, issue_id, talker):
    success = False

    metron_md = talker.fetchIssueDataByIssueId(issue_id)
    if metron_md:
        ca = ComicArchive(filename)
        md = createPagelistMetadata(ca)
        md.overlay(metron_md)
        ca.writeMetadata(md, MetaDataStyle.CIX)
        success = True

    return success


def selectChoiceFromMultipleMatches(filename, match_set):
    print(f"{os.path.basename(filename)} - Multiple results found")

    # sort match list by cover date
    match_set = sorted(match_set, key=lambda m: m["cover_date"])

    for (counter, m) in enumerate(match_set, start=1):
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


def processFile(filename, match_results, talker):
    ca = ComicArchive(filename)

    if not ca.seemsToBeAComicArchive():
        print(f"{os.path.basename(filename)} does not appear to be a comic archive.")
        return

    if not ca.isWritable():
        print(f"{os.path.basename(filename)} is not writable.")
        return

    query_dict = create_issue_query_dict(filename)
    res = talker.searchForIssue(query_dict)
    res_count = res["count"]

    issue_id = None
    multiple_match = False
    if not res_count > 0:
        issue_id = None
        multiple_match = False
    elif res_count > 1:
        issue_id = None
        multiple_match = True
        match_results.multipleMatches.append(MultipleMatch(filename, res["results"]))
    elif res_count == 1:
        issue_id = res["results"][0]["id"]
        multiple_match = False

    return issue_id, multiple_match


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

        filename = file_list[0]
        ca = ComicArchive(filename)
        if ca.isWritable():
            md = createPagelistMetadata(ca)
            talker = create_metron_talker()
            metron_md = talker.fetchIssueDataByIssueId(opts.id)
            if metron_md:
                md.overlay(metron_md)
                ca.writeMetadata(md, MetaDataStyle.CIX)
                print(f"match found for '{os.path.basename(filename)}'.")

    if opts.online:
        print("** Starting online search and tagging **")

        # Initialize class to handle results for files with multiple matches
        match_results = OnlineMatchResults()
        talker = create_metron_talker()

        # Let's look online to see if we can find any matches on Metron.
        for filename in file_list:
            issue_id, multiple_match = processFile(filename, match_results, talker)
            if issue_id:
                success = getIssueMetadata(filename, issue_id, talker)
                if success:
                    print(f"match found for '{os.path.basename(filename)}'.")
                else:
                    print(
                        f"there was a problem writing metadate for '{os.path.basename(filename)}'."
                    )
            else:
                if not multiple_match:
                    print(f"no match for '{os.path.basename(filename)}'.")
                    continue

        # If there are any files with multiple matches let's handle those now.
        if len(match_results.multipleMatches) > 0:
            for match_set in match_results.multipleMatches:
                issue_id = selectChoiceFromMultipleMatches(
                    match_set.filename, match_set.matches
                )
                if issue_id:
                    success = getIssueMetadata(match_set.filename, issue_id, talker)
                    if not success:
                        print(
                            f"Unable to retrieve metadata for '{os.path.basename(match_set.filename)}'."
                        )

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
        fs = FileSorter(SETTINGS.sort_dir)
        for comic in file_list:
            result = fs.sort_comics(comic)
            if not result:
                print(f"unable to move {os.path.basename(comic)}.")


if __name__ == "__main__":
    sys.exit(main())
