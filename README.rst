=============
Metron-Tagger
=============

.. image:: https://img.shields.io/pypi/v/metron-tagger.svg
    :target: https://pypi.org/project/metron-tagger/

.. image:: https://img.shields.io/pypi/pyversions/metron-tagger.svg
    :target: https://pypi.org/project/metron-tagger/

.. image:: https://img.shields.io/github/license/bpepple/metron-tagger
    :target: https://opensource.org/licenses/GPL-3.0

.. image:: https://codecov.io/gh/bpepple/metron-tagger/branch/master/graph/badge.svg?token=d8TyzWM2Uz
    :target: https://codecov.io/gh/bpepple/metron-tagger

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

Quick Description
-----------------

A command-line tool to tag comic archives with metadata from metron.cloud_.

.. _metron.cloud: https://metron.cloud

Installation
------------

PyPi
~~~~

Or install it yourself:

.. code:: bash

  $ pip install --user metron-tagger

GitHub
~~~~~~

Installing the latest version from Github:

.. code:: bash

  $ git clone https://github.com/bpepple/metron-tagger.git
  $ cd metron-tagger
  $ python3 setup.py install

FAQ
---

**Why no .cbr (rar) support?**

- I'm not aware of any provider (Comixology, Humble Bundle, DriveThru Comics, etc.) of legally downloadable DRM-free comics that use the rar format.
- It's a non-free software file format.
- It is trivial to convert to cbz (zip) format.

Help
----

::

    usage: metron-tagger [-h] [-r] [-o] [--id ID] [-d] [--ignore-existing]
                         [--missing] [-u USER] [-p PASSWORD] [--set-metron-user]
                         [-s] [--sort-dir SORT_DIR] [--set-sort-dir] [--version]
                         path [path ...]

    Read in a file or set of files, and return the result.

    positional arguments:
        path                  Path of a file or a folder of files.

    optional arguments:
        -h, --help            show this help message and exit
        -r, --rename          Rename comic archive from the files metadata. (default: False)
        -o, --online          Search online and attempt to identify comic archive. (default: False)
        --id ID               Identify file for tagging with the Metron Issue Id. (default: None)
        -d, --delete          Delete the metadata tags from the file. (default: False)
        --ignore-existing     Ignore files that have existing metadata tag. (default: False)
        --missing             List files without metadata. (default: False)
        -u USER, --user USER  Metron user identity (default: None)
        -p PASSWORD, --password PASSWORD
                              Metron user password (default: None)
        --set-metron-user     Save the Metron user settings (default: False)
        -s, --sort            Sort files that contain metadata tags. (default: False)
        --sort-dir SORT_DIR   Directory wher files should be sorted to. This should
                              not have a trailing path serparator. (default: None)
        --set-sort-dir        Set the directory where files should be sorted. (default: False)
        --version             Show the version number and exit

Bugs/Requests
-------------

Please use the `GitHub issue tracker <https://github.com/bpepple/metron-tagger/issues>`_ to submit bugs or request features.

License
-------

This project is licensed under the `GPLv3 License <LICENSE>`_.

