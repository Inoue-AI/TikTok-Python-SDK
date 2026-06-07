"""Standalone async OAuth 2.0 client for TikTok user-token management.

This is intentionally separate from :class:`~tiktok.client.TikTokClient`: the
OAuth flow authenticates with the *application* ``client_key`` /
``client_secret`` pair (not a user access token), and is used precisely to
*obtain* the first user access token — at which point no user token exists yet.

Typical flow::

    oauth = TikTokOAuth(client_key="...", client_secret="...")
    try:
        # 1. Send the user to the authorization URL.
        url = oauth.build_authorization_url(
            redirect_uri="https://app.example.com/callback",
            scopes=["user.info.basic", "video.publish"],
            state="csrf-token",
        )
        # 2. After the redirect back, exchange the code for tokens.
        tokens = await oauth.exchange_code(
            code="server_received_code",
            redirect_uri="https://app.example.com/callback",
        )
        # 3. Later, refresh the (rotating) access token.
        tokens = await oauth.refresh_access_token(tokens.refresh_token)
    finally:
        await oauth.aclose()

Reference: https://developers.tiktok.com/doc/oauth-user-access-token-management
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlencode

import aiohttp

from tiktok.config import (
    DEFAULT_TIMEOUT,
    TIKTOK_API_BASE_URL,
    TIKTOK_AUTHORIZE_URL,
)
from tiktok.exceptions import TikTokConfigError, build_api_error
from tiktok.models.oauth import TokenResponse


class TikTokOAuth:
    """Async helper for the TikTok OAuth 2.0 user-token lifecycle.

    Parameters
    ----------
    client_key:
        TikTok application client key (also called ``client_id`` in some docs).
    client_secret:
        TikTok application client secret.
    timeout:
        Total HTTP request timeout in seconds (default: ``DEFAULT_TIMEOUT``).
    """

    def __init__(
        self,
        client_key: str,
        client_secret: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if not client_key:
            raise TikTokConfigError("client_key must not be empty.")
        if not client_secret:
            raise TikTokConfigError("client_secret must not be empty.")

        self._client_key = client_key
        self._client_secret = client_secret
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, ssl=True)
                self._session = aiohttp.ClientSession(connector=connector, timeout=self._timeout)
        return self._session

    async def aclose(self) -> None:
        """Close the underlying HTTP session and release all connections."""
        async with self._lock:
            if self._session is not None and not self._session.closed:
                await self._session.close()
                self._session = None

    # ------------------------------------------------------------------
    # Authorization URL (no network call)
    # ------------------------------------------------------------------

    def build_authorization_url(
        self,
        *,
        redirect_uri: str,
        scopes: list[str],
        state: str,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
        disable_auto_auth: bool | None = None,
    ) -> str:
        """Construct the URL to redirect a user to for consent.

        This performs no network call; it simply assembles the query string.

        Parameters
        ----------
        redirect_uri:
            Callback URL registered with your TikTok app.  Must match exactly.
        scopes:
            OAuth scopes to request (e.g. ``["user.info.basic", "video.publish"]``).
        state:
            Opaque value echoed back to the callback; use it for CSRF protection.
        code_challenge:
            PKCE code challenge.  Required for desktop/PKCE flows; omit for the
            standard server-side ``authorization_code`` flow.
        code_challenge_method:
            PKCE challenge method (default ``"S256"``).  Ignored when
            ``code_challenge`` is ``None``.
        disable_auto_auth:
            When ``True``, forces the consent screen even if the user has
            previously authorised the app.

        Returns:
            The fully-qualified authorization URL.
        """
        params: dict[str, str] = {
            "client_key": self._client_key,
            "response_type": "code",
            "scope": ",".join(scopes),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        if code_challenge is not None:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
        if disable_auto_auth is not None:
            params["disable_auto_auth"] = "1" if disable_auto_auth else "0"
        return f"{TIKTOK_AUTHORIZE_URL}?{urlencode(params)}"

    # ------------------------------------------------------------------
    # Token grants
    # ------------------------------------------------------------------

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> TokenResponse:
        """Exchange an authorization ``code`` for an access/refresh token pair.

        Parameters
        ----------
        code:
            The authorization code delivered to your ``redirect_uri``.
        redirect_uri:
            The same callback URL used to obtain ``code``.
        code_verifier:
            PKCE code verifier.  Required when the authorization URL was built
            with a ``code_challenge``.

        Returns:
            :class:`~tiktok.models.oauth.TokenResponse`.

        Raises:
            :class:`~tiktok.exceptions.TikTokAPIError`: The grant was rejected.
        """
        form: dict[str, str] = {
            "client_key": self._client_key,
            "client_secret": self._client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        if code_verifier is not None:
            form["code_verifier"] = code_verifier
        payload = await self._post_token(form)
        return TokenResponse.model_validate(payload)

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Exchange a refresh token for a fresh access/refresh token pair.

        TikTok rotates the refresh token on every refresh, so callers must
        persist the returned :attr:`~tiktok.models.oauth.TokenResponse.refresh_token`
        for the next cycle.

        Parameters
        ----------
        refresh_token:
            The refresh token previously issued to the user.

        Returns:
            :class:`~tiktok.models.oauth.TokenResponse` with the new tokens.

        Raises:
            :class:`~tiktok.exceptions.TikTokAPIError`: The refresh was rejected.
        """
        if not refresh_token:
            raise TikTokConfigError("refresh_token must not be empty.")
        form = {
            "client_key": self._client_key,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        payload = await self._post_token(form)
        return TokenResponse.model_validate(payload)

    async def revoke_access_token(self, access_token: str) -> None:
        """Revoke a user access token, invalidating the grant.

        Parameters
        ----------
        access_token:
            The user access token to revoke.

        Raises:
            :class:`~tiktok.exceptions.TikTokAPIError`: The revocation failed.
        """
        if not access_token:
            raise TikTokConfigError("access_token must not be empty.")
        form = {
            "client_key": self._client_key,
            "client_secret": self._client_secret,
            "token": access_token,
        }
        await self._post_form(f"{TIKTOK_API_BASE_URL}/v2/oauth/revoke/", form)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _post_token(self, form: dict[str, str]) -> dict[str, Any]:
        """POST the token endpoint and return the parsed flat JSON body."""
        return await self._post_form(f"{TIKTOK_API_BASE_URL}/v2/oauth/token/", form)

    async def _post_form(self, url: str, form: dict[str, str]) -> dict[str, Any]:
        """POST a ``x-www-form-urlencoded`` body and surface OAuth2 errors."""
        session = await self._get_session()
        async with session.post(
            url,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as response:
            payload: dict[str, Any] = await response.json(content_type=None)
            has_oauth_error = bool(payload.get("error"))
            if response.status >= 400 or has_oauth_error:
                raise build_api_error(
                    code=str(payload.get("error", "oauth_error")),
                    message=str(payload.get("error_description", "")),
                    log_id=str(payload.get("log_id", "")),
                    http_status=response.status,
                )
            return payload
