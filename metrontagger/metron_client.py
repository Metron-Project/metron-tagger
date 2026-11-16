"""Metron API access: rate limiting, retries and API error handling."""

from __future__ import annotations

__all__ = ["MetronClient"]

import time
from http import HTTPStatus
from logging import getLogger
from typing import TYPE_CHECKING, Self, TypeVar

import mokkari
import questionary
from mokkari.exceptions import ApiError, RateLimitError
from mokkari.rate_limit import HeaderPacedRateLimiter
from requests.exceptions import HTTPError

from metrontagger import __version__
from metrontagger.ui import UIPresenter

if TYPE_CHECKING:
    from collections.abc import Callable

    from mokkari.rate_limit import RateLimiter
    from mokkari.session import Session
    from redis import Redis

LOGGER = getLogger(__name__)

RATE_LIMIT_AUTO_RETRY_THRESHOLD = 60  # seconds
RATE_LIMIT_RETRY_BUFFER = 2  # seconds added to retry_after to account for clock skew
# The first try plus up to two retries: one after the first rate limit, and one more if
# the retry hits a short rate limit too.
MAX_API_ATTEMPTS = 3
# Bound Redis connects/reads so an unreachable or stalled server raises a RedisError
# instead of hanging; redis-py waits indefinitely by default.
REDIS_SOCKET_TIMEOUT = 5  # seconds

# HTTP statuses where retrying (or continuing with other files) is pointless: bad
# credentials or a malformed request will fail identically on every subsequent call.
FATAL_API_STATUS_CODES = {HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED}

# Type variable for generic API call return types
T = TypeVar("T")


