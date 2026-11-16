# 📰 Metron-Tagger News

## Unreleased

## 🚀 Features

- Search by cover hash before falling back to filename search @bpepple (#294)
- Options that need `--comicinfo` and/or `--metroninfo` (`--missing`,
  `--delete`, `--online`, `--id`, `--validate`) now stop with a usage error
  before anything runs, instead of exiting partway through a run. The exit
  status is now 2.

## 🐛 Bug Fixes

- Online tagging now finds a Metron ID stored only in a comic's ComicInfo.xml
  when its MetronInfo.xml has no ID. This works around a darkseid caching bug
  ([darkseid#267](https://github.com/Metron-Project/darkseid/issues/267)).
- Pressing Ctrl-C at the API token or sort directory prompt no longer saves
  `None` as that setting. A `None` saved by an earlier version is cleared when
  the settings load, so you're asked for the token again.
- Fix a crash after tagging an issue whose series has no format.
- `--migrate` no longer stops at the first invalid comic; it skips it and
  migrates the rest.
- Duplicate page removal could group one comic's pages under another comic whose
  path contained the first one's (for example, `a.cbz` and `ba.cbz`).
- A comic with malformed metadata XML is renamed and sorted using its other
  metadata format, instead of from empty metadata.
- Online tagging no longer crashes with a traceback when Metron returns a
  non-standard HTTP status, such as Cloudflare's 520–524; the error is reported
  and tagging continues.
- Tagging an issue from a Hardcover series now shows it as a collection; only
  Metron's old "Hard Cover" name was recognized.
- A setting with an invalid value now uses its default. For example, an
  unrecognized `rename_use_smart_string_cleanup` value used to turn smart
  cleanup off; it now leaves it on, the default.

## 🧰 Maintenance

- Drop the pandas dependency.
- Internal refactoring, more tests, and type checking with pyright.

## v2.5.1

## 🚀 Features

- Fix User Matching Interaction @bpepple (#138)

## 🐛 Bug Fixes

- Ignore `Corrupt EXIF data` warnings @bpepple (#137)

## v2.5.0

## 🚀 Features

- Add imprint support @bpepple (#135)

## 🧰 Maintenance

- v2.5.0 @bpepple (#136)

## v2.4.0

## 🚀 Features

- Add New Format Name to mapping in FileRenamer class @bpepple (#132)
- Update for Hardcover Naming Change @bpepple (#131)

## 🧰 Maintenance

- v2.4.0 @bpepple (#134)
- Update Project Dependencies @bpepple (#133)

## v2.3.2

## 🧰 Maintenance

- Performance Refactoring @bpepple (#128)
- Bump certifi from 2024.6.2 to 2024.7.4 @dependabot (#129)

## v2.3.1

## 🧰 Maintenance

- Bump minimum version of comicfn2dict.
- Add Tests \& Docstrings @bpepple (#126)
- Refactoring @bpepple (#124)

## v2.3.0

## 🚀 Features

- Handle Renaming of Digital Comics @bpepple (#122)
- Remove Oddball Rename Tokens @bpepple (#120)
- Remove Non-Valid Metadata @bpepple (#119)

## 🧰 Maintenance

- Type Annotation Fixes @bpepple (#118)
- Bump requests from 2.31.0 to 2.32.0 @dependabot (#121)
- Bump idna from 3.6 to 3.7 @dependabot (#117)

## v2.2.4

### 🐛 Bug Fixes

- Fix Tagging Bug with Existing `ComicInfo.xml` @bpepple (#114)
- Fix bug in duplicate image detection when attempting to hash a bad image.
  (#105)

### 🧰 Maintenance

- Update Pillow and Other Deps @bpepple (#115)
- Bump actions/cache from 2 to 4 @dependabot (#111)
- Bump actions/checkout from 2 to 4 @dependabot (#107)
- Bump release-drafter/release-drafter from 5 to 6 @dependabot (#110)
- Bump github/codeql-action from 1 to 3 @dependabot (#109)
- Bump JRubics/poetry-publish from 1.17 to 2.0 @dependabot (#108)
- Bump actions/setup-python from 2 to 5 @dependabot (#106)

## v2.2.3

### Changes

### 🧰 Maintenance

- Update minimum required version of `comicfn2dict`.
- Rework project files to use a Makefile for development.

## v2.2.2

### Changes

### 🐛 Bug Fixes

- Strip commas and `&` from series name @bpepple (#103)
