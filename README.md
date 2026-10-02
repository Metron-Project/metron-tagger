# Metron-Tagger

[![PyPI version](https://img.shields.io/pypi/v/metron-tagger.svg)](https://pypi.org/project/metron-tagger/)
[![Python versions](https://img.shields.io/pypi/pyversions/metron-tagger.svg)](https://pypi.org/project/metron-tagger/)
[![License](https://img.shields.io/github/license/bpepple/metron-tagger)](https://opensource.org/licenses/GPL-3.0)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Quick Description

A command-line tool to tag comic archives with metadata from
[metron.cloud](https://metron.cloud).

## Installation

### PyPi

Or install it yourself:

```bash
pipx install metron-tagger
```

There are optional dependencies which can be installed by specifying one or more
of them in braces e.g. metron-tagger[7zip]

The optional dependencies are:

- 7zip: Provides support for reading/writing to CB7 files.
- pdf: Provides support for reading/writing to PDF files.
- redis: Provides a Redis-backed rate limiter for the Metron API.

## FAQ

**How do I use the Redis rate limiter?**

- Install the `redis` extra (e.g. `pipx install metron-tagger[redis]`), and set
  `redis_url` in the `[metron]` section of your `settings.ini`:

  ```ini
  [metron]
  redis_url = redis://localhost:6379/0
  ```

  Every metron-tagger process using the same Metron account and Redis server
  will then share one rate limit, so running several at once won't exceed
  Metron's limits. If Redis can't be reached, metron-tagger falls back to its
  local rate limiter. If Redis fails partway through a run, metron-tagger stops
  processing the remaining files.

**How do I share the rate limit with other mokkari-based software?**

- Other software using mokkari's `RedisRateLimiter` will share metron-tagger's
  rate limit as long as it uses the same Redis server and database, mokkari's
  default `key_prefix` (`mokkari:ratelimit`), and the same `account` name.
  metron-tagger derives the `account` name from your Metron credentials:
  - With an API token: `token-` followed by the first 16 hex characters of the
    token's SHA-256 hash. The token itself is never used, since the account name
    appears in Redis key names.
  - With a username and password (deprecated): the username.

  For example:

  ```python
  import hashlib

  from mokkari.redis_rate_limit import RedisRateLimiter

  account = f"token-{hashlib.sha256(api_token.encode()).hexdigest()[:16]}"
  rate_limiter = RedisRateLimiter(redis_client, account)
  ```

**What comics formats are supported?**

- Metron-Tagger supports CBZ, CBR, CBT, CB7 (optional), and PDF (optional)
  comics.

**How to enable RAR support?**

- It depends on the unrar command-line utility, and expects it to be in your
  $PATH.
  > _NOTE_: unrar only supports reading archives, so you will need to convert
  > the archive to a cbz to write to it. To do so you can use
  > `-z, --export-to-cbz` and if you want you can remove the orginal .cbr
  > archive with `--delete-original` after successful conversion.

## Help

```text
usage: metron-tagger [-h] [-r] [-o] [-m] [-c] [--id ID] [-d] [--ignore-existing] [--accept-only] [--skip-multiple] [--ignore-modified] [--missing] [-s] [-z] [--validate] [--remove-non-valid] [--delete-original] [--duplicates] [--migrate] [--version]
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
  --id ID              Identify file for tagging with the Metron Issue Id, or restrict directory matches to issues from a specific Metron Series Id. (default: None)
  -d, --delete         Delete the metadata tags from the file. (default: False)
  --ignore-existing    Ignore files that have existing metadata tag. (default: False)
  --accept-only        Automatically accept the match when exactly one valid match is found. (default: False)
  --skip-multiple      Skip files that have multiple matches instead of prompting for selection. (default: False)
  --ignore-modified    Retag files with an existing Metron ID without using the last modified date, forcing a full refresh from the API. Useful for pulling in changes, such as an updated community rating, that don't update the issue's modified date. (default: False)
  --missing            List files without metadata. (default: False)
  -s, --sort           Sort files that contain metadata tags. (default: False)
  -z, --export-to-cbz  Export a CBR (rar) archive to a CBZ (zip) archive. (default: False)
  --validate           Verify that comic archive has a valid metadata xml. (default: False)
  --remove-non-valid   Remove metadata xml from comic if not valid. Used with --validate option (default: False)
  --delete-original    Delete the original archive after successful export to another format. (default: False)
  --duplicates         Identify and give the option to delete duplicate pages in a directory of comics. (Experimental) (default: False)
  --migrate            Migrate information from a ComicInfo.xml into a *new* MetronInfo.xml (default: False)
  --version            Show the version number and exit
```

## Examples

To tag all comics in a directory with MetronInfo.xml that don't already have
one:

```bash
metron-tagger -om --ignore-existing /path/to/comics
```

To remove any ComicInfo.xml from a directory of comics:

```bash
metron-tagger -dc /path/to/comics
```

To validate any metadata, ComicInfo.xml and MetronInfo.xml, would be done by
running the following:

```bash
metron-tagger -cm --validate /path/to/comics
```

To write MetronInfo.xml metadata from comics with ComicInfo.xml data, and
migrate data for comics that don't exist at the Metron Comic Database:

```bash
metron-tagger -om --migrate /path/to/comics
```

To remove duplicate pages from comics (which should be only ran on a directory
of weekly release since we scan all the pages within a comic), would be done by
running the following:

```bash
metron-tagger --duplicates /path/to/weekly/comics
```

## Bugs/Requests

Please use the
[GitHub issue tracker](https://github.com/Metron-Project/metron-tagger/issues)
to submit bugs or request features.

## License

This project is licensed under the [GPLv3 License](LICENSE).