class MetronClient:
    """A Metron API session with rate limiting and centralized error handling.

    API calls made through `call` are retried after short rate limits, and the user is
    asked whether to wait out long ones. Errors that would make every later request
    fail too (bad credentials, a malformed request, an unusable Redis rate limiter, or
    the user declining to wait) set `stop_processing`, which callers check before
    starting more work.
    """

    def __init__(
        self,
        api_token: str,
        *,
        username: str | None = None,
        redis_url: str | None = None,
        ui: UIPresenter | None = None,
    ) -> None:
        """Create the Metron API session.

        When `redis_url` is given, API requests are paced by a Redis-backed rate limiter
        shared by every process using the same Metron account. Otherwise, or if Redis
        can't be used, they're paced by a local limiter that spreads requests evenly
        across Metron's rate-limit window.
        """
        self.ui = ui or UIPresenter()
        self._redis_client: Redis | None = None
        # Errors raised by the Redis rate limiter; empty unless one is in use, since
        # `redis` is an optional dependency.
        self._redis_errors: tuple[type[Exception], ...] = ()
        rate_limiter = (
            self._create_redis_rate_limiter(redis_url, username) if redis_url else None
        )
        if rate_limiter is None:
            rate_limiter = HeaderPacedRateLimiter()
        self.api: Session = mokkari.api(
            user_agent=f"Metron-Tagger/{__version__}",
            api_token=api_token,
            rate_limiter=rate_limiter,
        )
        self.stop_processing = False

    def _create_redis_rate_limiter(
        self, redis_url: str, username: str | None
    ) -> RateLimiter | None:
        """Create a Redis-backed rate limiter, or None to fall back to a local limiter.

        The shared rate-limit state is keyed by the Metron username, even when
        authenticating with an API token, since each application typically has its own
        token while the account's rate limit is shared across all of them.
        """
        if not username:
            self.ui.print_warning(
                "Redis rate limiting requires your Metron username to be set as 'user' in "
                "the [metron] section of your settings.ini, even when using an API token. "
                "Using the local rate limiter."
            )
            return None

        try:
            import redis  # noqa: PLC0415 - optional dependency
            from mokkari.redis_rate_limit import RedisRateLimiter  # noqa: PLC0415
        except ImportError:
            self.ui.print_warning(
                "Redis rate limiting requires the 'redis' extra (metron-tagger[redis]). "
                "Using the local rate limiter."
            )
            return None

        try:
            client = redis.Redis.from_url(
                redis_url,
                socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
            )
        except ValueError as e:
            self.ui.print_warning(
                f"Invalid Redis URL '{redis_url}': {e}. Using the local rate limiter."
            )
            return None

        try:
            client.ping()
        except redis.RedisError as e:
            client.close()
            self.ui.print_warning(
                f"Unable to connect to Redis at '{redis_url}': {e}. "
                "Using the local rate limiter."
            )
            return None

        self._redis_client = client
        self._redis_errors = (redis.RedisError,)
        return RedisRateLimiter(client, username)

    def close(self) -> None:
        """Close the Metron API session's pooled connections and any Redis client."""
        self.api.close()
        if self._redis_client is not None:
            self._redis_client.close()
            self._redis_client = None

    def __enter__(self) -> Self:
        """Enter the context manager, returning this client."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Exit the context manager, closing pooled connections."""
        self.close()

    @staticmethod
    def _get_http_status_code(error: ApiError) -> HTTPStatus | None:
        """Extract the underlying HTTP status code from an ApiError, if any.

        Mokkari's ApiError is a blanket exception for network errors, JSON
        decoding failures, and HTTP error responses alike, and doesn't expose
        the status code as an attribute. When it *was* raised from an HTTP
        error response though, it's chained with `raise ... from err`, so the
        status code can still be recovered from `__cause__`.
        """
        cause = error.__cause__
        if isinstance(cause, HTTPError) and cause.response is not None:
            return HTTPStatus(cause.response.status_code)
        return None

    def _handle_fatal_api_error(self, error: ApiError, error_context: str) -> bool:
        """Stop further processing if an ApiError is unrecoverable.

        A 400 or 401 response means every subsequent request will fail the
        same way (bad credentials or a malformed request), so continuing to
        process the remaining files is pointless.

        Returns:
            True if the error was fatal and has been handled, False otherwise.
        """
        status_code = self._get_http_status_code(error)
        if status_code not in FATAL_API_STATUS_CODES:
            return False

        LOGGER.error("%s: unrecoverable HTTP %s error: %s", error_context, status_code, error)
        if status_code == HTTPStatus.UNAUTHORIZED:
            msg = (
                "Metron authentication failed (HTTP 401). Check your username and "
                "password, or your API token. Stopping further processing."
            )
        else:
            msg = f"Metron rejected the request (HTTP 400): {error}. Stopping further processing."
        self.ui.print_error(msg)
        self.stop_processing = True
        return True

    def _handle_redis_error(self, error: Exception, error_context: str) -> None:
        """Stop further processing after the Redis rate limiter fails.

        Every request goes through the rate limiter, so once Redis is unavailable
        every subsequent request will fail the same way.
        """
        LOGGER.error("%s: Redis rate limiter error: %s", error_context, error)
        self.ui.print_error(
            f"Redis rate limiter error: {error}. Check your Redis server or remove "
            "'redis_url' from your settings. Stopping further processing."
        )
        self.stop_processing = True

    def _report_api_error(self, error: ApiError, context: str) -> None:
        """Report an ApiError, stopping further processing if it's unrecoverable."""
        if self._handle_fatal_api_error(error, context):
            return
        LOGGER.exception(context)
        self.ui.print_error(f"{context}: {error}")

    def _ask_to_wait(self, error: RateLimitError, retry_after: float) -> float | None:
        """Ask whether to wait out a long rate limit.

        Returns:
            How long to sleep before retrying, or None (and stop processing) if the
            user declines.
        """
        self.ui.print_warning(f"{error!s}")
        wait_start = time.monotonic()
        if not questionary.confirm("Do you want to wait and retry?", default=False).ask():
            self.stop_processing = True
            return None

        # Deduct time already spent waiting on the user's answer so the
        # total delay matches retry_after instead of stacking on top of it.
        elapsed = time.monotonic() - wait_start
        self.ui.print_info("Waiting to retry...")
        return max(0.0, retry_after - elapsed) + RATE_LIMIT_RETRY_BUFFER

    def _rate_limit_wait(self, error: RateLimitError, attempt: int) -> float | None:
        """Decide how long to wait before retrying after a rate limit.

        On the first attempt a short limit is waited out automatically and the user is
        asked about a long one. A retry only waits again for a short limit, and the last
        attempt never does.

        Returns:
            How long to sleep before retrying, or None to give up.
        """
        retry_after = getattr(error, "retry_after", 0) or 0
        is_short = 0 < retry_after < RATE_LIMIT_AUTO_RETRY_THRESHOLD

        if attempt == 0:
            LOGGER.debug("Rate limit exceeded: %s", error)
            if retry_after <= 0:
                self.ui.print_warning(f"{error!s}")
                return None
            if is_short:
                return retry_after + RATE_LIMIT_RETRY_BUFFER
            return self._ask_to_wait(error, retry_after)

        if is_short and attempt < MAX_API_ATTEMPTS - 1:
            LOGGER.debug("Rate limit hit on retry, waiting %s seconds", retry_after)
            return retry_after + RATE_LIMIT_RETRY_BUFFER

        LOGGER.debug("Rate limit hit on retry: %s", error)
        self.ui.print_error(f"Retry failed: {error!s}")
        return None

    def call(self, api_call: Callable[[], T], error_context: str = "API call") -> T | None:
        """Make an API call, retrying after rate limits and reporting any errors.

        A call is attempted up to MAX_API_ATTEMPTS times; see `_rate_limit_wait` for
        when a rate limit leads to another attempt. Any other error is reported and
        ends the call.

        Args:
            api_call: A callable that makes the API call.
            error_context: Describes the call in error messages. Errors on a retry are
                reported as "Retry failed".

        Returns:
            The result of the API call, or None if it didn't succeed.
        """
        context = error_context
        for attempt in range(MAX_API_ATTEMPTS):
            try:
                return api_call()
            except RateLimitError as e:
                delay = self._rate_limit_wait(e, attempt)
            except ApiError as e:
                self._report_api_error(e, context)
                return None
            except self._redis_errors as e:
                self._handle_redis_error(e, context)
                return None

            if delay is None:
                return None
            time.sleep(delay)
            context = "Retry failed"
        return None  # pragma: no cover - the last attempt never asks to wait
