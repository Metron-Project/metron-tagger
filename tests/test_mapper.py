"""Tests for MetadataMapper."""

import xml.etree.ElementTree as ET
from decimal import Decimal
from unittest.mock import Mock

from darkseid.metadata import Basic, Metadata, MetronInfo

from metrontagger.mapper import MetadataMapper
from tests.fakes import (
    create_mock_issue_response,
)


def test_metadata_mapper_create_resource_list():
    """Test creating resource list."""
    resources = [Mock(name="Resource1", id=1), Mock(name="Resource2", id=2)]
    result = MetadataMapper.create_resource_list(resources)
    assert len(result) == 2
    assert all(isinstance(item, Basic) for item in result)


def test_metadata_mapper_map_ratings():
    """Test rating mapping."""
    test_cases = [
        ("Everyone", ("Everyone", "Everyone")),
        ("Teen", ("Teen", "Teen")),
        ("Teen Plus", ("Teen Plus", "Teen")),
        ("Mature", ("Mature", "Mature 17+")),
        ("Unknown Rating", ("Unknown", "Unknown")),
    ]

    for input_rating, expected in test_cases:
        result = MetadataMapper.map_ratings(input_rating)
        assert result.metron_info == expected[0]
        assert result.comic_rack == expected[1]


def test_metadata_mapper_map_response_to_metadata():
    """Test mapping response to metadata."""

    resp = create_mock_issue_response()
    result = MetadataMapper.map_response_to_metadata(resp)

    assert isinstance(result, Metadata)
    assert result.series is not None
    assert result.series.name == "Test Series"
    assert result.issue == "1"
    assert result.info_source is not None
    assert len(result.info_source) >= 1
    assert result.info_source[0].name == "Metron"
    # Verify price is mapped
    assert result.prices is not None
    assert len(result.prices) == 1
    assert result.prices[0].amount == Decimal("3.99")
    assert result.prices[0].currency == "USD"
    # Verify community rating is mapped
    assert result.community_rating == Decimal("4.25")
    assert result.rating_count == 8


def test_metadata_mapper_map_response_to_metadata_without_average_rating():
    """Test mapping response to metadata when no average rating is present."""

    resp = create_mock_issue_response(average_rating=None, rating_count=0)
    result = MetadataMapper.map_response_to_metadata(resp)

    assert result.community_rating is None
    assert result.rating_count is None


def test_metadata_mapper_map_response_to_metadata_with_alternate_number():
    """Test mapping response to metadata when an alternate number is present."""

    resp = create_mock_issue_response(alt_number="1AU")
    result = MetadataMapper.map_response_to_metadata(resp)

    assert result.alternate_number == "1AU"


def test_metadata_mapper_map_response_to_metadata_without_alternate_number():
    """Test mapping response to metadata when no alternate number is present."""

    resp = create_mock_issue_response(alt_number=None)
    result = MetadataMapper.map_response_to_metadata(resp)

    assert result.alternate_number is None


def test_metadata_mapper_set_basic_issue_info_with_alternate_number():
    """Test setting basic issue info maps the alternate number."""
    resp = create_mock_issue_response(alt_number="25")
    md = Metadata()
    MetadataMapper._set_basic_issue_info(md, resp)

    assert md.alternate_number == "25"


def test_metadata_mapper_set_basic_issue_info_without_alternate_number():
    """Test setting basic issue info when no alternate number is present."""
    resp = create_mock_issue_response(alt_number=None)
    md = Metadata()
    MetadataMapper._set_basic_issue_info(md, resp)

    assert md.alternate_number is None


def test_metadata_mapper_set_series_info_with_alt_names():
    """Test setting series info maps alternate names."""
    resp = create_mock_issue_response(alt_names=["Alt Name One", "Alt Name Two"])
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert md.series is not None
    assert [n.name for n in md.series.alternative_names] == [
        "Alt Name One",
        "Alt Name Two",
    ]


def test_metadata_mapper_set_series_info_without_alt_names():
    """Test setting series info when no alternate names are present."""
    resp = create_mock_issue_response(alt_names=[])
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert md.series is not None
    assert md.series.alternative_names == []


