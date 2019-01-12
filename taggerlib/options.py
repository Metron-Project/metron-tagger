import argparse


def make_parser():
    parser = argparse.ArgumentParser(description='Read in a file or set of files, and return the result.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('path', nargs='+', help='Path of a file or a folder of files.')
    parser.add_argument("-R", "--recursive",
                        help="Recursively include files in sub-folders",
                        action="store_true",
                        default=False)
    parser.add_argument("-u", "--user", help="Metron user identity")
    parser.add_argument("-p", "--password", help="Metron user identity")
    parser.add_argument("--set-metron-user",
                        help="Save the Metron user settings",
                        action="store_true")

    return parser
