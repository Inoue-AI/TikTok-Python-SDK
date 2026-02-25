"""Display API namespace.

Wraps the following TikTok endpoints:

* ``GET  /v2/user/info/``    — user profile information
* ``POST /v2/video/list/``   — paginated list of the user's videos
* ``POST /v2/video/query/``  — fetch specific videos by ID

Reference: https://developers.tiktok.com/doc/display-api-overview
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from tiktok.apis.base import BaseAPI
from tiktok.config import TIKTOK_API_BASE_URL, VIDEO_LIST_MAX_COUNT, VIDEO_QUERY_MAX_IDS
from tiktok.exceptions import TikTokAPIError
from tiktok.models.display import (
    User,
    UserField,
    Video,
    VideoField,
    VideoListData,
    VideoQueryData,
)

_BASE = TIKTOK_API_BASE_URL


class DisplayAPI(BaseAPI):
    """Methods for reading TikTok user and video data.

    Requires an access token authorised with at minimum
    ``user.info.basic`` and/or ``video.list`` scopes depending on the
    method being called.
    """

    # ------------------------------------------------------------------
    # User info
    # ------------------------------------------------------------------

    async def get_user_info(self, fields: list[UserField]) -> User:
        """Retrieve profile information for the authenticated user.

        Parameters
        ----------
        fields:
            One or more :class:`~tiktok.models.display.UserField` values to
            include in the response.  Only requested fields will be populated
            on the returned :class:`~tiktok.models.display.User` object.

        Scope required: ``user.info.basic`` (plus ``user.info.profile`` and/or
        ``user.info.stats`` for the corresponding fields).

        Returns:
            :class:`~tiktok.models.display.User` with the requested fields.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        params: dict[str, Any] = {"fields": _join_fields(fields)}
        payload = await self._session.get(f"{_BASE}/v2/user/info/", params=params)
        return User.model_validate(payload["data"]["user"])

    # ------------------------------------------------------------------
    # Video list
    # ------------------------------------------------------------------

    async def list_videos(
        self,
        fields: list[VideoField],
        *,
        cursor: int | None = None,
        max_count: int = VIDEO_LIST_MAX_COUNT,
    ) -> VideoListData:
        """Return one page of the authenticated user's public videos.

        Videos are sorted by ``create_time`` in descending order (newest
        first).  Use :attr:`~tiktok.models.display.VideoListData.cursor`
        and :attr:`~tiktok.models.display.VideoListData.has_more` to
        paginate, or use :meth:`iter_videos` for an automatic async iterator.

        Parameters
        ----------
        fields:
            Video fields to include in each returned
            :class:`~tiktok.models.display.Video` object.
        cursor:
            Pagination cursor (UTC Unix timestamp in milliseconds) from the
            previous response.  Omit to start from the most recent video.
        max_count:
            Maximum number of videos per page (default: ``20``, max: ``20``).

        Scope required: ``video.list``

        Returns:
            :class:`~tiktok.models.display.VideoListData`.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        params: dict[str, Any] = {"fields": _join_fields(fields)}
        body: dict[str, Any] = {"max_count": max_count}
        if cursor is not None:
            body["cursor"] = cursor

        payload = await self._session.post(f"{_BASE}/v2/video/list/", json=body, params=params)
        return VideoListData.model_validate(payload["data"])

    async def iter_videos(
        self,
        fields: list[VideoField],
        *,
        max_count: int = VIDEO_LIST_MAX_COUNT,
    ) -> AsyncIterator[Video]:
        """Async generator that yields every video for the authenticated user.

        Automatically follows pagination cursors until all videos have been
        yielded.

        Parameters
        ----------
        fields:
            Video fields to include in each yielded
            :class:`~tiktok.models.display.Video` object.
        max_count:
            Page size for each internal request (default: ``20``).

        Scope required: ``video.list``

        Yields:
            :class:`~tiktok.models.display.Video` instances.

        Example::

            async for video in client.display.iter_videos([VideoField.ID, VideoField.TITLE]):
                print(video.id, video.title)
        """
        cursor: int | None = None
        while True:
            page = await self.list_videos(fields, cursor=cursor, max_count=max_count)
            for video in page.videos:
                yield video
            if not page.has_more:
                break
            cursor = page.cursor

    # ------------------------------------------------------------------
    # Video query
    # ------------------------------------------------------------------

    async def query_videos(
        self,
        video_ids: list[str],
        fields: list[VideoField],
    ) -> VideoQueryData:
        """Fetch metadata for specific videos by their IDs.

        The authenticated user must own all requested videos.  Up to
        ``VIDEO_QUERY_MAX_IDS`` (20) IDs may be requested per call.

        Parameters
        ----------
        video_ids:
            List of video IDs to look up (1 - 20 items).
        fields:
            Video fields to include in the response.

        Scope required: ``video.list``

        Returns:
            :class:`~tiktok.models.display.VideoQueryData`.

        Raises:
            :class:`~tiktok.exceptions.TikTokAPIError`:
                If ``video_ids`` is empty or exceeds ``VIDEO_QUERY_MAX_IDS``.
        """
        if not video_ids:
            raise TikTokAPIError(
                code="invalid_params",
                message="video_ids must contain at least one ID.",
                log_id="",
            )
        if len(video_ids) > VIDEO_QUERY_MAX_IDS:
            raise TikTokAPIError(
                code="invalid_params",
                message=(
                    f"video_ids may contain at most {VIDEO_QUERY_MAX_IDS} IDs "
                    f"per request; {len(video_ids)} were provided."
                ),
                log_id="",
            )

        params: dict[str, Any] = {"fields": _join_fields(fields)}
        payload = await self._session.post(
            f"{_BASE}/v2/video/query/",
            json={"filters": {"video_ids": video_ids}},
            params=params,
        )
        return VideoQueryData.model_validate(payload["data"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _join_fields(fields: list[UserField] | list[VideoField]) -> str:
    """Serialise a list of field enums into a comma-separated string."""
    return ",".join(f.value for f in fields)
