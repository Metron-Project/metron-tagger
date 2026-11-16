"""Tests for MetronClient: rate limiting, retries and API error handling."""

from unittest.mock import ANY, Mock, patch

import pytest
import redis
import requests
from mokkari.exceptions import ApiError, RateLimitError
from mokkari.rate_limit import HeaderPacedRateLimiter

from metrontagger import __version__
from metrontagger.metron_client import MAX_API_ATTEMPTS, REDIS_SOCKET_TIMEOUT, MetronClient


@pytest.fixture
def client():
    """Create a MetronClient with a mocked API session."""
    with patch("metrontagger.metron_client.mokkari.api", return_value=Mock()):
        return MetronClient("my-token")


def create_http_api_error(status_code: int, message: str = "HTTP error") -> ApiError:
    """Create an ApiError chained to an HTTPError, mirroring what mokkari raises."""
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    http_error = requests.exceptions.HTTPError(response=response)
    api_error = ApiError(message)
    api_error.__cause__ = http_error
    return api_error


def test_client_initialization_with_username_only_used_for_redis():
    """Test a username isn't passed to mokkari, since Basic Auth is no longer used."""
    token = "my-token"  # noqa: S105
    with patch("metrontagger.metron_client.mokkari.api") as mock_api_func:
        MetronClient(token, username="user")
        mock_api_func.assert_called_once_with(
            user_agent=f"Metron-Tagger/{__version__}",
            api_token=token,
            rate_limiter=ANY,
        )
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )


@patch("metrontagger.ui.UIPresenter.print_warning")
def test_client_with_redis_url_without_username_falls_back(mock_warning):
    """Test Redis rate limiting is skipped without a username, even with an API token."""
    with (
        patch("redis.Redis.from_url") as mock_from_url,
        patch("metrontagger.metron_client.mokkari.api") as mock_api_func,
    ):
        MetronClient(
            "my-token",
            redis_url="redis://localhost:6379/0",
        )
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
        mock_from_url.assert_not_called()
    assert "Metron username" in mock_warning.call_args.args[0]


def test_client_with_redis_url_uses_redis_rate_limiter():
    """Test a reachable Redis URL builds a RedisRateLimiter for the API session."""
    mock_client = Mock()
    with (
        patch("redis.Redis.from_url", return_value=mock_client) as mock_from_url,
        patch("mokkari.redis_rate_limit.RedisRateLimiter") as mock_limiter_cls,
        patch("metrontagger.metron_client.mokkari.api") as mock_api_func,
    ):
        client = MetronClient(
            "my-token", username="user", redis_url="redis://localhost:6379/0"
        )
        mock_from_url.assert_called_once_with(
            "redis://localhost:6379/0",
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )
        mock_client.ping.assert_called_once_with()
        mock_limiter_cls.assert_called_once_with(mock_client, "user")
        assert mock_api_func.call_args.kwargs["rate_limiter"] is mock_limiter_cls.return_value

        client.close()
        mock_client.close.assert_called_once_with()


def test_client_with_redis_url_and_token_keys_by_username():
    """Test the Redis rate limiter is keyed by username, not the API token."""
    with (
        patch("redis.Redis.from_url", return_value=Mock()),
        patch("mokkari.redis_rate_limit.RedisRateLimiter") as mock_limiter_cls,
        patch("metrontagger.metron_client.mokkari.api"),
    ):
        MetronClient(
            "my-token",
            username="user",
            redis_url="redis://localhost:6379/0",
        )
        assert mock_limiter_cls.call_args.args[1] == "user"


@patch("metrontagger.ui.UIPresenter.print_warning")
def test_client_with_unreachable_redis_falls_back(mock_warning):
    """Test an unreachable Redis server falls back to the local rate limiter."""
    import redis  # noqa: PLC0415

    mock_client = Mock()
    mock_client.ping.side_effect = redis.ConnectionError("refused")
    with (
        patch("redis.Redis.from_url", return_value=mock_client),
        patch("metrontagger.metron_client.mokkari.api") as mock_api_func,
    ):
        client = MetronClient("my-token", username="user", redis_url="redis://localhost:1")
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
        mock_client.close.assert_called_once_with()
        assert client._redis_client is None
    assert "Unable to connect to Redis" in mock_warning.call_args.args[0]


