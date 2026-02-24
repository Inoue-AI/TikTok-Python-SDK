"""Abstract base class shared by all API namespace classes."""

from __future__ import annotations

from tiktok.http.session import TikTokSession


class BaseAPI:
    """Holds a reference to the shared HTTP session.

    All concrete API classes inherit from this so that the session is
    accessible via ``self._session`` without repetitive constructor code.
    """

    __slots__ = ("_session",)

    def __init__(self, session: TikTokSession) -> None:
        self._session = session
