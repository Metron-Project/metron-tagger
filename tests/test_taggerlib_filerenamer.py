from metrontagger.taggerlib.filerenamer import FileRenamer


def test_determine_name(fake_comic, fake_metadata):
    expected_result = "Aquaman v2 #001 (2011).zip"

    renamer = FileRenamer(fake_metadata)
    new_file_name = renamer.determine_name(fake_comic)
    assert new_file_name == expected_result
