import io
import tarfile
from argparse import ArgumentParser
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from darkseid.comic import Comic, ComicArchiveError, MetadataFormat
from darkseid.metadata import Metadata
from darkseid.validate import SchemaVersion

from metrontagger.duplicates import DuplicateIssue
from metrontagger.run import Runner
from metrontagger.settings import MetronTaggerSettings
from metrontagger.talker import ProcessingConfig
from tests.conftest import create_cover_page


@pytest.mark.parametrize(
    ("has_metadata", "write_success", "expected_log_message"),
    [
        (
            True,
            True,
            None,
        ),
        (
            False,
            False,  # Value doesn't matter when has_metadata is False
            None,
        ),
        # TODO: Need to mock the comic name, so the return message is correct.
        # (
        #     True,
        #     False,
        #     "Could not write metadata to test_comic.cbz",
        # ),
    ],
    ids=[
        "happy_path_metadata_exists_write_success",
        "edge_case_no_metadata",
        # "error_case_write_fails",
    ],
)
def test__update_ci_xml(
    has_metadata: bool,
    write_success: bool,
    expected_log_message: str | None,
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    # Arrange
    comic_path = str(tmp_path / "test_comic.cbz")
    file_list = [DuplicateIssue(comic_path, [1])]

    mock_comic = Mock(spec=Comic)
    mock_comic.path = comic_path  # Set path for accurate logging
    mock_comic.has_metadata.return_value = has_metadata
    mock_comic.write_metadata.return_value = write_success
    if has_metadata:
        mock_comic.read_metadata.return_value = Metadata()
        mock_comic.get_number_of_pages.return_value = 10
    monkeypatch.setattr("metrontagger.comics.Comic", lambda _: mock_comic)

    # Act
    with caplog.at_level("ERROR"):  # Capture log messages at ERROR level
        Runner._update_ci_xml(file_list)

    # Assert
    if expected_log_message:
        assert expected_log_message in caplog.text
    else:
        assert "Could not write metadata" not in caplog.text  # Ensure no unexpected error logs


def test_migrate_ci_to_mi_skips_invalid_comic(
    tmp_path: Path, fake_comic: Path, fake_metadata: Metadata, monkeypatch
) -> None:
    """An invalid archive shouldn't stop migration of the files after it."""
    bad_comic = tmp_path / "not_a_comic.cbz"

    def comic_factory(path: Path) -> Comic:
        if path == bad_comic:
            raise ComicArchiveError
        return Comic(path)

    monkeypatch.setattr("metrontagger.comics.Comic", comic_factory)

    comic = Comic(fake_comic)
    assert comic.write_metadata(fake_metadata, MetadataFormat.COMIC_INFO)
    assert not comic.has_metadata(MetadataFormat.METRON_INFO)

    Runner.migrate_ci_to_mi([bad_comic, fake_comic])

    assert Comic(fake_comic).has_metadata(MetadataFormat.METRON_INFO)


# --- Helpers -----------------------------------------------------------------


@pytest.fixture
def output(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every message printed with questionary.print."""
    lines: list[str] = []
    monkeypatch.setattr(
        "metrontagger.ui.questionary.print", lambda msg, **_kw: lines.append(str(msg))
    )
    return lines


def _make_runner(parser: ArgumentParser, settings: MetronTaggerSettings, *argv: str) -> Runner:
    return Runner(parser.parse_args(list(argv)), settings)


def _tag(path: Path, md: Metadata, *formats: MetadataFormat) -> None:
    comic = Comic(path)
    for fmt in formats:
        assert comic.write_metadata(md, fmt)


def _make_cbt(path: Path) -> Path:
    data = create_cover_page()
    info = tarfile.TarInfo("cover.png")
    info.size = len(data)
    with tarfile.open(path, "w") as tf:
        tf.addfile(info, io.BytesIO(data))
    return path


CI = MetadataFormat.COMIC_INFO
MI = MetadataFormat.METRON_INFO


# --- Missing metadata --------------------------------------------------------


@pytest.mark.parametrize(
    ("tagged_formats", "flags", "expect_listed"),
    [
        ((), ("-c",), True),
        ((CI,), ("-c",), False),
        ((CI,), ("-m",), True),
        ((CI,), ("-c", "-m"), True),
        ((CI, MI), ("-c", "-m"), False),
    ],
    ids=["untagged", "has_ci", "ci_only_wants_mi", "ci_only_wants_both", "has_both"],
)
def test_comics_with_no_metadata(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    fake_metadata: Metadata,
    output: list[str],
    tagged_formats: tuple[MetadataFormat, ...],
    flags: tuple[str, ...],
    expect_listed: bool,
) -> None:
    _tag(fake_comic, fake_metadata, *tagged_formats)
    runner = _make_runner(parser, settings, str(fake_comic), "--missing", *flags)

    runner._comics_with_no_metadata([fake_comic])

    assert (str(fake_comic) in "\n".join(output)) is expect_listed


# --- Delete metadata ---------------------------------------------------------


@pytest.mark.parametrize(
    ("tagged_formats", "flags", "expected_remaining", "expected_msg"),
    [
        ((CI, MI), ("-c", "-m"), set(), "Removed 'ComicInfo.xml' and 'MetronInfo.xml'"),
        ((CI, MI), ("-c",), {MI}, "Removed 'ComicInfo.xml' metadata"),
        ((CI, MI), ("-m",), {CI}, "Removed 'MetronInfo.xml' metadata"),
        ((CI,), ("-c", "-m"), set(), "Removed 'ComicInfo.xml' metadata"),
        ((MI,), ("-c", "-m"), set(), "Removed 'MetronInfo.xml' metadata"),
        ((MI,), ("-c",), {MI}, "no metadata in"),
        ((), ("-c", "-m"), set(), "no metadata in"),
    ],
    ids=[
        "both_requested_both_present",
        "ci_requested",
        "mi_requested",
        "both_requested_only_ci_present",
        "both_requested_only_mi_present",
        "ci_requested_only_mi_present",
        "untagged",
    ],
)
def test_delete_metadata(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    fake_metadata: Metadata,
    output: list[str],
    tagged_formats: tuple[MetadataFormat, ...],
    flags: tuple[str, ...],
    expected_remaining: set[MetadataFormat],
    expected_msg: str,
) -> None:
    _tag(fake_comic, fake_metadata, *tagged_formats)
    runner = _make_runner(parser, settings, str(fake_comic), "--delete", *flags)

    runner._delete_metadata([fake_comic])

    comic = Comic(fake_comic)
    assert {fmt for fmt in (CI, MI) if comic.has_metadata(fmt)} == expected_remaining
    assert expected_msg in "\n".join(output)


def test_delete_metadata_reports_failure(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    output: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_comic = Mock(spec=Comic)
    mock_comic.has_metadata.return_value = True
    mock_comic.remove_metadata.return_value = False
    monkeypatch.setattr("metrontagger.comics.Comic", lambda _: mock_comic)
    runner = _make_runner(parser, settings, str(fake_comic), "--delete", "-c")

    runner._delete_metadata([fake_comic])

    out = "\n".join(output)
    assert "Failed to remove 'ComicInfo.xml'" in out
    assert "no metadata in" not in out


# --- Export to CBZ -----------------------------------------------------------


def test_export_to_zip_skips_cbz(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    output: list[str],
) -> None:
    runner = _make_runner(parser, settings, str(fake_comic), "-z")

    runner._export_to_zip([fake_comic])

    assert "already a cbz archive" in "\n".join(output)
    assert fake_comic.exists()


@pytest.mark.parametrize("delete_original", [False, True], ids=["keep", "delete"])
def test_export_to_zip_converts_cbt(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    tmp_path: Path,
    output: list[str],
    delete_original: bool,
) -> None:
    cbt = _make_cbt(tmp_path / "comic.cbt")
    argv = [str(cbt), "-z"] + (["--delete-original"] if delete_original else [])
    runner = _make_runner(parser, settings, *argv)

    runner._export_to_zip([cbt])

    cbz = cbt.with_suffix(".cbz")
    assert cbz.exists()
    assert Comic(cbz).is_valid_comic()
    assert cbt.exists() is not delete_original
    assert "Exported 'comic.cbt' to a cbz archive." in "\n".join(output)


def test_export_to_zip_reports_failure(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    tmp_path: Path,
    output: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cbt = tmp_path / "comic.cbt"
    mock_comic = Mock(spec=Comic)
    mock_comic.export_as_zip.return_value = False
    monkeypatch.setattr("metrontagger.comics.Comic", lambda _: mock_comic)
    runner = _make_runner(parser, settings, str(cbt), "-z", "--delete-original")

    runner._export_to_zip([cbt])

    assert "Failed to export 'comic.cbt'" in "\n".join(output)


def test_export_to_zip_skips_invalid_comic(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    tmp_path: Path,
    output: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = tmp_path / "bad.cbt"
    good = _make_cbt(tmp_path / "good.cbt")

    def comic_factory(path: Path) -> Comic:
        if path == bad:
            raise ComicArchiveError
        return Comic(path)

    monkeypatch.setattr("metrontagger.comics.Comic", comic_factory)
    runner = _make_runner(parser, settings, str(bad), "-z")

    runner._export_to_zip([bad, good])

    assert "'bad.cbt' is not a valid comic" in "\n".join(output)
    assert good.with_suffix(".cbz").exists()


# --- Validate ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "expected_msgs"),
    [
        (("-c",), ["has a valid ComicInfo Version 2"]),
        (("-m",), ["has a valid MetronInfo Version"]),
        (
            ("-c", "-m"),
            ["has a valid ComicInfo Version 2", "has a valid MetronInfo Version"],
        ),
    ],
    ids=["ci", "mi", "both"],
)
def test_validate_comic_info_valid(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    fake_metadata: Metadata,
    output: list[str],
    flags: tuple[str, ...],
    expected_msgs: list[str],
) -> None:
    _tag(fake_comic, fake_metadata, CI, MI)
    runner = _make_runner(parser, settings, str(fake_comic), "--validate", *flags)

    runner._validate_comic_info([fake_comic])

    out = "\n".join(output)
    for msg in expected_msgs:
        assert msg in out
    assert "is not valid" not in out


def test_validate_comic_info_no_metadata(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    output: list[str],
) -> None:
    runner = _make_runner(parser, settings, str(fake_comic), "--validate", "-c")

    runner._validate_comic_info([fake_comic])

    assert "doesn't have any metadata files" in "\n".join(output)


@pytest.mark.parametrize("remove", [False, True], ids=["report_only", "remove"])
def test_check_if_xml_is_valid_invalid(output: list[str], remove: bool) -> None:
    mock_comic = Mock(spec=Comic)
    mock_comic.path = Path("bad.cbz")
    mock_comic.validate_metadata.return_value = SchemaVersion.UNKNOWN
    mock_comic.remove_metadata.return_value = True

    Runner._check_if_xml_is_valid(mock_comic, CI, remove)

    out = "\n".join(output)
    assert "'bad.cbz' is not valid" in out
    assert ("Removed non-valid metadata" in out) is remove
    if remove:
        mock_comic.remove_metadata.assert_called_once_with([CI])
    else:
        mock_comic.remove_metadata.assert_not_called()


def test_check_if_xml_is_valid_keeps_valid_metadata() -> None:
    mock_comic = Mock(spec=Comic)
    mock_comic.path = Path("good.cbz")
    mock_comic.validate_metadata.return_value = SchemaVersion.COMIC_INFO_V2

    Runner._check_if_xml_is_valid(mock_comic, CI, remove_metadata=True)

    mock_comic.remove_metadata.assert_not_called()


# --- Rename ------------------------------------------------------------------


@pytest.mark.parametrize("fmt", [CI, MI], ids=["comicinfo", "metroninfo"])
def test_rename_comics(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    fake_metadata: Metadata,
    fmt: MetadataFormat,
) -> None:
    _tag(fake_comic, fake_metadata, fmt)
    runner = _make_runner(parser, settings, str(fake_comic), "-r")

    result = runner.rename_comics([fake_comic])

    assert len(result) == 1
    assert fake_comic not in result
    assert not fake_comic.exists()
    assert result[0].exists()
    assert result[0].name.startswith("Aquaman")


def test_rename_comics_prefers_metron_info(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    fake_metadata: Metadata,
    fake_tpb_metadata: Metadata,
) -> None:
    _tag(fake_comic, fake_tpb_metadata, CI)
    _tag(fake_comic, fake_metadata, MI)
    runner = _make_runner(parser, settings, str(fake_comic), "-r")

    result = runner.rename_comics([fake_comic])

    assert result[0].name.startswith("Aquaman")


def test_rename_comics_skips_untagged(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    output: list[str],
) -> None:
    runner = _make_runner(parser, settings, str(fake_comic), "-r")

    result = runner.rename_comics([fake_comic])

    assert result == [fake_comic]
    assert fake_comic.exists()
    assert "no metadata available" in "\n".join(output)


def test_create_file_renamer_uses_settings(
    parser: ArgumentParser, settings: MetronTaggerSettings, fake_comic: Path
) -> None:
    settings["rename.rename_template"] = "%series% #%issue%"
    settings["rename.rename_issue_number_padding"] = 4
    settings["rename.rename_use_smart_string_cleanup"] = False
    runner = _make_runner(parser, settings, str(fake_comic), "-r")

    renamer = runner._create_file_renamer()

    assert renamer.template == "%series% #%issue%"
    assert renamer.issue_zero_padding == 4
    assert renamer.smart_cleanup is False


# --- Sort --------------------------------------------------------------------


def test_sort_comic_list_without_directory(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    output: list[str],
) -> None:
    runner = _make_runner(parser, settings, str(fake_comic), "-s")

    runner._sort_comic_list([fake_comic])

    assert "No destination directory was provided" in "\n".join(output)
    assert fake_comic.exists()


def test_sort_comic_list_moves_comic(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    fake_metadata: Metadata,
    tmp_path: Path,
) -> None:
    _tag(fake_comic, fake_metadata, MI)
    sort_dir = tmp_path / "sorted"
    settings["sort.directory"] = str(sort_dir)
    runner = _make_runner(parser, settings, str(fake_comic), "-s")

    runner._sort_comic_list([fake_comic])

    assert not fake_comic.exists()
    assert list(sort_dir.rglob(fake_comic.name))


def test_sort_comic_list_reports_unsortable(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    tmp_path: Path,
    output: list[str],
) -> None:
    settings["sort.directory"] = str(tmp_path / "sorted")
    runner = _make_runner(parser, settings, str(fake_comic), "-s")

    runner._sort_comic_list([fake_comic])

    assert f"Unable to move '{fake_comic.name}'" in "\n".join(output)
    assert fake_comic.exists()


# --- Duplicates --------------------------------------------------------------


def _dup(path: str, page: int) -> Mock:
    item = Mock(spec=DuplicateIssue)
    item.path_ = path
    item.pages_index = [page]
    return item


def test_remove_duplicates_groups_pages_per_comic(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each comic gets a single DuplicateIssue holding every page picked for removal."""
    hashes = {
        # "a.cbz" is a substring of "ba.cbz"; they must stay separate.
        "hash_a": [_dup("ba.cbz", 3), _dup("a.cbz", 1), _dup("b.cbz", 4)],
        "hash_b": [_dup("a.cbz", 7), _dup("c.cbz", 2)],
        "hash_c": [_dup("b.cbz", 9)],  # declined below
    }
    dup_objs = MagicMock()
    dup_objs.get_distinct_hashes.return_value = list(hashes)
    dup_objs.get_comic_list_from_hash.side_effect = hashes.__getitem__
    dup_objs.delete_comic_pages.return_value = {}
    dup_objs.get_statistics.return_value = dict.fromkeys(
        ("total_pages", "duplicate_pages", "unique_duplicate_hashes", "comics_processed"), 0
    )
    duplicates_cls = MagicMock()
    duplicates_cls.return_value.__enter__.return_value = dup_objs
    monkeypatch.setattr("metrontagger.run.Duplicates", duplicates_cls)

    # review? yes; remove hash_a, hash_b, not hash_c; write changes? yes
    answers = iter([True, True, True, False, True])
    monkeypatch.setattr(
        "metrontagger.run.questionary.confirm",
        lambda *_a, **_k: Mock(ask=lambda: next(answers)),
    )
    runner = _make_runner(parser, settings, str(fake_comic), "--duplicates")

    runner._remove_duplicates([fake_comic])

    duplicates_cls.assert_called_once_with([fake_comic], quick=False)
    written = dup_objs.delete_comic_pages.call_args.args[0]
    assert {d.path_: d.pages_index for d in written} == {
        "ba.cbz": [3],
        "a.cbz": [1, 7],
        "b.cbz": [4],
        "c.cbz": [2],
    }


def test_remove_duplicates_declined_review(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dup_objs = MagicMock()
    dup_objs.get_distinct_hashes.return_value = ["hash_a"]
    duplicates_cls = MagicMock()
    duplicates_cls.return_value.__enter__.return_value = dup_objs
    monkeypatch.setattr("metrontagger.run.Duplicates", duplicates_cls)
    monkeypatch.setattr(
        "metrontagger.run.questionary.confirm",
        lambda *_a, **_k: Mock(ask=lambda: False),
    )
    runner = _make_runner(parser, settings, str(fake_comic), "--duplicates")

    runner._remove_duplicates([fake_comic])

    dup_objs.get_comic_list_from_hash.assert_not_called()
    dup_objs.delete_comic_pages.assert_not_called()


# --- run() dispatch ----------------------------------------------------------


def test_run_exits_when_no_files(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    tmp_path: Path,
    output: list[str],
) -> None:
    runner = _make_runner(parser, settings, str(tmp_path), "-r")

    with pytest.raises(SystemExit) as exc:
        runner.run()

    assert exc.value.code == 0
    assert "No files to process" in "\n".join(output)


def test_run_dispatch_order(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operations run in a fixed order, and rename's new paths feed into sort."""
    calls: list[str] = []
    renamed = [fake_comic.with_name("renamed.cbz")]

    def recorder(name: str, result: object = None):
        def _record(*args: object, **_kwargs: object) -> object:
            calls.append(name)
            if name == "_sort_comic_list":
                assert args[-1] == renamed
            return result

        return _record

    for name in (
        "_comics_with_no_metadata",
        "_export_to_zip",
        "_delete_metadata",
        "_remove_duplicates",
        "migrate_ci_to_mi",
        "_sort_comic_list",
        "_validate_comic_info",
    ):
        monkeypatch.setattr(Runner, name, recorder(name))
    monkeypatch.setattr(Runner, "rename_comics", recorder("rename_comics", renamed))
    talker = MagicMock()
    talker.identify_comics.side_effect = recorder("identify_comics")
    talker_cls = MagicMock()
    talker_cls.return_value.__enter__.return_value = talker
    monkeypatch.setattr("metrontagger.run.Talker", talker_cls)

    runner = _make_runner(
        parser,
        settings,
        str(fake_comic),
        "-c",
        "--missing",
        "-z",
        "--delete",
        "--duplicates",
        "--online",
        "--migrate",
        "-r",
        "-s",
        "--validate",
    )
    runner.run()

    assert calls == [
        "_comics_with_no_metadata",
        "_export_to_zip",
        "_delete_metadata",
        "_remove_duplicates",
        "identify_comics",
        "migrate_ci_to_mi",
        "rename_comics",
        "_sort_comic_list",
        "_validate_comic_info",
    ]


@pytest.mark.parametrize(
    ("quick_flag", "expected_quick"),
    [("--duplicates", False), ("--quick-duplicates", True)],
)
def test_run_duplicates_quick_mode(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    monkeypatch: pytest.MonkeyPatch,
    quick_flag: str,
    expected_quick: bool,
) -> None:
    remove = Mock()
    monkeypatch.setattr(Runner, "_remove_duplicates", remove)
    runner = _make_runner(parser, settings, str(fake_comic), quick_flag)

    runner.run()

    remove.assert_called_once_with([fake_comic], **({"quick": True} if expected_quick else {}))


@pytest.mark.parametrize(
    ("extra_files", "expect_single"),
    [(0, True), (1, False)],
    ids=["single_file_is_issue_id", "multiple_files_is_series_id"],
)
def test_run_id_dispatch(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_files: int,
    expect_single: bool,
) -> None:
    paths = [fake_comic]
    for i in range(extra_files):
        extra = tmp_path / f"extra{i}.cbz"
        extra.write_bytes(fake_comic.read_bytes())
        paths.append(extra)
    talker = MagicMock()
    talker_cls = MagicMock()
    talker_cls.return_value.__enter__.return_value = talker
    monkeypatch.setattr("metrontagger.run.Talker", talker_cls)
    settings["metron.auth_token"] = "token"  # noqa: S105
    runner = _make_runner(parser, settings, *map(str, paths), "--id", "42", "-m")

    runner.run()

    talker_cls.assert_called_once_with("token", [MI], username=None, redis_url=None)
    if expect_single:
        talker.retrieve_single_issue.assert_called_once_with(42, fake_comic)
        talker.identify_comics.assert_not_called()
    else:
        talker.identify_comics.assert_called_once()
        config = talker.identify_comics.call_args.args[1]
        assert config == ProcessingConfig(series_id=42)
        talker.retrieve_single_issue.assert_not_called()


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ([], ProcessingConfig()),
        (["--accept-only"], ProcessingConfig(accept_only=True)),
        (["--skip-multiple"], ProcessingConfig(skip_multiple=True)),
        (["--ignore-existing"], ProcessingConfig(ignore_existing=True)),
        (["--ignore-modified"], ProcessingConfig(ignore_modified=True)),
        (["--id", "7"], ProcessingConfig(series_id=7)),
    ],
    ids=[
        "defaults",
        "accept_only",
        "skip_multiple",
        "ignore_existing",
        "ignore_modified",
        "id",
    ],
)
def test_processing_config_from_args(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    flags: list[str],
    expected: ProcessingConfig,
) -> None:
    runner = _make_runner(parser, settings, str(fake_comic), "-o", "-c", *flags)

    assert runner._processing_config() == expected


@pytest.mark.parametrize(
    ("flags", "expected_formats"),
    [(["-c"], [CI]), (["-m"], [MI]), (["-c", "-m"], [CI, MI])],
    ids=["comicinfo", "metroninfo", "both"],
)
def test_tag_online_passes_selected_formats(
    parser: ArgumentParser,
    settings: MetronTaggerSettings,
    fake_comic: Path,
    monkeypatch: pytest.MonkeyPatch,
    flags: list[str],
    expected_formats: list[MetadataFormat],
) -> None:
    """Talker writes the chosen formats, ComicInfo first when both are chosen."""
    talker_cls = MagicMock()
    monkeypatch.setattr("metrontagger.run.Talker", talker_cls)
    runner = _make_runner(parser, settings, str(fake_comic), "-o", *flags)

    runner._tag_online([fake_comic])

    assert talker_cls.call_args.args[1] == expected_formats
