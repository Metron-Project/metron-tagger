#!/usr/bin/env python3

import sys
from taggerlib.settings import MetronTaggerSettings

# Load the settings
SETTINGS = MetronTaggerSettings()


def main():

    print(f"User: {SETTINGS.metron_user}")
    print(f"Password: {SETTINGS.metron_pass}")

if __name__ == '__main__':
    sys.exit(main())
