"""Class to validate a comic archive ComicInfo.xml."""

from __future__ import annotations

from enum import Enum, auto, unique
from importlib.resources import as_file, files
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from lxml import etree as et


@unique
class SchemaVersion(Enum):
    """Enumeration of schema versions.

    This class defines different schema versions for ComicInfo XML validation.
    """

    v1 = auto()
    v2 = auto()
    Unknown = auto()


class ValidateComicInfo:
    """Class for validating ComicInfo XML.

    This class provides methods to validate ComicInfo XML against different schema versions and determine the valid
    schema version.

    Args:
        ci_xml: bytes: The ComicInfo XML content to validate.

    Returns:
        None
    """

    def __init__(self: ValidateComicInfo, ci_xml: bytes) -> None:
        """Initialize the ValidateComicInfo object with ComicInfo XML content.

        This method sets the ComicInfo XML content for validation.
        """

        self.comic_info_xml = ci_xml

    @staticmethod
    def _get_xsd(schema_version: SchemaVersion) -> Path | None:
        """Get the path of the ComicInfo schema based on the schema version.

        This static method returns the path of the ComicInfo schema file corresponding to the provided schema version.


        Args:
            schema_version: SchemaVersion: The version of the schema to retrieve.

        Returns:
            Path | None: The path of the schema file or None if the schema version is unknown.
        """
        schema_paths = {
            SchemaVersion.v1: "metrontagger.schema.v1",
            SchemaVersion.v2: "metrontagger.schema.v2",
        }

        if schema_path := schema_paths.get(schema_version):
            with as_file(files(schema_path).joinpath("ComicInfo.xsd")) as xsd:
                return xsd
        else:
            return None

    def _is_valid(self: ValidateComicInfo, schema_version: SchemaVersion) -> bool:
        """Validate the ComicInfo XML against a specific schema version.

        This method validates the ComicInfo XML content against the schema corresponding to the provided schema version.

        Args:
            schema_version: SchemaVersion: The version of the schema to validate against.

        Returns:
            bool: True if the XML is valid according to the schema, False otherwise.
        """
        xsd_path = self._get_xsd(schema_version)
        if xsd_path is None:
            return False

        # Parse the XML schema once
        xmlschema = et.XMLSchema(et.parse(xsd_path))  # noqa: S320

        # Parse the XML document and validate
        xml_doc = et.parse(BytesIO(self.comic_info_xml))  # noqa: S320
        return xmlschema.validate(xml_doc)

    def validate(self: ValidateComicInfo) -> SchemaVersion:
        """
        Returns the highest valid schema version based on the given ValidateComicInfo instance.

        Returns:
            SchemaVersion: The highest valid schema version found.
        """

        return next(
            (
                schema_version
                for schema_version in [SchemaVersion.v2, SchemaVersion.v1]
                if self._is_valid(schema_version)
            ),
            SchemaVersion.Unknown,
        )
