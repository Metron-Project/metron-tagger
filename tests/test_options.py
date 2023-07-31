from argparse import ArgumentParser
from pathlib import Path


def test_path_options(parser: ArgumentParser, tmpdir: Path) -> None:
    parsed = parser.parse_args([str(tmpdir)])
    assert parsed.path == [str(tmpdir)]


def test_online_option(parser: ArgumentParser, tmpdir: Path) -> None:
    parsed = parser.parse_args(["-o", str(tmpdir)])
    assert parsed.online is True
    assert parsed.path == [str(tmpdir)]


def test_id_option(parser: ArgumentParser, tmpdir: Path) -> None:
    parsed = parser.parse_args(["--id", "1", str(tmpdir)])
    assert parsed.id == "1"
    assert parsed.path == [str(tmpdir)]


def test_delete_option(parser: ArgumentParser, tmpdir: Path) -> None:
    parsed = parser.parse_args(["-d", str(tmpdir)])
    assert parsed.delete is True
    assert parsed.path == [str(tmpdir)]


def test_missing_option(parser: ArgumentParser, tmpdir: Path) -> None:
    parsed = parser.parse_args(["--missing", str(tmpdir)])
    assert parsed.missing is True
    assert parsed.path == [str(tmpdir)]


def test_rename_option(parser: ArgumentParser, tmpdir: Path) -> None:
    parsed = parser.parse_args(["-r", str(tmpdir)])
    assert parsed.rename is True
    assert parsed.path == [str(tmpdir)]


def test_ignore_option(parser: ArgumentParser, tmpdir: Path) -> None:
    parsed = parser.parse_args(["--ignore-existing", str(tmpdir)])
    assert parsed.ignore_existing is True
    assert parsed.path == [str(tmpdir)]
