"""Class to validate a comic archive ComicInfo.xml."""
from enum import Enum, auto, unique
from importlib.resources import path
from io import BytesIO
from pathlib import Path

from lxml import etree as et


@unique
class SchemaVersion(Enum):
    v1 = auto()
    v2 = auto()
    Unknown = auto()


class ValidateComicInfo:
    """Class to verify comic archive ComicInfo XML."""

    def __init__(self, ci_xml: bytes) -> None:
        self.comic_info_xml = ci_xml

    @staticmethod
    def _get_xsd(schema_version: SchemaVersion) -> Path | None:
        """Method to return path of CI Schema."""
        if schema_version == SchemaVersion.v1:
            with path("metrontagger.schema.v1", "ComicInfo.xsd") as xsd:
                return xsd
        elif schema_version == SchemaVersion.v2:
            with path("metrontagger.schema.v2", "ComicInfo.xsd") as xsd:
                return xsd
        else:
            return None

    def _is_valid(self, schema_version: SchemaVersion) -> bool:
        """Method to validate CI XML."""
        xsd_path = self._get_xsd(schema_version)
        if xsd_path is None:
            return False
        xmlschema_doc = et.parse(xsd_path)
        xmlschema = et.XMLSchema(xmlschema_doc)
        xml_doc = et.parse(BytesIO(self.comic_info_xml))
        return xmlschema.validate(xml_doc)

    def validate(self):
        return next(
            (
                schema_version
                for schema_version in [SchemaVersion.v2, SchemaVersion.v1]
                if self._is_valid(schema_version)
            ),
            SchemaVersion.Unknown,
        )
