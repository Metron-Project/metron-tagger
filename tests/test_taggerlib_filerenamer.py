from darkseid.genericmetadata import GenericMetadata
from metrontagger.taggerlib.filerenamer import FileRenamer


def test_determine_name(fake_comic):
    meta_data = GenericMetadata()
    meta_data.series = "Aquaman"
    meta_data.volume = "2"
    meta_data.issue = "1"
    meta_data.year = "2011"

    expected_result = "Aquaman v2 #001 (2011).zip"

    renamer = FileRenamer(meta_data)
    new_file_name = renamer.determine_name(fake_comic)
    assert new_file_name == expected_result
