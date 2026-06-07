"""Tests for the standalone OAuth 2.0 client."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest
from aioresponses import aioresponses

from tiktok.config import TIKTOK_API_BASE_URL, TIKTOK_AUTHORIZE_URL
from tiktok.exceptions import TikTokAPIError, TikTokConfigError
from tiktok.models.oauth import TokenResponse
from tiktok.oauth import TikTokOAuth

_URL_TOKEN = re.compile(rf"^{re.escape(TIKTOK_API_BASE_URL)}/v2/oauth/token/")
_URL_REVOKE = re.compile(rf"^{re.escape(TIKTOK_API_BASE_URL)}/v2/oauth/revoke/")

CLIENT_KEY = "test_client_key"
CLIENT_SECRET = "test_client_secret"


@pytest.fixture
async def oauth() -> TikTokOAuth:  # type: ignore[misc]
    async with TikTokOAuth(client_key=CLIENT_KEY, client_secret=CLIENT_SECRET) as o:
        yield o


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------


def test_empty_client_key_raises() -> None:
    with pytest.raises(TikTokConfigError):
        TikTokOAuth(client_key="", client_secret=CLIENT_SECRET)


def test_empty_client_secret_raises() -> None:
    with pytest.raises(TikTokConfigError):
        TikTokOAuth(client_key=CLIENT_KEY, client_secret="")


# ---------------------------------------------------------------------------
# build_authorization_url (no network call)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_authorization_url(oauth: TikTokOAuth) -> None:
    url = oauth.build_authorization_url(
        redirect_uri="https://app.example.com/callback",
        scopes=["user.info.basic", "video.publish"],
        state="csrf123",
    )
    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == TIKTOK_AUTHORIZE_URL
    qs = parse_qs(parsed.query)
    assert qs["client_key"] == [CLIENT_KEY]
    assert qs["response_type"] == ["code"]
    assert qs["scope"] == ["user.info.basic,video.publish"]
    assert qs["redirect_uri"] == ["https://app.example.com/callback"]
    assert qs["state"] == ["csrf123"]
    # PKCE params absent unless requested.
    assert "code_challenge" not in qs


@pytest.mark.asyncio
async def test_build_authorization_url_with_pkce(oauth: TikTokOAuth) -> None:
    url = oauth.build_authorization_url(
        redirect_uri="https://app.example.com/callback",
        scopes=["user.info.basic"],
        state="s",
        code_challenge="abc123challenge",
        disable_auto_auth=True,
    )
    qs = parse_qs(urlparse(url).query)
    assert qs["code_challenge"] == ["abc123challenge"]
    assert qs["code_challenge_method"] == ["S256"]
    assert qs["disable_auto_auth"] == ["1"]


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exchange_code_success(oauth: TikTokOAuth) -> None:
    token_payload = {
        "access_token": "act.NEW",
        "expires_in": 86400,
        "refresh_token": "rft.NEXT",
        "refresh_expires_in": 31536000,
        "open_id": "open_abc",
        "scope": "user.info.basic,video.publish",
        "token_type": "Bearer",
    }
    with aioresponses() as mock:
        mock.post(_URL_TOKEN, payload=token_payload)
        result = await oauth.exchange_code(
            code="auth_code_xyz",
            redirect_uri="https://app.example.com/callback",
        )

    assert isinstance(result, TokenResponse)
    assert result.access_token == "act.NEW"
    assert result.refresh_token == "rft.NEXT"
    assert result.open_id == "open_abc"
    assert result.expires_in == 86400


@pytest.mark.asyncio
async def test_exchange_code_with_pkce_verifier(oauth: TikTokOAuth) -> None:
    token_payload = {
        "access_token": "act.A",
        "expires_in": 100,
        "refresh_token": "rft.B",
        "refresh_expires_in": 200,
        "open_id": "o",
        "scope": "user.info.basic",
        "token_type": "Bearer",
    }
    with aioresponses() as mock:
        mock.post(_URL_TOKEN, payload=token_payload)
        result = await oauth.exchange_code(
            code="c",
            redirect_uri="https://app.example.com/callback",
            code_verifier="verifier123",
        )
    assert result.access_token == "act.A"


@pytest.mark.asyncio
async def test_exchange_code_oauth_error(oauth: TikTokOAuth) -> None:
    error_payload = {
        "error": "invalid_grant",
        "error_description": "Authorization code is invalid or expired.",
        "log_id": "log_err_1",
    }
    with aioresponses() as mock:
        mock.post(_URL_TOKEN, payload=error_payload, status=400)
        with pytest.raises(TikTokAPIError) as exc_info:
            await oauth.exchange_code(code="bad", redirect_uri="https://x/cb")

    assert exc_info.value.code == "invalid_grant"
    assert exc_info.value.log_id == "log_err_1"
    assert exc_info.value.http_status == 400


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_access_token_success(oauth: TikTokOAuth) -> None:
    token_payload = {
        "access_token": "act.REFRESHED",
        "expires_in": 86400,
        "refresh_token": "rft.ROTATED",
        "refresh_expires_in": 31536000,
        "open_id": "open_abc",
        "scope": "user.info.basic",
        "token_type": "Bearer",
    }
    with aioresponses() as mock:
        mock.post(_URL_TOKEN, payload=token_payload)
        result = await oauth.refresh_access_token("rft.OLD")

    assert result.access_token == "act.REFRESHED"
    # TikTok rotates the refresh token — the new one must be surfaced.
    assert result.refresh_token == "rft.ROTATED"


@pytest.mark.asyncio
async def test_refresh_access_token_empty_token_raises(oauth: TikTokOAuth) -> None:
    with pytest.raises(TikTokConfigError):
        await oauth.refresh_access_token("")


@pytest.mark.asyncio
async def test_refresh_access_token_error_status_200(oauth: TikTokOAuth) -> None:
    # TikTok sometimes returns OAuth2 errors with a 200 status; the SDK must
    # still treat a populated "error" field as a failure.
    error_payload = {
        "error": "invalid_request",
        "error_description": "refresh_token is invalid.",
        "log_id": "L2",
    }
    with aioresponses() as mock:
        mock.post(_URL_TOKEN, payload=error_payload, status=200)
        with pytest.raises(TikTokAPIError) as exc_info:
            await oauth.refresh_access_token("rft.bad")

    assert exc_info.value.code == "invalid_request"


# ---------------------------------------------------------------------------
# revoke_access_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_access_token_success(oauth: TikTokOAuth) -> None:
    with aioresponses() as mock:
        mock.post(_URL_REVOKE, payload={}, status=200)
        # Should complete without raising.
        await oauth.revoke_access_token("act.to_revoke")


@pytest.mark.asyncio
async def test_revoke_access_token_empty_raises(oauth: TikTokOAuth) -> None:
    with pytest.raises(TikTokConfigError):
        await oauth.revoke_access_token("")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aclose_is_idempotent() -> None:
    o = TikTokOAuth(client_key=CLIENT_KEY, client_secret=CLIENT_SECRET)
    await o.aclose()  # No session was ever created.
    await o.aclose()  # Second call must not raise.
