"""Content Posting API namespace.

Wraps the following TikTok endpoints:

* ``POST /v2/post/publish/creator_info/query/``
* ``POST /v2/post/publish/video/init/``          (direct post)
* ``POST /v2/post/publish/inbox/video/init/``    (inbox / draft)
* ``PUT  {upload_url}``                          (chunk upload)
* ``POST /v2/post/publish/content/init/``        (photo post)
* ``POST /v2/post/publish/status/fetch/``        (post status)

Reference: https://developers.tiktok.com/doc/content-posting-api-get-started
"""

from __future__ import annotations

import asyncio
import math
import os
from typing import Any

from tiktok.apis.base import BaseAPI
from tiktok.config import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_POLL_TIMEOUT,
    DEFAULT_VIDEO_CHUNK_SIZE,
    TIKTOK_API_BASE_URL,
)
from tiktok.exceptions import TikTokAPIError
from tiktok.models.content_posting import (
    CreatorInfo,
    PhotoInitData,
    PostStatus,
    PostStatusData,
    PrivacyLevel,
    VideoContentType,
    VideoInitData,
    VideoSource,
)

_BASE = TIKTOK_API_BASE_URL

# Terminal states: no further status changes will occur.
_TERMINAL_STATUSES = {PostStatus.PUBLISH_COMPLETE, PostStatus.FAILED}


