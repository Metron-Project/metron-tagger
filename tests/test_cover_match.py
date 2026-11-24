"""Tests for CoverHashMatcher."""

import io
import random
from unittest.mock import Mock, patch

import pytest
from imagehash import hex_to_hash, phash
from mokkari.schemas.issue import CoverMatch
from PIL import ExifTags, Image, ImageDraw

from metrontagger.cover_match import (
    COVER_ACCEPT_DISTANCE,
    HALF_COVER_HAMMING_DISTANCE,
    HAMMING_DISTANCE,
    CoverHashMatcher,
)
from tests.fakes import (
    SEARCH_HASH,
    create_mock_base_issue,
    hash_at_distance,
)


def _make_image_bytes(size: tuple[int, int], seed: int = 0) -> bytes:
    """Create a PNG with a random noise pattern so phash values are distinctive."""
    rng = random.Random(seed)  # noqa: S311 - deterministic test data
    img = Image.new("L", size)
    img.putdata([rng.randint(0, 255) for _ in range(size[0] * size[1])])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_spread_bytes(left: bytes, right: bytes) -> bytes:
    """Join two page images side-by-side into a double-page spread."""
    with Image.open(io.BytesIO(left)) as left_img, Image.open(io.BytesIO(right)) as right_img:
        spread = Image.new("L", (left_img.width + right_img.width, left_img.height))
        spread.paste(left_img, (0, 0))
        spread.paste(right_img, (left_img.width, 0))
    buf = io.BytesIO()
    spread.save(buf, format="PNG")
    return buf.getvalue()


def _hash_hex(data: bytes) -> str:
    with Image.open(io.BytesIO(data)) as img:
        return str(phash(img))


@pytest.fixture
def _clear_cover_hash_cache():
    """Clear the cover-hash cache around tests that compute real cover hashes."""
    CoverHashMatcher.get_comic_cover_hashes_cached.cache_clear()
    yield
    CoverHashMatcher.get_comic_cover_hashes_cached.cache_clear()


@pytest.mark.parametrize(
    ("size", "expected"),
    [((650, 1000), False), ((1000, 1000), False), ((1150, 1000), False), ((1300, 1000), True)],
)
def test_cover_hash_matcher_is_double_spread(size, expected):
    """Only landscape images are treated as double-page spreads."""
    assert CoverHashMatcher.is_double_spread(Image.new("L", size)) is expected


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_single_cover():
    """A portrait cover yields a single hash."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = _make_image_bytes((65, 100))

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == 1


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_double_spread():
    """A landscape cover yields full, right-half, and left-half hashes."""
    left = _make_image_bytes((65, 100), seed=1)
    right = _make_image_bytes((65, 100), seed=2)
    mock_comic = Mock()
    mock_comic.get_page.return_value = _make_spread_bytes(left, right)

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == 3
    assert str(result[1]) == _hash_hex(right)
    assert str(result[2]) == _hash_hex(left)


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@pytest.mark.parametrize(("orientation", "expected_len"), [(1, 3), (6, 1), (8, 1)])
def test_cover_hash_matcher_get_comic_cover_hashes_exif_orientation(orientation, expected_len):
    """A landscape-stored cover that EXIF rotates to portrait isn't treated as a spread."""
    with Image.open(io.BytesIO(_make_image_bytes((130, 100)))) as img:
        exif = Image.Exif()
        exif[ExifTags.Base.Orientation] = orientation
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", exif=exif)
    mock_comic = Mock()
    mock_comic.get_page.return_value = buf.getvalue()

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == expected_len


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_jxl():
    """A JPEG XL cover is hashed when the optional `jxl` extra is installed."""
    pytest.importorskip("pillow_jxl")
    with Image.open(io.BytesIO(_make_image_bytes((65, 100)))) as img:
        buf = io.BytesIO()
        img.save(buf, format="JXL", lossless=True)
    mock_comic = Mock()
    mock_comic.get_page.return_value = buf.getvalue()

    result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
    assert len(result) == 1


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_corrupt_jxl():
    """A truncated JPEG XL cover yields no hashes instead of raising."""
    pytest.importorskip("pillow_jxl")
    with Image.open(io.BytesIO(_make_image_bytes((65, 100)))) as img:
        buf = io.BytesIO()
        img.save(buf, format="JXL", lossless=True)
    mock_comic = Mock()
    mock_comic.get_page.return_value = buf.getvalue()[: len(buf.getvalue()) // 2]

    with patch("metrontagger.ui.questionary.print"):
        assert CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic) == ()


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@patch("metrontagger.cover_match.Image.open", side_effect=RuntimeError("decode failed"))
def test_cover_hash_matcher_get_comic_cover_hash_runtime_error(_):  # noqa: PT019
    """A decoder RuntimeError (e.g. from pillow-jxl-plugin) yields no hashes."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = b"fake_image_data"

    with patch("metrontagger.ui.questionary.print"):
        assert CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic) == ()


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_get_comic_cover_hashes_no_page():
    """Missing cover page yields no hashes."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = None

    with patch("metrontagger.ui.questionary.print"):
        assert CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic) == ()


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@patch("metrontagger.cover_match.Image.open", side_effect=OSError("Invalid image"))
def test_cover_hash_matcher_get_comic_cover_hash_failure(_):  # noqa: PT019
    """Test cover hash calculation failure."""
    mock_comic = Mock()
    mock_comic.get_page.return_value = b"fake_image_data"

    with patch("metrontagger.ui.questionary.print"):
        result = CoverHashMatcher.get_comic_cover_hashes_cached(mock_comic)
        assert result == ()


