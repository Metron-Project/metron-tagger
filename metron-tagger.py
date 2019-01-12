#!/usr/bin/env python3

import os
import sys
from taggerlib.options import make_parser
from taggerlib.settings import MetronTaggerSettings

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
                            # TODO: Use ZipFile to determine file type
                            if fileExt == '.cbz':
                                file_list.append(os.path.join(root, f))

    print(f'Files: {file_list}')

    if not file_list:
        print('No files to process. Exiting.')
        sys.exit(0)


if __name__ == '__main__':
    sys.exit(main())
