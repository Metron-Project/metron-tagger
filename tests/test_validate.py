import pytest

from metrontagger.validate import SchemaVersion, ValidateMetadata


@pytest.mark.parametrize(
    ("xml_content", "schema_version", "expected_result"),
    [
        (b"<ComicInfo></ComicInfo>", SchemaVersion.ci_v1, True),
        (b"<ComicInfo></ComicInfo>", SchemaVersion.ci_v2, True),
        (
            b"<?xml version='1.0' encoding='UTF-8'?><MetronInfo xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' "
            b"xsi:noNamespaceSchemaLocation='MetronInfo.xsd'><Publisher><Name>Foo</Name></Publisher><Number>1</Number"
            b"><Series><Name>Bar</Name></Series></MetronInfo>",
            SchemaVersion.mi_v1,
            True,
        ),
        (b"<Invalid></Invalid>", SchemaVersion.ci_v1, False),
    ],
    ids=[
        "valid_ci_v1",
        "invalid_ci_v2",
        "valid_mi_v1",
        "invalid_schema",
    ],
)
def test_is_valid(xml_content, schema_version, expected_result):
    # Arrange
    validator = ValidateMetadata(xml_content)

    # Act
    result = validator._is_valid(schema_version)

    # Assert
    assert result == expected_result


@pytest.mark.parametrize(
    ("xml_content", "expected_version"),
    [
        (b"<ComicInfo></ComicInfo>", SchemaVersion.ci_v2),
        (
            b"<?xml version='1.0' encoding='UTF-8'?><MetronInfo xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' "
            b"xsi:noNamespaceSchemaLocation='MetronInfo.xsd'><Publisher><Name>Foo</Name></Publisher><Number>1</Number"
            b"><Series><Name>Bar</Name></Series></MetronInfo>",
            SchemaVersion.mi_v1,
        ),
    ],
    ids=[
        "valid_ci_v2",
        "valid_mi_v1",
    ],
)
def test_validate(xml_content, expected_version):
    # Arrange
    validator = ValidateMetadata(xml_content)

    # Act
    result = validator.validate()

    # Assert
    assert result == expected_version


@pytest.mark.parametrize(
    ("schema_version", "expected_path"),
    [
        (SchemaVersion.ci_v1, "metrontagger.schema.comicinfo.v1/ComicInfo.xsd"),
        (SchemaVersion.ci_v2, "metrontagger.schema.comicinfo.v2/ComicInfo.xsd"),
        (SchemaVersion.mi_v1, "metrontagger.schema.metroninfo.v1/MetronInfo.xsd"),
        (SchemaVersion.Unknown, None),
    ],
    ids=[
        "ci_v1_path",
        "ci_v2_path",
        "mi_v1_path",
        "unknown_version",
    ],
)
def test_get_xsd(schema_version, expected_path):
    # Act
    result = ValidateMetadata._get_xsd(schema_version)

    # Assert
    if expected_path is None:
        assert result is None
    else:
        assert result.name == expected_path.split("/")[-1]
