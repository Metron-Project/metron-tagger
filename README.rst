=============
Metron-Tagger
=============

.. image:: https://img.shields.io/pypi/v/metron-tagger.svg
    :target: https://pypi.org/project/metron-tagger/

.. image:: https://img.shields.io/pypi/pyversions/metron-tagger.svg
    :target: https://pypi.org/project/metron-tagger/

.. image:: https://codecov.io/gh/bpepple/metron-tagger/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/bpepple/metron-tagger
    :alt: Code coverage Status

.. image:: https://travis-ci.org/bpepple/metron-tagger.svg?branch=master
    :target: https://travis-ci.org/bpepple/metron-tagger

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

1. Why no .cbr (rar) support?

  - I'm not aware of any provider (Comixology, Humble Bundle, DriveThru Comics, etc.) of legally downloadable DRM-free comics that use the rar format.
  - It's a non-free software file format.
  - It is trivial to convert to cbz (zip) format.

Bugs/Requests
-------------

Please use the `GitHub issue tracker <https://github.com/bpepple/metron-tagger/issues>`_ to submit bugs or request features.

License
-------

This project is licensed under the `GPLv3 License <LICENSE>`_.

