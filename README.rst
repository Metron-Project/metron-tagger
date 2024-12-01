=============
Metron-Tagger
=============

.. image:: https://img.shields.io/pypi/v/metron-tagger.svg
    :target: https://pypi.org/project/metron-tagger/

.. image:: https://img.shields.io/pypi/pyversions/metron-tagger.svg
    :target: https://pypi.org/project/metron-tagger/

.. image:: https://img.shields.io/github/license/bpepple/metron-tagger
    :target: https://opensource.org/licenses/GPL-3.0

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Ruff

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

  $ pipx install metron-tagger

FAQ
---

**How to enable RAR support?**

- It depends on the unrar command-line utility, and expects it to be in your $PATH.

Help
----

::

  usage: metron-tagger [-h] [-r] [-o] [-m] [-c] [--id ID] [-d] [--ignore-existing] [-i] [--missing] [-s] [-z] [--validate] [--remove-non-valid] [--delete-original]
                     [--duplicates] [--migrate] [--version]
                     path [path ...]


  Read in a file or set of files, and return the result.

  positional arguments:
    path                 Path of a file or a folder of files.

  options:
    -h, --help           show this help message and exit
    -r, --rename         Rename comic archive from the files metadata. (default: False)
    -o, --online         Search online and attempt to identify comic archive. (default: False)
    -m, --metroninfo     Write, delete, or validate MetronInfo.xml. (default: False)
    -c, --comicinfo      Write, delete, or validate ComicInfo.xml. (default: False)
    --id ID              Identify file for tagging with the Metron Issue Id. (default: None)
    -d, --delete         Delete the metadata tags from the file. (default: False)
    --ignore-existing    Ignore files that have existing metadata tag. (default: False)
    -i, --interactive    Interactively query the user when there are matches for an online search. (default: False)
    --missing            List files without metadata. (default: False)
    -s, --sort           Sort files that contain metadata tags. (default: False)
    -z, --export-to-cbz  Export a CBR (rar) archive to a CBZ (zip) archive. (default: False)
    --validate           Verify that comic archive has a valid metadata xml. (default: False)
    --remove-non-valid   Remove metadata xml from comic if not valid. Used with --validate option (default: False)
    --delete-original    Delete the original archive after successful export to another format. (default: False)
    --duplicates         Identify and give the option to delete duplicate pages in a directory of comics. (Experimental) (default: False)
    --migrate            Migrate information from a ComicInfo.xml into a *new* MetronInfo.xml (default: False)
    --version            Show the version number and exit

Examples
--------

To tag all comics in a directory with MetronInfo.xml that don't already have one:
::

  metron-tagger -om --ignore-existing /path/to/comics

To remove any ComicInfo.xml from a directory of comics:
::

  metron-tagger -dc /path/to/comics

To validate any metadata, ComicInfo.xml and MetronInfo.xml, would be done by running the following:
::

  metron-tagger -cm --validate /path/to/comics

To write MetronInfo.xml metadata from comics with ComicInfo.xml data, and migrate data for comics that don't exist at the Metron Comic Database:
::

  metron-tagger -om --migrate /path/to/comics


Bugs/Requests
-------------

Please use the `GitHub issue tracker <https://github.com/Metron-Project/metron-tagger/issues>`_ to submit bugs or request features.

License
-------

This project is licensed under the `GPLv3 License <LICENSE>`_.

