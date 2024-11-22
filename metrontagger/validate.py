"""Class to validate a comic archive ComicInfo.xml."""

from __future__ import annotations

from enum import Enum, auto, unique
from importlib.resources import as_file, files
from io import BytesIO
from typing import TYPE_CHECKING

from xmlschema import XMLSchema10, XMLSchema11, XMLSchemaValidationError

if TYPE_CHECKING:
    from pathlib import Path


@unique
class SchemaVersion(Enum):
    """Enumeration of schema versions.

    This class defines different schema versions for XML validation.
    """

    ci_v1 = auto()
    ci_v2 = auto()
    mi_v1 = auto()
    Unknown = auto()


class ValidateMetadata:
    """Class for validating XML.

    This class provides methods to validate XML against different schema versions and determine the valid
    schema version.

    Args:
        xml: bytes: The XML content to validate.

    Returns:
        None
    """

    def __init__(self: ValidateMetadata, xml: bytes) -> None:
        """Initialize the ValidateMetadata object with XML content.

        This method sets the XML content for validation.
        """

        self.xml = xml

    @staticmethod
    def _get_xsd(schema_version: SchemaVersion) -> Path | None:
        """Get the path of the schema based on the schema version.

        This static method returns the path of the xsd schema file corresponding to the provided schema version.

        Args:
            schema_version: SchemaVersion: The version of the schema to retrieve.

        Returns:
            Path | None: The path of the schema file or None if the schema version is unknown.
        """
        if schema_version == SchemaVersion.Unknown:
            return None

        schema_paths = {
            SchemaVersion.ci_v1: "metrontagger.schema.comicinfo.v1",
            SchemaVersion.ci_v2: "metrontagger.schema.comicinfo.v2",
            SchemaVersion.mi_v1: "metrontagger.schema.metroninfo.v1",
        }

        if schema_path := schema_paths.get(schema_version):
            file_name = (
                "ComicInfo.xsd"
                if schema_version in [SchemaVersion.ci_v1, SchemaVersion.ci_v2]
                else "MetronInfo.xsd"
            )
            with as_file(files(schema_path).joinpath(file_name)) as xsd:
                return xsd
        return None

    def _is_valid(self: ValidateMetadata, schema_version: SchemaVersion) -> bool:
        """Validate the XML against a specific schema version.

        This method validates the XML content against the schema corresponding to the provided schema version.

        Args:
            schema_version: SchemaVersion: The version of the schema to validate against.

        Returns:
            bool: True if the XML is valid according to the schema, False otherwise.
        """
        xsd_path = self._get_xsd(schema_version)
        if xsd_path is None:
            return False

        if schema_version == SchemaVersion.mi_v1:
            schema = XMLSchema11(xsd_path)
        elif schema_version in [SchemaVersion.ci_v1, SchemaVersion.ci_v2]:
            schema = XMLSchema10(xsd_path)
        else:
            return False

        try:
            schema.validate(BytesIO(self.xml))
        except XMLSchemaValidationError:
            return False

        return True

    def validate(self: ValidateMetadata) -> SchemaVersion:
        """
        Returns the highest valid schema version based on the given ValidateMetadata instance.

        Returns:
            SchemaVersion: The highest valid schema version found.
        """

        return next(
            (
                schema_version
                for schema_version in [
                    SchemaVersion.ci_v2,
                    SchemaVersion.ci_v1,
                    SchemaVersion.mi_v1,
                ]
                if self._is_valid(schema_version)
            ),
            SchemaVersion.Unknown,
        )