@pytest.mark.parametrize(("bits", "expected"), [(5, True), (15, False)])
def test_cover_hash_matcher_is_within_hamming_distance(bits, expected):
    """A Metron hash matches if it's within HAMMING_DISTANCE of the cover."""
    with patch.object(
        CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=(SEARCH_HASH,)
    ):
        result = CoverHashMatcher.is_within_hamming_distance(Mock(), hash_at_distance(bits))
    assert result is expected


def test_cover_hash_matcher_is_within_hamming_distance_no_hashes():
    """No cover hashes means no match."""
    with patch.object(CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=()):
        assert CoverHashMatcher.is_within_hamming_distance(Mock(), "abcdef") is False


@pytest.mark.parametrize(
    ("full_distance", "half_distance", "expected"),
    [
        (HAMMING_DISTANCE, 40, True),  # Full cover within its limit
        (HAMMING_DISTANCE + 1, 40, False),  # Full cover just over its limit
        (40, HALF_COVER_HAMMING_DISTANCE, True),  # Half within its limit
        (40, HALF_COVER_HAMMING_DISTANCE + 1, False),  # Half just over its limit
    ],
)
def test_cover_hash_matcher_half_cover_uses_own_distance(
    full_distance, half_distance, expected
):
    """The full cover and the half-cover crops are each checked against their own limit."""
    # The cover hashes are the given distances from an all-zero Metron hash.
    full_hash = hex_to_hash(hash_at_distance(full_distance))
    half_hash = hex_to_hash(hash_at_distance(half_distance))

    with patch.object(
        CoverHashMatcher,
        "get_comic_cover_hashes_cached",
        return_value=(full_hash, half_hash, half_hash),
    ):
        assert (
            CoverHashMatcher.is_within_hamming_distance(Mock(), str(SEARCH_HASH)) is expected
        )


@pytest.mark.usefixtures("_clear_cover_hash_cache")
@pytest.mark.parametrize("front", ["right", "left"])
def test_cover_hash_matcher_double_spread_matches_single_cover(front):
    """A double-spread cover matches Metron's single front cover on either half."""
    back = _make_image_bytes((65, 100), seed=1)
    cover = _make_image_bytes((65, 100), seed=2)
    spread = (
        _make_spread_bytes(back, cover)
        if front == "right"
        else _make_spread_bytes(cover, back)
    )
    mock_comic = Mock()
    mock_comic.get_page.return_value = spread

    assert CoverHashMatcher.is_within_hamming_distance(mock_comic, _hash_hex(cover)) is True


@pytest.mark.usefixtures("_clear_cover_hash_cache")
def test_cover_hash_matcher_double_spread_no_match():
    """A double-spread cover doesn't match an unrelated cover."""
    spread = _make_spread_bytes(
        _make_image_bytes((65, 100), seed=1), _make_image_bytes((65, 100), seed=2)
    )
    mock_comic = Mock()
    mock_comic.get_page.return_value = spread
    unrelated = _hash_hex(_make_image_bytes((65, 100), seed=3))

    assert CoverHashMatcher.is_within_hamming_distance(mock_comic, unrelated) is False


