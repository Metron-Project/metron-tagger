"""Utility to create an argument parser"""

import argparse

from metrontagger import __version__


def make_parser() -> argparse.ArgumentParser:
    """Function to create the argument parser"""
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
    parser.add_argument("--id", help="Identify file for tagging with the Metron Issue Id.")
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
        "-i",
        "--interactive",
        help="Interactively query the user when there are matches for an online search.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--missing",
        help="List files without metadata.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-s",
        "--sort",
        help="Sort files that contain metadata tags.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-z",
        "--export-to-cbz",
        help="Export a CBR (rar) archive to a CBZ (zip) archive.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--validate",
        help="Verify that comic archive has a valid ComicInfo.xml.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--remove-non-valid",
        help="Remove ComicInfo.xml from comic if not valid. Used with --validate option",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--delete-original",
        help="Delete the original archive after successful export to another format.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--duplicates",
        help="Identify and give the option to delete duplicate pages "
        "in a directory of comics. (Experimental)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the version number and exit",
    )

    return parser
