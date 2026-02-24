"""Main entry point for the TikTok Python SDK.

Usage — async context manager (recommended)::

    async with TikTokClient(access_token="USER_ACCESS_TOKEN") as client:
        user = await client.display.get_user_info(
            fields=[UserField.DISPLAY_NAME, UserField.FOLLOWER_COUNT]
        )
        print(user.display_name, user.follower_count)

Usage — manual lifecycle management::

    client = TikTokClient(access_token="USER_ACCESS_TOKEN")
    try:
        creator = await client.content_posting.query_creator_info()
    finally:
        await client.aclose()
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from tiktok.apis.content_posting import ContentPostingAPI
from tiktok.apis.data_portability import DataPortabilityAPI
from tiktok.apis.display import DisplayAPI
from tiktok.config import DEFAULT_TIMEOUT
from tiktok.exceptions import TikTokConfigError
from tiktok.http.session import TikTokSession


class TikTokClient:
    """Async TikTok API client.

    Instantiate with a valid user access token obtained through your OAuth 2.0
    flow.  The SDK does **not** handle OAuth itself; token refresh must be
    managed externally.

    Parameters
    ----------
    access_token:
        TikTok user access token.
    timeout:
        Total HTTP request timeout in seconds (default: ``30.0``).

    Attributes:
        content_posting:  :class:`~tiktok.apis.content_posting.ContentPostingAPI`
        display:          :class:`~tiktok.apis.display.DisplayAPI`
        data_portability: :class:`~tiktok.apis.data_portability.DataPortabilityAPI`
    """

    def __init__(self, access_token: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        if not access_token:
            raise TikTokConfigError("access_token must not be empty.")

        self._session = TikTokSession(access_token=access_token, timeout=timeout)
        self.content_posting = ContentPostingAPI(self._session)
        self.display = DisplayAPI(self._session)
        self.data_portability = DataPortabilityAPI(self._session)

    # ------------------------------------------------------------------
    # Context manager support
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
    # Lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying HTTP session and release all connections.

        Call this when you are done with the client if you are **not** using
        it as an async context manager.
        """
        await self._session.aclose()
