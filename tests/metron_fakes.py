"""Fake Metron API objects shared by the talker, cover and mapper tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

from imagehash import hex_to_hash

tzinfo = timezone(timedelta(hours=-5))


def create_mock_base_issue(issue_id=123, cover_hash="abcdef123456", series_name="Test Comic"):
    """Create a mock BaseIssue object."""
    issue = Mock()
    issue.id = issue_id
    issue.issue_name = f"{series_name} #1"
    issue.series.name = series_name
    issue.cover_date = datetime(2023, 1, 1, tzinfo=tzinfo).date()
    issue.cover_hash = cover_hash
    return issue


def create_mock_issue_response(  # noqa: PLR0913, PLR0917 - mirrors the Issue fields tests vary
    isbn=None,
    upc=None,
    average_rating=Decimal("4.25"),
    rating_count=8,
    alt_number=None,
    alt_names=None,
    language="en",
):
    """Create a mock Issue response object."""

    issue = Mock()
    issue.id = 123
    issue.number = "1"
    issue.alt_number = alt_number
    issue.cover_date = datetime(2023, 1, 1, tzinfo=tzinfo).date()
    issue.store_date = datetime(2023, 1, 15, tzinfo=tzinfo).date()
    issue.desc = "Test description"
    issue.modified = datetime(2023, 1, 1, tzinfo=tzinfo)
    issue.cv_id = 456
    issue.gcd_id = None
    issue.collection_title = None
    issue.story_titles = ["Main Story"]
    issue.rating = Mock()
    issue.rating.name = "Teen"
    issue.resource_url = "https://example.com/issue/123"
    issue.price = Decimal("3.99")
    issue.price_currency = "USD"
    issue.isbn = isbn
    issue.upc = upc
    issue.average_rating = average_rating
    issue.rating_count = rating_count

    # Series mock
    issue.series = Mock()
    issue.series.name = "Test Series"
    issue.series.id = 1
    issue.series.sort_name = "Test Series"
    issue.series.alt_names = alt_names if alt_names is not None else []
    issue.series.volume = 1
    issue.series.series_type = Mock()
    issue.series.series_type.name = "Regular"
    issue.series.year_began = 2023
    issue.series.language = language
    issue.series.genres = [Mock(name="Action", id=1)]

    # Publisher mock
    issue.publisher = Mock()
    issue.publisher.name = "Test Publisher"
    issue.publisher.id = 1
    issue.imprint = None

    # Other collections
    issue.characters = [Mock(name="Hero", id=1)]
    issue.teams = [Mock(name="Team", id=1)]
    issue.arcs = [Mock(name="Arc", id=1)]
    issue.reprints = []
    issue.universes = [Mock(name="Universe", id=1)]
    issue.credits = [Mock(creator="Writer", role=[Mock(name="Writer", id=1)], id=1)]

    return issue


SEARCH_HASH = hex_to_hash("0000000000000000")


def hash_at_distance(bits: int) -> str:
    """A cover hash exactly `bits` bits from SEARCH_HASH."""
    return f"{(1 << bits) - 1:016x}"