@patch("metrontagger.ui.UIPresenter.print_warning")
def test_client_with_invalid_redis_url_falls_back(mock_warning):
    """Test an invalid Redis URL falls back to the local rate limiter."""
    with patch("metrontagger.metron_client.mokkari.api") as mock_api_func:
        MetronClient("my-token", username="user", redis_url="bogus://nowhere")
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
    assert "Invalid Redis URL" in mock_warning.call_args.args[0]


@patch("metrontagger.ui.UIPresenter.print_warning")
def test_client_without_redis_installed_falls_back(mock_warning):
    """Test a missing redis package falls back to the local rate limiter."""
    with (
        patch.dict("sys.modules", {"redis": None}),
        patch("metrontagger.metron_client.mokkari.api") as mock_api_func,
    ):
        MetronClient("my-token", username="user", redis_url="redis://localhost:6379/0")
        assert isinstance(
            mock_api_func.call_args.kwargs["rate_limiter"], HeaderPacedRateLimiter
        )
    assert "metron-tagger[redis]" in mock_warning.call_args.args[0]


def test_call_success(client):
    """Test successful API call."""
    mock_call = Mock(return_value="success")
    result = client.call(mock_call)
    assert result == "success"
    mock_call.assert_called_once()


def test_call_rate_limit_no_retry_after(client):
    """Test rate limit error with no retry_after attribute."""
    error = RateLimitError("Rate limit exceeded")
    mock_call = Mock(side_effect=error)

    result = client.call(mock_call)
    assert result is None
    mock_call.assert_called_once()


def test_call_rate_limit_zero_retry_after(client):
    """Test rate limit error with retry_after = 0."""
    error = RateLimitError("Rate limit exceeded", retry_after=0)
    mock_call = Mock(side_effect=error)

    result = client.call(mock_call)
    assert result is None
    mock_call.assert_called_once()


@patch("metrontagger.ui.UIPresenter.print_error")
def test_call_redis_error_stops_processing(mock_error, client):
    """Test a Redis rate limiter error stops further processing."""
    client._redis_errors = (redis.RedisError,)
    mock_call = Mock(side_effect=redis.ConnectionError("refused"))

    result = client.call(mock_call, "Failed to retrieve data")

    assert result is None
    assert client.stop_processing is True
    assert "Redis rate limiter error" in mock_error.call_args.args[0]


def test_call_redis_error_not_caught_without_redis(client):
    """Test Redis errors aren't swallowed when no Redis rate limiter is in use."""
    mock_call = Mock(side_effect=redis.ConnectionError("refused"))

    with pytest.raises(redis.ConnectionError):
        client.call(mock_call)


@patch("metrontagger.ui.UIPresenter.print_error")
@patch("metrontagger.metron_client.time.sleep")
def test_call_redis_error_on_retry_stops_processing(mock_sleep, mock_error, client):
    """Test a Redis error raised while retrying after a rate limit stops processing."""
    client._redis_errors = (redis.RedisError,)
    error = RateLimitError("Rate limit exceeded", retry_after=30)
    mock_call = Mock(side_effect=[error, redis.ConnectionError("refused")])

    result = client.call(mock_call)

    assert result is None
    assert client.stop_processing is True
    mock_sleep.assert_called_once_with(32)
    assert "Redis rate limiter error" in mock_error.call_args.args[0]


@patch("metrontagger.ui.UIPresenter.print_error")
@patch("metrontagger.metron_client.time.sleep")
def test_call_redis_error_on_second_retry_stops_processing(mock_sleep, mock_error, client):
    """Test a Redis error raised on the second short rate-limit retry stops processing."""
    client._redis_errors = (redis.RedisError,)
    mock_call = Mock(
        side_effect=[
            RateLimitError("Rate limit exceeded", retry_after=30),
            RateLimitError("Rate limit exceeded", retry_after=10),
            redis.ConnectionError("refused"),
        ]
    )

    result = client.call(mock_call)

    assert result is None
    assert client.stop_processing is True
    assert mock_call.call_count == 3
    assert mock_sleep.call_count == 2
    assert "Redis rate limiter error" in mock_error.call_args.args[0]


