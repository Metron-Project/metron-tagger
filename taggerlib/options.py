import argparse


def make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-R", "--recursive",
                        help="Recursively include files in sub-folders",
                        action="store_true")
    parser.add_argument("-u", "--user", help="Metron user identity")
    parser.add_argument("-p", "--password", help="Metron user identity")
    parser.add_argument("--set-metron-user",
                        help="Save the Metron user settings",
                        action="store_true")

    return parser
