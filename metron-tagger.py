#!/usr/bin/env python3

import sys
from taggerlib.settings import MetronTaggerSettings
from taggerlib.options import make_parser

# Load the settings
SETTINGS = MetronTaggerSettings()


def main():

    parser = make_parser()
    opts = parser.parse_args()

    if opts.user:
        SETTINGS.metron_user = opts.user

    if opts.password:
        SETTINGS.metron_pass = opts.password

    if opts.set_metron_user:
        SETTINGS.save()

    if opt.recursive:
        # TODO: get the file list of comic archives
        pass


if __name__ == '__main__':
    sys.exit(main())