@patch("metrontagger.metron_client.time.sleep")
def test_call_rate_limit_short_delay_success(mock_sleep, client):
    """Test rate limit with short delay (< 60s) that succeeds on retry."""
    error = RateLimitError("Rate limit exceeded", retry_after=30)
    mock_call = Mock(side_effect=[error, "success"])

    result = client.call(mock_call)

    assert result == "success"
    mock_sleep.assert_called_once_with(32)
    assert mock_call.call_count == 2


@patch("metrontagger.metron_client.time.sleep")
def test_call_rate_limit_short_delay_retry_fails(mock_sleep, client):
    """Test rate limit with short delay (< 60s) that fails on retry."""
    error = RateLimitError("Rate limit exceeded", retry_after=45)
    retry_error = ApiError("API error on retry")
    mock_call = Mock(side_effect=[error, retry_error])

    result = client.call(mock_call)

    assert result is None
    mock_sleep.assert_called_once_with(47)
    assert mock_call.call_count == 2


@patch("metrontagger.metron_client.questionary.confirm")
@patch("metrontagger.metron_client.time.sleep")
@patch("metrontagger.metron_client.time.monotonic")
def test_call_rate_limit_long_delay_user_confirms_success(
    mock_monotonic, mock_sleep, mock_confirm, client
):
    """Test rate limit with long delay (>= 60s) where user confirms and retry succeeds."""
    mock_monotonic.side_effect = [1000.0, 1000.0]  # no time spent answering the prompt
    error = RateLimitError("Rate limit exceeded", retry_after=120)
    mock_call = Mock(side_effect=[error, "success"])
    mock_confirm.return_value.ask.return_value = True

    result = client.call(mock_call)

    assert result == "success"
    mock_sleep.assert_called_once_with(122)
    mock_confirm.assert_called_once()
    assert mock_call.call_count == 2
    assert client.stop_processing is False


@patch("metrontagger.metron_client.questionary.confirm")
@patch("metrontagger.metron_client.time.sleep")
@patch("metrontagger.metron_client.time.monotonic")
def test_call_rate_limit_long_delay_user_confirms_retry_fails(
    mock_monotonic, mock_sleep, mock_confirm, client
):
    """Test rate limit with long delay (>= 60s) where user confirms but retry fails."""
    mock_monotonic.side_effect = [1000.0, 1000.0]  # no time spent answering the prompt
    error = RateLimitError("Rate limit exceeded", retry_after=90)
    retry_error = RateLimitError("Still rate limited")
    mock_call = Mock(side_effect=[error, retry_error])
    mock_confirm.return_value.ask.return_value = True

    result = client.call(mock_call)

    assert result is None
    mock_sleep.assert_called_once_with(92)
    mock_confirm.assert_called_once()
    assert mock_call.call_count == 2
    assert client.stop_processing is False


@patch("metrontagger.metron_client.questionary.confirm")
@patch("metrontagger.metron_client.time.sleep")
@patch("metrontagger.metron_client.time.monotonic")
def test_call_rate_limit_long_delay_deducts_time_spent_answering(
    mock_monotonic, mock_sleep, mock_confirm, client
):
    """Time spent waiting for the user's answer is deducted from the retry sleep."""
    # 35 seconds pass between when retry_after is known and when the user answers.
    mock_monotonic.side_effect = [1000.0, 1035.0]
    error = RateLimitError("Rate limit exceeded", retry_after=120)
    mock_call = Mock(side_effect=[error, "success"])
    mock_confirm.return_value.ask.return_value = True

    result = client.call(mock_call)

    assert result == "success"
    # 120 - 35 elapsed + 2s buffer = 87
    mock_sleep.assert_called_once_with(87)


@patch("metrontagger.metron_client.questionary.confirm")
@patch("metrontagger.metron_client.time.sleep")
@patch("metrontagger.metron_client.time.monotonic")
def test_call_rate_limit_long_delay_answer_exceeds_retry_after(
    mock_monotonic, mock_sleep, mock_confirm, client
):
    """If the user takes longer than retry_after to answer, don't sleep a negative amount."""
    # 150 seconds pass, more than the 120s retry_after.
    mock_monotonic.side_effect = [1000.0, 1150.0]
    error = RateLimitError("Rate limit exceeded", retry_after=120)
    mock_call = Mock(side_effect=[error, "success"])
    mock_confirm.return_value.ask.return_value = True

    result = client.call(mock_call)

    assert result == "success"
    # elapsed already exceeds retry_after, so only the buffer remains
    mock_sleep.assert_called_once_with(2)


