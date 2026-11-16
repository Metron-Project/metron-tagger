"""Perceptual-hash matching of comic covers against Metron's cover hashes."""

from __future__ import annotations

__all__ = ["CoverHashMatcher"]

import io
import warnings
from functools import lru_cache
from logging import getLogger
from typing import TYPE_CHECKING

from imagehash import ImageHash, hex_to_hash, phash
from PIL import ExifTags, Image, ImageOps

from metrontagger.ui import UIPresenter

if TYPE_CHECKING:
    from darkseid.comic import Comic
    from mokkari.schemas.issue import BaseIssue

LOGGER = getLogger(__name__)

warnings.filterwarnings(
    "ignore", category=UserWarning
)  # Ignore 'UserWarning: Corrupt EXIF data' warnings

HAMMING_DISTANCE = 10
# Limit for the half-cover crops of a double-page spread, kept separate from
# HAMMING_DISTANCE so it can be tuned on its own. Real spread covers put the
# front-cover half at 6-10 from Metron's cover and the back-cover half at 28-38,
# so the normal limit separates them cleanly.
HALF_COVER_HAMMING_DISTANCE = 10
# Width/height ratio above which a cover is treated as a double-page spread.
# Single covers are ~0.65; two-page spreads are ~1.3. The margin above 1.0 keeps
# square-ish single covers from being split.
DOUBLE_SPREAD_ASPECT_RATIO = 1.2
# Cover search: Metron's cover_hash_near filter, narrowed by the filename's issue number
# and a cover-date range around its year. Tuned on 633 tagged comics: the correct issue
# was always the closest result; most were within 2 bits, while digital editions without
# the print cover's price/UPC box were 10-18 bits off. At 20 bits one comic whose number
# Metron writes differently ("16" vs "16.NOW") matched the wrong issue, so results are
# only accepted up to 18. The closest result must also lead the next one by
# COVER_ACCEPT_MARGIN bits (the closest correct leads seen were 2), so ties are never
# auto-picked. Finally, its series name must share a word with the filename's series or
# title: on 802 comics this was the only check that caught a wrong match (a CGC-slab
# photo whose closest cover was another publisher's issue with the same number), and it
# cost no correct ones.
COVER_SEARCH_MAX_DISTANCE = 20  # Metron's maximum cover_hash_max_distance
COVER_ACCEPT_DISTANCE = 18
COVER_ACCEPT_MARGIN = 2
# Filename years are often the release year, which can differ from the cover year.
COVER_YEAR_TOLERANCE = 1
# Filename years outside this range aren't treated as cover years: an odd parse such as
# "0000" would otherwise make an invalid date that Metron rejects, which stops the run.
COVER_YEAR_RANGE = range(1900, 2100)