def test_metadata_mapper_set_series_info_with_language():
    """Test setting series info maps the series language."""
    resp = create_mock_issue_response(language="en")
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert md.series is not None
    assert md.series.language == "en"


def test_metadata_mapper_set_series_info_without_language():
    """Test setting series info when no language is present."""
    resp = create_mock_issue_response(language=None)
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    assert md.series is not None
    assert md.series.language is None


def test_metadata_mapper_convert_gtin_to_int_valid():
    """Test converting valid GTIN string to int."""
    result = MetadataMapper._convert_gtin_to_int("9781234567890")
    assert result == 9781234567890
    assert isinstance(result, int)


def test_metadata_mapper_convert_gtin_to_int_invalid_string():
    """Test converting invalid GTIN string returns None."""
    result = MetadataMapper._convert_gtin_to_int("invalid")
    assert result is None


def test_metadata_mapper_convert_gtin_to_int_none():
    """Test converting None returns None."""
    result = MetadataMapper._convert_gtin_to_int(None)
    assert result is None


def test_metadata_mapper_convert_gtin_to_int_empty_string():
    """Test converting empty string returns None."""
    result = MetadataMapper._convert_gtin_to_int("")
    assert result is None


def test_metadata_mapper_set_gtin_info_both_isbn_and_upc():
    """Test setting GTIN info with both ISBN and UPC."""
    resp = create_mock_issue_response(isbn="9781234567890", upc="12345678901")
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is not None
    assert md.gtin.isbn == 9781234567890
    assert md.gtin.upc == 12345678901


def test_metadata_mapper_set_gtin_info_isbn_only():
    """Test setting GTIN info with ISBN only."""
    resp = create_mock_issue_response(isbn="9781234567890", upc=None)
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is not None
    assert md.gtin.isbn == 9781234567890
    assert md.gtin.upc is None


def test_metadata_mapper_set_gtin_info_upc_only():
    """Test setting GTIN info with UPC only."""
    resp = create_mock_issue_response(isbn=None, upc="12345678901")
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is not None
    assert md.gtin.isbn is None
    assert md.gtin.upc == 12345678901


def test_metadata_mapper_set_gtin_info_neither():
    """Test setting GTIN info with neither ISBN nor UPC."""
    resp = create_mock_issue_response(isbn=None, upc=None)
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    assert md.gtin is None


def test_metadata_mapper_set_gtin_info_invalid_values():
    """Test setting GTIN info with invalid values."""
    resp = create_mock_issue_response(isbn="invalid", upc="also_invalid")
    md = Metadata()
    MetadataMapper._set_gtin_info(md, resp)

    # Both values are invalid, so gtin should not be set
    assert md.gtin is None


def test_metadata_mapper_map_response_to_metadata_with_gtin():
    """Test mapping response to metadata includes GTIN data."""
    resp = create_mock_issue_response(isbn="9781234567890", upc="12345678901")
    result = MetadataMapper.map_response_to_metadata(resp)

    assert isinstance(result, Metadata)
    assert result.gtin is not None
    assert result.gtin.isbn == 9781234567890
    assert result.gtin.upc == 12345678901


def test_metadata_mapper_series_language_written_to_metron_info_xml():
    """Test that the series language mapped from a response ends up as the
    Series element's ``lang`` attribute when writing MetronInfo.xml."""
    resp = create_mock_issue_response(language="en")
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    xml_string = MetronInfo().string_from_metadata(md)
    root = ET.fromstring(xml_string)  # noqa: S314

    series_node = root.find("Series")
    assert series_node is not None
    assert series_node.get("lang") == "en"


def test_metadata_mapper_series_without_language_omits_lang_attribute():
    """Test that a missing series language leaves the ``lang`` attribute unset
    when writing MetronInfo.xml."""
    resp = create_mock_issue_response(language=None)
    md = Metadata()
    MetadataMapper._set_series_info(md, resp)

    xml_string = MetronInfo().string_from_metadata(md)
    root = ET.fromstring(xml_string)  # noqa: S314

    series_node = root.find("Series")
    assert series_node is not None
    assert series_node.get("lang") is None