@patch("metrontagger.metron_client.questionary.confirm")
def test_call_rate_limit_long_delay_user_declines(mock_confirm, client):
    """Test rate limit with long delay (>= 60s) where user declines to wait."""
    error = RateLimitError("Rate limit exceeded", retry_after=300)
    mock_call = Mock(side_effect=error)
    mock_confirm.return_value.ask.return_value = False

    result = client.call(mock_call)

    assert result is None
    mock_confirm.assert_called_once()
    assert mock_call.call_count == 1
    assert client.stop_processing is True


def test_call_api_error(client):
    """Test handling of ApiError."""
    error = ApiError("API error occurred")
    mock_call = Mock(side_effect=error)

    result = client.call(mock_call, error_context="Test API call")

    assert result is None
    mock_call.assert_called_once()
    assert client.stop_processing is False


@pytest.mark.parametrize("status_code", [400, 401])
def test_call_fatal_http_error_stops_processing(client, status_code):
    """A 400 or 401 response should stop further tagging, not just this call."""
    error = create_http_api_error(status_code)
    mock_call = Mock(side_effect=error)

    result = client.call(mock_call, error_context="Test API call")

    assert result is None
    assert client.stop_processing is True


@pytest.mark.parametrize("status_code", [403, 404, 500, 503])
def test_call_non_fatal_http_error_does_not_stop_processing(client, status_code):
    """Other HTTP errors are logged but shouldn't halt processing of remaining files."""
    error = create_http_api_error(status_code)
    mock_call = Mock(side_effect=error)

    result = client.call(mock_call, error_context="Test API call")

    assert result is None
    assert client.stop_processing is False


def test_get_http_status_code_from_chained_http_error(client):
    """Status code is recovered from the HTTPError that ApiError was raised from."""
    error = create_http_api_error(401)
    assert client._get_http_status_code(error) == 401


def test_get_http_status_code_without_cause_returns_none(client):
    """An ApiError with no chained HTTPError (e.g. JSON decode failure) has no status code."""
    error = ApiError("Invalid JSON response")
    assert client._get_http_status_code(error) is None


# Retries: each test starts with a short rate limit, so the call is retried once.
SHORT_RATE_LIMIT = RateLimitError("Rate limit exceeded", retry_after=10)


@patch("metrontagger.metron_client.time.sleep")
def test_call_retry_success(mock_sleep, client):
    """A call that succeeds on the retry returns its result."""
    mock_call = Mock(side_effect=[SHORT_RATE_LIMIT, "retry success"])

    assert client.call(mock_call) == "retry success"
    assert mock_call.call_count == 2
    mock_sleep.assert_called_once_with(12)


@patch("metrontagger.ui.UIPresenter.print_error")
@patch("metrontagger.metron_client.time.sleep")
def test_call_retry_rate_limit_without_retry_after(mock_sleep, mock_error, client):
    """A rate limit on the retry with no usable retry_after isn't retried again."""
    mock_call = Mock(side_effect=[SHORT_RATE_LIMIT, RateLimitError("Still rate limited")])

    assert client.call(mock_call) is None
    assert mock_call.call_count == 2
    mock_sleep.assert_called_once_with(12)
    assert mock_error.call_args.args[0] == "Retry failed: Still rate limited"
    assert client.stop_processing is False


@patch("metrontagger.metron_client.questionary.confirm")
@patch("metrontagger.metron_client.time.sleep")
def test_call_retry_long_rate_limit_does_not_prompt(mock_sleep, mock_confirm, client):
    """Only the first rate limit can prompt; a long one on the retry just fails."""
    long_limit = RateLimitError("Rate limit exceeded", retry_after=300)
    mock_call = Mock(side_effect=[SHORT_RATE_LIMIT, long_limit])

    assert client.call(mock_call) is None
    assert mock_call.call_count == 2
    mock_sleep.assert_called_once_with(12)
    mock_confirm.assert_not_called()
    assert client.stop_processing is False