class CoverHashMatcher:
    """Handles cover hash matching for comics."""

    @staticmethod
    def upright(img: Image.Image) -> Image.Image:
        """Return the image as displayed, applying any EXIF orientation rotation."""
        if img.getexif().get(ExifTags.Base.Orientation, 1) == 1:
            return img
        return ImageOps.exif_transpose(img)

    @staticmethod
    def is_double_spread(img: Image.Image) -> bool:
        """Return True if the image is clearly landscape, i.e. likely a two-page spread."""
        width, height = img.size
        return width / height > DOUBLE_SPREAD_ASPECT_RATIO

    @staticmethod
    def hash_cover_image(img: Image.Image) -> tuple[ImageHash, ...]:
        """Hash a cover image, including each half if it's a double-page spread.

        A double-spread cover usually has the front cover on the right half
        (left half for right-to-left books like manga), while Metron typically
        stores only the single front cover, so each half is hashed as well.
        The split is exactly at the midpoint: phash is sensitive to where the
        cut lands, and even a 1px shift can change the hash by a few bits.
        """
        # Hash and judge the shape as displayed, so a portrait cover stored sideways
        # with an EXIF rotation matches Metron's upright cover and isn't mistaken for
        # a spread. phash converts to grayscale itself; doing it once up front avoids
        # repeating the full-size conversion for each half-cover crop.
        upright = CoverHashMatcher.upright(img)
        gray = upright.convert("L")
        hashes = [phash(gray)]
        if CoverHashMatcher.is_double_spread(upright):
            width, height = gray.size
            mid = width // 2
            right = gray.crop((mid, 0, width, height))
            left = gray.crop((0, 0, mid, height))
            hashes.extend((phash(right), phash(left)))
        return tuple(hashes)

    @staticmethod
    @lru_cache(maxsize=128)
    def get_comic_cover_hashes_cached(comic: Comic) -> tuple[ImageHash, ...]:
        """Get the image hash(es) of a comic cover.

        Args:
            comic: The Comic object representing the comic.

        Returns:
            A tuple of cover hashes: the full cover, plus the right and left
            halves if the cover is a double-page spread. Empty if unable to
            calculate.
        """
        cover = comic.get_page(0)
        if cover is None:
            UIPresenter.print_error("Unable to get cover hash.")
            return ()
        try:
            with Image.open(io.BytesIO(cover)) as img:
                return CoverHashMatcher.hash_cover_image(img)
        except (OSError, RuntimeError):
            # pillow-jxl-plugin raises RuntimeError on corrupt/truncated JXL data.
            UIPresenter.print_error("Unable to get cover hash.")
            return ()

    @classmethod
    def is_within_hamming_distance(cls, comic: Comic, metron_hash: str | None = None) -> bool:
        """Check if the comic cover matches the Metron cover hash.

        The full cover must be within HAMMING_DISTANCE; the half-cover crops of a
        double-page spread must be within HALF_COVER_HAMMING_DISTANCE.
        """
        comic_hashes = cls.get_comic_cover_hashes_cached(comic)
        if not comic_hashes:
            return False
        full_hash, *half_hashes = comic_hashes
        full_distance = cls.distance(full_hash, metron_hash)
        if full_distance is None:
            LOGGER.debug("Can't compare %s with cover hash %r", comic.name, metron_hash)
            return False
        if full_distance <= HAMMING_DISTANCE:
            return True
        return any(
            (half_distance := cls.distance(half_hash, metron_hash)) is not None
            and half_distance <= HALF_COVER_HAMMING_DISTANCE
            for half_hash in half_hashes
        )

    @staticmethod
    def distance(comic_hash: ImageHash, metron_hash: str | None) -> int | None:
        """Return the Hamming distance between a comic's hash and a Metron cover hash.

        Returns None if the Metron hash is missing, malformed, or a different size,
        so it can't be compared.
        """
        if not metron_hash:
            return None
        try:
            return int(comic_hash - hex_to_hash(metron_hash))
        except (TypeError, ValueError):
            return None

    @classmethod
    def get_search_hashes(cls, comic: Comic) -> tuple[tuple[ImageHash, int], ...]:
        """Get the cover hash(es) to search Metron with, in the order to try them.

        Each comes with the distance up to which a match on it may be accepted.
        Metron stores only the single front cover, so for a double-page spread its
        halves come first: the right half (the usual front cover), then the left half
        (the front cover of right-to-left books like manga). They're held to
        HALF_COVER_HAMMING_DISTANCE, as in is_within_hamming_distance, since one of
        them is the back cover. The whole cover comes last, held to
        COVER_ACCEPT_DISTANCE, in case it's a genuinely landscape single cover.
        """
        comic_hashes = cls.get_comic_cover_hashes_cached(comic)
        if not comic_hashes:
            return ()
        full, *halves = comic_hashes
        return (
            *((half, HALF_COVER_HAMMING_DISTANCE) for half in halves),
            (full, COVER_ACCEPT_DISTANCE),
        )

    @classmethod
    def rank_by_distance(
        cls, search_hash: ImageHash, issues: list[BaseIssue]
    ) -> list[tuple[int, BaseIssue]]:
        """Pair each issue with its cover's distance from search_hash, closest first.

        Issues whose cover hash is missing, malformed, or a different size are dropped.
        """
        ranked = []
        for issue in issues:
            distance = cls.distance(search_hash, issue.cover_hash)
            if distance is None:
                LOGGER.debug("Skipping issue %s with invalid cover hash", issue.id)
            else:
                ranked.append((distance, issue))
        return sorted(ranked, key=lambda pair: pair[0])

    @classmethod
    def filter_by_hamming_distance(
        cls, comic: Comic, issue_list: list[BaseIssue]
    ) -> list[BaseIssue]:
        """Get the list of BaseIssue objects within the specified Hamming distance."""
        return [
            item
            for item in issue_list
            if cls.is_within_hamming_distance(comic, item.cover_hash)
        ]
