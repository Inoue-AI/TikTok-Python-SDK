"""Tests for the exception hierarchy and error-mapping helper."""

from __future__ import annotations

import pytest

from tiktok.client import TikTokClient
from tiktok.exceptions import (
    TikTokAPIError,
    TikTokAuthError,
    TikTokConfigError,
    TikTokNotFoundError,
    TikTokRateLimitError,
    TikTokServerError,
    build_api_error,
)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("access_token_invalid", TikTokAuthError),
        ("access_token_expired", TikTokAuthError),
        ("scope_not_authorized", TikTokAuthError),
        ("permission_denied", TikTokAuthError),
        ("rate_limit_exceeded", TikTokRateLimitError),
        ("spam_risk_too_many_posts", TikTokRateLimitError),
        ("resource_not_found", TikTokNotFoundError),
        ("internal_error", TikTokServerError),
        ("server_error", TikTokServerError),
        ("some_unknown_code", TikTokAPIError),
    ],
)
def test_build_api_error_maps_code_to_subclass(code: str, expected: type[TikTokAPIError]) -> None:
    err = build_api_error(code=code, message="m", log_id="L", http_status=400)
    assert type(err) is expected
    assert err.code == code
    assert err.log_id == "L"
    assert err.http_status == 400


def test_build_api_error_5xx_unknown_code_is_server_error() -> None:
    # An unknown code with a 5xx status should be promoted to TikTokServerError.
    err = build_api_error(code="weird", message="boom", log_id="L", http_status=503)
    assert isinstance(err, TikTokServerError)


def test_api_error_str_contains_code_and_log_id() -> None:
    err = build_api_error(code="rate_limit_exceeded", message="slow down", log_id="LID")
    text = str(err)
    assert "rate_limit_exceeded" in text
    assert "slow down" in text
    assert "LID" in text


def test_client_rejects_empty_access_token() -> None:
    with pytest.raises(TikTokConfigError):
        TikTokClient(access_token="")


@pytest.mark.asyncio
async def test_client_aclose_is_idempotent() -> None:
    client = TikTokClient(access_token="act.x")
    await client.aclose()  # No session was ever created.
    await client.aclose()  # Second call must not raise.
