"""Map Metron API issue responses to darkseid Metadata."""

from __future__ import annotations

__all__ = ["MetadataMapper"]

from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING

from darkseid.issue_string import IssueString
from darkseid.metadata import (
    GTIN,
    AgeRatings,
    AlternativeNames,
    Arc,
    Basic,
    Credit,
    InfoSources,
    Links,
    Metadata,
    Notes,
    Price,
    Publisher,
    Role,
    Series,
    Universe,
)

from metrontagger import __version__

if TYPE_CHECKING:
    from mokkari.schemas.generic import GenericItem
    from mokkari.schemas.issue import Credit as MokkariCredit, Issue

# Rating mappings for age ratings
RATING_MAPPINGS = {
    ("everyone", "cca"): ("Everyone", "Everyone"),
    ("teen",): ("Teen", "Teen"),
    ("teen plus",): ("Teen Plus", "Teen"),
    ("mature",): ("Mature", "Mature 17+"),
}


class MetadataMapper:
    """Handles mapping of API responses to metadata objects."""

    @staticmethod
    def create_resource_list(resource) -> list[Basic]:
        """Create a list of Basic objects from a given resource."""
        return [Basic(r.name, r.id) for r in resource]

    @staticmethod
    def create_arc_list(resource) -> list[Arc]:
        """Create a list of Arc objects from a given resource."""
        return [Arc(item.name, item.id) for item in resource]

    @staticmethod
    def create_notes(issue_id: int) -> Notes:
        """Create a note for an issue."""
        now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
        metron_info_note = (
            f"Tagged with MetronTagger-{__version__} using info from Metron on {now_date}."
        )
        comic_rack_note = f"{metron_info_note} [issue_id:{issue_id}]"
        return Notes(metron_info=metron_info_note, comic_rack=comic_rack_note)

    @staticmethod
    def create_role_list(roles: list[GenericItem]) -> list[Role]:
        """Create a list of Role objects from a list of GenericItem objects."""
        return [Role(r.name, r.id) for r in roles]

    @classmethod
    def add_credits_to_metadata(
        cls, meta_data: Metadata, credits_resp: list[MokkariCredit]
    ) -> Metadata:
        """Add credits to metadata."""
        for c in credits_resp:
            roles = cls.create_role_list(c.role) if c.role else []
            meta_data.add_credit(Credit(c.creator, roles, c.id))
        return meta_data

    @staticmethod
    def map_ratings(rating: str) -> AgeRatings:
        """Map a rating string to a standardized format."""
        age_rating = rating.lower()

        for rating_keys, (metron_rating, comic_rack_rating) in RATING_MAPPINGS.items():
            if age_rating in rating_keys:
                return AgeRatings(metron_info=metron_rating, comic_rack=comic_rack_rating)

        return AgeRatings(metron_info="Unknown", comic_rack="Unknown")

    @staticmethod
    def _set_info_sources(md: Metadata, resp: Issue) -> None:
        """Set information sources for metadata."""
        alt_info_sources = []
        if resp.cv_id:
            alt_info_sources.append(InfoSources("Comic Vine", resp.cv_id))
        if resp.gcd_id:
            alt_info_sources.append(InfoSources("Grand Comics Database", resp.gcd_id))

        # Should always have Metron as a primary source
        md.info_source = [InfoSources("Metron", resp.id, True), *alt_info_sources]

    @staticmethod
    def _set_series_info(md: Metadata, resp: Issue) -> None:
        """Set series information for metadata."""
        md.series = Series(
            id_=resp.series.id,
            name=resp.series.name,
            alternative_names=[AlternativeNames(name=n) for n in resp.series.alt_names],
            sort_name=resp.series.sort_name,
            volume=resp.series.volume,
            format=resp.series.series_type.name,
            start_year=resp.series.year_began,
            language=resp.series.language,
        )

    @classmethod
    def _set_basic_issue_info(cls, md: Metadata, resp: Issue) -> None:
        """Set basic issue information for metadata."""
        md.issue = IssueString(resp.number).as_string() if resp.number else None
        md.alternate_number = resp.alt_number
        md.cover_date = resp.cover_date
        md.store_date = resp.store_date
        md.comments = resp.desc
        md.notes = cls.create_notes(resp.id)
        md.modified = resp.modified

    @staticmethod
    def _set_publisher_info(md: Metadata, resp: Issue) -> None:
        """Set publisher information for metadata."""
        if resp.publisher:
            md.publisher = Publisher(resp.publisher.name, resp.publisher.id)
            if resp.imprint:
                md.publisher.imprint = Basic(resp.imprint.name, resp.imprint.id)

    @staticmethod
    def _convert_gtin_to_int(value: str) -> int | None:
        """Convert a GTIN string to an integer, returning None if invalid.

        Args:
            value: The GTIN string to convert.

        Returns:
            The GTIN as an integer, or None if conversion fails.
        """
        with suppress(ValueError, TypeError):
            return int(value)
        return None

    @classmethod
    def _set_gtin_info(cls, md: Metadata, resp: Issue) -> None:
        """Set GTIN information for metadata."""
        isbn = cls._convert_gtin_to_int(resp.isbn) if resp.isbn else None
        upc = cls._convert_gtin_to_int(resp.upc) if resp.upc else None

        if isbn or upc:
            md.gtin = GTIN(upc=upc, isbn=isbn)

    @staticmethod
    def _set_community_rating(md: Metadata, resp: Issue) -> None:
        """Set community rating information for metadata."""
        if resp.average_rating:
            md.community_rating = resp.average_rating
            md.rating_count = resp.rating_count

    @classmethod
    def _set_optional_metadata(cls, md: Metadata, resp: Issue) -> None:
        """Set optional collections and lists for metadata."""
        if resp.story_titles:
            md.stories = [Basic(story) for story in resp.story_titles]
        if resp.collection_title:
            md.collection_title = resp.collection_title
        if resp.characters:
            md.characters = cls.create_resource_list(resp.characters)
        if resp.teams:
            md.teams = cls.create_resource_list(resp.teams)
        if resp.arcs:
            md.story_arcs = cls.create_arc_list(resp.arcs)
        if resp.series.genres:
            md.genres = cls.create_resource_list(resp.series.genres)
        if resp.reprints:
            md.reprints = [Basic(r.issue, r.id) for r in resp.reprints]
        if resp.universes:
            md.universes = [Universe(uni.name, uni.id) for uni in resp.universes]
        if resp.credits:
            md = cls.add_credits_to_metadata(md, resp.credits)
        if resp.rating:
            md.age_rating = cls.map_ratings(resp.rating.name)
        if resp.resource_url:
            md.web_link = [Links(str(resp.resource_url), True)]
        if resp.price:
            md.prices = [Price(resp.price, resp.price_currency)]
        cls._set_community_rating(md, resp)

    @classmethod
    def map_response_to_metadata(cls, resp: Issue) -> Metadata:
        """Map response data to metadata."""
        md = Metadata()

        cls._set_info_sources(md, resp)
        cls._set_series_info(md, resp)
        cls._set_basic_issue_info(md, resp)
        cls._set_publisher_info(md, resp)
        cls._set_optional_metadata(md, resp)
        cls._set_gtin_info(md, resp)

        return md