class ContentPostingAPI(BaseAPI):
    """Methods for creating and monitoring TikTok posts.

    Requires an access token authorised with either the ``video.publish``
    scope (direct post) or ``video.upload`` scope (inbox / draft upload).
    """

    # ------------------------------------------------------------------
    # Creator info
    # ------------------------------------------------------------------

    async def query_creator_info(self) -> CreatorInfo:
        """Return capability information about the authenticated creator.

        Use the returned :class:`~tiktok.models.content_posting.CreatorInfo`
        to determine which :class:`~tiktok.models.content_posting.PrivacyLevel`
        options are available before constructing a post request.

        Scope required: ``video.publish``

        Returns:
            A :class:`~tiktok.models.content_posting.CreatorInfo` instance.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        payload = await self._session.post_no_body(f"{_BASE}/v2/post/publish/creator_info/query/")
        return CreatorInfo.model_validate(payload["data"])

    # ------------------------------------------------------------------
    # Direct post - video
    # ------------------------------------------------------------------

    async def init_video_post(
        self,
        *,
        privacy_level: PrivacyLevel,
        source: VideoSource,
        title: str | None = None,
        disable_duet: bool | None = None,
        disable_stitch: bool | None = None,
        disable_comment: bool | None = None,
        video_cover_timestamp_ms: int | None = None,
        brand_content_toggle: bool | None = None,
        brand_organic_toggle: bool | None = None,
        is_aigc: bool | None = None,
        # FILE_UPLOAD fields
        video_size: int | None = None,
        chunk_size: int | None = None,
        total_chunk_count: int | None = None,
        # PULL_FROM_URL fields
        video_url: str | None = None,
    ) -> VideoInitData:
        """Initialise a direct video post and obtain an upload token.

        Parameters
        ----------
        privacy_level:
            Who can view the video.  Must be one of the values returned by
            :meth:`query_creator_info`.
        source:
            ``VideoSource.FILE_UPLOAD`` to push binary data via
            :meth:`upload_video_chunk`, or ``VideoSource.PULL_FROM_URL`` to
            have TikTok download the video from a public URL.
        title:
            Post caption (max 2 200 UTF-16 code units).  Supports ``#hashtags``
            and ``@mentions``.
        disable_duet:
            Prevent other users from creating duets with this video.
        disable_stitch:
            Prevent other users from stitching this video.
        disable_comment:
            Disable the comments section for this video.
        video_cover_timestamp_ms:
            Frame position (milliseconds) to use as the cover thumbnail.
        brand_content_toggle:
            Set ``True`` for paid partnership / branded content.
        brand_organic_toggle:
            Set ``True`` when promoting the creator's own brand organically.
        is_aigc:
            Set ``True`` to label the video as AI-generated content.
        video_size:
            Total file size in bytes - required for ``FILE_UPLOAD``.
        chunk_size:
            Size of each chunk in bytes - required for ``FILE_UPLOAD``.
        total_chunk_count:
            Number of chunks - required for ``FILE_UPLOAD``.
        video_url:
            Publicly accessible video URL - required for ``PULL_FROM_URL``.

        Returns:
            :class:`~tiktok.models.content_posting.VideoInitData` containing
            ``publish_id`` and (for ``FILE_UPLOAD``) ``upload_url``.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        post_info: dict[str, Any] = {"privacy_level": privacy_level.value}
        if title is not None:
            post_info["title"] = title
        if disable_duet is not None:
            post_info["disable_duet"] = disable_duet
        if disable_stitch is not None:
            post_info["disable_stitch"] = disable_stitch
        if disable_comment is not None:
            post_info["disable_comment"] = disable_comment
        if video_cover_timestamp_ms is not None:
            post_info["video_cover_timestamp_ms"] = video_cover_timestamp_ms
        if brand_content_toggle is not None:
            post_info["brand_content_toggle"] = brand_content_toggle
        if brand_organic_toggle is not None:
            post_info["brand_organic_toggle"] = brand_organic_toggle
        if is_aigc is not None:
            post_info["is_aigc"] = is_aigc

        source_info = _build_video_source_info(
            source=source,
            video_size=video_size,
            chunk_size=chunk_size,
            total_chunk_count=total_chunk_count,
            video_url=video_url,
        )

        payload = await self._session.post(
            f"{_BASE}/v2/post/publish/video/init/",
            json={"post_info": post_info, "source_info": source_info},
        )
        return VideoInitData.model_validate(payload["data"])

    # ------------------------------------------------------------------
    # Inbox / draft video
    # ------------------------------------------------------------------

    async def init_inbox_video(
        self,
        *,
        source: VideoSource,
        video_size: int | None = None,
        chunk_size: int | None = None,
        total_chunk_count: int | None = None,
        video_url: str | None = None,
    ) -> VideoInitData:
        """Initialise an inbox (draft) video upload.

        Sends the video to the creator's TikTok inbox so they can review and
        publish it themselves.  No ``post_info`` is required.

        Parameters
        ----------
        source:
            Upload method - ``FILE_UPLOAD`` or ``PULL_FROM_URL``.
        video_size:
            Total file size in bytes (``FILE_UPLOAD`` only).
        chunk_size:
            Chunk size in bytes (``FILE_UPLOAD`` only).
        total_chunk_count:
            Number of chunks (``FILE_UPLOAD`` only).
        video_url:
            Public video URL (``PULL_FROM_URL`` only).

        Scope required: ``video.upload``

        Returns:
            :class:`~tiktok.models.content_posting.VideoInitData`.

        Raises:
            :class:`~tiktok.exceptions.TikTokAuthError`: Token lacks scope.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        source_info = _build_video_source_info(
            source=source,
            video_size=video_size,
            chunk_size=chunk_size,
            total_chunk_count=total_chunk_count,
            video_url=video_url,
        )
        payload = await self._session.post(
            f"{_BASE}/v2/post/publish/inbox/video/init/",
            json={"source_info": source_info},
        )
        return VideoInitData.model_validate(payload["data"])

    # ------------------------------------------------------------------
    # Chunk upload
    # ------------------------------------------------------------------

    async def upload_video_chunk(
        self,
        upload_url: str,
        *,
        data: bytes,
        start_byte: int,
        total_bytes: int,
        content_type: VideoContentType = VideoContentType.MP4,
    ) -> None:
        """Upload a single video chunk to TikTok's upload server.

        Parameters
        ----------
        upload_url:
            The pre-signed URL from :meth:`init_video_post` or
            :meth:`init_inbox_video`.
        data:
            Raw bytes for this chunk.
        start_byte:
            Zero-based offset of the first byte in this chunk.
        total_bytes:
            Total size of the complete video file in bytes.
        content_type:
            MIME type of the video file.

        Raises:
            :class:`~tiktok.exceptions.TikTokUploadError`: HTTP-level failure.
        """
        end_byte = start_byte + len(data) - 1
        content_range = f"bytes {start_byte}-{end_byte}/{total_bytes}"
        await self._session.put_chunk(
            upload_url,
            data=data,
            content_type=content_type.value,
            content_range=content_range,
        )

    async def upload_video_file(
        self,
        upload_url: str,
        file_path: str,
        *,
        content_type: VideoContentType = VideoContentType.MP4,
        chunk_size: int = DEFAULT_VIDEO_CHUNK_SIZE,
    ) -> None:
        """Upload an entire video file from disk, handling chunking automatically.

        Parameters
        ----------
        upload_url:
            The pre-signed URL from :meth:`init_video_post` or
            :meth:`init_inbox_video`.
        file_path:
            Absolute or relative path to the video file.
        content_type:
            MIME type of the video file (default: ``video/mp4``).
        chunk_size:
            Maximum bytes per chunk (default: ``DEFAULT_VIDEO_CHUNK_SIZE``).

        Raises:
            :class:`~tiktok.exceptions.TikTokUploadError`: Any chunk fails.
            :exc:`FileNotFoundError`: *file_path* does not exist.
        """
        total_bytes = os.path.getsize(file_path)
        with open(file_path, "rb") as fh:
            start = 0
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                await self.upload_video_chunk(
                    upload_url,
                    data=chunk,
                    start_byte=start,
                    total_bytes=total_bytes,
                    content_type=content_type,
                )
                start += len(chunk)

    # ------------------------------------------------------------------
    # Convenience: post video from URL (direct post)
    # ------------------------------------------------------------------

    async def post_video_from_url(
        self,
        video_url: str,
        *,
        privacy_level: PrivacyLevel,
        title: str | None = None,
        disable_duet: bool | None = None,
        disable_stitch: bool | None = None,
        disable_comment: bool | None = None,
        video_cover_timestamp_ms: int | None = None,
        brand_content_toggle: bool | None = None,
        brand_organic_toggle: bool | None = None,
        is_aigc: bool | None = None,
    ) -> VideoInitData:
        """Direct-post a video by URL in a single call.

        Convenience wrapper around :meth:`init_video_post` that sets
        ``source=VideoSource.PULL_FROM_URL`` automatically.

        Returns:
            :class:`~tiktok.models.content_posting.VideoInitData` with
            ``publish_id`` for use with :meth:`get_post_status`.
        """
        return await self.init_video_post(
            privacy_level=privacy_level,
            source=VideoSource.PULL_FROM_URL,
            title=title,
            disable_duet=disable_duet,
            disable_stitch=disable_stitch,
            disable_comment=disable_comment,
            video_cover_timestamp_ms=video_cover_timestamp_ms,
            brand_content_toggle=brand_content_toggle,
            brand_organic_toggle=brand_organic_toggle,
            is_aigc=is_aigc,
            video_url=video_url,
        )

    # ------------------------------------------------------------------
    # Convenience: post video from file (direct post)
    # ------------------------------------------------------------------

    async def post_video_from_file(
        self,
        file_path: str,
        *,
        privacy_level: PrivacyLevel,
        title: str | None = None,
        disable_duet: bool | None = None,
        disable_stitch: bool | None = None,
        disable_comment: bool | None = None,
        video_cover_timestamp_ms: int | None = None,
        brand_content_toggle: bool | None = None,
        brand_organic_toggle: bool | None = None,
        is_aigc: bool | None = None,
        content_type: VideoContentType = VideoContentType.MP4,
        chunk_size: int = DEFAULT_VIDEO_CHUNK_SIZE,
    ) -> VideoInitData:
        """Direct-post a video from a local file, handling the full upload flow.

        Calls :meth:`init_video_post` then :meth:`upload_video_file`
        automatically.  After this method returns the post is processing;
        use :meth:`get_post_status` or :meth:`wait_for_post_completion`
        to monitor its progress.

        Parameters
        ----------
        file_path:
            Path to the video file on disk.
        privacy_level:
            Visibility of the resulting post.
        title:
            Post caption (max 2 200 UTF-16 code units).
        content_type:
            MIME type of the video (default: ``video/mp4``).
        chunk_size:
            Upload chunk size in bytes.

        Returns:
            :class:`~tiktok.models.content_posting.VideoInitData`.

        Raises:
            :exc:`FileNotFoundError`: *file_path* does not exist.
            :class:`~tiktok.exceptions.TikTokUploadError`: Upload failure.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any other API error.
        """
        total_bytes = os.path.getsize(file_path)
        total_chunks = math.ceil(total_bytes / chunk_size)

        init_data = await self.init_video_post(
            privacy_level=privacy_level,
            source=VideoSource.FILE_UPLOAD,
            title=title,
            disable_duet=disable_duet,
            disable_stitch=disable_stitch,
            disable_comment=disable_comment,
            video_cover_timestamp_ms=video_cover_timestamp_ms,
            brand_content_toggle=brand_content_toggle,
            brand_organic_toggle=brand_organic_toggle,
            is_aigc=is_aigc,
            video_size=total_bytes,
            chunk_size=chunk_size,
            total_chunk_count=total_chunks,
        )

        assert init_data.upload_url is not None, (
            "TikTok did not return an upload_url for FILE_UPLOAD source."
        )

        await self.upload_video_file(
            init_data.upload_url,
            file_path,
            content_type=content_type,
            chunk_size=chunk_size,
        )
        return init_data

    # ------------------------------------------------------------------
    # Photo post
    # ------------------------------------------------------------------

    async def post_photos(
        self,
        photo_image_urls: list[str],
        *,
        privacy_level: PrivacyLevel,
        photo_cover_index: int = 0,
        title: str | None = None,
        description: str | None = None,
        disable_comment: bool | None = None,
        auto_add_music: bool | None = None,
    ) -> PhotoInitData:
        """Direct-post a photo carousel.

        Parameters
        ----------
        photo_image_urls:
            Publicly accessible URLs of the photo images (1 - 35 items).
        privacy_level:
            Visibility of the post.
        photo_cover_index:
            Zero-based index of the photo to use as the cover (default: ``0``).
        title:
            Post title.
        description:
            Post description / caption.
        disable_comment:
            Disable comments on the post.
        auto_add_music:
            Let TikTok automatically add background music.

        Scope required: ``video.publish``

        Returns:
            :class:`~tiktok.models.content_posting.PhotoInitData` with
            ``publish_id`` for use with :meth:`get_post_status`.

        Raises:
            :class:`~tiktok.exceptions.TikTokAPIError`: Any API error.
        """
        post_info: dict[str, Any] = {"privacy_level": privacy_level.value}
        if title is not None:
            post_info["title"] = title
        if description is not None:
            post_info["description"] = description
        if disable_comment is not None:
            post_info["disable_comment"] = disable_comment
        if auto_add_music is not None:
            post_info["auto_add_music"] = auto_add_music

        source_info: dict[str, Any] = {
            "source": "PULL_FROM_URL",
            "photo_cover_index": photo_cover_index,
            "photo_images": photo_image_urls,
        }

        payload = await self._session.post(
            f"{_BASE}/v2/post/publish/content/init/",
            json={
                "post_info": post_info,
                "source_info": source_info,
                "post_mode": "DIRECT_POST",
                "media_type": "PHOTO",
            },
        )
        return PhotoInitData.model_validate(payload["data"])

    # ------------------------------------------------------------------
    # Post status
    # ------------------------------------------------------------------

    async def get_post_status(self, publish_id: str) -> PostStatusData:
        """Fetch the current processing status of a publish action.

        Parameters
        ----------
        publish_id:
            The ``publish_id`` returned by an ``/init/`` endpoint.

        Scope required: ``video.publish`` or ``video.upload``

        Returns:
            :class:`~tiktok.models.content_posting.PostStatusData`.

        Raises:
            :class:`~tiktok.exceptions.TikTokAPIError`: Any API error.
        """
        payload = await self._session.post(
            f"{_BASE}/v2/post/publish/status/fetch/",
            json={"publish_id": publish_id},
        )
        return PostStatusData.model_validate(payload["data"])

    async def wait_for_post_completion(
        self,
        publish_id: str,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        timeout: float = DEFAULT_POLL_TIMEOUT,
    ) -> PostStatusData:
        """Poll :meth:`get_post_status` until the post reaches a terminal state.

        A "terminal state" is either :attr:`PostStatus.PUBLISH_COMPLETE` or
        :attr:`PostStatus.FAILED`.

        Parameters
        ----------
        publish_id:
            The ``publish_id`` to monitor.
        poll_interval:
            Seconds between each status check (default: ``3.0``).
        timeout:
            Maximum total seconds to wait before raising :exc:`TimeoutError`
            (default: ``300.0``).

        Returns:
            The final :class:`~tiktok.models.content_posting.PostStatusData`.

        Raises:
            :exc:`TimeoutError`: The post did not complete within *timeout*.
            :class:`~tiktok.exceptions.TikTokAPIError`: Any API error.
        """
        elapsed = 0.0
        while elapsed < timeout:
            status_data = await self.get_post_status(publish_id)
            if status_data.status in _TERMINAL_STATUSES:
                return status_data
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Post {publish_id!r} did not reach a terminal state within {timeout}s.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_video_source_info(
    *,
    source: VideoSource,
    video_size: int | None,
    chunk_size: int | None,
    total_chunk_count: int | None,
    video_url: str | None,
) -> dict[str, Any]:
    """Construct the ``source_info`` dict for video init endpoints."""
    if source is VideoSource.FILE_UPLOAD:
        if video_size is None or chunk_size is None or total_chunk_count is None:
            raise TikTokAPIError(
                code="invalid_params",
                message=(
                    "video_size, chunk_size, and total_chunk_count are required "
                    "when source is FILE_UPLOAD."
                ),
                log_id="",
            )
        return {
            "source": source.value,
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        }
    else:  # PULL_FROM_URL
        if video_url is None:
            raise TikTokAPIError(
                code="invalid_params",
                message="video_url is required when source is PULL_FROM_URL.",
                log_id="",
            )
        return {
            "source": source.value,
            "video_url": video_url,
        }