def test_cover_hash_matcher_filter_by_hamming_distance():
    """Test filtering issues by hamming distance."""
    mock_comic = Mock()
    issue1 = create_mock_base_issue()
    issue1.cover_hash = "hash1"
    issue2 = create_mock_base_issue()
    issue2.cover_hash = "hash2"

    with patch.object(
        CoverHashMatcher, "is_within_hamming_distance", side_effect=[True, False]
    ):
        result = CoverHashMatcher.filter_by_hamming_distance(mock_comic, [issue1, issue2])
        assert len(result) == 1
        assert result[0] == issue1


def test_get_search_hashes_single_cover():
    """A single cover is searched by its full-cover hash, at the cover-search limit."""
    with patch.object(
        CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=("full",)
    ):
        assert CoverHashMatcher.get_search_hashes(Mock()) == (("full", COVER_ACCEPT_DISTANCE),)


def test_get_search_hashes_double_spread():
    """A spread is searched by its right then left half, then as a whole.

    The halves are held to the half-cover limit, since one of them is the back
    cover. The whole cover comes last in case it's a genuinely landscape single cover.
    """
    with patch.object(
        CoverHashMatcher,
        "get_comic_cover_hashes_cached",
        return_value=("full", "right", "left"),
    ):
        assert CoverHashMatcher.get_search_hashes(Mock()) == (
            ("right", HALF_COVER_HAMMING_DISTANCE),
            ("left", HALF_COVER_HAMMING_DISTANCE),
            ("full", COVER_ACCEPT_DISTANCE),
        )


def test_get_search_hashes_no_cover():
    """No hashes when the cover can't be hashed."""
    with patch.object(CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=()):
        assert CoverHashMatcher.get_search_hashes(Mock()) == ()


def test_rank_by_distance():
    """Matches are ranked closest first; ones without a distance are dropped."""
    far = create_mock_base_issue(1, hash_at_distance(12))
    near = create_mock_base_issue(2, hash_at_distance(2))
    invalid = create_mock_base_issue(3, "abcd")
    matches = [
        CoverMatch.model_construct(issue=far, distance=12),
        CoverMatch.model_construct(issue=invalid, distance=None),
        CoverMatch.model_construct(issue=near, distance=2),
    ]
    ranked = CoverHashMatcher.rank_by_distance(matches)
    assert [(d, i.id) for d, i in ranked] == [(2, 2), (12, 1)]


@pytest.mark.parametrize(
    ("metron_hash", "expected"),
    [
        (hash_at_distance(5), 5),
        (None, None),
        ("", None),
        ("zzzzzzzzzzzzzzzz", None),
        ("abcd", None),
        ("0" * 64, None),
        (f" {hash_at_distance(5)}", None),
    ],
)
def test_cover_hash_distance(metron_hash, expected):
    """The distance is None when the Metron hash can't be compared.

    The cover search ranks by the distance mokkari's issues_by_cover_hash works out
    with the same hamming_distance, so these cases cover it too.
    """
    assert CoverHashMatcher.distance(SEARCH_HASH, metron_hash) == expected


def test_is_within_hamming_distance_wrong_size_hash():
    """A Metron hash of another size doesn't match, rather than raising TypeError."""
    with patch.object(
        CoverHashMatcher, "get_comic_cover_hashes_cached", return_value=(SEARCH_HASH,)
    ):
        assert CoverHashMatcher.is_within_hamming_distance(Mock(), "abcd") is False


def test_hash_cover_image_hashes_cover_as_displayed():
    """A portrait cover stored sideways with an EXIF rotation hashes as displayed.

    Metron's cover is upright, so hashing the stored (sideways) pixels wouldn't match.
    """
    portrait = Image.new("RGB", (100, 150), "white")
    draw = ImageDraw.Draw(portrait)
    draw.rectangle((10, 10, 60, 40), fill="black")
    draw.ellipse((30, 80, 90, 140), fill="gray")
    draw.line((0, 150, 100, 0), fill="black", width=5)
    stored = portrait.rotate(90, expand=True)
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # rotate 90 degrees clockwise to display
    buf = io.BytesIO()
    stored.save(buf, format="PNG", exif=exif)

    with Image.open(io.BytesIO(buf.getvalue())) as img:
        hashes = CoverHashMatcher.hash_cover_image(img)

    assert hashes == (phash(portrait.convert("L")),)