@patch("metrontagger.ui.UIPresenter.print_error")
@patch("metrontagger.metron_client.time.sleep")
def test_call_gives_up_after_max_attempts(mock_sleep, mock_error, client):
    """Short rate limits are retried at most MAX_API_ATTEMPTS times in total."""
    mock_call = Mock(side_effect=[SHORT_RATE_LIMIT] * (MAX_API_ATTEMPTS + 1))

    assert client.call(mock_call) is None
    assert mock_call.call_count == MAX_API_ATTEMPTS
    assert mock_sleep.call_count == MAX_API_ATTEMPTS - 1
    assert mock_error.call_args.args[0].startswith("Retry failed:")


@patch("metrontagger.ui.UIPresenter.print_error")
@patch("metrontagger.metron_client.time.sleep")
def test_call_retry_api_error(mock_sleep, mock_error, client):
    """A non-fatal ApiError on the retry is reported as a failed retry."""
    mock_call = Mock(side_effect=[SHORT_RATE_LIMIT, ApiError("API error")])

    assert client.call(mock_call, error_context="Failed to retrieve data") is None
    assert mock_call.call_count == 2
    mock_sleep.assert_called_once_with(12)
    assert mock_error.call_args.args[0] == "Retry failed: API error"
    assert client.stop_processing is False


@patch("metrontagger.ui.UIPresenter.print_error")
def test_call_api_error_message(mock_error, client):
    """An ApiError on the first attempt is reported with the call's context."""
    mock_call = Mock(side_effect=ApiError("API error"))

    assert client.call(mock_call, error_context="Failed to retrieve data") is None
    assert mock_error.call_args.args[0] == "Failed to retrieve data: API error"


@patch("metrontagger.metron_client.time.sleep")
def test_call_retry_fatal_http_error_stops_processing(mock_sleep, client):
    """A 401 hit during a retry should also stop further processing."""
    mock_call = Mock(side_effect=[SHORT_RATE_LIMIT, create_http_api_error(401)])

    assert client.call(mock_call) is None
    assert client.stop_processing is True
    mock_sleep.assert_called_once_with(12)


@patch("metrontagger.metron_client.time.sleep")
def test_call_fatal_http_error_after_second_short_rate_limit(mock_sleep, client):
    """A fatal error on the last attempt (after two short rate-limit waits) also stops."""
    mock_call = Mock(
        side_effect=[SHORT_RATE_LIMIT, SHORT_RATE_LIMIT, create_http_api_error(400)]
    )

    assert client.call(mock_call) is None
    assert client.stop_processing is True
    assert mock_call.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.parametrize("status_code", [520, 522, 524])
def test_get_http_status_code_non_standard_status_returns_none(client, status_code):
    """Cloudflare's non-standard 52x codes aren't HTTPStatus members."""
    assert client._get_http_status_code(create_http_api_error(status_code)) is None


@patch("metrontagger.ui.UIPresenter.print_error")
def test_call_non_standard_http_status_is_reported_not_raised(mock_error, client):
    """A Cloudflare 520 is reported as a failed call instead of crashing the run."""
    mock_call = Mock(side_effect=create_http_api_error(520, "Web server is down"))

    assert client.call(mock_call, error_context="Failed to retrieve data") is None
    assert client.stop_processing is False
    assert mock_error.call_args.args[0] == "Failed to retrieve data: Web server is down"


@patch("metrontagger.ui.UIPresenter.print_error", new=Mock())
def test_call_records_whether_it_failed(client):
    """last_call_failed tells a failed call apart from one that returned no data."""
    client.call(Mock(return_value="ok"))
    assert client.last_call_failed is False

    client.call(Mock(return_value=None))  # e.g. a 304 Not Modified
    assert client.last_call_failed is False

    client.call(Mock(side_effect=ApiError("Server error")))
    assert client.last_call_failed is True

    client.call(Mock(return_value="ok"))
    assert client.last_call_failed is False


@patch("metrontagger.ui.UIPresenter.print_error")
def test_unauthorized_message_points_at_api_token(mock_error, client):
    """A 401 sends the user to their API token; password auth no longer exists."""
    client.call(Mock(side_effect=create_http_api_error(401)))

    message = mock_error.call_args.args[0]
    assert "API token" in message
    assert "password" not in message
