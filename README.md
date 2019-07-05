## Metron-Tagger

[![PyPI version](https://badge.fury.io/py/metron-tagger.svg)](https://badge.fury.io/py/metron-tagger)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/e2b6caca439a4684a96b01844ced5207)](https://app.codacy.com/app/bpepple/metron-tagger?utm_source=github.com&utm_medium=referral&utm_content=bpepple/metron-tagger&utm_campaign=Badge_Grade_Dashboard)
[![Codacy Badge](https://api.codacy.com/project/badge/Coverage/eed1b6534cbf46ee9184dfe26e994d46)](https://www.codacy.com/app/bpepple/metron-tagger?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bpepple/metron-tagger&amp;utm_campaign=Badge_Coverage)
[![Build Status](https://travis-ci.org/bpepple/metron-tagger.svg?branch=master)](https://travis-ci.org/bpepple/metron-tagger)

### Quick Description

A command-line tool to tag comic archives with metadata from [metron.cloud](https://metron.cloud).

### Installation

- PyPi

  Install it yourself:

  ```
    $ pip3 install --user metron-tagger
  ```
    
- GitHub

  Installing the latest version from Github:
  ```
    $ git clone https://github.com/bpepple/metron-tagger.git
    $ cd metron-tagger
    $ python3 setup.py install
  ```


### FAQ

1. **Why no cbr (rar) support?**

   * I'm not aware of any provider (Comixology, Humble Bundle, DriveThru Comics, etc.) of legally downloadable DRM-free comics that use the rar format.
   * It's a non-free software file format.
   * It is trivial to convert to cbz (zip) format.
   
### Help

```
usage: metron_tagger.py [-h] [-r] [-o] [--id ID] [-d] [--ignore-existing]
                        [--missing] [-u USER] [-p PASSWORD]
                        [--set-metron-user] [-s] [--sort-dir SORT_DIR]
                        [--set-sort-dir] [--version]
                        path [path ...]

Read in a file or set of files, and return the result.

positional arguments:
  path                  Path of a file or a folder of files.

optional arguments:
  -h, --help            show this help message and exit
  -r, --rename          Rename comic archive from the files metadata.
                        (default: False)
  -o, --online          Search online and attempt to identify comic archive.
                        (default: False)
  --id ID               Identify file for tagging with the Metron Issue Id.
                        (default: None)
  -d, --delete          Delete the metadata tags from the file. (default:
                        False)
  --ignore-existing     Ignore files that have existing metadata tag.
                        (default: False)
  --missing             List files without metadata. (default: False)
  -u USER, --user USER  Metron user identity (default: None)
  -p PASSWORD, --password PASSWORD
                        Metron user password (default: None)
  --set-metron-user     Save the Metron user settings (default: False)
  -s, --sort            Sort files that contain metadata tags. (default:
                        False)
  --sort-dir SORT_DIR   Directory wher files should be sorted to. This should
                        not have a trailing path serparator. (default: None)
  --set-sort-dir        Set the directory where files should be sorted.
                        (default: False)
  --version             Show the version number and exit
```
