import argparse

from .. import version


def make_parser():
    parser = argparse.ArgumentParser(
        description="Read in a file or set of files, and return the result.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("path", nargs="+", help="Path of a file or a folder of files.")
    parser.add_argument(
        "-r",
        "--rename",
        help="Rename comic archive from the files metadata.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-o",
        "--online",
        help="Search online and attempt to identify comic archive.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--id", help="Identify file for tagging with the Metron Issue Id."
    )
    parser.add_argument(
        "-d",
        "--delete",
        help="Delete the metadata tags from the file.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--ignore-existing",
        help="Ignore files that have existing metadata tag.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--missing",
        help="List files without metadata.",
        action="store_true",
        default=False,
    )
    parser.add_argument("-u", "--user", help="Metron user identity")
    parser.add_argument("-p", "--password", help="Metron user identity")
    parser.add_argument(
        "--set-metron-user", help="Save the Metron user settings", action="store_true"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {}".format(version),
        help="Show the version number and exit",
    )

    return parser
